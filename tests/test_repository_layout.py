from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class RepositoryLayoutTests(unittest.TestCase):
    def test_core_source_directories_exist(self) -> None:
        for relative in ("docs", "regression", "rl", "tests"):
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_dir())

    def test_python_packages_have_markers(self) -> None:
        for relative in ("regression/__init__.py", "rl/__init__.py", "tests/__init__.py"):
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file())


if __name__ == "__main__":
    unittest.main()
