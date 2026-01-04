"""
Mastermind Dashboard - FastAPI server for xclash automation control.

Provides REST API endpoints and serves static frontend.
Auto-detects available port on startup.
"""
from __future__ import annotations

import asyncio
import json
import socket
import threading
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# Add project root to path
import sys
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils.arms_race import get_arms_race_status, SCHEDULE, VALID_EVENTS
from utils.scheduler import get_scheduler

# Global reference to daemon instance (set by icon_daemon.py on startup)
_daemon_instance: Any = None
_dashboard_port: int | None = None


def set_daemon_instance(daemon: Any) -> None:
    """Called by icon_daemon.py to share daemon instance."""
    global _daemon_instance
    _daemon_instance = daemon


def get_dashboard_port() -> int | None:
    """Get the port dashboard is running on."""
    return _dashboard_port


# ============================================================================
# Pydantic Models
# ============================================================================

class FlowRunRequest(BaseModel):
    """Request to run a flow."""
    pass  # No body needed, flow name is in URL


class StatusResponse(BaseModel):
    """Daemon status response."""
    paused: bool
    active_flows: list[str]
    critical_flow: str | None
    stamina: int | None
    idle_seconds: float
    view: str | None
    timestamp: str


class ArmsRaceResponse(BaseModel):
    """Arms Race status response."""
    current_event: str
    previous_event: str
    next_event: str
    day: int
    time_remaining_seconds: float
    time_elapsed_seconds: float
    block_start: str
    block_end: str


class FlowInfo(BaseModel):
    """Flow information."""
    name: str
    critical: bool
    last_run: str | None
    running: bool


# ============================================================================
# Helper Functions
# ============================================================================

