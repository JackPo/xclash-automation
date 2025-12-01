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

# API Keys (required - set in config_local.py or environment)
GOOGLE_API_KEY = None
ANTHROPIC_API_KEY = None

# Daemon timing
DAEMON_INTERVAL = 3.0              # Check interval (seconds)
IDLE_THRESHOLD = 300               # 5 minutes before idle triggers activate
IDLE_CHECK_INTERVAL = 300          # 5 minutes between idle recovery checks

# Elite Zombie rally
ELITE_ZOMBIE_STAMINA_THRESHOLD = 118   # Minimum stamina to trigger rally
ELITE_ZOMBIE_CONSECUTIVE_REQUIRED = 3  # Consecutive valid OCR reads required

# Cooldowns (seconds)
AFK_REWARDS_COOLDOWN = 3600        # 1 hour between AFK rewards checks
UNION_GIFTS_COOLDOWN = 3600        # 1 hour between union gift claims
UNION_GIFTS_IDLE_THRESHOLD = 1200  # 20 minutes idle required for union gifts

# Recovery
UNKNOWN_STATE_TIMEOUT = 60         # Seconds in UNKNOWN state before recovery

# Screen regions (4K resolution: 3840x2160)
STAMINA_REGION = (69, 203, 96, 60)  # x, y, w, h for stamina OCR

# =============================================================================
# LOAD LOCAL OVERRIDES
# =============================================================================

# Try to load from config_local.py first (for local development)
try:
    from config_local import *
    print("Loaded config from config_local.py")
except ImportError:
    # Fall back to environment variables for API keys
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

    if not GOOGLE_API_KEY:
        print("WARNING: GOOGLE_API_KEY not set. Copy config_local.py.example to config_local.py and add your key.")
