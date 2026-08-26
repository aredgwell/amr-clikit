"""Tests for the Typer glue (amr_clikit.cli): build_app and shared options."""

from __future__ import annotations

import json
from typing import Any

import pytest
import typer
from typer.testing import CliRunner

from amr_clikit import CliError, OutputFormat, emit, get_logger
from amr_clikit.cli import OUTPUT_OPTION, AliasGroup, build_app, command_tree
from amr_clikit.testing import assert_agent_ready

runner = CliRunner()


def _make_app() -> typer.Typer:
    app = build_app(cli_name="demo", version="1.2.3")

    @app.command()
    def items(output: OutputFormat = OUTPUT_OPTION) -> None:
        emit([{"a": 1}], output=output)

    return app


def test_version_flag_prints_version() -> None:
    result = runner.invoke(_make_app(), ["--version"])
    assert result.exit_code == 0
    assert "1.2.3" in result.stdout


def test_version_command_prints_version() -> None:
    result = runner.invoke(_make_app(), ["version"])
    assert result.exit_code == 0
    assert "1.2.3" in result.stdout


def test_command_honours_output_option() -> None:
    result = runner.invoke(_make_app(), ["items", "--output", "json"])
    assert result.exit_code == 0
    assert '"a": 1' in result.stdout


def test_command_honours_agent_output_option() -> None:
    result = runner.invoke(_make_app(), ["items", "--output", "agent"])
    assert result.exit_code == 0
    assert result.stdout == '[{"a":1}]\n'


def test_command_alias_resolves() -> None:
    app = build_app(cli_name="demo", version="0")

    @app.command("list | ls")
    def list_items() -> None:
        emit(["x"], output="text")

    canonical = runner.invoke(app, ["list"])
    alias = runner.invoke(app, ["ls"])
    assert canonical.exit_code == 0
    assert alias.exit_code == 0
    assert alias.stdout == canonical.stdout == "x\n"


def test_unknown_command_still_errors() -> None:
    app = build_app(cli_name="demo", version="0")

    @app.command("list | ls")
    def list_items() -> None:
        emit(["x"], output="text")

    result = runner.invoke(app, ["nope"])
    assert result.exit_code != 0


def _completions(app: typer.Typer, incomplete: str) -> list[str]:
    """Drive the group's completion the way a shell does, via `shell_complete`."""
    group = typer.main.get_command(app)
    ctx = group.make_context("demo", [], resilient_parsing=True)
    return [item.value for item in group.shell_complete(ctx, incomplete)]


def _alias_app() -> typer.Typer:
    app = build_app(cli_name="demo", version="0")

    @app.command("list | ls")
    def list_items() -> None:
        """List the items."""

    sub = typer.Typer()

    @sub.command("run")
    def sub_run() -> None: ...

    app.add_typer(sub, name="harness | h")
    return app


def test_completion_offers_each_alias_separately() -> None:
    """The registered name `list | ls` is not a command; both spellings are."""
    assert _completions(_alias_app(), "l") == ["list", "ls"]


def test_completion_matches_an_alias_prefix() -> None:
    assert _completions(_alias_app(), "ls") == ["ls"]


def test_completion_expands_a_mounted_sub_app_name() -> None:
    assert _completions(_alias_app(), "h") == ["harness", "h"]


def test_completion_still_offers_options() -> None:
    assert _completions(_alias_app(), "--qu") == ["--quiet"]


def test_completion_offers_nothing_for_an_unknown_prefix() -> None:
    assert _completions(_alias_app(), "nope") == []


def test_clierror_exit_code_survives_clirunner() -> None:
    """`run_cli` is the console-script path; a test drives the app directly."""
    app = build_app(cli_name="demo", version="0")

    @app.command()
    def boom() -> None:
        raise CliError("nope", exit_code=3)

    result = runner.invoke(app, ["boom"])
    assert result.exit_code == 3


def test_version_command_can_be_suppressed() -> None:
    """`--version` stays; the subcommand goes, for trees that get enumerated."""
    app = build_app(cli_name="demo", version="1.2.3", version_command=False, commands_command=False)

    @app.command()
    def items() -> None: ...

    assert _completions(app, "") == ["items"]
    assert runner.invoke(app, ["version"]).exit_code != 0
    assert "1.2.3" in runner.invoke(app, ["--version"]).stdout


def test_completion_does_not_duplicate_a_subclass_extra_command() -> None:
    """A group may list more commands than it registers — each is offered once.

    `amr`'s root group appends declared sibling binaries to `list_commands`, so
    filtering the base class's own candidates against `self.commands` would
    have let those through a second time.
    """

    class RootGroup(AliasGroup):
        def list_commands(self, ctx: Any) -> list[str]:
            return [*super().list_commands(ctx), "publish"]

        def get_command(self, ctx: Any, cmd_name: str) -> Any:
            if cmd_name == "publish":
                return typer.main.get_command(build_app(cli_name="p", version="0"))
            return super().get_command(ctx, cmd_name)

    app = build_app(
        cli_name="demo", version="0", version_command=False, commands_command=False, cls=RootGroup
    )

    @app.command("list | ls")
    def list_items() -> None: ...

    assert _completions(app, "") == ["list", "ls", "publish"]
    assert _completions(app, "pub") == ["publish"]


def test_help_names_a_command_that_can_be_typed() -> None:
    """Typer registers `"list | ls"` as the name; help must not print it back."""
    app = build_app(cli_name="demo", version="0", version_command=False)

    @app.command("list | ls")
    def list_items() -> None:
        """List the items."""

    stdout = runner.invoke(app, ["--help"]).stdout
    assert "list | ls" not in stdout
    assert "list" in stdout


