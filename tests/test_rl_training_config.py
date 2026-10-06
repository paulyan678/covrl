from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from rl.checkpoint import load_verified_policy
from rl.env import CoverageGuidedCodecEnv, EpisodeConfig
from rl.evaluate import evaluate_policy
from rl.train import TrainingConfig, train_maskable_ppo


class TrainingConfigTests(unittest.TestCase):
    def test_invalid_minibatch_shape_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "divisible"):
            TrainingConfig(n_steps=3, batch_size=2)

    @unittest.skipUnless(
        os.environ.get("RUN_RL_TRAINING_SMOKE") == "1",
        "set RUN_RL_TRAINING_SMOKE=1 after installing the RL extra",
    )
    def test_short_maskable_ppo_training(self) -> None:
        config = TrainingConfig(
            total_timesteps=128,
            n_steps=64,
            batch_size=32,
            checkpoint_frequency=64,
            evaluation_episodes=1,
            max_episode_steps=16,
        )
        with tempfile.TemporaryDirectory() as directory:
            artifacts = train_maskable_ppo(config, Path(directory))
            self.assertTrue(artifacts.final_model.is_file())
            self.assertTrue(artifacts.metadata.is_file())
            episode_config = EpisodeConfig(max_steps=16)
            env = CoverageGuidedCodecEnv(episode_config=episode_config)
            self.addCleanup(env.close)
            # Check periodic as well as final checkpoints through the public loader.
            paths = [artifacts.final_model, *Path(directory).glob("checkpoints/*.zip")]
            self.assertEqual(len(paths), 3)
            for path in paths:
                policy = load_verified_policy(path, env)
                result = evaluate_policy(
                    policy,
                    lambda: CoverageGuidedCodecEnv(episode_config=episode_config),
                    episodes=1,
                    seed=2024,
                )
                self.assertEqual(len(result), 1)


if __name__ == "__main__":
    unittest.main()
