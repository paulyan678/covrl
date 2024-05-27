"""Coverage backend contract shared by mock and simulator integrations."""

from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING

from rl.actions import CodecCapabilities

if TYPE_CHECKING:
    from rl.actions import CodecAction


class ProtocolState(IntEnum):
    UNCONFIGURED = 0
    CONFIGURED = 1
    RUNNING = 2


@dataclass(frozen=True, slots=True)
class CoverageSnapshot:
    """Immutable backend state returned after reset and every transaction."""

    covered_bins: frozenset[str]
    total_bins: int
    protocol_state: ProtocolState
    capabilities: CodecCapabilities
    current_configuration: Mapping[str, object] | None = None
    step_count: int = 0
    last_status: str = "reset"
    metadata: Mapping[str, object] = field(default_factory=dict)

    @property
    def coverage_count(self) -> int:
        return len(self.covered_bins)

    @property
    def coverage_fraction(self) -> float:
        if self.total_bins <= 0:
            return 0.0
        return self.coverage_count / self.total_bins


@dataclass(frozen=True, slots=True)
class BackendStep:
    """Outcome of one transaction submitted to a coverage backend."""

    snapshot: CoverageSnapshot
    newly_covered: tuple[str, ...]
    accepted: bool = True
    status: str = "ok"
    latency_cycles: int = 0
    timed_out: bool = False
    invalid_transition: bool = False
    infrastructure_failure: bool = False
    details: Mapping[str, object] = field(default_factory=dict)


class CoverageBackend(ABC):
    """Replaceable boundary between stimulus generation and simulation.

    A real adapter may batch transactions and parse simulator coverage, but it
    must preserve these reset/execute/snapshot semantics.  It must never report
    bins not present in ``bin_names``.
    """

    @property
    @abstractmethod
    def bin_names(self) -> tuple[str, ...]:
        """Return stable bin ordering for the lifetime of this backend."""

    @abstractmethod
    def reset(self, seed: int | None = None) -> CoverageSnapshot:
        """Start a fresh episode and return its initial snapshot."""

    @abstractmethod
    def execute(self, action: CodecAction) -> BackendStep:
        """Apply one legal action and report coverage and protocol effects."""

    @abstractmethod
    def snapshot(self) -> CoverageSnapshot:
        """Return current state without advancing simulation."""

    def validate_step(self, step: BackendStep) -> None:
        known = set(self.bin_names)
        unknown = set(step.snapshot.covered_bins).difference(known)
        if unknown:
            raise ValueError(f"backend reported unknown coverage bins: {sorted(unknown)}")
        if step.snapshot.total_bins != len(self.bin_names):
            raise ValueError("backend snapshot total_bins does not match bin_names")
        if set(step.newly_covered).difference(step.snapshot.covered_bins):
            raise ValueError("newly_covered must be a subset of covered_bins")

    @property
    def bin_digest(self) -> str:
        """Fingerprint the observation's fixed coverage-vector semantics."""

        encoded = json.dumps(self.bin_names, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()
