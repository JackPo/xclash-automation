# Mystic Beast Training (Smart Flow)

This document describes the smart Mystic Beast Training automation used during Arms Race. It complements `arms_race.md` and focuses on the point/target logic and stamina decision engine.

## Key numbers

Depends on **zombie mode** (configurable via WebSocket API):

| Mode | Stamina/Action | Points/Action | Actions for 30k |
|------|----------------|---------------|-----------------|
| elite (default) | 20 | 2,000 | 15 rallies |
| gold | 10 | 1,000 | 30 attacks |
| food | 10 | 1,000 | 30 attacks |
| iron_mine | 10 | 1,000 | 30 attacks |

- Points per stamina: 100 (same for all modes)
- Chest 3 target: 30000 (from `utils/arms_race.py` metadata)
- Same total stamina (300), zombie mode = 2x more actions

## Zombie Mode

Allows using regular zombie attacks instead of elite zombie rallies during Beast Training.

**WebSocket API:**
```bash
# Set gold mode for 24 hours
echo '{"cmd": "set_zombie_mode", "args": {"mode": "gold", "hours": 24}}' | websocat ws://127.0.0.1:9876

# Check current mode
echo '{"cmd": "get_zombie_mode"}' | websocat ws://127.0.0.1:9876

# Clear mode (revert to elite)
echo '{"cmd": "clear_zombie_mode"}' | websocat ws://127.0.0.1:9876

# Manual zombie attack (with custom type and plus_clicks)
echo '{"cmd": "run_zombie_attack", "args": {"zombie_type": "gold", "plus_clicks": 10}}' | websocat ws://127.0.0.1:9876
```

**`run_zombie_attack` arguments:**
- `zombie_type`: "gold", "food", or "iron_mine" (default: "gold")
- `plus_clicks`: Number of plus button clicks to increase level (default: 10)

**State storage** (`data/daemon_schedule.json`):
```json
{
  "zombie_mode": {
    "mode": "gold",
    "expires": "2025-01-04T06:00:00+00:00",
    "set_at": "2025-01-03T06:00:00+00:00"
  }
}
```

Mode auto-expires after set duration, reverting to elite.

## Goals
- Reach chest 3 without wasting stamina or recovery items.
- Use actual Arms Race points as the source of truth.

## Phases

### Phase 1: Hour mark check
Triggered once when the last-hour window begins.

Steps:
1. Open the stamina popup and capture inventory (owned 10/50 items and free-claim cooldown).
2. Open the Arms Race panel and OCR current points.
3. Compute rallies needed: `ceil((chest3 - current_points) / 2000)`.
4. Run the deterministic decision engine (see below) to decide free-claim and item usage.
5. Execute the decision and persist `beast_training_target_rallies` for the block.

### Phase 2: Last 6 minutes check
Triggered once in the last 6 minutes of the block.

Steps:
1. Re-check current points.
2. Recompute target rallies and reset the rally counter.
3. Claim free stamina or use items if needed.

### Continuous rally/attack loop
During the last `ARMS_RACE_BEAST_TRAINING_LAST_MINUTES` of the block:
- If stamina >= threshold (20 for elite, 10 for zombie) and under target:
  - **Elite mode**: run `elite_zombie_flow` with zero plus-clicks
  - **Zombie mode**: run `zombie_attack_flow` with configured zombie_type and plus_clicks
- If stamina < `ARMS_RACE_STAMINA_CLAIM_THRESHOLD` and the red dot is visible, run `stamina_claim_flow`.
- If stamina is low and a free claim will not arrive before the event ends, run `stamina_use_flow`.

## Stamina decision engine
Implementation: `utils/claude_cli_helper.py` and `utils/stamina_popup_helper.py`.

Despite the name, the decision engine is deterministic and does not call Claude. It uses:
- Current stamina
- Item inventory (10 and 50 stamina items)
- Free-claim cooldown
- Time remaining in the block

Decision rules (simplified):
- Round required stamina up to the next multiple of 20.
- Claim free 50 if ready, or if it will be ready before the block ends.
- Prefer 50 items for bulk, 10 items for remainder.
- Avoid using items if a free claim will arrive in time.

## Scheduler state
Stored in `data/daemon_schedule.json` under `arms_race`:
- `beast_training_target_rallies`
- `beast_training_rally_count`
- `beast_training_hour_mark_block`
- `beast_training_last_6_block`

The rally counter is reset whenever points are re-checked. Points are the source of truth.

## Related docs
- `arms_race.md` for the full event automation overview
- `../ARMS_RACE_SCHEDULE.md` for the schedule table
