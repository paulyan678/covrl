from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from rl.env import CoverageGuidedCodecEnv, EpisodeConfig
from rl.evaluate import evaluate_policy
from rl.metrics import (
    EpisodeMetric,
    StepMetric,
    fixed_budget_coverage_curve,
    normalized_area_under_curve,
    read_episode_metrics,
    write_run_metrics,
    write_training_progress,
)


class FirstLegalPolicy:
    def predict(self, observation, *, action_masks, deterministic):  # type: ignore[no-untyped-def]
        del observation, deterministic
        return int(action_masks.nonzero()[0][0]), None


class MetricsTests(unittest.TestCase):
    def test_early_termination_curve_is_padded_to_the_full_budget(self) -> None:
        steps = tuple(
            StepMetric(
                episode=0,
                step=index,
                action_index=0,
                action_name="idle",
                reward=0.0,
                cumulative_reward=0.0,
                coverage_gain=0,
                coverage_count=count,
                coverage_total=10,
                coverage_fraction=fraction,
                protocol_state="configured",
                terminated=index == 2,
                truncated=False,
                termination_reason="coverage_target" if index == 2 else None,
            )
            for index, count, fraction in ((1, 1, 0.1), (2, 3, 0.3))
        )
        episode = EpisodeMetric(
            episode=0,
            seed=1,
            strategy="test",
            steps=steps,
            final_coverage_fraction=0.3,
            total_reward=0.0,
            termination_reason="coverage_target",
        )
        self.assertEqual(fixed_budget_coverage_curve(episode, 4), (0.1, 0.3, 0.3, 0.3))
        self.assertAlmostEqual(normalized_area_under_curve(episode, 4), 0.25)

    def test_json_csv_and_summary_round_trip(self) -> None:
        config = EpisodeConfig(max_steps=4, coverage_target=1.0, stale_step_limit=None)
        episodes = evaluate_policy(
            FirstLegalPolicy(),
            lambda: CoverageGuidedCodecEnv(episode_config=config),
            episodes=2,
            seed=5,
        )
        with tempfile.TemporaryDirectory() as directory:
            paths = write_run_metrics(Path(directory), "smoke", episodes, {"mode": "mock"})
            self.assertEqual(read_episode_metrics(paths.json), episodes)
            self.assertGreater(len(paths.csv.read_text(encoding="utf-8").splitlines()), 1)
            summary = json.loads(paths.summary.read_text(encoding="utf-8"))
            self.assertEqual(summary["episode_count"], 2)
            self.assertEqual(summary["run_name"], "smoke")

    def test_training_progress_includes_compact_summary(self) -> None:
        rows = [
            {
                "training_step": 1,
                "coverage_fraction": 0.1,
                "coverage_gain": 2,
                "reward": 2.0,
            },
            {
                "training_step": 2,
                "coverage_fraction": 0.15,
                "coverage_gain": 1,
                "reward": 1.0,
            },
        ]
        with tempfile.TemporaryDirectory() as directory:
            _, _, summary_path = write_training_progress(Path(directory), rows)
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["last_training_step"], 2)
            self.assertEqual(summary["total_new_bins"], 3)
            self.assertEqual(summary["max_coverage_fraction"], 0.15)


if __name__ == "__main__":
    unittest.main()
