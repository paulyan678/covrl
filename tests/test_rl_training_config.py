from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

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


if __name__ == "__main__":
    unittest.main()
