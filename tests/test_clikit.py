"""Contract tests for amr-clikit: logging routing/format/levels and result output."""

from __future__ import annotations

import io
import json
import subprocess
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
    [
        (0, False, "WARNING"),
        (1, False, "INFO"),
        (2, False, "DEBUG"),
        (0, True, "ERROR"),
    ],
)
def test_level_for_verbosity(verbose: int, quiet: bool, expected: str) -> None:
    assert level_for_verbosity(verbose=verbose, quiet=quiet) == expected


# --- emit (results -> stdout) ----------------------------------------------


def test_emit_json_dict(capsys: pytest.CaptureFixture[str]) -> None:
    emit({"b": 2, "a": 1}, output="json")
    out = capsys.readouterr().out
    assert json.loads(out) == {"a": 1, "b": 2}
    assert out.endswith("\n")


def test_emit_agent_dict(capsys: pytest.CaptureFixture[str]) -> None:
    emit({"b": 2, "a": 1}, output="agent")
    out = capsys.readouterr().out
    assert json.loads(out) == {"a": 1, "b": 2}
    assert out == '{"a":1,"b":2}\n'


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


def test_emit_table_has_no_trailing_whitespace(capsys: pytest.CaptureFixture[str]) -> None:
    """Padding the final column puts trailing space on every header and short row."""
    emit([{"name": "a", "note": "long note"}, {"name": "bb", "note": "x"}], output="text")
    lines = capsys.readouterr().out.splitlines()
    assert lines == [line.rstrip() for line in lines]
    assert lines[0] == "name  note"


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
    assert "Traceback" not in err  # no traceback below DEBUG
    assert "-vv" in err  # the hint names the level that actually shows one


# --- logging contract ------------------------------------------------------


def test_logs_to_stderr_as_json_with_bound_context(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(cli_name="t", version="9.9.9", level="INFO")
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


def test_default_level_filters_info(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(cli_name="t", version="0")
    log = get_logger()
    log.info("hidden")
    log.warning("shown")
    assert [r["event"] for r in _log_records(capsys)] == ["shown"]


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


def test_module_level_logger_follows_a_replaced_stream(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A logger held from before configure_logging writes to stderr *now*.

    `log = get_logger()` at module scope is the documented idiom. Binding the
    stream at configure time made it write to a stale stderr for the life of
    the process — under CliRunner, one the runner had already closed.
    """
    module_log = get_logger()

    first = io.StringIO()
    monkeypatch.setattr(sys, "stderr", first)
    configure_logging(cli_name="t", version="0")
    module_log.warning("one")

    second = io.StringIO()
    monkeypatch.setattr(sys, "stderr", second)
    configure_logging(cli_name="t", version="0")
    module_log.warning("two")

    assert [json.loads(line)["event"] for line in first.getvalue().splitlines()] == ["one"]
    assert [json.loads(line)["event"] for line in second.getvalue().splitlines()] == ["two"]


def test_module_level_logger_follows_a_reconfigured_level(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The same staleness in a second place: a cached logger froze the level."""
    module_log = get_logger()

    configure_logging(cli_name="t", version="0")  # WARNING
    module_log.info("hidden")
    configure_logging(cli_name="t", version="0", level="INFO")
    module_log.info("shown")

    assert [r["event"] for r in _log_records(capsys)] == ["shown"]


def test_structlog_is_not_imported_by_a_cli_that_never_logs() -> None:
    """The whole point of deferring it: importing the toolkit must not cost 62 ms.

    Run in a subprocess because this one has structlog imported many times over
    by the tests above, and `sys.modules` is process-wide.
    """
    script = (
        "import sys\n"
        "import amr_clikit\n"
        "from amr_clikit import configure_logging\n"
        "configure_logging(cli_name='t', version='0')\n"
        "print('structlog' in sys.modules)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "False"


def test_a_module_level_logger_costs_nothing_until_it_logs() -> None:
    """The idiom eight `amr` modules use must not drag structlog in at import."""
    script = (
        "import sys\n"
        "from amr_clikit import configure_logging, get_logger\n"
        "log = get_logger()\n"
        "configure_logging(cli_name='t', version='0')\n"
        "before = 'structlog' in sys.modules\n"
        "log.warning('now')\n"
        "print(before, 'structlog' in sys.modules)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    assert result.stdout.strip() == "False True"


def test_a_cli_that_does_log_still_gets_the_configured_renderer() -> None:
    """And the deferral is invisible to one that does: same JSON, same fields."""
    script = (
        "from amr_clikit import configure_logging, get_logger\n"
        "configure_logging(cli_name='t', version='9.9', level='INFO')\n"
        "get_logger().info('hello', n=1)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    record = json.loads(result.stderr.strip())
    assert record["event"] == "hello"
    assert record["cli"] == "t"
    assert record["version"] == "9.9"
    assert record["n"] == 1


def test_console_logs_are_concise(monkeypatch: pytest.MonkeyPatch) -> None:
    class TtyStringIO(io.StringIO):
        def isatty(self) -> bool:
            return True

    err = TtyStringIO()
    monkeypatch.setattr(sys, "stderr", err)
    configure_logging(cli_name="demo", version="1.2.3", level="INFO")
    get_logger().info("listing labs", count=0)
    assert err.getvalue() == "listing labs count=0\n"


def test_console_logs_format_exception_on_newline(monkeypatch: pytest.MonkeyPatch) -> None:
    class TtyStringIO(io.StringIO):
        def isatty(self) -> bool:
            return True

    err = TtyStringIO()
    monkeypatch.setattr(sys, "stderr", err)
    configure_logging(cli_name="demo", version="1.2.3", level="DEBUG")
    try:
        raise ValueError("bad thing")
    except ValueError as exc:
        get_logger().error("failed operation", exc_info=exc)

    output = err.getvalue()
    lines = output.splitlines()
    assert lines[0] == "failed operation"
    assert "Traceback (most recent call last):" in output
    assert "ValueError: bad thing" in output


def test_emit_empty_dict_table(capsys: pytest.CaptureFixture[str]) -> None:
    emit([{}], output="text")
    assert capsys.readouterr().out == "\n"


def test_emit_dict_with_none_and_collections(capsys: pytest.CaptureFixture[str]) -> None:
    emit({"empty": None, "items": [1, 2], "tuple": ("a", "b")}, output="text")
    assert capsys.readouterr().out == "empty: \nitems: 1, 2\ntuple: a, b\n"


def test_confirm_interactive(monkeypatch: pytest.MonkeyPatch) -> None:
    class InteractiveStdin(io.StringIO):
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(sys, "stdin", InteractiveStdin("y\n"))
    assert confirm("proceed?") is True

    monkeypatch.setattr(sys, "stdin", InteractiveStdin("yes\n"))
    assert confirm("proceed?") is True

    monkeypatch.setattr(sys, "stdin", InteractiveStdin("n\n"))
    assert confirm("proceed?") is False


def test_run_cli_unexpected_error_debug_shows_traceback(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging(cli_name="t", version="0", level="DEBUG")
    with pytest.raises(SystemExit) as exit_info:
        run_cli(_raise(RuntimeError("kaboom")))
    assert exit_info.value.code == 1
    err = capsys.readouterr().err
    assert "unexpected error" in err
    assert "Traceback" in err
