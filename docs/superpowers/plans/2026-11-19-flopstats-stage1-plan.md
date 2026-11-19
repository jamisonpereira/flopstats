# Flopstats Stage 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove the AI can reliably spot flops. Build the football data layer, the video detection pipeline and a private review screen, then run them on a 5-match pilot and one full Premier League season.

**Architecture:**
- A Python package (`flopstats`) runs every stage of the pipeline as resumable jobs. The job queue lives in Supabase Postgres.
- API-Football responses are stored raw and then built into clean tables.
- Footballia videos are scored in overlapping windows by a cheap decision model, checked by a stronger video model, clipped, and queued for Jamison's review.
- A small Next.js app (`web/`) holds the private review screen. It becomes the public site in stage 2.

**Tech Stack:**
- Python 3.12, uv, httpx, psycopg 3, pydantic v2, typer, pytest, respx, google-genai, Playwright (Python), ffmpeg
- Supabase (Postgres, Auth, Storage) with the Supabase CLI for migrations and local dev
- Next.js (App Router, TypeScript) with `@supabase/ssr`
- 1Password CLI (`op`) for secrets

**Spec:** `docs/superpowers/specs/2026-11-19-flopstats-design.md` (approved 2026-11-19). Executors read both documents.

**Out of scope here:** stage 2 (public site, weekly ingest, R2 move, fan input). It gets its own plan after stage 1 passes. The only stage-2 work here is Task 9's "first seen" logging, because the spec asks for footballia's posting lag to be measured early.

## Global Constraints

- **Secrets (revised 2026-11-19):** keys live in a git-ignored `.env` in the repo root on each machine, with a master copy in 1Password. The repo commits only `.env.example`. Never commit, log, echo or read `.env` contents. Code loads it at runtime through pydantic-settings (`env_file=".env"`). Agent no-read rules live in `.claude/settings.json`, `.cursorignore`, `CLAUDE.md` and `AGENTS.md`.
- **The pipeline runs on the Mac mini (and the MacBook for development).** Commands are plain `uv run flopstats ...`. There's no `op run` wrapper.
- **No secret-dependent step before the key exists:** every task that needs a key lists it under "Requires keys", and Task 1's `verify-setup` must pass for those keys first.
- **API-Football:** Pro plan. Respect both the per-minute and daily limits using the response rate-limit headers. Never repeat a call whose raw response is already stored.
- **Budget:** stage 1 AI spend is capped at **$500** in total, enforced in code (`FLOPSTATS_BUDGET_USD`, default `500`). The pipeline stops before going over.
- **Starting values:**
  - Windows are **20 s long every 10 s**.
  - The review cap per match is **off** (`null`). Every borderline item goes to review.
  - First-pass model: `gemini-decision-1`. Verifier: chosen in the pilot (Task 18).
- **Flop types** (exact enum): `dive`, `exaggeration`, `feigned_injury`, `time_wasting`.
- **Contact levels:** `none`, `light`, `real`.
- **Referee decisions:** `none`, `foul`, `yellow`, `red`, `penalty`.
- **SIM multipliers:**
  - Contact: none 1.5, light 1.0, real 0.5.
  - Payoff: nothing 1.0, foul 1.2, opponent booked 1.5, penalty won 2.0, penalty scored 2.5.
  - All weights live in config, not code.
- **Full match videos are deleted after processing.** Keep only candidate segments and clips.
- **Never guess silently:** an uncertain video↔match link or a low-confidence player ID creates a review item. It never becomes a silent pick.
- **Pass criteria (reported by Task 17):**
  - Precision ≥ 80% (Jamison agrees with AI-confirmed flops).
  - Near-complete recall of the known dives (`Card` events with comment "Simulation", and VAR "Penalty cancelled").
  - An optional highlights spot check.

## Review Focus

