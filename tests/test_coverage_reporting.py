from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from regression.adapters import create_adapter
from regression.config import load_manifest
from regression.coverage import coverage_databases, merge_coverage
from regression.models import Outcome, RunSummary
from regression.reporting import html_text, load_json, markdown_text, write_reports
from regression.runner import RegressionRunner
from tests.common import MANIFEST


class CoverageAndReportingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_manifest(MANIFEST)

    def _mock_summary(self, directory: Path) -> RunSummary:
        return RegressionRunner(self.manifest, "mock", directory / "run", jobs=2, reruns=0).run(
            self.manifest.suite_tests("smoke")
        )

    def test_mock_coverage_merge_is_executable_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            summary = self._mock_summary(root)
            databases = coverage_databases(summary)
            adapter = create_adapter(
                "mock", self.manifest.project_root, self.manifest.simulators["mock"]
            )
            merged = merge_coverage(adapter, databases, root / "coverage")
            payload = json.loads(merged.merged_path.read_text(encoding="utf-8"))
        self.assertEqual(merged.outcome, Outcome.PASSED)
        self.assertEqual(payload["format"], "mock-coverage-merged-v1")
        self.assertEqual(payload["sources"], [str(path) for path in databases])

    def test_vcs_coverage_merge_dry_run_needs_no_database_or_tool(self) -> None:
        adapter = create_adapter("vcs", self.manifest.project_root, self.manifest.simulators["vcs"])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            merged = merge_coverage(
                adapter,
                (root / "planned-a.vdb", root / "planned-b.vdb"),
                root / "coverage",
                dry_run=True,
            )
        self.assertEqual(merged.outcome, Outcome.DRY_RUN)
        self.assertEqual(merged.stages[0].command.argv[0], "urg")

    def test_json_round_trip_and_all_report_formats(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            summary = self._mock_summary(root)
            paths = write_reports(summary, root / "reports")
            loaded = load_json(root / "reports" / "results.json")
            self.assertEqual(loaded.to_dict(), summary.to_dict())
            self.assertTrue(all(path.exists() for path in paths))

    def test_markdown_and_html_escape_untrusted_test_output(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            summary = self._mock_summary(Path(directory))
        first = replace(
            summary.results[0],
            failure_reasons=("<script>alert('x')</script> | newline\nvalue",),
        )
        modified = replace(summary, results=(first, *summary.results[1:]))
        html = html_text(modified)
        markdown = markdown_text(modified)
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;", html)
        self.assertIn("\\|", markdown)
        self.assertIn("coverage=", markdown)

    def test_missing_coverage_database_is_rejected_for_real_merge(self) -> None:
        adapter = create_adapter(
            "mock", self.manifest.project_root, self.manifest.simulators["mock"]
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaisesRegex(ValueError, "do not exist"):
                merge_coverage(adapter, (root / "missing.json",), root / "coverage")

    def test_malformed_result_schema_is_rejected_actionably(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "results.json"
            path.write_text('{"schema_version": 1}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid regression result schema"):
                load_json(path)


if __name__ == "__main__":
    unittest.main()
