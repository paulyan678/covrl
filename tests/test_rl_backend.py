from __future__ import annotations

import unittest

from rl.actions import (
    DEFAULT_ACTION_CATALOG,
    ControlOperation,
    TransactionType,
)
from rl.backends import CoverageBackend, MockCoverageBackend, ProtocolState


def action_index(**fields: object) -> int:
    for action in DEFAULT_ACTION_CATALOG:
        if all(getattr(action, name) == value for name, value in fields.items()):
            return action.index
    raise AssertionError(f"action not found: {fields}")


class MockCoverageBackendTests(unittest.TestCase):
    def test_backend_contract_and_bin_order(self) -> None:
        backend = MockCoverageBackend()
        self.assertIsInstance(backend, CoverageBackend)
        self.assertEqual(len(backend.bin_names), len(set(backend.bin_names)))
        self.assertGreater(len(backend.bin_names), 50)
        self.assertEqual(backend.bin_digest, MockCoverageBackend().bin_digest)

    def test_fixed_seed_and_actions_produce_identical_trajectory(self) -> None:
        indexes = (
            action_index(
                transaction_type=TransactionType.CONFIGURE,
                profile="main",
                resolution="hd",
                bit_depth=10,
                quantizer=26,
            ),
            action_index(
                transaction_type=TransactionType.CONTROL,
                control=ControlOperation.START,
            ),
            action_index(
                transaction_type=TransactionType.FRAME,
                frame_type="p",
                input_size="nominal",
                timing_mode="variable",
                backpressure_cycles=2,
            ),
        )
        trajectories = []
        for _ in range(2):
            backend = MockCoverageBackend()
            backend.reset(seed=91)
            trajectories.append(
                tuple(backend.execute(DEFAULT_ACTION_CATALOG[index]) for index in indexes)
            )
        self.assertEqual(trajectories[0], trajectories[1])

    def test_direct_illegal_configuration_reports_error(self) -> None:
        backend = MockCoverageBackend()
        backend.reset(seed=1)
        illegal_index = action_index(
            transaction_type=TransactionType.CONFIGURE,
            profile="baseline",
            resolution="hd",
            bit_depth=10,
            quantizer=26,
        )
        result = backend.execute(DEFAULT_ACTION_CATALOG[illegal_index])
        self.assertFalse(result.accepted)
        self.assertTrue(result.invalid_transition)
        self.assertIn("configuration.illegal", result.newly_covered)

    def test_reset_during_traffic_and_reconfiguration_cover_recovery(self) -> None:
        backend = MockCoverageBackend()
        backend.reset(seed=3)
        configure = action_index(
            transaction_type=TransactionType.CONFIGURE,
            profile="high",
            resolution="fhd",
            bit_depth=10,
            quantizer=42,
        )
        start = action_index(
            transaction_type=TransactionType.CONTROL,
            control=ControlOperation.START,
        )
        reset = action_index(
            transaction_type=TransactionType.CONTROL,
            control=ControlOperation.RESET,
        )
        backend.execute(DEFAULT_ACTION_CATALOG[configure])
        backend.execute(DEFAULT_ACTION_CATALOG[start])
        reset_result = backend.execute(DEFAULT_ACTION_CATALOG[reset])
        self.assertEqual(reset_result.snapshot.protocol_state, ProtocolState.UNCONFIGURED)
        self.assertIn("reset.active", reset_result.newly_covered)
        recovery = backend.execute(DEFAULT_ACTION_CATALOG[configure])
        self.assertIn("reset.recovery", recovery.newly_covered)


if __name__ == "__main__":
    unittest.main()
