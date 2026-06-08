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
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import uvicorn

# Add project root to path
import sys
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from utils.arms_race import get_arms_race_status, get_time_until_event, SCHEDULE, VALID_EVENTS
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


@app.get("/api/current-state")
async def api_current_state() -> dict[str, Any]:
    """
    Get persisted current state (survives page refreshes).

    Returns stamina, arms race score, view state, zombie mode - all from
    the state file that the daemon writes to.
    """
    from utils.current_state import get_full_state
    return get_full_state()


@app.get("/api/tavern-quests")
async def api_tavern_quests() -> dict[str, Any]:
    """Get pending tavern quest completion times."""
    scheduler = get_scheduler()
    completions = scheduler.get_tavern_completions()
    now = datetime.now()

    quests = []
    for completion in completions:
        if completion > now:
            remaining = (completion - now).total_seconds()
            quests.append({
                "completion_time": completion.isoformat(),
                "remaining_seconds": remaining,
            })

    return {
        "quests": quests,
        "count": len(quests),
        "timestamp": now.isoformat(),
    }


@app.get("/api/tavern-status")
async def api_tavern_status() -> dict[str, Any]:
    """Dispatch-related tavern status (three-tier model).

    Returns the first-screen counts captured during the most recent dispatch
    attempt, plus exhaustion + daily claims. Tiers:

    - dispatchable_visible: total Go buttons visible (any quest type).
      The universe -- our addressable market.
    - directly_startable_visible: subset our code can click Go on right
      now (gold scroll + question marks post VS-day filter).
    - refresh_candidates: dispatchable - directly_startable. Visible Gos
      of unsupported types; refresh candidates the player could re-roll
      in-game into a supported type. Derived here for UI convenience.
    """
    scheduler = get_scheduler()
    counts = scheduler.get_tavern_visible_counts() or {}
    dispatchable = counts.get("dispatchable")
    directly_startable = counts.get("directly_startable")
    if dispatchable is not None and directly_startable is not None:
        refresh_candidates: int | None = max(0, int(dispatchable) - int(directly_startable))
    else:
        refresh_candidates = None
    return {
        "gold_visible": counts.get("gold"),
        "question_visible": counts.get("question"),
        "dispatchable_visible": dispatchable,
        "directly_startable_visible": directly_startable,
        "refresh_candidates": refresh_candidates,
        "checked_at": counts.get("checked_at"),
        "exhausted_today": scheduler.is_tavern_dispatch_exhausted_today(),
        "claims_today": scheduler.get_tavern_claims_today(),
    }


@app.post("/api/tavern-status/clear-exhaustion")
async def api_clear_tavern_exhaustion() -> dict[str, Any]:
    """Manually clear today's tavern dispatch exhaustion flag."""
    scheduler = get_scheduler()
    scheduler.clear_tavern_dispatch_exhausted_today()
    return {"success": True, "exhausted_today": scheduler.is_tavern_dispatch_exhausted_today()}


@app.get("/api/arms-race")
async def api_arms_race() -> dict[str, Any]:
    """Get Arms Race status including next occurrence times for all events."""
    status = get_arms_race_status()

    # Calculate time until next occurrence of each event type
    # skip_current=True means if you're IN Soldier Training, show when NEXT Soldier Training is
    next_occurrences = {}
    for event_name in VALID_EVENTS:
        time_until = get_time_until_event(event_name, skip_current=True)
        if time_until is not None:
            next_occurrences[event_name] = time_until.total_seconds()
        else:
            next_occurrences[event_name] = None

    return {
        "current_event": status["current"],
        "previous_event": status["previous"],
        "next_event": status["next"],
        "day": status["day"],
        "time_remaining_seconds": status["time_remaining"].total_seconds(),
        "time_elapsed_seconds": status["time_elapsed"].total_seconds(),
        "block_start": status["block_start"].isoformat(),
        "block_end": status["block_end"].isoformat(),
        "next_occurrences": next_occurrences,
    }


