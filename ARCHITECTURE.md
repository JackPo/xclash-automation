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
- OCR runs through a local Qwen3-VL-2B server in bf16 (`services/ocr_server.py`), ~190ms per read.
- Used for stamina and Arms Race points.
- Arms Race scores are validated against a monotonic floor: same-block readings
  below the last confirmed score are rejected unless all reads unanimously agree
  (which instead overwrites a stale stored score). See `utils/arms_race_ocr.py`.
- Stamina OCR is bounded to 0-`STAMINA_OCR_MAX_VALID` (2500; real stamina reaches
  ~2000 with items); reads outside that range (e.g. a misread `123456789`) are
  discarded as garbage, not cached.
- The daemon health-checks and restarts the OCR server as needed.

### View recovery
- `utils/return_to_base_view.py` is the unified recovery primitive (fast back-tap
  path, then full multi-step recovery). It is name-imported once at module scope
  in `icon_daemon.py` — never re-import it locally inside the loop, or Python
  scopes the name function-local and the recovery calls raise `UnboundLocalError`.
- Cleanup/recovery yields to the user only on *active* input
  (`RETURN_ACTIVE_ABORT_SECONDS`, 3s), not the 5-min `IDLE_THRESHOLD`, so finished
  flows close their panels promptly.
- CHAT is a known view (so UNKNOWN recovery never fires for it); a dedicated
  CHAT-stuck escape clicks back out after `CHAT_STUCK_TIMEOUT` once the user has
  been idle `CHAT_STUCK_IDLE_REQUIRED` seconds.

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
