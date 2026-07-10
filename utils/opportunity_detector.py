"""
Continuous opportunity detection - the detector side of the detect/act split.

Architecture (one screen + one input channel => detection parallelizes, action
serializes): a background DetectorThread consumes the newest frame from the
FrameBus (published by every capture anywhere in the process), classifies the
frame's view ONCE, then runs only the view-appropriate speed-critical matchers
and records sightings on an OpportunityBoard. It never taps and is never
blocked by flows - so an icon that appears WHILE a flow runs is on the board
the moment the actor (main loop) is free, instead of being missed entirely.

The main loop consumes the board at the same code sites (and with the same
mode/cooldown gates) where it used to inline-match, and flows still re-verify
on execution - a slightly stale center can never misfire a click.
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from utils.frame_bus import FrameBus
from utils.view_state_detector import detect_view, ViewState

logger = logging.getLogger("opportunity_detector")

# A spec's matcher: frame -> (found, score, center|None)
MatcherFn = Callable[[Any], tuple[bool, float, tuple[int, int] | None]]


@dataclass
class Opportunity:
    name: str
    center: tuple[int, int] | None
    score: float
    first_seen: float
    last_seen: float


@dataclass
class DetectorSpec:
    name: str
    views: set[ViewState]      # which views this target can appear in
    fn: MatcherFn
    hits: int = field(default=0, compare=False)


class OpportunityBoard:
    """Lock-guarded {name: Opportunity}. Sightings refresh last_seen; stale
    entries (not re-sighted within ttl) simply stop being 'fresh'."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._opps: dict[str, Opportunity] = {}

    def sighting(self, name: str, center: tuple[int, int] | None, score: float) -> None:
        now = time.time()
        with self._lock:
            cur = self._opps.get(name)
            if cur is not None and (now - cur.last_seen) < 10.0:
                cur.center = center
                cur.score = score
                cur.last_seen = now
            else:
                self._opps[name] = Opportunity(name, center, score, now, now)

    def get_fresh(self, name: str, ttl: float = 3.0) -> Opportunity | None:
        """The opportunity if it was sighted within the last `ttl` seconds."""
        with self._lock:
            opp = self._opps.get(name)
            if opp is not None and (time.time() - opp.last_seen) <= ttl:
                return opp
            return None

    def consume(self, name: str) -> None:
        """Remove after acting so the actor doesn't double-fire on one sighting."""
        with self._lock:
            self._opps.pop(name, None)

    def snapshot(self) -> dict[str, dict[str, Any]]:
        now = time.time()
        with self._lock:
            return {
                n: {"center": o.center, "score": round(o.score, 4),
                    "age_s": round(now - o.last_seen, 1)}
                for n, o in self._opps.items()
            }


class DetectorThread(threading.Thread):
    """Continuously classify the newest frame and scan view-appropriate specs.

    Read-only: never taps, never navigates. GPU/template matching is
    thread-safe (gpu_lock + cache_lock in template_matcher); capture via the
    shared WindowsScreenshotHelper is serialized by its class lock.
    """

    def __init__(
        self,
        bus: FrameBus,
        board: OpportunityBoard,
        specs: list[DetectorSpec],
        win: Any = None,               # WindowsScreenshotHelper for heartbeat capture
        tick_interval: float = 0.5,
        heartbeat_after: float = 2.0,  # self-capture if the bus goes stale this long
    ) -> None:
        super().__init__(daemon=True, name="OpportunityDetector")
        self.bus = bus
        self.board = board
        self.specs = specs
        self.win = win
        self.tick_interval = tick_interval
        self.heartbeat_after = heartbeat_after
        self._stop = threading.Event()
        self._last_ts = 0.0
        self.ticks = 0
        self.last_view: str = "?"

    def stop(self) -> None:
        self._stop.set()

    def run(self) -> None:
        logger.info(f"DETECTOR: started ({len(self.specs)} specs, tick={self.tick_interval}s)")
        while not self._stop.is_set():
            try:
                self._tick()
            except Exception as e:
                # Detection is best-effort; log and keep going.
                logger.warning(f"DETECTOR: tick error: {e}")
                time.sleep(1.0)

    def _tick(self) -> None:
        item = self.bus.wait_for_frame(newer_than=self._last_ts, timeout=self.tick_interval)
        if item is None:
            # Nothing captured recently anywhere in the process (loop asleep,
            # no flow running). Heartbeat: grab a frame ourselves - the publish
            # hook feeds it back through the bus for us and any other consumer.
            if self.win is not None and self.bus.age > self.heartbeat_after:
                try:
                    self.win.get_screenshot_cv2()
                except Exception:
                    time.sleep(0.5)
            return

        frame, ts = item
        self._last_ts = ts
        self.ticks += 1

        view, _score = detect_view(frame)
        self.last_view = getattr(view, "value", str(view))
        if view not in (ViewState.TOWN, ViewState.WORLD):
            return  # menus / chat / unknown: none of our targets live there

        for spec in self.specs:
            if view not in spec.views:
                continue
            try:
                found, score, center = spec.fn(frame)
            except Exception as e:
                logger.debug(f"DETECTOR: spec {spec.name} error: {e}")
                continue
            if found:
                spec.hits += 1
                self.board.sighting(spec.name, center, score)
                logger.debug(f"DETECTOR: sighted {spec.name} score={score:.4f} at {center}")

        # Pace ourselves: never rescan faster than tick_interval even when
        # frames pour in (flows can capture 5+/s).
        time.sleep(self.tick_interval)
