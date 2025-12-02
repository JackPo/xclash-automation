# xclash-automation

A fully automated bot for **X-Clash** (`com.xman.na.gp`) running on BlueStacks Android emulator. Uses computer vision and AI to detect UI elements and execute complex multi-step automation flows.

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
- [Development](#development)
- [Troubleshooting](#troubleshooting)
- [License](#license)

## Features

### What Gets Automated

- **Resource Harvesting**: Automatically clicks corn, gold, iron, gem, cabbage, and equipment bubbles when they appear
- **Alliance Handshakes**: Clicks the alliance handshake icon whenever available
- **Treasure Maps**: Opens and collects treasure map rewards
- **Harvest Boxes**: Opens surprise harvest boxes
- **AFK Rewards**: Claims idle/AFK reward popups
- **Union Gifts**: Collects alliance gift packages
- **Elite Zombie Rallies**: Automatically starts rallies when stamina is sufficient (118+)
- **Arms Race - Beast Training**: During Mystic Beast event, trains beasts when stamina >= 20 (configurable)
- **Arms Race - Hero Enhancement**: During Enhance Hero event, upgrades heroes in the last 20 minutes (configurable)

### Technical Features

- **24/7 Background Operation**: Runs continuously as a daemon, checking every 3 seconds
- **Idle-Aware**: Only triggers resource harvesting when you're AFK (5+ minutes idle)
- **Crash Recovery**: Automatically restarts the game if it crashes or gets stuck
- **View Navigation**: Detects TOWN/WORLD/CHAT views and navigates as needed
- **Template Matching**: Sub-pixel accurate icon detection using OpenCV
- **Local GPU OCR**: Reads stamina numbers using Qwen2.5-VL on your GPU (no cloud API needed)
- **Arms Race Tracking**: Tracks the 5-activity Arms Race rotation and triggers event-specific flows
- **Template Verification**: Validates all required templates exist at startup to catch missing files early
- **Configurable**: All coordinates, thresholds, and timings can be customized

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
| **CPU** | Any x86_64 (Intel/AMD) | Server-class CPU for 24/7 operation |
| **RAM** | 8GB | 16GB+ (BlueStacks uses 4GB) |
| **GPU** | NVIDIA with ~4GB VRAM | Any CUDA-capable GPU |
| **Storage** | 10GB free | 20GB+ (model cache) |

**Tested Setup (24/7 rack server):**
- CPU: Intel Xeon E-2186G @ 3.80GHz (works great for 3s intervals)
- GPU: GTX 1080 (8GB VRAM) - handles Qwen OCR well
- Runs continuously as a background service

**GPU Requirements for Qwen OCR:**
- The Qwen2.5-VL-3B-Instruct model runs on modest NVIDIA GPUs
- CUDA-capable NVIDIA GPU required (no AMD/Intel GPU support)
- If you don't have a compatible GPU, the daemon will still work but stamina-based triggers (Elite Zombie) won't function
- Note: Quadro P4000 was too slow for practical use

**Performance Tuning:**
- Default `DAEMON_INTERVAL = 3.0` seconds is conservative for 24/7 server use
- With faster CPU/GPU, you can reduce this to 1-2 seconds for quicker response
- See [Configuration](#configuration) for how to adjust

### Software
- **OS**: Windows 10/11
- **BlueStacks 5**: [Download](https://www.bluestacks.com/download.html)
  - Enable ADB in Settings > Advanced
  - Default ADB path: `C:\Program Files\BlueStacks_nxt\hd-adb.exe`
- **Python 3.12+**: [Download](https://www.python.org/downloads/)
- **CUDA Toolkit**: For GPU acceleration (optional but recommended)

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

### 4. Setup BlueStacks Resolution

The automation requires **4K resolution (3840x2160)** for template matching:

```bash
python scripts/setup_bluestacks.py
```

This script:
1. Auto-detects the BlueStacks device
2. Sets resolution to 3840x2160 (requires two-step process)
3. Sets DPI to 560

**Important**: All templates are calibrated for 4K. Other resolutions will not work.

### Resolution Scaling

Screenshots are automatically scaled to 4K (3840x2160) regardless of your actual display resolution:

- **Template Matching**: All templates are 4K; screenshots are scaled to match
- **Native Resolution**: BlueStacks runs at 4K internally (set by `setup_bluestacks.py`)
- **Automatic Scaling**: `WindowsScreenshotHelper` handles any necessary scaling transparently

This means templates work across different display setups without recapture.

### 5. Verify Installation

```bash
# Test ADB connection
python -c "from utils.adb_helper import ADBHelper; a = ADBHelper(); print(f'Connected: {a.device}')"

# Test screenshot capture
python -c "from utils.windows_screenshot_helper import WindowsScreenshotHelper; w = WindowsScreenshotHelper(); print(f'Screenshot: {w.get_screenshot_cv2().shape}')"
```

## Configuration

All configuration has sensible defaults. You only need to create `config_local.py` if you want to override defaults.

| File | Purpose | Git Status |
|------|---------|------------|
| `config.py` | Default values, config loader | Tracked |
| `config_local.py` | Your overrides (optional) | **Gitignored** |
| `config_local.py.example` | Template showing available options | Tracked |

To customize, copy the example and uncomment what you need:
```bash
cp config_local.py.example config_local.py
notepad config_local.py
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
# Stamina-based triggers (unified validation)
# All stamina triggers require 3 consecutive valid readings (0-200)
# with consistency check (diff <= 20 between readings)
ELITE_ZOMBIE_STAMINA_THRESHOLD = 118   # Minimum stamina for elite zombie rally
ELITE_ZOMBIE_CONSECUTIVE_REQUIRED = 3  # Consecutive valid OCR reads required

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

These defaults match the [BlueStacks Keybinding Setup](#bluestacks-keybinding-setup-required). Override in `config_local.py` if you use different keys:

```python
# Must match your BlueStacks game controls setup
KEY_ZOOM_IN = 'shift+a'    # Pinch zoom in
KEY_ZOOM_OUT = 'shift+z'   # Pinch zoom out
KEY_PAN_UP = 'up'          # Arrow keys for camera pan
KEY_PAN_DOWN = 'down'
KEY_PAN_LEFT = 'left'
KEY_PAN_RIGHT = 'right'
```

### Town Layout Coordinates (Required for Harvest Flows)

**Important**: The resource harvest flows (corn, gold, iron, gem, cabbage, equipment) click at **fixed coordinates** based on your town layout. You **must calibrate these** for your account or they will click in the wrong locations.

**Reference town layout** (this is how the developer's town is arranged - your coordinates will differ):

![Town Layout Example](docs/town_layout_example.png)

```python
# Dog house - alignment anchor (must be visible for harvest flows to trigger)
DOG_HOUSE_POSITION = (1605, 882)    # x, y - where dog house should appear
DOG_HOUSE_SIZE = (172, 197)         # width, height of detection region

# Resource bubble positions: {'region': (x, y, w, h), 'click': (x, y)}
CORN_BUBBLE = {'region': (1015, 869, 67, 57), 'click': (1048, 897)}
GOLD_BUBBLE = {'region': (1369, 800, 53, 43), 'click': (1395, 835)}
IRON_BUBBLE = {'region': (1617, 351, 46, 32), 'click': (1639, 377)}
GEM_BUBBLE = {'region': (1378, 652, 54, 51), 'click': (1405, 696)}
CABBAGE_BUBBLE = {'region': (1267, 277, 67, 57), 'click': (1300, 305)}
EQUIPMENT_BUBBLE = {'region': (1246, 859, 67, 57), 'click': (1279, 887)}
```

**To calibrate for your town:**

1. Take a screenshot:
   ```bash
   python -c "from utils.windows_screenshot_helper import WindowsScreenshotHelper; import cv2; cv2.imwrite('screenshot.png', WindowsScreenshotHelper().get_screenshot_cv2())"
   ```

2. Use Gemini to find coordinates (requires `GOOGLE_API_KEY`):
   ```bash
   python detect_object.py screenshot.png "the corn harvest bubble"
   ```

3. Update `config_local.py` with your coordinates

### Detection Thresholds

Adjust if detection is too sensitive (false positives) or not sensitive enough (missing icons):

```python
THRESHOLDS = {
    'dog_house': 0.1,      # View alignment check
    'corn': 0.06,          # Resource bubbles
    'gold': 0.06,
    'iron': 0.08,
    'gem': 0.13,
    'cabbage': 0.05,
    'equipment': 0.06,
    'handshake': 0.04,     # UI icons
    'treasure_map': 0.05,
    'harvest_box': 0.1,
    'afk_rewards': 0.06,
    'back_button': 0.06,
}
```

Lower threshold = stricter matching (fewer false positives, may miss real icons)
Higher threshold = looser matching (catches more icons, may have false positives)

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
│   ├── arms_race.py             # Arms Race schedule calculator
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

### Universal Flows (Work Out of Box)

These flows detect standard UI popups and work on any account:

| Icon | Matcher | Flow | Conditions |
|------|---------|------|------------|
| Handshake | `handshake_icon_matcher.py` | `handshake_flow.py` | Always active |
| Treasure Map | `treasure_map_matcher.py` | `treasure_map_flow.py` | Always active |
| Harvest Box | `harvest_box_matcher.py` | `harvest_box_flow.py` | Always active |
| AFK Rewards | `afk_rewards_matcher.py` | `afk_rewards_flow.py` | 5 min idle, 1h cooldown |

### ⚠️ Setup-Specific Flows (Requires Calibration)

These flows click at **fixed coordinates** and require calibration for your account. See [Town Layout Coordinates](#town-layout-coordinates-required-for-harvest-flows) for setup instructions.

| Icon | Matcher | Flow | Conditions |
|------|---------|------|------------|
| Corn Bubble | `corn_harvest_matcher.py` | `corn_harvest_flow.py` | 5 min idle + aligned |
| Gold Coin | `gold_coin_matcher.py` | `gold_coin_flow.py` | 5 min idle + aligned |
| Iron Bar | `iron_bar_matcher.py` | `iron_bar_flow.py` | 5 min idle + aligned |
| Gem | `gem_matcher.py` | `gem_flow.py` | 5 min idle + aligned |
| Cabbage | `cabbage_matcher.py` | `cabbage_flow.py` | 5 min idle + aligned |
| Equipment | `equipment_enhancement_matcher.py` | `equipment_enhancement_flow.py` | 5 min idle + aligned |
| Elite Zombie | (stamina-based) | `elite_zombie_flow.py` | Stamina >= 118, 5 min idle |
| Union Gifts | (time-based) | `union_gifts_flow.py` | 20 min idle, 1h cooldown |

**"Aligned" condition**: The daemon checks if the dog house is at expected coordinates before triggering harvest flows. If the camera has panned, bubbles won't be at the right locations.

### Arms Race Event Tracking

The daemon tracks the Arms Race event rotation and triggers event-specific flows. Both features are **enabled by default** but can be disabled in `config_local.py`.

| Event | Trigger Condition | Flow | Config to Disable |
|-------|-------------------|------|-------------------|
| **Mystic Beast** | Last 60 minutes, stamina >= 20 (3 consecutive valid reads) | `elite_zombie_flow` (0 plus clicks) | `ARMS_RACE_BEAST_TRAINING_ENABLED = False` |
| **Enhance Hero** | Last 20 minutes, **idle since block start** | `hero_upgrade_arms_race_flow` | `ARMS_RACE_ENHANCE_HERO_ENABLED = False` |

**Stamina Validation**: Both Elite Zombie and Beast Training use a **unified stamina validation system**:
- Requires 3 consecutive valid readings (0-200 range)
- Consecutive readings must be consistent (diff <= 20)
- Prevents false triggers from OCR errors (e.g., "1234567890")

**Enhance Hero Idle Requirement**: The Enhance Hero flow only triggers if you were **idle since the START of the Enhance Hero block** (not just idle for 5 minutes). This ensures the automation doesn't interrupt active gameplay.

**Stamina Management** (during Beast Training):

The daemon automatically manages stamina during Mystic Beast events:

1. **Stamina Claim** (free, every 4 hours):
   - Triggers when stamina < 60 AND red notification dot visible on stamina display
   - Red dot detection prevents false positives (only claims when actually available)
   - Uses `stamina_red_dot_detector.py` for pixel-based dot detection

2. **Stamina Use** (recovery items, +50 stamina):
   - Triggers when stamina < 20, idle since block start, rally count < 15
   - Max 4 uses per block, 3-minute cooldown between uses
   - Only uses if Claim button not available (prioritizes free claims)

**Configuration options** (in `config_local.py`):
```python
# Beast Training (during Mystic Beast event)
ARMS_RACE_BEAST_TRAINING_ENABLED = True        # Set False to disable
ARMS_RACE_BEAST_TRAINING_LAST_MINUTES = 60     # Trigger window (last N minutes)
ARMS_RACE_BEAST_TRAINING_STAMINA_THRESHOLD = 20  # Minimum stamina required
ARMS_RACE_BEAST_TRAINING_COOLDOWN = 90         # Seconds between rallies

# Stamina Claim (free claim, every 4 hours)
ARMS_RACE_STAMINA_CLAIM_THRESHOLD = 60         # Claim if stamina < 60

# Stamina Use (recovery items)
ARMS_RACE_BEAST_TRAINING_USE_ENABLED = True    # Set False to disable
ARMS_RACE_BEAST_TRAINING_USE_MAX = 4           # Max uses per block
ARMS_RACE_BEAST_TRAINING_USE_COOLDOWN = 180    # 3 minutes between uses
ARMS_RACE_BEAST_TRAINING_USE_STAMINA_THRESHOLD = 20  # Use if stamina < 20
ARMS_RACE_BEAST_TRAINING_MAX_RALLIES = 15      # Don't use if >= 15 rallies

# Enhance Hero (during Enhance Hero event)
# Only triggers if idle since the START of the Enhance Hero block
ARMS_RACE_ENHANCE_HERO_ENABLED = True          # Set False to disable
ARMS_RACE_ENHANCE_HERO_LAST_MINUTES = 20       # Trigger window (last N minutes)
```

**How it works:**
- Arms Race rotates through 5 activities every 4 hours: City Construction, Soldier Training, Tech Research, Mystic Beast, Enhance Hero
- The daemon computes the current event from UTC time (no screenshot needed)
- Status is displayed in the log output: `AR:Mys(98m)` means "Mystic Beast, 98 minutes remaining"

**Programmatic access:**
```python
from utils.arms_race import get_arms_race_status

status = get_arms_race_status()
print(f"Day {status['day']}: {status['current']}")
print(f"Time remaining: {status['time_remaining']}")
```

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

## Development

This section is for developers who want to add new detection flows. **Normal users don't need this** - just run the daemon.

### API Keys for Development

To use `detect_object.py` for finding UI element coordinates, you need a Google API key:

1. Get a free key at [Google AI Studio](https://aistudio.google.com/app/apikey)
2. Create `config_local.py`:
   ```bash
   cp config_local.py.example config_local.py
   ```
3. Add your key:
   ```python
   GOOGLE_API_KEY = 'AIza...'
   ```

**Note**: This key is only for development. Once you have templates, the daemon runs 100% locally.

### Finding UI Elements with Gemini

```bash
# Take a screenshot first
python -c "from utils.windows_screenshot_helper import WindowsScreenshotHelper; import cv2; cv2.imwrite('screenshot.png', WindowsScreenshotHelper().get_screenshot_cv2())"

# Use Gemini 3.0 Pro to find elements
python detect_object.py screenshot.png "the green Attack button"
```

Returns bounding box coordinates: `(x, y, width, height)`. Use these to crop a template and determine click coordinates.

### Manual ADB Commands

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

### Adding a New Flow

#### 1. Create Template

```bash
# Take screenshot and use Gemini to find coordinates
python detect_object.py screenshot.png "the button you want to detect"

# Crop template from screenshot using returned coordinates
# Save to templates/ground_truth/your_element_4k.png
```

#### 2. Create Matcher

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

#### 3. Create Flow

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

#### 4. Register in Daemon

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
