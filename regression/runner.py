"""Compile, elaborate, and run simulator-neutral regression plans."""

from __future__ import annotations

import os
import subprocess
import time
from collections.abc import Callable, Iterable
from datetime import datetime, timezone
from pathlib import Path

from regression.adapters import create_adapter
from regression.config import Manifest, TestSpec
from regression.models import (
    Command,
    Outcome,
    Provenance,
    RunSummary,
    StageResult,
    TestResult,
)

Console = Callable[[str], None]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class RegressionRunner:
    """Staged compile/elaborate/run controller with dry-run provenance."""

    def __init__(
        self,
        manifest: Manifest,
        simulator: str,
        output_dir: Path,
        *,
        dry_run: bool = False,
        console: Console | None = None,
    ) -> None:
        if simulator not in manifest.simulators:
            choices = ", ".join(sorted(manifest.simulators))
            raise ValueError(f"simulator {simulator!r} is not configured; choose: {choices}")
        self.manifest = manifest
        self.simulator = simulator
        self.output_dir = output_dir.expanduser().resolve()
        self.dry_run = dry_run
        self.console = console or (lambda _message: None)
        self.adapter = create_adapter(
            simulator, manifest.project_root, manifest.simulators[simulator]
        )

    @property
    def provenance(self) -> Provenance:
        return Provenance.DRY_RUN if self.dry_run else self.adapter.provenance

    def run_names(self, names: Iterable[str]) -> RunSummary:
        return self.run(self.manifest.require_tests(tuple(names)))

    def run(self, tests: Iterable[TestSpec]) -> RunSummary:
        selected = tuple(tests)
        if not selected:
            raise ValueError("at least one test must be selected")
        started_at = _utc_now()
        build_dir = self.output_dir / "build" / self.simulator
        build_dir.mkdir(parents=True, exist_ok=True)
        stages: list[StageResult] = []
        results: list[TestResult] = []

        supported = tuple(test for test in selected if self.adapter.supports(test))
        for test in selected:
            if test not in supported:
                results.append(
                    self._nonexecution_result(
                        test, Outcome.UNSUPPORTED, self.adapter.unsupported_reason(test)
                    )
                )

        if supported and not self.dry_run:
            availability = self.adapter.regression_availability()
            if not availability.available:
                results.extend(
                    self._nonexecution_result(test, Outcome.UNAVAILABLE, availability.detail)
                    for test in supported
                )
                return self._summary(started_at, selected, stages, results)

        stage_commands = (
            *(("compile", command) for command in self.adapter.compile_commands(build_dir)),
            *(("elaborate", command) for command in self.adapter.elaborate_commands(build_dir)),
        )
        for stage_name, command in stage_commands:
            stage = self._run_stage(stage_name, command)
            stages.append(stage)
            if not stage.outcome.is_success:
                results.extend(
                    self._nonexecution_result(
                        test,
                        Outcome.ERROR,
                        f"{stage_name} stage failed: {stage.reason}",
                    )
                    for test in supported
                )
                return self._summary(started_at, selected, stages, results)

        for index, test in enumerate(supported):
            seed = test.seed.value or (self.manifest.defaults.seed_base + index)
            results.append(self._run_one(test, seed, build_dir))
        return self._summary(started_at, selected, stages, results)

    def _run_stage(self, name: str, command: Command) -> StageResult:
        self.console(f"[{self.provenance.value}] {name}: {command.display()}")
        if self.dry_run:
            return StageResult(name, Outcome.DRY_RUN, command, reason="command generated only")
        try:
            returncode, duration = self._execute(command)
        except OSError as error:
            return StageResult(
                name, Outcome.ERROR, command, reason=f"could not launch command: {error}"
            )
        if returncode != 0:
            return StageResult(
                name,
                Outcome.ERROR,
                command,
                duration,
                returncode,
                f"exit status {returncode}",
            )
        return StageResult(name, Outcome.PASSED, command, duration, returncode)

    def _run_one(self, test: TestSpec, seed: int, build_dir: Path) -> TestResult:
        test_dir = self.output_dir / "tests" / test.name / "attempt-1"
        test_dir.mkdir(parents=True, exist_ok=True)
        plan = self.adapter.test_plan(test, seed, build_dir, test_dir)
        self.console(f"[{self.provenance.value}] run: {plan.command.display()}")
        if self.dry_run:
            return TestResult(
                test_name=test.name,
                simulator=self.simulator,
                attempt=1,
                seed=seed,
                outcome=Outcome.DRY_RUN,
                provenance=self.provenance,
                expected_result=test.expected_result,
                command=plan.command,
                log_path=plan.command.log_path,
                coverage_path=plan.coverage_path,
                waveform_path=plan.waveform_path,
                failure_reasons=("command generated only; simulator was not executed",),
            )
        started_at = _utc_now()
        try:
            returncode, duration = self._execute(plan.command)
            if test.expected_result == "fail":
                outcome = Outcome.EXPECTED_FAILURE if returncode else Outcome.UNEXPECTED_PASS
            else:
                outcome = Outcome.PASSED if returncode == 0 else Outcome.FAILED
            reasons = () if outcome.is_success else (f"exit status {returncode}",)
        except OSError as error:
            returncode = None
            duration = 0.0
            outcome = Outcome.ERROR
            reasons = (f"could not launch test command: {error}",)
        return TestResult(
            test_name=test.name,
            simulator=self.simulator,
            attempt=1,
            seed=seed,
            outcome=outcome,
            provenance=self.provenance,
            expected_result=test.expected_result,
            command=plan.command,
            duration_seconds=duration,
            returncode=returncode,
            started_at=started_at,
            log_path=plan.command.log_path,
            coverage_path=plan.coverage_path,
            waveform_path=plan.waveform_path,
            failure_reasons=reasons,
        )

    @staticmethod
    def _execute(command: Command) -> tuple[int, float]:
        command.cwd.mkdir(parents=True, exist_ok=True)
        log_path = command.log_path or command.cwd / "process.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        environment = os.environ.copy()
        environment.update(command.env)
        start = time.monotonic()
        with log_path.open("w", encoding="utf-8") as log:
            log.write(f"$ {command.display()}\n")
            log.flush()
            completed = subprocess.run(  # noqa: S603 - shell-free adapter argv
                list(command.argv),
                cwd=command.cwd,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
        return completed.returncode, time.monotonic() - start

    def _nonexecution_result(
        self, test: TestSpec, outcome: Outcome, reason: str
    ) -> TestResult:
        seed = test.seed.value or self.manifest.defaults.seed_base
        return TestResult(
            test_name=test.name,
            simulator=self.simulator,
            attempt=1,
            seed=seed,
            outcome=outcome,
            provenance=self.provenance,
            expected_result=test.expected_result,
            command=None,
            started_at=_utc_now(),
            failure_reasons=(reason,),
        )

    def _summary(
        self,
        started_at: str,
        selected: tuple[TestSpec, ...],
        stages: list[StageResult],
        results: list[TestResult],
    ) -> RunSummary:
        selected_names = tuple(test.name for test in selected)
        order = {name: index for index, name in enumerate(selected_names)}
        ordered = tuple(sorted(results, key=lambda item: order[item.test_name]))
        return RunSummary(
            schema_version=1,
            simulator=self.simulator,
            provenance=self.provenance,
            manifest_path=self.manifest.path,
            output_dir=self.output_dir,
            started_at=started_at,
            finished_at=_utc_now(),
            stages=tuple(stages),
            results=ordered,
            selected_tests=selected_names,
        )
