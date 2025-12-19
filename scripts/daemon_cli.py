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

Examples:
    python daemon_cli.py run_flow bag_flow
    python daemon_cli.py set_config IDLE_THRESHOLD 600
    python daemon_cli.py watch  # Press Ctrl+C to stop

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


async def send_command(cmd: str, args: dict = None, uri: str = DEFAULT_URI) -> dict:
    """
    Send a command to the daemon and return the response.

    Args:
        cmd: Command name (e.g., "run_flow", "status")
        args: Command arguments dict
        uri: WebSocket URI (default ws://localhost:9876)

    Returns:
        Response dict from daemon
    """
    try:
        async with websockets.connect(uri, close_timeout=5) as ws:
            request = {"cmd": cmd, "args": args or {}}
            await ws.send(json.dumps(request))
            response = await asyncio.wait_for(ws.recv(), timeout=30)
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

    # Send command and print response
    result = asyncio.run(send_command(cmd, args))

    # Pretty print result
    if result.get("success"):
        data = result.get("data", {})
        print(json.dumps(data, indent=2, default=str))
    else:
        error = result.get("error", "Unknown error")
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
