#!/usr/bin/env python3
"""
CLI client for daemon WebSocket API.

This script sends commands to a running icon_daemon via WebSocket.
The daemon must be running with its WebSocket server active.

Usage:
    python daemon_cli.py status              # Get daemon status
    python daemon_cli.py run_flow tavern     # Trigger tavern_quest flow
    python daemon_cli.py list_flows          # List available flows
    python daemon_cli.py get_state           # Get full daemon state
    python daemon_cli.py set_config KEY VAL  # Set config value
    python daemon_cli.py pause               # Pause daemon loop
    python daemon_cli.py resume              # Resume daemon loop
    python daemon_cli.py save_state          # Force save state to disk
    python daemon_cli.py watch               # Stream live events
    python daemon_cli.py read_stamina        # Read current stamina (fresh OCR)
    python daemon_cli.py get_view            # Get current view state
    python daemon_cli.py return_to_base      # Navigate back to TOWN/WORLD
    python daemon_cli.py apply_title <name>   # Apply kingdom title at Royal City
    python daemon_cli.py list_titles          # List available kingdom titles

Rally Target Commands (Beast Training):
    python daemon_cli.py get_rally_status              # Show status + optimal stamina strategy
    python daemon_cli.py set_rally_count 5             # "I did 5 rallies manually"
    python daemon_cli.py set_rally_target 12           # "Do 12 total this block"
    python daemon_cli.py set_rally_target 15 --next    # "Do 15 in NEXT Beast Training"
    python daemon_cli.py add_rallies 7                 # "Do 7 more from current count"

Stamina Commands:
    python daemon_cli.py use_stamina --use-50 3 --use-10 1   # Use stamina items
    python daemon_cli.py use_stamina --claim-free            # Claim free 50
    python daemon_cli.py get_stamina_inventory               # Check inventory

Zombie Attack Commands:
    python daemon_cli.py run_zombie_attack iron_mine         # Attack iron mine zombie
    python daemon_cli.py run_zombie_attack gold              # Attack gold zombie
    python daemon_cli.py run_zombie_attack food              # Attack food zombie
    python daemon_cli.py run_zombie_attack iron_mine --plus 15  # Custom plus clicks
    python daemon_cli.py set_zombie_mode iron_mine 4         # Set mode for 4 hours
    python daemon_cli.py get_zombie_mode                     # Check current mode
    python daemon_cli.py clear_zombie_mode                   # Reset to elite

Examples:
    python daemon_cli.py run_flow bag_flow
    python daemon_cli.py set_config IDLE_THRESHOLD 600
    python daemon_cli.py watch  # Press Ctrl+C to stop
    python daemon_cli.py read_stamina  # Get fresh stamina reading
    python daemon_cli.py set_rally_count 3  # Tell daemon you did 3 manual rallies
    python daemon_cli.py add_rallies 10  # Ask daemon to run 10 more rallies
    python daemon_cli.py apply_title ministry_of_construction  # Get building buff

For Claude Code integration:
    Claude can call this script to interact with the running daemon
    without stopping it. Ask Claude to "run tavern quest" and it will
    execute: python daemon_cli.py run_flow tavern_quest
"""
import asyncio
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import websockets
except ImportError:
    print("Error: websockets library required")
    print("Install with: pip install websockets")
    sys.exit(1)

DEFAULT_URI = "ws://localhost:9876"


async def send_command(cmd: str, args: dict = None, uri: str = DEFAULT_URI, timeout: int = None) -> dict:
    """
    Send a command to the daemon and return the response.

    Args:
        cmd: Command name (e.g., "run_flow", "status")
        args: Command arguments dict
        uri: WebSocket URI (default ws://localhost:9876)
        timeout: Response timeout in seconds (default: 30 for status, 180 for run_flow)

    Returns:
        Response dict from daemon
    """
    # Flows can take a while (navigation, OCR, scrolling, etc.)
    if timeout is None:
        timeout = 180 if cmd == "run_flow" else 30

    try:
        async with websockets.connect(uri, close_timeout=5) as ws:
            request = {"cmd": cmd, "args": args or {}}
            await ws.send(json.dumps(request))
            response = await asyncio.wait_for(ws.recv(), timeout=timeout)
            return json.loads(response)
    except ConnectionRefusedError:
        return {"success": False, "error": "Cannot connect to daemon. Is it running?"}
    except asyncio.TimeoutError:
        return {"success": False, "error": "Command timed out"}
    except Exception as e:
        return {"success": False, "error": str(e)}


