import pytest

from flopstats.detect.candidates import WindowRow, final_score, select


def W(start, score, prior=0.0, length=20):
    return WindowRow(start_s=start, end_s=start + length, score=score, prior=prior)


def test_prior_never_lowers_score():
    assert final_score(0.42, 0.0, prior_weight=0.3) == 0.42
    assert final_score(0.42, 1.0, prior_weight=-0.5) == 0.42  # even a negative weight can't lower it
    assert final_score(0.42, 1.0, prior_weight=0.3) == pytest.approx(0.72)
    assert final_score(0.9, 1.0, prior_weight=0.3) == 1.0  # clipped


def test_overlapping_windows_merge_into_one_candidate():
    rows = [W(0, 0.1), W(10, 0.8), W(20, 0.9), W(30, 0.7), W(40, 0.1), W(50, 0.1)]
    cands = select(rows, threshold=0.6, prior_weight=0.0)
    assert len(cands) == 1
    c = cands[0]
    assert (c.start_s, c.end_s, c.final_score) == (10, 50, 0.9)
    assert [w.start_s for w in c.windows] == [10, 20, 30]


def test_separate_runs_are_separate_candidates():
    rows = [W(0, 0.9), W(10, 0.1), W(20, 0.1), W(30, 0.1), W(40, 0.8)]
    assert [(c.start_s, c.end_s) for c in select(rows, 0.6, 0.0)] == [(0, 20), (40, 60)]


def test_adjacent_windows_merge():
    rows = [WindowRow(0, 20, 0.9, 0), WindowRow(20, 40, 0.9, 0)]
    assert [(c.start_s, c.end_s) for c in select(rows, 0.6, 0.0)] == [(0, 40)]


def test_below_threshold_not_selected():
    rows = [W(0, 0.59), W(10, 0.2)]
    assert select(rows, threshold=0.6, prior_weight=0.0) == []
    # ...unless a prior lifts it over.
    boosted = select([W(0, 0.5, prior=1.0)], threshold=0.6, prior_weight=0.2)
    assert len(boosted) == 1 and boosted[0].final_score == pytest.approx(0.7)


def test_unsorted_input_is_handled():
    rows = [W(20, 0.9), W(0, 0.1), W(10, 0.8)]
    assert [(c.start_s, c.end_s) for c in select(rows, 0.6, 0.0)] == [(10, 40)]
