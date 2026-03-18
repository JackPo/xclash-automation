"""
Stamina Use flow - scan stamina dialog and use items to get stamina.

Dialog Layout (4K coordinates):
- Row 0: Free 50 claim (Y~744) - timer or Claim button
- Row 1: 100 Purchase (Y~950) - IGNORE (costs gems)
- Row 2: 10 Stamina items (Y~1210) - Owned: XX, Use button
- Row 3: 50 Stamina items (Y~1444) - Owned: XX, Use button
"""
from __future__ import annotations

import re
import time
from typing import TYPE_CHECKING, Any, cast

import numpy.typing as npt

from config import STAMINA_REGION, STAMINA_CLAIM_BUTTON
from utils.template_matcher import match_template
from utils.ui_helpers import click_back
from .back_from_chat_flow import back_from_chat_flow

if TYPE_CHECKING:
    from utils.adb_helper import ADBHelper
    from utils.windows_screenshot_helper import WindowsScreenshotHelper
    from utils.ocr_client import OCRClient

STAMINA_DISPLAY_X = STAMINA_REGION[0] + STAMINA_REGION[2] // 2
STAMINA_DISPLAY_Y = STAMINA_REGION[1] + STAMINA_REGION[3] // 2

ROW_0_TIMER_REGION = (2050, 700, 350, 100)
ROW_0_CLAIM_BTN_POS = (2284, 741)  # Free 50 claim button
CLAIM_BUTTON_SEARCH_REGION: tuple[int, int, int, int] = cast(
    tuple[int, int, int, int], STAMINA_CLAIM_BUTTON.get("search_region", (1800, 400, 800, 500))
)
CLAIM_BUTTON_THRESHOLD = 0.05
ROW_2_OWNED_REGION = (1600, 1180, 350, 70)
ROW_3_OWNED_REGION = (1600, 1410, 350, 70)
ROW_2_USE_BTN_POS = (2225, 1208)
ROW_3_USE_BTN_POS = (2225, 1442)
POPUP_CLOSE_POS = (500, 500)  # Tap blank space to close


def _scan_stamina_dialog(frame: npt.NDArray[Any], ocr: "OCRClient") -> dict[str, Any]:
    x, y, w, h = ROW_0_TIMER_REGION
    timer_crop = frame[y:y+h, x:x+w]
    timer_text = ocr.extract_text(timer_crop)
    has_timer = bool(re.search(r"\d+:\d+", timer_text))
    free_50_claimable = not has_timer

    x, y, w, h = ROW_2_OWNED_REGION
    owned2_crop = frame[y:y+h, x:x+w]
    owned2_text = ocr.extract_text(owned2_crop)
    match2 = re.search(r"(\d+)", owned2_text)
    item_10_owned = int(match2.group(1)) if match2 else 0

    x, y, w, h = ROW_3_OWNED_REGION
    owned3_crop = frame[y:y+h, x:x+w]
    owned3_text = ocr.extract_text(owned3_crop)
    match3 = re.search(r"(\d+)", owned3_text)
    item_50_owned = int(match3.group(1)) if match3 else 0

    total = (50 if free_50_claimable else 0) + (item_10_owned * 10) + (item_50_owned * 50)

    return {
        "free_50_claimable": free_50_claimable,
        "free_50_timer": timer_text if has_timer else None,
        "item_10_owned": item_10_owned,
        "item_50_owned": item_50_owned,
        "total_available": total
    }


def _click_use_button(adb: "ADBHelper", row: int) -> None:
    if row == 2:
        adb.tap(*ROW_2_USE_BTN_POS, source="flow:stamina_use:use_10_stamina")
    elif row == 3:
        adb.tap(*ROW_3_USE_BTN_POS, source="flow:stamina_use:use_50_stamina")


def _is_claim_button_visible(frame: npt.NDArray[Any]) -> tuple[bool, float]:
    """Template-check whether free-50 Claim button is actually visible."""
    found, score, _ = match_template(
        frame,
        "claim_button_4k.png",
        search_region=CLAIM_BUTTON_SEARCH_REGION,
        threshold=CLAIM_BUTTON_THRESHOLD,
    )
    return found, float(score)


