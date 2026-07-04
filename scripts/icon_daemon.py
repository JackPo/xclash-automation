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
from __future__ import annotations

import gc
import sys
import time
import argparse
import threading
import logging
import importlib
import re
from pathlib import Path
from datetime import datetime, date, timezone, timedelta
from functools import partial
from typing import TYPE_CHECKING, Any, Callable

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
from utils.union_war_panel_detector import UnionWarPanelDetector
from utils.disconnection_dialog_matcher import is_disconnection_dialog_visible, get_confirm_button_position
from utils.debug_screenshot import get_daemon_debug, cleanup_old_screenshots
from utils.ui_helpers import click_back
from utils.template_matcher import clear_gpu_cache
import cv2

# Daemon frame debug directory (for every-cycle screenshot capture)
DAEMON_FRAMES_DIR = Path(__file__).parent.parent / "screenshots" / "debug" / "daemon_frames"
DAEMON_FRAMES_DIR.mkdir(parents=True, exist_ok=True)
DAEMON_FRAMES_MAX_GB = 50  # Auto-cleanup when folder exceeds this size

# Global cycle counter for daemon frame screenshots
_daemon_frame_cycle = 0


def _cleanup_daemon_frames_if_over_limit() -> None:
    """Remove oldest daemon frame screenshots if folder exceeds size limit.

    Called periodically during daemon execution (every 100 cycles).
    Targets 90% of max to avoid constant cleanup.
    """
    max_bytes = DAEMON_FRAMES_MAX_GB * 1024 * 1024 * 1024
    target_bytes = int(max_bytes * 0.9)  # Clean to 90% when triggered

    # Calculate current size
    try:
        files = list(DAEMON_FRAMES_DIR.glob('*.png'))
        total_size = sum(f.stat().st_size for f in files)
    except Exception:
        return  # Can't check, skip cleanup

    if total_size < max_bytes:
        return  # Under limit, nothing to do

    # Get files sorted by mtime (oldest first)
    files_sorted = sorted(files, key=lambda f: f.stat().st_mtime)

    deleted_count = 0
    while total_size > target_bytes and files_sorted:
        oldest = files_sorted.pop(0)
        try:
            size = oldest.stat().st_size
            oldest.unlink()
            total_size -= size
            deleted_count += 1
        except Exception:
            pass  # File may have been deleted by another process

    if deleted_count > 0:
        logging.getLogger(__name__).info(
            f"[CLEANUP] Deleted {deleted_count} old daemon frames, now at {total_size / 1024**3:.1f}GB"
        )


def _save_daemon_frame(frame: Any, view_state: str, stamina: int | None) -> None:
    """Save daemon cycle screenshot with metadata in filename.

    Args:
        frame: BGR numpy array screenshot
        view_state: Current view state (TOWN, WORLD, CHAT, UNKNOWN, etc.)
        stamina: Current stamina value or None if unknown
    """
    global _daemon_frame_cycle
    _daemon_frame_cycle += 1

    timestamp = datetime.now().strftime("%H%M%S_%f")[:-3]
    stam_str = str(stamina) if stamina is not None else "NA"
    filename = f"{timestamp}_c{_daemon_frame_cycle:06d}_{view_state}_stam{stam_str}.png"
    filepath = DAEMON_FRAMES_DIR / filename

    try:
        cv2.imwrite(str(filepath), frame)
    except Exception:
        pass  # Don't crash daemon for debug screenshots

    # Cleanup check every 100 frames
    if _daemon_frame_cycle % 100 == 0:
        _cleanup_daemon_frames_if_over_limit()


# Disconnection dialog wait time (user playing on mobile)
DISCONNECTION_WAIT_SECONDS = 300  # 5 minutes

# Logcat threadtime timestamp: "03-02 21:05:01.540 ..."
LOGCAT_THREADTIME_RE = re.compile(
    r"^(?P<month>\d{2})-(?P<day>\d{2})\s+"
    r"(?P<hour>\d{2}):(?P<minute>\d{2}):(?P<second>\d{2})\.(?P<millis>\d{3})"
)

from scripts.flows import handshake_flow, treasure_map_flow, corn_harvest_flow, gold_coin_flow, harvest_box_flow, iron_bar_flow, gem_flow, cabbage_flow, equipment_enhancement_flow, elite_zombie_flow, afk_rewards_flow, union_gifts_flow, union_technology_flow, hero_upgrade_arms_race_flow, stamina_claim_flow, stamina_use_flow, soldier_training_flow, soldier_upgrade_flow, rally_join_flow, healing_flow, bag_flow, gift_box_flow, marshall_speedup_all_flow, quick_production_flow, back_from_chat_flow
from scripts.flows.tavern_quest_flow import tavern_quest_claim_flow, run_tavern_quest_flow
from scripts.flows.faction_trials_flow import faction_trials_flow
from scripts.flows.zombie_attack_flow import zombie_attack_flow
from scripts.flows.community_click_flow import community_click_flow
from scripts.flows.royal_city_attack_flow import royal_city_attack_flow
from scripts.flows.union_coal_flow import union_coal_flow
from scripts.flows.union_furnace_flow import union_furnace_flow
from scripts.flows.marshall_speedup_all_flow import marshall_speedup_all_flow, apply_marshall_and_verify
from scripts.flows.beast_training_flow import aggressive_beast_training_flow
from scripts.flows.city_construction_flow import city_construction_speedup_flow
from scripts.flows.technology_research_flow import technology_research_speedup_flow
from utils.arms_race import get_arms_race_status, get_time_until_beast_training
from utils.arms_race_data_collector import (
    load_persisted_into_memory,
    should_collect_event_data,
    collect_and_save_current_event,
)
from utils.arms_race_panel_helper import check_beast_training_progress, check_arms_race_progress
from utils.scheduler import get_scheduler
from utils.config_overrides import get_override_manager
from utils.current_state import update_stamina, update_view_state, update_daemon_status

# Import configurable parameters
from config import (
    IDLE_THRESHOLD,
    IDLE_CHECK_INTERVAL,
    STAMINA_OCR_INTERVAL,
    STAMINA_OCR_MAX_VALID,
    DAEMON_FRAME_CAPTURE_ENABLED,
    DAEMON_FRAME_CAPTURE_EVERY_N,
    ELITE_ZOMBIE_STAMINA_THRESHOLD,
    ELITE_ZOMBIE_CONSECUTIVE_REQUIRED,
    ELITE_ZOMBIE_TARGET_LEVEL,
    AFK_REWARDS_COOLDOWN,
    UNION_GIFTS_COOLDOWN,
    UNION_TECHNOLOGY_COOLDOWN,
    UNION_COAL_COOLDOWN,
    UNION_FURNACE_COOLDOWN,
    BAG_FLOW_COOLDOWN,
    GIFT_BOX_COOLDOWN,
    UNKNOWN_STATE_TIMEOUT,
    UNKNOWN_LOOP_TIMEOUT,
    CHAT_STUCK_TIMEOUT,
    CHAT_STUCK_IDLE_REQUIRED,
    STAMINA_REGION,
    # Arms Race automation settings
    ARMS_RACE_BEAST_TRAINING_ENABLED,
    ARMS_RACE_BEAST_TRAINING_LAST_MINUTES,
    ARMS_RACE_BEAST_TRAINING_STAMINA_THRESHOLD,
    ARMS_RACE_BEAST_TRAINING_COOLDOWN,
    ARMS_RACE_ENHANCE_HERO_ENABLED,
    ARMS_RACE_ENHANCE_HERO_LAST_MINUTES,
    ARMS_RACE_CONSTRUCTION_ENABLED,
    ARMS_RACE_CONSTRUCTION_LAST_MINUTES,
    ARMS_RACE_TECH_RESEARCH_ENABLED,
    ARMS_RACE_TECH_RESEARCH_LAST_MINUTES,
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
    END_OF_DAY_STAMINA_CLAIM_MINUTES,
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
    BACK_BUTTON_CLICK,
    # Tavern quest scan
    TAVERN_SCAN_COOLDOWN,
    TAVERN_QUEST_START_HOUR,
    TAVERN_QUEST_START_MINUTE,
    TAVERN_BLOCKING_FLOW_GUARD_SECONDS,
    TAVERN_OVERDUE_GUARD_GRACE_SECONDS,
    # WebSocket API server
    DAEMON_SERVER_PORT,
    DAEMON_SERVER_ENABLED,
    # Dashboard web server
    DASHBOARD_ENABLED,
    DASHBOARD_PORT,
)

from dataclasses import dataclass
from enum import IntEnum

if TYPE_CHECKING:
    from utils.daemon_server import DaemonWebSocketServer
    from utils.barracks_state_matcher import BarrackState


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
    flow_func: Callable[..., Any]
    priority: FlowPriority
    critical: bool = False
    reason: str = ""  # Why this flow was triggered (for logging)
    record_to_scheduler: bool = False  # If True, records cooldown after execution


@dataclass
class QueuedFlow:
    """
    Deferred flow entry for later execution when user becomes idle.
    """
    candidate: FlowCandidate
    queued_at: float


