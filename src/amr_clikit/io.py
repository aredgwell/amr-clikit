"""Command-result output and interactive prompts for CLIs.

The other half of the stderr/stdout discipline: *results* — the data a command
produces — go to **stdout** so they can be piped (`mycli list | jq`), while logs
go to stderr via `amr_clikit.log` (`get_logger`). Interactive prompts
(`confirm`) read stdin and write to stderr, keeping stdout clean.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from typing import Any, Literal, TextIO

OutputFormat = Literal["text", "json", "agent"]


def emit(data: Any, *, output: OutputFormat = "text", file: TextIO | None = None) -> None:
    """Write a command result to stdout.

    output="agent": ultra-compact, whitespace-minimized deterministic JSON for LLM tool calls.
    output="json": compact, deterministic JSON (sorted keys) plus a newline.
    output="text": a human rendering —
      - a list of dicts becomes an aligned table (header + rows);
      - any other list/tuple becomes one item per line;
      - a dict becomes `key: value` lines;
      - anything else is str()'d.

    Table cells are single-line by contract. A value containing a newline is
    not a cell: the second line starts at column zero and every column after it
    is meaningless. Data that is multi-line by nature — captured tool output,
    one line per package — wants its own sectioned rendering, not this table.
    No column is padded past its last character, so rows carry no trailing
    whitespace and copy cleanly.
    """
    stream = file or sys.stdout
    if output == "agent":
        json.dump(data, stream, sort_keys=True, separators=(",", ":"), default=str)
        stream.write("\n")
        return
    if output == "json":
        json.dump(data, stream, sort_keys=True, default=str)
        stream.write("\n")
        return

    if isinstance(data, Sequence) and not isinstance(data, str | bytes):
        rows = list(data)
        if rows and all(isinstance(row, dict) for row in rows):
            print(_as_table(rows), file=stream)
        else:
            for item in rows:
                print(item, file=stream)
    elif isinstance(data, dict):
        for key, value in data.items():
            print(f"{key}: {_cell(value)}", file=stream)
    else:
        print(data, file=stream)


def confirm(prompt: str, *, assume_yes: bool = False) -> bool:
    """Ask the user to confirm an action.

    Returns True if `assume_yes` (e.g. a `--yes` flag) is set. Otherwise prompts
    on stderr and reads stdin; in a non-interactive context (no TTY) returns
    False rather than blocking, so destructive commands stay safe in scripts/CI.
    """
    if assume_yes:
        return True
    if not sys.stdin.isatty():
        return False
    print(f"{prompt} [y/N] ", end="", file=sys.stderr, flush=True)
    answer = sys.stdin.readline().strip().lower()
    return answer in {"y", "yes"}


def _cell(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple)):
        return ", ".join(str(item) for item in value)
    return str(value)


def _as_table(rows: list[dict]) -> str:
    headers: list[str] = []
    for row in rows:
        for key in row:
            if key not in headers:
                headers.append(key)
    if not headers:
        return ""
    rendered = [{h: _cell(row.get(h)) for h in headers} for row in rows]
    widths = {h: max(len(h), *(len(r[h]) for r in rendered)) for h in headers}
    last = headers[-1]

    def _row(cells: dict[str, str]) -> str:
        # The final column is not padded: padding it puts trailing whitespace on
        # every header and every short last cell, which breaks copy-paste and
        # shows up in diffs.
        return "  ".join(cells[h] if h == last else cells[h].ljust(widths[h]) for h in headers)

    return "\n".join(
        [
            _row({h: h for h in headers}),
            _row({h: "-" * widths[h] for h in headers}),
            *(_row(r) for r in rendered),
        ]
    )
