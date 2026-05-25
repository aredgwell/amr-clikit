"""Error type for expected, user-facing CLI failures."""

from __future__ import annotations


class CliError(Exception):
    """A failure to report to the user, not a bug.

    Raise this for expected problems (bad input, missing file, failed
    precondition). `run_cli` turns it into a concise stderr message and the
    given exit code — no traceback. Let any other exception propagate; `run_cli`
    treats those as unexpected.
    """

    def __init__(self, message: str, *, exit_code: int = 1) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code
