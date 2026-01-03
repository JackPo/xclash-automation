# SUGGESTIONS (Deep Dive Findings)

Scope: full re-scan across flows, daemon, helpers, and template-matching migration.

## Fixes Applied (2025-01-02)

### 1. match_template signature misuse - FIXED
Fixed calls passing `pos, size` as separate positional args instead of `search_region=(*pos, *size)`:
- `scripts/flows/marshall_speedup_all_flow.py:48-54` - Fixed
- `scripts/flows/barrack_speedup_flow.py:62` - Fixed
- `scripts/flows/soldier_speedup_flow.py:79-92` - Fixed
- `scripts/flows/title_management_flow.py` - Already correct (no fix needed)

### 2. BackButtonMatcher CCORR/SQDIFF confusion - FIXED
Rewrote `utils/back_button_matcher.py` to:
- Import `has_mask` from template_matcher
- Normalize scores to common 0-1 range (higher=better)
- Use `has_mask()` to determine normalization (CCORR stays as-is, SQDIFF becomes `1-score`)
- Compare `normalized > best_normalized` for correct ordering
- Removed hardcoded threshold - uses template_matcher defaults (SQDIFF: 0.1, CCORR: 0.90)

### 3. Wrong thresholds for template methods - FIXED
- `scripts/flows/royal_city_flow.py:86` - Changed threshold 0.9 to 0.1 (SQDIFF - no mask)
- `scripts/flows/union_gifts_flow.py:62` - Changed BACK_BUTTON_THRESHOLD from 0.06 to 0.95 (CCORR - has mask)

### 4. Duplicate `_can_run_flow` definition - FIXED
Deleted the second definition at `scripts/icon_daemon.py:970-973` that ignored `critical_flow_active`.
The first definition at lines 563-578 (which properly checks both `active_flows` AND `critical_flow_active`) is now the only one.

### 5. return_to_base_view unconditional debug screenshots - FIXED
Wrapped `utils/return_to_base_view.py:328-333` with `if debug:` so screenshots only write when debug mode is on.

### 6. `stamina_confirmed` referenced before assignment - FIXED
Added initialization `stamina_confirmed = False` and `confirmed_stamina = None` at the start of each daemon loop iteration.

### 7. Pre-beast stamina claim cooldown bypass - FIXED
- Changed FlowCandidate name from `"stamina_claim"` to `"pre_beast_stamina_claim"` to match scheduler config
- Added `record_to_scheduler=True` to record the cooldown
- Set `self.beast_training_pre_claim_block = upcoming_beast_block` before queueing to prevent re-queue

### 8. UNKNOWN state recovery was blocked by high idle threshold - FIXED
- Recovery was gated behind `effective_idle_secs >= IDLE_THRESHOLD` (5 min default)
- Now uses `self.IDLE_THRESHOLD` from config (respects config_local setting)
- Added **shaded button detection** as first recovery check (popup blocking view)
- Recovery tries EVERY iteration: shaded button → back button → safe ground
- Falls back to full `return_to_base_view` only after 180s stuck

### 9. bag_flow cooldown not applied - FIXED
- FlowCandidate used `name="bag"` but scheduler config uses `"bag_flow"`
- Cooldown checks against `"bag_flow"` never found matching entries
- Changed `name="bag"` to `name="bag_flow"` in 3 places

### 10. FlowCandidate wrappers have wrong signature - FIXED
- `beast_rally_wrapper()` defined with no args, but `_run_flow` calls `flow_func(self.adb)`
- Same for `marshall_speedup_all_flow` lambdas at lines 2174/2187
- Fixed by adding `adb` parameter: `def beast_rally_wrapper(adb):` and `lambda adb:`

### 11. return_to_base_view RESTART_TRIGGER screenshot unconditional - FIXED
- `utils/return_to_base_view.py:481-482` wrote screenshot regardless of `debug` flag
- Wrapped the entire restart screenshot block in `if debug:`

### 12. Dead state variable beast_training_pre_claim_done - FIXED
- Removed unused `self.beast_training_pre_claim_done` from `scripts/icon_daemon.py:353`

