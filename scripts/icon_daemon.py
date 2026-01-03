#!/usr/bin/env python3
"""
Icon Auto-Clicker Daemon

Runs continuously, checking for clickable icons every 3 seconds.
When an icon is detected, kicks off a flow handler in a separate thread.

Currently detects:
- Handshake icon (Union button)
- Treasure map icon (bouncing scroll on barracks)
- Corn harvest bubble
- Gold coin bubble
- Harvest box icon
- Iron bar bubble
- Gem bubble
- Cabbage bubble
- Equipment enhancement bubble (crossed swords)

Arms Race event tracking:
- Beast Training: During Mystic Beast Training last hour, if stamina >= 20 (3 consecutive reads),
  triggers elite_zombie_flow with 0 plus clicks. 90s cooldown between rallies.
- Enhance Hero: During Enhance Hero last 10 minutes, triggers hero_upgrade_arms_race_flow.
  Flow checks real-time progress from Events panel - skips if chest3 (12000) already reached.
  NO idle requirement - the progress check is quick and non-disruptive.

Idle recovery (every 5 min when idle 5+ min):
- If back button visible (chat window) → click back to exit
- If no world button AND no back button (menu gone) → click back location to recover
- If not in town view → switch to town

Press Ctrl+C to stop.

Usage:
    python icon_daemon.py [--interval SECONDS] [--debug]
"""

import sys
import time
import argparse
import threading
import logging
import importlib
from pathlib import Path
from datetime import datetime
import pytz

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.adb_helper import ADBHelper
from utils.ocr_client import OCRClient, ensure_ocr_server, start_ocr_server, kill_ocr_servers, SERVER_HOST, SERVER_PORT
from utils.handshake_icon_matcher import HandshakeIconMatcher
from utils.treasure_map_matcher import TreasureMapMatcher
from utils.corn_harvest_matcher import CornHarvestMatcher
from utils.gold_coin_matcher import GoldCoinMatcher
from utils.harvest_box_matcher import HarvestBoxMatcher
from utils.iron_bar_matcher import IronBarMatcher
from utils.gem_matcher import GemMatcher
from utils.cabbage_matcher import CabbageMatcher
from utils.equipment_enhancement_matcher import EquipmentEnhancementMatcher
from utils.hospital_state_matcher import HospitalStateMatcher, HospitalState
from utils.back_button_matcher import BackButtonMatcher
from utils.afk_rewards_matcher import AfkRewardsMatcher
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.idle_detector import get_idle_seconds, format_idle_time
from utils.user_idle_tracker import get_user_idle_seconds, mark_daemon_action
from utils.stamina_reader import StaminaReader
from utils.view_state_detector import detect_view, go_to_town, go_to_world, ViewState
from utils.dog_house_matcher import DogHouseMatcher
from utils.return_to_base_view import return_to_base_view, _get_current_resolution, _run_setup_bluestacks
from utils.barracks_state_matcher import BarracksStateMatcher, format_barracks_states, format_barracks_states_detailed
from utils.stamina_red_dot_detector import has_stamina_red_dot
from utils.rally_march_button_matcher import RallyMarchButtonMatcher
from utils.disconnection_dialog_matcher import is_disconnection_dialog_visible, get_confirm_button_position
from utils.debug_screenshot import get_daemon_debug

# Disconnection dialog wait time (user playing on mobile)
DISCONNECTION_WAIT_SECONDS = 300  # 5 minutes

from flows import handshake_flow, treasure_map_flow, corn_harvest_flow, gold_coin_flow, harvest_box_flow, iron_bar_flow, gem_flow, cabbage_flow, equipment_enhancement_flow, elite_zombie_flow, afk_rewards_flow, union_gifts_flow, union_technology_flow, hero_upgrade_arms_race_flow, stamina_claim_flow, stamina_use_flow, soldier_training_flow, soldier_upgrade_flow, rally_join_flow, healing_flow, bag_flow, gift_box_flow, run_hour_mark_phase, run_last_6_minutes_phase, check_progress_quick, marshall_speedup_all_flow
from flows.tavern_quest_flow import tavern_quest_claim_flow, run_tavern_quest_flow
from flows.faction_trials_flow import faction_trials_flow
from flows.zombie_attack_flow import zombie_attack_flow
from utils.arms_race import get_arms_race_status, get_time_until_beast_training
from utils.arms_race_data_collector import (
    load_persisted_into_memory,
    should_collect_event_data,
    collect_and_save_current_event,
)
from utils.arms_race_panel_helper import check_beast_training_progress, check_arms_race_progress
from utils.scheduler import get_scheduler

# Import configurable parameters
from config import (
    IDLE_THRESHOLD,
    IDLE_CHECK_INTERVAL,
    ELITE_ZOMBIE_STAMINA_THRESHOLD,
    ELITE_ZOMBIE_CONSECUTIVE_REQUIRED,
    AFK_REWARDS_COOLDOWN,
    UNION_GIFTS_COOLDOWN,
    UNION_TECHNOLOGY_COOLDOWN,
    BAG_FLOW_COOLDOWN,
    GIFT_BOX_COOLDOWN,
    UNKNOWN_STATE_TIMEOUT,
    UNKNOWN_LOOP_TIMEOUT,
    STAMINA_REGION,
    # Arms Race automation settings
    ARMS_RACE_BEAST_TRAINING_ENABLED,
    ARMS_RACE_BEAST_TRAINING_LAST_MINUTES,
    ARMS_RACE_BEAST_TRAINING_STAMINA_THRESHOLD,
    ARMS_RACE_BEAST_TRAINING_COOLDOWN,
    ARMS_RACE_ENHANCE_HERO_ENABLED,
    ARMS_RACE_ENHANCE_HERO_LAST_MINUTES,
    STAMINA_CLAIM_BUTTON,
    ARMS_RACE_STAMINA_CLAIM_THRESHOLD,
    ARMS_RACE_BEAST_TRAINING_USE_ENABLED,
    ARMS_RACE_BEAST_TRAINING_USE_MAX,
    ARMS_RACE_BEAST_TRAINING_USE_COOLDOWN,
    ARMS_RACE_BEAST_TRAINING_USE_LAST_MINUTES,
    ARMS_RACE_BEAST_TRAINING_MAX_RALLIES,
    ARMS_RACE_BEAST_TRAINING_USE_STAMINA_THRESHOLD,
    ZOMBIE_MODE_CONFIG,
    ARMS_RACE_SOLDIER_TRAINING_ENABLED,
    ARMS_RACE_BEAST_TRAINING_PRE_EVENT_MINUTES,
    # VS Event overrides
    VS_SOLDIER_PROMOTION_DAYS,
    # Rally joining
    RALLY_JOIN_ENABLED,
    RALLY_MARCH_BUTTON_COOLDOWN,
    UNION_BOSS_MODE_DURATION,
    UNION_BOSS_RALLY_COOLDOWN,
    # Hospital state detection
    HOSPITAL_CONSECUTIVE_REQUIRED,
    # Resolution check
    RESOLUTION_CHECK_INTERVAL,
    EXPECTED_RESOLUTION,
    # Tavern quest scan
    TAVERN_SCAN_COOLDOWN,
    TAVERN_QUEST_START_HOUR,
    TAVERN_QUEST_START_MINUTE,
    # WebSocket API server
    DAEMON_SERVER_PORT,
    DAEMON_SERVER_ENABLED,
)

from dataclasses import dataclass
from typing import Callable, Optional, List
from enum import IntEnum


class FlowPriority(IntEnum):
    """
    Flow priority levels. Higher = more urgent, runs first.

    When multiple flows are triggered in the same iteration,
    the highest priority one wins.
    """
    LOW = 10           # Harvest bubbles (corn, gold, iron, gem, cabbage, equip)
    NORMAL = 20        # Regular flows (AFK rewards, union gifts/tech, bag)
    HIGH = 30          # Important flows (hospital, barracks training)
    URGENT = 40        # Time-sensitive (elite zombie rally, treasure map)
    CRITICAL = 50      # Arms Race event flows (beast training, enhance hero)


@dataclass
class FlowCandidate:
    """
    A flow that has been detected as triggerable.

    Collected during detection phase, executed in execution phase.
    """
    name: str
    flow_func: Callable
    priority: FlowPriority
    critical: bool = False
    reason: str = ""  # Why this flow was triggered (for logging)
    record_to_scheduler: bool = False  # If True, records cooldown after execution