1. **API-Football errors arrive as HTTP 200** with a non-empty `errors` field and an empty `response`. Treat that as a failed fetch (log it, don't store it as good raw data, retry later), never as "no data".
2. **Unreadable on-screen clock** at sample points (replays, half-time, graphics). Time sync must pick other samples, and if it still can't fit a consistent mapping, mark the video `needs_review`. A wrong offset must never be guessed.
3. **Interrupted runs:** a crash, rate limit or budget stop mid-match must resume with no duplicate incidents, no duplicate charges and no repeated API or model calls for work already recorded.
4. **The same incident in several places:** shown again as a replay, or caught by overlapping windows. It becomes exactly one incident.
5. **A flopper who isn't confidently in the lineup:** an unreadable number, a substitute, or a shirt number not in the lineup. The result is a "who is this?" review item with the top lineup guesses, counted for the team only. It never crashes and never picks silently.

Each of these is pinned by a named test in its owning task.

---

## File structure

```
flopstats/                          (new GitHub repo)
├── .env.example                    variable names only (real values in git-ignored .env)
├── CLAUDE.md, AGENTS.md, .cursorignore, .claude/settings.json   agent rules (never read .env)
├── docs/superpowers/{specs,plans}/ design + this plan
├── supabase/
│   ├── config.toml
│   └── migrations/
│       ├── 0001_football_core.sql  countries…match_events, external_refs, review_items
│       ├── 0002_ops.sql            api_raw, jobs, cost_ledger, settings
│       └── 0003_detection.sql      videos, detection_runs, windows, candidates, incidents, incident_players, clips, reviews
├── pipeline/
│   ├── pyproject.toml
│   ├── src/flopstats/
│   │   ├── config.py               Settings (env + DB settings table)
│   │   ├── db.py                   connection + transaction helpers
│   │   ├── jobs.py                 Postgres job queue / load log
│   │   ├── costs.py                spend ledger + budget guard
│   │   ├── storage.py              StorageAdapter + SupabaseStorage + LocalStorage
│   │   ├── review.py               create/resolve review_items
│   │   ├── setup_check.py          verify-setup checks
│   │   ├── apifootball/{client.py, build.py, linking.py}
│   │   ├── footballia/{catalog.py, download.py, match_link.py}
│   │   ├── video/{ffmpeg.py, windows.py, timesync.py}
│   │   ├── detect/{models.py, gemini.py, priors.py, candidates.py,
│   │   │          verify.py, dedupe.py, decide.py, enrich.py, sim.py}
│   │   ├── runner.py               process-match orchestration
│   │   ├── report.py               pass-criteria + verifier comparison
│   │   └── cli.py                  typer entry point `flopstats`
│   └── tests/                      mirrors src/; fixtures/ holds sample API JSON + tiny videos
└── web/                            Next.js app (review screen now, public site in stage 2)
    ├── app/review/…                review pages
    ├── lib/supabase.ts
    └── tests/                      Playwright e2e
```

Tests that touch the database run against local Supabase (`supabase start`). The fixture `db` in `pipeline/tests/conftest.py` runs `supabase db reset` once per session and truncates tables between tests. Model and HTTP calls are always faked in tests: models through the protocols in `detect/models.py`, HTTP through `respx`.

---

### Task 0: Jamison's account and secrets setup (manual, no code)

**Owner:** Jamison. **Status:** accounts created on 2026-11-19.

- [ ] **Step 1: Create the accounts:** API-Football Pro, a new Supabase project `flopstats-v2` (East US), a Google AI Studio Gemini key with billing on, the footballia login, and the private GitHub repo `flopstats`.
- [ ] **Step 2: Save a master copy** of all values in a 1Password Secure Note, "Flopstats keys".
- [ ] **Step 3: On each machine (MacBook, Mac mini):** clone the repo, run `cp .env.example .env && chmod 600 .env`, and fill in the values.
- [ ] **Step 4: On each machine:** install the tools with `brew install ffmpeg uv node supabase/tap/supabase`, plus Docker Desktop or OrbStack.
- [ ] **Step 5: Extra verifier keys** (`VERIFIER_<NAME>_KEY` in `.env`): add them before Task 18, once Task 13 names the candidates.

---

### Task 1: Repo scaffold, config and `verify-setup`

**Files:**
- Create: `.env.example`, `pipeline/pyproject.toml`, `pipeline/src/flopstats/{config.py,db.py,setup_check.py,cli.py}`, `pipeline/tests/test_config.py`, `pipeline/tests/test_setup_check.py`, `.gitignore`, `README.md`
- Copy: the design doc to `docs/superpowers/specs/2026-11-19-flopstats-design.md` and this plan to `docs/superpowers/plans/`

**Requires keys:** none for the tests; all stage-1 keys for the real `verify-setup` run.

**Interfaces:**
- Produces:
  - `Settings` (pydantic-settings): fields `apifootball_key`, `supabase_url`, `supabase_service_key`, `database_url`, `gemini_key`, `footballia_username`, `footballia_password`, `budget_usd: Decimal = 500`, `verifier_keys: dict[str, str]` (parsed from env vars named `VERIFIER_<NAME>_KEY`)
  - `get_settings() -> Settings`
  - `connect() -> psycopg.Connection`
  - `check_all(settings) -> list[CheckResult]`, where `CheckResult(name: str, ok: bool, detail: str)`
  - CLI: `flopstats verify-setup`

- [ ] **Step 1: Write the failing tests.**
  - `test_settings_reads_env`: env vars map to fields, and `budget_usd` defaults to `Decimal("500")`.
  - `test_settings_never_repr_secrets`: `repr(settings)` contains no key values.
  - `test_check_all_reports_each_service`: with respx-mocked endpoints, it returns exactly 5 results named `api-football`, `supabase-db`, `supabase-storage`, `gemini`, `footballia-login`. A 401 from API-Football gives `ok=False` and a detail containing "401" but not the key.
- [ ] **Step 2: Run them to see them fail.** Run `uv run pytest pipeline/tests/test_config.py pipeline/tests/test_setup_check.py -v`. Expected: FAIL (import errors).
- [ ] **Step 3: Implement.**
  - `.env.example` holds blank lines for `APIFOOTBALL_KEY`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`, `DATABASE_URL`, `GEMINI_KEY`, `FOOTBALLIA_USERNAME`, `FOOTBALLIA_PASSWORD` (already committed in the initial scaffold). `Settings` loads `.env` from the repo root.
  - Use `SecretStr` for secret fields.
  - Each check makes one cheap call: API-Football `GET /status`; `SELECT 1`; list storage buckets; one tiny Gemini call; the footballia login check reuses Task 9's `login()` (stubbed until Task 9 and marked "skipped").
- [ ] **Step 4: Run the tests and confirm they pass.** Expected: PASS.
- [ ] **Step 5: Run for real.** Run `uv run flopstats verify-setup`. Expected: every check prints `OK`, except footballia, which shows "skipped" until Task 9.
- [ ] **Step 6: Commit.** Message: `chore: scaffold repo, config, verify-setup`.

---

### Task 2: Football core schema

**Files:**
- Create: `supabase/config.toml`, `supabase/migrations/0001_football_core.sql`, `pipeline/tests/conftest.py`, `pipeline/tests/test_schema_core.py`

**Interfaces:**
- Produces these tables (all with `id bigint generated always as identity`, `created_at`, `updated_at`):
  - `countries(name, code, flag_source_url, flag_path)`
  - `leagues(name, country_id, type, logo_source_url, logo_path)`
  - `seasons(league_id, year int, start_date, end_date)`, unique `(league_id, year)`
  - `venues(name, city, country_id, capacity, surface, image_source_url, image_path)`
  - `teams(name, code, country_id, venue_id, logo_source_url, logo_path)`
  - `team_seasons(team_id, season_id)`
  - `players(first_name, last_name, display_name, birth_date, nationality_country_id, photo_source_url, photo_path, photo_is_placeholder bool)`
  - `player_team_seasons(player_id, team_id, season_id, shirt_number, position)`
  - `coaches(name, nationality_country_id, photo_source_url, photo_path)`
  - `referees(name, nationality_country_id)`, unique `name`
  - `matches(season_id, home_team_id, away_team_id, kickoff_at timestamptz, venue_id, referee_id, home_coach_id, away_coach_id, round, status, goals_home, goals_away, attendance)`
  - `match_lineups(match_id, player_id, team_id, is_starter, shirt_number, position, minutes_played, fouls_drawn, fouls_committed, yellow_cards, red_cards, penalties_won, penalties_committed, penalties_scored, penalties_missed)`, unique `(match_id, player_id)`
  - `match_events(match_id, team_id, player_id null, assist_player_id null, minute smallint, extra_minute smallint, type text, detail text, comments text, source_hash text unique)`
  - `external_refs(entity_type text, entity_id bigint null, source text, source_id text, confidence real, status text check in ('linked','needs_review','rejected'))`, unique `(entity_type, source, source_id)`
  - `review_items(kind text check in ('match_link','video_sync','player_link','flop_verdict','flop_player'), subject_type text, subject_id bigint, payload jsonb, status text default 'open', resolution jsonb, resolved_at)`

- [ ] **Step 1: Write the failing tests.**
  - `test_core_tables_exist`: every table above exists.
  - `test_external_ref_unique`: a second insert with the same `(entity_type, source, source_id)` raises `UniqueViolation`.
  - `test_match_event_source_hash_unique`: the same for `source_hash`.
  - `test_review_item_kind_check`: kind `'banana'` is rejected.
- [ ] **Step 2: Run them to see them fail.** Run `uv run pytest pipeline/tests/test_schema_core.py -v`. Expected: FAIL.
- [ ] **Step 3: Write the migration.** Add the `updated_at` trigger function once and attach it to every table. Add foreign keys with `on delete restrict`, except child rows of matches (`on delete cascade`). Enable RLS on all tables with no public policies (the service role bypasses RLS).
- [ ] **Step 4: Apply and test.** Run `supabase db reset && uv run pytest pipeline/tests/test_schema_core.py -v`. Expected: PASS.
- [ ] **Step 5: Commit.** Message: `feat(db): football core schema`.

---

### Task 3: Ops schema, job queue and cost ledger

**Files:**
- Create: `supabase/migrations/0002_ops.sql`, `pipeline/src/flopstats/{jobs.py,costs.py}`, `pipeline/tests/{test_jobs.py,test_costs.py}`

**Interfaces:**
- Produces these tables:
  - `api_raw(endpoint, params jsonb, params_hash text unique, status_code, body jsonb, fetched_at)`
  - `jobs(kind, key text, payload jsonb, status check in ('pending','running','done','failed','needs_review','blocked_budget'), attempts int, last_error, locked_until timestamptz)`, unique `(kind, key)`
  - `cost_ledger(run_id null, match_id null, service, model, units jsonb, usd numeric(10,4), idempotency_key text unique, at)`
  - `settings(key text primary key, value jsonb)`
- Produces these functions:
  - `jobs.enqueue(conn, kind: str, key: str, payload: dict) -> int`: idempotent. Re-enqueueing an existing `(kind, key)` returns its id and doesn't reset a `done` job.
  - `jobs.claim(conn, kinds: list[str], lease_s: int = 900) -> Job | None`: uses `FOR UPDATE SKIP LOCKED` and also picks up `running` jobs whose lease has expired.
  - `jobs.complete(conn, job_id)`, `jobs.fail(conn, job_id, err: str, retry: bool)`, `jobs.mark(conn, job_id, status)`.
  - `costs.record(conn, *, service, model, units, usd, idempotency_key, run_id=None, match_id=None) -> bool`: returns False if the key already exists, so nothing is double-counted.
  - `costs.spent(conn) -> Decimal`
  - `costs.guard(conn, settings, estimate_usd: Decimal) -> None`: raises `BudgetExceeded` if `spent + estimate > budget_usd`.

- [ ] **Step 1: Write the failing tests.**
  - `test_enqueue_idempotent`
  - `test_claim_skips_locked_and_reclaims_expired_lease`
  - `test_fail_with_retry_returns_to_pending_and_increments_attempts`
  - `test_cost_record_idempotent` (the second call returns False, and `spent` is unchanged)
  - `test_guard_raises_when_estimate_would_exceed_budget`, with `budget_usd=500`, spent `499.50`, estimate `0.60` → `BudgetExceeded`
- [ ] **Step 2: Run them to see them fail.** Expected: FAIL.
- [ ] **Step 3: Implement** the migration and both modules.
- [ ] **Step 4: Run the tests and confirm they pass.** Expected: PASS.
- [ ] **Step 5: Commit.** Message: `feat: job queue, cost ledger, budget guard`.

---

### Task 4: API-Football client (rate limits and raw store)

**Files:**
- Create: `pipeline/src/flopstats/apifootball/client.py`, `pipeline/tests/apifootball/test_client.py`, `pipeline/tests/fixtures/apifootball/*.json`

**Requires keys:** `APIFOOTBALL_KEY` (for the manual smoke run only).

**Interfaces:**
- Consumes: `api_raw` table (Task 3).
- Produces:
  - `ApiFootball(conn, key: str, base_url="https://v3.football.api-sports.io")`
  - `.get(endpoint: str, params: dict) -> dict`: returns the stored body if `params_hash` exists, otherwise fetches, validates and stores it.
  - `.fixtures_for_season(league: int, season: int) -> list[dict]`
  - `.fixtures_by_ids(ids: list[int]) -> list[dict]`: chunks into groups of ≤20 and joins with `-`.
  - `.squad(team: int)`, `.coaches(team: int)`, `.venue(venue_id: int)`, `.player(player_id: int, season: int)`
  - Exceptions: `ApiError`, `RateLimited(retry_at: datetime)`
- Auth header: `x-apisports-key`. Rate headers: `x-ratelimit-requests-remaining` (daily) and `X-RateLimit-Remaining` (per minute). Confirm the names against the live docs during the smoke run.

- [ ] **Step 1: Write the failing tests** (respx).
  - `test_get_returns_cached_raw_without_http`: a second call with the same params makes 0 HTTP requests.
  - `test_errors_field_with_200_is_failure` (Review Focus #1): body `{"errors":{"token":"bad"},"response":[]}` raises `ApiError` and writes no `api_raw` row.
  - `test_pauses_when_minute_remaining_zero`: header `X-RateLimit-Remaining: 0` makes the next call sleep (an injected clock or sleep fake) until the next minute.
  - `test_daily_remaining_zero_raises_rate_limited`
  - `test_fixtures_by_ids_chunks_by_20`: 45 ids → 3 requests with 20, 20 and 5 ids.
- [ ] **Step 2: Run them to see them fail.** Expected: FAIL.
- [ ] **Step 3: Implement.** `params_hash` = sha256 of the endpoint plus canonical JSON of the params. Use httpx with a 30 s timeout. Retry 5xx responses up to 3 times with backoff.
- [ ] **Step 4: Run the tests and confirm they pass.** Expected: PASS.
- [ ] **Step 5: Smoke test.** Run `uv run flopstats api fetch-season --league 39 --season <YEAR>`, then `SELECT count(*) FROM api_raw`. Expected: about 20 rows.
- [ ] **Step 6: Commit.** Message: `feat(api): rate-limited API-Football client with raw store`.

---

### Task 5: Build clean tables from raw

**Files:**
- Create: `pipeline/src/flopstats/apifootball/build.py`, `pipeline/tests/apifootball/test_build.py`

**Interfaces:**
- Consumes: `api_raw` and `ApiFootball` (Task 4), `external_refs` (Task 2).
- Produces:
  - `build_season(conn, league_api_id: int, season_year: int) -> BuildReport`, where `BuildReport` has counts per table plus `needs_review: int`.
  - It's idempotent: rows are upserted through `external_refs(source='api-football')`. Running it twice changes nothing.
  - Match events get `source_hash` = sha256 of the fixture id plus the event's JSON.
  - Card events keep the API `comments` (for example "Simulation"). VAR events keep their `detail` (for example "Penalty cancelled").
  - Referee names are normalized by stripping the ", Country" suffix and collapsing whitespace before the upsert into `referees`.
  - Images: store only `*_source_url` (the downloads are stage 2).

- [ ] **Step 1: Write the failing tests**, using fixture JSON from 2 fixtures with events and lineups.
  - `test_build_creates_matches_teams_venue_referee`
  - `test_build_is_idempotent` (row counts are equal after two runs)
  - `test_simulation_card_comment_preserved`
  - `test_var_penalty_cancelled_preserved`
  - `test_lineup_stats_loaded`: the fixture player has `fouls_drawn=3` and `minutes_played=90`.
- [ ] **Step 2: Run them to see them fail.** Expected: FAIL.
- [ ] **Step 3: Implement.** Player linking for events calls Task 6's `link_event_player`. Until Task 6 exists, map only by API player id.
- [ ] **Step 4: Run the tests and confirm they pass.** Expected: PASS.
- [ ] **Step 5: Commit.** Message: `feat(api): build clean football tables from raw`.

---

### Task 6: Player linking, dedupe and the needs-review path

**Files:**
- Create: `pipeline/src/flopstats/apifootball/linking.py`, `pipeline/src/flopstats/review.py`, `pipeline/tests/apifootball/test_linking.py`, `pipeline/tests/test_review.py`

**Interfaces:**
- Produces:
  - `link_event_player(conn, match_id, team_id, api_player_id: int | None, name: str | None) -> LinkResult(player_id: int | None, confidence: float, method: str)`
    - Order: API id → exact name match within that match's lineup for the team → fuzzy match (`rapidfuzz` token_sort_ratio ≥ 90) within the lineup → none.
    - When nothing is confident, it creates a `review_items(kind='player_link')` row and returns `player_id=None`.
  - `find_duplicate_players(conn) -> list[tuple[int, int]]`: same normalized name and the same birth date.
  - `backfill_nationality(conn, client, season: int) -> int`: calls `client.player` for players without nationality.
  - `review.create(conn, kind, subject_type, subject_id, payload) -> int`: idempotent per `(kind, subject_type, subject_id)` while open.
  - `review.resolve(conn, item_id, resolution: dict) -> None`

- [ ] **Step 1: Write the failing tests.**
  - `test_link_by_api_id`
  - `test_link_by_exact_lineup_name`
  - `test_link_fuzzy_accent_insensitive`: "Joao Felix" matches "João Félix".
  - `test_unlinkable_creates_review_item_and_returns_none`
  - `test_find_duplicate_players`
  - `test_review_create_idempotent_while_open`
- [ ] **Step 2: Run them to see them fail.** Expected: FAIL.
- [ ] **Step 3: Implement** both modules, and wire `link_event_player` into `build_season`.
- [ ] **Step 4: Run the tests and confirm they pass**, including Task 5's tests. Expected: PASS.
- [ ] **Step 5: Real season build.** Run `uv run flopstats api build-season --league 39 --season <YEAR>`. Expected: 380 matches, and events with a null player under 2% (print it in the report). Investigate if it's higher.
- [ ] **Step 6: Commit.** Message: `feat(api): player linking, dedupe, review items`.

---

### Task 7: Storage adapter

**Files:**
- Create: `pipeline/src/flopstats/storage.py`, `pipeline/tests/test_storage.py`

**Interfaces:**
- Produces:
  - `class StorageAdapter(Protocol)`: `put(path: str, local_file: Path, content_type: str) -> None`, `delete(path: str) -> None`, `public_url(path: str) -> str`, `signed_url(path: str, expires_s: int) -> str`
  - `SupabaseStorage(url, service_key, bucket="media")` and `LocalStorage(root: Path)` (for tests)
  - `get_storage(settings) -> StorageAdapter`: picks the backend from `settings.storage_backend` (`supabase` by default). An R2 backend is added in stage 2 with the same protocol.
  - Path conventions: `clips/<match_id>/<incident_id>.mp4`, `segments/<match_id>/<candidate_id>.mp4`, `images/<kind>/<id>.<ext>`

- [ ] **Step 1: Write the failing tests.**
  - `test_local_put_then_url_then_delete`
  - `test_supabase_put_uses_upsert_and_content_type` (respx)
  - `test_get_storage_selects_backend`
- [ ] **Step 2: Run them to see them fail.** Expected: FAIL.
- [ ] **Step 3: Implement.** The `media` bucket is private. The review screen uses signed URLs.
- [ ] **Step 4: Run the tests and confirm they pass.** Expected: PASS.
- [ ] **Step 5: Commit.** Message: `feat: storage adapter`.

---

### Task 8: Detection schema

**Files:**
- Create: `supabase/migrations/0003_detection.sql`, `pipeline/tests/test_schema_detection.py`

**Interfaces:**
- Produces these tables:
  - `videos(match_id null, source text, source_url, duration_s, kickoff_offset_s, second_half_offset_s, sync_status check in ('pending','ok','needs_review'), local_path null, deleted_at null)`
  - `detection_runs(name, config jsonb, created_at)`. `config` holds window length and step, thresholds, review cap, padding, model ids and prompt versions.
  - `windows(run_id, video_id, start_s, end_s, score real, prior real, final_score real)`, unique `(run_id, video_id, start_s)`
  - `candidates(run_id, video_id, start_s, end_s, final_score, status check in ('pending','verified','rejected'), segment_path)`
  - `verifications(candidate_id, model, answers jsonb, confidence real, usd numeric)`, unique `(candidate_id, model)`
  - `incidents(run_id, match_id, video_id, candidate_id, type, video_start_s, video_end_s, game_minute, game_second, team_id, confidence real, status check in ('confirmed','review','rejected','ai_judged'), attrs jsonb, ref_decision, ref_penalized_team_id, consequence jsonb, sim_score real, dedupe_key text)`, unique `(run_id, video_id, dedupe_key)`
  - `incident_players(incident_id, player_id null, team_id, role check in ('flopper','alleged_fouler','other'), confidence real, guesses jsonb)`
  - `clips(incident_id unique, path, duration_s, bytes)`
  - `reviews(incident_id, item_id, decision check in ('confirm','reject','change_type','set_player'), value jsonb, reason text, at)`
  - `attrs` keys: `time_on_ground_s`, `rolls`, `fake_pain`, `clutched_part`, `contact_part`, `contact_level`, `miracle_recovery`, `recovery_trigger`, `pitch_x`, `pitch_y`, `pitch_conf`.

- [ ] **Step 1: Write the failing tests.**
  - `test_detection_tables_exist`
  - `test_incident_type_check_rejects_unknown`: only the 4 flop types are allowed.
  - `test_incident_dedupe_unique`
- [ ] **Step 2: Run them to see them fail.** Expected: FAIL.
- [ ] **Step 3: Write the migration.** `incidents.type` is a check constraint on the 4 values in Global Constraints.
- [ ] **Step 4: Apply and test.** Run `supabase db reset && uv run pytest pipeline/tests/test_schema_detection.py -v`. Expected: PASS.
- [ ] **Step 5: Commit.** Message: `feat(db): detection schema`.

---

### Task 9: Footballia catalog, download, match linking and first-seen logging

**Files:**
- Create: `pipeline/src/flopstats/footballia/{catalog.py,download.py,match_link.py}`, `pipeline/tests/footballia/{test_catalog.py,test_match_link.py,test_download.py}`, `pipeline/tests/fixtures/footballia/*.html`

**Requires keys:** `FOOTBALLIA_USERNAME`, `FOOTBALLIA_PASSWORD`.

**Reference:** the old repo's `video_scraper.py` and `scrape_game_pages.py` (login flow, `get_video_url`, next-part clicking), plus `urls/game_urls_2015_2025.csv`.

**Interfaces:**
- Produces:
  - `catalog.list_season(page, league: str, season: str) -> list[CatalogEntry(url, home, away, date, competition)]`
  - `catalog.record_first_seen(conn, entries) -> int`: upserts `external_refs(entity_type='footballia_listing', source='footballia', source_id=url)` with `payload.first_seen_at`. This supports the spec's posting-lag measurement. CLI: `flopstats footballia watch` (Jamison runs it daily on cron).
  - `download.login(page, username, password) -> None`
  - `download.fetch_match(url, dest_dir: Path) -> Path`: Playwright opens the page, captures the stream (HLS) URLs for every part or half, and `ffmpeg -c copy` concatenates them into one mp4. It raises `IncompleteVideo` if the total duration is under 85 minutes.
  - `match_link.link(conn, entry: CatalogEntry) -> MatchLink(match_id: int | None, confidence: float)`: matches on date ±1 day plus normalized home and away team names (an alias table seeded from the old repo's `utils.map_team_name` list). At confidence < 0.95 it creates a `review_items(kind='match_link')` row and returns `match_id=None`.

- [ ] **Step 1: Write the failing tests.**
  - `test_list_season_parses_fixture_html`
  - `test_record_first_seen_keeps_earliest_timestamp`
  - `test_link_exact_date_and_teams`
  - `test_link_team_alias` ("Spurs" → "Tottenham Hotspur")
  - `test_ambiguous_link_creates_review_item`
  - `test_incomplete_video_raises`: a fake ffprobe duration of 40 min raises `IncompleteVideo`.
- [ ] **Step 2: Run them to see them fail.** Expected: FAIL.
- [ ] **Step 3: Implement.** Playwright runs headless with a persistent context in `~/.flopstats/footballia-profile` so the login is reused. Replace the `footballia-login` stub in `setup_check` with a real `login()`.
- [ ] **Step 4: Run the tests and confirm they pass.** Expected: PASS.
- [ ] **Step 5: Manual smoke test.** Run `flopstats footballia fetch --url <one PL match>`. Expected: an mp4 of 90+ min, and `verify-setup` now shows footballia `OK`.
- [ ] **Step 6: Commit.** Message: `feat(footballia): catalog, download, match link, first-seen log`.

---

### Task 10: Video utilities and windows

**Files:**
- Create: `pipeline/src/flopstats/video/{ffmpeg.py,windows.py}`, `pipeline/tests/video/test_ffmpeg.py`, `pipeline/tests/video/test_windows.py`, `pipeline/tests/fixtures/video/tiny.mp4` (a 60 s test pattern made with ffmpeg `testsrc`)

**Interfaces:**
- Produces:
  - `ffmpeg.probe_duration(path) -> float`
  - `ffmpeg.cut(src, start_s, end_s, dest, reencode: bool) -> Path`: re-encoding uses `libx264 -preset veryfast -crf 26 -vf scale=-2:720 -an` for model segments, and keeps audio (`aac 96k`) for clips.
  - `ffmpeg.frame_at(src, t_s, dest_png) -> Path`
  - `windows.make(duration_s, length_s=20, step_s=10) -> list[tuple[float, float]]`: the last window is clipped to the duration.

- [ ] **Step 1: Write the failing tests.**
  - `test_windows_60s_len20_step10` → `[(0,20),(10,30),(20,40),(30,50),(40,60)]`
  - `test_windows_last_clipped` (65 s → the last is `(50,65)`)
  - `test_cut_produces_expected_duration` (±0.5 s)
  - `test_frame_at_writes_png`
- [ ] **Step 2: Run them to see them fail.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests and confirm they pass.** Expected: PASS.
- [ ] **Step 5: Commit.** Message: `feat(video): ffmpeg helpers and windowing`.

---

### Task 11: Time sync

**Files:**
- Create: `pipeline/src/flopstats/video/timesync.py`, `pipeline/tests/video/test_timesync.py`

**Interfaces:**
- Consumes: `ffmpeg.frame_at`, and `ClockReader` (the protocol in Task 12's `detect/models.py`; define the protocol here if Task 12 isn't done yet, and Task 12 imports it).
- Produces:
  - `class ClockReader(Protocol): read(png: Path) -> ClockReading | None`, where `ClockReading(minute: int, second: int, confidence: float)`
  - `sync(video_path, duration_s, reader, samples=24) -> SyncResult(kickoff_offset_s: float | None, second_half_offset_s: float | None, status: Literal['ok','needs_review'])`
    - Fit: each reading gives a candidate offset (`video_t - (minute*60+second)`) for the first half (clock ≤ 45:00+stoppage) or the second (clock ≥ 45:00 after the break). Take the median per half and require at least 5 agreeing readings within ±3 s. Otherwise `needs_review`.
  - `to_game_time(video_t, sync) -> tuple[int, int] | None` and `to_video_time(minute, second, sync) -> float | None`

- [ ] **Step 1: Write the failing tests** (a fake reader).
  - `test_sync_clean_readings_ok`
  - `test_sync_ignores_unreadable_and_outlier_samples` (Review Focus #2: 8 of 24 readings are `None` and 3 are wild outliers, and it's still `ok`)
  - `test_sync_mostly_unreadable_needs_review` (only 3 readings → `needs_review`, offsets `None`)
  - `test_round_trip_game_video_time`
- [ ] **Step 2: Run them to see them fail.** Expected: FAIL.
- [ ] **Step 3: Implement.** Samples are spread evenly across the video. Avoid the first and last 2 minutes.
- [ ] **Step 4: Run the tests and confirm they pass.** Expected: PASS.
- [ ] **Step 5: Commit.** Message: `feat(video): time sync from on-screen clock`.

---

### Task 12: Model interfaces, the Gemini adapters, the wide net and candidates

**Files:**
- Create: `pipeline/src/flopstats/detect/{models.py,gemini.py,priors.py,candidates.py}`, `pipeline/tests/detect/{test_priors.py,test_candidates.py,test_gemini.py}`

**Requires keys:** `GEMINI_KEY` (for the smoke test only).

**Interfaces:**
- Produces:
  - `class WindowScorer(Protocol)`: `score(segment: Path) -> ScoreResult(p_flop: float, usd: Decimal, raw: dict)`
  - `class Verifier(Protocol)`: `name: str`, `verify(segment: Path, context: VerifyContext) -> VerifyResult` (Task 13 defines `VerifyResult`)
  - `ClockReader` (re-exported from Task 11)
  - `gemini.DecisionScorer(api_key, model="gemini-decision-1")`: one closed-set question per window: "Does this clip show a player diving, exaggerating contact, feigning injury or time-wasting by staying down?" (yes/no) → `p_flop` = the probability of yes. Usage cost is computed from the input tokens the response reports and a configurable price (default `0.10` USD per 1M input tokens).
  - `gemini.DecisionClockReader`: reads the scoreboard clock from a frame (a minute/second answer, or "no clock visible").
  - `priors.window_priors(events: list[MatchEvent], lineups, sync, windows) -> list[float]`: a 0–1 boost. Windows within ±30 s of a foul-related card, a penalty, a VAR event, or an injury sub (`subst` with comment "Injury" where present) get 1.0, with linear decay to 0 at ±90 s.
  - `candidates.select(windows: list[WindowRow], threshold: float, prior_weight: float) -> list[Candidate]`: `final_score = max(score, score + prior_weight*prior)` clipped to 1. A prior never lowers a score. Adjacent or overlapping windows at or above the threshold merge into one candidate.

- [ ] **Step 1: Write the failing tests.**
  - `test_prior_peaks_at_event_and_decays`
  - `test_prior_never_lowers_score` (with a zero prior, `final_score == score`)
  - `test_overlapping_windows_merge_into_one_candidate` (Review Focus #4, part 1)
  - `test_below_threshold_not_selected`
  - `test_decision_scorer_maps_probability_and_cost`: a mocked SDK response gives `p_flop` 0.83 and `usd` = input tokens × price.
- [ ] **Step 2: Run them to see them fail.** Expected: FAIL.
- [ ] **Step 3: Implement.** `gemini.py` is the only module that imports `google.genai`. Check the Decisions API request and response shape against the current Google docs, and record the doc URL in a comment.
- [ ] **Step 4: Run the tests and confirm they pass.** Expected: PASS.
- [ ] **Step 5: Smoke test.** Score 3 windows from Task 9's downloaded match. Expected: probabilities between 0 and 1, with cost rows written.
- [ ] **Step 6: Commit.** Message: `feat(detect): model protocols, Gemini decision scorer, priors, candidates`.

---

### Task 13: Verification and replay dedupe

**Files:**
- Create: `pipeline/src/flopstats/detect/{verify.py,dedupe.py}`, the verifier adapters inside `gemini.py` plus an optional `detect/<vendor>.py` for each extra candidate, `pipeline/tests/detect/{test_verify.py,test_dedupe.py}`

**Interfaces:**
- Produces:
  - `VerifyContext(lineups: list[LineupPlayer], home_team, away_team, kit_notes: str | None)`
  - `VerifyResult` (pydantic, validated from model JSON):
    - `is_flop: bool`
    - `type: Literal['dive','exaggeration','feigned_injury','time_wasting'] | None`
    - `confidence: float`
    - `start_s: float`, `end_s: float` (relative to the segment)
    - `is_replay: bool`
    - `flopper: PlayerGuess(team: Literal['home','away'] | None, shirt_number: int | None, name: str | None, confidence: float)`
    - `others: list[PlayerGuess]`
    - `attrs: FlopAttrs`, which has `time_on_ground_s`, `rolls`, `fake_pain` (1–10), `clutched_part`, `contact_part`, `contact_level` (none/light/real), `miracle_recovery`, `recovery_trigger`, `pitch_x`, `pitch_y` (0–100, attacking left→right), `pitch_conf`
    - `ref_decision: Literal['none','foul','yellow','red','penalty']`
    - `usd: Decimal`
  - `verify.run(candidate, verifiers: list[Verifier], context) -> list[VerifyResult]`: runs every configured verifier (more than one during the pilot) and stores one `verifications` row per `(candidate, model)`. It skips any model already stored for that candidate.
  - `verify.primary(results, primary_model: str) -> VerifyResult`
  - `gemini.GeminiVerifier(api_key, model: str)`: structured JSON output against the `VerifyResult` schema, with the prompt version from the run config.
  - `dedupe.key(result, video_start_s) -> str`: the absolute start rounded to 15 s, plus the team and shirt number.
  - `dedupe.collapse(results_abs: list[...]) -> list[...]`: drops `is_replay=True` results when a non-replay within 120 s shares the same flopper. Otherwise it keeps the earliest.

- [ ] **Step 1: Write the failing tests.**
  - `test_invalid_model_json_retried_once_then_rejected`
  - `test_verify_skips_already_stored_model` (Review Focus #3: no second paid call)
  - `test_multiple_verifiers_each_stored`
  - `test_replay_collapses_into_original` (Review Focus #4, part 2)
  - `test_two_distinct_flops_same_minute_kept` (different floppers → 2)
- [ ] **Step 2: Run them to see them fail.** Expected: FAIL.
- [ ] **Step 3: Implement.** Propose 1–2 extra verifier candidates in the PR description, chosen from the strongest video-capable models available, and ask Jamison to add their keys (Task 0, step 2).
- [ ] **Step 4: Run the tests and confirm they pass.** Expected: PASS.
- [ ] **Step 5: Commit.** Message: `feat(detect): structured verification and replay dedupe`.

---

### Task 14: Decide, enrich and SIM

**Files:**
- Create: `pipeline/src/flopstats/detect/{decide.py,enrich.py,sim.py}`, `pipeline/tests/detect/{test_decide.py,test_enrich.py,test_sim.py}`

**Interfaces:**
- Consumes: `VerifyResult` (Task 13), `review.create` (Task 6), `to_game_time` (Task 11), `match_events` and `match_lineups`.
- Produces:
  - `decide.status(confidence, confirm_t, review_t, review_cap: int | None, review_count_so_far: int) -> Literal['confirmed','review','rejected','ai_judged']`. With `review_cap=None`, every borderline item becomes `review`.
  - `enrich.attribute(guess: PlayerGuess, lineup, team_id, min_conf: float) -> Attribution(player_id: int | None, confidence: float, guesses: list[dict])`: matches on shirt number within the team's lineup, falling back to the name. Below `min_conf`, or with no lineup match, it returns `player_id=None` with the top 3 lineup guesses.
  - `enrich.consequence(match_events, game_minute, game_second, team_id) -> dict`: finds a penalty awarded within 60 s, and whether it was scored. It also finds an opponent card within 60 s and a goal from the resulting set piece within 60 s. Keys: `penalty_awarded`, `penalty_scored`, `opponent_booked`, `goal_within_60s`.
  - `enrich.persist(conn, run_id, candidate, result, sync, match) -> int` (the incident id): writes the incident, its incident_players, a `review_items` row of kind `flop_verdict` when the status is `review`, and one of kind `flop_player` when the flopper is unattributed. It's idempotent through `dedupe_key`.
  - `sim.flop_score(attrs, consequence, ref_decision, confidence, weights: SimWeights) -> float`: `base * acting * ground * contact * payoff * bonus * confidence`, where:
    - `acting = fake_pain / 10`
    - `ground = 1 + ln(1 + time_on_ground_s / 10)`
    - `contact` and `payoff` use the Global Constraints values. Payoff picks the highest that applies.
    - `bonus = 1 + 0.05*min(rolls,5) + (0.1 if miracle_recovery else 0)`
    - `base = 10`
  - `sim.entity_sim(scores_by_entity: dict[int, float], minutes_by_entity: dict[int, int]) -> dict[int, float]`: per 90, scaled so the max is 100. Entities with fewer than 270 minutes are excluded.
  - `SimWeights` loads from `settings` key `sim_weights`, falling back to the defaults above.

- [ ] **Step 1: Write the failing tests.**
  - `test_status_no_cap_all_borderline_review`
  - `test_status_with_cap_overflow_ai_judged`
  - `test_attribute_by_shirt_number`
  - `test_unattributed_flopper_creates_flop_player_item_and_team_only` (Review Focus #5: shirt 44 isn't in the lineup → `player_id None`, a `review_items(kind='flop_player')` row with 3 guesses, and the incident keeps its `team_id`)
  - `test_consequence_penalty_scored`
  - `test_flop_score_contact_and_payoff_multipliers`: pain 8, 20 s, no contact, penalty scored, confidence 0.9 → `10*0.8*(1+ln 3)*1.5*2.5*1.0*0.9` within 1e-6
  - `test_entity_sim_scales_top_to_100`
  - `test_persist_idempotent` (Review Focus #3)
- [ ] **Step 2: Run them to see them fail.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests and confirm they pass.** Expected: PASS.
- [ ] **Step 5: Commit.** Message: `feat(detect): decide, enrich, SIM`.

---

### Task 15: Match runner and CLI

**Files:**
- Create: `pipeline/src/flopstats/runner.py`, extend `cli.py`, `pipeline/tests/test_runner.py`

**Interfaces:**
- Consumes: everything above.
- Produces:
  - `create_run(conn, name: str, config: RunConfig) -> int`. `RunConfig` (pydantic) holds `window_len_s=20`, `window_step_s=10`, `candidate_threshold`, `prior_weight`, `confirm_threshold`, `review_threshold`, `review_cap=None`, `pad_s=8`, `player_min_conf`, `scorer_model`, `verifier_models: list[str]`, `primary_verifier`, `prompt_versions`. It has no defaults for the thresholds: the pilot config sets them.
  - `process_match(conn, run_id, footballia_url, deps: Deps) -> MatchReport`. The steps are idempotent and each one is a job (`kind` = step, `key` = `run:video:step`):
    1. Download
    2. Link the match
    3. Sync time
    4. Score the windows
    5. Select candidates and cut their segments, uploading each segment to storage
    6. Verify
    7. Persist incidents
    8. Cut and upload clips (`pad_s` before, plus the recovery)
    9. Delete the full video
  - `costs.guard` is checked before each paid batch. When the budget runs out, the job goes to `blocked_budget` and the runner stops cleanly.
  - `Deps` bundles the storage, scorer, verifiers, clock reader and downloader, so tests inject fakes.
  - CLI:
    - `flopstats run create --name pilot-v1 --config pilot.json`
    - `flopstats run match --run <id> --url <url>`
    - `flopstats run season --run <id> --league 39 --season <YEAR> [--limit N] [--urls url1,url2,...]` (`--urls` restricts the run to those footballia matches)
    - `flopstats run status --run <id>`

- [ ] **Step 1: Write the failing tests** (all deps faked, local storage).
  - `test_process_match_end_to_end_with_fakes`: incidents, clips and review items are created, and the full video is deleted (`videos.deleted_at` set, file gone).
  - `test_resume_after_crash_mid_verify` (Review Focus #3): a fake verifier raises on the 3rd candidate. A re-run makes no repeated scorer calls, no duplicate incidents, and no new cost rows for finished work.
  - `test_budget_exhausted_stops_cleanly`: the jobs end `blocked_budget`, and nothing goes over the budget.
  - `test_needs_review_sync_skips_detection`: the match stops after sync with a `review_items(kind='video_sync')` row and no window scoring. Resolving it in review (by entering the offsets manually) re-queues the match.
  - `test_unlinked_match_pauses_until_reviewed`
- [ ] **Step 2: Run them to see them fail.** Expected: FAIL.
- [ ] **Step 3: Implement.** Process windows in batches of 50, with the budget guard estimate = batch size × the median cost per window so far (a default before the first batch: `0.002`).
- [ ] **Step 4: Run the tests and confirm they pass.** Expected: PASS.
- [ ] **Step 5: Commit.** Message: `feat: resumable match runner and CLI`.

---

### Task 16: Review screen (`web/`)

**Files:**
- Create: the `web/` Next.js app: `app/review/page.tsx` (queue), `app/review/[itemId]/page.tsx` (item), `app/review/actions.ts` (server actions), `app/login/page.tsx`, `lib/supabase.ts`, `middleware.ts`, `tests/review.spec.ts` (Playwright), `supabase/migrations/0004_review_access.sql`

**Requires keys:** Supabase url and anon key (from `.env`).

**Interfaces:**
- Consumes: `review_items`, `incidents`, `incident_players`, `clips`, `match_lineups`, `players`, and storage signed URLs (generated on the server with the service key and never sent to the browser).
- Produces:
  - Access: Supabase Auth magic link. Only emails in the `settings` key `admin_emails` can use `/review`. RLS policies on the review tables allow `select`/`update` for those emails.
  - Queue page: open items grouped by match, filterable by kind (`flop_verdict`, `flop_player`, `match_link`, `video_sync`, `player_link`). It shows counts, plus a "spot check" tab that samples 10% of `confirmed` incidents for each run.
  - Item page: the clip player (signed URL), the AI verdict, type, confidence, key attrs, the game minute and the lineup guesses.
  - Actions, each writing a `reviews` row and resolving the `review_items` row:
    - ✓ confirm → incident `confirmed`
    - ✗ not a flop → `rejected`
    - change type (the 4 types)
    - set player (pick from the lineup or search the squad) → `incident_players.player_id`
    - For `match_link` items: pick the match or reject.
    - For `video_sync` items: enter the kickoff and second-half video times (mm:ss) while watching the video, which sets the offsets and re-queues the match.
  - Keyboard shortcuts: `y` confirm, `n` reject, `1–4` type, `j/k` next/previous.

- [ ] **Step 1: Write the failing e2e tests** (local Supabase seeded by a fixture script).
  - `non-admin is redirected from /review`
  - `confirm resolves item and sets incident confirmed`
  - `set player from lineup guess updates incident_players and closes flop_player item`
  - `spot check tab shows confirmed incidents only`
- [ ] **Step 2: Run them to see them fail.** Run `cd web && npx playwright test`. Expected: FAIL.
- [ ] **Step 3: Implement.** Keep the UI plain and fast: a server-rendered list, mobile-friendly so review works on a phone.
- [ ] **Step 4: Run the tests and confirm they pass.** Expected: PASS.
- [ ] **Step 5: Commit.** Message: `feat(web): private review screen`.

---

### Task 17: Pass-criteria and verifier comparison reports

**Files:**
- Create: `pipeline/src/flopstats/report.py`, `pipeline/tests/test_report.py`

**Interfaces:**
- Produces:
  - `precision(conn, run_id) -> Precision(agreed: int, reviewed: int, rate: float)`: among AI-confirmed or auto-confirmed incidents that Jamison reviewed (spot checks plus any decisions made on them), the share he confirmed.
  - `known_dive_recall(conn, run_id) -> Recall(found: int, total: int, missed: list[dict])`. Known dives are `match_events` with `type='Card' AND comments ILIKE 'Simulation%'`, or `type='Var' AND detail='Penalty cancelled'`. An event counts as found when a confirmed or review incident lies within ±60 s of game time.
  - `verifier_comparison(conn, run_id) -> list[VerifierStats(model, agreed_with_jamison: int, reviewed: int, usd_per_match: float)]`
  - `cost_projection(conn, run_id, matches_total: int) -> Decimal`
  - CLI: `flopstats report --run <id>`, which prints all four plus a PASS/FAIL line against the 80% precision bar and the known-dive recall (configurable, default ≥ 90%).

- [ ] **Step 1: Write the failing tests.**
  - `test_precision_counts_only_reviewed_confirmed`
  - `test_known_dive_found_within_60s`
  - `test_known_dive_missed_listed`
  - `test_verifier_comparison_per_model`
  - `test_cost_projection_scales_by_matches`
- [ ] **Step 2: Run them to see them fail.** Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the tests and confirm they pass.** Expected: PASS.
- [ ] **Step 5: Commit.** Message: `feat: pass-criteria and verifier comparison reports`.

---

### Task 18: Pilot (5 matches), operational

**Owner:** builder plus Jamison. No new code unless the pilot finds bugs (fix those through the normal TDD cycle in their owning task's files).

- [ ] **Step 1: Pick 5 matches** from the chosen season that between them contain at least 3 known dives. Query `match_events` for them.
- [ ] **Step 2: Write `pilot.json`** with `verifier_models` = Gemini Pro-class plus 1–2 candidates, starting thresholds `candidate_threshold=0.35`, `prior_weight=0.3`, `confirm_threshold=0.85`, `review_threshold=0.5`, `player_min_conf=0.8`, `review_cap=null`.
- [ ] **Step 3: Run the pilot.** Run `uv run flopstats run season --run <id> --league 39 --season <YEAR> --urls <the 5 urls>`. Expected: all 5 matches reach `done` (or `needs_review`, if a sync or link is unclear and then resolved in review).
- [ ] **Step 4: Jamison reviews** every item in `/review`, including the spot-check tab.
- [ ] **Step 5: Run `flopstats report --run <id>`**, and share precision, recall, the verifier comparison and the projected season cost with Jamison.
- [ ] **Step 6: Jamison picks the primary verifier.** Tune the thresholds if the review load or precision is off, and record the final config as `season-v1.json` in the repo. If the projected season cost is over $500, propose specific cuts (a longer window step, a cheaper verifier, a higher candidate threshold) and get Jamison's OK before Task 19.
- [ ] **Step 7: Commit** `season-v1.json` and a short `docs/pilot-results.md` (the numbers, the choices and why).

---

### Task 19: Full season run, operational

- [ ] **Step 1: Create the season run.** Run `flopstats run create --name season-v1 --config season-v1.json`.
- [ ] **Step 2: Run it.** Run `flopstats run season --run <id> --league 39 --season <YEAR>` on the laptop (or a cloud server with the service account), batched overnight. It resumes on restart.
- [ ] **Step 3: Monitor.** Run `flopstats run status` daily to watch progress, spend against the $500 cap, failed jobs and the open review count.
- [ ] **Step 4: Jamison works through `/review`** as it fills.
- [ ] **Step 5: Final report.** Run `flopstats report --run <id>`. Expected: the PASS/FAIL line for stage 1. Write `docs/stage1-results.md` with the numbers, and take the go/no-go for stage 2 to Jamison.
- [ ] **Step 6: Commit** the results doc.

---

## Stage 2 (separate plan, written after stage 1 passes)

These are outlined here only so stage 1 doesn't block them:
- The public Next.js site on Vercel (pages per spec §10).
- The SIM leaderboards from `sim.entity_sim`.
- Share cards.
- Image re-collection into storage.
- Fan input with auth and rate limits.
- Weekly ingest on a schedule, timed by the `footballia watch` lag data.
- R2 behind the `StorageAdapter`.
- Reserved ad spots, and the newsletter soon after launch.
