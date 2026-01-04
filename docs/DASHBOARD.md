# Mastermind Dashboard

Web-based control panel for xclash automation. Provides real-time status monitoring, flow control, and runtime config overrides.

## Architecture

```
Browser <--HTTP/SSE--> FastAPI Server <--WebSocket--> Daemon (port 9876)
```

- **Dashboard server**: FastAPI app started automatically by the daemon
- **Frontend**: Single HTML file with Alpine.js + Tailwind CSS (no build step)
- **Communication**: REST API for actions, Server-Sent Events for live updates

## Starting the Dashboard

The dashboard starts automatically when the daemon runs:

```bash
python scripts/icon_daemon.py
# Output: [DASHBOARD] Dashboard running at: http://localhost:XXXXX
```

The port is auto-detected (finds a free port). The URL is printed to console and logs.

## Dashboard Sections

### Status Bar
- Daemon state: Running/Paused
- Current view: TOWN/WORLD/UNKNOWN
- Stamina level
- Idle time
- Active flow indicator

### Arms Race Panel
- Current event name and time remaining
- Day in 7-day cycle
- **Check Score button**: Opens Arms Race panel in-game, OCRs current points, displays:
  - Current points
  - Chest 3 target
  - Remaining points to Chest 3 (or "Complete!" if reached)
  - "Checked X ago" timestamp

### Flow Control Grid
- All 25+ flows with status indicators
- Click to trigger any flow manually
- Shows last run time and cooldown state
- Color coding: Critical (yellow), Normal (gray), Running (blue)

### Quick Actions
- Pause/Resume daemon
- Return to base view
- Apply kingdom titles
- Set zombie mode

### Config Overrides
Runtime config overrides with optional expiry. See details below.

## Config Override System

Override config values temporarily via the dashboard. Useful for:
- Enabling rally join for a limited time
- Adjusting stamina thresholds during events
- Disabling specific Arms Race automations

### How It Works

1. **Set override**: Choose value and duration (15min to permanent)
2. **Active indicator**: Orange badge shows override is active with countdown
3. **Auto-expiry**: Override reverts to default when time expires
4. **Persistence**: Overrides survive daemon restarts (stored in `data/config_overrides.json`)

### Available Configs

| Config | Type | Default | Description |
|--------|------|---------|-------------|
| `RALLY_JOIN_ENABLED` | bool | false | Auto-join rallies when handshake icon detected |
| `RALLY_IGNORE_DAILY_LIMIT` | bool | false | Click Confirm on daily limit warning |
| `ELITE_ZOMBIE_STAMINA_THRESHOLD` | int | 118 | Minimum stamina to trigger Elite Zombie |
| `ELITE_ZOMBIE_PLUS_CLICKS` | int | 5 | Times to click plus button (zombie level) |
| `ARMS_RACE_BEAST_TRAINING_ENABLED` | bool | true | Enable Beast Training automation |
| `ARMS_RACE_SOLDIER_TRAINING_ENABLED` | bool | true | Enable Soldier Training automation |
| `ARMS_RACE_ENHANCE_HERO_ENABLED` | bool | true | Enable Enhance Hero automation |
| `IDLE_THRESHOLD` | int | 300 | Seconds idle before flows trigger |
| `BAG_FLOW_COOLDOWN` | int | 1200 | Bag flow cooldown (seconds) |
| `AFK_REWARDS_COOLDOWN` | int | 3600 | AFK rewards cooldown (seconds) |
| `UNION_GIFTS_COOLDOWN` | int | 3600 | Union gifts cooldown (seconds) |
| `SOLDIER_TRAINING_COOLDOWN` | int | 300 | Soldier training cooldown (seconds) |

### Duration Options

- 15 minutes
- 30 minutes
- 1 hour
- 2 hours (default)
- 4 hours (1 Arms Race block)
- 8 hours (2 blocks)
- 24 hours
- 3 days
- 7 days
- Permanent (no expiry)

### UI Controls

**Boolean configs**: Toggle switch
- Click to flip between ON/OFF
- Select duration from dropdown before clicking

**Numeric configs**: Slider + Apply button
- Adjust slider to desired value
- Click "Apply" to set override with selected duration

**Clear override**: Click the "Clear" button next to any active override to revert to default immediately.

## API Reference

### Status Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/status` | GET | Daemon status (paused, active flows, stamina, idle) |
| `/api/events` | GET | SSE stream for live updates |
| `/api/arms-race` | GET | Current Arms Race event and timing |
| `/api/arms-race/schedule` | GET | Full 7-day schedule |
| `/api/arms-race/check-score` | POST | Check current Arms Race score (triggers flow, returns points) |

### Flow Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/flows` | GET | List all flows with status |
| `/api/flows/{name}/run` | POST | Trigger a flow |

### Control Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/pause` | POST | Pause daemon |
| `/api/resume` | POST | Resume daemon |
| `/api/return-to-base` | POST | Return to base view |

### Config Override Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/config` | GET | All configs with values and override status |
| `/api/config/{key}/override` | POST | Set override (body: `{value, duration_minutes}`) |
| `/api/config/{key}/override` | DELETE | Clear override |
| `/api/config/overrides` | GET | List active overrides only |

### Title and Zombie Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/titles` | GET | List available kingdom titles |
| `/api/titles/{name}/apply` | POST | Apply a title |
| `/api/zombie-mode` | GET | Get current zombie mode |
| `/api/zombie-mode/{mode}` | POST | Set zombie mode |

## Files

```
dashboard/
├── server.py           # FastAPI app with all endpoints
├── static/
│   └── index.html      # Dashboard UI (Alpine.js + Tailwind)

utils/
├── config_overrides.py # Override manager with JSON persistence
├── daemon_server.py    # WebSocket server (bridges dashboard to daemon)

data/
└── config_overrides.json  # Persisted overrides (auto-created)
```

## Troubleshooting

**Dashboard not loading**: Check if daemon is running. Dashboard only starts with the daemon.

**"Daemon not connected" error**: WebSocket connection to daemon failed. Restart the daemon.

**Override not taking effect**: Check the daemon logs for override messages. Ensure the config key is spelled correctly.

**Port already in use**: The dashboard auto-finds a free port. Check logs for the actual URL.