### 13. UNKNOWN full recovery ran when user was NOT idle - FIXED
- Full recovery (`return_to_base_view` after 180s in UNKNOWN) triggered regardless of idle status
- Added idle check: `if unknown_duration >= self.UNKNOWN_STATE_TIMEOUT and effective_idle_secs >= self.IDLE_THRESHOLD:`
- Won't interrupt active gameplay anymore

### 14. Disk cleanup was O(n²) and froze daemon - FIXED
- `utils/debug_screenshot.py:_cleanup_old` called `_get_disk_usage_gb()` after EVERY file deletion
- 10,000 files = 100 million stat() calls, took minutes
- Refactored to single scan with byte tracking - now O(n), takes seconds

## Verified fixes / confirmed OK (observed in current code)
- VS Day 7 chest checkpoints use `arms_race_remaining_mins` instead of a missing field in `scripts/icon_daemon.py`.
- Rally monster offsets treat plus button coordinates as centers (`utils/rally_monster_validator.py`, `config.py`).
- Enhance Hero flow uses existing `adb` instance (no hard-coded ADB path/device) in `scripts/flows/hero_upgrade_arms_race_flow.py`.
- Union Technology badge selection picks top-most/lowest Y in `scripts/flows/union_technology_flow.py`.
- Idle tracking integrated via `ADBHelper(on_action=mark_daemon_action)` in `scripts/icon_daemon.py`.
- WebSocket status reports filtered idle in `scripts/icon_daemon.py`.
- Rally join gating uses filtered idle in `scripts/icon_daemon.py`.
- Rally plus X centralized via config and used in matcher (`config.py`, `utils/rally_plus_matcher.py`).
- Resource bubble flows now verify presence before clicking (`scripts/flows/corn_harvest_flow.py`, `scripts/flows/gold_coin_flow.py`, `scripts/flows/iron_bar_flow.py`, `scripts/flows/gem_flow.py`, `scripts/flows/cabbage_flow.py`, `scripts/flows/equipment_enhancement_flow.py`).
- Stamina claim/use flows derive positions and search regions from config (`scripts/flows/stamina_claim_flow.py`, `scripts/flows/stamina_use_flow.py`).
- Union Technology long-press comment matches 3s duration in `scripts/flows/union_technology_flow.py`.
- Rally join debug output uses `utils/debug_screenshot` (no repo-root writes) in `scripts/flows/rally_join_flow.py`.
- `TEMPLATE_DIR` path fixes for `scripts/flows/soldier_training_flow.py` and `scripts/flows/tavern_quest_flow.py`.
- Safe-ground matcher template path uses `Path(__file__)` in `utils/safe_ground_matcher.py`.
- Masked search button threshold now respects `has_mask()` in `scripts/flows/go_to_mark_flow.py`.
- BackButtonMatcher location math uses center coords (no +50 offset bug).

## High-risk issues (likely broken or crashing)

1) ~~`match_template` called with wrong signature~~ **FIXED** - See "Fixes Applied" above

2) ~~BackButtonMatcher mixes CCORR/SQDIFF scoring~~ **FIXED** - See "Fixes Applied" above

3) ~~Union gifts back-button uses wrong threshold~~ **FIXED** - See "Fixes Applied" above

4) ~~Royal City "unoccupied" uses wrong threshold~~ **FIXED** - See "Fixes Applied" above
   - Note: `rally_button_4k.png` HAS a mask, so threshold 0.90 is actually correct for that one

5) WebSocket API exposes flows without preconditions
- Evidence: `scripts/icon_daemon.py:981-1011` lists flows with no view/panel gating.
- Impact: API calls can trigger flows in the wrong view, leading to random taps or stuck states.
- Suggested fix: add flow metadata (required view/panel/idle) and enforce in `trigger_flow`.

6) ~~return_to_base_view writes debug screenshots even when debug=False~~ **FIXED** - See "Fixes Applied" above

7) ~~`stamina_confirmed` referenced before assignment during Beast Training priority check~~ **FIXED** - See "Fixes Applied" above

8) ~~Pre-beast stamina claim never records cooldown and block isn't updated~~ **FIXED** - See "Fixes Applied" above

9) ~~FlowCandidate wrappers have wrong signature and crash on execution~~ **FIXED** - See "Fixes Applied" above

