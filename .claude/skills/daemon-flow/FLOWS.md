# Daemon Flow Documentation

Detailed documentation for all automated flows in the icon daemon.

## Currently Detected Icons

| Icon | Matcher | Threshold | Click | Flow |
|------|---------|-----------|-------|------|
| Handshake | `handshake_icon_matcher.py` | 0.04 | (3165, 1843) | `handshake_flow` |
| Treasure Map | `treasure_map_matcher.py` | 0.05 | (2175, 1621) | `treasure_map_flow` |
| Harvest Box | `harvest_box_matcher.py` | 0.1 | (2177, 1618) | `harvest_box_flow` |
| Corn | `corn_harvest_matcher.py` | 0.05 | (1932, 1297) | `corn_harvest_flow` |
| Gold | `gold_coin_matcher.py` | 0.06 | (1395, 835) | `gold_coin_flow` |
| Iron | `iron_bar_matcher.py` | 0.08 | (1639, 377) | `iron_bar_flow` |
| Gem | `gem_matcher.py` | 0.06 | (1405, 696) | `gem_flow` |
| Healing | `healing_bubble_matcher.py` | 0.06 | (3340, 364) | `healing_flow` |
| Elite Zombie | Stamina OCR | stamina >= 118 | N/A | `elite_zombie_flow` |
| Hero Upgrade | Enhance Hero event | last N min + idle | (2272, 2038) | `hero_upgrade_arms_race_flow` |
| Bag | Idle trigger | 5 min idle + 1 hr cooldown | (3725, 1624) | `bag_flow` |
| Royal City | Scheduled | User-specified time | N/A | `royal_city_flow` |
| Reinforce Camp | Manual/Loop | Star icon click | N/A | `reinforce_camp_star` |

---

## Harvest Action Requirements

Harvest actions (corn, gold, iron, gem, cabbage, equipment) require ALL of:
1. **TOWN view** - must see World button
2. **5+ minutes idle** - won't trigger while user active
3. **Dog house aligned** - town view not panned

**Immediate actions** (no idle/alignment check):
- Handshake flow
- Treasure map (digging) flow
- Harvest box flow

---

## Elite Zombie Rally (Stamina-based)

**Trigger**: stamina >= 118 AND user idle 5+ min

**Sequence**:
1. Navigate to WORLD view
2. Click magnifying glass → **POLL** for `rally_search_button_4k.png`
3. Click Elite Zombie tab → **VERIFY** `elite_zombie_tab_4k.png`
4. Set level via OCR (`target_level`) OR click plus/minus N times (`level_clicks`)
5. **VERIFY** `rally_search_button_4k.png`, click detected location
6. Check for **frozen zombie** (see below)
7. **POLL** for `rally_button_4k.png` → click detected location
8. **POLL** for `team_up_button_4k.png`
9. Select LEFTMOST idle hero (with Zz icon)
10. **VERIFY** and click `team_up_button_4k.png`

**Templates**:
- `rally_search_button_4k.png` (368x126, threshold 0.05)
- `elite_zombie_tab_4k.png` (284x97, threshold 0.1)
- `rally_button_4k.png` (153x177, threshold 0.08)
- `team_up_button_4k.png` (368x134, threshold 0.05)
- `unfreeze_button_4k.png` + mask (153x162, threshold 0.05) - Season 1

**Hero Selection**:
- Elite Zombie: LEFTMOST idle hero
- Treasure Map: RIGHTMOST idle hero

**Level Control** (two methods):

1. **OCR-based targeting** (`target_level`) - RECOMMENDED:
   - Reads current level via OCR from "Level XX" text
   - Taps slider at calculated X position
   - Fine-tunes with plus/minus if needed (max 10 clicks)
   - Verifies final level matches target

2. **Relative clicks** (`level_clicks`):
   - Clicks plus/minus button N times from current position
   - No verification of actual level reached

**API**:
```python
# OCR-based targeting (recommended)
elite_zombie_flow(adb, target_level=30)  # Set to exactly level 30

# Relative clicks (legacy)
elite_zombie_flow(adb, level_clicks=0)   # No level change
elite_zombie_flow(adb, level_clicks=5)   # 5 plus clicks
elite_zombie_flow(adb, level_clicks=-3)  # 3 minus clicks
elite_zombie_flow(adb)                   # Uses ELITE_ZOMBIE_LEVEL_CLICKS config
```

