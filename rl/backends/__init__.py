"""Coverage backend contracts and implementations."""

from rl.backends.base import BackendStep, CoverageBackend, CoverageSnapshot, ProtocolState
from rl.backends.mock import MockCoverageBackend

__all__ = [
    "BackendStep",
    "CoverageBackend",
    "CoverageSnapshot",
    "MockCoverageBackend",
    "ProtocolState",
]