async def watch_events(uri: str = DEFAULT_URI):
    """
    Stream live events from the daemon.

    Connects to the WebSocket and prints all events received.
    Press Ctrl+C to stop.
    """
    try:
        async with websockets.connect(uri) as ws:
            print(f"Connected to {uri}")
            print("Watching for events... (Ctrl+C to stop)")
            print("-" * 60)

            async for message in ws:
                data = json.loads(message)
                if data.get("type") == "event":
                    event = data.get("event", "?")
                    event_data = data.get("data", {})
                    timestamp = data.get("timestamp", "")[:19]  # Trim microseconds
                    print(f"[{timestamp}] {event}: {json.dumps(event_data)}")
                elif data.get("type") == "response":
                    # Response to a command (shouldn't happen in watch mode)
                    print(f"Response: {json.dumps(data)}")

    except ConnectionRefusedError:
        print("Error: Cannot connect to daemon. Is it running?")
        sys.exit(1)
    except KeyboardInterrupt:
        print("\nStopped watching.")


def parse_value(value_str: str):
    """
    Parse a string value into appropriate Python type.

    Handles: int, float, bool, None, string
    """
    if value_str.lower() == "none":
        return None
    if value_str.lower() == "true":
        return True
    if value_str.lower() == "false":
        return False
    try:
        return int(value_str)
    except ValueError:
        pass
    try:
        return float(value_str)
    except ValueError:
        pass
    return value_str


def print_help():
    """Print usage help."""
    print(__doc__)


def main():
    if len(sys.argv) < 2:
        print_help()
        sys.exit(1)

    cmd = sys.argv[1]
    args = {}

    # Handle special commands
    if cmd in ("-h", "--help", "help"):
        print_help()
        sys.exit(0)

    if cmd == "watch":
        asyncio.run(watch_events())
        return

    # Parse command-specific arguments
    if cmd == "run_flow":
        if len(sys.argv) < 3:
            print("Error: run_flow requires a flow name")
            print("Usage: daemon_cli.py run_flow <flow_name>")
            sys.exit(1)
        args["flow"] = sys.argv[2]

    elif cmd == "set_config":
        if len(sys.argv) < 4:
            print("Error: set_config requires key and value")
            print("Usage: daemon_cli.py set_config <key> <value>")
            sys.exit(1)
        args["key"] = sys.argv[2]
        args["value"] = parse_value(sys.argv[3])

    elif cmd == "set_rally_count":
        if len(sys.argv) < 3:
            print("Error: set_rally_count requires a count")
            print("Usage: daemon_cli.py set_rally_count <count>")
            sys.exit(1)
        args["count"] = int(sys.argv[2])

    elif cmd == "set_rally_target":
        if len(sys.argv) < 3:
            print("Error: set_rally_target requires a target")
            print("Usage: daemon_cli.py set_rally_target <target> [--next]")
            sys.exit(1)
        args["target"] = int(sys.argv[2])
        if "--next" in sys.argv:
            args["next"] = True

    elif cmd == "add_rallies":
        if len(sys.argv) < 3:
            print("Error: add_rallies requires a count")
            print("Usage: daemon_cli.py add_rallies <count>")
            sys.exit(1)
        args["count"] = int(sys.argv[2])

    elif cmd == "apply_title":
        if len(sys.argv) < 3:
            print("Error: apply_title requires a title name")
            print("Usage: daemon_cli.py apply_title <title_name>")
            print("Available: ministry_of_construction, minister_of_science, minister_of_health, etc.")
            sys.exit(1)
        args["title"] = sys.argv[2]

    elif cmd == "use_stamina":
        # Parse JSON-like args or individual flags
        # Usage: daemon_cli.py use_stamina --claim-free --use-10 5 --use-50 3
        # Or:    daemon_cli.py use_stamina {"use_10_count": 5, "use_50_count": 3}
        i = 2
        while i < len(sys.argv):
            arg = sys.argv[i]
            if arg == "--claim-free":
                args["claim_free_50"] = True
            elif arg == "--use-10" and i + 1 < len(sys.argv):
                args["use_10_count"] = int(sys.argv[i + 1])
                i += 1
            elif arg == "--use-50" and i + 1 < len(sys.argv):
                args["use_50_count"] = int(sys.argv[i + 1])
                i += 1
            elif arg.startswith("{"):
                # JSON format
                try:
                    args.update(json.loads(arg))
                except json.JSONDecodeError:
                    print(f"Error: Invalid JSON: {arg}")
                    sys.exit(1)
            i += 1

    elif cmd == "run_zombie_attack":
        # Usage: daemon_cli.py run_zombie_attack <type> [--plus N]
        if len(sys.argv) < 3:
            print("Error: run_zombie_attack requires a zombie type")
            print("Usage: daemon_cli.py run_zombie_attack <iron_mine|gold|food> [--plus N]")
            sys.exit(1)
        args["zombie_type"] = sys.argv[2]
        # Check for --plus argument
        if "--plus" in sys.argv:
            plus_idx = sys.argv.index("--plus")
            if plus_idx + 1 < len(sys.argv):
                args["plus_clicks"] = int(sys.argv[plus_idx + 1])

    elif cmd == "set_zombie_mode":
        # Usage: daemon_cli.py set_zombie_mode <mode> [hours]
        if len(sys.argv) < 3:
            print("Error: set_zombie_mode requires a mode")
            print("Usage: daemon_cli.py set_zombie_mode <iron_mine|gold|food> [hours]")
            sys.exit(1)
        args["mode"] = sys.argv[2]
        if len(sys.argv) >= 4:
            args["hours"] = float(sys.argv[3])

    # Send command and print response
    result = asyncio.run(send_command(cmd, args))

    # Pretty print result
    if result.get("success"):
        data = result.get("data", {})

        # Special formatting for get_rally_status
        if cmd == "get_rally_status":
            print_rally_status(data)
        else:
            print(json.dumps(data, indent=2, default=str))
    else:
        error = result.get("error", "Unknown error")
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)


