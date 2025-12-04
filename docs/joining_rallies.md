# Joining Rally Automation

This document describes the rally joining flow for Union War events.

## Overview

The rally joining automation detects when the Union War panel is open and automatically joins available rallies by clicking the plus buttons.

## Templates and Coordinates (4K Resolution)

All templates extracted from `screenshots/joining_team.png`.

### Tab Detection Templates

| Template | Size | Position | Click Center | Purpose |
|----------|------|----------|--------------|---------|
| `team_intelligence_tab_4k.png` | 587x116 | (1336, 125) | (1629, 183) | Verify we're on Team Intelligence tab |
| `solo_intelligence_tab_4k.png` | 549x125 | (1916, 125) | (2190, 187) | Solo tab (not used, for reference) |

### Panel Detection Template

| Template | Size | Position | Click Center | Purpose |
|----------|------|----------|--------------|---------|
| `union_war_heading_4k.png` | 315x58 | (1754, 30) | (1911, 59) | Verify Union War panel is open |

### Rally Element Templates

| Template | Size | Search Method | Threshold | Purpose |
|----------|------|---------------|-----------|---------|
| `rally_plus_button_4k.png` | 130x130 | TM_SQDIFF_NORMED | 0.05 | Join rally button (4 slots per rally) |
| `rally_monster_icon_4k.png` | 290x363 | (2130, 326) | (2275, 507) | Monster icon with text label below (for reference/validation) |

## Flow Logic

### Prerequisites
1. User must have Union War panel open
2. Must be on "Team Intelligence" tab
3. Must see "Union War" heading at top

### Rally Detection
The flow searches for rally plus buttons in the list and clicks them to join rallies.

**Plus Button Search:**
- Template: `rally_plus_button_4k.png` (130x130)
- Search method: Template matching with TM_SQDIFF_NORMED
- Threshold: 0.05
- Expected positions: 4 horizontal slots per rally row

**Rally Slot Layout:**
- **4 horizontal slots per rally row**
- **Y coordinate**: Varies per rally (each rally at different row)
- **X coordinates** (EXACT for slots 2, 3, 4; calculated for slot 1):
  - Slot 1: 1404 (calculated via 166px spacing)
  - Slot 2: 1570 (EXACT from template matching)
  - Slot 3: 1737 (EXACT from template matching)
  - Slot 4: 1902 (EXACT from template matching)
- **Spacing**: 166 pixels (used to calculate slot 1 position)

**Example Coordinates:**
- Rally at Y=474: Slots at (1404,474), (1570,474), (1737,474), (1902,474)
- Rally at Y=964: Slots at (1411,964), (1574,964), (1737,964), (1902,964)

**Detection Strategy:**
- Use template matching across entire panel
- Each rally row can have 0-4 plus buttons visible
- Filled slots show player icons instead of plus buttons
- Click center = (X + 65, Y + 65) for 130x130 template

### Flow Steps

1. **Verify Panel State**
   - Check for "Union War" heading at top
   - Verify "Team Intelligence" tab is selected
   - If not on correct tab/panel, abort

2. **Search for Plus Buttons**
   - Search entire panel area for plus button templates
   - Sort by Y coordinate (top to bottom)

3. **Click Plus Buttons**
   - For each detected plus button:
     - Click at center position
     - Wait for join confirmation
     - Move to next button

4. **Exit Flow**
   - Click back button to close panel
   - Return to base view

## Detection Notes

### Tab Verification
- **Team Intelligence tab**: Selected state (highlighted)
- **Solo Intelligence tab**: Unselected state (dimmed)
- Only proceed if Team Intelligence is active

### Monster Icon Usage
The monster icon template (`rally_monster_icon_4k.png`) can be used to:
- Validate that a rally entry is properly formatted
- Confirm we're looking at the correct list
- Future: Identify rally type (if different monsters have different behaviors)

## Configuration

### Monster Configuration (config.py)

Rally monsters are configured with per-monster auto-join settings:

```python
RALLY_MONSTERS = [
    {
        "name": "Zombie Overlord",
        "auto_join": True,       # Auto-join rallies for this monster
        "max_level": 130,        # Join if level <= 130
        "has_level": True,
        "level_increment": 10,
        "level_range": "100+",
    },
    {
        "name": "Elite Zombie",
        "auto_join": True,
        "max_level": 30,
        "has_level": True,
        "level_increment": 1,
        "level_range": "1-40",
    },
    {
        "name": "Nightfall Servant",
        "auto_join": True,
        "max_level": 30,
        "has_level": True,
        "level_increment": 1,
        "level_range": "1-40",
    },
]

# General rally settings
RALLY_JOIN_ENABLED = False  # Set to True to enable rally joining
RALLY_MARCH_BUTTON_COOLDOWN = 30  # Seconds between march button clicks
RALLY_DATA_GATHERING_MODE = False  # Save monster crops to data_gathering/
```

### OCR and Validation

- **OCR Method**: JSON-based extraction using Qwen2.5-VL-3B
- **OCR Prompt**: Auto-generated from `RALLY_MONSTERS` list
- **Expected Format**: `{"name": "Monster Name", "level": 130}`
- **Validation**: Checks `auto_join` flag and `max_level` threshold

### Data Gathering

When `RALLY_DATA_GATHERING_MODE = True`, monster icon crops are saved to:
- `data_gathering/matched/` - Known monsters from `RALLY_MONSTERS` list
- `data_gathering/unknown/` - Monsters not in configuration

Filename format: `monster_{name}_lv{level}_{timestamp}_rally{idx}_x{x}_y{y}.png`

## Matchers

Location: `utils/rally_join_matcher.py`

```python
class RallyJoinMatcher:
    """Detects plus buttons in Union War rally list"""

    def find_plus_buttons(self, frame):
        """
        Find all plus buttons in the rally list.
        Returns list of (x, y, score) tuples.
        """
        pass

    def is_team_intelligence_tab(self, frame):
        """Check if Team Intelligence tab is selected"""
        pass

    def is_union_war_panel(self, frame):
        """Check if Union War panel is open"""
        pass
```

## Integration with Daemon

The icon daemon detects the rally march button and automatically triggers the flow:

### Trigger Conditions
1. **March button detected** - Green march button visible on screen
2. **User idle** - Idle time >= `IDLE_THRESHOLD` (default 0s for testing, 300s for production)
3. **Valid view** - Currently in TOWN or WORLD view
4. **Cooldown elapsed** - At least 30s since last march button click

### Flow Sequence
1. Daemon detects march button
2. Clicks march button (opens Union War panel)
3. Waits 0.5s for panel to start loading
4. Triggers `rally_join_flow()`
5. Flow validates panel, finds plus buttons, validates monsters via OCR
6. Joins first matching rally (or exits if none match)
7. Returns to base view

### Monster Validation
- OCR extracts monster name and level from icon
- Checks if monster is in `RALLY_MONSTERS` with `auto_join: True`
- Only joins if level <= `max_level` threshold
- Saves monster crops to `data_gathering/` if enabled

## Future Enhancements

1. **Rally Type Selection**: Only join specific rally types (e.g., Elite Zombies only)
2. **Stamina Check**: Verify sufficient stamina before joining
3. **Rally Status**: Detect if rally is full or already joined
4. **Auto-Open Panel**: Navigate to Union War panel automatically during event windows

## Related Documentation

- [README.md](../README.md) - Main project documentation
- [arms_race.md](arms_race.md) - Arms Race event automation
- [future_steps.md](future_steps.md) - Automation roadmap
