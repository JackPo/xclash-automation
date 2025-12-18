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
- Enhance Hero: During Enhance Hero last N minutes (configurable), triggers hero_upgrade_arms_race_flow
  ONLY if user was idle since the START of the Enhance Hero block (ensures no interruption).

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
from pathlib import Path
from datetime import datetime
import pytz

sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.adb_helper import ADBHelper
from utils.ocr_client import OCRClient, ensure_ocr_server, start_ocr_server, SERVER_HOST, SERVER_PORT
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
from utils.bluestacks_idle_detector import get_bluestacks_idle_detector, format_bluestacks_idle_time
# user_idle_tracker removed - using raw Windows idle (idle_detector) instead
from utils.view_state_detector import detect_view, go_to_town, go_to_world, ViewState
from utils.dog_house_matcher import DogHouseMatcher
from utils.return_to_base_view import return_to_base_view, _get_current_resolution, _run_setup_bluestacks
from utils.barracks_state_matcher import BarracksStateMatcher, format_barracks_states, format_barracks_states_detailed
from utils.stamina_red_dot_detector import has_stamina_red_dot
from utils.rally_march_button_matcher import RallyMarchButtonMatcher

from flows import handshake_flow, treasure_map_flow, corn_harvest_flow, gold_coin_flow, harvest_box_flow, iron_bar_flow, gem_flow, cabbage_flow, equipment_enhancement_flow, elite_zombie_flow, afk_rewards_flow, union_gifts_flow, union_technology_flow, hero_upgrade_arms_race_flow, stamina_claim_flow, stamina_use_flow, soldier_training_flow, soldier_upgrade_flow, rally_join_flow, healing_flow, bag_flow, gift_box_flow
from flows.tavern_quest_flow import tavern_quest_claim_flow, tavern_scan_flow
from utils.arms_race import get_arms_race_status
from utils.scheduler import get_scheduler

