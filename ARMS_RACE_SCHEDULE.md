# Arms Race Schedule

The Arms Race event has two overlapping cycles:
1. **Activity Rotation**: 5 activities rotating every 4 hours
2. **Day Counter**: 7-day week that increments with each activity block

## Activity Rotation (5 activities, 4 hours each)

1. City Construction
2. Soldier Training
3. Tech Research
4. Mystic Beast
5. Enhance Hero

Each activity runs for 4 hours, then rotates to the next. After "Enhance Hero", it wraps back to "City Construction". The full activity cycle is 20 hours.

## Day Counter (7-day week)

The game displays a "Day X" counter (1-7) that increments with each 4-hour activity block. This is a separate 7-day cycle that doesn't align with the 5-activity rotation.

## Usage

```python
from utils.arms_race import get_arms_race_status

status = get_arms_race_status()
print(f"Day {status['day']}: {status['current']}")
print(f"Next: {status['next']}")
print(f"Time remaining: {status['time_remaining']}")
```

Or run directly:
```bash
python utils/arms_race.py
```

Example output:
```
=== Arms Race Status (Day 5) ===
Current:  Mystic Beast
Previous: Tech Research
Next:     Enhance Hero

Time elapsed:   02:00:00
Time remaining: 02:00:00

Started:  2025-12-01 22:00:00 UTC
Ends:     2025-12-02 02:00:00 UTC
```

## Calibration

Reference point (used for calculations):
- **2025-12-02 02:00 UTC** = Start of Day 6, "Enhance Hero" block

## Timing Functions

### Get Time Until Soldier Training

To optimize barracks training for the Soldier Training event:

```python
from utils.arms_race import get_time_until_soldier_training

time_until = get_time_until_soldier_training()

if time_until.total_seconds() == 0:
    print("Soldier Training is ACTIVE NOW!")
else:
    hours = time_until.total_seconds() / 3600
    print(f"Soldier Training starts in {hours:.2f} hours")
```

This returns:
- `timedelta(0)` if Soldier Training is currently active
- `timedelta` representing time until the next Soldier Training block starts

### Practical Use: Barracks Training Flow

Queue soldier training to complete right when Soldier Training starts:

```python
from utils.arms_race import get_time_until_soldier_training
from utils.adb_helper import ADBHelper
from scripts.flows.barracks_training_flow import barracks_training_flow

time_until = get_time_until_soldier_training()
target_hours = time_until.total_seconds() / 3600

adb = ADBHelper()
barracks_training_flow(adb, soldier_level=4, target_hours=target_hours, debug=True)
```

**Requirements:**
1. OCR server must be running: `python services/ocr_server.py`
2. Training panel must already be open (click a PENDING barrack bubble first)

See `docs/arms_race.md` for detailed flow documentation.
