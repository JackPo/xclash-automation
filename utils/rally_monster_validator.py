"""
Rally Monster Validator - OCR and validation for rally monster icons.

Extracts monster icon relative to plus button position, uses OCR to read
monster name and level, validates against configuration rules.

Supports DATA GATHERING MODE to collect monster samples for OCR tuning.
"""

from pathlib import Path
import cv2
import re
from typing import Tuple, Optional
from datetime import datetime


class RallyMonsterValidator:
    """Validates rally monsters using OCR and configuration rules."""

    # Monster icon offset relative to plus button
    # Plus button at (1905, 477) → Monster icon to the LEFT and ABOVE
    # Corrected offset (monster is LEFT of plus, not right)
    MONSTER_OFFSET_X = 235  # Monster is 235px LEFT of plus (was wrongly +735)
    MONSTER_OFFSET_Y = -151  # Monster is 151px ABOVE plus
    MONSTER_WIDTH = 290
    MONSTER_HEIGHT = 363

    def __init__(self, ocr_client, monsters_config: list, data_gathering_mode: bool = False):
        """
        Initialize validator.

        Args:
            ocr_client: OCRClient instance for text extraction
            monsters_config: List of monster dicts from RALLY_MONSTERS config
            data_gathering_mode: If True, save crops to matched/unknown subfolders
        """
        self.ocr = ocr_client
        self.monsters_config = monsters_config
        self.data_gathering_mode = data_gathering_mode

        # Create data gathering directories if needed
        if self.data_gathering_mode:
            self.data_dir = Path(__file__).parent.parent / "data_gathering"
            self.matched_dir = self.data_dir / "matched"
            self.unknown_dir = self.data_dir / "unknown"

            self.data_dir.mkdir(exist_ok=True)
            self.matched_dir.mkdir(exist_ok=True)
            self.unknown_dir.mkdir(exist_ok=True)

            print(f"[RALLY] Data gathering mode ENABLED")
            print(f"  Matched monsters → {self.matched_dir}")
            print(f"  Unknown monsters → {self.unknown_dir}")

    def get_monster_region(self, plus_x: int, plus_y: int) -> Tuple[int, int, int, int]:
        """
        Calculate monster icon region from plus button position.

        Args:
            plus_x: X coordinate of plus button top-left
            plus_y: Y coordinate of plus button top-left

        Returns:
            (x, y, w, h) - Monster icon bounding box
        """
        monster_x = plus_x + self.MONSTER_OFFSET_X
        monster_y = plus_y + self.MONSTER_OFFSET_Y
        return monster_x, monster_y, self.MONSTER_WIDTH, self.MONSTER_HEIGHT

    def validate_monster(self, frame, plus_x: int, plus_y: int, rally_index: int = 0) -> Tuple[bool, Optional[str], Optional[int], str]:
        """
        OCR and validate monster at position.

        Args:
            frame: BGR screenshot from WindowsScreenshotHelper
            plus_x: X coordinate of plus button
            plus_y: Y coordinate of plus button
            rally_index: Index of this rally in the list (for data gathering filenames)

        Returns:
            (should_join, monster_name, level, raw_ocr_text)
            - should_join: True if monster matches config rules
            - monster_name: Parsed monster name (or None if OCR failed)
            - level: Parsed level number (or None if OCR failed)
            - raw_ocr_text: Raw text from OCR for logging
        """
        # Calculate monster icon region
        monster_x, monster_y, monster_w, monster_h = self.get_monster_region(plus_x, plus_y)

        # Extract monster icon crop
        monster_crop = frame[monster_y:monster_y+monster_h, monster_x:monster_x+monster_w]

        # OCR the monster icon with specific prompt (expects JSON response)
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

    def _parse_monster_text(self, raw_text: str) -> Tuple[Optional[str], Optional[int]]:
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

    def _should_join_rally(self, monster_name: str, level: int) -> Tuple[bool, bool]:
        """
        Check if monster matches configuration rules.

        Args:
            monster_name: Parsed monster name (lowercase)
            level: Parsed level number

        Returns:
            (should_join, is_known_monster)
            - should_join: True if auto_join enabled AND level <= max_level
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
                if level <= max_level:
                    return True, True  # Known and should join
                else:
                    return False, True  # Known but level too high

        # No match found - UNKNOWN monster
        return False, False

    def _save_monster_sample(self, monster_crop, rally_index: int, plus_x: int, plus_y: int,
                              monster_name: str, level: int, subfolder: str):
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
