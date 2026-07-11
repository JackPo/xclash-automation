#!/usr/bin/env python3
"""
Log-based behavior verifier: parse a daemon log over a time window [A, B] and
assert behavioral invariants. This is the "prove the fix held from time point A
to time point B" tool - run it after any incident or fix.

Usage:
    python scripts/verify_daemon_log.py                          # latest log, whole file
    python scripts/verify_daemon_log.py --log logs/daemon_X.log
    python scripts/verify_daemon_log.py --from "14:00" --to "16:30"

Invariants checked (each PASS/FAIL with violating lines):
  ZOMBIE-STAMINA-CONSISTENT  every zombie INTENT POP's stamina= must be within
                             +/-TOLERANCE of the nearest status-line stamina
                             (catches the 511-vs-11 divergence of 2026-07-11)
  ZOMBIE-THRESHOLD           no zombie pop while nearest status stamina < 118
  ZOMBIE-CADENCE             no two zombie rally FLOW STARTs within 90s
  STAMINA-QUARANTINE         a quarantined value must never appear as the
                             confirmed value within the window
  RES-CADENCE                [RES-CHECK]/Resolution lines gap <= 5 min while
                             unpaused (pause windows excluded)
  RES-NO-FAKE-FIX            no "Resolution fixed!" with 4K score > 0.08
"""
from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}),\d+")
STATUS_RE = re.compile(r"Stamina:(\d+) ")
POP_RE = re.compile(r"INTENT POP: (elite_zombie|zombie_attack_\w+).*stamina=(\d+)")
FLOWSTART_RE = re.compile(r"(?:CRITICAL )?FLOW START: (elite_zombie|zombie_attack_\w+)\b")
QUAR_RE = re.compile(r"\[STAMINA\] quarantined implausible jump \S+ -> (\d+)")
CONF_RE = re.compile(r"\[STAMINA\] confirmed (\d+)")
RESLINE_RE = re.compile(r"\[RES-CHECK\]|Resolution (drift|fixed|still wrong|check failed)")
RESFIX_RE = re.compile(r"Resolution fixed! 4K=([0-9.]+)")
PAUSED_RE = re.compile(r"\] PAUSED \(")

STAMINA_TOLERANCE = 30       # pop stamina vs nearest status stamina
ZOMBIE_THRESHOLD = 118
ZOMBIE_COOLDOWN_S = 90
STAMINA_HARD_CAP = 200      # user-confirmed: stamina > 200 is impossible
RES_MAX_GAP_S = 300          # 60s cadence + slack
PAUSE_SLACK_S = 60           # around PAUSED markers


