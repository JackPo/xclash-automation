"""
WebSocket server for daemon control.

Runs async in a background thread, accepts connections on ws://localhost:9876.
Enables external processes to trigger flows, check status, and receive push events.

Protocol: JSON messages
- Client -> Server: {"cmd": "run_flow", "args": {"flow": "tavern_quest"}}
- Server -> Client: {"type": "response", "cmd": "run_flow", "success": true, "data": {...}}
- Server -> Client: {"type": "event", "event": "flow_started", "data": {"flow": "tavern_quest"}}
"""
import asyncio
import json
import logging
import threading
from datetime import datetime
from typing import Set, TYPE_CHECKING

if TYPE_CHECKING:
    from scripts.icon_daemon import IconDaemon

try:
    import websockets
    from websockets.server import serve
except ImportError:
    websockets = None

DEFAULT_PORT = 9876
logger = logging.getLogger("DaemonServer")


class DaemonWebSocketServer:
    """
    WebSocket server for daemon control.

    Runs in a background thread with its own asyncio event loop.
    Commands are processed synchronously by calling daemon methods.
    Events can be broadcast from the daemon thread to all connected clients.
    """

    def __init__(self, daemon: "IconDaemon", port: int = DEFAULT_PORT):
        """
        Initialize the WebSocket server.

        Args:
            daemon: The IconDaemon instance to control
            port: Port to listen on (default 9876)
        """
        if websockets is None:
            raise ImportError("websockets library required: pip install websockets")

        self.daemon = daemon
        self.port = port
        self.clients: Set = set()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.thread: threading.Thread | None = None
        self.running = False

    def start(self):
        """Start WebSocket server in background thread."""
        self.running = True
        self.thread = threading.Thread(target=self._run_server, daemon=True, name="DaemonWS")
        self.thread.start()
        logger.info(f"WebSocket server starting on ws://localhost:{self.port}")

    def stop(self):
        """Stop the WebSocket server."""
        self.running = False
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.thread:
            self.thread.join(timeout=2.0)
        logger.info("WebSocket server stopped")

    def _run_server(self):
        """Run async event loop in dedicated thread."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._serve())
        except Exception as e:
            logger.error(f"WebSocket server error: {e}")
        finally:
            self.loop.close()

    async def _serve(self):
        """Main server coroutine."""
        try:
            async with serve(self._handle_client, "127.0.0.1", self.port):
                logger.info(f"WebSocket server listening on ws://127.0.0.1:{self.port}")
                # Run until stopped
                while self.running:
                    await asyncio.sleep(0.5)
        except OSError as e:
            logger.error(f"Failed to start WebSocket server: {e}")

    async def _handle_client(self, websocket):
        """Handle a single WebSocket connection."""
        self.clients.add(websocket)
        client_count = len(self.clients)
        logger.info(f"Client connected ({client_count} total)")

        try:
            async for message in websocket:
                try:
                    response = self._process_message(message)
                    await websocket.send(json.dumps(response))
                except Exception as e:
                    error_response = {"type": "response", "success": False, "error": str(e)}
                    await websocket.send(json.dumps(error_response))
        except websockets.ConnectionClosed:
            pass
        except Exception as e:
            logger.error(f"Client handler error: {e}")
        finally:
            self.clients.discard(websocket)
            logger.info(f"Client disconnected ({len(self.clients)} total)")

    def _process_message(self, message: str) -> dict:
        """
        Process incoming message and return response.

        Args:
            message: JSON string with {cmd, args}

        Returns:
            Response dict with {type, cmd, success, data/error}
        """
        data = json.loads(message)
        cmd = data.get("cmd")
        args = data.get("args", {})

        # Command dispatch table
        handlers = {
            "run_flow": self._cmd_run_flow,
            "status": self._cmd_status,
            "list_flows": self._cmd_list_flows,
            "get_state": self._cmd_get_state,
            "set_config": self._cmd_set_config,
            "pause": self._cmd_pause,
            "resume": self._cmd_resume,
            "ping": self._cmd_ping,
            "save_state": self._cmd_save_state,
            "read_stamina": self._cmd_read_stamina,
            "return_to_base": self._cmd_return_to_base,
            "get_view": self._cmd_get_view,
            # Rally target commands
            "set_rally_count": self._cmd_set_rally_count,
            "set_rally_target": self._cmd_set_rally_target,
            "add_rallies": self._cmd_add_rallies,
            "get_rally_status": self._cmd_get_rally_status,
        }

        handler = handlers.get(cmd)
        if handler:
            try:
                result = handler(args)
                return {"type": "response", "cmd": cmd, "success": True, "data": result}
            except Exception as e:
                logger.error(f"Command {cmd} failed: {e}")
                return {"type": "response", "cmd": cmd, "success": False, "error": str(e)}
        else:
            return {"type": "response", "cmd": cmd, "success": False, "error": f"Unknown command: {cmd}"}

    def broadcast(self, event: str, data: dict):
        """
        Push event to all connected clients (called from daemon thread).

        Args:
            event: Event name (e.g., "flow_started", "icon_detected")
            data: Event data dict
        """
        if not self.clients or not self.loop:
            return

        message = json.dumps({
            "type": "event",
            "event": event,
            "data": data,
            "timestamp": datetime.now().isoformat()
        })

        # Schedule broadcast in the server's event loop
        asyncio.run_coroutine_threadsafe(self._broadcast_async(message), self.loop)

    async def _broadcast_async(self, message: str):
        """Async broadcast to all clients."""
        if not self.clients:
            return

        # Send to all clients, ignore individual failures
        await asyncio.gather(
            *[client.send(message) for client in self.clients.copy()],
            return_exceptions=True
        )

    # =========================================================================
    # Command Handlers
    # =========================================================================

    def _cmd_run_flow(self, args: dict) -> dict:
        """Trigger a specific flow."""
        flow_name = args.get("flow")
        if not flow_name:
            raise ValueError("Missing 'flow' argument")
        return self.daemon.trigger_flow(flow_name)

    def _cmd_status(self, args: dict) -> dict:
        """Get current daemon status."""
        return self.daemon.get_status()

    def _cmd_list_flows(self, args: dict) -> dict:
        """List available flows."""
        flows = self.daemon.get_available_flows()
        return {
            "flows": [
                {"name": name, "critical": critical}
                for name, (_, critical) in flows.items()
            ]
        }

    def _cmd_get_state(self, args: dict) -> dict:
        """Get full daemon state."""
        return self.daemon.scheduler.get_daemon_state()

    def _cmd_set_config(self, args: dict) -> dict:
        """Dynamically update a config value."""
        key = args.get("key")
        value = args.get("value")
        if not key:
            raise ValueError("Missing 'key' argument")
        return self.daemon.set_config(key, value)

    def _cmd_pause(self, args: dict) -> dict:
        """Pause daemon main loop."""
        self.daemon.paused = True
        self.daemon.scheduler.update_daemon_state(paused=True)
        self.broadcast("paused", {"paused": True})
        return {"paused": True}

    def _cmd_resume(self, args: dict) -> dict:
        """Resume daemon main loop."""
        self.daemon.paused = False
        self.daemon.scheduler.update_daemon_state(paused=False)
        self.broadcast("resumed", {"paused": False})
        return {"paused": False}

    def _cmd_ping(self, args: dict) -> dict:
        """Health check."""
        return {
            "pong": True,
            "time": datetime.now().isoformat(),
            "clients": len(self.clients),
        }

    def _cmd_save_state(self, args: dict) -> dict:
        """Force save daemon state now."""
        self.daemon._save_runtime_state()
        return {"saved": True}

    def _cmd_read_stamina(self, args: dict) -> dict:
        """Read current stamina from screen (fresh OCR)."""
        from utils.view_state_detector import detect_view, ViewState

        frame = self.daemon.windows_helper.get_screenshot_cv2()

        # Check view state first
        view_state, view_score = detect_view(frame)

        # Only read stamina if in TOWN view
        if view_state != ViewState.TOWN:
            return {
                "stamina": None,
                "view": view_state.name,
                "error": f"Not in TOWN view (current: {view_state.name})"
            }

        # Read stamina via OCR
        stamina = self.daemon.ocr_client.extract_number(
            frame, self.daemon.STAMINA_REGION
        )

        return {
            "stamina": stamina,
            "view": view_state.name,
            "valid": stamina is not None and 0 <= stamina <= 200
        }

    def _cmd_return_to_base(self, args: dict) -> dict:
        """Navigate back to TOWN/WORLD view."""
        from utils.return_to_base_view import return_to_base_view

        success = return_to_base_view(
            self.daemon.adb,
            self.daemon.windows_helper,
            debug=args.get("debug", False)
        )
        return {"success": success}

    def _cmd_get_view(self, args: dict) -> dict:
        """Get current view state."""
        from utils.view_state_detector import detect_view

        frame = self.daemon.windows_helper.get_screenshot_cv2()
        view_state, score = detect_view(frame)

        return {
            "view": view_state.name,
            "score": round(score, 4)
        }

    # =========================================================================
    # Rally Target Commands
    # =========================================================================

    def _cmd_set_rally_count(self, args: dict) -> dict:
        """Set the current rally count (e.g., 'I did 5 manually')."""
        count = args.get("count")
        if count is None:
            raise ValueError("Missing 'count' argument")
        count = int(count)

        self.daemon.scheduler.update_arms_race_state(beast_training_rally_count=count)
        self.daemon.beast_training_rally_count = count  # Update daemon's in-memory count

        arms_race = self.daemon.scheduler.get_arms_race_state()
        target = arms_race.get("beast_training_target_rallies")

        return {
            "rally_count": count,
            "target": target,
            "remaining": (target - count) if target else None
        }

    def _cmd_set_rally_target(self, args: dict) -> dict:
        """Set rally target for current or next Beast Training block."""
        target = args.get("target")
        if target is None:
            raise ValueError("Missing 'target' argument")
        target = int(target)

        next_block = args.get("next", False)

        if next_block:
            self.daemon.scheduler.update_arms_race_state(beast_training_next_target_rallies=target)
            return {"target": target, "block": "next"}
        else:
            self.daemon.scheduler.update_arms_race_state(beast_training_target_rallies=target)
            arms_race = self.daemon.scheduler.get_arms_race_state()
            count = arms_race.get("beast_training_rally_count", 0)
            return {
                "target": target,
                "block": "current",
                "rally_count": count,
                "remaining": target - count
            }

    def _cmd_add_rallies(self, args: dict) -> dict:
        """Add N more rallies to current target (target = current_count + N)."""
        count = args.get("count")
        if count is None:
            raise ValueError("Missing 'count' argument")
        count = int(count)

        arms_race = self.daemon.scheduler.get_arms_race_state()
        current_count = arms_race.get("beast_training_rally_count", 0)
        new_target = current_count + count

        self.daemon.scheduler.update_arms_race_state(beast_training_target_rallies=new_target)

        return {
            "rally_count": current_count,
            "added": count,
            "target": new_target,
            "remaining": count
        }

    def _cmd_get_rally_status(self, args: dict) -> dict:
        """Get current rally status for Beast Training with stamina projections."""
        from utils.arms_race import get_arms_race_status
        from utils.view_state_detector import detect_view, ViewState

        arms_race_status = get_arms_race_status()
        arms_race_state = self.daemon.scheduler.get_arms_race_state()

        count = arms_race_state.get("beast_training_rally_count", 0)
        target = arms_race_state.get("beast_training_target_rallies")
        next_target = arms_race_state.get("beast_training_next_target_rallies")

        # Use daemon's in-memory count if available (more up-to-date)
        if hasattr(self.daemon, 'beast_training_rally_count'):
            count = self.daemon.beast_training_rally_count

        event_remaining_mins = int(arms_race_status["time_remaining"].total_seconds() / 60)
        is_beast_training = arms_race_status["current"] == "Mystic Beast Training"

        # Get current stamina if in TOWN view
        current_stamina = None
        frame = self.daemon.windows_helper.get_screenshot_cv2()
        view_state, _ = detect_view(frame)
        if view_state == ViewState.TOWN:
            current_stamina = self.daemon.ocr_client.extract_number(
                frame, self.daemon.STAMINA_REGION
            )

        # Calculate stamina projections
        # Natural regen: 1 stamina per 6 minutes
        expected_natural_stamina = event_remaining_mins // 6 if is_beast_training else 0
        total_expected_stamina = (current_stamina or 0) + expected_natural_stamina
        rallies_possible_natural = total_expected_stamina // 20

        # Calculate shortfall for target (each rally costs 20 stamina)
        remaining_rallies = (target - count) if target else 0
        stamina_needed = remaining_rallies * 20
        stamina_shortfall = max(0, stamina_needed - total_expected_stamina) if current_stamina is not None else None

        return {
            "rally_count": count,
            "target": target,
            "remaining": (target - count) if target else None,
            "next_target": next_target,
            "current_event": arms_race_status["current"],
            "event_remaining_mins": event_remaining_mins,
            "is_beast_training": is_beast_training,
            # Stamina projections
            "current_stamina": current_stamina,
            "expected_natural_stamina": expected_natural_stamina,
            "total_expected_stamina": total_expected_stamina if current_stamina is not None else None,
            "rallies_possible_natural": rallies_possible_natural if current_stamina is not None else None,
            "stamina_needed": stamina_needed if target else None,
            "stamina_shortfall": stamina_shortfall,
        }
