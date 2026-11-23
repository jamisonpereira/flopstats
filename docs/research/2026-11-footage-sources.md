# Full-match EPL footage sources: alternatives to footballia.eu

Research date: 2026-11-19. Read-only desk research: no sign-ups, trials, downloads or logins.
Scope: full 90-minute broadcasts (with the on-screen clock) of Premier League seasons 2015-16 to 2024-25. A source must give us a file that ffmpeg can process.

**Baseline (footballia.eu):** direct MP4 per half, login by form post, 1 GB in under a minute. It has at most 177 of a season's 380 matches. 2023-24 is the best season, and 2024-25 has 139. It's an unlicensed fan archive.

## TL;DR

- **The big news:** in about April 2026 the Premier League launched its own free **Premier League Archive** on premierleague.com and its app. It claims full-match replays of every match from 1992/93 to 2024/25 (now with some 2025/26), behind a **free myPremierLeague account**. That is 380 of 380 per season, roughly 2× footballia. **But** the web player is configured for **Widevine DRM** (MediaKind), and the terms forbid reuse, commercial use and building a database from site material. It's great for **manual viewing and spot-checks**. It's not a pipeline input unless the League licenses it to us.
- **Every legitimate consumer source is DRM-protected streaming** (Peacock, Stan, beIN, Sky/NOW, TNT/HBO Max, club TV, DAZN). Most keep only the current season and short-lived replays (Peacock about 30 days), so none covers 2015-2025 back catalogues. None is usable without circumventing DRM, which we won't do.
- **The licensed route for files** is **IMG Replay**, the Premier League's official archive licensing agent. Footage is non-exclusive, quote-only and approval-gated. It's likely expensive, but it's the clean answer to the "rights before public launch" risk. **Hudl Wyscout** has full matches with downloads, but only on sales-negotiated professional plans, and its rights are for "professional purposes" (scouting), not publishing.
- **The only other "free, downloadable files" options are unlicensed**: Internet Archive user uploads (sparse) and full-match replay aggregator sites (embeds on third-party file hosts). They're the same rights posture as footballia, but less reliable and with less coverage.

## Comparison table

