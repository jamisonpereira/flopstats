# Divestats — Stage 2 site design

*Date: 2026-11-20 · Owner: Jamison · Status: draft for review*
*Feeds: the Stage 2 plan (public site). Builds on `docs/superpowers/specs/2026-11-19-flopstats-design.md` (the "spec").*

Mock-ups live in `docs/design/mockups/` (open the `.html` files in a browser). All names, clubs and numbers in them are invented.

| File | What it shows |
|---|---|
| `brand-directions.html` | The three brand directions considered (A chosen) |
| `home-v1.html` | First home pass (pre-rename, kept for history) |
| `home-v2.html` | **Current home, mobile** |
| `key-screens-v1.html` | **Rankings, player page, three 9:16 share cards** |
| `compare-desktop-v1.html` | **Compare (picking + the hearing) and desktop home** |

---

## 1. Intent and why

The public site exists to find out whether fans care (spec §2, stage 2). Jamison's answer to "who shares it, and where": **group chats, X and football TikTok.** It is built for virality. The raw stats matter because they make the jokes land and make arguments winnable.

The three share moments, in Jamison's words:
1. **Comparisons as ammunition**: two players, clubs or nations, "see, you lot dive way more than us".
2. **A single player**, when people are slating or praising someone.
3. **A great case of the day.**

Take it step by step: image cards first, TikTok video later.

## 2. Goals, non-goals, anti-goals

