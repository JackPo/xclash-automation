# Automation Roadmap

This document tracks what is implemented, what is partial, and what is still missing. For system architecture and how flows work, see `../ARCHITECTURE.md` and `arms_race.md`.

## Current coverage

### Always-on automation (daemon)
- Resource harvest bubbles: corn, gold, iron, gems, cabbage, equipment (requires calibrated coordinates)
- Popups: handshake, treasure map, harvest box, AFK rewards
- Union: gifts and Union Technology donations
- Tavern: quest claim/start with scheduler-based timing
- Bag items and gift box rewards
- Hospital healing (triggered when the healing bubble is detected)
- Union War rally joining with OCR-based monster filtering
- Arms Race: Mystic Beast, Enhance Hero, Soldier Training

### Event and scheduler intelligence
- Arms Race schedule calculation and time-to-event helpers
- Pre-beast stamina claim and rally preservation
- Smart Mystic Beast target calculation with points checks
- Daily rally limit tracking with server reset handling
- VS overrides for soldier promotion and chest timing

### On-demand/manual flows
- Title management (Royal City)
- Faction trials
- Go-to-mark navigation

### Data collection
- Arms Race points logging in the last 10 minutes of each block

## Missing or partial automation

High impact:
1. City Construction event automation (Arms Race)
2. Technology Research event automation (Arms Race)
3. Daily quest reward collection
4. VIP chest and daily login rewards

Medium impact:
5. Alliance help actions beyond the handshake icon
6. Hero expedition or adventure management

Lower priority or higher risk:
7. Arena/PvP automation
8. Market trading automation
9. Proactive queue management (build/research/training)

## Suggested roadmap

Phase 1: Complete Arms Race coverage
- City Construction
- Technology Research

Phase 2: Daily rewards
- Daily quest rewards
- VIP chest and login popups
- Alliance help actions

Phase 3: Passive progression
- Hero expedition automation
- Optional proactive queueing

Phase 4: Advanced or risky automation
- Arena/PvP
- Market trading

## Related docs
- `arms_race.md` for event automation behavior
- `joining_rallies.md` for rally join details
- `KINGDOM_TITLES.md` for title management
