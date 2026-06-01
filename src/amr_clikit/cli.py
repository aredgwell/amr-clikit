"""Typer glue: a pre-wired app builder and shared options.

Optional — requires the ``typer`` extra (``pip install amr-clikit[typer]``).
Keeps the core (logging / emit / run / errors) free of any CLI-framework
dependency.
"""

from __future__ import annotations

import re
from typing import Any

import click
import typer
from typer.core import TyperGroup

from amr_clikit.log import configure_logging, level_for_verbosity

#: Reusable `--output text|json` option. Annotate the parameter with
#: `amr_clikit.OutputFormat`: `def cmd(output: OutputFormat = OUTPUT_OPTION)`.
OUTPUT_OPTION = typer.Option("text", "--output", help="Output format: text or json.")

#: Reusable `--yes/-y` option to skip confirmation prompts; pass to `confirm`.
YES_OPTION = typer.Option(False, "--yes", "-y", help="Skip confirmation prompts.")

_ALIAS_SPLIT = re.compile(r"\s*[,|]\s*")
_DEFAULT_CONTEXT_SETTINGS = {"max_content_width": 100}


class AliasGroup(TyperGroup):
    """Typer command group that resolves aliases declared in a command's name.

    Name a command (or mounted sub-app) with `|`- or `,`-separated aliases and
    any of them resolves; the canonical name and its aliases show together in
    help::

        @app.command("list | ls")
        def list_items() -> None: ...

        app.add_typer(plugin, name="learn | l")  # `amr l` -> `amr learn`

    `build_app` uses this group by default, so any CLI built on amr-clikit gets
    aliases with no extra wiring. A command without a separator behaves exactly
    as before (non-breaking).
    """

    def get_command(self, ctx: click.Context, cmd_name: str) -> click.Command | None:
        return super().get_command(ctx, self._canonical(cmd_name))

    def _canonical(self, name: str) -> str:
        for registered in self.commands:
            if name in _ALIAS_SPLIT.split(registered):
                return registered
        return name


def build_app(*, cli_name: str, version: str, **kwargs: Any) -> typer.Typer:
    """Create a Typer app with the standard root options pre-wired.

    Adds `-v/--verbose`, `--quiet`, and `--version`, and configures logging once
    per invocation. Add commands to the returned app and expose it via
    `run_cli`::

        app = build_app(cli_name="mycli", version=__version__)

        @app.command()
        def hello() -> None: ...

        def run() -> None:
            run_cli(app)
    """
    kwargs.setdefault("no_args_is_help", True)
    kwargs.setdefault("cls", AliasGroup)
    kwargs.setdefault("context_settings", _DEFAULT_CONTEXT_SETTINGS)
    app = typer.Typer(**kwargs)

    def _show_version(value: bool) -> None:
        if value:
            typer.echo(version)
            raise typer.Exit()

    @app.callback()
    def _root(
        verbose: int = typer.Option(
            0, "-v", "--verbose", count=True, help="Increase log verbosity; repeat for debug."
        ),
        quiet: bool = typer.Option(False, "--quiet", help="Suppress warning and info logs."),
        _version: bool = typer.Option(
            False, "--version", callback=_show_version, is_eager=True, help="Show version and exit."
        ),
    ) -> None:
        configure_logging(
            cli_name=cli_name, version=version, level=level_for_verbosity(verbose, quiet)
        )

    @app.command("version")
    def version_cmd() -> None:
        """Show version and exit."""
        typer.echo(version)

    return app
