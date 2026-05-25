"""amr-clikit — structured logging and stdout/stderr discipline for Python CLIs.

Free-standing and typed: any Typer or Click CLI can adopt the same logging
contract, result-output helpers, and error/exit-code handling. The optional
``typer`` extra adds a pre-wired app builder (``amr_clikit.cli``).
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

from amr_clikit.errors import CliError
from amr_clikit.io import OutputFormat, confirm, emit
from amr_clikit.log import configure_logging, get_logger, level_for_verbosity
from amr_clikit.run import run_cli

try:
    __version__ = _version("amr-clikit")
except PackageNotFoundError:  # pragma: no cover - source checkout without install
    __version__ = "0+unknown"

__all__ = [
    "CliError",
    "OutputFormat",
    "__version__",
    "configure_logging",
    "confirm",
    "emit",
    "get_logger",
    "level_for_verbosity",
    "run_cli",
]