class IconDaemon:
    """
    Daemon that detects icons and triggers non-blocking flows.
    """

    def __init__(self, interval: float = None, debug: bool = False):
        from config import DAEMON_INTERVAL
        self.interval = interval if interval is not None else DAEMON_INTERVAL
        self.debug = debug
        self.adb = None
        self.windows_helper = None

        # Stamina OCR (via OCR server)
        self.ocr_client = None
        self.STAMINA_REGION = STAMINA_REGION  # From config

        # OCR server health check - verify every 5 minutes, restart if down
        self.OCR_HEALTH_CHECK_INTERVAL = 300  # 5 minutes
        self.last_ocr_health_check = 0
        self.ocr_consecutive_failures = 0  # Track consecutive OCR failures

        # Matchers
        self.handshake_matcher = None
        self.treasure_matcher = None
        self.corn_matcher = None
        self.gold_matcher = None
        self.harvest_box_matcher = None
        self.iron_matcher = None
        self.gem_matcher = None
        self.cabbage_matcher = None
        self.equipment_enhancement_matcher = None
        self.hospital_matcher = None  # Unified hospital state matcher
        self.back_button_matcher = None
        self.dog_house_matcher = None
        self.afk_rewards_matcher = None
        self.barracks_matcher = None

        # Track active flows to prevent re-triggering
        self.active_flows = set()
        self.flow_lock = threading.Lock()

        # Critical flow protection - blocks all other daemon actions
        self.critical_flow_active = False
        self.critical_flow_name = None

        # Idle town view switching (values from config)
        self.last_idle_check_time = 0
        self.IDLE_THRESHOLD = IDLE_THRESHOLD
        self.IDLE_CHECK_INTERVAL = IDLE_CHECK_INTERVAL

        # User idle tracker removed - using raw Windows idle instead

        # Elite zombie rally - stamina threshold (from config)
        self.ELITE_ZOMBIE_STAMINA_THRESHOLD = ELITE_ZOMBIE_STAMINA_THRESHOLD

        # AFK rewards cooldown - once per hour (from config)
        self.last_afk_rewards_time = 0
        self.AFK_REWARDS_COOLDOWN = AFK_REWARDS_COOLDOWN

        # Union gifts cooldown - once per hour (from config)
        self.last_union_gifts_time = 0
        self.UNION_GIFTS_COOLDOWN = UNION_GIFTS_COOLDOWN

        # Bag flow cooldown - once per hour, requires 5 min idle
        self.last_bag_flow_time = 0
        self.BAG_FLOW_COOLDOWN = BAG_FLOW_COOLDOWN

        # Gift box flow cooldown - once per hour, requires WORLD view + 5 min idle
        self.last_gift_box_time = 0
        self.GIFT_BOX_COOLDOWN = GIFT_BOX_COOLDOWN

        # Tavern quest cooldown - every 30 minutes, requires 5 min idle + TOWN view
        self.TAVERN_QUEST_COOLDOWN = TAVERN_SCAN_COOLDOWN

        # VS Day 7 chest surprise - trigger bag flow at 10, 5, 1 min remaining
        self.VS_CHEST_CHECKPOINTS = [10, 5, 1]  # Minutes before day ends
        self.vs_chest_triggered = set()  # Track which checkpoints we've hit
        self.vs_chest_last_day = None  # Reset tracking when day changes

        # Union technology cooldown - once per hour
        self.last_union_technology_time = 0
        self.UNION_TECHNOLOGY_COOLDOWN = UNION_TECHNOLOGY_COOLDOWN

        # Return-to-town tracking - every 5 idle iterations, go back to TOWN
        self.idle_iteration_count = 0
        self.IDLE_RETURN_TO_TOWN_INTERVAL = 5  # Every 5 iterations when idle

        # Initialize unified scheduler with config overrides
        # All flows now use IDLE_THRESHOLD from config (default 5 min)
        self.scheduler = get_scheduler(config_overrides={
            "afk_rewards": {"cooldown": AFK_REWARDS_COOLDOWN, "idle_required": IDLE_THRESHOLD},
            "union_gifts": {"cooldown": UNION_GIFTS_COOLDOWN, "idle_required": IDLE_THRESHOLD},
            "union_technology": {"cooldown": UNION_TECHNOLOGY_COOLDOWN, "idle_required": IDLE_THRESHOLD},
            "bag_flow": {"cooldown": BAG_FLOW_COOLDOWN, "idle_required": IDLE_THRESHOLD},
            "gift_box": {"cooldown": GIFT_BOX_COOLDOWN, "idle_required": IDLE_THRESHOLD},
            "tavern_quest": {"cooldown": TAVERN_SCAN_COOLDOWN, "idle_required": IDLE_THRESHOLD},
        })

        # Unified stamina validation - ONE system for all stamina-based triggers
        # Uses StaminaReader for MODE-based confirmation with consistency check
        self.stamina_reader = StaminaReader()

        # Pacific timezone for logging
        self.pacific_tz = pytz.timezone('America/Los_Angeles')

        # UNKNOWN state recovery tracking (from config)
        self.unknown_state_start = None  # When we first entered UNKNOWN state
        self.unknown_state_left_time = None  # When we left UNKNOWN (for hysteresis)
        self.UNKNOWN_STATE_TIMEOUT = UNKNOWN_STATE_TIMEOUT
        self.UNKNOWN_HYSTERESIS = 10  # Seconds out of UNKNOWN before resetting timer

        # UNKNOWN recovery loop detection - force restart if recovery keeps cycling
        self.unknown_recovery_count = 0  # How many times recovery ran
        self.unknown_first_recovery_time = None  # When first recovery started
        self.UNKNOWN_LOOP_TIMEOUT = UNKNOWN_LOOP_TIMEOUT  # 8 min from config

        # Disconnection dialog tracking (user playing on mobile)
        self.disconnection_dialog_detected_time = None  # When we first saw the dialog

        # Resolution check (proactive, not just on recovery)
        self.RESOLUTION_CHECK_INTERVAL = RESOLUTION_CHECK_INTERVAL
        self.EXPECTED_RESOLUTION = EXPECTED_RESOLUTION

        # Scheduled triggers (old mechanism - kept for future use)
        self.scheduled_triggers = []  # Empty - no scheduled triggers
        self.continuous_idle_start = None  # Track when continuous idle began

        # Tavern quest scheduled trigger at 10:30 PM Pacific
        # Triggers immediately when time is reached, ignoring cooldown/idle
        self.tavern_scheduled_triggered_date = None  # Track which date we've triggered

        # Arms Race event tracking (values from config)
        # Beast Training: Mystic Beast last N minutes, stamina threshold, cooldown between rallies
        self.ARMS_RACE_BEAST_TRAINING_ENABLED = ARMS_RACE_BEAST_TRAINING_ENABLED
        self.ARMS_RACE_BEAST_TRAINING_LAST_MINUTES = ARMS_RACE_BEAST_TRAINING_LAST_MINUTES
        self.BEAST_TRAINING_STAMINA_THRESHOLD = ARMS_RACE_BEAST_TRAINING_STAMINA_THRESHOLD
        self.BEAST_TRAINING_RALLY_COOLDOWN = ARMS_RACE_BEAST_TRAINING_COOLDOWN
        self.beast_training_last_rally = 0
        self.beast_training_rally_count = 0  # Track total rallies in current Beast Training block
        self.beast_training_current_block = None  # Track which block we're in
        self.STAMINA_CLAIM_THRESHOLD = ARMS_RACE_STAMINA_CLAIM_THRESHOLD  # Claim when stamina < this

        # Use Button tracking (for stamina recovery items during Beast Training)
        self.BEAST_TRAINING_USE_ENABLED = ARMS_RACE_BEAST_TRAINING_USE_ENABLED
        self.BEAST_TRAINING_USE_MAX = ARMS_RACE_BEAST_TRAINING_USE_MAX  # Max 4 Use clicks per block
        self.BEAST_TRAINING_USE_COOLDOWN = ARMS_RACE_BEAST_TRAINING_USE_COOLDOWN  # 3 min between uses
        self.BEAST_TRAINING_MAX_RALLIES = ARMS_RACE_BEAST_TRAINING_MAX_RALLIES  # Don't use if rallies >= 15
        self.BEAST_TRAINING_USE_STAMINA_THRESHOLD = ARMS_RACE_BEAST_TRAINING_USE_STAMINA_THRESHOLD  # Use when < 20
        self.BEAST_TRAINING_USE_LAST_MINUTES = ARMS_RACE_BEAST_TRAINING_USE_LAST_MINUTES  # 3rd+ uses only in last N min
        self.beast_training_use_count = 0  # Track Use button clicks per block
        self.beast_training_last_use_time = 0  # Track cooldown between uses
        self.beast_training_claim_attempted = False  # Track if we tried to claim this iteration

        # Smart Beast Training flow phases use scheduler-based tracking (beast_training_hour_mark_block, beast_training_last_6_block)
        self.beast_training_last_progress_check = 0  # Timestamp of last progress check

        # Enhance Hero: last N minutes of Enhance Hero, runs once per block
        self.ARMS_RACE_ENHANCE_HERO_ENABLED = ARMS_RACE_ENHANCE_HERO_ENABLED
        self.ENHANCE_HERO_LAST_MINUTES = ARMS_RACE_ENHANCE_HERO_LAST_MINUTES
        self.enhance_hero_last_block_start = None  # Track which block we triggered for

        # Generic Arms Race progress check: log points for ALL events in last 10 min
        self.ARMS_RACE_PROGRESS_CHECK_MINUTES = 10  # Check in last N minutes
        self.arms_race_progress_check_block = None  # Track which block we checked

        # Soldier Training: when idle 5+ min, any barrack PENDING during Soldier Training event
        # CONTINUOUSLY checks and upgrades PENDING barracks (no block limitation)
        self.ARMS_RACE_SOLDIER_TRAINING_ENABLED = ARMS_RACE_SOLDIER_TRAINING_ENABLED

        # Pre-Beast Training: claim stamina + block elite rallies N minutes before event
        self.BEAST_TRAINING_PRE_EVENT_MINUTES = ARMS_RACE_BEAST_TRAINING_PRE_EVENT_MINUTES
        self.beast_training_pre_claim_block = None  # Track which upcoming block we've pre-claimed for

        # VS Event overrides - soldier promotions all day on specific days
        self.VS_SOLDIER_PROMOTION_DAYS = VS_SOLDIER_PROMOTION_DAYS

        # Barracks state validation - require 10 readings with 60%+ being a specific state
        # Allows UNKNOWN (?) readings as long as 60%+ are a consistent letter (R, P, or T)
        # Example: PPPPPP???? (6P + 4?) = 60% P = PASS
        # Example: PPPPP????? (5P + 5?) = 50% P = FAIL
        # Example: PPPPRRR??? (mixed P and R) = FAIL
        self.barracks_state_history = [[], [], [], []]  # Per-barrack state history
        self.BARRACKS_CONSECUTIVE_REQUIRED = 10
        self.BARRACKS_MIN_LETTER_RATIO = 0.6  # 60% must be a specific letter

        # Hospital state history - same pattern as barracks
        self.hospital_state_history = []  # List of HospitalState values
        self.HOSPITAL_CONSECUTIVE_REQUIRED = HOSPITAL_CONSECUTIVE_REQUIRED

        # Setup logging
        self.log_dir = Path('logs')
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = self.log_dir / f"daemon_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        # Track current log file (Windows doesn't support symlinks without admin)
        self.current_log_link = self.log_dir / 'current_daemon.log'

        # Configure logging with dual file output
        log_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
                logging.FileHandler(self.current_log_link),  # Also write to current_daemon.log
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger('IconDaemon')

        # WebSocket API server for external control
        self.command_server = None
        self.paused = False  # Can be toggled via API

        # State persistence tracking
        self.state_save_interval = 60  # Save state every N iterations (~3 min at 3s interval)

    def _verify_templates(self):
        """
        Verify all required templates exist before startup.
        Raises FileNotFoundError if any template is missing.
        """
        print("Verifying templates...")
        template_dir = Path('templates/ground_truth')

        # All templates required by matchers and view_state_detector
        required_templates = [
            # Icon matcher templates
            'handshake_icon_4k.png',
            'treasure_map_4k.png',
            'corn_harvest_bubble_4k.png',
            'gold_coin_tight_4k.png',
            'harvest_box_4k.png',
            'iron_bar_tight_4k.png',
            'gem_tight_4k.png',
            'cabbage_tight_4k.png',
            'sword_tight_4k.png',  # Equipment enhancement
            'dog_house_4k.png',
            'chest_timer_4k.png',  # AFK rewards
            # Back button templates (multiple variants)
            'back_button_4k.png',
            'back_button_light_4k.png',
            'back_button_union_4k.png',
            'back_button_union_mask_4k.png',
            # Shaded button templates (popup detection)
            'world_button_shaded_4k.png',
            'world_button_shaded_dark_4k.png',
            # View state detector templates
            'world_button_4k.png',
            'town_button_4k.png',
            'town_button_zoomed_out_4k.png',
            # Barracks state templates
            'stopwatch_barrack_4k.png',
            'white_soldier_barrack_4k.png',
            'yellow_soldier_barrack_4k.png',
            'yellow_soldier_barrack_v2_4k.png',
            'yellow_soldier_barrack_v3_4k.png',
            'yellow_soldier_barrack_v4_4k.png',
            'yellow_soldier_barrack_v5_4k.png',
            'yellow_soldier_barrack_v6_4k.png',
        ]

        missing = []
        for template in required_templates:
            path = template_dir / template
            if not path.exists():
                missing.append(str(path))

        if missing:
            print(f"  ERROR: Missing {len(missing)} templates:")
            for m in missing:
                print(f"    - {m}")
            raise FileNotFoundError(f"Missing {len(missing)} required templates. See list above.")

        print(f"  OK - All {len(required_templates)} templates verified")

    def initialize(self):
        """Initialize all components."""
        self.logger.info("Initializing icon daemon...")
        self.logger.info(f"Log file: {self.log_file}")

        # Verify templates exist before loading matchers
        self._verify_templates()

        # Ensure OCR server is running (auto-start if not)
        print("Checking OCR server...")
        if not ensure_ocr_server(auto_start=True):
            raise RuntimeError("Could not start OCR server!")
        print("  OCR server is running")

        # ADB - with idle tracking callback to filter daemon actions from user idle
        self.adb = ADBHelper(on_action=mark_daemon_action)
        print(f"  Connected to device: {self.adb.device}")

        # Windows screenshot helper
        self.windows_helper = WindowsScreenshotHelper()
        print("  Windows screenshot helper initialized")

        # Stamina OCR (via OCR server)
        self.ocr_client = OCRClient()
        print("  OCR client initialized (uses OCR server)")

        # Load persisted Arms Race event data (chest thresholds)
        load_persisted_into_memory()
        print("  Arms Race event data loaded")

        # Matchers
        debug_dir = Path('templates/debug')

        # Matchers use their own default thresholds - edit thresholds in the matcher files
        self.handshake_matcher = HandshakeIconMatcher(debug_dir=debug_dir)
        print(f"  Handshake matcher: {self.handshake_matcher.TEMPLATE_NAME} (threshold={self.handshake_matcher.threshold})")

        self.treasure_matcher = TreasureMapMatcher(debug_dir=debug_dir)
        print(f"  Treasure map matcher: {self.treasure_matcher.TEMPLATE_NAME} (threshold={self.treasure_matcher.threshold})")

        self.corn_matcher = CornHarvestMatcher(debug_dir=debug_dir)
        print(f"  Corn harvest matcher: {self.corn_matcher.TEMPLATE_NAME} (threshold={self.corn_matcher.threshold})")

        self.gold_matcher = GoldCoinMatcher(debug_dir=debug_dir)
        print(f"  Gold coin matcher: {self.gold_matcher.TEMPLATE_NAME} (threshold={self.gold_matcher.threshold})")

        self.harvest_box_matcher = HarvestBoxMatcher(debug_dir=debug_dir)
        print(f"  Harvest box matcher: {self.harvest_box_matcher.TEMPLATE_NAME} (threshold={self.harvest_box_matcher.threshold})")

        self.iron_matcher = IronBarMatcher(debug_dir=debug_dir)
        print(f"  Iron bar matcher: {self.iron_matcher.TEMPLATE_NAME} (threshold={self.iron_matcher.threshold})")

        self.gem_matcher = GemMatcher(debug_dir=debug_dir)
        print(f"  Gem matcher: {self.gem_matcher.TEMPLATE_NAME} (threshold={self.gem_matcher.threshold})")

        self.cabbage_matcher = CabbageMatcher(debug_dir=debug_dir)
        print(f"  Cabbage matcher: {self.cabbage_matcher.TEMPLATE_NAME} (threshold={self.cabbage_matcher.threshold})")

        self.equipment_enhancement_matcher = EquipmentEnhancementMatcher(debug_dir=debug_dir)
        print(f"  Equipment enhancement matcher: {self.equipment_enhancement_matcher.TEMPLATE_NAME} (threshold={self.equipment_enhancement_matcher.threshold})")

        self.hospital_matcher = HospitalStateMatcher()
        print(f"  Hospital state matcher: threshold={self.hospital_matcher.threshold}, consecutive={self.HOSPITAL_CONSECUTIVE_REQUIRED}")

        self.back_button_matcher = BackButtonMatcher(debug_dir=debug_dir)
        print(f"  Back button matcher: {self.back_button_matcher.TEMPLATES} (threshold={self.back_button_matcher.threshold})")

        self.dog_house_matcher = DogHouseMatcher(debug_dir=debug_dir)
        print(f"  Dog house matcher: {self.dog_house_matcher.TEMPLATE_NAME} (threshold={self.dog_house_matcher.threshold})")

        self.afk_rewards_matcher = AfkRewardsMatcher(debug_dir=debug_dir)
        print(f"  AFK rewards matcher: {self.afk_rewards_matcher.TEMPLATE_NAME} (threshold={self.afk_rewards_matcher.threshold})")

        self.barracks_matcher = BarracksStateMatcher()
        print(f"  Barracks state matcher: 4 positions, threshold={self.barracks_matcher.MATCH_THRESHOLD if hasattr(self.barracks_matcher, 'MATCH_THRESHOLD') else 0.06}")

        self.rally_march_matcher = RallyMarchButtonMatcher()
        print(f"  Rally march button matcher: rally_march_button_small_4k.png (threshold={self.rally_march_matcher.threshold})")

        # Rally joining tracking
        self.last_rally_march_click = 0  # Timestamp of last march button click
        self.union_boss_mode_until = 0   # Timestamp when Union Boss mode expires (faster rally joining)

        # Startup recovery - return_to_base_view handles EVERYTHING:
        # - Checks if app is running, starts it if not
        # - Runs setup_bluestacks.py
        # - Gets to TOWN/WORLD via back button clicking
        # - Restarts and retries if stuck
        self.logger.info("STARTUP: Running recovery to ensure ready state...")
        return_to_base_view(self.adb, self.windows_helper, debug=True)

        # Log scheduler status on startup
        self.logger.info("STARTUP: Scheduler status:")
        self.scheduler.log_status()

        # Check for missed flows and log them
        missed = self.scheduler.get_missed_flows()
        if missed:
            self.logger.info(f"STARTUP: Missed flows (will catch up): {missed}")

        # Load runtime state from persistent storage
        self._load_runtime_state()

        # Start WebSocket API server (for external control via daemon_cli.py)
        if DAEMON_SERVER_ENABLED:
            try:
                from utils.daemon_server import DaemonWebSocketServer
                self.command_server = DaemonWebSocketServer(self, port=DAEMON_SERVER_PORT)
                self.command_server.start()
                self.logger.info(f"STARTUP: WebSocket API server started on ws://localhost:{DAEMON_SERVER_PORT}")
            except ImportError as e:
                self.logger.warning(f"STARTUP: WebSocket server disabled (websockets not installed): {e}")
            except Exception as e:
                self.logger.error(f"STARTUP: WebSocket server failed to start: {e}")
        else:
            self.logger.info("STARTUP: WebSocket API server disabled by config")

        self.logger.info("STARTUP: Ready")

    def _can_run_flow(self) -> bool:
        """
        Check if a flow can be started (no other flow is active).

        Use this BEFORE logging "triggering" messages and clicking UI elements
        to prevent flows from stepping on each other.

        Returns:
            True if no flow is active, False otherwise
        """
        with self.flow_lock:
            if self.active_flows:
                return False
            if self.critical_flow_active:
                return False
        return True

    def _execute_best_flow(self, candidates: List[FlowCandidate], iteration: int) -> Optional[str]:
        """
        From a list of flow candidates, select and execute the highest priority one.

        This is the SINGLE point of execution for flows detected in an iteration.
        Only ONE flow runs per iteration, preventing flows from stepping on each other.

        Args:
            candidates: List of FlowCandidate objects detected this iteration
            iteration: Current iteration number (for logging)

        Returns:
            Name of the flow that was started, or None if no flow could run
        """
        if not candidates:
            return None

        # Check if we can run any flow
        with self.flow_lock:
            if self.active_flows:
                self.logger.debug(f"[{iteration}] FLOW BLOCKED: {len(candidates)} candidates, but {self.active_flows} already running")
                return None
            if self.critical_flow_active:
                self.logger.debug(f"[{iteration}] FLOW BLOCKED: {len(candidates)} candidates, but critical flow {self.critical_flow_name} active")
                return None

        # Sort by priority (highest first)
        candidates.sort(key=lambda c: c.priority, reverse=True)
        best = candidates[0]

        # Log what we're doing
        if len(candidates) > 1:
            skipped = ", ".join([f"{c.name}({c.priority.name})" for c in candidates[1:]])
            self.logger.info(f"[{iteration}] FLOW SELECT: {best.name} (priority={best.priority.name}) - {best.reason}")
            self.logger.debug(f"[{iteration}] FLOW SKIPPED: {skipped}")
        else:
            self.logger.info(f"[{iteration}] FLOW: {best.name} - {best.reason}")

        # Execute the best flow
        if self._run_flow(best.name, best.flow_func, critical=best.critical):
            # Record cooldown if needed
            if best.record_to_scheduler:
                self.scheduler.record_flow_run(best.name)
            return best.name
        return None

    def _run_flow(self, flow_name: str, flow_func, critical: bool = False):
        """
        Run a flow in a thread-safe way.

        Args:
            flow_name: Identifier for the flow
            flow_func: Function to execute (takes adb as argument)
            critical: If True, blocks all other daemon actions during execution
        """
        def wrapper():
            try:
                # Mark as critical if requested
                if critical:
                    with self.flow_lock:
                        self.critical_flow_active = True
                        self.critical_flow_name = flow_name
                    self.logger.info(f"CRITICAL FLOW START: {flow_name}")
                else:
                    self.logger.info(f"FLOW START: {flow_name}")

                # Mark daemon action before flow clicks (filters from idle tracking)
                mark_daemon_action()
                flow_func(self.adb)

                if critical:
                    self.logger.info(f"CRITICAL FLOW END: {flow_name}")
                else:
                    self.logger.info(f"FLOW END: {flow_name}")
            except Exception as e:
                self.logger.error(f"FLOW ERROR: {flow_name} - {e}")
            finally:
                with self.flow_lock:
                    self.active_flows.discard(flow_name)
                    if critical and self.critical_flow_name == flow_name:
                        self.critical_flow_active = False
                        self.critical_flow_name = None

        with self.flow_lock:
            if flow_name in self.active_flows:
                self.logger.debug(f"SKIP: {flow_name} already running")
                return False

            # Block non-critical flows if a critical flow is active
            if not critical and self.critical_flow_active:
                self.logger.debug(f"SKIP: {flow_name} blocked by critical flow {self.critical_flow_name}")
                return False

            # Block ALL flows if ANY flow is active (prevent parallel UI interference)
            if self.active_flows:
                self.logger.debug(f"SKIP: {flow_name} blocked - another flow is active: {self.active_flows}")
                return False

            self.active_flows.add(flow_name)

        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()
        return True

    def _check_ocr_server_health(self):
        """Check if OCR server is healthy, restart if necessary.

        Called periodically and on consecutive OCR failures.
        Returns True if server is healthy (or was restarted), False otherwise.
        """
        if not OCRClient.check_server(force=True):
            self.logger.warning("OCR server health check FAILED - killing existing servers and restarting...")
            # Kill existing servers first to prevent accumulation
            # (also done inside start_ocr_server, but log explicitly here)
            killed = kill_ocr_servers()
            if killed > 0:
                self.logger.info(f"Killed {killed} stale OCR server process(es)")
            # Reset auto-start flag to allow restart
            OCRClient._auto_start_attempted = False
            if start_ocr_server():
                self.logger.info("OCR server restarted successfully")
                self.ocr_client = OCRClient()  # Recreate client
                return True
            else:
                self.logger.error("OCR server restart FAILED!")
                return False
        return True

    def _switch_to_town(self):
        """Switch to town view using view_state_detector."""
        success = go_to_town(self.adb, debug=False)
        if success:
            self.logger.info("IDLE SWITCH: Successfully switched to TOWN view")
        else:
            self.logger.warning("IDLE SWITCH: Failed to switch to TOWN view")

    def _is_xclash_in_foreground(self) -> bool:
        """Check if xclash (com.xman.na.gp) is the foreground app."""
        import subprocess
        try:
            result = subprocess.run(
                [self.adb.ADB_PATH, '-s', self.adb.device, 'shell',
                 'dumpsys window | grep mFocusedApp'],
                capture_output=True, text=True, timeout=5
            )
            return 'com.xman.na.gp' in result.stdout
        except Exception as e:
            self.logger.error(f"Failed to check foreground app: {e}")
            return False

    def _force_app_restart(self):
        """Force stop and restart xclash app when stuck in UNKNOWN loop."""
        import subprocess
        from pathlib import Path

        self.logger.info("FORCING APP RESTART due to UNKNOWN recovery loop...")

        # Force stop the app
        try:
            subprocess.run(
                [self.adb.ADB_PATH, '-s', self.adb.device, 'shell',
                 'am force-stop com.xman.na.gp'],
                capture_output=True, timeout=10
            )
            self.logger.info("App force-stopped")
        except Exception as e:
            self.logger.error(f"Failed to force stop app: {e}")

        time.sleep(2)

        # Start the app
        try:
            subprocess.run(
                [self.adb.ADB_PATH, '-s', self.adb.device, 'shell',
                 'am start -n com.xman.na.gp/com.q1.ext.Q1UnityActivity'],
                capture_output=True, timeout=10
            )
            self.logger.info("App started, waiting 30s for load...")
        except Exception as e:
            self.logger.error(f"Failed to start app: {e}")

        time.sleep(30)  # Wait for app to load

        # Run setup to ensure resolution
        try:
            subprocess.run(
                ['python', 'scripts/setup_bluestacks.py'],
                capture_output=True, timeout=30,
                cwd=str(Path(__file__).parent.parent)
            )
            self.logger.info("setup_bluestacks.py completed")
        except Exception as e:
            self.logger.error(f"Failed to run setup: {e}")

    def _check_resolution(self, iteration: int) -> bool:
        """
        Check resolution by comparing world button against 4K vs low-res templates.

        Checks every RESOLUTION_CHECK_INTERVAL iterations (no idle requirement).
        If low-res template matches better, resolution drifted - runs setup_bluestacks.py.

        Returns True if resolution is OK, False if fix failed.
        """
        # Only check every N iterations (iteration=0 always checks for startup)
        if iteration > 0 and iteration % self.RESOLUTION_CHECK_INTERVAL != 0:
            return True  # Not time to check yet

        try:
            import cv2

            # Take screenshot and extract world button region
            frame = self.windows_helper.get_screenshot_cv2()
            x, y, w, h = 3600, 1920, 240, 240
            current_roi = frame[y:y+h, x:x+w]

            # Load both templates
            template_4k = cv2.imread('templates/ground_truth/world_button_4k.png')
            template_lowres = cv2.imread('templates/ground_truth/world_button_lowres_4k.png')

            if template_4k is None or template_lowres is None:
                self.logger.warning(f"[{iteration}] Resolution check: missing templates, falling back to wm size")
                return self._check_resolution_fallback(iteration)

            # Compare against both (SQDIFF - lower is better)
            result_4k = cv2.matchTemplate(current_roi, template_4k, cv2.TM_SQDIFF_NORMED)
            result_lowres = cv2.matchTemplate(current_roi, template_lowres, cv2.TM_SQDIFF_NORMED)
            score_4k = result_4k[0][0]
            score_lowres = result_lowres[0][0]

            self.logger.debug(f"[{iteration}] Resolution check: 4K={score_4k:.4f}, lowres={score_lowres:.4f}")

            # If 4K matches better (lower score), resolution is correct
            if score_4k <= score_lowres:
                return True

            # GUARD: If NEITHER template matches well (both > 0.08), something is covering
            # the corner (popup, menu, etc.) - this is NOT a resolution issue
            MATCH_THRESHOLD = 0.08
            if score_4k > MATCH_THRESHOLD and score_lowres > MATCH_THRESHOLD:
                self.logger.debug(f"[{iteration}] Resolution check: both templates fail to match (4K={score_4k:.4f}, lowres={score_lowres:.4f}), corner likely covered - skipping")
                return True  # Assume resolution is fine, corner just covered

            # Low-res matches better AND actually matches - resolution drifted!
            self.logger.warning(f"[{iteration}] Resolution drift detected! 4K={score_4k:.4f} > lowres={score_lowres:.4f}")
            self.logger.info(f"[{iteration}] Running setup_bluestacks.py to fix...")
            _run_setup_bluestacks(debug=self.debug)

            # Verify fix by re-checking
            frame = self.windows_helper.get_screenshot_cv2()
            current_roi = frame[y:y+h, x:x+w]
            result_4k = cv2.matchTemplate(current_roi, template_4k, cv2.TM_SQDIFF_NORMED)
            result_lowres = cv2.matchTemplate(current_roi, template_lowres, cv2.TM_SQDIFF_NORMED)
            score_4k = result_4k[0][0]
            score_lowres = result_lowres[0][0]

            if score_4k <= score_lowres:
                self.logger.info(f"[{iteration}] Resolution fixed! 4K={score_4k:.4f}")
                return True
            else:
                self.logger.error(f"[{iteration}] Resolution still wrong after fix: 4K={score_4k:.4f} > lowres={score_lowres:.4f}")
                return False

        except Exception as e:
            self.logger.error(f"[{iteration}] Resolution check failed: {e}")
            return True  # Don't block on errors

    def _check_resolution_fallback(self, iteration: int) -> bool:
        """Fallback resolution check using wm size."""
        current_res = _get_current_resolution(self.adb)
        if current_res == self.EXPECTED_RESOLUTION:
            return True

        self.logger.warning(f"[{iteration}] Resolution wrong: {current_res}, expected {self.EXPECTED_RESOLUTION}")
        _run_setup_bluestacks(debug=self.debug)

        new_res = _get_current_resolution(self.adb)
        return new_res == self.EXPECTED_RESOLUTION

    def _validate_barrack_state(self, barrack_index: int) -> tuple:
        """
        Validate barracks state history for a single barrack.

        Requires N readings where:
        - At least 60% are a specific letter (R, P, or T)
        - Remaining can only be ? (UNKNOWN)
        - No mixing of different letters

        Args:
            barrack_index: 0-3 for the 4 barracks

        Returns:
            (is_valid, dominant_state, ratio) where:
            - is_valid: True if validation passes
            - dominant_state: The dominant state letter (R, P, T) or None
            - ratio: The ratio of dominant state readings
        """
        from utils.barracks_state_matcher import BarrackState

        history = self.barracks_state_history[barrack_index]

        if len(history) < self.BARRACKS_CONSECUTIVE_REQUIRED:
            return False, None, 0.0

        # Convert to letters
        state_chars = []
        for state in history:
            if state == BarrackState.READY:
                state_chars.append('R')
            elif state == BarrackState.PENDING:
                state_chars.append('P')
            elif state == BarrackState.TRAINING:
                state_chars.append('T')
            else:  # UNKNOWN
                state_chars.append('?')

        # Count letters (excluding ?)
        letters = [c for c in state_chars if c != '?']
        unknown_count = len(state_chars) - len(letters)

        if not letters:
            return False, None, 0.0  # All UNKNOWN

        # Check if all letters are the same
        unique_letters = set(letters)
        if len(unique_letters) > 1:
            return False, None, 0.0  # Mixed letters (e.g., R and P)

        # Calculate ratio
        dominant_letter = letters[0]
        letter_count = len(letters)
        ratio = letter_count / len(state_chars)

        if ratio >= self.BARRACKS_MIN_LETTER_RATIO:
            # Map letter back to state
            state_map = {'R': BarrackState.READY, 'P': BarrackState.PENDING, 'T': BarrackState.TRAINING}
            return True, state_map[dominant_letter], ratio

        return False, None, ratio

    # =========================================================================
    # WebSocket API Methods (called by daemon_server.py)
    # =========================================================================

    def _load_runtime_state(self):
        """Load runtime state from scheduler on startup for resumability."""
        from utils.barracks_state_matcher import BarrackState
        from utils.hospital_state_matcher import HospitalState

        state = self.scheduler.get_daemon_state()
        if not state:
            self.logger.info("STARTUP: No saved daemon state found, starting fresh")
            return

        # Restore state from persistent storage
        self.stamina_reader.history = state.get("stamina_history", [])

        # Convert string names back to BarrackState enums
        saved_barracks = state.get("barracks_state_history", [[], [], [], []])
        self.barracks_state_history = [
            [BarrackState[s] if s in BarrackState.__members__ else BarrackState.UNKNOWN for s in history]
            for history in saved_barracks
        ]

        # Convert string names back to HospitalState enums
        saved_hospital = state.get("hospital_state_history", [])
        self.hospital_state_history = [
            HospitalState[s] if s in HospitalState.__members__ else HospitalState.IDLE
            for s in saved_hospital
        ]

        self.vs_chest_triggered = set(state.get("vs_chest_triggered", []))
        self.vs_chest_last_day = state.get("vs_chest_last_day")
        self.beast_training_last_rally = state.get("beast_training_last_rally", 0)
        self.beast_training_rally_count = state.get("beast_training_rally_count", 0)
        self.last_rally_march_click = state.get("last_rally_march_click", 0)
        self.union_boss_mode_until = state.get("union_boss_mode_until", 0)
        self.paused = state.get("paused", False)

        self.logger.info(f"STARTUP: Loaded daemon state (paused={self.paused}, stamina_history={len(self.stamina_reader.history)} readings)")

    def _save_runtime_state(self):
        """Save runtime state to scheduler (called periodically + on shutdown)."""
        # Convert enum values to strings for JSON serialization
        barracks_history_serializable = [
            [s.name if hasattr(s, 'name') else str(s) for s in history]
            for history in self.barracks_state_history
        ]
        hospital_history_serializable = [
            s.name if hasattr(s, 'name') else str(s)
            for s in self.hospital_state_history
        ]

        self.scheduler.update_daemon_state(
            stamina_history=self.stamina_reader.history,
            barracks_state_history=barracks_history_serializable,
            hospital_state_history=hospital_history_serializable,
            vs_chest_triggered=list(self.vs_chest_triggered),
            vs_chest_last_day=self.vs_chest_last_day,
            beast_training_last_rally=self.beast_training_last_rally,
            beast_training_rally_count=self.beast_training_rally_count,
            last_rally_march_click=self.last_rally_march_click,
            union_boss_mode_until=self.union_boss_mode_until,
            paused=self.paused,
        )

    def trigger_flow(self, flow_name: str) -> dict:
        """
        API: Trigger a specific flow immediately and wait for result.

        Args:
            flow_name: Name of flow to trigger (e.g., "tavern_quest", "bag_flow")

        Returns:
            dict with success status, flow name, and flow result
        """
        # Hot-reload flow modules to pick up code changes
        try:
            self.reload_flows()
        except Exception as e:
            self.logger.error(f"HOT-RELOAD ERROR: {e}")

        flow_map = self.get_available_flows()
        if flow_name not in flow_map:
            return {"success": False, "error": f"Unknown flow: {flow_name}", "available": list(flow_map.keys())}

        flow_func, critical = flow_map[flow_name]

        # Run flow synchronously and capture result
        result = self._run_flow_sync(flow_name, flow_func, critical=critical)

        # Broadcast event to connected clients
        if self.command_server:
            self.command_server.broadcast("flow_completed", {
                "flow": flow_name,
                "success": result.get("success", False),
                "critical": critical,
                "result": result.get("result")
            })

        return result

    def _is_user_idle(self) -> bool:
        """Check if user is currently idle (fresh check against IDLE_THRESHOLD)."""
        return get_user_idle_seconds() >= self.IDLE_THRESHOLD

    def _run_flow_sync(self, flow_name: str, flow_func, critical: bool = False) -> dict:
        """
        Run a flow synchronously (blocking) and return its result.

        Used by the WebSocket API to wait for flow completion.
        """
        with self.flow_lock:
            if flow_name in self.active_flows:
                return {"success": False, "error": f"{flow_name} already running"}

            if not critical and self.critical_flow_active:
                return {"success": False, "error": f"Blocked by critical flow {self.critical_flow_name}"}

            if self.active_flows:
                return {"success": False, "error": f"Another flow is active: {self.active_flows}"}

            self.active_flows.add(flow_name)

        try:
            if critical:
                with self.flow_lock:
                    self.critical_flow_active = True
                    self.critical_flow_name = flow_name
                self.logger.info(f"CRITICAL FLOW START: {flow_name}")
            else:
                self.logger.info(f"FLOW START: {flow_name}")

            # Mark daemon action before flow clicks (filters from idle tracking)
            mark_daemon_action()
            # Run flow and capture result
            flow_result = flow_func(self.adb)

            if critical:
                self.logger.info(f"CRITICAL FLOW END: {flow_name}")
            else:
                self.logger.info(f"FLOW END: {flow_name}")

            return {"success": True, "flow": flow_name, "critical": critical, "result": flow_result}

        except Exception as e:
            self.logger.error(f"FLOW ERROR: {flow_name} - {e}")
            return {"success": False, "flow": flow_name, "error": str(e)}

        finally:
            with self.flow_lock:
                self.active_flows.discard(flow_name)
                if critical and self.critical_flow_name == flow_name:
                    self.critical_flow_active = False
                    self.critical_flow_name = None

    def reload_flows(self):
        """
        Hot-reload all flow modules for live code updates.

        Called before trigger_flow() to pick up any code changes.
        """
        import sys

        # List of modules to reload (in dependency order)
        modules_to_reload = [
            'utils.windows_screenshot_helper',
            'flows.bag_use_item_subflow',
            'flows.bag_special_flow',
            'flows.bag_hero_flow',
            'flows.bag_resources_flow',
            'flows.bag_flow',
            'flows.tavern_quest_flow',
            'flows.faction_trials_flow',
            'flows',
        ]

        for mod_name in modules_to_reload:
            if mod_name in sys.modules:
                importlib.reload(sys.modules[mod_name])
            else:
                self.logger.debug(f"HOT-RELOAD: Module {mod_name} not loaded, skipping")

        # Re-import all flow functions after reload
        global handshake_flow, treasure_map_flow, corn_harvest_flow, gold_coin_flow
        global harvest_box_flow, iron_bar_flow, gem_flow, cabbage_flow
        global equipment_enhancement_flow, elite_zombie_flow, afk_rewards_flow
        global union_gifts_flow, union_technology_flow, hero_upgrade_arms_race_flow
        global stamina_claim_flow, stamina_use_flow, soldier_training_flow
        global soldier_upgrade_flow, rally_join_flow, healing_flow, bag_flow, gift_box_flow
        global tavern_quest_claim_flow, run_tavern_quest_flow, faction_trials_flow
        global zombie_attack_flow

        from flows import (handshake_flow, treasure_map_flow, corn_harvest_flow,
                          gold_coin_flow, harvest_box_flow, iron_bar_flow, gem_flow,
                          cabbage_flow, equipment_enhancement_flow, elite_zombie_flow,
                          afk_rewards_flow, union_gifts_flow, union_technology_flow,
                          hero_upgrade_arms_race_flow, stamina_claim_flow, stamina_use_flow,
                          soldier_training_flow, soldier_upgrade_flow, rally_join_flow,
                          healing_flow, bag_flow, gift_box_flow)
        from flows.tavern_quest_flow import tavern_quest_claim_flow, run_tavern_quest_flow
        from flows.faction_trials_flow import faction_trials_flow
        from flows.zombie_attack_flow import zombie_attack_flow

        self.logger.info("HOT-RELOAD: All flow modules reloaded")

    def get_available_flows(self) -> dict:
        """
        Return dict of flow_name -> (flow_func, is_critical).

        Used by WebSocket API to list and trigger flows.
        """
        return {
            "tavern_quest": (run_tavern_quest_flow, True),  # Double-pass claim strategy
            "bag_flow": (bag_flow, True),
            "union_gifts": (union_gifts_flow, False),
            "union_technology": (union_technology_flow, False),
            "afk_rewards": (afk_rewards_flow, False),
            "hero_upgrade": (hero_upgrade_arms_race_flow, True),
            "soldier_training": (lambda adb: soldier_training_flow(adb, debug=False), True),
            "soldier_upgrade": (lambda adb: soldier_upgrade_flow(adb, debug=False), True),
            "healing": (healing_flow, False),
            "elite_zombie": (elite_zombie_flow, False),
            "zombie_attack": (lambda adb: zombie_attack_flow(adb, zombie_type='iron_mine', plus_clicks=10), False),
            "handshake": (handshake_flow, False),
            "treasure_map": (treasure_map_flow, True),
            "corn_harvest": (corn_harvest_flow, False),
            "gold_coin": (gold_coin_flow, False),
            "iron_bar": (iron_bar_flow, False),
            "gem": (gem_flow, False),
            "cabbage": (cabbage_flow, False),
            "equipment": (equipment_enhancement_flow, False),
            "harvest_box": (harvest_box_flow, False),
            "gift_box": (gift_box_flow, True),
            "stamina_claim": (stamina_claim_flow, False),
            "faction_trials": (lambda adb: faction_trials_flow(adb, self.windows_helper), True),
            "arms_race_check": (lambda adb: check_arms_race_progress(adb, self.windows_helper, debug=True), False),
        }

    def get_status(self) -> dict:
        """
        API: Get current daemon status.

        Returns comprehensive status dict for monitoring.
        """
        arms_race = get_arms_race_status()
        return {
            "paused": self.paused,
            "active_flows": list(self.active_flows),
            "critical_flow": self.critical_flow_name,
            "stamina": self.stamina_reader.history[-1] if self.stamina_reader.history else None,
            "idle_seconds": get_user_idle_seconds(),  # Use filtered idle (same as gating logic)
            "arms_race": {
                "event": arms_race.get("current"),
                "day": arms_race.get("day"),
                "time_remaining": str(arms_race.get("time_remaining", "")),
            },
            "server_port": DAEMON_SERVER_PORT,
        }

    def set_config(self, key: str, value) -> dict:
        """
        API: Dynamically update a config value.

        Only allows whitelisted keys to prevent security issues.
        """
        valid_keys = {
            "IDLE_THRESHOLD": "self.IDLE_THRESHOLD",
            "interval": "self.interval",
            "paused": "self.paused",
        }

        if key not in valid_keys:
            return {"success": False, "error": f"Cannot set '{key}'. Allowed: {list(valid_keys.keys())}"}

        try:
            setattr(self, key if key != "IDLE_THRESHOLD" else "IDLE_THRESHOLD", value)
            self.logger.info(f"API: Config updated: {key} = {value}")
            return {"success": True, "key": key, "value": value}
        except Exception as e:
            return {"success": False, "error": str(e)}

    def run(self):
        """Main detection loop."""
        self.logger.info(f"Starting detection loop (interval: {self.interval}s)")
        self.logger.info("Detecting: Handshake, Treasure map, Corn, Gold, Harvest box, Iron, Gem, Cabbage, Equipment, World")
        print("Press Ctrl+C to stop")
        print("=" * 60)

        # Check resolution immediately on startup
        self._check_resolution(0)

        iteration = 0
        while True:
            iteration += 1

            try:
                # Initialize stamina tracking for this iteration (set properly at line ~1802)
                stamina_confirmed = False
                confirmed_stamina = None

                # Check if paused via API
                if self.paused:
                    if iteration % 30 == 0:  # Log every ~1 min when paused
                        self.logger.info(f"[{iteration}] PAUSED (use daemon_cli.py resume to unpause)")
                    time.sleep(self.interval)
                    continue

                # Periodic state save (every N iterations for resumability)
                if iteration % self.state_save_interval == 0:
                    self._save_runtime_state()

                # Check if xclash is running and in foreground
                if not self._is_xclash_in_foreground():
                    self.logger.warning(f"[{iteration}] xclash not in foreground - running full recovery...")
                    return_to_base_view(self.adb, self.windows_helper, debug=True)
                    continue  # Skip this iteration, start fresh

                # Take single screenshot for all checks
                frame = self.windows_helper.get_screenshot_cv2()

                # Skip all daemon checks if critical flow is active
                if self.critical_flow_active:
                    self.logger.info(f"[{iteration}] BLOCKED: Critical flow active ({self.critical_flow_name})")
                    time.sleep(self.interval)
                    continue

                # =================================================================
                # FLOW CANDIDATE COLLECTION
                # All flow detection adds to this list - NO direct execution here.
                # At the end of detection, _execute_best_flow() picks ONE to run.
                # This prevents flows from stepping on each other.
                # =================================================================
                flow_candidates: List[FlowCandidate] = []

                # Check IMMEDIATE action icons FIRST (before slow OCR)
                handshake_present, handshake_score = self.handshake_matcher.is_present(frame)
                treasure_present, treasure_score = self.treasure_matcher.is_present(frame)
                harvest_present, harvest_score = self.harvest_box_matcher.is_present(frame)

                # Collect immediate actions as candidates (no idle requirements)
                if handshake_present:
                    flow_candidates.append(FlowCandidate(
                        name="handshake",
                        flow_func=handshake_flow,
                        priority=FlowPriority.URGENT,
                        reason=f"score={handshake_score:.4f}"
                    ))

                if treasure_present:
                    # Validate: treasure map can only appear when world/town button visible
                    view_state, view_score = detect_view(frame)
                    if view_state in (ViewState.TOWN, ViewState.WORLD):
                        flow_candidates.append(FlowCandidate(
                            name="treasure_map",
                            flow_func=treasure_map_flow,
                            priority=FlowPriority.URGENT,
                            critical=True,
                            reason=f"score={treasure_score:.4f}, view={view_state.value}"
                        ))
                    else:
                        self.logger.warning(f"[{iteration}] TREASURE rejected - no world/town icon (view={view_state.value}, score={treasure_score:.4f})")

                if harvest_present:
                    flow_candidates.append(FlowCandidate(
                        name="harvest_box",
                        flow_func=harvest_box_flow,
                        priority=FlowPriority.URGENT,
                        reason=f"score={harvest_score:.4f}"
                    ))

                # Tavern Quest scheduled claim - check if completion is imminent (within 15 seconds)
                # Uses run_tavern_quest_flow for double-pass strategy (avoids UI glitches missing claims)
                if self.scheduler.is_tavern_completion_imminent():
                    flow_candidates.append(FlowCandidate(
                        name="tavern_quest",
                        flow_func=run_tavern_quest_flow,
                        priority=FlowPriority.CRITICAL,  # Imminent completion is time-critical
                        critical=True,
                        reason="completion imminent"
                    ))

                # Get current time for cooldown checks
                current_time = time.time()

                # Rally march button check (requires idle + cooldown, but not alignment)
                if RALLY_JOIN_ENABLED:
                    march_match = self.rally_march_matcher.find_march_button(frame)
                    march_present = march_match is not None
                    march_score = march_match[2] if march_match else 1.0

                    if march_present:
                        march_x, march_y, _ = march_match
                        # Check prerequisites: TOWN or WORLD view, idle, cooldown
                        view_state, _ = detect_view(frame)
                        # Use filtered idle (excludes daemon's own clicks) - consistent with rest of daemon
                        rally_effective_idle = get_user_idle_seconds()

                        # Union Boss mode: faster cooldown (15s instead of 30s)
                        in_union_boss_mode = current_time < self.union_boss_mode_until
                        rally_cooldown = UNION_BOSS_RALLY_COOLDOWN if in_union_boss_mode else RALLY_MARCH_BUTTON_COOLDOWN
                        rally_cooldown_elapsed = (current_time - self.last_rally_march_click) >= rally_cooldown

                        rally_idle_ok = rally_effective_idle >= IDLE_THRESHOLD
                        rally_view_ok = view_state in [ViewState.TOWN, ViewState.WORLD]

                        # Log Union Boss mode status
                        if in_union_boss_mode:
                            remaining = int(self.union_boss_mode_until - current_time)
                            self.logger.debug(f"[{iteration}] UNION BOSS MODE: {remaining}s remaining, cooldown={rally_cooldown}s")

                        if rally_idle_ok and rally_view_ok and rally_cooldown_elapsed:
                            # Check if another flow is running BEFORE clicking
                            if not self._can_run_flow():
                                self.logger.debug(f"[{iteration}] RALLY: Skipping - another flow is active")
                            else:
                                mode_str = " [BOSS MODE]" if in_union_boss_mode else ""
                                self.logger.info(f"[{iteration}] RALLY MARCH button detected at ({march_x}, {march_y}), score={march_score:.4f}{mode_str}")
                                # Click the march button to open Union War panel
                                click_x, click_y = self.rally_march_matcher.get_click_position(march_x, march_y)
                                mark_daemon_action()
                                self.adb.tap(click_x, click_y)
                                self.last_rally_march_click = current_time
                                time.sleep(0.5)  # Brief wait for panel to start loading

                                # Run rally join flow via _run_flow_sync to get result AND coordinate with other flows
                                flow_result = self._run_flow_sync(
                                    "rally_join_flow",
                                    lambda adb: rally_join_flow(adb, union_boss_mode=in_union_boss_mode),
                                    critical=True
                                )
                                if flow_result.get("success"):
                                    result = flow_result.get("result", {})
                                    # Check if Union Boss was joined - enter Union Boss mode
                                    if result.get('monster_name') == 'Union Boss':
                                        self.union_boss_mode_until = current_time + UNION_BOSS_MODE_DURATION
                                        self.logger.info(f"[{iteration}] UNION BOSS detected! Entering Union Boss mode for 30 minutes")
                                elif flow_result.get("error"):
                                    self.logger.warning(f"[{iteration}] Rally join blocked: {flow_result.get('error')}")

                # Periodic OCR server health check (every 5 minutes)
                if current_time - self.last_ocr_health_check >= self.OCR_HEALTH_CHECK_INTERVAL:
                    self.last_ocr_health_check = current_time
                    self._check_ocr_server_health()

                # Extract stamina using OCR server (fast - no model loading)
                try:
                    stamina = self.ocr_client.extract_number(frame, self.STAMINA_REGION)
                    if stamina is None:
                        self.ocr_consecutive_failures += 1
                    else:
                        self.ocr_consecutive_failures = 0  # Reset on success
                except Exception as ocr_err:
                    self.logger.warning(f"[{iteration}] OCR error: {ocr_err}")
                    stamina = None
                    self.ocr_consecutive_failures += 1

                # After 3 consecutive OCR failures, try to restart server
                if self.ocr_consecutive_failures >= 3:
                    self.logger.warning(f"[{iteration}] {self.ocr_consecutive_failures} consecutive OCR failures, checking server health...")
                    self._check_ocr_server_health()
                    self.ocr_consecutive_failures = 0  # Reset counter after check

                stamina_str = str(stamina) if stamina is not None else "?"

                # Check remaining icons (these need idle/alignment checks anyway)
                corn_present, corn_score = self.corn_matcher.is_present(frame)
                gold_present, gold_score = self.gold_matcher.is_present(frame)
                iron_present, iron_score = self.iron_matcher.is_present(frame)
                gem_present, gem_score = self.gem_matcher.is_present(frame)
                cabbage_present, cabbage_score = self.cabbage_matcher.is_present(frame)
                equip_present, equip_score = self.equipment_enhancement_matcher.is_present(frame)
                hospital_state, hospital_score = self.hospital_matcher.get_state(frame)
                afk_present, afk_score = self.afk_rewards_matcher.is_present(frame)
                # Get view state using view_state_detector
                view_state_enum, view_score = detect_view(frame)
                view_state = view_state_enum.value.upper()  # "TOWN", "WORLD", "CHAT", "UNKNOWN"
                back_present, back_score = self.back_button_matcher.is_present(frame)

                # DEBUG: Capture screenshot when view is CHAT or UNKNOWN (problematic states)
                if view_state in ("CHAT", "UNKNOWN"):
                    get_daemon_debug().capture(frame, iteration, view_state, "view_problem")

                # DEBUG: Periodic baseline capture (every 50 iterations)
                if iteration % 50 == 0:
                    get_daemon_debug().capture(frame, iteration, view_state, "baseline")

                # Reset UNKNOWN recovery loop counters when we're genuinely out of UNKNOWN
                # This only resets when detect_view returns TOWN/WORLD, not when return_to_base_view says "success"
                if view_state in ("TOWN", "WORLD") and self.unknown_recovery_count > 0:
                    self.logger.debug(f"[{iteration}] UNKNOWN loop counters reset (view={view_state})")
                    self.unknown_recovery_count = 0
                    self.unknown_first_recovery_time = None

                # For backwards compatibility with flow checks
                world_present = (view_state == "TOWN")
                town_present = (view_state == "WORLD")

                # Get idle time (filtered - ignores daemon clicks and BlueStacks noise)
                idle_secs = get_user_idle_seconds()
                idle_str = format_idle_time(idle_secs)

                # Use Windows idle directly for all automation checks
                effective_idle_secs = idle_secs

                # Check resolution periodically (every N iterations, no idle requirement)
                self._check_resolution(iteration)

                # Get Pacific time for logging
                pacific_time = datetime.now(self.pacific_tz).strftime('%H:%M:%S')

                # Get Arms Race status (computed from UTC time, no screenshot needed)
                arms_race = get_arms_race_status()
                arms_race_event = arms_race['current']
                arms_race_remaining = arms_race['time_remaining']
                arms_race_remaining_mins = int(arms_race_remaining.total_seconds() / 60)

                # Get barracks states
                barracks_state_str = format_barracks_states(frame)

                # Update barracks history EVERY iteration during Soldier Training/VS day
                # This allows history to build up BEFORE idle threshold is met
                is_soldier_event_active = arms_race_event == "Soldier Training"
                is_vs_promo_day = arms_race['day'] in self.VS_SOLDIER_PROMOTION_DAYS
                if view_state == "TOWN" and (is_soldier_event_active or is_vs_promo_day):
                    from utils.barracks_state_matcher import BarrackState
                    states = self.barracks_matcher.get_all_states(frame)
                    for i, (state, _) in enumerate(states):
                        self.barracks_state_history[i].append(state)
                        if len(self.barracks_state_history[i]) > self.BARRACKS_CONSECUTIVE_REQUIRED:
                            self.barracks_state_history[i].pop(0)

                # Check if VS promotion day is active (for logging)
                vs_promo_active = arms_race['day'] in self.VS_SOLDIER_PROMOTION_DAYS
                vs_indicator = " [VS:Promo]" if vs_promo_active else ""

                # Check for active special events (for logging)
                from utils.special_events import get_active_events_short
                special_events_indicator = get_active_events_short()

                # =================================================================
                # ARMS RACE DATA COLLECTION (automated, runs once per event type)
                # Triggers in first 15 min of block when idle 5+ min and data missing
                # =================================================================
                time_elapsed_secs = arms_race['time_elapsed'].total_seconds()
                if (effective_idle_secs >= 300 and  # 5+ min idle
                    time_elapsed_secs < 900 and  # First 15 min of block
                    view_state == "TOWN" and
                    should_collect_event_data(arms_race_event)):
                    self.logger.info(f"[{iteration}] ARMS RACE DATA: Collecting missing data for {arms_race_event}...")
                    try:
                        success = collect_and_save_current_event(self.adb, self.windows_helper, debug=self.debug)
                        if success:
                            self.logger.info(f"[{iteration}] ARMS RACE DATA: Successfully collected data for {arms_race_event}")
                        else:
                            self.logger.warning(f"[{iteration}] ARMS RACE DATA: Failed to collect data for {arms_race_event}")
                    except Exception as e:
                        self.logger.error(f"[{iteration}] ARMS RACE DATA: Error collecting data: {e}")

                # Format hospital state for logging
                hospital_state_char = {
                    HospitalState.HELP_READY: "HELP",
                    HospitalState.TRAINING: "TRAIN",
                    HospitalState.HEALING: "HEAL",
                    HospitalState.SOLDIERS_WOUNDED: "WOUND",
                    HospitalState.IDLE: "IDLE",
                    HospitalState.UNKNOWN: "?"
                }.get(hospital_state, "?")

                # Log status line with view state, stamina, barracks, and arms race
                self.logger.info(f"[{iteration}] {pacific_time} [{view_state}] Stamina:{stamina_str} idle:{idle_str} AR:{arms_race_event[:3]}({arms_race_remaining_mins}m){vs_indicator}{special_events_indicator} Barracks:[{barracks_state_str}] H:{handshake_score:.3f} T:{treasure_score:.3f} C:{corn_score:.3f} G:{gold_score:.3f} HB:{harvest_score:.3f} I:{iron_score:.3f} Gem:{gem_score:.3f} Cab:{cabbage_score:.3f} Eq:{equip_score:.3f} Hosp:{hospital_state_char}({hospital_score:.3f}) AFK:{afk_score:.3f} V:{view_score:.3f} B:{back_score:.3f}")

                # Log detailed barracks scores (s=stopwatch, y=yellow, w=white)
                # Only log when barracks has UNKNOWN or PENDING state (to avoid noise)
                if "?" in barracks_state_str or "P" in barracks_state_str:
                    barracks_detailed = format_barracks_states_detailed(frame)
                    self.logger.info(f"[{iteration}] Barracks detailed: {barracks_detailed}")

                # =================================================================
                # IN-TOWN QUICK ACTIONS (harvest, hospital, barracks)
                # These run FIRST because they're quick clicks that don't navigate away.
                # Must run before Elite Zombie/Bag/Tavern which leave TOWN view.
                # =================================================================

                # PRIORITY CHECK: Skip harvest flows if Beast Training rally is imminent
                # Beast Training rallies are time-critical and should not be blocked by harvest flows
                beast_training_priority = False
                if (self.ARMS_RACE_BEAST_TRAINING_ENABLED and
                    arms_race_event == "Mystic Beast Training" and
                    arms_race_remaining_mins <= self.ARMS_RACE_BEAST_TRAINING_LAST_MINUTES and
                    stamina_confirmed and
                    confirmed_stamina >= self.BEAST_TRAINING_STAMINA_THRESHOLD):
                    beast_training_priority = True
                    self.logger.debug(f"[{iteration}] BEAST TRAINING PRIORITY: Skipping harvest flows (stamina={confirmed_stamina}, event_remaining={arms_race_remaining_mins}min)")

                # Harvest/Hospital/Barracks conditions
                harvest_idle_ok = effective_idle_secs >= self.IDLE_THRESHOLD
                if not harvest_idle_ok:
                    self.logger.debug(f"[{iteration}] HARVEST: Blocked - idle time {idle_secs}s < threshold {self.IDLE_THRESHOLD}s")
                harvest_aligned = False
                if harvest_idle_ok and world_present:
                    is_aligned, dog_score = self.dog_house_matcher.is_aligned(frame)
                    harvest_aligned = is_aligned
                    if not is_aligned:
                        self.logger.debug(f"[{iteration}] HARVEST: Blocked - misaligned (score={dog_score:.4f}, threshold={self.dog_house_matcher.threshold})")

                # Corn, Gold, Iron, Gem, Cabbage, Equip - quick bubble clicks in TOWN
                # Skip if Beast Training rally has priority (time-critical)
                # Collect as flow candidates - execution happens via _execute_best_flow()
                if corn_present and world_present and harvest_aligned and not beast_training_priority and self._is_user_idle():
                    flow_candidates.append(FlowCandidate(
                        name="corn_harvest",
                        flow_func=corn_harvest_flow,
                        priority=FlowPriority.LOW,
                        reason=f"score={corn_score:.4f}"
                    ))

                if gold_present and world_present and harvest_aligned and not beast_training_priority and self._is_user_idle():
                    flow_candidates.append(FlowCandidate(
                        name="gold_coin",
                        flow_func=gold_coin_flow,
                        priority=FlowPriority.LOW,
                        reason=f"score={gold_score:.4f}"
                    ))

                if iron_present and world_present and harvest_aligned and not beast_training_priority and self._is_user_idle():
                    flow_candidates.append(FlowCandidate(
                        name="iron_bar",
                        flow_func=iron_bar_flow,
                        priority=FlowPriority.LOW,
                        reason=f"score={iron_score:.4f}"
                    ))

                if gem_present and world_present and harvest_aligned and not beast_training_priority and self._is_user_idle():
                    flow_candidates.append(FlowCandidate(
                        name="gem",
                        flow_func=gem_flow,
                        priority=FlowPriority.LOW,
                        reason=f"score={gem_score:.4f}"
                    ))

                if cabbage_present and world_present and harvest_aligned and not beast_training_priority and self._is_user_idle():
                    flow_candidates.append(FlowCandidate(
                        name="cabbage",
                        flow_func=cabbage_flow,
                        priority=FlowPriority.LOW,
                        reason=f"score={cabbage_score:.4f}"
                    ))

                if equip_present and world_present and harvest_aligned and not beast_training_priority and self._is_user_idle():
                    flow_candidates.append(FlowCandidate(
                        name="equipment_enhancement",
                        flow_func=equipment_enhancement_flow,
                        priority=FlowPriority.LOW,
                        reason=f"score={equip_score:.4f}"
                    ))

                # Hospital state detection with majority vote (same 60% rule as barracks)
                # History accumulates when in TOWN, idle check is only for ACTION
                if world_present:
                    self.hospital_state_history.append(hospital_state)
                    if len(self.hospital_state_history) > self.HOSPITAL_CONSECUTIVE_REQUIRED:
                        self.hospital_state_history.pop(0)

                    # Check if we have enough readings and idle threshold met (fresh check)
                    if len(self.hospital_state_history) >= self.HOSPITAL_CONSECUTIVE_REQUIRED and self._is_user_idle():
                        # Count each actionable state
                        help_ready_count = sum(1 for s in self.hospital_state_history if s == HospitalState.HELP_READY)
                        healing_count = sum(1 for s in self.hospital_state_history if s == HospitalState.HEALING)
                        wounded_count = sum(1 for s in self.hospital_state_history if s == HospitalState.SOLDIERS_WOUNDED)

                        # Use 60% majority rule (same as barracks)
                        min_required = int(self.HOSPITAL_CONSECUTIVE_REQUIRED * 0.6)  # 6 out of 10

                        # Get click position for hospital actions
                        hospital_click_x, hospital_click_y = self.hospital_matcher.get_click_position()

                        # HELP_READY: Just click to request ally help (simple action, not a flow)
                        if help_ready_count >= min_required:
                            # Create a simple click flow
                            def help_ready_flow(adb, x=hospital_click_x, y=hospital_click_y):
                                mark_daemon_action()
                                adb.tap(x, y)
                            flow_candidates.append(FlowCandidate(
                                name="hospital_help",
                                flow_func=help_ready_flow,
                                priority=FlowPriority.HIGH,
                                reason=f"HELP_READY {help_ready_count}/{self.HOSPITAL_CONSECUTIVE_REQUIRED}"
                            ))

                        # HEALING: Click to open panel, run healing flow
                        elif healing_count >= min_required:
                            # Create wrapper that clicks, waits, then runs healing_flow
                            def healing_wrapper(adb, x=hospital_click_x, y=hospital_click_y):
                                mark_daemon_action()
                                adb.tap(x, y)
                                time.sleep(2.5)  # Wait for panel to fully open
                                healing_flow(adb)
                            flow_candidates.append(FlowCandidate(
                                name="healing",
                                flow_func=healing_wrapper,
                                priority=FlowPriority.HIGH,
                                reason=f"HEALING {healing_count}/{self.HOSPITAL_CONSECUTIVE_REQUIRED}"
                            ))

                        # SOLDIERS_WOUNDED: Click to open panel, run healing flow
                        elif wounded_count >= min_required:
                            # Create wrapper that clicks, waits, then runs healing_flow
                            def wounded_wrapper(adb, x=hospital_click_x, y=hospital_click_y):
                                mark_daemon_action()
                                adb.tap(x, y)
                                time.sleep(2.5)  # Wait for panel to fully open
                                healing_flow(adb)
                            flow_candidates.append(FlowCandidate(
                                name="healing",
                                flow_func=wounded_wrapper,
                                priority=FlowPriority.HIGH,
                                reason=f"WOUNDED {wounded_count}/{self.HOSPITAL_CONSECUTIVE_REQUIRED}"
                            ))
                else:
                    # Not in TOWN - reset hospital state history
                    if self.hospital_state_history:
                        self.hospital_state_history = []

                # Barracks: READY/PENDING barracks (non-Arms Race ONLY)
                # During Arms Race "Soldier Training" or VS promotion days, soldier_upgrade_flow handles this
                # Fresh idle check (user may have become active)
                is_arms_race_soldier_active = arms_race_event == "Soldier Training" or arms_race['day'] in self.VS_SOLDIER_PROMOTION_DAYS
                if world_present and harvest_aligned and self._is_user_idle() and not is_arms_race_soldier_active:
                    from utils.barracks_state_matcher import BarrackState
                    states = self.barracks_matcher.get_all_states(frame)
                    ready_count = sum(1 for state, _ in states if state == BarrackState.READY)
                    pending_count = sum(1 for state, _ in states if state == BarrackState.PENDING)

                    if ready_count > 0 or pending_count > 0:
                        flow_candidates.append(FlowCandidate(
                            name="soldier_training",
                            flow_func=soldier_training_flow,
                            priority=FlowPriority.HIGH,
                            critical=True,
                            reason=f"{ready_count} READY, {pending_count} PENDING"
                        ))

                # =================================================================
                # UNKNOWN STATE TRACKING AND RECOVERY
                # =================================================================

                # Track UNKNOWN state duration (with hysteresis to prevent flicker resets)
                if view_state == "UNKNOWN":
                    # Back in UNKNOWN - reset the "left" timer
                    self.unknown_state_left_time = None
                    if self.unknown_state_start is None:
                        self.unknown_state_start = time.time()
                        self.logger.debug(f"[{iteration}] Entered UNKNOWN state")
                else:
                    # Not in UNKNOWN - track when we left (hysteresis)
                    if self.unknown_state_start is not None:
                        if self.unknown_state_left_time is None:
                            # Just left UNKNOWN, start hysteresis timer
                            self.unknown_state_left_time = time.time()
                            self.logger.debug(f"[{iteration}] Left UNKNOWN state (now {view_state}), starting hysteresis...")
                        else:
                            # Check if we've been out long enough to reset
                            time_out = time.time() - self.unknown_state_left_time
                            if time_out >= self.UNKNOWN_HYSTERESIS:
                                self.logger.debug(f"[{iteration}] Out of UNKNOWN for {time_out:.0f}s, resetting timer")
                                self.unknown_state_start = None
                                self.unknown_state_left_time = None

                # UNKNOWN state recovery - IMMEDIATE and aggressive
                # When stuck in UNKNOWN, try to recover EVERY iteration:
                # 1. Check for disconnection dialog (user on mobile) → wait before dismiss
                # 2. Check for shaded button (popup blocking) → click to dismiss
                # 3. Check for back button → click to close dialog
                # 4. Check for safe ground → click to dismiss floating panel
                # 5. If stuck 180s+, run full return_to_base_view
                # CRITICAL: Skip recovery if ANY flow is active - flows control their own UI
                if view_state == "UNKNOWN" and not self.active_flows:
                    if self.unknown_state_start is not None:
                        unknown_duration = time.time() - self.unknown_state_start

                        # Check for disconnection dialog (user playing on mobile) - needs idle wait
                        is_disconnected, disc_score = is_disconnection_dialog_visible(frame, debug=self.debug)
                        if is_disconnected:
                            # Track when we first saw the dialog
                            if self.disconnection_dialog_detected_time is None:
                                self.disconnection_dialog_detected_time = time.time()
                                self.logger.info(f"[{iteration}] DISCONNECTION DIALOG: Detected! User may be on mobile. Waiting {DISCONNECTION_WAIT_SECONDS}s before dismissing...")

                            wait_elapsed = time.time() - self.disconnection_dialog_detected_time
                            if wait_elapsed >= DISCONNECTION_WAIT_SECONDS:
                                # Waited long enough, click Confirm
                                confirm_pos = get_confirm_button_position()
                                self.logger.info(f"[{iteration}] DISCONNECTION DIALOG: Waited {wait_elapsed:.0f}s, clicking Confirm at {confirm_pos}...")
                                mark_daemon_action()
                                self.adb.tap(*confirm_pos)
                                self.disconnection_dialog_detected_time = None
                                self.unknown_state_start = None
                                self.unknown_state_left_time = None
                                time.sleep(2)  # Wait for reconnect
                                continue
                            else:
                                # Still waiting, skip normal recovery
                                remaining = DISCONNECTION_WAIT_SECONDS - wait_elapsed
                                if iteration % 10 == 0:  # Log every 10 iterations
                                    self.logger.debug(f"[{iteration}] DISCONNECTION DIALOG: Waiting... {remaining:.0f}s remaining")
                                continue
                        else:
                            # No disconnection dialog, reset timer if it was set
                            if self.disconnection_dialog_detected_time is not None:
                                self.logger.debug(f"[{iteration}] DISCONNECTION DIALOG: Dialog dismissed externally")
                                self.disconnection_dialog_detected_time = None

                        # RECOVERY - try every iteration once user is idle
                        if effective_idle_secs >= self.IDLE_THRESHOLD and unknown_duration < self.UNKNOWN_STATE_TIMEOUT:
                            from utils.template_matcher import match_template
                            from utils.safe_ground_matcher import find_safe_ground
                            from utils.ui_helpers import click_back
                            from utils.shaded_button_helper import is_button_shaded, BUTTON_CLICK

                            # FIRST: Check for shaded button (popup blocking view)
                            shaded, shaded_score = is_button_shaded(frame)
                            if shaded:
                                self.logger.info(f"[{iteration}] UNKNOWN RECOVERY: Shaded button detected (score={shaded_score:.4f}), clicking to dismiss popup...")
                                mark_daemon_action()
                                self.adb.tap(*BUTTON_CLICK)
                                time.sleep(0.5)
                                # Re-check view state
                                new_frame = self.windows_helper.get_screenshot_cv2()
                                new_state, _ = detect_view(new_frame)
                                if new_state.name in ("TOWN", "WORLD"):
                                    self.logger.info(f"[{iteration}] UNKNOWN RECOVERY: Success! Now in {new_state.name}")
                                    self.unknown_state_start = None
                                    self.unknown_state_left_time = None
                                    continue  # Skip rest of iteration, start fresh
                                else:
                                    self.logger.debug(f"[{iteration}] UNKNOWN RECOVERY: Still in {new_state.name} after shaded click, will keep trying")
                                    continue  # Keep trying

                            # SECOND: Check for back button with masked template (catches dialogs/menus)
                            back_found, back_score, back_pos = match_template(frame, "back_button_union_4k.png", threshold=0.98)
                            if back_found:
                                self.logger.info(f"[{iteration}] UNKNOWN RECOVERY: Back button detected (score={back_score:.4f}), clicking...")
                                mark_daemon_action()
                                click_back(self.adb)
                                time.sleep(0.5)
                                # Re-check view state
                                new_frame = self.windows_helper.get_screenshot_cv2()
                                new_state, _ = detect_view(new_frame)
                                if new_state.name in ("TOWN", "WORLD"):
                                    self.logger.info(f"[{iteration}] UNKNOWN RECOVERY: Success! Now in {new_state.name}")
                                    self.unknown_state_start = None
                                    self.unknown_state_left_time = None
                                    continue  # Skip rest of iteration, start fresh
                                else:
                                    self.logger.debug(f"[{iteration}] UNKNOWN RECOVERY: Still in {new_state.name}, will keep trying back button")
                                    continue  # Keep trying back button if it's still visible

                            # SECOND: Try safe ground (for floating popups without back button)
                            ground_pos = find_safe_ground(frame, debug=self.debug)
                            if ground_pos:
                                self.logger.info(f"[{iteration}] UNKNOWN RECOVERY: Clicking safe ground at {ground_pos} to dismiss popup...")
                                mark_daemon_action()
                                self.adb.tap(*ground_pos)
                                time.sleep(0.5)
                                # Re-check view state
                                new_frame = self.windows_helper.get_screenshot_cv2()
                                new_state, _ = detect_view(new_frame)
                                if new_state.name in ("TOWN", "WORLD"):
                                    self.logger.info(f"[{iteration}] UNKNOWN RECOVERY: Success! Now in {new_state.name}")
                                    self.unknown_state_start = None
                                    self.unknown_state_left_time = None
                                    continue  # Skip rest of iteration, start fresh
                                else:
                                    self.logger.debug(f"[{iteration}] UNKNOWN RECOVERY: Still in {new_state.name}, will retry")

                        # Full recovery: After 180s AND user is idle, run return_to_base_view
                        # Don't interrupt if user is actively using the game
                        if unknown_duration >= self.UNKNOWN_STATE_TIMEOUT and effective_idle_secs >= self.IDLE_THRESHOLD:
                            # Track recovery cycles for loop detection
                            if self.unknown_first_recovery_time is None:
                                self.unknown_first_recovery_time = time.time()
                            self.unknown_recovery_count += 1

                            # Check if we're stuck in a loop (multiple recoveries in short time)
                            time_since_first = time.time() - self.unknown_first_recovery_time
                            if time_since_first >= self.UNKNOWN_LOOP_TIMEOUT:
                                self.logger.error(f"[{iteration}] UNKNOWN LOOP DETECTED: {self.unknown_recovery_count} recoveries in {time_since_first/60:.1f}min - FORCING APP RESTART")
                                self._force_app_restart()
                                # Reset all UNKNOWN tracking after restart
                                self.unknown_recovery_count = 0
                                self.unknown_first_recovery_time = None
                                self.unknown_state_start = None
                                self.unknown_state_left_time = None
                                continue

                            self.logger.info(f"[{iteration}] UNKNOWN FULL RECOVERY (attempt {self.unknown_recovery_count}): In UNKNOWN for {unknown_duration:.0f}s, idle for {idle_str}, running return_to_base_view...")
                            # DEBUG: Capture screenshot before recovery
                            get_daemon_debug().capture(frame, iteration, view_state, "recovery", f"attempt_{self.unknown_recovery_count}")
                            success = return_to_base_view(self.adb, self.windows_helper, debug=True)
                            if success:
                                self.logger.info(f"[{iteration}] UNKNOWN FULL RECOVERY: Successfully reached base view")
                            else:
                                self.logger.warning(f"[{iteration}] UNKNOWN FULL RECOVERY: Had to restart app")
                            self.unknown_state_start = None  # Reset UNKNOWN timer after recovery attempt
                            self.unknown_state_left_time = None
                            # NOTE: Do NOT reset unknown_recovery_count here - only reset when view is actually TOWN/WORLD
                            continue  # Skip rest of iteration, start fresh

                # Idle return-to-town - every 5 iterations when idle, return to TOWN
                # Most scanning happens in TOWN view, so we want to be there when idle
                # CRITICAL: Skip if ANY flow is running (not just critical flows)
                if effective_idle_secs >= self.IDLE_THRESHOLD and not self.active_flows:
                    self.idle_iteration_count += 1

                    if self.idle_iteration_count >= self.IDLE_RETURN_TO_TOWN_INTERVAL:
                        self.idle_iteration_count = 0  # Reset counter

                        # Not in town - navigate there (handles CHAT, WORLD)
                        if view_state != "TOWN" and view_state != "UNKNOWN":
                            self.logger.info(f"[{iteration}] IDLE RETURN: In {view_state}, navigating to TOWN...")
                            self._switch_to_town()
                        elif view_state == "TOWN":
                            # In TOWN - check if dog house is aligned
                            is_aligned, dog_score = self.dog_house_matcher.is_aligned(frame)
                            if not is_aligned:
                                self.logger.info(f"[{iteration}] IDLE RETURN: Town view misaligned (dog_score={dog_score:.4f}), resetting view...")
                                # Go to WORLD then back to TOWN to reset alignment
                                go_to_world(self.adb, debug=False)
                                time.sleep(1.0)
                                go_to_town(self.adb, debug=False)
                                self.logger.info(f"[{iteration}] IDLE RETURN: View reset complete")
                else:
                    # Not idle or a flow is active - reset counter
                    self.idle_iteration_count = 0

                # =================================================================
                # UNIFIED STAMINA VALIDATION
                # =================================================================
                # Uses StaminaReader for MODE-based confirmation with consistency check
                # Requires 3 consistent readings (max-min <= 10), returns MODE value
                stamina_confirmed, confirmed_stamina = self.stamina_reader.add_reading(stamina)

                # =================================================================
                # PRE-BEAST TRAINING: Claim stamina + block elite rallies before event
                # =================================================================
                # Calculate time until Beast Training starts
                time_until_beast = get_time_until_beast_training()
                minutes_until_beast = time_until_beast.total_seconds() / 60 if time_until_beast else 999

                # Track if we're in the pre-event window (0 < minutes <= 6)
                in_pre_beast_window = 0 < minutes_until_beast <= self.BEAST_TRAINING_PRE_EVENT_MINUTES

                # Pre-event stamina claim: 6 min before Beast Training, claim if red dot visible
                # This starts the 4-hour cooldown early so we can claim again in last 6 min of event
                # Uses scheduler's pre_beast_stamina_claim flow config (idle_required=20s, lower than IDLE_THRESHOLD)
                # REQUIRES: TOWN or WORLD view (need to see stamina area)
                if in_pre_beast_window and view_state not in ("TOWN", "WORLD"):
                    self.logger.warning(f"[{iteration}] PRE-BEAST STAMINA: {minutes_until_beast:.1f}min until event but view={view_state} - cannot detect red dot!")
                    get_daemon_debug().capture(frame, iteration, view_state, "pre_beast_blocked", f"{minutes_until_beast:.0f}min")
                if in_pre_beast_window and view_state in ("TOWN", "WORLD") and self.scheduler.is_flow_ready("pre_beast_stamina_claim", idle_seconds=effective_idle_secs):
                    # Calculate which upcoming block this is for
                    upcoming_beast_block = arms_race['block_end']  # Next block starts when current ends

                    # Only claim once per upcoming block
                    if self.beast_training_pre_claim_block != upcoming_beast_block:
                        # Check for red notification dot
                        has_dot, red_count = has_stamina_red_dot(frame, debug=self.debug)
                        if has_dot:
                            # Mark this block as claimed BEFORE queueing to prevent re-queue
                            self.beast_training_pre_claim_block = upcoming_beast_block
                            flow_candidates.append(FlowCandidate(
                                name="pre_beast_stamina_claim",  # Must match scheduler config key
                                flow_func=stamina_claim_flow,
                                priority=FlowPriority.CRITICAL,
                                reason=f"pre-beast {minutes_until_beast:.1f}min, red dot ({red_count} pixels)",
                                record_to_scheduler=True  # Record cooldown
                            ))
                        elif self.debug:
                            self.logger.debug(f"[{iteration}] PRE-BEAST TRAINING: {minutes_until_beast:.1f}min until event, but no red dot ({red_count} pixels)")

                # Elite zombie rally - stamina >= 118 and idle 5+ min
                # BLOCKED: if Beast Training starts in < 6 minutes (preserve stamina for event)
                elite_rally_blocked = in_pre_beast_window
                elite_zombie_triggered = False
                if stamina_confirmed and confirmed_stamina >= self.ELITE_ZOMBIE_STAMINA_THRESHOLD and effective_idle_secs >= self.IDLE_THRESHOLD:
                    if elite_rally_blocked:
                        self.logger.info(f"[{iteration}] ELITE ZOMBIE: BLOCKED - Beast Training starts in {minutes_until_beast:.1f}min, preserving stamina")
                    else:
                        elite_zombie_triggered = True
                        flow_candidates.append(FlowCandidate(
                            name="elite_zombie",
                            flow_func=elite_zombie_flow,
                            priority=FlowPriority.URGENT,
                            critical=True,
                            reason=f"stamina={confirmed_stamina}, idle={idle_str}"
                        ))

                # =================================================================
                # ARMS RACE EVENT TRACKING
                # =================================================================
                current_time = time.time()  # Needed for cooldown checks
                # arms_race, arms_race_event, arms_race_remaining, arms_race_remaining_mins already set above

                # Beast Training: Mystic Beast Training last N minutes, stamina >= 20, cooldown
                # Uses the SAME stamina_confirmed from unified validation above
                #
                # Sequence order (optimized for last 6 minutes):
                # 1. Claim free stamina (if red dot visible)
                # 2. Rally (burn stamina down to < 20)
                # 3. Use +50 recovery items (only when stamina < 20, after rallies burn it down)
                # 4. Rally again (with the +50 stamina from Use)
                #
                # This order ensures we do rallies FIRST with existing stamina, THEN use recovery items.
                if (self.ARMS_RACE_BEAST_TRAINING_ENABLED and
                    arms_race_event == "Mystic Beast Training" and
                    arms_race_remaining_mins <= self.ARMS_RACE_BEAST_TRAINING_LAST_MINUTES):

                    # Track which block we're in - reset counters if new block
                    block_start = arms_race['block_start']
                    if self.beast_training_current_block != block_start:
                        self.beast_training_current_block = block_start
                        self.beast_training_rally_count = 0
                        self.beast_training_use_count = 0  # Reset Use count for new block
                        # Check if there's a pre-set target for this block
                        arms_race_state = self.scheduler.get_arms_race_state()
                        next_target = arms_race_state.get("beast_training_next_target_rallies")
                        # Get zombie mode for logging
                        block_zombie_mode, block_zombie_expires = self.scheduler.get_zombie_mode()
                        mode_info = f", mode={block_zombie_mode}" if block_zombie_mode != "elite" else ""
                        if next_target:
                            # Copy next target to current target
                            self.scheduler.update_arms_race_state(
                                beast_training_target_rallies=next_target,
                                beast_training_next_target_rallies=None,
                                beast_training_rally_count=0
                            )
                            self.logger.info(f"[{iteration}] BEAST TRAINING: New block started, rally count reset to 0, use count reset to 0, target={next_target} (from pre-set){mode_info}")
                        else:
                            self.scheduler.update_arms_race_state(beast_training_rally_count=0)
                            self.logger.info(f"[{iteration}] BEAST TRAINING: New block started, rally count reset to 0, use count reset to 0{mode_info}")

                    # =========================================================
                    # SMART BEAST TRAINING FLOW - With Claude CLI decision
                    # Phase 1: Hour mark (60 min remaining) - inventory + progress + claim upfront
                    # Phase 2: Last 6 minutes - re-check + claim remainder
                    # =========================================================

                    # PHASE 1: Hour Mark Check - retry until success (like union_technology)
                    # Uses scheduler pattern: is_flow_ready() checks idle, record_flow_run() on success
                    if self.scheduler.is_flow_ready("beast_training_hour_mark", idle_seconds=effective_idle_secs):
                        # Check if already done for THIS block (block-based tracking)
                        phase_state = self.scheduler.get_arms_race_state()
                        hour_mark_block = phase_state.get("beast_training_hour_mark_block")

                        if hour_mark_block != str(block_start):  # Not done for this block
                            self.logger.info(f"[{iteration}] BEAST TRAINING: Running Hour Mark Phase (Claude CLI)...")
                            result = run_hour_mark_phase(self.adb, self.windows_helper, debug=self.debug)

                            if result["success"]:
                                rallies_needed = result["rallies_needed"]
                                current_pts = result.get("current_points")
                                stamina_claimed = result.get("stamina_claimed", 0)

                                self.logger.info(
                                    f"[{iteration}] BEAST TRAINING: Hour Mark complete - "
                                    f"Progress {current_pts}/30000 pts, need {rallies_needed} more rallies, "
                                    f"claimed {stamina_claimed} stamina"
                                )

                                # ALWAYS reset rally_count and recalculate target from actual points
                                # The POINTS are the source of truth, not our counter
                                self.beast_training_rally_count = 0
                                self.scheduler.update_arms_race_state(
                                    beast_training_rally_count=0,
                                    beast_training_target_rallies=rallies_needed
                                )
                                if rallies_needed == 0:
                                    self.logger.info(f"[{iteration}] BEAST TRAINING: Chest3 already reached! Skipping rallies.")
                                else:
                                    self.logger.info(f"[{iteration}] BEAST TRAINING: Reset rally_count=0, target={rallies_needed} (from {current_pts}/30000 pts)")

                                # Mark block as done and record flow run
                                self.scheduler.update_arms_race_state(beast_training_hour_mark_block=str(block_start))
                                self.scheduler.record_flow_run("beast_training_hour_mark")
                            else:
                                # Failed - DON'T mark as done, will retry next iteration
                                self.logger.warning(f"[{iteration}] BEAST TRAINING: Hour Mark phase failed, will retry...")

                    # PHASE 2: Last 6 Minutes Re-check - retry until success
                    if (arms_race_remaining_mins <= 6 and
                        self.scheduler.is_flow_ready("beast_training_last_6", idle_seconds=effective_idle_secs)):
                        # Check if already done for THIS block
                        phase_state = self.scheduler.get_arms_race_state()
                        last_6_block = phase_state.get("beast_training_last_6_block")

                        if last_6_block != str(block_start):  # Not done for this block
                            self.logger.info(f"[{iteration}] BEAST TRAINING: Running Last 6 Minutes Phase (Claude CLI)...")
                            result = run_last_6_minutes_phase(self.adb, self.windows_helper, debug=self.debug)

                            if result["success"]:
                                rallies_needed = result["rallies_needed"]
                                current_pts = result.get("current_points")
                                stamina_claimed = result.get("stamina_claimed", 0)

                                self.logger.info(
                                    f"[{iteration}] BEAST TRAINING: Last 6 Min complete - "
                                    f"Progress {current_pts}/30000 pts, need {rallies_needed} more rallies, "
                                    f"claimed {stamina_claimed} stamina"
                                )

                                # ALWAYS reset rally_count and recalculate target from actual points
                                # The POINTS are the source of truth, not our counter
                                self.beast_training_rally_count = 0
                                self.scheduler.update_arms_race_state(
                                    beast_training_rally_count=0,
                                    beast_training_target_rallies=rallies_needed
                                )
                                if rallies_needed == 0:
                                    self.logger.info(f"[{iteration}] BEAST TRAINING: Chest3 reached! Mission accomplished.")
                                else:
                                    self.logger.info(f"[{iteration}] BEAST TRAINING: Reset rally_count=0, target={rallies_needed} (from {current_pts}/30000 pts)")

                                # Mark block as done and record flow run
                                self.scheduler.update_arms_race_state(beast_training_last_6_block=str(block_start))
                                self.scheduler.record_flow_run("beast_training_last_6")
                            else:
                                # Failed - DON'T mark as done, will retry next iteration
                                self.logger.warning(f"[{iteration}] BEAST TRAINING: Last 6 Minutes phase failed, will retry...")

                    # Get target from scheduler (or use MAX_RALLIES as default)
                    # NOTE: Use "is None" check, NOT "or", because 0 is a valid target (chest3 reached)
                    arms_race_state = self.scheduler.get_arms_race_state()
                    rally_target = arms_race_state.get("beast_training_target_rallies")
                    if rally_target is None:
                        rally_target = self.BEAST_TRAINING_MAX_RALLIES

                    # STEP 1: Stamina Claim candidate - if stamina < 60 AND red dot visible
                    # Highest priority within beast training (get free stamina first)
                    beast_claim_candidate = False
                    if (stamina_confirmed and
                        confirmed_stamina < self.STAMINA_CLAIM_THRESHOLD):
                        # Check for red notification dot (indicates free claim available)
                        has_dot, red_count = has_stamina_red_dot(frame, debug=self.debug)
                        if has_dot:
                            beast_claim_candidate = True
                            flow_candidates.append(FlowCandidate(
                                name="beast_stamina_claim",
                                flow_func=stamina_claim_flow,
                                priority=FlowPriority.CRITICAL,
                                reason=f"beast training, stamina={confirmed_stamina}, red dot ({red_count}px)"
                            ))
                        elif self.debug:
                            self.logger.debug(f"[{iteration}] BEAST TRAINING: Stamina {confirmed_stamina} < {self.STAMINA_CLAIM_THRESHOLD}, but no red dot ({red_count} pixels), skipping claim")

                    # STEP 2: Rally candidate - if stamina >= threshold, cooldown ok, and under target
                    # Only add if claim wasn't already a candidate (mutually exclusive)
                    # Get current zombie mode (may be "elite", "gold", "food", or "iron_mine")
                    zombie_mode, zombie_expires = self.scheduler.get_zombie_mode()
                    mode_config = ZOMBIE_MODE_CONFIG.get(zombie_mode, ZOMBIE_MODE_CONFIG["elite"])
                    stamina_threshold = mode_config["stamina"]

                    rally_cooldown_ok = (current_time - self.beast_training_last_rally) >= self.BEAST_TRAINING_RALLY_COOLDOWN
                    beast_rally_candidate = False
                    if (not beast_claim_candidate and
                        stamina_confirmed and
                        confirmed_stamina >= stamina_threshold and
                        rally_cooldown_ok and
                        self.beast_training_rally_count < rally_target):
                        # Create wrapper based on zombie mode
                        if zombie_mode == "elite":
                            def beast_rally_wrapper(adb):
                                import config
                                original_clicks = getattr(config, 'ELITE_ZOMBIE_PLUS_CLICKS', 5)
                                config.ELITE_ZOMBIE_PLUS_CLICKS = 0
                                try:
                                    return elite_zombie_flow(adb)
                                finally:
                                    config.ELITE_ZOMBIE_PLUS_CLICKS = original_clicks
                        else:
                            # Zombie attack mode (gold/food/iron_mine)
                            zombie_type = mode_config.get("zombie_type", "gold")
                            plus_clicks = mode_config.get("plus_clicks", 10)
                            def beast_rally_wrapper(adb, zt=zombie_type, pc=plus_clicks):
                                return zombie_attack_flow(adb, zombie_type=zt, plus_clicks=pc)

                        beast_rally_candidate = True
                        remaining = rally_target - self.beast_training_rally_count - 1  # -1 because we're about to do one
                        mode_str = f"[{zombie_mode}]" if zombie_mode != "elite" else ""
                        flow_candidates.append(FlowCandidate(
                            name="beast_training",
                            flow_func=beast_rally_wrapper,
                            priority=FlowPriority.CRITICAL,
                            critical=True,
                            reason=f"{mode_str}rally #{self.beast_training_rally_count+1}/{rally_target}, {remaining} remaining, {arms_race_remaining_mins:.0f}min left"
                        ))

                    # STEP 3: Use Button candidate - only if neither claim nor rally is a candidate
                    # Conditions: idle 5+ min, rally count < target, stamina < threshold, Use clicks < 4, cooldown
                    # SMART: Check claim timer first - if free claim will be available before event ends, WAIT
                    # Note: stamina_threshold is already set from zombie mode (10 for zombie, 20 for elite)
                    use_cooldown_ok = (current_time - self.beast_training_last_use_time) >= self.BEAST_TRAINING_USE_COOLDOWN
                    use_allowed_by_time = (self.beast_training_use_count < 2 or
                                           arms_race_remaining_mins <= self.BEAST_TRAINING_USE_LAST_MINUTES)
                    if (not beast_claim_candidate and
                        not beast_rally_candidate and
                        self.BEAST_TRAINING_USE_ENABLED and
                        effective_idle_secs >= self.IDLE_THRESHOLD and
                        stamina_confirmed and
                        confirmed_stamina < stamina_threshold and
                        self.beast_training_rally_count < rally_target and
                        self.beast_training_use_count < self.BEAST_TRAINING_USE_MAX and
                        use_cooldown_ok and
                        use_allowed_by_time):

                        # SMART CHECK: Will free claim be available before event ends?
                        # If yes, WAIT for it instead of using recovery items
                        from flows.stamina_claim_flow import check_claim_status
                        claim_status = check_claim_status(self.adb, self.windows_helper)
                        timer_seconds = claim_status.get("timer_seconds")
                        event_remaining_seconds = arms_race_remaining_mins * 60

                        if timer_seconds is not None and timer_seconds < event_remaining_seconds:
                            # Free claim will be available before event ends - WAIT
                            timer_mins = timer_seconds // 60
                            self.logger.info(
                                f"[{iteration}] BEAST TRAINING: Stamina low but free claim in {timer_mins}min "
                                f"(event has {arms_race_remaining_mins:.0f}min left) - WAITING instead of using recovery item"
                            )
                        else:
                            # Timer won't expire in time OR OCR failed - add use candidate
                            remaining = rally_target - self.beast_training_rally_count
                            timer_reason = "timer OCR failed" if timer_seconds is None else f"timer {timer_seconds//60}min > event {arms_race_remaining_mins:.0f}min"
                            flow_candidates.append(FlowCandidate(
                                name="beast_stamina_use",
                                flow_func=stamina_use_flow,
                                priority=FlowPriority.CRITICAL,
                                reason=f"recovery item ({timer_reason}), use #{self.beast_training_use_count+1}/{self.BEAST_TRAINING_USE_MAX}, rally #{self.beast_training_rally_count}/{rally_target}"
                            ))

                # Enhance Hero: last N minutes, runs once per block
                # NO idle requirement - flow checks real-time progress and skips if chest3 reached
                enhance_hero_candidate = False
                if (self.ARMS_RACE_ENHANCE_HERO_ENABLED and
                    arms_race_event == "Enhance Hero" and
                    arms_race_remaining_mins <= self.ENHANCE_HERO_LAST_MINUTES):
                    # Check if we already triggered for this block
                    block_start = arms_race['block_start']
                    if self.enhance_hero_last_block_start != block_start:
                        enhance_hero_candidate = True
                        flow_candidates.append(FlowCandidate(
                            name="enhance_hero_arms_race",
                            flow_func=hero_upgrade_arms_race_flow,
                            priority=FlowPriority.CRITICAL,
                            critical=True,
                            reason=f"last {arms_race_remaining_mins:.0f}min of Enhance Hero"
                        ))

                # =================================================================
                # GENERIC ARMS RACE PROGRESS CHECK - ALL EVENTS, last 10 minutes
                # Log current points for data collection, even if we don't have actions
                # =================================================================
                if (arms_race_remaining_mins <= self.ARMS_RACE_PROGRESS_CHECK_MINUTES and
                    effective_idle_secs >= 120):  # 2 min idle
                    block_start = arms_race['block_start']
                    if self.arms_race_progress_check_block != block_start:
                        self.logger.info(f"[{iteration}] ARMS RACE PROGRESS: Last {arms_race_remaining_mins:.0f}min of {arms_race_event}, checking points...")
                        try:
                            result = check_arms_race_progress(self.adb, self.windows_helper, debug=self.debug)
                            if result["success"]:
                                pts = result["current_points"]
                                chest3 = result["chest3_target"]
                                remaining = result["points_to_chest3"]

                                if chest3:
                                    self.logger.info(
                                        f"[{iteration}] ARMS RACE PROGRESS: {arms_race_event} - "
                                        f"{pts}/{chest3} pts ({remaining} to chest3)"
                                    )
                                else:
                                    # chest3 threshold not known yet - log anyway
                                    self.logger.info(
                                        f"[{iteration}] ARMS RACE PROGRESS: {arms_race_event} - "
                                        f"{pts} pts (chest3 threshold unknown)"
                                    )

                                # Store in scheduler for history
                                self.scheduler.record_arms_race_progress(
                                    event=arms_race_event,
                                    points=pts,
                                    chest3_target=chest3,
                                    block_start=str(block_start)
                                )
                            else:
                                self.logger.warning(f"[{iteration}] ARMS RACE PROGRESS: Failed to check progress")
                        except Exception as e:
                            self.logger.error(f"[{iteration}] ARMS RACE PROGRESS: Error - {e}")

                        # Mark block as checked (even on failure, to avoid spam)
                        self.arms_race_progress_check_block = block_start

                # =========================================================
                # SOLDIER SPEEDUP AT HOUR 2 AND HOUR 3 (Marshall + Quick Speedup)
                # During "Soldier Training" event, speed up all TRAINING barracks
                # Hour 2: ~2 hours into event, Hour 3: ~3 hours into event
                # Uses Marshall title for speedup bonus, then Quick Speedup all barracks
                # =========================================================
                is_soldier_event = arms_race_event == "Soldier Training"
                soldier_speedup_h2_candidate = False
                soldier_speedup_h3_candidate = False
                speedup_block_start = None

                if is_soldier_event and self._is_user_idle():
                    hours_into_event = arms_race['time_elapsed'].total_seconds() / 3600
                    speedup_block_start = arms_race['block_start']
                    phase_state = self.scheduler.get_arms_race_state()

                    # Hour 2 checkpoint (2.0 - 2.5 hours into event)
                    if 2.0 <= hours_into_event < 2.5:
                        hour2_block = phase_state.get("soldier_speedup_hour2_block")
                        if hour2_block != str(speedup_block_start):
                            soldier_speedup_h2_candidate = True
                            flow_candidates.append(FlowCandidate(
                                name="soldier_speedup_h2",
                                flow_func=lambda adb: marshall_speedup_all_flow(adb, self.windows_helper, debug=self.debug),
                                priority=FlowPriority.CRITICAL,
                                critical=True,
                                reason=f"Hour 2 checkpoint ({hours_into_event:.2f}h into event)"
                            ))

                    # Hour 3 checkpoint (3.0 - 3.5 hours into event)
                    elif 3.0 <= hours_into_event < 3.5:
                        hour3_block = phase_state.get("soldier_speedup_hour3_block")
                        if hour3_block != str(speedup_block_start):
                            soldier_speedup_h3_candidate = True
                            flow_candidates.append(FlowCandidate(
                                name="soldier_speedup_h3",
                                flow_func=lambda adb: marshall_speedup_all_flow(adb, self.windows_helper, debug=self.debug),
                                priority=FlowPriority.CRITICAL,
                                critical=True,
                                reason=f"Hour 3 checkpoint ({hours_into_event:.2f}h into event)"
                            ))

                # Soldier Training: during Soldier Training event OR VS promotion day, idle 5+ min
                # Requires TOWN view and dog house aligned (same as harvest conditions)
                # CONTINUOUSLY checks for READY/PENDING barracks and upgrades them (no block limitation)
                # VS override: On VS_SOLDIER_PROMOTION_DAYS, promotions run ALL DAY regardless of event
                is_vs_promotion_day = arms_race['day'] in self.VS_SOLDIER_PROMOTION_DAYS

                if (self.ARMS_RACE_SOLDIER_TRAINING_ENABLED and
                    (is_soldier_event or is_vs_promotion_day) and
                    effective_idle_secs >= self.IDLE_THRESHOLD):
                    trigger_reason = "VS Day" if is_vs_promotion_day and not is_soldier_event else "Soldier Training event"
                    self.logger.debug(f"[{iteration}] SOLDIER: Outer conditions PASS (reason={trigger_reason}, day={arms_race['day']}, event={arms_race_event}, idle={idle_secs}s)")

                    # History is already updated every iteration above (lines 1148-1158)
                    # Just validate with 60% rule (allows ? mixed with consistent letter)
                    validated_states = []
                    for i in range(4):
                        is_valid, dominant_state, ratio = self._validate_barrack_state(i)
                        validated_states.append((is_valid, dominant_state, ratio))

                    # Check if we have enough readings
                    if len(self.barracks_state_history[0]) < self.BARRACKS_CONSECUTIVE_REQUIRED:
                        self.logger.debug(f"[{iteration}] SOLDIER: Not enough readings ({len(self.barracks_state_history[0])}/{self.BARRACKS_CONSECUTIVE_REQUIRED})")
                        continue

                    # Log validation status for debugging
                    validation_str = " ".join([
                        f"B{i+1}:{v[1].value[0].upper() if v[1] else '?'}({v[2]:.0%})"
                        for i, v in enumerate(validated_states)
                    ])
                    self.logger.debug(f"[{iteration}] SOLDIER: Validation: {validation_str}")

                    # Count validated READY and PENDING barracks
                    pending_indices = [i for i, (valid, state, _) in enumerate(validated_states)
                                       if valid and state == BarrackState.PENDING]
                    ready_indices = [i for i, (valid, state, _) in enumerate(validated_states)
                                     if valid and state == BarrackState.READY]

                    pending_count = len(pending_indices)
                    ready_count = len(ready_indices)

                    self.logger.debug(f"[{iteration}] SOLDIER: Validated - ready={ready_count}, pending={pending_count}, world_present={world_present}")

                    if (ready_count > 0 or pending_count > 0) and world_present:
                        # Check alignment
                        is_aligned, dog_score = self.dog_house_matcher.is_aligned(frame)
                        if not is_aligned:
                            self.logger.info(f"[{iteration}] SOLDIER: Blocked - dog house misaligned (score={dog_score:.4f}, threshold={self.dog_house_matcher.threshold})")
                        else:
                            self.logger.debug(f"[{iteration}] SOLDIER: Alignment PASS (score={dog_score:.4f})")
                            idle_mins = int(idle_secs / 60)

                            self.logger.info(f"[{iteration}] SOLDIER UPGRADE: {trigger_reason}, idle {idle_mins}min, {ready_count} READY, {pending_count} PENDING barrack(s)")

                            # First, collect soldiers from READY barracks (click yellow bubble)
                            from scripts.flows.soldier_upgrade_flow import soldier_upgrade_flow, get_barrack_click_position
                            if ready_count > 0:
                                self.logger.info(f"[{iteration}] SOLDIER: Collecting from {ready_count} READY barrack(s) at indices {ready_indices}")
                                for idx in ready_indices:
                                    # Re-check idle - stop if user became active
                                    if get_user_idle_seconds() < self.IDLE_THRESHOLD:
                                        self.logger.info(f"[{iteration}] SOLDIER: User active, stopping collection loop")
                                        break
                                    click_x, click_y = get_barrack_click_position(idx)
                                    self.logger.info(f"[{iteration}] SOLDIER: Collecting from barrack {idx+1} at ({click_x}, {click_y})")
                                    mark_daemon_action()
                                    self.adb.tap(click_x, click_y)
                                    time.sleep(0.5)
                                    # Clear history for this barrack after collecting
                                    self.barracks_state_history[idx] = []
                                # Wait for state change after collecting
                                time.sleep(1.0)

                            # Then upgrade each validated PENDING barrack
                            upgrades = 0
                            for idx in pending_indices:
                                # Re-check idle - stop if user became active
                                if get_user_idle_seconds() < self.IDLE_THRESHOLD:
                                    self.logger.info(f"[{iteration}] SOLDIER: User active, stopping upgrade loop")
                                    break

                                # Check if another flow is running BEFORE clicking
                                if not self._can_run_flow():
                                    self.logger.debug(f"[{iteration}] SOLDIER: Skipping - another flow is active")
                                    break  # Exit loop, don't interrupt other flow

                                self.logger.info(f"[{iteration}] SOLDIER: Processing barrack {idx+1}...")

                                # Click to open this barrack's panel
                                click_x, click_y = get_barrack_click_position(idx)
                                self.logger.info(f"[{iteration}] SOLDIER: Clicking barrack {idx+1} at ({click_x}, {click_y})")
                                mark_daemon_action()
                                self.adb.tap(click_x, click_y)
                                time.sleep(1.0)

                                # Run upgrade flow via _run_flow_sync to coordinate with other flows
                                flow_result = self._run_flow_sync(
                                    f"soldier_upgrade_flow_b{idx+1}",
                                    lambda adb, idx=idx: soldier_upgrade_flow(adb, barrack_index=idx, debug=True),
                                    critical=True
                                )
                                success = flow_result.get("success") and flow_result.get("result", False)
                                if not flow_result.get("success") and flow_result.get("error"):
                                    self.logger.warning(f"[{iteration}] SOLDIER: Upgrade blocked: {flow_result.get('error')}")
                                if success:
                                    upgrades += 1
                                    self.logger.info(f"[{iteration}] SOLDIER: Barrack {idx+1} upgrade complete")
                                    # Clear history for this barrack after upgrade
                                    self.barracks_state_history[idx] = []
                                else:
                                    self.logger.info(f"[{iteration}] SOLDIER: Barrack {idx+1} upgrade failed")

                                time.sleep(0.5)

                            self.logger.info(f"[{iteration}] SOLDIER UPGRADE: Completed {upgrades}/{pending_count} upgrade(s)")

                # =================================================================
                # SIDE QUESTS / NAVIGATING FLOWS (run after in-town actions)
                # These flows navigate away from TOWN, so run them after harvest/hospital/barracks
                # =================================================================

                # AFK rewards: requires AFK icon detected + harvest conditions + cooldown
                if afk_present and world_present and harvest_aligned and self._is_user_idle():
                    if self.scheduler.is_flow_ready("afk_rewards", idle_seconds=effective_idle_secs):
                        flow_candidates.append(FlowCandidate(
                            name="afk_rewards",
                            flow_func=afk_rewards_flow,
                            priority=FlowPriority.NORMAL,
                            reason=f"score={afk_score:.4f}",
                            record_to_scheduler=True
                        ))

                # Union gifts: 1 hour cooldown
                if self._is_user_idle() and self.scheduler.is_flow_ready("union_gifts", idle_seconds=effective_idle_secs):
                    flow_candidates.append(FlowCandidate(
                        name="union_gifts",
                        flow_func=union_gifts_flow,
                        priority=FlowPriority.NORMAL,
                        reason=f"idle={idle_str}",
                        record_to_scheduler=True
                    ))

                # Union technology: 1 hour cooldown
                if self._is_user_idle() and self.scheduler.is_flow_ready("union_technology", idle_seconds=effective_idle_secs):
                    flow_candidates.append(FlowCandidate(
                        name="union_technology",
                        flow_func=union_technology_flow,
                        priority=FlowPriority.NORMAL,
                        reason=f"idle={idle_str}",
                        record_to_scheduler=True
                    ))

                # VS Day 7 chest surprise: trigger bag flow at 10, 5, 1 min remaining
                # This opens level chests right before VS day ends to surprise competitors
                vs_day = arms_race['day']
                vs_minutes_remaining = arms_race_remaining_mins  # Use already-calculated value

                # Reset checkpoint tracking when day changes
                if vs_day != self.vs_chest_last_day:
                    self.vs_chest_triggered.clear()
                    self.vs_chest_last_day = vs_day

                # Track which VS checkpoint triggered this candidate (if any)
                vs_checkpoint_triggered = None

                # On Day 7, check if we should trigger bag flow at checkpoint
                if vs_day == 7 and self._is_user_idle():
                    for checkpoint in self.VS_CHEST_CHECKPOINTS:
                        if vs_minutes_remaining <= checkpoint and checkpoint not in self.vs_chest_triggered:
                            vs_checkpoint_triggered = checkpoint
                            flow_candidates.append(FlowCandidate(
                                name="bag_flow",
                                flow_func=bag_flow,
                                priority=FlowPriority.CRITICAL,  # VS surprise is time-critical
                                critical=True,
                                reason=f"VS Day 7 surprise, {vs_minutes_remaining:.1f}min left (checkpoint {checkpoint})"
                            ))
                            break  # Only add one candidate

                # Bag flow: idle threshold, cooldown (navigates to TOWN itself)
                if self._is_user_idle() and self.scheduler.is_flow_ready("bag_flow", idle_seconds=effective_idle_secs):
                    flow_candidates.append(FlowCandidate(
                        name="bag_flow",
                        flow_func=bag_flow,
                        priority=FlowPriority.NORMAL,
                        critical=True,
                        reason=f"idle={idle_str}",
                        record_to_scheduler=True
                    ))

                # Tavern quest SCHEDULED trigger at 10:30 PM Pacific (ignores cooldown/idle)
                # This ensures quests start right when the window opens
                now_pacific = datetime.now(self.pacific_tz)
                tavern_trigger_time = now_pacific.replace(hour=TAVERN_QUEST_START_HOUR, minute=TAVERN_QUEST_START_MINUTE, second=0, microsecond=0)
                tavern_scheduled_triggered = False
                if (now_pacific >= tavern_trigger_time and
                    self.tavern_scheduled_triggered_date != now_pacific.date()):
                    tavern_scheduled_triggered = True
                    flow_candidates.append(FlowCandidate(
                        name="tavern_quest",
                        flow_func=run_tavern_quest_flow,
                        priority=FlowPriority.HIGH,  # Scheduled triggers are important
                        critical=True,
                        reason=f"scheduled {TAVERN_QUEST_START_HOUR}:{TAVERN_QUEST_START_MINUTE:02d} PT",
                        record_to_scheduler=True
                    ))

                # Tavern quest: 5 min idle, 30 min cooldown (claims + Go clicks + timer scan)
                elif self._is_user_idle() and self.scheduler.is_flow_ready("tavern_quest", idle_seconds=effective_idle_secs):
                    flow_candidates.append(FlowCandidate(
                        name="tavern_quest",
                        flow_func=run_tavern_quest_flow,
                        priority=FlowPriority.NORMAL,
                        critical=True,
                        reason=f"idle={idle_str}",
                        record_to_scheduler=True
                    ))

                # Gift box flow: requires WORLD view (town_present means we're in WORLD), 5 min idle, 1 hour cooldown
                if town_present and self._is_user_idle() and self.scheduler.is_flow_ready("gift_box", idle_seconds=effective_idle_secs):
                    flow_candidates.append(FlowCandidate(
                        name="gift_box",
                        flow_func=gift_box_flow,
                        priority=FlowPriority.NORMAL,
                        critical=True,
                        reason=f"idle={idle_str}",
                        record_to_scheduler=True
                    ))

                # Scheduled + continuous idle triggers (e.g., fing_hero at 2 AM Pacific)
                # Track continuous idle start time (using BlueStacks-specific idle)
                if effective_idle_secs >= 5:  # Consider idle if no input for 5+ seconds
                    if self.continuous_idle_start is None:
                        self.continuous_idle_start = time.time()
                else:
                    self.continuous_idle_start = None  # Reset on activity

                # Check scheduled triggers
                now_pacific = datetime.now(self.pacific_tz)
                scheduled_trigger_candidate = None  # Track which trigger was added
                for trigger in self.scheduled_triggers:
                    # Check if we're past trigger time and haven't triggered today
                    if now_pacific.time() >= trigger['trigger_time']:
                        if trigger['last_triggered_date'] != now_pacific.date():
                            # Check idle duration requirement
                            if self.continuous_idle_start:
                                idle_duration = time.time() - self.continuous_idle_start
                                if idle_duration >= trigger['required_idle_seconds']:
                                    # Additional conditions: TOWN view, dog house aligned
                                    if world_present and harvest_aligned:
                                        scheduled_trigger_candidate = trigger
                                        flow_candidates.append(FlowCandidate(
                                            name=trigger['name'],
                                            flow_func=trigger['flow'],
                                            priority=FlowPriority.HIGH,  # Scheduled triggers are important
                                            reason=f"scheduled {trigger['trigger_time']}, idle {idle_duration/3600:.2f}h"
                                        ))
                                        break  # Only one scheduled trigger per iteration
                                    else:
                                        self.logger.debug(f"[{iteration}] SCHEDULED TRIGGER: {trigger['name']} - conditions not met (view={view_state}, aligned={harvest_aligned})")

                # =================================================================
                # FLOW EXECUTION - Execute ONE flow from all candidates
                # This is the SINGLE point of execution, preventing flows from
                # stepping on each other. Priority determines which flow runs.
                # =================================================================
                executed_flow = self._execute_best_flow(flow_candidates, iteration)
                if executed_flow:
                    self.logger.debug(f"[{iteration}] Executed flow: {executed_flow}")

                    # Handle special post-execution tracking
                    if executed_flow == "bag_flow" and vs_checkpoint_triggered is not None:
                        self.vs_chest_triggered.add(vs_checkpoint_triggered)
                        self.logger.info(f"[{iteration}] VS checkpoint {vs_checkpoint_triggered} marked as triggered")

                    if executed_flow == "tavern_quest" and tavern_scheduled_triggered:
                        self.tavern_scheduled_triggered_date = now_pacific.date()
                        self.logger.info(f"[{iteration}] Tavern scheduled trigger marked for {now_pacific.date()}")

                    # Reset hospital state history after hospital flows execute
                    if executed_flow in ("hospital_help", "healing"):
                        self.hospital_state_history = []

                    # Beast training post-execution tracking
                    if executed_flow == "beast_training":
                        self.beast_training_rally_count += 1
                        self.scheduler.update_arms_race_state(beast_training_rally_count=self.beast_training_rally_count)
                        self.beast_training_last_rally = current_time
                        self.stamina_reader.reset()
                        self.logger.info(f"[{iteration}] Beast training rally #{self.beast_training_rally_count} complete")

                    if executed_flow == "beast_stamina_use":
                        self.beast_training_use_count += 1
                        self.beast_training_last_use_time = current_time
                        self.logger.info(f"[{iteration}] Beast training use #{self.beast_training_use_count} complete")

                    # Enhance hero block tracking
                    if executed_flow == "enhance_hero_arms_race" and enhance_hero_candidate:
                        block_start = arms_race['block_start']
                        self.enhance_hero_last_block_start = block_start
                        self.logger.info(f"[{iteration}] Enhance hero arms race complete for block {block_start}")

                    # Soldier speedup block tracking
                    if executed_flow == "soldier_speedup_h2" and soldier_speedup_h2_candidate and speedup_block_start:
                        self.scheduler.update_arms_race_state(soldier_speedup_hour2_block=str(speedup_block_start))
                        self.logger.info(f"[{iteration}] Soldier speedup Hour 2 complete")

                    if executed_flow == "soldier_speedup_h3" and soldier_speedup_h3_candidate and speedup_block_start:
                        self.scheduler.update_arms_race_state(soldier_speedup_hour3_block=str(speedup_block_start))
                        self.logger.info(f"[{iteration}] Soldier speedup Hour 3 complete")

                    # Scheduled trigger tracking
                    if scheduled_trigger_candidate and executed_flow == scheduled_trigger_candidate['name']:
                        scheduled_trigger_candidate['last_triggered_date'] = now_pacific.date()
                        self.logger.info(f"[{iteration}] Scheduled trigger {scheduled_trigger_candidate['name']} marked for {now_pacific.date()}")

                # Log view state for debugging
                if view_state == "TOWN":
                    self.logger.info(f"[{iteration}] View: TOWN (world button visible, score={view_score:.4f})")
                elif view_state == "WORLD":
                    self.logger.info(f"[{iteration}] View: WORLD (town button visible, score={view_score:.4f})")

            except Exception as e:
                self.logger.error(f"[{iteration}] ERROR: {e}")

            time.sleep(self.interval)


