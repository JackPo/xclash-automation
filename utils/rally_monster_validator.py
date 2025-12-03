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

    # Monster icon offset relative to plus button (from docs/joining_rallies.md)
    # Plus button example: (1405, 477)
    # Monster icon example: (2140, 326)
    # Offset: X = 2140 - 1405 = +735, Y = 326 - 477 = -151
    MONSTER_OFFSET_X = 735
    MONSTER_OFFSET_Y = -151
    MONSTER_WIDTH = 290
    MONSTER_HEIGHT = 363

    def __init__(self, ocr_client, valid_monsters: dict, data_gathering_mode: bool = False):
        """
        Initialize validator.

        Args:
            ocr_client: OCRClient instance for text extraction
            valid_monsters: Dict of {monster_name: max_level} from config
            data_gathering_mode: If True, save all monster crops to data_gathering/ folder
        """
        self.ocr = ocr_client
        self.valid_monsters = valid_monsters
        self.data_gathering_mode = data_gathering_mode

        # Create data gathering directory if needed
        if self.data_gathering_mode:
            self.data_dir = Path(__file__).parent.parent / "data_gathering"
            self.data_dir.mkdir(exist_ok=True)
            print(f"[RALLY] Data gathering mode ENABLED - saving monsters to {self.data_dir}")

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

        # Data gathering mode: Save crop to disk
        if self.data_gathering_mode:
            self._save_monster_sample(monster_crop, rally_index, plus_x, plus_y)

        # OCR the monster icon
        try:
            raw_text = self.ocr.extract_text(monster_crop)
            if not raw_text or not raw_text.strip():
                print(f"    [RALLY] OCR returned empty text for rally {rally_index}")
                return False, None, None, "(empty)"

        except Exception as e:
            print(f"    [RALLY] OCR failed for rally {rally_index}: {e}")
            return False, None, None, f"(error: {e})"

        # Parse monster name and level
        monster_name, level = self._parse_monster_text(raw_text)

        if not monster_name:
            print(f"    [RALLY] Failed to parse monster name from: {raw_text!r}")
            return False, None, None, raw_text

        if level is None:
            print(f"    [RALLY] Failed to parse level from: {raw_text!r}")
            return False, monster_name, None, raw_text

        # Validate against config rules
        should_join = self._should_join_rally(monster_name, level)

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
            name_lines.append(line)

        # Join remaining lines as monster name
        if not name_lines:
            return None, level

        monster_name = " ".join(name_lines)
        # Normalize: lowercase, strip whitespace
        monster_name = monster_name.lower().strip()

        return monster_name, level

    def _should_join_rally(self, monster_name: str, level: int) -> bool:
        """
        Check if monster matches configuration rules.

        Args:
            monster_name: Parsed monster name (lowercase)
            level: Parsed level number

        Returns:
            True if should join this rally
        """
        # Match against valid monsters (case-insensitive)
        for config_monster, max_level in self.valid_monsters.items():
            config_monster_lower = config_monster.lower().strip()

            # Check if monster name matches
            if monster_name == config_monster_lower or config_monster_lower in monster_name:
                # Check level requirement
                if level <= max_level:
                    return True

        return False

    def _save_monster_sample(self, monster_crop, rally_index: int, plus_x: int, plus_y: int):
        """
        Save monster crop to data_gathering folder for OCR tuning.

        Filename format: monster_YYYYMMDD_HHMMSS_rallyN_xXXXX_yYYYY.png

        Args:
            monster_crop: BGR image of monster icon
            rally_index: Index of rally in list
            plus_x: Plus button X coordinate
            plus_y: Plus button Y coordinate
        """
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"monster_{timestamp}_rally{rally_index}_x{plus_x}_y{plus_y}.png"
        filepath = self.data_dir / filename

        cv2.imwrite(str(filepath), monster_crop)
        print(f"    [DATA-GATHER] Saved monster sample: {filename}")
