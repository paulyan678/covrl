"""Deterministic simulator-free functional coverage model."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable

from rl.actions import (
    BACKPRESSURE_CYCLES,
    CodecAction,
    CodecCapabilities,
    ControlOperation,
    ErrorKind,
    TransactionType,
    configuration_is_supported,
    frame_is_supported,
)
from rl.backends.base import (
    BackendStep,
    CoverageBackend,
    CoverageSnapshot,
    ProtocolState,
)


def _bp_class(cycles: int) -> str:
    if cycles == 0:
        return "none"
    if cycles <= 2:
        return "short"
    return "long"


def _latency_class(cycles: int) -> str:
    if cycles <= 2:
        return "short"
    if cycles <= 6:
        return "medium"
    return "long"


def _coverage_bins(capabilities: CodecCapabilities) -> tuple[str, ...]:
    bins: list[str] = []
    bins.extend(f"profile.{value}" for value in capabilities.profiles)
    bins.extend(f"resolution.{value}" for value in capabilities.resolutions)
    bins.extend(f"bit_depth.{value}" for value in capabilities.bit_depths)
    bins.extend(f"quantizer.{value}" for value in capabilities.quantizers)
    bins.extend(f"frame_type.{value}" for value in capabilities.frame_types)
    bins.extend(f"input_size.{value}" for value in capabilities.input_sizes)
    bins.extend(f"timing.{value}" for value in capabilities.timing_modes)
    bins.extend(("configuration.legal", "configuration.illegal"))
    backpressure_classes = tuple(
        dict.fromkeys(
            _bp_class(cycles)
            for cycles in BACKPRESSURE_CYCLES
            if cycles <= capabilities.max_backpressure_cycles
        )
    )
    reachable_bp_latency: set[tuple[str, str]] = set()
    for backpressure in backpressure_classes:
        if backpressure == "none":
            if "fixed" in capabilities.timing_modes:
                reachable_bp_latency.add((backpressure, "short"))
            if "variable" in capabilities.timing_modes:
                reachable_bp_latency.update({(backpressure, "short"), (backpressure, "medium")})
        elif backpressure == "short":
            if "fixed" in capabilities.timing_modes:
                reachable_bp_latency.add((backpressure, "medium"))
            if "variable" in capabilities.timing_modes:
                reachable_bp_latency.update({(backpressure, "medium"), (backpressure, "long")})
        else:
            reachable_bp_latency.add((backpressure, "long"))
    latency_classes = tuple(
        value
        for value in ("short", "medium", "long")
        if any(pair[1] == value for pair in reachable_bp_latency)
    )
    bins.extend(f"backpressure.{value}" for value in backpressure_classes)
    bins.extend(f"latency.{value}" for value in latency_classes)
    bins.extend(f"reset.{value}" for value in ("idle", "active", "recovery"))
    bins.extend(f"error.{value.value}" for value in ErrorKind)
    bins.extend(f"control.{value.value}" for value in ControlOperation)
    bins.extend(
        f"cross.profile_resolution.{profile}.{resolution}"
        for profile in capabilities.profiles
        for resolution in capabilities.resolutions
        if set(dict(capabilities.profile_bit_depths).get(profile, ())).intersection(
            dict(capabilities.resolution_bit_depths).get(resolution, ())
        )
    )
    legal_profile_depths = tuple(
        (profile, depth)
        for profile in capabilities.profiles
        for depth in capabilities.bit_depths
        if depth in dict(capabilities.profile_bit_depths).get(profile, ())
    )
    bins.extend(f"cross.profile_depth.{profile}.{depth}" for profile, depth in legal_profile_depths)
    bins.extend(
        f"cross.frame_input.{frame_type}.{input_size}"
        for frame_type in capabilities.frame_types
        for input_size in capabilities.input_sizes
    )
    bins.extend(
        f"cross.profile_frame.{profile}.{frame_type}"
        for profile in capabilities.profiles
        for frame_type in capabilities.frame_types
        if frame_type in dict(capabilities.profile_frame_types).get(profile, ())
    )
    bins.extend(
        f"cross.resolution_input.{resolution}.{input_size}"
        for resolution in capabilities.resolutions
        for input_size in capabilities.input_sizes
    )
    # Only structurally reachable backpressure/latency combinations are goals.
    bins.extend(
        f"cross.backpressure_latency.{bp}.{latency}" for bp, latency in sorted(reachable_bp_latency)
    )
    return tuple(bins)


MOCK_COVERAGE_BINS = _coverage_bins(CodecCapabilities())


class MockCoverageBackend(CoverageBackend):
    """Stateful deterministic backend used for development and CI.

    This is an executable functional model, not a claim about RTL coverage.
    The same seed and action indexes always produce the same state, latency, and
    coverage trajectory, including across Python processes.
    """

    def __init__(self, capabilities: CodecCapabilities | None = None) -> None:
        self._capabilities = capabilities or CodecCapabilities()
        self._bin_names = _coverage_bins(self._capabilities)
        self._seed = 0
        self._covered: set[str] = set()
        self._state = ProtocolState.UNCONFIGURED
        self._current_configuration: dict[str, object] | None = None
        self._step_count = 0
        self._last_status = "created"
        self._awaiting_reset_recovery = False
        self._execution_history: list[int] = []
        self.reset(seed=0)

    @property
    def bin_names(self) -> tuple[str, ...]:
        return self._bin_names

    @property
    def execution_history(self) -> tuple[int, ...]:
        """Action indexes actually accepted by the backend boundary."""

        return tuple(self._execution_history)

    def reset(self, seed: int | None = None) -> CoverageSnapshot:
        self._seed = 0 if seed is None else int(seed)
        self._covered.clear()
        self._state = ProtocolState.UNCONFIGURED
        self._current_configuration = None
        self._step_count = 0
        self._last_status = "episode_reset"
        self._awaiting_reset_recovery = False
        self._execution_history.clear()
        return self.snapshot()

    def snapshot(self) -> CoverageSnapshot:
        configuration = (
            dict(self._current_configuration) if self._current_configuration is not None else None
        )
        return CoverageSnapshot(
            covered_bins=frozenset(self._covered),
            total_bins=len(self._bin_names),
            protocol_state=self._state,
            capabilities=self._capabilities,
            current_configuration=configuration,
            step_count=self._step_count,
            last_status=self._last_status,
            metadata={
                "backend": "deterministic_mock",
                "seed": self._seed,
                "executed_actions": len(self._execution_history),
            },
        )

    def execute(self, action: CodecAction) -> BackendStep:
        previous = self.snapshot()
        before = set(self._covered)
        self._step_count += 1
        self._execution_history.append(action.index)
        accepted = True
        timed_out = False
        invalid_transition = False
        latency_cycles = 0
        status = "ok"

        if action.transaction_type is TransactionType.CONFIGURE:
            accepted, invalid_transition, status = self._configure(action)
        elif action.transaction_type is TransactionType.FRAME:
            accepted, invalid_transition, status, latency_cycles = self._frame(action)
        elif action.transaction_type is TransactionType.CONTROL:
            accepted, invalid_transition, status = self._control(action)
        elif action.transaction_type is TransactionType.ERROR_INJECTION:
            accepted, invalid_transition, timed_out, status = self._inject_error(action)
        elif action.transaction_type is TransactionType.IDLE:
            status = "idle"
        else:  # pragma: no cover - enum exhaustiveness guard
            accepted = False
            invalid_transition = True
            status = "unknown_transaction"

        self._last_status = status
        newly_covered = tuple(sorted(self._covered.difference(before)))
        result = BackendStep(
            snapshot=self.snapshot(),
            newly_covered=newly_covered,
            accepted=accepted,
            status=status,
            latency_cycles=latency_cycles,
            timed_out=timed_out,
            invalid_transition=invalid_transition,
            details={"action_name": action.name},
        )
        self.validate_step(result, previous)
        return result

    def _configure(self, action: CodecAction) -> tuple[bool, bool, str]:
        if self._state is ProtocolState.RUNNING:
            return False, True, "configuration_while_running"
        if not configuration_is_supported(action, self._capabilities):
            self._cover("configuration.illegal", "error.invalid_config")
            return False, True, "illegal_configuration"

        assert action.profile is not None
        assert action.resolution is not None
        assert action.bit_depth is not None
        assert action.quantizer is not None
        self._current_configuration = {
            "profile": action.profile,
            "resolution": action.resolution,
            "bit_depth": action.bit_depth,
            "quantizer": action.quantizer,
        }
        self._state = ProtocolState.CONFIGURED
        self._cover(
            "configuration.legal",
            f"profile.{action.profile}",
            f"resolution.{action.resolution}",
            f"bit_depth.{action.bit_depth}",
            f"quantizer.{action.quantizer}",
            f"cross.profile_resolution.{action.profile}.{action.resolution}",
            f"cross.profile_depth.{action.profile}.{action.bit_depth}",
        )
        if self._awaiting_reset_recovery:
            self._cover("reset.recovery")
            self._awaiting_reset_recovery = False
        return True, False, "configured"

    def _frame(self, action: CodecAction) -> tuple[bool, bool, str, int]:
        if self._state is not ProtocolState.RUNNING:
            return False, True, "frame_outside_running", 0
        if not frame_is_supported(action, self._capabilities, self._current_configuration):
            self._cover("error.invalid_input")
            return False, True, "unsupported_frame", 0

        assert action.frame_type is not None
        assert action.input_size is not None
        assert action.timing_mode is not None
        assert self._current_configuration is not None
        latency_cycles = self._deterministic_latency(action)
        latency = _latency_class(latency_cycles)
        backpressure = _bp_class(action.backpressure_cycles)
        profile = str(self._current_configuration["profile"])
        resolution = str(self._current_configuration["resolution"])
        self._cover(
            f"frame_type.{action.frame_type}",
            f"input_size.{action.input_size}",
            f"timing.{action.timing_mode}",
            f"backpressure.{backpressure}",
            f"latency.{latency}",
            f"cross.frame_input.{action.frame_type}.{action.input_size}",
            f"cross.profile_frame.{profile}.{action.frame_type}",
            f"cross.resolution_input.{resolution}.{action.input_size}",
            f"cross.backpressure_latency.{backpressure}.{latency}",
        )
        return True, False, "frame_accepted", latency_cycles

    def _control(self, action: CodecAction) -> tuple[bool, bool, str]:
        operation = action.control
        if operation is ControlOperation.RESET:
            previous = self._state
            self._state = ProtocolState.UNCONFIGURED
            self._current_configuration = None
            self._awaiting_reset_recovery = True
            self._cover(
                "control.reset",
                "reset.active" if previous is ProtocolState.RUNNING else "reset.idle",
            )
            return True, False, "reset_applied"
        if operation is ControlOperation.START and self._state is ProtocolState.CONFIGURED:
            self._state = ProtocolState.RUNNING
            self._cover("control.start")
            return True, False, "started"
        if operation is ControlOperation.FLUSH and self._state is ProtocolState.RUNNING:
            self._state = ProtocolState.CONFIGURED
            self._cover("control.flush")
            return True, False, "flushed"
        if operation is ControlOperation.STOP and self._state in {
            ProtocolState.CONFIGURED,
            ProtocolState.RUNNING,
        }:
            self._state = ProtocolState.UNCONFIGURED
            self._current_configuration = None
            self._cover("control.stop")
            return True, False, "stopped"
        return False, True, "illegal_control_transition"

    def _inject_error(self, action: CodecAction) -> tuple[bool, bool, bool, str]:
        error = action.error_kind
        if error is ErrorKind.INVALID_CONFIG and self._state is not ProtocolState.RUNNING:
            self._cover("configuration.illegal", "error.invalid_config")
            return True, False, False, "expected_invalid_config"
        if error is ErrorKind.INVALID_INPUT and self._state is ProtocolState.RUNNING:
            self._cover("error.invalid_input")
            return True, False, False, "expected_invalid_input"
        if error is ErrorKind.INVALID_CONTROL:
            self._cover("error.invalid_control")
            return True, False, False, "expected_invalid_control"
        if error is ErrorKind.RESPONSE_TIMEOUT and self._state is ProtocolState.RUNNING:
            self._cover("error.response_timeout", "latency.long")
            return False, False, True, "response_timeout"
        return False, True, False, "error_injection_out_of_state"

    def _deterministic_latency(self, action: CodecAction) -> int:
        if action.timing_mode == "fixed":
            base = 1
        else:
            token = f"{self._seed}:{self._step_count}:{action.index}".encode()
            base = 2 + hashlib.sha256(token).digest()[0] % 5
        return base + action.backpressure_cycles

    def _cover(self, *bins: str) -> None:
        self._cover_many(bins)

    def _cover_many(self, bins: Iterable[str]) -> None:
        known = set(self._bin_names)
        for bin_name in bins:
            if bin_name not in known:
                raise RuntimeError(f"mock model tried to cover unknown bin {bin_name!r}")
            self._covered.add(bin_name)
