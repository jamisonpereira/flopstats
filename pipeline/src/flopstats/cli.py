"""`flopstats` command-line entry point."""

from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=True, add_completion=False)
api_app = typer.Typer(no_args_is_help=True, help="API-Football downloads (raw store).")
app.add_typer(api_app, name="api")
footballia_app = typer.Typer(no_args_is_help=True, help="Footballia listings and match videos.")
app.add_typer(footballia_app, name="footballia")


def _settings():
    from flopstats.config import Settings

    return Settings()


def _connect(settings):
    from flopstats.db import connect

    return connect(settings)


@app.callback()
def main() -> None:
    """Flopstats pipeline."""


@app.command("verify-setup")
def verify_setup() -> None:
    """Check each service's key works with one cheap call. Prints OK/FAIL, never values."""
    from flopstats.setup_check import check_all

    results = check_all(_settings())
    for r in results:
        status = "SKIP" if r.skipped else ("OK" if r.ok else "FAIL")
        typer.echo(f"{status:<5} {r.name:<18} {r.detail}")
    if not all(r.ok for r in results):
        raise typer.Exit(1)


@api_app.command("fetch-season")
def fetch_season(
    league: int = typer.Option(..., help="API-Football league id (39 = Premier League)"),
    season: int = typer.Option(..., help="Season start year, e.g. 2024"),
) -> None:
    """Store a season's fixture list and full fixture details (events, lineups, player stats)."""
    from flopstats.apifootball.client import ApiFootball

    settings = _settings()
    if settings.apifootball_key is None:
        typer.echo("APIFOOTBALL_KEY not set", err=True)
        raise typer.Exit(1)
    conn = _connect(settings)
    api = ApiFootball(conn, settings.apifootball_key.get_secret_value())
    fixtures = api.fixtures_for_season(league, season)
    ids = [f["fixture"]["id"] for f in fixtures]
    details = api.fixtures_by_ids(ids)
    typer.echo(f"league {league} season {season}: {len(fixtures)} fixtures, {len(details)} with details")


@api_app.command("build-season")
def build_season_cmd(
    league: int = typer.Option(..., help="API-Football league id (39 = Premier League)"),
    season: int = typer.Option(..., help="Season start year, e.g. 2024"),
) -> None:
    """Build the clean football tables for a season from stored raw responses (no HTTP)."""
    from flopstats.apifootball import build

    report = build.build_season(_connect(_settings()), league, season)
    typer.echo(f"league {league} season {season}:")
    for table, n in sorted(report.counts.items()):
        typer.echo(f"  {table}: {n}")
    total = report.counts.get("match_events", 0)
    typer.echo(f"  events with null player: {report.null_player_events} of {total} ({report.null_player_pct:.2f}%)")
    typer.echo(f"  player links needing review: {report.needs_review}")
    typer.echo(f"  fixtures missing details: {report.missing_details}")


def _current_season(today=None) -> str:
    """Footballia season label, e.g. "2026-2027"; a season starts in August."""
    from datetime import date

    today = today or date.today()
    start = today.year if today.month >= 8 else today.year - 1
    return f"{start}-{start + 1}"


@footballia_app.command("watch")
def footballia_watch(
    league: str = typer.Option("premier-league", help="Footballia competition slug"),
    season: str = typer.Option(None, help='Season label, e.g. "2026-2027" (default: current)'),
) -> None:
    """Log every listed match's first-seen time (run daily; measures footballia's posting lag)."""
    from flopstats.footballia import catalog
    from flopstats.footballia.download import new_client

    season = season or _current_season()
    with new_client() as client:
        entries = catalog.list_season(client, league, season)
    new = catalog.record_first_seen(_connect(_settings()), entries)
    typer.echo(f"{league} {season}: {len(entries)} listed, {new} new")


@footballia_app.command("fetch")
def footballia_fetch(
    url: str = typer.Option(..., help="Footballia match page URL"),
    dest: str = typer.Option("data/videos", help="Directory for the joined mp4"),
) -> None:
    """Download a full match (all parts joined) as one mp4."""
    from flopstats.footballia import download

    settings = _settings()
    if settings.footballia_username is None or settings.footballia_password is None:
        typer.echo("FOOTBALLIA_USERNAME and FOOTBALLIA_PASSWORD must be set", err=True)
        raise typer.Exit(1)
    client = download.session(settings.footballia_username.get_secret_value(),
                              settings.footballia_password.get_secret_value())
    out = download.fetch_match(url, dest, client=client)
    typer.echo(f"{out} ({download.probe_duration_s(out) / 60:.1f} min)")
