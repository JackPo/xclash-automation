# Claude Instructions for xclash Project

X-Clash automation using BlueStacks emulator. 4K resolution (3840x2160).

## Skills Reference

| Skill | Use For |
|-------|---------|
| `/screenshot-detection` | Detect UI elements, extract templates, Gemini detection |
| `/template-catalog` | Template positions, sizes, thresholds, click coordinates |
| `/daemon-flow` | Run flows, zombie mode, titles, daemon internals |

---

## CRITICAL RULES

### 1. NEVER Analyze Screenshots Directly

Use Gemini via `calibration/detect_object.py`:

```bash
python calibration/detect_object.py screenshot.png "description of element"
```

### 2. ALWAYS Use WindowsScreenshotHelper

ADB screenshots have different pixel values and WILL NOT match templates.

```python
from utils.windows_screenshot_helper import WindowsScreenshotHelper

win = WindowsScreenshotHelper()
frame = win.get_screenshot_cv2()  # BGR numpy array, 3840x2160
```

**Rules**:
- Detection/matching: `WindowsScreenshotHelper`
- Template capture: `WindowsScreenshotHelper`
- Actions (tap, swipe): `ADBHelper`

### 3. Use Centralized Template Matching

```python
from utils.template_matcher import match_template

found, score, center = match_template(frame, "button_4k.png", threshold=0.05)
if found:
    adb.tap(*center)  # center is already the click position!
```

---

## Project Context

- ADB: `C:\Program Files\BlueStacks_nxt\hd-adb.exe`
- Device: `emulator-5554`
- Resolution: 3840x2160 (4K)
- OCR: Qwen3-VL-2B-Instruct (bf16) on GPU via `services/ocr_server.py`

## Directory Structure

```
screenshots/debug/     - Debug screenshots
scripts/flows/         - Automation flows
scripts/one_off/       - One-off scripts
logs/                  - Daemon logs (current_daemon.log)
templates/ground_truth/ - All template images
utils/                 - Utilities and matchers
config.py              - Tracked defaults
config_local.py        - Gitignored user overrides
```

---

## Configuration Files

| File | Purpose | Git |
|------|---------|-----|
| `config.py` | Defaults (positions, thresholds) | Tracked |
| `config_local.py` | User overrides (API keys) | Gitignored |

**User-specific** → `config_local.py`: API keys, `IDLE_THRESHOLD`, feature toggles

---

## BlueStacks Setup

```bash
python setup_bluestacks.py
```

Two-step resolution (required): 3088x1440 → 3840x2160 → 560 DPI

**BlueStacks right sidebar MUST be ON** - `WindowsScreenshotHelper` crops 30px from right.

---

## View State Detection & Navigation

```python
from utils.view_state_detector import detect_view, ViewState
from utils.return_to_base_view import return_to_base_view

# Detect current view
state, score = detect_view(frame)  # TOWN/WORLD/CHAT/WEBVIEW/UNKNOWN

# Navigate to base view (TOWN or WORLD) - THE unified function
return_to_base_view(adb)  # Fast path first, full recovery if needed

# Navigate to specific view
return_to_base_view(adb, target=ViewState.TOWN)   # Go to TOWN specifically
return_to_base_view(adb, target=ViewState.WORLD)  # Go to WORLD specifically
```

**Note**: `go_to_town()`/`go_to_world()` are convenience wrappers around `return_to_base_view(target=...)`

---

## Game Controls

| Control | Method | Implementation |
|---------|--------|----------------|
| Screenshots | Windows API | `WindowsScreenshotHelper` |
| Navigation | ADB tap | `return_to_base_view(target=ViewState.TOWN/WORLD)` |
| UI Clicking | ADB tap | `adb_helper.tap(x, y)` |
| Arrow Keys | Win32 API | `send_arrow_proper.py` (focus required) |
| Zoom | Win32 API | `send_zoom.py` (Shift+A/Z, focus required) |

---

## DEPRECATED APPROACHES

### ADB Screenshots for Matching
**Do not use** `adb_helper.take_screenshot()`. Different pixel values = matching fails.

### Traditional OCR
**Do not use** Tesseract, EasyOCR, PaddleOCR. Use `utils/qwen_ocr.py`.

### Old View Detection
**Removed**: `view_detection.py`, `view_button_matcher.py`. Use `view_state_detector.py`.

---

## Quick Reference

### Take Screenshot + Save

```python
from utils.windows_screenshot_helper import WindowsScreenshotHelper
import cv2

win = WindowsScreenshotHelper()
frame = win.get_screenshot_cv2()
cv2.imwrite("screenshot.png", frame)
```

### Template Matching

```python
from utils.template_matcher import match_template

# Fixed position
found, score, center = match_template(
    frame, "icon_4k.png",
    search_region=(x, y, w, h),
    threshold=0.05
)

# Search anywhere
found, score, center = match_template(frame, "button_4k.png", threshold=0.02)
```

### Run Daemon Flow

```bash
python scripts/daemon_cli.py run_flow elite_zombie
python scripts/daemon_cli.py status
```

---

## See Skills for Details

- **Template positions/thresholds**: `/template-catalog`
- **Extract new templates**: `/screenshot-detection`
- **Flow documentation**: `/daemon-flow`
