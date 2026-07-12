#!/usr/bin/env python3
"""
Spend all stamina by running elite_zombie flow repeatedly.

Usage:
    python scripts/spend_stamina.py [--max-runs N] [--delay SECONDS]

Options:
    --max-runs N     Maximum number of rally attempts (default: 10)
    --delay SECONDS  Delay between runs in seconds (default: 5)
    --min-stamina N  Stop when stamina falls below this (default: 20)
"""
import asyncio
import json
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import websockets
except ImportError:
    print("Error: websockets library required")
    print("Install with: pip install websockets")
    sys.exit(1)

DEFAULT_URI = "ws://127.0.0.1:9876"


async def send_command(cmd: str, args: dict = None, uri: str = DEFAULT_URI, timeout: int = 180) -> dict:
    """Send command to daemon and return response."""
    try:
        async with websockets.connect(uri, close_timeout=5) as ws:
            request = {"cmd": cmd, "args": args or {}}
            await ws.send(json.dumps(request))
            response = await asyncio.wait_for(ws.recv(), timeout=timeout)
            return json.loads(response)
    except ConnectionRefusedError:
        return {"success": False, "error": "Cannot connect to daemon"}
    except asyncio.TimeoutError:
        return {"success": False, "error": "Command timed out"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def read_stamina() -> tuple[int | None, str]:
    """
    Read current stamina from screen (fresh OCR).

    Returns:
        (stamina, view_state) - stamina may be None if not in TOWN
    """
    result = await send_command("read_stamina", timeout=30)
    if result.get("success"):
        data = result.get("data", {})
        return data.get("stamina"), data.get("view", "UNKNOWN")
    return None, "ERROR"


async def get_view() -> str:
    """Get current view state."""
    result = await send_command("get_view", timeout=10)
    if result.get("success"):
        return result.get("data", {}).get("view", "UNKNOWN")
    return "ERROR"


async def return_to_base() -> bool:
    """Navigate back to TOWN/WORLD view."""
    print("  Navigating back to base view...")
    result = await send_command("return_to_base", timeout=60)
    if result.get("success"):
        return result.get("data", {}).get("success", False)
    return False


async def run_elite_zombie() -> bool:
    """Run elite_zombie flow and return success status."""
    print("  Running elite_zombie flow...")
    result = await send_command("run_flow", {"flow": "elite_zombie"})
    if result.get("success"):
        flow_result = result.get("data", {}).get("result")
        print(f"  Flow completed: {flow_result}")
        return flow_result
    else:
        print(f"  Flow failed: {result.get('error')}")
        return False


async def ensure_town_view() -> bool:
    """Ensure we're in TOWN view, navigate if needed."""
    view = await get_view()
    if view == "TOWN":
        return True

    print(f"  Current view: {view}, need TOWN view")
    if await return_to_base():
        # Verify we're now in TOWN
        view = await get_view()
        if view == "TOWN":
            return True
        print(f"  WARNING: Still in {view} after return_to_base")

    return False


async def spend_stamina(max_runs: int = 10, delay: float = 5.0, min_stamina: int = 20):
    """
    Spend stamina by repeatedly running elite_zombie flow.

    Each elite_zombie rally costs ~20 stamina. We run the flow repeatedly
    until we hit max_runs or stamina falls below min_stamina.
    """
    print(f"=== SPEND STAMINA ===")
    print(f"Max runs: {max_runs}, Delay: {delay}s, Min stamina: {min_stamina}")
    print()

    # Check daemon is running
    result = await send_command("ping")
    if not result.get("success"):
        print("ERROR: Cannot connect to daemon. Is it running?")
        print("The daemon needs to be restarted to pick up new API commands.")
        return

    # Ensure we're in TOWN view first
    print("Checking view state...")
    if not await ensure_town_view():
        print("ERROR: Could not navigate to TOWN view")
        return

    # Get initial stamina
    stamina, view = await read_stamina()
    if stamina is None:
        print(f"ERROR: Could not read stamina (view: {view})")
        return

    print(f"Initial stamina: {stamina}")
    print()

    if stamina < min_stamina:
        print(f"Stamina ({stamina}) already below minimum ({min_stamina}). Nothing to do.")
        return

    successful_runs = 0
    for i in range(max_runs):
        print(f"[{i+1}/{max_runs}] Stamina: {stamina}, attempting elite zombie rally...")

        success = await run_elite_zombie()
        if success:
            successful_runs += 1

        # Return to TOWN view to read stamina
        await asyncio.sleep(1)  # Brief pause for UI to settle
        if not await ensure_town_view():
            print("  WARNING: Could not return to TOWN view")

        # Read stamina after run
        stamina, view = await read_stamina()
        if stamina is not None:
            print(f"  Stamina after run: {stamina}")
        else:
            print(f"  Could not read stamina (view: {view})")
            # Try to read again after a delay
            await asyncio.sleep(2)
            stamina, view = await read_stamina()
            if stamina is not None:
                print(f"  Stamina (retry): {stamina}")

        # If stamina is known and below threshold, stop
        if stamina is not None and stamina < min_stamina:
            print(f"\nStamina ({stamina}) below minimum ({min_stamina}). Stopping.")
            break

        # Delay before next run (unless last iteration)
        if i < max_runs - 1:
            print(f"  Waiting {delay}s before next run...")
            await asyncio.sleep(delay)

        print()

    print(f"=== COMPLETE ===")
    print(f"Successful rally attempts: {successful_runs}/{max_runs}")

    # Final stamina reading
    if await ensure_town_view():
        stamina, _ = await read_stamina()
        if stamina is not None:
            print(f"Final stamina: {stamina}")


def main():
    parser = argparse.ArgumentParser(description="Spend stamina via elite zombie rallies")
    parser.add_argument("--max-runs", type=int, default=10, help="Maximum rally attempts")
    parser.add_argument("--delay", type=float, default=5.0, help="Delay between runs (seconds)")
    parser.add_argument("--min-stamina", type=int, default=20, help="Stop when stamina falls below this")
    args = parser.parse_args()

    asyncio.run(spend_stamina(max_runs=args.max_runs, delay=args.delay, min_stamina=args.min_stamina))


if __name__ == "__main__":
    main()
