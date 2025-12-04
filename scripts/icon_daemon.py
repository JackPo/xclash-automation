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
- Beast Training: During Mystic Beast last hour, if stamina >= 20 (3 consecutive reads),
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
from utils.back_button_matcher import BackButtonMatcher
from utils.afk_rewards_matcher import AfkRewardsMatcher
from utils.windows_screenshot_helper import WindowsScreenshotHelper
from utils.idle_detector import get_idle_seconds, format_idle_time
from utils.view_state_detector import detect_view, go_to_town, go_to_world, ViewState
from utils.dog_house_matcher import DogHouseMatcher
from utils.return_to_base_view import return_to_base_view
from utils.barracks_state_matcher import BarracksStateMatcher, format_barracks_states
from utils.stamina_red_dot_detector import has_stamina_red_dot
from utils.rally_march_button_matcher import RallyMarchButtonMatcher

from datetime import time as dt_time
from flows import handshake_flow, treasure_map_flow, corn_harvest_flow, gold_coin_flow, harvest_box_flow, iron_bar_flow, gem_flow, cabbage_flow, equipment_enhancement_flow, elite_zombie_flow, afk_rewards_flow, union_gifts_flow, hero_upgrade_arms_race_flow, stamina_claim_flow, stamina_use_flow, soldier_training_flow, soldier_upgrade_flow, rally_join_flow
from utils.arms_race import get_arms_race_status

