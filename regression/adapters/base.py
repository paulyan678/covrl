"""Contract shared by all simulator adapters."""

from __future__ import annotations

import os
import shlex
import shutil
from abc import ABC, abstractmethod
from collections.abc import Iterable
from pathlib import Path

from regression.config import SimulatorConfig, TestSpec
from regression.models import Availability, Command, Provenance, TestRunPlan


class SimulatorAdapter(ABC):
    """Converts simulator-neutral test data into shell-free commands."""

    name: str
    provenance = Provenance.REAL
    supported_flows = frozenset({"uvm", "smoke"})
    coverage_supported = True

    def __init__(self, project_root: Path, config: SimulatorConfig) -> None:
        self.project_root = project_root.resolve()
        self.config = config

    @staticmethod
    def tool(env_name: str, default: str) -> tuple[str, ...]:
        """Resolve an executable and optional wrapper args from the environment."""

        value = os.environ.get(env_name, default)
        tokens = tuple(shlex.split(value))
        if not tokens:
            raise ValueError(f"environment variable {env_name} resolved to an empty command")
        return tokens

    @classmethod
    @abstractmethod
    def regression_tools(cls) -> tuple[tuple[str, str], ...]:
        """Return `(environment variable, default executable)` requirements."""

    @classmethod
    @abstractmethod
    def coverage_tools(cls) -> tuple[tuple[str, str], ...]:
        """Return tool requirements used only for coverage merge/report."""

    @classmethod
    def _check_tools(cls, tools: Iterable[tuple[str, str]]) -> Availability:
        missing: list[str] = []
        for env_name, default in tools:
            command = cls.tool(env_name, default)
            executable = command[0]
            if shutil.which(executable) is None:
                missing.append(f"{env_name}={executable}")
        if missing:
            detail = "missing executable(s): " + ", ".join(missing)
            return Availability(False, tuple(missing), detail)
        return Availability(True, (), "all required executables are available")

    @classmethod
    def regression_availability(cls) -> Availability:
        return cls._check_tools(cls.regression_tools())

    @classmethod
    def coverage_availability(cls) -> Availability:
        return cls._check_tools(cls.coverage_tools())

    def supports(self, test: TestSpec) -> bool:
        return test.flow in self.supported_flows and (
            self.coverage_supported or not test.coverage
        )

    def unsupported_reason(self, test: TestSpec) -> str:
        if test.flow not in self.supported_flows:
            return f"{self.name} does not support the {test.flow!r} flow"
        if test.coverage and not self.coverage_supported:
            return f"{self.name} does not provide coverage for this flow"
        return f"{self.name} cannot run this test configuration"

    @abstractmethod
    def compile_commands(self, build_dir: Path) -> tuple[Command, ...]:
        """Build source libraries without elaborating the top."""

    @abstractmethod
    def elaborate_commands(self, build_dir: Path) -> tuple[Command, ...]:
        """Build or optimize the runnable top-level image."""

    @abstractmethod
    def test_plan(
        self, test: TestSpec, seed: int, build_dir: Path, test_dir: Path
    ) -> TestRunPlan:
        """Return one test command and its anticipated artifacts."""

    @abstractmethod
    def merge_commands(
        self,
        databases: tuple[Path, ...],
        merged_path: Path,
        report_dir: Path,
    ) -> tuple[Command, ...]:
        """Return coverage database merge and report commands."""

    def test_options(self, test: TestSpec) -> tuple[str, ...]:
        return tuple(test.simulator_options.get(self.name, ()))

    @staticmethod
    def command(
        argv: tuple[str, ...], cwd: Path, description: str, log_path: Path
    ) -> Command:
        return Command(argv=argv, cwd=cwd, description=description, log_path=log_path)
