"""Portable JSON/CSV metrics for training, evaluation, and comparison."""

from __future__ import annotations

import csv
import json
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field
from pathlib import Path
from statistics import mean


@dataclass(frozen=True, slots=True)
class StepMetric:
    episode: int
    step: int
    action_index: int
    action_name: str
    reward: float
    cumulative_reward: float
    coverage_gain: int
    coverage_count: int
    coverage_total: int
    coverage_fraction: float
    protocol_state: str
    terminated: bool
    truncated: bool
    termination_reason: str | None = None


@dataclass(frozen=True, slots=True)
class EpisodeMetric:
    episode: int
    seed: int
    strategy: str
    steps: tuple[StepMetric, ...]
    final_coverage_fraction: float
    total_reward: float
    termination_reason: str | None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["steps"] = [asdict(step) for step in self.steps]
        return payload


@dataclass(frozen=True, slots=True)
class MetricsPaths:
    json: Path
    csv: Path
    summary: Path


@dataclass(frozen=True, slots=True)
class RunSummary:
    run_name: str
    episode_count: int
    mean_final_coverage: float
    min_final_coverage: float
    max_final_coverage: float
    mean_reward: float
    mean_steps: float
    termination_reasons: Mapping[str, int] = field(default_factory=dict)


def _metric_float(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"training metric {field_name!r} must be numeric")
    return float(value)


def _metric_int(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"training metric {field_name!r} must be an integer")
    return value


def summarize(run_name: str, episodes: Sequence[EpisodeMetric]) -> RunSummary:
    if not episodes:
        raise ValueError("at least one episode is required")
    finals = [episode.final_coverage_fraction for episode in episodes]
    rewards = [episode.total_reward for episode in episodes]
    lengths = [len(episode.steps) for episode in episodes]
    reasons: dict[str, int] = {}
    for episode in episodes:
        reason = episode.termination_reason or "unknown"
        reasons[reason] = reasons.get(reason, 0) + 1
    return RunSummary(
        run_name=run_name,
        episode_count=len(episodes),
        mean_final_coverage=mean(finals),
        min_final_coverage=min(finals),
        max_final_coverage=max(finals),
        mean_reward=mean(rewards),
        mean_steps=mean(lengths),
        termination_reasons=dict(sorted(reasons.items())),
    )


def write_run_metrics(
    output_dir: Path,
    run_name: str,
    episodes: Sequence[EpisodeMetric],
    metadata: Mapping[str, object] | None = None,
) -> MetricsPaths:
    """Write complete metrics and a compact summary in deterministic formats."""

    output_dir.mkdir(parents=True, exist_ok=True)
    summary = summarize(run_name, episodes)
    json_path = output_dir / f"{run_name}.json"
    csv_path = output_dir / f"{run_name}.csv"
    summary_path = output_dir / f"{run_name}.summary.json"
    payload = {
        "schema_version": 1,
        "run_name": run_name,
        "metadata": dict(metadata or {}),
        "episodes": [episode.to_dict() for episode in episodes],
    }
    json_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        fieldnames = [field.name for field in StepMetric.__dataclass_fields__.values()]
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for episode in episodes:
            for step in episode.steps:
                writer.writerow(asdict(step))
    summary_path.write_text(
        json.dumps(asdict(summary), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return MetricsPaths(json=json_path, csv=csv_path, summary=summary_path)


def write_training_progress(
    output_dir: Path,
    rows: Iterable[Mapping[str, object]],
) -> tuple[Path, Path, Path]:
    """Persist callback rows without requiring pandas or TensorBoard."""

    output_dir.mkdir(parents=True, exist_ok=True)
    materialized = [dict(row) for row in rows]
    json_path = output_dir / "training_progress.json"
    csv_path = output_dir / "training_progress.csv"
    summary_path = output_dir / "training_progress.summary.json"
    json_path.write_text(
        json.dumps(materialized, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    fieldnames = sorted({key for row in materialized for key in row})
    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        if fieldnames:
            writer = csv.DictWriter(handle, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(materialized)
    coverage_values = [
        _metric_float(row["coverage_fraction"], "coverage_fraction") for row in materialized
    ]
    reward_values = [_metric_float(row.get("reward", 0.0), "reward") for row in materialized]
    training_steps = [
        _metric_int(row.get("training_step", 0), "training_step") for row in materialized
    ]
    summary_payload = {
        "samples": len(materialized),
        "last_training_step": max(training_steps, default=0),
        "final_coverage_fraction": coverage_values[-1] if coverage_values else 0.0,
        "max_coverage_fraction": max(coverage_values, default=0.0),
        "mean_step_reward": mean(reward_values) if reward_values else 0.0,
        "total_new_bins": sum(
            _metric_int(row.get("coverage_gain", 0), "coverage_gain") for row in materialized
        ),
    }
    summary_path.write_text(
        json.dumps(summary_payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return json_path, csv_path, summary_path


def read_episode_metrics(path: Path) -> tuple[EpisodeMetric, ...]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema_version") != 1:
        raise ValueError("unsupported metrics schema_version")
    episodes: list[EpisodeMetric] = []
    for raw_episode in payload.get("episodes", []):
        raw_steps = raw_episode.pop("steps")
        steps = tuple(StepMetric(**raw_step) for raw_step in raw_steps)
        episodes.append(EpisodeMetric(steps=steps, **raw_episode))
    return tuple(episodes)


def normalized_area_under_curve(episode: EpisodeMetric, budget: int | None = None) -> float:
    """Mean covered fraction, optionally padded to a fixed comparison budget."""

    if budget is not None:
        values = fixed_budget_coverage_curve(episode, budget)
    else:
        values = tuple(step.coverage_fraction for step in episode.steps)
    if not values:
        return 0.0
    return mean(values)


def fixed_budget_coverage_curve(episode: EpisodeMetric, budget: int) -> tuple[float, ...]:
    """Pad terminal coverage so every comparison curve spans the same decision budget."""

    if budget <= 0:
        raise ValueError("budget must be positive")
    values = [step.coverage_fraction for step in episode.steps]
    last = values[-1] if values else 0.0
    return tuple((values + [last] * budget)[:budget])