# Import configurable parameters
from config import (
    IDLE_THRESHOLD,
    IDLE_CHECK_INTERVAL,
    ELITE_ZOMBIE_STAMINA_THRESHOLD,
    ELITE_ZOMBIE_CONSECUTIVE_REQUIRED,
    AFK_REWARDS_COOLDOWN,
    UNION_GIFTS_COOLDOWN,
    SOLDIER_TRAINING_COOLDOWN,
    UNION_GIFTS_IDLE_THRESHOLD,
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
    # Rally joining
    RALLY_JOIN_ENABLED,
    RALLY_MARCH_BUTTON_COOLDOWN,
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

        # Elite zombie rally - stamina threshold (from config)
        self.ELITE_ZOMBIE_STAMINA_THRESHOLD = ELITE_ZOMBIE_STAMINA_THRESHOLD

        # AFK rewards cooldown - once per hour (from config)
        self.last_afk_rewards_time = 0
        self.AFK_REWARDS_COOLDOWN = AFK_REWARDS_COOLDOWN

        # Union gifts cooldown - once per hour, requires 20 min idle (from config)
        self.last_union_gifts_time = 0
        self.UNION_GIFTS_COOLDOWN = UNION_GIFTS_COOLDOWN
        self.UNION_GIFTS_IDLE_THRESHOLD = UNION_GIFTS_IDLE_THRESHOLD

        # Soldier training cooldown - once per 5 minutes
        self.last_soldier_training_time = 0
        self.SOLDIER_TRAINING_COOLDOWN = SOLDIER_TRAINING_COOLDOWN

        # Unified stamina validation - ONE system for all stamina-based triggers
        # Tracks last 3 readings, requires all 3 to be valid (0-200) and consistent (diff <= 20)
        self.stamina_history = []  # List of last 3 valid readings
        self.STAMINA_CONSECUTIVE_REQUIRED = ELITE_ZOMBIE_CONSECUTIVE_REQUIRED  # 3

        # Pacific timezone for logging
        self.pacific_tz = pytz.timezone('America/Los_Angeles')

        # UNKNOWN state recovery tracking (from config)
        self.unknown_state_start = None  # When we first entered UNKNOWN state
        self.UNKNOWN_STATE_TIMEOUT = UNKNOWN_STATE_TIMEOUT

        # Scheduled + continuous idle triggers
        # Pattern: "At scheduled time X, if user was continuously idle for Y duration before that time, trigger"
        self.scheduled_triggers = [
            {
                'name': 'hero_upgrade_arms_race',
                'trigger_time': dt_time(2, 0),  # 2:00 AM Pacific
                'required_idle_seconds': 3 * 3600 + 45 * 60,  # 3h 45m = 13500s
                'flow': hero_upgrade_arms_race_flow,
                'last_triggered_date': None,  # Track to prevent double-trigger same day
            }
        ]
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

        # Setup logging
        self.log_dir = Path('logs')
        self.log_dir.mkdir(exist_ok=True)
        self.log_file = self.log_dir / f"daemon_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

        # Configure logging
        log_level = logging.DEBUG if debug else logging.INFO
        logging.basicConfig(
            level=log_level,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(self.log_file),
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

        # Startup recovery - return_to_base_view handles EVERYTHING:
        # - Checks if app is running, starts it if not
        # - Runs setup_bluestacks.py
        # - Gets to TOWN/WORLD via back button clicking
        # - Restarts and retries if stuck
        self.logger.info("STARTUP: Running recovery to ensure ready state...")
        return_to_base_view(self.adb, self.windows_helper, debug=True)
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
                    self.logger.debug(f"[{iteration}] CRITICAL FLOW ACTIVE: {self.critical_flow_name} - skipping daemon checks")
                    time.sleep(self.DAEMON_INTERVAL)
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
                        idle_secs = get_idle_seconds()
                        rally_cooldown_elapsed = (current_time - self.last_rally_march_click) >= RALLY_MARCH_BUTTON_COOLDOWN

                        rally_idle_ok = idle_secs >= IDLE_THRESHOLD
                        rally_view_ok = view_state in [ViewState.TOWN, ViewState.WORLD]

                        if rally_idle_ok and rally_view_ok and rally_cooldown_elapsed:
                            self.logger.info(f"[{iteration}] RALLY MARCH button detected at ({march_x}, {march_y}), score={march_score:.4f}")
                            # Click the march button to open Union War panel
                            click_x, click_y = self.rally_march_matcher.get_click_position(march_x, march_y)
                            self.adb.tap(click_x, click_y)
                            self.last_rally_march_click = current_time
                            time.sleep(0.5)  # Brief wait for panel to start loading
                            # Then trigger rally join flow
                            self._run_flow("rally_join", rally_join_flow)

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
                afk_present, afk_score = self.afk_rewards_matcher.is_present(frame)
                # Get view state using view_state_detector
                view_state_enum, view_score = detect_view(frame)
                view_state = view_state_enum.value.upper()  # "TOWN", "WORLD", "CHAT", "UNKNOWN"
                back_present, back_score = self.back_button_matcher.is_present(frame)

                # For backwards compatibility with flow checks
                world_present = (view_state == "TOWN")
                town_present = (view_state == "WORLD")

                # Get idle time
                idle_secs = get_idle_seconds()
                idle_str = format_idle_time(idle_secs)

                # Get Pacific time for logging
                pacific_time = datetime.now(self.pacific_tz).strftime('%H:%M:%S')

                # Get Arms Race status (computed from UTC time, no screenshot needed)
                arms_race = get_arms_race_status()
                arms_race_event = arms_race['current']
                arms_race_remaining = arms_race['time_remaining']
                arms_race_remaining_mins = int(arms_race_remaining.total_seconds() / 60)

                # Get barracks states
                barracks_state_str = format_barracks_states(frame)

                # Always print scores to stdout with view state, stamina, barracks, and arms race
                print(f"[{iteration}] {pacific_time} [{view_state}] Stamina:{stamina_str} idle:{idle_str} AR:{arms_race_event[:3]}({arms_race_remaining_mins}m) Barracks:[{barracks_state_str}] H:{handshake_score:.3f} T:{treasure_score:.3f} C:{corn_score:.3f} G:{gold_score:.3f} HB:{harvest_score:.3f} I:{iron_score:.3f} Gem:{gem_score:.3f} Cab:{cabbage_score:.3f} Eq:{equip_score:.3f} AFK:{afk_score:.3f} V:{view_score:.3f} B:{back_score:.3f}")

                # Track UNKNOWN state duration
                if view_state == "UNKNOWN":
                    if self.unknown_state_start is None:
                        self.unknown_state_start = time.time()
                        self.logger.debug(f"[{iteration}] Entered UNKNOWN state")
                else:
                    if self.unknown_state_start is not None:
                        self.logger.debug(f"[{iteration}] Left UNKNOWN state (now {view_state})")
                    self.unknown_state_start = None

                # UNKNOWN state recovery - if in UNKNOWN for 1+ min AND idle 5+ min, run return_to_base_view
                if view_state == "UNKNOWN" and idle_secs >= self.IDLE_THRESHOLD:
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
                            continue  # Skip rest of iteration, start fresh

                # Idle recovery - every 5 min when idle 5+ min, go to town and ensure alignment
                if idle_secs >= self.IDLE_THRESHOLD:
                    current_time = time.time()
                    if current_time - self.last_idle_check_time >= self.IDLE_CHECK_INTERVAL:
                        self.last_idle_check_time = current_time

                        # Not in town - navigate there (handles CHAT, WORLD)
                        if view_state != "TOWN" and view_state != "UNKNOWN":
                            self.logger.info(f"[{iteration}] IDLE RECOVERY: In {view_state}, navigating to TOWN...")
                            self._switch_to_town()
                        elif view_state == "TOWN":
                            # In TOWN - check if dog house is aligned
                            is_aligned, dog_score = self.dog_house_matcher.is_aligned(frame)
                            if not is_aligned:
                                self.logger.info(f"[{iteration}] IDLE RECOVERY: Town view misaligned (dog_score={dog_score:.4f}), resetting view...")
                                # Go to WORLD then back to TOWN to reset alignment
                                go_to_world(self.adb, debug=False)
                                time.sleep(1.0)
                                go_to_town(self.adb, debug=False)
                                self.logger.info(f"[{iteration}] IDLE RECOVERY: View reset complete")

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
                if stamina_confirmed and confirmed_stamina >= self.ELITE_ZOMBIE_STAMINA_THRESHOLD and idle_secs >= self.IDLE_THRESHOLD:
                    self.logger.info(f"[{iteration}] ELITE ZOMBIE: Stamina={confirmed_stamina} >= {self.ELITE_ZOMBIE_STAMINA_THRESHOLD}, idle={idle_str}, triggering rally...")
                    self._run_flow("elite_zombie", elite_zombie_flow, critical=True)
                    self.stamina_history = []  # Reset after triggering

                # =================================================================
                # ARMS RACE EVENT TRACKING
                # =================================================================
                current_time = time.time()  # Needed for cooldown checks
                # arms_race, arms_race_event, arms_race_remaining, arms_race_remaining_mins already set above

                # Beast Training: Mystic Beast last N minutes, stamina >= 20, cooldown
                # Uses the SAME stamina_confirmed from unified validation above
                if (self.ARMS_RACE_BEAST_TRAINING_ENABLED and
                    arms_race_event == "Mystic Beast" and
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
                    idle_since_block_start = idle_secs >= time_elapsed_secs

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
                        if idle_secs >= time_elapsed_secs:
                            idle_mins = int(idle_secs / 60)
                            elapsed_mins = int(time_elapsed_secs / 60)
                            self.logger.info(f"[{iteration}] ENHANCE HERO: Last {arms_race_remaining_mins}min of Enhance Hero, idle {idle_mins}min >= {elapsed_mins}min since block start, triggering hero upgrade flow...")
                            self._run_flow("enhance_hero_arms_race", hero_upgrade_arms_race_flow)
                            self.enhance_hero_last_block_start = block_start

                # Soldier Training: during Soldier Training event, idle 5+ min, any barrack PENDING
                # Requires TOWN view and dog house aligned (same as harvest conditions)
                # CONTINUOUSLY checks for PENDING barracks and promotes them (no block limitation)
                if (self.ARMS_RACE_SOLDIER_TRAINING_ENABLED and
                    arms_race_event == "Soldier Training" and
                    idle_secs >= self.IDLE_THRESHOLD):
                    # Check for PENDING barracks (barracks states already computed in main loop)
                    from utils.barracks_state_matcher import BarrackState
                    states = self.barracks_matcher.get_all_states(frame)
                    pending_count = sum(1 for state, _ in states if state == BarrackState.PENDING)

                    if pending_count > 0 and world_present:
                        # Check alignment
                        is_aligned, dog_score = self.dog_house_matcher.is_aligned(frame)
                        if is_aligned:
                            idle_mins = int(idle_secs / 60)
                            self.logger.info(f"[{iteration}] SOLDIER UPGRADE: Soldier Training event, idle {idle_mins}min, {pending_count} PENDING barrack(s), triggering soldier upgrade...")
                            # Import the upgrade_all_pending_barracks function
                            from scripts.flows.soldier_upgrade_flow import upgrade_all_pending_barracks
                            # Run upgrade for all pending barracks (NOT as a threaded flow - blocks until done)
                            upgrades = upgrade_all_pending_barracks(self.adb, debug=True)
                            self.logger.info(f"[{iteration}] SOLDIER UPGRADE: Completed {upgrades} upgrade(s)")

                # Harvest actions: require TOWN view, 5min idle, and dog house aligned
                # Check alignment once for all harvest actions
                harvest_idle_ok = idle_secs >= self.IDLE_THRESHOLD
                harvest_aligned = False
                if harvest_idle_ok and world_present:
                    is_aligned, dog_score = self.dog_house_matcher.is_aligned(frame)
                    harvest_aligned = is_aligned

                # Corn, Gold, Iron, Gem, Cabbage, Equip only activate when idle 5+ min and aligned
                if corn_present and world_present and harvest_idle_ok and harvest_aligned:
                    self.logger.info(f"[{iteration}] CORN detected (diff={corn_score:.4f})")
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

                # Barracks: Check for READY barracks to collect soldiers
                # Requires TOWN view, alignment, and 5-minute cooldown
                soldier_cooldown_ok = (current_time - self.last_soldier_training_time) >= self.SOLDIER_TRAINING_COOLDOWN
                if world_present and harvest_idle_ok and harvest_aligned and soldier_cooldown_ok:
                    # Get barracks states
                    from utils.barracks_state_matcher import BarrackState
                    states = self.barracks_matcher.get_all_states(frame)
                    ready_count = sum(1 for state, _ in states if state == BarrackState.READY)

                    if ready_count > 0:
                        self.logger.info(f"[{iteration}] BARRACKS: {ready_count} READY barrack(s) detected, triggering soldier collection...")
                        self.last_soldier_training_time = current_time
                        self._run_flow("soldier_training", soldier_training_flow)

                # AFK rewards: requires all harvest conditions + 1 hour cooldown
                current_time = time.time()
                afk_cooldown_ok = (current_time - self.last_afk_rewards_time) >= self.AFK_REWARDS_COOLDOWN
                if afk_present and world_present and harvest_idle_ok and harvest_aligned and afk_cooldown_ok:
                    self.logger.info(f"[{iteration}] AFK REWARDS detected (diff={afk_score:.4f})")
                    self.last_afk_rewards_time = current_time
                    self._run_flow("afk_rewards", afk_rewards_flow)

                # Union gifts: requires TOWN view, 20 min idle, dog house aligned, 1 hour cooldown
                # This is a time-based trigger (no icon detection needed)
                union_idle_ok = idle_secs >= self.UNION_GIFTS_IDLE_THRESHOLD
                union_cooldown_ok = (current_time - self.last_union_gifts_time) >= self.UNION_GIFTS_COOLDOWN
                if world_present and union_idle_ok and harvest_aligned and union_cooldown_ok:
                    self.logger.info(f"[{iteration}] UNION GIFTS: idle={idle_str}, triggering flow...")
                    self.last_union_gifts_time = current_time
                    self._run_flow("union_gifts", union_gifts_flow)

                # Scheduled + continuous idle triggers (e.g., fing_hero at 2 AM Pacific)
                # Track continuous idle start time
                if idle_secs >= 5:  # Consider idle if no input for 5+ seconds
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

    daemon = IconDaemon(interval=args.interval, debug=args.debug)

    try:
        daemon.initialize()
        daemon.run()
    except KeyboardInterrupt:
        print("\n\nStopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
