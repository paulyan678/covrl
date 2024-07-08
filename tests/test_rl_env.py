from __future__ import annotations

import unittest
from dataclasses import replace

from rl.actions import (
    DEFAULT_ACTION_CATALOG,
    ControlOperation,
    ErrorKind,
    TransactionType,
)
from rl.backends import MockCoverageBackend
from rl.env import CoverageGuidedCodecEnv, EpisodeConfig


def find_action(**fields: object) -> int:
    return next(
        action.index
        for action in DEFAULT_ACTION_CATALOG
        if all(getattr(action, key) == value for key, value in fields.items())
    )


class InfrastructureFailureBackend(MockCoverageBackend):
    def execute(self, action):  # type: ignore[no-untyped-def]
        return replace(super().execute(action), infrastructure_failure=True)


class CoverageEnvironmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.backend = MockCoverageBackend()
        self.env = CoverageGuidedCodecEnv(backend=self.backend)
        self.observation, _ = self.env.reset(seed=11)
        self.configure = find_action(
            transaction_type=TransactionType.CONFIGURE,
            profile="baseline",
            resolution="hd",
            bit_depth=8,
            quantizer=26,
        )
        self.start = find_action(
            transaction_type=TransactionType.CONTROL,
            control=ControlOperation.START,
        )

    def test_rich_observation_matches_declared_space(self) -> None:
        self.assertTrue(self.env.observation_space.contains(self.observation))
        self.assertEqual(
            set(self.observation),
            {
                "coverage",
                "recent_transactions",
                "protocol_state",
                "current_configuration",
                "available_configurations",
                "remaining_budget",
                "recent_rewards",
                "recent_coverage_gains",
                "action_mask",
            },
        )

    def test_mask_changes_with_protocol_state_and_capabilities(self) -> None:
        initial = self.env.action_masks()
        baseline_ten_bit = find_action(
            transaction_type=TransactionType.CONFIGURE,
            profile="baseline",
            resolution="hd",
            bit_depth=10,
            quantizer=26,
        )
        self.assertFalse(initial[self.start])
        self.assertFalse(initial[baseline_ten_bit])
        self.assertTrue(initial[self.configure])
        configured_observation, _, _, _, _ = self.env.step(self.configure)
        self.assertEqual(int(configured_observation["current_configuration"].sum()), 4)
        self.assertTrue(self.env.action_masks()[self.start])
        self.env.step(self.start)
        b_frame = find_action(
            transaction_type=TransactionType.FRAME,
            frame_type="b",
            input_size="nominal",
            timing_mode="fixed",
            backpressure_cycles=0,
        )
        p_frame = find_action(
            transaction_type=TransactionType.FRAME,
            frame_type="p",
            input_size="nominal",
            timing_mode="fixed",
            backpressure_cycles=0,
        )
        running = self.env.action_masks()
        self.assertFalse(running[b_frame])
        self.assertTrue(running[p_frame])

    def test_masked_action_never_reaches_backend(self) -> None:
        before = self.backend.execution_history
        _, reward, terminated, truncated, info = self.env.step(self.start)
        self.assertEqual(self.backend.execution_history, before)
        self.assertLess(reward, 0)
        self.assertFalse(terminated)
        self.assertFalse(truncated)
        self.assertFalse(info["action_reached_backend"])
        self.assertTrue(info["illegal_action"])

    def test_repeated_mask_violations_truncate_without_backend_calls(self) -> None:
        backend = MockCoverageBackend()
        env = CoverageGuidedCodecEnv(
            backend=backend,
            episode_config=EpisodeConfig(max_illegal_attempts=2),
        )
        env.reset(seed=5)
        env.step(self.start)
        _, _, terminated, truncated, info = env.step(self.start)
        self.assertFalse(terminated)
        self.assertTrue(truncated)
        self.assertEqual(info["termination_reason"], "illegal_action_limit")
        self.assertEqual(backend.execution_history, ())

    def test_new_coverage_reward_dominates_redundancy_penalty(self) -> None:
        _, first_reward, _, _, first_info = self.env.step(self.configure)
        _, repeat_reward, _, _, repeat_info = self.env.step(self.configure)
        self.assertGreater(first_reward, 0)
        self.assertGreater(first_info["coverage_gain"], 0)
        self.assertLess(repeat_reward, 0)
        self.assertEqual(repeat_info["coverage_gain"], 0)

    def test_step_budget_is_an_explicit_truncation(self) -> None:
        env = CoverageGuidedCodecEnv(
            episode_config=EpisodeConfig(
                max_steps=1,
                coverage_target=1.0,
                stale_step_limit=None,
            )
        )
        env.reset(seed=1)
        _, _, terminated, truncated, info = env.step(self.configure)
        self.assertFalse(terminated)
        self.assertTrue(truncated)
        self.assertEqual(info["termination_reason"], "step_budget")

    def test_coverage_target_is_an_explicit_termination(self) -> None:
        env = CoverageGuidedCodecEnv(
            episode_config=EpisodeConfig(
                coverage_target=0.05,
                stale_step_limit=None,
            )
        )
        env.reset(seed=2)
        _, reward, terminated, truncated, info = env.step(self.configure)
        self.assertTrue(terminated)
        self.assertFalse(truncated)
        self.assertEqual(info["termination_reason"], "coverage_target")
        self.assertGreater(reward, info["coverage_gain"])

    def test_stale_limit_is_an_explicit_truncation(self) -> None:
        env = CoverageGuidedCodecEnv(
            episode_config=EpisodeConfig(
                coverage_target=1.0,
                stale_step_limit=2,
            )
        )
        env.reset(seed=2)
        env.step(self.configure)
        env.step(self.configure)
        _, _, terminated, truncated, info = env.step(self.configure)
        self.assertFalse(terminated)
        self.assertTrue(truncated)
        self.assertEqual(info["termination_reason"], "stale_limit")

    def test_timeout_is_penalized_and_truncated(self) -> None:
        self.env.step(self.configure)
        self.env.step(self.start)
        timeout = find_action(
            transaction_type=TransactionType.ERROR_INJECTION,
            error_kind=ErrorKind.RESPONSE_TIMEOUT,
        )
        _, reward, terminated, truncated, info = self.env.step(timeout)
        self.assertFalse(terminated)
        self.assertTrue(truncated)
        self.assertEqual(info["termination_reason"], "backend_timeout")
        self.assertTrue(info["timed_out"])
        self.assertLess(reward, 0)

    def test_infrastructure_failure_terminates_with_large_penalty(self) -> None:
        env = CoverageGuidedCodecEnv(backend=InfrastructureFailureBackend())
        env.reset(seed=4)
        _, reward, terminated, truncated, info = env.step(self.configure)
        self.assertTrue(terminated)
        self.assertFalse(truncated)
        self.assertEqual(info["termination_reason"], "infrastructure_failure")
        self.assertLess(reward, 0)

    def test_reproducible_observations_and_rewards(self) -> None:
        trajectories = []
        frame = find_action(
            transaction_type=TransactionType.FRAME,
            frame_type="p",
            input_size="large",
            timing_mode="variable",
            backpressure_cycles=2,
        )
        for _ in range(2):
            env = CoverageGuidedCodecEnv()
            observation, _ = env.reset(seed=88)
            trajectory = []
            for action in (self.configure, self.start, frame):
                observation, reward, terminated, truncated, info = env.step(action)
                trajectory.append(
                    (
                        observation["coverage"].tobytes(),
                        reward,
                        terminated,
                        truncated,
                        info["latency_cycles"],
                    )
                )
            trajectories.append(trajectory)
        self.assertEqual(trajectories[0], trajectories[1])

    def test_seeded_automatic_episode_resets_are_reproducible(self) -> None:
        seed_streams = []
        for _ in range(2):
            env = CoverageGuidedCodecEnv()
            _, first = env.reset(seed=123)
            _, second = env.reset()
            _, third = env.reset()
            seed_streams.append(
                (first["episode_seed"], second["episode_seed"], third["episode_seed"])
            )
        self.assertEqual(seed_streams[0], seed_streams[1])
        self.assertEqual(seed_streams[0][0], 123)

    def test_out_of_range_action_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "outside"):
            self.env.step(len(DEFAULT_ACTION_CATALOG))
        with self.assertRaisesRegex(ValueError, "discrete integer"):
            self.env.step(1.5)  # type: ignore[arg-type]


if __name__ == "__main__":
    unittest.main()
