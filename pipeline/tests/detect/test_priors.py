import pytest

from flopstats.detect.priors import MatchEvent, window_priors
from flopstats.video.timesync import SyncResult

SYNC = SyncResult(kickoff_offset_s=300.0, second_half_offset_s=3900.0, status="ok")


def _windows(start, stop, step=10, length=20):
    return [(s, s + length) for s in range(start, stop, step)]


def test_prior_peaks_at_event_and_decays():
    # Card for simulation in minute 20 -> clock ~19:30 -> video 300 + 1170 = 1470.
    ev = MatchEvent(minute=20, extra_minute=None, type="Card", detail="Yellow Card", comments="Simulation")
    wins = [(1460, 1480), (1500, 1520), (1530, 1550), (1560, 1580), (1600, 1620)]
    p = window_priors([ev], [], SYNC, wins)
    assert p[0] == 1.0  # contains the event
    assert p[1] == 1.0  # 30 s away
    assert p[2] == pytest.approx(0.5)  # 60 s away: halfway between 30 and 90
    assert p[3] == pytest.approx(0.0, abs=1e-9)  # 90 s away
    assert p[4] == 0.0


def test_prior_event_types():
    wins = [(1460, 1480)]
    at = dict(minute=20, extra_minute=None)
    boosts = {
        "penalty": MatchEvent(type="Goal", detail="Penalty", comments=None, **at),
        "missed penalty": MatchEvent(type="Goal", detail="Missed Penalty", comments=None, **at),
        "var": MatchEvent(type="Var", detail="Penalty cancelled", comments=None, **at),
        "injury sub": MatchEvent(type="subst", detail="Substitution 1", comments="Injury", **at),
        "foul card": MatchEvent(type="Card", detail="Yellow Card", comments="Foul", **at),
    }
    for name, ev in boosts.items():
        assert window_priors([ev], [], SYNC, wins) == [1.0], name
    none = {
        "normal goal": MatchEvent(type="Goal", detail="Normal Goal", comments=None, **at),
        "tactical sub": MatchEvent(type="subst", detail="Substitution 2", comments=None, **at),
        "dissent card": MatchEvent(type="Card", detail="Yellow Card", comments="Argument", **at),
    }
    for name, ev in none.items():
        assert window_priors([ev], [], SYNC, wins) == [0.0], name


def test_prior_stoppage_time_maps_to_the_right_half():
    # 45+3 is first-half stoppage: kickoff + 47:30 = 300 + 2850 = 3150 (not after the second-half start).
    ev = MatchEvent(minute=45, extra_minute=3, type="Card", detail="Yellow Card", comments="Simulation")
    assert window_priors([ev], [], SYNC, [(3140, 3160), (3900 + 150, 3900 + 170)]) == [1.0, 0.0]
    # 90+2 -> second half start + 46:30 = 3900 + 2790.
    ev2 = MatchEvent(minute=90, extra_minute=2, type="Var", detail="Penalty cancelled", comments=None)
    assert window_priors([ev2], [], SYNC, [(6680, 6700)]) == [1.0]


def test_no_priors_without_ok_sync():
    ev = MatchEvent(minute=20, extra_minute=None, type="Card", detail="Yellow Card", comments="Simulation")
    bad = SyncResult(None, None, "needs_review")
    assert window_priors([ev], [], bad, [(1460, 1480)]) == [0.0]
