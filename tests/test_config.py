from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from regression.config import ManifestError, load_manifest
from tests.common import MANIFEST, read_manifest_data


class ManifestTests(unittest.TestCase):
    def test_loads_representative_manifest_and_suites(self) -> None:
        manifest = load_manifest(MANIFEST)
        self.assertEqual(len(manifest.tests), 6)
        self.assertEqual(len(manifest.suite_tests("nightly")), 5)
        self.assertEqual(manifest.defaults.seed_base, 20_230_921)
        self.assertTrue(manifest.simulators["vcs"].source_manifest.is_absolute())

    def test_unknown_suite_is_actionable(self) -> None:
        manifest = load_manifest(MANIFEST)
        with self.assertRaisesRegex(ManifestError, "available suites"):
            manifest.suite_tests("does-not-exist")

    def test_rejects_duplicate_test_names(self) -> None:
        data = read_manifest_data()
        data["project_root"] = str(MANIFEST.parents[2])
        data["tests"].append(dict(data["tests"][0]))
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, "duplicate test name"):
                load_manifest(path)

    def test_rejects_invalid_timeout_type(self) -> None:
        data = read_manifest_data()
        data["project_root"] = str(MANIFEST.parents[2])
        data["tests"][0]["timeout_seconds"] = True
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, "must be a number"):
                load_manifest(path)

    def test_rejects_missing_fixed_seed_value(self) -> None:
        data = read_manifest_data()
        data["project_root"] = str(MANIFEST.parents[2])
        data["tests"][0]["seed"] = {"policy": "fixed"}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, "value is required"):
                load_manifest(path)

    def test_reports_json_line_and_column(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.json"
            path.write_text('{"schema_version":', encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, r"broken.json:1:\d+"):
                load_manifest(path)

    def test_rejects_unknown_fields_instead_of_ignoring_typos(self) -> None:
        data = read_manifest_data()
        data["defaults"]["wavefrom"] = True
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            data["project_root"] = str(MANIFEST.parents[2])
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, "unknown field.*wavefrom"):
                load_manifest(path)

    def test_rejects_non_finite_timeout(self) -> None:
        data = read_manifest_data()
        data["project_root"] = str(MANIFEST.parents[2])
        data["tests"][0]["timeout_seconds"] = float("nan")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, "must be finite"):
                load_manifest(path)

    def test_rejects_numeric_overflow_actionably(self) -> None:
        data = read_manifest_data()
        data["project_root"] = str(MANIFEST.parents[2])
        data["tests"][0]["timeout_seconds"] = 10**400
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, "must be finite"):
                load_manifest(path)

    def test_repeated_simulator_flags_preserve_order(self) -> None:
        data = read_manifest_data()
        data["project_root"] = str(MANIFEST.parents[2])
        data["tests"][0]["simulator_options"] = {"questa": ["-L", "first_lib", "-L", "second_lib"]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "options.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            manifest = load_manifest(path)
        self.assertEqual(
            manifest.tests[0].simulator_options["questa"],
            ("-L", "first_lib", "-L", "second_lib"),
        )

    def test_rejects_duplicate_generated_plusarg_controls(self) -> None:
        data = read_manifest_data()
        data["project_root"] = str(MANIFEST.parents[2])
        data["tests"][0]["uvm_args"] = ["+COVERAGE=0"]
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            with self.assertRaisesRegex(ManifestError, "reserved generated control"):
                load_manifest(path)


if __name__ == "__main__":
    unittest.main()
