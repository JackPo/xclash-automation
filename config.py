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

# Use Button during Beast Training (consumes stamina recovery items)
ARMS_RACE_BEAST_TRAINING_USE_ENABLED = True    # Enable/disable Use button automation
ARMS_RACE_BEAST_TRAINING_USE_MAX = 4           # Max Use button clicks per Beast Training block
ARMS_RACE_BEAST_TRAINING_USE_COOLDOWN = 180    # 3 minutes between Use button clicks
ARMS_RACE_BEAST_TRAINING_USE_LAST_MINUTES = 10 # 3rd+ uses only allowed in last N minutes
ARMS_RACE_BEAST_TRAINING_MAX_RALLIES = 15      # Don't use stamina items if rally count >= this
ARMS_RACE_BEAST_TRAINING_USE_STAMINA_THRESHOLD = 20  # Use stamina items when stamina < this

# Enhance Hero (during Enhance Hero event)
# Triggers hero_upgrade_arms_race_flow to upgrade heroes
# IMPORTANT: Only triggers if user was idle since the START of the Enhance Hero block.
# This ensures the automation doesn't interrupt active gameplay.
ARMS_RACE_ENHANCE_HERO_ENABLED = True          # Enable/disable hero enhancement automation
ARMS_RACE_ENHANCE_HERO_LAST_MINUTES = 20       # Trigger in last N minutes of Enhance Hero
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

# Cooldowns (seconds)
AFK_REWARDS_COOLDOWN = 3600        # 1 hour between AFK rewards checks
UNION_GIFTS_COOLDOWN = 3600        # 1 hour between union gift claims
UNION_TECHNOLOGY_COOLDOWN = 3600   # 1 hour between union technology donations
UNION_FLOW_SEPARATION = 600        # 10 minutes minimum between union gifts and union technology
SOLDIER_TRAINING_COOLDOWN = 300    # 5 minutes between soldier training collection attempts
UNION_GIFTS_IDLE_THRESHOLD = 1200  # 20 minutes idle required for union gifts

# Recovery
UNKNOWN_STATE_TIMEOUT = 180        # Seconds in CONTINUOUS UNKNOWN state before recovery

# Screen regions (4K resolution: 3840x2160)
STAMINA_REGION = (69, 203, 96, 60)  # x, y, w, h for stamina OCR

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
# DETECTION THRESHOLDS (TM_SQDIFF_NORMED - lower score = better match)
# Threshold is maximum score to consider a match. Typical: 0.04-0.10
# =============================================================================

THRESHOLDS = {
    'dog_house': 0.1,
    'corn': 0.06,
    'gold': 0.06,
    'iron': 0.08,
    'gem': 0.13,
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

# Match threshold for barracks state (TM_SQDIFF_NORMED)
# Relaxed to 0.08 to handle animation variance, with yellow pixel verification
BARRACKS_MATCH_THRESHOLD = 0.08

# Yellow pixel threshold for READY vs PENDING verification
# READY (yellow soldier) has ~2600 yellow pixels, PENDING (white) has ~0
BARRACKS_YELLOW_PIXEL_THRESHOLD = 1500

# Default soldier level to train when NOT in Arms Race Soldier Training event
# During Arms Race Soldier Training, this may be overridden to train higher levels
SOLDIER_TRAINING_DEFAULT_LEVEL = 4

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

# BlueStacks keybindings (must match your BlueStacks game controls setup)
# These are sent via Windows API, not ADB
KEY_ZOOM_IN = 'shift+a'    # Pinch zoom in
KEY_ZOOM_OUT = 'shift+z'   # Pinch zoom out
KEY_PAN_UP = 'up'          # Arrow keys for camera pan
KEY_PAN_DOWN = 'down'
KEY_PAN_LEFT = 'left'
KEY_PAN_RIGHT = 'right'

# =============================================================================
# RALLY JOINING AUTOMATION
# =============================================================================
# Automatically join Union War rallies based on monster type and level.

# Rally joining enable/disable
RALLY_JOIN_ENABLED = False  # Set to True to enable rally joining
RALLY_MARCH_BUTTON_COOLDOWN = 30  # Seconds between march button clicks

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
]

# Legacy dict for backward compatibility (auto-generated from RALLY_MONSTERS)
# Only includes monsters with auto_join=True
RALLY_JOIN_MONSTERS = {
    monster["name"].lower(): monster["max_level"]
    for monster in RALLY_MONSTERS
    if monster.get("auto_join", True)
}

# Plus button detection (fixed X + Y search)
RALLY_PLUS_BUTTON_X = 1905  # Fixed X coordinate (rightmost column)
RALLY_PLUS_BUTTON_THRESHOLD = 0.05  # Template matching threshold
RALLY_PLUS_SEARCH_Y_START = 400  # Y search range start
RALLY_PLUS_SEARCH_Y_END = 1800   # Y search range end

# Monster icon relative to plus button
RALLY_MONSTER_OFFSET_X = 235   # Pixels LEFT of plus button
RALLY_MONSTER_OFFSET_Y = -151  # Pixels above plus button
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
