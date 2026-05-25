"""Contract tests for amr-clikit: logging routing/format/levels and result output."""

from __future__ import annotations

import io
import json
import sys
from collections.abc import Callable

import pytest

from amr_clikit import (
    CliError,
    configure_logging,
    confirm,
    emit,
    get_logger,
    level_for_verbosity,
    run_cli,
)


def _raise(exc: BaseException) -> Callable[[], None]:
    def _entry() -> None:
        raise exc

    return _entry


def _log_records(capsys: pytest.CaptureFixture[str]) -> list[dict]:
    """Parse JSON log lines captured on stderr."""
    err = capsys.readouterr().err
    return [json.loads(line) for line in err.splitlines() if line.strip()]


# --- level_for_verbosity ---------------------------------------------------


@pytest.mark.parametrize(
    ("verbose", "quiet", "expected"),
    [(0, False, "INFO"), (1, False, "DEBUG"), (2, False, "DEBUG"), (0, True, "ERROR")],
)
def test_level_for_verbosity(verbose: int, quiet: bool, expected: str) -> None:
    assert level_for_verbosity(verbose=verbose, quiet=quiet) == expected


# --- emit (results -> stdout) ----------------------------------------------


def test_emit_json_dict(capsys: pytest.CaptureFixture[str]) -> None:
    emit({"b": 2, "a": 1}, output="json")
    out = capsys.readouterr().out
    assert json.loads(out) == {"a": 1, "b": 2}
    assert out.endswith("\n")


def test_emit_text_list(capsys: pytest.CaptureFixture[str]) -> None:
    emit(["one", "two"], output="text")
    assert capsys.readouterr().out == "one\ntwo\n"


def test_emit_text_scalar(capsys: pytest.CaptureFixture[str]) -> None:
    emit("hello", output="text")
    assert capsys.readouterr().out == "hello\n"


def test_emit_text_table_of_dicts(capsys: pytest.CaptureFixture[str]) -> None:
    emit([{"name": "a", "port": 1}, {"name": "bb", "port": 22}], output="text")
    lines = capsys.readouterr().out.splitlines()
    assert lines[0].split() == ["name", "port"]  # header
    assert set(lines[1]) <= {"-", " "}  # separator
    assert lines[2].split() == ["a", "1"]
    assert lines[3].split() == ["bb", "22"]


def test_emit_text_dict_as_kv(capsys: pytest.CaptureFixture[str]) -> None:
    emit({"a": 1, "b": 2}, output="text")
    assert capsys.readouterr().out == "a: 1\nb: 2\n"


# --- confirm ---------------------------------------------------------------


def test_confirm_assume_yes() -> None:
    assert confirm("proceed?", assume_yes=True) is True


def test_confirm_non_interactive_is_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdin", io.StringIO())  # StringIO.isatty() -> False
    assert confirm("proceed?") is False


# --- run_cli (error / exit-code contract) ----------------------------------


def test_run_cli_success_returns_none() -> None:
    assert run_cli(lambda: None) is None


def test_run_cli_clierror_exit_code_and_message(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(cli_name="t", version="0")
    with pytest.raises(SystemExit) as exit_info:
        run_cli(_raise(CliError("boom", exit_code=3)))
    assert exit_info.value.code == 3
    assert "boom" in capsys.readouterr().err


def test_run_cli_keyboard_interrupt_is_130() -> None:
    with pytest.raises(SystemExit) as exit_info:
        run_cli(_raise(KeyboardInterrupt()))
    assert exit_info.value.code == 130


def test_run_cli_passes_through_systemexit() -> None:
    with pytest.raises(SystemExit) as exit_info:
        run_cli(_raise(SystemExit(0)))
    assert exit_info.value.code == 0


def test_run_cli_unexpected_error_is_1_without_traceback(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging(cli_name="t", version="0", level="INFO")
    with pytest.raises(SystemExit) as exit_info:
        run_cli(_raise(RuntimeError("kaboom")))
    assert exit_info.value.code == 1
    err = capsys.readouterr().err
    assert "unexpected error" in err
    assert "kaboom" in err
    assert "Traceback" not in err  # no traceback unless -v


# --- logging contract ------------------------------------------------------


def test_logs_to_stderr_as_json_with_bound_context(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(cli_name="t", version="9.9.9")
    get_logger().info("hello", count=2)
    captured = capsys.readouterr()
    assert captured.out == ""  # results channel left untouched
    record = json.loads(captured.err.strip())
    assert record["event"] == "hello"
    assert record["count"] == 2
    assert record["level"] == "info"
    assert record["cli"] == "t"
    assert record["version"] == "9.9.9"
    assert "timestamp" in record


def test_info_level_filters_debug(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(cli_name="t", version="0", level="INFO")
    log = get_logger()
    log.debug("hidden")
    log.info("shown")
    assert [r["event"] for r in _log_records(capsys)] == ["shown"]


def test_debug_level_shows_debug(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(cli_name="t", version="0", level="DEBUG")
    get_logger().debug("now-visible")
    assert [r["event"] for r in _log_records(capsys)] == ["now-visible"]


def test_amr_log_level_env_override(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AMR_LOG_LEVEL", "ERROR")
    configure_logging(cli_name="t", version="0")  # no explicit level
    log = get_logger()
    log.warning("suppressed")
    log.error("kept")
    assert [r["event"] for r in _log_records(capsys)] == ["kept"]


def test_explicit_level_beats_env(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AMR_LOG_LEVEL", "ERROR")
    configure_logging(cli_name="t", version="0", level="DEBUG")
    get_logger().debug("kept")
    assert [r["event"] for r in _log_records(capsys)] == ["kept"]
