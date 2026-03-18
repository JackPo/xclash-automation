# xclash-automation

Automation daemon for X-Clash (com.xman.na.gp) running on BlueStacks. Uses Windows screenshots, OpenCV template matching, OCR, and ADB input to drive in-game flows.

## What it automates
- Passive popups: handshake, treasure maps, harvest boxes, AFK rewards
- Resource harvest bubbles (requires calibrated coordinates and aligned town view)
- Tavern quests (claim, start gold scrolls, schedule-aware claiming, ally quest assists for gold 4+ star quests)
- Union gifts, Union Technology donations, Union Coal collection, Union Furnace donations
- Bag items and gift box rewards
- Union War rally joining (monster filters + daily limit handling)
- Hospital healing (batch healing)
- Arms Race events: Mystic Beast, Enhance Hero, Soldier Training
- Event-specific stamina management during Mystic Beast

Notes:
- Some flows are manual or on-demand (for example, faction trials, title management).
- Planned and missing features are tracked in `docs/future_steps.md`.

## How it works (short version)
- `WindowsScreenshotHelper` captures frames for matching (ADB screenshots are not used).
- Matchers detect UI elements; the daemon triggers flows when conditions are met.
- OCR runs via a local Qwen2.5-VL server for stamina and event points.
- A JSON scheduler persists cooldowns and daily limits across restarts.
- State file (`data/daemon_current_state.json`) tracks stamina, tavern quest counters (assist allies, plunder others), daily check-ins, and Arms Race progress.
- Web dashboard shows live status and allows flow control via WebSocket.

## Quick start
1. Install Python 3.12+, BlueStacks 5, and optional CUDA (for OCR).
2. Install CUDA-enabled PyTorch (recommended for RTX 50 series):
   ```bash
   pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu128
   ```
