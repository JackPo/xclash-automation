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

## Three tiers (source of truth for terminology)

Tavern dispatch tracking uses three concentric tiers. **Use these names
exactly** in code and on the dashboard.

| Tier | Name | What it counts | Where |
|---|---|---|---|
| 1 | **dispatchable** (a.k.a. visible Gos) | Every Go button visible on the first screen, regardless of quest type. The universe of quest slots. | `find_all_go_buttons()` in `scripts/flows/tavern_quest_flow.py` using `go_button_4k.png` template + NMS in `QUEST_LIST_Y_MIN..QUEST_LIST_Y_MAX`. |
| 2 | **directly_startable** | Subset of Tier 1 that our code can click Go on right now: gold-scroll Gos + (question-mark Gos if today is not a VS skip day). | `find_gold_scroll_go_buttons()` + `find_question_mark_go_buttons()`. |
| -- | **refresh_candidates** (derived) | `dispatchable - directly_startable`. Visible Gos of unsupported types (e.g. Soldier Training, Rescue Merchant) that the player could in-game refresh to potentially roll into a supported type. | Computed at the dashboard. Not stored. |

A third "will dispatch this run" tier (Tier 3) exists conceptually -- it's
Tier 2 filtered by the time-window gate and the 30-min gap gate. It isn't
stored because it's a per-attempt decision, not a persistent count.

### Why the user-facing word is "dispatchable" for Tier 1

"Dispatchable" means "has a Go button you can dispatch from". Whether the
bot's *current code* actually starts that quest is a separate question
governed by type-specific matchers and gates. The bot may grow more
type-specific matchers over time; the universe of dispatchable slots is
what tracks the total opportunity.

### Exhaustion semantics

The `dispatch_exhausted_date` flag fires only when **Tier 1 == 0** -- a
truly empty quest panel. If the screen has 3 visible Gos of unsupported
types (refresh candidates), the flag does NOT fire and the bot keeps
checking on the next scan cycle. Otherwise we'd lose the chance to refresh
those slots into supported types.

## Auto-refresh (re-roll unsupported quests into supported types)

When `_dispatch_in_open_tavern()` sees that the first frame has
**dispatchable > 0 and directly_startable = 0**, it tries to use the
in-game Refresh button to re-roll the quest list into a state with at
least one directly-startable quest, then proceeds with the normal dispatch
loop. This handles the common case where all visible quest slots are
unsupported quest types (Soldier Training, Rescue Merchant, etc.).

### Trigger

Fires from a single condition (one rule covers both VS-skip and non-skip
days because `directly_startable` already encodes the VS-day filter):

```
first_frame_dispatchable > 0 AND first_frame_directly_startable == 0
```

On non-skip days the loop terminates when ANY supported type appears
(gold-scroll or question-mark); on skip days it only terminates on
gold-scroll, since question-marks don't count toward
`directly_startable` on those days.

### Stop conditions

The refresh loop in `_try_refresh_to_startable()` exits when ANY of:

| Reason | Trigger |
| --- | --- |
| `success` | `directly_startable > 0` after the latest refresh |
| `no_change` | Post-refresh quest list signature identical to pre-refresh (Refresh button is disabled / out of resources) |
| `button_not_visible` | After ensuring Normal mode, the Refresh button can't be found |
| `mode_switch_failed` | Couldn't transition from Mega mode to Normal mode |
| `safety_cap` | `MAX_REFRESH_ATTEMPTS_PER_RUN` (20) hit in a single dispatch run. Logged as a warning; should never fire in normal operation. |

### Signature comparison

`_capture_go_signature(frame)` returns
`(dispatchable, gold_count, question_count, sorted_go_ys)`. A successful
in-game refresh re-rolls quests in place, so the Y positions of the
visible Gos will change even if the total count happens to coincidentally
stay the same. Identical signatures across two consecutive refreshes mean
the click had no effect -- stop.

### Mode handling

Refresh button only appears in Normal mode. If we land in Mega mode (yellow
Mega Dispatch + Mega Refresh buttons visible, with a small "Normal" book
toggle on the right), `_ensure_normal_mode()` clicks the toggle to switch.
We never restore the prior mode -- the user said it doesn't matter.

### Per-day tracking

Each Refresh click increments `tavern_quests.refreshes_today` (date-stamped
counter that resets at midnight). The current dispatch run's refresh count
is also written under `tavern_quests.visible_counts.refreshes_this_attempt`
so the dashboard can distinguish "we refreshed once at 6 AM" from
"we refreshed 8 times this attempt".

### Templates

- `templates/ground_truth/tavern_refresh_button_4k.png` -- orange Refresh
  button (Normal mode only)
- `templates/ground_truth/tavern_normal_mode_toggle_4k.png` -- small
  "Normal" book toggle (visible in Mega mode only)

## Dispatch exhaustion (auto-skip when no Go buttons left)

Once a dispatch attempt today walks the entire quest list without spotting
**any** Go button candidate, dispatch is effectively done for the day -- no
more visible quests will appear unless slots free up via claims, and even
then they typically don't materialize in time to dispatch before the 6 PM
PT cutoff. To stop the daemon from re-checking pointlessly:

- `utils/scheduler.py`: `mark_tavern_dispatch_exhausted_today()` /
  `is_tavern_dispatch_exhausted_today()` set/read a date-stamped flag.
  Mirrors the `claims_date` pattern; auto-resets at midnight via date
  comparison.
- `_dispatch_gates_passed()` adds an `exhausted_today` gate. Both the
  standalone `_run_dispatch_mode` and scan's dispatch-follow-up skip
  immediately when set.
- `_dispatch_in_open_tavern()` tracks `found_any_go` during its scroll
  loop. If it exits having never seen a Go candidate, it sets the flag.

**Scope:** dispatch only. Claim still runs (we still need to grab
completions from active quests started earlier in the day). Ally still
runs (with its existing 5/5 pre-check). Scan still runs (still needed to
OCR fresh timer state into the scheduler so the claim guard fires on time)
-- only its dispatch-follow-up becomes a no-op once exhausted.

Manual reset: `scheduler.clear_tavern_dispatch_exhausted_today()`.

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
