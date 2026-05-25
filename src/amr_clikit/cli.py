"""Typer glue: a pre-wired app builder and shared options.

Optional — requires the ``typer`` extra (``pip install amr-clikit[typer]``).
Keeps the core (logging / emit / run / errors) free of any CLI-framework
dependency.
"""

from __future__ import annotations

from typing import Any

import typer

from amr_clikit.log import configure_logging, level_for_verbosity

#: Reusable `--output text|json` option. Annotate the parameter with
#: `amr_clikit.OutputFormat`: `def cmd(output: OutputFormat = OUTPUT_OPTION)`.
OUTPUT_OPTION = typer.Option("text", "--output", help="Output format: text or json.")

#: Reusable `--yes/-y` option to skip confirmation prompts; pass to `confirm`.
YES_OPTION = typer.Option(False, "--yes", "-y", help="Skip confirmation prompts.")


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
        quiet: bool = typer.Option(False, "--quiet", help="Suppress info logs."),
        _version: bool = typer.Option(
            False, "--version", callback=_show_version, is_eager=True, help="Show version and exit."
        ),
    ) -> None:
        configure_logging(
            cli_name=cli_name, version=version, level=level_for_verbosity(verbose, quiet)
        )

    return app