def test_typo_suggests_a_command_that_can_be_typed() -> None:
    """`Did you mean 'workspace | ws'?` is worse than no suggestion at all."""
    app = build_app(cli_name="demo", version="0", version_command=False)

    @app.command("workspace | ws")
    def workspace() -> None:
        """Do workspace things."""

    result = runner.invoke(app, ["wrokspace"])
    assert result.exit_code != 0
    assert "workspace | ws" not in result.output
    assert "Did you mean 'workspace'?" in result.output


def test_a_mounted_sub_app_is_also_named_canonically() -> None:
    app = build_app(cli_name="demo", version="0", version_command=False)
    sub = typer.Typer()

    @sub.command("run")
    def sub_run() -> None: ...

    app.add_typer(sub, name="harness | h")
    stdout = runner.invoke(app, ["--help"]).stdout
    assert "harness | h" not in stdout
    assert runner.invoke(app, ["h", "run"]).exit_code == 0


def test_registration_keys_still_carry_the_aliases() -> None:
    """Consumers read the declared spellings off `commands`; resolution must not move them."""
    app = build_app(cli_name="demo", version="0", version_command=False, commands_command=False)

    @app.command("list | ls")
    def list_items() -> None: ...

    group: Any = typer.main.get_command(app)
    group.make_context("demo", [], resilient_parsing=True)  # after any canonicalisation
    assert list(group.commands) == ["list | ls"]


def test_command_tree_reports_what_to_type_and_the_aliases_separately() -> None:
    """No row ever puts a string like `list | ls` where a caller might type it."""
    app = build_app(cli_name="demo", version="1.0", commands_command=False)

    @app.command("list | ls")
    def list_items() -> None:
        """List the items."""

    rows = command_tree(app)
    listing = next(row for row in rows if row["command"] == "list")
    assert listing["aliases"] == ["ls"]
    assert listing["help"] == "List the items."
    assert not any("|" in str(row["command"]) for row in rows)


def test_command_tree_flattens_a_sub_app_and_crosses_its_spellings() -> None:
    """A row's `command` is a complete invocation, not a path to reassemble."""
    app = build_app(cli_name="demo", version="1.0", version_command=False, commands_command=False)
    sub = typer.Typer()

    @sub.command("show | s")
    def show() -> None:
        """Show one."""

    app.add_typer(sub, name="workspace | ws")

    (row,) = command_tree(app)
    assert row["command"] == "workspace show"
    # Every combination that resolves, not one per level.
    aliases: list[str] = row["aliases"]  # type: ignore[assignment]
    assert sorted(aliases) == ["workspace s", "ws s", "ws show"]


def test_command_tree_includes_version() -> None:
    """A real command. A consumer wanting an affordance list can drop it."""
    app = build_app(cli_name="demo", version="1.0", commands_command=False)
    assert [row["command"] for row in command_tree(app)] == ["version"]


def test_commands_command_emits_json() -> None:
    app = build_app(cli_name="demo", version="1.0", version_command=False)

    @app.command("list | ls")
    def list_items() -> None:
        """List the items."""

    result = runner.invoke(app, ["commands", "--output", "json"])
    assert result.exit_code == 0
    rows = json.loads(result.stdout)
    assert {row["command"] for row in rows} == {"commands", "list"}


def test_commands_command_can_be_suppressed() -> None:
    app = build_app(cli_name="demo", version="1.0", commands_command=False)
    assert runner.invoke(app, ["commands"]).exit_code != 0


def test_clierror_puts_its_exit_code_on_the_record() -> None:
    """Captured stderr is JSON, so a caller reads the failure structurally."""
    app = build_app(cli_name="demo", version="0")

    @app.command()
    def boom() -> None:
        raise CliError.usage("called wrong")

    result = runner.invoke(app, ["boom"])
    assert result.exit_code == 2
    record = json.loads(result.stderr.strip().splitlines()[-1])
    assert record["event"] == "called wrong"
    assert record["exit_code"] == 2


def test_a_mounted_sub_app_resolves_its_own_aliases_without_wiring() -> None:
    """`add_typer(sub, ...)` builds `sub`'s group from `sub`'s class, not ours."""
    app = build_app(cli_name="demo", version="0")
    sub = typer.Typer()  # deliberately not cls=AliasGroup

    @sub.command("show | s")
    def show() -> None:
        emit(["shown"], output="text")

    app.add_typer(sub, name="workspace | ws")

    for argv in (["workspace", "show"], ["workspace", "s"], ["ws", "show"], ["ws", "s"]):
        result = runner.invoke(app, argv)
        assert result.exit_code == 0, argv
        assert result.stdout == "shown\n", argv


def test_assert_agent_ready_passes_a_well_formed_app() -> None:
    app = build_app(cli_name="demo", version="1.0")

    @app.command("list | ls")
    def list_items(output: OutputFormat = OUTPUT_OPTION) -> None:
        """List the items."""
        emit([{"a": 1}], output=output)

    assert_agent_ready(app)


def test_assert_agent_ready_catches_a_command_that_writes_no_result() -> None:
    """The defect it exists for: output routed to the logger, suite still green."""
    app = build_app(cli_name="demo", version="1.0")

    @app.command()
    def quiet(output: OutputFormat = OUTPUT_OPTION) -> None:
        """Report something, on the wrong channel."""
        get_logger().error("the result, on the diagnostics channel")

    with pytest.raises(AssertionError, match="wrote nothing to stdout"):
        assert_agent_ready(app)


def test_assert_agent_ready_honours_skip() -> None:
    app = build_app(cli_name="demo", version="1.0")

    @app.command()
    def quiet(output: OutputFormat = OUTPUT_OPTION) -> None:
        """Report something, on the wrong channel."""
        get_logger().error("nothing on stdout")

    assert_agent_ready(app, skip={"quiet"})
