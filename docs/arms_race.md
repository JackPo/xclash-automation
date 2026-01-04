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

Not implemented:
- City Construction
- Technology Research

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
2. If stamina >= `ARMS_RACE_BEAST_TRAINING_STAMINA_THRESHOLD` and under target, run `elite_zombie_flow` with zero plus-clicks.
3. If stamina < `ARMS_RACE_STAMINA_CLAIM_THRESHOLD` and red dot visible, run `stamina_claim_flow`.
4. If stamina is low and a free claim will not arrive before event end, run `stamina_use_flow` (subject to cooldown and max-use limits).

Key safeguards:
- Recovery item use is capped by `ARMS_RACE_BEAST_TRAINING_USE_MAX` and `ARMS_RACE_BEAST_TRAINING_USE_COOLDOWN`.
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

## VS day overrides
- `VS_SOLDIER_PROMOTION_DAYS`: enables promotions all day, regardless of the current 4-hour block.
- `VS_LEVEL_CHEST_DAYS`: Day 7 opens level chests near the end of the day via bag flow checkpoints.
- `VS_QUESTION_MARK_SKIP_DAYS`: skips question-mark quests on specific days (tavern logic).

## Progress data collection
In the last 10 minutes of every Arms Race block, the daemon records points for diagnostics and future threshold discovery. This is used for unautomated events like City Construction and Technology Research.

## Related docs
- `../ARMS_RACE_SCHEDULE.md` for the full schedule table
- `BEAST_TRAINING_LOGIC.md` for the smart beast training flow
- `future_steps.md` for roadmap and missing features
