"""Mark click position on screenshots to see what it would hit."""
import cv2
from pathlib import Path

CLICK_POS = (3165, 1843)  # Handshake flow click position

frames = [
    "082558_165_c001679_WORLD_stam113.png",  # WORLD view before castle popup
    "082559_102_c001680_UNKNOWN_stam113.png",  # Castle popup
]

for fname in frames:
    path = Path(f"C:/Users/mail/xclash/screenshots/debug/recent_issue/{fname}")
    frame = cv2.imread(str(path))

    # Draw big red circle at click position
    cv2.circle(frame, CLICK_POS, 50, (0, 0, 255), 5)
    cv2.circle(frame, CLICK_POS, 10, (0, 0, 255), -1)  # Center dot
    cv2.putText(frame, f"CLICK ({CLICK_POS[0]}, {CLICK_POS[1]})",
                (CLICK_POS[0]-150, CLICK_POS[1]-70),
                cv2.FONT_HERSHEY_SIMPLEX, 1.5, (0, 0, 255), 3)

    out_path = Path(f"C:/Users/mail/xclash/screenshots/debug/{fname.replace('.png', '_CLICK.png')}")
    cv2.imwrite(str(out_path), frame)
    print(f"Saved: {out_path}")
