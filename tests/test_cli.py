from __future__ import annotations

import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from regression.cli import main, safe_clean
from regression.reporting import load_json
from tests.common import MANIFEST, ROOT, read_manifest_data


class CliTests(unittest.TestCase):
    def test_list_suite_discovers_manifest_tests(self) -> None:
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            status = main(["list", "--manifest", str(MANIFEST), "--suite", "smoke"])
        self.assertEqual(status, 0)
        self.assertIn("codec_normal_test", output.getvalue())
        self.assertNotIn("codec_random_test", output.getvalue())

    def test_run_one_mock_test_writes_reports(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "run"
            with contextlib.redirect_stdout(io.StringIO()):
                status = main(
                    [
                        "run",
                        "codec_normal_test",
                        "--manifest",
                        str(MANIFEST),
                        "--simulator",
                        "mock",
                        "--output",
                        str(output),
                        "--reruns",
                        "0",
                    ]
                )
            self.assertEqual(status, 0)
            self.assertTrue((output / "results.json").exists())
            self.assertTrue((output / "report.md").exists())
            self.assertTrue((output / "report.html").exists())

    def test_commercial_dry_run_exits_zero_without_claiming_execution(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "vcs-plan"
            with contextlib.redirect_stdout(io.StringIO()):
                status = main(
                    [
                        "run",
                        "codec_normal_test",
                        "--manifest",
                        str(MANIFEST),
                        "--simulator",
                        "vcs",
                        "--output",
                        str(output),
                        "--dry-run",
                    ]
                )
            summary = load_json(output / "results.json")
        self.assertEqual(status, 0)
        self.assertTrue(summary.plan_only)
        self.assertFalse(summary.successful)

    def test_clean_refuses_path_outside_outputs_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root / "source"
            outside.mkdir()
            with self.assertRaisesRegex(ValueError, "refusing to clean"):
                safe_clean(outside, root / "outputs")
            self.assertTrue(outside.exists())

    def test_clean_removes_only_selected_generated_subtree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "outputs" / "run-a"
            sibling = root / "outputs" / "run-b"
            target.mkdir(parents=True)
            sibling.mkdir(parents=True)
            self.assertTrue(safe_clean(target, root / "outputs"))
            self.assertFalse(target.exists())
            self.assertTrue(sibling.exists())

    def test_rerun_reuses_seed_recorded_by_failed_attempt(self) -> None:
        data = read_manifest_data()
        data["project_root"] = str(ROOT)
        normal = data["tests"][0]
        normal["seed"] = {"policy": "random"}
        normal["mock_behavior"] = "fail"
        normal["waveform"] = False
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest_path = root / "regression.json"
            manifest_path.write_text(json.dumps(data), encoding="utf-8")
            first_output = root / "first"
            with contextlib.redirect_stdout(io.StringIO()):
                first_status = main(
                    [
                        "run",
                        "codec_normal_test",
                        "--manifest",
                        str(manifest_path),
                        "--simulator",
                        "mock",
                        "--output",
                        str(first_output),
                        "--reruns",
                        "0",
                    ]
                )
            first = load_json(first_output / "results.json")
            rerun_output = root / "rerun"
            with contextlib.redirect_stdout(io.StringIO()):
                rerun_status = main(
                    [
                        "rerun",
                        "--results",
                        str(first_output / "results.json"),
                        "--manifest",
                        str(manifest_path),
                        "--simulator",
                        "mock",
                        "--output",
                        str(rerun_output),
                        "--reruns",
                        "0",
                    ]
                )
            rerun = load_json(rerun_output / "results.json")
        self.assertEqual(first_status, 1)
        self.assertEqual(rerun_status, 1)
        self.assertEqual(first.final_results[0].seed, rerun.final_results[0].seed)

    def test_merge_and_report_commands_process_mock_results(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            run_output = root / "run"
            with contextlib.redirect_stdout(io.StringIO()):
                run_status = main(
                    [
                        "run",
                        "codec_normal_test",
                        "--manifest",
                        str(MANIFEST),
                        "--simulator",
                        "mock",
                        "--output",
                        str(run_output),
                        "--reruns",
                        "0",
                    ]
                )
                merge_status = main(
                    [
                        "merge",
                        "--manifest",
                        str(MANIFEST),
                        "--simulator",
                        "mock",
                        "--results",
                        str(run_output / "results.json"),
                        "--output",
                        str(root / "coverage"),
                    ]
                )
                report_status = main(
                    [
                        "report",
                        "--results",
                        str(run_output / "results.json"),
                        "--output",
                        str(root / "regenerated"),
                    ]
                )
            self.assertEqual((run_status, merge_status, report_status), (0, 0, 0))
            self.assertTrue((root / "coverage" / "merged-coverage.json").exists())
            self.assertTrue((root / "regenerated" / "report.md").exists())
            self.assertTrue((root / "regenerated" / "report.html").exists())

    def test_real_merge_rejects_dry_run_results_even_if_stale_database_exists(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            plan_output = root / "vcs-plan"
            with contextlib.redirect_stdout(io.StringIO()):
                plan_status = main(
                    [
                        "run",
                        "codec_normal_test",
                        "--manifest",
                        str(MANIFEST),
                        "--simulator",
                        "vcs",
                        "--output",
                        str(plan_output),
                        "--dry-run",
                    ]
                )
            summary = load_json(plan_output / "results.json")
            coverage_path = summary.final_results[0].coverage_path
            assert coverage_path is not None
            coverage_path.mkdir(parents=True)
            error = io.StringIO()
            with contextlib.redirect_stderr(error), contextlib.redirect_stdout(io.StringIO()):
                merge_status = main(
                    [
                        "merge",
                        "--manifest",
                        str(MANIFEST),
                        "--simulator",
                        "vcs",
                        "--results",
                        str(plan_output / "results.json"),
                        "--output",
                        str(root / "coverage"),
                    ]
                )
        self.assertEqual(plan_status, 0)
        self.assertEqual(merge_status, 2)
        self.assertIn("dry-run results", error.getvalue())


if __name__ == "__main__":
    unittest.main()
