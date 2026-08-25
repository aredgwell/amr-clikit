"""Typer glue: a pre-wired app builder and shared options.

Optional — requires the ``typer`` extra (``pip install amr-clikit[typer]``).
Keeps the core (logging / emit / run / errors) free of any CLI-framework
dependency.
"""

from __future__ import annotations

import re
from typing import Any

import typer
from typer.core import TyperGroup

from amr_clikit.errors import CliError
from amr_clikit.log import configure_logging, get_logger, level_for_verbosity

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

    The group also maps `CliError` to its exit code, so a command reached
    through `typer.testing.CliRunner` exits the same way it does through
    `run_cli` — see `invoke`.
    """

    def get_command(self, ctx: Any, cmd_name: str) -> Any:
        return super().get_command(ctx, self._canonical(cmd_name))

    def invoke(self, ctx: Any) -> Any:
        """Invoke the chosen command, mapping `CliError` to its exit code.

        `run_cli` does the same, but it is the console-script entry point, so
        the mapping only happened when the command was reached through the
        installed binary. A test driving the app with `typer.testing.CliRunner`
        bypassed it and saw a bare exit 1 with the exception attached — making
        the exit code, the part of a CLI's contract most worth pinning, the one
        part a test could not assert.

        Doing it here puts the mapping on the app itself, so both paths agree.
        `run_cli` stays the outer boundary for anything that escapes: an
        unexpected exception, or a `CliError` raised outside a command.
        """
        try:
            return super().invoke(ctx)
        except CliError as exc:
            get_logger().error(exc.message)
            raise SystemExit(exc.exit_code) from None

    def shell_complete(self, ctx: Any, incomplete: str) -> list[Any]:
        """Offer each alias as its own completion candidate.

        Completion does not go through `get_command`. Click enumerates the
        *registered* names, so a command declared `"list | ls"` arrives as a
        single candidate spelled `list | ls`, and accepting it inserts a string
        that is not a command.

        Asking the base class for the empty prefix yields one correctly-typed
        item per visible command; each is then split into its aliases and
        filtered by what the user has actually typed. Help and resolution are
        untouched — only this method is narrowed.
        """
        candidates = [
            type(item)(alias, type=item.type, help=item.help)
            for item in super().shell_complete(ctx, "")
            for alias in _ALIAS_SPLIT.split(item.value)
            if alias.startswith(incomplete)
        ]
        # Options and anything else the base class offers for this prefix.
        # Everything the group *lists* is already covered above, under every
        # spelling — `list_commands` rather than `self.commands`, because a
        # subclass may list more than it registers (a root group dispatching to
        # sibling binaries, say).
        listed = set(self.list_commands(ctx))
        candidates.extend(
            item for item in super().shell_complete(ctx, incomplete) if item.value not in listed
        )
        return candidates

    def _canonical(self, name: str) -> str:
        for registered in self.commands:
            if name in _ALIAS_SPLIT.split(registered):
                return registered
        return name


def build_app(
    *, cli_name: str, version: str, version_command: bool = True, **kwargs: Any
) -> typer.Typer:
    """Create a Typer app with the standard root options pre-wired.

    Adds `-v/--verbose`, `--quiet`, and `--version`, and configures logging once
    per invocation. Add commands to the returned app and expose it via
    `run_cli`::

        app = build_app(cli_name="mycli", version=__version__)

        @app.command()
        def hello() -> None: ...

        def run() -> None:
            run_cli(app)

    `version_command=False` omits the `version` subcommand, keeping `--version`.
    Pass it when something enumerates the command tree and would otherwise have
    to know to skip a command that is not part of the CLI's own surface.
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

    if version_command:

        @app.command("version")
        def version_cmd() -> None:
            """Show version and exit."""
            typer.echo(version)

    return app