3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```
4. Set BlueStacks to 3840x2160:
   ```bash
   python scripts/setup_bluestacks.py
   ```
5. Copy config overrides:
   ```bash
   cp config_local.py.example config_local.py
   ```
6. Run the daemon:
   ```bash
   python scripts/icon_daemon.py
   ```

## Configuration
- Defaults live in `config.py`; overrides go in `config_local.py`.
- Calibrate town layout coordinates for harvest flows using `OBJECT_DETECTION_GUIDE.md`.

## Tavern Quest Logic (Documented)
- Modes in `scripts/flows/tavern_quest_flow.py`:
  - `claim`: claim ready tavern quests.
  - `scan`: OCR quest timers, persist completion schedule, then run a dispatch follow-up attempt.
  - `dispatch`: start new quests via `Go` + bounty dialog handling.
  - `ally`: assist ally quests (gold 4+ star logic).
- Dispatch time window (Pacific):
  - Start time: `TAVERN_QUEST_START_HOUR` / `TAVERN_QUEST_START_MINUTE` (currently 6:00 AM PT).
  - End/block point: `TAVERN_SERVER_RESET_HOUR` (currently 6:00 PM PT).
  - Dispatch attempts outside the allowed window return `skipped: "before_start_time"`.
- Dispatch cooldown:
  - `TAVERN_MIN_DISPATCH_GAP_MINUTES` is enforced between successful dispatches (currently 30 min).
  - Timestamp is persisted as `tavern_quests.last_dispatch` in scheduler state (`data/daemon_schedule.json` via scheduler API).
  - If called too soon, dispatch returns `skipped: "too_soon"`.
- VS day gating for question-mark quests:
  - `VS_QUESTION_MARK_SKIP_DAYS = [3, 6]` means question-mark dispatch is disabled on those days.
  - On skip days, dispatch effectively runs gold-scroll quests only.
  - If VS-day lookup fails, logic fails open and allows question-mark dispatch.
- Dispatch target detection details:
  - Go taps use fixed X (`GO_BUTTON_CLICK_X`) and reward-row Y derived from template matches.
  - Reward matching is limited to quest-list Y range (`QUEST_LIST_Y_MIN..QUEST_LIST_Y_MAX`) to avoid top-header false positives.
- Post-dispatch view behavior:
  - The game may leave tavern view after a successful dispatch due to a transition/popup.
  - A `Lost tavern view` warning after `dispatches: 1` can be expected in this case, not necessarily a failed dispatch.
- Debug artifacts:
  - Dispatch mode can save step screenshots under `screenshots/debug/` (enabled by `debug=True`) for verification of matching and taps.
- Claim timing and guard semantics:
  - See `docs/tavern_quests.md` for exact trigger windows (`imminent`), overdue guard behavior, and why a claim can still be missed in edge timing cases.

## Operational Safeguards (Recent)
- Mystic Beast stamina claim hardening:
  - `stamina_use_flow` now cross-checks free-50 availability with claim-button template matching, not timer OCR alone.
  - If OCR says free-50 is ready but claim button is not visible, it is treated as not claimable.
  - Free-50 stamina is only counted after post-tap confirmation (claim consumed and/or stamina increased).
- Mystic Beast retry-loop guard:
  - If aggressive Beast Training fails with `Out of stamina`, daemon marks the current Beast checkpoint block as handled to prevent per-loop retry storms.
- Rally monster cap update:
  - Default monster config now allows `Elite Zombie` up to level `60`.

## Docs
See `docs/README.md` for the full documentation map and deep dives. For a game primer, start with `docs/game_overview.md`.

## Change Log Since Last Commit
<!-- CHANGELOG-SINCE-LAST-COMMIT:START -->
Base commit: `a88e371` 

Generated: 2026-03-02 05:16:02 -08:00

This list includes all version-controlled file changes currently present since the base commit.

```text
M	.claude/skills/daemon-flow/FLOWS.md
M	README.md
M	SUGGESTIONS.MD
M	config.py
M	config_local.py.example
M	dashboard/server.py
M	dashboard/static/index.html
M	data/kingdom_titles.json
M	requirements.txt
M	scripts/daemon_cli.py
M	scripts/demo_4_hours.py
M	scripts/flows/__init__.py
M	scripts/flows/afk_rewards_flow.py
M	scripts/flows/bag_hero_flow.py
M	scripts/flows/bag_resources_flow.py
M	scripts/flows/bag_special_flow.py
M	scripts/flows/barrack_speedup_flow.py
M	scripts/flows/barracks_training_flow.py
M	scripts/flows/beast_training_flow.py
M	scripts/flows/cabbage_flow.py
M	scripts/flows/elite_zombie_flow.py
M	scripts/flows/faction_trials_flow.py
M	scripts/flows/gift_box_flow.py
M	scripts/flows/gold_coin_flow.py
M	scripts/flows/handshake_flow.py
M	scripts/flows/harvest_box_flow.py
M	scripts/flows/hero_upgrade_arms_race_flow.py
M	scripts/flows/hospital_healing_flow.py
M	scripts/flows/marshall_speedup_all_flow.py
M	scripts/flows/rally_join_flow.py
M	scripts/flows/reinforce_camp_star_flow.py
M	scripts/flows/royal_city_attack_flow.py
M	scripts/flows/royal_city_flow.py
M	scripts/flows/snowman_flow.py
M	scripts/flows/soldier_speedup_flow.py
M	scripts/flows/soldier_training_flow.py
M	scripts/flows/soldier_upgrade_flow.py
M	scripts/flows/stamina_claim_flow.py
M	scripts/flows/tavern_quest_flow.py
M	scripts/flows/treasure_map_flow.py
M	scripts/flows/union_gifts_flow.py
M	scripts/flows/union_technology_flow.py
M	scripts/icon_daemon.py
M	scripts/one_off/test_stamina_rule_engine.py
M	services/ocr_server.py
D	templates/ground_truth/bag_button_4k.png.template.png
D	templates/ground_truth/bag_shield_5_4k.png
D	templates/ground_truth/bag_shield_blue_5_4k.png
D	templates/ground_truth/bag_shield_green_4_4k.png
D	templates/ground_truth/bag_shield_purple_4_4k.png
D	templates/ground_truth/treasure_chat_notification_4k.png
D	templates/ground_truth/treasure_digging_marker_4k.png
D	templates/ground_truth/treasure_map_4k.png
D	templates/ground_truth/treasure_not_ready_circle_4k.png
D	templates/ground_truth/treasure_not_ready_circle_mask_4k.png
D	templates/ground_truth/treasure_ready_circle_4k.png
D	templates/ground_truth/treasure_ready_circle_mask_4k.png
M	templates/ground_truth/use_button_4k.png
M	tests/test_templates.py
M	tests/unit/test_template_matcher.py
M	utils/adb_helper.py
M	utils/afk_rewards_matcher.py
M	utils/ally_quest_scanner.py
M	utils/arms_race_data_collector.py
M	utils/barracks_state_matcher.py
M	utils/bubble_matcher.py
M	utils/cabbage_matcher.py
M	utils/config_overrides.py
M	utils/corn_harvest_matcher.py
M	utils/daemon_server.py
M	utils/equipment_enhancement_matcher.py
M	utils/events_icon_matcher.py
M	utils/gem_matcher.py
M	utils/gold_coin_matcher.py
M	utils/handshake_icon_matcher.py
M	utils/harvest_box_matcher.py
M	utils/iron_bar_matcher.py
M	utils/ocr_client.py
D	utils/qwen_ocr.py
M	utils/rally_march_button_matcher.py
M	utils/replenish_all_helper.py
M	utils/return_to_base_view.py
M	utils/scheduler.py
M	utils/shaded_button_helper.py
M	utils/snowman_chat_matcher.py
M	utils/snowman_matcher.py
M	utils/soldier_tile_matcher.py
M	utils/stamina_popup_helper.py
M	utils/template_matcher.py
M	utils/ui_helpers.py
M	utils/user_idle_tracker.py
```
<!-- CHANGELOG-SINCE-LAST-COMMIT:END -->

