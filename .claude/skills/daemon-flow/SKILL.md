---
name: daemon-flow
description: Control daemon via WebSocket - run flows, change zombie mode, apply titles. Use for "run flow", "zombie attack", "iron zombie", "gold zombie", "clear zombie mode", "switch to elite", "apply title", "minister of construction", "get status", "stamina".
allowed-tools: Bash
---

# Daemon WebSocket Control

Control the icon daemon via WebSocket commands using `daemon_cli.py`.

## Quick Reference

| Action | Command |
|--------|---------|
| Run a flow | `python scripts/daemon_cli.py run_flow elite_zombie` |
| Zombie attack (iron) | `python scripts/daemon_cli.py run_zombie_attack iron_mine` |
| Set zombie mode | `python scripts/daemon_cli.py set_zombie_mode iron_mine 4` |
| Clear zombie mode | `python scripts/daemon_cli.py clear_zombie_mode` |
| Apply title | `python scripts/daemon_cli.py apply_title ministry_of_construction` |
| Get status | `python scripts/daemon_cli.py status` |

---

## Zombie Attack Commands

Run zombie attacks on-demand (independent of Beast Training):

```bash
# Attack iron mine zombie
python scripts/daemon_cli.py run_zombie_attack iron_mine

# Attack gold zombie with 15 plus clicks
python scripts/daemon_cli.py run_zombie_attack gold --plus 15

# Attack food zombie
python scripts/daemon_cli.py run_zombie_attack food
```

**Types**: `iron_mine`, `gold`, `food`

---

## Zombie Mode (Beast Training)

Change zombie mode for Beast Training Arms Race. By default, Beast Training uses elite zombie rallies. Set zombie mode to use regular zombie attacks instead.

```bash
# Set iron_mine mode for 4 hours
python scripts/daemon_cli.py set_zombie_mode iron_mine 4

# Set gold mode for 24 hours
python scripts/daemon_cli.py set_zombie_mode gold 24

# Check current mode and expiry
python scripts/daemon_cli.py get_zombie_mode

# Clear mode (revert to elite zombie rallies)
python scripts/daemon_cli.py clear_zombie_mode
```

**Modes**: `elite` (default), `iron_mine`, `gold`, `food`

**How it works**:
- Elite: 20 stamina/rally, 2000 points/rally (15 rallies for 30k)
- Zombie: 10 stamina/attack, 1000 points/attack (30 attacks for 30k)
- Mode auto-expires after set duration, reverting to elite

---

## Run Flows

Trigger any registered daemon flow:

```bash
python scripts/daemon_cli.py run_flow <flow_name>
```

| Flow | Critical | Description |
|------|----------|-------------|
| `tavern_quest` | Yes | Tavern quests (My Quests tab) |
| `bag_flow` | Yes | Bag claim (Special + Hero + Resources) |
| `elite_zombie` | No | Elite zombie rally |
| `soldier_training` | Yes | Soldier training (collect + train) |
| `treasure_map` | Yes | Treasure map digging |
| `healing` | No | Hospital healing |
| `union_gifts` | No | Union rally gifts |
| `stamina_claim` | No | Claim free stamina |

Full list: `python scripts/daemon_cli.py list_flows`

---

## Title Management

Apply kingdom titles at marked Royal City. **Pre-condition:** Must be at Royal City with star icon visible (use `go_to_mark_flow` first).

```bash
# Apply a title
python scripts/daemon_cli.py apply_title ministry_of_construction

# List available titles
python scripts/daemon_cli.py list_titles
```

**Available titles:**
| Key | Buffs |
|-----|-------|
| `ministry_of_construction` | Building +50%, Tech Research +25% |
| `minister_of_science` | Tech Research +50%, Building +25% |
| `marshall` | Barrack Capacity +20%, Soldier Training +20% |
| `minister_of_health` | Hospital +20%, Healing Speed +20% |
| `minister_of_domestic_affairs` | Food/Iron/Gold Output +100% |
| `prime_minister` | Building +20%, Tech +20%, Training +10% |

---

## Stamina Commands

```bash
# Read current stamina (fresh OCR)
python scripts/daemon_cli.py read_stamina

# Check inventory
python scripts/daemon_cli.py get_stamina_inventory

# Use stamina items
python scripts/daemon_cli.py use_stamina --claim-free
python scripts/daemon_cli.py use_stamina --use-10 3 --use-50 1

# Get rally status with optimal stamina strategy
python scripts/daemon_cli.py get_rally_status
```

---

## Rally Target Commands (Beast Training)

```bash
# Show status + optimal stamina strategy
python scripts/daemon_cli.py get_rally_status

# "I did 5 rallies manually"
python scripts/daemon_cli.py set_rally_count 5

# "Do 12 total this block"
python scripts/daemon_cli.py set_rally_target 12

# "Do 7 more from current count"
python scripts/daemon_cli.py add_rallies 7
```

---

## Other Commands

```bash
# Get daemon status
python scripts/daemon_cli.py status

# Get full state
python scripts/daemon_cli.py get_state

# Get current view
python scripts/daemon_cli.py get_view

# Return to base view
python scripts/daemon_cli.py return_to_base

# Pause/resume daemon loop
python scripts/daemon_cli.py pause
python scripts/daemon_cli.py resume

# Watch live events (Ctrl+C to stop)
python scripts/daemon_cli.py watch
```

---

## IMPORTANT: Daemon Management

**NEVER start the icon daemon.** The user manages daemon startup.

Claude can ONLY:
- Trigger flows via WebSocket (when daemon is running)
- Check daemon status
- Kill rogue processes if asked

```bash
# Check if daemon is running
powershell -Command "Get-Process python* | Format-Table Id, ProcessName, StartTime"

# Check daemon log
powershell -Command "Get-Content 'C:\Users\mail\xclash\logs\current_daemon.log' -Tail 20"
```
