# Flopstats

AI-detected soccer flops and dives, with cheeky stats. See `docs/superpowers/specs/` for the design.

## Machine setup (MacBook / Mac mini)

```bash
brew install ffmpeg uv node supabase/tap/supabase   # plus Docker Desktop or OrbStack
git clone https://github.com/jamisonpereira/flopstats.git
cd flopstats
cp .env.example .env && chmod 600 .env
open -e .env    # paste each value after its "=", no quotes or spaces, then save
```

`.env` is git-ignored, and coding agents are told never to read it (see `AGENTS.md`). The master copy of the keys is in 1Password ("Flopstats keys").