def find_free_port() -> int:
    """Find a free port to bind to."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        s.listen(1)
        port = s.getsockname()[1]
    return port


async def get_daemon_status_via_ws() -> dict[str, Any]:
    """Get daemon status via WebSocket connection."""
    import websockets
    import json

    try:
        async with websockets.connect('ws://localhost:9876', close_timeout=2) as ws:
            await ws.send(json.dumps({'cmd': 'status'}))
            response = json.loads(await ws.recv())
            if response.get('success'):
                data = response.get('data', {})
                return {
                    "paused": data.get('paused', False),
                    "active_flows": data.get('active_flows', []),
                    "critical_flow": data.get('critical_flow'),
                    "stamina": data.get('stamina'),
                    "idle_seconds": data.get('idle_seconds', 0),
                    "view": data.get('view'),
                }
    except Exception as e:
        print(f"[DASHBOARD] WebSocket error: {e}")

    return {
        "paused": False,
        "active_flows": [],
        "critical_flow": None,
        "stamina": None,
        "idle_seconds": 0,
        "view": None,
        "error": "Daemon not connected",
    }


async def get_flows_list_async() -> list[dict[str, Any]]:
    """Get list of all flows with their status via daemon WebSocket."""
    # Flow definitions with criticality
    # NOTE: Flows that require arguments (title_management, go_to_mark) are NOT included
    # Those are handled via separate API commands (apply_title, list_titles, etc.)
    FLOWS = [
        ("tavern_quest", True),
        ("bag_flow", True),
        ("treasure_map", True),
        ("gift_box", True),
        ("hero_upgrade", True),
        ("soldier_training", True),
        ("soldier_upgrade", True),
        ("faction_trials", True),
        ("union_gifts", False),
        ("union_technology", False),
        ("afk_rewards", False),
        ("healing", False),
        ("elite_zombie", False),
        ("handshake", False),
        ("corn_harvest", False),
        ("gold_coin", False),
        ("iron_bar", False),
        ("gem", False),
        ("cabbage", False),
        ("equipment", False),
        ("harvest_box", False),
        ("stamina_claim", False),
        ("arms_race_check", False),
    ]

    # Get active flows from daemon
    active_flows = set()
    status = await get_daemon_status_via_ws()
    if status.get('active_flows'):
        active_flows = set(status['active_flows'])

    scheduler = get_scheduler()

    flows = []
    for name, critical in FLOWS:
        # Get last run time from scheduler
        last_run = None
        flow_state = scheduler.schedule.get('flows', {}).get(name, {})
        if flow_state.get('last_run'):
            last_run = flow_state['last_run']

        flows.append({
            "name": name,
            "critical": critical,
            "last_run": last_run,
            "running": name in active_flows,
        })

    return flows


# ============================================================================
# FastAPI App
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    print(f"[DASHBOARD] Starting on port {_dashboard_port}")
    yield
    print("[DASHBOARD] Shutting down")


app = FastAPI(
    title="xclash Mastermind Dashboard",
    description="Control panel for xclash automation",
    lifespan=lifespan,
)

# Mount static files
STATIC_DIR = Path(__file__).parent / "static"
if STATIC_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


# ============================================================================
# API Endpoints
# ============================================================================

@app.get("/")
async def root() -> HTMLResponse:
    """Serve the dashboard HTML."""
    index_path = STATIC_DIR / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text(encoding='utf-8'))
    return HTMLResponse(content="<h1>Dashboard not found</h1><p>index.html missing</p>")


@app.get("/api/status")
async def api_status() -> dict[str, Any]:
    """Get current daemon status via WebSocket to daemon."""
    status = await get_daemon_status_via_ws()
    status["timestamp"] = datetime.now(timezone.utc).isoformat()
    return status


@app.get("/api/arms-race")
async def api_arms_race() -> dict[str, Any]:
    """Get Arms Race status."""
    status = get_arms_race_status()
    return {
        "current_event": status["current"],
        "previous_event": status["previous"],
        "next_event": status["next"],
        "day": status["day"],
        "time_remaining_seconds": status["time_remaining"].total_seconds(),
        "time_elapsed_seconds": status["time_elapsed"].total_seconds(),
        "block_start": status["block_start"].isoformat(),
        "block_end": status["block_end"].isoformat(),
    }


@app.post("/api/arms-race/check-score")
async def api_check_arms_race_score() -> dict[str, Any]:
    """Check current Arms Race score by triggering the flow."""
    import websockets

    try:
        # Longer timeout for flow execution (180s like daemon_cli)
        async with websockets.connect('ws://localhost:9876', close_timeout=180) as ws:
            await ws.send(json.dumps({'cmd': 'run_flow', 'args': {'flow': 'arms_race_check'}}))
            response = json.loads(await asyncio.wait_for(ws.recv(), timeout=180))

            if response.get('success'):
                # Flow result is in data.result (the dict returned by check_arms_race_progress)
                result = response.get('data', {}).get('result', {})
                return {
                    "success": True,
                    "current_points": result.get('current_points'),
                    "chest3_target": result.get('chest3_target'),
                    "points_to_chest3": result.get('points_to_chest3'),
                    "detected_event": result.get('detected_event'),
                }
            return {"success": False, "error": response.get('error', 'Failed to check score')}
    except asyncio.TimeoutError:
        return {"success": False, "error": "Timeout - flow took too long"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/arms-race/schedule")
async def api_arms_race_schedule() -> dict[str, Any]:
    """Get full 7-day Arms Race schedule."""
    # Build schedule with timing info
    current_status = get_arms_race_status()
    current_index = current_status.get("event_index", 0)

    events = []
    for i, (day, event_name) in enumerate(SCHEDULE):
        events.append({
            "index": i,
            "day": day,
            "event": event_name,
            "is_current": i == current_index,
        })

    return {
        "schedule": events,
        "current_index": current_index,
        "cycle_day": current_status["day"],
    }


@app.get("/api/flows")
async def api_flows() -> list[dict[str, Any]]:
    """Get list of all flows."""
    return await get_flows_list_async()


async def send_daemon_command(cmd: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    """Send command to daemon via WebSocket."""
    import websockets
    import json

    try:
        async with websockets.connect('ws://localhost:9876', close_timeout=5) as ws:
            msg = {'cmd': cmd}
            if args:
                msg['args'] = args
            await ws.send(json.dumps(msg))
            response = json.loads(await ws.recv())
            return response
    except Exception as e:
        return {'success': False, 'error': str(e)}


@app.post("/api/flows/{flow_name}/run")
async def api_run_flow(flow_name: str) -> dict[str, Any]:
    """Trigger a flow to run via daemon WebSocket."""
    response = await send_daemon_command('run_flow', {'flow': flow_name})
    if response.get('success'):
        return {"success": True, "flow": flow_name, "result": response.get('data')}
    else:
        raise HTTPException(status_code=503, detail=response.get('error', 'Daemon error'))


@app.post("/api/pause")
async def api_pause() -> dict[str, Any]:
    """Pause the daemon via WebSocket."""
    response = await send_daemon_command('pause')
    if response.get('success'):
        return {"success": True, "paused": True}
    raise HTTPException(status_code=503, detail=response.get('error', 'Daemon error'))


@app.post("/api/resume")
async def api_resume() -> dict[str, Any]:
    """Resume the daemon via WebSocket."""
    response = await send_daemon_command('resume')
    if response.get('success'):
        return {"success": True, "paused": False}
    raise HTTPException(status_code=503, detail=response.get('error', 'Daemon error'))


@app.post("/api/return-to-base")
async def api_return_to_base() -> dict[str, Any]:
    """Return to base view via daemon WebSocket."""
    response = await send_daemon_command('return_to_base')
    if response.get('success'):
        return {"success": True}
    raise HTTPException(status_code=503, detail=response.get('error', 'Daemon error'))


@app.get("/api/titles")
async def api_list_titles() -> dict[str, Any]:
    """Get list of available kingdom titles."""
    response = await send_daemon_command('list_titles')
    if response.get('success'):
        return response.get('data', {})
    raise HTTPException(status_code=503, detail=response.get('error', 'Daemon error'))


@app.post("/api/titles/{title_name}/apply")
async def api_apply_title(title_name: str) -> dict[str, Any]:
    """Apply a kingdom title."""
    response = await send_daemon_command('apply_title', {'title': title_name})
    if response.get('success'):
        return {"success": True, "title": title_name, "result": response.get('data')}
    raise HTTPException(status_code=503, detail=response.get('error', 'Daemon error'))


@app.get("/api/zombie-mode")
async def api_get_zombie_mode() -> dict[str, Any]:
    """Get current zombie mode."""
    response = await send_daemon_command('get_zombie_mode')
    if response.get('success'):
        return response.get('data', {})
    raise HTTPException(status_code=503, detail=response.get('error', 'Daemon error'))


@app.post("/api/zombie-mode/{mode}")
async def api_set_zombie_mode(mode: str, hours: float = 24) -> dict[str, Any]:
    """Set zombie mode (elite, gold, food, iron_mine)."""
    response = await send_daemon_command('set_zombie_mode', {'mode': mode, 'hours': hours})
    if response.get('success'):
        return {"success": True, "mode": mode, "result": response.get('data')}
    raise HTTPException(status_code=503, detail=response.get('error', 'Daemon error'))


@app.post("/api/zombie-attack")
async def api_run_zombie_attack(zombie_type: str = "gold", plus_clicks: int = 10) -> dict[str, Any]:
    """Run a zombie attack with specified type."""
    response = await send_daemon_command('run_zombie_attack', {'zombie_type': zombie_type, 'plus_clicks': plus_clicks})
    if response.get('success'):
        return {"success": True, "zombie_type": zombie_type, "result": response.get('data')}
    raise HTTPException(status_code=503, detail=response.get('error', 'Daemon error'))


# ============================================================================
# Config Override Endpoints
# ============================================================================

@app.get("/api/config")
async def api_get_config() -> dict[str, Any]:
    """Get all config definitions with current values and override status."""
    response = await send_daemon_command('get_config')
    if response.get('success'):
        return response.get('data', {})
    raise HTTPException(status_code=503, detail=response.get('error', 'Daemon error'))


class OverrideRequest(BaseModel):
    """Request to set a config override."""
    value: Any
    duration_minutes: int | None = None


@app.post("/api/config/{key}/override")
async def api_set_override(key: str, request: OverrideRequest) -> dict[str, Any]:
    """Set a config override with optional duration."""
    response = await send_daemon_command('set_override', {
        'key': key,
        'value': request.value,
        'duration_minutes': request.duration_minutes
    })
    if response.get('success'):
        return response.get('data', {})
    raise HTTPException(status_code=503, detail=response.get('error', 'Daemon error'))


@app.delete("/api/config/{key}/override")
async def api_clear_override(key: str) -> dict[str, Any]:
    """Clear a config override, reverting to default."""
    response = await send_daemon_command('clear_override', {'key': key})
    if response.get('success'):
        return response.get('data', {})
    raise HTTPException(status_code=503, detail=response.get('error', 'Daemon error'))


@app.get("/api/config/overrides")
async def api_list_overrides() -> dict[str, Any]:
    """Get all currently active overrides."""
    response = await send_daemon_command('list_overrides')
    if response.get('success'):
        return response.get('data', {})
    raise HTTPException(status_code=503, detail=response.get('error', 'Daemon error'))


@app.get("/api/events")
async def api_events() -> StreamingResponse:
    """Server-Sent Events stream for live updates."""
    async def event_generator() -> AsyncGenerator[str, None]:
        while True:
            # Get current status via WebSocket
            status = await get_daemon_status_via_ws()
            arms_race = get_arms_race_status()

            data = {
                "type": "update",
                "status": status,
                "arms_race": {
                    "current_event": arms_race["current"],
                    "time_remaining_seconds": arms_race["time_remaining"].total_seconds(),
                    "day": arms_race["day"],
                },
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            # Always send update (frontend handles diff)
            yield f"data: {json.dumps(data)}\n\n"

            await asyncio.sleep(3)  # Update every 3 seconds

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ============================================================================
# Server Startup
# ============================================================================

def start_dashboard_server(daemon_instance: Any = None, port: int | None = None) -> int:
    """
    Start the dashboard server in a background thread.

    Args:
        daemon_instance: Reference to IconDaemon instance
        port: Specific port to use, or None for auto-detect

    Returns:
        Port number the server is running on
    """
    global _daemon_instance, _dashboard_port

    if daemon_instance:
        _daemon_instance = daemon_instance

    if port is None:
        port = find_free_port()

    _dashboard_port = port

    def run_server():
        try:
            config = uvicorn.Config(
                app,
                host="127.0.0.1",
                port=port,
                log_level="warning",
                access_log=False,
                log_config=None,  # Disable uvicorn's logging config (conflicts with daemon's Tee stdout)
            )
            server = uvicorn.Server(config)
            server.run()
        except Exception as e:
            print(f"[DASHBOARD] Server crashed: {e}")
            import traceback
            traceback.print_exc()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    # Wait for server to start and verify
    time.sleep(1.5)

    # Verify port is actually listening
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        if s.connect_ex(('127.0.0.1', port)) == 0:
            print(f"[DASHBOARD] Dashboard running at: http://localhost:{port}")
        else:
            print(f"[DASHBOARD] WARNING: Server thread started but port {port} not listening!")

    return port


# ============================================================================
# Standalone Mode
# ============================================================================

if __name__ == "__main__":
    from config import DASHBOARD_PORT
    print("Starting dashboard in standalone mode...")
    port = DASHBOARD_PORT if DASHBOARD_PORT else find_free_port()
    print(f"Dashboard: http://localhost:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port)
