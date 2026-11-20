from flopstats.detect.decide import status


def test_status_thresholds():
    assert status(0.9, 0.85, 0.5, None, 0) == "confirmed"
    assert status(0.85, 0.85, 0.5, None, 0) == "confirmed"
    assert status(0.49, 0.85, 0.5, None, 0) == "rejected"


def test_status_no_cap_all_borderline_review():
    assert all(status(0.6, 0.85, 0.5, None, n) == "review" for n in (0, 10, 10_000))


def test_status_with_cap_overflow_ai_judged():
    assert status(0.6, 0.85, 0.5, 3, 2) == "review"
    assert status(0.6, 0.85, 0.5, 3, 3) == "ai_judged"
    assert status(0.9, 0.85, 0.5, 3, 99) == "confirmed"  # the cap only affects borderline items
