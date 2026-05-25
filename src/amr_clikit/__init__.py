"""amr-clikit — structured logging and stdout/stderr discipline for Python CLIs.

Free-standing and typed: any Typer or Click CLI can adopt the same logging
contract and result-output helpers.
"""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as _version

from amr_clikit.io import OutputFormat, emit
from amr_clikit.log import configure_logging, get_logger, level_for_verbosity

try:
    __version__ = _version("amr-clikit")
except PackageNotFoundError:  # pragma: no cover - source checkout without install
    __version__ = "0+unknown"

__all__ = [
    "OutputFormat",
    "__version__",
    "configure_logging",
    "emit",
    "get_logger",
    "level_for_verbosity",
]