def parse_ts(line: str) -> datetime | None:
    m = TS_RE.match(line)
    return datetime.strptime(m.group(1), "%Y-%m-%d %H:%M:%S") if m else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=None)
    ap.add_argument("--from", dest="t_from", default=None, help="HH:MM (today's date assumed)")
    ap.add_argument("--to", dest="t_to", default=None, help="HH:MM")
    args = ap.parse_args()

    log = Path(args.log) if args.log else max(Path("logs").glob("daemon_*.log"), key=lambda p: p.stat().st_mtime)
    lines = log.read_text(encoding="utf-8", errors="ignore").splitlines()

    # Window filter
    events = []
    for ln in lines:
        ts = parse_ts(ln)
        if ts is None:
            continue
        events.append((ts, ln))
    if not events:
        print(f"no timestamped lines in {log}")
        return 2
    day = events[0][0].date()
    t_from = datetime.combine(day, datetime.strptime(args.t_from, "%H:%M").time()) if args.t_from else events[0][0]
    t_to = datetime.combine(day, datetime.strptime(args.t_to, "%H:%M").time()) if args.t_to else events[-1][0]
    events = [(ts, ln) for ts, ln in events if t_from <= ts <= t_to]

    status = [(ts, int(m.group(1))) for ts, ln in events if (m := STATUS_RE.search(ln))]
    pops = [(ts, m.group(1), int(m.group(2)), ln) for ts, ln in events if (m := POP_RE.search(ln))]
    starts = [(ts, m.group(1)) for ts, ln in events if (m := FLOWSTART_RE.search(ln))]
    quars = [(ts, int(m.group(1))) for ts, ln in events if (m := QUAR_RE.search(ln))]
    confs = [(ts, int(m.group(1))) for ts, ln in events if (m := CONF_RE.search(ln))]
    res_lines = [ts for ts, ln in events if RESLINE_RE.search(ln)]
    res_fixes = [(ts, float(m.group(1)), ln) for ts, ln in events if (m := RESFIX_RE.search(ln))]
    pauses = [ts for ts, ln in events if PAUSED_RE.search(ln)]

    failures: dict[str, list[str]] = {}

    def nearest_status(ts: datetime) -> int | None:
        best, bestdt = None, timedelta(seconds=11)
        for sts, val in status:
            d = abs(sts - ts)
            if d < bestdt:
                best, bestdt = val, d
        return best

    # ZOMBIE-STAMINA-CONSISTENT + ZOMBIE-THRESHOLD + STAMINA-IMPOSSIBLE
    v1, v2, v0 = [], [], []
    for ts, name, pop_stam, ln in pops:
        near = nearest_status(ts)
        if pop_stam > STAMINA_HARD_CAP:
            v0.append(f"{ts} {name} pop stamina={pop_stam} > hard cap {STAMINA_HARD_CAP} (impossible)")
        if near is not None and abs(near - pop_stam) > STAMINA_TOLERANCE:
            v1.append(f"{ts} {name} pop stamina={pop_stam} but status={near}")
        if near is not None and near < ZOMBIE_THRESHOLD:
            v2.append(f"{ts} {name} popped while real stamina={near} < {ZOMBIE_THRESHOLD}")
    for ts, val in status:
        if val > STAMINA_HARD_CAP:
            v0.append(f"{ts} status stamina={val} > hard cap {STAMINA_HARD_CAP} (impossible)")
    if v0: failures["STAMINA-IMPOSSIBLE"] = v0
    if v1: failures["ZOMBIE-STAMINA-CONSISTENT"] = v1
    if v2: failures["ZOMBIE-THRESHOLD"] = v2

    # ZOMBIE-CADENCE
    v3 = []
    for (t1, n1), (t2, n2) in zip(starts, starts[1:]):
        gap = (t2 - t1).total_seconds()
        if gap < ZOMBIE_COOLDOWN_S:
            v3.append(f"{t2} {n2} started {gap:.0f}s after {n1} (min {ZOMBIE_COOLDOWN_S}s)")
    if v3: failures["ZOMBIE-CADENCE"] = v3

    # STAMINA-QUARANTINE: quarantined value must not become confirmed soon after
    v4 = []
    for qts, qval in quars:
        for cts, cval in confs:
            if 0 <= (cts - qts).total_seconds() <= 60 and cval == qval:
                v4.append(f"{qts} quarantined {qval} but confirmed at {cts}")
    if v4: failures["STAMINA-QUARANTINE"] = v4

    # RES-CADENCE (exclude gaps that overlap a pause marker +/- slack)
    v5 = []
    for t1, t2 in zip(res_lines, res_lines[1:]):
        gap = (t2 - t1).total_seconds()
        if gap > RES_MAX_GAP_S:
            paused_inside = any(t1 - timedelta(seconds=PAUSE_SLACK_S) <= p <= t2 + timedelta(seconds=PAUSE_SLACK_S) for p in pauses)
            if not paused_inside:
                v5.append(f"resolution check gap {gap/60:.1f} min ({t1} -> {t2}) while unpaused")
    if v5: failures["RES-CADENCE"] = v5

    # RES-NO-FAKE-FIX
    v6 = [f"{ts} {ln.strip()}" for ts, sc, ln in res_fixes if sc > 0.08]
    if v6: failures["RES-NO-FAKE-FIX"] = v6

    # Report
    checks = ["STAMINA-IMPOSSIBLE", "ZOMBIE-STAMINA-CONSISTENT", "ZOMBIE-THRESHOLD", "ZOMBIE-CADENCE",
              "STAMINA-QUARANTINE", "RES-CADENCE", "RES-NO-FAKE-FIX"]
    print(f"log={log.name} window={t_from.time()}..{t_to.time()} "
          f"pops={len(pops)} rally_starts={len(starts)} status_samples={len(status)} "
          f"res_lines={len(res_lines)} quarantines={len(quars)}")
    ok = True
    for c in checks:
        if c in failures:
            ok = False
            print(f"FAIL {c} ({len(failures[c])} violations)")
            for v in failures[c][:5]:
                print(f"     {v}")
        else:
            print(f"PASS {c}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
