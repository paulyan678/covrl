"""Siemens Questa/ModelSim command generation."""

from __future__ import annotations

from pathlib import Path

from regression.adapters.base import SimulatorAdapter
from regression.config import TestSpec
from regression.models import Command, TestRunPlan


class QuestaAdapter(SimulatorAdapter):
    name = "questa"
    supported_flows = frozenset({"uvm"})

    @classmethod
    def regression_tools(cls) -> tuple[tuple[str, str], ...]:
        return (
            ("VLIB", "vlib"),
            ("VLOG", "vlog"),
            ("VOPT", "vopt"),
            ("VSIM", "vsim"),
        )

    @classmethod
    def coverage_tools(cls) -> tuple[tuple[str, str], ...]:
        return (("VCOVER", "vcover"),)

    @staticmethod
    def _work(build_dir: Path) -> Path:
        return build_dir / "work"

    @staticmethod
    def _optimized_top(build_dir: Path) -> str:
        return "codec_opt"

    def _coverage_options(self) -> tuple[str, ...]:
        return self.config.coverage_options or ("+cover=bcesft",)

    def compile_commands(self, build_dir: Path) -> tuple[Command, ...]:
        work = self._work(build_dir)
        create = self.command(
            (*self.tool("VLIB", "vlib"), str(work)),
            self.project_root,
            "Questa create work library",
            build_dir / "vlib.log",
        )
        compile_command = self.command(
            (
                *self.tool("VLOG", "vlog"),
                "-sv",
                "-mfcu",
                "-L",
                "uvm",
                "-work",
                str(work),
                "-f",
                str(self.config.source_manifest),
                *self.config.compile_options,
            ),
            self.project_root,
            "Questa compile",
            build_dir / "compile.log",
        )
        return (create, compile_command)

    def elaborate_commands(self, build_dir: Path) -> tuple[Command, ...]:
        argv = (
            *self.tool("VOPT", "vopt"),
            "-work",
            str(self._work(build_dir)),
            "-L",
            "uvm",
            self.config.top,
            "-o",
            self._optimized_top(build_dir),
            *self._coverage_options(),
            *self.config.elaborate_options,
        )
        return (
            self.command(argv, self.project_root, "Questa optimize", build_dir / "elaborate.log"),
        )

    @staticmethod
    def _tcl_path(path: Path) -> str:
        return "{" + str(path).replace("}", "\\}") + "}"

    def test_plan(self, test: TestSpec, seed: int, build_dir: Path, test_dir: Path) -> TestRunPlan:
        coverage_path = test_dir / "coverage.ucdb" if test.coverage else None
        waveform_path = test_dir / "waves.vcd" if test.waveform else None
        actions: list[str] = []
        actions.append("run -all")
        if coverage_path:
            actions.append(f"coverage save {self._tcl_path(coverage_path)}")
        actions.append("quit -f")
        argv: tuple[str, ...] = (
            *self.tool("VSIM", "vsim"),
            "-c",
        )
        if coverage_path:
            argv += ("-coverage",)
        argv += (
            *self.config.run_options,
            *self.test_options(test),
            "-lib",
            str(self._work(build_dir)),
            "-L",
            "uvm",
            "-sv_seed",
            str(seed),
            self._optimized_top(build_dir),
            f"+UVM_TESTNAME={test.uvm_test}",
            f"+UVM_VERBOSITY={test.uvm_verbosity}",
            *test.uvm_args,
            "-do",
            "; ".join(actions),
        )
        if waveform_path:
            argv += ("+WAVES=1", f"+WAVEFORM_FILE={waveform_path}")
        command = self.command(argv, test_dir, f"Questa run {test.name}", test_dir / "run.log")
        return TestRunPlan(command, coverage_path, waveform_path)

    def merge_commands(
        self,
        databases: tuple[Path, ...],
        merged_path: Path,
        report_dir: Path,
    ) -> tuple[Command, ...]:
        merge = self.command(
            (
                *self.tool("VCOVER", "vcover"),
                "merge",
                str(merged_path),
                *(str(path) for path in databases),
            ),
            self.project_root,
            "Questa coverage merge",
            report_dir / "vcover-merge.log",
        )
        report = self.command(
            (
                *self.tool("VCOVER", "vcover"),
                "report",
                "-html",
                "-output",
                str(report_dir),
                str(merged_path),
            ),
            self.project_root,
            "Questa coverage report",
            report_dir / "vcover-report.log",
        )
        return (merge, report)
