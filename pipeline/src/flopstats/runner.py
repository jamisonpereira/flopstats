"""Process one footballia match end to end, as resumable steps.

Every step is a `jobs` row (kind = step, key = "run:video:step"). A finished step is never
redone, so a crash, rate limit or budget stop resumes without repeated downloads, model
calls, charges or duplicate incidents (Review Focus #3). Two steps can pause the match for
Jamison: an uncertain match link and an unreadable clock. Resolving their review item lets
the next run continue.
"""

from __future__ import annotations

import shutil
import statistics
from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

import psycopg
from psycopg.types.json import Jsonb
from pydantic import BaseModel, Field

from flopstats import costs, jobs, review
from flopstats.config import Settings
from flopstats.detect import candidates as cand_mod
from flopstats.detect import dedupe, enrich, verify
from flopstats.detect.gemini import ContentBlocked
from flopstats.parallel import parallel as _parallel
from flopstats.detect.priors import MatchEvent, window_priors
from flopstats.detect.sim import SimWeights
from flopstats.detect.verify import LineupPlayer, VerifyContext, VerifyResult
from flopstats.footballia.catalog import CatalogEntry
from flopstats.footballia.match_link import link as link_match
from flopstats.storage import StorageAdapter, clip_path, segment_path
from flopstats.video import timesync, windows

STEPS = ("link", "download", "sync", "score", "candidates", "verify", "persist", "clips", "delete")
BATCH = 50
DEFAULT_WINDOW_USD = Decimal("0.002")
DEFAULT_VERIFY_USD = Decimal("0.05")
SYNC_ESTIMATE_USD = Decimal("0.02")


class RunConfig(BaseModel):
    window_len_s: float = 20
    window_step_s: float = 10
    candidate_threshold: float = Field(ge=0, le=1)
    prior_weight: float = Field(ge=0)
    confirm_threshold: float = Field(ge=0, le=1)
    review_threshold: float = Field(ge=0, le=1)
    review_cap: int | None = None
    pad_s: float = 8
    player_min_conf: float = Field(ge=0, le=1)
    scorer_model: str
    verifier_models: list[str]
    primary_verifier: str
    prompt_versions: dict[str, str] = Field(default_factory=dict)
    sync_samples: int = 24
    # USD per 1M tokens per model, e.g. {"gemini-3.8-flash": {"input": 0.5, "output": 3}}.
    prices: dict[str, dict[str, float]] = Field(default_factory=dict)
    # Model calls (window scoring, verification) made at the same time. Writes stay one at a time.
    workers: int = Field(default=8, ge=1)
    # Reads the broadcast clock for time sync (needs an entry in prices).
    clock_model: str = "gemini-3.8-flash"


@dataclass
class Deps:
    storage: StorageAdapter
    scorer: Any  # WindowScorer
    verifiers: list
    clock_reader: Any  # ClockReader
    download: Callable[[str, Path], Path]
    entry_for: Callable[[psycopg.Connection, str], CatalogEntry | None]
    probe_duration: Callable[[Path], float]
    cut: Callable[..., Path]
    frame_at: Callable[[Path, float, Path], Path]
    workdir: Path
    settings: Settings


@dataclass
class MatchReport:
    status: str  # done | paused_link | paused_sync | blocked_budget
    video_id: int | None = None
    counts: dict = field(default_factory=dict)


class _Stop(Exception):
    def __init__(self, status: str, job_status: str):
        self.status, self.job_status = status, job_status


def create_run(conn: psycopg.Connection, name: str, config: RunConfig) -> int:
    with conn.transaction():
        row = conn.execute(
            "insert into detection_runs (name, config) values (%s, %s) on conflict (name) do nothing returning id",
            (name, Jsonb(config.model_dump())),
        ).fetchone()
    return row[0] if row else conn.execute("select id from detection_runs where name = %s", (name,)).fetchone()[0]


