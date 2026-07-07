#!/usr/bin/env python3
"""
Replay a captured action session — re-issue the recorded command stream.

Reads a session's `actions.jsonl` (written by utils/action_capture.py) and
re-dispatches each tap/swipe/key_event/zoom/arrow through ADBHelper / the Win32
senders, honoring the inter-action delays so timing matches the original run.

    python -m scripts.replay_actions --session latest
    python -m scripts.replay_actions --session 20260707_143001 --source-filter flow:python_rally
    python -m scripts.replay_actions --session latest --max-actions 10 --dry-run

FIDELITY (read this): this is OPEN-LOOP coordinate replay with NO visual
verification. It reliably reproduces only SHORT, DETERMINISTIC sequences started
from the SAME screen as the capture. Any game-state divergence (a popup, a timer,
a different current view, animation mid-capture) desyncs coordinate taps after a
few actions. Use it to reproduce a short flow segment for debugging or to
stress-test the input path — NOT as a general macro/bot engine. `--max-actions`
defaults small on purpose.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def _capture_dir() -> Path:
    try:
        from config import ACTION_CAPTURE_DIR
        return PROJECT_ROOT / ACTION_CAPTURE_DIR
    except Exception:
        return PROJECT_ROOT / "screenshots" / "action_capture"


def _resolve_session(session: str | None) -> Path | None:
    base = _capture_dir()
    if not base.exists():
        return None
    if not session or session == "latest":
        dirs = [d for d in base.iterdir() if d.is_dir()]
        return max(dirs, key=lambda d: d.stat().st_mtime) if dirs else None
    cand = base / session
    return cand if cand.is_dir() else None


def _load_records(session_dir: Path) -> list[dict]:
    records: dict[int, dict] = {}
    for fname in ("actions.pre.jsonl", "actions.jsonl"):
        fp = session_dir / fname
        if not fp.exists():
            continue
        with open(fp, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                    records[rec["seq"]] = rec
                except Exception:
                    continue
    return [records[k] for k in sorted(records)]


def _dispatch(adb, rec: dict) -> None:
    """Re-issue one action. Raises on unknown type (caller decides)."""
    at = rec.get("action_type")
    p = rec.get("params", {})
    src = f"replay:{rec.get('source', '?')}"
    if at == "tap":
        adb.tap(int(p["x"]), int(p["y"]), source=src)
    elif at == "swipe":
        adb.swipe(int(p["x1"]), int(p["y1"]), int(p["x2"]), int(p["y2"]),
                  duration=int(p.get("duration", 300)), source=src)
    elif at == "key_event":
        adb.key_event(int(p["keycode"]), source=src)
    elif at == "zoom":
        from utils.send_zoom import send_zoom
        send_zoom(str(p["direction"]))
    elif at == "arrow":
        from utils.send_arrow_proper import send_arrow
        send_arrow(str(p["direction"]))
    else:
        raise ValueError(f"unknown action_type: {at}")


def main() -> int:
    ap = argparse.ArgumentParser(description="Replay a captured action session.")
    ap.add_argument("--session", default="latest", help="session id or 'latest'")
    ap.add_argument("--source-filter", default=None, help="only actions whose source contains this")
    ap.add_argument("--since", type=float, default=None, help="only actions with ts >= this (epoch)")
    ap.add_argument("--until", type=float, default=None, help="only actions with ts <= this (epoch)")
    ap.add_argument("--speed", type=float, default=1.0, help="time compression (2.0 = twice as fast)")
    ap.add_argument("--max-actions", type=int, default=25, help="safety cap (default 25)")
    ap.add_argument("--max-delay", type=float, default=5.0, help="clamp inter-action wait to this many seconds")
    ap.add_argument("--dry-run", action="store_true", help="print the plan, send nothing")
    args = ap.parse_args()

    sd = _resolve_session(args.session)
    if sd is None:
        print(f"No session found for '{args.session}' under {_capture_dir()}")
        return 1

    recs = _load_records(sd)
    if args.source_filter:
        recs = [r for r in recs if args.source_filter.lower() in str(r.get("source", "")).lower()]
    if args.since is not None:
        recs = [r for r in recs if (r.get("ts") or 0) >= args.since]
    if args.until is not None:
        recs = [r for r in recs if (r.get("ts") or 0) <= args.until]

    if not recs:
        print("No matching actions.")
        return 1

    if len(recs) > args.max_actions:
        print(f"WARNING: {len(recs)} actions matched; capping to --max-actions={args.max_actions}. "
              f"Open-loop replay desyncs on long sequences — raise the cap only if you know the screen matches.")
        recs = recs[:args.max_actions]

    print(f"Session {sd.name}: replaying {len(recs)} action(s), speed={args.speed}x"
          + (" [DRY RUN]" if args.dry_run else ""))

    adb = None
    if not args.dry_run:
        # Disable capture during replay so we don't recursively record the replay.
        try:
            from utils.action_capture import get_action_capture
            get_action_capture().enabled = False
        except Exception:
            pass
        from utils.adb_helper import ADBHelper
        adb = ADBHelper()

    for i, rec in enumerate(recs):
        wait = 0.0
        dbm = rec.get("delay_before_ms")
        if i > 0 and dbm:
            wait = min(max(dbm / 1000.0 / max(args.speed, 0.01), 0.0), args.max_delay)
        params = rec.get("params", {})
        line = (f"[{i+1}/{len(recs)}] +{wait:4.2f}s  #{rec.get('seq')} "
                f"{rec.get('action_type'):9s} {params}  <- {rec.get('source')}")
        print(line)
        if args.dry_run:
            continue
        if wait:
            time.sleep(wait)
        try:
            _dispatch(adb, rec)
        except Exception as e:
            print(f"   ! dispatch failed: {e}")

    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
