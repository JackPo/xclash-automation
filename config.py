"""
Configuration loader - loads API keys from config.local.py or environment variables.

Usage:
    from config import GOOGLE_API_KEY

Setup:
    1. Copy config.local.py.example to config.local.py
    2. Fill in your API keys in config.local.py
    3. config.local.py is gitignored so your keys stay safe
"""
import os

# Try to load from config.local.py first (for local development)
try:
    from config_local import *
    print("Loaded config from config_local.py")
except ImportError:
    # Fall back to environment variables
    GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY')

    if not GOOGLE_API_KEY:
        print("WARNING: GOOGLE_API_KEY not set. Copy config_local.py.example to config_local.py and add your key.")
