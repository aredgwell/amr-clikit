# Changelog

All notable changes to amr-clikit are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.5.0] - 2026-08-25

### Fixed

- **`AliasGroup` no longer reports the declared string where a command name
  belongs.** v0.4.x fixed resolution and completion but left `list_commands`
  returning the registration key, so `@app.command("list | ls")` printed
  `list | ls` in the help table and — worse — answered a typo with
  `Did you mean 'workspace | ws'?`. That is a confident instruction that fails
  when followed, which for an agent reading the output is worse than no
  suggestion at all. `list_commands` now reports canonical names, commands are
  named canonically so the rich help table agrees, and `resolve_command`
  suggests one spelling at a time. Resolution and completion are unchanged:
  either spelling still runs, and completion still offers both.

  The registration keys are deliberately left alone — they are where the
  aliases are declared, and a consumer reading the command tree reads them from
  there.

### Changed

- The help table shows `list`, not `list | ls`, so a person reading `--help` no
  longer sees the alias there. Putting it in the command's help text would put
  alias text into the same attribute a structured reader takes as the help
  string. Aliases remain discoverable through completion, which offers each
  spelling as its own candidate.

## [0.4.1] - 2026-08-25

### Fixed

- Alias completion no longer offers a command twice in a group that lists more
  commands than it registers. `amr`'s root group appends declared sibling
  binaries to `list_commands`; 0.4.0 filtered the base class's own candidates
  against `self.commands`, so those siblings came through a second time.
  Filtering against `list_commands` covers both. Found while adopting 0.4.0.

## [0.4.0] - 2026-08-25

Two defects found while adopting 0.3.1 in `amr-agent-toolchain` and
`amr-publish`, each of which had been patched separately in both. Fixing them
here removes the duplication: a consumer on 0.4.0 can delete its local
`group.py` and `diagnostics.py` and change nothing else.

### Fixed

- **`get_logger()` no longer binds its output stream.** `configure_logging`
  used `PrintLoggerFactory(file=sys.stderr)` with
  `cache_logger_on_first_use=True`, which resolved the stream at configure time
  and cached the bound logger at first use. A module-level `log = get_logger()`
  — the documented idiom — therefore kept writing to whatever `sys.stderr` was
  the first time that module logged, for the life of the process. Invisible in
  a one-command process; under `typer.testing.CliRunner`, which replaces stderr
  per invocation and closes it afterwards, the second invocation in a test file
  raised `ValueError: I/O operation on closed file`. Logging now resolves
  `sys.stderr` at write time and no longer caches the bound logger, so the same
  logger also picks up a reconfigured *level*. Public API unchanged.
- **`AliasGroup` completes each alias separately.** Shell completion does not go
  through `get_command`; Click enumerates the registered names, so a command
  declared `@app.command("list | ls")` offered a single candidate spelled
  `list | ls` — a string that is not a command. `shell_complete` now offers
  `list` and `ls` as separate candidates, filtered by the typed prefix. Help
  and command resolution are unchanged.
- **`CliError` reaches its exit code without `run_cli`.** `run_cli` is the
  console-script path, so a test driving the app with `typer.testing.CliRunner`
  bypassed it and saw a bare exit 1 with the exception attached — making the
  exit code the one part of the contract a test could not assert. `AliasGroup`
  (which `build_app` uses) now maps `CliError` to its message and exit code in
  `invoke`, so both paths agree. `run_cli` remains the outer boundary.
- **`emit`'s table no longer pads its final column.** Every header row and any
  row with a short last cell carried trailing whitespace, which breaks
  copy-paste and shows up in diffs.
- **`run_cli`'s traceback hint names the right flag.** It said "re-run with -v";
  the traceback appears at DEBUG, which is `-vv`. The threshold is unchanged —
  the message and the docstrings were wrong.

### Added

- `build_app(..., version_command=False)` omits the `version` subcommand while
  keeping `--version`, for CLIs whose command tree gets enumerated.

### Changed

- The `typer` extra now requires `typer>=0.19`, not `>=0.12`. This is a
  correction, not an upgrade: `OutputFormat` is a `Literal`, and Typer only
  began accepting `Literal` parameter types in 0.19.0 — building an app on
  anything earlier raised `RuntimeError: Type not yet supported`. The declared
  floor had been wrong since 0.2.0. `structlog>=24.1` and `click>=8.1` are
  unchanged; both were verified against those floors.
- Dev tooling: `ruff>=0.16` (the generation whose formatter output this tree
  matches). Ruff 0.16 formats Python inside Markdown; `[tool.ruff.format]`
  excludes `*.md`, because the README's examples align their trailing comments
  deliberately.
- CI tests 3.12, 3.13 and 3.14, matching what the consumers test against.

### Documented

- `emit`'s table takes single-line cells. A value containing a newline is not a
  cell; multi-line data wants its own sectioned rendering. Stated in the
  docstring and the README rather than silently discovered.

## [0.3.1] - 2026-05-28

### Added

- `version` subcommand in `build_app` CLIs, matching the documented CLI
  convention alongside `--version`.

### Changed

- Console diagnostics are quiet by default (`WARNING`), with `-v` for info and
  `-vv` for debug.
- TTY diagnostics render as concise message lines rather than timestamped
  structured records.
- The `typer` extra now explicitly includes `click`, matching
  `amr_clikit.cli` imports.

## [0.3.0] - 2026-05-26

### Added

- `AliasGroup` (in `amr_clikit.cli`) and `build_app` wiring for command aliases:
  name a command or mounted sub-app with `|`/`,`-separated aliases
  (`@app.command("list | ls")`, `add_typer(plugin, name="harness | h")`) and any
  of them resolves. Non-breaking — names without a separator are unchanged.

## [0.2.0] - 2026-05-25

### Added

- `CliError` and `run_cli` for a consistent error/exit-code contract: expected
  errors become a stderr message + exit code, `KeyboardInterrupt` → 130, and
  unexpected errors → exit 1 with the traceback shown only under `-v`.
- `confirm` for interactive confirmation that stays safe in non-interactive
  contexts (returns `False` without a TTY).
- Tabular `emit` output — a list of dicts renders as an aligned table in text
  mode.
- Optional `typer` extra (`amr_clikit.cli`): `build_app` (pre-wires
  `-v`/`--quiet`/`--version` and logging) plus reusable `OUTPUT_OPTION` and
  `YES_OPTION`.
- MIT license, `py.typed` marker, and packaging metadata for public release.
- ruff lint + format, pyright, `pytest-cov`, and a Python 3.12 / 3.13 CI matrix.

### Changed

- Renamed the internal `logging` module to `log` to avoid shadowing the stdlib
  (public API unchanged).

## [0.1.0] - 2026-05-25

### Added

- Structured logging contract (`configure_logging`, `get_logger`,
  `level_for_verbosity`): JSON when piped, console on a TTY, `NO_COLOR`
  honoured, level via flags or `AMR_LOG_LEVEL`, diagnostics to stderr.
- `emit` for command results on stdout (`text` / `json`), keeping results and
  logs on separate streams.
