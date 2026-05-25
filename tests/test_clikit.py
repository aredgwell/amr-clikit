"""Contract tests for amr-clikit: logging routing/format/levels and result output."""

from __future__ import annotations

import json

import pytest

from amr_clikit import configure_logging, emit, get_logger, level_for_verbosity


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
