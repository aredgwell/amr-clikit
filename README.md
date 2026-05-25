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
uv add "amr-clikit @ git+https://github.com/aredgwell/amr-clikit.git@v0.1.0"
# or
pip install "amr-clikit @ git+https://github.com/aredgwell/amr-clikit.git@v0.1.0"
```

## API

| Function | Purpose |
|---|---|
| `configure_logging(cli_name, version, level=None)` | Configure logging once, in the root command. JSON when piped, console on a TTY; level from `level` / `AMR_LOG_LEVEL` / `INFO`. |
| `get_logger()` | A bound structlog logger (diagnostics → stderr). |
| `level_for_verbosity(verbose=0, quiet=False)` | Map `-v` count / `--quiet` to a level name. |
| `emit(data, output="text"\|"json")` | Write a command **result** to stdout. |

## Usage (Typer)

```python
import typer
from amr_clikit import configure_logging, emit, get_logger, level_for_verbosity

app = typer.Typer(no_args_is_help=True)
log = get_logger()


@app.callback()
def main(
    verbose: int = typer.Option(0, "-v", count=True),
    quiet: bool = typer.Option(False, "--quiet"),
) -> None:
    configure_logging(
        cli_name="mycli", version="1.0.0", level=level_for_verbosity(verbose, quiet)
    )


@app.command(name="list")
def list_items(output: str = typer.Option("text", "--output")) -> None:
    log.info("listing items")             # -> stderr (JSON when piped)
    emit(["postgres", "kafka"], output=output)  # -> stdout
```

## Development

```bash
uv sync --extra dev
uv run ruff check . && uv run ruff format --check .
uv run pyright
uv run pytest
```

See [CHANGELOG.md](CHANGELOG.md) for release notes.
