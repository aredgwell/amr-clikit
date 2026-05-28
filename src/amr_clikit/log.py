"""Structured logging contract for CLIs.

One configuration, shared by every CLI:

- Logs are diagnostics and go to **stderr**. Command results go to stdout via
  `amr_clikit.io` — never mix the two.
- JSON renderer when stderr is not a TTY (piped/redirected); concise event-only
  output on a TTY so routine commands stay quiet and readable.
- Level resolves from the explicit argument, else `AMR_LOG_LEVEL`, else WARNING.
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
_CONSOLE_RESERVED_KEYS = {"event", "level", "timestamp", "cli", "version"}

# Resolved level of the most recent configure_logging() call; used by run_cli to
# decide whether to surface a traceback for unexpected errors.
_LEVEL = logging.WARNING


def level_for_verbosity(verbose: int = 0, quiet: bool = False) -> str:
    """Map repeated -v / --quiet flags to a level name.

    quiet -> ERROR; default -> WARNING; -v -> INFO; -vv -> DEBUG.
    """
    if quiet:
        return "ERROR"
    index = min(verbose, len(_VERBOSITY_LEVELS) - 1)
    return _VERBOSITY_LEVELS[index]


def _resolve_level(level: str | None) -> int:
    name = (level or os.environ.get("AMR_LOG_LEVEL") or "WARNING").upper()
    return getattr(logging, name, logging.INFO)


def _console_message_renderer(_, __, event_dict: dict) -> str:
    """Render human stderr as a short message, not a structured log record."""
    event = str(event_dict.get("event", ""))
    details = [
        f"{key}={value}"
        for key, value in event_dict.items()
        if key not in _CONSOLE_RESERVED_KEYS and value not in (None, "")
    ]
    return " ".join([event, *details]).strip()


def configure_logging(*, cli_name: str, version: str, level: str | None = None) -> None:
    """Configure structlog process-wide. Call once, in the root command."""
    global _LEVEL
    _LEVEL = _resolve_level(level)
    use_json = not sys.stderr.isatty()

    processors: list = [structlog.contextvars.merge_contextvars]
    if use_json:
        processors.extend(
            [
                structlog.processors.add_log_level,
                structlog.processors.TimeStamper(fmt="iso", utc=True),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.JSONRenderer(),
            ]
        )
    else:
        processors.extend(
            [
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                _console_message_renderer,
            ]
        )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(_LEVEL),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(cli=cli_name, version=version)


def is_debug() -> bool:
    """True if the active log level is DEBUG or lower (i.e. -v was given)."""
    return _LEVEL <= logging.DEBUG


def get_logger(*args, **kwargs):
    """Return a bound structlog logger. Thin pass-through for a single import site."""
    return structlog.get_logger(*args, **kwargs)
