"""Bind saved policies to the ordered actions and observations they learned."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import TYPE_CHECKING

from rl.env import CoverageGuidedCodecEnv

if TYPE_CHECKING:
    from rl.evaluate import MaskedPolicy


def environment_contract(env: CoverageGuidedCodecEnv) -> dict[str, object]:
    """Bump observation_schema when feature meanings or encodings change."""
    return {
        "catalog_digest": env.catalog.digest,
        "coverage_bin_digest": env.backend.bin_digest,
        "backend": f"{type(env.backend).__module__}.{type(env.backend).__qualname__}",
        "observation_schema": 1,
        "history_length": env.episode_config.history_length,
    }


def _sidecar(model_path: Path) -> Path:
    return model_path.with_suffix(model_path.suffix + ".metadata.json")


def write_checkpoint_metadata(model_path: Path, env: CoverageGuidedCodecEnv) -> Path:
    """Write a sidecar for this exact saved zip, including periodic checkpoints."""
    metadata = {
        "schema_version": 1,
        "model_sha256": hashlib.sha256(model_path.read_bytes()).hexdigest(),
        "environment": environment_contract(env),
    }
    path = _sidecar(model_path)
    path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def validate_checkpoint(model_path: Path, env: CoverageGuidedCodecEnv) -> None:
    """Fail before deserialization when a policy's contract is absent or stale."""
    try:
        metadata = json.loads(_sidecar(model_path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ValueError(
            f"checkpoint metadata is missing or invalid: {_sidecar(model_path)}"
        ) from exc
    if not isinstance(metadata, dict) or metadata.get("schema_version") != 1:
        raise ValueError("unsupported checkpoint metadata schema")
    contract = metadata.get("environment")
    expected = environment_contract(env)
    if not isinstance(contract, dict):
        raise ValueError("checkpoint environment contract is missing")
    mismatches = [key for key, value in expected.items() if contract.get(key) != value]
    if mismatches:
        raise ValueError("checkpoint environment mismatch: " + ", ".join(mismatches))
    digest = hashlib.sha256(model_path.read_bytes()).hexdigest()
    if metadata.get("model_sha256") != digest:
        raise ValueError("checkpoint bytes do not match metadata model_sha256")


def load_verified_policy(model_path: Path, env: CoverageGuidedCodecEnv) -> MaskedPolicy:
    """Load a trusted local model after validating its interpretation.

    The digest detects accidental file mixups; it is not a trust signature. Never
    deserialize models obtained from untrusted sources.
    """
    validate_checkpoint(model_path, env)
    try:
        from sb3_contrib import MaskablePPO
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise RuntimeError("install the RL extra: python -m pip install -e '.[rl]'") from exc
    return MaskablePPO.load(model_path)