def load_config(conn: psycopg.Connection, run_id: int) -> RunConfig:
    return RunConfig.model_validate(conn.execute("select config from detection_runs where id = %s", (run_id,)).fetchone()[0])


def entry_from_listing(conn: psycopg.Connection, url: str) -> CatalogEntry | None:
    """The footballia listing recorded by `footballia watch` / `run season`."""
    from datetime import date

    row = conn.execute(
        "select payload from external_refs where entity_type = 'footballia_listing' and source = 'footballia' and source_id = %s",
        (url,),
    ).fetchone()
    if not row or not row[0] or "home" not in row[0]:
        return None
    p = row[0]
    return CatalogEntry(url=url, home=p["home"], away=p["away"], date=date.fromisoformat(p["match_date"]),
                        competition=p.get("competition", ""), season=p.get("season", ""), stage=p.get("stage", ""))


# --- the match ---------------------------------------------------------------------------


def process_match(conn: psycopg.Connection, run_id: int, footballia_url: str, deps: Deps) -> MatchReport:
    cfg = load_config(conn, run_id)
    with conn.transaction():
        conn.execute("insert into videos (source, source_url) values ('footballia', %s) on conflict do nothing", (footballia_url,))
    video_id = conn.execute("select id from videos where source = 'footballia' and source_url = %s", (footballia_url,)).fetchone()[0]
    # One process per match: a second runner would pay for the same model calls again.
    lock = match_lock_key(run_id, video_id)
    if not conn.execute("select pg_try_advisory_lock(%s)", (lock,)).fetchone()[0]:
        return MatchReport("busy", video_id, {})
    try:
        return _process(conn, run_id, video_id, footballia_url, cfg, deps)
    finally:
        conn.execute("select pg_advisory_unlock(%s)", (lock,))


def match_lock_key(run_id: int, video_id: int) -> int:
    """A stable 63-bit advisory-lock key for (run, video)."""
    import hashlib

    return int.from_bytes(hashlib.sha256(f"flopstats:match:{run_id}:{video_id}".encode()).digest()[:8], "big") >> 1


def _process(conn, run_id: int, video_id: int, footballia_url: str, cfg: RunConfig, deps: Deps) -> MatchReport:
    ctx = _Ctx(conn, run_id, video_id, footballia_url, cfg, deps)
    for step in STEPS:
        job_id = jobs.enqueue(conn, step, f"{run_id}:{video_id}:{step}", {"url": footballia_url})
        if conn.execute("select status from jobs where id = %s", (job_id,)).fetchone()[0] == "done":
            continue
        jobs.mark(conn, job_id, "running")
        try:
            getattr(ctx, f"step_{step}")()
        except _Stop as stop:
            jobs.mark(conn, job_id, stop.job_status)
            return MatchReport(stop.status, video_id, ctx.counts())
        except Exception as exc:
            jobs.fail(conn, job_id, f"{type(exc).__name__}: {exc}"[:500], retry=True)
            raise
        jobs.complete(conn, job_id)
    return MatchReport("done", video_id, ctx.counts())


