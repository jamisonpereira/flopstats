"""`flopstats` command-line entry point."""

from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=True, add_completion=False)
api_app = typer.Typer(no_args_is_help=True, help="API-Football downloads (raw store).")
app.add_typer(api_app, name="api")
footballia_app = typer.Typer(no_args_is_help=True, help="Footballia listings and match videos.")
app.add_typer(footballia_app, name="footballia")
run_app = typer.Typer(no_args_is_help=True, help="Detection runs: create, process matches, status.")
app.add_typer(run_app, name="run")

FOOTBALLIA_LEAGUES = {39: "premier-league"}


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


def _build_deps(settings, cfg):
    """Real dependencies for a detection run (Gemini models, footballia, ffmpeg, storage)."""
    from pathlib import Path

    from flopstats import runner
    from flopstats.detect.gemini import DecisionScorer, GeminiClockReader, GeminiVerifier
    from flopstats.footballia import download
    from flopstats.storage import SupabaseStorage, get_storage
    from flopstats.video import ffmpeg

    if settings.gemini_key is None:
        raise typer.BadParameter("GEMINI_KEY is not set")
    key = settings.gemini_key.get_secret_value()
    verifiers = []
    for model in cfg.verifier_models:
        if not model.startswith("gemini"):
            raise typer.BadParameter(f"no adapter for verifier {model!r} yet")
        price = cfg.prices.get(model)
        if not price:
            raise typer.BadParameter(f"config.prices has no entry for {model!r}")
        verifiers.append(GeminiVerifier(key, model, usd_per_m_input=price["input"], usd_per_m_output=price["output"],
                                        prompt_version=cfg.prompt_versions.get("verify", "v1")))
    clock_price = cfg.prices.get(cfg.clock_model)
    if not clock_price:
        raise typer.BadParameter(f"config.prices has no entry for clock_model {cfg.clock_model!r}")
    clock_reader = GeminiClockReader(key, cfg.clock_model, usd_per_m_input=clock_price["input"],
                                     usd_per_m_output=clock_price["output"])
    storage = get_storage(settings)
    if isinstance(storage, SupabaseStorage):
        storage.ensure_bucket()
    session = {}

    def fetch(url, dest):
        if "client" not in session:
            session["client"] = download.session(settings.footballia_username.get_secret_value(),
                                                 settings.footballia_password.get_secret_value())
        return download.fetch_match(url, dest, client=session["client"])

    return runner.Deps(storage=storage, scorer=DecisionScorer(key, cfg.scorer_model), verifiers=verifiers,
                       clock_reader=clock_reader, download=fetch, entry_for=runner.entry_from_listing,
                       probe_duration=ffmpeg.probe_duration, cut=ffmpeg.cut, frame_at=ffmpeg.frame_at,
                       workdir=Path("data/work"), settings=settings,
                       working_copy=ffmpeg.working_copy, window=ffmpeg.window)


@run_app.command("create")
def run_create(name: str = typer.Option(...), config: str = typer.Option(..., help="JSON file with the RunConfig")) -> None:
    """Create a detection run from a config file (thresholds have no defaults)."""
    import json
    from pathlib import Path

    from pydantic import ValidationError

    from flopstats import runner

    try:
        cfg = runner.RunConfig.model_validate(json.loads(Path(config).read_text()))
    except ValidationError as exc:
        typer.echo(f"invalid run config: {exc}", err=True)
        raise typer.Exit(1)
    run_id = runner.create_run(_connect(_settings()), name, cfg)
    typer.echo(f"run {name}: id {run_id}")


@run_app.command("match")
def run_match(run: int = typer.Option(...), url: str = typer.Option(...)) -> None:
    """Process one footballia match (resumable)."""
    from flopstats import runner

    settings = _settings()
    conn = _connect(settings)
    rep = runner.process_match(conn, run, url, _build_deps(settings, runner.load_config(conn, run)))
    typer.echo(f"{url}: {rep.status} {rep.counts}")