| Source | Seasons / coverage (of 380) | Full match? | Cost & term | Downloadable file? | DRM | ToS on downloads / reuse | Notes |
|---|---|---|---|---|---|---|---|
| **footballia.eu** (baseline) | 2015-25; ≤177/season (best 2023-24; 2024-25 = 139) | Yes, per half | Free account | **Yes**, direct MP4 | No | Unlicensed fan archive | Works today; known rights risk |
| **Premier League Archive** (premierleague.com / app) | 1992/93–2024/25, claims **every match** (≈380/season); some 2025/26 replays posted | Yes ("full-match replays/reruns"), plus 3/8/20-min highlights | **Free** with myPremierLeague account; player code also has "Premium"/"Paid" entitlements and a per-country allow check | **No**, browser/app streaming only | **Widevine** configured in the web player (MediaKind `…/drm/widevine-license`) | Download only "for your own private and personal use"; no commercial use, reproduction or redistribution; no "creating a database" from site material | Official and very likely durable. US availability **not verified** (player has an `inAllowedCountry` gate). Best for manual review and ground truth |
| **Peacock (US, NBC)** | Current season only; replays of Peacock/NBC/USA matches | Yes | About $11–17/mo, monthly, cancel anytime (check current price) | No | Yes (standard for Peacock) | Personal, non-commercial streaming | Replays reportedly expire after about 30 days. Past seasons have highlights only. Can't reach 2015-25 |
| **NBC Sports Gold "Premier League Pass"** | 2017-2019 era | Was yes | Discontinued | n/a | n/a | n/a | Dead product |
| **Sky Sports / NOW (UK, IE)** | Current season | NOW: **no full replays** (3-min highlights) | Monthly passes | No | Yes | Personal use | Not viable |
| **TNT Sports / HBO Max (UK)** | Current season, TNT's live games only | Yes, on HBO Max catch-up | Monthly | No | Yes | Personal use | Subset of matches, current season only |
| **Stan Sport (Australia, since Aug 2025)** | Current season (all matches) | Yes (also condensed 25/9/3-min) | About A$27/mo (base + Sport), monthly | No | Yes | Personal use | Geo-locked to AU. Retention window unknown |
| **Optus Sport (AU)** | — | — | **Shut down 1 Aug 2025** | — | — | — | Replay library's fate unknown |
| **beIN SPORTS CONNECT (MENA)** | Current season, all 380 | Yes | Subscription | No | Yes | Personal use | Replays "for a limited period". Geo-locked |
| **DAZN** | Country-specific rights (e.g. Spain, Canada earlier) | Varies | Monthly | No | Yes | Personal use | No PL back catalogue found |
| **Club TV** (CITY+, LFCTV GO, MUTV, CFC+, etc.) | One club's matches; some classic matches | Yes, own club | e.g. CFC+ £14.99/yr; others unpublished | No | Yes | Personal use | 20 clubs × subscriptions is still DRM and still current-heavy |
| **FIFA+** | No PL full matches found | — | Free | — | — | — | Not a source for the PL |
| **IMG Replay** (official PL archive licensor) | Entire PL archive since 1992 (renewal covers through 2024/25, 1,140 matches for 2022-25) | Yes, broadcast masters | **Quote only**; non-exclusive; "subject to final approval" | **Yes**, licensed delivery | No (delivered files) | Licence terms negotiated | The legitimate path to files and publishing rights. Likely priced for broadcasters/producers |
| **PL "Turnstile"** | Full matches | Yes | Rights holders only | Yes | — | Rights holders only | Not available to us |
| **Hudl Wyscout** | Top leagues incl. PL (Football DataCo licence) | Yes | Online individual plans (Copper/Mercury) **exclude full-match views and downloads**; those features need a sales contract; plans are 1-year terms | Yes, on pro plans | Platform-controlled | Rights for "Professional Purposes"; app terms restrict sharing to other Wyscout users | Not "pay briefly". Publishing clips likely prohibited |
| **Hudl Instat / StatsBomb** | Pro football | Yes | Sales quote; aimed at clubs/organisations | Platform | Platform | Professional use | Same as Wyscout |
| **Getty / Reuters / AP / stock archives** | News clips, not matches | No | Per-clip licence | Yes | No | Licensed | PL match action is controlled by the League/IMG; these don't carry full matches |
| **Internet Archive (archive.org)** | ~930 "Premier League" video items in total (not all EPL); about 55 for 2023-24 and 65 for 2024-25, many split into halves; near zero for 2015-22 | Some full, often per half | Free | **Yes**, direct HTTP download | No | Uploader-posted, unlicensed; removed on DMCA | Sparse. Same rights issue as footballia. Coverage far below footballia |
| **Full-match replay aggregators** (fullmatchtv, footyfull, fullmatch-replay, etc.) | Mostly recent seasons; unknown depth | Usually | Free, ad-heavy | Embeds on third-party file hosts | Usually none | Unlicensed piracy | Unstable domains, malware risk. Not recommended |
| **506 Sports / torrent trackers** | Varies | Yes | Free | Yes | No | Unlicensed piracy | Not recommended; listed for completeness |

## How each compares to footballia's coverage

- **Better than footballia:** the PL Archive (≈380/380 per season, every season) and IMG Replay (complete). Both are blocked for pipeline use: the first by DRM and its terms, the second by price and a negotiation.
- **Roughly equal or worse, but downloadable:** nothing found matches footballia's 139–177 matches per season. Internet Archive has tens per season at best, and only for recent seasons.
- **Broadcasters:** one season at a time, and replays expire. None reaches back to 2015-25.

## Ranked recommendation

1. **Best free: keep footballia for the pipeline, and use the Premier League Archive for manual review.** The PL Archive is free and complete. It's the best way for the reviewer to check context, or watch a match footballia lacks. It can't feed the pipeline (Widevine DRM; no reuse or database building). For stage 1, pick the season that footballia covers best (2023-24, ≤177 matches) or accept a partial season. Internet Archive only works as a gap-filler for the odd recent match, under the same rights caveats.
2. **Best cheap: none that's usable.** Every cheap legitimate service (Peacock, Stan, club TV and the rest) is DRM streaming of the current season. We can't use any of them without circumventing DRM.
3. **Best "pay briefly": none.** There's no subscribe-collect-cancel option for files. The nearest is a **Hudl Wyscout pro contract**, which has full matches and downloads. It's a 1-year term, quote-only and for professional use only, so ask Hudl whether a short research licence is possible.
4. **The real fix before public launch: contact IMG Replay** about a non-exclusive archive licence (and, separately, a clip-publishing licence). It's the only source that solves coverage (380/380, files) and rights together. Also ask the Premier League whether myPremierLeague Archive access has any research or API tier (not advertised).

## Why footballia is missing matches, and other leagues' coverage

