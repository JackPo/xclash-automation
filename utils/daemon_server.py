"""
WebSocket server for daemon control.

Runs async in a background thread, accepts connections on ws://localhost:9876.
Enables external processes to trigger flows, check status, and receive push events.

Protocol: JSON messages
- Client -> Server: {"cmd": "run_flow", "args": {"flow": "tavern_quest"}}
- Server -> Client: {"type": "response", "cmd": "run_flow", "success": true, "data": {...}}
- Server -> Client: {"type": "event", "event": "flow_started", "data": {"flow": "tavern_quest"}}
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from datetime import datetime
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from websockets.legacy.server import WebSocketServerProtocol

_websockets_available = False
websockets: Any = None
ws_serve: Any = None

try:
    import websockets as _ws
    from websockets.server import serve as _serve
    websockets = _ws
    ws_serve = _serve
    _websockets_available = True
    # Silence websockets library spam (connection open/closed messages)
    logging.getLogger("websockets").setLevel(logging.WARNING)
    logging.getLogger("websockets.server").setLevel(logging.WARNING)
    logging.getLogger("websockets.protocol").setLevel(logging.WARNING)
except ImportError:
    pass

DEFAULT_PORT = 9876
logger = logging.getLogger("DaemonServer")


class DaemonWebSocketServer:
    """
    WebSocket server for daemon control.

    Runs in a background thread with its own asyncio event loop.
    Commands are processed synchronously by calling daemon methods.
    Events can be broadcast from the daemon thread to all connected clients.
    """

    def __init__(self, daemon: Any, port: int = DEFAULT_PORT) -> None:
        """
        Initialize the WebSocket server.

        Args:
            daemon: The IconDaemon instance to control
            port: Port to listen on (default 9876)
        """
        if not _websockets_available:
            raise ImportError("websockets library required: pip install websockets")

        self.daemon = daemon
        self.port = port
        self.clients: set[WebSocketServerProtocol] = set()
        self.loop: asyncio.AbstractEventLoop | None = None
        self.thread: threading.Thread | None = None
        self.running = False

    def start(self) -> None:
        """Start WebSocket server in background thread."""
        self.running = True
        self.thread = threading.Thread(target=self._run_server, daemon=True, name="DaemonWS")
        self.thread.start()
        logger.info(f"WebSocket server starting on ws://localhost:{self.port}")

    def stop(self) -> None:
        """Stop the WebSocket server."""
        self.running = False
        if self.loop:
            self.loop.call_soon_threadsafe(self.loop.stop)
        if self.thread:
            self.thread.join(timeout=2.0)
        logger.info("WebSocket server stopped")

    def _run_server(self) -> None:
        """Run async event loop in dedicated thread."""
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        try:
            self.loop.run_until_complete(self._serve())
        except Exception as e:
            logger.error(f"WebSocket server error: {e}")
        finally:
            self.loop.close()

    async def _serve(self) -> None:
        """Main server coroutine."""
        if ws_serve is None:
            return
        try:
            try:
                from config import API_BIND_HOST as _bind_host
            except Exception:
                _bind_host = "127.0.0.1"
            async with ws_serve(self._handle_client, _bind_host, self.port):
                logger.info(f"WebSocket server listening on ws://{_bind_host}:{self.port}")
                # Run until stopped
                while self.running:
                    await asyncio.sleep(0.5)
        except OSError as e:
            logger.error(f"Failed to start WebSocket server: {e}")

    async def _handle_client(self, websocket: WebSocketServerProtocol) -> None:
        """Handle a single WebSocket connection."""
        self.clients.add(websocket)
        client_count = len(self.clients)
        logger.debug(f"Client connected ({client_count} total)")

        try:
            async for message in websocket:
                try:
                    response = self._process_message(str(message))
                    await websocket.send(json.dumps(response))
                except Exception as e:
                    error_response: dict[str, Any] = {"type": "response", "success": False, "error": str(e)}
                    await websocket.send(json.dumps(error_response))
        except Exception as e:
            if websockets is not None and isinstance(e, websockets.ConnectionClosed):
                pass
            else:
                logger.error(f"Client handler error: {e}")
        finally:
            self.clients.discard(websocket)
            logger.debug(f"Client disconnected ({len(self.clients)} total)")

    def _process_message(self, message: str) -> dict[str, Any]:
        """
        Process incoming message and return response.

        Args:
            message: JSON string with {cmd, args}

        Returns:
            Response dict with {type, cmd, success, data/error}
        """
        data: dict[str, Any] = json.loads(message)
        cmd: str | None = data.get("cmd")
        args: dict[str, Any] = data.get("args", {})

        # Command dispatch table
        handlers = {
            "run_flow": self._cmd_run_flow,
            "status": self._cmd_status,
            "list_flows": self._cmd_list_flows,
            "get_state": self._cmd_get_state,
            "set_tavern_claims": self._cmd_set_tavern_claims,
            "mark_overlord_done": self._cmd_mark_overlord_done,
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
            # Title commands
            "apply_title": self._cmd_apply_title,
            "list_titles": self._cmd_list_titles,
            # Zombie mode commands
            "set_zombie_mode": self._cmd_set_zombie_mode,
            "get_zombie_mode": self._cmd_get_zombie_mode,
            "clear_zombie_mode": self._cmd_clear_zombie_mode,
            # Reinforce mode commands
            "start_reinforce": self._cmd_start_reinforce,
            "stop_reinforce": self._cmd_stop_reinforce,
            "get_reinforce_status": self._cmd_get_reinforce_status,
            # Steal sniper mode commands
            "start_sniper": self._cmd_start_sniper,
            "stop_sniper": self._cmd_stop_sniper,
            "get_sniper_status": self._cmd_get_sniper_status,
            # Flow with arguments
            "run_zombie_attack": self._cmd_run_zombie_attack,
            "run_elite_zombie": self._cmd_run_elite_zombie,
            "faction_trial": self._cmd_faction_trial,
            # Stamina commands
            "use_stamina": self._cmd_use_stamina,
            "get_stamina_inventory": self._cmd_get_stamina_inventory,
            # Shield inventory
            "get_shield_inventory": self._cmd_get_shield_inventory,
            "use_shield": self._cmd_use_shield,
            # Quick Production
            "mark_quick_production_done": self._cmd_mark_quick_production_done,
            # Config override commands
            "get_config": self._cmd_get_config,
            "set_override": self._cmd_set_override,
            "clear_override": self._cmd_clear_override,
            "list_overrides": self._cmd_list_overrides,
            # Debug commands
            "clear_active_flows": self._cmd_clear_active_flows,
        }

        if cmd is None:
            return {"type": "response", "cmd": cmd, "success": False, "error": "Missing 'cmd' field"}
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

    def broadcast(self, event: str, data: dict[str, Any]) -> None:
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

    async def _broadcast_async(self, message: str) -> None:
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

    def _cmd_run_flow(self, args: dict[str, Any]) -> dict[str, Any]:
        """Trigger a specific flow."""
        flow_name = args.get("flow")
        if not flow_name:
            raise ValueError("Missing 'flow' argument")
        result: dict[str, Any] = self.daemon.trigger_flow(flow_name)
        return result

    def _cmd_status(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get current daemon status."""
        result: dict[str, Any] = self.daemon.get_status()
        return result

    def _cmd_list_flows(self, args: dict[str, Any]) -> dict[str, Any]:
        """List available flows."""
        flows = self.daemon.get_available_flows()
        return {
            "flows": [
                {"name": name, "critical": critical}
                for name, (_, critical) in flows.items()
            ]
        }

    def _cmd_get_state(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get full daemon state."""
        result: dict[str, Any] = self.daemon.scheduler.get_daemon_state()
        return result

    def _cmd_set_tavern_claims(self, args: dict[str, Any]) -> dict[str, Any]:
        """Force-set today's tavern claims counter."""
        count_raw = args.get("count")
        if count_raw is None:
            raise ValueError("Missing 'count' argument")
        try:
            count = int(count_raw)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid count: {count_raw}")
        if count < 0:
            raise ValueError("count must be >= 0")

        self.daemon.scheduler.set_tavern_claims_today(count)
        self.broadcast("tavern_claims_set", {"count": count, "date": datetime.now().date().isoformat()})
        return {"tavern_claims_today": self.daemon.scheduler.get_tavern_claims_today()}

    def _cmd_set_config(self, args: dict[str, Any]) -> dict[str, Any]:
        """Dynamically update a config value."""
        key = args.get("key")
        value = args.get("value")
        if not key:
            raise ValueError("Missing 'key' argument")
        result: dict[str, Any] = self.daemon.set_config(key, value)
        return result

    def _cmd_pause(self, args: dict[str, Any]) -> dict[str, Any]:
        """Pause daemon main loop."""
        self.daemon.paused = True
        self.daemon.scheduler.update_daemon_state(paused=True)
        self.broadcast("paused", {"paused": True})
        return {"paused": True}

    def _cmd_resume(self, args: dict[str, Any]) -> dict[str, Any]:
        """Resume daemon main loop."""
        self.daemon.paused = False
        self.daemon.scheduler.update_daemon_state(paused=False)
        self.broadcast("resumed", {"paused": False})
        return {"paused": False}

    def _cmd_ping(self, args: dict[str, Any]) -> dict[str, Any]:
        """Health check."""
        return {
            "pong": True,
            "time": datetime.now().isoformat(),
            "clients": len(self.clients),
        }

    def _cmd_save_state(self, args: dict[str, Any]) -> dict[str, Any]:
        """Force save daemon state now."""
        self.daemon._save_runtime_state()
        return {"saved": True}

    def _cmd_mark_overlord_done(self, args: dict[str, Any]) -> dict[str, Any]:
        """Manually satisfy the overlord first-kill gate for this reset cycle
        (user already sent a team to a Lv190+ overlord by hand)."""
        level = int(args.get("level", 0) or 0)
        self.daemon.scheduler.mark_overlord_first_kill_done(level)
        return {"done": True, "level": level}

    def _cmd_read_stamina(self, args: dict[str, Any]) -> dict[str, Any]:
        """Read current stamina from screen (fresh OCR)."""
        from utils.view_state_detector import detect_view, ViewState
        from utils.current_state import update_stamina, update_view_state

        if self.daemon.windows_helper is None or self.daemon.ocr_client is None:
            raise RuntimeError("Daemon not initialized")

        frame = self.daemon.windows_helper.get_screenshot_cv2()

        # Check view state first
        view_state, view_score = detect_view(frame)

        # Persist view state
        update_view_state(view_state.name)

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

        # Persist stamina to state file
        if stamina is not None:
            update_stamina(stamina, view_state.name)

        return {
            "stamina": stamina,
            "view": view_state.name,
            "valid": stamina is not None and 0 <= stamina <= 200
        }

    def _cmd_return_to_base(self, args: dict[str, Any]) -> dict[str, Any]:
        """Navigate back to TOWN/WORLD view."""
        from utils.return_to_base_view import return_to_base_view

        if self.daemon.adb is None or self.daemon.windows_helper is None:
            raise RuntimeError("Daemon not initialized")

        success = return_to_base_view(
            self.daemon.adb,
            self.daemon.windows_helper,
            debug=bool(args.get("debug", False))
        )
        return {"success": success}

    def _cmd_get_view(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get current view state."""
        from utils.view_state_detector import detect_view

        if self.daemon.windows_helper is None:
            raise RuntimeError("Daemon not initialized")

        frame = self.daemon.windows_helper.get_screenshot_cv2()
        view_state, score = detect_view(frame)

        return {
            "view": view_state.name,
            "score": round(score, 4)
        }

    # =========================================================================
    # Rally Target Commands
    # =========================================================================

    def _cmd_set_rally_count(self, args: dict[str, Any]) -> dict[str, Any]:
        """Set the current rally count (e.g., 'I did 5 manually')."""
        count_val = args.get("count")
        if count_val is None:
            raise ValueError("Missing 'count' argument")
        count = int(count_val)

        self.daemon.scheduler.update_arms_race_state(beast_training_rally_count=count)
        self.daemon.beast_training_rally_count = count  # Update daemon's in-memory count

        arms_race = self.daemon.scheduler.get_arms_race_state()
        target: int | None = arms_race.get("beast_training_target_rallies")

        return {
            "rally_count": count,
            "target": target,
            "remaining": (target - count) if target else None
        }

    def _cmd_set_rally_target(self, args: dict[str, Any]) -> dict[str, Any]:
        """Set rally target for current or next Beast Training block."""
        target_val = args.get("target")
        if target_val is None:
            raise ValueError("Missing 'target' argument")
        target = int(target_val)

        next_block = args.get("next", False)

        if next_block:
            self.daemon.scheduler.update_arms_race_state(beast_training_next_target_rallies=target)
            return {"target": target, "block": "next"}
        else:
            self.daemon.scheduler.update_arms_race_state(beast_training_target_rallies=target)
            arms_race = self.daemon.scheduler.get_arms_race_state()
            count: int = arms_race.get("beast_training_rally_count", 0)
            return {
                "target": target,
                "block": "current",
                "rally_count": count,
                "remaining": target - count
            }

    def _cmd_add_rallies(self, args: dict[str, Any]) -> dict[str, Any]:
        """Add N more rallies to current target (target = current_count + N)."""
        count_val = args.get("count")
        if count_val is None:
            raise ValueError("Missing 'count' argument")
        count = int(count_val)

        arms_race = self.daemon.scheduler.get_arms_race_state()
        current_count: int = arms_race.get("beast_training_rally_count", 0)
        new_target = current_count + count

        self.daemon.scheduler.update_arms_race_state(beast_training_target_rallies=new_target)

        return {
            "rally_count": current_count,
            "added": count,
            "target": new_target,
            "remaining": count
        }

    def _cmd_get_rally_status(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get current Arms Race status with real points from game UI.

        Returns what actually matters: points needed, rallies needed, stamina needed,
        and available stamina items.
        """
        from config import ZOMBIE_MODE_CONFIG
        from utils.arms_race import get_arms_race_status
        from utils.view_state_detector import detect_view, go_to_town, ViewState
        from scripts.flows.beast_training_flow import check_progress_quick
        from scripts.flows.stamina_use_flow import get_inventory_snapshot

        if self.daemon.adb is None or self.daemon.windows_helper is None or self.daemon.ocr_client is None:
            raise RuntimeError("Daemon not initialized")

        arms_race_status = get_arms_race_status()

        # Get zombie mode for stamina/points calculations
        zombie_mode, zombie_expires = self.daemon.scheduler.get_zombie_mode()
        mode_config: dict[str, Any] = ZOMBIE_MODE_CONFIG.get(zombie_mode, ZOMBIE_MODE_CONFIG["elite"])
        stamina_per_rally: int = mode_config["stamina"]
        points_per_rally: int = mode_config.get("points", 2000)

        event_remaining_mins = int(arms_race_status["time_remaining"].total_seconds() / 60)
        is_beast_training = arms_race_status["current"] == "Mystic Beast Training"

        # Check the game for current points
        current_points: int | None = None
        chest3_target = 30000
        points_remaining: int | None = None
        rallies_needed: int | None = None

        if is_beast_training:
            try:
                progress = check_progress_quick(
                    self.daemon.adb,
                    self.daemon.windows_helper,
                    debug=False
                )
                if progress.get("success"):
                    current_points = progress.get("current_points")
                    if current_points is not None:
                        points_remaining = max(0, chest3_target - current_points)
                        rallies_needed = (points_remaining + points_per_rally - 1) // points_per_rally
            except Exception as e:
                logger.warning(f"Failed to check arms race progress: {e}")

        # Ensure we're in TOWN for stamina reading
        frame = self.daemon.windows_helper.get_screenshot_cv2()
        view_state, _ = detect_view(frame)
        if view_state != ViewState.TOWN:
            go_to_town(self.daemon.adb, debug=False)
            time.sleep(1.0)
            frame = self.daemon.windows_helper.get_screenshot_cv2()

        # Get current stamina
        current_stamina = self.daemon.ocr_client.extract_number(
            frame, self.daemon.STAMINA_REGION
        )

        # Get stamina inventory (opens popup, reads items, closes)
        inventory = get_inventory_snapshot(self.daemon.adb, self.daemon.windows_helper)
        owned_10 = inventory.get("owned_10", 0)
        owned_50 = inventory.get("owned_50", 0)
        free_50_cooldown = inventory.get("cooldown_secs", 0)
        free_50_available = free_50_cooldown == 0

        # Calculate total available stamina from items
        stamina_from_items = (owned_10 * 10) + (owned_50 * 50) + (50 if free_50_available else 0)
        total_stamina_available = (current_stamina or 0) + stamina_from_items

        # Calculate stamina needed and shortfall
        stamina_needed = rallies_needed * stamina_per_rally if rallies_needed else None
        stamina_shortfall = None
        if stamina_needed is not None:
            stamina_shortfall = max(0, stamina_needed - total_stamina_available)

        # Calculate stamina regeneration (1 per 5 mins)
        # Use stamina buffer (not time buffer) to ensure last rally can complete
        from config import STAMINA_REGEN_BUFFER
        stamina_regen_raw = event_remaining_mins // 5
        stamina_regen = max(0, stamina_regen_raw - STAMINA_REGEN_BUFFER)

        # Calculate optimal stamina usage strategy
        optimal_strategy = None
        if stamina_needed is not None and current_stamina is not None:
            from scripts.flows.stamina_use_flow import calculate_optimal_stamina
            # Account for natural regen when calculating deficit
            effective_stamina = current_stamina + stamina_regen
            deficit = max(0, stamina_needed - effective_stamina)
            if deficit > 0:
                claim_free, use_10s, use_50s, reasoning = calculate_optimal_stamina(
                    deficit, owned_10, owned_50, free_50_available
                )
                optimal_strategy = {
                    "claim_free_50": claim_free,
                    "use_10_count": use_10s,
                    "use_50_count": use_50s,
                    "stamina_gained": (50 if claim_free else 0) + use_10s * 10 + use_50s * 50,
                    "stamina_regen": stamina_regen,
                    "effective_stamina": effective_stamina,
                    "reasoning": reasoning
                }
            else:
                # No items needed - regen covers it
                optimal_strategy = {
                    "claim_free_50": False,
                    "use_10_count": 0,
                    "use_50_count": 0,
                    "stamina_gained": 0,
                    "stamina_regen": stamina_regen,
                    "effective_stamina": effective_stamina,
                    "reasoning": f"No items needed - {current_stamina} current + {stamina_regen} regen = {effective_stamina} covers {stamina_needed} needed"
                }

        result = {
            "current_event": arms_race_status["current"],
            "event_remaining_mins": event_remaining_mins,
            "is_beast_training": is_beast_training,
            # Points from game UI
            "current_points": current_points,
            "chest3_target": chest3_target,
            "points_remaining": points_remaining,
            # What you need to do
            "rallies_needed": rallies_needed,
            "stamina_per_rally": stamina_per_rally,
            "points_per_rally": points_per_rally,
            "stamina_needed": stamina_needed,
            # Current stamina
            "current_stamina": current_stamina,
            # Stamina items available
            "owned_10_stamina": owned_10,
            "owned_50_stamina": owned_50,
            "free_50_available": free_50_available,
            "free_50_cooldown_secs": free_50_cooldown,
            "stamina_from_items": stamina_from_items,
            "total_stamina_available": total_stamina_available,
            "stamina_shortfall": stamina_shortfall,
            # Optimal strategy
            "optimal_strategy": optimal_strategy,
            # Zombie mode
            "zombie_mode": zombie_mode,
        }

        if zombie_expires:
            from datetime import datetime, timezone
            remaining = (zombie_expires - datetime.now(timezone.utc)).total_seconds() / 3600
            result["zombie_expires"] = zombie_expires.isoformat()
            result["zombie_hours_remaining"] = round(remaining, 2)

        return result

    # =========================================================================
    # Title Commands
    # =========================================================================

    def _cmd_apply_title(self, args: dict[str, Any]) -> dict[str, Any]:
        """Apply a kingdom title. Requires being at marked Royal City."""
        from scripts.flows.title_management_flow import title_management_flow, TITLE_DATA

        if self.daemon.adb is None or self.daemon.windows_helper is None:
            raise RuntimeError("Daemon not initialized")

        title_name = args.get("title")
        if not title_name:
            raise ValueError("Missing 'title' argument. Use list_titles to see available titles.")

        # Validate title exists
        titles: dict[str, Any] = TITLE_DATA.get("titles", {})
        if title_name not in titles:
            raise ValueError(f"Unknown title: {title_name}. Available: {list(titles.keys())}")

        # Mark as critical flow to prevent daemon interference
        self.daemon.critical_flow_active = True
        self.daemon.critical_flow_name = "apply_title"

        try:
            # title_management_flow handles navigation to marked Royal City internally.
            logger.info(f"Applying title: {title_name}")
            flow_result: bool = title_management_flow(
                self.daemon.adb,
                title_name,
                screenshot_helper=self.daemon.windows_helper,
                debug=False,
                return_to_base=True
            )

            title_info: dict[str, Any] = titles[title_name]
            return {
                "success": flow_result,
                "title": title_name,
                "display_name": title_info.get("display_name"),
                "buffs": title_info.get("buffs", [])
            }
        finally:
            # Always clear critical flow flag
            self.daemon.critical_flow_active = False
            self.daemon.critical_flow_name = None

    def _cmd_list_titles(self, args: dict[str, Any]) -> dict[str, Any]:
        """List available kingdom titles."""
        from scripts.flows.title_management_flow import TITLE_DATA

        titles: dict[str, Any] = TITLE_DATA.get("titles", {})
        return {
            "titles": [
                {
                    "name": name,
                    "display_name": info.get("display_name"),
                    "buffs": [f"{b['name']} {b['value']}" for b in info.get("buffs", [])]
                }
                for name, info in titles.items()
            ]
        }

    # =========================================================================
    # Zombie Mode Commands
    # =========================================================================

    def _cmd_set_zombie_mode(self, args: dict[str, Any]) -> dict[str, Any]:
        """Set zombie mode for Beast Training (gold/food/iron_mine instead of elite)."""
        from config import ZOMBIE_MODE_CONFIG
        from utils.current_state import update_zombie_mode

        mode = args.get("mode", "gold")
        hours_val = args.get("hours", 24)

        if mode not in ZOMBIE_MODE_CONFIG:
            valid_modes = list(ZOMBIE_MODE_CONFIG.keys())
            raise ValueError(f"Invalid mode: {mode}. Valid modes: {valid_modes}")

        try:
            hours = float(hours_val)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid hours value: {hours_val}")

        expires = self.daemon.scheduler.set_zombie_mode(mode, hours)
        mode_config: dict[str, Any] = ZOMBIE_MODE_CONFIG[mode]

        # Persist to state file
        update_zombie_mode(mode, expires.isoformat())

        return {
            "mode": mode,
            "expires": expires.isoformat(),
            "hours": hours,
            "stamina_per_action": mode_config["stamina"],
            "points_per_action": mode_config["points"],
        }

    def _cmd_get_zombie_mode(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get current zombie mode and expiry."""
        from config import ZOMBIE_MODE_CONFIG
        from datetime import timezone

        mode, expires = self.daemon.scheduler.get_zombie_mode()
        mode_config: dict[str, Any] = ZOMBIE_MODE_CONFIG.get(mode, ZOMBIE_MODE_CONFIG["elite"])

        result: dict[str, Any] = {
            "mode": mode,
            "stamina_per_action": mode_config["stamina"],
            "points_per_action": mode_config["points"],
        }

        if expires:
            now = datetime.now(timezone.utc)
            remaining = (expires - now).total_seconds() / 3600
            result["expires"] = expires.isoformat()
            result["hours_remaining"] = round(remaining, 2)

        return result

    def _cmd_clear_zombie_mode(self, args: dict[str, Any]) -> dict[str, Any]:
        """Clear zombie mode, revert to elite."""
        self.daemon.scheduler.clear_zombie_mode()
        return {
            "mode": "elite",
            "message": "Zombie mode cleared, reverted to elite zombie rallies"
        }

    # =========================================================================
    # Reinforce Mode Commands (loop reinforce camp, block other flows)
    # =========================================================================

    def _cmd_start_reinforce(self, args: dict[str, Any]) -> dict[str, Any]:
        """Start reinforce loop mode. Blocks other flows except handshake."""
        hours = args.get("hours")  # None = until manually stopped
        interval = args.get("interval", 10)  # Seconds between runs, default 10

        expires = self.daemon.scheduler.set_reinforce_mode(hours)

        # Store interval in daemon state
        self.daemon.reinforce_interval = interval

        result: dict[str, Any] = {
            "active": True,
            "interval": interval,
            "message": f"Reinforce loop started (interval: {interval}s)"
        }

        if expires:
            result["expires"] = expires.isoformat()
            result["hours"] = hours

        return result

    def _cmd_stop_reinforce(self, args: dict[str, Any]) -> dict[str, Any]:
        """Stop reinforce loop mode."""
        import traceback
        logger.warning(f"STOP_REINFORCE called! Stack trace:\n{''.join(traceback.format_stack())}")
        self.daemon.scheduler.clear_reinforce_mode()
        self.daemon.reinforce_interval = None
        return {
            "active": False,
            "message": "Reinforce loop stopped"
        }

    def _cmd_get_reinforce_status(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get current reinforce mode status."""
        active, expires = self.daemon.scheduler.get_reinforce_mode()
        interval = getattr(self.daemon, 'reinforce_interval', 10)

        result: dict[str, Any] = {
            "active": active,
            "interval": interval,
        }

        if expires:
            from datetime import timezone
            now = datetime.now(timezone.utc)
            remaining = (expires - now).total_seconds() / 3600
            result["expires"] = expires.isoformat()
            result["hours_remaining"] = round(remaining, 2)

        return result

    # =========================================================================
    # Steal Sniper Mode Commands
    # =========================================================================

    def _cmd_start_sniper(self, args: dict[str, Any]) -> dict[str, Any]:
        """Start tavern steal sniper mode. Blocks all flows except tavern quests."""
        hours = args.get("hours")  # None = until manually stopped

        expires = self.daemon.scheduler.set_sniper_mode(hours)

        result: dict[str, Any] = {
            "active": True,
            "message": "Steal sniper armed - scanning for steal button",
        }
        if expires:
            result["expires"] = expires.isoformat()
            result["hours"] = hours
        return result

    def _cmd_stop_sniper(self, args: dict[str, Any]) -> dict[str, Any]:
        """Stop tavern steal sniper mode."""
        self.daemon.scheduler.clear_sniper_mode()
        from scripts.flows.tavern_steal_sniper_flow import reset_sniper_status
        reset_sniper_status()
        return {
            "active": False,
            "message": "Steal sniper disarmed",
        }

    def _cmd_get_sniper_status(self, args: dict[str, Any]) -> dict[str, Any]:
        """Get steal sniper mode status including lock state and countdown."""
        active, expires = self.daemon.scheduler.get_sniper_mode()

        from scripts.flows.tavern_steal_sniper_flow import get_sniper_status
        result: dict[str, Any] = {"active": active}
        result.update(get_sniper_status())
        if not active:
            result["state"] = "idle"

        if expires:
            from datetime import timezone
            now = datetime.now(timezone.utc)
            result["expires"] = expires.isoformat()
            result["hours_remaining"] = round((expires - now).total_seconds() / 3600, 2)
        return result

    # =========================================================================
    # Parameterized Flow Commands
    # =========================================================================

    def _cmd_run_zombie_attack(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Run zombie attack flow with custom parameters.

        Args:
            zombie_type: "gold", "food", or "iron_mine" (default: "gold")
            level_clicks: Signed int for level adjustment (+N = plus, -N = minus)
            target_level: Target level (1-50). Uses OCR to read current level and adjust.
                          Takes precedence over level_clicks if provided.

        Example:
            {"cmd": "run_zombie_attack", "args": {"zombie_type": "gold", "level_clicks": -2}}
            {"cmd": "run_zombie_attack", "args": {"zombie_type": "gold", "target_level": 25}}
        """
        from scripts.flows.zombie_attack_flow import zombie_attack_flow

        if self.daemon.adb is None:
            raise RuntimeError("Daemon not initialized")

        zombie_type: str = args.get("zombie_type", "gold")
        level_clicks_val = args.get("level_clicks", args.get("plus_clicks", 0))  # backward compat
        target_level_val = args.get("target_level")

        # Validate zombie_type
        valid_types = ["gold", "food", "iron_mine"]
        if zombie_type not in valid_types:
            raise ValueError(f"Invalid zombie_type: {zombie_type}. Valid: {valid_types}")

        # Parse level_clicks
        try:
            level_clicks = int(level_clicks_val)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid level_clicks value: {level_clicks_val}")

        # Parse target_level (optional)
        target_level: int | None = None
        if target_level_val is not None:
            try:
                target_level = int(target_level_val)
                if not (1 <= target_level <= 50):
                    raise ValueError(f"target_level must be 1-50, got: {target_level}")
            except (TypeError, ValueError) as e:
                raise ValueError(f"Invalid target_level value: {target_level_val}") from e

        level_str = f"target_level={target_level}" if target_level else f"level_clicks={level_clicks}"
        logger.info(f"Running zombie_attack_flow(zombie_type={zombie_type}, {level_str})")

        # Mark as flow to prevent daemon interference
        flow_name = f"zombie_attack_{zombie_type}"
        self.daemon.critical_flow_active = False  # Not critical, but track it
        self.daemon.active_flows.add(flow_name)

        try:
            flow_result: bool = zombie_attack_flow(
                self.daemon.adb,
                zombie_type=zombie_type,
                level_clicks=level_clicks,
                target_level=target_level
            )
            result: dict[str, Any] = {
                "success": True,
                "zombie_type": zombie_type,
                "result": flow_result
            }
            if target_level is not None:
                result["target_level"] = target_level
            else:
                result["level_clicks"] = level_clicks
            return result
        except Exception as e:
            logger.error(f"zombie_attack_flow failed: {e}")
            result = {
                "success": False,
                "zombie_type": zombie_type,
                "error": str(e)
            }
            if target_level is not None:
                result["target_level"] = target_level
            else:
                result["level_clicks"] = level_clicks
            return result
        finally:
            self.daemon.active_flows.discard(flow_name)

    def _cmd_run_elite_zombie(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Run elite zombie flow with custom parameters.

        Args:
            level_clicks: Signed int for level adjustment (+N = plus, -N = minus).
                          If None, uses config default.
            target_level: Target level (1-50). Uses OCR to read current level and adjust.
                          Takes precedence over level_clicks if provided.

        Example:
            {"cmd": "run_elite_zombie", "args": {"level_clicks": -2}}
            {"cmd": "run_elite_zombie", "args": {"target_level": 41}}
        """
        from scripts.flows.elite_zombie_flow import elite_zombie_flow

        if self.daemon.adb is None:
            raise RuntimeError("Daemon not initialized")

        level_clicks_val = args.get("level_clicks")
        target_level_val = args.get("target_level")

        # Parse level_clicks (optional)
        level_clicks: int | None = None
        if level_clicks_val is not None:
            try:
                level_clicks = int(level_clicks_val)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid level_clicks value: {level_clicks_val}")

        # Parse target_level (optional)
        target_level: int | None = None
        if target_level_val is not None:
            try:
                target_level = int(target_level_val)
                if not (1 <= target_level <= 50):
                    raise ValueError(f"target_level must be 1-50, got: {target_level}")
            except (TypeError, ValueError) as e:
                raise ValueError(f"Invalid target_level value: {target_level_val}") from e

        if target_level is not None:
            level_str = f"target_level={target_level}"
        elif level_clicks is not None:
            level_str = f"level_clicks={level_clicks}"
        else:
            level_str = "using config default"
        logger.info(f"Running elite_zombie_flow({level_str})")

        # Mark as flow to prevent daemon interference
        flow_name = "elite_zombie"
        self.daemon.active_flows.add(flow_name)

        try:
            flow_result: bool = elite_zombie_flow(
                self.daemon.adb,
                level_clicks=level_clicks,
                target_level=target_level
            )
            result: dict[str, Any] = {
                "success": True,
                "result": flow_result
            }
            if target_level is not None:
                result["target_level"] = target_level
            elif level_clicks is not None:
                result["level_clicks"] = level_clicks
            return result
        except Exception as e:
            logger.error(f"elite_zombie_flow failed: {e}")
            result = {
                "success": False,
                "error": str(e)
            }
            if target_level is not None:
                result["target_level"] = target_level
            elif level_clicks is not None:
                result["level_clicks"] = level_clicks
            return result
        finally:
            self.daemon.active_flows.discard(flow_name)

    def _cmd_faction_trial(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Run the faction trials flow.

        Example:
            {"cmd": "faction_trial"}
        """
        from scripts.flows.faction_trials_flow import faction_trials_flow

        if self.daemon.adb is None:
            raise RuntimeError("Daemon not initialized")

        logger.info("Running faction_trials_flow")

        # Mark as flow to prevent daemon interference
        flow_name = "faction_trial"
        self.daemon.active_flows.add(flow_name)

        try:
            battles: int = faction_trials_flow(self.daemon.adb)
            return {
                "success": True,
                "battles_completed": battles
            }
        except Exception as e:
            logger.error(f"faction_trials_flow failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
        finally:
            self.daemon.active_flows.discard(flow_name)

    # =========================================================================
    # Stamina Commands
    # =========================================================================

    def _cmd_use_stamina(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Use stamina items to replenish stamina.

        Args:
            claim_free_50: bool - Claim free 50 stamina if available (default: False)
            use_10_count: int - Number of 10-stamina items to use (default: 0)
            use_50_count: int - Number of 50-stamina items to use (default: 0)

        Example:
            {"cmd": "use_stamina", "args": {"claim_free_50": true, "use_10_count": 5}}
        """
        from scripts.flows.stamina_use_flow import (
            open_stamina_popup,
            close_stamina_popup,
            claim_free_50,
            use_10_stamina,
            use_50_stamina,
            get_cooldown_seconds,
            get_owned_counts
        )

        if self.daemon.adb is None or self.daemon.windows_helper is None:
            raise RuntimeError("Daemon not initialized")

        claim_free = args.get("claim_free_50", False)
        use_10_val = args.get("use_10_count", 0)
        use_50_val = args.get("use_50_count", 0)

        try:
            use_10 = int(use_10_val)
            use_50 = int(use_50_val)
        except (TypeError, ValueError):
            raise ValueError("use_10_count and use_50_count must be integers")

        logger.info(f"Using stamina: claim_free={claim_free}, use_10={use_10}, use_50={use_50}")

        # Open the popup
        open_stamina_popup(self.daemon.adb)

        # Get current state before using
        frame = self.daemon.windows_helper.get_screenshot_cv2()
        owned_before = get_owned_counts(frame)
        cooldown_before = get_cooldown_seconds(frame)

        result: dict[str, Any] = {
            "claimed_free_50": False,
            "used_10": 0,
            "used_50": 0,
            "owned_10_before": owned_before["owned_10"],
            "owned_50_before": owned_before["owned_50"],
        }

        # Claim free 50 if requested and available
        if claim_free and cooldown_before == 0:
            claim_free_50(self.daemon.adb)
            result["claimed_free_50"] = True
            logger.info("Claimed free 50 stamina")

        # Use 10-stamina items
        if use_10 > 0:
            actual_use = min(use_10, owned_before["owned_10"])
            if actual_use > 0:
                use_10_stamina(self.daemon.adb, actual_use)
                result["used_10"] = actual_use
                logger.info(f"Used {actual_use} x 10-stamina items")

        # Use 50-stamina items
        if use_50 > 0:
            actual_use = min(use_50, owned_before["owned_50"])
            if actual_use > 0:
                use_50_stamina(self.daemon.adb, actual_use)
                result["used_50"] = actual_use
                logger.info(f"Used {actual_use} x 50-stamina items")

        # Close popup
        close_stamina_popup(self.daemon.adb)

        # Calculate total stamina gained
        stamina_gained = (
            (50 if result["claimed_free_50"] else 0) +
            (result["used_10"] * 10) +
            (result["used_50"] * 50)
        )
        result["stamina_gained"] = stamina_gained

        return result

    def _cmd_get_stamina_inventory(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Get current stamina inventory without using any items.

        Returns owned counts and free 50 cooldown status.
        """
        from scripts.flows.stamina_use_flow import get_inventory_snapshot

        if self.daemon.adb is None or self.daemon.windows_helper is None:
            raise RuntimeError("Daemon not initialized")

        inventory = get_inventory_snapshot(self.daemon.adb, self.daemon.windows_helper)

        return {
            "owned_10": inventory["owned_10"],
            "owned_50": inventory["owned_50"],
            "free_50_available": inventory["cooldown_secs"] == 0,
            "free_50_cooldown_secs": inventory["cooldown_secs"],
            "total_stamina_available": (
                inventory["owned_10"] * 10 +
                inventory["owned_50"] * 50 +
                (50 if inventory["cooldown_secs"] == 0 else 0)
            )
        }

    def _cmd_get_shield_inventory(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Read shield inventory from bag Special tab.

        Opens bag, navigates to Special tab, matches shield templates,
        and extracts counts via OCR.

        Returns:
            {"8hr": N, "12hr": N, "24hr": N} - counts for each shield type
        """
        from scripts.flows.shield_inventory_flow import shield_inventory_flow

        if self.daemon.adb is None or self.daemon.windows_helper is None:
            raise RuntimeError("Daemon not initialized")

        debug = args.get("debug", False)
        result = shield_inventory_flow(
            self.daemon.adb,
            self.daemon.windows_helper,
            debug=debug
        )

        return {
            "shields": result,
            "8hr": result.get("8hr"),
            "12hr": result.get("12hr"),
            "24hr": result.get("24hr"),
        }

    def _cmd_use_shield(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Use/activate a shield from the bag.

        Args:
            shield_type: "8hr", "12hr", or "24hr"
            debug: Enable debug output (optional)
            force: Use shield even if one is already active (optional)

        Returns:
            {"success": True/False, "message": str}
        """
        from scripts.flows.shield_use_flow import shield_use_flow

        if self.daemon.adb is None or self.daemon.windows_helper is None:
            raise RuntimeError("Daemon not initialized")

        shield_type = args.get("shield_type")
        if not shield_type:
            raise ValueError("Missing 'shield_type' argument")
        if shield_type not in ["8hr", "12hr", "24hr"]:
            raise ValueError(f"Invalid shield_type: {shield_type}")

        debug = args.get("debug", False)
        force = args.get("force", False)
        result = shield_use_flow(
            self.daemon.adb,
            shield_type,
            self.daemon.windows_helper,
            debug=debug,
            force=force
        )

        return result

    # =========================================================================
    # Quick Production
    # =========================================================================

    def _cmd_mark_quick_production_done(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Mark Quick Production as done. Stops the daemon from retrying.

        Args:
            verify_ocr: bool (default True). If True, navigate to the Class
                        Skill panel and OCR the actual cooldown timer. If
                        False (or on OCR failure), fall back to a 24h cooldown.

        Returns dict:
            {
              "next_run_iso": str,
              "remaining_seconds": int,
              "source": "ocr" | "default_24h",
              "raw_text": str | None,
              "reason": str | None,    # set if OCR fell back
            }
        """
        from scripts.flows.quick_production_flow import verify_quick_production_cooldown_flow
        from datetime import datetime, timedelta

        if self.daemon.adb is None or self.daemon.windows_helper is None:
            raise RuntimeError("Daemon not initialized")

        verify_ocr = bool(args.get("verify_ocr", True))
        debug = bool(args.get("debug", False))

        DEFAULT_REMAINING = 86400  # 24h
        source = "default_24h"
        remaining: int = DEFAULT_REMAINING
        raw_text: str | None = None
        fallback_reason: str | None = None

        if verify_ocr:
            result = verify_quick_production_cooldown_flow(
                self.daemon.adb, self.daemon.windows_helper, debug=debug
            )
            raw_text = result.get("raw_text")
            if result.get("ok") and result.get("remaining_seconds") is not None:
                remaining = int(result["remaining_seconds"])
                source = "ocr"
                # If OCR reports 0 (available now) we still want to suppress
                # the retry storm for at least a short window -- the user just
                # told us they did it manually, so trust that over an OCR
                # blip that might have read 0 in error.
                if remaining < 60:
                    remaining = DEFAULT_REMAINING
                    source = "default_24h"
                    fallback_reason = f"OCR said available-now but user marked done; defaulting to 24h"
            else:
                fallback_reason = result.get("reason") or "OCR failed"

        # record_flow_run with cooldown_override backdates last_run so that
        # next_ready = now + remaining
        self.daemon.scheduler.record_flow_run("quick_production", cooldown_override=remaining)

        next_run = (datetime.now() + timedelta(seconds=remaining)).isoformat()
        return {
            "next_run_iso": next_run,
            "remaining_seconds": remaining,
            "source": source,
            "raw_text": raw_text,
            "reason": fallback_reason,
        }

    # =========================================================================
    # Config Override Commands
    # =========================================================================

    def _cmd_get_config(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Get all config definitions with current values and override status.

        Returns dict of all configs with:
        - value: Current effective value
        - default: Default value
        - overridden: Whether an override is active
        - expires_in: Seconds until override expires (or None)
        - type, min, max, category, description
        """
        from utils.config_overrides import get_override_manager

        manager = get_override_manager()
        return {"configs": manager.get_all_configs()}

    def _cmd_set_override(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Set a config override with optional duration.

        Args:
            key: Config key to override (e.g., "RALLY_JOIN_ENABLED")
            value: New value
            duration_minutes: Minutes until expiry (None = permanent)

        Example:
            {"cmd": "set_override", "args": {"key": "RALLY_JOIN_ENABLED", "value": true, "duration_minutes": 120}}
        """
        from utils.config_overrides import get_override_manager, CONFIG_DEFINITIONS

        key = args.get("key")
        value = args.get("value")
        duration_val = args.get("duration_minutes")

        if not key:
            raise ValueError("Missing 'key' argument")
        if value is None:
            raise ValueError("Missing 'value' argument")

        # Validate key exists
        if key not in CONFIG_DEFINITIONS:
            raise ValueError(f"Unknown config key: {key}. Valid keys: {list(CONFIG_DEFINITIONS.keys())}")

        # Parse duration
        duration_minutes = None
        if duration_val is not None:
            try:
                duration_minutes = int(duration_val)
            except (TypeError, ValueError):
                raise ValueError(f"Invalid duration_minutes: {duration_val}")

        manager = get_override_manager()
        result = manager.set_override(key, value, duration_minutes)

        logger.info(f"Config override set: {key}={value} for {duration_minutes} minutes")
        self.broadcast("config_override", {"key": key, "value": value, "duration_minutes": duration_minutes})

        return result

    def _cmd_clear_override(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Clear a config override, reverting to default.

        Args:
            key: Config key to clear

        Example:
            {"cmd": "clear_override", "args": {"key": "RALLY_JOIN_ENABLED"}}
        """
        from utils.config_overrides import get_override_manager

        key = args.get("key")
        if not key:
            raise ValueError("Missing 'key' argument")

        manager = get_override_manager()
        result = manager.clear_override(key)

        logger.info(f"Config override cleared: {key}")
        self.broadcast("config_override_cleared", {"key": key})

        return result

    def _cmd_list_overrides(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Get all currently active overrides with time remaining.

        Returns dict of active overrides (keys that are currently overridden).
        """
        from utils.config_overrides import get_override_manager

        manager = get_override_manager()
        return {"overrides": manager.get_active_overrides()}

    def _cmd_clear_active_flows(self, args: dict[str, Any]) -> dict[str, Any]:
        """
        Clear stuck active_flows set. Use when a flow crashed without cleanup.

        Example:
            {"cmd": "clear_active_flows"}
        """
        old_flows = list(self.daemon.active_flows)
        self.daemon.active_flows.clear()
        logger.warning(f"Cleared stuck active_flows: {old_flows}")
        self.broadcast("active_flows_cleared", {"cleared": old_flows})
        return {"cleared": old_flows}