# ==============================================================================
# PID Lock File - Prevents multiple daemon instances from running
# ==============================================================================

PID_FILE = Path(__file__).parent.parent / 'logs' / 'daemon.pid'


def _is_process_running(pid: int) -> bool:
    """Check if a process with given PID is running."""
    import subprocess
    try:
        # On Windows, use tasklist to check if PID exists
        result = subprocess.run(
            ['tasklist', '/FI', f'PID eq {pid}', '/NH'],
            capture_output=True, text=True, timeout=5
        )
        # tasklist returns "INFO: No tasks are running..." if not found
        return str(pid) in result.stdout and 'No tasks' not in result.stdout
    except Exception:
        return False


def acquire_daemon_lock() -> bool:
    """
    Acquire exclusive daemon lock. Returns True if acquired, False if another instance running.

    Creates a PID file with current process ID. Before creating, checks if existing
    PID file points to a running process - if so, refuses to start.
    """
    import os

    # Ensure logs directory exists
    PID_FILE.parent.mkdir(exist_ok=True)

    if PID_FILE.exists():
        try:
            existing_pid = int(PID_FILE.read_text().strip())
            if _is_process_running(existing_pid):
                print(f"ERROR: Another daemon instance is already running (PID {existing_pid})")
                print(f"       Kill it first with: taskkill /F /PID {existing_pid}")
                print(f"       Or delete the lock file: {PID_FILE}")
                return False
            else:
                print(f"Stale PID file found (PID {existing_pid} not running), removing...")
                PID_FILE.unlink()
        except (ValueError, OSError) as e:
            print(f"Warning: Could not read PID file, removing: {e}")
            try:
                PID_FILE.unlink()
            except OSError:
                pass

    # Write current PID
    current_pid = os.getpid()
    PID_FILE.write_text(str(current_pid))
    print(f"Daemon lock acquired (PID {current_pid})")
    return True


