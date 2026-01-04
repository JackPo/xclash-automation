# Union War Rally Joining

This document describes how rally joining works for Union War events.

## Overview
The daemon detects the rally march button, opens the Union War panel, and joins the first eligible rally based on configured monster rules.

Key behaviors:
- Validates the Union War panel and Team Intelligence tab.
- Clicks rallies first, then OCRs the monster name/level for speed.
- Requires an idle hero (Zz icon). Union Boss mode can use any idle hero.
- Handles daily limit dialogs with optional overrides.

## Trigger conditions (daemon)
- Rally march button visible (`utils/rally_march_button_matcher.py`).
- Idle time >= `IDLE_THRESHOLD`.
- View is TOWN or WORLD.
- Cooldown >= `RALLY_MARCH_BUTTON_COOLDOWN` (faster during Union Boss mode).

## Flow sequence
1. Validate Union War panel (`utils/union_war_panel_detector.py`).
2. Find rally plus buttons via `utils/rally_plus_matcher.py` (full-frame search, filtered to rightmost column).
3. For each plus button (top to bottom):
   - Click the plus button to open Team Up.
   - OCR monster name/level from the original frame (`utils/rally_monster_validator.py`).
   - If the rally matches `RALLY_MONSTERS`, continue; otherwise click back and try next.
4. Select an idle hero:
   - Default: leftmost idle hero with Zz.
   - Union Boss mode: any idle hero with Zz.
5. Click Team Up.
6. Handle daily limit dialog if it appears.
7. Return to base view.

## Daily limit handling
If the daily rally reward dialog appears:
- Default behavior: click Cancel and skip the rally.
- Override behavior: click Confirm if `RALLY_IGNORE_DAILY_LIMIT` is true or if the current date is inside `RALLY_IGNORE_DAILY_LIMIT_EVENTS`.

## Union Boss mode
If a joined rally is detected as "Union Boss", the daemon enters a 30-minute Union Boss mode:
- Rally join cooldown drops to `UNION_BOSS_RALLY_COOLDOWN`.
- Hero selection uses any idle hero instead of leftmost.

## Configuration
Relevant settings in `config.py`:
- `RALLY_JOIN_ENABLED`
- `RALLY_MARCH_BUTTON_COOLDOWN`
- `RALLY_MONSTERS` (per-monster filters: auto_join, max_level, has_level)
- `RALLY_IGNORE_DAILY_LIMIT`
- `RALLY_IGNORE_DAILY_LIMIT_EVENTS`
- `RALLY_DATA_GATHERING_MODE`

## Data gathering mode
If `RALLY_DATA_GATHERING_MODE = True`, monster crops are saved to:
- `data_gathering/matched/`
- `data_gathering/unknown/`

## Related files
- `scripts/flows/rally_join_flow.py`
- `utils/union_war_panel_detector.py`
- `utils/rally_plus_matcher.py`
- `utils/rally_monster_validator.py`
