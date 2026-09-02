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

**structlog is imported on first use, not on import of this module.** It costs
62 ms to import — measured 2026-09-03 against a 26 ms bare interpreter and a
33 ms typer/click — and it is imported by every `amr-*` command whether or not
that command logs anything. At the default WARNING level most do not: a routine
`amr verify` or `amr-publish document build` emits nothing on the happy path.
So `configure_logging` records the decision in stdlib state and `get_logger`
applies it, which means a command that never logs never pays.

The contract that changes with it, stated because it is a contract: structlog
is process-wide configured at the first `get_logger()` rather than at the
`configure_logging()` call. Anything reaching for `structlog.get_logger()`
directly, ahead of this module, now gets structlog's defaults where it used to
get this configuration. Nothing in the estate does — structlog appears in one
file, this one — and `get_logger()` is the documented way in.
"""

from __future__ import annotations

import logging
import os
import sys
import threading
from typing import TYPE_CHECKING, Any, cast

if TYPE_CHECKING:
    import structlog

_VERBOSITY_LEVELS = ["WARNING", "INFO", "DEBUG"]
# `exit_code` is reserved rather than rendered: a structured reader wants it on
# the record, and a person reading the terminal already gets it from the shell.
_CONSOLE_RESERVED_KEYS = {"event", "level", "timestamp", "cli", "version", "exit_code"}

# One stream, so one lock: keeps a message and its newline together when a CLI
# logs from more than one thread.
_WRITE_LOCK = threading.Lock()

# Resolved level of the most recent configure_logging() call; used by run_cli to
# decide whether to surface a traceback for unexpected errors.
_LEVEL = logging.WARNING

# What the most recent `configure_logging()` decided, held until something
# actually logs. `None` means nothing has configured logging yet, in which case
# `get_logger()` still works and structlog's own defaults apply — the same as
# calling `get_logger()` before `configure_logging()` always did.
_PENDING: dict[str, Any] | None = None
_APPLIED = False


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


class _StderrLogger:
    """A structlog logger that resolves ``sys.stderr`` at write time.

    ``structlog.PrintLoggerFactory(file=sys.stderr)`` captures the stream when
    logging is *configured*, so a module-level ``log = get_logger()`` — the
    documented idiom — keeps writing to whatever stderr was then, even after
    logging is reconfigured. That is invisible in a one-command process and
    immediately visible wherever stderr is replaced per invocation, such as
    ``typer.testing.CliRunner``: the second invocation writes to the first
    one's stream, which the runner has closed.

    Resolving per write is what a caller means by "stderr". Together with
    ``cache_logger_on_first_use=False`` it measures at roughly 5 us per log
    line, which for a CLI that emits tens of them is not a cost.
    """

    def msg(self, message: str) -> None:
        with _WRITE_LOCK:
            print(message, file=sys.stderr, flush=True)

    log = debug = info = warn = warning = msg
    fatal = failure = err = error = critical = exception = msg


def _stderr_logger_factory(*_args: Any) -> _StderrLogger:
    """structlog ``logger_factory`` producing late-binding stderr loggers."""
    return _StderrLogger()


def _console_message_renderer(_, __, event_dict: dict) -> str:
    """Render human stderr as a short message, not a structured log record."""
    event = str(event_dict.get("event", ""))
    details = [
        f"{key}={value}"
        for key, value in event_dict.items()
        if key not in _CONSOLE_RESERVED_KEYS and key != "exception" and value not in (None, "")
    ]
    message = " ".join([event, *details]).strip()
    exc = event_dict.get("exception")
    if exc:
        return f"{message}\n{exc}" if message else str(exc)
    return message


def configure_logging(*, cli_name: str, version: str, level: str | None = None) -> None:
    """Decide how this process will log. Call once, in the root command.

    Applied at the first `get_logger()` rather than here, so a command that
    emits nothing does not import structlog. Everything resolved eagerly is
    resolved with the stdlib: the level, and whether stderr is a terminal.
    `sys.stderr.isatty()` in particular is read *now* rather than at first log,
    because the caller's stderr at root-callback time is what the renderer
    choice has always been made against.
    """
    global _LEVEL, _PENDING, _APPLIED
    _LEVEL = _resolve_level(level)
    _PENDING = {
        "cli_name": cli_name,
        "version": version,
        "level": _LEVEL,
        "use_json": not sys.stderr.isatty(),
    }
    _APPLIED = False
    # Deferral saves an *import*, so once structlog is imported there is nothing
    # left to save and every reason not to wait: a caller holding a logger from
    # a module-level `log = get_logger()` never calls `get_logger()` again, and
    # would go on logging at the level this call just replaced. That idiom is
    # documented above and `cache_logger_on_first_use=False` exists to serve it.
    if "structlog" in sys.modules:
        _apply()


def _apply() -> None:
    """Configure structlog from the pending decision, at most once per decision."""
    global _APPLIED
    if _APPLIED or _PENDING is None:
        return
    _APPLIED = True

    import structlog

    cli_name = _PENDING["cli_name"]
    version = _PENDING["version"]
    level = _PENDING["level"]
    use_json = _PENDING["use_json"]

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
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=_stderr_logger_factory,
        cache_logger_on_first_use=False,
    )
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(cli=cli_name, version=version)


def is_debug() -> bool:
    """True if the active log level is DEBUG or lower (i.e. -vv was given)."""
    return _LEVEL <= logging.DEBUG


class _LazyLogger:
    """Stands in for a structlog logger until something is actually logged.

    `log = get_logger()` at module scope is the documented idiom, and eight
    modules in `amr` alone use it. Returning a real logger there would import
    structlog at *their* import and hand back the whole 62 ms this module
    defers, so what comes back is this: an object that resolves the real logger
    on the first attribute reached for, and not before.

    It resolves on **every** access rather than caching one, which is the same
    choice `_StderrLogger` makes about `sys.stderr` and for the same reason: a
    logger obtained at import time must follow a later `configure_logging`,
    not freeze the level and stream that were current when the module loaded.
    `structlog.get_logger()` is a dictionary lookup and a bind, and this module
    already accepts ~5 us per line for the same property.
    """

    __slots__ = ("_args", "_kwargs")

    def __init__(self, args: tuple[Any, ...], kwargs: dict[str, Any]) -> None:
        self._args = args
        self._kwargs = kwargs

    def __getattr__(self, name: str) -> Any:
        _apply()

        import structlog

        return getattr(structlog.get_logger(*self._args, **self._kwargs), name)


def get_logger(*args: Any, **kwargs: Any) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger, deferring the import until it is used.

    The return is a `_LazyLogger` standing in for the real one. It forwards
    every attribute, so it is a `BoundLogger` in every way a caller can observe
    — the annotation says what a caller may rely on, and `cast` is the only way
    to say that about a proxy.
    """
    return cast("structlog.stdlib.BoundLogger", _LazyLogger(args, kwargs))
