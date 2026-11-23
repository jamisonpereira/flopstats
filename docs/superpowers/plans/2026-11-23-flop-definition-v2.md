# Flop Definition v2 and Judging Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-judge pilot 2's stored candidate clips with a v2 flop prompt (flop yes/no + theatrics 1–10 + who), let Jamison judge them on a keyboard-first screen, and score Pro and Flash against those judgments.

**Architecture:** A v2 prompt and answer schema sit beside v1 in `detect/`. A new `rejudge` module copies run 2's candidates into a new run (linked by `source_candidate_id`), downloads each stored segment and runs both verifiers with v2. Judgments live in a new `judgments` table keyed on the original clip. The web review screen gets a Judge tab, and `flopstats report --judged-run` prints the scorecard.

**Tech Stack:** Python 3.12 + uv, psycopg 3, httpx/respx, typer, pytest; Supabase Postgres migrations; Next.js 15 + supabase-js, Playwright.

**Spec:** `docs/superpowers/specs/2026-11-23-flop-definition-v2-design.md`

## Global Constraints

- Never read `.env` or any `.env.*` except `.env.example`; never print secrets (AGENTS.md).
- v1 prompt, `ModelAnswer` and runs 1–2 keep working unchanged; the existing report must still run for run 2.
- Theatrics is an integer 1–10, null when not a flop.
- Judgments record what is in the clip: `is_flop` (null = can't tell), `theatrics`, `team` (`home`/`away`/null), `player_id` (null = can't tell), `shown_model`, `note`.
- Judgments key on the original (run 2) candidate and `on delete restrict`.
- Order: flagged clips by match then time, one clip both models rejected after every three, then the rest of the rejected.
- The shown model is Pro or Flash chosen per clip, stored, never named on screen.
- Hosted DB migrations are pushed only after Jamison says yes, in Task 8.
- The draft v2 prompt text in the spec is copied verbatim (Jamison may edit it later).

## Review Focus

1. A clip whose verifier output is invalid or blocked: rejudge stores it and moves on; the judge screen shows the clip with "no answer" and still lets Jamison judge it. (Task 4, Task 7)
2. Rerunning `rejudge` after a crash: no second copy of any candidate and no model paid twice. (Task 4)
3. A segment missing from storage: that candidate is skipped with a message, the rest continue. (Task 4)
4. A model guess whose shirt number isn't in the lineup, or whose team is null: the judge screen pre-selects "can't tell"; the scorecard only marks player/team wrong when Jamison named one. (Task 6, Task 7)
5. Judging the same clip twice overwrites the row, and deleting the judged run is refused. (Task 3, Task 7)

---

### Task 1: v2 answer schema and prompt