**Footballia's own explanation** (FAQ at https://footballia.eu/contact, read 2026-11-20):
- Matches come from people who recorded the TV broadcast and chose to share it. Footballia can't take requests: "we can't produce matches out of thin air." So gaps are whatever no contributor recorded and uploaded. They aren't a rights or geo policy.
- Commentary is in the language of whichever channel the recording came from. Often only one copy exists.
- The site says it was recently offline and "in danger of disappearing". It added more protection, its costs rose, and it now asks for support through a paid "Footballia Master" tier.
- **"Can I download matches? No, it's not permitted to download content from this website."** Our pipeline's downloader goes against this stated rule. That adds to the rights risk already in the design doc.
- No public statement about takedowns, DMCA or removed matches. No per-competition counts are published.

**Forums:** web searches found no Reddit or forum threads discussing footballia's gaps. Reddit blocks automated search, so this wasn't checked directly.

**Counts from footballia's public competition listings** (walked 2026-11-20 with the pipeline's own `catalog.parse_listing`, no login, 1 request/s; listings deduped by match URL; a match posted twice in different languages would count twice):

| Season | Premier League (380) | La Liga (380) | Serie A (380) | Bundesliga (306) | Ligue 1 (380 → 306 from 23-24) | Champions League (≈125 → 189 from 24-25, plus qualifiers) | Championship (552) | Eredivisie (306) | Primeira Liga (306) | FA Cup |
|---|---|---|---|---|---|---|---|---|---|---|
| 2015-16 | 103 | 109 | 46 | 48 | 25 | 101 | 9 | 7 | 15 | 14 |
| 2016-17 | 89 | 158 | 88 | 57 | 32 | 119 | 27 | 9 | 36 | 16 |
| 2017-18 | 134 | 185 | 134 | 61 | 43 | 135 | 23 | 16 | 40 | 23 |
| 2018-19 | 154 | **334** | 86 | 76 | 50 | 155 | 34 | 19 | 38 | 25 |
| 2019-20 | 126 | 191 | 118 | 86 | 68 | 145 | 50 | 22 | 49 | 19 |
| 2020-21 | 140 | 118 | 99 | 128 | 57 | 141 | 21 | 13 | 31 | 19 |
| 2021-22 | 130 | 120 | 102 | 93 | 78 | 152 | 29 | 5 | 15 | 25 |
| 2022-23 | 166 | 98 | 113 | 92 | 185 | 156 | 37 | 9 | 17 | 25 |
| 2023-24 | **177** | 114 | 105 | 124 | 156 | 153 | 62 | 13 | 36 | 24 |
| 2024-25 | 139 | 158 | 108 | 143 | **204** | **183** | 107 | 15 | 14 | 24 |
| 2025-26 | 162 | 108 | 108 | **195** | 197 | 196 | 59 | 21 | 5 | 22 |
| 2026-27 (in progress) | 40 | 35 | 40 | 31 | 46 | 81 | 25 | 7 | 5 | 2 |

What this shows:
- **No domestic league has full coverage on footballia.** The best season of any league is La Liga 2018-19, at 334/380 (88%). Bundesliga 2025-26 (195/306, 64%) and Ligue 1 2024-25 (204/306, 67%) are the next best.
- **The Champions League is close to complete in recent seasons.** 2024-25 has 183 listings against 189 matches in the new format. Older seasons are also high. Some listings may be qualifiers, so treat these as upper bounds.
- **Premier League 2025-26 (162) was missed earlier.** It's the most recent complete season and the second-best after 2023-24 (177). The 2026-27 season is being added as it's played (40 so far).
- Coverage moves around from season to season for every league. That fits volunteer uploading rather than a rule or takedowns.

**Team-page cross-check (2026-11-20):** walked the public team pages of all 20 clubs for 2023-24 and 2025-26 and compared them with the Premier League listing. **No hidden or mis-tagged Premier League matches turned up.** Every match on a team page between two PL clubs in that season was either already in the PL listing or correctly tagged as another competition: FA Cup, League Cup, Community Shield, Europa League or the Summer Series (16 such matches in 2023-24, 15 in 2025-26). The listing counts (177 and 162) are what footballia actually has.

**Missing Premier League matches, 2015-16 to 2025-26 (2026-11-20):** compared each season's full 380-fixture list (football-data.co.uk `mmz4281/<yyyy>/E0.csv`) with footballia's PL listing. Every footballia listing in every season maps to a fixture (zero left over). **2,660 of 4,180 fixtures are missing.** The full list (season, date, home, away, score) is in [`footballia-missing-pl-2015-2026.csv`](footballia-missing-pl-2015-2026.csv).

Matches on footballia per club and season (of 38; **bold** = complete; blank = not in the PL that season):

