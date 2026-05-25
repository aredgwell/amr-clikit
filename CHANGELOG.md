# Changelog

All notable changes to amr-clikit are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
