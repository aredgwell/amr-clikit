# amr-clikit

[![ci](https://github.com/aredgwell/amr-clikit/actions/workflows/ci.yml/badge.svg)](https://github.com/aredgwell/amr-clikit/actions/workflows/ci.yml)

A small, typed toolkit for Python CLIs: a **structured-logging contract** and
**stdout/stderr discipline**, so logs and results never get tangled.

The one rule it enforces: **diagnostics go to stderr, command results go to
stdout.** That keeps `mycli list | jq` working while logs still reach the
terminal. Logs render as JSON when piped and as concise message lines on a TTY.
Routine `info` diagnostics are hidden by default; use `-v` to show them and
`-vv` for debug logs.

Free-standing and dependency-light — any Typer or Click CLI can adopt it. It
depends only on [structlog](https://www.structlog.org/).

## Install

```bash
# core only
uv add "amr-clikit @ git+https://github.com/aredgwell/amr-clikit.git@v0.8.0"
# with the Typer glue (build_app + shared options)
uv add "amr-clikit[typer] @ git+https://github.com/aredgwell/amr-clikit.git@v0.8.0"
```

## API

Core (no CLI-framework dependency):

| Name | Purpose |
|---|---|
| `configure_logging(cli_name, version, level=None)` | Configure logging once, in the root command. JSON when piped, concise console messages on a TTY; level from `level` / `AMR_LOG_LEVEL` / `WARNING`. |
| `get_logger()` | A bound structlog logger (diagnostics → stderr). |
| `level_for_verbosity(verbose=0, quiet=False)` | Map `-v` count / `--quiet` to a level name. |
| `emit(data, output="text"\|"json"\|"agent")` | Write a result to stdout. A list of dicts renders as an aligned table in text mode (single-line cells; no trailing whitespace). `"json"` is compact, sorted-key JSON; `"agent"` is the same but whitespace-minimized, for LLM tool calls. |
| `confirm(prompt, assume_yes=False)` | Confirmation prompt; returns `False` in non-interactive contexts. |
| `CliError(message, exit_code=1)` | Raise for expected, user-facing failures. `CliError.usage(message)` is the same thing with exit 2, for *you called this wrong*. |
| `run_cli(entry)` | Run an entry point with the standard error/exit-code contract. |

Typer glue (`amr_clikit.cli`, needs the `typer` extra):
`build_app(cli_name, version, version_command=True, commands_command=True)`,
`command_tree(app)`, `AliasGroup`, `OUTPUT_OPTION`, `YES_OPTION`. Pass
`version_command=False` or `commands_command=False` to omit either subcommand;
`--version` stays either way.

## Usage

```python
from amr_clikit import CliError, OutputFormat, confirm, emit, get_logger, run_cli
from amr_clikit.cli import OUTPUT_OPTION, YES_OPTION, build_app

app = build_app(cli_name="mycli", version="1.0.0")  # -v/-vv/--quiet/--version + logging
log = get_logger()


@app.command(name="list")
def list_items(output: OutputFormat = OUTPUT_OPTION) -> None:
    log.info("listing items")                                  # -> stderr under -v
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
traceback shown only under `-vv`.

`CliError` reaches its exit code by both routes. `run_cli` is the outer
boundary, and apps built by `build_app` also map it in the group itself — so a
test driving the app with `typer.testing.CliRunner`, which never goes through
`run_cli`, sees the same exit code the installed binary gives.

### Command aliases

Apps built with `build_app` accept `|`- or `,`-separated aliases in a command
(or mounted sub-app) name — any of them resolves, and help shows them together:

```python
@app.command("list | ls")
def list_items() -> None: ...

app.add_typer(plugin, name="harness | h")  # `mycli h …` -> `mycli harness …`
```

A name without a separator behaves exactly as before. Shell completion offers
each alias as its own candidate (`list` and `ls`, not `list | ls`), and anywhere
a command is *named back* to the caller — the help table, the usage line, the
"did you mean" on a typo — it is named canonically, so what you are told to type
is something that runs.

### The command tree, as data

The audience for a CLI on this workstation is often not a person. Every command
here emits `--output json` on request — and so does the command surface itself:

```console
$ mycli commands --output json
[{"command": "list", "aliases": ["ls"], "help": "List the items."}, ...]
```

`command` is the spelling to prefer and `aliases` is a separate list, so nothing
puts a string like `list | ls` where a caller might type it. Sub-apps flatten to
`"parent child"`, so a row is a complete invocation, and every combination of
spellings that resolves is listed. It is derived from the live tree, so it
cannot fall behind what the app offers.

`build_app` registers it by default. To extend it — extra fields, or rows for
commands that are not in the tree at all — pass `commands_command=False` and
build on `command_tree(app)`:

```python
app = build_app(cli_name="mycli", version=__version__, commands_command=False)

@app.command("commands")
def commands(output: OutputFormat = OUTPUT_OPTION) -> None:
    emit([{**row, "runs": "mycli"} for row in command_tree(app)], output=output)
```

### Is it agent-ready?

`amr_clikit.testing.assert_agent_ready(app)` is one importable assertion to run
against your own tree in your own suite:

```python
from amr_clikit.testing import assert_agent_ready
from mycli.cli import app

def test_the_cli_is_legible_to_an_agent() -> None:
    assert_agent_ready(app)
```

It checks that every command's `--help` renders, that every alias `command_tree`
publishes actually resolves, that every command taking `--output` produces
parseable JSON, and that none of them writes its result anywhere but stdout.
Pass `skip={"deploy"}` for commands that must not be run.

### Exit codes

`2` means *you called this wrong* — an argument that does not parse, a name that
does not exist. `1` means *it ran, and found a problem*. The distinction is the
one a caller deciding whether to retry needs: a `2` fails identically however
many times it is repeated. `CliError.usage(message)` is the first case;
`CliError(message)` defaults to the second.

Diagnostics are already structured when stderr is not a TTY, so a caller
capturing stderr reads a failure as JSON — including the `exit_code` — rather
than parsing prose.

### Tables are single-line

`emit`'s table is for tabular data: one value per cell, on one line. A cell
holding a newline is not a cell — the second line starts at column zero and
every column after it is meaningless. Data that is multi-line by nature, such as
captured tool output with one line per package, wants its own sectioned
rendering rather than this table.

## Development

```bash
uv sync --extra dev
uv run ruff check . && uv run ruff format --check .
uv run pyright
uv run pytest
```

See [CHANGELOG.md](CHANGELOG.md) for release notes.
