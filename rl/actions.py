"""Stable discrete action catalog for codec stimulus generation.

The policy sees one Discrete action. Each index expands to a complete,
serializable transaction that a simulator-backed adapter can replay.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path
from typing import TypeVar, overload


class TransactionType(str, Enum):
    CONFIGURE = "configure"
    FRAME = "frame"
    CONTROL = "control"
    ERROR_INJECTION = "error_injection"
    IDLE = "idle"


class ControlOperation(str, Enum):
    START = "start"
    FLUSH = "flush"
    STOP = "stop"
    RESET = "reset"


class ErrorKind(str, Enum):
    INVALID_CONFIG = "invalid_config"
    INVALID_INPUT = "invalid_input"
    INVALID_CONTROL = "invalid_control"
    RESPONSE_TIMEOUT = "response_timeout"


PROFILES = ("baseline", "main", "high")
RESOLUTIONS = ("qcif", "sd", "hd", "fhd")
BIT_DEPTHS = (8, 10)
QUANTIZERS = (10, 26, 42)
FRAME_TYPES = ("i", "p", "b")
INPUT_SIZES = ("small", "nominal", "large")
TIMING_MODES = ("fixed", "variable")
BACKPRESSURE_CYCLES = (0, 2, 7)

_Key = TypeVar("_Key")
_Value = TypeVar("_Value")


@dataclass(frozen=True, slots=True)
class CodecCapabilities:
    """Choices supported by a DUT adapter.

    Relational restrictions, such as Baseline being 8-bit only, are applied by
    :func:`configuration_is_supported` in addition to these flat choices.
    """

    profiles: tuple[str, ...] = PROFILES
    resolutions: tuple[str, ...] = RESOLUTIONS
    bit_depths: tuple[int, ...] = BIT_DEPTHS
    quantizers: tuple[int, ...] = QUANTIZERS
    frame_types: tuple[str, ...] = FRAME_TYPES
    input_sizes: tuple[str, ...] = INPUT_SIZES
    timing_modes: tuple[str, ...] = TIMING_MODES
    max_backpressure_cycles: int = 7
    profile_bit_depths: tuple[tuple[str, tuple[int, ...]], ...] = (
        ("baseline", (8,)),
        ("main", (8, 10)),
        ("high", (8, 10)),
    )
    resolution_bit_depths: tuple[tuple[str, tuple[int, ...]], ...] = (
        ("qcif", (8,)),
        ("sd", (8, 10)),
        ("hd", (8, 10)),
        ("fhd", (8, 10)),
    )
    profile_frame_types: tuple[tuple[str, tuple[str, ...]], ...] = (
        ("baseline", ("i", "p")),
        ("main", FRAME_TYPES),
        ("high", FRAME_TYPES),
    )

    def __post_init__(self) -> None:
        choice_groups = {
            "profiles": self.profiles,
            "resolutions": self.resolutions,
            "bit_depths": self.bit_depths,
            "quantizers": self.quantizers,
            "frame_types": self.frame_types,
            "input_sizes": self.input_sizes,
            "timing_modes": self.timing_modes,
        }
        for name, choices in choice_groups.items():
            if not choices:
                raise ValueError(f"capability {name} must not be empty")
            if len(choices) != len(set(choices)):
                raise ValueError(f"capability {name} contains duplicate values")
        if self.max_backpressure_cycles < 0:
            raise ValueError("max_backpressure_cycles must not be negative")

        profile_depths = _unique_relation("profile_bit_depths", self.profile_bit_depths)
        resolution_depths = _unique_relation("resolution_bit_depths", self.resolution_bit_depths)
        profile_frames = _unique_relation("profile_frame_types", self.profile_frame_types)
        for profile in self.profiles:
            if not set(profile_depths.get(profile, ())).intersection(self.bit_depths):
                raise ValueError(f"profile {profile!r} has no advertised bit depth")
            if not set(profile_frames.get(profile, ())).intersection(self.frame_types):
                raise ValueError(f"profile {profile!r} has no advertised frame type")
        for resolution in self.resolutions:
            if not set(resolution_depths.get(resolution, ())).intersection(self.bit_depths):
                raise ValueError(f"resolution {resolution!r} has no advertised bit depth")


@dataclass(frozen=True, slots=True)
class CodecAction:
    """One fully specified entry in the discrete action catalog."""

    index: int
    name: str
    transaction_type: TransactionType
    profile: str | None = None
    resolution: str | None = None
    bit_depth: int | None = None
    quantizer: int | None = None
    frame_type: str | None = None
    input_size: str | None = None
    timing_mode: str | None = None
    backpressure_cycles: int = 0
    control: ControlOperation | None = None
    error_kind: ErrorKind | None = None

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["transaction_type"] = self.transaction_type.value
        payload["control"] = self.control.value if self.control is not None else None
        payload["error_kind"] = self.error_kind.value if self.error_kind is not None else None
        return payload


class ActionCatalog(Sequence[CodecAction]):
    """Validated, index-addressable catalog with a reproducibility digest."""

    def __init__(self, actions: Sequence[CodecAction]) -> None:
        self._actions = tuple(actions)
        expected = tuple(range(len(self._actions)))
        actual = tuple(action.index for action in self._actions)
        if actual != expected:
            raise ValueError("action indexes must be contiguous and ordered from zero")
        names = [action.name for action in self._actions]
        if len(names) != len(set(names)):
            raise ValueError("action names must be unique")
        for action in self._actions:
            _validate_action(action)

    @overload
    def __getitem__(self, index: int) -> CodecAction: ...

    @overload
    def __getitem__(self, index: slice) -> tuple[CodecAction, ...]: ...

    def __getitem__(self, index: int | slice) -> CodecAction | tuple[CodecAction, ...]:
        return self._actions[index]

    def __len__(self) -> int:
        return len(self._actions)

    def __iter__(self) -> Iterator[CodecAction]:
        return iter(self._actions)

    @property
    def digest(self) -> str:
        encoded = json.dumps(self.to_list(), sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def to_list(self) -> list[dict[str, object]]:
        return [action.to_dict() for action in self._actions]

    def write_json(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_list(), indent=2) + "\n", encoding="utf-8")

    def indexes_by_type(self, transaction_type: TransactionType) -> tuple[int, ...]:
        return tuple(
            action.index for action in self._actions if action.transaction_type is transaction_type
        )


def configuration_is_supported(
    action: CodecAction,
    capabilities: CodecCapabilities,
) -> bool:
    """Return whether a configuration is legal for the advertised toy protocol."""

    if action.transaction_type is not TransactionType.CONFIGURE:
        return False
    if (
        action.profile not in capabilities.profiles
        or action.resolution not in capabilities.resolutions
        or action.bit_depth not in capabilities.bit_depths
        or action.quantizer not in capabilities.quantizers
    ):
        return False
    profile_depths = dict(capabilities.profile_bit_depths).get(action.profile, ())
    resolution_depths = dict(capabilities.resolution_bit_depths).get(action.resolution, ())
    if action.bit_depth not in profile_depths:
        return False
    if action.bit_depth not in resolution_depths:
        return False
    return True


def frame_is_supported(
    action: CodecAction,
    capabilities: CodecCapabilities,
    current_configuration: Mapping[str, object] | None,
) -> bool:
    if action.transaction_type is not TransactionType.FRAME:
        return False
    if (
        action.frame_type not in capabilities.frame_types
        or action.input_size not in capabilities.input_sizes
        or action.timing_mode not in capabilities.timing_modes
        or action.backpressure_cycles > capabilities.max_backpressure_cycles
    ):
        return False
    if current_configuration is not None:
        profile = str(current_configuration.get("profile"))
        allowed_frames = dict(capabilities.profile_frame_types).get(profile, ())
        return action.frame_type in allowed_frames
    return True


def build_default_catalog() -> ActionCatalog:
    """Build the canonical catalog in deterministic, append-only order."""

    actions: list[CodecAction] = []

    def add(name: str, kind: TransactionType, **fields: object) -> None:
        actions.append(
            CodecAction(
                index=len(actions),
                name=name,
                transaction_type=kind,
                **fields,  # type: ignore[arg-type]
            )
        )

    for profile in PROFILES:
        for resolution in RESOLUTIONS:
            for bit_depth in BIT_DEPTHS:
                for quantizer in QUANTIZERS:
                    add(
                        f"cfg.{profile}.{resolution}.{bit_depth}b.q{quantizer}",
                        TransactionType.CONFIGURE,
                        profile=profile,
                        resolution=resolution,
                        bit_depth=bit_depth,
                        quantizer=quantizer,
                    )

    for frame_type in FRAME_TYPES:
        for input_size in INPUT_SIZES:
            for timing_mode in TIMING_MODES:
                for backpressure_cycles in BACKPRESSURE_CYCLES:
                    add(
                        f"frame.{frame_type}.{input_size}.{timing_mode}.bp{backpressure_cycles}",
                        TransactionType.FRAME,
                        frame_type=frame_type,
                        input_size=input_size,
                        timing_mode=timing_mode,
                        backpressure_cycles=backpressure_cycles,
                    )

    for operation in ControlOperation:
        add(f"control.{operation.value}", TransactionType.CONTROL, control=operation)
    for error_kind in ErrorKind:
        add(
            f"error.{error_kind.value}",
            TransactionType.ERROR_INJECTION,
            error_kind=error_kind,
        )
    add("idle.one_cycle", TransactionType.IDLE)
    return ActionCatalog(actions)


def _unique_relation(
    name: str,
    relation: tuple[tuple[_Key, tuple[_Value, ...]], ...],
) -> dict[_Key, tuple[_Value, ...]]:
    keys = [key for key, _ in relation]
    if len(keys) != len(set(keys)):
        raise ValueError(f"capability relation {name} contains duplicate keys")
    return dict(relation)


def _validate_action(action: CodecAction) -> None:
    if not action.name:
        raise ValueError("action name must not be empty")
    if action.backpressure_cycles < 0:
        raise ValueError(f"action {action.name!r} has negative backpressure")
    if action.transaction_type is TransactionType.CONFIGURE:
        required = (action.profile, action.resolution, action.bit_depth, action.quantizer)
    elif action.transaction_type is TransactionType.FRAME:
        required = (action.frame_type, action.input_size, action.timing_mode)
    elif action.transaction_type is TransactionType.CONTROL:
        required = (action.control,)
    elif action.transaction_type is TransactionType.ERROR_INJECTION:
        required = (action.error_kind,)
    else:
        required = ()
    if any(value is None for value in required):
        raise ValueError(f"action {action.name!r} is missing fields for its transaction type")


DEFAULT_ACTION_CATALOG = build_default_catalog()
