"""
Smart Mystic Beast Training flow.

Handles the last hour of Beast Training with:
- Hour mark (60 min): Check progress, claim stamina upfront
- Mid-check (30 min): Re-check, claim more if needed
- Final phase: Continuous rallies until chest3

Key Values:
- 100 points per stamina spent
- 20 stamina per rally
- 2000 points per rally (20 * 100)
- Chest3 target: 30000 points
- Max 15 rallies for full chest3
"""
from __future__ import annotations

import logging
import time
from typing import TYPE_CHECKING, Any, TypedDict, cast

import numpy.typing as npt

from config import STAMINA_REGION, ZOMBIE_MODE_CONFIG
from utils.arms_race_panel_helper import (
    check_beast_training_progress,
    CHEST3_TARGET,
)
from scripts.flows.stamina_use_flow import stamina_get
from utils.ocr_client import OCRClient
from utils.return_to_base_view import return_to_base_view

from utils.windows_screenshot_helper import WindowsScreenshotHelper

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper
    from utils.scheduler import DaemonScheduler

logger = logging.getLogger(__name__)


class HourMarkResult(TypedDict):
    """Result from run_hour_mark_phase."""

    success: bool
    rallies_needed: int
    stamina_claimed: int
    decision: dict[str, Any] | None
    current_points: int | None
    zombie_mode: str


class QuickProgressResult(TypedDict):
    """Result from check_progress_quick."""

    success: bool
    current_points: int | None
    rallies_needed: int | None
    chest3_reached: bool


def get_current_stamina(
    frame: npt.NDArray[Any], ocr_client: OCRClient | None = None
) -> int:
    """Extract current stamina from HUD."""
    client = ocr_client if ocr_client is not None else OCRClient()

    stamina = client.extract_number(frame, STAMINA_REGION)
    return stamina or 0


def run_hour_mark_phase(
    adb: ADBHelper,
    win: WindowsScreenshotHelper,
    debug: bool = False,
    scheduler: DaemonScheduler | None = None,
) -> HourMarkResult:
    """
    Phase 1: Hour mark check and initial stamina claim.

    This runs when we enter the last hour of Beast Training (60 min remaining).

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance
        debug: Enable debug logging
        scheduler: Optional Scheduler instance to get zombie mode

    Returns:
        HourMarkResult with success, rallies_needed, stamina_claimed, decision,
        current_points, and zombie_mode.
    """
    # Get zombie mode from scheduler
    zombie_mode = "elite"
    if scheduler:
        zombie_mode, _ = scheduler.get_zombie_mode()
    mode_config = ZOMBIE_MODE_CONFIG.get(zombie_mode, ZOMBIE_MODE_CONFIG["elite"])
    stamina_per_action = cast(int, mode_config["stamina"])

    result: HourMarkResult = {
        "success": False,
        "rallies_needed": 0,
        "stamina_claimed": 0,
        "decision": None,
        "current_points": None,
        "zombie_mode": zombie_mode,
    }

    try:
        action_type = "attacks" if zombie_mode != "elite" else "rallies"
        logger.info("=" * 50)
        logger.info(f"=== PHASE 1: HOUR MARK CHECK [mode={zombie_mode}] ===")
        logger.info("=" * 50)

        # Step 1: Check Arms Race progress (navigates to panel)
        logger.info("Step 1: Checking Arms Race progress...")
        progress = check_beast_training_progress(adb, win, debug=debug, scheduler=scheduler)

        if not progress["success"]:
            logger.error("  Failed to check Arms Race progress")
            return result

        rallies_needed = progress["rallies_needed"]
        current_points = progress["current_points"]
        result["current_points"] = current_points

        logger.info(f"  Progress: {current_points}/{CHEST3_TARGET} pts")
        logger.info(f"  {action_type.capitalize()} needed: {rallies_needed}")

        if rallies_needed == 0:
            logger.info(f"  CHEST3 ALREADY REACHED! No {action_type} needed.")
            result["success"] = True
            result["rallies_needed"] = 0
            return result

        result["rallies_needed"] = rallies_needed

        # Step 2: Get current stamina from HUD
        logger.info("Step 2: Reading current stamina...")
        frame = win.get_screenshot_cv2()
        current_stamina = get_current_stamina(frame)
        stamina_needed = rallies_needed * stamina_per_action
        deficit = stamina_needed - current_stamina
        logger.info(f"  Current stamina: {current_stamina}")
        logger.info(f"  Stamina needed: {stamina_needed} ({rallies_needed} x {stamina_per_action})")
        logger.info(f"  Deficit: {deficit}")

        if deficit <= 0:
            logger.info("  No deficit - current stamina is sufficient")
            result["success"] = True
            return result

        # Step 3: Get time remaining from Arms Race status
        from utils.arms_race import get_arms_race_status
        arms_race = get_arms_race_status()
        time_remaining_mins = int(arms_race['time_remaining'].total_seconds() / 60)

        # Step 4: Get stamina (opens popup, scans, calculates, executes, closes)
        logger.info(f"Step 3: Getting stamina (deficit={deficit}, time_remaining={time_remaining_mins}min)...")
        ocr = OCRClient()
        stamina_result = stamina_get(adb, win, ocr, deficit, dry_run=False, time_remaining_mins=time_remaining_mins)

        result["decision"] = {
            "claim_free_50": stamina_result["plan"].get("claim_free", False),
            "use_10_count": stamina_result["plan"].get("use_10s", 0),
            "use_50_count": stamina_result["plan"].get("use_50s", 0),
            "reasoning": stamina_result["plan"].get("reasoning", "N/A")
        }
        result["stamina_claimed"] = stamina_result["obtained"]
        logger.info(f"  Obtained: {stamina_result['obtained']} stamina")
        logger.info(f"  Plan: {stamina_result['plan'].get('reasoning', 'N/A')}")

        result["success"] = True
        logger.info("=== PHASE 1 COMPLETE ===")

    except Exception as e:
        logger.error(f"Hour mark phase error: {e}", exc_info=True)

    finally:
        # Always return to base view
        try:
            return_to_base_view(adb, win, debug=debug)
        except Exception as e:
            logger.warning(f"Failed to return to base view: {e}")

    return result