10) Recovery/setup uses `python` binary that may not exist
- `utils/return_to_base_view.py:121-131` and `scripts/icon_daemon.py:756-770` call `['python', 'scripts/setup_bluestacks.py']`.
- On systems where only `python3` is available (common), recovery/resolution fix silently fails.
- **N/A for this setup** - Windows has `python` in PATH.

11) Foreground detection relies on `grep` inside `adb shell`
- `scripts/icon_daemon.py:_is_xclash_in_foreground` and `utils/return_to_base_view._is_xclash_in_foreground` run `dumpsys window | grep mFocusedApp`.
- Some Android shells lack `grep`.
- **N/A for this setup** - BlueStacks has grep, verified working.

12) OCR server restart logic is Windows‑only and can leave orphans
- `utils/ocr_client.kill_ocr_servers()` uses `wmic` (removed on newer Windows, unavailable in WSL/Linux).
- If kill fails, a stale server can keep port 5123 busy; new starts fail silently.

13) OCR auto‑start only tries once per process
- `OCRClient._auto_start_attempted` prevents any retry after the first failure.
- A transient failure (GPU busy, slow load) can permanently disable OCR until daemon restart.

14) OCR call sites lack error handling
- Several helpers call `OCRClient.extract_text/number` without try/except; if OCR dies mid‑flow, the flow crashes and leaves UI in an unknown state.
- Examples: `utils/stamina_popup_helper.py`, `utils/hospital_panel_helper.py`, `utils/arms_race_ocr.py`.

## Candidate flow system review (flow stepping/overlap)

What works:
- When UI actions are represented as `FlowCandidate` entries and executed via `_execute_best_flow()`, only one flow thread starts, and `active_flows` prevents concurrent flow threads.

Key issues / bypasses:
- Direct synchronous UI actions bypass the candidate system and can run while another flow is active, or before `_execute_best_flow()` runs:
  - `collect_and_save_current_event` in `scripts/icon_daemon.py:1407-1415` (Arms Race data collection).
  - `run_hour_mark_phase` and `run_last_6_minutes_phase` in `scripts/icon_daemon.py:1889-1937` (Beast Training phases).
  - `check_arms_race_progress` in `scripts/icon_daemon.py:2087-2094`.
- Rally join runs inline (tap + `_run_flow_sync`) before candidate execution in `scripts/icon_daemon.py:1248-1293`.
- Soldier upgrade loop taps READY barracks directly (no `active_flows` guard) and runs `_run_flow_sync` per barrack before candidate execution in `scripts/icon_daemon.py:2221-2270`.
- Foreground recovery runs before the “critical flow active” guard; `return_to_base_view` can fire even while a critical flow is running if the app loses focus. Evidence: `scripts/icon_daemon.py:1181-1188` (foreground check) vs `scripts/icon_daemon.py:1192-1197` (critical flow guard).
- `record_to_scheduler=True` writes cooldowns immediately after `_run_flow` starts (before success), so failures still consume cooldown and prevent retries. Evidence: `_execute_best_flow` in `scripts/icon_daemon.py:603-622`.
- Impact: multiple flows can run in the same iteration, and candidates are based on a stale pre-flow screenshot; UI changes from direct flows can invalidate candidates and cause misclicks.

Structural risk:
- ~~`_can_run_flow` is defined twice~~ **FIXED** - Deleted the second definition at lines 970-973 that ignored `critical_flow_active`. See "Fixes Applied" above.

Suggested fix:
- Move all UI-affecting actions into FlowCandidates (or mark the iteration as “flow already executed” and skip `_execute_best_flow()`), and gate all direct taps with `_can_run_flow`/`active_flows`.

## Policy: Always record + Always escape (requested)
- Record EVERY flow attempt regardless of success (add `last_attempt`, `attempt_count`, `last_error`), and only apply cooldowns on `last_success`. This avoids “silent no‑ops” while keeping cooldown logic honest.
- Standardize flow results (e.g., `FlowResult {success, reason, details}`) so `_run_flow` can record outcomes uniformly.
- Add a guaranteed escape path for all flows: on exceptions or invalid states, run a bounded `escape_to_base()` (non‑recursive, with a hard cap and restart fallback). Ensure this path runs in a `finally` or in `_run_flow`’s error handler.