**CLI**:
```bash
python scripts/flows/elite_zombie_flow.py --target-level 30
python scripts/flows/elite_zombie_flow.py --level-clicks -5
```

**WebSocket API**:
```json
{"cmd": "run_elite_zombie", "args": {"target_level": 30}}
{"cmd": "run_elite_zombie", "args": {"level_clicks": -5}}
```

### Season 1: Frozen Zombie Handling

In Season 1, zombies can be **frozen** and must be unfrozen before rallying.

**Detection**: After clicking Search, check for `unfreeze_button_4k.png` (hexagonal blue icon)

**Unfreeze Flow**:
1. Search finds frozen zombie → Unfreeze button appears
2. Click Unfreeze → March screen opens (attack to break ice)
3. Click March → Zombie is unfrozen
4. Return to base view, click magnifying glass again
5. **Re-apply level clicks** (search panel resets to default level)
6. Search again → Now find SAME level unfrozen zombie → Rally normally

**Important**: Level clicks are re-applied after reopening the search panel to ensure we search for the SAME zombie we just unfroze. Otherwise we'd unfreeze level 45 but search for level 50.

**Retry Logic**: Up to 3 search attempts with unfreeze handling

**Templates**:
- `unfreeze_button_4k.png` - Blue hexagon with pickaxe icon
- `unfreeze_button_4k_mask.png` - Mask for background-independent matching (72% coverage)
- `march_button_4k.png` - Used after unfreeze to attack and break ice

---

## Zombie Attack Flow (Non-Elite)

**Trigger**: Zombie mode set to gold/food/iron_mine (not elite)

**Sequence**:
1. Navigate to WORLD view
2. Click magnifying glass
3. Click Zombie tab (not Elite Zombie)
4. Select zombie type (gold/food/iron_mine)
5. Set level via OCR (`target_level`) OR click plus/minus (`level_clicks`)
6. Click Search
7. Click Attack button
8. Select hero, click March

**Zombie Types**:
- `gold` - Gold zombie (points for Beast Training)
- `food` - Food zombie
- `iron_mine` - Iron mine zombie

**Level Control** (same as Elite Zombie):
- `target_level`: OCR-based, taps slider at exact position
- `level_clicks`: Relative plus/minus clicks

**API**:
```python
zombie_attack_flow(adb, zombie_type='gold', target_level=25)
zombie_attack_flow(adb, zombie_type='gold', level_clicks=-2)
```

**CLI**:
```bash
python scripts/flows/zombie_attack_flow.py --type gold --target-level 25
python scripts/flows/zombie_attack_flow.py --type food --level-clicks -3
```

**WebSocket API**:
```json
{"cmd": "run_zombie_attack", "args": {"zombie_type": "gold", "target_level": 25}}
{"cmd": "run_zombie_attack", "args": {"zombie_type": "iron_mine", "level_clicks": -2}}
```

---

## Hero Upgrade Arms Race Flow

**Trigger**: During "Enhance Hero" event, last N minutes, idle since block start

**Sequence**:
1. Click Fing Hero button at (2272, 2038)
2. Wait for hero grid (3x4)
3. Scan 12 tiles for red notification dots
4. For each tile with dot:
   - Click tile center
   - Check upgrade button (green=available, gray=unavailable)
   - If available: click upgrade at (1919, 1829)
   - If unavailable: click back
5. `return_to_base_view()`

**Red Dot Detection**:
- Count red pixels in upper-right 40x40 of each tile
- Red in BGR: B<100, G<100, R>150
- Threshold: 50+ pixels = has dot

**Hero Grid (4K)**:

| Row | Col 1 | Col 2 | Col 3 | Col 4 |
|-----|-------|-------|-------|-------|
| 1 | (1497, 413) | (1775, 413) | (2056, 413) | (2330, 413) |
| 2 | (1497, 837) | (1775, 837) | (2056, 837) | (2330, 837) |
| 3 | (1497, 1265) | (1775, 1265) | (2056, 1265) | (2330, 1265) |

**Templates**:
- `heroes_button_4k.png` (123x177, click: 2272,2038)
- `upgrade_button_available_4k.png` (407x121)
- `upgrade_button_unavailable_4k.png` (365x126)

---

## Soldier Training Arms Race Flow

**Trigger**: During "Soldier Training" event OR VS promotion day, idle 5+ min, PENDING barrack

**VS Override**: Days in `VS_SOLDIER_PROMOTION_DAYS` run soldier promotion ALL DAY.

