# Arms Race Event Automation

This document describes the automation triggers and logic for Arms Race events.

## Arms Race Event Schedule

Arms Race rotates through 5 activities every 4 hours (UTC-based):

| Event | Duration | Description |
|-------|----------|-------------|
| City Construction | 4 hours | Building upgrades earn points |
| Soldier Training | 4 hours | Training soldiers earns points |
| Tech Research | 4 hours | Research earns points |
| **Mystic Beast** | 4 hours | Beast training/zombie rallies earn points |
| **Enhance Hero** | 4 hours | Hero upgrades earn points |

The rotation repeats every 20 hours (5 events x 4 hours each).

## Beast Training Automation (Mystic Beast Event)

**When**: Last 60 minutes of the Mystic Beast event block

**Purpose**: Automatically train beasts via elite zombie rallies to earn Arms Race points

### Trigger Conditions

```
ARMS_RACE_BEAST_TRAINING_ENABLED = True
ARMS_RACE_BEAST_TRAINING_LAST_MINUTES = 60  # Trigger in last hour
```

### Rally Logic

Rallies are triggered when:
1. Current event is "Mystic Beast"
2. Remaining time <= 60 minutes
3. Stamina confirmed >= 20 (3 consecutive OCR readings)
4. Rally cooldown elapsed (90 seconds between rallies)

```python
# Rally conditions
if stamina >= 20 and rally_cooldown_ok:
    trigger elite_zombie_flow with 0 plus clicks
    rally_count += 1
```

### Stamina Claim Logic

During Beast Training, the daemon will claim free stamina when available (every 4 hours).

**Conditions** (BOTH must be true):
1. Stamina < 60 (threshold)
2. **Red notification dot visible** on stamina display (indicates free claim available)

```python
ARMS_RACE_STAMINA_CLAIM_THRESHOLD = 60
```

**Red Dot Detection** (`utils/stamina_red_dot_detector.py`):
- Checks 25x20 pixel region to the RIGHT of stamina bar (offset: X+101, Y+20)
- Position: (170, 223) absolute screen coordinates
- Red pixel criteria: B<100, G<100, R>150 (BGR color space)
- Threshold: 100+ red pixels = dot present (out of 500 total)
- Prevents false positives when claim isn't actually available

**Flow**: `stamina_claim_flow`
1. Daemon detects red dot on stamina display (without opening popup)
2. Click stamina display to open popup
3. Detect Claim button via template matching
4. Click Claim if found
5. Click back button (1407, 2055) to close popup
6. Run back_from_chat_flow for cleanup

**Why Red Dot Check?**
Without the red dot check, the daemon would trigger the claim flow every 3 seconds when stamina < 60, even when no free claim is available. The red dot ensures we only attempt to claim when the free stamina is actually ready.

### Stamina Use Button Logic (Recovery Items)

When stamina runs low during Beast Training and no free Claim is available, the daemon can use stamina recovery items (+50 each).

