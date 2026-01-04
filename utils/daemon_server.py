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
import time
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
            # Title commands
            "apply_title": self._cmd_apply_title,
            "list_titles": self._cmd_list_titles,
            # Zombie mode commands
            "set_zombie_mode": self._cmd_set_zombie_mode,
            "get_zombie_mode": self._cmd_get_zombie_mode,
            "clear_zombie_mode": self._cmd_clear_zombie_mode,
            # Flow with arguments
            "run_zombie_attack": self._cmd_run_zombie_attack,
            "faction_trial": self._cmd_faction_trial,
            # Stamina commands
            "use_stamina": self._cmd_use_stamina,
            "get_stamina_inventory": self._cmd_get_stamina_inventory,
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
        """Get current Arms Race status with real points from game UI.

        Returns what actually matters: points needed, rallies needed, stamina needed,
        and available stamina items.
        """
        from config import ZOMBIE_MODE_CONFIG
        from utils.arms_race import get_arms_race_status
        from utils.view_state_detector import detect_view, go_to_town, ViewState
        from scripts.flows.beast_training_flow import check_progress_quick
        from utils.stamina_popup_helper import get_inventory_snapshot

        arms_race_status = get_arms_race_status()

        # Get zombie mode for stamina/points calculations
        zombie_mode, zombie_expires = self.daemon.scheduler.get_zombie_mode()
        mode_config = ZOMBIE_MODE_CONFIG.get(zombie_mode, ZOMBIE_MODE_CONFIG["elite"])
        stamina_per_rally = mode_config["stamina"]
        points_per_rally = mode_config.get("points", 2000)

        event_remaining_mins = int(arms_race_status["time_remaining"].total_seconds() / 60)
        is_beast_training = arms_race_status["current"] == "Mystic Beast Training"

        # Check the game for current points
        current_points = None
        chest3_target = 30000
        points_remaining = None
        rallies_needed = None

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
            from utils.claude_cli_helper import calculate_optimal_stamina
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

    def _cmd_apply_title(self, args: dict) -> dict:
        """Apply a kingdom title. Requires being at marked Royal City."""
        from scripts.flows.go_to_mark_flow import go_to_mark_flow
        from scripts.flows.title_management_flow import title_management_flow, TITLE_DATA

        title_name = args.get("title")
        if not title_name:
            raise ValueError("Missing 'title' argument. Use list_titles to see available titles.")

        # Validate title exists
        titles = TITLE_DATA.get("titles", {})
        if title_name not in titles:
            raise ValueError(f"Unknown title: {title_name}. Available: {list(titles.keys())}")

        # Mark as critical flow to prevent daemon interference
        self.daemon.critical_flow_active = True
        self.daemon.critical_flow_name = "apply_title"

        try:
            # Step 1: Go to marked Royal City
            logger.info(f"Navigating to marked Royal City...")
            go_success = go_to_mark_flow(self.daemon.adb, debug=False)
            if not go_success:
                return {"success": False, "error": "Failed to navigate to marked Royal City"}

            # Step 2: Apply the title
            logger.info(f"Applying title: {title_name}")
            result = title_management_flow(
                self.daemon.adb,
                title_name,
                screenshot_helper=self.daemon.windows_helper,
                debug=False,
                return_to_base=True
            )

            title_info = titles[title_name]
            return {
                "success": result,
                "title": title_name,
                "display_name": title_info.get("display_name"),
                "buffs": title_info.get("buffs", [])
            }
        finally:
            # Always clear critical flow flag
            self.daemon.critical_flow_active = False
            self.daemon.critical_flow_name = None

    def _cmd_list_titles(self, args: dict) -> dict:
        """List available kingdom titles."""
        from scripts.flows.title_management_flow import TITLE_DATA

        titles = TITLE_DATA.get("titles", {})
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

    def _cmd_set_zombie_mode(self, args: dict) -> dict:
        """Set zombie mode for Beast Training (gold/food/iron_mine instead of elite)."""
        from config import ZOMBIE_MODE_CONFIG

        mode = args.get("mode", "gold")
        hours = args.get("hours", 24)

        if mode not in ZOMBIE_MODE_CONFIG:
            valid_modes = list(ZOMBIE_MODE_CONFIG.keys())
            raise ValueError(f"Invalid mode: {mode}. Valid modes: {valid_modes}")

        try:
            hours = float(hours)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid hours value: {hours}")

        expires = self.daemon.scheduler.set_zombie_mode(mode, hours)
        mode_config = ZOMBIE_MODE_CONFIG[mode]

        return {
            "mode": mode,
            "expires": expires.isoformat(),
            "hours": hours,
            "stamina_per_action": mode_config["stamina"],
            "points_per_action": mode_config["points"],
        }

    def _cmd_get_zombie_mode(self, args: dict) -> dict:
        """Get current zombie mode and expiry."""
        from config import ZOMBIE_MODE_CONFIG
        from datetime import datetime, timezone

        mode, expires = self.daemon.scheduler.get_zombie_mode()
        mode_config = ZOMBIE_MODE_CONFIG.get(mode, ZOMBIE_MODE_CONFIG["elite"])

        result = {
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

    def _cmd_clear_zombie_mode(self, args: dict) -> dict:
        """Clear zombie mode, revert to elite."""
        self.daemon.scheduler.clear_zombie_mode()
        return {
            "mode": "elite",
            "message": "Zombie mode cleared, reverted to elite zombie rallies"
        }

    # =========================================================================
    # Parameterized Flow Commands
    # =========================================================================

    def _cmd_run_zombie_attack(self, args: dict) -> dict:
        """
        Run zombie attack flow with custom parameters.

        Args:
            zombie_type: "gold", "food", or "iron_mine" (default: "gold")
            plus_clicks: Number of plus button clicks (default: 10)

        Example:
            {"cmd": "run_zombie_attack", "args": {"zombie_type": "gold", "plus_clicks": 10}}
        """
        from scripts.flows.zombie_attack_flow import zombie_attack_flow

        zombie_type = args.get("zombie_type", "gold")
        plus_clicks = args.get("plus_clicks", 5)

        # Validate zombie_type
        valid_types = ["gold", "food", "iron_mine"]
        if zombie_type not in valid_types:
            raise ValueError(f"Invalid zombie_type: {zombie_type}. Valid: {valid_types}")

        try:
            plus_clicks = int(plus_clicks)
        except (TypeError, ValueError):
            raise ValueError(f"Invalid plus_clicks value: {plus_clicks}")

        logger.info(f"Running zombie_attack_flow(zombie_type={zombie_type}, plus_clicks={plus_clicks})")

        # Mark as flow to prevent daemon interference
        flow_name = f"zombie_attack_{zombie_type}"
        self.daemon.critical_flow_active = False  # Not critical, but track it
        self.daemon.active_flows.add(flow_name)

        try:
            result = zombie_attack_flow(
                self.daemon.adb,
                zombie_type=zombie_type,
                plus_clicks=plus_clicks
            )
            return {
                "success": True,
                "zombie_type": zombie_type,
                "plus_clicks": plus_clicks,
                "result": result
            }
        except Exception as e:
            logger.error(f"zombie_attack_flow failed: {e}")
            return {
                "success": False,
                "zombie_type": zombie_type,
                "plus_clicks": plus_clicks,
                "error": str(e)
            }
        finally:
            self.daemon.active_flows.discard(flow_name)

    def _cmd_faction_trial(self, args: dict) -> dict:
        """
        Run the faction trials flow.

        Example:
            {"cmd": "faction_trial"}
        """
        from scripts.flows.faction_trials_flow import faction_trials_flow

        logger.info("Running faction_trials_flow")

        # Mark as flow to prevent daemon interference
        flow_name = "faction_trial"
        self.daemon.active_flows.add(flow_name)

        try:
            battles = faction_trials_flow(self.daemon.adb)
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

    def _cmd_use_stamina(self, args: dict) -> dict:
        """
        Use stamina items to replenish stamina.

        Args:
            claim_free_50: bool - Claim free 50 stamina if available (default: False)
            use_10_count: int - Number of 10-stamina items to use (default: 0)
            use_50_count: int - Number of 50-stamina items to use (default: 0)

        Example:
            {"cmd": "use_stamina", "args": {"claim_free_50": true, "use_10_count": 5}}
        """
        from utils.stamina_popup_helper import (
            open_stamina_popup,
            close_stamina_popup,
            claim_free_50,
            use_10_stamina,
            use_50_stamina,
            get_cooldown_seconds,
            get_owned_counts
        )

        claim_free = args.get("claim_free_50", False)
        use_10 = args.get("use_10_count", 0)
        use_50 = args.get("use_50_count", 0)

        try:
            use_10 = int(use_10)
            use_50 = int(use_50)
        except (TypeError, ValueError):
            raise ValueError("use_10_count and use_50_count must be integers")

        logger.info(f"Using stamina: claim_free={claim_free}, use_10={use_10}, use_50={use_50}")

        # Open the popup
        open_stamina_popup(self.daemon.adb)

        # Get current state before using
        frame = self.daemon.windows_helper.get_screenshot_cv2()
        owned_before = get_owned_counts(frame)
        cooldown_before = get_cooldown_seconds(frame)

        result = {
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

    def _cmd_get_stamina_inventory(self, args: dict) -> dict:
        """
        Get current stamina inventory without using any items.

        Returns owned counts and free 50 cooldown status.
        """
        from utils.stamina_popup_helper import get_inventory_snapshot

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