# Import configurable parameters
from config import (
    IDLE_THRESHOLD,
    IDLE_CHECK_INTERVAL,
    USE_BLUESTACKS_IDLE,
    ELITE_ZOMBIE_STAMINA_THRESHOLD,
    ELITE_ZOMBIE_CONSECUTIVE_REQUIRED,
    AFK_REWARDS_COOLDOWN,
    UNION_GIFTS_COOLDOWN,
    UNION_TECHNOLOGY_COOLDOWN,
    BAG_FLOW_COOLDOWN,
    GIFT_BOX_COOLDOWN,
    UNKNOWN_STATE_TIMEOUT,
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
    ARMS_RACE_SOLDIER_TRAINING_ENABLED,
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
)


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

        # BlueStacks-specific idle detection (deprecated - keeping for logging only)
        self.bluestacks_idle_detector = get_bluestacks_idle_detector()

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

        # Tavern scan cooldown - every 30 minutes, requires 5 min idle + TOWN view
        self.last_tavern_scan_time = 0
        self.TAVERN_SCAN_COOLDOWN = TAVERN_SCAN_COOLDOWN

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
            "tavern_scan": {"cooldown": TAVERN_SCAN_COOLDOWN, "idle_required": IDLE_THRESHOLD},
        })

        # Unified stamina validation - ONE system for all stamina-based triggers
        # Tracks last 3 readings, requires all 3 to be valid (0-200) and consistent (diff <= 20)
        self.stamina_history = []  # List of last 3 valid readings
        self.STAMINA_CONSECUTIVE_REQUIRED = ELITE_ZOMBIE_CONSECUTIVE_REQUIRED  # 3

        # Pacific timezone for logging
        self.pacific_tz = pytz.timezone('America/Los_Angeles')

        # UNKNOWN state recovery tracking (from config)
        self.unknown_state_start = None  # When we first entered UNKNOWN state
        self.unknown_state_left_time = None  # When we left UNKNOWN (for hysteresis)
        self.UNKNOWN_STATE_TIMEOUT = UNKNOWN_STATE_TIMEOUT
        self.UNKNOWN_HYSTERESIS = 10  # Seconds out of UNKNOWN before resetting timer

        # Resolution check (proactive, not just on recovery)
        self.RESOLUTION_CHECK_INTERVAL = RESOLUTION_CHECK_INTERVAL
        self.EXPECTED_RESOLUTION = EXPECTED_RESOLUTION

        # Scheduled + continuous idle triggers - DISABLED
        # Hero upgrade now only triggers during Arms Race "Enhance Hero" event (lines 800-816)
        self.scheduled_triggers = []  # Empty - no scheduled triggers
        self.continuous_idle_start = None  # Track when continuous idle began

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

        # Enhance Hero: last N minutes of Enhance Hero, runs once per block
        self.ARMS_RACE_ENHANCE_HERO_ENABLED = ARMS_RACE_ENHANCE_HERO_ENABLED
        self.ENHANCE_HERO_LAST_MINUTES = ARMS_RACE_ENHANCE_HERO_LAST_MINUTES
        self.enhance_hero_last_block_start = None  # Track which block we triggered for

        # Soldier Training: when idle 5+ min, any barrack PENDING during Soldier Training event
        # CONTINUOUSLY checks and upgrades PENDING barracks (no block limitation)
        self.ARMS_RACE_SOLDIER_TRAINING_ENABLED = ARMS_RACE_SOLDIER_TRAINING_ENABLED

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
            'handshake_iter2.png',
            'treasure_map_4k.png',
            'corn_harvest_bubble_4k.png',
            'gold_coin_tight_4k.png',
            'harvest_box_4k.png',
            'iron_bar_tight_4k.png',
            'gem_tight_4k.png',
            'cabbage_tight_4k.png',
            'sword_tight_4k.png',  # Equipment enhancement
            'back_button_4k.png',
            'back_button_light_4k.png',
            'dog_house_4k.png',
            'chest_timer_4k.png',  # AFK rewards
            # View state detector templates
            'world_button_4k.png',
            'town_button_4k.png',
            'town_button_zoomed_out_4k.png',
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

        # ADB
        self.adb = ADBHelper()
        print(f"  Connected to device: {self.adb.device}")

        # Windows screenshot helper
        self.windows_helper = WindowsScreenshotHelper()
        print("  Windows screenshot helper initialized")

        # Stamina OCR (via OCR server)
        self.ocr_client = OCRClient()
        print("  OCR client initialized (uses OCR server)")

        # Matchers
        debug_dir = Path('templates/debug')

        # Matchers use their own default thresholds - edit thresholds in the matcher files
        self.handshake_matcher = HandshakeIconMatcher(debug_dir=debug_dir)
        print(f"  Handshake matcher: {self.handshake_matcher.template_path.name} (threshold={self.handshake_matcher.threshold})")

        self.treasure_matcher = TreasureMapMatcher(debug_dir=debug_dir)
        print(f"  Treasure map matcher: {self.treasure_matcher.template_path.name} (threshold={self.treasure_matcher.threshold})")

        self.corn_matcher = CornHarvestMatcher(debug_dir=debug_dir)
        print(f"  Corn harvest matcher: {self.corn_matcher.template_path.name} (threshold={self.corn_matcher.threshold})")

        self.gold_matcher = GoldCoinMatcher(debug_dir=debug_dir)
        print(f"  Gold coin matcher: {self.gold_matcher.template_path.name} (threshold={self.gold_matcher.threshold})")

        self.harvest_box_matcher = HarvestBoxMatcher(debug_dir=debug_dir)
        print(f"  Harvest box matcher: {self.harvest_box_matcher.template_path.name} (threshold={self.harvest_box_matcher.threshold})")

        self.iron_matcher = IronBarMatcher(debug_dir=debug_dir)
        print(f"  Iron bar matcher: {self.iron_matcher.template_path.name} (threshold={self.iron_matcher.threshold})")

        self.gem_matcher = GemMatcher(debug_dir=debug_dir)
        print(f"  Gem matcher: {self.gem_matcher.template_path.name} (threshold={self.gem_matcher.threshold})")

        self.cabbage_matcher = CabbageMatcher(debug_dir=debug_dir)
        print(f"  Cabbage matcher: {self.cabbage_matcher.template_path.name} (threshold={self.cabbage_matcher.threshold})")

        self.equipment_enhancement_matcher = EquipmentEnhancementMatcher(debug_dir=debug_dir)
        print(f"  Equipment enhancement matcher: {self.equipment_enhancement_matcher.template_path.name} (threshold={self.equipment_enhancement_matcher.threshold})")

        self.hospital_matcher = HospitalStateMatcher()
        print(f"  Hospital state matcher: threshold={self.hospital_matcher.threshold}, consecutive={self.HOSPITAL_CONSECUTIVE_REQUIRED}")

        self.back_button_matcher = BackButtonMatcher(debug_dir=debug_dir)
        print(f"  Back button matcher: {self.back_button_matcher.template_path.name} (threshold={BackButtonMatcher.THRESHOLD})")

        self.dog_house_matcher = DogHouseMatcher(debug_dir=debug_dir)
        print(f"  Dog house matcher: {self.dog_house_matcher.template_path.name} (threshold={self.dog_house_matcher.threshold})")

        self.afk_rewards_matcher = AfkRewardsMatcher(debug_dir=debug_dir)
        print(f"  AFK rewards matcher: {self.afk_rewards_matcher.template_path.name} (threshold={self.afk_rewards_matcher.threshold})")

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

        self.logger.info("STARTUP: Ready")

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

            self.active_flows.add(flow_name)

        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()
        return True

    def _check_ocr_server_health(self):
        """Check if OCR server is healthy, restart if necessary.

        Called periodically and on consecutive OCR failures.
        Returns True if server is healthy (or was restarted), False otherwise.
        """
        if not OCRClient.check_server():
            self.logger.warning("OCR server health check FAILED - attempting restart...")
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

    def _check_resolution(self, iteration: int, idle_seconds: float) -> bool:
        """
        Check resolution periodically when idle and fix if wrong.

        Only checks every RESOLUTION_CHECK_INTERVAL iterations AND when user is idle.
        If resolution is wrong, runs setup_bluestacks.py to fix it.

        Returns True if resolution is OK, False if fix failed.
        """
        # Only check every N iterations
        if iteration % self.RESOLUTION_CHECK_INTERVAL != 0:
            return True  # Not time to check yet

        # Only check when user is idle (no point fixing resolution during active use)
        if idle_seconds < self.IDLE_THRESHOLD:
            return True  # User is active, skip check

        current_res = _get_current_resolution(self.adb)
        if current_res == self.EXPECTED_RESOLUTION:
            self.logger.debug(f"[{iteration}] Resolution check: {current_res} (OK)")
            return True

        self.logger.warning(f"[{iteration}] Resolution wrong: {current_res}, expected {self.EXPECTED_RESOLUTION}")
        self.logger.info(f"[{iteration}] Running setup_bluestacks.py to fix...")
        _run_setup_bluestacks(debug=self.debug)

        # Verify fix
        new_res = _get_current_resolution(self.adb)
        if new_res == self.EXPECTED_RESOLUTION:
            self.logger.info(f"[{iteration}] Resolution fixed: {new_res}")
            return True
        else:
            self.logger.error(f"[{iteration}] Resolution still wrong after fix: {new_res}")
            return False

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

    def run(self):
        """Main detection loop."""
        self.logger.info(f"Starting detection loop (interval: {self.interval}s)")
        self.logger.info("Detecting: Handshake, Treasure map, Corn, Gold, Harvest box, Iron, Gem, Cabbage, Equipment, World")
        print("Press Ctrl+C to stop")
        print("=" * 60)

        iteration = 0
        while True:
            iteration += 1

            try:
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

                # Check IMMEDIATE action icons FIRST (before slow OCR)
                handshake_present, handshake_score = self.handshake_matcher.is_present(frame)
                treasure_present, treasure_score = self.treasure_matcher.is_present(frame)
                harvest_present, harvest_score = self.harvest_box_matcher.is_present(frame)

                # Trigger immediate actions right away (no stamina/idle requirements)
                if handshake_present:
                    self.logger.info(f"[{iteration}] HANDSHAKE detected (diff={handshake_score:.4f})")
                    self._run_flow("handshake", handshake_flow)

                if treasure_present:
                    self.logger.info(f"[{iteration}] TREASURE detected (diff={treasure_score:.4f})")
                    self._run_flow("treasure_map", treasure_map_flow, critical=True)

                if harvest_present:
                    self.logger.info(f"[{iteration}] HARVEST detected (diff={harvest_score:.4f})")
                    self._run_flow("harvest_box", harvest_box_flow)

                # Tavern Quest scheduled claim - check if completion is imminent (within 15 seconds)
                # Critical flow - blocks other daemon actions while polling for claim
                if self.scheduler.is_tavern_completion_imminent():
                    self.logger.info(f"[{iteration}] TAVERN QUEST completion imminent, triggering claim flow")
                    self._run_flow("tavern_quest_claim", tavern_quest_claim_flow, critical=True)

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
                        # Get idle based on config
                        self.bluestacks_idle_detector.update()
                        rally_sys_idle = get_idle_seconds()
                        rally_bs_idle = self.bluestacks_idle_detector.get_bluestacks_idle_seconds()
                        rally_effective_idle = rally_bs_idle if USE_BLUESTACKS_IDLE else rally_sys_idle

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
                            mode_str = " [BOSS MODE]" if in_union_boss_mode else ""
                            self.logger.info(f"[{iteration}] RALLY MARCH button detected at ({march_x}, {march_y}), score={march_score:.4f}{mode_str}")
                            # Click the march button to open Union War panel
                            click_x, click_y = self.rally_march_matcher.get_click_position(march_x, march_y)
                            self.adb.tap(click_x, click_y)
                            self.last_rally_march_click = current_time
                            time.sleep(0.5)  # Brief wait for panel to start loading

                            # Run rally join flow directly (not via _run_flow) to get result
                            try:
                                result = rally_join_flow(self.adb, union_boss_mode=in_union_boss_mode)
                                # Check if Union Boss was joined - enter Union Boss mode
                                if result.get('monster_name') == 'Union Boss':
                                    self.union_boss_mode_until = current_time + UNION_BOSS_MODE_DURATION
                                    self.logger.info(f"[{iteration}] UNION BOSS detected! Entering Union Boss mode for 30 minutes")
                            except Exception as e:
                                self.logger.error(f"[{iteration}] Rally join flow error: {e}")

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

                # For backwards compatibility with flow checks
                world_present = (view_state == "TOWN")
                town_present = (view_state == "WORLD")

                # Get idle time (Windows system-wide) - this is what we use for all checks
                idle_secs = get_idle_seconds()
                idle_str = format_idle_time(idle_secs)

                # Use Windows idle directly for all automation checks
                effective_idle_secs = idle_secs

                # Check resolution periodically when idle (every 100 iterations)
                self._check_resolution(iteration, idle_secs)

                # Get Pacific time for logging
                pacific_time = datetime.now(self.pacific_tz).strftime('%H:%M:%S')

                # Get Arms Race status (computed from UTC time, no screenshot needed)
                arms_race = get_arms_race_status()
                arms_race_event = arms_race['current']
                arms_race_remaining = arms_race['time_remaining']
                arms_race_remaining_mins = int(arms_race_remaining.total_seconds() / 60)

                # Get barracks states
                barracks_state_str = format_barracks_states(frame)

                # Check if VS promotion day is active (for logging)
                vs_promo_active = arms_race['day'] in self.VS_SOLDIER_PROMOTION_DAYS
                vs_indicator = " [VS:Promo]" if vs_promo_active else ""

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
                self.logger.info(f"[{iteration}] {pacific_time} [{view_state}] Stamina:{stamina_str} idle:{idle_str} AR:{arms_race_event[:3]}({arms_race_remaining_mins}m){vs_indicator} Barracks:[{barracks_state_str}] H:{handshake_score:.3f} T:{treasure_score:.3f} C:{corn_score:.3f} G:{gold_score:.3f} HB:{harvest_score:.3f} I:{iron_score:.3f} Gem:{gem_score:.3f} Cab:{cabbage_score:.3f} Eq:{equip_score:.3f} Hosp:{hospital_state_char}({hospital_score:.3f}) AFK:{afk_score:.3f} V:{view_score:.3f} B:{back_score:.3f}")

                # Log detailed barracks scores (s=stopwatch, y=yellow, w=white)
                # Only log when barracks has UNKNOWN or PENDING state (to avoid noise)
                if "?" in barracks_state_str or "P" in barracks_state_str:
                    barracks_detailed = format_barracks_states_detailed(frame)
                    self.logger.info(f"[{iteration}] Barracks detailed: {barracks_detailed}")

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

                # UNKNOWN state recovery - if in UNKNOWN for 1+ min AND idle 5+ min, run return_to_base_view
                if view_state == "UNKNOWN" and effective_idle_secs >= self.IDLE_THRESHOLD:
                    if self.unknown_state_start is not None:
                        unknown_duration = time.time() - self.unknown_state_start
                        if unknown_duration >= self.UNKNOWN_STATE_TIMEOUT:
                            self.logger.info(f"[{iteration}] UNKNOWN RECOVERY: In UNKNOWN for {unknown_duration:.0f}s, idle for {idle_str}, running return_to_base_view...")
                            success = return_to_base_view(self.adb, self.windows_helper, debug=True)
                            if success:
                                self.logger.info(f"[{iteration}] UNKNOWN RECOVERY: Successfully reached base view")
                            else:
                                self.logger.warning(f"[{iteration}] UNKNOWN RECOVERY: Had to restart app")
                            self.unknown_state_start = None  # Reset after recovery attempt
                            self.unknown_state_left_time = None
                            continue  # Skip rest of iteration, start fresh

                # Idle return-to-town - every 5 iterations when idle, return to TOWN
                # Most scanning happens in TOWN view, so we want to be there when idle
                if effective_idle_secs >= self.IDLE_THRESHOLD and not self.critical_flow_active:
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
                    # Not idle or critical flow active - reset counter
                    self.idle_iteration_count = 0

                # =================================================================
                # UNIFIED STAMINA VALIDATION
                # =================================================================
                # ONE system for all stamina-based triggers (elite zombie, beast training, etc.)
                # Requires 3 consecutive valid readings (0-200) with consistency (diff <= 20)
                stamina_valid = stamina is not None and 0 <= stamina <= 200
                if stamina_valid:
                    # Check consistency with previous readings
                    if self.stamina_history and abs(stamina - self.stamina_history[-1]) > 20:
                        # Too much variance from last reading, reset
                        self.stamina_history = [stamina]
                    else:
                        self.stamina_history.append(stamina)
                        if len(self.stamina_history) > self.STAMINA_CONSECUTIVE_REQUIRED:
                            self.stamina_history = self.stamina_history[-self.STAMINA_CONSECUTIVE_REQUIRED:]
                else:
                    self.stamina_history = []  # Reset on invalid reading

                # stamina_confirmed: True if we have 3 consecutive valid, consistent readings
                stamina_confirmed = len(self.stamina_history) >= self.STAMINA_CONSECUTIVE_REQUIRED
                confirmed_stamina = self.stamina_history[-1] if stamina_confirmed else None

                # Elite zombie rally - stamina >= 118 and idle 5+ min
                if stamina_confirmed and confirmed_stamina >= self.ELITE_ZOMBIE_STAMINA_THRESHOLD and effective_idle_secs >= self.IDLE_THRESHOLD:
                    self.logger.info(f"[{iteration}] ELITE ZOMBIE: Stamina={confirmed_stamina} >= {self.ELITE_ZOMBIE_STAMINA_THRESHOLD}, idle={idle_str}, triggering rally...")
                    self._run_flow("elite_zombie", elite_zombie_flow, critical=True)
                    self.stamina_history = []  # Reset after triggering

                # =================================================================
                # ARMS RACE EVENT TRACKING
                # =================================================================
                current_time = time.time()  # Needed for cooldown checks
                # arms_race, arms_race_event, arms_race_remaining, arms_race_remaining_mins already set above

                # Beast Training: Mystic Beast Training last N minutes, stamina >= 20, cooldown
                # Uses the SAME stamina_confirmed from unified validation above
                if (self.ARMS_RACE_BEAST_TRAINING_ENABLED and
                    arms_race_event == "Mystic Beast Training" and
                    arms_race_remaining_mins <= self.ARMS_RACE_BEAST_TRAINING_LAST_MINUTES):

                    # Track which block we're in - reset counters if new block
                    block_start = arms_race['block_start']
                    if self.beast_training_current_block != block_start:
                        self.beast_training_current_block = block_start
                        self.beast_training_rally_count = 0
                        self.beast_training_use_count = 0  # Reset Use count for new block
                        self.logger.info(f"[{iteration}] BEAST TRAINING: New block started, rally count reset to 0, use count reset to 0")

                    # Check if user was idle since block start (required for Use button)
                    time_elapsed_secs = arms_race['time_elapsed'].total_seconds()
                    idle_since_block_start = effective_idle_secs >= time_elapsed_secs

                    # Stamina Claim: if stamina < 60 AND red dot visible, try to claim free stamina
                    # Track if claim was attempted (to know if we should try Use button)
                    claim_triggered = False
                    if (stamina_confirmed and
                        confirmed_stamina < self.STAMINA_CLAIM_THRESHOLD):
                        # Check for red notification dot (indicates free claim available)
                        has_dot, red_count = has_stamina_red_dot(frame, debug=self.debug)
                        if has_dot:
                            self.logger.info(f"[{iteration}] BEAST TRAINING: Stamina {confirmed_stamina} < {self.STAMINA_CLAIM_THRESHOLD}, red dot detected ({red_count} pixels), triggering stamina claim...")
                            claim_triggered = self._run_flow("stamina_claim", stamina_claim_flow)
                        elif self.debug:
                            self.logger.debug(f"[{iteration}] BEAST TRAINING: Stamina {confirmed_stamina} < {self.STAMINA_CLAIM_THRESHOLD}, but no red dot ({red_count} pixels), skipping claim")

                    # Use Button Logic (stamina recovery items):
                    # Conditions: idle entire block, rally count < 15, no Claim available (stamina already at threshold),
                    # stamina < 20, Use clicks < 4, 3 min cooldown
                    # For 3rd+ uses, require being in the last N minutes of the block
                    use_cooldown_ok = (current_time - self.beast_training_last_use_time) >= self.BEAST_TRAINING_USE_COOLDOWN
                    use_allowed_by_time = (self.beast_training_use_count < 2 or
                                           arms_race_remaining_mins <= self.BEAST_TRAINING_USE_LAST_MINUTES)
                    if (self.BEAST_TRAINING_USE_ENABLED and
                        idle_since_block_start and
                        stamina_confirmed and
                        confirmed_stamina < self.BEAST_TRAINING_USE_STAMINA_THRESHOLD and
                        self.beast_training_rally_count < self.BEAST_TRAINING_MAX_RALLIES and
                        self.beast_training_use_count < self.BEAST_TRAINING_USE_MAX and
                        use_cooldown_ok and
                        use_allowed_by_time and
                        not claim_triggered):  # Only use if claim wasn't just triggered
                        # All conditions met - use stamina recovery item
                        self.beast_training_use_count += 1
                        self.logger.info(f"[{iteration}] BEAST TRAINING: Stamina {confirmed_stamina} < {self.BEAST_TRAINING_USE_STAMINA_THRESHOLD}, using recovery item (use #{self.beast_training_use_count}/{self.BEAST_TRAINING_USE_MAX}, rally #{self.beast_training_rally_count}/{self.BEAST_TRAINING_MAX_RALLIES})...")
                        self._run_flow("stamina_use", stamina_use_flow)
                        self.beast_training_last_use_time = current_time

                    # Rally: if stamina >= 20 and cooldown ok
                    rally_cooldown_ok = (current_time - self.beast_training_last_rally) >= self.BEAST_TRAINING_RALLY_COOLDOWN
                    if (stamina_confirmed and
                        confirmed_stamina >= self.BEAST_TRAINING_STAMINA_THRESHOLD and
                        rally_cooldown_ok):
                        self.beast_training_rally_count += 1
                        self.logger.info(f"[{iteration}] BEAST TRAINING: Mystic Beast ({arms_race_remaining_mins}min left), stamina={confirmed_stamina}, triggering rally #{self.beast_training_rally_count}...")
                        # Use elite_zombie_flow with 0 plus clicks
                        import config
                        original_clicks = getattr(config, 'ELITE_ZOMBIE_PLUS_CLICKS', 5)
                        config.ELITE_ZOMBIE_PLUS_CLICKS = 0
                        self._run_flow("beast_training", elite_zombie_flow, critical=True)
                        config.ELITE_ZOMBIE_PLUS_CLICKS = original_clicks
                        self.beast_training_last_rally = current_time
                        self.stamina_history = []  # Reset after triggering

                # Enhance Hero: last N minutes, runs once per block
                # Requires user to be idle since the START of the Enhance Hero block
                if (self.ARMS_RACE_ENHANCE_HERO_ENABLED and
                    arms_race_event == "Enhance Hero" and
                    arms_race_remaining_mins <= self.ENHANCE_HERO_LAST_MINUTES):
                    # Check if we already triggered for this block
                    block_start = arms_race['block_start']
                    if self.enhance_hero_last_block_start != block_start:
                        # User must be idle since the START of the Enhance Hero block
                        # (not just idle for 5 minutes)
                        time_elapsed_secs = arms_race['time_elapsed'].total_seconds()
                        if effective_idle_secs >= time_elapsed_secs:
                            idle_mins = int(idle_secs / 60)
                            elapsed_mins = int(time_elapsed_secs / 60)
                            self.logger.info(f"[{iteration}] ENHANCE HERO: Last {arms_race_remaining_mins}min of Enhance Hero, idle {idle_mins}min >= {elapsed_mins}min since block start, triggering hero upgrade flow...")
                            self._run_flow("enhance_hero_arms_race", hero_upgrade_arms_race_flow)
                            self.enhance_hero_last_block_start = block_start

                # Soldier Training: during Soldier Training event OR VS promotion day, idle 5+ min
                # Requires TOWN view and dog house aligned (same as harvest conditions)
                # CONTINUOUSLY checks for READY/PENDING barracks and upgrades them (no block limitation)
                # VS override: On VS_SOLDIER_PROMOTION_DAYS, promotions run ALL DAY regardless of event
                is_vs_promotion_day = arms_race['day'] in self.VS_SOLDIER_PROMOTION_DAYS
                is_soldier_event = arms_race_event == "Soldier Training"

                if (self.ARMS_RACE_SOLDIER_TRAINING_ENABLED and
                    (is_soldier_event or is_vs_promotion_day) and
                    effective_idle_secs >= self.IDLE_THRESHOLD):
                    trigger_reason = "VS Day" if is_vs_promotion_day and not is_soldier_event else "Soldier Training event"
                    self.logger.debug(f"[{iteration}] SOLDIER: Outer conditions PASS (reason={trigger_reason}, day={arms_race['day']}, event={arms_race_event}, idle={idle_secs}s)")

                    # Get current barracks states and update history
                    from utils.barracks_state_matcher import BarrackState
                    states = self.barracks_matcher.get_all_states(frame)

                    # Update per-barrack state history
                    for i, (state, _) in enumerate(states):
                        self.barracks_state_history[i].append(state)
                        if len(self.barracks_state_history[i]) > self.BARRACKS_CONSECUTIVE_REQUIRED:
                            self.barracks_state_history[i].pop(0)

                    # Validate each barrack with 60% rule (allows ? mixed with consistent letter)
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
                                    click_x, click_y = get_barrack_click_position(idx)
                                    self.logger.info(f"[{iteration}] SOLDIER: Collecting from barrack {idx+1} at ({click_x}, {click_y})")
                                    self.adb.tap(click_x, click_y)
                                    time.sleep(0.5)
                                    # Clear history for this barrack after collecting
                                    self.barracks_state_history[idx] = []
                                # Wait for state change after collecting
                                time.sleep(1.0)

                            # Then upgrade each validated PENDING barrack
                            upgrades = 0
                            for idx in pending_indices:
                                self.logger.info(f"[{iteration}] SOLDIER: Processing barrack {idx+1}...")

                                # Click to open this barrack's panel
                                click_x, click_y = get_barrack_click_position(idx)
                                self.logger.info(f"[{iteration}] SOLDIER: Clicking barrack {idx+1} at ({click_x}, {click_y})")
                                self.adb.tap(click_x, click_y)
                                time.sleep(1.0)

                                # Run upgrade flow (assumes panel is open)
                                success = soldier_upgrade_flow(self.adb, barrack_index=idx, debug=True)
                                if success:
                                    upgrades += 1
                                    self.logger.info(f"[{iteration}] SOLDIER: Barrack {idx+1} upgrade complete")
                                    # Clear history for this barrack after upgrade
                                    self.barracks_state_history[idx] = []
                                else:
                                    self.logger.info(f"[{iteration}] SOLDIER: Barrack {idx+1} upgrade failed")

                                time.sleep(0.5)

                            self.logger.info(f"[{iteration}] SOLDIER UPGRADE: Completed {upgrades}/{pending_count} upgrade(s)")

                # Harvest actions: require TOWN view, 5min idle, and dog house aligned
                # Check alignment once for all harvest actions
                harvest_idle_ok = effective_idle_secs >= self.IDLE_THRESHOLD
                if not harvest_idle_ok:
                    self.logger.debug(f"[{iteration}] HARVEST: Blocked - idle time {idle_secs}s < threshold {self.IDLE_THRESHOLD}s")
                harvest_aligned = False
                if harvest_idle_ok and world_present:
                    is_aligned, dog_score = self.dog_house_matcher.is_aligned(frame)
                    harvest_aligned = is_aligned
                    if not is_aligned:
                        self.logger.debug(f"[{iteration}] HARVEST: Blocked - misaligned (score={dog_score:.4f}, threshold={self.dog_house_matcher.threshold})")

                # Corn, Gold, Iron, Gem, Cabbage, Equip only activate when idle 5+ min and aligned
                if corn_present and world_present and harvest_idle_ok and harvest_aligned:
                    self.logger.info(f"[{iteration}] CORN: Triggering harvest flow (score={corn_score:.4f})")
                    self._run_flow("corn_harvest", corn_harvest_flow)

                if gold_present and world_present and harvest_idle_ok and harvest_aligned:
                    self.logger.info(f"[{iteration}] GOLD detected (diff={gold_score:.4f})")
                    self._run_flow("gold_coin", gold_coin_flow)

                if iron_present and world_present and harvest_idle_ok and harvest_aligned:
                    self.logger.info(f"[{iteration}] IRON detected (diff={iron_score:.4f})")
                    self._run_flow("iron_bar", iron_bar_flow)

                if gem_present and world_present and harvest_idle_ok and harvest_aligned:
                    self.logger.info(f"[{iteration}] GEM detected (diff={gem_score:.4f})")
                    self._run_flow("gem", gem_flow)

                if cabbage_present and world_present and harvest_idle_ok and harvest_aligned:
                    self.logger.info(f"[{iteration}] CABBAGE detected (diff={cabbage_score:.4f})")
                    self._run_flow("cabbage", cabbage_flow)

                if equip_present and world_present and harvest_idle_ok and harvest_aligned:
                    self.logger.info(f"[{iteration}] EQUIPMENT ENHANCEMENT detected (diff={equip_score:.4f})")
                    self._run_flow("equipment_enhancement", equipment_enhancement_flow)

                # Hospital state detection with consecutive frame validation
                # Update hospital state history (same pattern as barracks)
                if world_present and harvest_aligned:
                    self.hospital_state_history.append(hospital_state)
                    if len(self.hospital_state_history) > self.HOSPITAL_CONSECUTIVE_REQUIRED:
                        self.hospital_state_history.pop(0)

                    # Check if we have enough consecutive readings of an actionable state
                    if len(self.hospital_state_history) >= self.HOSPITAL_CONSECUTIVE_REQUIRED and harvest_idle_ok:
                        # Count states in history
                        help_ready_count = sum(1 for s in self.hospital_state_history if s == HospitalState.HELP_READY)
                        healing_count = sum(1 for s in self.hospital_state_history if s == HospitalState.HEALING)
                        wounded_count = sum(1 for s in self.hospital_state_history if s == HospitalState.SOLDIERS_WOUNDED)

                        # HELP_READY: Just click to request ally help (no panel needed)
                        if help_ready_count == self.HOSPITAL_CONSECUTIVE_REQUIRED:
                            self.logger.info(f"[{iteration}] HOSPITAL HELP_READY confirmed ({help_ready_count}/{self.HOSPITAL_CONSECUTIVE_REQUIRED} consecutive) - requesting ally help")
                            click_x, click_y = self.hospital_matcher.get_click_position()
                            self.adb.tap(click_x, click_y)
                            # Clear history after clicking
                            self.hospital_state_history = []

                        # HEALING: Click to open panel, run healing flow
                        elif healing_count == self.HOSPITAL_CONSECUTIVE_REQUIRED:
                            self.logger.info(f"[{iteration}] HOSPITAL HEALING confirmed ({healing_count}/{self.HOSPITAL_CONSECUTIVE_REQUIRED} consecutive)")
                            # Click hospital building to open panel
                            click_x, click_y = self.hospital_matcher.get_click_position()
                            self.adb.tap(click_x, click_y)
                            time.sleep(1.5)  # Wait for panel to open
                            # Run healing flow (panel should now be open)
                            self._run_flow("healing", healing_flow)
                            # Clear history after triggering
                            self.hospital_state_history = []

                        # SOLDIERS_WOUNDED: Click to open panel, run healing flow
                        elif wounded_count == self.HOSPITAL_CONSECUTIVE_REQUIRED:
                            self.logger.info(f"[{iteration}] HOSPITAL SOLDIERS_WOUNDED confirmed ({wounded_count}/{self.HOSPITAL_CONSECUTIVE_REQUIRED} consecutive)")
                            # Click hospital building to open panel
                            click_x, click_y = self.hospital_matcher.get_click_position()
                            self.adb.tap(click_x, click_y)
                            time.sleep(1.5)  # Wait for panel to open
                            # Run healing flow (panel should now be open)
                            self._run_flow("healing", healing_flow)
                            # Clear history after triggering
                            self.hospital_state_history = []
                else:
                    # Not in TOWN or not aligned - reset hospital state history
                    if self.hospital_state_history:
                        self.hospital_state_history = []

                # Barracks: Check for READY/PENDING barracks to collect/train soldiers (non-Arms Race ONLY)
                # During Arms Race "Soldier Training" event or VS promotion days, we use soldier_upgrade_flow instead
                # No cooldown - just requires TOWN view, alignment, and idle
                is_arms_race_soldier_active = arms_race_event == "Soldier Training" or arms_race['day'] in self.VS_SOLDIER_PROMOTION_DAYS
                if world_present and harvest_aligned and harvest_idle_ok and not is_arms_race_soldier_active:
                    # Get barracks states
                    from utils.barracks_state_matcher import BarrackState
                    states = self.barracks_matcher.get_all_states(frame)
                    ready_count = sum(1 for state, _ in states if state == BarrackState.READY)
                    pending_count = sum(1 for state, _ in states if state == BarrackState.PENDING)

                    if ready_count > 0 or pending_count > 0:
                        self.logger.info(f"[{iteration}] BARRACKS: {ready_count} READY, {pending_count} PENDING barrack(s), triggering soldier training...")
                        self._run_flow("soldier_training", soldier_training_flow)

                # AFK rewards: requires AFK icon detected + harvest conditions + cooldown
                if afk_present and world_present and harvest_aligned:
                    if self.scheduler.is_flow_ready("afk_rewards", idle_seconds=effective_idle_secs):
                        self.logger.info(f"[{iteration}] AFK REWARDS detected (diff={afk_score:.4f})")
                        self._run_flow("afk_rewards", afk_rewards_flow)
                        self.scheduler.record_flow_run("afk_rewards")

                # Union gifts: 1 hour cooldown
                if self.scheduler.is_flow_ready("union_gifts", idle_seconds=effective_idle_secs):
                    self.logger.info(f"[{iteration}] UNION GIFTS: idle={idle_str}, triggering flow...")
                    self._run_flow("union_gifts", union_gifts_flow)
                    self.scheduler.record_flow_run("union_gifts")

                # Union technology: 1 hour cooldown
                if self.scheduler.is_flow_ready("union_technology", idle_seconds=effective_idle_secs):
                    self.logger.info(f"[{iteration}] UNION TECHNOLOGY: idle={idle_str}, triggering flow...")
                    self._run_flow("union_technology", union_technology_flow)
                    self.scheduler.record_flow_run("union_technology")

                # VS Day 7 chest surprise: trigger bag flow at 10, 5, 1 min remaining
                # This opens level chests right before VS day ends to surprise competitors
                vs_day = arms_race['day']
                vs_minutes_remaining = arms_race.get('minutes_remaining', 999)

                # Reset checkpoint tracking when day changes
                if vs_day != self.vs_chest_last_day:
                    self.vs_chest_triggered.clear()
                    self.vs_chest_last_day = vs_day

                # On Day 7, check if we should trigger bag flow at checkpoint
                if vs_day == 7 and effective_idle_secs >= self.IDLE_THRESHOLD:
                    for checkpoint in self.VS_CHEST_CHECKPOINTS:
                        if vs_minutes_remaining <= checkpoint and checkpoint not in self.vs_chest_triggered:
                            self.logger.info(f"[{iteration}] VS CHEST SURPRISE: Day 7, {vs_minutes_remaining:.1f} min left (checkpoint {checkpoint}), triggering bag flow...")
                            self._run_flow("bag", bag_flow, critical=True)
                            self.vs_chest_triggered.add(checkpoint)
                            break  # Only trigger once per iteration

                # Bag flow: idle threshold, cooldown (navigates to TOWN itself)
                if self.scheduler.is_flow_ready("bag_flow", idle_seconds=effective_idle_secs):
                    self.logger.info(f"[{iteration}] BAG FLOW: idle={idle_str}, triggering flow...")
                    self._run_flow("bag", bag_flow, critical=True)
                    self.scheduler.record_flow_run("bag_flow")

                # Tavern scan: 5 min idle, 30 min cooldown (claims completed quests + updates schedule)
                if self.scheduler.is_flow_ready("tavern_scan", idle_seconds=effective_idle_secs):
                    self.logger.info(f"[{iteration}] TAVERN SCAN: idle={idle_str}, triggering scan flow...")
                    self._run_flow("tavern_scan", tavern_scan_flow)
                    self.scheduler.record_flow_run("tavern_scan")

                # Gift box flow: requires WORLD view (town_present means we're in WORLD), 5 min idle, 1 hour cooldown
                if town_present and self.scheduler.is_flow_ready("gift_box", idle_seconds=effective_idle_secs):
                    self.logger.info(f"[{iteration}] GIFT BOX: idle={idle_str}, triggering flow...")
                    self._run_flow("gift_box", gift_box_flow)
                    self.scheduler.record_flow_run("gift_box")

                # Scheduled + continuous idle triggers (e.g., fing_hero at 2 AM Pacific)
                # Track continuous idle start time (using BlueStacks-specific idle)
                if effective_idle_secs >= 5:  # Consider idle if no input for 5+ seconds
                    if self.continuous_idle_start is None:
                        self.continuous_idle_start = time.time()
                else:
                    self.continuous_idle_start = None  # Reset on activity

                # Check scheduled triggers
                now_pacific = datetime.now(self.pacific_tz)
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
                                        self.logger.info(f"[{iteration}] SCHEDULED TRIGGER: {trigger['name']} at {trigger['trigger_time']}, idle duration={idle_duration/3600:.2f}h >= {trigger['required_idle_seconds']/3600:.2f}h required")
                                        self._run_flow(trigger['name'], trigger['flow'])
                                        trigger['last_triggered_date'] = now_pacific.date()
                                    else:
                                        self.logger.debug(f"[{iteration}] SCHEDULED TRIGGER: {trigger['name']} - conditions not met (view={view_state}, aligned={harvest_aligned})")

                # Log view state for debugging
                if view_state == "TOWN":
                    self.logger.info(f"[{iteration}] View: TOWN (world button visible, score={view_score:.4f})")
                elif view_state == "WORLD":
                    self.logger.info(f"[{iteration}] View: WORLD (town button visible, score={view_score:.4f})")

            except Exception as e:
                self.logger.error(f"[{iteration}] ERROR: {e}")

            time.sleep(self.interval)


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

    args = parser.parse_args()

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
        print("\n\nStopped by user")
        stdout_file.close()
        sys.exit(0)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        stdout_file.close()
        sys.exit(1)


if __name__ == "__main__":
    main()
