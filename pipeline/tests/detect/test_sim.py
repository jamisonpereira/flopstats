import math

import pytest

from flopstats.detect.sim import SimWeights, entity_sim, flop_score
from flopstats.detect.verify import FlopAttrs

NONE = {"penalty_awarded": False, "penalty_scored": False, "opponent_booked": False, "goal_within_60s": False}


def test_flop_score_contact_and_payoff_multipliers():
    attrs = FlopAttrs(fake_pain=8, time_on_ground_s=20, contact_level="none")
    cons = {**NONE, "penalty_awarded": True, "penalty_scored": True}
    expected = 10 * 0.8 * (1 + math.log(3)) * 1.5 * 2.5 * 1.0 * 0.9
    assert flop_score(attrs, cons, "penalty", 0.9, SimWeights()) == pytest.approx(expected, abs=1e-6)


def test_payoff_picks_highest_and_bonus():
    attrs = FlopAttrs(fake_pain=5, time_on_ground_s=0, contact_level="real", rolls=9, miracle_recovery=True)
    w = SimWeights()
    foul = flop_score(attrs, NONE, "foul", 1.0, w)
    booked = flop_score(attrs, {**NONE, "opponent_booked": True}, "foul", 1.0, w)
    assert foul == pytest.approx(10 * 0.5 * 1.0 * 0.5 * 1.2 * (1 + 0.25 + 0.1))
    assert booked == pytest.approx(foul / 1.2 * 1.5)
    assert flop_score(attrs, NONE, "none", 1.0, w) == pytest.approx(foul / 1.2)


def test_weights_load_from_settings_with_defaults(db):
    assert SimWeights.load(db) == SimWeights()
    db.execute("insert into settings (key, value) values ('sim_weights', '{\"base\": 20, \"contact\": {\"none\": 2.0}}')")
    w = SimWeights.load(db)
    assert w.base == 20 and w.contact["none"] == 2.0 and w.contact["real"] == 0.5 and w.payoff["penalty_scored"] == 2.5


def test_entity_sim_scales_top_to_100():
    scores = {1: 30.0, 2: 15.0, 3: 50.0}
    minutes = {1: 900, 2: 270, 3: 200}  # 3 has too few minutes
    out = entity_sim(scores, minutes)
    assert set(out) == {1, 2}
    assert out[2] == pytest.approx(100.0)  # 15/270*90 = 5.0 per 90 is the top
    assert out[1] == pytest.approx(30 / 900 * 90 / 5.0 * 100)
    assert entity_sim({}, {}) == {}
