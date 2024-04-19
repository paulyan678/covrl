"""Simulator adapter registry."""

from __future__ import annotations

from pathlib import Path

from regression.adapters.base import SimulatorAdapter
from regression.adapters.iverilog import IcarusAdapter
from regression.adapters.mock import MockAdapter
from regression.adapters.questa import QuestaAdapter
from regression.adapters.vcs import VcsAdapter
from regression.config import SimulatorConfig

_ADAPTERS: dict[str, type[SimulatorAdapter]] = {
    "iverilog": IcarusAdapter,
    "mock": MockAdapter,
    "questa": QuestaAdapter,
    "vcs": VcsAdapter,
}


def adapter_names() -> tuple[str, ...]:
    return tuple(sorted(_ADAPTERS))


def create_adapter(
    name: str, project_root: Path, config: SimulatorConfig
) -> SimulatorAdapter:
    try:
        adapter_type = _ADAPTERS[name]
    except KeyError as error:
        choices = ", ".join(adapter_names())
        raise ValueError(f"unknown simulator {name!r}; choose one of: {choices}") from error
    return adapter_type(project_root, config)

__all__ = ["SimulatorAdapter", "adapter_names", "create_adapter"]
