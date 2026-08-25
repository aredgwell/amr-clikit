"""Error type for expected, user-facing CLI failures."""

from __future__ import annotations


class CliError(Exception):
    """A failure to report to the user, not a bug.

    Raise this for expected problems (bad input, missing file, failed
    precondition). `run_cli` turns it into a concise stderr message and the
    given exit code — no traceback — and so does the group `build_app` uses, so
    a test driving the app gets the same exit code the installed binary gives.
    Let any other exception propagate; those are treated as unexpected.

    **The exit-code convention.** `2` means *you called this wrong* — an
    argument that does not parse, a name that does not exist, a flag that is not
    valid here. `1` means *it ran, and found a problem* — the check failed, the
    file was malformed, the precondition did not hold. The distinction is worth
    keeping because it is the one a caller deciding whether to retry actually
    needs: a `2` will fail identically however many times it is repeated, and a
    `1` may not.

    The default is `1`, so the caller-error case is the one to say out loud.
    `CliError.usage(...)` is that case::

        raise CliError.usage(f"unknown check {name!r}; expected one of {options}")
        raise CliError("3 of 9 documents are stale")            # exit 1
    """

    def __init__(self, message: str, *, exit_code: int = 1) -> None:
        super().__init__(message)
        self.message = message
        self.exit_code = exit_code

    @classmethod
    def usage(cls, message: str) -> CliError:
        """A `CliError` for a caller error: exit 2, by the convention above."""
        return cls(message, exit_code=2)
