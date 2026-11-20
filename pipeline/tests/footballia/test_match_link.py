from datetime import date

import pytest

from flopstats.footballia.catalog import CatalogEntry
from flopstats.footballia.match_link import link, normalize_team


def _one(db, sql, *p):
    return db.execute(sql, p).fetchone()[0]


@pytest.fixture
def season(db):
    c = _one(db, "insert into countries (name) values ('England') returning id")
    lg = _one(db, "insert into leagues (name, country_id) values ('Premier League', %s) returning id", c)
    s = _one(db, "insert into seasons (league_id, year) values (%s, 2024) returning id", lg)
    teams = {n: _one(db, "insert into teams (name) values (%s) returning id", n)
             for n in ("Tottenham", "Brighton", "Manchester United", "Manchester City", "Everton", "Brentford", "Nottingham Forest", "Wolves")}

    def match(home, away, kickoff):
        return _one(db, "insert into matches (season_id, home_team_id, away_team_id, kickoff_at) values (%s, %s, %s, %s) returning id",
                    s, teams[home], teams[away], kickoff)

    return {
        "spurs": match("Tottenham", "Brighton", "2025-05-25 15:00Z"),
        "brentford": match("Brentford", "Nottingham Forest", "2024-12-21 15:00Z"),
        "united": match("Manchester United", "Everton", "2024-11-30 12:30Z"),
        "city": match("Manchester City", "Everton", "2024-12-01 14:00Z"),
        "wolves": match("Wolves", "Brentford", "2025-01-04 15:00Z"),
    }


def _entry(home, away, d, url=None):
    return CatalogEntry(url=url or f"https://footballia.eu/matches/{normalize_team(home)}-{normalize_team(away)}".replace(" ", "-"),
                        home=home, away=away, date=d, competition="Premier League", season="2024-2025", stage="")


def test_normalize_team():
    assert normalize_team("Brighton &amp; Hove Albion") == normalize_team("Brighton") == "brighton"
    assert normalize_team("Brentford FC") == "brentford"
    assert normalize_team("Wolverhampton Wanderers") == normalize_team("WOL") == "wolves"


def test_link_exact_date_and_teams(db, season):
    r = link(db, _entry("Brentford FC", "Nottingham Forest", date(2024, 12, 21)))
    assert (r.match_id, r.confidence) == (season["brentford"], 1.0)
    ref = db.execute("select entity_id, status from external_refs where entity_type = 'footballia_listing' and source = 'footballia'").fetchone()
    assert ref == (season["brentford"], "linked")


def test_link_team_alias(db, season):
    r = link(db, _entry("Spurs", "Brighton & Hove Albion", date(2025, 5, 25)))
    assert r.match_id == season["spurs"] and r.confidence >= 0.95


def test_link_one_day_off_still_links(db, season):
    r = link(db, _entry("Wolverhampton Wanderers", "Brentford FC", date(2025, 1, 5)))
    assert r.match_id == season["wolves"] and 0.95 <= r.confidence < 1.0


def test_ambiguous_link_creates_review_item(db, season):
    # "Manchester" vs Everton: United (Nov 30) and City (Dec 1) are both within a day of Nov 30.
    entry = _entry("Manchester", "Everton FC", date(2024, 11, 30), url="https://footballia.eu/matches/manchester-everton")
    r = link(db, entry)
    assert r.match_id is None and r.confidence < 0.95
    kind, subject_type, payload = db.execute("select kind, subject_type, payload from review_items").fetchone()
    assert (kind, subject_type) == ("match_link", "footballia_listing")
    assert payload["url"] == entry.url
    assert {g["match_id"] for g in payload["guesses"]} == {season["united"], season["city"]}
    link(db, entry)  # linking again does not pile up review items
    assert _one(db, "select count(*) from review_items") == 1


def test_no_candidate_creates_review_item(db, season):
    r = link(db, _entry("Brentford FC", "Nottingham Forest", date(2024, 8, 1)))
    assert r.match_id is None
    assert _one(db, "select count(*) from review_items where kind = 'match_link'") == 1