def release_daemon_lock():
    """Release the daemon lock by removing PID file."""
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
    except OSError:
        pass


def main():
    parser = argparse.ArgumentParser(
        description="Icon auto-clicker daemon"
    )
    parser.add_argument(
        '--interval',
        type=float,
        default=None,
        help="Check interval in seconds (default: 2.0 from config)"
    )
    parser.add_argument(
        '--debug',
        action='store_true',
        help="Enable debug logging (logs all scores, not just detections)"
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help="Force start: kill existing daemon instance if running"
    )

    args = parser.parse_args()

    # ============================================================
    # CRITICAL: Acquire lock FIRST - prevents multiple instances
    # ============================================================
    if args.force:
        # Force mode: kill existing daemon if running
        if PID_FILE.exists():
            try:
                existing_pid = int(PID_FILE.read_text().strip())
                if _is_process_running(existing_pid):
                    print(f"Force mode: Killing existing daemon (PID {existing_pid})...")
                    import subprocess
                    subprocess.run(['taskkill', '/F', '/PID', str(existing_pid)], capture_output=True)
                    time.sleep(1)  # Wait for process to die
                PID_FILE.unlink()
            except Exception as e:
                print(f"Warning: Could not kill existing daemon: {e}")

    if not acquire_daemon_lock():
        sys.exit(1)

    # Redirect stdout to logs/current_daemon.log for easy access
    log_dir = Path(__file__).parent.parent / 'logs'
    log_dir.mkdir(exist_ok=True)
    stdout_log = log_dir / 'current_daemon.log'

    # Tee stdout to both console and file
    import io
    class Tee:
        def __init__(self, *files):
            self.files = files
        def write(self, data):
            for f in self.files:
                f.write(data)
                f.flush()
        def flush(self):
            for f in self.files:
                f.flush()

    stdout_file = open(stdout_log, 'w', buffering=1)
    sys.stdout = Tee(sys.stdout, stdout_file)

    daemon = IconDaemon(interval=args.interval, debug=args.debug)

    try:
        daemon.initialize()
        daemon.run()
    except KeyboardInterrupt:
        print("\n\nStopping...")
        # Save state on shutdown for resumability
        try:
            daemon._save_runtime_state()
            print("State saved.")
        except Exception:
            pass
        stdout_file.close()
        release_daemon_lock()
        print("Stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        stdout_file.close()
        release_daemon_lock()
        sys.exit(1)
    finally:
        # Always release lock on exit
        release_daemon_lock()


if __name__ == "__main__":
    main()
