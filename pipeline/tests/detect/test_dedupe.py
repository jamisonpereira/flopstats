from decimal import Decimal

from flopstats.detect.dedupe import Placed, collapse, key
from flopstats.detect.verify import FlopAttrs, PlayerGuess, VerifyResult


def R(start, team="home", shirt=7, replay=False, name=None):
    return VerifyResult(is_flop=True, type="dive", confidence=0.8, start_s=start, end_s=start + 5, is_replay=replay,
                        flopper=PlayerGuess(team=team, shirt_number=shirt, name=name, confidence=0.9), others=[],
                        attrs=FlopAttrs(), ref_decision="none", usd=Decimal(0))


def test_key_rounds_absolute_start_to_15s():
    assert key(R(3.0), video_start_s=1000) == "1005:home:7"   # 1003 -> 1005
    assert key(R(10.0), video_start_s=1000) == "1005:home:7"  # 1010 -> 1005
    assert key(R(14.0), video_start_s=1000) == "1020:home:7"  # 1014 -> 1020
    assert key(R(1.0, shirt=None), video_start_s=0) == "0:home:?"


def test_replay_collapses_into_original():
    original = Placed(R(2.0), video_start_s=1000, candidate_id=1)
    replay = Placed(R(4.0, replay=True), video_start_s=1040, candidate_id=2)  # 42 s later, same flopper
    assert collapse([replay, original]) == [original]


def test_replay_without_original_is_kept():
    replay = Placed(R(4.0, replay=True), video_start_s=1040, candidate_id=2)
    assert collapse([replay]) == [replay]


def test_replay_of_a_different_player_is_kept():
    original = Placed(R(2.0), video_start_s=1000, candidate_id=1)
    other = Placed(R(4.0, shirt=10, replay=True), video_start_s=1040, candidate_id=2)
    assert collapse([original, other]) == [original, other]


def test_replay_far_away_is_kept():
    original = Placed(R(2.0), video_start_s=1000, candidate_id=1)
    late = Placed(R(4.0, replay=True), video_start_s=1200, candidate_id=2)  # 202 s later
    assert len(collapse([original, late])) == 2


def test_overlap_duplicates_keep_the_earliest():
    a = Placed(R(9.0), video_start_s=1000, candidate_id=1)   # 1009
    b = Placed(R(0.0), video_start_s=1010, candidate_id=2)   # 1010: same moment seen from an overlapping candidate
    assert collapse([b, a]) == [a]


def test_two_distinct_flops_same_minute_kept():
    a = Placed(R(5.0, team="home", shirt=7), video_start_s=1000, candidate_id=1)
    b = Placed(R(20.0, team="away", shirt=9), video_start_s=1000, candidate_id=1)
    assert collapse([a, b]) == [a, b]


# --- final review I2: partial identities ------------------------------------------------

def test_replay_with_partial_identity_collapses_into_original():
    live = Placed(R(2.0, shirt=None), video_start_s=1000, candidate_id=1)  # wide shot: number unreadable
    replay = Placed(R(4.0, shirt=7, replay=True), video_start_s=1030, candidate_id=2)  # close-up replay reads it
    assert collapse([live, replay]) == [live]


def test_overlap_with_unknown_team_collapses():
    a = Placed(R(9.0, team=None, shirt=None), video_start_s=1000, candidate_id=1)
    b = Placed(R(3.0, team=None, shirt=None), video_start_s=1010, candidate_id=2)  # 4 s later
    assert collapse([a, b]) == [a]


def test_conflicting_identities_are_kept_apart():
    a = Placed(R(5.0, shirt=7), video_start_s=1000, candidate_id=1)
    b = Placed(R(8.0, shirt=10), video_start_s=1000, candidate_id=1)  # same team, different known shirts
    assert len(collapse([a, b])) == 2


def test_key_includes_name_when_shirt_unknown():
    assert key(R(5.0, shirt=None, name="Bruno Fernandes"), 1000) != key(R(5.0, shirt=None, name="Mason Mount"), 1000)
