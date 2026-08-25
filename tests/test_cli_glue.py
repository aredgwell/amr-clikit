"""Tests for the Typer glue (amr_clikit.cli): build_app and shared options."""

from __future__ import annotations

from typing import Any

import typer
from typer.testing import CliRunner

from amr_clikit import CliError, OutputFormat, emit
from amr_clikit.cli import OUTPUT_OPTION, AliasGroup, build_app

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
    app = build_app(cli_name="demo", version="1.2.3", version_command=False)

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

    app = build_app(cli_name="demo", version="0", version_command=False, cls=RootGroup)

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
    app = build_app(cli_name="demo", version="0", version_command=False)

    @app.command("list | ls")
    def list_items() -> None: ...

    group: Any = typer.main.get_command(app)
    group.make_context("demo", [], resilient_parsing=True)  # after any canonicalisation
    assert list(group.commands) == ["list | ls"]
