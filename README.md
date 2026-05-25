# amr-clikit

[![ci](https://github.com/aredgwell/amr-clikit/actions/workflows/ci.yml/badge.svg)](https://github.com/aredgwell/amr-clikit/actions/workflows/ci.yml)

A small, typed toolkit for Python CLIs: a **structured-logging contract** and
**stdout/stderr discipline**, so logs and results never get tangled.

The one rule it enforces: **diagnostics go to stderr, command results go to
stdout.** That keeps `mycli list | jq` working while logs still reach the
terminal. Logs render as JSON when piped and as readable console lines on a
TTY (honouring `NO_COLOR`).

Free-standing and dependency-light — any Typer or Click CLI can adopt it. It
depends only on [structlog](https://www.structlog.org/).

## Install

```bash
# core only
uv add "amr-clikit @ git+https://github.com/aredgwell/amr-clikit.git@v0.2.0"
# with the Typer glue (build_app + shared options)
uv add "amr-clikit[typer] @ git+https://github.com/aredgwell/amr-clikit.git@v0.2.0"
```

## API

Core (no CLI-framework dependency):

| Name | Purpose |
|---|---|
| `configure_logging(cli_name, version, level=None)` | Configure logging once, in the root command. JSON when piped, console on a TTY; level from `level` / `AMR_LOG_LEVEL` / `INFO`. |
| `get_logger()` | A bound structlog logger (diagnostics → stderr). |
| `level_for_verbosity(verbose=0, quiet=False)` | Map `-v` count / `--quiet` to a level name. |
| `emit(data, output="text"\|"json")` | Write a result to stdout. A list of dicts renders as an aligned table in text mode. |
| `confirm(prompt, assume_yes=False)` | Confirmation prompt; returns `False` in non-interactive contexts. |
| `CliError(message, exit_code=1)` | Raise for expected, user-facing failures. |
| `run_cli(entry)` | Run an entry point with the standard error/exit-code contract. |

Typer glue (`amr_clikit.cli`, needs the `typer` extra): `build_app(cli_name, version)`, `OUTPUT_OPTION`, `YES_OPTION`.

## Usage

```python
from amr_clikit import CliError, OutputFormat, confirm, emit, get_logger, run_cli
from amr_clikit.cli import OUTPUT_OPTION, YES_OPTION, build_app

app = build_app(cli_name="mycli", version="1.0.0")  # -v/--quiet/--version + logging
log = get_logger()


@app.command(name="list")
def list_items(output: OutputFormat = OUTPUT_OPTION) -> None:
    log.info("listing items")                                  # -> stderr
    emit([{"name": "postgres", "port": 5432}], output=output)  # -> stdout (table or json)


@app.command()
def remove(name: str, yes: bool = YES_OPTION) -> None:
    if not confirm(f"Remove {name}?", assume_yes=yes):
        raise CliError("aborted")
    log.info("removed", name=name)


def run() -> None:  # console_scripts entry point
    run_cli(app)
```

Errors are reported consistently: `CliError` → its message on stderr and its
exit code; `KeyboardInterrupt` → 130; anything unexpected → exit 1 with the
traceback shown only under `-v`.

## Development

```bash
uv sync --extra dev
uv run ruff check . && uv run ruff format --check .
uv run pyright
uv run pytest
```

See [CHANGELOG.md](CHANGELOG.md) for release notes.
