"""
Unified Event Timeline Generator

Combines multiple event sources into a single timeline view:
- Current status: Active Arms Race event and VS day
- Past events: Flow executions from scheduler event_log
- Future cooldown events: When flows become eligible based on cooldowns
- Future Arms Race events: Scheduled game events (4-hour blocks)
- Future VS events: Day transitions and special checkpoints
- Future tavern completions: Scheduled quest completion times

Used by the dashboard to display a visual timeline of automation activity.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from utils.scheduler import get_scheduler, FLOW_CONFIGS
from utils.arms_race import SCHEDULE, REFERENCE_TIME, EVENT_HOURS, get_arms_race_status


# Flow categories for visual grouping
FLOW_CATEGORIES: dict[str, str | None] = {
    # Arms Race related
    "elite_zombie": "combat",
    "zombie_attack": "combat",
    "zombie_attack_gold": "combat",
    "zombie_attack_food": "combat",
    "zombie_attack_iron_mine": "combat",
    "beast_training_hour_mark": "arms_race",
    "beast_training_last_hour": "arms_race",
    "beast_training_mid_check": "arms_race",
    "hero_upgrade": "arms_race",
    "hero_upgrade_arms_race": "arms_race",
    "soldier_training": "arms_race",
    "soldier_upgrade": "arms_race",
    "marshall_speedup": "arms_race",
    "pre_beast_stamina_claim": "arms_race",

    # Quests
    "tavern_quest": "quest",
    "tavern_quest_claim": "quest",
    "faction_trials": "quest",

    # Maintenance / Resource collection
    "bag_flow": "maintenance",
    "afk_rewards": "maintenance",
    "union_gifts": "maintenance",
    "union_technology": "maintenance",
    "gift_box": "maintenance",
    "healing": "maintenance",
    "hospital_help": "maintenance",
    "treasure_map": "maintenance",
    "equipment_enhancement": "maintenance",
    "rally_join": "combat",

    # Excluded (harvest bubbles - too noisy)
    "corn_harvest": None,
    "gold_coin": None,
    "iron_bar": None,
    "gem": None,
    "cabbage": None,
    "harvest_box": None,
    "handshake": None,
}

# Flows to exclude from timeline (harvest bubbles)
EXCLUDED_FLOWS = {k for k, v in FLOW_CATEGORIES.items() if v is None}

# Map Arms Race event names to associated flows
ARMS_RACE_EVENT_FLOWS: dict[str, list[str]] = {
    "Mystic Beast Training": ["elite_zombie", "beast_training_hour_mark", "beast_training_last_hour", "beast_training_mid_check"],
    "Enhance Hero": ["hero_upgrade_arms_race"],
    "Soldier Training": ["soldier_upgrade", "marshall_speedup"],
    "City Construction": [],
    "Technology Research": [],
}

# VS special days configuration (imported from config if available)
try:
    from config import VS_SOLDIER_PROMOTION_DAYS, VS_LEVEL_CHEST_DAYS, VS_QUESTION_MARK_SKIP_DAYS
except ImportError:
    VS_SOLDIER_PROMOTION_DAYS = [2]
    VS_LEVEL_CHEST_DAYS = [7]
    VS_QUESTION_MARK_SKIP_DAYS = [3, 6]

# VS Day 7 surprise checkpoints (minutes before day ends)
VS_DAY7_CHECKPOINTS = [10, 5, 1]

# VS Day descriptions
VS_DAY_INFO: dict[int, str] = {
    1: "Day 1 - Event Start",
    2: "Day 2 - Soldier Promotions",
    3: "Day 3 - Skip Question Marks",
    4: "Day 4",
    5: "Day 5",
    6: "Day 6 - Skip Question Marks",
    7: "Day 7 - Level Chest Day (Surprise!)",
}


def get_flow_category(flow_name: str) -> str:
    """Get category for a flow, defaulting to 'maintenance'."""
    return FLOW_CATEGORIES.get(flow_name) or "maintenance"


def get_timeline(hours_back: int = 12, hours_forward: int = 12) -> dict[str, Any]:
    """
    Generate unified timeline data.

    Args:
        hours_back: Hours to look back for past events
        hours_forward: Hours to look forward for future events

    Returns:
        Dict with current_status, past_events, future_events, etc.
    """
    now = datetime.now()
    start = now - timedelta(hours=hours_back)
    end = now + timedelta(hours=hours_forward)

    # Get current Arms Race / VS status
    current_status = _get_current_status()

    past_events = _get_past_events(start, now)
    future_cooldown_events = _get_future_cooldown_events(now, end)
    future_arms_race_events = _get_future_arms_race_events(now, end)
    future_vs_events = _get_future_vs_events(now, end)
    future_tavern_events = _get_future_tavern_events(now, end)

    # Combine all future events
    future_events = future_cooldown_events + future_arms_race_events + future_vs_events + future_tavern_events
    future_events.sort(key=lambda e: e["timestamp"])

    return {
        "current_status": current_status,
        "past_events": past_events,
        "future_events": future_events,
        "current_time": now.isoformat(),
        "range_start": start.isoformat(),
        "range_end": end.isoformat(),
    }


def _get_current_status() -> dict[str, Any]:
    """Get current Arms Race and VS status."""
    try:
        status = get_arms_race_status()
        day = status["day"]
        current_event = status["current"]
        time_remaining = status["time_remaining"]
        time_elapsed = status["time_elapsed"]

        # Calculate minutes remaining in current event
        mins_remaining = time_remaining.total_seconds() / 60
        mins_elapsed = time_elapsed.total_seconds() / 60

        # VS Day info
        vs_info = VS_DAY_INFO.get(day, f"Day {day}")
        is_soldier_promo_day = day in VS_SOLDIER_PROMOTION_DAYS
        is_level_chest_day = day in VS_LEVEL_CHEST_DAYS
        is_question_skip_day = day in VS_QUESTION_MARK_SKIP_DAYS

        return {
            "arms_race_event": current_event,
            "arms_race_mins_remaining": round(mins_remaining, 1),
            "arms_race_mins_elapsed": round(mins_elapsed, 1),
            "vs_day": day,
            "vs_info": vs_info,
            "is_soldier_promo_day": is_soldier_promo_day,
            "is_level_chest_day": is_level_chest_day,
            "is_question_skip_day": is_question_skip_day,
            "block_start": status["block_start"].isoformat() if status.get("block_start") else None,
            "block_end": status["block_end"].isoformat() if status.get("block_end") else None,
        }
    except Exception as e:
        return {"error": str(e)}


def _get_past_events(start: datetime, end: datetime) -> list[dict[str, Any]]:
    """Get completed events from scheduler event log."""
    scheduler = get_scheduler()
    events = scheduler.get_events_in_range(start, end)

    # Filter out excluded flows and add event_type
    result = []
    for event in events:
        flow_name = event.get("flow_name", "")
        if flow_name in EXCLUDED_FLOWS:
            continue

        result.append({
            "id": event.get("id", ""),
            "flow_name": flow_name,
            "timestamp": event.get("timestamp", ""),
            "event_type": "past",
            "status": event.get("status", "completed"),
            "duration_seconds": event.get("duration_seconds"),
            "category": event.get("category") or get_flow_category(flow_name),
            "is_critical": event.get("is_critical", False),
            "source": "event_log",
            "result": event.get("result"),  # Flow-specific result data (e.g., monster_name, level)
        })

    return result


def _get_future_cooldown_events(start: datetime, end: datetime) -> list[dict[str, Any]]:
    """Calculate when flows become eligible based on cooldowns."""
    scheduler = get_scheduler()
    result = []

    for flow_name, config in FLOW_CONFIGS.items():
        if flow_name in EXCLUDED_FLOWS:
            continue

        next_eligible = scheduler.get_next_eligible(flow_name)

        if next_eligible is None:
            # Flow is ready now - show as immediate eligibility
            result.append({
                "id": f"future_{flow_name}_ready",
                "flow_name": flow_name,
                "timestamp": start.isoformat(),
                "event_type": "future_cooldown",
                "status": "ready",
                "category": get_flow_category(flow_name),
                "is_critical": False,
                "source": "cooldown",
                "eligibility_reason": f"Ready now (idle required: {config['idle_required']}s)",
            })
        elif start <= next_eligible <= end:
            # Will become eligible within our window
            result.append({
                "id": f"future_{flow_name}_{next_eligible.isoformat()}",
                "flow_name": flow_name,
                "timestamp": next_eligible.isoformat(),
                "event_type": "future_cooldown",
                "status": "pending",
                "category": get_flow_category(flow_name),
                "is_critical": False,
                "source": "cooldown",
                "eligibility_reason": f"Cooldown: {config['cooldown']}s, Idle: {config['idle_required']}s",
            })

    return result


def _get_future_arms_race_events(now: datetime, end: datetime) -> list[dict[str, Any]]:
    """Get upcoming Arms Race events from schedule."""
    result = []

    # Get current status to find our position in the schedule
    now_utc = datetime.now(timezone.utc)
    status = get_arms_race_status(now_utc)
    current_idx = status["event_index"]

    # Calculate the absolute start time of the current event
    current_block_start = status["block_start"]

    # Look at upcoming events (up to 24 hours = 6 events max)
    for offset in range(1, 7):  # Next 6 events (24 hours)
        event_idx = (current_idx + offset) % 42
        day, hour, event_name = SCHEDULE[event_idx]

        # Calculate event start time
        event_start = current_block_start + timedelta(hours=offset * EVENT_HOURS)

        # Convert to local time for comparison
        if event_start.tzinfo is not None:
            event_start_local = event_start.replace(tzinfo=None)
        else:
            event_start_local = event_start

        # Check if within our window
        if now <= event_start_local <= end:
            associated_flows = ARMS_RACE_EVENT_FLOWS.get(event_name, [])

            result.append({
                "id": f"arms_race_{event_idx}_{event_start.isoformat()}",
                "flow_name": event_name,
                "timestamp": event_start_local.isoformat(),
                "event_type": "future_arms_race",
                "status": "scheduled",
                "category": "arms_race",
                "is_critical": event_name == "Mystic Beast Training",
                "source": "arms_race_schedule",
                "eligibility_reason": f"Day {day}, {event_name}",
                "associated_flows": associated_flows,
                "duration_hours": EVENT_HOURS,
                "vs_day": day,
            })

    return result


def _get_future_vs_events(now: datetime, end: datetime) -> list[dict[str, Any]]:
    """Get VS-specific events like day transitions and Day 7 checkpoints."""
    result = []

    # Get current status
    status = get_arms_race_status()
    current_day = status["day"]
    block_end = status["block_end"]

    # Convert block_end to local time
    if block_end.tzinfo is not None:
        block_end_local = block_end.replace(tzinfo=None)
    else:
        block_end_local = block_end

    # Calculate when each future day starts (every 24 hours from day boundary)
    # Each day has 6 events × 4 hours = 24 hours
    # Day boundary = when event 0 of a day starts (02:00 UTC for Day 1)

    # Find the next day boundary
    time_remaining = status["time_remaining"]
    current_event_end = now + time_remaining

    # How many events until end of current day?
    event_idx = status["event_index"]
    events_in_day = event_idx % 6  # 0-5 within day
    events_until_day_end = 6 - events_in_day - 1  # Events remaining after current

    # Time until current day ends
    time_until_day_end = time_remaining + timedelta(hours=events_until_day_end * EVENT_HOURS)
    day_end_time = now + time_until_day_end

    # Add VS Day 7 checkpoints if we're on Day 7
    if current_day == 7:
        mins_remaining = time_remaining.total_seconds() / 60

        for checkpoint in VS_DAY7_CHECKPOINTS:
            # Only add if checkpoint is in future and within our window
            if mins_remaining > checkpoint:
                checkpoint_time = block_end_local - timedelta(minutes=checkpoint)
                if now <= checkpoint_time <= end:
                    result.append({
                        "id": f"vs_day7_checkpoint_{checkpoint}",
                        "flow_name": f"VS Surprise ({checkpoint}min)",
                        "timestamp": checkpoint_time.isoformat(),
                        "event_type": "future_vs",
                        "status": "scheduled",
                        "category": "arms_race",
                        "is_critical": True,
                        "source": "vs_checkpoint",
                        "eligibility_reason": f"Open level chests {checkpoint} min before event ends",
                    })

    # Add day transitions for next days
    for day_offset in range(1, 8):  # Up to 7 days ahead
        next_day = ((current_day - 1 + day_offset) % 7) + 1  # Wrap Day 7 -> Day 1
        transition_time = day_end_time + timedelta(hours=(day_offset - 1) * 24)

        if now <= transition_time <= end:
            vs_info = VS_DAY_INFO.get(next_day, f"Day {next_day}")
            is_special = next_day in VS_SOLDIER_PROMOTION_DAYS or next_day in VS_LEVEL_CHEST_DAYS

            result.append({
                "id": f"vs_day_{next_day}_{transition_time.isoformat()}",
                "flow_name": f"VS {vs_info}",
                "timestamp": transition_time.isoformat(),
                "event_type": "future_vs",
                "status": "scheduled",
                "category": "arms_race",
                "is_critical": is_special,
                "source": "vs_day_transition",
                "eligibility_reason": vs_info,
                "vs_day": next_day,
            })

    return result


def _get_future_tavern_events(start: datetime, end: datetime) -> list[dict[str, Any]]:
    """Get scheduled tavern quest completion times."""
    scheduler = get_scheduler()
    completions = scheduler.get_tavern_completions()
    result = []

    for completion_time in completions:
        if start <= completion_time <= end:
            result.append({
                "id": f"tavern_completion_{completion_time.isoformat()}",
                "flow_name": "tavern_quest_claim",
                "timestamp": completion_time.isoformat(),
                "event_type": "future_tavern",
                "status": "scheduled",
                "category": "quest",
                "is_critical": False,
                "source": "tavern_completion",
                "eligibility_reason": "Quest completing",
            })

    return result


def get_timeline_blocks(blocks_back: int = 2, blocks_forward: int = 3) -> dict[str, Any]:
    """
    Get Arms Race blocks with flow executions mapped to each block.

    Returns a structured view showing:
    - Past blocks (completed)
    - Current block (with progress)
    - Future blocks (upcoming)
    - VS Day info
    - Server reset countdown

    Args:
        blocks_back: Number of past blocks to include
        blocks_forward: Number of future blocks to include

    Returns:
        Dict with blocks array and metadata
    """
    from datetime import timezone
    now = datetime.now()
    now_utc = datetime.now(timezone.utc)

    # Get current Arms Race status
    status = get_arms_race_status(now_utc)
    current_idx = status["event_index"]
    current_day = status["day"]
    block_start = status["block_start"]
    block_end = status["block_end"]
    time_remaining = status["time_remaining"]
    time_elapsed = status["time_elapsed"]

    # Convert to local time
    if block_start.tzinfo is not None:
        block_start_local = block_start.replace(tzinfo=None)
        block_end_local = block_end.replace(tzinfo=None)
    else:
        block_start_local = block_start
        block_end_local = block_end

    # Get past events for mapping flows to blocks
    scheduler = get_scheduler()
    past_start = now - timedelta(hours=(blocks_back + 1) * EVENT_HOURS)
    past_events = scheduler.get_events_in_range(past_start, now)

    # Build blocks array
    blocks = []

    # Past blocks
    for offset in range(blocks_back, 0, -1):
        idx = (current_idx - offset) % 42
        day, hour, event_name = SCHEDULE[idx]
        b_start = block_start_local - timedelta(hours=offset * EVENT_HOURS)
        b_end = b_start + timedelta(hours=EVENT_HOURS)

        # Find flows that ran during this block
        block_flows = _get_flows_in_block(past_events, b_start, b_end)

        blocks.append({
            "event": event_name,
            "event_short": _abbreviate_event(event_name),
            "start_time": b_start.isoformat(),
            "end_time": b_end.isoformat(),
            "status": "completed",
            "progress": 100,
            "vs_day": day,
            "flows": block_flows,
        })

    # Current block
    elapsed_mins = time_elapsed.total_seconds() / 60
    total_mins = EVENT_HOURS * 60
    progress = (elapsed_mins / total_mins) * 100
    remaining_mins = time_remaining.total_seconds() / 60

    current_flows = _get_flows_in_block(past_events, block_start_local, now)

    blocks.append({
        "event": status["current"],
        "event_short": _abbreviate_event(status["current"]),
        "start_time": block_start_local.isoformat(),
        "end_time": block_end_local.isoformat(),
        "status": "current",
        "progress": round(progress, 1),
        "time_remaining": _format_minutes(remaining_mins),
        "time_remaining_mins": round(remaining_mins, 1),
        "vs_day": current_day,
        "flows": current_flows,
    })

    # Future blocks
    for offset in range(1, blocks_forward + 1):
        idx = (current_idx + offset) % 42
        day, hour, event_name = SCHEDULE[idx]
        b_start = block_start_local + timedelta(hours=offset * EVENT_HOURS)
        b_end = b_start + timedelta(hours=EVENT_HOURS)

        blocks.append({
            "event": event_name,
            "event_short": _abbreviate_event(event_name),
            "start_time": b_start.isoformat(),
            "end_time": b_end.isoformat(),
            "status": "upcoming",
            "progress": 0,
            "vs_day": day,
            "flows": [],
        })

    # Calculate server reset countdown (02:00 UTC)
    server_reset = _get_server_reset_countdown(now_utc)

    # VS Day info
    vs_info = VS_DAY_INFO.get(current_day, f"Day {current_day}")
    is_special = current_day in VS_SOLDIER_PROMOTION_DAYS or current_day in VS_LEVEL_CHEST_DAYS

    # Find day boundaries within visible range
    day_boundaries = _get_day_boundaries(blocks)

    return {
        "blocks": blocks,
        "current_event": status["current"],
        "current_event_short": _abbreviate_event(status["current"]),
        "time_remaining": _format_minutes(remaining_mins),
        "time_remaining_mins": round(remaining_mins, 1),
        "vs_day": current_day,
        "vs_info": vs_info,
        "is_special_day": is_special,
        "is_soldier_promo_day": current_day in VS_SOLDIER_PROMOTION_DAYS,
        "is_level_chest_day": current_day in VS_LEVEL_CHEST_DAYS,
        "is_question_skip_day": current_day in VS_QUESTION_MARK_SKIP_DAYS,
        "server_reset_in": server_reset,
        "day_boundaries": day_boundaries,
        "current_time": now.isoformat(),
    }


def _abbreviate_event(event_name: str) -> str:
    """Abbreviate event names for compact display."""
    abbrev = {
        "Mystic Beast Training": "Beast",
        "Technology Research": "Tech",
        "City Construction": "City",
        "Soldier Training": "Soldier",
        "Enhance Hero": "Hero",
    }
    return abbrev.get(event_name, event_name)


def _format_minutes(mins: float) -> str:
    """Format minutes as 'Xh Ym' string."""
    hours = int(mins // 60)
    minutes = int(mins % 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"


def _get_flows_in_block(
    events: list[dict[str, Any]], block_start: datetime, block_end: datetime
) -> list[dict[str, Any]]:
    """Get flow executions that occurred during a block."""
    result = []
    for event in events:
        flow_name = event.get("flow_name", "")
        if flow_name in EXCLUDED_FLOWS:
            continue

        try:
            timestamp = datetime.fromisoformat(event["timestamp"])
            if block_start <= timestamp <= block_end:
                result.append({
                    "name": flow_name,
                    "time": timestamp.strftime("%H:%M"),
                    "status": event.get("status", "completed"),
                    "category": event.get("category", "maintenance"),
                })
        except (ValueError, KeyError):
            continue

    return result


def _get_server_reset_countdown(now_utc: datetime) -> str:
    """Calculate countdown to server reset (02:00 UTC)."""
    reset_hour = 2
    hours_until = (reset_hour - now_utc.hour - 1) % 24
    mins_until = 60 - now_utc.minute

    if mins_until == 60:
        mins_until = 0
        hours_until = (hours_until + 1) % 24

    return f"{hours_until}h {mins_until}m"


def _get_day_boundaries(blocks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Find VS day boundaries within the visible blocks."""
    boundaries = []
    prev_day = None

    for i, block in enumerate(blocks):
        day = block.get("vs_day")
        if prev_day is not None and day != prev_day:
            boundaries.append({
                "day": day,
                "time": block["start_time"],
                "label": f"Day {day}",
                "block_index": i,
            })
        prev_day = day

    return boundaries


def get_timeline_summary(hours_back: int = 12, hours_forward: int = 12) -> dict[str, Any]:
    """
    Get a summary of timeline activity.

    Returns counts by category and status.
    """
    timeline = get_timeline(hours_back, hours_forward)

    past_by_category: dict[str, int] = {}
    past_by_status: dict[str, int] = {}
    future_by_category: dict[str, int] = {}
    future_by_source: dict[str, int] = {}

    for event in timeline["past_events"]:
        cat = event.get("category", "unknown")
        status = event.get("status", "unknown")
        past_by_category[cat] = past_by_category.get(cat, 0) + 1
        past_by_status[status] = past_by_status.get(status, 0) + 1

    for event in timeline["future_events"]:
        cat = event.get("category", "unknown")
        source = event.get("source", "unknown")
        future_by_category[cat] = future_by_category.get(cat, 0) + 1
        future_by_source[source] = future_by_source.get(source, 0) + 1

    return {
        "current_status": timeline.get("current_status", {}),
        "total_past": len(timeline["past_events"]),
        "total_future": len(timeline["future_events"]),
        "past_by_category": past_by_category,
        "past_by_status": past_by_status,
        "future_by_category": future_by_category,
        "future_by_source": future_by_source,
    }
