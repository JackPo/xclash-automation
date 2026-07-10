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
    views: set[ViewState] | None   # which views this target can appear in; None = ANY view (incl. CHAT/UNKNOWN)
    fn: MatcherFn
    hits: int = field(default=0, compare=False)


@dataclass
class TrackerSpec:
    """A stateful sampler (vote histories, stamina OCR) - unlike DetectorSpec
    these MUTATE state via sink(), so perception must be their ONLY caller.

    Sampling gates (all must pass):
    - not busy_fn(): never sample while the actor is executing a flow - mid-flow
      frames (half-open panels that still classify TOWN) would poison votes
    - view in views (None = any)
    - min_interval elapsed since last sample - vote windows are time-windows in
      disguise (10 readings @ 2s = 20s debounce); sampling at tick rate would
      collapse them
    - frame age < max_frame_age: don't feed a stale pre-flow frame after resume
    """
    name: str
    views: set[ViewState] | None
    min_interval: float
    fn: Callable[[Any], Any]           # frame -> value (None = skip sink)
    sink: Callable[[Any], None]        # receives the value; runs on perception thread
    max_frame_age: float = 1.5
    last_sample: float = field(default=0.0, compare=False)
    samples: int = field(default=0, compare=False)


@dataclass
class SpecReading:
    """The last result of running a spec, whether or not it matched - the
    status line needs scores for ABSENT icons, which the board can't hold."""
    found: bool
    score: float
    center: tuple[int, int] | None
    ts: float


class PerceptionState:
    """Thread-safe snapshot of everything perception knows: last reading per
    spec (found/score/center/ts) and the current view classification. Extended
    in later stages with vote histories and stamina. Written only by the
    perception thread; read by the actor for telemetry and decisions."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._readings: dict[str, SpecReading] = {}
        self._view: ViewState = ViewState.UNKNOWN
        self._view_ts: float = 0.0
        self._view_since: float = 0.0   # when the CURRENT view classification began

    def record(self, name: str, found: bool, score: float,
               center: tuple[int, int] | None) -> None:
        with self._lock:
            self._readings[name] = SpecReading(found, score, center, time.time())

    def get(self, name: str, max_age: float | None = None) -> SpecReading | None:
        with self._lock:
            r = self._readings.get(name)
            if r is None:
                return None
            if max_age is not None and (time.time() - r.ts) > max_age:
                return None
            return r

    def score_of(self, name: str, default: float = 1.0, max_age: float = 10.0) -> float:
        """Last score for the status line; `default` when never/staleley scanned."""
        r = self.get(name, max_age=max_age)
        return r.score if r is not None else default

    def set_view(self, view: ViewState) -> None:
        with self._lock:
            now = time.time()
            if view != self._view:
                self._view_since = now
            self._view = view
            self._view_ts = now

    @property
    def view(self) -> ViewState:
        with self._lock:
            return self._view

    def view_info(self) -> tuple[ViewState, float, float]:
        """(view, seconds since classified, seconds the view has persisted)."""
        with self._lock:
            now = time.time()
            return self._view, now - self._view_ts, now - self._view_since


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
        state: PerceptionState | None = None,
        paused_fn: Callable[[], bool] | None = None,  # daemon pause: no heartbeat captures
        trackers: list[TrackerSpec] | None = None,
        busy_fn: Callable[[], bool] | None = None,     # actor executing a flow -> suppress trackers
    ) -> None:
        super().__init__(daemon=True, name="OpportunityDetector")
        self.bus = bus
        self.board = board
        self.specs = specs
        self.win = win
        self.tick_interval = tick_interval
        self.heartbeat_after = heartbeat_after
        self.state = state if state is not None else PerceptionState()
        self.paused_fn = paused_fn
        self.trackers = trackers if trackers is not None else []
        self.busy_fn = busy_fn
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
            # NEVER while paused: paused means zero captures, zero game touch.
            if (self.win is not None and self.bus.age > self.heartbeat_after
                    and not (self.paused_fn is not None and self.paused_fn())):
                try:
                    self.win.get_screenshot_cv2()
                except Exception:
                    time.sleep(0.5)
            return

        frame, ts = item
        self._last_ts = ts
        self.ticks += 1

        # Classify the view ONCE per frame; always record it (recovery and
        # chat-stuck logic need CHAT/UNKNOWN persistence, not just TOWN/WORLD).
        view, _score = detect_view(frame)
        self.last_view = getattr(view, "value", str(view))
        self.state.set_view(view)

        for spec in self.specs:
            # views=None -> runs on ANY frame (e.g. handshake, state monitors);
            # otherwise only when the frame's view matches.
            if spec.views is not None and view not in spec.views:
                continue
            try:
                found, score, center = spec.fn(frame)
            except Exception as e:
                logger.debug(f"DETECTOR: spec {spec.name} error: {e}")
                continue
            # Record EVERY reading (found or not) - the status line reports
            # scores for absent icons; the board only gets actual sightings.
            self.state.record(spec.name, found, score, center)
            if found:
                spec.hits += 1
                self.board.sighting(spec.name, center, score)
                logger.debug(f"DETECTOR: sighted {spec.name} score={score:.4f} at {center}")

        # Stateful trackers (vote histories, stamina OCR): sample only on
        # fresh, non-busy frames at each tracker's own cadence.
        if self.trackers and not (self.busy_fn is not None and self.busy_fn()):
            now = time.time()
            frame_age = now - ts
            for tr in self.trackers:
                if tr.views is not None and view not in tr.views:
                    continue
                if frame_age > tr.max_frame_age:
                    continue
                if (now - tr.last_sample) < tr.min_interval:
                    continue
                tr.last_sample = now
                try:
                    value = tr.fn(frame)
                    if value is not None:
                        tr.sink(value)
                        tr.samples += 1
                except Exception as e:
                    logger.debug(f"DETECTOR: tracker {tr.name} error: {e}")

        # Pace ourselves: never rescan faster than tick_interval even when
        # frames pour in (flows can capture 5+/s).
        time.sleep(self.tick_interval)
