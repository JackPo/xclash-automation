"""
Verify Rally Monster OCR Offset Bug

Bug #2 from SUGGESTIONS.MD:
- rally_plus_matcher.py returns CENTER coordinates (line 42)
- rally_monster_validator.py expects TOP-LEFT coordinates (docstring lines 63-64)
- Offset is +235 but comment says monster is LEFT of plus

This script takes a screenshot and draws boxes to visually verify:
1. Plus button positions (from find_all_plus_buttons)
2. Monster crop regions (as calculated by get_monster_region)
"""
import sys
from pathlib import Path

# Add parent dirs to path
script_dir = Path(__file__).parent.parent.parent
if str(script_dir) not in sys.path:
    sys.path.insert(0, str(script_dir))

import cv2
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.rally_plus_matcher import RallyPlusMatcher
from utils.rally_monster_validator import RallyMonsterValidator

OUTPUT_DIR = script_dir / "screenshots" / "debug" / "rally_offset_verify"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def main():
    print("=== Rally Offset Verification ===")
    print()

    # Take screenshot
    win = WindowsScreenshotHelper()
    frame = win.get_screenshot_cv2()
    if frame is None:
        print("ERROR: Failed to capture screenshot")
        return

    print(f"Screenshot: {frame.shape}")

    # Find plus buttons
    plus_matcher = RallyPlusMatcher()
    plus_buttons = plus_matcher.find_all_plus_buttons(frame)

    print(f"Found {len(plus_buttons)} plus button(s)")
    if not plus_buttons:
        print("No plus buttons found. Make sure Union War panel is open.")
        # Save screenshot anyway
        out_path = OUTPUT_DIR / "no_plus_buttons.png"
        cv2.imwrite(str(out_path), frame)
        print(f"Saved: {out_path}")
        return

    # Create annotated copy
    annotated = frame.copy()

    # Create a dummy validator just to use get_monster_region
    class DummyOCR:
        def extract_json(self, *args, **kwargs):
            return {}

    validator = RallyMonsterValidator(DummyOCR(), [], data_gathering_mode=False)

    for i, (px, py, score) in enumerate(plus_buttons):
        print(f"\nPlus button {i}: ({px}, {py}) score={score:.4f}")

        # Plus button region (assuming center coords)
        # Plus button is 130x130
        plus_half_w, plus_half_h = 65, 65
        plus_x1 = px - plus_half_w
        plus_y1 = py - plus_half_h
        plus_x2 = px + plus_half_w
        plus_y2 = py + plus_half_h

        print(f"  Plus button rect (assuming CENTER): ({plus_x1}, {plus_y1}) to ({plus_x2}, {plus_y2})")

        # Draw plus button in GREEN
        cv2.rectangle(annotated, (plus_x1, plus_y1), (plus_x2, plus_y2), (0, 255, 0), 3)
        cv2.putText(annotated, f"Plus {i}", (plus_x1, plus_y1 - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

        # Monster region (what validator calculates)
        mx, my, mw, mh = validator.get_monster_region(px, py)
        print(f"  Monster region: ({mx}, {my}, {mw}, {mh})")
        print(f"  Monster rect: ({mx}, {my}) to ({mx+mw}, {my+mh})")

        # Draw monster region in RED
        cv2.rectangle(annotated, (mx, my), (mx+mw, my+mh), (0, 0, 255), 3)
        cv2.putText(annotated, f"Monster {i}", (mx, my - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)

        # Also show what region would be if we treated coords as TOP-LEFT
        # (adjust offset calculation)
        mx_topleft = px + validator.MONSTER_OFFSET_X
        my_topleft = py + validator.MONSTER_OFFSET_Y
        print(f"  If TOP-LEFT: ({mx_topleft}, {my_topleft}) to ({mx_topleft+mw}, {my_topleft+mh})")

        # Draw alternative in YELLOW (dashed effect via thickness)
        cv2.rectangle(annotated, (mx_topleft, my_topleft), (mx_topleft+mw, my_topleft+mh), (0, 255, 255), 2)
        cv2.putText(annotated, f"Alt {i}", (mx_topleft, my_topleft - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)

    # Add legend
    legend_y = 50
    cv2.putText(annotated, "GREEN = Plus button (assuming CENTER coords)", (50, legend_y),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
    cv2.putText(annotated, "RED = Monster region (current calc)", (50, legend_y + 40),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
    cv2.putText(annotated, "YELLOW = Alt region (if TOP-LEFT)", (50, legend_y + 80),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

    # Save
    out_path = OUTPUT_DIR / "rally_offset_verify.png"
    cv2.imwrite(str(out_path), annotated)
    print(f"\nSaved annotated screenshot: {out_path}")
    print("\nPlease open this image to visually verify:")
    print("- RED box should cover the monster icon")
    print("- If RED box is misaligned, there's a bug")
    print("- If RED box is correct, documentation needs updating")

if __name__ == "__main__":
    main()
