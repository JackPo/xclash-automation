"""
Rally Monster Validator - Template matching and OCR for rally monster icons.

Extracts monster icon relative to plus button position. Uses template matching
first for speed, falls back to OCR if no template match found. Automatically
saves new OCR results as templates for future matching.

Supports DATA GATHERING MODE to collect monster samples for OCR tuning.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any

import cv2
import numpy as np
import numpy.typing as npt
import re
from datetime import datetime

if TYPE_CHECKING:
    from utils.ocr_client import OCRClient

logger = logging.getLogger(__name__)

# Template directory for cached monster icons
MONSTER_TEMPLATE_DIR = Path(__file__).parent.parent / "templates" / "ground_truth" / "rally_monsters"

# Live template cache - reloads when directory changes
# Stores BGR float32 templates for fast numpy SSD comparison (5x faster than cv2.matchTemplate)
_template_cache: dict[str, npt.NDArray[Any]] = {}
_template_dir_mtime: float = 0.0


def _load_monster_templates() -> dict[str, npt.NDArray[Any]]:
    """
    Load monster templates as BGR float32 for fast matching.

    Returns dict mapping template name (e.g., "elite_zombie_24") to BGR float32 array.
    Using numpy SSD on same-size images is 5x faster than cv2.matchTemplate.
    """
    global _template_cache, _template_dir_mtime

    if not MONSTER_TEMPLATE_DIR.exists():
        return {}

    # Check if directory modified (new templates added)
    try:
        current_mtime = MONSTER_TEMPLATE_DIR.stat().st_mtime
    except OSError:
        return _template_cache

    if current_mtime != _template_dir_mtime:
        # Reload all templates as BGR float32
        _template_cache = {}
        for path in MONSTER_TEMPLATE_DIR.glob("*.png"):
            name = path.stem  # e.g., "elite_zombie_24"
            template = cv2.imread(str(path))
            if template is not None:
                _template_cache[name] = template.astype(np.float32)
        _template_dir_mtime = current_mtime
        if _template_cache:
            logger.info(f"Loaded {len(_template_cache)} monster templates from {MONSTER_TEMPLATE_DIR}")

    return _template_cache


def _try_template_match(monster_crop: npt.NDArray[Any], templates: dict[str, npt.NDArray[Any]],
                        threshold: float = 10.0) -> tuple[str, int] | None:
    """
    Try to match monster crop against cached templates using numpy MSE.

    Uses numpy instead of cv2.matchTemplate for 5x speed improvement on same-size images.

    Args:
        monster_crop: BGR image of monster icon (290×363)
        templates: Dict mapping template name to BGR float32 image
        threshold: MSE threshold (lower = stricter). ~50 is good for exact match.

    Returns:
        (monster_name, level) if matched, None otherwise.
    """
    if not templates:
        return None

    best_match = None
    best_score = threshold  # Must beat this threshold

    # Convert crop to float32 once
    crop_f32 = monster_crop.astype(np.float32)

    for template_name, template in templates.items():
        # Skip if shapes don't match
        if crop_f32.shape != template.shape:
            continue

        # Fast numpy MSE (5x faster than cv2.matchTemplate for same-size)
        diff = crop_f32 - template
        mse = np.mean(diff * diff)

        if mse < best_score:
            best_score = mse
            best_match = template_name

    if best_match:
        # Parse "elite_zombie_24" -> ("elite zombie", 24)
        parts = best_match.rsplit("_", 1)
        if len(parts) == 2 and parts[1].isdigit():
            name = parts[0].replace("_", " ")
            level = int(parts[1])
            logger.info(f"Template matched: {name} Lv{level} (mse={best_score:.1f})")
            return (name, level)

    return None


def _save_as_template(monster_crop: npt.NDArray[Any], name: str, level: int) -> None:
    """
    Save OCR'd crop as template for future matching.

    Args:
        monster_crop: BGR image of monster icon
        name: Monster name from OCR
        level: Monster level from OCR
    """
    MONSTER_TEMPLATE_DIR.mkdir(parents=True, exist_ok=True)

    # Sanitize name: "Elite Zombie" -> "elite_zombie"
    safe_name = name.lower().replace(" ", "_").replace("-", "_")
    filename = f"{safe_name}_{level}.png"
    path = MONSTER_TEMPLATE_DIR / filename

    if not path.exists():  # Don't overwrite existing
        cv2.imwrite(str(path), monster_crop)
        logger.info(f"Saved new monster template: {filename}")


class RallyMonsterValidator:
    """Validates rally monsters using OCR and configuration rules."""

    # Monster icon offset relative to plus button CENTER
    # Note: rally_plus_matcher.find_all_plus_buttons() returns CENTER coordinates
    # Monster region is offset from that center position
    MONSTER_OFFSET_X = 235   # Pixels to the RIGHT of plus button center
    MONSTER_OFFSET_Y = -151  # Pixels ABOVE plus button center (negative = up)
    MONSTER_WIDTH = 290
    MONSTER_HEIGHT = 363

    def __init__(self, ocr_client: OCRClient, monsters_config: list[dict[str, Any]], data_gathering_mode: bool = False,
                 ignore_daily_limit: bool = False) -> None:
        """
        Initialize validator.

        Args:
            ocr_client: OCRClient instance for text extraction
            monsters_config: List of monster dicts from RALLY_MONSTERS config
            data_gathering_mode: If True, save crops to matched/unknown subfolders
            ignore_daily_limit: If True, skip exhaustion checks (e.g., during special events)
        """
        self.ocr = ocr_client
        self.monsters_config = monsters_config
        self.data_gathering_mode = data_gathering_mode
        self.ignore_daily_limit = ignore_daily_limit

        # Create data gathering directories if needed
        if self.data_gathering_mode:
            self.data_dir = Path(__file__).parent.parent / "data_gathering"
            self.matched_dir = self.data_dir / "matched"
            self.unknown_dir = self.data_dir / "unknown"

            self.data_dir.mkdir(exist_ok=True)
            self.matched_dir.mkdir(exist_ok=True)
            self.unknown_dir.mkdir(exist_ok=True)

            print(f"[RALLY] Data gathering mode ENABLED")
            print(f"  Matched monsters -> {self.matched_dir}")
            print(f"  Unknown monsters -> {self.unknown_dir}")

    def get_monster_region(self, plus_x: int, plus_y: int) -> tuple[int, int, int, int]:
        """
        Calculate monster icon region from plus button position.

        Args:
            plus_x: X coordinate of plus button CENTER
            plus_y: Y coordinate of plus button CENTER

        Returns:
            (x, y, w, h) - Monster icon bounding box
        """
        monster_x = plus_x + self.MONSTER_OFFSET_X
        monster_y = plus_y + self.MONSTER_OFFSET_Y
        return monster_x, monster_y, self.MONSTER_WIDTH, self.MONSTER_HEIGHT

    def validate_monster(self, frame: npt.NDArray[Any], plus_x: int, plus_y: int, rally_index: int = 0) -> tuple[bool, str | None, int | None, str]:
        """
        Validate monster at position using template matching first, OCR fallback.

        Args:
            frame: BGR screenshot from WindowsScreenshotHelper
            plus_x: X coordinate of plus button CENTER
            plus_y: Y coordinate of plus button CENTER
            rally_index: Index of this rally in the list (for data gathering filenames)

        Returns:
            (should_join, monster_name, level, raw_ocr_text)
            - should_join: True if monster matches config rules
            - monster_name: Parsed monster name (or None if detection failed)
            - level: Parsed level number (or None if detection failed)
            - raw_ocr_text: Raw text from OCR or "(template)" for logging
        """
        # Calculate monster icon region
        monster_x, monster_y, monster_w, monster_h = self.get_monster_region(plus_x, plus_y)

        # Extract monster icon crop
        monster_crop = frame[monster_y:monster_y+monster_h, monster_x:monster_x+monster_w]

        # ========== STEP 1: Try template matching first (fast) ==========
        templates = _load_monster_templates()
        template_match = _try_template_match(monster_crop, templates)

        if template_match:
            monster_name, level = template_match
            raw_text = "(template)"
        else:
            # ========== STEP 2: Fall back to OCR (slow) ==========
            try:
                from config import OCR_PROMPT_RALLY_MONSTER
                monster_data = self.ocr.extract_json(monster_crop, prompt=OCR_PROMPT_RALLY_MONSTER)

                if not monster_data:
                    print(f"    [RALLY] OCR returned invalid JSON for rally {rally_index}")
                    # Save to unknown/ if data gathering enabled
                    if self.data_gathering_mode:
                        self._save_monster_sample(monster_crop, rally_index, plus_x, plus_y,
                                                  "json-parse-error", 0, "unknown")
                    return False, None, None, "(json-parse-error)"

                # Extract fields from JSON
                monster_name = monster_data.get("name", "").lower().strip()
                level = monster_data.get("level")

                # Convert level to int if it's a string
                if isinstance(level, str):
                    level = int(level) if level.isdigit() else None

                raw_text = str(monster_data)  # For logging

                # ========== STEP 3: Save as template for future matching ==========
                if monster_name and level is not None:
                    _save_as_template(monster_crop, monster_name, level)

            except Exception as e:
                print(f"    [RALLY] OCR failed for rally {rally_index}: {e}")
                # Save to unknown/ if data gathering enabled
                if self.data_gathering_mode:
                    self._save_monster_sample(monster_crop, rally_index, plus_x, plus_y,
                                              "error", 0, "unknown")
                return False, None, None, f"(error: {e})"

            if not monster_name:
                print(f"    [RALLY] Failed to parse monster name from: {raw_text!r}")
                # Save to unknown/ if data gathering enabled
                if self.data_gathering_mode:
                    self._save_monster_sample(monster_crop, rally_index, plus_x, plus_y,
                                              "parse-failed", 0, "unknown")
                return False, None, None, raw_text

            if level is None:
                print(f"    [RALLY] Failed to parse level from: {raw_text!r}")
                # Save to unknown/ if data gathering enabled (use level=0 as placeholder)
                if self.data_gathering_mode:
                    self._save_monster_sample(monster_crop, rally_index, plus_x, plus_y,
                                              monster_name, 0, "unknown")
                return False, monster_name, None, raw_text

        # Validate against config rules
        should_join, is_known = self._should_join_rally(monster_name, level)

        # Data gathering mode: Save crop to matched/ or unknown/
        if self.data_gathering_mode:
            subfolder = "matched" if is_known else "unknown"
            self._save_monster_sample(monster_crop, rally_index, plus_x, plus_y,
                                      monster_name, level, subfolder)

        return should_join, monster_name, level, raw_text

    def _parse_monster_text(self, raw_text: str) -> tuple[str | None, int | None]:
        """
        Parse monster name and level from OCR text.

        Expected formats:
        - "Lv.100\\nZombie Overlord"
        - "ATK\\nLv.100\\nZombie Overlord"
        - "Elite Zombie\\nLevel 50"

        Args:
            raw_text: Raw OCR text

        Returns:
            (monster_name, level) - Parsed values or (None, None) if parsing fails
        """
        # Split by newlines
        lines = [line.strip() for line in raw_text.split('\n') if line.strip()]

        # Extract level using regex
        level = None
        level_pattern = r"(?:Lv\.?|Level)\s*(\d+)"
        for line in lines:
            match = re.search(level_pattern, line, re.IGNORECASE)
            if match:
                level = int(match.group(1))
                break

        # Extract monster name (all non-level, non-ATK lines)
        name_lines = []
        for line in lines:
            # Skip lines that are just level indicators
            if re.match(r"^(?:Lv\.?|Level)\s*\d+$", line, re.IGNORECASE):
                continue
            # Skip ATK/DEF indicators
            if line.upper() in ["ATK", "DEF", "ATTACK", "DEFENSE"]:
                continue
            # Remove level pattern from line (e.g. "Zombie Overlord Lv.130" → "Zombie Overlord")
            cleaned_line = re.sub(r"\s*(?:Lv\.?|Level)\s*\d+", "", line, flags=re.IGNORECASE).strip()
            if cleaned_line:
                name_lines.append(cleaned_line)

        # Join remaining lines as monster name
        if not name_lines:
            return None, level

        monster_name = " ".join(name_lines)
        # Normalize: lowercase, strip whitespace
        monster_name = monster_name.lower().strip()

        return monster_name, level

    def _should_join_rally(self, monster_name: str, level: int) -> tuple[bool, bool]:
        """
        Check if monster matches configuration rules.

        Args:
            monster_name: Parsed monster name (lowercase)
            level: Parsed level number

        Returns:
            (should_join, is_known_monster)
            - should_join: True if auto_join enabled AND level <= max_level AND not exhausted
            - is_known_monster: True if monster name matches config (for data gathering)
        """
        # Match against configured monsters (case-insensitive)
        for monster in self.monsters_config:
            config_name = monster["name"].lower().strip()

            # Check if monster name matches (exact or substring)
            if monster_name == config_name or config_name in monster_name:
                # Found match - this is a KNOWN monster
                is_known = True

                # Check auto_join flag
                auto_join_enabled = monster.get("auto_join", True)
                if not auto_join_enabled:
                    return False, True  # Known but don't join

                # Check level requirement
                max_level = monster.get("max_level", float('inf'))
                if level > max_level:
                    return False, True  # Known but level too high

                # Check daily exhaustion (only for monsters with track_daily_limit=True)
                # Skip this check if ignore_daily_limit is set (e.g., during Winter Fest)
                if monster.get("track_daily_limit", False) and not self.ignore_daily_limit:
                    from utils.scheduler import get_scheduler
                    scheduler = get_scheduler()
                    limit_name = f"rally_{config_name.lower().replace(' ', '_')}"
                    if scheduler.is_exhausted(limit_name):
                        print(f"    [RALLY] {monster['name']} is exhausted for today, skipping")
                        return False, True  # Known but exhausted

                return True, True  # Known and should join

        # No match found - UNKNOWN monster
        return False, False

    def _save_monster_sample(self, monster_crop: npt.NDArray[Any], rally_index: int, plus_x: int, plus_y: int,
                              monster_name: str, level: int, subfolder: str) -> None:
        """
        Save monster crop to data_gathering/matched/ or data_gathering/unknown/

        Filename format: monster_{name}_lv{level}_{timestamp}_rally{idx}_x{x}_y{y}.png
        Example: monster_zombie-overlord_lv120_20251203_161054_rally0_x1905_y477.png

        Args:
            monster_crop: BGR image of monster icon
            rally_index: Index of rally in list
            plus_x: Plus button X coordinate
            plus_y: Plus button Y coordinate
            monster_name: Parsed monster name (or "unknown"/"error"/"parse-failed")
            level: Parsed level number (or 0 if unknown)
            subfolder: "matched" or "unknown"
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        # Sanitize monster name for filename
        safe_name = monster_name.replace(" ", "-").replace("_", "-").lower()

        filename = f"monster_{safe_name}_lv{level}_{timestamp}_rally{rally_index}_x{plus_x}_y{plus_y}.png"

        # Save to matched/ or unknown/ subfolder
        save_dir = self.matched_dir if subfolder == "matched" else self.unknown_dir
        filepath = save_dir / filename

        cv2.imwrite(str(filepath), monster_crop)
        print(f"    [DATA-GATHER-{subfolder.upper()}] Saved: {filename}")