## Recovery flow issues (return_to_base_view)
- Recursion is unbounded (`return_to_base_view` calls itself on failure). Persistent failures can hit recursion limits instead of looping safely.
- Shaded-button detection only runs once at entry (Step 1b). If a popup appears later, `detect_view` stays UNKNOWN and the loop never calls `dismiss_popups` again.
- Fixed “blind” clicks (`CENTER_SCREEN_CLICK`, `MAP_DESELECT_CLICK`) are used in UNKNOWN state without verifying UI; can accidentally confirm dialogs or purchase prompts.
- `_detect_resource_bar` / `_detect_troop_selected` use raw SQDIFF on fixed ROIs; false positives can trigger the wrong recovery branch and random taps.

## Behavior risks / missing checks (random clicking)
- Handshake flow is a fixed-coordinate tap with no verification (`scripts/flows/handshake_flow.py`).
- Harvest box flow clicks icon + Open without verifying either (`scripts/flows/harvest_box_flow.py`).
- AFK rewards and gift box flows click Claim/Back without confirming dialogs (`scripts/flows/afk_rewards_flow.py`, `scripts/flows/gift_box_flow.py`).
- Union gifts flow is mostly blind clicking until back-button loop (`scripts/flows/union_gifts_flow.py`).
- Stamina claim/use flows open/close popups via fixed coordinates without validating popup state and duplicate logic from `utils/stamina_popup_helper.py`.
- Snowman flow still has a placeholder claim step and clicks the snowman itself (`scripts/flows/snowman_flow.py`).
- `BackButtonMatcher.click()` ignores the detected location and taps a fixed coordinate; flows that detect then call `click()` can misclick if the back button position shifts or a union variant is shown. Evidence: `utils/back_button_matcher.py:79-80`, `scripts/flows/treasure_map_flow.py:395-414`, `scripts/flows/rally_join_flow.py:361/444/447/526`.

## Template matching migration issues
- Active flows still use raw `cv2.matchTemplate` (no masks, inconsistent thresholds):
  - `scripts/flows/tavern_quest_flow.py` (multiple matches)
  - `scripts/flows/bag_special_flow.py`, `scripts/flows/bag_hero_flow.py`, `scripts/flows/bag_resources_flow.py`
  - `scripts/flows/bag_use_item_subflow.py`
  - `scripts/flows/stamina_use_flow.py`
  - `scripts/flows/soldier_training_flow.py`
  - `scripts/flows/back_from_chat_flow.py` (TM_CCOEFF_NORMED, different score semantics)
  - `scripts/flows/harvest_box_flow.py` (TM_CCOEFF_NORMED)
  - `scripts/flows/faction_trials_flow.py` (manual, still raw matching)
  - `scripts/flows/rally_join_flow.py`
  - `utils/ally_quest_scanner.py`
  - `utils/replenish_all_helper.py`
  - `utils/hospital_panel_helper.py`, `scripts/flows/hospital_healing_flow.py`
  - `utils/safe_ground_matcher.py`, `utils/training_slider_helper.py`, `utils/return_to_base_view.py`
  - `utils/rally_plus_matcher.py`
  - `utils/arms_race_panel_helper.py`, `utils/arms_race_ocr.py`
  - `utils/soldier_panel_slider.py`
  - `utils/shaded_button_helper.py`
- `utils/template_matcher.py` docs are inconsistent with code: docs imply masked thresholds of 0.95 and show masked example using `threshold=0.05`, but code uses `DEFAULT_CCORR_THRESHOLD = 0.90`. Update docs/examples to reflect mask semantics.
- `utils/bubble_matcher.py` docs/threshold defaults assume SQDIFF; masked templates (corn/gold/iron/gem) use CCORR and rely on `config.THRESHOLDS` to be correct.
- Speedup flows use both `speedup_button_4k.png` and `speed_up_button_4k.png`; verify they are the intended templates and consolidate if they refer to the same UI.