def _confirm_free_claim_consumed(
    win: "WindowsScreenshotHelper",
    ocr: "OCRClient",
    pre_stamina: int,
    timeout_s: float = 2.0,
) -> tuple[bool, int, float]:
    """
    Confirm free claim was consumed by checking UI/stamina after tap.

    Returns:
        (confirmed, stamina_gain, last_claim_score)
    """
    deadline = time.time() + timeout_s
    last_score = 1.0
    best_gain = 0
    while time.time() < deadline:
        frame = win.get_screenshot_cv2()
        claim_visible, score = _is_claim_button_visible(frame)
        last_score = score
        stamina_now = ocr.extract_number(frame, STAMINA_REGION) or pre_stamina
        best_gain = max(best_gain, max(0, stamina_now - pre_stamina))
        # Confirmed if Claim button disappears OR stamina jumps materially.
        if (not claim_visible) or (best_gain >= 20):
            return True, best_gain, last_score
        time.sleep(0.2)
    return False, best_gain, last_score


def _parse_timer_to_seconds(timer_text: str) -> int:
    """Parse timer text like '00:50:27' or '14:34' to seconds."""
    if not timer_text:
        return 0
    timer_text = timer_text.strip()
    try:
        parts = timer_text.split(":")
        if len(parts) == 3:
            hours, mins, secs = int(parts[0]), int(parts[1]), int(parts[2])
            return hours * 3600 + mins * 60 + secs
        elif len(parts) == 2:
            mins, secs = int(parts[0]), int(parts[1])
            return mins * 60 + secs
    except (ValueError, IndexError):
        pass
    return 0


def open_stamina_popup(adb: "ADBHelper") -> None:
    """Click stamina display to open recovery popup."""
    adb.tap(STAMINA_DISPLAY_X, STAMINA_DISPLAY_Y, source="flow:stamina_use:open_popup")
    time.sleep(1.0)


def close_stamina_popup(adb: "ADBHelper") -> None:
    """Close the popup by tapping blank space."""
    adb.tap(*POPUP_CLOSE_POS, source="flow:stamina_use:close_popup")
    time.sleep(0.5)


def get_inventory_snapshot(adb: "ADBHelper", win: "WindowsScreenshotHelper") -> dict[str, int]:
    """
    Open popup, capture inventory state, close popup.

    Returns:
        {
            "owned_10": int,
            "owned_50": int,
            "cooldown_secs": int
        }
    """
    from utils.ocr_client import OCRClient

    open_stamina_popup(adb)
    time.sleep(0.5)

    frame = win.get_screenshot_cv2()
    ocr = OCRClient()
    scan = _scan_stamina_dialog(frame, ocr)

    close_stamina_popup(adb)

    cooldown = 0
    if scan["free_50_timer"]:
        cooldown = _parse_timer_to_seconds(scan["free_50_timer"])

    return {
        "owned_10": scan["item_10_owned"],
        "owned_50": scan["item_50_owned"],
        "cooldown_secs": cooldown
    }


def execute_claim_decision(adb: "ADBHelper", decision: dict[str, Any]) -> None:
    """
    Execute the claim decision from the stamina rule engine.

    Args:
        decision: {claim_free_50: bool, use_10_count: int, use_50_count: int}
    """
    if decision.get("claim_free_50"):
        adb.tap(*ROW_0_CLAIM_BTN_POS, source="flow:stamina_use:claim_free_50")
        time.sleep(0.5)

    use_10_count = decision.get("use_10_count", 0)
    for _ in range(use_10_count):
        adb.tap(*ROW_2_USE_BTN_POS, source="flow:stamina_use:use_10_stamina")
        time.sleep(0.3)

    use_50_count = decision.get("use_50_count", 0)
    for _ in range(use_50_count):
        adb.tap(*ROW_3_USE_BTN_POS, source="flow:stamina_use:use_50_stamina")
        time.sleep(0.3)


# Lower-level functions for daemon_server compatibility
def claim_free_50(adb: "ADBHelper") -> None:
    """Click the free 50 stamina claim button."""
    adb.tap(*ROW_0_CLAIM_BTN_POS, source="flow:stamina_use:claim_free_50")
    time.sleep(0.5)


