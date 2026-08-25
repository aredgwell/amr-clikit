"""Run a CLI entry point with a consistent error/exit-code contract."""

from __future__ import annotations

from collections.abc import Callable

from amr_clikit.errors import CliError
from amr_clikit.log import get_logger, is_debug


def run_cli(entry: Callable[[], object]) -> None:
    """Invoke `entry` and map exceptions to exit codes consistently.

    - `CliError`        -> its message on stderr, its exit code (default 1).
    - `KeyboardInterrupt` -> exit 130, quietly.
    - `SystemExit`      -> propagated unchanged (the framework's own exit).
    - any other error   -> exit 1; a one-line message, with the traceback only
                           when logging is at DEBUG (i.e. `-vv` was given).

    Use as the console-script target, e.g. `def run() -> None: run_cli(app)`.
    """
    log = get_logger()
    try:
        entry()
    except CliError as exc:
        # `exit_code` on the record, not in the message: stderr is already JSON
        # when it is not a TTY, so a caller capturing it can read the failure
        # structurally rather than parsing prose. The console renderer reserves
        # the key, so a person sees the message alone.
        log.error(exc.message, exit_code=exc.exit_code)
        raise SystemExit(exc.exit_code) from None
    except KeyboardInterrupt:
        raise SystemExit(130) from None
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001 — the top-level boundary for the CLI
        if is_debug():
            log.error("unexpected error", exc_info=exc)
        else:
            log.error("unexpected error", error=str(exc), hint="re-run with -vv for a traceback")
        raise SystemExit(1) from None
