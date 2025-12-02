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
DAEMON_INTERVAL = 3.0              # Check interval (seconds)
IDLE_THRESHOLD = 300               # 5 minutes before idle triggers activate
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

# Beast Training (during Mystic Beast event)
# Triggers elite_zombie_flow with 0 plus clicks to train beasts
ARMS_RACE_BEAST_TRAINING_ENABLED = True        # Enable/disable beast training automation
ARMS_RACE_BEAST_TRAINING_LAST_MINUTES = 60     # Trigger in last N minutes of Mystic Beast
ARMS_RACE_BEAST_TRAINING_STAMINA_THRESHOLD = 20  # Minimum stamina required
ARMS_RACE_BEAST_TRAINING_COOLDOWN = 90         # Seconds between rallies

# Enhance Hero (during Enhance Hero event)
# Triggers hero_upgrade_arms_race_flow to upgrade heroes
ARMS_RACE_ENHANCE_HERO_ENABLED = True          # Enable/disable hero enhancement automation
ARMS_RACE_ENHANCE_HERO_LAST_MINUTES = 20       # Trigger in last N minutes of Enhance Hero

# Cooldowns (seconds)
AFK_REWARDS_COOLDOWN = 3600        # 1 hour between AFK rewards checks
UNION_GIFTS_COOLDOWN = 3600        # 1 hour between union gift claims
UNION_GIFTS_IDLE_THRESHOLD = 1200  # 20 minutes idle required for union gifts

# Recovery
UNKNOWN_STATE_TIMEOUT = 60         # Seconds in UNKNOWN state before recovery

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
