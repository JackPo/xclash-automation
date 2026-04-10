# Arms Race Automation

This document describes the Arms Race schedule and how the daemon automates event blocks. For the full schedule table, see `../ARMS_RACE_SCHEDULE.md`.

## Schedule model
- 7-day cycle, 6 blocks per day, 4 hours per block (42 blocks total).
- The starting activity shifts by one each day.
- Reference start: 2025-12-04 02:00 UTC (Day 1, block 1).
- Implementation: `utils/arms_race.py`.

Event types:
- City Construction
- Soldier Training
- Technology Research
- Mystic Beast Training
- Enhance Hero

## Automation coverage
Implemented:
- Mystic Beast Training (Beast Training) rallies and stamina management
- Enhance Hero upgrades
- Soldier Training promotions
- Technology Research (queue OCR + speedup)
- City Construction (queue OCR + speedup)

All Arms Race events are now automated.

See `future_steps.md` for the roadmap and missing features.

## Mystic Beast Training automation
Mystic Beast uses a smart flow that combines points checks, stamina claims, and rally targets.

### Pre-event stamina claim
- Window: `ARMS_RACE_BEAST_TRAINING_PRE_EVENT_MINUTES` before the event.
- If the stamina red dot is visible, the daemon runs `stamina_claim_flow` to start the 4-hour cooldown early.
- Elite Zombie rallies are blocked in this window to preserve stamina.

### Hour-mark and last-6-minute phases
Two scheduled phases compute rally targets from the Arms Race panel and optionally claim stamina items:
- Hour mark: runs once when the last-hour window begins.
- Last 6 minutes: re-checks points and claims again if needed.

These phases:
- Open the Arms Race panel and OCR current points.
- Compute rallies needed to reach chest 3 (based on event metadata).
- Use `claude_cli_helper` to decide whether to claim free stamina or consume items.
- Persist targets into the scheduler state for the current block.

Deep dive: `BEAST_TRAINING_LOGIC.md`.

### Rally loop
During the last `ARMS_RACE_BEAST_TRAINING_LAST_MINUTES` of the event:
1. Validate stamina via consecutive OCR readings.
2. If stamina >= `ARMS_RACE_BEAST_TRAINING_STAMINA_THRESHOLD` and under target, run `elite_zombie_flow` with configured `level_clicks`.
3. If stamina < `ARMS_RACE_STAMINA_CLAIM_THRESHOLD` and red dot visible, run `stamina_claim_flow`.
4. If stamina is low and a free claim will not arrive before event end, run `stamina_use_flow` (subject to cooldown and max-use limits).

## Zombie Level Management

Both `elite_zombie_flow` and `zombie_attack_flow` support a signed `level_clicks` parameter:
- **Positive values** (+1, +2, etc.): Click the plus button to increase zombie level
- **Negative values** (-1, -2, etc.): Click the minus button to decrease zombie level
- **Zero**: No level adjustment, use whatever level the game defaults to

### Season 1 Behavior

In Season 1, the game automatically increases the zombie level after each successful attack. This creates a problem: the automation keeps succeeding, the level keeps increasing, and eventually your troops get killed because the zombie is too strong.

**Solution**: Set `level_clicks` to a negative value (e.g., -1) to dial back the level before each attack, counteracting the automatic level increase.

### Configuration

In `config_local.py`:
```python
# Elite zombie (standalone attacks when stamina >= 118)
ELITE_ZOMBIE_LEVEL_CLICKS = -1  # Click minus once before each rally

# All zombie modes (Beast Training automation)
ZOMBIE_MODE_CONFIG = {
    "elite": {"stamina": 20, "points": 2000, "flow": "elite_zombie", "level_clicks": -1},
    "gold": {"stamina": 10, "points": 1000, "flow": "zombie_attack", "zombie_type": "gold", "level_clicks": -1},
    "food": {"stamina": 10, "points": 1000, "flow": "zombie_attack", "zombie_type": "food", "level_clicks": -1},
    "iron_mine": {"stamina": 10, "points": 1000, "flow": "zombie_attack", "zombie_type": "iron_mine", "level_clicks": -1},
}
```

### CLI Usage

Run zombie attacks with specific level adjustments:
```bash
# Gold zombie, click minus twice
python scripts/daemon_cli.py run_zombie_attack gold --level-clicks -2

# Iron mine zombie, click plus once
python scripts/daemon_cli.py run_zombie_attack iron_mine --level-clicks 1
```

Key safeguards:
- Recovery item use is capped by `ARMS_RACE_BEAST_TRAINING_USE_MAX` and `ARMS_RACE_BEAST_TRAINING_USE_COOLDOWN`.

### Frozen Zombie Handling

Zombies can become "frozen" after being attacked. Frozen zombies display both a Rally button AND an Unfreeze button simultaneously.

