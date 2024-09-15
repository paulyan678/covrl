from __future__ import annotations

import unittest

import numpy as np

from rl.compare import compare_policy_to_random
from rl.env import CoverageGuidedCodecEnv, EpisodeConfig
from rl.evaluate import evaluate_policy


class FirstLegalPolicy:
    def __init__(self) -> None:
        self.masks_seen: list[np.ndarray] = []

    def predict(self, observation, *, action_masks, deterministic):  # type: ignore[no-untyped-def]
        del observation, deterministic
        self.masks_seen.append(action_masks.copy())
        return int(action_masks.nonzero()[0][0]), None


class MaskIgnoringPolicy:
    def predict(self, observation, *, action_masks, deterministic):  # type: ignore[no-untyped-def]
        del observation, deterministic
        illegal = int((~action_masks).nonzero()[0][0])
        return illegal, None


class SeedTrackingPolicy(FirstLegalPolicy):
    def __init__(self) -> None:
        super().__init__()
        self.seeds: list[int] = []

    def set_random_seed(self, seed: int) -> None:
        self.seeds.append(seed)


class SeedRaisingPolicy(FirstLegalPolicy):
    def set_random_seed(self, seed: int) -> None:
        del seed
        raise RuntimeError("seed failure")


class FloatActionPolicy(FirstLegalPolicy):
    def predict(self, observation, *, action_masks, deterministic):  # type: ignore[no-untyped-def]
        del observation, action_masks, deterministic
        return 1.5, None


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
        self.closed = False

    def step(self, action):  # type: ignore[no-untyped-def]
        self.step_calls += 1
        return super().step(action)

    def close(self) -> None:
        self.closed = True
        super().close()


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

    def test_stochastic_policy_receives_reproducibility_seed(self) -> None:
        policy = SeedTrackingPolicy()
        evaluate_policy(
            policy,
            self.factory,
            episodes=1,
            seed=37,
            deterministic=False,
        )
        self.assertEqual(policy.seeds, [37])

    def test_evaluator_rejects_policy_that_ignores_mask(self) -> None:
        env = TrackingEnvironment()
        with self.assertRaisesRegex(RuntimeError, "excluded"):
            evaluate_policy(MaskIgnoringPolicy(), lambda: env, episodes=1, seed=2)
        self.assertEqual(env.step_calls, 0)
        self.assertTrue(env.closed)

    def test_environment_closes_when_stochastic_policy_seeding_fails(self) -> None:
        env = TrackingEnvironment()
        with self.assertRaisesRegex(RuntimeError, "seed failure"):
            evaluate_policy(
                SeedRaisingPolicy(),
                lambda: env,
                episodes=1,
                seed=2,
                deterministic=False,
            )
        self.assertTrue(env.closed)

    def test_evaluator_rejects_non_integer_scalar_action(self) -> None:
        env = TrackingEnvironment()
        with self.assertRaisesRegex(RuntimeError, "non-integer"):
            evaluate_policy(FloatActionPolicy(), lambda: env, episodes=1, seed=2)
        self.assertEqual(env.step_calls, 0)
        self.assertTrue(env.closed)

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

    def test_comparison_rejects_budget_environment_mismatch(self) -> None:
        with self.assertRaisesRegex(ValueError, "must equal comparison budget"):
            compare_policy_to_random(
                FirstLegalPolicy(),
                self.factory,
                episodes=1,
                seed=9,
                budget=7,
            )


if __name__ == "__main__":
    unittest.main()
