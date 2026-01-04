"""
Configuration loader - loads API keys and parameters from config_local.py or environment variables.

Usage:
    from config import GOOGLE_API_KEY, IDLE_THRESHOLD

Setup:
    1. Copy config_local.py.example to config_local.py
    2. Fill in your API keys in config_local.py
    3. Optionally override any default parameters
    4. config_local.py is gitignored so your keys stay safe
"""
import os

# =============================================================================
# DEFAULT PARAMETERS (can be overridden in config_local.py)
# =============================================================================

# API Keys (optional - only needed for development tools)
# GOOGLE_API_KEY: Used by detect_object.py for Gemini-based template extraction
# ANTHROPIC_API_KEY: Used for Claude OCR (experimental)
GOOGLE_API_KEY = None
ANTHROPIC_API_KEY = None

# Daemon timing
DAEMON_INTERVAL = 2.0              # Check interval (seconds)
IDLE_THRESHOLD = 300               # Default: 5 minutes idle required for automation (override in config_local.py)
IDLE_CHECK_INTERVAL = 300          # 5 minutes between idle recovery checks

# WebSocket API server
DAEMON_SERVER_PORT = 9876          # Port for WebSocket API (ws://localhost:9876)
DAEMON_SERVER_ENABLED = True       # Set to False to disable WebSocket server

# Elite Zombie rally
ELITE_ZOMBIE_STAMINA_THRESHOLD = 118   # Minimum stamina to trigger rally
ELITE_ZOMBIE_CONSECUTIVE_REQUIRED = 3  # Consecutive valid OCR reads required
ELITE_ZOMBIE_PLUS_CLICKS = 5           # Times to click plus button (increases zombie level)

# =============================================================================
# ARMS RACE EVENT AUTOMATION
# =============================================================================
# Arms Race rotates through 5 activities every 4 hours:
# City Construction → Soldier Training → Tech Research → Mystic Beast → Enhance Hero
# These settings control event-specific automation triggers.
#
# IMPORTANT: Auto-rallies only trigger during specific events and time windows!
# - Beast Training rallies: Only during "Mystic Beast" event, in the LAST N minutes
# - Soldier upgrades: Only during "Soldier Training" event
# - Hero upgrades: Only during "Enhance Hero" event, in the LAST N minutes
#
# Check daemon log output: AR:Mys(45m) means Mystic Beast with 45 minutes remaining
# Rallies won't trigger if remaining time > ARMS_RACE_BEAST_TRAINING_LAST_MINUTES
#
# See docs/arms_race.md for full documentation.

# Beast Training (during Mystic Beast event)
# Triggers elite_zombie_flow with 0 plus clicks to train beasts
# NOTE: Only triggers when time remaining <= LAST_MINUTES (default: last 60 min of 4-hour event)
ARMS_RACE_BEAST_TRAINING_ENABLED = True        # Enable/disable beast training automation
ARMS_RACE_BEAST_TRAINING_LAST_MINUTES = 60     # Only trigger in last N minutes (set to 240 for full event)
ARMS_RACE_BEAST_TRAINING_STAMINA_THRESHOLD = 20  # Minimum stamina required
ARMS_RACE_BEAST_TRAINING_COOLDOWN = 90         # Seconds between rallies
ARMS_RACE_STAMINA_CLAIM_THRESHOLD = 60         # Claim free stamina when stamina < this value
ARMS_RACE_BEAST_TRAINING_PRE_EVENT_MINUTES = 6 # Claim stamina + block elite rallies this many min BEFORE event

# Use Button during Beast Training (consumes stamina recovery items)
ARMS_RACE_BEAST_TRAINING_USE_ENABLED = True    # Enable/disable Use button automation
ARMS_RACE_BEAST_TRAINING_USE_MAX = 4           # Max Use button clicks per Beast Training block
ARMS_RACE_BEAST_TRAINING_USE_COOLDOWN = 180    # 3 minutes between Use button clicks
ARMS_RACE_BEAST_TRAINING_USE_LAST_MINUTES = 10 # 3rd+ uses only allowed in last N minutes
ARMS_RACE_BEAST_TRAINING_MAX_RALLIES = 15      # Don't use stamina items if rally count >= this
ARMS_RACE_BEAST_TRAINING_USE_STAMINA_THRESHOLD = 20  # Use stamina items when stamina < this

