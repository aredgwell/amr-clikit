"""One importable assertion a CLI runs against itself.

`assert_agent_ready(app)` checks the properties that make a command tree usable
by something that is not a person. Each one corresponds to a defect that shipped
in a real CLI built on this toolkit and was found by hand rather than by a test:

- three read-only commands went **silent** after their output was routed to the
  logger — the suite stayed green throughout, because nothing asserted that a
  read-only command writes to stdout at all;
- a command declared ``"list | ls"`` was reported back as ``list | ls`` in help
  and in the "did you mean" on a typo, which is a string that is not a command.

Needs the ``typer`` extra, and `typer.testing.CliRunner`. Call it from your own
suite::

    from amr_clikit.testing import assert_agent_ready
    from mycli.cli import app

    def test_the_cli_is_legible_to_an_agent() -> None:
        assert_agent_ready(app)
"""

from __future__ import annotations

import json
from typing import Any
from unittest import mock

import typer
from typer.testing import CliRunner

from amr_clikit.cli import OUTPUT_OPTION, command_tree

__all__ = ["assert_agent_ready"]


def assert_agent_ready(app: typer.Typer, *, skip: set[str] | None = None) -> None:
    """Assert that `app`'s command surface can be read and driven by an agent.

    Checks, in order:

    1. every command's `--help` exits 0 — a command whose help does not render
       is one nobody can discover;
    2. every alias `command_tree` reports actually resolves — the aliases are
       published as usable spellings, so an unusable one is a lie;
    3. every command taking `--output` produces parseable JSON under
       `--output json`;
    4. no command taking `--output` writes its result to stderr and leaves
       stdout empty — the results channel is the contract.

    Checks 3 and 4 only run a command if it needs no arguments, because running
    one that does would be a test of your CLI's behaviour rather than its shape.
    Pass `skip` for commands that must not be run at all — anything that
    mutates, costs money, or takes a long time.

    `os.execvp` is patched out for the duration. A CLI that dispatches to a
    sibling binary would otherwise **replace the test process** when its help is
    requested: one dot, no summary, exit 0, and a truncated run that looks
    exactly like a green one.
    """
    skipped = skip or set()
    runner = CliRunner()
    rows = [row for row in command_tree(app) if str(row["command"]) not in skipped]

    with mock.patch("os.execvp"):
        for row in rows:
            command = str(row["command"])
            _assert_help_renders(runner, app, command)
            for alias in row["aliases"]:  # type: ignore[union-attr]
                _assert_help_renders(runner, app, str(alias), because=f"alias of {command!r}")
            if _takes_output_option(app, command) and not _takes_arguments(app, command):
                _assert_json_and_stdout(runner, app, command)


def _assert_help_renders(
    runner: CliRunner, app: typer.Typer, command: str, because: str = ""
) -> None:
    result = runner.invoke(app, [*command.split(), "--help"])
    detail = f" ({because})" if because else ""
    assert result.exit_code == 0, (
        f"`{command} --help`{detail} exited {result.exit_code}, not 0:\n{result.output}"
    )


def _assert_json_and_stdout(runner: CliRunner, app: typer.Typer, command: str) -> None:
    result = runner.invoke(app, [*command.split(), "--output", "json"])
    if result.exit_code != 0:
        return  # it ran and reported a problem; that is the command's business
    assert result.stdout.strip(), (
        f"`{command} --output json` wrote nothing to stdout. A command that "
        f"produces a result must write it to the results channel."
    )
    try:
        json.loads(result.stdout)
    except json.JSONDecodeError as exc:  # pragma: no cover - message is the point
        raise AssertionError(
            f"`{command} --output json` did not produce parseable JSON: {exc}\n{result.stdout}"
        ) from None


def _resolve(app: typer.Typer, command: str) -> Any:
    node: Any = typer.main.get_command(app)
    ctx = node.make_context(app.info.name or "app", [], resilient_parsing=True)
    for part in command.split():
        node = node.get_command(ctx, part)
        if node is None:
            return None
    return node


def _takes_output_option(app: typer.Typer, command: str) -> bool:
    node = _resolve(app, command)
    names = {opt for param in getattr(node, "params", []) for opt in getattr(param, "opts", [])}
    return bool(names & set(OUTPUT_OPTION.param_decls or ["--output"]))


def _takes_arguments(app: typer.Typer, command: str) -> bool:
    node = _resolve(app, command)
    return any(getattr(param, "required", False) for param in getattr(node, "params", []))
