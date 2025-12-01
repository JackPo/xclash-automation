# xclash-automation

A fully automated bot for mobile games running on BlueStacks Android emulator. Uses computer vision and AI to detect UI elements and execute complex multi-step automation flows.

## Table of Contents

- [Features](#features)
- [Technology Stack](#technology-stack)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [Architecture](#architecture)
- [How It Works](#how-it-works)
- [Automation Flows](#automation-flows)
- [Adding New Flows](#adding-new-flows)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Features

- **Continuous Icon Detection**: Daemon monitors screen every 3 seconds for clickable UI elements
- **Template Matching**: Sub-pixel accurate detection using OpenCV's normalized squared difference
- **AI-Powered Object Detection**: Google Gemini 2.0 Flash for dynamic element discovery
- **Local GPU OCR**: Qwen2.5-VL-3B-Instruct running on local NVIDIA GPU for text extraction
- **View State Machine**: Automatically detects and navigates between TOWN/WORLD/CHAT views
- **Idle-Aware Automation**: Different behaviors based on user activity (harvesting only when idle)
- **Auto-Recovery**: Handles stuck states, app crashes, and UI anomalies automatically
- **Scheduled Tasks**: Time-based triggers (e.g., 2 AM daily tasks)
- **Crash Recovery**: Automatically detects and recovers from game crashes, restarts app if needed

## Technology Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| **Emulator** | [BlueStacks 5](https://www.bluestacks.com/) | Android emulation on Windows |
| **Device Control** | [ADB](https://developer.android.com/tools/adb) (Android Debug Bridge) | Tap, swipe, app control |
| **Screenshot Capture** | Windows GDI API | Fast, consistent screenshots for template matching |
| **Template Matching** | [OpenCV](https://opencv.org/) `cv2.matchTemplate` | UI element detection via `TM_SQDIFF_NORMED` |
| **Object Detection** | [Google Gemini 3.0 Pro](https://ai.google.dev/) | AI-based bounding box detection |
| **OCR** | [Qwen2.5-VL-3B-Instruct](https://huggingface.co/Qwen/Qwen2.5-VL-3B-Instruct) | Local GPU text extraction |
| **Idle Detection** | Windows `GetLastInputInfo` API | Track keyboard/mouse activity |
| **Language** | Python 3.12 | Core automation logic |

## Prerequisites

### Hardware

| Component | Minimum | Recommended |
|-----------|---------|-------------|
| **CPU** | Any x86_64 (Intel/AMD) | 4+ cores |
| **RAM** | 8GB | 16GB+ (BlueStacks uses 4GB) |
| **GPU** | NVIDIA GTX 1060 6GB | RTX 3060 12GB+ |
| **VRAM** | 6GB (for Qwen 3B model) | 8GB+ |
| **Storage** | 10GB free | 20GB+ (model cache) |

**GPU Requirements for Qwen OCR:**
- The Qwen2.5-VL-3B-Instruct model requires ~5-6GB VRAM
- CUDA-capable NVIDIA GPU required (no AMD/Intel GPU support)
- If you don't have a compatible GPU, the daemon will still work but stamina-based triggers (Elite Zombie) won't function
- Tested on: RTX 3060, RTX 3080, RTX 4090

### Software
- **OS**: Windows 10/11
- **BlueStacks 5**: [Download](https://www.bluestacks.com/download.html)
  - Enable ADB in Settings > Advanced
  - Default ADB path: `C:\Program Files\BlueStacks_nxt\hd-adb.exe`
- **Python 3.12+**: [Download](https://www.python.org/downloads/)
- **CUDA Toolkit**: For GPU acceleration (optional but recommended)
- **Google AI API Key**: [Get one free](https://aistudio.google.com/app/apikey)

### BlueStacks ADB Setup

1. Open BlueStacks Settings (gear icon)
2. Go to **Advanced** tab
3. Enable **Android Debug Bridge (ADB)**
4. Note the ADB port (default: 5555, but often 5554)

Verify connection:
```bash
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" devices
# Should show: emulator-5554  device
```

### BlueStacks Keybinding Setup (Required)

The automation uses keyboard inputs for zoom and camera control. These must be configured in BlueStacks:

1. Open BlueStacks with the game running
2. Click the **keyboard icon** (bottom-right) or press `Ctrl+Shift+A`
3. Go to **Game Controls** editor
4. Add the following keybindings:

| Action | Key | BlueStacks Control Type |
|--------|-----|------------------------|
| **Zoom In** | `Shift+A` | Pinch zoom in |
| **Zoom Out** | `Shift+Z` | Pinch zoom out |
| **Pan Up** | `Up Arrow` | Swipe down (inverted) |
| **Pan Down** | `Down Arrow` | Swipe up (inverted) |
| **Pan Left** | `Left Arrow` | Swipe right (inverted) |
| **Pan Right** | `Right Arrow` | Swipe left (inverted) |

**Note**: Pan controls are inverted because swiping left moves the camera right, etc.

5. Save the control scheme

**Why keyboard instead of ADB swipe?**
- More precise control over zoom levels
- Faster than ADB touch emulation
- Consistent behavior across sessions

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/JackPo/xclash-automation.git
cd xclash-automation
```

### 2. Create Virtual Environment (Recommended)

```bash
python -m venv venv
venv\Scripts\activate  # Windows
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

Key dependencies:
- `opencv-python` - Template matching and image processing
- `numpy` - Array operations
- `Pillow` - Image handling
- `google-generativeai` - Gemini API client
- `transformers` - Qwen model loading
- `torch` - PyTorch for GPU inference
- `pywin32` - Windows API access
- `pytz` - Timezone handling

### 4. Configure API Keys

```bash
# Copy the example config
cp config_local.py.example config_local.py

# Edit config_local.py and add your API key
notepad config_local.py
```

Required in `config_local.py`:
```python
GOOGLE_API_KEY = 'your-google-ai-api-key-here'
```

### 5. Setup BlueStacks Resolution

The automation requires **4K resolution (3840x2160)** for template matching:

```bash
python scripts/setup_bluestacks.py
```

This script:
1. Auto-detects the BlueStacks device
2. Sets resolution to 3840x2160 (requires two-step process)
3. Sets DPI to 560

**Important**: All templates are calibrated for 4K. Other resolutions will not work.

### 6. Verify Installation

```bash
# Test ADB connection
python -c "from utils.adb_helper import ADBHelper; a = ADBHelper(); print(f'Connected: {a.device}')"

# Test screenshot capture
python -c "from utils.windows_screenshot_helper import WindowsScreenshotHelper; w = WindowsScreenshotHelper(); print(f'Screenshot: {w.get_screenshot_cv2().shape}')"
```

## Configuration

Configuration uses a two-file system for security:

| File | Purpose | Git Status |
|------|---------|------------|
| `config.py` | Default values, config loader | Tracked |
| `config_local.py` | Your API keys and overrides | **Gitignored** |
| `config_local.py.example` | Template for config_local.py | Tracked |

### API Keys

```python
# config_local.py
GOOGLE_API_KEY = 'AIza...'  # Required for Gemini object detection
ANTHROPIC_API_KEY = '...'   # Optional
```

### Timing Parameters

```python
# Daemon behavior
DAEMON_INTERVAL = 3.0              # Seconds between detection cycles
IDLE_THRESHOLD = 300               # Seconds of inactivity before "idle" mode (5 min)
IDLE_CHECK_INTERVAL = 300          # Seconds between idle recovery checks (5 min)

# Recovery
UNKNOWN_STATE_TIMEOUT = 60         # Seconds in unknown state before recovery
```

### Game-Specific Parameters

```python
# Elite Zombie Rally
ELITE_ZOMBIE_STAMINA_THRESHOLD = 118   # Minimum stamina to trigger
ELITE_ZOMBIE_CONSECUTIVE_REQUIRED = 3  # Valid OCR reads before triggering

# Cooldowns (seconds)
AFK_REWARDS_COOLDOWN = 3600        # 1 hour between AFK reward claims
UNION_GIFTS_COOLDOWN = 3600        # 1 hour between union gift claims
UNION_GIFTS_IDLE_THRESHOLD = 1200  # 20 min idle required for union gifts
```

### Screen Regions

```python
# 4K coordinates (x, y, width, height)
STAMINA_REGION = (69, 203, 96, 60)  # Where to OCR stamina number
```

### Keybindings

```python
# Must match your BlueStacks game controls setup
KEY_ZOOM_IN = 'shift+a'    # Pinch zoom in
KEY_ZOOM_OUT = 'shift+z'   # Pinch zoom out
KEY_PAN_UP = 'up'          # Arrow keys for camera pan
KEY_PAN_DOWN = 'down'
KEY_PAN_LEFT = 'left'
KEY_PAN_RIGHT = 'right'
```

## Usage

### Running the Daemon

The main entry point is the icon daemon:

```bash
# Normal mode
python scripts/icon_daemon.py

# With debug logging (shows all detection scores)
python scripts/icon_daemon.py --debug

# Custom check interval
python scripts/icon_daemon.py --interval 5.0
```

Output example:
```
[142] 14:23:45 [TOWN] Stamina:87 idle:2m H:0.891 T:0.923 C:0.456 G:0.234 HB:0.876 ...
[143] 14:23:48 [TOWN] Stamina:87 idle:2m H:0.032 T:0.923 C:0.456 G:0.234 HB:0.876 ...
[143] HANDSHAKE detected (diff=0.0320)
FLOW START: handshake
```

### Object Detection with Gemini

For finding new UI elements:

```bash
python detect_object.py screenshot.png "the green Attack button"
```

Returns bounding box coordinates you can use to create new templates.

### Manual Commands

```python
from utils.adb_helper import ADBHelper
from utils.windows_screenshot_helper import WindowsScreenshotHelper

adb = ADBHelper()
win = WindowsScreenshotHelper()

# Take screenshot
frame = win.get_screenshot_cv2()

# Tap at coordinates
adb.tap(1920, 1080)

# Swipe
adb.swipe(1000, 500, 2000, 500, duration=300)
```

## Architecture

```
xclash/
├── config.py                    # Configuration loader with defaults
├── config_local.py              # Your API keys (gitignored)
├── config_local.py.example      # Template for config_local.py
├── detect_object.py             # Gemini-based object detection CLI
│
├── scripts/
│   ├── icon_daemon.py           # Main daemon process
│   ├── setup_bluestacks.py      # BlueStacks configuration
│   └── flows/                   # Automation flow modules
│       ├── __init__.py
│       ├── handshake_flow.py
│       ├── treasure_map_flow.py
│       ├── harvest_box_flow.py
│       ├── corn_harvest_flow.py
│       ├── elite_zombie_flow.py
│       └── ...
│
├── utils/
│   ├── adb_helper.py            # ADB command wrapper
│   ├── windows_screenshot_helper.py  # Windows GDI screenshots
│   ├── view_state_detector.py   # TOWN/WORLD/CHAT detection
│   ├── qwen_ocr.py              # Local GPU OCR
│   ├── idle_detector.py         # Windows idle time detection
│   ├── return_to_base_view.py   # Recovery logic
│   │
│   │ # Template matchers (one per icon type)
│   ├── handshake_icon_matcher.py
│   ├── treasure_map_matcher.py
│   ├── harvest_box_matcher.py
│   ├── corn_harvest_matcher.py
│   ├── gold_coin_matcher.py
│   └── ...
│
├── templates/
│   └── ground_truth/            # Template images (4K resolution)
│       ├── handshake_iter2.png
│       ├── treasure_map_4k.png
│       ├── world_button_4k.png
│       └── ...
│
└── logs/                        # Runtime logs (gitignored)
    └── daemon_YYYYMMDD_HHMMSS.log
```

## How It Works

### Detection Pipeline

```
┌─────────────────┐
│ Windows GDI     │  Fast screenshot capture (~50ms)
│ Screenshot      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Template        │  OpenCV TM_SQDIFF_NORMED at fixed regions
│ Matching        │  Score < threshold = match found
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Trigger         │  Check conditions (idle time, cooldowns, etc.)
│ Conditions      │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Flow            │  Execute multi-step automation
│ Execution       │  (runs in separate thread)
└─────────────────┘
```

### Why Windows Screenshots (Not ADB)

This project uses Windows GDI API for screenshots instead of ADB's `screencap` command. Here's why:

| Aspect | Windows GDI | ADB screencap |
|--------|-------------|---------------|
| **Speed** | ~50ms | ~500-2000ms |
| **Pixel Values** | Consistent BGR | Different color encoding |
| **Template Match** | Works perfectly | Templates don't match |
| **Reliability** | Very stable | Can timeout/fail |

**The critical issue**: ADB screenshots produce slightly different pixel values than Windows screenshots. Templates captured via Windows GDI will **not match** when compared against ADB screenshots (scores ~0.07 instead of ~0.00).

This means:
- Templates must be captured with `WindowsScreenshotHelper`
- Detection must use `WindowsScreenshotHelper`
- The project is **Windows-only** due to this dependency

If you need cross-platform support, you would need to:
1. Recapture all templates using ADB screenshots
2. Accept slower detection cycles (~2 seconds vs 50ms)
3. Handle ADB timeout failures

### Template Matching

Each icon has a dedicated matcher class with:
- **Fixed region**: Where to look (x, y, width, height)
- **Template image**: What to look for
- **Threshold**: Maximum score to consider a match (lower = stricter)

```python
# Example: HandshakeIconMatcher
REGION = (3088, 1780, 155, 127)  # Where handshake appears
THRESHOLD = 0.04                 # Score must be < 0.04
```

Using `TM_SQDIFF_NORMED`:
- Score of 0.0 = perfect match
- Score of 0.03 = very good match
- Score of 0.10 = poor match
- Score > threshold = not present

### View State Machine

```
         ┌──────────┐
    ┌───►│   TOWN   │◄───┐
    │    └────┬─────┘    │
    │         │ toggle   │
    │         ▼          │
    │    ┌──────────┐    │
    │    │  WORLD   │    │
    │    └────┬─────┘    │
    │         │          │
    │    ┌────▼─────┐    │
    └────┤   CHAT   ├────┘
         └────┬─────┘
              │ back button
              ▼
         ┌──────────┐
         │ UNKNOWN  │ → Recovery
         └──────────┘
```

## Automation Flows

| Icon | Matcher | Flow | Conditions |
|------|---------|------|------------|
| Handshake | `handshake_icon_matcher.py` | `handshake_flow.py` | Always active |
| Treasure Map | `treasure_map_matcher.py` | `treasure_map_flow.py` | Always active |
| Harvest Box | `harvest_box_matcher.py` | `harvest_box_flow.py` | Always active |
| Corn Bubble | `corn_harvest_matcher.py` | `corn_harvest_flow.py` | 5 min idle + aligned |
| Gold Coin | `gold_coin_matcher.py` | `gold_coin_flow.py` | 5 min idle + aligned |
| Iron Bar | `iron_bar_matcher.py` | `iron_bar_flow.py` | 5 min idle + aligned |
| Gem | `gem_matcher.py` | `gem_flow.py` | 5 min idle + aligned |
| Cabbage | `cabbage_matcher.py` | `cabbage_flow.py` | 5 min idle + aligned |
| Equipment | `equipment_enhancement_matcher.py` | `equipment_enhancement_flow.py` | 5 min idle + aligned |
| Elite Zombie | (stamina-based) | `elite_zombie_flow.py` | Stamina >= 118, 5 min idle |
| AFK Rewards | `afk_rewards_matcher.py` | `afk_rewards_flow.py` | 5 min idle, 1h cooldown |
| Union Gifts | (time-based) | `union_gifts_flow.py` | 20 min idle, 1h cooldown |

### "Aligned" Condition

Some flows require the camera to be in a specific position (dog house visible at expected coordinates). This prevents clicking the wrong location if the user scrolled the view.

### Crash & Idle Recovery

The daemon includes robust recovery mechanisms for common failure scenarios:

**App Crash Detection:**
- Every detection cycle checks if game is in foreground (`dumpsys window | grep mFocusedApp`)
- If app not running/foreground → triggers `return_to_base_view()` recovery
- Recovery restarts app via ADB: `am start -n com.xman.na.gp/.SplashActivity`
- Waits for app to load, then navigates to TOWN view

**UNKNOWN State Recovery:**
- If view state is UNKNOWN for 60+ seconds AND user is idle 5+ minutes
- Triggers full recovery: clicks back buttons, detects view, navigates to TOWN
- If still stuck after multiple attempts → restarts app

**Idle Recovery (every 5 min when idle):**
- Ensures camera is aligned (dog house at expected position)
- If in WORLD/CHAT → navigates back to TOWN
- If camera misaligned → toggles WORLD/TOWN to reset view

**Why This Matters:**
- Games crash periodically (memory leaks, network issues)
- Without recovery, daemon would sit idle waiting for icons that never appear
- Recovery ensures automation continues 24/7 with minimal intervention

## Adding New Flows

### 1. Create Template

```bash
# Take screenshot
python -c "from utils.windows_screenshot_helper import WindowsScreenshotHelper; import cv2; cv2.imwrite('screenshot.png', WindowsScreenshotHelper().get_screenshot_cv2())"

# Find element with Gemini
python detect_object.py screenshot.png "the button you want to detect"

# Crop template from screenshot using returned coordinates
```

Save to `templates/ground_truth/your_element_4k.png`

### 2. Create Matcher

```python
# utils/your_element_matcher.py
import cv2
from pathlib import Path

class YourElementMatcher:
    REGION = (x, y, width, height)  # Where to look
    THRESHOLD = 0.05                 # Adjust based on testing

    def __init__(self, debug_dir=None):
        base_dir = Path(__file__).parent.parent
        self.template_path = base_dir / "templates/ground_truth/your_element_4k.png"
        self.template = cv2.imread(str(self.template_path), cv2.IMREAD_GRAYSCALE)
        self.threshold = self.THRESHOLD
        self.debug_dir = debug_dir

    def is_present(self, frame):
        x, y, w, h = self.REGION
        roi = frame[y:y+h, x:x+w]
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)

        result = cv2.matchTemplate(roi_gray, self.template, cv2.TM_SQDIFF_NORMED)
        score = result[0, 0]

        return score < self.threshold, score
```

### 3. Create Flow

```python
# scripts/flows/your_element_flow.py
import time

def your_element_flow(adb):
    """Handle your element click."""
    # Click the element
    adb.tap(center_x, center_y)
    time.sleep(0.5)

    # Additional steps...
```

### 4. Register in Daemon

Add to `scripts/icon_daemon.py`:
```python
from utils.your_element_matcher import YourElementMatcher
from flows import your_element_flow

# In __init__:
self.your_matcher = YourElementMatcher(debug_dir=debug_dir)

# In run loop:
your_present, your_score = self.your_matcher.is_present(frame)
if your_present:
    self._run_flow("your_element", your_element_flow)
```

## Troubleshooting

### "No device found" / ADB connection issues

```bash
# Check if BlueStacks is running
"C:\Program Files\BlueStacks_nxt\hd-adb.exe" devices

# If empty, restart BlueStacks and ensure ADB is enabled in settings
# Device should show as: emulator-5554  device
```

### Template matching always fails (high scores)

1. **Wrong resolution**: Must be 4K (3840x2160)
   ```bash
   python scripts/setup_bluestacks.py
   ```

2. **Using ADB screenshots**: Must use Windows screenshots
   ```python
   # WRONG
   frame = adb.take_screenshot()

   # CORRECT
   from utils.windows_screenshot_helper import WindowsScreenshotHelper
   frame = WindowsScreenshotHelper().get_screenshot_cv2()
   ```

3. **Template from different session**: Re-capture template with current game state

### OCR returns None or wrong values

1. **No NVIDIA GPU**: Qwen requires CUDA
2. **Wrong region coordinates**: Check `STAMINA_REGION` in config
3. **GPU memory**: Close other GPU applications

### Daemon stuck in UNKNOWN state

The daemon should auto-recover after 60 seconds. If stuck:
1. Manually navigate game to town view
2. Restart daemon
3. Check `logs/` for error details

### Flows not triggering

Check conditions:
- **Idle flows**: Require 5+ minutes without keyboard/mouse input
- **Cooldown flows**: Check if cooldown expired
- **Aligned flows**: Camera must be at default position

## License

MIT License - See [LICENSE](LICENSE) for details.

## Acknowledgments

- [BlueStacks](https://www.bluestacks.com/) for Android emulation
- [OpenCV](https://opencv.org/) for computer vision
- [Google Gemini](https://ai.google.dev/) for AI object detection
- [Qwen](https://github.com/QwenLM/Qwen2.5-VL) for local OCR model