# Zombie Mode for Beast Training
# "elite" = elite_zombie_flow (20 stamina, 2000 pts), "gold"/"food"/"iron_mine" = zombie_attack_flow (10 stamina, 1000 pts)
# Set via WebSocket: {"action": "set_zombie_mode", "mode": "gold", "hours": 24}
ZOMBIE_MODE_CONFIG = {
    "elite": {"stamina": 20, "points": 2000, "flow": "elite_zombie", "plus_clicks": 0},
    "gold": {"stamina": 10, "points": 1000, "flow": "zombie_attack", "zombie_type": "gold", "plus_clicks": 10},
    "food": {"stamina": 10, "points": 1000, "flow": "zombie_attack", "zombie_type": "food", "plus_clicks": 10},
    "iron_mine": {"stamina": 10, "points": 1000, "flow": "zombie_attack", "zombie_type": "iron_mine", "plus_clicks": 10},
}

# Enhance Hero (during Enhance Hero event)
# Triggers hero_upgrade_arms_race_flow to upgrade heroes
# Flow checks current points from Events panel - skips if chest3 already reached
# NO idle requirement - the quick progress check is non-disruptive
ARMS_RACE_ENHANCE_HERO_ENABLED = True          # Enable/disable hero enhancement automation
ARMS_RACE_ENHANCE_HERO_LAST_MINUTES = 10       # Trigger in last N minutes of Enhance Hero
ARMS_RACE_ENHANCE_HERO_MAX_UPGRADES = 1        # Max hero upgrades per block (1 is usually enough)

# Soldier Training (during Soldier Training event)
# Triggers soldier_upgrade_flow to upgrade soldiers at PENDING barracks
# Requires: idle 5+ min, any barrack in PENDING state, TOWN view with dog house aligned
ARMS_RACE_SOLDIER_TRAINING_ENABLED = True      # Enable/disable soldier upgrade automation

# =============================================================================
# VS EVENT OVERRIDES
# =============================================================================
# VS (Versus) events have daily themes that span all Arms Race events in a day.
# These settings override the normal event-specific triggers.
#
# Arms Race Day Reference (7-day cycle):
#   Day 1 = Wednesday (cycle starts 6PM PT Tuesday / 02:00 UTC Wednesday)
#   Day 2 = Thursday
#   Day 3 = Friday
#   Day 4 = Saturday
#   Day 5 = Sunday
#   Day 6 = Monday
#   Day 7 = Tuesday
#
# Check current day: python -c "from utils.arms_race import get_arms_race_status; print(get_arms_race_status()['day'])"

# VS Soldier Promotion Days
# When the current Arms Race day is in this list, soldier promotions trigger ALL DAY
# regardless of which 4-hour event is active (overrides "Soldier Training" event check)
# Example: [2] = Day 2 only, [2, 5] = Day 2 and Day 5
VS_SOLDIER_PROMOTION_DAYS = [2]  # Day 2 = Thursday in current cycle

# VS Level Chest Days
# When the current Arms Race day is in this list, open level chests (Lv2, Lv3, Lv4) in bag
# Example: [3] = Day 3 only (Wednesday)
VS_LEVEL_CHEST_DAYS = [7]  # Day 7 = chest-opening VS event day

# VS Question Mark Quest Skip Days
# On these days, skip starting quests with question mark reward tiles (only gold quests allowed)
# Day 3 = gold quest event day
# Day 6 = day before chest opening, save question marks for Day 7
VS_QUESTION_MARK_SKIP_DAYS = [3, 6]

# Tavern Quest Time Gating (Pacific Time)
# Quest starts (clicking Go) only allowed from start time until server reset
# This applies to BOTH gold scroll quests AND question mark quests
TAVERN_QUEST_START_HOUR = 22  # 10 PM
TAVERN_QUEST_START_MINUTE = 30  # :30
# Server resets at 02:00 UTC = 18:00 Pacific (6 PM)
TAVERN_SERVER_RESET_HOUR = 18  # 6 PM Pacific - blocked window starts here

