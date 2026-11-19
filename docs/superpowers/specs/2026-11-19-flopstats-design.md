# Flopstats — Design

*Date: 2026-11-19 · Owner: Jamison · Status: approved by Jamison, 2026-11-19*

## 1. Intent and why

Flopstats is a fun, cheeky website that tracks soccer players faking it: diving to win fouls or penalties, and faking or exaggerating injuries (rolling around, time-wasting). Every flop is detected from match video by AI and has its own clip. The site turns those flops into leaderboards (players, teams, nationalities, leagues), a Flop of the Day, weekly medals, season awards and shareable cards.

It's a side project for fun. If it drives a lot of traffic, monetization (ads, newsletter, sponsorship) comes later.

This is a **fresh build**. The 2025 repo (`jamisonpereira/flopstats_scrape`) and the old Supabase database are references for sources and lessons only. No code or data has to be kept.

## 2. Stages and success

The work runs in two stages. Stage 2 starts only if stage 1 passes.

**Stage 1: can the AI reliably spot flops?**
Build the football data layer, the detection pipeline and a private review screen. Run them on historical footballia matches. Jamison judges accuracy by reviewing what the AI flags. Nobody tags full matches by hand.

- **Scope:** a **5-match pilot** to measure real cost and quality per match, then **one full Premier League season (380 matches)**. Use the most recent complete season available on footballia.
- **Budget:** up to **$500 of AI usage for stage 1**. The pipeline tracks spend per match and per run, projects the season total after the pilot, and stops before going over a configurable limit.
- **Pass criteria (all three):**
  1. **Precision:** Jamison agrees with at least ~80% of AI-confirmed flops.
  2. **Known-dive recall:** the AI catches nearly all the "known" dives in the processed matches: yellow cards with reason "Simulation", and VAR "Penalty cancelled" events. These are a sanity check, not the stats.
  3. **Optional spot check:** Jamison watches the ~10-minute extended highlights of 2–3 matches and notes any flops the AI missed.

**Stage 2: do fans care?**
Build the public site on top of the stage 1 data. Launch without a newsletter, and add the newsletter soon after launch.

**Weekly ingest (stage 2):** a scheduled job picks up newly posted footballia matches each week and runs them through the pipeline, so "this week" means matches actually played that week. We don't yet know how quickly footballia posts matches. Measuring that lag is an early task, and it sets when the job runs. If the lag is too long, revisit the footage source.

Later, out of scope for now: real-time capture and posting, social auto-posting, player salaries ("cost per flop"), ads, other footage sources.

## 3. Goals, non-goals, anti-goals

**Goals**
- Find most of the flops in a match from video. Match data helps decide where to look but never rules a moment out.
- Keep a short clip for every confirmed flop.
- Record fun attributes per flop (§7.4) from the start, even before the site displays them.
- Keep the review load manageable and adjustable. Jamison shouldn't review "tons and tons" per game. At first he reviews every borderline item; the thresholds and an optional per-match cap are the knobs for reducing that later.
- Make it easy to re-run: better models or prompts later shouldn't mean re-downloading API data or rebuilding. **Full match videos are not kept long-term** (confirmed by Jamison). That's about 1–3 GB per match, terabytes across a season list. After processing, we keep the candidate windows (short segments) and clips, and delete the full video. A full re-run of the wide net re-downloads from footballia, which is acceptable because the URL is stored.
- Grow coverage step by step (league by league, season by season).

