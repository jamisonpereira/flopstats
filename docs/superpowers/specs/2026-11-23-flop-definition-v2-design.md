# Flop definition v2 and the judging loop

Date: 2026-11-23. Status: design, awaiting Jamison's approval.
Builds on: `2026-11-19-flopstats-design.md` (stage 1) and the pilot 2 run (run id 2).

## Why

Pilot 2 confirmed 55 flops in 5 matches, but Jamison only saw about 5 of them (the
review queue holds borderline items; the spot check shows a 10% sample). Those few
didn't look like flops. Before running the season, we need (a) a definition of a flop
that matches what the site is for, and (b) a way for Jamison to judge many detections
quickly, so we can tell whether the pipeline is pulling the right data and tune it.

The site's point: footballers exaggerate to win fouls and get opponents booked or sent
off. We want to catch that and show it, with a straight face.

## The definition (Jamison's)

A **flop** is any time a player goes down, or reacts, out of proportion to the contact:

- no or light contact and the player goes down (even a quiet drop-and-up counts);
- real contact, even a real foul, but a reaction far bigger than the contact
  ("light contact that is a foul, but they act like they've been murdered").

**Not a flop:** a reaction in proportion to what happened (a genuine injury; a hard
foul with an honest fall); a player who slips or falls with no attempt to deceive.

Two separate things are measured:

1. **Flop: yes/no.** The gate. Theatrics don't decide it.
2. **Theatrics: 1–10.** How big the performance is, only for flops.

Plus **who**: team and player.

Everything else (injury area, pitch position, contact level, referee decision, flop
type) is out of scope for this test and gets layered back in only once each is shown
to be reliable.

## Goals, non-goals, anti-goals

- **Goal:** a verifier prompt (v2) built on the definition above, run on pilot 2's
  clips, plus a judging screen and a scorecard that tell us how reliable it is
  (flop yes/no, theatrics, team, player), per model (Pro and Flash).
- **Goal:** Jamison can judge lots of clips fast (keyboard-first, one clip per screen).
- **Non-goal:** measuring what the wide net misses. This test only re-judges clips the
  pilot 2 scorer already flagged. A full re-run with a new scorer question (option B)
  comes after the verifier scores well.
- **Non-goal:** publishing anything, persisting incidents, cutting new clips.
- **Anti-goal:** a theatrics number that drifts between clips because it has no anchors.
- **Anti-goal:** judging that's so slow Jamison stops after 20 clips.

## Approaches considered

- **A. Re-judge pilot 2's stored clips with a new prompt (chosen).** No downloads, no
  re-scoring; every candidate segment from run 2 is still in storage. Cheap (~$5–7 in
  model calls for 167 clips × 2 models) and same-day. Can't measure what the scorer missed.
- **B. Re-run the whole pilot with new prompts everywhere.** Tests detection end to end
  including misses, but re-downloads 5 matches (~2 h, ~$10) and pays for the whole
  pipeline before we know the verifier works. Next step after A.
- **C. Hand-built test set first.** Most rigorous; slowest start; depends on Jamison
  collecting clips. Grows over time from Jamison's example videos and from A's judged clips.

Jamison picked A.

## The design

### 1. Verifier prompt v2

A new prompt version `v2` next to `v1` in `detect/gemini.py`, with its own answer
schema (`ModelAnswerV2`). Draft prompt (Jamison owns the wording; tweak freely):

```
You are reviewing a short clip from a {home} (home) vs {away} (away) football match.

A FLOP is any time a player goes down, or reacts, out of proportion to the contact:
- no contact or light contact, and the player goes down, even if they get straight back up;
- real contact, even a real foul, but the reaction is far bigger than the contact
  (rolling, clutching, appealing as if badly hurt from a light knock).
NOT a flop: a reaction in proportion to what happened (a genuine injury, a hard foul with
an honest fall), or a player who slips or loses balance without trying to deceive.
Whether the referee gives a foul or a card does not matter.

If there is a flop, rate its THEATRICS from 1 to 10:
1-2  drops and is straight back up, little reaction
3-4  a few seconds down, arms up appealing, maybe one roll
5-6  several seconds down, rolling and/or clutching, pained face
7-8  long time down (10 s+), repeated rolling or clutching, waves for the physio
9-10 a full performance: treatment or a long stoppage, then an instant recovery once
     the decision is made
Clutching a body part that wasn't touched, or a recovery the moment the free kick or
card is given, pushes the rating up.

Replays: the clip may include replays or slow motion. Judge the live action; use replays
only to see the contact more clearly. Report one flop: the clearest one in the clip.

Answer with JSON only, following the schema.
{kits}
Lineups (use them to name players by shirt number):
{lineups}
```

Answer schema v2:

| field | meaning |
|---|---|
| `is_flop` | bool |
| `confidence` | 0–1, confidence in `is_flop` |
| `theatrics` | 1–10, null when not a flop |
| `what_happened` | one sentence, plain words (shown to Jamison while judging) |
| `start_s`, `end_s` | the flop in seconds from the clip start (live action, not replay) |
| `flopper` | team (home/away), shirt number, name, confidence (same shape as v1's `PlayerGuess`) |

v1 stays as it is (pilot 1 and 2 used it; the report must keep working for them).

### 2. Re-judge command

`flopstats rejudge --from-run 2 --name pilot-2-v2 --config runs/pilot-v2.json`

- Creates a new detection run (run 3) whose config records `prompt_versions.verify = "v2"`,
  the verifier models (Pro and Flash), prices, and `source_run_id = 2`.
- Copies each run 2 candidate that has a `segment_path` into run 3 (same video, times,
  `final_score` and `segment_path`; status `pending`), recording the original in a new
  `candidates.source_candidate_id` column. Copying keeps the existing
  `verifications (candidate_id, model)` uniqueness and leaves run 2 untouched.
- Target: the hosted project, where pilot 2's data and segments live. Run 3's candidates,
  verifications and cost rows need no migration; `judgments` does (see Constraints).
- For each copied candidate: download the segment from storage to a temp file, run both
  verifiers with the v2 prompt, store answers in `verifications` (as today, via
  `verify.run_many`), set the candidate to `verified`/`rejected` by the primary verifier.
- Resumable: candidates that already have both verifications are skipped. Parallel calls
  as in `step_verify` (`workers`), budget guard as today.
- No incidents, no clips, no review items: judging works on candidates directly.

Needs a storage download (`StorageAdapter.get(path, dest)`): signed URL + streamed GET
for Supabase, file copy for local.

### 3. Judging screen

A new tab on the review screen, `/review/judge?run=3`, using the local review mode.

- **Order:** clips either model called a flop (by match, then time), with one clip both
  models rejected mixed in after every three (deterministic shuffle), then the remaining
  rejected clips. Mixing them in early keeps recall honest if Jamison stops partway
  (builder-check call). Jamison judges as many as they like; progress shows "judged N of M".
- **One clip per screen:** the candidate segment plays (signed URL to `segment_path`)
  with a marker for the model's `start_s`–`end_s`. Beside it, one model's answer, shown
  upfront (Jamison's choice, for speed): flop yes/no, theatrics, `what_happened`, team and
  player (named from the lineup by shirt number). Which model is shown (Pro or Flash) is
  picked at random per clip and stored as `shown_model`, so seeing an answer first pulls
  both models' scores the same way and the scorecard can check for that pull
  (builder-check call). The model's name is not shown.
- **Jamison marks:**
  - Flop? **yes / no / can't tell** (keys `y` / `n` / `?`).
  - If yes: theatrics **their own 1–10** (number keys; `0` = 10). Pre-filled with the
    shown model's number.
  - Team: **home / away / can't tell**, pre-selected from the model's guess.
  - Player: picked from the lineup, pre-selected from the model's guess (by shirt number);
    "can't tell" allowed.
  - Optional note.
  - Enter saves and moves to the next clip.
- Same clip appearing twice (overlapping 40 s pieces, or a replay of the same moment)
  is judged on each candidate as shown; the scorecard notes duplicates by overlapping time.

Stored in a new table `judgments`: **what is in the clip, not a grade of one model's
answer** (builder-check call), so both models are scored against the same truth and the
labels carry over to v3 and to the hand-built test set (approach C).
One row per clip, keyed on the **original** run 2 candidate (`source_candidate_id`), so a
later re-judge with a v3 prompt reuses the judgments instead of asking for them again.
Columns: `candidate_id` (the original clip), `is_flop` (bool, null = can't tell),
`theatrics` (1–10, null), `team` (home/away, null = can't tell), `player_id` (null =
can't tell), `shown_model`, `note`, timestamps. Re-judging a clip overwrites its row. Deleting a run
must not delete judgments (`on delete restrict`, like `reviews`).
RLS and grants like the other review tables (admins only).

### 4. Scorecard

`flopstats report --judged-run 3` prints, per model (Pro and Flash), over judged clips:

- **Flop precision:** of clips the model called a flop, how many Jamison called a flop.
- **Flop recall (within these clips):** of clips Jamison called a flop, how many the
  model caught.
- **Theatrics:** mean absolute difference from Jamison's number, and how often it's within 2.
- **Team and player accuracy** on clips Jamison called a flop and the model also did,
  against Jamison's team and player.
- "Can't tell" judgments are left out of the metric they're unsure about.
- **Cost** of the re-judge run.
- A short list of the biggest disagreements (candidate ids and `what_happened`), so the
  next prompt tweak has examples.

The other model's answer is read from `verifications`, so both models are scored on the
same judged clips.

### 5. Making all detections visible

The spot check's 10% sample stays for later runs. For this test, the judge tab is how
Jamison sees everything.

## Constraints

- Secrets rules in `AGENTS.md`: no `.env` reads; the rejudge command uses the existing settings.
- Hosted DB: the `judgments` and `source_candidate_id` migration goes to the hosted
  project only with Jamison's OK, asked for when the plan reaches it.
- Prompts and thresholds are Jamison's to steer (AGENTS.md "spirit"): the v2 wording
  above is a draft for Jamison to edit; scoring thresholds stay as config.
- The review screen runs locally (`npm run review:local`).

## Decided

- Definition and the two-step measure (Jamison).
- Approach A, then B (Jamison).
- Judging covers flop yes/no, theatrics, team, player (Jamison).
- Theatrics 1–10 with written anchors (proposed; Jamison approved the playback).
- Show rejected clips too, after the flops (proposed; approved with the playback).
- The model's answer is shown upfront while judging (Jamison, for speed).

## Calls made after the builder check (Claude's; check while reading)

- Judgments record what is in the clip (team, player, theatrics), pre-filled from the
  model, not a right/wrong grade of one model.
- Judgments are keyed on the original pilot 2 clip and survive run deletion, so v3 reuses them.
- Rejected clips are mixed in early (one per three) so recall stays honest if judging stops partway.
- The answer shown is from a random model per clip, unnamed, so the upfront answer biases
  Pro and Flash equally.
- Target is the hosted project; its one migration waits for Jamison's OK.

## Left to the builder

- Exact UI layout of the judge tab (keep it keyboard-first, one clip per screen).
- How the segment is streamed/downloaded and cleaned up.
- Report formatting.