| Club | 15-16 | 16-17 | 17-18 | 18-19 | 19-20 | 20-21 | 21-22 | 22-23 | 23-24 | 24-25 | 25-26 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Man City | 11 | **38** | **38** | **38** | **38** | **38** | **38** | **38** | **38** | 21 | 18 |
| Liverpool | 15 | 15 | 22 | 27 | **38** | 22 | **38** | 25 | **38** | **38** | 20 |
| Man United | 32 | 9 | 20 | 31 | 19 | 27 | 21 | 20 | 24 | 18 | 24 |
| Arsenal | 15 | 14 | 16 | 16 | 16 | 14 | 13 | 37 | **38** | 14 | 21 |
| Chelsea | 15 | 15 | 18 | 34 | 15 | 12 | 18 | 21 | 16 | 19 | 27 |
| Tottenham | 11 | 8 | 15 | 18 | 15 | 16 | 13 | 20 | 21 | 15 | 16 |
| West Ham | 10 | 9 | 16 | 15 | 10 | 20 | 13 | 12 | 12 | 10 | 10 |
| Everton | 11 | 9 | 10 | 10 | 10 | 9 | 9 | 10 | 12 | 8 | 19 |
| Newcastle | 7 |  | 12 | 11 | 5 | 11 | 10 | 11 | 18 | 15 | 17 |
| Brighton |  |  | 14 | 9 | 11 | 9 | 7 | 25 | 13 | 12 | 10 |
| Leicester | 32 | 4 | 7 | 10 | 7 | 14 | 10 | 12 |  | 10 |  |
| Fulham |  |  |  | 15 |  | 7 |  | 11 | 13 | 10 | **38** |
| Nott'm Forest |  |  |  |  |  |  |  | 18 | 21 | 25 | 21 |
| Aston Villa | 4 |  |  |  | 8 | 8 | 10 | 8 | 18 | 12 | 12 |
| Bournemouth | 3 | 8 | 11 | 9 | 7 |  |  | 11 | 8 | 8 | 13 |
| Crystal Palace | 5 | 7 | 12 | 9 | 6 | 6 | 4 | 9 | 7 | 5 | 7 |
| Wolves |  |  |  | 13 | 7 | 11 | 8 | 11 | 12 | 10 | 5 |
| Southampton | 5 | 3 | 8 | 10 | 9 | 8 | 9 | 12 |  | 5 |  |
| Burnley |  | 3 | 7 | 8 | 8 | 8 | 7 |  | 9 |  | 7 |
| Leeds |  |  |  |  |  | 21 | 10 | 11 |  |  | 13 |
| Brentford |  |  |  |  |  |  | 10 | 10 | 11 | 10 | 12 |
| Watford | 4 | 6 | 7 | 10 | 7 |  | 6 |  |  |  |  |
| Sheffield United |  |  |  |  | 12 | 9 |  |  | 12 |  |  |
| Stoke | 6 | 9 | 10 |  |  |  |  |  |  |  |  |
| West Brom | 5 | 3 | 6 |  |  | 10 |  |  |  |  |  |
| Sunderland | 6 | 3 |  |  |  |  |  |  |  |  | 14 |
| Huddersfield |  |  | 12 | 7 |  |  |  |  |  |  |  |
| Swansea | 4 | 6 | 7 |  |  |  |  |  |  |  |  |
| Norwich | 5 |  |  |  | 4 |  | 6 |  |  |  |  |
| Ipswich |  |  |  |  |  |  |  |  |  | 13 |  |
| Luton |  |  |  |  |  |  |  |  | 13 |  |  |
| Cardiff |  |  |  | 8 |  |  |  |  |  |  |  |
| Middlesbrough |  | 5 |  |  |  |  |  |  |  |  |  |
| Hull |  | 4 |  |  |  |  |  |  |  |  |  |
| **Matches on footballia (of 380)** | 103 | 89 | 134 | 154 | 126 | 140 | 130 | 166 | 177 | 139 | 162 |

What it shows:
- **Coverage follows clubs, through a few dedicated uploaders.** Man City is complete for eight straight seasons (2016-17 to 2023-24). Liverpool is complete in 4 seasons, Arsenal in 2023-24 (37 in 2022-23), Fulham in 2025-26, and Leicester (32) and Man United (32) in 2015-16. When an uploader stops, the club drops off: Man City falls to 21 and then 18 after 2023-24.
- **Every other club is mostly covered only when it plays a "followed" club.** Crystal Palace, Wolves, Southampton, Burnley and the promoted clubs usually have 4–13 matches a season, which is roughly their games against the followed clubs.
- **For stage 1** (stats across all 20 clubs), any footballia season over-represents the followed clubs and their opponents. Per-club flop stats must be normalised by matches covered, and "flops per match" for small clubs will rest on a handful of matches, mostly against big clubs. 2023-24 has the most matches (177), but Arsenal, Liverpool and Man City are each complete in it, so it's the most skewed toward them.
- The missing games are spread across each season, not bunched into particular months.