**Detection**: The flow checks for the Unfreeze button BEFORE checking for Rally. If a frozen zombie is detected:

1. Click Unfreeze button
2. If march screen appears, click March to complete unfreeze
3. Retry the search to find a non-frozen zombie or the now-unfrozen zombie
4. Continue with normal rally flow

**Templates**:
- `unfreeze_button_4k.png` + `unfreeze_button_mask_4k.png` - Unfreeze button detection

**Why this matters**: If the flow clicks Rally on a frozen zombie without unfreezing first, the rally screen won't open and the flow fails.
- The 3rd+ use requires the event to be within `ARMS_RACE_BEAST_TRAINING_USE_LAST_MINUTES`.
- If the free-claim timer will expire before the event ends, the daemon waits instead of using items.

## Enhance Hero automation
- Trigger: last `ARMS_RACE_ENHANCE_HERO_LAST_MINUTES` of the Enhance Hero block.
- The flow checks Arms Race points; if chest 3 is already reached, it skips upgrades.
- Otherwise, it upgrades heroes with red notification dots, capped by `ARMS_RACE_ENHANCE_HERO_MAX_UPGRADES`.
- Progress check does not require idle time; actual upgrades do.

## Soldier Training automation
- Trigger: during Soldier Training blocks, or all day on VS promotion days (`VS_SOLDIER_PROMOTION_DAYS`).
- Requires idle time, TOWN view, and dog house alignment.
- Barracks state detection identifies READY and PENDING bubbles.
- READY bubbles are collected; PENDING bubbles are upgraded using `soldier_upgrade_flow`.
- Normal training outside promotion windows uses `soldier_training_flow` and may time training to finish before the next promotion opportunity.

## Technology Research automation
- Trigger: last `ARMS_RACE_TECH_RESEARCH_LAST_MINUTES` (20 min) of the Technology Research block.
- If points < chest 3 threshold (30,000), runs speedup flow.

### Points calculation
- 1 CP (research completion point) = 1 Arms Race point
- 1 minute of speedup = 10 Arms Race points
- Frontend displays `speedup_minutes_needed` = points_gap / 10

### Speedup flow (`technology_research_speedup_flow`)
1. Open Research Queue panel from town view
2. OCR both queue times (queue 1 = in progress, queue 2 = queued)
3. Pick the **smaller queue** (more efficient use of speedups)
4. Click Speed Up button for that queue
5. Click Quick Speedup button (uses available free speedups)
6. Click Confirm
7. If research completes (time = 00:00:00), click Complete button
8. Close panel

### Queue detection
- Queue 1 time region: (1616, 954, 365, 35)
- Queue 2 time region: (1601, 1194, 464, 56)
- Speed Up button positions: Queue 1 = (2305, 978), Queue 2 = (2305, 1235)

### State tracking
Research queue times are saved to `daemon_current_state.json` for frontend display:
- `research_queue.queue1_seconds`, `queue1_name`
- `research_queue.queue2_seconds`, `queue2_name`

## City Construction automation
- Trigger: last `ARMS_RACE_CONSTRUCTION_LAST_MINUTES` (20 min) of the City Construction block.
- If points < chest 3 threshold (30,000), runs speedup flow.
- Same points calculation as Technology Research: 1 minute speedup = 10 points.

### Speedup flow (`city_construction_speedup_flow`)
Identical logic to Technology Research:
1. Open Construction Queue panel from town view (hammer button)
2. OCR both queue times
3. Pick the **smaller queue** (more efficient use of speedups)
4. Click Speed Up → Quick Speedup → Confirm
5. If construction completes, click Complete button
6. Close panel

### Queue detection
- Queue 1 time region: (1735, 671, 246, 43)
- Queue 2 time region: (1724, 926, 215, 28)
- Speed Up button positions: Queue 1 = (2253, 672), Queue 2 = (2252, 918)

### State tracking
Construction queue times are saved to `daemon_current_state.json` for frontend display:
- `construction_queue.queue1_seconds`, `queue1_name`
- `construction_queue.queue2_seconds`, `queue2_name`

## VS day overrides
- `VS_SOLDIER_PROMOTION_DAYS`: enables promotions all day, regardless of the current 4-hour block.
- `VS_LEVEL_CHEST_DAYS`: Day 7 opens level chests near the end of the day via bag flow checkpoints.
- `VS_QUESTION_MARK_SKIP_DAYS`: skips question-mark quests on specific days (tavern logic).

## Progress data collection
In the last 10 minutes of every Arms Race block, the daemon records points for diagnostics and threshold tuning.

## Related docs
- `../ARMS_RACE_SCHEDULE.md` for the full schedule table
- `BEAST_TRAINING_LOGIC.md` for the smart beast training flow
- `future_steps.md` for roadmap and missing features
