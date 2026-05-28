"""
OCR-friendly time-remaining parser.

Used by the City Construction and Technology Research speedup flows to read
queue cooldown timers off the game UI. The function is tolerant of common OCR
artifacts:

  - Optional "Time:" / "Time Remaining:" prefix (any case, any whitespace).
  - Trailing colon (e.g. "1d 14:00:") — OCR sometimes captures the seconds
    separator but drops the seconds digits. We treat such partial captures as
    the truncated value rather than rejecting them, which is the correct
    behavior for picking the *smaller* of two queues to speed up.

Supported formats (whichever matches first wins):
  - Xd HH:MM:SS  -> seconds
  - Xd HH:MM     -> seconds
  - HH:MM:SS     -> seconds
  - HH:MM        -> seconds

Returns the parsed time in seconds, or None if no pattern matches.
"""
from __future__ import annotations

import logging
import re

logger = logging.getLogger(__name__)


_PREFIX_RE = re.compile(r"Time(\s+Remaining)?\s*:?\s*", re.IGNORECASE)


def parse_time_remaining(text: str) -> int | None:
    if not text:
        return None

    text = text.strip()
    text = _PREFIX_RE.sub("", text, count=1)
    # OCR sometimes appends an extra ':' when it sees the seconds separator
    # but can't read the digits after it. Strip trailing colons/whitespace so
    # the HH:MM patterns can match. Without this, "1d 14:00:" parses as None,
    # which makes the smaller-queue chooser fall back to the bigger queue.
    text = text.rstrip(":").rstrip()

    # Pattern 1: Xd HH:MM:SS
    m = re.search(r"(\d+)d\s*(\d{1,2}):(\d{2}):(\d{2})", text)
    if m:
        d, h, mn, s = (int(x) for x in m.groups())
        return d * 86400 + h * 3600 + mn * 60 + s

    # Pattern 2: Xd HH:MM (no seconds). The negative lookahead is (?!\d) so
    # we don't accidentally swallow part of a larger number — a trailing
    # colon is fine (it just means the seconds were dropped by OCR).
    m = re.search(r"(\d+)d\s*(\d{1,2}):(\d{2})(?!\d)", text)
    if m:
        d, h, mn = (int(x) for x in m.groups())
        return d * 86400 + h * 3600 + mn * 60

    # Pattern 3: HH:MM:SS
    m = re.search(r"(\d{1,2}):(\d{2}):(\d{2})", text)
    if m:
        h, mn, s = (int(x) for x in m.groups())
        return h * 3600 + mn * 60 + s

    # Pattern 4: HH:MM
    m = re.search(r"(\d{1,2}):(\d{2})(?!\d)", text)
    if m:
        h, mn = (int(x) for x in m.groups())
        return h * 3600 + mn * 60

    logger.warning(f"Could not parse time from: {text!r}")
    return None