def use_10_stamina(adb: "ADBHelper", count: int = 1) -> None:
    """Click Use button for 10 stamina item N times."""
    for _ in range(count):
        adb.tap(*ROW_2_USE_BTN_POS, source="flow:stamina_use:use_10_stamina")
        time.sleep(0.3)


def use_50_stamina(adb: "ADBHelper", count: int = 1) -> None:
    """Click Use button for 50 stamina item N times."""
    for _ in range(count):
        adb.tap(*ROW_3_USE_BTN_POS, source="flow:stamina_use:use_50_stamina")
        time.sleep(0.3)


def get_cooldown_seconds(frame: npt.NDArray[Any]) -> int:
    """
    OCR the cooldown timer and return seconds remaining.
    Returns 0 if ready to claim.
    """
    from utils.ocr_client import OCRClient
    ocr = OCRClient()
    scan = _scan_stamina_dialog(frame, ocr)
    if scan["free_50_timer"]:
        return _parse_timer_to_seconds(scan["free_50_timer"])
    return 0


def get_owned_counts(frame: npt.NDArray[Any]) -> dict[str, int]:
    """
    OCR owned counts for 10 and 50 stamina items.
    Returns: {"owned_10": int, "owned_50": int}
    """
    from utils.ocr_client import OCRClient
    ocr = OCRClient()
    scan = _scan_stamina_dialog(frame, ocr)
    return {
        "owned_10": scan["item_10_owned"],
        "owned_50": scan["item_50_owned"]
    }


