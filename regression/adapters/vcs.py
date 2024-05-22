"""Synopsys VCS/Vlogan/URG command generation."""

from __future__ import annotations

from pathlib import Path

from regression.adapters.base import SimulatorAdapter
from regression.config import TestSpec
from regression.models import Command, TestRunPlan


class VcsAdapter(SimulatorAdapter):
    name = "vcs"
    supported_flows = frozenset({"uvm"})

    @classmethod
    def regression_tools(cls) -> tuple[tuple[str, str], ...]:
        return (("VLOGAN", "vlogan"), ("VCS", "vcs"))

    @classmethod
    def coverage_tools(cls) -> tuple[tuple[str, str], ...]:
        return (("URG", "urg"),)

    @staticmethod
    def _simv(build_dir: Path) -> Path:
        return build_dir / "simv"

    def _coverage_options(self) -> tuple[str, ...]:
        if self.config.coverage_options:
            return self.config.coverage_options
        return ("-cm", "line+cond+fsm+tgl+branch+assert")

    def compile_commands(self, build_dir: Path) -> tuple[Command, ...]:
        argv = (
            *self.tool("VLOGAN", "vlogan"),
            "-full64",
            "-sverilog",
            "-ntb_opts",
            "uvm-1.2",
            "-Mdir=" + str(build_dir / "csrc"),
            "-f",
            str(self.config.source_manifest),
            *self.config.compile_options,
        )
        return (
            self.command(argv, self.project_root, "VCS compile", build_dir / "compile.log"),
        )

    def elaborate_commands(self, build_dir: Path) -> tuple[Command, ...]:
        argv = (
            *self.tool("VCS", "vcs"),
            "-full64",
            "-ntb_opts",
            "uvm-1.2",
            "-top",
            self.config.top,
            "-o",
            str(self._simv(build_dir)),
            "-Mdir=" + str(build_dir / "csrc"),
            *self._coverage_options(),
            *self.config.elaborate_options,
        )
        return (
            self.command(argv, self.project_root, "VCS elaborate", build_dir / "elaborate.log"),
        )

    def test_plan(
        self, test: TestSpec, seed: int, build_dir: Path, test_dir: Path
    ) -> TestRunPlan:
        coverage_path = test_dir / "coverage.vdb" if test.coverage else None
        waveform_path = test_dir / "waves.vcd" if test.waveform else None
        argv: tuple[str, ...] = (
            str(self._simv(build_dir)),
            f"+UVM_TESTNAME={test.uvm_test}",
            f"+UVM_VERBOSITY={test.uvm_verbosity}",
            f"+ntb_random_seed={seed}",
            *test.uvm_args,
            *self.config.run_options,
            *self.test_options(test),
        )
        if coverage_path:
            argv += (*self._coverage_options(), "-cm_dir", str(coverage_path))
        if waveform_path:
            argv += (
                "+WAVES=1",
                f"+WAVEFORM_FILE={waveform_path}",
            )
        command = self.command(argv, test_dir, f"VCS run {test.name}", test_dir / "run.log")
        return TestRunPlan(command, coverage_path, waveform_path)

    def merge_commands(
        self,
        databases: tuple[Path, ...],
        merged_path: Path,
        report_dir: Path,
    ) -> tuple[Command, ...]:
        argv = (
            *self.tool("URG", "urg"),
            "-dir",
            *(str(path) for path in databases),
            "-dbname",
            str(merged_path),
            "-report",
            str(report_dir),
        )
        return (
            self.command(argv, self.project_root, "VCS coverage merge", report_dir / "urg.log"),
        )
