from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from regression.detection import (
    classify_outcome,
    collect_artifacts,
    detect_failures,
    detect_failures_file,
)
from regression.models import Outcome


class DetectionTests(unittest.TestCase):
    def test_zero_uvm_summary_is_not_a_failure(self) -> None:
        detection = detect_failures("UVM_ERROR : 0\nUVM_FATAL : 0\n")
        self.assertFalse(detection.verification_failed)
        outcome, reasons = classify_outcome("pass", 0, False, detection)
        self.assertEqual(outcome, Outcome.PASSED)
        self.assertEqual(reasons, ())

    def test_assertion_failure_is_detected_even_with_zero_exit(self) -> None:
        detection = detect_failures("Error: Assertion failure at 100 ns\n")
        outcome, reasons = classify_outcome("pass", 0, False, detection)
        self.assertEqual(detection.assertion_failures, 1)
        self.assertEqual(outcome, Outcome.FAILED)
        self.assertIn("assertion", reasons[0])

    def test_zero_assertion_summary_is_not_a_failure(self) -> None:
        detection = detect_failures("Assertion errors: 0\nAssertions: 0\n")
        self.assertEqual(detection.assertion_failures, 0)

    def test_vendor_assertion_wording_is_detected(self) -> None:
        detection = detect_failures("Error: Assertion p_ready at 100 ns has failed\n")
        self.assertEqual(detection.assertion_failures, 1)

    def test_plural_assertion_summaries_are_counted(self) -> None:
        self.assertEqual(detect_failures("Assertion failures: 3\n").assertion_failures, 3)
        self.assertEqual(detect_failures("Assertions failed: 2\n").assertion_failures, 2)

    def test_zero_sva_summary_is_not_a_failure(self) -> None:
        self.assertEqual(detect_failures("SVA errors: 0\n").assertion_failures, 0)

    def test_file_detection_streams_the_complete_log(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "large.log"
            path.write_text(
                "Assertion p_early has failed\n" + ("ordinary output\n" * 100_000),
                encoding="utf-8",
            )
            detection = detect_failures_file(path)
        self.assertEqual(detection.assertion_failures, 1)

    def test_uvm_error_event_is_detected(self) -> None:
        detection = detect_failures("UVM_ERROR @ 20: reporter [SB] mismatch\n")
        self.assertEqual(detection.uvm_errors, 1)

    def test_uvm_file_line_event_is_detected(self) -> None:
        detection = detect_failures("UVM_ERROR codec_scoreboard.sv(10) @ 5: mismatch\n")
        self.assertEqual(detection.uvm_errors, 1)

    def test_event_is_not_hidden_by_an_inconsistent_zero_summary(self) -> None:
        detection = detect_failures("UVM_ERROR @ 20: reporter [SB] mismatch\nUVM_ERROR : 0\n")
        self.assertEqual(detection.uvm_errors, 1)

    def test_expected_failure_and_unexpected_pass_are_distinct(self) -> None:
        failure = detect_failures("[REGRESSION] FAILURE: bad status\n")
        outcome, _ = classify_outcome("fail", 1, False, failure)
        self.assertEqual(outcome, Outcome.EXPECTED_FAILURE)
        outcome, _ = classify_outcome("fail", 0, False, detect_failures("clean"))
        self.assertEqual(outcome, Outcome.UNEXPECTED_PASS)

    def test_timeout_takes_precedence(self) -> None:
        outcome, _ = classify_outcome("pass", -15, True, detect_failures(""))
        self.assertEqual(outcome, Outcome.TIMEOUT)

    def test_infrastructure_failure_is_not_an_expected_test_failure(self) -> None:
        detection = detect_failures("REGRESSION_INFRA_FAILURE: license issue\n")
        outcome, _ = classify_outcome("fail", 2, False, detection)
        self.assertEqual(outcome, Outcome.ERROR)

    def test_artifact_collector_reports_missing_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            existing = Path(directory) / "coverage.ucdb"
            existing.write_text("coverage", encoding="utf-8")
            coverage, waveform, missing = collect_artifacts(
                existing, Path(directory) / "missing.wlf"
            )
        self.assertEqual(coverage, existing)
        self.assertIsNone(waveform)
        self.assertIn("waveform not produced", missing[0])


if __name__ == "__main__":
    unittest.main()
