# Beast Training (Mystic Beast) Arms Race Logic

## Overview

During "Mystic Beast Training" Arms Race events, the daemon automatically does Elite Zombie rallies to earn points toward Chest 3.

## Key Numbers

| Value | Amount | Notes |
|-------|--------|-------|
| Chest 3 target | 30,000 points | The goal for each event block |
| Points per stamina | 100 | Every stamina spent = 100 points |
| Stamina per rally | 20 | Each Elite Zombie rally costs 20 stamina |
| Points per rally | 2,000 | 20 × 100 = 2000 points per rally |
| Max rallies for Chest 3 | 15 | ceil(30000 / 2000) = 15 |

## Dynamic Target Calculation

The daemon calculates a **dynamic rally target** based on:

```
rallies_needed = ceil((30000 - current_points) / 2000)
```

But we don't blindly do 15 rallies. We check **actual progress** at the 1-hour mark.

### Example

If at 1-hour mark check:
- Current points: 18,000
- Points needed: 30,000 - 18,000 = 12,000
- Rallies needed: ceil(12,000 / 2,000) = **6 rallies**

## Stamina Budget

Each rally costs 20 stamina. Available stamina sources:

| Source | Amount | Cooldown | Notes |
|--------|--------|----------|-------|
| Free Claim | 50 | 4 hours | Button appears when timer expires |
| Recovery Items (Use) | 50 | None | From bag, limited quantity |
| Natural regen | ~10-15 | Continuous | Over 4 hours |

**Typical budget**: 20 (current) + 50 (free claim) + 50 (use) = **120 stamina = 6 rallies**

## Smart Stamina Management (Timer OCR)

The daemon OCRs the **claim timer** to decide whether to WAIT or USE recovery items:

```
When stamina < 20 and still need rallies:
  1. Open stamina popup
  2. Check if Claim button is visible
     - YES: Click it (free 50 stamina)
     - NO: OCR the countdown timer (HH:MM:SS format)
  3. Compare timer to event remaining time:
     - timer < event_remaining → WAIT for free claim
     - timer >= event_remaining → USE recovery item
```

**Timer Region**: (2161, 693) size 246x99 - where Claim button appears when available

**Example**:
- Event has 45 min remaining
- Timer shows 00:30:00 (30 min until free claim)
- 30 < 45 → WAIT for free claim instead of using recovery items

This saves recovery items for situations where the timer won't expire in time.

## Two-Phase Flow

### Phase 1: Hour Mark Check (at 1 hour into event)

1. Open Events → Arms Race panel
2. OCR current points from the panel
3. Calculate `rallies_needed = ceil((30000 - current_points) / 2000)`
4. Set `beast_training_target_rallies` = rallies_needed
5. Return to base view

**Trigger conditions**:
- Event is "Mystic Beast Training"
- 1 hour has passed since event start
- Idle 2+ minutes

### Phase 2: Rally Execution (continuous)

After target is set, daemon continuously:

1. Check stamina (needs ≥ 20)
2. If stamina OK and rally_count < target:
   - Run Elite Zombie flow
   - Increment `beast_training_rally_count`
3. If stamina < 20 and Use count < 4:
   - Click Use button to claim free 50 stamina
   - Increment `beast_training_use_count`

**Stops when**: `rally_count >= target` OR event ends

### Phase 3: Last 6 Minutes Check (optional)

In the last 6 minutes:
1. Re-check Arms Race panel
2. Update target based on actual progress
3. Final push to hit Chest 3

## State Tracking

Stored in `data/daemon_schedule.json` under `arms_race`:

```json
{
  "beast_training_rally_count": 0,      // Rallies done SINCE last panel check
  "beast_training_target_rallies": 6,   // Target based on actual points
  "beast_training_hour_mark_block": "2025-12-30 18:00:00+00:00"
}
```

## Points Are The Source of Truth

**Every time we check the Arms Race panel**, we:
1. OCR the actual current points
2. Calculate `rallies_needed = ceil((30000 - points) / 2000)`
3. **RESET `rally_count = 0`**
4. **SET `target = rallies_needed`**

This means the counter is ALWAYS recalculated from actual points:
- If a rally failed silently → points didn't increase → recalculate will still need that rally
- If we got bonus points from elsewhere → points are higher → recalculate will need fewer rallies
- No risk of counter getting out of sync with reality

**Example**: If panel shows 26000 points:
- Points needed: 30000 - 26000 = 4000
- Rallies needed: ceil(4000 / 2000) = 2
- Reset: `rally_count = 0`, `target = 2`
- Daemon does 2 rallies, incrementing `rally_count` to 2
- When `rally_count >= target` (2 >= 2), stop

## Config Parameters

In `config.py`:

```python
ARMS_RACE_BEAST_TRAINING_ENABLED = True           # Master enable
ARMS_RACE_BEAST_TRAINING_LAST_MINUTES = 60        # Only act in last 60 min
ARMS_RACE_BEAST_TRAINING_STAMINA_THRESHOLD = 20   # Min stamina to rally
ARMS_RACE_BEAST_TRAINING_COOLDOWN = 30            # Seconds between rallies
ARMS_RACE_BEAST_TRAINING_MAX_RALLIES = 15         # Fallback if no target set

# Use button settings
ARMS_RACE_BEAST_TRAINING_USE_ENABLED = True       # Enable free stamina claim
ARMS_RACE_BEAST_TRAINING_USE_MAX = 4              # Max Use clicks per block
ARMS_RACE_BEAST_TRAINING_USE_STAMINA_THRESHOLD = 20  # Use when stamina < this
```

## Flow Diagram

```
Event Start (every 4 hours)
    │
    ├── Wait 1 hour
    │
    ▼
Hour Mark Check
    │
    ├── OCR current points
    ├── Calculate rallies_needed
    ├── Set target
    │
    ▼
Rally Loop (while rally_count < target)
    │
    ├── Stamina ≥ 20? ──Yes──> Do Rally ──> Increment rally_count
    │         │
    │         No
    │         │
    │         ▼
    │   Red dot visible? ──Yes──> Claim free stamina (+50)
    │         │
    │         No
    │         │
    │         ▼
    │   OCR claim timer
    │         │
    │         ├── Timer < event remaining? ──Yes──> WAIT for free claim
    │         │
    │         No (timer too long or OCR failed)
    │         │
    │         ▼
    │   Use count < 4? ──Yes──> Click Use ──> Get 50 stamina
    │         │
    │         No
    │         │
    │         ▼
    │   Wait for natural regen
    │
    ▼
Event End (or target reached)
    │
    ├── Reset rally_count = 0
    ├── Reset use_count = 0
    ├── Clear target
    │
    ▼
Next Event Block
```

## Troubleshooting

**Q: Why isn't it doing rallies?**
- Check stamina (needs ≥ 20)
- Check idle time (needs 2+ min)
- Check if target already reached (rally_count >= target)
- Check if Use count maxed (use_count >= 4)

**Q: How do I manually set target?**
```bash
# Via daemon WebSocket API
python -c "
import asyncio, websockets, json
async def main():
    async with websockets.connect('ws://localhost:9876') as ws:
        await ws.send(json.dumps({'cmd': 'set_rally_target', 'args': {'target': 10}}))
        print(await ws.recv())
asyncio.run(main())
"
```

**Q: How do I check current state?**
```bash
cat data/daemon_schedule.json | python -c "import json,sys; d=json.load(sys.stdin); print(json.dumps(d['arms_race'], indent=2))"
```
