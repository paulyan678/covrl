"""Optional Icarus adapter for the non-UVM RTL smoke bench."""

from __future__ import annotations

from pathlib import Path

from regression.adapters.base import SimulatorAdapter
from regression.config import TestSpec
from regression.models import Command, TestRunPlan


class IcarusAdapter(SimulatorAdapter):
    name = "iverilog"
    supported_flows = frozenset({"smoke"})
    coverage_supported = False

    @classmethod
    def regression_tools(cls) -> tuple[tuple[str, str], ...]:
        return (("IVERILOG", "iverilog"), ("VVP", "vvp"))

    @classmethod
    def coverage_tools(cls) -> tuple[tuple[str, str], ...]:
        return ()

    @staticmethod
    def _image(build_dir: Path) -> Path:
        return build_dir / "rtl_smoke.vvp"

    def compile_commands(self, build_dir: Path) -> tuple[Command, ...]:
        argv = (
            *self.tool("IVERILOG", "iverilog"),
            "-g2012",
            "-s",
            self.config.top,
            "-o",
            str(self._image(build_dir)),
            "-f",
            str(self.config.source_manifest),
            *self.config.compile_options,
        )
        return (
            self.command(
                argv, self.project_root, "Icarus compile smoke bench", build_dir / "compile.log"
            ),
        )

    def elaborate_commands(self, build_dir: Path) -> tuple[Command, ...]:
        return ()

    def test_plan(self, test: TestSpec, seed: int, build_dir: Path, test_dir: Path) -> TestRunPlan:
        waveform_path = test_dir / "waves.vcd" if test.waveform else None
        argv: tuple[str, ...] = (
            *self.tool("VVP", "vvp"),
            str(self._image(build_dir)),
            f"+SEED={seed}",
            *test.uvm_args,
            *self.config.run_options,
            *self.test_options(test),
        )
        if waveform_path:
            argv += ("+WAVES=1", f"+WAVEFORM_FILE={waveform_path}")
        command = self.command(argv, test_dir, f"Icarus run {test.name}", test_dir / "run.log")
        return TestRunPlan(command, None, waveform_path)

    def merge_commands(
        self,
        databases: tuple[Path, ...],
        merged_path: Path,
        report_dir: Path,
    ) -> tuple[Command, ...]:
        raise ValueError("Icarus smoke flow does not produce a mergeable coverage database")