@app.post("/api/arms-race/check-score")
async def api_check_arms_race_score() -> dict[str, Any]:
    """Check current Arms Race score by triggering the flow."""
    import websockets
    from utils.current_state import update_arms_race_score

    try:
        # Longer timeout for flow execution (180s like daemon_cli)
        async with websockets.connect('ws://localhost:9876', close_timeout=180) as ws:
            await ws.send(json.dumps({'cmd': 'run_flow', 'args': {'flow': 'arms_race_check'}}))
            response = json.loads(await asyncio.wait_for(ws.recv(), timeout=180))

            if response.get('success'):
                # Flow result is in data.result (the dict returned by check_arms_race_progress)
                result = response.get('data', {}).get('result', {})
                current_points = result.get('current_points')
                chest3_target = result.get('chest3_target', 30000)
                detected_event = result.get('detected_event')

                # Persist to state file so it survives page refresh
                if current_points is not None:
                    update_arms_race_score(current_points, chest3_target, detected_event)

                return {
                    "success": True,
                    "current_points": current_points,
                    "chest3_target": chest3_target,
                    "points_to_chest3": result.get('points_to_chest3'),
                    "detected_event": detected_event,
                }
            return {"success": False, "error": response.get('error', 'Failed to check score')}
    except asyncio.TimeoutError:
        return {"success": False, "error": "Timeout - flow took too long"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.post("/api/shields/refresh")
async def api_refresh_shields() -> dict[str, Any]:
    """Refresh shield inventory by reading from bag Special tab."""
    import websockets

    try:
        async with websockets.connect('ws://localhost:9876', close_timeout=180) as ws:
            await ws.send(json.dumps({'cmd': 'get_shield_inventory', 'args': {}}))
            response = json.loads(await asyncio.wait_for(ws.recv(), timeout=180))

            if response.get('success'):
                data = response.get('data', {})
                return {
                    "success": True,
                    "8hr": data.get('8hr'),
                    "12hr": data.get('12hr'),
                    "24hr": data.get('24hr'),
                }
            return {"success": False, "error": response.get('error', 'Failed to read shields')}
    except asyncio.TimeoutError:
        return {"success": False, "error": "Timeout - flow took too long"}
    except Exception as e:
        return {"success": False, "error": str(e)}


class UseShieldRequest(BaseModel):
    """Request to use a shield."""
    shield_type: str


class ScheduleShieldRequest(BaseModel):
    """Request to schedule a shield activation."""
    shield_type: str
    delay_seconds: int


# Track scheduled shield tasks
_scheduled_shield: dict[str, Any] = {
    "task": None,
    "shield_type": None,
    "activate_at": None,
}


async def _delayed_shield_activation(shield_type: str, delay_seconds: int):
    """Background task to activate shield after delay."""
    import websockets

    await asyncio.sleep(delay_seconds)

    try:
        async with websockets.connect('ws://localhost:9876', close_timeout=180) as ws:
            await ws.send(json.dumps({
                'cmd': 'use_shield',
                'args': {'shield_type': shield_type}
            }))
            await asyncio.wait_for(ws.recv(), timeout=180)
    except Exception as e:
        print(f"[DASHBOARD] Scheduled shield activation failed: {e}")
    finally:
        # Clear the scheduled state
        _scheduled_shield["task"] = None
        _scheduled_shield["shield_type"] = None
        _scheduled_shield["activate_at"] = None


@app.post("/api/shields/schedule")
async def api_schedule_shield(request: ScheduleShieldRequest) -> dict[str, Any]:
    """Schedule a shield to activate after a delay."""
    if request.shield_type not in ["8hr", "12hr", "24hr"]:
        return {"success": False, "error": f"Invalid shield type: {request.shield_type}"}

    if request.delay_seconds < 1:
        return {"success": False, "error": "Delay must be at least 1 second"}

    if request.delay_seconds > 86400:  # Max 24 hours
        return {"success": False, "error": "Delay cannot exceed 24 hours"}

    # Cancel existing scheduled shield if any
    if _scheduled_shield["task"] is not None:
        _scheduled_shield["task"].cancel()

    # Calculate activation time
    activate_at = datetime.now(timezone.utc) + timedelta(seconds=request.delay_seconds)

    # Create the delayed task
    task = asyncio.create_task(
        _delayed_shield_activation(request.shield_type, request.delay_seconds)
    )

    _scheduled_shield["task"] = task
    _scheduled_shield["shield_type"] = request.shield_type
    _scheduled_shield["activate_at"] = activate_at.isoformat()

    return {
        "success": True,
        "shield_type": request.shield_type,
        "delay_seconds": request.delay_seconds,
        "activate_at": activate_at.isoformat(),
    }


@app.get("/api/shields/scheduled")
async def api_get_scheduled_shield() -> dict[str, Any]:
    """Get the currently scheduled shield, if any."""
    if _scheduled_shield["task"] is None or _scheduled_shield["task"].done():
        return {"scheduled": False}

    return {
        "scheduled": True,
        "shield_type": _scheduled_shield["shield_type"],
        "activate_at": _scheduled_shield["activate_at"],
    }


@app.post("/api/shields/cancel")
async def api_cancel_scheduled_shield() -> dict[str, Any]:
    """Cancel a scheduled shield activation."""
    if _scheduled_shield["task"] is None or _scheduled_shield["task"].done():
        return {"success": False, "error": "No shield scheduled"}

    _scheduled_shield["task"].cancel()
    shield_type = _scheduled_shield["shield_type"]

    _scheduled_shield["task"] = None
    _scheduled_shield["shield_type"] = None
    _scheduled_shield["activate_at"] = None

    return {"success": True, "cancelled": shield_type}


@app.post("/api/shields/use")
async def api_use_shield(request: UseShieldRequest) -> dict[str, Any]:
    """Use/activate a shield from the bag."""
    import websockets

    if request.shield_type not in ["8hr", "12hr", "24hr"]:
        return {"success": False, "error": f"Invalid shield type: {request.shield_type}"}

    try:
        async with websockets.connect('ws://localhost:9876', close_timeout=180) as ws:
            await ws.send(json.dumps({
                'cmd': 'use_shield',
                'args': {'shield_type': request.shield_type}
            }))
            response = json.loads(await asyncio.wait_for(ws.recv(), timeout=180))

            if response.get('success'):
                data = response.get('data', {})
                return {
                    "success": data.get('success', False),
                    "message": data.get('message', ''),
                    "error": data.get('error'),
                }
            return {"success": False, "error": response.get('error', 'Failed to use shield')}
    except asyncio.TimeoutError:
        return {"success": False, "error": "Timeout - flow took too long"}
    except Exception as e:
        return {"success": False, "error": str(e)}


class QuickProductionMarkDoneRequest(BaseModel):
    """Request to mark Quick Production as done."""
    verify_ocr: bool = True  # if False, skip the in-game navigation+OCR step


@app.post("/api/quick-production/mark-done")
async def api_mark_quick_production_done(request: QuickProductionMarkDoneRequest) -> dict[str, Any]:
    """
    Mark Quick Production as done from the dashboard.

    If verify_ocr=True (default), the daemon navigates to the Class Skill
    panel and OCRs the actual cooldown timer to set the next-run time
    precisely. If OCR fails or returns nothing usable, it falls back to a
    24h cooldown.
    """
    import websockets

    try:
        async with websockets.connect('ws://localhost:9876', close_timeout=180) as ws:
            await ws.send(json.dumps({
                'cmd': 'mark_quick_production_done',
                'args': {'verify_ocr': request.verify_ocr},
            }))
            response = json.loads(await asyncio.wait_for(ws.recv(), timeout=180))
            if response.get('success'):
                data = response.get('data', {})
                return {"success": True, **data}
            return {"success": False, "error": response.get('error', 'unknown error')}
    except asyncio.TimeoutError:
        return {"success": False, "error": "Timeout - flow took too long"}
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/quick-production/status")
async def api_quick_production_status() -> dict[str, Any]:
    """Return current scheduler state for quick_production."""
    scheduler = get_scheduler()
    flow_data = scheduler.schedule.get("flows", {}).get("quick_production", {})
    next_eligible = scheduler.get_next_eligible("quick_production")
    return {
        "last_run": flow_data.get("last_run"),
        "next_eligible_iso": next_eligible.isoformat() if next_eligible else None,
        "ready_now": next_eligible is None,
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


# ============================================================================
# Timeline API
# ============================================================================

# Cache for timeline data (10 second TTL)
_timeline_cache: dict[str, Any] = {"data": None, "expires": 0.0}


@app.get("/api/timeline")
async def api_timeline(hours_back: int = 12, hours_forward: int = 12) -> dict[str, Any]:
    """
    Get unified event timeline.

    Returns past events (from event log) and future events (cooldown-based + Arms Race schedule).
    """
    global _timeline_cache

    now = time.time()

    # Check cache (10 second TTL)
    if _timeline_cache["expires"] > now:
        return _timeline_cache["data"]

    from utils.timeline import get_timeline
    data = get_timeline(hours_back, hours_forward)

    _timeline_cache = {"data": data, "expires": now + 10}
    return data


@app.get("/api/timeline/summary")
async def api_timeline_summary(hours_back: int = 12, hours_forward: int = 12) -> dict[str, Any]:
    """Get timeline summary with counts by category."""
    from utils.timeline import get_timeline_summary
    return get_timeline_summary(hours_back, hours_forward)


# Cache for blocks data (5 second TTL - more frequent updates for progress bar)
_blocks_cache: dict[str, Any] = {"data": None, "expires": 0.0}


@app.get("/api/timeline/blocks")
async def api_timeline_blocks(blocks_back: int = 2, blocks_forward: int = 3) -> dict[str, Any]:
    """
    Get Arms Race blocks with flow executions mapped to each block.

    Returns structured block data for the block-based timeline UI.
    """
    global _blocks_cache

    now = time.time()

    # Check cache (5 second TTL for more responsive progress bar)
    if _blocks_cache["expires"] > now:
        return _blocks_cache["data"]

    from utils.timeline import get_timeline_blocks
    data = get_timeline_blocks(blocks_back, blocks_forward)

    _blocks_cache = {"data": data, "expires": now + 5}
    return data


@app.get("/api/flows")
async def api_flows() -> list[dict[str, Any]]:
    """Get list of all flows."""
    return await get_flows_list_async()


async def send_daemon_command(cmd: str, args: dict[str, Any] | None = None, timeout: int = 180) -> dict[str, Any]:
    """Send command to daemon via WebSocket.

    Args:
        cmd: Command to send (e.g., 'run_flow', 'status')
        args: Optional arguments dict
        timeout: Timeout in seconds for flow execution (default 180s / 3 minutes)
    """
    import websockets
    import json

    try:
        async with websockets.connect('ws://localhost:9876', close_timeout=timeout) as ws:
            msg = {'cmd': cmd}
            if args:
                msg['args'] = args
            await ws.send(json.dumps(msg))
            response = json.loads(await asyncio.wait_for(ws.recv(), timeout=timeout))
            return response
    except asyncio.TimeoutError:
        return {'success': False, 'error': f'Timeout after {timeout}s'}
    except Exception as e:
        return {'success': False, 'error': str(e)}


@app.post("/api/ws/command")
async def api_ws_command(request: Request) -> dict[str, Any]:
    """Forward arbitrary command to daemon via WebSocket."""
    body = await request.json()
    cmd = body.get('cmd')
    args = body.get('args')

    if not cmd:
        raise HTTPException(status_code=400, detail="Missing 'cmd' field")

    response = await send_daemon_command(cmd, args)
    return response


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


@app.get("/api/screenshot")
async def api_screenshot() -> dict[str, Any]:
    """Take a screenshot and save to debug folder. Returns the file path."""
    import cv2
    try:
        from utils.windows_screenshot_helper import WindowsScreenshotHelper
        win = WindowsScreenshotHelper()
        frame = win.get_screenshot_cv2()

        # Save to debug folder with timestamp
        debug_dir = PROJECT_ROOT / "screenshots" / "debug"
        debug_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"manual_screenshot_{timestamp}.png"
        filepath = debug_dir / filename
        cv2.imwrite(str(filepath), frame)

        return {
            "success": True,
            "filename": filename,
            "path": str(filepath),
            "timestamp": timestamp
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Screenshot failed: {str(e)}")


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


@app.get("/api/zombie-modes")
async def api_get_zombie_modes() -> dict[str, Any]:
    """Get available zombie modes with their stamina costs from config."""
    from config import ZOMBIE_MODE_CONFIG
    return {
        "modes": {
            mode: {"stamina": cfg.get("stamina", 0), "points": cfg.get("points", 0), "flow": cfg.get("flow", "")}
            for mode, cfg in ZOMBIE_MODE_CONFIG.items()
        }
    }


# ============================================================================
# Reinforce Mode Endpoints
# ============================================================================

@app.get("/api/reinforce-mode")
async def api_get_reinforce_mode() -> dict[str, Any]:
    """Get current reinforce loop mode status."""
    response = await send_daemon_command('get_reinforce_status')
    if response.get('success'):
        return response.get('data', {})
    raise HTTPException(status_code=503, detail=response.get('error', 'Daemon error'))


class ReinforceStartRequest(BaseModel):
    """Request to start reinforce loop."""
    interval: int = 10  # Seconds between runs


@app.post("/api/reinforce-mode/start")
async def api_start_reinforce(request: ReinforceStartRequest) -> dict[str, Any]:
    """Start reinforce loop mode."""
    response = await send_daemon_command('start_reinforce', {'interval': request.interval})
    if response.get('success'):
        return {"success": True, "result": response.get('data')}
    raise HTTPException(status_code=503, detail=response.get('error', 'Daemon error'))


@app.post("/api/reinforce-mode/stop")
async def api_stop_reinforce() -> dict[str, Any]:
    """Stop reinforce loop mode."""
    response = await send_daemon_command('stop_reinforce')
    if response.get('success'):
        return {"success": True, "result": response.get('data')}
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


@app.get("/api/rally/monsters")
async def api_rally_monsters() -> dict[str, Any]:
    """
    Get recognized rally monster types and per-monster daily-limit override state.
    """
    from config import RALLY_MONSTERS
    from utils.config_overrides import get_rally_ignore_daily_limit_key

    cfg_response = await send_daemon_command('get_config')
    if not cfg_response.get('success'):
        raise HTTPException(status_code=503, detail=cfg_response.get('error', 'Daemon error'))

    configs = cfg_response.get('data', {}).get('configs', {})
    monsters: list[dict[str, Any]] = []
    for monster in RALLY_MONSTERS:
        name = str(monster.get("name", "")).strip()
        if not name:
            continue
        override_key = get_rally_ignore_daily_limit_key(name)
        override_state = configs.get(override_key, {})

        monsters.append({
            "name": name,
            "auto_join": bool(monster.get("auto_join", True)),
            "max_level": monster.get("max_level"),
            "level_range": monster.get("level_range"),
            "track_daily_limit": bool(monster.get("track_daily_limit", True)),
            "ignore_override_key": override_key,
            "ignore_daily_limit": {
                "value": bool(override_state.get("value", False)),
                "default": bool(override_state.get("default", False)),
                "overridden": bool(override_state.get("overridden", False)),
                "expires_in": override_state.get("expires_in"),
            },
        })

    return {"monsters": monsters, "count": len(monsters)}


# ============================================================================
# DM Chat Sessions API
# ============================================================================

@app.get("/api/dm-sessions")
async def api_dm_sessions() -> dict[str, Any]:
    """Get all DM chat sessions from playerprefs."""
    import re
    from urllib.parse import unquote

    # Path to playerprefs on device - copy to sdcard first
    import subprocess
    adb = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"

    try:
        # Copy playerprefs to sdcard
        subprocess.run([adb, "-s", "emulator-5554", "shell",
                       "su -c 'cp /data/data/com.xman.na.gp/shared_prefs/com.xman.na.gp.v2.playerprefs.xml /sdcard/playerprefs.xml'"],
                      capture_output=True, timeout=10)

        # Read the file
        result = subprocess.run([adb, "-s", "emulator-5554", "shell", "cat /sdcard/playerprefs.xml"],
                               capture_output=True, text=True, timeout=30, encoding='utf-8', errors='replace')
        content = result.stdout

        if not content:
            return {"success": False, "error": "Could not read playerprefs"}

        # Parse sessions
        sessions = re.findall(r'<string name="session_(\d+)_(\d+)_">([^<]*)</string>', content)

        # Get role names from roleInfo
        role_names = {}
        role_infos = re.findall(r'<string name="roleInfo_(\d+)[^"]*">([^<]*)</string>', content)
        for role_id, value in role_infos:
            try:
                data = json.loads(unquote(value))
                role_names[role_id] = {
                    "name": data.get("name", f"Role_{role_id}"),
                    "guild": data.get("guildname", ""),
                    "level": data.get("roleLv", 0),
                }
            except:
                pass

        # Build session list
        result_sessions = []
        for my_id, other_id, value in sessions:
            try:
                decoded = unquote(value)
                data = json.loads(decoded)
                if not data:
                    continue

                last_msg = data[-1]
                last_ts = last_msg.get("chatTime", 0)
                last_text = last_msg.get("context", "")[:50]
                last_sender = "me" if str(last_msg.get("roleid", "")) == my_id else "them"

                other_info = role_names.get(other_id, {"name": f"Role_{other_id}", "guild": "", "level": 0})

                result_sessions.append({
                    "other_id": other_id,
                    "other_name": other_info["name"],
                    "other_guild": other_info["guild"],
                    "other_level": other_info["level"],
                    "message_count": len(data),
                    "last_timestamp": last_ts,
                    "last_message": last_text,
                    "last_sender": last_sender,
                })
            except:
                pass

        # Sort by last message time (most recent first)
        result_sessions.sort(key=lambda x: -x["last_timestamp"])

        return {
            "success": True,
            "sessions": result_sessions,
            "total": len(result_sessions),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


@app.get("/api/dm-sessions/{other_id}")
async def api_dm_session_messages(other_id: str, limit: int = 50) -> dict[str, Any]:
    """Get messages from a specific DM session."""
    import re
    from urllib.parse import unquote
    import subprocess

    adb = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"
    my_id = "5179912"  # Your role ID

    try:
        # Read playerprefs
        result = subprocess.run([adb, "-s", "emulator-5554", "shell", "cat /sdcard/playerprefs.xml"],
                               capture_output=True, text=True, timeout=30, encoding='utf-8', errors='replace')
        content = result.stdout

        if not content:
            return {"success": False, "error": "Could not read playerprefs"}

        # Find the session
        match = re.search(rf'<string name="session_{my_id}_{other_id}_">([^<]*)</string>', content)
        if not match:
            return {"success": False, "error": f"Session with {other_id} not found"}

        decoded = unquote(match.group(1))
        data = json.loads(decoded)

        # Get other player's name
        other_name = f"Role_{other_id}"
        role_match = re.search(rf'<string name="roleInfo_{other_id}[^"]*">([^<]*)</string>', content)
        if role_match:
            try:
                role_data = json.loads(unquote(role_match.group(1)))
                other_name = role_data.get("name", other_name)
            except:
                pass

        # Format messages (last N)
        messages = []
        for msg in data[-limit:]:
            sender_id = str(msg.get("roleid", ""))
            messages.append({
                "sender": "me" if sender_id == my_id else "them",
                "sender_name": "You" if sender_id == my_id else other_name,
                "text": msg.get("context", ""),
                "timestamp": msg.get("chatTime", 0),
            })

        return {
            "success": True,
            "other_id": other_id,
            "other_name": other_name,
            "messages": messages,
            "total": len(data),
            "showing": len(messages),
        }
    except Exception as e:
        return {"success": False, "error": str(e)}


# Player Profile API
# ============================================================================

# Cache for playerprefs to avoid hammering ADB
_playerprefs_cache = {"content": None, "timestamp": 0}
_PLAYERPREFS_CACHE_TTL = 30  # seconds

# Title ID to internal name mapping (based on game order)
# These map numeric titleID values to kingdom_titles.json keys
TITLE_ID_MAP = {
    0: None,  # No title
    1: "prime_minister",
    2: "marshall",
    3: "minister_of_health",
    4: "ministry_of_construction",
    5: "minister_of_science",
    6: "minister_of_domestic_affairs",
    7: "grand_chancellor",
    8: "military_commander",
}


def _get_playerprefs_cached() -> str | None:
    """Get playerprefs content with caching."""
    import subprocess
    import time

    now = time.time()
    if _playerprefs_cache["content"] and (now - _playerprefs_cache["timestamp"]) < _PLAYERPREFS_CACHE_TTL:
        return _playerprefs_cache["content"]

    adb = r"C:\Program Files\BlueStacks_nxt\hd-adb.exe"

    try:
        # Copy playerprefs to sdcard
        subprocess.run([adb, "-s", "emulator-5554", "shell",
                       "su -c 'cp /data/data/com.xman.na.gp/shared_prefs/com.xman.na.gp.v2.playerprefs.xml /sdcard/playerprefs.xml'"],
                      capture_output=True, timeout=10)

        # Read the file
        result = subprocess.run([adb, "-s", "emulator-5554", "shell", "cat /sdcard/playerprefs.xml"],
                               capture_output=True, text=True, timeout=30, encoding='utf-8', errors='replace')
        content = result.stdout

        if content:
            _playerprefs_cache["content"] = content
            _playerprefs_cache["timestamp"] = now

        return content
    except Exception:
        return _playerprefs_cache.get("content")


@app.get("/api/player-profile")
async def api_player_profile() -> dict[str, Any]:
    """Get current player profile from playerprefs."""
    import re
    from urllib.parse import unquote

    content = _get_playerprefs_cached()
    if not content:
        return {"success": False, "error": "Could not read playerprefs"}

    try:
        # First, find OUR role ID from session keys (session_{myId}_{otherId}_)
        session_match = re.search(r'<string name="session_(\d+)_\d+_">', content)
        my_role_id = session_match.group(1) if session_match else None

        if not my_role_id:
            return {"success": False, "error": "Could not determine player role ID"}

        # Find our roleInfo entry
        role_infos = re.findall(r'<string name="roleInfo_(\d+)_(\d+)">([^<]*)</string>', content)

        # Look for our specific role ID
        our_info = None
        for role_id, world_id, value in role_infos:
            if role_id == my_role_id:
                try:
                    data = json.loads(unquote(value))
                    # Check this has real data (not an empty cross-world cache)
                    if data.get("name") or data.get("ce", 0) > 0:
                        our_info = (role_id, world_id, data)
                        break
                except:
                    pass

        if not our_info:
            return {"success": False, "error": f"Could not find profile for role {my_role_id}"}

        role_id, world_id, data = our_info

        # Build profile response
        profile = {
            "role_id": role_id,
            "world_id": world_id,
            "name": data.get("name", "Unknown"),
            "level": data.get("roleLv", 0),
            "vip_level": data.get("nVipLv", 0),
            "guild": data.get("guildname", ""),
            "ce": data.get("ce", 0),
            "campaign_stage": data.get("passStage", 0),
            "title_id": data.get("titleID", 0),
            "title": None,
            "avatar_url": None,
        }

        # Get avatar URL - try toFaceStr first (custom photo), then faceStr
        for face_key in ["toFaceStr", "toFaceId", "faceStr"]:
            face_str = data.get(face_key, "")
            if face_str and face_str.startswith("http"):
                profile["avatar_url"] = face_str
                break

        # Map title ID to title info
        title_id = profile["title_id"]
        title_key = TITLE_ID_MAP.get(title_id)

        if title_key:
            # Load kingdom titles
            titles_path = Path(__file__).parent.parent / "data" / "kingdom_titles.json"
            if titles_path.exists():
                with open(titles_path, "r") as f:
                    titles_data = json.load(f)
                    title_info = titles_data.get("titles", {}).get(title_key)
                    if title_info:
                        profile["title"] = {
                            "key": title_key,
                            "name": title_info.get("display_name", title_key),
                            "buffs": title_info.get("buffs", []),
                        }

        return {
            "success": True,
            "profile": profile,
            "cache_ttl": _PLAYERPREFS_CACHE_TTL,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    except Exception as e:
        return {"success": False, "error": str(e)}


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
