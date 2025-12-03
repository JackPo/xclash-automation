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

| Template | Size | Position | Click Center | Purpose |
|----------|------|----------|--------------|---------|
| `rally_plus_button_4k.png` | 127x132 | (1405, 477) | (1468, 543) | Join rally button |
| `rally_monster_icon_4k.png` | 290x363 | (2130, 326) | (2275, 507) | Monster icon with text label below (for reference/validation) |

## Flow Logic

### Prerequisites
1. User must have Union War panel open
2. Must be on "Team Intelligence" tab
3. Must see "Union War" heading at top

### Rally Detection
The flow searches for rally plus buttons in the list and clicks them to join rallies.

**Plus Button Search:**
- Template: `rally_plus_button_4k.png` (127x132)
- Search method: Template matching with TM_SQDIFF_NORMED
- Threshold: TBD (needs calibration)
- Expected positions: Vertical list on left side of panel

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

```python
# Rally joining settings (config.py)
RALLY_JOIN_ENABLED = True
RALLY_JOIN_CHECK_INTERVAL = 60  # Check every 60 seconds
RALLY_JOIN_PLUS_THRESHOLD = 0.05  # Template matching threshold
```

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

The icon daemon will check for Union War panel state and trigger rally joining when:
1. User is idle for 5+ minutes
2. Union War panel is detected as open
3. Team Intelligence tab is active
4. Plus buttons are found in the list

## Future Enhancements

1. **Rally Type Selection**: Only join specific rally types (e.g., Elite Zombies only)
2. **Stamina Check**: Verify sufficient stamina before joining
3. **Rally Status**: Detect if rally is full or already joined
4. **Auto-Open Panel**: Navigate to Union War panel automatically during event windows

## Related Documentation

- [README.md](../README.md) - Main project documentation
- [arms_race.md](arms_race.md) - Arms Race event automation
- [future_steps.md](future_steps.md) - Automation roadmap
