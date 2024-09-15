from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from regression.process import read_log


class LogReadTests(unittest.TestCase):
    def test_default_read_retains_early_failure_markers(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sim.log"
            path.write_text("Assertion p_ready has failed\n" + ("x" * 1024), encoding="utf-8")
            text = read_log(path)
        self.assertIn("Assertion p_ready has failed", text)

    def test_explicit_tail_limit_remains_available(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sim.log"
            path.write_text("start\n" + ("x" * 128) + "\nend\n", encoding="utf-8")
            text = read_log(path, max_bytes=16)
        self.assertNotIn("start", text)
        self.assertIn("end", text)

    def test_invalid_tail_limit_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sim.log"
            path.write_text("log\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "max_bytes"):
                read_log(path, max_bytes=0)


if __name__ == "__main__":
    unittest.main()
