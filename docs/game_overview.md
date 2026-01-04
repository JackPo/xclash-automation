# Game Overview and Why This Repo Exists

This document summarizes what the game appears to be based on the automation flows and explains why the repository contains many scripts and utilities.

## What the game is (as inferred from automation)
X-Clash is structured around two primary views and a set of time-gated systems:

### Glossary (terms used in code)
- Union: the in-game alliance system.
- Arms Race: the rotating 4-hour event schedule.
- Mystic Beast Training: Arms Race event where stamina spend yields points.
- Elite Zombie: a stamina-based rally that the bot uses for Beast Training points.
- Tavern: the quest board for time-based tasks.
- Bag: the inventory for consumables and chests.
- Dog house: a fixed town landmark used to verify camera alignment.

### Town view (base management)
- Buildings and production live in town view.
- Barracks train soldiers and produce READY and PENDING states.
- Hospital heals wounded troops in timed batches.
- Bag and inventory contain consumable items and chests.
- Tavern quests provide time-based rewards and dispatch tasks.

### World view (map and alliance activity)
- Resource bubbles appear on the map and can be harvested.
- Alliance ("Union") features include gifts, technology donations, and rally participation.
- Union War rallies are joinable via a marching panel.
- Special map navigation uses the search/mark UI (go-to-mark flow).

### Event systems
- Arms Race runs on a fixed 7-day schedule of 4-hour blocks.
- Events include Mystic Beast Training, Enhance Hero, Soldier Training, City Construction, and Technology Research.
- VS days add daily modifiers (e.g., soldier promotion days, chest opening timing).

### Stamina and rallies
- Stamina is spent on elite zombie rallies and is time-gated by cooldowns.
- A free stamina claim uses a red-dot indicator and a 4-hour timer.
- Recovery items can be used when time is short and stamina is low.

### Heroes and upgrades
- Heroes have upgrade availability indicated by red dots.
- Rallies and certain flows require idle heroes (Zz icons).

This automation focuses on repetitive, time-gated actions that are easy to miss when playing manually.

## Why there are so many scripts
The repo splits responsibilities into small, testable pieces because every UI element and flow is fragile. A small change in coordinates or templates can break one part without affecting others. The scripts exist to isolate that risk and make calibration and recovery manageable.

### Feature-to-flow mapping (examples)
- Alliance handshake popup -> `scripts/flows/handshake_flow.py`
- Treasure map popup -> `scripts/flows/treasure_map_flow.py`
- Harvest surprise boxes -> `scripts/flows/harvest_box_flow.py`
- Resource bubbles -> `scripts/flows/*_harvest_flow.py`
- Tavern quests -> `scripts/flows/tavern_quest_flow.py`
- Union gifts -> `scripts/flows/union_gifts_flow.py`
- Union technology donations -> `scripts/flows/union_technology_flow.py`
- Union War rally joining -> `scripts/flows/rally_join_flow.py`
- Elite Zombie rallies -> `scripts/flows/elite_zombie_flow.py`
- Mystic Beast event phases -> `scripts/flows/beast_training_flow.py`
- Enhance Hero event upgrades -> `scripts/flows/hero_upgrade_arms_race_flow.py`
- Soldier promotions -> `scripts/flows/soldier_upgrade_flow.py`
- Normal barracks training -> `scripts/flows/soldier_training_flow.py`
- Hospital healing -> `scripts/flows/hospital_healing_flow.py`

### Main orchestrator
- `scripts/icon_daemon.py` runs the detection loop, applies gating rules, and triggers flows.

### Flows (game actions)
- `scripts/flows/*.py` implement multi-step interactions (rallies, tavern, bag, hospital, etc.).
- Each flow assumes a known UI state and uses fixed templates/coordinates.

### Matchers and helpers
- `utils/*` contains template matchers, view detection, OCR, scheduler logic, and safety helpers.
- This is where most detection logic lives (for example, dog house alignment and red-dot detection).

### Calibration and tooling
- `calibration/*` and `scripts/calibrate_*` capture templates and model the soldier training slider.
- `OBJECT_DETECTION_GUIDE.md` explains how we derive coordinates from screenshots.

### Templates and assets
- `templates/ground_truth/*` stores 4K template images used for matching.
- Masked templates exist for icons with transparent backgrounds.

### Services
- `services/ocr_server.py` runs the local Qwen2.5-VL OCR service for stamina and event points.

### Data and state
- `data/daemon_schedule.json` persists cooldowns, rally limits, and Arms Race block state.

### One-off scripts
- `scripts/one_off/*` are experiments and extraction helpers used to create or refine templates.

## Design constraints
- All matching uses Windows screenshots; ADB screenshots do not match the templates.
- BlueStacks must run at 3840x2160; templates are calibrated to that resolution.
- Coordinate-based clicks require the town camera to be aligned.
- Idle time gating prevents automation from interrupting active play.

## Related docs
- `../README.md` for setup and usage
- `../ARCHITECTURE.md` for system layout and runtime flow
- `README.md` for the full documentation map
