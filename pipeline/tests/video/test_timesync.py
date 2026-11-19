import random
from pathlib import Path

import pytest

from flopstats.video.timesync import ClockReading, SyncResult, sync, to_game_time, to_video_time

KICKOFF = 312.0  # video second where the first half starts (clock 00:00)
SECOND = 3600.0 + 312.0  # video second where the second half starts (clock 45:00)
DURATION = 6900.0


def true_clock(t):
    """The on-screen clock at video time t, or None in the break / before kickoff."""
    if KICKOFF <= t < KICKOFF + 2700 + 180:  # first half incl. 3 min stoppage
        return t - KICKOFF
    if t >= SECOND:
        return 2700 + (t - SECOND)
    return None


def fake_extract(src, t, dest):
    return Path(f"{t:.3f}.png")


class FakeReader:
    def __init__(self, unreadable=(), outliers=(), jitter=1.0, seed=1):
        self.unreadable, self.outliers = set(unreadable), set(outliers)
        self.rng = random.Random(seed)
        self.calls = 0
        self.jitter = jitter

    def read(self, png):
        i = self.calls
        self.calls += 1
        t = float(Path(png).stem)
        c = true_clock(t)
        if c is None or i in self.unreadable:
            return None
        if i in self.outliers:
            c = self.rng.uniform(0, 5400)  # misread digits
        c = max(0.0, c + self.rng.uniform(-self.jitter, self.jitter))
        m, s = divmod(int(c), 60)
        return ClockReading(minute=m, second=s, confidence=0.9)


def test_sync_clean_readings_ok():
    r = sync("match.mp4", DURATION, FakeReader(), extract=fake_extract)
    assert r.status == "ok"
    assert r.kickoff_offset_s == pytest.approx(KICKOFF, abs=2)
    assert r.second_half_offset_s == pytest.approx(SECOND, abs=2)


def test_sync_samples_spread_and_avoid_ends():
    times = []
    sync("m.mp4", DURATION, FakeReader(), samples=24, extract=lambda s, t, d: times.append(t) or Path(f"{t:.3f}.png"))
    assert len(times) == 24
    assert min(times) >= 120 and max(times) <= DURATION - 120
    gaps = [b - a for a, b in zip(times, times[1:])]
    assert max(gaps) - min(gaps) < 0.01


def test_sync_ignores_unreadable_and_outlier_samples():
    reader = FakeReader(unreadable={0, 3, 6, 9, 12, 15, 18, 21}, outliers={1, 13, 22})
    r = sync("match.mp4", DURATION, reader, samples=24, extract=fake_extract)
    assert r.status == "ok"
    assert r.kickoff_offset_s == pytest.approx(KICKOFF, abs=2)
    assert r.second_half_offset_s == pytest.approx(SECOND, abs=2)


def test_sync_low_confidence_readings_are_ignored():
    class Unsure(FakeReader):
        def read(self, png):
            r = super().read(png)
            return r and ClockReading(r.minute, r.second, confidence=0.05)

    assert sync("m.mp4", DURATION, Unsure(), extract=fake_extract).status == "needs_review"


def test_sync_mostly_unreadable_needs_review():
    reader = FakeReader(unreadable=set(range(24)) - {4, 10, 17})  # only 3 readings
    r = sync("match.mp4", DURATION, reader, samples=24, extract=fake_extract)
    assert r == SyncResult(kickoff_offset_s=None, second_half_offset_s=None, status="needs_review")


def test_round_trip_game_video_time():
    r = SyncResult(kickoff_offset_s=KICKOFF, second_half_offset_s=SECOND, status="ok")
    for minute, second in [(0, 0), (12, 34), (44, 59), (45, 0), (67, 8), (90, 0)]:
        t = to_video_time(minute, second, r)
        assert to_game_time(t, r) == (minute, second)
    assert to_video_time(12, 34, r) == KICKOFF + 754
    assert to_video_time(67, 8, r) == SECOND + (67 * 60 + 8 - 2700)
    assert to_game_time(KICKOFF - 30, r) is None  # before kickoff


def test_game_time_needs_ok_sync():
    r = SyncResult(kickoff_offset_s=None, second_half_offset_s=None, status="needs_review")
    assert to_game_time(1000, r) is None and to_video_time(10, 0, r) is None