**Sequence** (per PENDING barrack):
1. Click barrack bubble
2. **POLL** for `soldier_training_header_4k.png` (3s timeout)
3. Detect highest unlocked soldier level
4. Target = highest - 1
5. Scroll horizontally if needed
6. Click target level tile
7. **VERIFY** `train_button_4k.png`
8. Click Train at (2153, 1462)
9. Handle resource replenishment if needed
10. `return_to_base_view()` (always in finally)

**Soldier Tile Detection**:
- Bottom-half templates: `half_soldier_lv{3-8}_4k.png` (79x148)
- Fixed Y: 890-969, threshold 0.02
- Scroll direction: swipe FROM tile TO RIGHT to reveal left

**Config**:
- `ARMS_RACE_SOLDIER_TRAINING_ENABLED = True`
- `VS_SOLDIER_PROMOTION_DAYS = [2]` (Day 2 = Thursday)

**Testing**:
```bash
python scripts/flows/soldier_upgrade_flow.py --detect-only
python scripts/flows/soldier_upgrade_flow.py --scroll-and-select
python scripts/flows/soldier_upgrade_flow.py
```

---

## Non-Arms-Race Soldier Training

**Trigger**: NOT during Soldier Training event, READY barracks, 5+ min idle

**Flow**:
1. `soldier_training_flow` collects READY, trains PENDING
2. `train_soldier_at_barrack()` calculates time until next event
3. If training exceeds time → use `target_hours` to finish before event
4. Otherwise → max training time

**Timing Logic**:
```python
time_until = get_time_until_soldier_training()
if time_until and time_until.total_seconds() > 0:
    max_hours = (time_until.total_seconds() - 300) / 3600  # 5 min buffer
    max_hours = max(0.5, max_hours)  # Min 30 min
```

---

## Beast Training Arms Race Flow

**Trigger**: During "Mystic Beast Training" event, last 60 minutes

**Key Numbers** (by zombie mode):

| Mode | Stamina | Points | Actions for 30k |
|------|---------|--------|-----------------|
| elite | 24 | 2,000 | 15 rallies |
| gold/food/iron_mine | 10 | 1,000 | 30 attacks |

**Verification Loop** (`aggressive_beast_training_flow`):

```
WHILE score < 30,000 (max 5 iterations):
    1. Check score from Arms Race panel
    2. If score >= 30,000: VERIFIED DONE
    3. Calculate deficit and rallies needed
    4. Get stamina for this batch
    5. Do rallies until stamina runs out
    6. WAIT 60 SECONDS for marches to complete
    7. GOTO 1 (re-verify score)
```

**Key Points**:
- Score doesn't update until march FINISHES (~1 min)
- Must wait after rallies before re-checking score
- Only claims stamina when needed (after verification)
- Exits only when score is PROVEN >= 30,000

**Checkpoints** (in daemon):
- **60-min mark**: Run aggressive flow (once per block)
- **30-min mark**: Re-run aggressive flow (safety check)

**Config**:
- `ARMS_RACE_BEAST_TRAINING_LAST_MINUTES = 60`
- `ELITE_STAMINA_COST = 24`
- `CHEST3_TARGET = 30000`

---

## Rally Join Flow

**Trigger**: Handshake icon → Union War panel → `rally_join_flow`

**Sequence**:
1. Validate panel (heading + Team Intelligence tab)
2. Find plus buttons in rightmost column
3. For each rally (top to bottom):
   - Click plus → Team Up panel
   - OCR monster name/level
   - Check `RALLY_MONSTERS` config
   - Skip → **click grass to dismiss** (no back button)
   - Match → hero selection
4. **POLL** for Team Up panel (5s)
5. Select leftmost idle hero
6. Click Team Up
7. **POLL** for daily limit dialog (2s):
   - If found → Cancel → mark exhausted

**Team Up Dismissal**: Click grass via `find_safe_grass()`, not back button.

**Daily Limit**: Template `daily_rally_limit_dialog_4k.png` (983x527, threshold 0.05)

**Config**:
```python
RALLY_MONSTERS = [
    {"name": "Zombie Overlord", "auto_join": True, "max_level": 130, "track_daily_limit": False},
    {"name": "Elite Zombie", "auto_join": True, "max_level": 25, "track_daily_limit": True},
    {"name": "Union Boss", "auto_join": True, "max_level": 9999, "track_daily_limit": False},
    # ...
]
```

---

## Royal City Flow (Scheduled)

**Trigger**: Scheduled execution

