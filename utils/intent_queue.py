"""
Intent queue - the single funnel between "something wants to happen" and the
actor that executes it.

Every action source becomes an Intent: manual web commands, on-sight
opportunities from perception, scheduled/cooldown flows, mode ticks, recovery.
The actor pops the highest-priority ADMISSIBLE intent and executes it - one at
a time, one screen, one input channel.

Design points:
- Coalesce by name: re-submitting an existing intent merges it (keeps MAX
  priority, earliest created_at for age-fair ties, merges completion hooks).
- Admission at POP time, not submit time: gates (idle, tavern guard, modes)
  are evaluated when the slot is actually free, so an intent can wait in the
  queue until it becomes runnable (this replaces the old deferred_flow_queue).
- TTL: an intent that stays inadmissible too long expires and is dropped
  (logged) - nothing waits forever on a stale sighting.
- pre_execute: re-verify hook run just before execution (e.g. "is the icon
  still on a FRESH frame?"). Returning False drops the intent without running.
- on_complete(result): completion callbacks (arms-race block latching,
  post-treasure chaining, manual-command completion events).
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("intent_queue")

# Priority bands (higher pops first). Ties broken by age (older first).
PRIO_MANUAL = 100
PRIO_RECOVERY = 90
PRIO_TIME_CRITICAL = 80   # treasure, tavern-claim-imminent, arms-race checkpoints
PRIO_ON_SIGHT = 60        # assist, cobra, sandstorm, gift box
PRIO_STAMINA = 50         # zombie rallies / stamina burns
PRIO_ROUTINE = 30         # hospital, barracks, unions, tavern, bag
PRIO_HARVEST = 20         # bubbles


@dataclass
class Intent:
    name: str
    source: str                                     # manual|opportunity|schedule|mode|recovery
    priority: int
    flow_func: Callable[..., Any] | None = None     # direct callable (adb) -> result
    flow_name: str | None = None                    # resolve via registry at pop (hot-reload safe)
    critical: bool = False
    reason: str = ""
    record_to_scheduler: bool = True
    admission: Callable[[], tuple[bool, str]] | None = None
    pre_execute: Callable[[], bool] | None = None
    on_complete: list[Callable[[Any], None]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    ttl: float = 300.0
    last_denial: str = ""                           # why admission last said no (introspection)

    @property
    def age(self) -> float:
        return time.time() - self.created_at

    @property
    def expired(self) -> bool:
        return self.age > self.ttl


class IntentQueue:
    """Lock-guarded {name: Intent} with priority/age pop and admission gates."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._intents: dict[str, Intent] = {}

    def submit(self, intent: Intent) -> str:
        """Add or coalesce. Returns 'queued' or 'coalesced'."""
        with self._lock:
            cur = self._intents.get(intent.name)
            if cur is None:
                self._intents[intent.name] = intent
                return "queued"
            # Coalesce: keep max priority, earliest age, merge hooks; refresh
            # ttl to the new intent's (a re-sighting extends the deadline).
            cur.priority = max(cur.priority, intent.priority)
            cur.ttl = max(cur.ttl, intent.ttl)
            cur.on_complete.extend(intent.on_complete)
            if intent.pre_execute is not None:
                cur.pre_execute = intent.pre_execute
            if intent.admission is not None:
                cur.admission = intent.admission
            cur.reason = intent.reason or cur.reason
            return "coalesced"

    def contains(self, name: str) -> Intent | None:
        with self._lock:
            return self._intents.get(name)

    def remove(self, name: str) -> None:
        with self._lock:
            self._intents.pop(name, None)

    def pop_best(self, mask: Callable[[Intent], bool] | None = None) -> Intent | None:
        """Remove and return the highest-priority admissible intent.

        - Expired intents are dropped (logged).
        - `mask` (mode exclusivity): intents it rejects stay queued untouched.
        - admission() False: intent stays queued (denial reason recorded).
        Ties on priority go to the OLDEST intent (starvation fairness).
        """
        with self._lock:
            # prune expired
            for name in [n for n, i in self._intents.items() if i.expired]:
                dropped = self._intents.pop(name)
                logger.info(f"INTENT EXPIRED: {dropped.name} (source={dropped.source}, "
                            f"waited {dropped.age:.0f}s > ttl {dropped.ttl:.0f}s, "
                            f"last denial: {dropped.last_denial or 'n/a'})")

            candidates = sorted(
                self._intents.values(),
                key=lambda i: (-i.priority, i.created_at),
            )

        # Admission checks OUTSIDE the queue lock (they may take other locks).
        for intent in candidates:
            if mask is not None and not mask(intent):
                continue
            if intent.admission is not None:
                try:
                    ok, why = intent.admission()
                except Exception as e:
                    ok, why = False, f"admission error: {e}"
                if not ok:
                    intent.last_denial = why
                    continue
            with self._lock:
                # re-check it wasn't consumed/removed while we were checking
                if self._intents.get(intent.name) is intent:
                    del self._intents[intent.name]
                    return intent
        return None

    def snapshot(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {"name": i.name, "source": i.source, "priority": i.priority,
                 "age_s": round(i.age, 1), "ttl": i.ttl, "reason": i.reason,
                 "last_denial": i.last_denial}
                for i in sorted(self._intents.values(), key=lambda x: -x.priority)
            ]

    def __len__(self) -> int:
        with self._lock:
            return len(self._intents)