class IconDaemon:
    """
    Daemon that detects icons and triggers non-blocking flows.
    """

    # Type annotations for instance attributes
    interval: float
    debug: bool
    adb: ADBHelper | None
    windows_helper: WindowsScreenshotHelper | None
    ocr_client: OCRClient | None
    STAMINA_REGION: tuple[int, int, int, int]
    OCR_HEALTH_CHECK_INTERVAL: int
    last_ocr_health_check: float
    ocr_consecutive_failures: int
    handshake_matcher: HandshakeIconMatcher | None
    treasure_matcher: TreasureMapMatcher | None
    corn_matcher: CornHarvestMatcher | None
    gold_matcher: GoldCoinMatcher | None
    harvest_box_matcher: HarvestBoxMatcher | None
    iron_matcher: IronBarMatcher | None
    gem_matcher: GemMatcher | None
    cabbage_matcher: CabbageMatcher | None
    equipment_enhancement_matcher: EquipmentEnhancementMatcher | None
    hospital_matcher: HospitalStateMatcher | None
    back_button_matcher: BackButtonMatcher | None
    dog_house_matcher: DogHouseMatcher | None
    afk_rewards_matcher: AfkRewardsMatcher | None
    barracks_matcher: BarracksStateMatcher | None
    rally_march_matcher: RallyMarchButtonMatcher | None
    union_war_panel_detector: UnionWarPanelDetector
    deferred_flow_queue: list[QueuedFlow]
    active_flows: set[str]
    flow_lock: threading.Lock
    critical_flow_active: bool
    critical_flow_name: str | None
    critical_flow_start_time: float | None
    critical_flow_thread: threading.Thread | None
    command_server: DaemonWebSocketServer | None
    paused: bool
    vs_chest_triggered: set[int]
    vs_chest_last_day: int | None
    scheduled_triggers: list[dict[str, Any]]
    barracks_state_history: list[list[BarrackState]]
    hospital_state_history: list[HospitalState]
    tavern_scheduled_triggered_date: date | None
    enhance_hero_last_block_start: datetime | None
    construction_speedup_last_block_start: datetime | None
    arms_race_progress_check_block: datetime | None
    beast_training_current_block: datetime | None
    beast_training_pre_claim_block: datetime | None
    unknown_state_start: float | None
    unknown_state_left_time: float | None
    unknown_first_recovery_time: float | None
    disconnection_dialog_detected_time: float | None
    continuous_idle_start: float | None
    ui_timeout_window_seconds: int
    ui_timeout_threshold: int
    ui_timeout_logcat_tail_lines: int
    last_ui_timeout_restart_ts: datetime | None
    TAVERN_BLOCKING_FLOW_GUARD_SECONDS: int
    TAVERN_OVERDUE_GUARD_GRACE_SECONDS: int

    def __init__(self, interval: float | None = None, debug: bool = False) -> None:
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
        self.last_ocr_health_check = 0.0
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
        self.rally_march_matcher = None
        self.union_war_panel_detector = UnionWarPanelDetector()
        self.deferred_flow_queue = []

        # Track active flows to prevent re-triggering
        self.active_flows: set[str] = set()
        self.flow_lock = threading.Lock()

        # Critical flow protection - blocks all other daemon actions
        self.critical_flow_active = False
        self.critical_flow_name = None
        self.critical_flow_start_time: float | None = None
        self.critical_flow_thread: threading.Thread | None = None
        self.CRITICAL_FLOW_TIMEOUT = 120  # Auto-clear after 2 minutes
        self.DEFERRED_FLOW_TTL = 1800  # 30 min: drop stale deferred flows

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
        # Guard critical flows around tavern completion windows (except treasure/tavern_claim).
        self.TAVERN_BLOCKING_FLOW_GUARD_SECONDS = TAVERN_BLOCKING_FLOW_GUARD_SECONDS
        # Treat recently-overdue completions as claim-urgent to recover after blocking flows.
        self.TAVERN_OVERDUE_GUARD_GRACE_SECONDS = TAVERN_OVERDUE_GUARD_GRACE_SECONDS

        # VS Day 7 chest surprise - trigger bag flow at 10, 5, 1 min remaining
        self.VS_CHEST_CHECKPOINTS: list[int] = [10, 5, 1]  # Minutes before day ends
        self.vs_chest_triggered: set[int] = set()  # Track which checkpoints we've hit
        self.vs_chest_last_day: int | None = None  # Reset tracking when day changes

        # Union technology cooldown - once per hour
        self.last_union_technology_time = 0
        self.UNION_TECHNOLOGY_COOLDOWN = UNION_TECHNOLOGY_COOLDOWN

        # Union coal cooldown - once per hour
        self.last_union_coal_time = 0
        self.UNION_COAL_COOLDOWN = UNION_COAL_COOLDOWN

        # Union furnace cooldown - every 2 hours
        self.last_union_furnace_time = 0
        self.UNION_FURNACE_COOLDOWN = UNION_FURNACE_COOLDOWN

        # Return-to-town tracking - every 5 idle iterations, go back to TOWN
        self.idle_iteration_count = 0
        self.IDLE_RETURN_TO_TOWN_INTERVAL = 5  # Every 5 iterations when idle

        # Initialize unified scheduler with config overrides
        # All flows now use IDLE_THRESHOLD from config (default 5 min)
        self.scheduler = get_scheduler(config_overrides={
            "afk_rewards": {"cooldown": AFK_REWARDS_COOLDOWN, "idle_required": IDLE_THRESHOLD},
            "union_gifts": {"cooldown": UNION_GIFTS_COOLDOWN, "idle_required": IDLE_THRESHOLD},
            "union_technology": {"cooldown": UNION_TECHNOLOGY_COOLDOWN, "idle_required": IDLE_THRESHOLD},
            "union_coal": {"cooldown": UNION_COAL_COOLDOWN, "idle_required": IDLE_THRESHOLD},
            "union_furnace": {"cooldown": UNION_FURNACE_COOLDOWN, "idle_required": IDLE_THRESHOLD},
            "bag_flow": {"cooldown": BAG_FLOW_COOLDOWN, "idle_required": IDLE_THRESHOLD},
            "gift_box": {"cooldown": GIFT_BOX_COOLDOWN, "idle_required": IDLE_THRESHOLD},
            # Tavern modes - separate cooldowns for each mode
            "tavern_scan": {"cooldown": TAVERN_SCAN_COOLDOWN, "idle_required": IDLE_THRESHOLD},  # 30 min - OCR timers
            "tavern_dispatch": {"cooldown": 3600, "idle_required": IDLE_THRESHOLD},  # 1 hour - start new quests
            "tavern_ally": {"cooldown": 3600, "idle_required": IDLE_THRESHOLD},  # 1 hour - assist ally quests
            "community_checkin": {"cooldown": 3600, "idle_required": IDLE_THRESHOLD},  # 1 hour, flow skips if already done today
        })

        # Unified stamina validation - ONE system for all stamina-based triggers
        # Uses StaminaReader for MODE-based confirmation with consistency check
        self.stamina_reader = StaminaReader()

        # Stamina OCR throttling - OCR is expensive (~200ms), no need to run every iteration
        self.last_stamina_ocr_time: float = 0.0
        self.cached_stamina: int | None = None
        self.stamina_ocr_interval = STAMINA_OCR_INTERVAL

        # Last detected view state (for dashboard API)
        self.last_view_state: str | None = None

        # Pacific timezone for logging
        self.pacific_tz = pytz.timezone('America/Los_Angeles')

        # UNKNOWN state recovery tracking (from config)
        self.unknown_state_start: float | None = None  # When we first entered UNKNOWN state
        self.unknown_state_left_time: float | None = None  # When we left UNKNOWN (for hysteresis)
        self.UNKNOWN_STATE_TIMEOUT = UNKNOWN_STATE_TIMEOUT
        self.UNKNOWN_HYSTERESIS = 10  # Seconds out of UNKNOWN before resetting timer

        # CHAT stuck tracking: CHAT is a known view so UNKNOWN recovery never
        # fires, and the back button matcher was removed from the main loop -
        # without this the daemon idles in chat forever.
        self.chat_state_start: float | None = None
        self.last_chat_back_attempt = 0.0
        self.CHAT_STUCK_TIMEOUT = CHAT_STUCK_TIMEOUT
        self.CHAT_STUCK_IDLE_REQUIRED = CHAT_STUCK_IDLE_REQUIRED

        # UNKNOWN recovery loop detection - force restart if recovery keeps cycling
        self.unknown_recovery_count = 0  # How many times recovery ran
        self.unknown_first_recovery_time: float | None = None  # When first recovery started
        self.UNKNOWN_LOOP_TIMEOUT = UNKNOWN_LOOP_TIMEOUT  # 8 min from config

        # Disconnection dialog tracking (user playing on mobile)
        self.disconnection_dialog_detected_time: float | None = None  # When we first saw the dialog

        # Game-stuck detector from app telemetry:
        # If we observe >=3 "ui_timeout" logs in 20s, force restart immediately.
        self.ui_timeout_window_seconds = 20
        self.ui_timeout_threshold = 3
        self.ui_timeout_logcat_tail_lines = 4000
        self.last_ui_timeout_restart_ts: datetime | None = None

        # Resolution check (proactive, not just on recovery)
        self.RESOLUTION_CHECK_INTERVAL = RESOLUTION_CHECK_INTERVAL
        self.EXPECTED_RESOLUTION = EXPECTED_RESOLUTION

        # Scheduled triggers (old mechanism - kept for future use)
        self.scheduled_triggers: list[dict[str, Any]] = []  # Empty - no scheduled triggers
        self.continuous_idle_start: float | None = None  # Track when continuous idle began

        # Tavern quest scheduled trigger at 10:30 PM Pacific
        # Triggers immediately when time is reached, ignoring cooldown/idle
        self.tavern_scheduled_triggered_date: date | None = None  # Track which date we've triggered

        # Arms Race event tracking (values from config)
        # Beast Training: Mystic Beast last N minutes, stamina threshold, cooldown between rallies
        self.ARMS_RACE_BEAST_TRAINING_ENABLED = ARMS_RACE_BEAST_TRAINING_ENABLED
        self.ARMS_RACE_BEAST_TRAINING_LAST_MINUTES = ARMS_RACE_BEAST_TRAINING_LAST_MINUTES
        self.BEAST_TRAINING_STAMINA_THRESHOLD = ARMS_RACE_BEAST_TRAINING_STAMINA_THRESHOLD
        self.BEAST_TRAINING_RALLY_COOLDOWN = ARMS_RACE_BEAST_TRAINING_COOLDOWN
        self.beast_training_last_rally: float = 0
        self.beast_training_rally_count: int = 0  # Track total rallies in current Beast Training block
        self.beast_training_current_block: datetime | None = None  # Track which block we're in
        self.STAMINA_CLAIM_THRESHOLD = ARMS_RACE_STAMINA_CLAIM_THRESHOLD  # Claim when stamina < this

        # Use Button tracking (for stamina recovery items during Beast Training)
        self.BEAST_TRAINING_USE_ENABLED = ARMS_RACE_BEAST_TRAINING_USE_ENABLED
        self.BEAST_TRAINING_USE_MAX = ARMS_RACE_BEAST_TRAINING_USE_MAX  # Max 4 Use clicks per block
        self.BEAST_TRAINING_USE_COOLDOWN = ARMS_RACE_BEAST_TRAINING_USE_COOLDOWN  # 3 min between uses
        self.BEAST_TRAINING_MAX_RALLIES = ARMS_RACE_BEAST_TRAINING_MAX_RALLIES  # Don't use if rallies >= 15
        self.BEAST_TRAINING_USE_STAMINA_THRESHOLD = ARMS_RACE_BEAST_TRAINING_USE_STAMINA_THRESHOLD  # Use when < 20
        self.BEAST_TRAINING_USE_LAST_MINUTES = ARMS_RACE_BEAST_TRAINING_USE_LAST_MINUTES  # 3rd+ uses only in last N min
        self.beast_training_use_count: int = 0  # Track Use button clicks per block
        self.beast_training_last_use_time: float = 0  # Track cooldown between uses
        self.beast_training_claim_attempted: bool = False  # Track if we tried to claim this iteration

        # Smart Beast Training flow phases use scheduler-based tracking (beast_training_hour_mark_block, beast_training_last_hour_block, beast_training_mid_check_block)
        self.beast_training_last_progress_check: float = 0  # Timestamp of last progress check

        # Enhance Hero: last N minutes of Enhance Hero, runs once per block
        self.ARMS_RACE_ENHANCE_HERO_ENABLED = ARMS_RACE_ENHANCE_HERO_ENABLED
        self.ENHANCE_HERO_LAST_MINUTES = ARMS_RACE_ENHANCE_HERO_LAST_MINUTES
        self.enhance_hero_last_block_start: datetime | None = None  # Track which block we triggered for

        # City Construction: last N minutes, speedup smallest queue
        self.ARMS_RACE_CONSTRUCTION_ENABLED = ARMS_RACE_CONSTRUCTION_ENABLED
        self.CONSTRUCTION_LAST_MINUTES = ARMS_RACE_CONSTRUCTION_LAST_MINUTES
        self.construction_speedup_last_block_start: datetime | None = None

        # Technology Research: last N minutes, speedup smallest queue
        self.ARMS_RACE_TECH_RESEARCH_ENABLED = ARMS_RACE_TECH_RESEARCH_ENABLED
        self.TECH_RESEARCH_LAST_MINUTES = ARMS_RACE_TECH_RESEARCH_LAST_MINUTES
        self.tech_research_speedup_last_block_start: datetime | None = None

        # Generic Arms Race progress check: log points for ALL events in last 10 min
        self.ARMS_RACE_PROGRESS_CHECK_MINUTES = 10  # Check in last N minutes
        self.arms_race_progress_check_block: datetime | None = None  # Track which block we checked

        # Soldier Training: when idle 5+ min, any barrack PENDING during Soldier Training event
        # CONTINUOUSLY checks and upgrades PENDING barracks (no block limitation)
        self.ARMS_RACE_SOLDIER_TRAINING_ENABLED = ARMS_RACE_SOLDIER_TRAINING_ENABLED

        # Pre-Beast Training: claim stamina + block elite rallies N minutes before event
        self.BEAST_TRAINING_PRE_EVENT_MINUTES = ARMS_RACE_BEAST_TRAINING_PRE_EVENT_MINUTES
        self.beast_training_pre_claim_block: datetime | None = None  # Track which upcoming block we've pre-claimed for

        # VS Event overrides - soldier promotions all day on specific days
        self.VS_SOLDIER_PROMOTION_DAYS = VS_SOLDIER_PROMOTION_DAYS

        # Screenshot cleanup - every 6 hours
        self.SCREENSHOT_CLEANUP_INTERVAL = 6 * 60 * 60  # 6 hours
        self.last_screenshot_cleanup: float = 0

        # Shield inventory check - every 6 hours
        self.SHIELD_INVENTORY_INTERVAL = 6 * 60 * 60  # 6 hours
        self.last_shield_inventory_check: float = 0

        # Under attack detection
        self.under_attack: bool = False  # Current attack state
        self.last_attack_log_time: float = 0  # Prevent log spam
        self.ATTACK_LOG_COOLDOWN = 60  # Only log once per minute while under attack

        # Bloodlust detection
        self.bloodlust_active: bool = False  # Current bloodlust state
        self.bloodlust_started_at: float | None = None  # When bloodlust was first detected

        # Shield active detection
        self.shield_protection_active: bool = False  # Current shield protection state

        # Barracks state validation - require 10 readings with 60%+ being a specific state
        # Allows UNKNOWN (?) readings as long as 60%+ are a consistent letter (R, P, or T)
        # Example: PPPPPP???? (6P + 4?) = 60% P = PASS
        # Example: PPPPP????? (5P + 5?) = 50% P = FAIL
        # Example: PPPPRRR??? (mixed P and R) = FAIL
        self.barracks_state_history: list[list[Any]] = [[], [], [], []]  # Per-barrack state history
        self.BARRACKS_CONSECUTIVE_REQUIRED = 10
        self.BARRACKS_MIN_LETTER_RATIO = 0.6  # 60% must be a specific letter

        # Hospital state history - same pattern as barracks
        self.hospital_state_history: list[HospitalState] = []  # List of HospitalState values
        self.HOSPITAL_CONSECUTIVE_REQUIRED = HOSPITAL_CONSECUTIVE_REQUIRED

        # Handshake cooldown tracking
        self._last_handshake_click: float = 0.0
        self.HANDSHAKE_COOLDOWN: float = 2.0  # seconds between handshake clicks

        # Royal City Reinforce scheduling (Fridays 6:15-9:00 AM PT)
        self._royal_city_last_attempt: float = 0.0
        self._royal_city_success_date: date | None = None  # Date when we successfully marched (stop retrying)

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

        # Reinforce loop mode
        self.reinforce_interval: int | None = None  # Seconds between reinforce runs
        self.last_reinforce_time: float = 0  # Last time reinforce was run

        # State persistence tracking
        self.state_save_interval = 60  # Save state every N iterations (~3 min at 3s interval)

    def _verify_templates(self) -> None:
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
            'treasure_map/treasure_map_4k.png',
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

    def initialize(self) -> None:
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

        # Kill other apps (Play Store, BlueStacks bloatware, etc.)
        killed = self.adb.kill_other_apps()
        if killed:
            print(f"  Killed other apps: {', '.join(killed)}")

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
        print(f"  Treasure map matcher: {self.treasure_matcher.TEMPLATE} (threshold={self.treasure_matcher.threshold})")

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
        self.last_rally_march_click: float = 0  # Timestamp of last march button click
        self.union_boss_mode_until: float = 0   # Timestamp when Union Boss mode expires (faster rally joining)
        self.rally_march_suppress_until: float = 0  # Suppress repeated rally march retries after no-action outcomes
        self.last_union_war_panel_back_click: float = 0
        self.UNION_WAR_PANEL_BACK_COOLDOWN = 2.0

        # Startup recovery - return_to_base_view handles EVERYTHING:
        # - Checks if app is running, starts it if not
        # - Runs setup_bluestacks.py
        # - Gets to TOWN/WORLD via back button clicking
        # - Restarts and retries if stuck
        if self._check_ui_timeout_burst_and_restart(iteration=0):
            self.logger.info("STARTUP: ui_timeout burst handled, proceeding with base recovery after restart")
        self.logger.info("STARTUP: Running recovery to ensure ready state...")
        return_to_base_view(self.adb, self.windows_helper, debug=True, respect_idle=False)

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

        # Start Dashboard web server
        if DASHBOARD_ENABLED:
            try:
                from dashboard.server import start_dashboard_server
                dashboard_port = start_dashboard_server(daemon_instance=self, port=DASHBOARD_PORT)
                self.logger.info(f"STARTUP: Dashboard running at http://localhost:{dashboard_port}")
            except ImportError as e:
                self.logger.warning(f"STARTUP: Dashboard disabled (missing dependencies): {e}")
            except Exception as e:
                self.logger.error(f"STARTUP: Dashboard failed to start: {e}")
        else:
            self.logger.info("STARTUP: Dashboard disabled by config")

        self.logger.info("STARTUP: Ready")

    def _get_config(self, key: str, default: Any) -> Any:
        """
        Get effective config value, checking override manager first.

        Args:
            key: Config key (e.g., 'RALLY_JOIN_ENABLED')
            default: Default value from config.py

        Returns:
            Override value if set, otherwise default
        """
        manager = get_override_manager()
        value, is_overridden = manager.get_effective(key, default)
        return value

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

    def _is_tavern_guard_exempt_flow(self, flow_name: str) -> bool:
        """Flows allowed to run while tavern completion guard is active."""
        return flow_name in {"treasure_map", "tavern_claim"}

    def _get_tavern_guard_status(self, window_seconds: int | None = None) -> tuple[bool, str]:
        """
        Return whether tavern completion guard should be active.

        Guard is active when:
        - A scheduled completion is within `window_seconds`, OR
        - A completion recently passed (grace window), meaning we should claim ASAP.
        """
        guard_window = window_seconds if window_seconds is not None else self.TAVERN_BLOCKING_FLOW_GUARD_SECONDS
        completions = self.scheduler.get_tavern_completions()
        if not completions:
            return False, "no tavern completions scheduled"

        now = datetime.now()
        upcoming: list[float] = []
        overdue: list[float] = []
        for completion in completions:
            delta = (completion - now).total_seconds()
            if delta >= 0:
                upcoming.append(delta)
            else:
                overdue.append(delta)

        if upcoming:
            nearest = min(upcoming)
            if nearest <= guard_window:
                return True, f"next completion in {nearest:.0f}s"

        if overdue:
            latest_overdue = max(overdue)  # Closest past completion (negative)
            overdue_by = abs(latest_overdue)
            if overdue_by <= self.TAVERN_OVERDUE_GUARD_GRACE_SECONDS:
                return True, f"completion overdue by {overdue_by:.0f}s"

        return False, "outside tavern guard window"

    def _run_post_treasure_tavern_claim_if_due(self) -> None:
        """
        Immediately run tavern claim after treasure_map if completion is due/near-due.
        """
        guard_active, guard_reason = self._get_tavern_guard_status()
        if not guard_active:
            return

        self.logger.info(f"POST-TREASURE: triggering tavern_claim immediately ({guard_reason})")
        result = self._run_flow_sync("tavern_claim", self._run_tavern_claim_with_retries, critical=True)
        if not result.get("success"):
            self.logger.warning(
                f"POST-TREASURE: tavern_claim failed to start/run ({result.get('error', 'unknown error')})"
            )

    def _execute_best_flow(self, candidates: list[FlowCandidate], iteration: int) -> str | None:
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
        now_ts = time.time()

        # Drop stale deferred queue items
        if self.deferred_flow_queue:
            kept: list[QueuedFlow] = []
            dropped = 0
            for queued in self.deferred_flow_queue:
                if now_ts - queued.queued_at <= self.DEFERRED_FLOW_TTL:
                    kept.append(queued)
                else:
                    dropped += 1
            self.deferred_flow_queue = kept
            if dropped > 0:
                self.logger.info(
                    f"[{iteration}] Deferred queue cleanup: dropped {dropped} stale item(s)"
                )

        if not candidates and not self.deferred_flow_queue:
            return None

        # Tavern guard: near completion windows should not be preempted by blocking flows.
        guard_active, guard_reason = self._get_tavern_guard_status()
        if guard_active and candidates:
            blocked = [
                c for c in candidates
                if c.critical and not self._is_tavern_guard_exempt_flow(c.name)
            ]
            if blocked:
                blocked_names = ", ".join(sorted({c.name for c in blocked}))
                self.logger.info(
                    f"[{iteration}] TAVERN GUARD: blocked critical candidate(s) ({guard_reason}): {blocked_names}"
                )
                candidates = [
                    c for c in candidates
                    if not (c.critical and not self._is_tavern_guard_exempt_flow(c.name))
                ]

        # Treasure map is time-sensitive and should run immediately on detection.
        # It bypasses idle/deferred queue gating to avoid stale delayed executions.
        treasure_candidate = next((c for c in candidates if c.name == "treasure_map"), None)
        if treasure_candidate is not None:
            queued_before = len(self.deferred_flow_queue)
            self.deferred_flow_queue = [
                q for q in self.deferred_flow_queue if q.candidate.name != "treasure_map"
            ]
            removed = queued_before - len(self.deferred_flow_queue)
            if removed > 0:
                self.logger.info(
                    f"[{iteration}] Removed {removed} stale deferred treasure_map item(s)"
                )

            self.logger.info(
                f"[{iteration}] TREASURE IMMEDIATE: executing treasure_map now "
                f"(score/ctx: {treasure_candidate.reason})"
            )
            if self._run_flow(
                treasure_candidate.name,
                treasure_candidate.flow_func,
                critical=treasure_candidate.critical,
                record_to_scheduler=treasure_candidate.record_to_scheduler,
            ):
                return treasure_candidate.name

            # Do not queue treasure_map if immediate execution failed this iteration.
            candidates = [c for c in candidates if c.name != "treasure_map"]
            if not candidates and not self.deferred_flow_queue:
                return None

        # Tavern claim is also time-sensitive; run immediately when detected.
        # It bypasses idle/deferred queue gating to avoid missing short claim windows.
        tavern_claim_candidate = next((c for c in candidates if c.name == "tavern_claim"), None)
        if tavern_claim_candidate is not None:
            queued_before = len(self.deferred_flow_queue)
            self.deferred_flow_queue = [
                q for q in self.deferred_flow_queue if q.candidate.name != "tavern_claim"
            ]
            removed = queued_before - len(self.deferred_flow_queue)
            if removed > 0:
                self.logger.info(
                    f"[{iteration}] Removed {removed} stale deferred tavern_claim item(s)"
                )

            self.logger.info(
                f"[{iteration}] TAVERN IMMEDIATE: executing tavern_claim now "
                f"(score/ctx: {tavern_claim_candidate.reason})"
            )
            if self._run_flow(
                tavern_claim_candidate.name,
                tavern_claim_candidate.flow_func,
                critical=tavern_claim_candidate.critical,
                record_to_scheduler=tavern_claim_candidate.record_to_scheduler,
            ):
                return tavern_claim_candidate.name

            # Do not queue tavern_claim if immediate execution failed this iteration.
            candidates = [c for c in candidates if c.name != "tavern_claim"]
            if not candidates and not self.deferred_flow_queue:
                return None

        # Global safety gate: never run auto flows while user is actively interacting.
        # Some candidates are time-based and may not have local idle checks.
        # This central gate prevents any automated clicks from interrupting manual play.
        current_idle = get_user_idle_seconds()
        if current_idle < self.IDLE_THRESHOLD:
            if candidates:
                # Queue highest-priority candidate for idle execution (dedup by flow name).
                candidates.sort(key=lambda c: c.priority, reverse=True)
                best_pending = candidates[0]
                if not any(q.candidate.name == best_pending.name for q in self.deferred_flow_queue):
                    self.deferred_flow_queue.append(QueuedFlow(candidate=best_pending, queued_at=now_ts))
                    self.logger.info(
                        f"[{iteration}] FLOW DEFERRED: queued {best_pending.name} "
                        f"(priority={best_pending.priority.name}) until idle "
                        f"(queue_size={len(self.deferred_flow_queue)})"
                    )
            self.logger.debug(
                f"[{iteration}] FLOW BLOCKED: user active (idle={current_idle:.1f}s < {self.IDLE_THRESHOLD}s), "
                f"skipping {len(candidates)} candidate(s)"
            )
            return None

        # User is idle: drain deferred queue first (FIFO).
        if self.deferred_flow_queue:
            queue_index = 0
            if guard_active:
                next_allowed_index = next(
                    (
                        idx for idx, queued_item in enumerate(self.deferred_flow_queue)
                        if (not queued_item.candidate.critical)
                        or self._is_tavern_guard_exempt_flow(queued_item.candidate.name)
                    ),
                    None,
                )
                if next_allowed_index is None:
                    self.logger.info(
                        f"[{iteration}] TAVERN GUARD: deferred queue held ({guard_reason}); "
                        "all queued critical flows are blocked"
                    )
                    return None
                queue_index = next_allowed_index

            queued = self.deferred_flow_queue[queue_index]
            q = queued.candidate
            self.logger.info(
                f"[{iteration}] FLOW QUEUE RUN: {q.name} "
                f"(priority={q.priority.name}, queued_for={int(now_ts - queued.queued_at)}s)"
            )
            if self._run_flow(q.name, q.flow_func, critical=q.critical,
                              record_to_scheduler=q.record_to_scheduler):
                self.deferred_flow_queue.pop(queue_index)
                return q.name
            return None

        # Guard filtering can remove every candidate in this iteration.
        # In that case there is nothing to run right now.
        if not candidates:
            self.logger.debug(
                f"[{iteration}] FLOW NONE: no runnable candidates "
                f"(guard_active={guard_active}, reason={guard_reason})"
            )
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
        # Note: scheduler recording now happens inside _run_flow thread (only if flow doesn't skip)
        started = self._run_flow(best.name, best.flow_func, critical=best.critical,
                                 record_to_scheduler=best.record_to_scheduler)
        if started:
            return best.name
        return None

    def _run_flow(self, flow_name: str, flow_func: Callable[..., Any], critical: bool = False,
                  record_to_scheduler: bool = False) -> bool:
        """
        Run a flow in a thread-safe way.

        Args:
            flow_name: Identifier for the flow
            flow_func: Function to execute (takes adb as argument)
            critical: If True, blocks all other daemon actions during execution
            record_to_scheduler: If True, records cooldown after execution (unless flow returns skipped=True)
        """
        from utils.timeline import EXCLUDED_FLOWS, get_flow_category

        def wrapper() -> None:
            start_time = time.time()
            flow_result = None
            status = "completed"
            run_post_treasure_claim = critical and flow_name == "treasure_map"

            try:
                # Mark as critical if requested
                if critical:
                    with self.flow_lock:
                        self.critical_flow_active = True
                        self.critical_flow_name = flow_name
                        self.critical_flow_start_time = time.time()
                    self.logger.info(f"CRITICAL FLOW START: {flow_name}")
                else:
                    self.logger.info(f"FLOW START: {flow_name}")

                # Mark daemon action before flow clicks (filters from idle tracking)
                mark_daemon_action()
                flow_result = flow_func(self.adb)

                if critical:
                    self.logger.info(f"CRITICAL FLOW END: {flow_name}")
                else:
                    self.logger.info(f"FLOW END: {flow_name}")
            except Exception as e:
                self.logger.error(f"FLOW ERROR: {flow_name} - {e}")
                status = "failed"
                flow_result = {"error": str(e)}
            finally:
                duration = time.time() - start_time

                # Record to event log for timeline (skip harvest/noise flows)
                if flow_name not in EXCLUDED_FLOWS:
                    result_data = flow_result if isinstance(flow_result, dict) else {"success": bool(flow_result)}
                    self.scheduler.record_event(
                        flow_name=flow_name,
                        status=status,
                        duration=duration,
                        result=result_data,
                        category=get_flow_category(flow_name),
                        is_critical=critical,
                    )

                # Record to scheduler with appropriate cooldown based on outcome:
                # - FAILED (False): Short 15-min retry to handle transient issues
                # - SKIPPED (dict with "skipped"): Short 5-min retry
                # - SUCCESS (True or dict): Full cooldown
                if record_to_scheduler:
                    if flow_result is False or status == "failed":
                        # FAILED - retry in 15 minutes instead of full cooldown
                        self.scheduler.record_flow_run(flow_name, cooldown_override=900)
                        self.logger.warning(f"[SCHEDULER] {flow_name} FAILED - will retry in 15 min")
                    elif isinstance(flow_result, dict) and flow_result.get("skipped"):
                        # SKIPPED - retry in 5 minutes
                        self.scheduler.record_flow_run(flow_name, cooldown_override=300)
                    else:
                        # SUCCESS - full cooldown
                        self.scheduler.record_flow_run(flow_name)

                with self.flow_lock:
                    self.active_flows.discard(flow_name)
                    if critical and self.critical_flow_name == flow_name:
                        self.critical_flow_active = False
                        self.critical_flow_name = None
                        self.critical_flow_start_time = None
                        self.critical_flow_thread = None

                if run_post_treasure_claim:
                    self._run_post_treasure_tavern_claim_if_due()

        if critical and not self._is_tavern_guard_exempt_flow(flow_name):
            guard_active, guard_reason = self._get_tavern_guard_status()
            if guard_active:
                self.logger.info(f"SKIP: {flow_name} blocked by tavern guard ({guard_reason})")
                return False

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
        if critical:
            with self.flow_lock:
                self.critical_flow_thread = thread
        thread.start()
        return True

    def _check_ocr_server_health(self) -> bool:
        """Check if OCR server is healthy, restart if necessary.

        Called periodically and on consecutive OCR failures.
        Returns True if server is healthy (or was restarted), False otherwise.
        """
        server_up = OCRClient.check_server(force=True)
        inference_ok = False

        if server_up:
            try:
                client = self.ocr_client if self.ocr_client is not None else OCRClient()
                inference_ok = client.probe_inference()
            except Exception as probe_err:
                self.logger.warning(f"OCR inference probe failed: {probe_err}")
                inference_ok = False

        if server_up and inference_ok:
            return True

        reason = "server down" if not server_up else "inference probe failed"
        self.logger.warning(f"OCR health check FAILED ({reason}) - killing existing servers and restarting...")
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

    def _switch_to_town(self) -> None:
        """Switch to town view using view_state_detector."""
        assert self.adb is not None
        success = go_to_town(self.adb, debug=False)
        if success:
            self.logger.info("IDLE SWITCH: Successfully switched to TOWN view")
        else:
            self.logger.warning("IDLE SWITCH: Failed to switch to TOWN view")

    def _is_xclash_in_foreground(self) -> bool:
        """Check if xclash (com.xman.na.gp) is the foreground app."""
        import subprocess
        assert self.adb is not None
        assert self.adb.device is not None
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

    @staticmethod
    def _parse_logcat_timestamp(line: str) -> datetime | None:
        """Parse a logcat threadtime timestamp prefix."""
        match = LOGCAT_THREADTIME_RE.match(line)
        if not match:
            return None
        now = datetime.now()
        try:
            return datetime(
                year=now.year,
                month=int(match.group("month")),
                day=int(match.group("day")),
                hour=int(match.group("hour")),
                minute=int(match.group("minute")),
                second=int(match.group("second")),
                microsecond=int(match.group("millis")) * 1000,
            )
        except ValueError:
            return None

    def _check_ui_timeout_burst_and_restart(self, iteration: int) -> bool:
        """
        Force restart when game emits ui_timeout too frequently.

        Trigger condition: >= self.ui_timeout_threshold events inside
        self.ui_timeout_window_seconds.
        """
        import subprocess

        assert self.adb is not None
        assert self.adb.device is not None

        try:
            result = subprocess.run(
                [
                    self.adb.ADB_PATH,
                    "-s",
                    self.adb.device,
                    "logcat",
                    "-d",
                    "-v",
                    "threadtime",
                    "-t",
                    str(self.ui_timeout_logcat_tail_lines),
                ],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=8,
            )
        except Exception as e:
            self.logger.debug(f"[{iteration}] UI_TIMEOUT detector skipped (logcat read failed): {e}")
            return False

        if result.returncode != 0 or not result.stdout:
            return False

        event_times: list[datetime] = []
        latest_log_ts: datetime | None = None
        for line in result.stdout.splitlines():
            ts = self._parse_logcat_timestamp(line)
            if ts is None:
                continue
            if latest_log_ts is None or ts > latest_log_ts:
                latest_log_ts = ts
            if "eventName: ui_timeout" in line:
                event_times.append(ts)

        if latest_log_ts is None or not event_times:
            return False

        # Use latest timestamp in the sampled log tail as "now" anchor.
        # This avoids triggering on stale historical bursts.
        window_start = latest_log_ts - timedelta(seconds=self.ui_timeout_window_seconds)
        recent_count = sum(1 for ts in event_times if ts > window_start)

        if recent_count < self.ui_timeout_threshold:
            return False

        # De-duplicate trigger across loop iterations when same log window is read repeatedly.
        if (
            self.last_ui_timeout_restart_ts is not None
            and latest_log_ts <= self.last_ui_timeout_restart_ts
        ):
            return False

        self.last_ui_timeout_restart_ts = latest_log_ts
        self.logger.error(
            f"[{iteration}] UI_TIMEOUT BURST: {recent_count} events in "
            f"{self.ui_timeout_window_seconds}s (latest={latest_log_ts.strftime('%m-%d %H:%M:%S.%f')[:-3]}). "
            "Forcing immediate app restart."
        )
        self._force_app_restart(reason="ui_timeout burst")
        return True

    def _force_app_restart(self, reason: str = "UNKNOWN recovery loop") -> None:
        """Force stop and restart xclash app."""
        import subprocess
        from pathlib import Path

        assert self.adb is not None
        assert self.adb.device is not None
        self.logger.info(f"FORCING APP RESTART due to {reason}...")

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

        assert self.windows_helper is not None
        assert self.adb is not None

        try:
            import cv2

            # Take screenshot and extract world button region
            frame = self.windows_helper.get_screenshot_cv2()
            x, y, w, h = 3600, 1920, 240, 240
            current_roi = frame[y:y+h, x:x+w]

            # Load both templates
            template_4k = cv2.imread('templates/ground_truth/world_button_4k.png')
            template_lowres = cv2.imread('templates/ground_truth/world_button_lowres_4k.png')

            if template_4k is None or template_lowres is None:  # noqa: E501
                self.logger.warning(f"[{iteration}] Resolution check: missing templates, falling back to wm size")  # type: ignore[unreachable]
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
        assert self.adb is not None
        current_res = _get_current_resolution(self.adb)
        if current_res == self.EXPECTED_RESOLUTION:
            return True

        self.logger.warning(f"[{iteration}] Resolution wrong: {current_res}, expected {self.EXPECTED_RESOLUTION}")
        _run_setup_bluestacks(debug=self.debug)

        new_res = _get_current_resolution(self.adb)
        return new_res == self.EXPECTED_RESOLUTION

    def _validate_barrack_state(self, barrack_index: int) -> tuple[bool, Any | None, float]:
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

    def _load_runtime_state(self) -> None:
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
        self.rally_march_suppress_until = state.get("rally_march_suppress_until", 0)
        self.paused = state.get("paused", False)

        self.logger.info(f"STARTUP: Loaded daemon state (paused={self.paused}, stamina_history={len(self.stamina_reader.history)} readings)")

    def _save_runtime_state(self) -> None:
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
            rally_march_suppress_until=self.rally_march_suppress_until,
            paused=self.paused,
        )

    def trigger_flow(self, flow_name: str) -> dict[str, Any]:
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

    def _run_tavern_scan_twice(self, adb: Any) -> dict[str, Any]:
        """
        Run Tavern SCAN mode once.

        Historically ran two back-to-back passes "for reliability when the
        first pass lands during UI transitions". With the current
        is_in_tavern() verification inside _open_tavern (which already retries
        up to 3 times internally on a single high-level call), the second
        pass was almost always wasted work and contributed to the user's
        "tavern loads 3+ times every 30 min" complaint.

        Name preserved for callsite stability (also referenced in
        get_available_flows). One pass now. Dispatch follow-up still runs
        inside the same tavern session via _run_scan_mode itself, so a
        typical scan trigger opens the tavern ONCE instead of FOUR times.
        """
        self.logger.info("TAVERN SCAN: single pass")
        try:
            return run_tavern_quest_flow(adb, mode="scan")
        except Exception as e:
            self.logger.error(f"TAVERN SCAN: failed: {e}")
            return {"error": str(e)}

    def _run_tavern_claim_with_retries(self, adb: Any) -> dict[str, Any]:
        """
        Run Tavern CLAIM mode with bounded retries.

        Behavior:
        - Up to 5 attempts.
        - Continue attempts to drain multiple ready claims in one trigger.
        - Stop when an attempt finds 0 claims after at least one prior success.
        - Force return-to-town between attempts to clear stale UI/panels.
        """
        max_attempts = 5
        total_claims = 0
        attempts: list[dict[str, Any]] = []

        for attempt in range(1, max_attempts + 1):
            self.logger.info(f"TAVERN CLAIM RETRY: attempt {attempt}/{max_attempts}")

            try:
                result_raw = run_tavern_quest_flow(adb, mode="claim")
            except Exception as e:
                self.logger.error(f"TAVERN CLAIM RETRY: attempt {attempt} failed with exception: {e}")
                result_raw = {"claims": 0, "mode": "claim", "error": str(e)}

            result = result_raw if isinstance(result_raw, dict) else {"claims": int(bool(result_raw))}
            attempts.append(result)

            claims = int(result.get("claims", 0) or 0)
            total_claims += max(0, claims)

            if claims > 0:
                self.logger.info(
                    f"TAVERN CLAIM RETRY: attempt {attempt} claimed {claims} (running total={total_claims})"
                )
            elif total_claims > 0:
                self.logger.info(
                    f"TAVERN CLAIM RETRY: attempt {attempt} found no more claims; stopping with total={total_claims}"
                )
                return {
                    "success": True,
                    "claims": total_claims,
                    "attempts_used": attempt,
                    "attempts": attempts,
                }

            if attempt < max_attempts:
                self.logger.info(
                    f"TAVERN CLAIM RETRY: preparing next attempt {attempt + 1}/{max_attempts} "
                    f"(last_claims={claims}, total={total_claims})"
                )
                try:
                    return_to_base_view(adb, self.windows_helper, debug=self.debug, respect_idle=False)
                except Exception as e:
                    self.logger.warning(f"TAVERN CLAIM RETRY: return_to_base_view failed between attempts: {e}")
                time.sleep(1.0)

        if total_claims > 0:
            self.logger.info(
                f"TAVERN CLAIM RETRY: reached max attempts with claims total={total_claims}"
            )
            return {
                "success": True,
                "claims": total_claims,
                "attempts_used": max_attempts,
                "attempts": attempts,
                "max_attempts_reached": True,
            }

        self.logger.warning(f"TAVERN CLAIM RETRY: exhausted {max_attempts} attempts with no claim")
        return {
            "success": False,
            "claims": total_claims,
            "attempts_used": max_attempts,
            "attempts": attempts,
            "exhausted": True,
        }

    def _is_royal_city_window(self) -> bool:
        """
        Check if we're in the Royal City Reinforce window (Fridays 6:15-9:00 AM PT).

        Returns True if:
        - It's Friday (weekday() == 4)
        - Time is between 6:15 AM and 9:00 AM Pacific
        """
        now_pt = datetime.now(self.pacific_tz)

        # Check if Friday (weekday 4)
        if now_pt.weekday() != 4:
            return False

        # Check time window: 6:15 AM to 9:00 AM PT
        current_minutes = now_pt.hour * 60 + now_pt.minute
        start_minutes = 6 * 60 + 15  # 6:15 AM = 375 minutes
        end_minutes = 9 * 60  # 9:00 AM = 540 minutes

        return start_minutes <= current_minutes < end_minutes

    def _should_run_royal_city_reinforce(self) -> bool:
        """
        Check if we should attempt Royal City Reinforce.

        Returns True if:
        - ROYAL_CITY_REINFORCE_ENABLED is True
        - In the Friday window (6:15-9:00 AM PT)
        - Haven't successfully marched today
        - Cooldown (15 min) has passed since last attempt
        - User is idle
        """
        # Check if enabled
        manager = get_override_manager()
        enabled, _ = manager.get_effective("ROYAL_CITY_REINFORCE_ENABLED", True)
        if not enabled:
            return False

        # Check window
        if not self._is_royal_city_window():
            return False

        # Check if already succeeded today
        today = datetime.now(self.pacific_tz).date()
        if self._royal_city_success_date == today:
            return False

        # Check cooldown
        cooldown, _ = manager.get_effective("ROYAL_CITY_REINFORCE_COOLDOWN", 900)
        if time.time() - self._royal_city_last_attempt < cooldown:
            return False

        # Check idle
        if not self._is_user_idle():
            return False

        return True

    def _run_flow_sync(self, flow_name: str, flow_func: Callable[..., Any], critical: bool = False) -> dict[str, Any]:
        """
        Run a flow synchronously (blocking) and return its result.

        Used by the WebSocket API to wait for flow completion.
        Records events to scheduler for timeline tracking.
        """
        from utils.timeline import EXCLUDED_FLOWS, get_flow_category

        if critical and not self._is_tavern_guard_exempt_flow(flow_name):
            guard_active, guard_reason = self._get_tavern_guard_status()
            if guard_active:
                return {"success": False, "error": f"Blocked by tavern guard ({guard_reason})"}

        run_post_treasure_claim = critical and flow_name == "treasure_map"

        with self.flow_lock:
            if flow_name in self.active_flows:
                return {"success": False, "error": f"{flow_name} already running"}

            if not critical and self.critical_flow_active:
                return {"success": False, "error": f"Blocked by critical flow {self.critical_flow_name}"}

            if self.active_flows:
                return {"success": False, "error": f"Another flow is active: {self.active_flows}"}

            self.active_flows.add(flow_name)

        start_time = time.time()
        try:
            if critical:
                with self.flow_lock:
                    self.critical_flow_active = True
                    self.critical_flow_name = flow_name
                    self.critical_flow_start_time = time.time()
                    self.critical_flow_thread = threading.current_thread()
                self.logger.info(f"CRITICAL FLOW START: {flow_name}")
            else:
                self.logger.info(f"FLOW START: {flow_name}")

            # Mark daemon action before flow clicks (filters from idle tracking)
            mark_daemon_action()
            # Run flow and capture result
            flow_result = flow_func(self.adb)
            duration = time.time() - start_time

            if critical:
                self.logger.info(f"CRITICAL FLOW END: {flow_name}")
            else:
                self.logger.info(f"FLOW END: {flow_name}")

            # Record to event log for timeline (skip harvest/noise flows)
            if flow_name not in EXCLUDED_FLOWS:
                result_data = flow_result if isinstance(flow_result, dict) else {"success": bool(flow_result)}
                self.scheduler.record_event(
                    flow_name=flow_name,
                    status="completed",
                    duration=duration,
                    result=result_data,
                    category=get_flow_category(flow_name),
                    is_critical=critical,
                )

            return {"success": True, "flow": flow_name, "critical": critical, "result": flow_result}

        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"FLOW ERROR: {flow_name} - {e}")

            # Record failure to event log
            if flow_name not in EXCLUDED_FLOWS:
                self.scheduler.record_event(
                    flow_name=flow_name,
                    status="failed",
                    duration=duration,
                    result={"error": str(e)},
                    category=get_flow_category(flow_name),
                    is_critical=critical,
                )

            return {"success": False, "flow": flow_name, "error": str(e)}

        finally:
            with self.flow_lock:
                self.active_flows.discard(flow_name)
                if critical and self.critical_flow_name == flow_name:
                    self.critical_flow_active = False
                    self.critical_flow_name = None
                    self.critical_flow_start_time = None
                    self.critical_flow_thread = None

            if run_post_treasure_claim:
                self._run_post_treasure_tavern_claim_if_due()

    def reload_flows(self) -> None:
        """
        Hot-reload all flow modules for live code updates.

        Called before trigger_flow() to pick up any code changes.
        """
        import sys

        # List of modules to reload (in dependency order)
        modules_to_reload = [
            'utils.windows_screenshot_helper',
            'scripts.flows.bag_use_item_subflow',
            'scripts.flows.bag_special_flow',
            'scripts.flows.bag_hero_flow',
            'scripts.flows.bag_resources_flow',
            'scripts.flows.bag_flow',
            'scripts.flows.union_technology_flow',
            'scripts.flows.tavern_quest_flow',
            'scripts.flows.faction_trials_flow',
            'scripts.flows.community_click_flow',
            'scripts.flows.marshall_speedup_all_flow',
            'scripts.flows',
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
        global zombie_attack_flow, community_click_flow, marshall_speedup_all_flow, apply_marshall_and_verify
        global quick_production_flow

        from scripts.flows import (handshake_flow, treasure_map_flow, corn_harvest_flow,
                          gold_coin_flow, harvest_box_flow, iron_bar_flow, gem_flow,
                          cabbage_flow, equipment_enhancement_flow, elite_zombie_flow,
                          afk_rewards_flow, union_gifts_flow, union_technology_flow,
                          hero_upgrade_arms_race_flow, stamina_claim_flow, stamina_use_flow,
                          soldier_training_flow, soldier_upgrade_flow, rally_join_flow,
                          healing_flow, bag_flow, gift_box_flow, quick_production_flow)
        from scripts.flows.tavern_quest_flow import tavern_quest_claim_flow, run_tavern_quest_flow
        from scripts.flows.faction_trials_flow import faction_trials_flow
        from scripts.flows.zombie_attack_flow import zombie_attack_flow
        from scripts.flows.community_click_flow import community_click_flow
        from scripts.flows.marshall_speedup_all_flow import marshall_speedup_all_flow, apply_marshall_and_verify

        self.logger.info("HOT-RELOAD: All flow modules reloaded")

    def get_available_flows(self) -> dict[str, tuple[Callable[..., Any], bool]]:
        """
        Return dict of flow_name -> (flow_func, is_critical).

        Used by WebSocket API to list and trigger flows.
        """
        return {
            # Tavern modes - each does ONE thing
            "tavern_quest": (partial(run_tavern_quest_flow, mode="claim"), True),  # Legacy name - now just claim
            "tavern_claim": (self._run_tavern_claim_with_retries, True),
            "tavern_scan": (self._run_tavern_scan_twice, True),
            "tavern_dispatch": (partial(run_tavern_quest_flow, mode="dispatch"), True),
            "tavern_ally": (partial(run_tavern_quest_flow, mode="ally"), True),
            "bag_flow": (bag_flow, True),
            "union_gifts": (union_gifts_flow, False),
            "union_technology": (union_technology_flow, False),
            "afk_rewards": (afk_rewards_flow, False),
            "hero_upgrade": (hero_upgrade_arms_race_flow, True),
            "soldier_training": (lambda adb: soldier_training_flow(adb, debug=False), True),
            "soldier_upgrade": (lambda adb: soldier_upgrade_flow(adb, debug=False), True),
            "healing": (healing_flow, False),
            "elite_zombie": (lambda adb: elite_zombie_flow(adb, target_level=ELITE_ZOMBIE_TARGET_LEVEL), False),
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
            "stamina_use": (lambda adb: stamina_use_flow(adb, self.windows_helper), False),
            "faction_trials": (lambda adb: faction_trials_flow(adb, self.windows_helper), True),
            "arms_race_check": (lambda adb: check_arms_race_progress(adb, self.windows_helper, debug=True), False),  # type: ignore[arg-type]
            "beast_training": (lambda adb: aggressive_beast_training_flow(adb, self.windows_helper), True),
            "community_checkin": (lambda adb: community_click_flow(adb, self.windows_helper), False),
            "royal_city_attack": (lambda adb: royal_city_attack_flow(adb, self.windows_helper), False),
            "union_coal": (union_coal_flow, False),
            "union_furnace": (union_furnace_flow, False),
            "marshall_speedup": (lambda adb: marshall_speedup_all_flow(adb, self.windows_helper, debug=True), True),
            "apply_marshall": (lambda adb: apply_marshall_and_verify(adb, self.windows_helper, debug=True), True),
            "speedup_barracks": (lambda adb: marshall_speedup_all_flow(adb, self.windows_helper, skip_marshall=True, debug=True), True),
            "quick_production": (lambda adb: quick_production_flow(adb, self.windows_helper), False),
        }

    def get_status(self) -> dict[str, Any]:
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
            "view": self.last_view_state,  # TOWN, WORLD, CHAT, UNKNOWN
            "arms_race": {
                "event": arms_race.get("current"),
                "day": arms_race.get("day"),
                "time_remaining": str(arms_race.get("time_remaining", "")),
            },
            "tavern_claims_today": self.scheduler.get_tavern_claims_today(),
            "overlord_first_kill_done": self.scheduler.is_overlord_first_kill_done(),
            "server_port": DAEMON_SERVER_PORT,
        }

    def set_config(self, key: str, value: Any) -> dict[str, Any]:
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

    def run(self) -> None:
        """Main detection loop."""
        self.logger.info(f"Starting detection loop (interval: {self.interval}s)")
        self.logger.info("Detecting: Handshake, Treasure map, Corn, Gold, Harvest box, Iron, Gem, Cabbage, Equipment, World")
        print("Press Ctrl+C to stop")
        print("=" * 60)

        # Cleanup old screenshots (>3 days) on startup
        cleanup_old_screenshots()
        self.last_screenshot_cleanup = time.time()

        # Check resolution immediately on startup
        self._check_resolution(0)

        # Assert all required components are initialized (set by initialize())
        assert self.adb is not None, "ADBHelper not initialized"
        assert self.windows_helper is not None, "WindowsScreenshotHelper not initialized"
        assert self.ocr_client is not None, "OCRClient not initialized"
        assert self.handshake_matcher is not None, "HandshakeIconMatcher not initialized"
        assert self.treasure_matcher is not None, "TreasureMapMatcher not initialized"
        assert self.corn_matcher is not None, "CornHarvestMatcher not initialized"
        assert self.gold_matcher is not None, "GoldCoinMatcher not initialized"
        assert self.harvest_box_matcher is not None, "HarvestBoxMatcher not initialized"
        assert self.iron_matcher is not None, "IronBarMatcher not initialized"
        assert self.gem_matcher is not None, "GemMatcher not initialized"
        assert self.cabbage_matcher is not None, "CabbageMatcher not initialized"
        assert self.equipment_enhancement_matcher is not None, "EquipmentEnhancementMatcher not initialized"
        assert self.hospital_matcher is not None, "HospitalStateMatcher not initialized"
        assert self.back_button_matcher is not None, "BackButtonMatcher not initialized"
        assert self.dog_house_matcher is not None, "DogHouseMatcher not initialized"
        assert self.afk_rewards_matcher is not None, "AfkRewardsMatcher not initialized"
        assert self.barracks_matcher is not None, "BarracksStateMatcher not initialized"
        assert self.rally_march_matcher is not None, "RallyMarchButtonMatcher not initialized"

        iteration = 0
        while True:
            iteration += 1

            try:
                # Initialize stamina tracking for this iteration (set properly at line ~1802)
                stamina_confirmed = False
                confirmed_stamina: int | None = None

                # Check if paused via API
                if self.paused:
                    if iteration % 30 == 0:  # Log every ~1 min when paused
                        self.logger.info(f"[{iteration}] PAUSED (use daemon_cli.py resume to unpause)")
                    time.sleep(self.interval)
                    continue

                # Hard stuck detection from app telemetry:
                # ALWAYS restart immediately on ui_timeout burst, even during manual sessions.
                if self._check_ui_timeout_burst_and_restart(iteration):
                    continue

                # Get idle time early (needed for foreground check and other decisions)
                idle_secs_early = get_user_idle_seconds()

                # Periodic state save (every N iterations for resumability)
                if iteration % self.state_save_interval == 0:
                    self._save_runtime_state()

                # Periodic garbage collection (every 100 iterations to prevent memory leak)
                if iteration % 100 == 0:
                    gc.collect()
                    # Clear GPU template cache to prevent VRAM leak
                    released = clear_gpu_cache()
                    if released > 0:
                        self.logger.debug(f"[{iteration}] Released {released} GPU objects")
                    # Periodic scheduler maintenance:
                    # - Day rollover (if daemon runs across midnight)
                    # - Prune old/invalid flow history entries
                    maintenance = self.scheduler.run_periodic_maintenance()
                    if maintenance["day_reset"] or maintenance["pruned_entries"] > 0:
                        self.logger.info(
                            f"[{iteration}] Scheduler maintenance: "
                            f"day_reset={maintenance['day_reset']} "
                            f"pruned_entries={maintenance['pruned_entries']}"
                        )

                # Check if xclash is running and in foreground
                if not self._is_xclash_in_foreground():
                    # Skip recovery during critical flows - they manage their own state
                    if self.critical_flow_active:
                        self.logger.debug(f"[{iteration}] xclash not in foreground but critical flow {self.critical_flow_name} active - skipping recovery")
                        continue
                    # Only recover if user is idle - don't interrupt active user
                    if idle_secs_early >= self.IDLE_THRESHOLD:
                        self.logger.warning(f"[{iteration}] xclash not in foreground, user idle - running full recovery...")
                        return_to_base_view(self.adb, self.windows_helper, debug=True)
                    else:
                        self.logger.debug(f"[{iteration}] xclash not in foreground, user active (idle={idle_secs_early:.1f}s) - skipping recovery")
                    continue  # Skip this iteration, start fresh

                # =================================================================
                # BLOCKED CHECK - Must happen BEFORE screenshot to avoid race condition
                # Both daemon and flow threads use windows_helper - concurrent access crashes
                # =================================================================
                # reinforce_loop and tavern_steal_sniper run inline in this thread (no
                # concurrent windows_helper access), so they skip the early block.
                if self.critical_flow_active and self.critical_flow_name not in ("reinforce_loop", "tavern_steal_sniper"):
                    # Check for timeout - auto-clear stuck critical flows
                    # Treasure flows get 10 min timeout, others get 2 min
                    if self.critical_flow_start_time is not None:
                        elapsed = time.time() - self.critical_flow_start_time
                        is_treasure = self.critical_flow_name and "treasure" in self.critical_flow_name.lower()
                        timeout = 600 if is_treasure else self.CRITICAL_FLOW_TIMEOUT  # 10 min vs 2 min
                        if elapsed > timeout:
                            flow_thread = self.critical_flow_thread
                            if flow_thread is not None and flow_thread.is_alive():
                                # Flow thread is still running - clearing the flags now would
                                # let the daemon screenshot/tap concurrently with it (crash risk).
                                # Keep blocking until the thread actually exits.
                                self.logger.error(
                                    f"[{iteration}] CRITICAL FLOW TIMEOUT: {self.critical_flow_name} "
                                    f"stuck for {elapsed:.0f}s but its thread is still alive - waiting for exit"
                                )
                                time.sleep(self.interval)
                                continue
                            self.logger.error(f"[{iteration}] CRITICAL FLOW TIMEOUT: {self.critical_flow_name} stuck for {elapsed:.0f}s - force clearing!")
                            with self.flow_lock:
                                self.active_flows.discard(self.critical_flow_name)
                                self.critical_flow_active = False
                                self.critical_flow_name = None
                                self.critical_flow_start_time = None
                                self.critical_flow_thread = None
                            # Fall through to take screenshot and continue
                        else:
                            self.logger.info(f"[{iteration}] BLOCKED: Critical flow active ({self.critical_flow_name}, {elapsed:.0f}s)")
                            time.sleep(self.interval)
                            continue  # Skip WITHOUT taking screenshot
                    else:
                        self.logger.info(f"[{iteration}] BLOCKED: Critical flow active ({self.critical_flow_name})")
                        time.sleep(self.interval)
                        continue  # Skip WITHOUT taking screenshot

                # Take single screenshot for all checks (only when NOT blocked)
                frame = self.windows_helper.get_screenshot_cv2()

                # Periodic screenshot cleanup (every 6 hours)
                current_time_for_cleanup = time.time()
                if current_time_for_cleanup - self.last_screenshot_cleanup > self.SCREENSHOT_CLEANUP_INTERVAL:
                    self.last_screenshot_cleanup = current_time_for_cleanup
                    cleanup_old_screenshots()

                # Periodic shield inventory check (every 6 hours)
                # Only run if not in critical flow and user is idle
                if (current_time_for_cleanup - self.last_shield_inventory_check > self.SHIELD_INVENTORY_INTERVAL
                    and not self.critical_flow_active
                    and get_user_idle_seconds() >= self.IDLE_THRESHOLD):
                    self.last_shield_inventory_check = current_time_for_cleanup
                    self.logger.info(f"[{iteration}] Running periodic shield inventory check...")
                    try:
                        from scripts.flows.shield_inventory_flow import shield_inventory_flow
                        result = shield_inventory_flow(self.adb, self.windows_helper, debug=False)
                        self.logger.info(f"[{iteration}] Shield inventory: {result}")
                    except Exception as e:
                        self.logger.error(f"[{iteration}] Shield inventory check failed: {e}")

                # =================================================================
                # VIEW STATE DETECTION - Run FIRST to know what checks to do
                # =================================================================
                view_state_enum, view_score = detect_view(frame)
                view_state_str = view_state_enum.value.upper()  # "TOWN", "WORLD", "CHAT", "UNKNOWN"
                self.last_view_state = view_state_str  # Store for dashboard API

                # =================================================================
                # UNION WAR PANEL GUARD - If stale panel is open, exit when user is idle
                # =================================================================
                # Avoid interfering with active flows that intentionally use this panel.
                # Also avoid interfering with manual user actions.
                if not self.active_flows and idle_secs_early >= self.IDLE_THRESHOLD:
                    panel_present, panel_score = self.union_war_panel_detector.is_union_war_panel(frame)
                    if panel_present:
                        now_ts = time.time()
                        if now_ts - self.last_union_war_panel_back_click >= self.UNION_WAR_PANEL_BACK_COOLDOWN:
                            back_found, back_score, back_pos, back_template = self.back_button_matcher.find(frame)
                            click_pos = back_pos if back_found and back_pos is not None else BACK_BUTTON_CLICK
                            self.logger.warning(
                                f"[{iteration}] UNION WAR PANEL GUARD: panel detected (score={panel_score:.4f}) "
                                f"- clicking back at {click_pos} "
                                f"(template={back_template or 'fallback'}, score={back_score:.4f})"
                            )
                            mark_daemon_action()
                            self.adb.tap(*click_pos, source="daemon:union_war_panel_guard")
                            self.last_union_war_panel_back_click = now_ts
                            time.sleep(1.0)
                            continue

                # =================================================================
                # UNDER ATTACK DETECTION - Check if player is being attacked
                # =================================================================
                from utils.under_attack_matcher import is_under_attack
                attack_detected, attack_score = is_under_attack(frame)

                if attack_detected and not self.under_attack:
                    # Attack started - log it
                    self.under_attack = True
                    self.last_attack_log_time = time.time()
                    self.logger.warning(f"[{iteration}] UNDER ATTACK! (score={attack_score:.4f})")
                    # Update persistent state
                    from utils.current_state import update_under_attack
                    update_under_attack(True)
                    # Record event for frontend
                    self.scheduler.record_event(
                        flow_name="under_attack",
                        status="detected",
                        result={"score": attack_score, "view": view_state_str},
                        category="combat",
                        is_critical=True,
                    )
                    # Broadcast to connected clients
                    if self.command_server:
                        self.command_server.broadcast("under_attack", {
                            "detected": True,
                            "score": attack_score,
                            "timestamp": datetime.now().isoformat(),
                        })
                elif not attack_detected and self.under_attack:
                    # Attack ended
                    self.under_attack = False
                    self.logger.info(f"[{iteration}] Attack ended - safe now")
                    # Update persistent state
                    from utils.current_state import update_under_attack
                    update_under_attack(False)
                    self.scheduler.record_event(
                        flow_name="under_attack",
                        status="ended",
                        result={"view": view_state_str},
                        category="combat",
                        is_critical=False,
                    )
                    if self.command_server:
                        self.command_server.broadcast("under_attack", {
                            "detected": False,
                            "timestamp": datetime.now().isoformat(),
                        })

                # =================================================================
                # BLOODLUST DETECTION - Check if bloodlust is active (15 min duration)
                # =================================================================
                from utils.bloodlust_matcher import is_bloodlust_active, BLOODLUST_DURATION_SECONDS
                bloodlust_detected, bloodlust_score = is_bloodlust_active(frame)

                if bloodlust_detected and not self.bloodlust_active:
                    # Bloodlust just started
                    self.bloodlust_active = True
                    self.bloodlust_started_at = time.time()
                    self.logger.info(f"[{iteration}] BLOODLUST ACTIVE! (score={bloodlust_score:.4f}) - expires in 15 min")
                    # Update persistent state
                    from utils.current_state import update_bloodlust
                    update_bloodlust(True)
                    # Record event for frontend
                    self.scheduler.record_event(
                        flow_name="bloodlust",
                        status="started",
                        result={"score": bloodlust_score, "duration_seconds": BLOODLUST_DURATION_SECONDS},
                        category="combat",
                        is_critical=False,
                    )
                    if self.command_server:
                        self.command_server.broadcast("bloodlust", {
                            "active": True,
                            "started_at": datetime.now().isoformat(),
                            "duration_seconds": BLOODLUST_DURATION_SECONDS,
                        })
                elif not bloodlust_detected and self.bloodlust_active:
                    # Bloodlust ended
                    duration = time.time() - self.bloodlust_started_at if self.bloodlust_started_at else 0
                    self.bloodlust_active = False
                    self.bloodlust_started_at = None
                    self.logger.info(f"[{iteration}] Bloodlust ended after {duration:.0f}s")
                    # Update persistent state
                    from utils.current_state import update_bloodlust
                    update_bloodlust(False)
                    self.scheduler.record_event(
                        flow_name="bloodlust",
                        status="ended",
                        result={"duration_seconds": duration},
                        category="combat",
                        is_critical=False,
                    )
                    if self.command_server:
                        self.command_server.broadcast("bloodlust", {
                            "active": False,
                            "ended_at": datetime.now().isoformat(),
                            "duration_seconds": duration,
                        })

                # =================================================================
                # SHIELD ACTIVE DETECTION - Check if player has shield protection
                # =================================================================
                from utils.shield_active_matcher import is_shield_active
                shield_detected, shield_score = is_shield_active(frame)

                if shield_detected and not self.shield_protection_active:
                    # Shield just became active
                    self.shield_protection_active = True
                    self.logger.info(f"[{iteration}] SHIELD PROTECTION ACTIVE (score={shield_score:.4f})")
                    from utils.current_state import update_shield_active
                    update_shield_active(True)
                    if self.command_server:
                        self.command_server.broadcast("shield_active", {
                            "active": True,
                            "timestamp": datetime.now().isoformat(),
                        })
                elif not shield_detected and self.shield_protection_active:
                    # Shield ended
                    self.shield_protection_active = False
                    self.logger.info(f"[{iteration}] Shield protection ended")
                    from utils.current_state import update_shield_active
                    update_shield_active(False)
                    self.scheduler.record_event(
                        flow_name="shield_expired",
                        status="ended",
                        result={},
                        category="combat",
                        is_critical=True,
                    )
                    if self.command_server:
                        self.command_server.broadcast("shield_active", {
                            "active": False,
                            "timestamp": datetime.now().isoformat(),
                        })

                # =================================================================
                # DAEMON FRAME DEBUG - optional (disabled by default)
                # =================================================================
                if DAEMON_FRAME_CAPTURE_ENABLED and DAEMON_FRAME_CAPTURE_EVERY_N > 0:
                    if iteration % DAEMON_FRAME_CAPTURE_EVERY_N == 0:
                        last_stam = self.stamina_reader.history[-1] if self.stamina_reader.history else None
                        _save_daemon_frame(frame, view_state_str, last_stam)

                # =================================================================
                # FLOW CANDIDATE COLLECTION
                # All flow detection adds to this list - NO direct execution here.
                # At the end of detection, _execute_best_flow() picks ONE to run.
                # This prevents flows from stepping on each other.
                # =================================================================
                flow_candidates: list[FlowCandidate] = []

                # Check IMMEDIATE action icons (fixed spots, fast ~1ms each)
                # Handshake: always check (fixed spot)
                handshake_present, handshake_score = self.handshake_matcher.is_present(frame)
                # Treasure: only in TOWN or WORLD (fixed spot)
                if view_state_enum in (ViewState.TOWN, ViewState.WORLD):
                    treasure_present, treasure_score = self.treasure_matcher.is_present(frame)
                else:
                    treasure_present, treasure_score = False, 1.0
                # Harvest box: only in TOWN (fixed spot)
                if view_state_enum == ViewState.TOWN:
                    harvest_present, harvest_score = self.harvest_box_matcher.is_present(frame)
                else:
                    harvest_present, harvest_score = False, 1.0

                # IMMEDIATE execution for handshake - but with cooldown to prevent rapid-fire
                if handshake_present and self._can_run_flow():
                    now = time.time()
                    if now - self._last_handshake_click >= self.HANDSHAKE_COOLDOWN:
                        self.logger.info(f"[{iteration}] HANDSHAKE detected (score={handshake_score:.4f}) - executing immediately")
                        self._run_flow("handshake", handshake_flow)
                        self._last_handshake_click = now
                        continue  # Skip rest of iteration, start fresh

                # =================================================================
                # REINFORCE MODE - Loop reinforce camp as critical flow
                # =================================================================
                reinforce_active, _ = self.scheduler.get_reinforce_mode()
                if reinforce_active:
                    # Set critical flow to block everything
                    if not self.critical_flow_active:
                        self.critical_flow_active = True
                        self.critical_flow_name = "reinforce_loop"
                        self.critical_flow_start_time = time.time()
                        self.logger.info(f"[{iteration}] REINFORCE LOOP: Activated as critical flow")

                    # Run reinforce flow if interval elapsed
                    interval = self.reinforce_interval or 10
                    now = time.time()
                    if now - self.last_reinforce_time >= interval:
                        self.logger.info(f"[{iteration}] REINFORCE LOOP: Running reinforce_camp_star (interval={interval}s)")
                        from scripts.flows.reinforce_camp_star_flow import reinforce_camp_star_flow
                        try:
                            reinforce_camp_star_flow(self.adb, self.windows_helper, debug=False)
                        except Exception as e:
                            self.logger.error(f"[{iteration}] REINFORCE LOOP failed: {e}")
                        self.last_reinforce_time = now

                    time.sleep(self.interval)
                    continue
                else:
                    # Clear critical flow if reinforce mode was just disabled
                    if self.critical_flow_active and self.critical_flow_name == "reinforce_loop":
                        self.critical_flow_active = False
                        self.critical_flow_name = None
                        self.critical_flow_start_time = None
                        self.logger.info(f"[{iteration}] REINFORCE LOOP: Deactivated")

                # =================================================================
                # TAVERN STEAL SNIPER MODE - exclusive chest sniping
                # Blocks everything except tavern quests: if a tavern claim is
                # due, the mode exits so the normal claim machinery takes over.
                # =================================================================
                sniper_active, _ = self.scheduler.get_sniper_mode()
                if sniper_active:
                    if self.scheduler.is_tavern_completion_imminent(buffer_seconds=30):
                        self.logger.info(f"[{iteration}] STEAL SNIPER: tavern claim due - exiting sniper mode")
                        self.scheduler.clear_sniper_mode()
                        sniper_active = False
                    else:
                        if not self.critical_flow_active:
                            self.critical_flow_active = True
                            self.critical_flow_name = "tavern_steal_sniper"
                            self.critical_flow_start_time = time.time()
                            self.logger.info(f"[{iteration}] STEAL SNIPER: Activated as critical flow")

                        from config import SNIPER_TICK_SLEEP
                        from scripts.flows.tavern_steal_sniper_flow import sniper_tick
                        try:
                            tick = sniper_tick(self.adb, self.windows_helper)
                            if tick.get("newly_locked"):
                                self.logger.info(
                                    f"[{iteration}] STEAL SNIPER: SNIPE ACTIVATED - "
                                    f"{tick.get('seconds_left')}s until steal"
                                )
                            if tick.get("last_result"):
                                self.logger.info(f"[{iteration}] STEAL SNIPER: result={tick['last_result']}")
                        except Exception as e:
                            self.logger.error(f"[{iteration}] STEAL SNIPER tick failed: {e}")

                        time.sleep(SNIPER_TICK_SLEEP)
                        continue
                if not sniper_active:
                    # Clear critical flow if sniper mode was just disabled
                    if self.critical_flow_active and self.critical_flow_name == "tavern_steal_sniper":
                        self.critical_flow_active = False
                        self.critical_flow_name = None
                        self.critical_flow_start_time = None
                        from scripts.flows.tavern_steal_sniper_flow import reset_sniper_status
                        reset_sniper_status()
                        self.logger.info(f"[{iteration}] STEAL SNIPER: Deactivated")

                # =================================================================
                # SCHEDULED FLOWS - Royal City Reinforce (Fridays 6:15-9:00 AM PT)
                # =================================================================
                if self._should_run_royal_city_reinforce() and self._can_run_flow():
                    self.logger.info(f"[{iteration}] ROYAL CITY REINFORCE: Friday window, attempting reinforce...")
                    self._royal_city_last_attempt = time.time()

                    # Run the flow SYNCHRONOUSLY to check actual result
                    # _run_flow_sync returns {"success": True, "result": flow_result}
                    # where "success" means "ran without exception", "result" is the actual flow return value
                    sync_result = self._run_flow_sync("royal_city_attack", royal_city_attack_flow)
                    flow_result = sync_result.get("result") if isinstance(sync_result, dict) else sync_result
                    success = bool(flow_result)  # royal_city_attack_flow returns True/False

                    if success:
                        # Successfully marched - stop retrying this Friday
                        self._royal_city_success_date = datetime.now(self.pacific_tz).date()
                        self.logger.info(f"[{iteration}] ROYAL CITY REINFORCE: SUCCESS! Troops dispatched, won't retry today.")
                    else:
                        cooldown, _ = get_override_manager().get_effective("ROYAL_CITY_REINFORCE_COOLDOWN", 900)
                        self.logger.info(f"[{iteration}] ROYAL CITY REINFORCE: Failed, will retry in {cooldown // 60} minutes")

                    continue  # Skip rest of iteration after scheduled flow

                if treasure_present:
                    # Already validated: treasure only checked in TOWN/WORLD
                    flow_candidates.append(FlowCandidate(
                        name="treasure_map",
                        flow_func=treasure_map_flow,
                        priority=FlowPriority.URGENT,
                        critical=True,
                        reason=f"score={treasure_score:.4f}, view={view_state_str}"
                    ))

                if harvest_present:
                    flow_candidates.append(FlowCandidate(
                        name="harvest_box",
                        flow_func=harvest_box_flow,
                        priority=FlowPriority.URGENT,
                        reason=f"score={harvest_score:.4f}"
                    ))

                # Tavern Quest claim - check if completion is imminent (within 11 seconds)
                # Uses CLAIM mode - just clicks Claim buttons, no OCR, no Go buttons
                if self.scheduler.is_tavern_completion_imminent(buffer_seconds=7):
                    flow_candidates.append(FlowCandidate(
                        name="tavern_claim",
                        flow_func=self._run_tavern_claim_with_retries,
                        priority=FlowPriority.CRITICAL,  # Imminent completion is time-critical
                        critical=True,
                        reason="completion imminent"
                    ))

                # Get current time for cooldown checks
                current_time = time.time()

                # Rally march button check (requires idle + cooldown, but not alignment)
                if self._get_config('RALLY_JOIN_ENABLED', RALLY_JOIN_ENABLED):
                    march_match = self.rally_march_matcher.find_march_button(frame)
                    march_present = march_match is not None
                    march_score = march_match[2] if march_match else 1.0

                    if march_present and march_match is not None:
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
                        rally_suppressed = current_time < self.rally_march_suppress_until

                        # Log Union Boss mode status
                        if in_union_boss_mode:
                            remaining = int(self.union_boss_mode_until - current_time)
                            self.logger.debug(f"[{iteration}] UNION BOSS MODE: {remaining}s remaining, cooldown={rally_cooldown}s")

                        if rally_suppressed:
                            remaining = int(self.rally_march_suppress_until - current_time)
                            self.logger.debug(f"[{iteration}] RALLY: Suppressed for {remaining}s after no-action outcome")
                        elif rally_idle_ok and rally_view_ok and rally_cooldown_elapsed:
                            # Check if another flow is running BEFORE clicking
                            if not self._can_run_flow():
                                self.logger.debug(f"[{iteration}] RALLY: Skipping - another flow is active")
                            else:
                                mode_str = " [BOSS MODE]" if in_union_boss_mode else ""
                                self.logger.info(f"[{iteration}] RALLY MARCH button detected at ({march_x}, {march_y}), score={march_score:.4f}{mode_str}")

                                # Click march button and verify panel opened (may need multiple clicks if arrow toggled)
                                panel_detector = UnionWarPanelDetector()
                                panel_opened = False
                                click_x, click_y = self.rally_march_matcher.get_click_position(march_x, march_y)

                                for attempt in range(3):
                                    # Check if panel is already open BEFORE clicking
                                    verify_frame = self.windows_helper.get_screenshot_cv2()
                                    panel_present, panel_score = panel_detector.is_union_war_panel(verify_frame)

                                    # Save debug screenshot
                                    ts = datetime.now().strftime("%H%M%S")
                                    debug_path = Path("screenshots/debug") / f"rally_march_{ts}_attempt{attempt+1}_panel{'_OPEN' if panel_present else '_CLOSED'}.png"
                                    debug_path.parent.mkdir(parents=True, exist_ok=True)
                                    cv2.imwrite(str(debug_path), verify_frame)

                                    if panel_present:
                                        self.logger.info(f"[{iteration}] Union War panel detected (attempt {attempt + 1}, score={panel_score:.4f})")
                                        panel_opened = True
                                        break

                                    # Panel not open - click to open/toggle
                                    self.logger.info(f"[{iteration}] Panel not open (attempt {attempt + 1}, score={panel_score:.4f}) - clicking")
                                    mark_daemon_action()
                                    self.adb.tap(click_x, click_y, source="daemon:rally_march")
                                    time.sleep(0.5)  # Wait for panel/animation

                                self.last_rally_march_click = current_time

                                if not panel_opened:
                                    self.logger.warning(f"[{iteration}] Failed to open Union War panel after 3 attempts - skipping")
                                    continue  # Skip to next iteration

                                # Run rally join flow via _run_flow_sync to get result AND coordinate with other flows
                                flow_result = self._run_flow_sync(
                                    "rally_join_flow",
                                    lambda adb: rally_join_flow(adb, union_boss_mode=in_union_boss_mode),
                                    critical=True
                                )
                                if flow_result.get("success"):
                                    result = flow_result.get("result", {})
                                    abort_reason = result.get("abort_reason")
                                    if abort_reason in ("no_rallies", "no_matching_monster"):
                                        suppress_seconds = 120 if in_union_boss_mode else 180
                                        self.rally_march_suppress_until = current_time + suppress_seconds
                                        self.logger.info(
                                            f"[{iteration}] RALLY: {abort_reason}, suppressing march retries for {suppress_seconds}s"
                                        )
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

                # Extract stamina using OCR server (throttled - expensive operation)
                # Only run OCR every STAMINA_OCR_INTERVAL seconds, use cached value otherwise
                if current_time - self.last_stamina_ocr_time >= self.stamina_ocr_interval:
                    try:
                        stamina = self.ocr_client.extract_number(frame, self.STAMINA_REGION)
                        # Reject implausible OCR garbage (e.g. 123456789 from a
                        # misread/empty crop). Stamina maxes ~500 with recovery
                        # items; anything outside 0-500 is a bad read, treated as
                        # a failure so it neither caches nor poisons gating.
                        if stamina is not None and not (0 <= stamina <= STAMINA_OCR_MAX_VALID):
                            self.logger.warning(f"[{iteration}] Implausible stamina OCR {stamina}, discarding")
                            stamina = None
                        if stamina is None:
                            self.ocr_consecutive_failures += 1
                        else:
                            self.ocr_consecutive_failures = 0  # Reset on success
                            self.cached_stamina = stamina  # Cache successful reading
                        self.last_stamina_ocr_time = current_time
                    except Exception as ocr_err:
                        self.logger.warning(f"[{iteration}] OCR error: {ocr_err}")
                        stamina = None
                        self.ocr_consecutive_failures += 1
                        self.last_stamina_ocr_time = current_time

                    # After 3 consecutive OCR failures, try to restart server
                    if self.ocr_consecutive_failures >= 3:
                        self.logger.warning(f"[{iteration}] {self.ocr_consecutive_failures} consecutive OCR failures, checking server health...")
                        self._check_ocr_server_health()
                        self.ocr_consecutive_failures = 0  # Reset counter after check
                else:
                    # Use cached stamina value between OCR reads
                    stamina = self.cached_stamina

                stamina_str = str(stamina) if stamina is not None else "?"

                # =================================================================
                # TOWN-ONLY MATCHERS (bubbles, afk, hospital - all fixed spots)
                # View state already detected at top of iteration
                # =================================================================
                # Initialize all to defaults (not present)
                corn_present, corn_score = False, 1.0
                gold_present, gold_score = False, 1.0
                iron_present, iron_score = False, 1.0
                gem_present, gem_score = False, 1.0
                cabbage_present, cabbage_score = False, 1.0
                equip_present, equip_score = False, 1.0
                hospital_state, hospital_score = HospitalState.UNKNOWN, 1.0
                afk_present, afk_score = False, 1.0
                back_present, back_score = False, 1.0

                # Only check town-specific icons when in TOWN
                if view_state_enum == ViewState.TOWN:
                    corn_present, corn_score = self.corn_matcher.is_present(frame)
                    gold_present, gold_score = self.gold_matcher.is_present(frame)
                    iron_present, iron_score = self.iron_matcher.is_present(frame)
                    gem_present, gem_score = self.gem_matcher.is_present(frame)
                    cabbage_present, cabbage_score = self.cabbage_matcher.is_present(frame)
                    equip_present, equip_score = self.equipment_enhancement_matcher.is_present(frame)
                    hospital_state, hospital_score = self.hospital_matcher.get_state(frame)
                    afk_present, afk_score = self.afk_rewards_matcher.is_present(frame)

                # Back button - ONLY checked during UNKNOWN recovery (expensive half-screen search)
                # Don't waste ~750ms every frame; it's checked in UNKNOWN recovery section when needed

                # DEBUG: Capture screenshot when view is CHAT or UNKNOWN (problematic states)
                if view_state_enum in (ViewState.CHAT, ViewState.UNKNOWN):
                    get_daemon_debug().capture(frame, iteration, view_state_str, "view_problem")

                # DEBUG: Periodic baseline capture (every 50 iterations)
                if iteration % 50 == 0:
                    get_daemon_debug().capture(frame, iteration, view_state_str, "baseline")

                # Reset UNKNOWN recovery loop counters when we're genuinely out of UNKNOWN
                # This only resets when detect_view returns TOWN/WORLD/WEBVIEW, not when return_to_base_view says "success"
                if view_state_enum in (ViewState.TOWN, ViewState.WORLD, ViewState.WEBVIEW) and self.unknown_recovery_count > 0:
                    self.logger.debug(f"[{iteration}] UNKNOWN loop counters reset (view={view_state_str})")
                    self.unknown_recovery_count = 0
                    self.unknown_first_recovery_time = None

                # For backwards compatibility with flow checks
                world_present = (view_state_enum == ViewState.TOWN)
                town_present = (view_state_enum == ViewState.WORLD)

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

                # Get barracks states (TOWN only - they're at fixed positions in town view)
                barracks_state_str = format_barracks_states(frame) if view_state_enum == ViewState.TOWN else "[B1:? B2:? B3:? B4:?]"

                # Update barracks history EVERY iteration during Soldier Training/VS day
                # This allows history to build up BEFORE idle threshold is met
                is_soldier_event_active = arms_race_event == "Soldier Training"
                is_vs_promo_day = arms_race['day'] in self.VS_SOLDIER_PROMOTION_DAYS
                if view_state_enum == ViewState.TOWN and (is_soldier_event_active or is_vs_promo_day):
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
                    view_state_enum == ViewState.TOWN and
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
                self.logger.info(f"[{iteration}] {pacific_time} [{view_state_str}] Stamina:{stamina_str} idle:{idle_str} AR:{arms_race_event[:3]}({arms_race_remaining_mins}m){vs_indicator}{special_events_indicator} Barracks:[{barracks_state_str}] H:{handshake_score:.3f} T:{treasure_score:.3f} C:{corn_score:.3f} G:{gold_score:.3f} HB:{harvest_score:.3f} I:{iron_score:.3f} Gem:{gem_score:.3f} Cab:{cabbage_score:.3f} Eq:{equip_score:.3f} Hosp:{hospital_state_char}({hospital_score:.3f}) AFK:{afk_score:.3f} V:{view_score:.3f} B:{back_score:.3f}")

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
                harvest_bubbles_enabled = self._get_config('HARVEST_BUBBLES_ENABLED', True)
                beast_training_enabled = self._get_config('ARMS_RACE_BEAST_TRAINING_ENABLED', ARMS_RACE_BEAST_TRAINING_ENABLED)
                # Require stronger certainty before any harvest click candidate is queued.
                # This prevents borderline template matches from hijacking UI interactions.
                HARVEST_STRONG_MATCH_MAX = 0.02
                if (beast_training_enabled and
                    arms_race_event == "Mystic Beast Training" and
                    arms_race_remaining_mins <= self.ARMS_RACE_BEAST_TRAINING_LAST_MINUTES and
                    stamina_confirmed and
                    confirmed_stamina is not None and
                    confirmed_stamina >= self.BEAST_TRAINING_STAMINA_THRESHOLD):
                    beast_training_priority = True
                    self.logger.debug(f"[{iteration}] BEAST TRAINING PRIORITY: Skipping harvest flows (stamina={confirmed_stamina}, event_remaining={arms_race_remaining_mins}min)")
                if not harvest_bubbles_enabled:
                    self.logger.debug(f"[{iteration}] HARVEST: Disabled by HARVEST_BUBBLES_ENABLED=False")

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
                harvest_bubbles = [
                    ("corn_harvest", corn_present, corn_score, corn_harvest_flow),
                    ("gold_coin", gold_present, gold_score, gold_coin_flow),
                    ("iron_bar", iron_present, iron_score, iron_bar_flow),
                    ("gem", gem_present, gem_score, gem_flow),
                    ("cabbage", cabbage_present, cabbage_score, cabbage_flow),
                    ("equipment_enhancement", equip_present, equip_score, equipment_enhancement_flow),
                ]
                for bubble_name, bubble_present, bubble_score, bubble_flow in harvest_bubbles:
                    if (harvest_bubbles_enabled and bubble_present and bubble_score <= HARVEST_STRONG_MATCH_MAX and
                        world_present and harvest_aligned and not beast_training_priority and self._is_user_idle()):
                        flow_candidates.append(FlowCandidate(
                            name=bubble_name,
                            flow_func=bubble_flow,
                            priority=FlowPriority.LOW,
                            reason=f"score={bubble_score:.4f}",
                            record_to_scheduler=True
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
                            # Check if hospital soldier claiming is enabled
                            from utils.config_overrides import get_override_manager
                            claim_enabled, _ = get_override_manager().get_effective("HOSPITAL_SOLDIER_CLAIM_ENABLED", True)
                            if claim_enabled:
                                # Create a simple click flow
                                def _help_ready_flow(adb: Any, x: int = hospital_click_x, y: int = hospital_click_y) -> None:
                                    mark_daemon_action()
                                    adb.tap(x, y, source="daemon:hospital_help")
                                flow_candidates.append(FlowCandidate(
                                    name="hospital_help",
                                    flow_func=_help_ready_flow,
                                    priority=FlowPriority.HIGH,
                                    reason=f"HELP_READY {help_ready_count}/{self.HOSPITAL_CONSECUTIVE_REQUIRED}"
                                ))
                            else:
                                self.logger.debug(f"[{iteration}] HOSPITAL: Soldier claiming disabled by config, skipping")

                        # HEALING: Click to open panel, run healing flow
                        elif healing_count >= min_required:
                            # Check if hospital healing is enabled
                            from utils.config_overrides import get_override_manager
                            heal_enabled, _ = get_override_manager().get_effective("HOSPITAL_HEAL_ENABLED", True)
                            if heal_enabled:
                                # Create wrapper that clicks, waits, then runs healing_flow
                                def _healing_wrapper(adb: Any, x: int = hospital_click_x, y: int = hospital_click_y) -> None:
                                    mark_daemon_action()
                                    adb.tap(x, y, source="daemon:hospital_healing")
                                    time.sleep(2.5)  # Wait for panel to fully open
                                    healing_flow(adb)
                                flow_candidates.append(FlowCandidate(
                                    name="healing",
                                    flow_func=_healing_wrapper,
                                    priority=FlowPriority.HIGH,
                                    reason=f"HEALING {healing_count}/{self.HOSPITAL_CONSECUTIVE_REQUIRED}"
                                ))
                            else:
                                self.logger.debug(f"[{iteration}] HOSPITAL: Healing disabled by config, skipping")

                        # SOLDIERS_WOUNDED: Click to open panel, run healing flow
                        elif wounded_count >= min_required:
                            # Check if hospital healing is enabled
                            from utils.config_overrides import get_override_manager
                            heal_enabled, _ = get_override_manager().get_effective("HOSPITAL_HEAL_ENABLED", True)
                            if heal_enabled:
                                # Create wrapper that clicks, waits, then runs healing_flow
                                def _wounded_wrapper(adb: Any, x: int = hospital_click_x, y: int = hospital_click_y) -> None:
                                    mark_daemon_action()
                                    adb.tap(x, y, source="daemon:hospital_wounded")
                                    time.sleep(2.5)  # Wait for panel to fully open
                                    healing_flow(adb)
                                flow_candidates.append(FlowCandidate(
                                    name="healing",
                                    flow_func=_wounded_wrapper,
                                    priority=FlowPriority.HIGH,
                                    reason=f"WOUNDED {wounded_count}/{self.HOSPITAL_CONSECUTIVE_REQUIRED}"
                                ))
                            else:
                                self.logger.debug(f"[{iteration}] HOSPITAL: Healing disabled by config, skipping")
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
                # CHAT STUCK ESCAPE
                # CHAT is a known view, so UNKNOWN recovery never fires for it,
                # and the back-button matcher is no longer run every frame.
                # If we sit in CHAT while the user is idle, click back out.
                # =================================================================
                if view_state_enum == ViewState.CHAT:
                    if self.chat_state_start is None:
                        self.chat_state_start = time.time()
                    chat_duration = time.time() - self.chat_state_start
                    if (chat_duration >= self.CHAT_STUCK_TIMEOUT
                            and idle_secs >= self.CHAT_STUCK_IDLE_REQUIRED
                            and time.time() - self.last_chat_back_attempt >= self.CHAT_STUCK_TIMEOUT
                            and not self.active_flows):
                        self.last_chat_back_attempt = time.time()
                        self.logger.info(
                            f"[{iteration}] CHAT STUCK: in chat {chat_duration:.0f}s, "
                            f"user idle {idle_secs:.0f}s - clicking back out"
                        )
                        self._run_flow(
                            "back_from_chat",
                            lambda adb: back_from_chat_flow(adb, self.windows_helper),
                        )
                else:
                    self.chat_state_start = None

                # =================================================================
                # UNKNOWN STATE TRACKING AND RECOVERY
                # =================================================================

                # Track UNKNOWN state duration (with hysteresis to prevent flicker resets)
                if view_state_enum == ViewState.UNKNOWN:
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
                            self.logger.debug(f"[{iteration}] Left UNKNOWN state (now {view_state_str}), starting hysteresis...")
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
                if view_state_enum == ViewState.UNKNOWN and not self.active_flows:
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
                                self.adb.tap(*confirm_pos, source="daemon:disconnection_confirm")
                                self.disconnection_dialog_detected_time = None
                                self.unknown_state_start = None
                                self.unknown_state_left_time = None
                                time.sleep(2)  # Wait for reconnect
                                continue
                            else:
                                # Still waiting, skip normal recovery
                                wait_remaining: float = DISCONNECTION_WAIT_SECONDS - wait_elapsed
                                if iteration % 10 == 0:  # Log every 10 iterations
                                    self.logger.debug(f"[{iteration}] DISCONNECTION DIALOG: Waiting... {wait_remaining:.0f}s remaining")
                                continue
                        else:
                            # No disconnection dialog, reset timer if it was set
                            if self.disconnection_dialog_detected_time is not None:
                                self.logger.debug(f"[{iteration}] DISCONNECTION DIALOG: Dialog dismissed externally")
                                self.disconnection_dialog_detected_time = None

                        # RECOVERY - try every iteration once user is idle
                        # Require at least 3 seconds in UNKNOWN to avoid false triggers from intermittent bad frames
                        UNKNOWN_MIN_DURATION = 3  # Minimum seconds in UNKNOWN before recovery starts
                        if effective_idle_secs >= self.IDLE_THRESHOLD and unknown_duration >= UNKNOWN_MIN_DURATION and unknown_duration < self.UNKNOWN_STATE_TIMEOUT:
                            from utils.template_matcher import match_template
                            from utils.safe_ground_matcher import find_safe_ground
                            from utils.shaded_button_helper import is_button_shaded, BUTTON_CLICK

                            # FIRST: Check for shaded button (popup blocking view)
                            shaded, shaded_score = is_button_shaded(frame)
                            if shaded:
                                self.logger.info(f"[{iteration}] UNKNOWN RECOVERY: Shaded button detected (score={shaded_score:.4f}), clicking to dismiss popup...")
                                mark_daemon_action()
                                self.adb.tap(*BUTTON_CLICK, source="daemon:shaded_button")
                                time.sleep(1.5)  # Wait for UI to settle after popup dismiss
                                # Re-check view state
                                new_frame = self.windows_helper.get_screenshot_cv2()
                                new_state, _ = detect_view(new_frame)
                                if new_state.name in ("TOWN", "WORLD"):
                                    self.logger.info(f"[{iteration}] UNKNOWN RECOVERY: Success! Now in {new_state.name}")
                                    self.unknown_state_start = None
                                    self.unknown_state_left_time = None
                                    time.sleep(self.interval)  # Respect main loop timing
                                    continue  # Skip rest of iteration, start fresh
                                else:
                                    self.logger.debug(f"[{iteration}] UNKNOWN RECOVERY: Still in {new_state.name} after shaded click, waiting before retry...")
                                    time.sleep(2.0)  # Extra cooldown when recovery fails
                                    continue  # Keep trying

                            # SECOND: Check for back button with masked template (catches dialogs/menus)
                            # ONLY recover if user is idle - NEVER click anything while user is active
                            if effective_idle_secs >= self.IDLE_THRESHOLD:
                                back_found, back_score, back_pos = match_template(frame, "back_button_union_4k.png", threshold=0.02)
                                if back_found:
                                    self.logger.info(f"[{iteration}] UNKNOWN RECOVERY: Back button detected (score={back_score:.4f}), user idle, using return_to_base_view...")
                                    mark_daemon_action()
                                    return_to_base_view(self.adb, self.windows_helper, debug=False)
                                    # Re-check view state
                                    new_frame = self.windows_helper.get_screenshot_cv2()
                                    new_state, _ = detect_view(new_frame)
                                    if new_state.name in ("TOWN", "WORLD"):
                                        self.logger.info(f"[{iteration}] UNKNOWN RECOVERY: Success! Now in {new_state.name}")
                                        self.unknown_state_start = None
                                        self.unknown_state_left_time = None
                                        time.sleep(self.interval)  # Respect main loop timing
                                        continue  # Skip rest of iteration, start fresh
                                    else:
                                        self.logger.debug(f"[{iteration}] UNKNOWN RECOVERY: Still in {new_state.name}, waiting before retry...")
                                        time.sleep(3.0)  # Longer cooldown after full return_to_base_view fails
                                        continue  # Keep trying

                            # THIRD: Try safe ground/grass (for floating popups without back button)
                            # Try BOTH TOWN floor and WORLD grass, pick better match
                            # ONLY if user is idle - NEVER click anything while user is active
                            if effective_idle_secs >= self.IDLE_THRESHOLD:
                                from utils.safe_grass_matcher import find_safe_grass

                                # Try both matchers
                                ground_pos = find_safe_ground(frame, debug=self.debug)
                                grass_pos = find_safe_grass(frame, debug=self.debug)

                                # Pick the best one (both return position of lowest variance patch)
                                # If both found, we need to compare - but we don't have variance returned
                                # So just prefer whichever one found something
                                best_pos = None
                                pos_type = None
                                if ground_pos and grass_pos:
                                    # Both found - prefer ground (TOWN) as it's more common in popups
                                    best_pos = ground_pos
                                    pos_type = "ground(TOWN)"
                                elif ground_pos:
                                    best_pos = ground_pos
                                    pos_type = "ground(TOWN)"
                                elif grass_pos:
                                    best_pos = grass_pos
                                    pos_type = "grass(WORLD)"

                                if best_pos:
                                    self.logger.info(f"[{iteration}] UNKNOWN RECOVERY: Clicking safe {pos_type} at {best_pos} to dismiss popup...")
                                    mark_daemon_action()
                                    self.adb.tap(*best_pos, source=f"daemon:safe_{pos_type.split('(')[0]}")
                                    time.sleep(1.5)  # Wait for UI to settle after ground/grass click
                                    # Re-check view state
                                    new_frame = self.windows_helper.get_screenshot_cv2()
                                    new_state, _ = detect_view(new_frame)
                                    if new_state.name in ("TOWN", "WORLD"):
                                        self.logger.info(f"[{iteration}] UNKNOWN RECOVERY: Success! Now in {new_state.name}")
                                        self.unknown_state_start = None
                                        self.unknown_state_left_time = None
                                        time.sleep(self.interval)  # Respect main loop timing
                                        continue  # Skip rest of iteration, start fresh
                                    else:
                                        self.logger.debug(f"[{iteration}] UNKNOWN RECOVERY: Still in {new_state.name}, waiting before retry...")
                                        time.sleep(2.0)  # Extra cooldown when recovery fails
                                else:
                                    # FOURTH: No safe ground/grass found - try clicking screen edges
                                    # Building popups (Union Center, etc.) can be dismissed by clicking outside them
                                    # The edges of the screen often have visible game area even with popups
                                    EDGE_CLICK_POSITIONS = [
                                        (100, 1080),   # Left edge, middle
                                        (3700, 1080),  # Right edge, middle
                                        (1920, 100),   # Top edge, center
                                        (1920, 2050),  # Bottom edge, center
                                    ]
                                    # Rotate through edge positions based on iteration to try different ones
                                    edge_idx = iteration % len(EDGE_CLICK_POSITIONS)
                                    edge_pos = EDGE_CLICK_POSITIONS[edge_idx]
                                    self.logger.info(f"[{iteration}] UNKNOWN RECOVERY: No safe area found, trying edge click at {edge_pos}...")
                                    mark_daemon_action()
                                    self.adb.tap(*edge_pos, source="daemon:edge_click_recovery")
                                    time.sleep(1.5)  # Wait for UI to settle after edge click
                                    # Re-check view state
                                    new_frame = self.windows_helper.get_screenshot_cv2()
                                    new_state, _ = detect_view(new_frame)
                                    if new_state.name in ("TOWN", "WORLD"):
                                        self.logger.info(f"[{iteration}] UNKNOWN RECOVERY: Edge click success! Now in {new_state.name}")
                                        self.unknown_state_start = None
                                        self.unknown_state_left_time = None
                                        time.sleep(self.interval)  # Respect main loop timing
                                        continue
                                    else:
                                        self.logger.debug(f"[{iteration}] UNKNOWN RECOVERY: Still in {new_state.name} after edge click, waiting before retry...")
                                        time.sleep(2.0)  # Extra cooldown when recovery fails

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
                            get_daemon_debug().capture(frame, iteration, view_state_str, "recovery", f"attempt_{self.unknown_recovery_count}")
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
                        if view_state_enum != ViewState.TOWN and view_state_enum != ViewState.UNKNOWN:
                            self.logger.info(f"[{iteration}] IDLE RETURN: In {view_state_str}, navigating to TOWN...")
                            self._switch_to_town()
                        elif view_state_enum == ViewState.TOWN:
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
                # CRITICAL: Only accept stamina readings from TOWN or WORLD views
                # OCR produces garbage when view is UNKNOWN (UI popups, transitions)
                if view_state_enum in (ViewState.TOWN, ViewState.WORLD):
                    stamina_confirmed, confirmed_stamina = self.stamina_reader.add_reading(stamina)
                else:
                    # Don't trust stamina readings from UNKNOWN/CHAT/WEBVIEW states
                    stamina_confirmed = False
                    confirmed_stamina = None

                # Persist stamina to state file (throttled - only when confirmed or every 30s)
                if stamina_confirmed and confirmed_stamina is not None:
                    # Only persist when we have a confirmed reading
                    if not hasattr(self, '_last_persisted_stamina') or self._last_persisted_stamina != confirmed_stamina:
                        update_stamina(confirmed_stamina, view_state_str)
                        self._last_persisted_stamina = confirmed_stamina

                # Persist view state periodically (every 10 iterations = 30s)
                if iteration % 10 == 0:
                    update_view_state(view_state_str)

                # =================================================================
                # PRE-BEAST TRAINING: Claim stamina + block elite rallies before event
                # =================================================================
                # Calculate time until Beast Training starts
                time_until_beast = get_time_until_beast_training()
                minutes_until_beast = time_until_beast.total_seconds() / 60 if time_until_beast else 999

                # Track if we're in the pre-event window (0 < minutes <= 6)
                in_pre_beast_window = 0 < minutes_until_beast <= self.BEAST_TRAINING_PRE_EVENT_MINUTES

                # Pre-event stamina claim: 6 min before Beast Training, claim if red dot visible
                # This starts the 4-hour cooldown early so we can claim again in last hour of event
                # Uses scheduler's pre_beast_stamina_claim flow config (idle_required=20s, lower than IDLE_THRESHOLD)
                # REQUIRES: TOWN or WORLD view (need to see stamina area)
                if in_pre_beast_window and view_state_enum not in (ViewState.TOWN, ViewState.WORLD):
                    self.logger.warning(f"[{iteration}] PRE-BEAST STAMINA: {minutes_until_beast:.1f}min until event but view={view_state_str} - cannot detect red dot!")
                    get_daemon_debug().capture(frame, iteration, view_state_str, "pre_beast_blocked", f"{minutes_until_beast:.0f}min")
                if in_pre_beast_window and view_state_enum in (ViewState.TOWN, ViewState.WORLD) and self.scheduler.is_flow_ready("pre_beast_stamina_claim", idle_seconds=effective_idle_secs):
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

                # =================================================================
                # END-OF-DAY STAMINA CLAIM: Safety net to claim free stamina before day reset
                # =================================================================
                # Last event of day is when event_index % 6 == 5 (6 events per day)
                is_last_event_of_day = arms_race['event_index'] % 6 == 5
                arms_race_day_remaining_mins = arms_race['time_remaining'].total_seconds() / 60
                is_end_of_day = arms_race_day_remaining_mins <= END_OF_DAY_STAMINA_CLAIM_MINUTES

                if (is_last_event_of_day and
                    is_end_of_day and
                    view_state_enum in (ViewState.TOWN, ViewState.WORLD) and
                    self.scheduler.is_flow_ready("end_of_day_stamina_claim", idle_seconds=effective_idle_secs)):

                    # Flow opens panel and checks for Claim button - no red dot check needed
                    self.logger.info(f"[{iteration}] END-OF-DAY STAMINA: Day {arms_race['day']}, {arms_race_day_remaining_mins:.1f}min remaining - checking for free stamina")
                    flow_candidates.append(FlowCandidate(
                        name="end_of_day_stamina_claim",
                        flow_func=stamina_claim_flow,
                        priority=FlowPriority.CRITICAL,
                        critical=True,
                        reason=f"End of Day {arms_race['day']}, {arms_race_day_remaining_mins:.0f}min left",
                        record_to_scheduler=True
                    ))

                # Zombie rally/attack - stamina >= threshold and idle 5+ min
                # Respects zombie_mode setting (elite=20 stamina, gold/food/iron_mine=10 stamina)
                # BLOCKED: if Beast Training starts in < 6 minutes (preserve stamina for event)
                zombie_rally_blocked = in_pre_beast_window
                zombie_rally_triggered = False
                # Get zombie mode
                standalone_zombie_mode, _ = self.scheduler.get_zombie_mode()
                standalone_mode_config = ZOMBIE_MODE_CONFIG.get(standalone_zombie_mode, ZOMBIE_MODE_CONFIG["elite"])
                elite_threshold = self._get_config('ELITE_ZOMBIE_STAMINA_THRESHOLD', ELITE_ZOMBIE_STAMINA_THRESHOLD)
                if stamina_confirmed and confirmed_stamina is not None and confirmed_stamina >= elite_threshold and effective_idle_secs >= self.IDLE_THRESHOLD:
                    if zombie_rally_blocked:
                        self.logger.info(f"[{iteration}] ZOMBIE ({standalone_zombie_mode.upper()}): BLOCKED - Beast Training starts in {minutes_until_beast:.1f}min, preserving stamina")
                    else:
                        zombie_rally_triggered = True
                        # Select appropriate flow based on mode
                        if standalone_mode_config["flow"] == "elite_zombie":
                            _target = self._get_config('ELITE_ZOMBIE_TARGET_LEVEL', ELITE_ZOMBIE_TARGET_LEVEL)
                            standalone_flow_func = lambda adb, _t=_target: elite_zombie_flow(adb, target_level=_t)
                            standalone_flow_name = "elite_zombie"
                        else:
                            zt = standalone_mode_config.get("zombie_type", "gold")
                            tl = standalone_mode_config.get("target_level")  # OCR-based
                            lc = standalone_mode_config.get("level_clicks", standalone_mode_config.get("plus_clicks", 0))
                            standalone_flow_func = lambda adb, _zt=zt, _tl=tl, _lc=lc: zombie_attack_flow(adb, zombie_type=_zt, target_level=_tl, level_clicks=_lc)
                            standalone_flow_name = f"zombie_attack_{zt}"
                        flow_candidates.append(FlowCandidate(
                            name=standalone_flow_name,
                            flow_func=standalone_flow_func,
                            priority=FlowPriority.URGENT,
                            critical=True,
                            reason=f"stamina={confirmed_stamina}, mode={standalone_zombie_mode}, idle={idle_str}"
                        ))

                # =================================================================
                # ARMS RACE EVENT TRACKING
                # =================================================================
                current_time = time.time()  # Needed for cooldown checks
                # arms_race, arms_race_event, arms_race_remaining, arms_race_remaining_mins already set above

                # Beast Training: Mystic Beast Training last N minutes, stamina >= 20, cooldown
                # Uses the SAME stamina_confirmed from unified validation above
                #
                # Sequence order (optimized for last hour):
                # 1. Claim free stamina (if red dot visible)
                # 2. Rally (burn stamina down to < 20)
                # 3. Use +50 recovery items (only when stamina < 20, after rallies burn it down)
                # 4. Rally again (with the +50 stamina from Use)
                #
                # This order ensures we do rallies FIRST with existing stamina, THEN use recovery items.
                if (beast_training_enabled and
                    arms_race_event == "Mystic Beast Training" and
                    arms_race_remaining_mins <= self.ARMS_RACE_BEAST_TRAINING_LAST_MINUTES):

                    # Track which block we're in - reset counters if new block
                    block_start = arms_race['block_start']
                    if self.beast_training_current_block != block_start:
                        self.beast_training_current_block = block_start
                        self.beast_training_rally_count = 0
                        self.logger.info(f"[{iteration}] BEAST TRAINING: New block started")

                    # =========================================================
                    # AGGRESSIVE BEAST TRAINING - DO ALL RALLIES AT CHECKPOINTS
                    # 60-min mark: check progress, do ALL rallies
                    # 30-min mark: re-check, do any remaining rallies
                    # =========================================================
                    from scripts.flows.beast_training_flow import aggressive_beast_training_flow

                    # 60-MINUTE CHECKPOINT: Run aggressive flow (all rallies)
                    # No idle requirement - this is a timed event, just do it
                    phase_state = self.scheduler.get_arms_race_state()
                    aggressive_60_block = phase_state.get("beast_training_aggressive_60_block")

                    if aggressive_60_block != str(block_start):  # Not done for this block
                        self.logger.info(f"[{iteration}] BEAST TRAINING: 60-MIN CHECKPOINT - Running aggressive flow...")

                        result = aggressive_beast_training_flow(
                            self.adb, self.windows_helper, debug=self.debug, scheduler=self.scheduler
                        )

                        if result["success"]:
                            self.logger.info(
                                f"[{iteration}] BEAST TRAINING: 60-min complete - "
                                f"{result['rallies_done']}/{result['rallies_needed']} rallies done, "
                                f"points: {result.get('current_points')}/30000"
                            )
                            # Mark as done
                            self.scheduler.update_arms_race_state(beast_training_aggressive_60_block=str(block_start))
                        else:
                            error_text = str(result.get("error") or "")
                            self.logger.warning(f"[{iteration}] BEAST TRAINING: 60-min aggressive flow failed: {error_text}")
                            if "Out of stamina" in error_text:
                                # Prevent per-loop retry storm when no stamina is available.
                                update_payload: dict[str, Any] = {
                                    "beast_training_aggressive_60_block": str(block_start),
                                }
                                if arms_race_remaining_mins <= 30:
                                    update_payload["beast_training_aggressive_30_block"] = str(block_start)
                                self.scheduler.update_arms_race_state(**update_payload)
                                self.logger.warning(
                                    f"[{iteration}] BEAST TRAINING: marking checkpoint(s) complete for block "
                                    f"{block_start} after Out of stamina to prevent retry loop"
                                )

                    # 30-MINUTE CHECKPOINT: Re-check and do remaining rallies
                    if arms_race_remaining_mins <= 30:
                        aggressive_30_block = phase_state.get("beast_training_aggressive_30_block")

                        if aggressive_30_block != str(block_start):  # Not done for this block
                            self.logger.info(f"[{iteration}] BEAST TRAINING: 30-MIN CHECKPOINT - Re-checking progress...")

                            result = aggressive_beast_training_flow(
                                self.adb, self.windows_helper, debug=self.debug, scheduler=self.scheduler
                            )

                            if result["success"]:
                                self.logger.info(
                                    f"[{iteration}] BEAST TRAINING: 30-min complete - "
                                    f"{result['rallies_done']}/{result['rallies_needed']} rallies done, "
                                    f"points: {result.get('current_points')}/30000"
                                )
                                # Mark as done
                                self.scheduler.update_arms_race_state(beast_training_aggressive_30_block=str(block_start))
                            else:
                                error_text = str(result.get("error") or "")
                                self.logger.warning(f"[{iteration}] BEAST TRAINING: 30-min aggressive flow failed: {error_text}")
                                if "Out of stamina" in error_text:
                                    self.scheduler.update_arms_race_state(beast_training_aggressive_30_block=str(block_start))
                                    self.logger.warning(
                                        f"[{iteration}] BEAST TRAINING: marking 30-min checkpoint complete for block "
                                        f"{block_start} after Out of stamina to prevent retry loop"
                                    )

                # Enhance Hero: last N minutes, runs once per block
                # NO idle requirement - flow checks real-time progress and skips if chest3 reached
                enhance_hero_candidate = False
                enhance_hero_enabled = self._get_config('ARMS_RACE_ENHANCE_HERO_ENABLED', ARMS_RACE_ENHANCE_HERO_ENABLED)
                if (enhance_hero_enabled and
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

                # City Construction: last N minutes, speedup smallest queue.
                # NO idle requirement -- Arms Race chest scoring is time-critical
                # and the flow self-checks current points before acting.
                construction_candidate = False
                construction_enabled = self._get_config('ARMS_RACE_CONSTRUCTION_ENABLED', ARMS_RACE_CONSTRUCTION_ENABLED)
                if (construction_enabled and
                    arms_race_event == "City Construction" and
                    arms_race_remaining_mins <= self.CONSTRUCTION_LAST_MINUTES):
                    block_start = arms_race['block_start']
                    if self.construction_speedup_last_block_start != block_start:
                        construction_candidate = True
                        flow_candidates.append(FlowCandidate(
                            name="construction_speedup",
                            flow_func=lambda adb: city_construction_speedup_flow(adb, self.windows_helper),
                            priority=FlowPriority.CRITICAL,
                            critical=True,
                            reason=f"last {arms_race_remaining_mins:.0f}min of City Construction"
                        ))

                # Technology Research: last N minutes, speedup smallest queue.
                # NO idle requirement -- Arms Race chest scoring is time-critical
                # and the flow self-checks current points before acting.
                tech_research_candidate = False
                tech_research_enabled = self._get_config('ARMS_RACE_TECH_RESEARCH_ENABLED', ARMS_RACE_TECH_RESEARCH_ENABLED)
                if (tech_research_enabled and
                    arms_race_event == "Technology Research" and
                    arms_race_remaining_mins <= self.TECH_RESEARCH_LAST_MINUTES):
                    block_start = arms_race['block_start']
                    if self.tech_research_speedup_last_block_start != block_start:
                        tech_research_candidate = True
                        flow_candidates.append(FlowCandidate(
                            name="tech_research_speedup",
                            flow_func=lambda adb: technology_research_speedup_flow(adb, self.windows_helper),
                            priority=FlowPriority.CRITICAL,
                            critical=True,
                            reason=f"last {arms_race_remaining_mins:.0f}min of Technology Research"
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

                soldier_training_enabled = self._get_config('ARMS_RACE_SOLDIER_TRAINING_ENABLED', ARMS_RACE_SOLDIER_TRAINING_ENABLED)
                if (soldier_training_enabled and
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
                                # Check if barracks claiming is enabled
                                from utils.config_overrides import get_override_manager
                                claim_enabled, _ = get_override_manager().get_effective("BARRACKS_CLAIM_ENABLED", True)
                                if claim_enabled:
                                    self.logger.info(f"[{iteration}] BARRACKS: Collecting from {ready_count} READY barrack(s) at indices {ready_indices}")
                                    for idx in ready_indices:
                                        # Re-check idle - stop if user became active
                                        if get_user_idle_seconds() < self.IDLE_THRESHOLD:
                                            self.logger.info(f"[{iteration}] BARRACKS: User active, stopping collection loop")
                                            break
                                        click_x, click_y = get_barrack_click_position(idx)
                                        self.logger.info(f"[{iteration}] BARRACKS: Collecting from barrack {idx+1} at ({click_x}, {click_y})")
                                        mark_daemon_action()
                                        self.adb.tap(click_x, click_y, source=f"daemon:barrack_collect_{idx+1}")
                                        time.sleep(0.5)
                                        # Clear history for this barrack after collecting
                                        self.barracks_state_history[idx] = []
                                    # Wait for state change after collecting
                                    time.sleep(1.0)
                                else:
                                    self.logger.info(f"[{iteration}] BARRACKS: Claiming disabled by config, skipping {ready_count} READY barrack(s)")

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
                                self.adb.tap(click_x, click_y, source=f"daemon:barrack_upgrade_{idx+1}")
                                time.sleep(1.0)

                                # Run upgrade flow via _run_flow_sync to coordinate with other flows
                                flow_result = self._run_flow_sync(
                                    f"soldier_upgrade_flow_b{idx+1}",
                                    lambda adb, idx=idx: soldier_upgrade_flow(adb, barrack_index=idx, debug=True),
                                    critical=True
                                )
                                success = bool(flow_result.get("success")) and bool(flow_result.get("result", False))
                                if not flow_result.get("success") and flow_result.get("error"):
                                    self.logger.warning(f"[{iteration}] SOLDIER: Upgrade blocked: {flow_result.get('error')}")
                                if success:
                                    upgrades += 1
                                    self.logger.info(f"[{iteration}] SOLDIER: Barrack {idx+1} upgrade complete")
                                    # Clear history for this barrack after upgrade
                                    self.barracks_state_history[idx] = []
                                else:
                                    self.logger.info(f"[{iteration}] SOLDIER: Barrack {idx+1} upgrade failed")

                                # Always force-return to TOWN after each attempt. The
                                # underlying flow has multiple early-return paths that
                                # leave the Soldier Training popup open, which makes
                                # view detection go UNKNOWN and the daemon get stuck
                                # waiting for TOWN/WORLD that never comes back without
                                # intervention. respect_idle=False so we recover even
                                # if the user is actively touching the screen.
                                try:
                                    return_to_base_view(
                                        self.adb, self.windows_helper,
                                        target=ViewState.TOWN, respect_idle=False, debug=False,
                                    )
                                except Exception as e:
                                    self.logger.warning(f"[{iteration}] SOLDIER: post-upgrade RTB failed: {e}")

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

                # Union coal: 1 hour cooldown
                if self._is_user_idle() and self.scheduler.is_flow_ready("union_coal", idle_seconds=effective_idle_secs):
                    flow_candidates.append(FlowCandidate(
                        name="union_coal",
                        flow_func=union_coal_flow,
                        priority=FlowPriority.NORMAL,
                        reason=f"idle={idle_str}",
                        record_to_scheduler=True
                    ))

                # Union furnace: 2 hour cooldown
                if self._is_user_idle() and self.scheduler.is_flow_ready("union_furnace", idle_seconds=effective_idle_secs):
                    flow_candidates.append(FlowCandidate(
                        name="union_furnace",
                        flow_func=union_furnace_flow,
                        priority=FlowPriority.NORMAL,
                        reason=f"idle={idle_str}",
                        record_to_scheduler=True
                    ))

                # Community daily check-in: 4 hour cooldown (flow skips if already done today)
                # Only run when in TOWN or WORLD view (community icon visible in both)
                if (view_state_enum in (ViewState.TOWN, ViewState.WORLD) and
                    self._is_user_idle() and
                    self.scheduler.is_flow_ready("community_checkin", idle_seconds=effective_idle_secs)):
                    flow_candidates.append(FlowCandidate(
                        name="community_checkin",
                        flow_func=lambda adb: community_click_flow(adb, self.windows_helper),
                        priority=FlowPriority.NORMAL,
                        reason=f"idle={idle_str}",
                        record_to_scheduler=True
                    ))

                # Quick Production class skill: 24 hour cooldown (matches in-game cooldown)
                # Grants 24 hours of wheat, iron, and gold production instantly
                if (view_state_enum in (ViewState.TOWN, ViewState.WORLD) and
                    self._is_user_idle() and
                    self.scheduler.is_flow_ready("quick_production", idle_seconds=effective_idle_secs)):
                    flow_candidates.append(FlowCandidate(
                        name="quick_production",
                        flow_func=lambda adb: quick_production_flow(adb, self.windows_helper),
                        priority=FlowPriority.CRITICAL,  # Uninterruptible - valuable daily resource
                        reason=f"24h cooldown ready",
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

                # Tavern quest SCHEDULED trigger at configured start time Pacific (ignores cooldown/idle)
                # Uses DISPATCH mode to start new quests when the window opens
                now_pacific = datetime.now(self.pacific_tz)
                tavern_trigger_time = now_pacific.replace(hour=TAVERN_QUEST_START_HOUR, minute=TAVERN_QUEST_START_MINUTE, second=0, microsecond=0)
                tavern_scheduled_triggered = False
                if (now_pacific >= tavern_trigger_time and
                    self.tavern_scheduled_triggered_date != now_pacific.date()):
                    tavern_scheduled_triggered = True
                    flow_candidates.append(FlowCandidate(
                        name="tavern_dispatch",
                        flow_func=partial(run_tavern_quest_flow, mode="dispatch"),
                        priority=FlowPriority.HIGH,  # Scheduled triggers are important
                        critical=True,
                        reason=f"scheduled {TAVERN_QUEST_START_HOUR}:{TAVERN_QUEST_START_MINUTE:02d} PT",
                        record_to_scheduler=True
                    ))

                # Tavern SCAN: 5 min idle, 30 min cooldown - just OCR timers, no clicking
                elif self._is_user_idle() and self.scheduler.is_flow_ready("tavern_scan", idle_seconds=effective_idle_secs):
                    flow_candidates.append(FlowCandidate(
                        name="tavern_scan",
                        flow_func=self._run_tavern_scan_twice,
                        priority=FlowPriority.NORMAL,
                        critical=True,
                        reason=f"idle={idle_str}",
                        record_to_scheduler=True
                    ))

                # Tavern ALLY: 1 hour cooldown - assist ally quests (skips if 5/5)
                if self._is_user_idle() and self.scheduler.is_flow_ready("tavern_ally", idle_seconds=effective_idle_secs):
                    flow_candidates.append(FlowCandidate(
                        name="tavern_ally",
                        flow_func=partial(run_tavern_quest_flow, mode="ally"),
                        priority=FlowPriority.LOW,
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

                    if executed_flow == "tavern_dispatch" and tavern_scheduled_triggered:
                        self.tavern_scheduled_triggered_date = now_pacific.date()
                        self.logger.info(f"[{iteration}] Tavern dispatch scheduled trigger marked for {now_pacific.date()}")

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

                    # Construction speedup block tracking
                    if executed_flow == "construction_speedup" and construction_candidate:
                        block_start = arms_race['block_start']
                        self.construction_speedup_last_block_start = block_start
                        self.logger.info(f"[{iteration}] Construction speedup complete for block {block_start}")

                    # Technology Research speedup block tracking
                    if executed_flow == "tech_research_speedup" and tech_research_candidate:
                        block_start = arms_race['block_start']
                        self.tech_research_speedup_last_block_start = block_start
                        self.logger.info(f"[{iteration}] Tech research speedup complete for block {block_start}")

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
                if view_state_enum == ViewState.TOWN:
                    self.logger.info(f"[{iteration}] View: TOWN (world button visible, score={view_score:.4f})")
                elif view_state_enum == ViewState.WORLD:
                    self.logger.info(f"[{iteration}] View: WORLD (town button visible, score={view_score:.4f})")

            except Exception as e:
                import traceback
                self.logger.error(f"[{iteration}] ERROR: {e}\n{traceback.format_exc()}")

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


def release_daemon_lock() -> None:
    """Release the daemon lock by removing PID file."""
    try:
        if PID_FILE.exists():
            PID_FILE.unlink()
    except OSError:
        pass


def main() -> None:
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
    from typing import TextIO

    class Tee:
        def __init__(self, *files: TextIO) -> None:
            self.files = files

        def write(self, data: str) -> int:
            for f in self.files:
                f.write(data)
                f.flush()
            return len(data)

        def flush(self) -> None:
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
