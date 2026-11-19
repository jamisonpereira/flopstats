# Agent rules for Flopstats

## Secrets: hard rule
- **Never read, open, print, grep, copy or summarize `.env`** (or any `.env.*` file other than `.env.example`), in any way: file tools, shell commands, scripts or tests.
- Never echo environment variable values, and never log secrets. Use `.env.example` for variable names.
- To check that keys work, run `uv run flopstats verify-setup`, which reports OK/FAIL without printing values.
- If a task seems to require a secret's value, stop and ask the human instead.

## Project
- Design: `docs/superpowers/specs/2026-11-19-flopstats-design.md`
- Stage 1 plan: `docs/superpowers/plans/2026-11-19-flopstats-stage1-plan.md`
- Python pipeline in `pipeline/` (run with `uv`), Supabase migrations in `supabase/`, Next.js review screen and site in `web/`.