**Prerequisite**: `go_to_mark_flow` first

**Sequence**:
1. Find/click star → open panel
2. **VERIFY** city UNCLAIMED (`royal_city_unoccupied_tab_4k.png`)
3. Perform action:
   - `scout`: click Scout button
   - `attack`: opens troop selection → hero → March
   - `rally`: opens rally setup → hero → confirm
4. `return_to_base_view()`

**Usage**:
```bash
python scripts/flows/royal_city_flow.py scout --debug
python scripts/flows/royal_city_flow.py attack --debug
python scripts/flows/royal_city_flow.py rally --debug
```

---

## Reinforce Camp Flow

**Trigger**: Manual or loop mode via CLI

**Purpose**: Reinforce a marked siege camp by clicking star icon and sending troops.

**Sequence**:
1. Go to WORLD view
2. Find and click star icon (template: `mark_star_icon_4k.png`)
3. Click Reinforce button on camp popup (template: `royal_city_reinforce_button_4k.png`)
4. Click Reinforce button on panel (template: `reinforce_panel_button_4k.png`)
5. Click leftmost hero slot (fixed: 1467, 1869)
6. Click March button (template: `march_button_4k.png`, search_region constrained)

**Templates**:
- `mark_star_icon_4k.png` - Star marker on world map
- `royal_city_reinforce_button_4k.png` - Reinforce button on camp popup
- `reinforce_panel_button_4k.png` - Blue Reinforce button on panel

**Testing**:
```bash
python scripts/flows/reinforce_camp_star_flow.py --debug
```

---

## Hospital Healing Flow

**Trigger**: Hospital bubble (HELP_READY, HEALING, SOLDIERS_WOUNDED)

**Key Concept**: Reset ALL sliders first, then fill bottom row only to 1 hour.

**Sequence**:
1. Verify hospital panel (header match)
2. Scroll + reset ALL sliders to minimum
3. Check initial time (~0)
4. Select bottom row (`buttons[-1]`)
5. Drag slider to max, check time
6. If >1 hour → binary search (8 iterations) for ~1 hour
7. Click Healing
8. If "Insufficient Resources" → Replenish All → Healing again
9. `return_to_base_view()`

**Config**:
- `MAX_SAFE_HEAL_SECONDS = 5400` (90 min safety)

---

## Bag Flow (Idle-Triggered)

**Trigger**: TOWN view + 5 min idle + 1 hour cooldown

**Sequence**:
1. Navigate to TOWN
2. Click bag (3725, 1624)
3. `bag_special_flow` - claim chests (7 templates)
4. `bag_hero_flow` - claim chests (2 templates)
5. `bag_resources_flow` - claim diamonds
6. Close bag, `return_to_base_view()`

**Critical flow**: Blocks daemon idle recovery from closing bag.

---

## Tavern Quest Flow

**Trigger**: Tavern button detected (TBD - not yet in daemon)

**Entry**: Click (80, 1220)

**Double-Pass Strategy**: After Claim, exit tavern completely, re-enter, repeat.

**My Quests Flow**:
1. Navigate to TOWN
2. Click tavern button
3. Switch to My Quests tab if needed
4. Column-restricted Claim search (X: 2100-2500)
5. If Claim → click, dismiss, EXIT tavern
6. If none → scroll, rescan (max 2 scrolls with no claims)

---

## Snowman Party Flow (Scaffolding)

**Trigger**: "Snowman Party" chat message

**Sequence**:
1. Detect yellow chat bubble
2. Click to navigate
3. Wait for snowman
4. (TBD) Click claim bubble
5. `return_to_base_view()`

**Templates**:
- `snowman_party_chat_4k.png` (772x80)
- `snowman_4k.png` (254x212)
- `snowman_claim_bubble_4k.png` (TBD)

---

## Shield Inventory Flow

**Trigger**: 6-hour scheduled check OR manual via frontend/CLI

**Sequence**:
1. Open bag (click 3725, 1624)
2. Navigate to Special tab
3. Match shield templates (8hr, 12hr, 24hr)
4. OCR count from full tile region for each found shield
5. Update `daemon_current_state.json` with counts
6. Close bag

**Templates**:
- `bag_shield_8hr_4k.png` (230x189, green background)
- `bag_shield_12hr_4k.png` (230x189, blue background)
- `bag_shield_24hr_4k.png` (230x189, purple background)

