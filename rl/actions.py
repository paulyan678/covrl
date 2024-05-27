"""Codec transaction choices and DUT capability relationships."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass
from enum import Enum
from typing import TypeVar


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


def _unique_relation(
    name: str,
    relation: tuple[tuple[_Key, tuple[_Value, ...]], ...],
) -> dict[_Key, tuple[_Value, ...]]:
    keys = [key for key, _ in relation]
    if len(keys) != len(set(keys)):
        raise ValueError(f"capability relation {name} contains duplicate keys")
    return dict(relation)