# Cooldowns (seconds)
AFK_REWARDS_COOLDOWN = 3600        # 1 hour between AFK rewards checks
UNION_GIFTS_COOLDOWN = 3600        # 1 hour between union gift claims
UNION_TECHNOLOGY_COOLDOWN = 3600   # 1 hour between union technology donations
UNION_FLOW_SEPARATION = 600        # 10 minutes minimum between union gifts and union technology
SOLDIER_TRAINING_COOLDOWN = 300    # 5 minutes between soldier training collection attempts
BAG_FLOW_COOLDOWN = 1200           # 20 minutes between bag flow runs
GIFT_BOX_COOLDOWN = 3600           # 1 hour between gift box claims (WORLD view)
TAVERN_SCAN_COOLDOWN = 1800        # 30 minutes between tavern scans

# Recovery
UNKNOWN_STATE_TIMEOUT = 180        # Seconds in CONTINUOUS UNKNOWN state before recovery
UNKNOWN_LOOP_TIMEOUT = 480         # 8 minutes - force restart if recovery keeps cycling

# Resolution check (prevents template matching failures from resolution drift)
RESOLUTION_CHECK_INTERVAL = 10     # Check resolution every N daemon iterations (~30 seconds)
EXPECTED_RESOLUTION = "3840x2160"  # Expected BlueStacks resolution for templates

# Screen regions (4K resolution: 3840x2160)
STAMINA_REGION = (69, 203, 96, 60)  # x, y, w, h for stamina OCR
STAMINA_REGEN_BUFFER = 15  # Subtract from regen estimate to ensure last rally completes

# =============================================================================
# TOWN LAYOUT COORDINATES (4K resolution)
# These vary by user's town arrangement. Override in config_local.py for your layout.
# Use detect_object.py to find positions: python detect_object.py screenshot.png "the corn bubble"
# =============================================================================

# Dog house - used as alignment anchor for harvest detection
DOG_HOUSE_POSITION = (1605, 882)
DOG_HOUSE_SIZE = (172, 197)

# Resource bubble positions: {'region': (x, y, w, h), 'click': (x, y)}
CORN_BUBBLE = {
    'region': (1015, 869, 67, 57),
    'click': (1048, 897)
}
GOLD_BUBBLE = {
    'region': (1369, 800, 53, 43),
    'click': (1395, 835)
}
IRON_BUBBLE = {
    'region': (1617, 351, 46, 32),
    'click': (1639, 377)
}
GEM_BUBBLE = {
    'region': (1378, 652, 54, 51),
    'click': (1405, 696)
}
CABBAGE_BUBBLE = {
    'region': (1267, 277, 67, 57),
    'click': (1300, 305)
}
EQUIPMENT_BUBBLE = {
    'region': (1246, 859, 67, 57),
    'click': (1279, 887)
}

# =============================================================================
# DETECTION THRESHOLDS
# NOTE: Using COLOR matching. Masks auto-detected by template_matcher.
#
# MASKED templates (*_mask_4k.png exists): score ~1.0 = match, threshold is MINIMUM
# NON-MASKED templates: score ~0.0 = match, threshold is MAXIMUM
# =============================================================================

# Masked templates - threshold is MINIMUM score required (score >= threshold)
# These have *_mask_4k.png files, use TM_CCORR_NORMED
THRESHOLDS_MASKED = {
    'corn': 0.99,       # corn_harvest_bubble_mask_4k.png
    'gold': 0.99,       # gold_coin_tight_mask_4k.png
    'iron': 0.99,       # iron_bar_tight_mask_4k.png
    'gem': 0.99,        # gem_tight_mask_4k.png
}

# Non-masked templates - threshold is MAXIMUM score allowed (score <= threshold)
# Use TM_SQDIFF_NORMED
THRESHOLDS_SQDIFF = {
    'dog_house': 0.1,
    'cabbage': 0.05,
    'equipment': 0.06,
    'handshake': 0.04,
    'treasure_map': 0.05,
    'harvest_box': 0.1,
    'afk_rewards': 0.06,
    'back_button': 0.06,
    'claim_button': 0.05,
    'use_button': 0.05,
}

