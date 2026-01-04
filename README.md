# xclash-automation

Automation daemon for X-Clash (com.xman.na.gp) running on BlueStacks. Uses Windows screenshots, OpenCV template matching, OCR, and ADB input to drive in-game flows.

## What it automates
- Passive popups: handshake, treasure maps, harvest boxes, AFK rewards
- Resource harvest bubbles (requires calibrated coordinates and aligned town view)
- Tavern quests (claim, start gold scrolls, schedule-aware claiming)
- Union gifts and Union Technology donations
- Bag items and gift box rewards
- Union War rally joining (monster filters + daily limit handling)
- Hospital healing (batch healing)
- Arms Race events: Mystic Beast, Enhance Hero, Soldier Training
- Event-specific stamina management during Mystic Beast

Notes:
- Some flows are manual or on-demand (for example, faction trials, title management).
- Planned and missing features are tracked in `docs/future_steps.md`.

## How it works (short version)
- `WindowsScreenshotHelper` captures frames for matching (ADB screenshots are not used).
- Matchers detect UI elements; the daemon triggers flows when conditions are met.
- OCR runs via a local Qwen2.5-VL server for stamina and event points.
- A JSON scheduler persists cooldowns and daily limits across restarts.

## Quick start
1. Install Python 3.12+, BlueStacks 5, and optional CUDA (for OCR).
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
3. Set BlueStacks to 3840x2160:
   ```bash
   python scripts/setup_bluestacks.py
   ```
4. Copy config overrides:
   ```bash
   cp config_local.py.example config_local.py
   ```
5. Run the daemon:
   ```bash
   python scripts/icon_daemon.py
   ```

## Configuration
- Defaults live in `config.py`; overrides go in `config_local.py`.
- Calibrate town layout coordinates for harvest flows using `OBJECT_DETECTION_GUIDE.md`.

## Docs
See `docs/README.md` for the full documentation map and deep dives. For a game primer, start with `docs/game_overview.md`.
