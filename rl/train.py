"""Train action-masked PPO against the deterministic mock coverage backend."""

from __future__ import annotations

import argparse
import random
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from rl.actions import DEFAULT_ACTION_CATALOG
from rl.env import GYMNASIUM_AVAILABLE, CoverageGuidedCodecEnv, EpisodeConfig


@dataclass(frozen=True, slots=True)
class TrainingConfig:
    total_timesteps: int = 20_000
    seed: int = 2024
    max_episode_steps: int = 200
    coverage_target: float = 0.90
    learning_rate: float = 3e-4
    n_steps: int = 128
    batch_size: int = 64
    gamma: float = 0.99
    device: str = "auto"

    def __post_init__(self) -> None:
        if self.total_timesteps <= 0:
            raise ValueError("total_timesteps must be positive")
        if self.max_episode_steps <= 0:
            raise ValueError("max_episode_steps must be positive")
        if not 0.0 < self.coverage_target <= 1.0:
            raise ValueError("coverage_target must be in (0, 1]")
        if self.n_steps <= 0 or self.batch_size <= 0:
            raise ValueError("n_steps and batch_size must be positive")
        if self.n_steps % self.batch_size != 0:
            raise ValueError("n_steps must be divisible by batch_size for one environment")
        if not 0.0 < self.gamma <= 1.0:
            raise ValueError("gamma must be in (0, 1]")


@dataclass(frozen=True, slots=True)
class TrainingArtifacts:
    final_model: Path
    output_dir: Path


def train_maskable_ppo(config: TrainingConfig, output_dir: Path) -> TrainingArtifacts:
    """Train MaskablePPO; optional neural dependencies are imported on demand."""

    if not GYMNASIUM_AVAILABLE:
        raise RuntimeError("Gymnasium is required; install the project's RL extra")
    try:
        import torch
        from sb3_contrib import MaskablePPO
    except ImportError as error:  # pragma: no cover - depends on optional install
        raise RuntimeError("install the RL extra: python -m pip install -e '.[rl]'") from error

    random.seed(config.seed)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    output_dir = output_dir.expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    DEFAULT_ACTION_CATALOG.write_json(output_dir / "action_catalog.json")

    episode_config = EpisodeConfig(
        max_steps=config.max_episode_steps,
        coverage_target=config.coverage_target,
    )
    env = CoverageGuidedCodecEnv(episode_config=episode_config)
    env.reset(seed=config.seed)
    model = MaskablePPO(
        "MultiInputPolicy",
        env,
        learning_rate=config.learning_rate,
        n_steps=config.n_steps,
        batch_size=config.batch_size,
        gamma=config.gamma,
        seed=config.seed,
        device=config.device,
        verbose=1,
    )
    # MaskablePPO calls env.action_masks() before each rollout action.
    model.learn(total_timesteps=config.total_timesteps)
    final_stem = output_dir / "maskable_ppo_final"
    model.save(final_stem)
    env.close()
    return TrainingArtifacts(final_model=final_stem.with_suffix(".zip"), output_dir=output_dir)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/rl/training"))
    parser.add_argument("--timesteps", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=2024)
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--coverage-target", type=float, default=0.90)
    parser.add_argument("--device", default="auto")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = TrainingConfig(
        total_timesteps=args.timesteps,
        seed=args.seed,
        max_episode_steps=args.max_steps,
        coverage_target=args.coverage_target,
        device=args.device,
    )
    try:
        artifacts = train_maskable_ppo(config, args.output_dir)
    except RuntimeError as error:
        raise SystemExit(str(error)) from error
    print(artifacts.final_model)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