def calculate_optimal_stamina(
    deficit: int,
    owned_10: int,
    owned_50: int,
    free_ready: bool,
    free_cooldown_secs: int = 9999,
    time_remaining_mins: int = 60
) -> tuple[bool, int, int, str]:
    """
    Calculate optimal stamina item usage.

    Args:
        deficit: Raw stamina deficit (stamina_needed - current_stamina)
        owned_10: Number of 10-stamina items owned
        owned_50: Number of 50-stamina items owned
        free_ready: Whether free 50 stamina is claimable now
        free_cooldown_secs: Seconds until free 50 is available (for arms race)
        time_remaining_mins: Minutes remaining in event (for arms race)

    Returns:
        (claim_free, use_10s, use_50s, reasoning)
    """
    if deficit <= 0:
        return False, 0, 0, "No deficit"

    target = ((deficit + 19) // 20) * 20
    claim_free = free_ready
    remaining = target
    if claim_free:
        remaining = max(0, remaining - 50)
    if remaining == 0:
        return claim_free, 0, 0, f"Free 50 covers {target} deficit"

    # Check if free 50 will be ready before event ends (with 5 min buffer)
    CLAIM_BUFFER_MINS = 5
    free_coming_soon = False
    free_cooldown_mins = free_cooldown_secs / 60
    if not free_ready and free_cooldown_mins <= (time_remaining_mins - CLAIM_BUFFER_MINS):
        free_coming_soon = True
        remaining = max(0, remaining - 50)
        if remaining == 0:
            return False, 0, 0, f"Free 50 coming in {int(free_cooldown_mins)}min covers {target} deficit"

    ideal_50s = remaining // 50
    use_50s = min(ideal_50s, owned_50)
    still_need = remaining - use_50s * 50
    ideal_10s = (still_need + 9) // 10 if still_need > 0 else 0

    if ideal_10s <= owned_10:
        use_10s = ideal_10s
        spare_50s = owned_50 - use_50s
        if use_10s >= 5 and spare_50s > 0:
            use_50s += 1
            new_need = max(0, still_need - 50)
            use_10s = (new_need + 9) // 10 if new_need > 0 else 0
    else:
        use_10s = owned_10
        still_short = still_need - use_10s * 10
        if still_short > 0:
            extra_50s = (still_short + 49) // 50
            spare_50s = owned_50 - use_50s
            use_50s += min(extra_50s, spare_50s)

    # Include free_coming_soon in total calculation
    free_50_total = (50 if claim_free else 0) + (50 if free_coming_soon else 0)
    total = free_50_total + use_50s * 50 + use_10s * 10
    if total < target:
        use_50s += owned_50 - use_50s
        use_10s += owned_10 - use_10s
        total = free_50_total + use_50s * 50 + use_10s * 10

    parts = []
    if claim_free:
        parts.append("free50")
    if free_coming_soon:
        parts.append(f"free50@{int(free_cooldown_mins)}m")
    if use_50s > 0:
        parts.append(f"{use_50s}x50")
    if use_10s > 0:
        parts.append(f"{use_10s}x10")
    reasoning = f"{'+'.join(parts) if parts else '0'}={total} for {target} target"
    if total < target:
        reasoning += f" (SHORT by {target - total})"
    return claim_free, use_10s, use_50s, reasoning


def get_stamina_decision(state: dict[str, Any]) -> dict[str, Any]:
    """
    Calculate optimal stamina item usage from state dict.

    This is the interface used by beast_training_flow.py.

    Args:
        state: Dict with:
            - stamina_needed: int
            - current_stamina: int
            - free_50_cooldown_secs: int
            - owned_10: int
            - owned_50: int
            - time_remaining_mins: int (optional, default 60)

    Returns:
        Dict with:
            - claim_free_50: bool
            - use_10_count: int
            - use_50_count: int
            - reasoning: str
    """
    current_stamina = state.get("current_stamina", 0)
    stamina_needed = state.get("stamina_needed", 0)
    free_50_cooldown = state.get("free_50_cooldown_secs", 9999)
    owned_10 = state.get("owned_10", 0)
    owned_50 = state.get("owned_50", 0)
    time_remaining_mins = state.get("time_remaining_mins", 60)

    deficit = stamina_needed - current_stamina
    free_ready = free_50_cooldown <= 0

    claim_free, use_10, use_50, reasoning = calculate_optimal_stamina(
        deficit, owned_10, owned_50, free_ready,
        free_cooldown_secs=free_50_cooldown,
        time_remaining_mins=time_remaining_mins
    )

    return {
        "claim_free_50": claim_free,
        "use_10_count": use_10,
        "use_50_count": use_50,
        "reasoning": reasoning
    }


def stamina_get(
    adb: "ADBHelper",
    win: "WindowsScreenshotHelper",
    ocr: "OCRClient",
    target: int,
    dry_run: bool = False,
    time_remaining_mins: int = 60
) -> dict[str, Any]:
    """
    Open stamina popup, scan inventory, calculate optimal usage, execute.

    Args:
        adb: ADBHelper instance
        win: WindowsScreenshotHelper instance
        ocr: OCRClient instance
        target: Stamina deficit to cover (will be rounded up to multiple of 20)
        dry_run: If True, calculate only without clicking
        time_remaining_mins: Minutes remaining in event (for free-coming-soon optimization)

    Returns:
        Dict with success, obtained, shortfall, plan, available, error
    """
    result: dict[str, Any] = {"success": False, "obtained": 0, "shortfall": target, "plan": {}, "available": {}, "error": None}

    print(f"    [STAMINA] Opening stamina dialog...")
    adb.tap(STAMINA_DISPLAY_X, STAMINA_DISPLAY_Y, source="flow:stamina_use:open_dialog")
    time.sleep(0.5)

    frame = win.get_screenshot_cv2()
    available = _scan_stamina_dialog(frame, ocr)

    # Reconcile OCR timer inference with actual Claim-button template.
    claim_visible, claim_score = _is_claim_button_visible(frame)
    if available["free_50_claimable"] and not claim_visible:
        print(
            f"    [STAMINA] OCR says free_50 ready but Claim button not visible "
            f"(score={claim_score:.4f}) - treating as NOT ready"
        )
        available["free_50_claimable"] = False
    elif (not available["free_50_claimable"]) and claim_visible:
        print(
            f"    [STAMINA] Claim button visible (score={claim_score:.4f}) - treating free_50 as ready"
        )
        available["free_50_claimable"] = True
        available["free_50_timer"] = None

    result["available"] = available

    # Parse cooldown seconds from timer text
    cooldown_secs = 0
    if available["free_50_timer"]:
        cooldown_secs = _parse_timer_to_seconds(available["free_50_timer"])
    available["cooldown_secs"] = cooldown_secs

    print(f"    [STAMINA] Available: free_50={available['free_50_claimable']}, 10x{available['item_10_owned']}, 50x{available['item_50_owned']}, cooldown={cooldown_secs}s")

    claim_free, use_10s, use_50s, reasoning = calculate_optimal_stamina(
        target,
        available["item_10_owned"],
        available["item_50_owned"],
        available["free_50_claimable"],
        free_cooldown_secs=cooldown_secs,
        time_remaining_mins=time_remaining_mins
    )
    result["plan"] = {"claim_free": claim_free, "use_10s": use_10s, "use_50s": use_50s, "reasoning": reasoning}

    will_obtain = (50 if claim_free else 0) + use_50s * 50 + use_10s * 10
    rounded_target = ((target + 19) // 20) * 20
    shortfall = max(0, rounded_target - will_obtain)
    print(f"    [STAMINA] Plan: {reasoning}")

    if dry_run:
        print(f"    [STAMINA] DRY RUN - closing")
        click_back(adb)
        time.sleep(0.3)
        result["success"] = shortfall == 0
        result["shortfall"] = shortfall
        return result

    obtained = 0

    # Claim free 50 first
    if claim_free:
        pre_frame = win.get_screenshot_cv2()
        pre_stamina = ocr.extract_number(pre_frame, STAMINA_REGION) or 0
        print(f"    [STAMINA] Claiming free 50...")
        adb.tap(*ROW_0_CLAIM_BTN_POS, source="flow:stamina_use:claim_free_50")
        time.sleep(0.3)
        confirmed, gain, post_score = _confirm_free_claim_consumed(win, ocr, pre_stamina)
        if confirmed:
            # If OCR gain is flaky but button is consumed, count expected 50.
            gained = gain if gain > 0 else 50
            obtained += gained
            print(
                f"    [STAMINA] Free 50 confirmed (gain={gained}, claim_score={post_score:.4f})"
            )
        else:
            print(
                f"    [STAMINA] Free 50 NOT confirmed (gain={gain}, claim_score={post_score:.4f}); not counting it"
            )

    # Use 50s items
    for i in range(use_50s):
        print(f"    [STAMINA] Using 50-stamina ({i+1}/{use_50s})...")
        _click_use_button(adb, row=3)
        time.sleep(0.4)
        obtained += 50

    # Use 10s items
    for i in range(use_10s):
        print(f"    [STAMINA] Using 10-stamina ({i+1}/{use_10s})...")
        _click_use_button(adb, row=2)
        time.sleep(0.4)
        obtained += 10

    click_back(adb)
    time.sleep(0.3)
    # Note: Don't call back_from_chat_flow - stamina popup only needs one back click

    result["success"] = shortfall == 0
    result["obtained"] = obtained
    result["shortfall"] = shortfall
    if shortfall > 0:
        result["error"] = f"insufficient items, short by {shortfall}"
    print(f"    [STAMINA] Done: obtained={obtained}, shortfall={shortfall}")
    return result


def stamina_use_flow(adb: "ADBHelper", screenshot_helper: "WindowsScreenshotHelper | None" = None) -> bool:
    from utils.windows_screenshot_helper import WindowsScreenshotHelper as WinHelper
    from utils.ocr_client import OCRClient
    win = screenshot_helper or WinHelper()
    ocr = OCRClient()
    result = stamina_get(adb, win, ocr, target=10, dry_run=False)
    return result["success"]


def check_use_button(frame: npt.NDArray[Any]) -> tuple[bool, float, int]:
    found, score, pos = match_template(frame, "stamina_50_icon_4k.png", search_region=(1400, 1350, 200, 200), threshold=0.05)
    if found:
        return True, score, 50
    found, score, pos = match_template(frame, "stamina_10_icon_tight_4k.png", search_region=(1400, 1100, 200, 200), threshold=0.05)
    if found:
        return True, score, 10
    return False, score, 0