**Conditions** (ALL must be true):
1. User idle since the START of the Mystic Beast block
2. Rally count < 15 (don't waste items if already did many rallies)
3. No Claim button triggered this iteration (claim first if possible)
4. Stamina < 20 (threshold)
5. Use button clicks < 4 per block (max usage)
6. Use button cooldown elapsed (3 minutes between uses)

```python
# Config values
ARMS_RACE_BEAST_TRAINING_USE_ENABLED = True
ARMS_RACE_BEAST_TRAINING_USE_MAX = 4           # Max 4 uses per block
ARMS_RACE_BEAST_TRAINING_USE_COOLDOWN = 180    # 3 minutes
ARMS_RACE_BEAST_TRAINING_MAX_RALLIES = 15      # Don't use if >= 15 rallies
ARMS_RACE_BEAST_TRAINING_USE_STAMINA_THRESHOLD = 20
```

**Flow**: `stamina_use_flow`
1. Click stamina display to open popup
2. Detect Use button via template matching
3. Click Use if found (+50 stamina)
4. Click back button (1407, 2055) to close popup
5. Run back_from_chat_flow for cleanup

### Tracking Per Block

Counters reset when a new Beast Training block starts:
- `beast_training_rally_count` - Total rallies this block
- `beast_training_use_count` - Use button clicks this block
- `beast_training_current_block` - Timestamp of current block start

### Priority Order

1. **Claim** (free stamina every 4 hours) - Always try first if stamina < 60
2. **Use** (recovery items) - Only if idle entire block, rally count < 15, no claim available, stamina < 20
3. **Rally** - If stamina >= 20 and cooldown elapsed

## Soldier Training Automation (Soldier Training Event)

**When**: During the Soldier Training event block (4 hours)

**Purpose**: Train soldiers to earn Arms Race points by:
1. Collecting ready soldiers (yellow bubble)
2. Starting new training (white bubble)

### Barracks State Detection

The daemon continuously monitors 4 barracks buildings via floating bubble icons:

| State | Bubble | Meaning | Action |
|-------|--------|---------|--------|
| **READY** | Yellow soldier face | Soldiers ready to collect | Click to collect |
| **PENDING** | White soldier face | Idle, can start training | Click to train |
| **TRAINING** | Orange stopwatch | Currently training | Wait |
| **UNKNOWN** | No match | Detection failed | Skip |

### Barracks Positions (4K)

| Barrack | Position (x, y) | Location |
|---------|-----------------|----------|
| 1 | (2891, 1317) | Lowest/rightmost |
| 2 | (2768, 1237) | Middle left |
| 3 | (3005, 1237) | Middle right |
| 4 | (2883, 1157) | Highest/center |

### Templates

Templates in `templates/ground_truth/`:

| Template | Size | Description |
|----------|------|-------------|
| `yellow_soldier_barrack_4k.png` | 81x87 | READY state (collect) |
| `white_soldier_barrack_4k.png` | 81x87 | PENDING state (train) |
| `stopwatch_barrack_4k.png` | 81x87 | TRAINING state (wait) |

### Daemon Output

Barracks state is logged in the main loop:

```
[1] 15:30:45 [TOWN] Stamina:85 idle:2m AR:Sol(45m) Barracks:[B1:P B2:T B3:T B4:T] ...
```

State codes:
- `R` = READY (yellow) - soldiers ready
- `P` = PENDING (white) - can train
- `T` = TRAINING (stopwatch) - in progress
- `?` = UNKNOWN - detection failed

### Implementation Status

**Completed**:
- [x] Barracks state matcher (`utils/barracks_state_matcher.py`)
- [x] Three state templates extracted and saved
- [x] Continuous monitoring in icon_daemon
- [x] Status display in daemon output

**TODO**:
- [ ] Soldier collection flow (click READY barracks)
- [ ] Soldier training flow (click PENDING barracks, select soldier level)
- [ ] Arms Race trigger logic (only during Soldier Training event)
- [ ] Soldier level selection (Lv7/Lv8 based on resources)

### Matcher Details

```python
from utils.barracks_state_matcher import BarracksStateMatcher, format_barracks_states

# Get all states
matcher = BarracksStateMatcher()
states = matcher.get_all_states(frame)  # [(BarrackState, score), ...]

# Get formatted string
barracks_str = format_barracks_states(frame)  # "B1:R B2:T B3:P B4:T"
```

Match threshold: 0.06 (TM_SQDIFF_NORMED - lower is better)

---

## Enhance Hero Automation

**When**: Last 20 minutes of the Enhance Hero event block

**Purpose**: Upgrade heroes to earn Arms Race points

### Trigger Conditions

```
ARMS_RACE_ENHANCE_HERO_ENABLED = True
ARMS_RACE_ENHANCE_HERO_LAST_MINUTES = 20
```

### Trigger Logic

The automation triggers when:
1. Current event is "Enhance Hero"
2. Remaining time <= 20 minutes
3. User has been idle since the START of the Enhance Hero block (not just 5 min)
4. Haven't triggered for this block yet

```python
# Idle check
time_elapsed_secs = time since block started
if idle_secs >= time_elapsed_secs:
    trigger hero_upgrade_arms_race_flow
    mark block as triggered
```

**Important**: This ensures we don't interrupt active gameplay. The user must have been AFK the entire duration of the Enhance Hero block.

### Flow

`hero_upgrade_arms_race_flow` handles the hero upgrade process.

## Configuration Reference

All Arms Race settings in `config.py`:

```python
# Beast Training (during Mystic Beast event)
ARMS_RACE_BEAST_TRAINING_ENABLED = True
ARMS_RACE_BEAST_TRAINING_LAST_MINUTES = 60
ARMS_RACE_BEAST_TRAINING_STAMINA_THRESHOLD = 20
ARMS_RACE_BEAST_TRAINING_COOLDOWN = 90         # 90s between rallies

# Stamina Claim
ARMS_RACE_STAMINA_CLAIM_THRESHOLD = 60         # Claim when stamina < 60

# Use Button (stamina recovery items)
ARMS_RACE_BEAST_TRAINING_USE_ENABLED = True
ARMS_RACE_BEAST_TRAINING_USE_MAX = 4           # Max 4 per block
ARMS_RACE_BEAST_TRAINING_USE_COOLDOWN = 180    # 3 min between uses
ARMS_RACE_BEAST_TRAINING_MAX_RALLIES = 15      # Don't use if >= 15 rallies
ARMS_RACE_BEAST_TRAINING_USE_STAMINA_THRESHOLD = 20

# Enhance Hero
ARMS_RACE_ENHANCE_HERO_ENABLED = True
ARMS_RACE_ENHANCE_HERO_LAST_MINUTES = 20
```

## Stamina Flow Templates

Templates in `templates/ground_truth/`:

| Template | Size | Position | Use |
|----------|------|----------|-----|
| `claim_button_4k.png` | 256x107 | (2156, 690) | Claim button in stamina popup |
| `use_button_4k.png` | 271x118 | (2149, 1381) | Use button in stamina popup |

Click positions:
- Claim button: (2284, 743)
- Use button: (2284, 1440)
- Stamina display: (117, 233) - to open popup

## Logging

The daemon logs all Arms Race actions with the `[BEAST TRAINING]` or `[ENHANCE HERO]` prefix:

```
[123] BEAST TRAINING: New block started, rally count reset to 0, use count reset to 0
[124] BEAST TRAINING: Stamina 45 < 60, triggering stamina claim...
[125] BEAST TRAINING: Stamina 15 < 20, using recovery item (use #1/4, rally #3/15)...
[126] BEAST TRAINING: Mystic Beast (45min left), stamina=65, triggering rally #4...
```

## Decision Flow Diagram

```
During Mystic Beast last 60 minutes:
    |
    +-- New block? --> Reset rally_count=0, use_count=0
    |
    +-- Stamina < 60?
    |       |
    |       YES --> Trigger stamina_claim_flow
    |
    +-- Idle since block start AND stamina < 20 AND rallies < 15
    |   AND uses < 4 AND use_cooldown_ok AND claim not just triggered?
    |       |
    |       YES --> Trigger stamina_use_flow
    |                use_count += 1
    |
    +-- Stamina >= 20 AND rally_cooldown_ok?
            |
            YES --> Trigger elite_zombie_flow (0 plus clicks)
                    rally_count += 1
```
