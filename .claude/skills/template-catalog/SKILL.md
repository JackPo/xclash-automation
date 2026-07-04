---
name: template-catalog
description: Reference for all game UI templates. Use when asking about templates, positions, thresholds, or which template to use for a UI element. Keywords include "template", "where is", "position of", "threshold for", "what template".
allowed-tools: Read, Glob, Grep
---

# Template Catalog

Reference for all templates in `templates/ground_truth/`. All coordinates are 4K (3840x2160).

## Quick Lookup

```bash
# Find templates by keyword
ls templates/ground_truth/ | grep -i "keyword"
```

## View Detection Templates

**Fixed position: (3600, 1920) size 240x240**

| Template | Meaning | Notes |
|----------|---------|-------|
| `world_button_4k.png` | Currently in TOWN | Map icon visible |
| `town_button_4k.png` | Currently in WORLD | Castle icon visible |
| `town_button_zoomed_out_4k.png` | In WORLD (zoomed out) | Map with "Town" text |
| `world_button_shaded_4k.png` | Popup blocking | Light shading |
| `world_button_shaded_dark_4k.png` | Modal blocking | Dark shading |

---

## Icon Detection Templates (Fixed Position)

| Template | Position | Size | Threshold | Click |
|----------|----------|------|-----------|-------|
| `handshake_icon_4k.png` | (3088, 1780) | 155x127 | 0.04 | (3165, 1843) |
| `treasure_map_4k.png` | (2096, 1540) | 158x162 | 0.05 | (2175, 1621) |
| `harvest_box_4k.png` | (2100, 1540) | 154x157 | 0.1 | (2177, 1618) |
| `corn_harvest_bubble_4k.png` | (1884, 1260) | 99x74 | 0.05 | (1932, 1297) |
| `gold_coin_tight_4k.png` | (1369, 800) | 53x43 | 0.06 | (1395, 835) |
| `iron_bar_tight_4k.png` | (1617, 351) | 46x32 | 0.06 | (1639, 377) |
| `gem_tight_4k.png` | (1378, 652) | 54x51 | 0.06 | (1405, 696) |
| `stamina_number_4k.png` | (69, 203) | 96x60 | OCR | N/A |

---

## Barracks Templates

**Bubble icons (size 81x87, threshold 0.08)**

| Template | State | Notes |
|----------|-------|-------|
| `stopwatch_barrack_4k.png` | TRAINING | Timer icon |
| `white_soldier_barrack_4k.png` | PENDING | White soldier |
| `yellow_soldier_barrack_4k.png` | READY | v1 (purple hat) |
| `yellow_soldier_barrack_v2_4k.png` | READY | v2 (purple hat) |
| `yellow_soldier_barrack_v3_4k.png` | READY | v3 (red hat) |
| `yellow_soldier_barrack_v4_4k.png` | READY | v4 (orange hat) |
| `yellow_soldier_barrack_v5_4k.png` | READY | v5 (yellow hat) |

**Barracks Positions (4K)**:
```python
BARRACKS_POSITIONS = [
    (2891, 1317),  # Barrack 1
    (2768, 1237),  # Barrack 2
    (3005, 1237),  # Barrack 3
    (2883, 1157),  # Barrack 4
]
```

**Soldier Tiles (panel, Y=810-967, size 148x157)**:
- `soldier_lv3_4k.png` through `soldier_lv8_4k.png`

**Training Panel**:
| Template | Position | Size | Threshold | Click |
|----------|----------|------|-----------|-------|
| `soldier_training_header_4k.png` | (1678, 315) | 480x54 | 0.02 | N/A |
| `train_button_4k.png` | (1969, 1397) | 369x65 | 0.02 | (2153, 1462) |

---

## Hospital Templates

