"""Typer glue: a pre-wired app builder and shared options.

Optional — requires the ``typer`` extra (``pip install amr-clikit[typer]``).
Keeps the core (logging / emit / run / errors) free of any CLI-framework
dependency.
"""

from __future__ import annotations

import itertools
import re
from typing import Any

import typer
from typer.core import TyperGroup

from amr_clikit.errors import CliError
from amr_clikit.io import OutputFormat, emit
from amr_clikit.log import configure_logging, get_logger, level_for_verbosity

#: Reusable `--output text|json` option. Annotate the parameter with
#: `amr_clikit.OutputFormat`: `def cmd(output: OutputFormat = OUTPUT_OPTION)`.
OUTPUT_OPTION = typer.Option("text", "--output", help="Output format: text or json.")

#: Reusable `--yes/-y` option to skip confirmation prompts; pass to `confirm`.
YES_OPTION = typer.Option(False, "--yes", "-y", help="Skip confirmation prompts.")

_ALIAS_SPLIT = re.compile(r"\s*[,|]\s*")
_DEFAULT_CONTEXT_SETTINGS = {"max_content_width": 100}

#: `get_short_help_str` truncates; a machine-readable row has no column to fit,
#: so the limit is high enough to be effectively no limit for a one-line summary.
_HELP_LIMIT = 400


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
        self._prepare()
        return super().get_command(ctx, self._canonical(cmd_name))

    def list_commands(self, ctx: Any) -> list[str]:
        """Report the canonical name of each command, never the declared string.

        Typer registers `@app.command("list | ls")` under the whole string, and
        that string is what click reports back wherever it names a command: the
        help table, the "did you mean" suggestion on a typo, the usage line. All
        of those are places a caller is being told what to type, and
        `Did you mean 'workspace | ws'?` is worse than no suggestion at all — an
        agent will type it verbatim and it will fail.

        Resolution is unaffected: `get_command` canonicalises, so either
        spelling still works, and completion still offers both.
        """
        self._prepare()
        return [self._canonical_spelling(name) for name in super().list_commands(ctx)]

    def _prepare(self) -> None:
        """Name each command canonically, and make sub-groups resolve aliases too.

        **Names.** `list_commands` alone is not enough: Typer's rich help
        renders `command.name`, not the name it was looked up by, so the
        declared string would still reach the table. The registration key is
        deliberately left as it is — it is where the aliases are declared, and a
        consumer reading the tree reads them from there.

        The trade-off, stated because it is a real one: the help table now shows
        `list` rather than `list | ls`, so a person reading `--help` no longer
        sees the alias. Appending it to the command's help would put alias text
        into the same attribute that any structured reader takes as the help
        string, which is the wrong place for it. Aliases stay discoverable
        through completion, which offers each spelling separately.

        **Sub-groups.** `add_typer(sub, name="workspace | ws")` builds `sub`'s
        group from `sub`'s own class, which is a plain `TyperGroup` unless the
        caller remembered `cls=AliasGroup`. So `workspace` resolved, `ws`
        resolved, and `workspace show` — declared `"show | s"` inside `sub` —
        did not: an alias that help advertised and nothing honoured. Every
        consumer worked around it by passing `cls=` on every sub-app it mounted.

        A group reached through this one resolves aliases the same way, so that
        is no longer something to remember. `AliasGroup` specifically, not
        `type(self)`: a root group that adds behaviour of its own — dispatching
        to sibling binaries, say — means it for the root, not for everything
        mounted under it.
        """
        for registered, command in self.commands.items():
            canonical = self._canonical_spelling(registered)
            if command.name != canonical:
                command.name = canonical
            # The structural test again: a mounted sub-app is not an instance of
            # the public `click.Group`, because Typer vendors its own internals.
            if getattr(command, "commands", None) is not None and not isinstance(
                command, AliasGroup
            ):
                command.__class__ = AliasGroup

    def resolve_command(self, ctx: Any, args: list[str]) -> Any:
        """Resolve a command, suggesting only spellings that would work.

        Typer builds its "did you mean" from `self.commands.keys()` directly, so
        a typo against `@app.command("workspace | ws")` answered
        `Did you mean 'workspace | ws'?` — a confident instruction that fails
        when followed. That is worse than no suggestion: an agent types it
        verbatim.

        Expanding the map to one entry per spelling for the length of the call
        gives the suggestion real candidates to choose from, and gives them
        individually rather than as one unusable string. The registration keys
        are put back afterwards, because that is where the aliases are declared
        and where a consumer reading the tree expects to find them.
        """
        self._prepare()
        registered = self.commands
        self.commands = {
            spelling: command
            for name, command in registered.items()
            for spelling in _ALIAS_SPLIT.split(name)
        }
        try:
            return super().resolve_command(ctx, args)
        finally:
            self.commands = registered

    @staticmethod
    def _canonical_spelling(name: str) -> str:
        return _ALIAS_SPLIT.split(name)[0]

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
            get_logger().error(exc.message, exit_code=exc.exit_code)
            raise SystemExit(exc.exit_code) from None

    def shell_complete(self, ctx: Any, incomplete: str) -> list[Any]:
        """Offer each alias as its own completion candidate.

        Completion does not go through `get_command`. Click enumerates the
        *registered* names, so a command declared `"list | ls"` arrives as a
        single candidate spelled `list | ls`, and accepting it inserts a string
        that is not a command.

        Asking the base class for the empty prefix yields one correctly-typed
        item per visible command, named canonically; each is then offered under
        every spelling it was declared with, filtered by what the user has
        actually typed. Resolution is untouched — only this method is widened.
        """
        self._prepare()
        spellings = {
            self._canonical_spelling(name): _ALIAS_SPLIT.split(name) for name in self.commands
        }
        candidates = [
            type(item)(spelling, type=item.type, help=item.help)
            for item in super().shell_complete(ctx, "")
            # A subclass may list commands it does not register — a root group
            # dispatching to siblings — and those have one spelling.
            for spelling in spellings.get(item.value, [item.value])
            if spelling.startswith(incomplete)
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


def command_tree(app: typer.Typer) -> list[dict[str, object]]:
    """Every command the app exposes, as data: what to type, and what it does.

    **This exists because the audience is agents.** Everything else here emits
    `--output json` on request; the one thing that could not was the command
    surface itself, so finding out what a CLI offers meant parsing Typer's rich
    help — box-drawing glyphs that break byte-oriented tools, and text reflowed
    to whatever `COLUMNS` happens to be, so the same command produces different
    bytes in different terminals. A toolkit for building CLIs on a workstation
    driven by agents should not ship that as the only answer.

    One row per leaf command::

        {"command": "workspace list",
         "aliases": ["workspace ls", "ws list", "ws ls"],
         "help": "List the Vault workspaces and their lifecycle state."}

    `command` is always the spelling to prefer, and `aliases` is a separate
    list — so nothing here ever puts a string like `list | ls` where a caller
    might type it. Sub-apps flatten, so a row's `command` is a complete
    invocation rather than a path to reassemble, and every combination of
    spellings that resolves is listed, not just one per level.

    Derived from the live tree rather than maintained beside it, so it cannot
    fall behind what the app actually offers. `version` is included: it is a
    real command, and a consumer that wants an affordance list rather than a
    command list can drop it more easily than it could add it back.

    To extend it — extra fields, or rows for commands that are not in the tree
    at all — build on the returned dicts and register the result yourself::

        app = build_app(cli_name="mycli", version=__version__, commands_command=False)

        @app.command("commands")
        def commands(output: OutputFormat = OUTPUT_OPTION) -> None:
            rows = [{**row, "runs": "mycli"} for row in command_tree(app)]
            emit(rows + _sibling_rows(), output=output)
    """
    return sorted(
        _tree_rows(typer.main.get_command(app), []),
        key=lambda row: str(row["command"]),
    )


def _tree_rows(command: Any, spellings: list[list[str]]) -> list[dict[str, object]]:
    """Walk the click tree, carrying the spellings available at each level."""
    # A structural test, not `isinstance(command, click.Group)`: Typer vendors
    # its own click internals, so a mounted sub-app is not an instance of the
    # public package's `Group` and the isinstance check silently returns False.
    children = getattr(command, "commands", None)
    if not children:
        paths = [" ".join(parts) for parts in itertools.product(*spellings)]
        return [
            {
                "command": paths[0],
                "aliases": paths[1:],
                "help": command.get_short_help_str(limit=_HELP_LIMIT),
            }
        ]
    rows: list[dict[str, object]] = []
    for registered, child in children.items():
        if child.hidden:
            continue
        rows.extend(_tree_rows(child, [*spellings, _ALIAS_SPLIT.split(registered)]))
    return rows


def build_app(
    *,
    cli_name: str,
    version: str,
    version_command: bool = True,
    commands_command: bool = True,
    **kwargs: Any,
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

    `commands_command=False` omits the `commands` subcommand, which reports the
    tree as data for a caller that is not a person — see `command_tree`. Pass it
    when you want to register an extended version of your own; the default is on
    so that a CLI built here is legible to an agent with no wiring at all.
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

    if commands_command:

        @app.command("commands")
        def commands_cmd(output: OutputFormat = OUTPUT_OPTION) -> None:
            """List every command as data — what to type and what it does.

            `--output json` is the point of it. `--help` is for a person; this
            is for anything that has to decide which command to run without a
            human reading a table first. A row's `aliases` are alternative
            spellings that resolve to the same command; `command` is always the
            one to prefer.
            """
            emit(command_tree(app), output=output)

    return app
