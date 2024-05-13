"""Coverage database discovery and adapter-specific merge execution."""

from __future__ import annotations

import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from regression.adapters.base import SimulatorAdapter
from regression.models import Outcome, Provenance, RunSummary, StageResult
from regression.process import ProcessExecutor


@dataclass(frozen=True)
class CoverageMergeResult:
    schema_version: int
    simulator: str
    provenance: Provenance
    outcome: Outcome
    databases: tuple[Path, ...]
    merged_path: Path
    report_dir: Path
    stages: tuple[StageResult, ...]
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "simulator": self.simulator,
            "provenance": self.provenance.value,
            "outcome": self.outcome.value,
            "databases": [str(path) for path in self.databases],
            "merged_path": str(self.merged_path),
            "report_dir": str(self.report_dir),
            "reason": self.reason,
            "stages": [stage.to_dict() for stage in self.stages],
        }


def coverage_databases(summary: RunSummary, *, existing_only: bool = True) -> tuple[Path, ...]:
    databases: list[Path] = []
    for result in summary.final_results:
        if not result.outcome.is_success:
            continue
        path = result.coverage_path
        if path and (not existing_only or path.exists()) and path not in databases:
            databases.append(path)
    return tuple(databases)


def merged_database_path(simulator: str, output_dir: Path) -> Path:
    suffixes = {"vcs": ".vdb", "questa": ".ucdb", "mock": ".json"}
    try:
        suffix = suffixes[simulator]
    except KeyError as error:
        raise ValueError(f"{simulator} does not support coverage merging") from error
    return output_dir / f"merged-coverage{suffix}"


def merge_coverage(
    adapter: SimulatorAdapter,
    databases: tuple[Path, ...],
    output_dir: Path,
    *,
    dry_run: bool = False,
    executor: ProcessExecutor | None = None,
    console: Callable[[str], None] | None = None,
) -> CoverageMergeResult:
    """Merge coverage with provenance-preserving dry-run behavior."""

    if not databases:
        raise ValueError("no coverage databases were provided")
    if not dry_run:
        missing = tuple(path for path in databases if not path.exists())
        if missing:
            raise ValueError(
                "coverage database(s) do not exist: " + ", ".join(str(path) for path in missing)
            )
    output_dir = output_dir.expanduser().resolve()
    report_dir = output_dir / "report"
    output_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)
    merged_path = merged_database_path(adapter.name, output_dir)
    commands = adapter.merge_commands(databases, merged_path, report_dir)
    provenance = Provenance.DRY_RUN if dry_run else adapter.provenance
    emit = console or (lambda _message: None)
    if not dry_run:
        availability = adapter.coverage_availability()
        if not availability.available:
            return CoverageMergeResult(
                schema_version=1,
                simulator=adapter.name,
                provenance=provenance,
                outcome=Outcome.UNAVAILABLE,
                databases=databases,
                merged_path=merged_path,
                report_dir=report_dir,
                stages=(),
                reason=availability.detail,
            )
    process_executor = executor or ProcessExecutor()
    if not dry_run and merged_path.exists():
        if merged_path.is_dir():
            shutil.rmtree(merged_path)
        else:
            merged_path.unlink()
    stages: list[StageResult] = []
    for index, command in enumerate(commands, start=1):
        emit(f"[{'dry_run' if dry_run else adapter.provenance.value}] merge: {command.display()}")
        name = f"coverage-{index}"
        if dry_run:
            stages.append(
                StageResult(name, Outcome.DRY_RUN, command, reason="command generated only")
            )
            continue
        process = process_executor.run(command, timeout_seconds=900.0)
        if process.timed_out:
            stages.append(
                StageResult(
                    name,
                    Outcome.TIMEOUT,
                    command,
                    process.duration_seconds,
                    process.returncode,
                    "coverage command timed out",
                )
            )
            break
        if process.returncode != 0:
            stages.append(
                StageResult(
                    name,
                    Outcome.ERROR,
                    command,
                    process.duration_seconds,
                    process.returncode,
                    f"coverage command exited with status {process.returncode}",
                )
            )
            break
        stages.append(
            StageResult(
                name,
                Outcome.PASSED,
                command,
                process.duration_seconds,
                process.returncode,
            )
        )
    outcome = Outcome.DRY_RUN if dry_run else Outcome.PASSED
    if stages and not stages[-1].outcome.is_success:
        outcome = stages[-1].outcome
    if not dry_run and outcome is Outcome.PASSED and not merged_path.exists():
        outcome = Outcome.ERROR
        reason = f"coverage tool did not produce {merged_path}"
    else:
        reason = ""
    return CoverageMergeResult(
        schema_version=1,
        simulator=adapter.name,
        provenance=provenance,
        outcome=outcome,
        databases=databases,
        merged_path=merged_path,
        report_dir=report_dir,
        stages=tuple(stages),
        reason=reason,
    )
