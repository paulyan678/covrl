"""Masked policy evaluation for SB3-Contrib MaskablePPO checkpoints."""

from __future__ import annotations

import argparse
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

import numpy as np

from rl.env import CoverageGuidedCodecEnv, EpisodeConfig
from rl.metrics import EpisodeMetric, StepMetric, write_run_metrics


class MaskedPolicy(Protocol):
    def predict(
        self,
        observation: dict[str, np.ndarray],
        *,
        action_masks: np.ndarray,
        deterministic: bool,
    ) -> tuple[object, object]: ...


EnvFactory = Callable[[], CoverageGuidedCodecEnv]


def evaluate_policy(
    policy: MaskedPolicy,
    env_factory: EnvFactory,
    *,
    episodes: int,
    seed: int,
    deterministic: bool = True,
    strategy: str = "masked_ppo",
) -> tuple[EpisodeMetric, ...]:
    if episodes <= 0:
        raise ValueError("episodes must be positive")
    env = env_factory()
    results: list[EpisodeMetric] = []
    for episode_index in range(episodes):
        episode_seed = seed + episode_index
        observation, _ = env.reset(seed=episode_seed)
        cumulative_reward = 0.0
        steps: list[StepMetric] = []
        reason: str | None = None
        while True:
            mask = env.action_masks()
            prediction, _ = policy.predict(
                observation,
                action_masks=mask,
                deterministic=deterministic,
            )
            action_index = _scalar_action(prediction)
            if action_index < 0 or action_index >= len(mask) or not bool(mask[action_index]):
                raise RuntimeError("policy selected an action excluded by its inference mask")
            observation, reward, terminated, truncated, info = env.step(action_index)
            cumulative_reward += reward
            reason_value = info.get("termination_reason")
            reason = str(reason_value) if reason_value is not None else None
            steps.append(
                StepMetric(
                    episode=episode_index,
                    step=int(info["step"]),
                    action_index=action_index,
                    action_name=env.catalog[action_index].name,
                    reward=reward,
                    cumulative_reward=cumulative_reward,
                    coverage_gain=int(info["coverage_gain"]),
                    coverage_count=int(info["coverage_count"]),
                    coverage_total=int(info["coverage_total"]),
                    coverage_fraction=float(info["coverage_fraction"]),
                    protocol_state=str(info["protocol_state"]),
                    terminated=terminated,
                    truncated=truncated,
                    termination_reason=reason,
                )
            )
            if terminated or truncated:
                break
        final_coverage = steps[-1].coverage_fraction if steps else 0.0
        results.append(
            EpisodeMetric(
                episode=episode_index,
                seed=episode_seed,
                strategy=strategy,
                steps=tuple(steps),
                final_coverage_fraction=final_coverage,
                total_reward=cumulative_reward,
                termination_reason=reason,
            )
        )
    return tuple(results)


def _scalar_action(value: object) -> int:
    array = np.asarray(value)
    if array.size != 1:
        raise RuntimeError("policy returned a non-scalar action")
    return int(array.reshape(-1)[0])


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True, help="MaskablePPO .zip checkpoint")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/rl/evaluation"))
    parser.add_argument("--episodes", type=int, default=10)
    parser.add_argument("--seed", type=int, default=2024)
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--coverage-target", type=float, default=0.90)
    parser.add_argument(
        "--stochastic",
        action="store_true",
        help="sample from the masked policy instead of deterministic prediction",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        from sb3_contrib import MaskablePPO
    except ImportError as exc:  # pragma: no cover - depends on optional install
        raise SystemExit("install the RL extra: python -m pip install -e '.[rl]'") from exc
    model = MaskablePPO.load(args.model)
    episode_config = EpisodeConfig(
        max_steps=args.max_steps,
        coverage_target=args.coverage_target,
    )
    episodes = evaluate_policy(
        model,
        lambda: CoverageGuidedCodecEnv(episode_config=episode_config),
        episodes=args.episodes,
        seed=args.seed,
        deterministic=not args.stochastic,
    )
    paths = write_run_metrics(
        args.output_dir,
        "masked_ppo_evaluation",
        episodes,
        metadata={"model": str(args.model), "seed": args.seed},
    )
    print(paths.summary)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
