# World/Town View Detection (4K)

This document describes the view detection logic used by `utils/view_state_detector.py`.

## Button semantics
The button shows the DESTINATION, not the current view:
- If you are in WORLD, the button shows TOWN.
- If you are in TOWN, the button shows WORLD.

The detector returns the CURRENT view by inverting the button template match.

## Detection details
- Resolution: 3840x2160
- Screenshot source: `WindowsScreenshotHelper` (not ADB)
- Template matching: `TM_SQDIFF_NORMED`, threshold 0.05

### World/Town toggle button
- Region: (3600, 1920) size 240x240
- Templates:
  - `world_button_4k.png` -> current view is TOWN
  - `town_button_4k.png` -> current view is WORLD
  - `town_button_zoomed_out_4k.png` -> current view is WORLD
- Click position: (3720, 2040)

### Chat detection
- Chat header region: (1854, 36) size 123x59
- Template: `chat_header_4k.png`
- If chat is detected, the navigator clicks back to exit.

## Navigation behavior
`navigate_to()`:
- If current view is CHAT, click back and re-detect.
- If current view is TOWN and target is WORLD, click toggle.
- If current view is WORLD and target is TOWN, click toggle.
- If UNKNOWN, attempt safe ground/grass clicks, then back button.

## Related files
- `utils/view_state_detector.py`
- `utils/safe_grass_matcher.py`
- `utils/safe_ground_matcher.py`
