# Agent rules for Flopstats

## Secrets: hard rule
- **Never read, open, print, grep, copy or summarize `.env`** (or any `.env.*` file other than `.env.example`), in any way: file tools, shell commands, scripts or tests.
- Never echo environment variable values, and never log secrets. Use `.env.example` for variable names.
- To check that keys work, run `uv run flopstats verify-setup`, which reports OK/FAIL without printing values.
- If a task seems to require a secret's value, stop and ask the human instead.

## The spirit of the project

Divestats is a scrappy experiment with one question to answer: do people care?
Until that's answered, we move fast, take swings and sort out the grown-up
stuff (licensing, polish, process) later, if it earns it.

- **Bold over safe.** When there's a choice, pick the more interesting option
  and say why in a sentence. Don't hedge, and don't keep re-raising risks the
  owner has already accepted.
- **Provocative ideas, straight face.** We say things fans will argue about.
  The tone is the brand's deadpan research institute (`docs/design/design.md`),
  never shouty.
- **Rules later, truth always.** We'll bend norms to get noticed, but every
  claim is about something that really happened. No fabrication, no DRM
  breaking or borrowed logins, no going after ordinary fans.
- **The owner steers the details.** Detection prompts, thresholds and what we
  post are decided case by case. Bring options; don't make those calls alone.

## Project
- Design: `docs/superpowers/specs/2026-11-19-flopstats-design.md`
- Stage 1 plan: `docs/superpowers/plans/2026-11-19-flopstats-stage1-plan.md`
- Python pipeline in `pipeline/` (run with `uv`), Supabase migrations in `supabase/`, Next.js review screen and site in `web/`.