# Combined for backward compatibility - matchers use this
THRESHOLDS = {**THRESHOLDS_SQDIFF, **THRESHOLDS_MASKED}

# =============================================================================
# BARRACKS POSITIONS (4K resolution)
# Used by barracks_state_matcher to detect soldier training state
# Each barrack has a floating bubble icon above it (soldier face or stopwatch)
# =============================================================================

# Position where each barracks bubble appears (top-left corner of 81x87 template)
BARRACKS_POSITIONS = [
    (2891, 1317),  # Barrack 1 - lowest/rightmost
    (2768, 1237),  # Barrack 2 - middle left
    (3005, 1237),  # Barrack 3 - middle right
    (2883, 1157),  # Barrack 4 - highest/center
]

# Template size for barracks state detection
BARRACKS_TEMPLATE_SIZE = (81, 87)  # width, height

# Click offset from bubble top-left to center (for clicking barracks bubbles)
# Bubble is 81x87, so center offset is ~40, 43
BARRACKS_CLICK_OFFSETS = (40, 43)

# Match threshold for barracks state (TM_SQDIFF_NORMED)
# Raised to 0.08 from 0.06 due to animation variance (scores 0.00-0.08)
BARRACKS_MATCH_THRESHOLD = 0.08  # With yellow pixel verification for READY/PENDING

# Yellow pixel threshold for READY vs PENDING verification
# READY (yellow soldier) has ~1200-1600 yellow pixels, PENDING (white) has ~0
# (Reduced from 1500 after template resize from 81x87 to 61x67)
BARRACKS_YELLOW_PIXEL_THRESHOLD = 1000

# Default soldier level to train when NOT in Arms Race Soldier Training event
# During Arms Race Soldier Training, this may be overridden to train higher levels
SOLDIER_TRAINING_DEFAULT_LEVEL = 4

# =============================================================================
# HOSPITAL STATE DETECTION (4K resolution)
# Used by hospital_state_matcher to detect hospital status
# Hospital has a floating bubble icon above it (briefcase or yellow soldier)
# =============================================================================

# Position where hospital bubble appears (same position for both templates)
HOSPITAL_ICON_POSITION = (3312, 344)  # x, y - top-left corner
HOSPITAL_ICON_SIZE = (61, 67)         # width, height

# Click position - hospital building center (not bubble center)
HOSPITAL_CLICK_POSITION = (3342, 377)  # Icon center, not building

# Match threshold (TM_SQDIFF_NORMED) - stricter than barracks
HOSPITAL_MATCH_THRESHOLD = 0.03

# Consecutive frames required before triggering (same as barracks)
HOSPITAL_CONSECUTIVE_REQUIRED = 10

# =============================================================================
# STAMINA POPUP BUTTON POSITIONS (4K resolution)
# Used by stamina_claim_flow and stamina_use_flow
# =============================================================================

# Claim button in stamina popup (free stamina every 4 hours)
STAMINA_CLAIM_BUTTON = {
    'search_region': (1800, 400, 800, 500),  # x, y, w, h - upper half of popup
    'click': (2284, 743),
}

# Use button in stamina popup (+50 stamina recovery items)
STAMINA_USE_BUTTON = {
    'search_region': (1800, 1100, 800, 500),  # x, y, w, h - lower half of popup
    'click': (2284, 1440),
}

# =============================================================================
# COMMON UI POSITIONS (4K resolution)
# =============================================================================

# Back button - used to close popups, exit panels, dismiss dialogs
BACK_BUTTON_CLICK = (1407, 2055)

# Toggle button - switches between TOWN and WORLD views
TOGGLE_BUTTON_CLICK = (3720, 2040)

# BlueStacks keybindings (must match your BlueStacks game controls setup)
# These are sent via Windows API, not ADB
KEY_ZOOM_IN = 'shift+a'    # Pinch zoom in
KEY_ZOOM_OUT = 'shift+z'   # Pinch zoom out
KEY_PAN_UP = 'up'          # Arrow keys for camera pan
KEY_PAN_DOWN = 'down'
KEY_PAN_LEFT = 'left'
KEY_PAN_RIGHT = 'right'

