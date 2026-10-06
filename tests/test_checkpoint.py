from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from rl.actions import DEFAULT_ACTION_CATALOG, ActionCatalog
from rl.backends.mock import MockCoverageBackend
from rl.checkpoint import validate_checkpoint, write_checkpoint_metadata
from rl.env import CoverageGuidedCodecEnv, EpisodeConfig


class CheckpointTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "model.zip"
        self.path.write_bytes(b"test model bytes; never deserialized")
        self.env = CoverageGuidedCodecEnv()
        self.addCleanup(self.env.close)
        self.metadata = write_checkpoint_metadata(self.path, self.env)

    def test_matching_contract_and_adjusted_evaluation_budget_are_allowed(self) -> None:
        validate_checkpoint(self.path, self.env)
        env = CoverageGuidedCodecEnv(episode_config=EpisodeConfig(max_steps=32))
        self.addCleanup(env.close)
        validate_checkpoint(self.path, env)

    def test_reordered_actions_of_same_dimension_are_rejected(self) -> None:
        actions = list(DEFAULT_ACTION_CATALOG)
        actions[0], actions[1] = actions[1], actions[0]
        catalog = ActionCatalog([replace(action, index=i) for i, action in enumerate(actions)])
        env = CoverageGuidedCodecEnv(catalog=catalog)
        self.addCleanup(env.close)
        with self.assertRaisesRegex(ValueError, "catalog_digest"):
            validate_checkpoint(self.path, env)

    def test_reordered_coverage_bins_of_same_dimension_are_rejected(self) -> None:
        class ReorderedBackend(MockCoverageBackend):
            @property
            def bin_names(self) -> tuple[str, ...]:
                return tuple(reversed(super().bin_names))

        env = CoverageGuidedCodecEnv(backend=ReorderedBackend())
        self.addCleanup(env.close)
        with self.assertRaisesRegex(ValueError, "coverage_bin_digest"):
            validate_checkpoint(self.path, env)

    def test_changed_observation_shape_is_rejected(self) -> None:
        env = CoverageGuidedCodecEnv(episode_config=EpisodeConfig(history_length=16))
        self.addCleanup(env.close)
        with self.assertRaisesRegex(ValueError, "history_length"):
            validate_checkpoint(self.path, env)

    def test_swapped_model_bytes_are_rejected(self) -> None:
        self.path.write_bytes(b"different model")
        with self.assertRaisesRegex(ValueError, "model_sha256"):
            validate_checkpoint(self.path, self.env)

    def test_missing_malformed_and_unknown_metadata_are_rejected(self) -> None:
        self.metadata.unlink()
        with self.assertRaisesRegex(ValueError, "missing or invalid"):
            validate_checkpoint(self.path, self.env)
        for content in ("{", "[]", json.dumps({"schema_version": 2})):
            self.metadata.write_text(content)
            with self.assertRaises(ValueError):
                validate_checkpoint(self.path, self.env)