## Inconsistencies / drift
- `world_present`/`town_present` naming inverted by design in `scripts/icon_daemon.py` (easy to misread).
- Some flow comments still reference old idle thresholds while scheduler uses `IDLE_THRESHOLD`.
- Runtime `IDLE_THRESHOLD` updates (via API) don’t propagate to all checks: rally join uses module `IDLE_THRESHOLD` constant, and scheduler flow configs are initialized from config at startup only. Evidence: `scripts/icon_daemon.py:1265`, `utils/scheduler.py:19-30`.
- `_verify_templates()` doesn’t include templates used by critical matchers (e.g., `back_button_union_4k.png` and its mask, shaded button templates). Missing files won’t be caught at startup.
- VS Day 7 bag-flow surprise does **not** record scheduler cooldown, so a normal bag-flow can fire immediately after the surprise run. Evidence: `scripts/icon_daemon.py:2356-2377`.
- `ADBHelper.ADB_PATH` is hard‑coded to `C:\\Program Files\\BlueStacks_nxt\\hd-adb.exe` with no config override. Any non‑default install path breaks all ADB actions. Evidence: `utils/adb_helper.py:37`.
- `WindowsScreenshotHelper` hard-codes the window title ("BlueStacks App Player") and target window size; if the title changes or the window is resized/fullscreen, it raises and most flows don’t catch it, killing the daemon thread. Evidence: `utils/windows_screenshot_helper.py:32-96`.
- Back button templates include a dark variant (`back_button_union_dark_4k.png`) that is unused; decide whether to add to matchers or remove.
- View detection doesn’t consider shaded world/town button variants (`world_button_shaded_4k.png`, `world_button_shaded_dark_4k.png`), so modal popups can force `UNKNOWN` state and unnecessary recovery. Evidence: `utils/view_state_detector.py:33-53` vs `utils/shaded_button_helper.py:10-23`.
- ~~`beast_training_pre_claim_done` is defined but never used (dead state).~~ **FIXED** - Removed dead variable.

## Additional mess / cleanup candidates
- Flow return types are inconsistent (some return `bool`, others return `dict`, others return `None`), making centralized success tracking/error handling fragile.
- Multiple back‑button paths compete (`BackButtonMatcher`, `back_from_chat_flow`, `click_back`, hard‑coded `BACK_BUTTON_CLICK`), often without sharing the detected location. Consolidate to one back‑button API.
- Recovery logic is duplicated across `return_to_base_view`, `view_state_detector.navigate_to`, and daemon UNKNOWN recovery. These heuristics drift and conflict; consolidate into a single recovery state machine.
- Global config mutation is used for flow behavior (e.g., `ELITE_ZOMBIE_PLUS_CLICKS` toggled in Beast Training). This is not thread‑safe and can leak into other flows if a critical flow overlaps or crashes. Prefer passing parameters instead of mutating `config`.

## Debug outputs / artifacts
- Debug images still write to repo root or `screenshots/debug` without cleanup:
  - `utils/training_slider_helper.py`
  - `utils/windows_screenshot_helper.py`
  - `utils/view_state_detector.py`
- ~~`return_to_base_view` still writes a restart screenshot even when `debug=False` (RESTART_TRIGGER_*).~~ **FIXED** - See fix #11.

## Refactor opportunities
1) Centralize UI constants (template names, regions, click points).
2) Introduce a `FlowContext` (adb, win, logger, scheduler) so flows don’t instantiate helpers.
3) Add a `match_template_at(pos, size)` helper to avoid signature misuse.
4) Consolidate stamina popup logic into `utils/stamina_popup_helper.py` and make flows thin wrappers.
5) Consolidate bubble matchers and make a generic resource bubble flow around `utils/bubble_matcher.py`.
6) Unify speedup flows into a shared helper to reduce drift and duplicated constants.
7) Formalize a flow registry with preconditions (view/panel/idle) for WebSocket safety.
8) Finish the template-matching migration: prefer `utils.template_matcher` in active flows, standardize mask-aware thresholds.

## Testing gaps
- `test/` and `tests/` contain no runnable tests (only screenshot artifacts).
- No smoke tests for template presence, mask pairing, or flow preconditions.

## Open questions
- Should WebSocket-triggered flows refuse to run if preconditions are unmet, or auto-navigate to the right view/panel?
- Should debug screenshots be gated behind a flag, or always captured for postmortems?
- Should BubbleMatcher become the only resource-bubble detector with legacy matchers removed?
- Do you want masks added for templates like `royal_city_unoccupied_tab_4k.png` and `rally_button_4k.png` to enable CCORR thresholds?
- Should raw `cv2.matchTemplate` use remain in some flows (tavern quests, bag flows), or should we migrate everything to `template_matcher`?
