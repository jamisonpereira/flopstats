import pytest

from flopstats import review


def _row(db, item_id):
    return db.execute("select status, resolution, resolved_at is not null from review_items where id = %s", (item_id,)).fetchone()


def test_review_create_idempotent_while_open(db):
    a = review.create(db, "player_link", "match_event", 7, {"name": "X"})
    b = review.create(db, "player_link", "match_event", 7, {"name": "X again"})
    assert a == b
    assert db.execute("select count(*) from review_items").fetchone()[0] == 1
    other = review.create(db, "player_link", "match_event", 8, {})
    assert other != a


def test_resolved_item_allows_a_new_open_one(db):
    a = review.create(db, "player_link", "match_event", 7, {})
    review.resolve(db, a, {"player_id": 42})
    assert _row(db, a) == ("resolved", {"player_id": 42}, True)
    b = review.create(db, "player_link", "match_event", 7, {})
    assert b != a


def test_resolve_twice_raises(db):
    a = review.create(db, "match_link", "video", 1, {})
    review.resolve(db, a, {"ok": True})
    with pytest.raises(ValueError):
        review.resolve(db, a, {"ok": False})
