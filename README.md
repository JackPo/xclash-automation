# xclash-automation

Automation bot for Clash of Clans using BlueStacks Android emulator. Detects clickable UI elements via template matching and triggers automated flows.

## Features

- **Icon Detection Daemon**: Continuously monitors for clickable icons (handshake, treasure map, harvest bubbles, etc.)
- **Template Matching**: Uses OpenCV TM_SQDIFF_NORMED for precise UI element detection
- **Gemini Object Detection**: Uses Google's Gemini 2.0 Flash for dynamic object detection
- **Qwen OCR**: Local GPU-based OCR using Qwen2.5-VL-3B-Instruct for stamina reading
- **View State Detection**: Automatically detects TOWN/WORLD/CHAT states
- **Idle Recovery**: Auto-navigates back to town when user is idle

## Requirements

- Windows 10/11
- BlueStacks 5 (with ADB enabled)
- Python 3.12+
- NVIDIA GPU (for Qwen OCR)
- Google AI API key (for Gemini)

## Installation

1. Clone the repo:
```bash
git clone https://github.com/JackPo/xclash-automation.git
cd xclash-automation
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Configure API keys:
```bash
cp config_local.py.example config_local.py
# Edit config_local.py and add your Google API key
```

4. Setup BlueStacks resolution:
```bash
python scripts/setup_bluestacks.py
```

## Usage

### Run the Icon Daemon
```bash
python scripts/icon_daemon.py
```

Options:
- `--interval SECONDS` - Check interval (default: 3.0)
- `--debug` - Enable debug logging

### Detect Objects with Gemini
```bash
python detect_object.py screenshot.png "description of what to find"
```

## Architecture

```
xclash/
├── scripts/
│   ├── icon_daemon.py      # Main daemon - runs continuously
│   ├── setup_bluestacks.py # Configure BlueStacks resolution
│   └── flows/              # Automation flows for each icon type
├── utils/
│   ├── adb_helper.py       # ADB commands (tap, swipe)
│   ├── windows_screenshot_helper.py  # Windows API screenshots
│   ├── view_state_detector.py        # TOWN/WORLD detection
│   ├── qwen_ocr.py         # GPU-based OCR
│   └── *_matcher.py        # Template matchers for each icon
├── templates/
│   └── ground_truth/       # Template images for matching
├── config.py               # Config loader
└── config_local.py         # Your API keys (gitignored)
```

## Detected Icons

| Icon | Flow | Trigger Conditions |
|------|------|-------------------|
| Handshake | `handshake_flow` | Always (no idle required) |
| Treasure Map | `treasure_map_flow` | Always |
| Harvest Box | `harvest_box_flow` | Always |
| Corn Bubble | `corn_harvest_flow` | 5 min idle + aligned |
| Gold Coin | `gold_coin_flow` | 5 min idle + aligned |
| Iron Bar | `iron_bar_flow` | 5 min idle + aligned |
| Gem | `gem_flow` | 5 min idle + aligned |
| Cabbage | `cabbage_flow` | 5 min idle + aligned |
| Equipment | `equipment_enhancement_flow` | 5 min idle + aligned |
| Elite Zombie | `elite_zombie_flow` | Stamina >= 118 + 5 min idle |
| AFK Rewards | `afk_rewards_flow` | 5 min idle + 1 hour cooldown |
| Union Gifts | `union_gifts_flow` | 20 min idle + 1 hour cooldown |

## Configuration

All configurable parameters are in `config.py`. Copy `config_local.py.example` to `config_local.py` to override:

### API Keys
```python
GOOGLE_API_KEY = 'your-key'  # Required for Gemini object detection
```

### Daemon Parameters (in config_local.py)
```python
# Timing
DAEMON_INTERVAL = 3.0              # Check interval (seconds)
IDLE_THRESHOLD = 300               # 5 minutes before idle triggers
IDLE_CHECK_INTERVAL = 300          # 5 minutes between idle checks

# Elite Zombie
ELITE_ZOMBIE_STAMINA_THRESHOLD = 118
ELITE_ZOMBIE_CONSECUTIVE_REQUIRED = 3

# Cooldowns
AFK_REWARDS_COOLDOWN = 3600        # 1 hour
UNION_GIFTS_COOLDOWN = 3600        # 1 hour
UNION_GIFTS_IDLE_THRESHOLD = 1200  # 20 minutes

# Recovery
UNKNOWN_STATE_TIMEOUT = 60         # 1 minute in UNKNOWN triggers recovery

# Screen Regions (4K resolution)
STAMINA_REGION = (69, 203, 96, 60)  # x, y, w, h
```

## Template Matching

Templates are stored in `templates/ground_truth/`. Each matcher has a threshold defined in its source file:

- Lower score = better match (TM_SQDIFF_NORMED)
- Typical thresholds: 0.04-0.06 for icons
- Edit thresholds in `utils/*_matcher.py` files

## Troubleshooting

### Template matching failing
- Ensure BlueStacks is at 4K resolution (3840x2160)
- Run `python scripts/setup_bluestacks.py`
- Templates must be captured with Windows screenshots, not ADB

### OCR not working
- Requires NVIDIA GPU with CUDA
- Model: Qwen2.5-VL-3B-Instruct

### ADB connection issues
- BlueStacks ADB path: `C:\Program Files\BlueStacks_nxt\hd-adb.exe`
- Device: `emulator-5554` (auto-detected)

## License

MIT
