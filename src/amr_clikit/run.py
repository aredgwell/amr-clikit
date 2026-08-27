"""Run a CLI entry point with a consistent error/exit-code contract."""

from __future__ import annotations

import datetime
import json
import os
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from amr_clikit.errors import CliError
from amr_clikit.log import get_logger, is_debug


def _write_journal(record: dict[str, Any]) -> None:
    """Passively record run metadata to local journal (~/.amr/runs.jsonl).

    Fails silently so telemetry can never break or impede command execution.
    """
    if os.environ.get("AMR_NO_JOURNAL") == "1" or "PYTEST_CURRENT_TEST" in os.environ:
        return
    try:
        journal_dir = Path.home() / ".amr"
        journal_dir.mkdir(parents=True, exist_ok=True)
        journal_file = journal_dir / "runs.jsonl"
        with journal_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception:
        pass


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
    start_time = time.monotonic()
    iso_timestamp = datetime.datetime.now(datetime.UTC).isoformat()
    cli_name = Path(sys.argv[0]).stem if sys.argv else "amr"
    exit_code = 0

    try:
        entry()
    except CliError as exc:
        exit_code = exc.exit_code
        log.error(exc.message, exit_code=exc.exit_code)
        raise SystemExit(exc.exit_code) from None
    except KeyboardInterrupt:
        exit_code = 130
        raise SystemExit(130) from None
    except SystemExit as exc:
        exit_code = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        raise
    except Exception as exc:  # noqa: BLE001 — the top-level boundary for the CLI
        exit_code = 1
        if is_debug():
            log.error("unexpected error", exc_info=exc)
        else:
            log.error("unexpected error", error=str(exc), hint="re-run with -vv for a traceback")
        raise SystemExit(1) from None
    finally:
        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        record = {
            "ts": iso_timestamp,
            "cli": cli_name,
            "args": sys.argv[1:] if len(sys.argv) > 1 else [],
            "cwd": str(Path.cwd()),
            "duration_ms": duration_ms,
            "exit": exit_code,
        }
        _write_journal(record)
