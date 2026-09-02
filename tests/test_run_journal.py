"""Unit tests for the passive CLI run journal."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from amr_clikit.run import _MAX_JOURNAL_BYTES, _write_journal


def test_write_journal_appends_record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AMR_NO_JOURNAL", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    record = {
        "ts": "2026-08-27T10:00:00Z",
        "cli": "amr",
        "args": ["workspace", "list"],
        "cwd": "/tmp",
        "duration_ms": 42.5,
        "exit": 0,
    }

    _write_journal(record)

    journal_path = tmp_path / ".amr" / "runs.jsonl"
    lines = journal_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["cli"] == "amr"
    assert parsed["args"] == ["workspace", "list"]
    assert parsed["exit"] == 0


def test_write_journal_skips_when_no_journal_env_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("AMR_NO_JOURNAL", "1")
    monkeypatch.setattr(Path, "home", lambda: tmp_path)

    _write_journal({"ts": "2026-08-27T10:00:00Z", "cli": "amr"})

    assert not (tmp_path / ".amr" / "runs.jsonl").exists()


def test_write_journal_trims_once_over_the_size_cap(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("AMR_NO_JOURNAL", raising=False)
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    journal_path = tmp_path / ".amr"
    journal_path.mkdir()
    journal_file = journal_path / "runs.jsonl"
    oversized_line = json.dumps({"cli": "amr", "pad": "x" * 200})
    line_count = _MAX_JOURNAL_BYTES // len(oversized_line) + 10
    journal_file.write_text("\n".join([oversized_line] * line_count) + "\n", encoding="utf-8")

    _write_journal({"ts": "2026-08-27T10:00:00Z", "cli": "amr", "exit": 0})

    lines = journal_file.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) < line_count + 1
    assert json.loads(lines[-1])["exit"] == 0
