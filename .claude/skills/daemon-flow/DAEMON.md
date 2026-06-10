# Icon Daemon Reference

Technical reference for daemon internals.

## Running the Daemon

```bash
python scripts/icon_daemon.py           # Normal mode
python scripts/icon_daemon.py --debug   # Debug mode (log all scores)
python scripts/icon_daemon.py --interval 5  # Custom interval
```

**Logging**:
- `logs/daemon_YYYYMMDD_HHMMSS.log` - Timestamped (archived)
- `logs/current_daemon.log` - Latest (overwritten each restart)

```bash
cat logs/current_daemon.log
grep "BAG FLOW\|triggering" logs/current_daemon.log
```

---

## Flow Coordination

Prevents flows from interrupting each other.

**Key components**:
- `active_flows` set - tracks running flows
- `critical_flow_active` flag - blocks non-critical when True
- `_can_run_flow()` - pre-check before clicking

**Pattern**:
```python
# CORRECT: Check BEFORE clicking
if not self._can_run_flow():
    self.logger.debug("Skipping - another flow is active")
else:
    self.adb.tap(x, y)  # Only click if no flow active
    self._run_flow_sync("flow_name", flow_func, critical=True)

# WRONG: Click first (causes interruptions)
self.adb.tap(x, y)  # BAD!
self._run_flow_sync(...)  # Too late
```

---

## Idle Detection Modes

Controlled by `USE_BLUESTACKS_IDLE` in `config.py`:

| Mode | Value | Behavior |
|------|-------|----------|
| BlueStacks-specific | `True` (default) | Only tracks input in BlueStacks window |
| System-wide | `False` | Any input anywhere resets idle |

**BlueStacks mode**: Typing in Chrome doesn't reset timer. Automation runs while working in other apps.

**System-wide mode**: Any input resets timer. Automation only when fully AFK.

Daemon logs both: `idle:` (system-wide) and `bs:` (BlueStacks-specific)

---

## Idle Return-to-Town

Every 5 daemon iterations (~10 seconds) when idle 5+ min:
1. Not in TOWN → navigate to TOWN
2. In TOWN → check dog house alignment, reset if misaligned

Resets when user active or critical flow running.

---

## Disconnection Dialog Handling

When user opens game on mobile, BlueStacks disconnects:

1. **Detection**: Template matches "Error Code:7" dialog
2. **Wait 5 minutes**: User manages mobile
3. **Auto-dismiss**: Click Confirm to reconnect

**Templates**:
- `disconnection_dialog_4k.png` (980x350)
- `confirm_button_4k.png` (click: 1912, 1289)

**Config**: `DISCONNECTION_WAIT_SECONDS = 300`

---

## Zombie Mode

For Beast Training - use regular zombie instead of elite rallies.

**Modes**: `elite` (default), `iron_mine`, `gold`, `food`

**State** (`data/daemon_schedule.json`):
```json
{
  "zombie_mode": {
    "mode": "gold",
    "expires": "2025-01-04T06:00:00+00:00"
  }
}
```

**CLI Commands**:
```bash
python scripts/daemon_cli.py set_zombie_mode iron_mine 4  # 4 hours
python scripts/daemon_cli.py get_zombie_mode
python scripts/daemon_cli.py clear_zombie_mode
```

---

## Stamina Confirmation

`utils/stamina_reader.py` prevents OCR misreads.

```python
from utils.stamina_reader import StaminaReader

reader = StaminaReader()

# Add each OCR reading
confirmed, stamina = reader.add_reading(ocr_value)
if confirmed:
    do_action(stamina)
    reader.reset()
```

**Logic**:
- Requires 3 readings
- Checks consistency: max-min <= 10 (resets if too spread)
- Returns MODE (most common), not last value

**Example**: `[5, 5, 23]` → (False, None) because max-min=18>10

---

## OCR with Qwen3-VL-2B

Vision model for game text (better than Tesseract/EasyOCR). Served by
`services/ocr_server.py`; access it through the client:

```python
from utils.ocr_client import OCRClient

ocr = OCRClient()
number = ocr.extract_number(frame, region=(69, 203, 96, 60))
```

**GPU Config (RTX 5060 Ti 16GB)**: loaded in bf16, no quantization
(`dtype=torch.bfloat16`). If accuracy ever regresses, bump MODEL_ID to
`Qwen/Qwen3-VL-4B-Instruct` in `services/ocr_server.py`.

