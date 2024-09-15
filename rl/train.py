"""Train action-masked PPO against the deterministic mock coverage backend."""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import asdict, dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

import numpy as np

from rl.actions import DEFAULT_ACTION_CATALOG
from rl.env import GYMNASIUM_AVAILABLE, CoverageGuidedCodecEnv, EpisodeConfig
from rl.evaluate import evaluate_policy
from rl.metrics import write_run_metrics, write_training_progress


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
    checkpoint_frequency: int = 5_000
    evaluation_episodes: int = 5
    device: str = "auto"

    def __post_init__(self) -> None:
        if self.total_timesteps <= 0:
            raise ValueError("total_timesteps must be positive")
        if self.n_steps <= 0 or self.batch_size <= 0:
            raise ValueError("n_steps and batch_size must be positive")
        if self.n_steps % self.batch_size != 0:
            raise ValueError("n_steps must be divisible by batch_size for one environment")
        if self.checkpoint_frequency <= 0:
            raise ValueError("checkpoint_frequency must be positive")


@dataclass(frozen=True, slots=True)
class TrainingArtifacts:
    final_model: Path
    output_dir: Path
    metadata: Path


def train_maskable_ppo(config: TrainingConfig, output_dir: Path) -> TrainingArtifacts:
    """Train MaskablePPO; optional heavy dependencies are imported on demand."""

    if not GYMNASIUM_AVAILABLE:
        raise RuntimeError("Gymnasium is required for training; install the project's RL extra")
    try:
        import torch
        from sb3_contrib import MaskablePPO
        from stable_baselines3.common.callbacks import (
            BaseCallback,
            CallbackList,
            CheckpointCallback,
        )
    except ImportError as exc:  # pragma: no cover - depends on optional install
        raise RuntimeError("install the RL extra: python -m pip install -e '.[rl]'") from exc

    random.seed(config.seed)
    np.random.seed(config.seed)
    torch.manual_seed(config.seed)
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_dir = output_dir / "checkpoints"
    metrics_dir = output_dir / "metrics"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    DEFAULT_ACTION_CATALOG.write_json(output_dir / "action_catalog.json")

    episode_config = EpisodeConfig(
        max_steps=config.max_episode_steps,
        coverage_target=config.coverage_target,
    )
    env = CoverageGuidedCodecEnv(episode_config=episode_config)
    env.reset(seed=config.seed)
    rows: list[dict[str, object]] = []

    class TrainingProgressCallback(BaseCallback):
        def _on_step(self) -> bool:
            infos = self.locals.get("infos", [])
            rewards = np.asarray(self.locals.get("rewards", []), dtype=float).reshape(-1)
            actions = np.asarray(self.locals.get("actions", []), dtype=int).reshape(-1)
            for index, info in enumerate(infos):
                row: dict[str, object] = {
                    "training_step": int(self.num_timesteps),
                    "environment": index,
                    "coverage_fraction": float(info.get("coverage_fraction", 0.0)),
                    "coverage_gain": int(info.get("coverage_gain", 0)),
                    "episode_reward": float(info.get("episode_reward", 0.0)),
                    "protocol_state": str(info.get("protocol_state", "unknown")),
                    "termination_reason": info.get("termination_reason"),
                }
                if index < len(rewards):
                    row["reward"] = float(rewards[index])
                if index < len(actions):
                    row["action_index"] = int(actions[index])
                rows.append(row)
            return True

    checkpoint_callback = CheckpointCallback(
        save_freq=config.checkpoint_frequency,
        save_path=str(checkpoint_dir),
        name_prefix="maskable_ppo",
    )
    callbacks = CallbackList([checkpoint_callback, TrainingProgressCallback()])
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
    # MaskablePPO queries env.action_masks() before every sampled action.
    model.learn(total_timesteps=config.total_timesteps, callback=callbacks)
    final_stem = output_dir / "maskable_ppo_final"
    model.save(final_stem)
    final_model = final_stem.with_suffix(".zip")
    write_training_progress(metrics_dir, rows)

    evaluation = evaluate_policy(
        model,
        lambda: CoverageGuidedCodecEnv(episode_config=episode_config),
        episodes=config.evaluation_episodes,
        seed=config.seed + 10_000,
        deterministic=True,
    )
    write_run_metrics(
        metrics_dir,
        "post_training_evaluation",
        evaluation,
        metadata={"training_seed": config.seed},
    )
    metadata_path = output_dir / "training_metadata.json"
    metadata = {
        "schema_version": 1,
        "algorithm": "sb3_contrib.MaskablePPO",
        "action_masking": "training_and_inference",
        "backend": "deterministic_mock",
        "catalog_digest": DEFAULT_ACTION_CATALOG.digest,
        "coverage_bin_digest": env.backend.bin_digest,
        "config": asdict(config),
        "dependencies": {
            package: _package_version(package)
            for package in ("gymnasium", "stable-baselines3", "sb3-contrib", "torch")
        },
        "final_model": str(final_model),
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    env.close()
    return TrainingArtifacts(
        final_model=final_model,
        output_dir=output_dir,
        metadata=metadata_path,
    )


def _package_version(package: str) -> str:
    try:
        return version(package)
    except PackageNotFoundError:
        return "not-installed"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/rl/training"))
    parser.add_argument("--timesteps", type=int, default=20_000)
    parser.add_argument("--seed", type=int, default=2024)
    parser.add_argument("--max-steps", type=int, default=200)
    parser.add_argument("--coverage-target", type=float, default=0.90)
    parser.add_argument("--checkpoint-frequency", type=int, default=5_000)
    parser.add_argument("--evaluation-episodes", type=int, default=5)
    parser.add_argument("--device", default="auto")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = TrainingConfig(
        total_timesteps=args.timesteps,
        seed=args.seed,
        max_episode_steps=args.max_steps,
        coverage_target=args.coverage_target,
        checkpoint_frequency=args.checkpoint_frequency,
        evaluation_episodes=args.evaluation_episodes,
        device=args.device,
    )
    try:
        artifacts = train_maskable_ppo(config, args.output_dir)
    except RuntimeError as exc:
        raise SystemExit(str(exc)) from exc
    print(artifacts.final_model)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