@run_app.command("season")
def run_season(
    run: int = typer.Option(...),
    league: int = typer.Option(39, help="API-Football league id"),
    season: int = typer.Option(..., help="Season start year, e.g. 2024"),
    limit: int = typer.Option(None, help="Process at most N matches"),
    urls: str = typer.Option(None, help="Comma-separated footballia URLs to restrict the run to"),
    parallel: int = typer.Option(1, min=1, help="Matches processed at once (one's encode overlaps another's scoring)"),
) -> None:
    """Process every footballia-listed match of a season, in date order; stops on budget."""
    import threading

    from flopstats import runner
    from flopstats.footballia import catalog
    from flopstats.footballia.download import new_client

    settings = _settings()
    conn = _connect(settings)
    label = f"{season}-{season + 1}"
    with new_client() as client:
        entries = catalog.list_season(client, FOOTBALLIA_LEAGUES[league], label)
    catalog.record_first_seen(conn, entries)
    if urls:
        wanted = {u.strip() for u in urls.split(",") if u.strip()}
        entries = [e for e in entries if e.url in wanted]
    if limit is not None:
        entries = entries[:limit]
    deps = _build_deps(settings, runner.load_config(conn, run))
    summary: dict[str, int] = {}
    pending = list(entries)
    lock, stop = threading.Lock(), threading.Event()

    def worker(wconn) -> None:
        while not stop.is_set():
            with lock:
                if not pending:
                    return
                e = pending.pop(0)
            try:
                rep = runner.process_match(wconn, run, e.url, deps)
            except Exception as exc:  # recorded on the step's job; carry on with the next match
                with lock:
                    typer.echo(f"{e.url}: error {type(exc).__name__}: {exc}", err=True)
                    summary["error"] = summary.get("error", 0) + 1
                continue
            with lock:
                summary[rep.status] = summary.get(rep.status, 0) + 1
                typer.echo(f"{e.date} {e.home} v {e.away}: {rep.status} {rep.counts}")
                if rep.status == "blocked_budget" and not stop.is_set():
                    stop.set()
                    typer.echo("stopping: budget reached")

    if parallel == 1:
        worker(conn)
    else:  # each worker has its own connection (psycopg connections aren't shared across threads)
        threads = [threading.Thread(target=worker, args=(conn if i == 0 else _connect(settings),)) for i in range(parallel)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    typer.echo(f"season {label}: {summary}")


@run_app.command("status")
def run_status(run: int = typer.Option(...)) -> None:
    """Progress, spend against the budget, failures and open reviews."""
    from flopstats import runner

    settings = _settings()
    s = runner.status(_connect(settings), run)
    typer.echo(f"jobs: {s['jobs']}")
    typer.echo(f"incidents: {s['incidents']}")
    typer.echo(f"spent: run ${s['spent_usd']:.4f}, total ${s['spent_total_usd']:.4f} of ${settings.budget_usd}")
    typer.echo(f"open reviews: {s['open_reviews']}")
    for f in s["failed"]:
        typer.echo(f"  failed {f['kind']} {f['key']}: {f['error']}")


@app.command("report")
def report_cmd(
    run: int = typer.Option(...),
    matches_total: int = typer.Option(380, help="Matches to project the cost for"),
    precision_target: float = typer.Option(0.80),
    recall_target: float = typer.Option(0.90),
) -> None:
    """Pass criteria for a run: precision, known-dive recall, verifier comparison, cost projection."""
    from flopstats import report

    conn = _connect(_settings())
    p = report.precision(conn, run)
    r = report.known_dive_recall(conn, run)
    typer.echo(f"precision: {p.agreed}/{p.reviewed} = {p.rate:.0%} (target {precision_target:.0%})")
    typer.echo(f"known-dive recall: {r.found}/{r.total} = {r.rate:.0%} (target {recall_target:.0%})")
    for m in r.missed:
        typer.echo(f"  missed: match {m['match_id']} {m['minute']}'{'+' + str(m['extra_minute']) if m['extra_minute'] else ''} "
                   f"{m['type']} {m['detail'] or ''} {m['comments'] or ''} {m['player'] or ''}".rstrip())
    typer.echo("verifiers:")
    for v in report.verifier_comparison(conn, run):
        typer.echo(f"  {v.model}: agreed {v.agreed_with_jamison}/{v.reviewed}, ${v.usd_per_match:.4f} per match")
    typer.echo(f"cost projection for {matches_total} matches: ${report.cost_projection(conn, run, matches_total)}")
    ok_p = p.reviewed > 0 and p.rate >= precision_target
    ok_r = r.total > 0 and r.rate >= recall_target
    typer.echo(f"{'PASS' if ok_p else 'FAIL'} precision  ·  {'PASS' if ok_r else 'FAIL'} known-dive recall")
