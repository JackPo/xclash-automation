import cv2
import numpy as np
from pathlib import Path

buttons_dir = Path("templates/buttons")
town_full = cv2.imread(str(buttons_dir / "town_button_template.png"))
world_full = cv2.imread(str(buttons_dir / "world_button_template.png"))

if town_full is None or world_full is None:
    raise SystemExit("Missing button templates")

h, w = town_full.shape[:2]
segment_width = w // 2

town_segment = town_full[:, :segment_width]
world_segment = world_full[:, segment_width:]

cv2.imwrite(str(buttons_dir / "town_segment_template.png"), town_segment)
cv2.imwrite(str(buttons_dir / "world_segment_template.png"), world_segment)

print("Saved segment templates.")