def run_beast_training_phase(
    adb: ADBHelper,
    win: WindowsScreenshotHelper,
    debug: bool = False,
    scheduler: DaemonScheduler | None = None,
) -> HourMarkResult:
    """
    Run a Beast Training phase: check progress, claim stamina, run rallies.

    Used for Last Hour phase (60 min) and Mid-Check phase (30 min).
    Checks current score, claims stamina if needed, runs rallies until target.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance
        debug: Enable debug logging
        scheduler: Optional Scheduler instance to get zombie mode

    Returns:
        HourMarkResult with same structure as hour_mark_phase.
    """
    # Get zombie mode from scheduler
    zombie_mode = "elite"
    if scheduler:
        zombie_mode, _ = scheduler.get_zombie_mode()
    mode_config = ZOMBIE_MODE_CONFIG.get(zombie_mode, ZOMBIE_MODE_CONFIG["elite"])
    stamina_per_action = cast(int, mode_config["stamina"])

    result: HourMarkResult = {
        "success": False,
        "rallies_needed": 0,
        "stamina_claimed": 0,
        "decision": None,
        "current_points": None,
        "zombie_mode": zombie_mode,
    }

    try:
        action_type = "attacks" if zombie_mode != "elite" else "rallies"
        logger.info("=" * 50)
        logger.info(f"=== PHASE 2: LAST 6 MINUTES RE-CHECK [mode={zombie_mode}] ===")
        logger.info("=" * 50)

        # Step 1: Re-check Arms Race (user may have done rallies!)
        logger.info("Step 1: Re-checking Arms Race progress...")
        progress = check_beast_training_progress(adb, win, debug=debug, scheduler=scheduler)

        if not progress["success"]:
            logger.error("  Failed to check Arms Race progress")
            return result

        rallies_needed = progress["rallies_needed"]
        current_points = progress["current_points"]
        result["current_points"] = current_points

        logger.info(f"  Progress: {current_points}/{CHEST3_TARGET} pts")
        logger.info(f"  {action_type.capitalize()} still needed: {rallies_needed}")

        if rallies_needed == 0:
            logger.info("  CHEST3 ALREADY REACHED! Mission accomplished.")
            result["success"] = True
            result["rallies_needed"] = 0
            return result

        result["rallies_needed"] = rallies_needed

        # Step 2: Get current stamina from HUD
        logger.info("Step 2: Reading current stamina...")
        frame = win.get_screenshot_cv2()
        current_stamina = get_current_stamina(frame)
        stamina_needed = rallies_needed * stamina_per_action
        deficit = stamina_needed - current_stamina
        logger.info(f"  Current stamina: {current_stamina}")
        logger.info(f"  Stamina needed: {stamina_needed} ({rallies_needed} x {stamina_per_action})")
        logger.info(f"  Deficit: {deficit}")

        if deficit <= 0:
            logger.info("  No deficit - current stamina is sufficient")
            result["success"] = True
            return result

        # Step 3: Get time remaining from Arms Race status
        from utils.arms_race import get_arms_race_status
        arms_race = get_arms_race_status()
        time_remaining_mins = int(arms_race['time_remaining'].total_seconds() / 60)

        # Step 4: Get stamina (opens popup, scans, calculates, executes, closes)
        logger.info(f"Step 3: Getting stamina (deficit={deficit}, time_remaining={time_remaining_mins}min)...")
        ocr = OCRClient()
        stamina_result = stamina_get(adb, win, ocr, deficit, dry_run=False, time_remaining_mins=time_remaining_mins)

        result["decision"] = {
            "claim_free_50": stamina_result["plan"].get("claim_free", False),
            "use_10_count": stamina_result["plan"].get("use_10s", 0),
            "use_50_count": stamina_result["plan"].get("use_50s", 0),
            "reasoning": stamina_result["plan"].get("reasoning", "N/A")
        }
        result["stamina_claimed"] = stamina_result["obtained"]
        logger.info(f"  Obtained: {stamina_result['obtained']} stamina")
        logger.info(f"  Plan: {stamina_result['plan'].get('reasoning', 'N/A')}")

        result["success"] = True
        logger.info("=== PHASE 2 COMPLETE ===")

    except Exception as e:
        logger.error(f"Beast training phase error: {e}", exc_info=True)

    finally:
        try:
            return_to_base_view(adb, win, debug=debug)
        except Exception as e:
            logger.warning(f"Failed to return to base view: {e}")

    return result


