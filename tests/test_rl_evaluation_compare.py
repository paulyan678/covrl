from __future__ import annotations

import unittest

from rl.compare import compare_policy_to_random
from rl.env import CoverageGuidedCodecEnv, EpisodeConfig
from rl.evaluate import evaluate_policy


class FirstLegalPolicy:
    def __init__(self) -> None:
        self.masks_seen = []

    def predict(self, observation, *, action_masks, deterministic):  # type: ignore[no-untyped-def]
        del observation, deterministic
        self.masks_seen.append(action_masks.copy())
        return int(action_masks.nonzero()[0][0]), None


class MaskIgnoringPolicy:
    def predict(self, observation, *, action_masks, deterministic):  # type: ignore[no-untyped-def]
        del observation, deterministic
        illegal = int((~action_masks).nonzero()[0][0])
        return illegal, None


class TrackingEnvironment(CoverageGuidedCodecEnv):
    def __init__(self) -> None:
        super().__init__(
            episode_config=EpisodeConfig(
                max_steps=8,
                coverage_target=1.0,
                stale_step_limit=None,
            )
        )
        self.step_calls = 0

    def step(self, action):  # type: ignore[no-untyped-def]
        self.step_calls += 1
        return super().step(action)


class EvaluationAndComparisonTests(unittest.TestCase):
    @staticmethod
    def factory() -> CoverageGuidedCodecEnv:
        return CoverageGuidedCodecEnv(
            episode_config=EpisodeConfig(
                max_steps=8,
                coverage_target=1.0,
                stale_step_limit=None,
            )
        )

    def test_inference_receives_a_mask_on_every_prediction(self) -> None:
        policy = FirstLegalPolicy()
        episodes = evaluate_policy(policy, self.factory, episodes=2, seed=12)
        self.assertTrue(policy.masks_seen)
        self.assertEqual(len(policy.masks_seen), sum(len(item.steps) for item in episodes))
        self.assertTrue(all(mask.any() for mask in policy.masks_seen))

    def test_evaluator_rejects_policy_that_ignores_mask(self) -> None:
        env = TrackingEnvironment()
        with self.assertRaisesRegex(RuntimeError, "excluded"):
            evaluate_policy(MaskIgnoringPolicy(), lambda: env, episodes=1, seed=2)
        self.assertEqual(env.step_calls, 0)

    def test_comparison_is_reproducible(self) -> None:
        first, _, _ = compare_policy_to_random(
            FirstLegalPolicy(),
            self.factory,
            episodes=3,
            seed=9,
            budget=8,
        )
        second, _, _ = compare_policy_to_random(
            FirstLegalPolicy(),
            self.factory,
            episodes=3,
            seed=9,
            budget=8,
        )
        self.assertEqual(first, second)
        self.assertEqual(len(first.mean_ppo_curve), 8)
        self.assertEqual(len(first.mean_random_curve), 8)


if __name__ == "__main__":
    unittest.main()