## Filling the gaps: options for the MVP and beyond

Brainstormed 2026-11-20. The plan is to launch on partial data to test interest, then fill gaps. Costs are rough estimates, not quotes.

**Two rules regardless of option.** (1) We publish stats, not footage. Flop counts, timestamps and incident notes are facts. Clips stay internal and are never re-hosted. Re-hosting is what draws enforcement, and the Premier League is one of the most aggressive anti-piracy enforcers in sport. (2) We don't circumvent DRM (for example, stripping Widevine from the PL Archive). It's a separate legal violation (DMCA §1201 and its UK equivalent) that applies whatever we do with the video, so it's off the table.

### Cheap and fairly safe
1. **Paid annotators on the PL Archive.** The archive is free with a myPremierLeague account. Offshore annotators (Upwork, OnlineJobs.ph) watch at 1.5–2x and log timestamps in our review screen. We never handle the video. At about 70 minutes per match: all 2,660 missing matches is about 3,100 hours (about $19k at $6/hr). Completing just 2023-24 (203 matches) is about $1.5–3.5k. Risk: the archive's terms forbid building a database from the service, but watching and recording what you saw is hard to police.
2. **Fill selectively, not completely.** For fair per-club stats we need about 15–19 matches per club per season with a spread of opponents, not 380/380. Fill the small clubs' gaps first and skip the extra matches of the followed clubs. That's roughly a third of option 1's cost.
3. **Event data to aim annotators.** Free or scrapeable sources (FotMob, Sofascore, Understat, StatsBomb open data) give fouls won, simulation yellow cards and penalties with minute stamps. Annotators jump to those moments instead of watching the full 90, cutting hours by an estimated 3–5x. Scraping breaches those sites' terms, but it's low stakes.
4. **Modelled "expected flops" (xFlops).** Train a model on matches we tagged from video, using fouls won, no-card fouls, minute, score state and player. Then estimate the uncovered matches. Label the results as estimates. This gives full coverage on day one and makes a shareable story.
5. **Cover the current season live.** (Corrected 2026-11-20: most of this can't be recorded to a file.) In the US, most matches are on Peacock, many on USA Network, and about one per matchweek on NBC's broadcast network (the Saturday 12:30 ET slot). Only that over-the-air NBC match can be recorded to a file without DRM, using an antenna plus HDHomeRun, Tablo or Channels DVR. On cable, USA Network is usually flagged copy-once or copy-never, so an HDHomeRun Prime can show it live but not record it. Peacock and the online TV services (YouTube TV, Sling) are DRM-protected, so they're off the table under rule 2. The workable version: annotators watch live or on Peacock replay and log flops as they happen, and clips come from embeds (see "Clips" below). Footballia's uploaders and the newer aggregators also cover the current season best (see the coverage check below).

### Community-powered
6. **Crowdsourced reports.** A "report a flop" form (match, minute, player), checked by annotators. Rival fans are motivated to submit, and it doubles as marketing and an interest test.
7. **Pay footballia's uploaders.** The volunteers behind the complete Man City and Liverpool runs have recording setups and may hold unuploaded matches, or could cover other clubs for a fee per match. Reach them through footballia or club forums.
8. **Club fan communities.** Forums such as RedCafe and Bluemoon, and Discord groups of match collectors, keep their own full-match archives. Ask for, or pay for, access.

### Grey market (more coverage, more risk)
9. **International re-uploads.** Full matches appear on VK, Bilibili, Youku and Douyin (China held PL rights via PP Sports until 2022), and briefly on YouTube. Coverage is patchy but often includes small-club games. Downloading is infringement on our side, so use it internally only and delete copies after tagging.
10. **Full-match aggregator sites** (for example, footballorgin). Broad coverage, but these are pirate sites, so the same caveat applies. Enforcement targets the sites more than viewers, but a company is a more attractive target than an individual.

### With traction
11. **License.** Ask IMG Replay for a quote, or buy Opta-style event data with a simulation tag. This is where "worry about it later" comes due, and having users and a deck strengthens the negotiation.

### Grey-market coverage check (2026-11-20)

This was a read-only check of 22 missing matches: two per season, one involving small clubs only and one involving a big club. A "hit" means a page claims to have the full match. Nothing was played or downloaded, so none of these is confirmed to play.

| # | Match | Where it was found |
|---|---|---|
| 1 | 2016-01-13 Swansea v Sunderland | iQiyi Sports (ex-SSports) listing |
| 2 | 2016-05-15 Swansea v Man City | iQiyi Sports listing; Man City's CITY+ |
| 3 | 2016-10-22 Leicester v Crystal Palace | PPTV |
| 4 | 2016-12-17 Crystal Palace v Chelsea | footballorgin, page undated (possible) |
| 5 | 2017-09-16 West Brom v West Ham | PPTV |
| 6 | 2017-09-16 Tottenham v Swansea | PPTV; footballorgin |
| 7 | 2019-04-02 Watford v Fulham | PPTV (Chinese and English commentary); iQiyi Sports |
| 8 | 2018-10-28 Burnley v Chelsea | PPTV (Chinese and English); iQiyi Sports |
| 9 | 2020-01-11 Leicester v Southampton | PPTV |
| 10 | 2020-07-09 Bournemouth v Tottenham | PPTV |
| 11 | 2020-10-18 Leicester v Aston Villa | probable: Tencent title, footballorgin listing |
| 12 | 2021-04-04 Newcastle v Tottenham | Tencent (in halves) |
| 13 | 2021-11-28 Brentford v Everton | **not found** |
| 14 | 2021-09-11 Arsenal v Norwich | footballorgin |
| 15 | 2022-09-03 Nott'm Forest v Bournemouth | **official AFC Bournemouth YouTube** (full replay) |
| 16 | 2023-02-04 Man United v Crystal Palace | footballorgin |
| 17 | 2024-03-16 Luton v Nott'm Forest | probable: footballorgin listing |
| 18 | 2023-09-17 Bournemouth v Chelsea | fullreplays |
| 19 | 2024-12-08 Leicester v Brighton | fullreplays |
| 20 | 2024-09-21 Crystal Palace v Man United | fullreplays |
| 21 | 2026-01-18 Wolves v Newcastle | fullmatchshows; Migu (via the zhibo8 replay index) |
| 22 | 2026-02-01 Tottenham v Man City | footballorgin; fullmatchshows; Migu |

**Result: 18 of 22 confirmed listed somewhere, 20 counting the probables.** The best source depends on the era:
- **2015-19: China's licensed archives.** PPTV and the iQiyi Sports (ex-SSports) archive have 7 of 8, often with an English-commentary version as well. These are licensed broadcasters, not pirates, but they're geo-locked to mainland China, often paid (VIP or pay-per-match), and probably DRM-protected. A legitimate way to use them is to hire annotators in China to watch.
- **2019-23: the weakest era.** Five of 8 were found across PPTV (2019-20), Tencent (2020-21), footballorgin and one official club upload. No 2021-22 to 2024-25 replays were found on iQiyi, whose old albums appear to have been taken down.
- **2023-26: aggregators.** fullreplays, fullmatchshows and footballorgin have 5 of 6. These sites embed third-party file hosts (Streamtape, DoodStream, Mixdrop, OK.ru), which are heavy with ads and malware. The sites also churn: fullreplays now redirects to a parking domain, and its successor, fullmatchshows, only goes back to Nov 2025.
- **Dead ends:** YouTube (only official club uploads survive; unofficial "full matches" are fakes or watchalongs), Dailymotion (0/22, though the "WSFM" accounts host dozens of 2023-26 PL matches), OK.ru (logged-out search doesn't work; one channel posts Russian-commentary full matches) and Bilibili (0/22). VK, Youku, Douyin and Xigua couldn't be checked without logging in.
- **Official club full replays** are worth mining: Bournemouth "Relive the entire 90", Leicester, Chelsea and Man City's CITY+. They're free and legitimate, but only cover selected matches.

Note: through 2024-25 the PL Archive already lets annotators *watch* every match legitimately. The grey sources only matter if we need *files*, either for the automated pipeline or to cut clips.

### Clips

Clips matter to the product, and publishing them is where the legal risk concentrates, more than where the footage came from. In order of safety:
1. **Embed, don't host.** YouTube embeds take start and end times, so a flop can play from an official upload (a club's full-match replay, or NBC Sports or club highlights) without us hosting anything. The same goes for embedding social posts. Coverage is limited to what's officially posted, but the risk is close to zero.
2. **Short self-hosted clips with analysis** (a few seconds, annotated with slow-mo and arrows). US fair use for criticism or commentary, and UK fair dealing for criticism and review, make this defensible but contested. Expect DMCA notices, and have a takedown process. Book a one-off consult with a sports-media IP lawyer before launch (a few hundred to a couple of thousand dollars).
3. **Clips cut from pirated copies and published.** This stacks infringement in getting the footage on top of infringement in publishing it. It's the scenario most likely to draw a Premier League letter, so it shouldn't be part of a public launch.

**Decision (2026-11-20):** we publish only very short clips of the flop itself, annotated. A lawyer will review this later, before public launch.

#### Why annotation helps a fair-use case (not legal advice)

Annotation doesn't make a clip fair use by itself. It makes the strongest part of the argument stronger.

**US fair use, four factors:**

| Factor | Short annotated flop clip |
|---|---|
| 1. Purpose and character | **Annotation helps here.** The broadcast exists to show the match. Our clip uses a few seconds as evidence for a claim ("he went down before contact"). The arrows, slow-mo and verdict show the purpose is commentary, not replay. Caveats: since *Andy Warhol Foundation v. Goldsmith* (US Supreme Court, 2023), adding new meaning isn't enough without a genuinely different purpose, and commercial use counts against us. |
| 2. Nature of the work | Neutral to slightly negative. The broadcast is mostly factual, but camera and editing choices are protected. |
| 3. Amount used | **Helps if the clip stays short.** 3–8 seconds of the flop alone, out of a 90-minute broadcast, and only what the point needs. |
| 4. Market harm | **The biggest risk.** The PL licenses highlight clips, so a clip that works as a highlight takes that market. A clip that only makes sense alongside our analysis is much harder to call a substitute. |

There is little case law on short sports clips used for commentary, so the position is defensible, not settled.

**UK fair dealing (narrower):**
- *Criticism or review* (CDPA s30(1)) needs criticism of "a work" or "a performance of a work". Criticising a player's dive arguably targets an event within the broadcast rather than the broadcast itself, which makes this exception weaker.
- *Reporting current events* (s30(2)) fits better. In *BBC v British Satellite Broadcasting* (1991), short World Cup clips in news bulletins were held to be fair dealing. This helps for current-season flops, not for archive seasons.
- *Quotation* (s30(1ZA), added in 2014) is broader but untested for video. The extract must be no longer than necessary.

**House rules for clips:** keep them a few seconds long, covering only the flop. Annotate every clip and tie it to a verdict or stat. Never publish anything that works as a standalone highlight. Credit the broadcaster. Respond fast to takedowns.

**Questions for the lawyer:**
1. How much do commercial use and the existence of a licensed highlights market hurt factors 1 and 4?
2. Which UK exception would we rely on, especially for archive seasons?
3. Does the footage's source (licensed, a club upload, or grey market) change the analysis?

### Suggested path
Launch on footballia plus xFlops estimates (options 4 and 1). Spend about $2–3k on PL Archive tagging guided by event data to balance one season (options 1–3). Add crowdsourced reports to test interest (option 6). This needs nothing from the grey market (options 9–10).

## Couldn't verify

- Whether the PL Archive is available in the US, and whether every match it lists really has a full replay (one secondary outlet says "a select amount of full 90 minute games"). Also, whether the archive streams carry the original broadcast's on-screen clock and graphics, or a world-feed version, and their resolution. Checking these needs a signed-in session.
- Whether Widevine is actually applied to every archive stream. The player code attaches a Widevine licence URL to the player config. I didn't inspect a live stream because I wasn't signed in.
- Peacock's current price and its exact replay retention (about 30 days is reported by third parties, not by Peacock).
- Stan Sport and beIN retention windows, and what happened to Optus Sport's replay library.
- Pricing for IMG Replay, Wyscout pro and Instat (all quote-only).
- Real depth of the full-match aggregator sites (not visited; piracy and malware risk).
- Internet Archive counts are from a title search for "premier league" (videos). They include other leagues' "Premier League" items and per-half uploads, so the true number of EPL matches is lower.

## Sources

- Premier League Archive overview: https://www.premierleague.com/en/welcome/the-archive/overview
- Premier League Archive page ("full-match reruns of EVERY match"): https://www.premierleague.com/en/welcome/the-archive
- "Introducing the Premier League Archive" (dated 31 Mar 2026): https://www.premierleague.com/en/news/4345626/introducing-the-premier-league-archive
- SportBible on the free archive rollout (1 Apr 2026): https://www.sportbible.com/football/premier-league/premier-league-announcement-free-409399-20260401
- myPremierLeague sign-up: https://www.premierleague.com/en/news/4345793/sign-up-now-to-mypremier-league/
- premierleague.com terms of use (IP section): https://www.premierleague.com/en/terms-and-conditions
- PL broadcast FAQ (no PL on-demand subscription; regional licences): https://www.premierleague.com/en/about/faq/broadcast
- PL Archive web player code (Widevine/MediaKind config, `inAllowedCountry`, Premium/Paid entitlements), read in-browser: https://www.premierleague.com/resources/v1.57.16/scripts/video-player.js and https://www.premierleague.com/resources/v1.57.16/scripts/get-media-kind-video-player-config.js
- PL Turnstile (rights holders only): https://turnstile.premierleague.com/help
- IMG Replay, Premier League archive: https://www.imgreplay.com/client/premier_league_archive
- PL and IMG archive renewal to 2024/25: https://www.broadcastnow.co.uk/production/premier-league-and-img-continue-archive-partnership/5173141.article and https://www.sportcal.com/news/media/premier-league-and-img-replay-renew-long-running-video-archive-deal
- Goalhanger acquires PL archive footage rights (single source): https://www.insideworldfootball.com/2026/01/07/linekers-goalhanger-expands-launch-greats-show-driven-pl-archive-footage/
- Peacock Premier League: https://www.peacocktv.com/sports/premier-league
- Peacock replay removals: https://thestreamable.com/news/some-premier-league-matches-no-longer-available-on-demand-with-peacock
- Goal.com on US on-demand (about 30-day replays): https://www.goal.com/en-us/news/how-to-watch-and-live-stream-english-premier-league-soccer-on-demand/blt24a8371d60a2d8c0
- NBC Sports Gold Premier League Pass (historic): https://nbcsports.com/2017/06/27/nbc-sports-gold-introduces-premier-league-pass-with-exclusive-access-to-130-live-matches-unprecedented-suite-of-shoulder-programming/
- NOW (IE), no full match replays: https://www.nowtv.com/ie/help/article/watching-premier-league-with-now-ie
- Goal.com UK highlights and replays guide (TNT/HBO Max): https://www.goal.com/en-gb/news/premier-league-highlights-full-match-replays/blt7236868af8da3734
- Optus Sport shutdown: https://www.finder.com.au/news/optus-sport-shuts-down-how-to-keep-watching-epl-australia and https://en.wikipedia.org/wiki/Optus_Sport
- Stan Sport EPL replays and pricing: https://www.comparetv.com.au/stream-live-sport/epl and https://www.comparetv.com.au/epl-english-premier-league-highlights/
- beIN CONNECT replays: https://support.connect-au.beinsports.com/hc/en-us/articles/44223366979469-Can-I-Watch-Match-Replays-or-Highlights-After-a-Live-Game-Ends
- beIN MENA rights to 2028: https://www.sportsvideo.org/2025/06/20/bein-media-group-extends-exclusive-broadcast-rights-of-the-premier-league-across-mena-until-2028/
- PL broadcast deals 2025-28 (DAZN territories): https://www.premierleague.com/en/news/3703577
- Man City CITY+: https://supporterservices.mancity.com/hc/en-gb/articles/17653443476116-What-is-CITY
- MUTV FAQ: https://www.manutd.com/en/help/faqs/mutv
- LFCTV GO pricing FAQ: https://faq.liverpoolfc.com/portal/en/kb/articles/wsgo-lfctv-how-much-is-lfctv-go-subscription
- Chelsea CFC+: https://memberships.chelseafc.com/en/subscriptions
- Hudl Wyscout pricing (online plans exclude full-match views and downloads; 1-year term): https://www.hudl.com/products/wyscout/pricing
- Wyscout FAQ: https://www.hudl.com/products/wyscout/faq
- Wyscout general terms (PDF): https://get.wyscout.com/service.pdf
- Wyscout video data sourcing standard: https://hudl.com/blog/wyscout-video-data-sourcing-standard
- Hudl and Football DataCo licence: https://www.hudl.com/blog/hudl-announces-licence-deal-with-football-dataco-for-premier-league-and-english-football-league
- Hudl Instat FAQ: https://www.hudl.com/products/instat/faqs
- Hudl StatsBomb FAQ: https://www.hudl.com/products/statsbomb/faq
- Internet Archive search API (queried 2026-11-19, `title:("premier league") AND mediatype:movies`): https://archive.org/advancedsearch.php
- Example IA item: https://archive.org/details/tottenham-v-liverpool-sky-sports-uhd
- Aggregator listings (low-quality sources, not visited): https://alternativeto.net/software/watch-full-replay/about
