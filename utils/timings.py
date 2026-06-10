"""Shared UI timing constants for automation flows.

Flows previously each defined their own copies of these values; tuning a
delay meant hunting through every flow. Flows with genuinely unique
timing needs (unusual panel latency) may still define a local constant,
but common tiers live here.

All values in seconds.
"""
from __future__ import annotations

# Polling cadence for UI state checks (screenshot + template match loops)
POLL_INTERVAL = 0.3
POLL_INTERVAL_SLOW = 0.5

# How long to poll before giving up on a UI element appearing
POLL_TIMEOUT_SHORT = 3.0
POLL_TIMEOUT_MEDIUM = 5.0
POLL_TIMEOUT_LONG = 10.0

# Delay after a tap so the UI can react
CLICK_DELAY_FAST = 0.3
CLICK_DELAY = 0.5
CLICK_DELAY_SLOW = 1.0

# Delay for full-screen transitions (panel open/close, view switch)
SCREEN_TRANSITION_DELAY_FAST = 1.0
SCREEN_TRANSITION_DELAY = 1.5
