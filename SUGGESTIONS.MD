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

6) return_to_base_view writes debug screenshots even when debug=False
- Evidence: `utils/return_to_base_view.py:328-333` always writes `return_unknown_state_*`.
- Impact: disk churn and clutter in normal runs; recovery loops can dump many images.
- Suggested fix: gate behind `debug` or a dedicated flag.

## Behavior risks / missing checks (random clicking)
- Handshake flow is a fixed-coordinate tap with no verification (`scripts/flows/handshake_flow.py`).
- Harvest box flow clicks icon + Open without verifying either (`scripts/flows/harvest_box_flow.py`).
- AFK rewards and gift box flows click Claim/Back without confirming dialogs (`scripts/flows/afk_rewards_flow.py`, `scripts/flows/gift_box_flow.py`).
- Union gifts flow is mostly blind clicking until back-button loop (`scripts/flows/union_gifts_flow.py`).
- Stamina claim/use flows open/close popups via fixed coordinates without validating popup state and duplicate logic from `utils/stamina_popup_helper.py`.
- Snowman flow still has a placeholder claim step and clicks the snowman itself (`scripts/flows/snowman_flow.py`).

## Template matching migration issues
- Active flows still use raw `cv2.matchTemplate` (no masks, inconsistent thresholds):
  - `scripts/flows/tavern_quest_flow.py` (multiple matches)
  - `scripts/flows/bag_special_flow.py`, `scripts/flows/bag_hero_flow.py`, `scripts/flows/bag_resources_flow.py`
  - `scripts/flows/bag_use_item_subflow.py`
  - `scripts/flows/rally_join_flow.py`
  - `utils/ally_quest_scanner.py`
  - `utils/replenish_all_helper.py`
  - `utils/hospital_panel_helper.py`, `scripts/flows/hospital_healing_flow.py`
  - `utils/safe_ground_matcher.py`, `utils/training_slider_helper.py`, `utils/return_to_base_view.py`
  - `utils/rally_plus_matcher.py`
- `utils/template_matcher.py` docs are inconsistent with code: docs imply masked thresholds of 0.95 and show masked example using `threshold=0.05`, but code uses `DEFAULT_CCORR_THRESHOLD = 0.90`. Update docs/examples to reflect mask semantics.
- `utils/bubble_matcher.py` docs/threshold defaults assume SQDIFF; masked templates (corn/gold/iron/gem) use CCORR and rely on `config.THRESHOLDS` to be correct.
- Speedup flows use both `speedup_button_4k.png` and `speed_up_button_4k.png`; verify they are the intended templates and consolidate if they refer to the same UI.

## Inconsistencies / drift
- `world_present`/`town_present` naming inverted by design in `scripts/icon_daemon.py` (easy to misread).
- Some flow comments still reference old idle thresholds while scheduler uses `IDLE_THRESHOLD`.
- Back button templates include a dark variant (`back_button_union_dark_4k.png`) that is unused; decide whether to add to matchers or remove.

## Debug outputs / artifacts
- Debug images still write to repo root or `screenshots/debug` without cleanup:
  - `utils/training_slider_helper.py`
  - `utils/windows_screenshot_helper.py`
  - `utils/view_state_detector.py`
  - `utils/return_to_base_view.py`

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
