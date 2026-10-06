from __future__ import annotations

import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.audit_repo import (
    AuditConfig,
    audit_repository,
    is_generated_path,
    secret_hits,
)


def run_git(root: Path, *args: str, timestamp: str | None = None) -> None:
    environment = os.environ.copy()
    if timestamp is not None:
        environment["GIT_AUTHOR_DATE"] = timestamp
        environment["GIT_COMMITTER_DATE"] = timestamp
    subprocess.run(
        ("git", *args),
        cwd=root,
        env=environment,
        capture_output=True,
        text=True,
        check=True,
    )


def create_three_commit_repository(root: Path) -> None:
    run_git(root, "init", "-q")
    run_git(root, "config", "user.name", "Audit Test")
    run_git(root, "config", "user.email", "audit@example.invalid")
    (root / "README.md").write_text("# Test repository\n", encoding="utf-8")
    (root / ".gitignore").write_text(
        """.env
.env.*
license.dat
outputs/*
!outputs/.gitkeep
simv*
*.vdb/
*.vcd
.venv/
__pycache__/
*.pyc
.DS_Store
""",
        encoding="utf-8",
    )
    run_git(root, "add", "README.md", ".gitignore")
    run_git(
        root,
        "commit",
        "-q",
        "-m",
        "chore: initialize test repository",
        timestamp="2023-09-21T10:00:00+08:00",
    )
    (root / "docs").mkdir()
    (root / "docs" / "notes.md").write_text("# Test notes\n", encoding="utf-8")
    run_git(root, "add", "docs/notes.md")
    run_git(
        root,
        "commit",
        "-q",
        "-m",
        "docs: add test notes",
        timestamp="2023-09-22T11:00:00+08:00",
    )
    title, body = (root / "README.md").read_text(encoding="utf-8").split("\n", maxsplit=1)
    (root / "README.md").write_text(title + "\n\n" + body, encoding="utf-8")
    run_git(root, "add", "README.md")
    run_git(
        root,
        "commit",
        "-q",
        "-m",
        "docs: format test readme",
        timestamp="2023-09-23T12:00:00+08:00",
    )


class RepositoryAuditTests(unittest.TestCase):
    def test_complete_fixture_passes_history_and_hygiene_checks(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_three_commit_repository(root)
            checks = audit_repository(
                root,
                AuditConfig(),
            )
        self.assertTrue(all(check.passed for check in checks))

    def test_dirty_working_tree_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_three_commit_repository(root)
            (root / "untracked.txt").write_text("pending\n", encoding="utf-8")
            checks = audit_repository(
                root,
                AuditConfig(),
            )
        by_name = {check.name: check for check in checks}
        self.assertFalse(by_name["working tree"].passed)

    def test_normal_commit_subject_and_amended_date_are_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_three_commit_repository(root)
            run_git(
                root,
                "commit",
                "--amend",
                "-q",
                "-m",
                "invalid subject",
                timestamp="2023-09-23T12:00:00+08:00",
            )
            checks = audit_repository(
                root,
                AuditConfig(),
            )
        self.assertTrue(all(check.passed for check in checks))

    def test_additional_branch_history_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            create_three_commit_repository(root)
            tree = subprocess.run(
                ("git", "rev-parse", "HEAD^{tree}"),
                cwd=root,
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip()
            commit = subprocess.run(
                ("git", "commit-tree", tree, "-m", "chore: hidden history"),
                cwd=root,
                text=True,
                capture_output=True,
                check=True,
            ).stdout.strip()
            run_git(root, "tag", "extra-history", commit)
            checks = audit_repository(
                root,
                AuditConfig(),
            )
        self.assertTrue(all(check.passed for check in checks))

    def test_high_confidence_key_shape_is_detected(self) -> None:
        sample = "AK" + "IA" + ("A" * 16)
        self.assertTrue(secret_hits(sample, "fixture"))

    def test_generated_path_classification_preserves_output_sentinel(self) -> None:
        self.assertTrue(is_generated_path(Path("outputs/run/results.json")))
        self.assertTrue(is_generated_path(Path("pkg/__pycache__/value.pyc")))
        self.assertFalse(is_generated_path(Path("outputs/.gitkeep")))
        self.assertFalse(is_generated_path(Path("regression/runner.py")))


if __name__ == "__main__":
    unittest.main()