# =============================================================================
# ROYAL CITY PANEL BUTTONS (4K resolution)
# =============================================================================
# When clicking on a Royal City (via Mark or map), a panel opens with buttons.
# Button positions vary based on panel location, but RELATIVE positions are stable.
# Find Attack button, then calculate others using offsets.

# Relative offsets from Attack button (verified across multiple screenshots)
ROYAL_CITY_BUTTON_OFFSETS = {
    'attack': (0, 0),      # Reference point
    'rally': (205, 49),    # Attack + (205, 49)
    'scout': (411, 0),     # Attack + (411, 0)
}

# Button size (all same)
ROYAL_CITY_BUTTON_SIZE = (153, 177)

# Templates (in templates/ground_truth/)
# - royal_city_attack_button_4k.png + royal_city_attack_button_mask_4k.png
# - rally_button_4k.png + rally_button_mask_4k.png
# - royal_city_scout_button_4k.png + royal_city_scout_button_mask_4k.png
# - royal_city_unoccupied_tab_4k.png (570x55) - detects if city is unoccupied

# =============================================================================
# RALLY JOINING AUTOMATION
# =============================================================================
# Automatically join Union War rallies based on monster type and level.

# Rally joining enable/disable
RALLY_JOIN_ENABLED = False  # Set to True to enable rally joining
RALLY_MARCH_BUTTON_COOLDOWN = 30  # Seconds between march button clicks

# Rally daily limit override
# When True, click Confirm on "daily rewards exhausted" dialog instead of Cancel.
# This joins rallies even without rewards (to help alliance members).
RALLY_IGNORE_DAILY_LIMIT = False  # Global flag (always ignore)

# =============================================================================
# SPECIAL EVENTS REGISTRY
# =============================================================================
# Central registry of special events for automation triggers.
# Each event can have properties like: ignore_rally_limit, special_flows, etc.
# Server resets at 02:00 UTC daily - end date means active until next day 02:00 UTC.
SPECIAL_EVENTS = [
    {
        "name": "Winter Fest",
        "start": "2025-12-22",
        "end": "2025-12-28",
        "ignore_rally_limit": True,  # Click Confirm on daily limit dialog
    },
    {
        "name": "New Year's Feast",
        "start": "2025-12-28",
        "end": "2026-01-04",
        "ignore_rally_limit": False,  # Respect daily limits
    },
]

# Derived: events where rally limit is ignored (for backwards compatibility)
RALLY_IGNORE_DAILY_LIMIT_EVENTS = [
    e for e in SPECIAL_EVENTS if e.get("ignore_rally_limit", False)
]

# Union Boss mode - faster rally joining when Union Boss detected
UNION_BOSS_MODE_DURATION = 1800   # 30 minutes of faster rally joining
UNION_BOSS_RALLY_COOLDOWN = 15    # 15 seconds between rally joins during Union Boss mode

