"""
Tests for the standalone zombie-rally gate: what SHOULD happen.

The rule (user's design, unchanged): rally zombies while confirmed stamina >=
threshold (118) - i.e. burn excess back down to ~120 - then STOP. At most one
rally per 90s. The 2026-07-11 incident violated this via a misread stamina
input and a never-enforced cooldown; these tests pin the gate itself.
"""
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from scripts.icon_daemon import IconDaemon


def make_gate(idle_threshold: float = 30.0):
    """Bare object carrying just what _standalone_zombie_admissible needs."""
    d = types.SimpleNamespace(
        IDLE_THRESHOLD=idle_threshold,
        ZOMBIE_RALLY_COOLDOWN=IconDaemon.ZOMBIE_RALLY_COOLDOWN,
        _last_standalone_zombie_rally=0.0,
    )
    d.admissible = lambda *a, **k: IconDaemon._standalone_zombie_admissible(d, *a, **k)
    return d


THRESHOLD = 118


def test_rallies_when_above_threshold_and_idle():
    g = make_gate()
    assert g.admissible(True, 200, THRESHOLD, idle_secs=600, now=1000.0) is True


def test_stops_below_threshold():
    """Burn-down endpoint: 117 stamina -> NO rally. This is 'back down to ~120'."""
    g = make_gate()
    assert g.admissible(True, 117, THRESHOLD, idle_secs=600, now=1000.0) is False


def test_exactly_at_threshold_rallies():
    g = make_gate()
    assert g.admissible(True, 118, THRESHOLD, idle_secs=600, now=1000.0) is True


def test_unconfirmed_stamina_never_rallies():
    """No confirmed reading = no rally, regardless of the cached number."""
    g = make_gate()
    assert g.admissible(False, 500, THRESHOLD, idle_secs=600, now=1000.0) is False
    assert g.admissible(True, None, THRESHOLD, idle_secs=600, now=1000.0) is False


def test_user_active_never_rallies():
    g = make_gate(idle_threshold=30.0)
    assert g.admissible(True, 500, THRESHOLD, idle_secs=5, now=1000.0) is False


def test_cooldown_enforced_90s():
    """At most one rally per 90s - the never-enforced rule from the incident."""
    g = make_gate()
    g._last_standalone_zombie_rally = 1000.0
    assert g.admissible(True, 500, THRESHOLD, idle_secs=600, now=1015.0) is False   # 15s later (incident cadence)
    assert g.admissible(True, 500, THRESHOLD, idle_secs=600, now=1089.0) is False   # 89s
    assert g.admissible(True, 500, THRESHOLD, idle_secs=600, now=1090.0) is True    # 90s


def test_burn_down_sequence_stops_at_threshold():
    """Simulated burn from the REAL max (stamina > 200 is impossible):
    200 -> 100. Rallies while >=118, stops after."""
    g = make_gate()
    stamina = 200
    now = 0.0
    rallies = 0
    for _ in range(40):
        now += 91.0
        if g.admissible(True, stamina, THRESHOLD, idle_secs=600, now=now):
            rallies += 1
            g._last_standalone_zombie_rally = now
            stamina -= 20
    assert stamina == 100          # stopped just below threshold (burn to ~120 rule)
    assert rallies == 5            # 200,180,160,140,120 - then STOPPED
