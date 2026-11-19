"""`flopstats` command-line entry point."""

from __future__ import annotations

import typer

app = typer.Typer(no_args_is_help=True, add_completion=False)


@app.callback()
def main() -> None:
    """Flopstats pipeline."""


@app.command("verify-setup")
def verify_setup() -> None:
    """Check each service's key works with one cheap call. Prints OK/FAIL, never values."""
    from flopstats.config import Settings
    from flopstats.setup_check import check_all

    results = check_all(Settings())
    for r in results:
        status = "SKIP" if r.skipped else ("OK" if r.ok else "FAIL")
        typer.echo(f"{status:<5} {r.name:<18} {r.detail}")
    if not all(r.ok for r in results):
        raise typer.Exit(1)
