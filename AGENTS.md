# AGENTS.md - amr-clikit

Instructions for agents working in this repository.

## Purpose

`amr-clikit` is the shared CLI toolkit for AMR Python CLIs. It owns the
stdout/stderr discipline, structured logging setup, concise console rendering,
Typer glue, command aliases, common options, confirmation prompts, and expected
error handling.

Changes here fan out to every `amr-*` command, so prefer small,
backwards-compatible API changes and add tests for behaviour, not only helpers.

## Start here

1. Read `README.md` for the public contract and examples.
2. Read `pyproject.toml` before changing extras or dependencies.
3. Read `src/amr_clikit/` and existing tests before changing rendering,
   logging, aliases, or error handling.
4. Check downstream callers in sibling repos when changing public names or
   default behaviour.

## Rules

- Keep the core dependency-light. The base package should not require Typer or
  Click; framework glue belongs behind the `typer` extra.
- Preserve the output contract: command results on stdout, diagnostics on
  stderr, JSON when requested or when logs are piped.
- Keep console output readable by default. Routine `info` diagnostics should not
  appear unless verbosity asks for them.
- Treat `CliError`, `emit`, `run_cli`, `configure_logging`, `get_logger`,
  `build_app` and `AliasGroup` as public API. `AliasGroup` is subclassed
  downstream — `amr` extends it for sibling dispatch — so its `get_command`,
  `invoke`, `shell_complete` and `list_commands` are an extension point, not
  internals.
- Do not add component-specific behaviour. Component CLIs should supply their
  own data; this toolkit supplies rendering and CLI mechanics.

## Validation

```sh
uv sync --extra dev
uv run ruff check .
uv run ruff format --check .
uv run pyright
uv run pytest
```

When changing help output, completion, table rendering, or logging defaults,
also smoke test at least one downstream CLI from the meta repo after
reinstalling the tool.