**Goals**
- Every page can produce a shareable receipt. Compare is a front-door feature, not a sub-page.
- Stats look credible enough to argue with; the comedy comes from deadpan precision, not exclamation marks.
- A daily ritual (Today's Case) that people come back to and post.
- Honest partial coverage: a match without footage is "No footage", never zero.
- Every footage-dependent element has a version that works with no video.
- Mobile first; desktop is a widened layout of the same modules.
- One token-driven theme, so other looks can be added later as skins.

**Non-goals (now)**
- Real-time features, social auto-posting, TikTok video export (later).
- Player classifications/archetypes and nicknamed awards (Jamison: "a bit over the top… layer this in later").
- Ranking hearings by social-media engagement (later).
- Ad code (slots only) and the newsletter at launch (soon after).

**Anti-goals**
- A dry stats database (spec §3).
- Over-the-top mockery: no "VERDICT" stamps on comparisons, no cartoon nicknames at launch (Jamison toned these down).
- Ads that interrupt the daily ritual or a share flow (FotMob/Sofascore warning).
- A missing match that reads as zero dives.

## 3. Constraints

- **Coverage:** footballia has at most 177 of a Premier League season's 380 matches (2023-24 best). Every count, per-90 and ranking must say what was studied.
- **Footage rights are unresolved** (spec §4). See §11 for what depends on video and the fallbacks.
- **Data is mock until Stage 1 passes.** Shapes follow spec §7.4 (per-case fields) and §9 (SIM). Real tables may change.
- **Stack (spec §11):** Next.js on Vercel, Supabase, clips to Cloudflare R2, share cards rendered on the server.
- **Launch is one league, one season.** Multi-league UI must hide itself gracefully until a second league exists.

## 4. Decisions made with Jamison (2026-11-20)

| Topic | Decision |
|---|---|
| Audience | Group chats, X, football TikTok; built for virality |
| Comic frame | A deadpan **research institute**; **awards-show glitz** only for awards and events |
| Brand name | **Divestats** (Jamison owns divestats.com and flopstats.com; flopstats.com redirects) |
| Vocabulary | **"Simulation"** is the formal word, **"case"** the unit. "Dive" stays one of the four case types. "Flop" is retired from copy. |
| Daily feature | **Today's Case** (was "Flop of the Day") |
| Look | Direction **A, "Lab Report"** (graph paper, monospace, hazard orange, stamps). Other looks may come later as skins or A/B tests. |
| Rate the acting | **Required before the scores are revealed** |
| Fan vote on two incidents | **Double-Blind Trial**: hover (desktop) or scroll-to-centre (mobile) plays each; vote once both have played |
| Player-vs-player vote | Moves off the home page to Compare ("Fan vote", labelled not part of SIM) |
| Leagues on home | **Global by default**; league is a remembered lens (chips), never a split layout |
| Compare entry | **From anywhere**: every Compare button pre-fills one side; the Compare tab is the only blank start, and it has suggestions |
| Suggested comparisons | Yes ("Scheduled hearings"): this week's fixtures, derbies/rivalries, big names; engagement ranking later |
| Share card format | **9:16 first** |
| Tone checks | Classifications, "Golden Swan" and "VERDICT" stamps removed for now |
| Launch data | **One past season** (best footballia coverage, currently PL 2023-24), shown as a **calendar replay** (§4a) |
| Launch cut | See §4a: launch / next / later |
| Success measures | **Unique visitors**, **shares per visitor**, **7-day return rate**. A posting plan to drive initial engagement is a follow-up (§18a) |

## 4a. Launch scope (past-season launch)

The site launches on one completed season, not the live one. Weekly ingest of the live season comes after launch.

**Calendar replay (my proposal, agreed with Jamison).** Each day the site shows what happened on the same calendar date in the launch season:
- **Today's Case → "On this day in 2023-24"**: picked from the matches played on today's date that season. Gap days (international breaks, summer, midweeks without matches) use a vault pick from the same season. Numbering, rate-to-reveal and streaks are unchanged. No FRESH tag at launch; the tag reads `ON THIS DAY · 2023-24` or `FROM THE VAULT`.
- **"This week in the lab" → "This week in 2023-24"**: the matchweek played in this calendar week that season, with studied and no-footage matches.
- **"Top offenders this week"** uses that replayed matchweek; Rankings show the full season.
- **The season is labelled everywhere** ("2023-24 season" in the ticker, page titles, cards), and players show the club they played for that season, so it can't be mistaken for current form.

**Off until live ingest:** FRESH tags, ▲/▼ rank movement, weekly medals, fixture-based hearings. At launch, Scheduled hearings use rivalries and big names only. Later option: pair *real* upcoming fixtures with the launch season's record ("they meet Saturday; here's 2023-24").

| Stage | Surfaces |
|---|---|
| **Launch** | Home (replay version) · Today's Case + case pages · Rankings · Player · Team · Nation · Match · Compare · the three 9:16 share cards + link previews · Methodology |
| **Next** (engagement moments) | **The 2023-24 Awards** (ceremony with fan voting, a few weeks after launch) · Double-Blind Trial · weekly live ingest, which switches on FRESH, weekly modules, ▲/▼ and medals |
| **Later** | Referee · Stadium · League roundup (needed once a second league exists) · Event pages · a separate Vault browser (at launch the whole site is the vault) · skins and other §16 layers |

**Measuring "do fans care":** unique visitors, shares per visitor, 7-day return rate. Every card and shared link carries its type (e.g. `?s=rap`, `?s=beef`, `?s=case`) so returns can be attributed per card. Use privacy-friendly, cookie-free analytics plus a small event log (ratings submitted, shares by type, hearings opened). *(My call: no cookie banner if avoidable; A/B-test plumbing is not in the first build.)*

## 5. Approaches considered

**Brand direction** (`brand-directions.html`)
| | Direction | Trade-off |
|---|---|---|
| **A (chosen)** | Lab Report: paper, monospace, hazard orange, stamps, case files | Most credible; the case-file idea works without video. Less loud in a feed. |
| B | Tabloid Inquiry: black, acid yellow, condensed caps, halftone | Funniest at a glance, but the institute disappears. Kept as a possible skin. |
| C | The Institute: pitch green, gold, serif journal | Prestige joke; gold suits awards. Kept as the awards/events skin candidate. |

**Compare entry:** A, pre-filled from any page (chosen) vs B, a blank builder (more typing before the payoff). The Compare tab still needs a landing, so it has two slots with one suggested side.

**Leagues on home:** global with a remembered lens (chosen) vs a per-league home (splits an audience that's small at launch, and Today's Case must be one for everyone anyway).

**Two-incident vote naming:** "Flop-off" was rejected (not research-sounding, uses "flop"). "Double-Blind Trial" chosen.

## 6. Brand

### 6.1 Name and lockup
- **Divestats**, published by **the Divestats Institute for Simulation Research** (short: "the Institute"). *(My call; Jamison picked Divestats, the publisher name is a proposal. Alternatives were "Institute of Divology" and "The Simulation Bureau".)*
- **Wordmark:** `DIVE` in a solid hazard block (white text) butted against `STATS` in an ink-outlined box, IBM Plex Mono SemiBold. The split stops it reading as "divest-ats". Small caption under it on wide layouts: `INSTITUTE FOR SIMULATION RESEARCH`.
- **Favicon/app icon:** the `D` from the hazard block. **Seal** (for methodology, awards, certificates): a circular "DISR · EST. 2026" mark (to be drawn).
- **Tagline:** "Contact was minimal."
- **Domains:** divestats.com (primary), flopstats.com → 301 to divestats.com. Free at time of check and worth buying: simrating.com (→ methodology), theflopreport.com is now off-brand; a "dive report" domain should be checked before the newsletter launches.

### 6.2 Vocabulary (glossary)
| Use | Not | Notes |
|---|---|---|
| case | flop, incident (in UI) | Countable unit. "23 cases", "Case DS-2324-0187" |
| simulation | flopping, diving (as umbrella) | Formal register: "an incident of simulation" |
| dive / exaggeration / feigned injury / time-wasting | — | The four case types (spec §7.4), always these labels |
| SIM Rating | Sim score, SIM score | The metric (spec §9) |
| Today's Case | Flop of the Day | Numbered: "Today's Case #312" |
| peer review | rate, vote | Fan acting score |
| hearing | comparison, versus | A compare page; "Scheduled hearings" = suggested comparisons |
| Double-Blind Trial | flop-off | Two-incident vote. Results build "The Canon" (all-time ranking) |
| studied | covered, processed | "177 / 380 matches studied" |
| No footage | 0, n/a, missing | Unstudied match |
| awaiting identification | unknown player | Spec §7.1 step 7 "who is this?" cases |
| Top offenders | Top floppers | Leaderboard modules |
| grounded | on the floor | "41s grounded" |
| miracle recovery | — | Spec §7.4 field |

**Case numbers:** `DS-<season yymm>-<4-digit seq>`, e.g. `DS-2324-0187`. Players get `DS-P-<id>`. *(Proposal: needs a stable per-season sequence in the data.)*

### 6.3 Voice
- **Deadpan institute.** Clipped, certain, a little bureaucratic. The joke is the precision.
  - ✓ "Finding: Subject remained grounded 41s after contact rated none. Miracle recovery at award of penalty."
  - ✓ "Northbridge players go down 73% more per 90."
  - ✗ "LOL what a dive 😂", "VERDICT: GUILTY", nicknames.
- **Facts first, joke second.** Every funny line must be literally true from the data (e.g. the auto line "Clutched his face 61% of the time. Was hit there 0% of the time.").
- **Human-written templates, data-filled.** No AI-written jokes on the site (research: Spotify 2024 backlash).
- **Honesty lines are part of the voice:** "'No footage' means the match hasn't been studied, not that nobody dived."
- **Awards/events** may go warmer and glitzier (gold, spotlight), still without nicknames until layered in.

## 7. Design tokens

All visual values are tokens (CSS custom properties). A skin = a token set. Values below are from the mock-ups.

### 7.1 Colour (Lab Report, light)
| Token | Value | Use |
|---|---|---|
| `--paper` | `#f4f1ea` | Page background |
| `--grid` | `#e3ded2` | Graph-paper lines (16px), dividers, empty bar tracks |
| `--ink` | `#121212` | Text, borders, dark blocks |
| `--muted` | `#5d5a54` | Secondary text (6.1:1 on paper) |
| `--card` | `#ffffff` | Panels, tables |
| `--hazard` | `#ff4f1f` | Brand accent: wordmark block, stamps, #1 bars, knobs, large numbers |
| `--hazard-strong` | `#c8360a` | **Text and buttons that need AA**: small orange text, white-text buttons (5.3:1 vs white) |
| `--hazard-soft` | `#ffe1d6` | Selected rows, fan-vote panels |
| `--pitch` | `#2f6b3a` | Pitch diagrams, media placeholders |
| `--pitch-line` | `#e9f2e4` | Pitch markings |
| `--rolls` | `#ffd36b` | Roll squiggles / secondary marks on pitch |
| `--side-b` | `#2a5bd7` | Second side in compare (orange vs blue) |
| `--nofoot` | `#b9b4a8` | No-footage hatching and borders (decorative only) |
| `--nofoot-text` | ≥4.5:1 grey, e.g. `#6f6a60` | "No footage" label text |
| `--gold` | `#d8b45a` | Awards only (on ink: 9.5:1) |
| `--up` | `#1f7a3a` | Rank rising ▲ |

**Contrast rule:** raw `--hazard` (#ff4f1f) is 2.9:1 on paper and 3.3:1 with white text, so it fails WCAG AA for small text. Use it for fills, marks and large/bold numbers (≥24px), and use `--hazard-strong` for small text and white-text buttons. *(The mock-ups use raw hazard on buttons; fix in build.)* Ink on hazard is 5.7:1 and is fine.

**Hatching:** "No footage" = 135° stripes `--card`/`#f3f1ec`, 6px. Used for rows, cells and coverage bars. It is the single visual sign for "not studied" everywhere.

**Dark surfaces:** the awards block and the Rap Sheet card use `--ink` backgrounds with paper text and gold/hazard accents. A full dark mode is not designed yet (left to builder; graph paper becomes `#1b1b1d` lines on `#121212`).

### 7.2 Type
- **IBM Plex Mono** (400, 600): wordmark, labels, numbers, case numbers, table figures, buttons in data contexts.
- **IBM Plex Sans** (400, 600, 700): names, headlines, body, findings.
- Both free (Google Fonts / self-host via `next/font`).

| Role | Font | Size / weight (mobile) |
|---|---|---|
| Page title | Sans 700 | 26px, line-height 1 |
| Hero name | Sans 700 | 22–23px |
| Section label | Mono 600, uppercase, +0.1em | 11px, with an ink "01" index chip |
| Body / finding | Sans 400 | 13–13.5px, line-height 1.4 |
| Meta / captions | Mono 400 | 9.5–10.5px |
| Stat value | Mono 600 | 17–19px tiles, 28–36px hero SIM |
| Table figure | Mono 600 | 12.5–13px, tabular |

Desktop scales hero sizes ~1.3× (hero name 30px). Minimum text size in production: 10px (some mocks go to 8.5px on cards; cards are rendered at 1080px wide so that is ~34px real).

### 7.3 Space, shape, depth
- Base unit 4px; page gutter **14px** mobile, 28px desktop; module gap 18px (section head padding `18px 14px 8px`).
- **Corners are square.** Only device frames are rounded. Avatars are square "mugshots".
- **Borders:** 2px ink for panels and controls, 1px `--grid` for row dividers, 1.5px for chips/pills, dashed 2px for "do something here" (rating box, empty compare slot).
- **Depth:** no soft shadows on site UI. Hard offset shadow `3–4px 3px 0 var(--ink)` for raised/active things (hovered trial card, popover sheets). Sticky bars may use one soft shadow.
- **Background:** graph paper (`--grid` 1px lines every 16px) on `--paper`; 12px on share cards.

### 7.4 Motion
| Pattern | Spec |
|---|---|
| Stamp in ("THEATRICAL") | 180ms scale 1.3→1 + rotate -14°→-9°, ease-out, after the reveal |
| Score reveal | Blurred SIM tile un-blurs over 250ms; crowd/AI bars grow 400ms ease-out, staggered 80ms |
| Diagram replay | Run line draws ~1.6s linear, contact dot pops, roll squiggle wobbles 4× (see `home-v2.html`) |
| Hover lift | translateY(-2px) + hard shadow, 120ms |
| Rank change | ▲/▼ chip fades in 200ms; no reordering animation on load |
| Ticker | Static at launch (no marquee). Optional slow scroll later. |
- **`prefers-reduced-motion`:** no draw/wobble; diagrams show their final frame; stamps appear without rotation.
- Durations are tokens (`--dur-fast 120ms`, `--dur 250ms`, `--dur-slow 400ms`).

### 7.5 Skins (later)
Tokens are grouped so a whole look swaps by `data-skin` on `<html>`: `lab` (default), `tabloid` (B), `journal` (C, likely the awards/events skin). Uses: A/B tests, a user "Edition" picker, event takeovers. Only `lab` is designed now.

## 8. Components

| Component | Description | Seen in |
|---|---|---|
| App bar | Wordmark left; scope switch ("All leagues ▾"/season) + menu right; 2px ink bottom border | all |
| Coverage ticker | Ink strip: "PL 23/24: 177 / 380 MATCHES STUDIED · 1,204 CASES ON FILE · 203 MATCHES: NO FOOTAGE" | home |
| Bottom tab bar (mobile) | Today · Rankings · Compare · Awards · More. Active = hazard | all mobile |
| Top nav (desktop) | Today · Rankings · Leagues · Compare · Awards · Vault · Methodology + scope + search | desktop |
| Section head | Index chip ("01") + mono uppercase label + right-aligned text link | all |
| Case media | Bordered 16:10ish frame; **Clip / Diagram / Stills** mode switch top-left; optional stamp bottom-right | home, case |
| Stamp | Rotated bordered mono label in hazard ("THEATRICAL"). Used for case type/acting band, never for comparisons | case |
| Finding block | White panel, 4px hazard left border, "FINDING" kicker, one data-true sentence | case, player |
| Stat grid | 4 (or 3×2) bordered cells: mono value + tiny uppercase label; SIM cell inverted (ink) | case, player |
| Rate-to-reveal | Dashed box: 1–10 notched slider ("1 · Wooden" → "10 · Oscar"), Submit button, locked SIM tile | home, case |
| Leaderboard row | Rank · name + meta (club · league badge) · bar · value; #1 bar in hazard | home, rankings |
| League badge | 1.5px bordered mono code (ENG, ESP) | lists |
| Scope chips | Horizontal chips: All leagues / leagues / My clubs; remembered | home, rankings |
| Podium | Top 3 cards, #1 inverted and taller | rankings |
| Compare tick | Row checkbox; sticky "2 selected → Compare" bar | rankings |
| Hearing card | Fixture/kicker line, two sides with crest + SIM, history line, "Open the hearing →" | home, compare |
| Tug-of-war row | Value A · label + split bar (hazard vs `--side-b`) · value B | compare, beef card |
| Docket row | Match line + pill: "6 cases" / "0 cases ✓" / hatched "No footage" | home, match lists |
| Season file strip | One cell per fixture: case count shaded by heat; hatched = no footage; dashed = didn't play | player, team |
| Percentile bars | Label · bar · percentile, vs same position, 900+ studied minutes | player |
| Case map | Pitch with case dots (attacking →), colour by type or side | player, compare, team |
| Clutched-vs-hit figure | Body outline: where clutched (hazard) vs where contact happened (ink), % labels | player |
| Case log row | Thumbnail/diagram · type tag + "v Opponent, 63'" + one-line facts · SIM | player, team, match |
| Trial card | Media that plays on hover/centre, facts, "Watch to vote" → "This one" | home |
| Fan vote panel | Hazard-soft panel, two buttons, "Vote to see the split", labelled not SIM | compare |
| Awards block | Ink panel, gold radial glow, gold race bars | home, awards |
| Reserved slot | Dashed `--nofoot` box "Reserved · sponsor space"; renders nothing in production until filled | home, rails |
| Newsletter teaser | Panel + email field + "Notify me" | home footer |
| Awaiting-ID note | Dashed box explaining club vs player totals | rankings |

## 9. Pages

General rules for every page:
- **Summary first, detail below** (FBref/Sofascore): a Case Report header, then tiles/percentiles, maps, the season file, the case log.
- **Every entity page has Share and Compare** buttons, with Compare pre-filled and three suggested opponents.
- **Coverage is stated** on any page with counts ("21 of 34 studied").
- Scope (league/season) comes from the remembered lens unless the URL says otherwise.

### 9.1 Home (`home-v2.html`, `compare-desktop-v1.html` desktop)
Order (mobile): app bar → coverage ticker → **Today's Case** → 01 Scheduled hearings (rail) → 02 Top offenders this week (scope chips; players/clubs/nations) → 03 Double-Blind Trial → 04 Which league dives most? → 05 This week in the lab (docket + matchweek coverage bar) → 06 Awards race → reserved slot → newsletter teaser → footer with methodology link and the no-footage line.
- At launch (one league), 04 becomes **"Which club dives most?"** and the league chips are hidden.
- At launch (one past season), the "this week" modules follow the calendar replay (§4a), 03 Double-Blind Trial is not shown yet, and 06 shows the season's final standings as a teaser for the 2023-24 Awards.
- Desktop: Today's Case spans the main column (media left, info right); hearings as 3 columns; trial beside the docket; a 330px right rail holds Top offenders, the **300×250 reserved slot**, awards race, league table. Ads never sit inside the reading flow or the daily ritual.

### 9.2 Today's Case
- One per day, same for everyone (spec §10 rule). At launch the tag is `ON THIS DAY · 2023-24` or `FROM THE VAULT` (§4a); **FRESH** arrives with live ingest.
- **Selection (my call):** automatic. The highest-SIM confirmed case from that date's matches in the replay season; otherwise a vault case above a minimum SIM that hasn't been used. An editorial override is a single "pin as Today's Case" action next to the existing private `/review` screen, optional at launch. The day rolls over at **00:00 Europe/London**; once published, a day's case and number never change.
- Numbered (#312), countdown to the next case, review streak.
- **Rate-to-reveal:** SIM tile is blurred and locked; the user sets the slider and submits; then SIM, the Institute's acting score and the crowd average animate in, the stamp lands, and Share unlocks the Today's Case card.
- Logged-out users can rate (stored locally, counted after light sign-in or by rate-limited anonymous token: left to builder within spec §8.2 "light sign-in").
- Each case also has a permanent page (`/case/DS-2324-0187`) with the same block plus the full §7.4 detail and "more from this match".

### 9.3 Rankings (`key-screens-v1.html`)
- Tabs: Players · Clubs · Nations · Leagues (Referees and Stadiums under More or their own tabs, builder's call).
- Filters: league, season, **sort** (SIM default; cases, per 90, time grounded, acting, pens won), minimum studied minutes (default 900 for players), position.
- Coverage bar under the filters. Podium for top 3, then table with rank movement since last update.
- Tick two rows → sticky Compare bar.
- "+N cases awaiting identification" note (they count for clubs/leagues, not players).
- "Share table ↗" makes a top-10 card.

### 9.4 Player page (`key-screens-v1.html`)
Hero (mugshot with height-chart backdrop, file number, position · club · nation) → big SIM panel with ranks (league, all leagues, nation) and change vs last season → Case Report tiles (cases, per 90, avg grounded, avg acting, pens won, miracle recoveries) → percentiles vs same position → case map + clutched-vs-hit figure → **season file strip** → case log → Share rap sheet / Compare ▾ with suggestions (closest rival, teammate, next opponent's top offender).

### 9.5 Team, nation, league, referee, stadium, match pages (not mocked; same building blocks)

**Team:** like the player page with a squad table instead of percentiles.
```
[crest] Northbridge · PL       SIM 71.4  #3 of 20
Case Report tiles (cases, per 90, home vs away, pens won, time-wasting share)
Squad: player rows (SIM, cases) · season file strip (per fixture)
Case map · "Most dived against" opponents · case log
[Share rap sheet] [Compare ▾ next opponent / rival]
```
**Nation:** players of that nationality across studied leagues; "Which nation dives most?" rank; club breakdown.
**League roundup** (spec §10): league SIM, team table (SIM, cases, studied matches), top offenders, best cases of the week, coverage for the season.
**Referee:** "Susceptibility" page: cases in their matches, fouls/pens/cards given for cases (spec §6.2 "most-conned referees"), conned rate vs average, case log.
**Stadium:** cases at the ground, home vs away split, "local legend" (player with most cases there), capacity/photo.
**Match:**
```
Northbridge 1–1 Calder Utd · 12 Nov · ref A. Clarke · Kingsway Park
[Theatre momentum strip: cases per minute, home ↑ / away ↓, cards & VAR markers]
Case Report tiles (cases, grounded total, pens from cases)
Case log by minute (each opens the case page)
If not studied: hatched pitch, "No footage: this match hasn't been studied", score + events only
```

### 9.6 Compare (`compare-desktop-v1.html`)
- **Picking** (Compare tab): Players/Clubs/Nations switch; side A pre-filled from context (or empty), side B empty slot + search; "Suggested for X"; "Hearings everyone's opening".
- **The hearing:** two mugshots/crests with SIM (A hazard, B blue) and a "VS" chip; **one plain summary line** ("Vellani has the higher SIM per 90, by 13%"); tug-of-war rows (cases, per 90, avg grounded, avg acting, pens won); studied minutes line; both case maps; **When they met** (every meeting; dots per side; no-footage meetings hatched); **Fan vote** "Who's the bigger diver?" (not part of SIM); Share beef card, Swap side.
- Same layout for clubs and nations (crests/flags instead of mugshots).
- URL is shareable and canonical regardless of side order (e.g. `/h/nbr-cal`).

### 9.7 Scheduled hearings (suggested comparisons)
At launch only rules (2)–(4) apply (§4a). Pairing rules, in priority order: (1) fixtures in the next 7 days (after live ingest, or real upcoming fixtures paired with the launch season's record), teams and each side's top offender; (2) derbies/rivalries (a curated list); (3) big names (top SIM across leagues, cross-league pairs); (4) personal: "My clubs" vs their next opponent. Later: rank by social engagement. Each card shows both SIMs and one history line.

### 9.8 Awards (not mocked)
- **Weekly medals** (gold/silver/bronze for the week's top cases and offenders), shown on case and player pages.
- **Season ceremony:** gold "journal" skin (direction C), shortlists by SIM, fan voting, results reveal, certificates as share cards. Award names stay plain ("Simulator of the Season") until nicknames are layered in.
- Home shows the live race block.

### 9.9 Event pages (not mocked)
A template: event header (own colour accent within the token system), event-scoped rankings, Today's Case filtered to the event when it has matches, event awards, coverage for the event. World Cup, Champions League, end of season.

### 9.10 Vault (not mocked)
Browse by season → matchweek → match; "On this day"; random case; The Canon (all-time Double-Blind Trial ranking). Past Today's Cases listed by number (like Wordle's archive). Archive ratings don't affect streaks.

### 9.11 Methodology (not mocked)
Written as a **spoof academic paper**: abstract, the SIM formula and its ingredients (spec §9, weights "proprietary"), how cases are found (AI + review), **Limitations** (coverage per league/season with the hatched bar, "no footage ≠ zero", awaiting identification, AI confidence), "Conflicts of interest: none, sadly". Scrollytelling optional (The Pudding).

## 10. Interaction patterns

**Rate-to-reveal (decided).** Score hidden until the user submits a 1–10 acting score. After: SIM, Institute acting score and crowd average; your rating stored; streak +1; share unlocked.

**Double-Blind Trial (decided).** Five trials a day, mixing fresh and vault cases. Desktop: hover plays (muted loop from lead-in to recovery), leaving pauses. Mobile: the card nearest the viewport centre plays, one at a time; tap to choose. **Voting unlocks only after both have played once.** After voting: the split and the case's movement in The Canon. Ranking method: Bradley-Terry or Glicko with a minimum votes-per-pair before showing a rank (research warns Elo variants disagree).

**Compare flow (decided: from anywhere).** Any entity page → Compare ▾ (three suggestions + search) → hearing. Rankings → tick two → hearing. Compare tab → pick → hearing. The hearing's Share produces the Beef card.

**Share flow.** Share button → bottom sheet with the card preview, "Save image", "Copy link", native share (Web Share API on mobile), and for Today's Case "Copy text" (the emoji string). Every shared URL has a matching link preview (see §12).

**Scope lens.** Header switch + chips; remembered per browser; URL params override. Today's Case and trials ignore scope.

**No footage.** Hatching + "No footage" label on matches, fixture cells, meetings and coverage bars. Never a zero. Rates and per-90s use studied minutes only, and say so.

**Awaiting identification.** Cases without a confident player count for club/league totals only; a note explains the gap on player rankings and team pages. Later, fans can help identify (spec §7.1).

**Streaks.** Review streak counts consecutive days you reviewed Today's Case. Keep it light (no guilt copy). A weekly freeze ("physio bag") is a later option.

**Empty and launch states.** One league: hide league chips and "Which league dives most?". New season with few matches: show "Findings pending" instead of rankings until a minimum sample exists (Rotten Tomatoes rule).

## 11. Footage dependency and fallbacks

Public use of footballia clips is unresolved (spec §4). Everything below works in all three media modes.

| Element | Needs video? | Fallback |
|---|---|---|
| Today's Case media | Best with clip | **Diagram** (animated pitch replay from §7.4: approach, contact point, grounded time, rolls, recovery) or **Stills** (freeze frames) |
| Double-Blind Trial | Best with clip | Diagram replay plays on hover/centre; facts carry the comparison |
| Case log thumbnails | No | Static diagram thumbnail |
| Share cards | No | Diagram or generated art; never a video frame unless rights allow |
| Match page | No | Theatre momentum strip + case log |
| Player/compare maps | No | Built from pitch x,y (needs location data with confidence; hide dots below a threshold) |

**What the diagram needs from the data:** pitch location (x,y, normalised, spec §7.4), attacking direction, contact level, time grounded, rolls, miracle recovery trigger, ref decision, ideally the alleged fouler's position. Without location the diagram falls back to a "case card" (finding + stat grid, no pitch).

**Diagram v1 uses only what the pipeline records today (my call).** The schema holds one contact point (`pitch_x`, `pitch_y` with a confidence), not an approach path or the fouler's position. So v1 draws: the contact point; a **stylised** approach arrow from the attacking direction (marked "illustrative", not tracking data); the roll squiggle sized by roll count; a grounded-time counter; and the payoff label. Adding an approach path and the fouler's position is an optional pipeline extension for the Stage 2 plan. Below a location-confidence threshold, show the case card.

**Clips at launch** depend on the rights decision the spec requires before public launch. The design treats **Diagram as the default** and adds Clip as a mode when allowed. The plan should include R2 and the player only if that decision says yes.

**Stills** need rights for frames too; treat them as the same risk as clips. The safe default if rights fail is Diagram everywhere, and the mode switch hides unavailable modes.

## 12. Share cards and link previews

- **Rendered on the server** (spec §11), e.g. Next.js `ImageResponse`/Satori, from the same tokens. Fonts embedded.
- **Format:** 9:16 at 1080×1920 first. 4:5 (1080×1350) for the X timeline later. Transparent "SIM sticker" PNG later (Strava idea).
- **Link previews (Open Graph, 1200×630)** for every case, player, hearing and ranking URL, so a pasted link unfurls well in X and WhatsApp. Same visual language as the cards.
- **Every card** carries the wordmark, a short URL (`divestats.com/vellani`) and a footer fact (coverage or streak).

| Card | Content | Mock |
|---|---|---|
| **Rap sheet** (player/club/nation) | Ink background, mugshot with height chart and name plate, rank line, SIM + cases + avg grounded, one data-true "damning" line | `key-screens-v1.html` |
| **Beef card** (hearing) | Two sides with SIM, 4 tug-of-war stats, a plain "x% more per 90" line, studied matches in footer | same |
| **Today's Case** (after rating) | Hazard background, case number, diagram, your score vs Institute vs crowd as squares, a nudge line ("I went soft on him. Can you do better?"), streak | same |
| Text share | `Divestats Case #312 · 20 Nov` / `I rated 🟧🟧🟧🟧🟧⬜⬜⬜⬜⬜ 5` / `Institute ⬛⬛⬛⬛⬛⬛⬛⬛⬛⬜ 9` / line + URL | same |
| Later | Top-10 table card, weekly medal, award certificate, trial result, TikTok video | — |

## 13. Data the design needs (for the Stage 2 plan)

**Timing and ownership (my call, following spec §2):** this document is design only. The build starts after Stage 1 passes, on real tables, so no mock data layer is needed. The Stage 2 plan **owns** the data work below (pipeline changes and Supabase migrations), not just the UI that reads it.

Mostly from spec §7.4 and §9; these are the additions or clarifications the UI depends on:
1. **Global SIM scaling.** §9 scales SIM to ~100 within league/season. The "All leagues" lens needs a cross-league scale too (or rank by raw per-90 there). Decide before multi-league.
2. **Studied minutes per player/team** (minutes in matches with footage), for honest per-90s and the 900-minute threshold.
3. **Match coverage status** (studied / no footage / not yet processed) as first-class data, per league-season and matchweek.
4. **Case numbering** (stable per-season sequence).
5. **Rank history** (previous rank per scope) for ▲/▼.
6. **Percentiles by position** within scope.
7. **Clutched body part vs contact body part** as normalised categories (spec §7.4 has them as optional fields).
8. **Fan data:** acting ratings (per case, per user/token), trial votes (pairs, winner, timestamp), fan votes on hearings, streaks.
9. **Hearing suggestions:** fixtures list (next 7 days), curated rivalry list, "My clubs" preference.
10. **Awaiting-identification counts** per team/league.
11. **Images** (spec §6.2 stage-2 re-collection): headshots, crests, flags. Mugshot frame needs a consistent crop; fallback is the silhouette.

## 14. Accessibility

- AA contrast via `--hazard-strong` for small text and buttons (§7.1).
- Compare uses orange vs blue (colour-blind safe) and always shows numbers, never colour alone.
- Hatching is backed by the "No footage" text label.
- Slider is a native range input with keyboard steps and an announced value; the locked SIM is `aria-hidden` until reveal.
- Hover-to-play also works on focus and tap; autoplay is muted; respects reduced motion.
- Minimum touch target 44px (some mock chips are smaller; enlarge in build).

## 15. Monetization hooks
- Reserved slots: home (mid-scroll, mobile), desktop right rail 300×250, rankings (after row 10, builder's call). Render nothing in production until filled. Never an interstitial; never inside Today's Case, trials or share flows.
- Newsletter teaser in the home footer from launch ("Coming soon"); name to be confirmed (was "The Weekly Flop Report"; now "The Weekly Dive Report" in mocks).
- Sponsorship: a "Supported by" line on awards and event pages.

## 16. Later layers (parked, by Jamison's call or out of scope)
- Player classifications/archetypes; nicknamed awards (e.g. "Golden Swan").
- Skins (Tabloid, Journal) and A/B testing them; an "Edition" picker.
- Hearings ranked by social engagement.
- TikTok-ready vertical video cards (Remotion-style server rendering).
- "Certified Theatrical" badge with earn/lose thresholds (Rotten Tomatoes idea).
- Guess-the-diver daily game from an anonymised diagram (Who Are Ya idea).
- Mascot, streak freeze, season "Wrapped"-style recap.
- Generative match art as card backgrounds.

## 17. Changes this implies to the spec
- **Brand:** Flopstats → **Divestats** (domain, copy, case-number prefix `DS`). Repo/package names can stay.
- **Vocabulary:** "flop" → "case"/"simulation" in all public copy; "Flop of the Day" → "Today's Case"; "Flop Report" → "Case Report"; newsletter renamed.
- **§8.2 head-to-head:** "Who's the bigger flopper?" moves from home to Compare as "Fan vote"; home gets the **Double-Blind Trial** (case vs case), which is a new fan-input type to store.
- **§10 home:** adds Scheduled hearings, coverage ticker, "This week in the lab" and "Which league dives most?".

## 18. Left to the builder
- Component library and CSS approach (tokens as CSS variables are required; Tailwind or CSS modules are fine).
- Exact breakpoints (mock-ups assume 375px mobile and 1200px desktop).
- Dark mode values; seal artwork; diagram animation engine (SVG/CSS is enough).
- Anonymous vs signed-in rating storage, within spec §8.2.
- Routing and URL shapes (examples above are suggestions).
- Where Referees/Stadiums sit in navigation.

## 18a. Open follow-ups
- **Posting plan** to drive initial engagement (Jamison: "later"): which cards to post where and when around launch and the 2023-24 Awards, using the share cards and the calendar replay as the content engine.
- Buy simrating.com; pick and check the newsletter domain.
- The rights decision on public clips and stills (spec §4).

## 19. References

Researched 20 Nov 2026. Links were checked at the time; bot-blocked sites were confirmed via search. Fuller notes are in the research document kept with the design session.

**Spec starting list**
| Reference | Link | Borrowed |
|---|---|---|
| Wordle | https://www.nytimes.com/games/wordle/index.html | Numbered daily puzzle, spoiler-free emoji share, stats modal, archive |
| Spotify Wrapped 2025 | https://www.newsroom.spotify.com/2025-wrapped/ | Guess-before-reveal, colour saved for key moments; season recap later |
| FBref | https://fbref.com/en/ | Dense credible tables, per-90, summary-then-detail (layout only; lost Opta data Jan 2026) |
| Sofascore | https://www.sofascore.com | Rating chips, Attack Momentum → theatre momentum strip; warning: daily full-screen ad |
| Letterboxd | https://letterboxd.com | Satisfying rating row, year-in-review |
| Planet Football, Fallon d'Floor | https://www.planetfootball.com/lists-and-rankings/fallon-dfloor-2025-most-shocking-dives | Voice; links out instead of hosting clips (same rights problem); no scoring = our gap |
| FotMob | https://www.fotmob.com | Warning: pop-ups over article pages (evidence mixed) |

**Beyond the list**
| Reference | Link | Borrowed |
|---|---|---|
| Rotten Tomatoes | https://www.rottentomatoes.com/about | Critic vs audience score = Institute vs crowd; badges with thresholds; minimum-sample rule |
| Instagram emoji slider | https://about.instagram.com/blog/announcements/introducing-the-emoji-slider-sticker | Drag, release, see the crowd average → rate-to-reveal |
| Hudl StatsBomb freeze frames | https://www.hudl.com/blog/statsbomb-360-upgrade-adds-ai-powered-player-id | Still-image fallback showing positions at contact |
| John Muller match dashboards | https://johnspacemuller.substack.com/p/premier-league-match-dashboards | Video-free match page template |
| WC 2026 Data Portraits | https://wc26.bogachev.fr | Matches as generated art from event data |
| Fever case study | https://www.awwwards.com/case-study-fever.html | Trajectory glyphs per event |
| Opta Analyst radars | https://theanalyst.com/articles/introducing-opta-radars-compare-players | Compare benchmarks |
| mplsoccer | https://mplsoccer.readthedocs.io/en/latest/ | Server-side pitch plots/heatmaps in Python |
| The Pudding | https://pudding.cool | Opinionated questions; scrollytelling methodology |
| Razzies / Ig Nobel | https://www.razzies.com · https://improbable.com | Deadpan parody ceremonies run seriously |
| Who Are Ya? / Immaculate Footy | https://playfootball.games/who-are-ya/ · https://www.sports-reference.com/immaculate-footy/ | Daily football games, numbered archives, rarity scoring |
| Strava sticker stats | https://support.strava.com/en-us/articles/17718841-how-do-i-share-my-strava-activity-to-instagram-stories-as-a-transparent-sticker | Transparent sticker share output |
| Apple Music Replay | https://replay.music.apple.com | Full-screen animated share cards |
| GitHub Unwrapped / Remotion | https://githubunwrapped.com | Server-rendered per-user video (later) |
| Duolingo | https://blog.duolingo.com/how-duolingo-streak-builds-habit | Streaks and freezes, mascot voice (later) |
| BeReal | https://bereal.com | One daily drop, on-time rewards |
| EA SPORTS FC ratings | https://www.ea.com/games/ea-sports-fc/ratings | Leaderboard mini-modules (inspiration only; no trade dress) |
| Fantasy Premier League | https://fantasy.premierleague.com | Weekly cadence; warning about big-bang UI overhauls |

**Anti-patterns noted:** interstitial ads in rituals (Sofascore), guilt-trip streaks, AI-written jokes, big-bang redesigns, dependence on one data feed (FBref), copying trade dress, Elo ranking without uncertainty.
