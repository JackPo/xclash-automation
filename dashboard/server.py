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


def get_daemon_status() -> dict[str, Any]:
    """Get current daemon status."""
    if _daemon_instance is None:
        return {
            "paused": False,
            "active_flows": [],
            "critical_flow": None,
            "stamina": None,
            "idle_seconds": 0,
            "view": None,
        }

    # Access daemon state directly
    return {
        "paused": getattr(_daemon_instance, 'paused', False),
        "active_flows": list(getattr(_daemon_instance, 'active_flows', set())),
        "critical_flow": getattr(_daemon_instance, 'critical_flow_name', None),
        "stamina": getattr(_daemon_instance, 'last_stamina', None),
        "idle_seconds": getattr(_daemon_instance, 'idle_seconds', 0),
        "view": getattr(_daemon_instance, 'current_view', None),
    }


def get_flows_list() -> list[dict[str, Any]]:
    """Get list of all flows with their status."""
    # Flow definitions with criticality
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
        ("go_to_mark", False),
        ("title_management", False),
    ]

    active_flows = set()
    if _daemon_instance:
        active_flows = getattr(_daemon_instance, 'active_flows', set())

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
    """Get current daemon status."""
    status = get_daemon_status()
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
    return get_flows_list()


@app.post("/api/flows/{flow_name}/run")
async def api_run_flow(flow_name: str) -> dict[str, Any]:
    """Trigger a flow to run."""
    if _daemon_instance is None:
        raise HTTPException(status_code=503, detail="Daemon not connected")

    # Check if daemon has trigger_flow method
    trigger_flow = getattr(_daemon_instance, 'trigger_flow', None)
    if trigger_flow is None:
        raise HTTPException(status_code=503, detail="Daemon does not support flow triggering")

    # Trigger the flow
    try:
        result = trigger_flow(flow_name)
        return {"success": True, "flow": flow_name, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/pause")
async def api_pause() -> dict[str, Any]:
    """Pause the daemon."""
    if _daemon_instance is None:
        raise HTTPException(status_code=503, detail="Daemon not connected")

    _daemon_instance.paused = True
    return {"success": True, "paused": True}


@app.post("/api/resume")
async def api_resume() -> dict[str, Any]:
    """Resume the daemon."""
    if _daemon_instance is None:
        raise HTTPException(status_code=503, detail="Daemon not connected")

    _daemon_instance.paused = False
    return {"success": True, "paused": False}


@app.post("/api/return-to-base")
async def api_return_to_base() -> dict[str, Any]:
    """Return to base view."""
    if _daemon_instance is None:
        raise HTTPException(status_code=503, detail="Daemon not connected")

    # Import here to avoid circular imports
    from utils.return_to_base_view import return_to_base_view
    from utils.adb_helper import ADBHelper
    from utils.windows_screenshot_helper import WindowsScreenshotHelper

    adb = ADBHelper()
    win = WindowsScreenshotHelper()

    success = return_to_base_view(adb, win, debug=False)
    return {"success": success}


@app.get("/api/events")
async def api_events() -> StreamingResponse:
    """Server-Sent Events stream for live updates."""
    async def event_generator() -> AsyncGenerator[str, None]:
        last_status = None
        while True:
            # Get current status
            status = get_daemon_status()
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
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=port,
            log_level="warning",  # Reduce noise
            access_log=False,
        )
        server = uvicorn.Server(config)
        server.run()

    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()

    # Give server a moment to start
    time.sleep(0.5)

    print(f"[DASHBOARD] Dashboard running at: http://localhost:{port}")

    return port


# ============================================================================
# Standalone Mode
# ============================================================================

if __name__ == "__main__":
    print("Starting dashboard in standalone mode...")
    port = find_free_port()
    print(f"Dashboard: http://localhost:{port}")
    uvicorn.run(app, host="127.0.0.1", port=port)
