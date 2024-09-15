from __future__ import annotations

import os
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

from regression.adapters import create_adapter
from regression.config import load_manifest
from regression.models import Provenance
from tests.common import MANIFEST


class AdapterCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.manifest = load_manifest(MANIFEST)
        self.normal = self.manifest.tests_by_name["codec_normal_test"]
        self.smoke = self.manifest.tests_by_name["rtl_smoke_test"]
        self.root = self.manifest.project_root

    def test_vcs_generates_compile_elaborate_run_and_merge(self) -> None:
        adapter = create_adapter("vcs", self.root, self.manifest.simulators["vcs"])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            compile_command = adapter.compile_commands(output / "build")[0]
            elaborate = adapter.elaborate_commands(output / "build")[0]
            plan = adapter.test_plan(self.normal, 17, output / "build", output / "test")
            merge = adapter.merge_commands(
                (output / "a.vdb", output / "b.vdb"),
                output / "merged.vdb",
                output / "report",
            )[0]
        self.assertEqual(compile_command.argv[0], "vlogan")
        self.assertIn("-f", compile_command.argv)
        self.assertEqual(elaborate.argv[0], "vcs")
        self.assertIn("-o", elaborate.argv)
        self.assertIn("+UVM_TESTNAME=codec_normal_test", plan.command.argv)
        self.assertIn("+ntb_random_seed=17", plan.command.argv)
        self.assertEqual(merge.argv[0], "urg")
        self.assertIn("-dbname", merge.argv)

    def test_vcs_tool_command_is_environment_configurable(self) -> None:
        adapter = create_adapter("vcs", self.root, self.manifest.simulators["vcs"])
        with patch.dict(os.environ, {"VLOGAN": "/opt/wrapper vlogan --site"}):
            command = adapter.compile_commands(Path("/tmp/build"))[0]
        self.assertEqual(command.argv[:3], ("/opt/wrapper", "vlogan", "--site"))

    def test_questa_generates_separate_library_compile_and_optimize(self) -> None:
        adapter = create_adapter("questa", self.root, self.manifest.simulators["questa"])
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            compile_commands = adapter.compile_commands(output / "build")
            elaborate = adapter.elaborate_commands(output / "build")[0]
            plan = adapter.test_plan(self.normal, 23, output / "build", output / "test")
            merge = adapter.merge_commands(
                (output / "a.ucdb", output / "b.ucdb"),
                output / "merged.ucdb",
                output / "report",
            )
        self.assertEqual([command.argv[0] for command in compile_commands], ["vlib", "vlog"])
        self.assertEqual(elaborate.argv[0], "vopt")
        self.assertEqual(plan.command.argv[0], "vsim")
        self.assertIn("-coverage", plan.command.argv)
        self.assertIn("coverage save", " ".join(plan.command.argv))
        self.assertEqual(len(merge), 2)
        self.assertEqual(merge[0].argv[:2], ("vcover", "merge"))
        self.assertEqual(merge[1].argv[:2], ("vcover", "report"))

    def test_questa_uvm_header_and_library_are_environment_configurable(self) -> None:
        adapter = create_adapter("questa", self.root, self.manifest.simulators["questa"])
        with patch.dict(
            os.environ,
            {"QUESTA_UVM_SRC": "/opt/uvm/src", "QUESTA_UVM_LIB": "uvm_1_2"},
        ):
            command = adapter.compile_commands(Path("/tmp/build"))[1]
        self.assertIn("+incdir+/opt/uvm/src", command.argv)
        self.assertIn("uvm_1_2", command.argv)

    def test_manifest_coverage_flag_controls_uvm_collector(self) -> None:
        disabled = replace(self.normal, coverage=False)
        for simulator in ("vcs", "questa"):
            adapter = create_adapter(
                simulator,
                self.root,
                self.manifest.simulators[simulator],
            )
            plan = adapter.test_plan(
                disabled,
                17,
                Path("/tmp/build"),
                Path("/tmp/test"),
            )
            self.assertIn("+COVERAGE=0", plan.command.argv)
            self.assertEqual(
                sum(value.startswith("+COVERAGE=") for value in plan.command.argv),
                1,
            )
            self.assertIsNone(plan.coverage_path)

    def test_icarus_explicitly_supports_only_smoke_flow(self) -> None:
        adapter = create_adapter("iverilog", self.root, self.manifest.simulators["iverilog"])
        self.assertFalse(adapter.supports(self.normal))
        self.assertTrue(adapter.supports(self.smoke))
        command = adapter.compile_commands(Path("/tmp/build"))[0]
        self.assertEqual(command.argv[0], "iverilog")
        self.assertIn("-g2012", command.argv)

    def test_icarus_does_not_silently_ignore_requested_coverage(self) -> None:
        adapter = create_adapter("iverilog", self.root, self.manifest.simulators["iverilog"])
        coverage_smoke = replace(self.smoke, coverage=True)
        self.assertFalse(adapter.supports(coverage_smoke))
        self.assertIn("does not provide coverage", adapter.unsupported_reason(coverage_smoke))

    def test_mock_provenance_is_never_real(self) -> None:
        adapter = create_adapter("mock", self.root, self.manifest.simulators["mock"])
        self.assertEqual(adapter.provenance, Provenance.MOCK)
        self.assertTrue(adapter.regression_availability().available)


if __name__ == "__main__":
    unittest.main()
