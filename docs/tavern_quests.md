# Tavern Quests

This doc explains how tavern claim/scan/dispatch are triggered by the daemon and why a claim can still be missed in edge timing cases.

## Modes
- `claim`: clicks ready `Claim` buttons.
- `scan`: OCRs timer rows, saves completion times, then runs a dispatch follow-up attempt.
- `dispatch`: starts quests via `Go` + bounty dialog (`Auto Dispatch` + `Proceed`).
- `ally`: assists ally quests.

## Claim Trigger Path
1. `scan` writes completion timestamps to scheduler state (`tavern_quests.completions`).
2. Main daemon loop checks imminent completion:
   - `is_tavern_completion_imminent(buffer_seconds=7)` in `scripts/icon_daemon.py`.
   - Scheduler condition is strict future-only: `0 < time_until <= buffer_seconds`.
3. If imminent, daemon starts `tavern_claim` (critical flow) and runs bounded retries (`_run_tavern_claim_with_retries`, up to 5 attempts).

## Guard / Blocking Rules
- Tavern guard blocks non-exempt critical flows near completion windows.
- Exempt flows are `treasure_map` and `tavern_claim`.
- Guard also treats recent overdue completions as urgent for up to 600s (`TAVERN_OVERDUE_GUARD_GRACE_SECONDS`).

Important:
- Guard does not itself create a `tavern_claim` candidate.
- Retry logic only runs after `tavern_claim` has started.

## Why a Claim Can Still Be Missed
A miss can happen when all of these occur:
1. Completion lands while another flow is actively running.
2. The 7-second imminent window is missed.
3. No claim candidate is created afterward (because the trigger is future-only).
4. By the next tavern interaction, overdue age is beyond the 600-second grace window.

In this case, you may see repeated `flow:tavern_quest:open_tavern` taps with no `flow:tavern_quest:claim` tap in `logs/clicks.log`.

## Fast Verification Checklist
1. Check latest claim tap in `logs/clicks.log`:
   - search for `flow:tavern_quest:claim`
2. Compare against scheduler completions:
   - `data/daemon_schedule.json` -> `tavern_quests.completions`
3. Check whether tavern opens occurred without claim taps:
   - search for `flow:tavern_quest:open_tavern`
4. If needed, inspect debug screenshots:
   - `screenshots/debug/tavern_*`
