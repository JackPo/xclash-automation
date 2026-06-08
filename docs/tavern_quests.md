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

## Open-count budget per trigger

The tavern menu costs a noticeable open+animation each time we tap it.
Each entry point's typical open count:

| Trigger | Mode | Opens per trigger | Notes |
|---|---|---|---|
| Scheduled scan candidate | `scan` (+ inline dispatch) | **1** | Was 4 before the inline-dispatch refactor (2 scan passes × (scan + dispatch reopen)). Dispatch follow-up now runs inside the same tavern session via `_dispatch_in_open_tavern()`. |
| Scheduled morning dispatch | `dispatch` | 1 | Daily, ~06:00 PT. |
| Hourly ally check | `ally` | 0 or 1 | Pre-checks 5/5 before opening; skips open entirely if maxed. |
| Imminent-completion guard | `claim` (retry-wrapped) | 1-3 typical, 5 cap | **Intentional multi-attempt**: claim re-checks the tavern because a quest can become claimable mid-cycle and the claim animation can race the next claim's appearance. Caller is `_run_tavern_claim_with_retries` in `scripts/icon_daemon.py`. |
| Post-treasure hook | `claim` | 1-3 | Treasure rewards often complete tavern quests; we claim immediately rather than wait for the next scan. |

`_open_tavern` itself retries up to 3 times internally if the menu fails
to load (network/animation hiccup) — that's a per-call backstop, not a
separate open from the caller's perspective.

## What changed in this refactor

The "tavern loads everything 3+ times every 30 min" complaint came from
two stacked behaviors on the scan side, **not** from claim:

1. `_run_tavern_scan_twice` ran the entire scan twice back-to-back "for
   reliability when first pass lands during UI transitions". With the
   `is_in_tavern()` verification inside `_open_tavern` (which already
   retries 3x internally), the second pass was almost always wasted work.
   It now runs **once**.
2. `_run_scan_mode` previously closed the tavern and called
   `_run_dispatch_mode` as a follow-up, which reopened it. Now it calls
   `_dispatch_in_open_tavern()` directly while still in the tavern, then
   closes once at the end.

Combined: a scheduled `tavern_scan` trigger now opens the tavern **once**
instead of four times. Claim retries are unchanged.
