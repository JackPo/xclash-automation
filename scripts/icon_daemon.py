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
- Enhance Hero: During Enhance Hero last 20 minutes, triggers hero_upgrade_arms_race_flow
  once per event block.

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
from utils.qwen_ocr import QwenOCR
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

from datetime import time as dt_time
from flows import handshake_flow, treasure_map_flow, corn_harvest_flow, gold_coin_flow, harvest_box_flow, iron_bar_flow, gem_flow, cabbage_flow, equipment_enhancement_flow, elite_zombie_flow, afk_rewards_flow, union_gifts_flow, hero_upgrade_arms_race_flow
from utils.arms_race import get_arms_race_status

# Import configurable parameters
from config import (
    IDLE_THRESHOLD,
    IDLE_CHECK_INTERVAL,
    ELITE_ZOMBIE_STAMINA_THRESHOLD,
    ELITE_ZOMBIE_CONSECUTIVE_REQUIRED,
    AFK_REWARDS_COOLDOWN,
    UNION_GIFTS_COOLDOWN,
    UNION_GIFTS_IDLE_THRESHOLD,
    UNKNOWN_STATE_TIMEOUT,
    STAMINA_REGION,
)


class IconDaemon:
    """
    Daemon that detects icons and triggers non-blocking flows.
    """

    def __init__(self, interval: float = 3.0, debug: bool = False):
        self.interval = interval
        self.debug = debug
        self.adb = None
        self.windows_helper = None

        # Stamina OCR (Qwen2.5-VL-3B)
        self.qwen_ocr = None
        self.STAMINA_REGION = STAMINA_REGION  # From config

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

        # Track active flows to prevent re-triggering
        self.active_flows = set()
        self.flow_lock = threading.Lock()

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

        # Elite zombie - require consecutive valid stamina readings (from config)
        self.elite_zombie_consecutive_count = 0
        self.ELITE_ZOMBIE_CONSECUTIVE_REQUIRED = ELITE_ZOMBIE_CONSECUTIVE_REQUIRED

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

        # Arms Race event tracking
        # Beast Training: Mystic Beast last hour, stamina >= 20, 90s between rallies
        self.BEAST_TRAINING_STAMINA_THRESHOLD = 20
        self.BEAST_TRAINING_RALLY_COOLDOWN = 90  # seconds between rallies
        self.beast_training_last_rally = 0
        self.beast_training_consecutive_reads = 0
        self.beast_training_last_stamina = None

        # Enhance Hero: last 20 minutes of Enhance Hero, runs once per block
        self.ENHANCE_HERO_LAST_MINUTES = 20
        self.enhance_hero_last_block_start = None  # Track which block we triggered for

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

        # ADB
        self.adb = ADBHelper()
        print(f"  Connected to device: {self.adb.device}")

        # Windows screenshot helper
        self.windows_helper = WindowsScreenshotHelper()
        print("  Windows screenshot helper initialized")

        # Stamina OCR (Qwen2.5-VL-3B on GPU)
        self.qwen_ocr = QwenOCR()
        print("  Qwen OCR initialized (GPU)")

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

        # Startup recovery - return_to_base_view handles EVERYTHING:
        # - Checks if app is running, starts it if not
        # - Runs setup_bluestacks.py
        # - Gets to TOWN/WORLD via back button clicking
        # - Restarts and retries if stuck
        self.logger.info("STARTUP: Running recovery to ensure ready state...")
        return_to_base_view(self.adb, self.windows_helper, debug=True)
        self.logger.info("STARTUP: Ready")

    def _run_flow(self, flow_name: str, flow_func):
        """
        Run a flow in a thread-safe way.

        Args:
            flow_name: Identifier for the flow
            flow_func: Function to execute (takes adb as argument)
        """
        def wrapper():
            try:
                self.logger.info(f"FLOW START: {flow_name}")
                flow_func(self.adb)
                self.logger.info(f"FLOW END: {flow_name}")
            except Exception as e:
                self.logger.error(f"FLOW ERROR: {flow_name} - {e}")
            finally:
                with self.flow_lock:
                    self.active_flows.discard(flow_name)

        with self.flow_lock:
            if flow_name in self.active_flows:
                self.logger.debug(f"SKIP: {flow_name} already running")
                return False

            self.active_flows.add(flow_name)

        thread = threading.Thread(target=wrapper, daemon=True)
        thread.start()
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
                    self._run_flow("treasure_map", treasure_map_flow)

                if harvest_present:
                    self.logger.info(f"[{iteration}] HARVEST detected (diff={harvest_score:.4f})")
                    self._run_flow("harvest_box", harvest_box_flow)

                # Extract stamina using Qwen OCR (slow - after immediate actions)
                stamina = self.qwen_ocr.extract_number(frame, self.STAMINA_REGION)
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

                # Always print scores to stdout with view state, stamina, and arms race
                print(f"[{iteration}] {pacific_time} [{view_state}] Stamina:{stamina_str} idle:{idle_str} AR:{arms_race_event[:3]}({arms_race_remaining_mins}m) H:{handshake_score:.3f} T:{treasure_score:.3f} C:{corn_score:.3f} G:{gold_score:.3f} HB:{harvest_score:.3f} I:{iron_score:.3f} Gem:{gem_score:.3f} Cab:{cabbage_score:.3f} Eq:{equip_score:.3f} AFK:{afk_score:.3f} V:{view_score:.3f} B:{back_score:.3f}")

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

                # Elite zombie rally - stamina >= 118 and idle 5+ min
                # Filter out invalid stamina values (OCR errors return garbage like 1234567890)
                # Require 3 consecutive VALID readings, then check if >= threshold
                stamina_valid = stamina is not None and 0 <= stamina <= 200
                if stamina_valid:
                    self.elite_zombie_consecutive_count += 1
                else:
                    self.elite_zombie_consecutive_count = 0  # Reset if invalid reading

                # Only trigger after 3 consecutive valid reads AND stamina >= threshold AND idle
                if self.elite_zombie_consecutive_count >= self.ELITE_ZOMBIE_CONSECUTIVE_REQUIRED:
                    if stamina >= self.ELITE_ZOMBIE_STAMINA_THRESHOLD and idle_secs >= self.IDLE_THRESHOLD:
                        self.logger.info(f"[{iteration}] ELITE ZOMBIE: Stamina={stamina} >= {self.ELITE_ZOMBIE_STAMINA_THRESHOLD}, idle={idle_str}, {self.elite_zombie_consecutive_count} consecutive valid reads, triggering rally...")
                        self._run_flow("elite_zombie", elite_zombie_flow)
                        self.elite_zombie_consecutive_count = 0  # Reset after triggering

                # =================================================================
                # ARMS RACE EVENT TRACKING
                # =================================================================
                current_time = time.time()  # Needed for cooldown checks
                # arms_race, arms_race_event, arms_race_remaining, arms_race_remaining_mins already set above

                # Beast Training: Mystic Beast last hour, stamina >= 20, 90s cooldown
                if arms_race_event == "Mystic Beast" and arms_race_remaining_mins <= 60:
                    # Check stamina with consecutive read validation (separate from elite zombie)
                    if stamina_valid:
                        # Check consistency with previous read
                        if self.beast_training_last_stamina is not None:
                            diff = abs(stamina - self.beast_training_last_stamina)
                            if diff > 20:  # Too much variance, reset
                                self.beast_training_consecutive_reads = 1
                            else:
                                self.beast_training_consecutive_reads += 1
                        else:
                            self.beast_training_consecutive_reads = 1
                        self.beast_training_last_stamina = stamina
                    else:
                        self.beast_training_consecutive_reads = 0
                        self.beast_training_last_stamina = None

                    # Check all conditions: 3 consecutive reads, stamina >= 20, cooldown passed
                    rally_cooldown_ok = (current_time - self.beast_training_last_rally) >= self.BEAST_TRAINING_RALLY_COOLDOWN
                    if (self.beast_training_consecutive_reads >= 3 and
                        stamina >= self.BEAST_TRAINING_STAMINA_THRESHOLD and
                        rally_cooldown_ok):
                        self.logger.info(f"[{iteration}] BEAST TRAINING: Mystic Beast ({arms_race_remaining_mins}min left), stamina={stamina}, triggering rally...")
                        # Use elite_zombie_flow with 0 plus clicks
                        import config
                        original_clicks = getattr(config, 'ELITE_ZOMBIE_PLUS_CLICKS', 5)
                        config.ELITE_ZOMBIE_PLUS_CLICKS = 0
                        self._run_flow("beast_training", elite_zombie_flow)
                        config.ELITE_ZOMBIE_PLUS_CLICKS = original_clicks
                        self.beast_training_last_rally = current_time
                        self.beast_training_consecutive_reads = 0

                # Enhance Hero: last 20 minutes, runs once per block
                if arms_race_event == "Enhance Hero" and arms_race_remaining_mins <= self.ENHANCE_HERO_LAST_MINUTES:
                    # Check if we already triggered for this block
                    block_start = arms_race['block_start']
                    if self.enhance_hero_last_block_start != block_start:
                        # Additional conditions: idle 5+ min
                        if idle_secs >= self.IDLE_THRESHOLD:
                            self.logger.info(f"[{iteration}] ENHANCE HERO: Last {arms_race_remaining_mins}min of Enhance Hero, triggering hero upgrade flow...")
                            self._run_flow("enhance_hero_arms_race", hero_upgrade_arms_race_flow)
                            self.enhance_hero_last_block_start = block_start

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
        default=3.0,
        help="Check interval in seconds (default: 3.0)"
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