**Performance**: ~190ms median per read, ~5GB VRAM

---

## Shield Inventory Commands

Track and use protection shields (8hr, 12hr, 24hr).

**CLI Commands**:
```bash
python scripts/daemon_cli.py get_shield_inventory    # Read counts from bag
python scripts/daemon_cli.py use_shield --shield_type 8hr   # Activate 8hr shield
python scripts/daemon_cli.py use_shield --shield_type 12hr  # Activate 12hr shield
python scripts/daemon_cli.py use_shield --shield_type 24hr  # Activate 24hr shield
```

**API Endpoints**:
```
POST /api/shields/refresh  # Refresh inventory from bag
POST /api/shields/use      # Use shield: {"shield_type": "8hr"}
```

**Auto-refresh**: Every 6 hours when daemon is idle

**State** (`data/daemon_current_state.json`):
```json
{
  "shield_inventory": {
    "8hr": 8,
    "12hr": 7,
    "24hr": 3,
    "timestamp": "2026-01-31T..."
  }
}
```

---

## Under Attack Detection

Continuous monitoring for incoming attacks.

**Detection**: `utils/under_attack_matcher.py` - template matching in daemon loop

**Events logged to frontend**:
- `under_attack` / `detected` - attack started (combat category, critical)
- `under_attack` / `ended` - attack stopped

**State** (`data/daemon_current_state.json`):
```json
{
  "under_attack": {
    "is_under_attack": false,
    "last_detected": "2026-01-31T...",
    "attack_count_today": 3
  }
}
```

**Frontend**: Red alert banner with quick shield activation buttons

---

## Bloodlust Detection

Monitors for bloodlust state (crossed swords icon). Lasts ~15 minutes.

**Detection**: `utils/bloodlust_matcher.py` - checks position (283, 287)

**Template**: `bloodlust_icon_4k.png` (62x62)

**Events logged to frontend**:
- `bloodlust` / `started` - bloodlust began (combat category)
- `bloodlust` / `ended` - bloodlust ended with duration

**State** (`data/daemon_current_state.json`):
```json
{
  "bloodlust": {
    "is_active": true,
    "started_at": "2026-01-31T...",
    "expected_end": "2026-01-31T..."
  }
}
```

**Frontend**: Orange banner with 15-minute countdown

**CLI**:
```bash
python utils/bloodlust_matcher.py  # Test detection on current screen
```

---

## Shield Active Detection

Detects if player already has shield protection active.

**Detection**: `utils/shield_active_matcher.py` - checks position (283, 287)

**Template**: `shield_active_icon_4k.png` (62x62, blue glowing shield)

**Behavior**: Shield use flow automatically checks before activating:
- If shield active → returns `shield_already_active: true`, skips
- Use `--force` flag to override and apply new shield anyway

**CLI**:
```bash
python utils/shield_active_matcher.py  # Test detection

# Normal use (skips if shield active)
python scripts/daemon_cli.py use_shield --shield_type 8hr

# Force (use even if shield active)
python scripts/daemon_cli.py use_shield --shield_type 8hr --force
```

---

## Shield Scheduling

Schedule shield activation with delay via frontend or API.

**Time Formats**:
- `5m` - 5 minutes
- `1h 30m` - 1 hour 30 minutes
- `9m 13s` - 9 minutes 13 seconds
- `10:30` - activate at 10:30 (next occurrence)

**API Endpoints**:
```
POST /api/shields/schedule
{"shield_type": "8hr", "delay_seconds": 553}

GET /api/shields/scheduled
Returns: {"scheduled": true, "shield_type": "8hr", "activate_at": "..."}

POST /api/shields/cancel
Cancels pending scheduled shield
```

**Frontend**:
- Clock icon button next to shields opens schedule modal
- Yellow banner shows countdown when scheduled
- Cancel button to abort

---

## IMPORTANT: Daemon Management

**NEVER start the daemon.** User manages startup.

Claude can ONLY:
- Trigger flows via WebSocket (when daemon running)
- Check daemon status
- Kill rogue processes if asked

```bash
# Check if running
powershell -Command "Get-Process python* | Format-Table Id, ProcessName"

# Check log
powershell -Command "Get-Content 'C:\Users\mail\xclash\logs\current_daemon.log' -Tail 20"
```
