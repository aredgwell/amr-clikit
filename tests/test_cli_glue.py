"""Tests for the Typer glue (amr_clikit.cli): build_app and shared options."""

from __future__ import annotations

import typer
from typer.testing import CliRunner

from amr_clikit import OutputFormat, emit
from amr_clikit.cli import OUTPUT_OPTION, build_app

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
