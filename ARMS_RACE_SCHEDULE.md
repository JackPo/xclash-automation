# Arms Race Schedule

Reference table for the Arms Race rotation. For automation logic and triggers, see `docs/arms_race.md`.

The Arms Race event follows a **7-day cycle with 42 total events** (6 events per day, every 4 hours).

IMPORTANT: This is NOT a simple 5-activity rotation. The pattern shifts by one activity each day.

## Key Facts

- **7 days per cycle** (Days 1-7, then repeats)
- **6 events per day** at fixed times: 02:00, 06:00, 10:00, 14:00, 18:00, 22:00 UTC
- **4 hours per event**
- **Day 1 always starts Wednesday** at 02:00 UTC (Tuesday 6PM PT)
- **168 hours total** (7 days × 24 hours) per cycle
- **Reference point**: December 4, 2025, 02:00 UTC = Day 1 start

## Activity Types

1. **City Construction**
2. **Soldier Training**
3. **Technology Research**
4. **Mystic Beast Training**
5. **Enhance Hero**

## Full 7-Day Schedule

### Day 1 (Wednesday)
| UTC Time | PT Time | Event |
|----------|---------|-------|
| 02:00 | Tue 6:00 PM | Enhance Hero |
| 06:00 | Tue 10:00 PM | City Construction |
| 10:00 | Wed 2:00 AM | Soldier Training |
| 14:00 | Wed 6:00 AM | Technology Research |
| 18:00 | Wed 10:00 AM | Mystic Beast Training |
| 22:00 | Wed 2:00 PM | Enhance Hero |

### Day 2 (Thursday)
| UTC Time | PT Time | Event |
|----------|---------|-------|
| 02:00 | Wed 6:00 PM | City Construction |
| 06:00 | Wed 10:00 PM | Soldier Training |
| 10:00 | Thu 2:00 AM | Technology Research |
| 14:00 | Thu 6:00 AM | Mystic Beast Training |
| 18:00 | Thu 10:00 AM | Enhance Hero |
| 22:00 | Thu 2:00 PM | City Construction |

### Day 3 (Friday)
| UTC Time | PT Time | Event |
|----------|---------|-------|
| 02:00 | Thu 6:00 PM | Soldier Training |
| 06:00 | Thu 10:00 PM | Technology Research |
| 10:00 | Fri 2:00 AM | Mystic Beast Training |
| 14:00 | Fri 6:00 AM | Enhance Hero |
| 18:00 | Fri 10:00 AM | City Construction |
| 22:00 | Fri 2:00 PM | Soldier Training |

### Day 4 (Saturday)
| UTC Time | PT Time | Event |
|----------|---------|-------|
| 02:00 | Fri 6:00 PM | Technology Research |
| 06:00 | Fri 10:00 PM | Mystic Beast Training |
| 10:00 | Sat 2:00 AM | Enhance Hero |
| 14:00 | Sat 6:00 AM | City Construction |
| 18:00 | Sat 10:00 AM | Soldier Training |
| 22:00 | Sat 2:00 PM | Technology Research |

### Day 5 (Sunday)
| UTC Time | PT Time | Event |
|----------|---------|-------|
| 02:00 | Sat 6:00 PM | Mystic Beast Training |
| 06:00 | Sat 10:00 PM | Enhance Hero |
| 10:00 | Sun 2:00 AM | City Construction |
| 14:00 | Sun 6:00 AM | Soldier Training |
| 18:00 | Sun 10:00 AM | Technology Research |
| 22:00 | Sun 2:00 PM | Mystic Beast Training |

### Day 6 (Monday)
| UTC Time | PT Time | Event |
|----------|---------|-------|
| 02:00 | Sun 6:00 PM | Enhance Hero |
| 06:00 | Sun 10:00 PM | City Construction |
| 10:00 | Mon 2:00 AM | Soldier Training |
| 14:00 | Mon 6:00 AM | Technology Research |
| 18:00 | Mon 10:00 AM | Mystic Beast Training |
| 22:00 | Mon 2:00 PM | Enhance Hero |

### Day 7 (Tuesday)
| UTC Time | PT Time | Event |
|----------|---------|-------|
| 02:00 | Mon 6:00 PM | City Construction |
| 06:00 | Mon 10:00 PM | Soldier Training |
| 10:00 | Tue 2:00 AM | Technology Research |
| 14:00 | Tue 6:00 AM | Mystic Beast Training |
| 18:00 | Tue 10:00 AM | Enhance Hero |
| 22:00 | Tue 2:00 PM | City Construction |

After Day 7 ends, the cycle repeats back to Day 1 (Wednesday 02:00 UTC).

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
=== Arms Race Status (Day 1) ===
Current:  Soldier Training
Previous: City Construction
Next:     Technology Research

Time elapsed:   00:43:49
Time remaining: 03:16:10

Started:  2025-12-04 10:00:00 UTC
Ends:     2025-12-04 14:00:00 UTC
```

## Timing Functions

### Get Time Until Soldier Training

To optimize automation for Soldier Training events:

```python
from utils.arms_race import get_time_until_soldier_training

time_until = get_time_until_soldier_training()

if time_until.total_seconds() == 0:
    print("Soldier Training is ACTIVE NOW!")
else:
    hours = time_until.total_seconds() / 3600
    print(f"Soldier Training starts in {hours:.2f} hours")
```

This searches forward through the 42-event schedule to find the next Soldier Training event and returns the time until it starts.

## Pattern Analysis

The schedule follows a **shift pattern**:
- Each day, the starting activity shifts by **+1 position** in the 5-activity cycle
- Day 1 starts: Enhance Hero
- Day 2 starts: City Construction (shifted +1)
- Day 3 starts: Soldier Training (shifted +1)
- Day 4 starts: Technology Research (shifted +1)
- Day 5 starts: Mystic Beast Training (shifted +1)
- Day 6 starts: Enhance Hero (wrapped around, shifted +1)
- Day 7 starts: City Construction (shifted +1)

## Related docs
- `docs/arms_race.md` for automation behavior and event-specific flows