| Template | Position | Size | Threshold | Notes |
|----------|----------|------|-----------|-------|
| `hospital_header_4k.png` | - | - | 0.02 | Panel header |
| `hospital_plus_button_4k.png` | - | 79x77 | 0.05 | Plus button |
| `hospital_minus_button_4k.png` | - | 79x80 | 0.05 | Minus button |
| `hospital_slider_circle_4k.png` | - | - | 0.05 | Slider handle |

**Config**:
- `HOSPITAL_ICON_POSITION = (3312, 344)`
- `HOSPITAL_CLICK_POSITION = (3342, 377)`
- `HEALING_BUTTON_CLICK = (2148, 1477)`

---

## Royal City Templates

| Template | Size | Position | Click | Notes |
|----------|------|----------|-------|-------|
| `royal_city_unoccupied_tab_4k.png` | 570x55 | (1630, 330) | - | Detects unoccupied |
| `royal_city_attack_button_4k.png` | 153x177 | (1634, 1609) | (1710, 1697) | Red X icon |
| `rally_button_4k.png` + mask | 153x177 | (1839, 1658) | (1916, 1746) | Blue flag |
| `royal_city_scout_button_4k.png` | 153x177 | (2045, 1609) | (2121, 1697) | Binoculars |
| `star_single_4k.png` | - | Search | Detected | threshold 0.15 |

---

## Rally/Union Templates

| Template | Size | Threshold | Notes |
|----------|------|-----------|-------|
| `rally_search_button_4k.png` | 368x126 | 0.05 | "Search" text button |
| `elite_zombie_tab_4k.png` | 284x97 | 0.1 | Tab selection |
| `team_up_button_4k.png` | 368x134 | 0.05 | Team Up button |
| `daily_rally_limit_dialog_4k.png` | 983x527 | 0.05 | Daily limit popup |
| `cancel_button_4k.png` | - | 0.05 | Cancel in dialogs |
| `union_button_4k.png` | - | 0.05 | Click: (3165, 2033) |

---

## Tavern Templates

| Template | Position | Size | Threshold | Notes |
|----------|----------|------|-----------|-------|
| `tavern_button_4k.png` | (62, 1192) | 48x48 | 0.02 | Click: (80, 1220) |
| `tavern_my_quests_active_4k.png` | (1505, 723) | 299x65 | 0.02 | Active tab |
| `tavern_ally_quests_active_4k.png` | (2054, 723) | 299x65 | 0.02 | Active tab |
| `claim_button_4k.png` | Search | 333x88 | 0.02 | Column X: 2100-2500 |
| `assist_button_4k.png` | Search | 249x102 | 0.02 | Ally quests |
| `steal_button_4k.png` | Search | 146x169 | 0.10 | Floating hexagon on WORLD map (steal sniper mode); countdown OCR region at offset (-190, -435, 380, 120) from match center |
| `tavern_mega_mode_toggle_4k.png` | Bottom row y1700-1950 | 125x180 | 0.05 | Golden-book "Mega" toggle, visible in Normal mode; click to enter Mega mode |
| `tavern_mega_refresh_button_4k.png` | Bottom row, x>=1930 only | 265x95 | 0.02 | Text-focused crop; Mega Dispatch (x 1530-1910) differs only by label and cross-matches at ~0.047 - NEVER search left of x1930 or raise threshold |
| `tavern_mega_dispatch_button_4k.png` | (not matched) | 380x130 | - | Reference only; do NOT click. Mass-dispatches all quests |

---

## Community Daily Check-in Templates (v2 webview nav)

