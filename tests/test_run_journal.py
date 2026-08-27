"""Unit tests for passive CLI run journal."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from amr_clikit.run import _write_journal


class RunJournalTests(unittest.TestCase):
    def test_write_journal_appends_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_home = Path(tmp)
            record = {
                "ts": "2026-08-27T10:00:00Z",
                "cli": "amr",
                "args": ["workspace", "list"],
                "cwd": "/tmp",
                "duration_ms": 42.5,
                "exit": 0,
            }
            with (
                mock.patch.dict("os.environ", {}, clear=True),
                mock.patch("pathlib.Path.home", return_value=tmp_home),
            ):
                _write_journal(record)
                journal_path = tmp_home / ".amr" / "runs.jsonl"
                self.assertTrue(journal_path.is_file())
                lines = journal_path.read_text(encoding="utf-8").strip().splitlines()
                self.assertEqual(len(lines), 1)
                parsed = json.loads(lines[0])
                self.assertEqual(parsed["cli"], "amr")
                self.assertEqual(parsed["args"], ["workspace", "list"])
                self.assertEqual(parsed["exit"], 0)

    def test_write_journal_skips_when_no_journal_env_set(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            tmp_home = Path(tmp)
            record = {"ts": "2026-08-27T10:00:00Z", "cli": "amr"}
            with (
                mock.patch.dict("os.environ", {"AMR_NO_JOURNAL": "1"}),
                mock.patch("pathlib.Path.home", return_value=tmp_home),
            ):
                _write_journal(record)
                journal_path = tmp_home / ".amr" / "runs.jsonl"
                self.assertFalse(journal_path.exists())


if __name__ == "__main__":
    unittest.main()