**State** (`data/daemon_current_state.json`):
```json
{
  "shield_inventory": {
    "8hr": 8,
    "12hr": 7,
    "24hr": 3,
    "timestamp": "2026-01-31T..."
  }
}
```

**CLI**:
```bash
python scripts/daemon_cli.py get_shield_inventory
python scripts/flows/shield_inventory_flow.py --debug
```

---

## Shield Use Flow

**Trigger**: Frontend button click OR CLI command

**Sequence**:
1. Open bag (click 3725, 1624)
2. Navigate to Special tab
3. Find shield icon (8hr/12hr/24hr)
4. Click shield icon
5. Click Use button
6. Close bag
7. Update inventory count in state

**Templates**:
- `bag_shield_8hr_4k.png` (green, 8-hour protection)
- `bag_shield_12hr_4k.png` (blue, 12-hour protection)
- `bag_shield_24hr_4k.png` (purple, 24-hour protection)
- `use_button_4k.png` (Use dialog button)

**CLI**:
```bash
python scripts/daemon_cli.py use_shield --shield_type 8hr
python scripts/flows/shield_use_flow.py 8hr --debug
```

**API**:
```
POST /api/shields/use
{"shield_type": "8hr"}
```

---

## Under Attack Detection

**Trigger**: Continuous monitoring in daemon loop

**Detection**: Uses `under_attack_matcher.py` template matching

**Events**:
- Attack detected → `scheduler.record_event()` with category "combat"
- Attack ended → event logged

**State** (`data/daemon_current_state.json`):
```json
{
  "under_attack": {
    "is_under_attack": false,
    "last_detected": "2026-01-31T...",
    "attack_count_today": 3
  }
}
```

**Frontend**:
- Red alert banner when under attack
- Quick shield activation buttons
- Attack events in Recent Events timeline (red "combat" dot)

---

## Bloodlust Detection

**Trigger**: Continuous monitoring in daemon loop

**Detection**: `bloodlust_matcher.py` - checks for crossed swords icon at (283, 287)

**Duration**: ~15 minutes from first detection

**Template**: `bloodlust_icon_4k.png` (62x62)

**Position**: Upper-left area, below fist icon (same location as shield active icon)

**Events**:
- Bloodlust started → `scheduler.record_event()` with category "combat"
- Bloodlust ended → event logged with actual duration

**State** (`data/daemon_current_state.json`):
```json
{
  "bloodlust": {
    "is_active": true,
    "started_at": "2026-01-31T...",
    "expected_end": "2026-01-31T..."
  }
}
```

**Frontend**:
- Orange banner with 15-minute countdown when active
- Can trigger actions when bloodlust ends (e.g., auto-shield)

**CLI**:
```bash
python utils/bloodlust_matcher.py  # Test detection
```

---

## Shield Already Active Detection

**Detection**: `shield_active_matcher.py` - checks for blue shield icon at (283, 287)

**Template**: `shield_active_icon_4k.png` (62x62)

**Position**: Same as bloodlust icon (they don't appear simultaneously)

**Behavior**:
- Shield use flow checks if shield already active before using new one
- Returns early with `shield_already_active: true` if detected
- Use `force=True` to override and apply new shield anyway

**CLI**:
```bash
# Normal - skips if shield active
python scripts/flows/shield_use_flow.py 8hr --debug

# Force - use even if shield active
python scripts/flows/shield_use_flow.py 8hr --debug --force

# Via daemon CLI
python scripts/daemon_cli.py use_shield --shield_type 8hr --force
```

---

## Shield Scheduling

**Trigger**: Frontend modal OR API call

**Features**:
- Schedule shield activation with delay (e.g., "9m 13s", "1h 30m", "10:30")
- Supports flexible time formats:
  - `5m` - 5 minutes
  - `1h 30m` - 1 hour 30 minutes
  - `90s` - 90 seconds
  - `10:30` - activate at specific time (next occurrence)
- Quick preset buttons: 5m, 10m, 30m, 1h, 2h
- Cancel scheduled shield anytime
- Only one shield can be scheduled at a time

**Frontend**:
- Clock icon button next to shield refresh
- Modal with shield type selection and time input
- Yellow banner showing countdown when scheduled
- Cancel button to abort scheduled shield

**API Endpoints**:
```
POST /api/shields/schedule
{"shield_type": "8hr", "delay_seconds": 553}

GET /api/shields/scheduled
Returns: {"scheduled": true, "shield_type": "8hr", "activate_at": "..."}

POST /api/shields/cancel
Cancels any pending scheduled shield
```
