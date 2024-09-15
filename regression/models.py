"""Shared immutable models for commands, stages, tests, and reports."""

from __future__ import annotations

import shlex
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class Outcome(str, Enum):
    """Normalized outcome independent of a simulator's exit conventions."""

    PASSED = "passed"
    EXPECTED_FAILURE = "expected_failure"
    FAILED = "failed"
    UNEXPECTED_PASS = "unexpected_pass"
    TIMEOUT = "timeout"
    ERROR = "error"
    UNAVAILABLE = "unavailable"
    UNSUPPORTED = "unsupported"
    DRY_RUN = "dry_run"

    @property
    def is_success(self) -> bool:
        return self in {self.PASSED, self.EXPECTED_FAILURE, self.DRY_RUN}

    @property
    def is_rerunnable(self) -> bool:
        return self in {self.FAILED, self.UNEXPECTED_PASS, self.TIMEOUT, self.ERROR}


class Provenance(str, Enum):
    """Distinguishes generated plans, deterministic mocks, and real tools."""

    REAL = "real"
    MOCK = "mock"
    DRY_RUN = "dry_run"


@dataclass(frozen=True)
class Command:
    """A shell-free process invocation."""

    argv: tuple[str, ...]
    cwd: Path
    description: str
    env: Mapping[str, str] = field(default_factory=dict)
    log_path: Path | None = None

    def display(self) -> str:
        return shlex.join(self.argv)

    def to_dict(self) -> dict[str, Any]:
        return {
            "argv": list(self.argv),
            "cwd": str(self.cwd),
            "description": self.description,
            "env": dict(self.env),
            "log_path": str(self.log_path) if self.log_path else None,
            "display": self.display(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> Command:
        log_path = data.get("log_path")
        return cls(
            argv=tuple(str(value) for value in data["argv"]),
            cwd=Path(str(data["cwd"])),
            description=str(data["description"]),
            env={str(key): str(value) for key, value in dict(data.get("env", {})).items()},
            log_path=Path(str(log_path)) if log_path else None,
        )


@dataclass(frozen=True)
class Availability:
    available: bool
    missing: tuple[str, ...] = ()
    detail: str = ""


@dataclass(frozen=True)
class ProcessResult:
    returncode: int | None
    duration_seconds: float
    timed_out: bool
    started_at: str
    log_path: Path


@dataclass(frozen=True)
class Detection:
    assertion_failures: int = 0
    uvm_errors: int = 0
    uvm_fatals: int = 0
    infrastructure_failures: tuple[str, ...] = ()
    failure_markers: tuple[str, ...] = ()

    @property
    def verification_failed(self) -> bool:
        return bool(
            self.assertion_failures or self.uvm_errors or self.uvm_fatals or self.failure_markers
        )


@dataclass(frozen=True)
class TestRunPlan:
    command: Command
    coverage_path: Path | None = None
    waveform_path: Path | None = None


@dataclass(frozen=True)
class StageResult:
    name: str
    outcome: Outcome
    command: Command
    duration_seconds: float = 0.0
    returncode: int | None = None
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "outcome": self.outcome.value,
            "command": self.command.to_dict(),
            "duration_seconds": self.duration_seconds,
            "returncode": self.returncode,
            "reason": self.reason,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> StageResult:
        return cls(
            name=str(data["name"]),
            outcome=Outcome(str(data["outcome"])),
            command=Command.from_dict(data["command"]),
            duration_seconds=float(data.get("duration_seconds", 0.0)),
            returncode=(int(data["returncode"]) if data.get("returncode") is not None else None),
            reason=str(data.get("reason", "")),
        )


@dataclass(frozen=True)
class TestResult:
    test_name: str
    simulator: str
    attempt: int
    seed: int
    outcome: Outcome
    provenance: Provenance
    expected_result: str
    command: Command | None
    duration_seconds: float = 0.0
    returncode: int | None = None
    started_at: str = ""
    log_path: Path | None = None
    coverage_path: Path | None = None
    waveform_path: Path | None = None
    assertion_failures: int = 0
    uvm_errors: int = 0
    uvm_fatals: int = 0
    failure_reasons: tuple[str, ...] = ()

    @property
    def expectation_met(self) -> bool:
        has_execution_evidence = (
            self.command is not None
            and self.returncode is not None
            and bool(self.started_at)
            and self.log_path is not None
        )
        if self.expected_result == "pass" and self.outcome is Outcome.PASSED:
            return (
                has_execution_evidence
                and self.returncode == 0
                and self.assertion_failures == 0
                and self.uvm_errors == 0
                and self.uvm_fatals == 0
                and not self.failure_reasons
            )
        if self.expected_result == "fail" and self.outcome is Outcome.EXPECTED_FAILURE:
            return has_execution_evidence and bool(self.failure_reasons)
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "test_name": self.test_name,
            "simulator": self.simulator,
            "attempt": self.attempt,
            "seed": self.seed,
            "outcome": self.outcome.value,
            "provenance": self.provenance.value,
            "expected_result": self.expected_result,
            "expectation_met": self.expectation_met,
            "command": self.command.to_dict() if self.command else None,
            "duration_seconds": self.duration_seconds,
            "returncode": self.returncode,
            "started_at": self.started_at,
            "log_path": str(self.log_path) if self.log_path else None,
            "coverage_path": str(self.coverage_path) if self.coverage_path else None,
            "waveform_path": str(self.waveform_path) if self.waveform_path else None,
            "assertion_failures": self.assertion_failures,
            "uvm_errors": self.uvm_errors,
            "uvm_fatals": self.uvm_fatals,
            "failure_reasons": list(self.failure_reasons),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> TestResult:
        command_data = data.get("command")

        def optional_path(key: str) -> Path | None:
            value = data.get(key)
            return Path(str(value)) if value else None

        return cls(
            test_name=str(data["test_name"]),
            simulator=str(data["simulator"]),
            attempt=int(data["attempt"]),
            seed=int(data["seed"]),
            outcome=Outcome(str(data["outcome"])),
            provenance=Provenance(str(data["provenance"])),
            expected_result=str(data["expected_result"]),
            command=Command.from_dict(command_data) if command_data else None,
            duration_seconds=float(data.get("duration_seconds", 0.0)),
            returncode=(int(data["returncode"]) if data.get("returncode") is not None else None),
            started_at=str(data.get("started_at", "")),
            log_path=optional_path("log_path"),
            coverage_path=optional_path("coverage_path"),
            waveform_path=optional_path("waveform_path"),
            assertion_failures=int(data.get("assertion_failures", 0)),
            uvm_errors=int(data.get("uvm_errors", 0)),
            uvm_fatals=int(data.get("uvm_fatals", 0)),
            failure_reasons=tuple(str(value) for value in data.get("failure_reasons", [])),
        )


@dataclass(frozen=True)
class RunSummary:
    schema_version: int
    simulator: str
    provenance: Provenance
    manifest_path: Path
    output_dir: Path
    started_at: str
    finished_at: str
    stages: tuple[StageResult, ...]
    results: tuple[TestResult, ...]
    selected_tests: tuple[str, ...]

    @property
    def final_results(self) -> tuple[TestResult, ...]:
        by_name: dict[str, TestResult] = {}
        for result in self.results:
            previous = by_name.get(result.test_name)
            if previous is None or result.attempt >= previous.attempt:
                by_name[result.test_name] = result
        return tuple(by_name[name] for name in self.selected_tests if name in by_name)

    @property
    def has_complete_results(self) -> bool:
        final_names = tuple(result.test_name for result in self.final_results)
        return (
            bool(self.selected_tests)
            and final_names == self.selected_tests
            and len(set(self.selected_tests)) == len(self.selected_tests)
        )

    @property
    def successful(self) -> bool:
        return self.has_complete_results and all(
            result.expectation_met for result in self.final_results
        )

    @property
    def completed_without_failures(self) -> bool:
        """True for actual success or a fully generated dry-run plan."""

        return self.successful or self.plan_only

    @property
    def plan_only(self) -> bool:
        return self.has_complete_results and all(
            result.outcome is Outcome.DRY_RUN for result in self.final_results
        )

    def outcome_counts(self) -> dict[str, int]:
        counts = {outcome.value: 0 for outcome in Outcome}
        for result in self.final_results:
            counts[result.outcome.value] += 1
        return {key: value for key, value in counts.items() if value}

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "simulator": self.simulator,
            "provenance": self.provenance.value,
            "manifest_path": str(self.manifest_path),
            "output_dir": str(self.output_dir),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "selected_tests": list(self.selected_tests),
            "outcome_counts": self.outcome_counts(),
            "successful": self.successful,
            "completed_without_failures": self.completed_without_failures,
            "plan_only": self.plan_only,
            "stages": [stage.to_dict() for stage in self.stages],
            "results": [result.to_dict() for result in self.results],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> RunSummary:
        return cls(
            schema_version=int(data["schema_version"]),
            simulator=str(data["simulator"]),
            provenance=Provenance(str(data["provenance"])),
            manifest_path=Path(str(data["manifest_path"])),
            output_dir=Path(str(data["output_dir"])),
            started_at=str(data["started_at"]),
            finished_at=str(data["finished_at"]),
            stages=tuple(StageResult.from_dict(value) for value in data.get("stages", [])),
            results=tuple(TestResult.from_dict(value) for value in data.get("results", [])),
            selected_tests=tuple(str(value) for value in data.get("selected_tests", [])),
        )


def newest_results(results: Sequence[TestResult]) -> tuple[TestResult, ...]:
    """Return the highest attempt for each test while retaining first-seen order."""

    names: list[str] = []
    by_name: dict[str, TestResult] = {}
    for result in results:
        if result.test_name not in by_name:
            names.append(result.test_name)
        if result.test_name not in by_name or result.attempt >= by_name[result.test_name].attempt:
            by_name[result.test_name] = result
    return tuple(by_name[name] for name in names)
