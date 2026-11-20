import pytest

from flopstats.video.windows import make


def test_windows_60s_len20_step10():
    assert make(60) == [(0, 20), (10, 30), (20, 40), (30, 50), (40, 60)]


def test_windows_last_clipped():
    w = make(65)
    assert w[-1] == (50, 65)
    assert w[-2] == (40, 60)


def test_windows_short_video_is_one_window():
    assert make(12.5) == [(0, 12.5)]


def test_windows_no_tiny_tail_window():
    # 61 s: (50, 61) already reaches the end, so no extra (60, 61) sliver.
    assert make(61)[-1] == (50, 61)


@pytest.mark.parametrize("bad", [dict(duration_s=0), dict(duration_s=60, length_s=0), dict(duration_s=60, step_s=0)])
def test_windows_rejects_bad_input(bad):
    with pytest.raises(ValueError):
        make(**bad)
