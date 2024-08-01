from __future__ import annotations

import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from regression.config import SeedSpec, load_manifest
from regression.models import Outcome, Provenance
from regression.runner import RegressionRunner
from tests.common import MANIFEST


class RunnerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_manifest(MANIFEST)

    def test_mock_regression_runs_stages_in_parallel_and_collects_artifacts(self) -> None:
        tests = self.manifest.suite_tests("smoke")
        with tempfile.TemporaryDirectory() as directory:
            summary = RegressionRunner(
                self.manifest,
                "mock",
                Path(directory),
                jobs=2,
                reruns=0,
            ).run(tests)
            self.assertTrue(summary.successful)
            self.assertEqual(summary.provenance, Provenance.MOCK)
            self.assertEqual([stage.outcome for stage in summary.stages], [Outcome.PASSED] * 2)
            self.assertTrue(all(result.coverage_path for result in summary.final_results))
            self.assertTrue(summary.final_results[0].waveform_path)

    def test_dry_run_does_not_require_commercial_tools(self) -> None:
        test = self.manifest.tests_by_name["codec_normal_test"]
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(
                "os.environ", {"VLOGAN": "definitely-missing-vlogan", "VCS": "missing-vcs"}
            ):
                summary = RegressionRunner(
                    self.manifest,
                    "vcs",
                    Path(directory),
                    dry_run=True,
                    reruns=0,
                ).run((test,))
        self.assertEqual(summary.provenance, Provenance.DRY_RUN)
        self.assertFalse(summary.successful)
        self.assertTrue(summary.plan_only)
        self.assertTrue(summary.completed_without_failures)
        self.assertEqual(summary.final_results[0].outcome, Outcome.DRY_RUN)
        self.assertTrue(all(stage.outcome is Outcome.DRY_RUN for stage in summary.stages))

    def test_missing_tool_is_reported_without_attempting_execution(self) -> None:
        test = self.manifest.tests_by_name["codec_normal_test"]
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict(
                "os.environ", {"VLOGAN": "definitely-missing-vlogan", "VCS": "missing-vcs"}
            ):
                summary = RegressionRunner(self.manifest, "vcs", Path(directory), reruns=0).run(
                    (test,)
                )
        result = summary.final_results[0]
        self.assertEqual(result.outcome, Outcome.UNAVAILABLE)
        self.assertIn("missing executable", result.failure_reasons[0])

    def test_timeout_kills_mock_process_and_records_status(self) -> None:
        base = self.manifest.tests_by_name["codec_normal_test"]
        timeout_test = replace(
            base,
            name="timeout_case",
            uvm_test="timeout_case",
            timeout_seconds=0.05,
            expected_result="pass",
            mock_behavior="timeout",
            coverage=False,
            waveform=False,
            seed=SeedSpec("fixed", 77),
        )
        with tempfile.TemporaryDirectory() as directory:
            summary = RegressionRunner(
                self.manifest, "mock", Path(directory), jobs=1, reruns=0
            ).run((timeout_test,))
        result = summary.final_results[0]
        self.assertEqual(result.outcome, Outcome.TIMEOUT)
        self.assertEqual(result.seed, 77)

    def test_failed_test_is_rerun_with_same_seed(self) -> None:
        base = self.manifest.tests_by_name["codec_normal_test"]
        failing = replace(
            base,
            name="persistent_failure",
            uvm_test="persistent_failure",
            mock_behavior="fail",
            expected_result="pass",
            coverage=False,
            waveform=False,
        )
        with tempfile.TemporaryDirectory() as directory:
            summary = RegressionRunner(
                self.manifest, "mock", Path(directory), jobs=1, reruns=1
            ).run((failing,))
        self.assertEqual(len(summary.results), 2)
        self.assertEqual([result.attempt for result in summary.results], [1, 2])
        self.assertEqual(summary.results[0].seed, summary.results[1].seed)
        self.assertEqual(summary.final_results[0].outcome, Outcome.FAILED)

    def test_icarus_marks_uvm_test_unsupported(self) -> None:
        uvm_test = self.manifest.tests_by_name["codec_normal_test"]
        with tempfile.TemporaryDirectory() as directory:
            summary = RegressionRunner(
                self.manifest,
                "iverilog",
                Path(directory),
                dry_run=True,
                reruns=0,
            ).run((uvm_test,))
        self.assertEqual(summary.final_results[0].outcome, Outcome.UNSUPPORTED)
        self.assertEqual(summary.stages, ())


if __name__ == "__main__":
    unittest.main()
