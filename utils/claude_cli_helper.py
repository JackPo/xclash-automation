"""
Claude CLI helper for making decisions via subprocess.

Uses Claude CLI to get JSON decisions for complex game logic.
"""
from __future__ import annotations

import json
import logging
import subprocess
from typing import Optional

logger = logging.getLogger(__name__)


def get_stamina_decision(state: dict) -> dict:
    """
    Calculate optimal stamina item usage using deterministic rule engine.

    NOTE: Claude CLI is NOT used - the deterministic algorithm is sufficient
    and much faster. Claude CLI was causing 60s timeouts for simple math.

    Args:
        state: Dict with:
            - current_points: int (optional, for logging)
            - rallies_needed: int (optional, for logging)
            - stamina_needed: int
            - current_stamina: int
            - free_50_cooldown_secs: int
            - owned_10: int
            - owned_50: int
            - phase: str (optional, for logging)

    Returns:
        Dict with:
            - claim_free_50: bool
            - use_10_count: int
            - use_50_count: int
            - reasoning: str
    """
    # Use deterministic rule engine directly (no Claude CLI needed)
    return _fallback_decision(state)


def _parse_json_response(text: str) -> dict | None:
    """
    Parse JSON from Claude response, handling various formats.

    Claude might return:
    - Pure JSON
    - JSON wrapped in markdown code blocks
    - JSON with extra text around it
    """
    text = text.strip()

    # Try direct parse first
    try:
        data = json.loads(text)
        if _validate_decision(data):
            return data
    except json.JSONDecodeError:
        pass

    # Remove markdown code fences
    if "```json" in text:
        start = text.find("```json") + 7
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()
    elif "```" in text:
        start = text.find("```") + 3
        end = text.find("```", start)
        if end > start:
            text = text[start:end].strip()

    # Try to find JSON object in text
    try:
        # Find first { and last }
        start = text.find("{")
        end = text.rfind("}") + 1
        if start >= 0 and end > start:
            json_str = text[start:end]
            data = json.loads(json_str)
            if _validate_decision(data):
                return data
    except json.JSONDecodeError:
        pass

    return None


def _validate_decision(data: dict) -> bool:
    """Validate that the decision has required fields."""
    if not isinstance(data, dict):
        return False

    # Check for required fields (allow missing = default to False/0)
    return True  # Be lenient - fill in defaults in fallback


def calculate_optimal_stamina(deficit: int, owned_10: int, owned_50: int, free_ready: bool) -> tuple:
    """
    Deterministic rule engine for optimal stamina item usage.

    Rules:
    1. Round up to next multiple of 20 (each rally = 20 stamina)
    2. Claim free 50 first if available
    3. Use 50s for bulk, 10s for remainder
    4. If we'd need 5+ 10s AND have spare 50s, use a 50 instead (5x10 = 1x50)
    5. If we don't have enough 10s for remainder, use an extra 50

    Args:
        deficit: Raw stamina deficit (stamina_needed - current_stamina)
        owned_10: Number of 10-stamina items owned
        owned_50: Number of 50-stamina items owned
        free_ready: Whether free 50 stamina is available (cooldown <= 0)

    Returns:
        (claim_free, use_10s, use_50s, reasoning)
    """
    if deficit <= 0:
        return False, 0, 0, "No deficit"

    # Round up to next multiple of 20 (stamina spent per rally)
    target = ((deficit + 19) // 20) * 20

    # Step 1: Claim free 50 if available
    claim_free = free_ready
    remaining = target
    if claim_free:
        remaining = max(0, remaining - 50)

    if remaining == 0:
        return claim_free, 0, 0, f"Free 50 covers {target} deficit"

    # Step 2: Calculate ideal 50s and remainder
    ideal_50s = remaining // 50
    remainder_after_50s = remaining % 50

    # Use available 50s
    use_50s = min(ideal_50s, owned_50)
    covered_by_50s = use_50s * 50

    # What's left to cover?
    still_need = remaining - covered_by_50s

    # Step 3: Calculate 10s needed
    ideal_10s = (still_need + 9) // 10 if still_need > 0 else 0

    if ideal_10s <= owned_10:
        # We have enough 10s
        use_10s = ideal_10s

        # Optimization: if using 5+ 10s and have spare 50s, swap 5x10 for 1x50
        spare_50s = owned_50 - use_50s
        if use_10s >= 5 and spare_50s > 0:
            use_50s += 1
            new_need = max(0, still_need - 50)
            use_10s = (new_need + 9) // 10 if new_need > 0 else 0
    else:
        # Not enough 10s - use what we have and supplement with 50s
        use_10s = owned_10
        covered_by_10s = use_10s * 10
        still_short = still_need - covered_by_10s

        if still_short > 0:
            # Use extra 50s to cover the shortfall
            extra_50s_needed = (still_short + 49) // 50
            spare_50s = owned_50 - use_50s
            use_50s += min(extra_50s_needed, spare_50s)

    # Final check: if still short, use ALL remaining items
    total_claimed = (50 if claim_free else 0) + use_50s * 50 + use_10s * 10
    if total_claimed < target:
        # Use all remaining items
        remaining_50s = owned_50 - use_50s
        remaining_10s = owned_10 - use_10s
        use_50s += remaining_50s
        use_10s += remaining_10s
        total_claimed = (50 if claim_free else 0) + use_50s * 50 + use_10s * 10

    # Build reasoning
    parts = []
    if claim_free:
        parts.append("free50")
    if use_50s > 0:
        parts.append(f"{use_50s}x50")
    if use_10s > 0:
        parts.append(f"{use_10s}x10")

    total = (50 if claim_free else 0) + use_50s * 50 + use_10s * 10
    reasoning = f"{'+'.join(parts) if parts else '0'}={total} for {target} target"
    if total < target:
        reasoning += f" (SHORT by {target - total})"

    return claim_free, use_10s, use_50s, reasoning


def _fallback_decision(state: dict) -> dict:
    """
    Fallback decision using deterministic rule engine.

    This is now the PRIMARY decision algorithm - Claude CLI is optional.
    """
    logger.info("Using deterministic rule engine")

    current_stamina = state.get("current_stamina", 0)
    stamina_needed = state.get("stamina_needed", 0)
    free_50_cooldown = state.get("free_50_cooldown_secs", 9999)
    owned_10 = state.get("owned_10", 0)
    owned_50 = state.get("owned_50", 0)

    deficit = stamina_needed - current_stamina
    free_ready = free_50_cooldown <= 0

    claim_free, use_10, use_50, reasoning = calculate_optimal_stamina(
        deficit, owned_10, owned_50, free_ready
    )

    return {
        "claim_free_50": claim_free,
        "use_10_count": use_10,
        "use_50_count": use_50,
        "reasoning": reasoning
    }


# =============================================================================
# CLI TEST
# =============================================================================

if __name__ == "__main__":
    import sys

    logging.basicConfig(level=logging.DEBUG, format="%(levelname)s: %(message)s")

    print("=== Claude CLI Helper Test ===\n")

    # Example state
    test_state = {
        "current_points": 20000,
        "rallies_needed": 5,
        "stamina_needed": 100,
        "current_stamina": 40,
        "free_50_cooldown_secs": 3000,
        "owned_10": 19,
        "owned_50": 10,
        "phase": "hour_mark"
    }

    if len(sys.argv) > 1 and sys.argv[1] == "--fallback":
        print("Testing fallback decision only...")
        decision = _fallback_decision(test_state)
    else:
        print("Testing Claude CLI decision...")
        decision = get_stamina_decision(test_state)

    print(f"\nDecision: {json.dumps(decision, indent=2)}")
