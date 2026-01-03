"""
Smart Mystic Beast Training flow.

Handles the last hour of Beast Training with:
- Hour mark: Check progress, claim stamina upfront
- Last 6 minutes: Re-check, claim remainder
- Continuous: Check Arms Race every minute until chest3

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
from typing import Optional

from config import STAMINA_REGION, ZOMBIE_MODE_CONFIG
from utils.arms_race_panel_helper import (
    check_beast_training_progress,
    CHEST3_TARGET,
)
from utils.stamina_popup_helper import (
    get_inventory_snapshot,
    open_stamina_popup,
    close_stamina_popup,
    execute_claim_decision,
)
from utils.claude_cli_helper import get_stamina_decision
from utils.ocr_client import OCRClient
from utils.return_to_base_view import return_to_base_view

logger = logging.getLogger(__name__)


def get_current_stamina(frame, ocr_client: OCRClient = None) -> int:
    """Extract current stamina from HUD."""
    if ocr_client is None:
        ocr_client = OCRClient()

    stamina = ocr_client.extract_number(frame, STAMINA_REGION)
    return stamina or 0


def run_hour_mark_phase(adb, win, debug: bool = False, scheduler=None) -> dict:
    """
    Phase 1: Hour mark check and initial stamina claim.

    This runs when we enter the last hour of Beast Training (60 min remaining).

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance
        debug: Enable debug logging
        scheduler: Optional Scheduler instance to get zombie mode

    Returns:
        {
            "success": bool,
            "rallies_needed": int,
            "stamina_claimed": int,
            "decision": dict,
            "current_points": int | None,
            "zombie_mode": str
        }
    """
    # Get zombie mode from scheduler
    zombie_mode = "elite"
    if scheduler:
        zombie_mode, _ = scheduler.get_zombie_mode()
    mode_config = ZOMBIE_MODE_CONFIG.get(zombie_mode, ZOMBIE_MODE_CONFIG["elite"])
    stamina_per_action = mode_config["stamina"]

    result = {
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

        # Step 1: Inventory snapshot (opens/closes popup)
        logger.info("Step 1: Taking inventory snapshot...")
        inventory = get_inventory_snapshot(adb, win)
        logger.info(f"  Inventory: owned_10={inventory['owned_10']}, "
                   f"owned_50={inventory['owned_50']}, "
                   f"cooldown={inventory['cooldown_secs']}s")

        # Step 2: Check Arms Race progress (navigates to panel)
        logger.info("Step 2: Checking Arms Race progress...")
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

        # Step 3: Get current stamina from HUD
        logger.info("Step 3: Reading current stamina...")
        frame = win.get_screenshot_cv2()
        current_stamina = get_current_stamina(frame)
        stamina_needed = rallies_needed * stamina_per_action
        logger.info(f"  Current stamina: {current_stamina}")
        logger.info(f"  Stamina needed: {stamina_needed} ({rallies_needed} x {stamina_per_action})")

        # Step 4: Claude CLI decision
        # Get actual time remaining from Arms Race status
        from utils.arms_race import get_arms_race_status
        arms_race = get_arms_race_status()
        time_remaining_mins = arms_race['time_remaining'].total_seconds() / 60

        logger.info("Step 4: Getting stamina decision...")
        state = {
            "current_points": current_points,
            "rallies_needed": rallies_needed,
            "stamina_needed": stamina_needed,
            "current_stamina": current_stamina,
            "free_50_cooldown_secs": inventory["cooldown_secs"],
            "owned_10": inventory["owned_10"],
            "owned_50": inventory["owned_50"],
            "time_remaining_mins": time_remaining_mins,
            "phase": "hour_mark"
        }

        decision = get_stamina_decision(state)
        logger.info(f"  Decision: claim_free={decision.get('claim_free_50')}, "
                   f"use_10={decision.get('use_10_count', 0)}, "
                   f"use_50={decision.get('use_50_count', 0)}")
        logger.info(f"  Reasoning: {decision.get('reasoning', 'N/A')}")
        result["decision"] = decision

        # Step 5: Execute decision (if anything to claim)
        if (decision.get("claim_free_50") or
            decision.get("use_10_count", 0) > 0 or
            decision.get("use_50_count", 0) > 0):

            logger.info("Step 5: Executing claim decision...")
            open_stamina_popup(adb)
            time.sleep(0.5)
            execute_claim_decision(adb, decision)
            close_stamina_popup(adb)

            result["stamina_claimed"] = (
                (50 if decision.get("claim_free_50") else 0) +
                decision.get("use_10_count", 0) * 10 +
                decision.get("use_50_count", 0) * 50
            )
            logger.info(f"  Claimed {result['stamina_claimed']} stamina")
        else:
            logger.info("Step 5: No items to claim (current stamina sufficient)")

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


def run_last_6_minutes_phase(adb, win, debug: bool = False, scheduler=None) -> dict:
    """
    Phase 2: Last 6 minutes re-check and final stamina claim.

    This runs when we're in the last 6 minutes of Beast Training.
    The free 50 stamina cooldown may have expired by now!

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance
        debug: Enable debug logging
        scheduler: Optional Scheduler instance to get zombie mode

    Returns same structure as hour_mark_phase.
    """
    # Get zombie mode from scheduler
    zombie_mode = "elite"
    if scheduler:
        zombie_mode, _ = scheduler.get_zombie_mode()
    mode_config = ZOMBIE_MODE_CONFIG.get(zombie_mode, ZOMBIE_MODE_CONFIG["elite"])
    stamina_per_action = mode_config["stamina"]

    result = {
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

        # Re-check inventory (cooldown may be ready now!)
        logger.info("Step 1: Re-checking inventory...")
        inventory = get_inventory_snapshot(adb, win)
        logger.info(f"  Inventory: owned_10={inventory['owned_10']}, "
                   f"owned_50={inventory['owned_50']}, "
                   f"cooldown={inventory['cooldown_secs']}s")

        if inventory["cooldown_secs"] == 0:
            logger.info("  FREE 50 STAMINA IS NOW AVAILABLE!")

        # Re-check Arms Race (user may have done rallies!)
        logger.info("Step 2: Re-checking Arms Race progress...")
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

        # Get current stamina and make decision
        logger.info("Step 3: Reading current stamina...")
        frame = win.get_screenshot_cv2()
        current_stamina = get_current_stamina(frame)
        stamina_needed = rallies_needed * stamina_per_action
        logger.info(f"  Current stamina: {current_stamina}")
        logger.info(f"  Stamina needed: {stamina_needed} ({rallies_needed} x {stamina_per_action})")

        # Get actual time remaining from Arms Race status
        from utils.arms_race import get_arms_race_status
        arms_race = get_arms_race_status()
        time_remaining_mins = arms_race['time_remaining'].total_seconds() / 60

        logger.info("Step 4: Getting stamina decision...")
        state = {
            "current_points": current_points,
            "rallies_needed": rallies_needed,
            "stamina_needed": stamina_needed,
            "current_stamina": current_stamina,
            "free_50_cooldown_secs": inventory["cooldown_secs"],
            "owned_10": inventory["owned_10"],
            "owned_50": inventory["owned_50"],
            "time_remaining_mins": time_remaining_mins,
            "phase": "last_6_minutes"
        }

        decision = get_stamina_decision(state)
        logger.info(f"  Decision: claim_free={decision.get('claim_free_50')}, "
                   f"use_10={decision.get('use_10_count', 0)}, "
                   f"use_50={decision.get('use_50_count', 0)}")
        logger.info(f"  Reasoning: {decision.get('reasoning', 'N/A')}")
        result["decision"] = decision

        # Execute decision
        if (decision.get("claim_free_50") or
            decision.get("use_10_count", 0) > 0 or
            decision.get("use_50_count", 0) > 0):

            logger.info("Step 5: Executing claim decision...")
            open_stamina_popup(adb)
            time.sleep(0.5)
            execute_claim_decision(adb, decision)
            close_stamina_popup(adb)

            result["stamina_claimed"] = (
                (50 if decision.get("claim_free_50") else 0) +
                decision.get("use_10_count", 0) * 10 +
                decision.get("use_50_count", 0) * 50
            )
            logger.info(f"  Claimed {result['stamina_claimed']} stamina")
        else:
            logger.info("Step 5: No items to claim")

        result["success"] = True
        logger.info("=== PHASE 2 COMPLETE ===")

    except Exception as e:
        logger.error(f"Last 6 minutes phase error: {e}", exc_info=True)

    finally:
        try:
            return_to_base_view(adb, win, debug=debug)
        except Exception as e:
            logger.warning(f"Failed to return to base view: {e}")

    return result


def check_progress_quick(adb, win, debug: bool = False) -> dict:
    """
    Quick progress check for continuous monitoring.

    Just checks Arms Race points without full stamina inventory.

    Returns:
        {
            "success": bool,
            "current_points": int | None,
            "rallies_needed": int | None,
            "chest3_reached": bool
        }
    """
    result = {
        "success": False,
        "current_points": None,
        "rallies_needed": None,
        "chest3_reached": False
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
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

    print("=== Beast Training Flow Test ===\n")

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    if len(sys.argv) > 1:
        if sys.argv[1] == "--hour-mark":
            print("Running hour mark phase...")
            result = run_hour_mark_phase(adb, win, debug=True)
            print(f"\nResult: {result}")

        elif sys.argv[1] == "--last-6":
            print("Running last 6 minutes phase...")
            result = run_last_6_minutes_phase(adb, win, debug=True)
            print(f"\nResult: {result}")

        elif sys.argv[1] == "--quick":
            print("Running quick progress check...")
            result = check_progress_quick(adb, win, debug=True)
            print(f"\nResult: {result}")
    else:
        print("Usage:")
        print("  python beast_training_flow.py --hour-mark  # Run hour mark phase")
        print("  python beast_training_flow.py --last-6     # Run last 6 min phase")
        print("  python beast_training_flow.py --quick      # Quick progress check")
