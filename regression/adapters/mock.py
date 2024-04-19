"""Deterministic local adapter used to validate orchestration without licenses."""

from __future__ import annotations

import sys
from pathlib import Path

from regression.adapters.base import SimulatorAdapter
from regression.config import TestSpec
from regression.models import Command, Provenance, TestRunPlan


class MockAdapter(SimulatorAdapter):
    name = "mock"
    provenance = Provenance.MOCK

    @classmethod
    def regression_tools(cls) -> tuple[tuple[str, str], ...]:
        return ()

    @classmethod
    def coverage_tools(cls) -> tuple[tuple[str, str], ...]:
        return ()

    @staticmethod
    def _tool_script() -> Path:
        return Path(__file__).resolve().parents[1] / "mock_tool.py"

    def compile_commands(self, build_dir: Path) -> tuple[Command, ...]:
        argv = (sys.executable, str(self._tool_script()), "compile")
        return (
            self.command(argv, self.project_root, "Mock compile", build_dir / "compile.log"),
        )

    def elaborate_commands(self, build_dir: Path) -> tuple[Command, ...]:
        argv = (sys.executable, str(self._tool_script()), "elaborate")
        return (
            self.command(argv, self.project_root, "Mock elaborate", build_dir / "elaborate.log"),
        )

    def test_plan(
        self, test: TestSpec, seed: int, build_dir: Path, test_dir: Path
    ) -> TestRunPlan:
        coverage_path = test_dir / "coverage.json" if test.coverage else None
        waveform_path = test_dir / "waves.mock" if test.waveform else None
        argv: tuple[str, ...] = (
            sys.executable,
            str(self._tool_script()),
            "run",
            "--test",
            test.name,
            "--seed",
            str(seed),
            "--behavior",
            test.mock_behavior,
            "--delay",
            str(test.mock_delay_seconds),
        )
        if coverage_path:
            argv += ("--coverage", str(coverage_path))
        if waveform_path:
            argv += ("--waveform", str(waveform_path))
        command = self.command(argv, test_dir, f"Mock run {test.name}", test_dir / "run.log")
        return TestRunPlan(command, coverage_path, waveform_path)

    def merge_commands(
        self,
        databases: tuple[Path, ...],
        merged_path: Path,
        report_dir: Path,
    ) -> tuple[Command, ...]:
        argv = (
            sys.executable,
            str(self._tool_script()),
            "merge",
            "--output",
            str(merged_path),
            "--report-dir",
            str(report_dir),
            *(str(path) for path in databases),
        )
        return (
            self.command(argv, self.project_root, "Mock coverage merge", report_dir / "merge.log"),
        )