# Monster configuration: List of known monsters with metadata
# Each monster has: name, auto_join, max_level, level_increment, level_range
RALLY_MONSTERS = [
    {
        "name": "Zombie Overlord",
        "auto_join": True,       # Auto-join rallies for this monster
        "max_level": 130,        # Join if level <= 130
        "has_level": True,
        "level_increment": 10,   # Levels: 100, 110, 120, 130, 140, etc.
        "level_range": "100+",
        "track_daily_limit": False,  # No daily limit, always joinable
    },
    {
        "name": "Elite Zombie",
        "auto_join": True,       # Auto-join rallies for this monster
        "max_level": 25,         # Join if level <= 25
        "has_level": True,
        "level_increment": 1,    # Levels: 1-40
        "level_range": "1-40",
        "track_daily_limit": True,   # Has daily limit, track exhaustion
    },
    {
        "name": "Union Boss",
        "auto_join": True,       # Auto-join rallies for this monster
        "max_level": 9999,       # Join any level (effectively no limit)
        "has_level": True,
        "level_increment": 1,
        "level_range": "any",
        "track_daily_limit": False,  # No daily limit
    },
    {
        "name": "Nightfall Servant",
        "auto_join": True,       # Auto-join rallies for this monster
        "max_level": 25,         # Join if level <= 25
        "has_level": True,
        "level_increment": 1,    # Levels: 1-40
        "level_range": "1-40",
        "track_daily_limit": True,   # Has daily limit, track exhaustion
    },
    {
        "name": "Undead Boss",
        "auto_join": True,       # Auto-join rallies for this monster
        "max_level": 25,         # Join if level <= 25
        "has_level": True,
        "level_increment": 1,
        "level_range": "1-40",
        "track_daily_limit": True,   # Has daily limit, track exhaustion
    },
    {
        "name": "Klass",
        "auto_join": True,       # Auto-join rallies for this monster
        "max_level": 30,         # Join if level <= 30
        "has_level": True,
        "level_increment": 1,
        "level_range": "1-40",
        "track_daily_limit": True,   # Has daily limit, track exhaustion
    },
]

# Legacy dict for backward compatibility (auto-generated from RALLY_MONSTERS)
# Only includes monsters with auto_join=True
RALLY_JOIN_MONSTERS = {
    monster["name"].lower(): monster["max_level"]
    for monster in RALLY_MONSTERS
    if monster.get("auto_join", True)
}

# Plus button detection (fixed X + Y search)
RALLY_PLUS_BUTTON_X = 1902  # Fixed X coordinate (rightmost column, matches template detection)
RALLY_PLUS_BUTTON_THRESHOLD = 0.05  # Template matching threshold
RALLY_PLUS_SEARCH_Y_START = 400  # Y search range start
RALLY_PLUS_SEARCH_Y_END = 1800   # Y search range end

# Monster icon relative to plus button CENTER (from rally_plus_matcher)
RALLY_MONSTER_OFFSET_X = 235   # Pixels RIGHT of plus button center
RALLY_MONSTER_OFFSET_Y = -151  # Pixels ABOVE plus button center (negative = up)
RALLY_MONSTER_WIDTH = 290      # Monster icon width
RALLY_MONSTER_HEIGHT = 363     # Monster icon height

# Data gathering mode - collects monster samples for OCR tuning
RALLY_DATA_GATHERING_MODE = False  # Set to True to collect monster crops without joining

# =============================================================================
# OCR PROMPTS - Specific prompts for different OCR use cases
# =============================================================================

# Rally monster name and level (auto-generated from RALLY_MONSTERS)
def _generate_rally_monster_prompt():
    """Generate OCR prompt with known monster names for fuzzy matching."""
    monster_names = [m["name"] for m in RALLY_MONSTERS]
    monster_list = ", ".join(monster_names)

    return (
        f"Read the monster name and level from this game character portrait. "
        f"The image shows a character icon with text overlays. "
        f"Known monsters include: {monster_list}. "
        f"Return your answer as JSON with two fields: \"name\" (string) and \"level\" (integer). "
        f"If the text roughly matches one of the known monsters, use that name. "
        f"If you cannot match a known monster, use the exact text you see for the name. "
        f"Example: {{\"name\": \"Zombie Overlord\", \"level\": 130}}"
    )

OCR_PROMPT_RALLY_MONSTER = _generate_rally_monster_prompt()

# Stamina number extraction
OCR_PROMPT_STAMINA = (
    "Read the number displayed in this game UI element. "
    "This is a stamina/energy counter showing a numeric value between 0 and 200. "
    "Return only the number, nothing else."
)

# Training time slider
OCR_PROMPT_TRAINING_TIME = (
    "Read the time duration displayed in this game UI element. "
    "The format is expected to be XX:XX:XX (hours:minutes:seconds). "
    "Return exactly what is shown, preserving the format."
)

# =============================================================================
# LOAD LOCAL OVERRIDES
# =============================================================================

# Try to load from config_local.py first (for local development)
try:
    from config_local import *
    print("Loaded config from config_local.py")
except ImportError:
    # Fall back to environment variables for API keys (optional, for development only)
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')
