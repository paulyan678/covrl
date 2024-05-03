"""Fixed, stable-derived, and entropy-backed simulator seed selection."""

from __future__ import annotations

import hashlib
import secrets

from regression.config import SeedSpec

MAX_SEED = 2_147_483_646


def derived_seed(test_name: str, base_seed: int) -> int:
    """Derive a process-independent seed; Python's salted `hash` is not used."""

    if not 1 <= base_seed <= MAX_SEED:
        raise ValueError(f"base seed must be between 1 and {MAX_SEED}")
    digest = hashlib.sha256(f"codec-regression:{base_seed}:{test_name}".encode()).digest()
    return int.from_bytes(digest[:8], "big") % MAX_SEED + 1


def resolve_seed(spec: SeedSpec, test_name: str, base_seed: int) -> int:
    if spec.policy == "fixed":
        if spec.value is None:
            raise ValueError("fixed seed policy requires a value")
        return spec.value
    if spec.policy == "derived":
        return derived_seed(test_name, base_seed)
    if spec.policy == "random":
        return secrets.randbelow(MAX_SEED) + 1
    raise ValueError(f"unsupported seed policy: {spec.policy}")
