"""`flopstats` command-line entry point."""

from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=True, add_completion=False)
api_app = typer.Typer(no_args_is_help=True, help="API-Football downloads (raw store).")
app.add_typer(api_app, name="api")


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
