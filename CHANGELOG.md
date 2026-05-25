# Changelog

All notable changes to amr-clikit are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project
adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- MIT license, `py.typed` typing marker, and packaging metadata (classifiers,
  keywords, URLs) for public release.
- ruff lint + format configuration, pyright type-checking, `pytest-cov`, and a
  Python 3.12 / 3.13 CI matrix.
- Contract test suite covering log routing, JSON formatting, level filtering,
  and the `AMR_LOG_LEVEL` override.

### Changed

- Renamed the internal `logging` module to `log` to avoid shadowing the stdlib
  (public API via `amr_clikit` is unchanged).

## [0.1.0] - 2026-05-25

### Added

- Structured logging contract (`configure_logging`, `get_logger`,
  `level_for_verbosity`): JSON when piped, console on a TTY, `NO_COLOR`
  honoured, level via flags or `AMR_LOG_LEVEL`, diagnostics to stderr.
- `emit` for command results on stdout (`text` / `json`), keeping results and
  logs on separate streams.
