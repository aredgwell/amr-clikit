"""Command-result output for CLIs.

The other half of the stderr/stdout discipline: *results* — the data a command
produces — go to **stdout** so they can be piped (`mycli list | jq`), while logs
go to stderr via `amr_clikit.log` (`get_logger`).

`emit` is the seed of the output convention; richer text rendering (tables, etc.)
can be added as needed.
"""

from __future__ import annotations

import json
import sys
from typing import Any, Literal, TextIO

OutputFormat = Literal["text", "json"]


def emit(data: Any, *, output: OutputFormat = "text", file: TextIO | None = None) -> None:
    """Write a command result to stdout.

    output="json": compact, deterministic JSON (sorted keys) plus a newline.
    output="text": str(data), or one line per item for lists/tuples.
    """
    stream = file or sys.stdout
    if output == "json":
        json.dump(data, stream, sort_keys=True, default=str)
        stream.write("\n")
        return
    if isinstance(data, (list, tuple)):
        for item in data:
            print(item, file=stream)
    else:
        print(data, file=stream)