def print_rally_status(data: dict):
    """Pretty print rally status with optimal strategy."""
    print("=" * 60)
    print("ARMS RACE STATUS")
    print("=" * 60)

    # Event info
    event = data.get("current_event", "Unknown")
    mins = data.get("event_remaining_mins", 0)
    print(f"Event: {event} ({mins} mins remaining)")
    print()

    # Points progress
    if data.get("is_beast_training"):
        current = data.get("current_points")
        target = data.get("chest3_target", 30000)
        remaining = data.get("points_remaining")
        rallies = data.get("rallies_needed")
        mode = data.get("zombie_mode", "elite")
        pts_per = data.get("points_per_rally", "?")
        sta_per = data.get("stamina_per_rally", "?")

        if current is not None:
            print(f"Points: {current:,} / {target:,} ({remaining:,} remaining)")
            print(f"Rallies needed: {rallies} ({mode} @ {pts_per} pts, {sta_per} stamina each)")
        else:
            print("Points: Could not read from game UI")
        print()

    # Stamina situation
    print("STAMINA:")
    current_sta = data.get("current_stamina", 0) or 0
    owned_10 = data.get("owned_10_stamina", 0)
    owned_50 = data.get("owned_50_stamina", 0)
    free_avail = data.get("free_50_available", False)
    free_cd = data.get("free_50_cooldown_secs", 0)
    total = data.get("total_stamina_available", 0)
    needed = data.get("stamina_needed")
    shortfall = data.get("stamina_shortfall", 0)

    print(f"  Current: {current_sta}")
    print(f"  10-stamina items: {owned_10} ({owned_10 * 10} sta)")
    print(f"  50-stamina items: {owned_50} ({owned_50 * 50} sta)")
    if free_avail:
        print(f"  Free 50: AVAILABLE")
    else:
        print(f"  Free 50: {free_cd // 60}m {free_cd % 60}s cooldown")
    print(f"  Total available: {total}")
    if needed:
        print(f"  Needed: {needed}")
        if shortfall > 0:
            print(f"  SHORTFALL: {shortfall} (NOT ENOUGH!)")
        else:
            print(f"  Surplus: {total - needed}")
    print()

    # Optimal strategy
    strategy = data.get("optimal_strategy")
    if strategy:
        regen = strategy.get("stamina_regen", 0)
        effective = strategy.get("effective_stamina", current_sta)

        print("OPTIMAL STRATEGY:")
        if regen > 0:
            print(f"  Natural regen: +{regen} stamina (1 per 5 mins)")
            print(f"  Effective stamina: {current_sta} + {regen} = {effective}")
        print(f"  {strategy['reasoning']}")
        print()

        if strategy.get("stamina_gained", 0) > 0:
            print("  To execute now:")
            parts = []
            if strategy.get("claim_free_50"):
                parts.append('"claim_free_50": true')
            if strategy.get("use_10_count", 0) > 0:
                parts.append(f'"use_10_count": {strategy["use_10_count"]}')
            if strategy.get("use_50_count", 0) > 0:
                parts.append(f'"use_50_count": {strategy["use_50_count"]}')
            if parts:
                print(f'  python daemon_cli.py use_stamina {{{", ".join(parts)}}}')
                print(f"  => Gains {strategy['stamina_gained']} stamina")
    elif needed and current_sta >= needed:
        print("STRATEGY: No items needed - current stamina covers all rallies")

    print()
    print("=" * 60)


if __name__ == "__main__":
    main()