| Template | Position | Size | Threshold | Notes |
|----------|----------|------|-----------|-------|
| `community_icon_4k.png` (+mask) | Search | - | 0.05 | Opens community webview; matched ~(3540,290) |
| `community_hamburger_4k.png` | region (300,0,900,260) | 92x86 | 0.05 | Home-page hamburger ☰ next to X-Clash logo; presence = Home feed reached |
| `community_daily_signin_row_4k.png` | region (0,850,1000,300) | 450x84 | 0.05 | "Daily Sign-In" drawer row; click ~(295,990) |
| `daily_signin_loading_bear_4k.png` | region (750,300,450,400) | - | 0.01 | Polar-bear panel header = sign-in panel loaded |
| `daily_signin_checkin_button_4k.png` | region (700,400,2400,1400) | - | 0.01 | Blue "Check in" (scroll down to reveal) |
| `daily_signin_checked_button_4k.png` | region (700,400,2400,1400) | - | 0.01 | Grey "Checked in" (already done) |
| `daily_signin_success_close_4k.png` | region (2100,500,700,400) | 73x75 | 0.05 | Red X on "Check-in Success" popup ~(2378,648) |
| `daily_sig_icon_4k.png` | region (2850,50,300,250) | 219x155 | 0.03 | OLD top-right icon; presence triggers v2→v1 revert fallback |

Exit webview: top-right X at fixed (3755,96), tap until view=TOWN/WORLD.

---

## Bag Templates

**Tab Templates (region for active/inactive same)**:

| Tab | Region | Active | Inactive |
|-----|--------|--------|----------|
| Special | (1525, 2033, 163, 96) | `bag_special_tab_active_4k.png` | `bag_special_tab_4k.png` |
| Hero | (2158, 2015, 207, 127) | `bag_hero_tab_active_4k.png` | `bag_hero_tab_4k.png` |
| Resources | (1732, 2018, 179, 111) | `bag_resources_tab_active_4k.png` | `bag_resources_tab_4k.png` |

**Special Tab Items** (7):
- `bag_chest_special_4k.png`, `bag_golden_chest_4k.png`, `bag_green_chest_4k.png`
- `bag_purple_gold_chest_4k.png`, `bag_chest_blue_4k.png`, `bag_chest_purple_4k.png`
- `bag_chest_question_4k.png`

**Hero Tab Items**: `bag_hero_chest_4k.png`, `bag_hero_chest_purple_4k.png`

**Resources Tab**: `bag_diamond_icon_4k.png`

---

## Masked Templates

Templates with transparency need masks. Mask file: `<name>_mask_4k.png`

| Template | Mask | Method | Notes |
|----------|------|--------|-------|
| `search_button_4k.png` | Yes | TM_CCORR_NORMED | Magnifying glass |
| `title_active_icon_4k.png` | Yes | TM_CCORR_NORMED | Title scroll |
| `rally_button_4k.png` | Yes | TM_CCORR_NORMED | Hexagon button |

---

## Dialog Templates (Search-Based)

| Template | Size | Notes |
|----------|------|-------|
| `harvest_surprise_box_4k.png` | 791x253 | Moves vertically |
| `open_button_4k.png` | 242x99 | Dialog button |
| `back_button_union_4k.png` | 107x111 | Position: (1345, 2002), threshold 0.06 |
| `disconnection_dialog_4k.png` | 980x350 | Error Code:7 dialog |
| `confirm_button_4k.png` | - | Click: (1912, 1289) |

---

## Anchor Templates

| Template | Position | Size | Threshold | Purpose |
|----------|----------|------|-----------|---------|
| `dog_house_4k.png` | (1605, 882) | 172x197 | 0.1 | Town alignment |

---

## Other Templates

| Template | Notes |
|----------|-------|
| `heroes_button_4k.png` | 123x177, click: (2272, 2038) |
| `upgrade_button_available_4k.png` | Green, 407x121 |
| `upgrade_button_unavailable_4k.png` | Gray, 365x126 |
| `snowman_party_chat_4k.png` | 772x80 |
| `snowman_4k.png` | 254x212 |

---

## Threshold Guidelines

| Element Type | Threshold Range |
|-------------|-----------------|
| Static icons | 0.03-0.05 |
| Animated elements | 0.08-0.1 |
| Text elements | 0.02-0.03 |
| Buttons with states | 0.05-0.08 |
| Full dialogs | 0.05 |

Lower score = better match (TM_SQDIFF_NORMED)