**Non-goals (for now)**
- Real-time detection and posting.
- Loading the whole football world up front (the old database had about 620,000 matches across 1,174 leagues; we don't need that).
- Exact, tracking-data-level precision. Approximate values are fine for a comedy site.
- Player salaries, ads and newsletter at launch. The design leaves room for each.

**Anti-goals (failure even if it technically works)**
- A review queue so long that Jamison stops using it.
- Data that silently links a **video to the wrong match**, or a match's events to the wrong records, because a mismatch was guessed rather than flagged. Uncertain player identifications are flagged for review too (§7.1 step 7).
- A pipeline that can't resume. Half-finished runs with no record of where they stopped killed the last attempt.
- A site that feels like a dry stats database rather than something funny and shareable.

Note: wrongly labelling a player as a flopper is **not** a concern. Jamison said it doesn't matter.

## 4. Constraints

- **Footage:** footballia.eu full matches, starting with the historical archive. It needs a login, and the old repo has a Selenium login and scraper to use as reference. The old repo also has an index of about 1,270 Premier League matches from 2015–2025 (`urls/game_urls_2015_2025.csv`) as a starting point. Switch sources only if needed.
- **Football data:** API-Football (the source of the old database). Data is downloaded only for matches we analyze.
- **Budget:** scrappy side project. Keep fixed monthly costs low, and prefer usage-based services.
- **Rights:** using footballia footage on a public, eventually monetized site is a known risk. For now it's accepted ("scrappy test"). It's to be revisited before public launch.
- **People:** Jamison is the only reviewer in stage 1, with limited time.

## 5. Approaches considered

| | Approach | Trade-off |
|---|---|---|
| **A (chosen)** | Supabase (Postgres, auth, storage) + Python pipeline + Next.js site on Vercel; clips move to Cloudflare R2 before public launch | Two languages and three services, but a fast, cheap, spike-proof site with easy share cards and A/B tests, and Jamison already knows Supabase |
| B | Everything in Python on one server (pipeline, web app, Postgres) | Cheapest and simplest, but a traffic spike hits the same box that's processing video, and share cards and A/B tests are harder |
| C | Fully managed Google Cloud (Cloud Run, Cloud Storage, Vertex) | Scales on its own, but more setup and less predictable costs than a scrappy test needs |

Dropped: a dedicated video platform and microservices (overkill).

**Storage decision:** stage 1 stores clips in Supabase Storage for simplicity. All clip URLs go through one small piece of our own code (a storage adapter plus a URL helper), so switching to Cloudflare R2 is a configuration change. Switch around public launch, or earlier if bandwidth costs grow. The reason is that R2 charges nothing for bandwidth, while Supabase charges per GB past the plan allowance.

## 6. Football data layer

### 6.1 Principles
- **Load only what we analyze**, then grow league by league and season by season. The order of expansion will be decided as we go.
- **Store raw, build clean:** every API-Football response is saved as-is (a raw table keyed by endpoint and parameters, with the fetch time). The clean tables are *built* from the raw copies by a script that can be re-run. Fixing a mapping bug means re-running the build, not re-downloading.
- **A load log:** every fetch and build step is recorded with its status (pending / done / failed / needs-review). Runs can resume.
- **Never guess silently:** anything that can't be linked confidently goes to a needs-review list.
- **Fresh API-Football account and rate limiting:** Jamison provides a new API key (stored in the local `.env`, see §12). One Premier League season is about 100–150 calls (season fixture list; fixtures batched about 20 IDs per call with events, lineups and player stats; squads; coaches; venues). **Use the paid Pro plan (about $19/month, 7,500 requests/day as of Nov 2026) for at least the first month** (Jamison's decision: no roadblocks for something this cheap). The downloader respects both per-minute and daily limits using the API's rate-limit headers, pauses at a limit, and resumes from the load log. Raw storage means no call is ever repeated.

### 6.2 Core tables (kept from the old design, rebuilt fresh)
`countries`, `leagues`, `seasons` (new, a league-season row with dates), `teams`, `team_seasons`, `players`, `player_team_seasons`, `coaches`, `venues`, `referees` (new), `matches`, `match_lineups` (with per-player fouls drawn and committed, cards, penalties and minutes), `match_events` (goals, cards with reasons, subs, VAR).

Changes from the old design:
- Add a **`seasons`** table. The old `leagues` table mixed league and season.
- Add **`external_refs`** (entity type, our ID, source, source ID, confidence, status). It maps API-Football IDs, footballia URLs and any later source to our IDs, so matching becomes its own job with a review queue.
- Drop `player_salaries` for now, but keep room for a `player_contracts`/salaries table and a salary source later.
- **Images** (player headshots, team logos, league logos, flags, coach photos, stadium photos) are downloaded once from the source and stored in **the same file storage as clips** (Supabase Storage now, R2 later), behind the same storage adapter, in their own folders (for example `images/players/<id>.jpg`). Each row keeps both the original source URL and our stored path. The site serves only our copies, never hotlinking the source. Placeholder or default images from the source are detected and flagged so the site can show its own fallback. Re-collection is a stage 2 task (the site needs them; the stage 1 review screen doesn't).
- **Match and stadium context is kept in full**, because it powers fun stats:
  - **Venues:** name, city, country, capacity, surface, photo.
  - **Matches:** date and kickoff time, venue, referee, coaches, result, competition stage, home/away, and attendance where the source has it.
  - Every flop links to its match, and through it to the venue, referee, competition, and home/away side.
  - That enables, for example: stadiums with the most flops, home vs. away flopping, and "most-conned referees" (referees who gave the most fouls or penalties for flops).
  - A referees table (name, nationality) is added so referee stats don't depend on matching free-text names.

### 6.3 Known problems to design against (from the old data)
- 22% of events had no player linked. Player linking needs real matching (API player ID first, then name plus shirt number plus team plus season, with fuzzy fallback and a confidence score) and a review path.
- Only 41% of matches had events and 19% had lineups, from unfinished runs. The load log and resume address this.
- 689 likely duplicate players (same name and birthday). Add a dedupe step and use API IDs as the unique key.
- 46,000 players had no nationality. Nationality is needed for the "which nations flop most" stats, so backfill it from player detail endpoints and flag what's still missing.

## 7. Detection pipeline

### 7.1 Flow per match
1. **Acquire:** download the footballia full match and register it in `videos` (source, match, duration). Link it to the API-Football match through `external_refs`. An uncertain match goes to needs-review.
2. **Time sync:** work out the kickoff and second-half start offsets in the video (from the on-screen clock, read by a model at a few sample points). Then any video timestamp converts to a game minute and back. This is needed to line up match events and to show game minutes.
3. **Wide net (first pass):** split the match into short overlapping windows (starting point: about 20 seconds long, every 10 seconds). Score each window "possible flop" with a cheap video-capable decision model (starting choice: Google `gemini-decision-1`, which takes video and returns calibrated probabilities). Match data (fouls drawn, cards, penalties, stoppages, injury subs) raises nearby windows' scores but never removes a window. Windows above the **candidate threshold** become candidates. Overlapping candidates are merged.
4. **Trim (verification):** for each candidate, a stronger video model watches the window plus a few seconds either side and answers structured questions (§7.4). It decides flop or not, the type, the players involved, and an overall confidence. It also identifies replays and slow-motion repeats so the same incident isn't counted twice.
5. **Decide:**
   - **Auto-confirm** if confidence ≥ the confirm threshold.
   - **Reject** if confidence < the review threshold.
   - **Review** if in between. **Every borderline item goes to Jamison's review at first, with no cap.** A per-match review cap exists as a setting, off by default. If a cap is turned on later, items past it are kept as "AI-judged": they count in stats, weighted by confidence, are marked unreviewed, and can be changed by later review or fan disputes.
6. **Clip:** cut a clip for each confirmed or under-review flop (the incident plus a short lead-in and the "recovery"), encode it for the web (H.264, reasonable size), and store it via the storage adapter.
7. **Link and enrich:** attach players through lineups (shirt number + team + name read from the video, plus commentary audio if useful). Each attribution gets a confidence score. **Any flop whose player identification is below a confidence threshold goes to Jamison's review queue as a "who is this?" item**, with the AI's top guesses from the lineup to pick from. Until it's resolved, the flop counts for team and league stats but not player leaderboards. Later, fans can help resolve these. Then attach the ref's decision and the consequence (for example, penalty awarded → scored, from match events), and compute the SIM score (§9).

### 7.2 Things that can be tuned
Window length and step, candidate threshold, confirm threshold, review threshold, review cap per match, context padding, which models run each stage, and prompt/question versions. All are stored per **detection run** so runs can be compared.

### 7.3 Models
- First pass: `gemini-decision-1` (as of Nov 2026, it takes text, images, audio and video, returns probabilities, and charges only for input).
- Verifier: **not chosen yet, on purpose.** During the 5-match pilot, run 2–3 candidates (a current Gemini Pro model plus one or two other strong video models available at the time) over the same candidate moments. Jamison reviews the results, and we pick the one with the best agreement for the cost. Public video benchmarks don't test "was that a dive?", so our own pilot decides.
- Jev (TypeSafe) is text-only per its public docs. It's optional for text-only decisions (for example routing or tie-breaks using match events), not for watching video.
- Model and prompt choices sit behind an interface so they can be swapped per run.

### 7.4 What we record about each flop
Required: type (dive / exaggeration / feigned injury / time-wasting), start and end video times, game minute, flopper (player + team), confidence.

Optional (recorded from day one, displayed later):
- Time on the ground (seconds)
- Number of rolls (rough)
- Fake-pain score 1–10
- Body part clutched vs. where contact happened
- Contact level (none / light / real)
- Miracle recovery (yes/no, and what triggered it: call, free kick, card)
- Ref's decision (none / foul / yellow / red / penalty) and the team penalized
- Consequence (for example, a goal from the resulting penalty or free kick within N seconds)
- Rough pitch location (x, y on a 0–100 scale, attacking direction normalized) with its confidence
- Other players involved (for example the alleged fouler), each with a role

Optional fields are stored so they can be added or dropped without a schema redesign.

## 8. Review and fan input

### 8.1 Stage 1 private review screen (Jamison only)
A simple web page listing items to review, by match:
- Each item shows the clip, the AI's verdict, type, players and key attributes.
- One-tap actions: ✓ confirm · ✗ not a flop · change type · fix player.
- Two kinds of item: **"is this a flop?"** (borderline verdicts) and **"who is this?"** (uncertain player identification, with the AI's top lineup guesses). One flop can need both.
- Also shows a sample of auto-confirmed flops for spot checks.

Every decision is stored with a reason. These decisions measure accuracy (the share of AI-confirmed flops Jamison agrees with, per detection run) and become examples for improving prompts.

### 8.2 Fan input (stage 2+)
- **Rate the acting:** a fan fake-pain score, blended with the AI's.
- **Head-to-head "Who's the bigger flopper?"** votes, which feed a popularity ranking.
- **Flag a missed flop:** the fan gives a match and minute. That window goes straight to the verifier (step 4). A confident flop is added automatically, and a borderline one goes to the review screen.
- **Dispute a flop:** same path, the other way round. Enough disputes lower that flop's weight in SIM or send it to review.
- Voting needs light sign-in (Supabase auth) plus basic rate limiting.

## 9. SIM Rating (Simulation Index)

A mock-official, xG-style headline metric. The ingredients are published on a playful methodology page, and the exact weights stay "proprietary" so they can be tuned quietly.

**Per-flop score**
`base × acting × time_on_ground × contact × payoff × bonuses × confidence`
- **Acting:** fake-pain score (1–10). The largest factor. AI score at first, later blended with fans'.
- **Time on the ground:** grows with diminishing returns (log-like), so a 2-minute roll doesn't dwarf everything.
- **Contact:** none ×1.5, light ×1.0, real ×0.5.
- **Payoff:** nothing ×1.0, foul ×1.2, opponent booked ×1.5, penalty won ×2.0, penalty scored ×2.5.
- **Bonuses:** small extras for rolls and a miracle recovery.
- **Confidence:** the AI's confidence, adjusted by fan agreement or disputes.

**Entity SIM:** the sum of a player's flop scores per 90 minutes played (from lineups), scaled so the top is about 100 within the chosen scope (league/season). Teams, nations and leagues roll up the same way. Raw totals are also shown.

All weights are settings, so they can change without changing code.

## 10. Fan site (stage 2)

**Pages**
- **Home:**
  - Flop of the Day hero (clip, stat chips, rate-the-acting slider, share card).
  - This week's top floppers by SIM.
  - The season awards race.
  - A **separate** "Who's the bigger flopper?" section (not visually tied to the leaderboard).
  - Reserved ad spots (empty at launch).
- **Leaderboards:** players, teams, nations, and leagues. Sorted by SIM by default, switchable to count, per 90, time on the ground, acting or penalties won. Filter by league and season.
- **League roundup:** for each league, its overall SIM, team table, top floppers and best flops of the week.
- **Drill-down pages:** player, team, nation, match, **stadium and referee** pages. A short "Flop Report" on top (FBref scouting-report style), full detail and the flop log below, and a pitch heat map wherever we have location data.
- **Compare:** two players, teams or nations side by side: SIM and key stats, heat maps, and the **flopping history between them** (every flop when those two met).
- **Awards:** weekly medals and a season-end ceremony with fan voting.
- **Event pages:** a reusable template for special events (World Cup, Champions League, end of season) with their own leaderboards, awards and look.
- **Vault:** browse the historical archive.
- **Methodology page** for the SIM Rating.

**Flop of the Day rule:** exactly one per day, the same for everyone. On days with new matches it's the day's best new flop by SIM, with optional editorial override. On days without, it's a "From the vault" pick ("On this day…" where possible). A badge shows fresh vs. vault.

**Sharing:** every flop, player report and award has a vertical share card (made automatically on the server).

**Monetization hooks:** ad spots reserved in the layout, but no ad code yet. Newsletter ("The Weekly Flop Report") added soon after launch. Room for sponsorship.

**Layout inspiration (research, 19 Nov 2026):**
- Wordle: one daily thing, made for sharing.
- Spotify Wrapped: designed for social first, with race and quiz mechanics.
- FBref and Sofascore: a summary first, then drill down.
- Letterboxd: satisfying rating interactions.
- Planet Football's "Fallon d'Floor": the tone and voice.
- FotMob: a warning against aggressive ads.

## 11. Stack

- **Database and auth:** Supabase (Postgres). Migrations are kept in the repo.
- **Pipeline:** Python. It runs on Jamison's laptop at first, then on a single cheap cloud server. A job queue in Postgres makes runs resumable. ffmpeg for cutting and encoding.
- **Site:** Next.js on Vercel. Pages are pre-built and refreshed after each batch, plus live parts for votes. Share-card images are made on the server.
- **Clips:** Supabase Storage now, Cloudflare R2 by public launch, behind a storage adapter.
- **Repo:** a new repository (the old one stays as reference).

## 12. Accounts and secrets (setup steps for Jamison)

The implementation plan must include explicit, early setup steps where Jamison creates accounts and hands over keys, and the build must not start a step that needs a key before that key exists.

**Accounts to create or confirm (stage 1):**
- API-Football Pro plan (at least one month).
- A new Supabase project.
- Google AI Studio / Gemini API key (first pass and a Gemini verifier candidate).
- API keys for any other verifier candidates chosen for the pilot.
- footballia login (existing or new).
- A new GitHub repo.

**Stage 2:** Vercel, and Cloudflare (R2).

**Secrets handling (revised 2026-11-19 by Jamison):**
- Each machine (MacBook, Mac mini) keeps keys in a local **`.env` file in the repo root**, git-ignored, `chmod 600`. A master copy lives in 1Password (a Secure Note, "Flopstats keys").
- The repo commits only `.env.example` (variable names, no values).
- Coding agents must never read, print or copy `.env`. That's enforced with `.claude/settings.json` deny rules, `.cursorignore`, and instructions in `CLAUDE.md` / `AGENTS.md`. The code loads `.env` at runtime.
- Nothing secret is ever committed or pasted into chat.
- `flopstats verify-setup` checks each key works (one cheap call per service) without printing values.

## 13. Left to the builder

- Exact table and column names, indexes and migration tooling.
- Job queue implementation and server choice.
- Prompt wording and question design for both model stages (within §7.4).
- Starting values for windows and thresholds (§7.1 gives starting points).
- Clip encoding settings and storage paths.
- Matching algorithms and confidence cut-offs for player and match linking.
- Front-end component library and visual style. Keep it playful. The 19 Nov wireframes (shown in the brainstorming chat) are summarized in §10: a home page led by the Flop of the Day hero with stat chips and a share card, a weekly top-floppers list, the awards race as bars, and a separate head-to-head section. The leaderboard is a filterable table, and the player page has the Flop Report stat tiles beside a pitch heat map, with the flop log below.
