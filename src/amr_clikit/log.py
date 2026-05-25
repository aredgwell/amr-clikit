"""Structured logging contract for CLIs.

One configuration, shared by every CLI:

- Logs are diagnostics and go to **stderr**. Command results go to stdout via
  `amr_clikit.io` — never mix the two.
- JSON renderer when stderr is not a TTY (piped/redirected); a human-readable
  console renderer on a TTY. `NO_COLOR` disables colour.
- Level resolves from the explicit argument, else `AMR_LOG_LEVEL`, else INFO.
- Bound context (cli name, version) is attached to every event.

Each CLI calls `configure_logging(...)` once in its root command, then uses
`get_logger()` anywhere.
"""

from __future__ import annotations

import logging
import os
import sys

import structlog

_VERBOSITY_LEVELS = ["WARNING", "INFO", "DEBUG"]


def level_for_verbosity(verbose: int = 0, quiet: bool = False) -> str:
    """Map repeated -v / --quiet flags to a level name.

    quiet -> ERROR; default -> INFO; -v -> ... (capped at DEBUG).
    """
    if quiet:
        return "ERROR"
    index = min(1 + verbose, len(_VERBOSITY_LEVELS) - 1)
    return _VERBOSITY_LEVELS[index]


def _resolve_level(level: str | None) -> int:
    name = (level or os.environ.get("AMR_LOG_LEVEL") or "INFO").upper()
    return getattr(logging, name, logging.INFO)


def configure_logging(*, cli_name: str, version: str, level: str | None = None) -> None:
    """Configure structlog process-wide. Call once, in the root command."""
    use_json = not sys.stderr.isatty()
    no_color = bool(os.environ.get("NO_COLOR"))

    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    processors.append(
        structlog.processors.JSONRenderer()
        if use_json
        else structlog.dev.ConsoleRenderer(colors=not no_color)
    )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(_resolve_level(level)),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(cli=cli_name, version=version)


def get_logger(*args, **kwargs):
    """Return a bound structlog logger. Thin pass-through for a single import site."""
    return structlog.get_logger(*args, **kwargs)
