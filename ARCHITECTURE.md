# X-Clash Automation Architecture

## Purpose
Automate routine actions in X-Clash while running inside BlueStacks. The system watches the game UI, detects known elements, and executes multi-step flows without interrupting active gameplay.

## System overview
Core pieces and how they connect:

1. Windows screenshot capture
2. Template matchers and state detection
3. Flow gating (idle, cooldowns, alignment)
4. Flow execution (ADB taps/swipes)
5. Persistence and recovery

## Runtime flow
```
WindowsScreenshotHelper -> Matchers -> Gating -> Flow -> Scheduler/State
```

### Loop behavior (icon daemon)
1. Capture a 4K frame from BlueStacks.
2. Detect view state (TOWN/WORLD/CHAT) and critical UI elements.
3. Apply gating rules:
   - idle time
   - cooldowns and daily limits
   - town alignment (dog house position) for coordinate-based clicks
4. Trigger flows in a separate thread and record results.
5. Persist state to `data/daemon_schedule.json` and recover from UNKNOWN states.

## Key subsystems

### View detection and alignment
- `utils/view_state_detector.py` detects TOWN/WORLD/CHAT using 4K templates.
- Alignment uses the dog house anchor to ensure fixed coordinates are safe to click.
- Recovery logic returns to a base view when the UI gets stuck.

### Template matching
- OpenCV `TM_SQDIFF_NORMED` for most icons.
- Masked templates are used for icons with transparency.
- All templates are calibrated for 3840x2160.

### OCR
- OCR runs through a local Qwen2.5-VL server (`utils/ocr_server.py`).
- Used for stamina and Arms Race points.
- The daemon health-checks and restarts the OCR server as needed.

### Scheduler and state
- `utils/scheduler.py` manages cooldowns, daily limits, and Arms Race block state.
- State is persisted to `data/daemon_schedule.json` for crash recovery.

### Arms Race schedule
- `utils/arms_race.py` implements a 7-day, 42-block schedule with a fixed UTC reference start.
- Event-aware flows (Mystic Beast, Enhance Hero, Soldier Training) use this schedule.

### Control layer
- `utils/adb_helper.py` handles taps, swipes, and app restarts.
- All detection uses Windows screenshots, not ADB screenshots.

### Dashboard and config overrides
- `dashboard/server.py` runs a FastAPI web server for monitoring and control.
- `utils/config_overrides.py` manages runtime config overrides with expiry.
- Overrides persist to `data/config_overrides.json` for survival across restarts.
- See `docs/DASHBOARD.md` for full dashboard documentation.

## Files and directories (focused view)
```
config.py                  Defaults and global settings
config_local.py            User overrides (gitignored)
scripts/icon_daemon.py     Main loop
scripts/flows/             Automation flows
utils/                     Matchers, OCR, scheduler, helpers
dashboard/                 Web dashboard (FastAPI + Alpine.js)
templates/ground_truth/    4K templates
data/daemon_schedule.json  Persistent scheduler state
data/config_overrides.json Runtime config overrides
logs/                      Runtime logs
```

## Related docs
- `docs/README.md` for the full documentation map
- `docs/arms_race.md` and `docs/BEAST_TRAINING_LOGIC.md` for event automation
- `templates/buttons/WORLD_TOWN_DETECTION.md` for view detection details
- `docs/game_overview.md` for gameplay context