def check_progress_quick(
    adb: ADBHelper,
    win: WindowsScreenshotHelper,
    debug: bool = False,
) -> QuickProgressResult:
    """
    Quick progress check for continuous monitoring.

    Just checks Arms Race points without full stamina inventory.

    Returns:
        QuickProgressResult with success, current_points, rallies_needed,
        and chest3_reached.
    """
    result: QuickProgressResult = {
        "success": False,
        "current_points": None,
        "rallies_needed": None,
        "chest3_reached": False,
    }

    try:
        progress = check_beast_training_progress(adb, win, debug=debug)

        if progress["success"]:
            result["success"] = True
            result["current_points"] = progress["current_points"]
            result["rallies_needed"] = progress["rallies_needed"]
            result["chest3_reached"] = progress["rallies_needed"] == 0

            if result["chest3_reached"]:
                logger.info(f"CHEST3 REACHED! Points: {result['current_points']}/{CHEST3_TARGET}")
            else:
                logger.info(f"Progress: {result['current_points']}/{CHEST3_TARGET}, "
                           f"need {result['rallies_needed']} more rallies")

    except Exception as e:
        logger.error(f"Quick progress check error: {e}")

    finally:
        try:
            return_to_base_view(adb, win, debug=debug)
        except Exception:
            pass

    return result


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s %(levelname)s: %(message)s",
        datefmt="%H:%M:%S"
    )

    from utils.adb_helper import ADBHelper

    print("=== Beast Training Flow Test ===\n")

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    if len(sys.argv) > 1:
        if sys.argv[1] == "--hour-mark":
            print("Running hour mark phase...")
            hour_result = run_hour_mark_phase(adb, win, debug=True)
            print(f"\nResult: {hour_result}")

        elif sys.argv[1] == "--phase":
            print("Running beast training phase...")
            phase_result = run_beast_training_phase(adb, win, debug=True)
            print(f"\nResult: {phase_result}")

        elif sys.argv[1] == "--quick":
            print("Running quick progress check...")
            quick_result = check_progress_quick(adb, win, debug=True)
            print(f"\nResult: {quick_result}")
    else:
        print("Usage:")
        print("  python beast_training_flow.py --hour-mark  # Run hour mark phase")
        print("  python beast_training_flow.py --phase      # Run training phase (score check + rallies)")
        print("  python beast_training_flow.py --quick      # Quick progress check")
