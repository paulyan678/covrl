"""Coverage-guided, action-masked codec stimulus generation."""

from rl.actions import DEFAULT_ACTION_CATALOG, ActionCatalog, CodecAction
from rl.backends import CoverageBackend, MockCoverageBackend
from rl.env import CoverageGuidedCodecEnv, EpisodeConfig, RewardConfig

__all__ = [
    "ActionCatalog",
    "CodecAction",
    "CoverageBackend",
    "CoverageGuidedCodecEnv",
    "DEFAULT_ACTION_CATALOG",
    "EpisodeConfig",
    "MockCoverageBackend",
    "RewardConfig",
]

__version__ = "0.1.0"