class _Ctx:
    def __init__(self, conn, run_id, video_id, url, cfg: RunConfig, deps: Deps):
        self.conn, self.run_id, self.video_id, self.url, self.cfg, self.deps = conn, run_id, video_id, url, cfg, deps
        self.dir = Path(deps.workdir) / f"run{run_id}-video{video_id}"

    # helpers ---------------------------------------------------------------------------
    def video(self) -> dict:
        cols = ("match_id", "local_path", "duration_s", "kickoff_offset_s", "second_half_offset_s", "sync_status")
        row = self.conn.execute(f"select {', '.join(cols)} from videos where id = %s", (self.video_id,)).fetchone()
        return dict(zip(cols, row))

    def sync_result(self) -> timesync.SyncResult:
        v = self.video()
        return timesync.SyncResult(v["kickoff_offset_s"], v["second_half_offset_s"], v["sync_status"] if v["sync_status"] == "ok" else "needs_review")

    def guard(self, estimate: Decimal) -> None:
        try:
            costs.guard(self.conn, self.deps.settings, estimate)
        except costs.BudgetExceeded:
            raise _Stop("blocked_budget", "blocked_budget") from None

    def counts(self) -> dict:
        q = lambda sql: self.conn.execute(sql, (self.run_id, self.video_id)).fetchone()[0]
        return {
            "windows": q("select count(*) from windows where run_id = %s and video_id = %s"),
            "candidates": q("select count(*) from candidates where run_id = %s and video_id = %s"),
            "incidents": q("select count(*) from incidents where run_id = %s and video_id = %s"),
            "clips": q("select count(*) from clips c join incidents i on i.id = c.incident_id where i.run_id = %s and i.video_id = %s"),
        }

    def match_context(self) -> enrich.MatchContext:
        mid = self.video()["match_id"]
        home, away = self.conn.execute("select home_team_id, away_team_id from matches where id = %s", (mid,)).fetchone()
        lineup = [enrich.LineupEntry(*r) for r in self.conn.execute(
            "select l.player_id, l.team_id, l.shirt_number, p.display_name from match_lineups l "
            "join players p on p.id = l.player_id where l.match_id = %s order by l.team_id, l.shirt_number", (mid,))]
        events = [enrich.EventRow(*r) for r in self.conn.execute(
            "select minute, extra_minute, type, detail, comments, team_id from match_events where match_id = %s order by minute, id", (mid,))]
        return enrich.MatchContext(mid, home, away, lineup, events)

    def local_video(self) -> Path:
        path = self.video()["local_path"]
        if not path or not Path(path).exists():
            raise RuntimeError("the full video is missing locally; re-run the download step")
        return Path(path)

    def segment_file(self, cand_id: int, start: float, end: float) -> Path:
        dest = self.dir / "segments" / f"cand_{cand_id}_{int(start)}.mp4"
        if not dest.exists():
            seg_start = max(0.0, start - self.cfg.pad_s)
            self.deps.cut(self.local_video(), seg_start, end + self.cfg.pad_s, dest, reencode=True)
        return dest

    # steps -----------------------------------------------------------------------------
    def step_link(self) -> None:
        listing = self.conn.execute(
            "select id from external_refs where entity_type = 'footballia_listing' and source = 'footballia' and source_id = %s",
            (self.url,),
        ).fetchone()
        if listing:  # a resolved match_link review decides
            row = self.conn.execute(
                "select resolution from review_items where kind = 'match_link' and subject_type = 'footballia_listing' "
                "and subject_id = %s and status = 'resolved' order by resolved_at desc limit 1", (listing[0],)).fetchone()
            if row and row[0] and row[0].get("match_id"):
                with self.conn.transaction():
                    self.conn.execute("update external_refs set entity_id = %s, confidence = 1.0, status = 'linked' where id = %s",
                                      (row[0]["match_id"], listing[0]))
        linked = listing and self.conn.execute(
            "select entity_id from external_refs where id = %s and status = 'linked'", (listing[0],)).fetchone()
        match_id = linked[0] if linked else None
        if match_id is None:
            entry = self.deps.entry_for(self.conn, self.url)
            if entry is None:
                # Unknown listing: record it so the review item has a footballia_listing subject the
                # review screen and this step both understand.
                with self.conn.transaction():
                    ref = self.conn.execute(
                        "insert into external_refs (entity_type, source, source_id, status, payload) "
                        "values ('footballia_listing', 'footballia', %s, 'needs_review', %s) "
                        "on conflict (entity_type, source, source_id) do update set source_id = excluded.source_id returning id",
                        (self.url, Jsonb({"url": self.url})),
                    ).fetchone()[0]
                review.create(self.conn, "match_link", "footballia_listing", ref,
                              {"url": self.url, "reason": "no listing metadata", "guesses": []})
                raise _Stop("paused_link", "needs_review")
            match_id = link_match(self.conn, entry).match_id
            if match_id is None:
                raise _Stop("paused_link", "needs_review")
        with self.conn.transaction():
            self.conn.execute("update videos set match_id = %s where id = %s", (match_id, self.video_id))

    def step_download(self) -> None:
        v = self.video()
        if v["local_path"] and Path(v["local_path"]).exists():
            return
        path = self.deps.download(self.url, self.dir)
        duration = self.deps.probe_duration(path)
        with self.conn.transaction():
            self.conn.execute("update videos set local_path = %s, duration_s = %s where id = %s", (str(path), duration, self.video_id))

    def step_sync(self) -> None:
        v = self.video()
        if v["sync_status"] == "ok":
            return
        item = self.conn.execute(
            "select resolution from review_items where kind = 'video_sync' and subject_type = 'video' and subject_id = %s "
            "and status = 'resolved' order by resolved_at desc limit 1", (self.video_id,)).fetchone()
        if item and item[0] and item[0].get("kickoff_offset_s") is not None:
            self._save_sync(float(item[0]["kickoff_offset_s"]), float(item[0]["second_half_offset_s"]), "ok")
            return
        if v["sync_status"] == "needs_review":
            raise _Stop("paused_sync", "needs_review")  # still waiting for Jamison
        self.guard(SYNC_ESTIMATE_USD)
        reader = self.deps.clock_reader
        before = Decimal(getattr(reader, "spent_usd", 0))
        result = timesync.sync(self.local_video(), v["duration_s"], reader, samples=self.cfg.sync_samples, extract=self.deps.frame_at)
        spent = Decimal(getattr(reader, "spent_usd", 0)) - before
        if spent:
            costs.record(self.conn, service="sync", model=getattr(reader, "name", "clock-reader"), units={"samples": self.cfg.sync_samples},
                         usd=spent, idempotency_key=f"sync:{self.run_id}:{self.video_id}", run_id=self.run_id, match_id=v["match_id"])
        self._save_sync(result.kickoff_offset_s, result.second_half_offset_s, result.status)
        if result.status != "ok":
            review.create(self.conn, "video_sync", "video", self.video_id, {
                "url": self.url, "match_id": v["match_id"],
                "hint": "enter kickoff_offset_s and second_half_offset_s (video seconds where each half starts)"})
            raise _Stop("paused_sync", "needs_review")

    def _save_sync(self, kickoff, second, status) -> None:
        with self.conn.transaction():
            self.conn.execute("update videos set kickoff_offset_s = %s, second_half_offset_s = %s, sync_status = %s where id = %s",
                              (kickoff, second, status, self.video_id))

    def _window_usd(self) -> Decimal:
        rows = [r[0] for r in self.conn.execute(
            "select usd from cost_ledger where idempotency_key like %s", (f"window:{self.run_id}:%",))]
        return Decimal(statistics.median(rows)) if rows else DEFAULT_WINDOW_USD

    def step_score(self) -> None:
        v = self.video()
        spans = windows.make(v["duration_s"], self.cfg.window_len_s, self.cfg.window_step_s)
        mc = self.match_context()
        events = [MatchEvent(e.minute, e.extra_minute, e.type, e.detail, e.comments) for e in mc.events]
        priors = dict(zip(spans, window_priors(events, mc.lineup, self.sync_result(), spans)))
        done = {r[0] for r in self.conn.execute(
            "select start_s from windows where run_id = %s and video_id = %s", (self.run_id, self.video_id))}
        todo = [s for s in spans if float(s[0]) not in done]
        def score_one(span):
            start, end = span
            seg = self.deps.cut(self.local_video(), start, end, self.dir / "windows" / f"win_{int(start)}.mp4", reencode=True)
            try:
                return span, self.deps.scorer.score(seg)
            except ContentBlocked:  # refused every time; the overlapping windows cover this footage
                return span, None
            finally:
                Path(seg).unlink(missing_ok=True)

        for i in range(0, len(todo), BATCH):
            batch = todo[i: i + BATCH]
            self.guard(self._window_usd() * len(batch))
            for (start, end), r in _parallel(score_one, batch, self.cfg.workers):
                prior = priors[(start, end)]
                score = r.p_flop if r is not None else None
                with self.conn.transaction():
                    self.conn.execute(
                        "insert into windows (run_id, video_id, start_s, end_s, score, prior, final_score) values (%s, %s, %s, %s, %s, %s, %s) "
                        "on conflict (run_id, video_id, start_s) do nothing",
                        (self.run_id, self.video_id, start, end, score, prior,
                         cand_mod.final_score(score or 0.0, prior, self.cfg.prior_weight)))
                    if r is not None:
                        costs.record(self.conn, service="score", model=getattr(self.deps.scorer, "name", None),
                                     units=r.raw.get("usage", {}), usd=r.usd,
                                     idempotency_key=f"window:{self.run_id}:{self.video_id}:{start}",
                                     run_id=self.run_id, match_id=v["match_id"])

    def step_candidates(self) -> None:
        v = self.video()
        existing = self.conn.execute("select count(*) from candidates where run_id = %s and video_id = %s",
                                     (self.run_id, self.video_id)).fetchone()[0]
        if not existing:
            rows = [cand_mod.WindowRow(s, e, sc, pr) for s, e, sc, pr in self.conn.execute(
                "select start_s, end_s, coalesce(score, 0), prior from windows where run_id = %s and video_id = %s", (self.run_id, self.video_id))]
            with self.conn.transaction():
                for c in cand_mod.select(rows, self.cfg.candidate_threshold, self.cfg.prior_weight):
                    self.conn.execute(
                        "insert into candidates (run_id, video_id, start_s, end_s, final_score, status) values (%s, %s, %s, %s, %s, 'pending')",
                        (self.run_id, self.video_id, c.start_s, c.end_s, c.final_score))
        for cid, start, end in self.conn.execute(
                "select id, start_s, end_s from candidates where run_id = %s and video_id = %s and segment_path is null order by start_s",
                (self.run_id, self.video_id)).fetchall():
            seg = self.segment_file(cid, start, end)
            path = segment_path(v["match_id"], cid)
            self.deps.storage.put(path, seg, "video/mp4")
            with self.conn.transaction():
                self.conn.execute("update candidates set segment_path = %s where id = %s", (path, cid))

    def verify_context(self, mc: enrich.MatchContext) -> VerifyContext:
        names = dict(self.conn.execute("select id, name from teams where id in (%s, %s)", (mc.home_team_id, mc.away_team_id)).fetchall())
        side = {mc.home_team_id: "home", mc.away_team_id: "away"}
        return VerifyContext(lineups=[LineupPlayer(side[p.team_id], p.shirt_number, p.name) for p in mc.lineup if p.team_id in side],
                             home_team=names.get(mc.home_team_id, "home"), away_team=names.get(mc.away_team_id, "away"))

    def _verify_usd(self) -> Decimal:
        rows = [r[0] for r in self.conn.execute(
            "select v.usd from verifications v join candidates c on c.id = v.candidate_id where c.run_id = %s and v.usd is not null",
            (self.run_id,))]
        return Decimal(statistics.median(rows)) if rows else DEFAULT_VERIFY_USD

    def step_verify(self) -> None:
        mc = self.match_context()
        context = self.verify_context(mc)
        pending = self.conn.execute(
            "select id, start_s, end_s from candidates where run_id = %s and video_id = %s and status = 'pending' order by start_s",
            (self.run_id, self.video_id)).fetchall()
        group = max(1, self.cfg.workers)
        for i in range(0, len(pending), group):
            chunk = pending[i: i + group]
            self.guard(self._verify_usd() * len(self.deps.verifiers) * len(chunk))
            items = [(cid, self.segment_file(cid, start, end)) for cid, start, end in chunk]
            results = verify.run_many(self.conn, items, self.deps.verifiers, context, workers=self.cfg.workers,
                                      run_id=self.run_id, match_id=mc.id)
            for cid, _ in items:
                try:
                    is_flop = verify.primary(results[cid], self.cfg.primary_verifier).is_flop
                except LookupError:
                    is_flop = False
                with self.conn.transaction():
                    self.conn.execute("update candidates set status = %s where id = %s",
                                      ("verified" if is_flop else "rejected", cid))

    def step_persist(self) -> None:
        mc = self.match_context()
        placed = []
        for cid, start, answers in self.conn.execute(
                "select c.id, c.start_s, v.answers from candidates c join verifications v on v.candidate_id = c.id and v.model = %s "
                "where c.run_id = %s and c.video_id = %s and c.status = 'verified' order by c.start_s",
                (self.cfg.primary_verifier, self.run_id, self.video_id)).fetchall():
            seg_start = max(0.0, start - self.cfg.pad_s)  # results are relative to the padded segment
            placed.append(dedupe.Placed(VerifyResult.model_validate(answers), seg_start, cid))
        config = enrich.DecideConfig(self.cfg.confirm_threshold, self.cfg.review_threshold, self.cfg.review_cap,
                                     self.cfg.player_min_conf, SimWeights.load(self.conn))
        sync = self.sync_result()
        for p in dedupe.collapse([p for p in placed if p.result.is_flop]):
            enrich.persist(self.conn, self.run_id, enrich.CandidateRef(p.candidate_id, self.video_id, p.video_start_s),
                           p.result, sync, mc, config)

    def step_clips(self) -> None:
        v = self.video()
        for iid, start, end in self.conn.execute(
                "select i.id, i.video_start_s, i.video_end_s from incidents i left join clips c on c.incident_id = i.id "
                "where i.run_id = %s and i.video_id = %s and i.status <> 'rejected' and c.id is null order by i.id",
                (self.run_id, self.video_id)).fetchall():
            clip_start = max(0.0, start - self.cfg.pad_s)
            clip_end = min(v["duration_s"], end + self.cfg.pad_s)  # the lead-in, the flop and the "recovery"
            local = self.deps.cut(self.local_video(), clip_start, clip_end, self.dir / "clips" / f"{iid}.mp4", reencode=True, audio=True)
            path = clip_path(v["match_id"], iid)
            self.deps.storage.put(path, local, "video/mp4")
            with self.conn.transaction():
                self.conn.execute("insert into clips (incident_id, path, duration_s, bytes) values (%s, %s, %s, %s) on conflict (incident_id) do nothing",
                                  (iid, path, clip_end - clip_start, Path(local).stat().st_size))

    def step_delete(self) -> None:
        v = self.video()
        if v["local_path"]:
            Path(v["local_path"]).unlink(missing_ok=True)
        shutil.rmtree(self.dir, ignore_errors=True)
        with self.conn.transaction():
            self.conn.execute("update videos set local_path = null, deleted_at = coalesce(deleted_at, now()) where id = %s", (self.video_id,))


# --- reporting ---------------------------------------------------------------------------


def status(conn: psycopg.Connection, run_id: int) -> dict:
    prefix = f"{run_id}:%"
    return {
        "jobs": dict(conn.execute("select status, count(*) from jobs where key like %s group by 1", (prefix,)).fetchall()),
        "failed": [{"kind": k, "key": key, "error": e} for k, key, e in conn.execute(
            "select kind, key, last_error from jobs where key like %s and status <> 'done' and last_error is not null",
            (prefix,)).fetchall()],
        "incidents": dict(conn.execute("select status, count(*) from incidents where run_id = %s group by 1", (run_id,)).fetchall()),
        "open_reviews": conn.execute("select count(*) from review_items where status = 'open'").fetchone()[0],
        "spent_usd": conn.execute("select coalesce(sum(usd), 0) from cost_ledger where run_id = %s", (run_id,)).fetchone()[0],
        "spent_total_usd": costs.spent(conn),
    }