**Files:**
- Modify: `pipeline/src/flopstats/detect/verify.py` (add `ModelAnswerV2`, `VerifyResultV2`; `run_many` gains `result_cls`)
- Modify: `pipeline/src/flopstats/detect/gemini.py` (add `VERIFY_PROMPT_V2`; `PROMPTS` → `{"v1": (VERIFY_PROMPT_V1, ModelAnswer), "v2": (VERIFY_PROMPT_V2, ModelAnswerV2)}`; `GeminiVerifier` builds its schema and validates against the version's answer class)
- Test: `pipeline/tests/detect/test_gemini.py`, `pipeline/tests/detect/test_verify.py`

**Interfaces:**
- Produces:
  - `class ModelAnswerV2(_ModelText)`: `is_flop: bool`, `confidence: float (0–1)`, `theatrics: int | None (1–10)`, `what_happened: str = ""`, `start_s: float >= 0`, `end_s: float >= 0`, `flopper: PlayerGuess`
  - `class VerifyResultV2(ModelAnswerV2)`: `usd: Decimal = 0`, `model: str | None = None`
  - `GeminiVerifier(..., prompt_version="v2").verify(segment, context) -> VerifyResultV2`
  - `run_many(conn, items, verifiers, context, *, workers=1, run_id=None, match_id=None, result_cls=VerifyResult) -> dict[int, list]`

- [ ] **Step 1: Write the failing tests**

```python
# test_verify.py
def test_v2_answer_requires_theatrics_in_range():
    ok = ModelAnswerV2(is_flop=True, confidence=0.9, theatrics=7, what_happened="rolls twice",
                       start_s=3, end_s=9, flopper=PlayerGuess(team="home", shirt_number=7))
    assert ok.theatrics == 7
    for bad in (0, 11):
        with pytest.raises(ValidationError):
            ModelAnswerV2(is_flop=True, confidence=0.9, theatrics=bad, start_s=0, end_s=1)

def test_run_many_returns_v2_results_when_asked(db, ...):  # one fake verifier returning a VerifyResultV2
    out = verify.run_many(db, [(cid, seg)], [fake_v2], ctx, result_cls=VerifyResultV2)
    assert isinstance(out[cid][0], VerifyResultV2) and out[cid][0].theatrics == 5

# test_gemini.py (respx, like the existing v1 verifier test)
def test_v2_verifier_sends_v2_prompt_and_schema_and_parses_answer(respx_mock, tmp_path):
    # request body: prompt text contains "THEATRICS" and "Whether the referee gives a foul";
    # responseJsonSchema has "theatrics" and no "attrs"; returns VerifyResultV2 with theatrics 4
def test_v1_verifier_unchanged(...)  # existing test keeps passing
```

- [ ] **Step 2: Run them to see them fail**

Run: `cd pipeline && uv run pytest tests/detect/test_verify.py tests/detect/test_gemini.py -q`
Expected: FAIL, `ModelAnswerV2` not defined.

- [ ] **Step 3: Implement**

`VERIFY_PROMPT_V2` is the spec's draft prompt verbatim, with `{home}`, `{away}`, `{kits}`, `{lineups}` placeholders. `GeminiVerifier.__init__` looks up `(text, answer_cls) = PROMPTS[prompt_version]`, builds `_schema` from `answer_cls`, and `verify` validates with `answer_cls` and returns `VerifyResult` (v1) or `VerifyResultV2` (v2). `run_many` validates stored answers with `result_cls`.

- [ ] **Step 4: Run them to see them pass, then the whole suite**

Run: `uv run pytest -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add pipeline/src/flopstats/detect pipeline/tests/detect
git commit -m "feat: v2 flop prompt: flop yes/no, theatrics 1-10, who"
```

### Task 2: Download a stored file

**Files:**
- Modify: `pipeline/src/flopstats/storage.py`
- Test: `pipeline/tests/test_storage.py`

**Interfaces:**
- Produces: `StorageAdapter.get(path: str, dest: Path) -> Path` on `LocalStorage` (copy) and `SupabaseStorage` (GET `/object/{bucket}/{path}` with the service-key headers, streamed to `dest`); a missing object raises `FileNotFoundError(path)`, other errors go through `_raise`.

- [ ] **Step 1: Write the failing tests:** `test_local_get_copies_the_file`, `test_supabase_get_streams_to_dest` (respx: 200 with bytes → `dest.read_bytes()` equals them; request carries the apikey header), `test_supabase_get_missing_raises_file_not_found` (respx 400 with `{"statusCode":"404","error":"not_found"}` and a plain 404 both → `FileNotFoundError`).
- [ ] **Step 2: Run:** `uv run pytest tests/test_storage.py -q`. Expected: FAIL, no `get`.
- [ ] **Step 3: Implement** `get` on both adapters and the Protocol.
- [ ] **Step 4: Run:** `uv run pytest tests/test_storage.py -q`. Expected: PASS.
- [ ] **Step 5: Commit:** `git commit -m "feat: download stored files"`

### Task 3: `source_candidate_id` and the `judgments` table

**Files:**
- Create: `supabase/migrations/0010_judgments.sql`
- Test: `pipeline/tests/test_judgments_schema.py`

**Interfaces:**
- Produces:
  - `candidates.source_candidate_id bigint references candidates(id) on delete restrict` (nullable), indexed.
  - `judgments`: `id identity pk`, `candidate_id bigint not null unique references candidates(id) on delete restrict`, `is_flop boolean`, `theatrics smallint check (theatrics between 1 and 10)`, `team text check (team in ('home','away'))`, `player_id bigint references players(id) on delete restrict`, `shown_model text`, `note text`, `created_at`, `updated_at`.
  - RLS on, with `admin_select`, `admin_insert` and `admin_update` policies for `authenticated` using `public.is_admin()` (as in 0006/0008). Grants come from 0009's default privileges; the test checks them.

- [ ] **Step 1: Write the failing tests**
  - `test_judgment_theatrics_must_be_1_to_10`: inserting 0 or 11 raises `CheckViolation`.
  - `test_one_judgment_per_clip`: a second insert for the same candidate raises `UniqueViolation`, so the app upserts.
  - `test_deleting_a_judged_run_is_refused`: delete the run that owns the judged candidate → `ForeignKeyViolation`.
  - `test_api_roles_can_use_judgments`: `has_table_privilege('authenticated', 'judgments', 'insert')` is true and the `anon` select privilege is false.
- [ ] **Step 2: Run:** `uv run pytest tests/test_judgments_schema.py -q`. Expected: FAIL, no table.
- [ ] **Step 3: Write the migration.**
- [ ] **Step 4: Run the whole suite** (it rebuilds the DB from migrations): `uv run pytest -q`. Expected: all pass, including `test_api_grants.py`.
- [ ] **Step 5: Commit:** `git commit -m "feat: judgments table and source_candidate_id"`

### Task 4: The rejudge module

**Files:**
- Create: `pipeline/src/flopstats/rejudge.py`
- Modify: `pipeline/src/flopstats/runner.py` (extract the body of `_Ctx.verify_context`/`match_context`'s lineup query into module-level `load_verify_context(conn, match_id) -> VerifyContext`; `_Ctx` calls it)
- Modify: `RunConfig` gains `source_run_id: int | None = None`
- Test: `pipeline/tests/test_rejudge.py`

**Interfaces:**
- Consumes: `VerifyResultV2` and `run_many(..., result_cls=)` (Task 1); `StorageAdapter.get` (Task 2); `candidates.source_candidate_id` (Task 3).
- Produces:
  - `copy_candidates(conn, from_run: int, to_run: int) -> int`: copies every `from_run` candidate with a `segment_path` that has no copy in `to_run` yet; returns the number copied.
  - `@dataclass RejudgeDeps(storage, verifiers: list, primary_verifier: str, workers: int, settings, workdir: Path)`
  - `@dataclass RejudgeSummary(judged: int, flops: int, skipped: list[int], failed: list[int])`
  - `rejudge(conn, run_id: int, deps: RejudgeDeps, *, log=print) -> RejudgeSummary`: for each match, a VerifyContext from `load_verify_context`. The pending candidates go in groups of `workers`: `costs.guard` per group (median stored v2 cost × verifiers × group, `DEFAULT_VERIFY_USD` before any exist), `storage.get` each segment into `workdir`, `run_many(..., result_cls=VerifyResultV2, run_id=run_id, match_id=...)`, then status `verified` if the primary verifier's `is_flop` is true, else `rejected` (also `rejected` when the primary has no valid answer). Temp files are deleted after each group.

- [ ] **Step 1: Write the failing tests.** Fixtures: the `world` pattern from `test_runner.py`, a run 2 with three candidates with `segment_path`s stored in `LocalStorage`, and one without a path. Fake verifiers return `VerifyResultV2`; one of them can be set to raise `InvalidModelOutput`.
  - `test_copy_candidates_links_each_copy_to_its_source_and_is_idempotent`: copies 3 the first time, 0 the second; each copy has the source's times, `segment_path` and `source_candidate_id`.
  - `test_rejudge_verifies_every_copy_with_both_models_and_sets_status_by_primary`: 6 verifications; statuses follow the primary fake's `is_flop`; summary counts match.
  - `test_rejudge_resumes_without_paying_twice` (Review Focus 2): crash a fake verifier after 2 calls, rerun, total calls = 6 and the `cost_ledger` has 6 verify rows.
  - `test_invalid_output_is_stored_and_clip_rejected` (Review Focus 1).
  - `test_missing_segment_is_skipped_and_reported` (Review Focus 3): delete one file from storage; the summary's `skipped` has that id and the others are judged.
- [ ] **Step 2: Run:** `uv run pytest tests/test_rejudge.py -q`. Expected: FAIL, no module.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the whole suite:** `uv run pytest -q`. Expected: all pass (runner tests confirm the `load_verify_context` extraction).
- [ ] **Step 5: Commit:** `git commit -m "feat: re-judge stored candidates with a new prompt"`

### Task 5: `flopstats rejudge` command and the v2 run config

**Files:**
- Modify: `pipeline/src/flopstats/cli.py` (extract `_build_verifiers(settings, cfg) -> list` from `_build_deps`; add a top-level `rejudge` command)
- Create: `runs/pilot-v2.json`: `runs/pilot.json` plus `"prompt_versions": {"verify": "v2"}` and `"source_run_id": 2`
- Test: `pipeline/tests/test_cli_run.py`

**Interfaces:**
- Consumes: `copy_candidates`, `rejudge`, `RejudgeDeps` (Task 4).
- Produces: `flopstats rejudge --from-run INT --name TEXT --config PATH [--workers INT]`. It creates or reuses the run named `--name` (with `config.source_run_id` set to `--from-run`), copies, rejudges, and prints `run <id>: judged N, flops F, skipped S, failed X, $<cost>`.

- [ ] **Step 1: Write the failing test:** `test_rejudge_command_creates_run_copies_and_judges` (monkeypatch `_build_verifiers` to return fakes and `get_storage` to `LocalStorage`; run it twice; the second run prints `judged 0`).
- [ ] **Step 2: Run:** `uv run pytest tests/test_cli_run.py -q -k rejudge`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the whole suite:** `uv run pytest -q`. Expected: all pass.
- [ ] **Step 5: Commit:** `git commit -m "feat: flopstats rejudge command and pilot-v2 config"`

### Task 6: Scorecard

**Files:**
- Modify: `pipeline/src/flopstats/report.py`, `pipeline/src/flopstats/cli.py` (`report --judged-run INT` prints the scorecard instead of the stage 1 report)
- Test: `pipeline/tests/test_report_judged.py`

**Interfaces:**
- Consumes: the `judgments` table (Task 3); the run's v2 `verifications` (Task 4).
- Produces:
  - `@dataclass ModelScore(model, called, called_right, precision, flops_judged, caught, recall, theatrics_n, theatrics_mae, theatrics_within2, team_n, team_right, player_n, player_right, shown_n)`
  - `judged_scorecard(conn, run_id) -> list[ModelScore]`: judgments join through `candidates.source_candidate_id`.
    - "Can't tell" (null) is left out of the metric it is unsure about.
    - Team and player are scored on clips where Jamison and the model both say flop and Jamison gave a value.
    - The model's player is the lineup player with the guessed team side and shirt number; a guess not in the lineup counts as wrong (Review Focus 4).
    - `shown_n` is how many judged clips showed that model.
  - `disagreements(conn, run_id, limit=10) -> list[dict]`: candidate id, model, Jamison's flop/theatrics vs the model's, and `what_happened`. Flop yes/no disagreements come first, then the largest theatrics gaps.
  - `run_cost(conn, run_id) -> Decimal`.
  - `overlapping_judged(conn, run_id) -> int`: judged clips whose time range overlaps another judged clip of the same video (the spec's duplicate note), printed under the scorecard.

- [ ] **Step 1: Write the failing tests** with hand-built rows (2 models, 6 judged clips):
  - `test_precision_and_recall_per_model`: exact counts.
  - `test_cant_tell_is_left_out`.
  - `test_theatrics_mae_and_within_two`: e.g. Jamison 7 vs model 4 and 6 → mae 2.0, within2 1/2.
  - `test_player_scored_from_shirt_number_and_unknown_shirt_is_wrong`.
  - `test_disagreements_put_flop_mismatches_first`.
  - `test_overlapping_judged_counts_overlaps`.
- [ ] **Step 2: Run:** `uv run pytest tests/test_report_judged.py -q`. Expected: FAIL.
- [ ] **Step 3: Implement.**
- [ ] **Step 4: Run the whole suite.** Expected: all pass.
- [ ] **Step 5: Commit:** `git commit -m "feat: scorecard for judged runs"`

### Task 7: Judge tab on the review screen

**Files:**
- Create: `web/lib/judge.ts` (pure: `judgeOrder`, `shownModel`, `lineupPick`)
- Create: `web/app/review/judge/page.tsx` (redirects to the next unjudged clip in order, or shows "all judged" with counts)
- Create: `web/app/review/judge/[candidateId]/page.tsx` (one clip per screen)
- Create: `web/app/review/judge/actions.ts` (`saveJudgment`)
- Create: `web/app/review/judge/JudgeKeys.tsx` (keyboard handling, client component)
- Modify: `web/app/review/page.tsx` (add a "Judge" tab linking `/review/judge?run=<latest run whose config has source_run_id>`)
- Test: `web/tests/judge-order.spec.ts` (pure), `web/tests/judge.spec.ts` (e2e against local Supabase, using `seed.ts` helpers)

**Interfaces:**
- Consumes: the `judgments` table and `candidates.source_candidate_id` (Task 3); v2 answers in `verifications.answers` (Task 1 shape); `signedClipUrl(path)` (existing, works for any media path).
- Produces:
  - `judgeOrder(c: {id:number; matchId:number; startS:number; flagged:boolean}[]): number[]`
    - Flagged clips (either model said flop) come first, sorted by matchId then startS.
    - After every 3 flagged clips, insert the next unflagged clip. Unflagged clips are ordered by `Math.imul(id, 2654435761) >>> 0` (the same hash as `spotSample`).
    - The remaining unflagged clips follow at the end.
  - `shownModel(candidateId: number, models: string[]): string`: deterministic per clip, using the same hash mod `models.length`.
  - `lineupPick(guess: {team?: "home"|"away"|null; shirt_number?: number|null}, lineup: {team:"home"|"away"; shirt:number|null; playerId:number}[]): number | null`: null when the team or shirt is missing or not found.
  - `saveJudgment(form)`: upserts on `candidate_id` (= the source candidate) with `is_flop`, `theatrics`, `team`, `player_id`, `shown_model`, `note`, then redirects to `/review/judge?run=…`.

- [ ] **Step 1: Write the failing pure tests** (`judge-order.spec.ts`):
  - `judgeOrder interleaves one rejected clip after every three flagged`: 7 flagged and 4 unflagged → pattern F F F R F F F R F R R, with flagged in match/time order.
  - `shownModel is stable and uses both models`: the same id gives the same answer, and across ids 1..20 both models appear.
  - `lineupPick returns null for an unknown shirt or a missing team` (Review Focus 4).
- [ ] **Step 2: Run:** `cd web && npx playwright test tests/judge-order.spec.ts`. Expected: FAIL, no module.
- [ ] **Step 3: Implement `web/lib/judge.ts`.** Run again. Expected: PASS.
- [ ] **Step 4: Write the failing e2e test** (`judge.spec.ts`). Seed: run 2 with 2 candidates; run 3 copies with `source_candidate_id`; v2 verifications for 2 models, one of them `{"invalid": true}`; a segment file uploaded to local storage.
  - `judge: y, 7, Enter saves a judgment on the source clip and moves on`.
  - `judging a clip again overwrites it` (Review Focus 5): judge it, revisit `/review/judge/<id>`, press `n` and Enter; there is 1 row and `is_flop` is false.
  - `a clip with no valid answer still shows and can be judged` (Review Focus 1): the "no answer" text is visible.
- [ ] **Step 5: Run:** `npx playwright test tests/judge.spec.ts`. Expected: FAIL.
- [ ] **Step 6: Implement the pages, action and keys.**
  - **What the clip page shows:** the `<video>` plays the signed segment URL, with the model's `start_s`–`end_s` noted under it ("flop at 0:12–0:18"). Beside it: the shown model's flop yes/no, theatrics, `what_happened`, team, and the player named from the lineup, without the model's name. The progress line reads "judged N of M".
  - **Keys:**
    - `y` / `n` / `?`: flop yes, no, or can't tell.
    - `1`–`9`, and `0` for 10: theatrics, pre-filled from the model when it said flop.
    - `h` / `a` / `t`: team home, away, or can't tell, pre-selected from the guess.
    - The player is a `<select>` over the lineup plus "can't tell", pre-selected with `lineupPick`.
    - An optional note `<input>` (focusing it suspends the single-key shortcuts).
    - `Enter`: save.
- [ ] **Step 7: Run all web tests, typecheck and lint:** `npx playwright test && npx tsc --noEmit && npx eslint app lib tests`. Expected: all pass, no errors.
- [ ] **Step 8: Commit:** `git commit -m "feat: judge tab: keyboard-first judging of re-judged clips"`

### Task 8: Run it on pilot 2 (needs Jamison)

- [ ] **Step 1: Ask Jamison** to OK pushing migration 0010 to hosted `flopstats-v2`. Stop until yes.
- [ ] **Step 2:** `supabase db push --linked --dry-run`. Expected: only `0010_judgments.sql`. Then `supabase db push --remote --yes`.
- [ ] **Step 3:** From the main checkout: `uv run --project <worktree>/pipeline flopstats rejudge --from-run 2 --name pilot-2-v2 --config <worktree>/runs/pilot-v2.json`. Expected: about 167 judged, cost about $5–7. Run in the background, since it takes longer than 2 minutes.
- [ ] **Step 4:** Tell Jamison to restart `npm run review:local` and open `/review/judge`.
- [ ] **Step 5:** When Jamison is done, run `flopstats report --judged-run <id>` and bring the scorecard with prompt-tweak options (Jamison steers the wording).
