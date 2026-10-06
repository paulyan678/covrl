"""Reproducible masked-PPO versus constrained-random comparison."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean

import numpy as np

from rl.checkpoint import load_verified_policy
from rl.env import CoverageGuidedCodecEnv, EpisodeConfig
from rl.evaluate import MaskedPolicy, evaluate_policy
from rl.metrics import (
    EpisodeMetric,
    fixed_budget_coverage_curve,
    normalized_area_under_curve,
    write_run_metrics,
)


class UniformMaskedPolicy:
    """Uniform constrained-random baseline over the exact PPO action mask."""

    def __init__(self, seed: int) -> None:
        self._rng = np.random.default_rng(seed)

    def predict(
        self,
        observation: dict[str, np.ndarray],
        *,
        action_masks: np.ndarray,
        deterministic: bool,
    ) -> tuple[int, None]:
        del observation, deterministic
        legal = np.flatnonzero(action_masks)
        if len(legal) == 0:
            raise RuntimeError("constrained-random policy received an empty mask")
        return int(self._rng.choice(legal)), None


@dataclass(frozen=True, slots=True)
class StrategySummary:
    mean_final_coverage: float
    mean_normalized_auc: float
    mean_reward: float
    mean_steps: float


@dataclass(frozen=True, slots=True)
class ComparisonSummary:
    seed: int
    episodes: int
    budget: int
    ppo: StrategySummary
    constrained_random: StrategySummary
    final_coverage_delta: float
    normalized_auc_delta: float
    mean_ppo_curve: tuple[float, ...]
    mean_random_curve: tuple[float, ...]


def compare_policy_to_random(
    ppo_policy: MaskedPolicy,
    env_factory: Callable[[], CoverageGuidedCodecEnv],
    *,
    episodes: int,
    seed: int,
    budget: int,
) -> tuple[ComparisonSummary, tuple[EpisodeMetric, ...], tuple[EpisodeMetric, ...]]:
    """Evaluate both strategies with identical episode seeds and step budgets."""

    if budget <= 0:
        raise ValueError("budget must be positive")
    probe = env_factory()
    try:
        configured_budget = probe.episode_config.max_steps
    finally:
        probe.close()
    if configured_budget != budget:
        raise ValueError(
            f"environment max_steps ({configured_budget}) must equal comparison budget ({budget})"
        )
    ppo_episodes = evaluate_policy(
        ppo_policy,
        env_factory,
        episodes=episodes,
        seed=seed,
        deterministic=True,
        strategy="masked_ppo",
    )
    random_episodes = evaluate_policy(
        UniformMaskedPolicy(seed),
        env_factory,
        episodes=episodes,
        seed=seed,
        deterministic=False,
        strategy="constrained_random",
    )
    ppo_summary = _strategy_summary(ppo_episodes, budget)
    random_summary = _strategy_summary(random_episodes, budget)
    result = ComparisonSummary(
        seed=seed,
        episodes=episodes,
        budget=budget,
        ppo=ppo_summary,
        constrained_random=random_summary,
        final_coverage_delta=(ppo_summary.mean_final_coverage - random_summary.mean_final_coverage),
        normalized_auc_delta=(ppo_summary.mean_normalized_auc - random_summary.mean_normalized_auc),
        mean_ppo_curve=_mean_curve(ppo_episodes, budget),
        mean_random_curve=_mean_curve(random_episodes, budget),
    )
    return result, ppo_episodes, random_episodes


def _strategy_summary(episodes: tuple[EpisodeMetric, ...], budget: int) -> StrategySummary:
    if not episodes:
        raise ValueError("at least one episode is required")
    return StrategySummary(
        mean_final_coverage=mean(item.final_coverage_fraction for item in episodes),
        mean_normalized_auc=mean(normalized_area_under_curve(item, budget) for item in episodes),
        mean_reward=mean(item.total_reward for item in episodes),
        mean_steps=mean(len(item.steps) for item in episodes),
    )


def _mean_curve(episodes: tuple[EpisodeMetric, ...], budget: int) -> tuple[float, ...]:
    curves: list[list[float]] = []
    for episode in episodes:
        curves.append(list(fixed_budget_coverage_curve(episode, budget)))
    return tuple(mean(curve[step] for curve in curves) for step in range(budget))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/rl/comparison"))
    parser.add_argument("--episodes", type=int, default=20)
    parser.add_argument("--budget", type=int, default=200)
    parser.add_argument("--seed", type=int, default=2024)
    parser.add_argument("--coverage-target", type=float, default=0.99)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    episode_config = EpisodeConfig(
        max_steps=args.budget,
        coverage_target=args.coverage_target,
        stale_step_limit=None,
    )

    validation_env = CoverageGuidedCodecEnv(episode_config=episode_config)
    try:
        model = load_verified_policy(args.model, validation_env)
    except (ValueError, OSError, RuntimeError) as exc:
        raise SystemExit(str(exc)) from exc
    finally:
        validation_env.close()

    def factory() -> CoverageGuidedCodecEnv:
        return CoverageGuidedCodecEnv(episode_config=episode_config)

    summary, ppo_episodes, random_episodes = compare_policy_to_random(
        model,
        factory,
        episodes=args.episodes,
        seed=args.seed,
        budget=args.budget,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    write_run_metrics(args.output_dir, "ppo", ppo_episodes, metadata={"seed": args.seed})
    write_run_metrics(
        args.output_dir,
        "constrained_random",
        random_episodes,
        metadata={"seed": args.seed},
    )
    summary_path = args.output_dir / "comparison.json"
    summary_path.write_text(
        json.dumps(asdict(summary), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(summary_path)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
