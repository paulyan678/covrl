"""Gymnasium-compatible coverage-guided codec stimulus environment."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

import numpy as np

from rl.actions import DEFAULT_ACTION_CATALOG, ActionCatalog
from rl.backends.base import (
    BackendStep,
    CoverageBackend,
    CoverageSnapshot,
    ProtocolState,
)
from rl.backends.mock import MockCoverageBackend
from rl.masking import compute_action_mask, configuration_choice_mask

try:  # The mock model and unit tests remain usable with only NumPy installed.
    import gymnasium as gym
    from gymnasium import spaces

    GYMNASIUM_AVAILABLE = True
    _EnvBase = gym.Env
except ImportError:  # pragma: no cover - selected according to host dependencies
    GYMNASIUM_AVAILABLE = False

    class _EnvBase:  # type: ignore[no-redef]
        np_random: np.random.Generator

        def reset(self, *, seed: int | None = None, options: object = None) -> None:
            del options
            if seed is not None or not hasattr(self, "np_random"):
                self.np_random = np.random.default_rng(seed)

        def close(self) -> None:
            return None

    class _Discrete:
        def __init__(self, n: int) -> None:
            self.n = n

        def contains(self, value: object) -> bool:
            if isinstance(value, (bool, np.bool_)) or not isinstance(value, (int, np.integer)):
                return False
            integer = int(value)
            return integer == value and 0 <= integer < self.n

    class _Box:
        def __init__(
            self,
            low: float,
            high: float,
            shape: tuple[int, ...],
            dtype: np.dtype[Any] | type[np.generic],
        ) -> None:
            self.low = low
            self.high = high
            self.shape = shape
            self.dtype = np.dtype(dtype)

        def contains(self, value: object) -> bool:
            array = np.asarray(value)
            return bool(
                array.shape == self.shape
                and np.all(array >= self.low)
                and np.all(array <= self.high)
            )

    class _MultiBinary:
        def __init__(self, n: int) -> None:
            self.n = n

        def contains(self, value: object) -> bool:
            array = np.asarray(value)
            return bool(array.shape == (self.n,) and np.all((array == 0) | (array == 1)))

    class _Dict:
        def __init__(self, values: Mapping[str, Any]) -> None:
            self.spaces = dict(values)

        def contains(self, value: object) -> bool:
            if not isinstance(value, Mapping) or set(value) != set(self.spaces):
                return False
            return all(bool(space.contains(value[name])) for name, space in self.spaces.items())

    class _FallbackSpaces:
        Discrete = _Discrete
        Box = _Box
        MultiBinary = _MultiBinary
        Dict = _Dict

    spaces = _FallbackSpaces()  # type: ignore[assignment]


@dataclass(frozen=True, slots=True)
class RewardConfig:
    new_bin: float = 1.0
    coverage_target_bonus: float = 5.0
    redundant: float = -0.05
    illegal_action: float = -2.0
    timeout: float = -3.0
    invalid_transition: float = -3.0
    repeated_action: float = -0.10
    infrastructure_failure: float = -10.0


@dataclass(frozen=True, slots=True)
class EpisodeConfig:
    max_steps: int = 200
    history_length: int = 8
    coverage_target: float = 0.90
    max_illegal_attempts: int = 3
    stale_step_limit: int | None = 60

    def __post_init__(self) -> None:
        if self.max_steps <= 0:
            raise ValueError("max_steps must be positive")
        if self.history_length <= 0:
            raise ValueError("history_length must be positive")
        if not 0.0 < self.coverage_target <= 1.0:
            raise ValueError("coverage_target must be in (0, 1]")
        if self.max_illegal_attempts <= 0:
            raise ValueError("max_illegal_attempts must be positive")
        if self.stale_step_limit is not None and self.stale_step_limit <= 0:
            raise ValueError("stale_step_limit must be positive or None")


class CoverageGuidedCodecEnv(_EnvBase):
    """Action-masked RL environment over a replaceable coverage backend.

    Termination means the target was reached or the verification
    infrastructure failed. Truncation means the external timeout fired, the
    transaction budget was exhausted, the episode became stale, or repeated
    direct callers ignored the advertised action mask.
    """

    metadata = {"render_modes": []}

    def __init__(
        self,
        backend: CoverageBackend | None = None,
        catalog: ActionCatalog = DEFAULT_ACTION_CATALOG,
        episode_config: EpisodeConfig | None = None,
        reward_config: RewardConfig | None = None,
    ) -> None:
        self.backend = backend or MockCoverageBackend()
        self.catalog = catalog
        self.episode_config = episode_config or EpisodeConfig()
        self.reward_config = reward_config or RewardConfig()
        if len(set(self.backend.bin_names)) != len(self.backend.bin_names):
            raise ValueError("coverage backend bin names must be unique")

        self._bin_index = {name: index for index, name in enumerate(self.backend.bin_names)}
        self._configuration_dimensions = {
            field: tuple(
                dict.fromkeys(
                    getattr(action, field)
                    for action in self.catalog
                    if getattr(action, field) is not None
                )
            )
            for field in ("profile", "resolution", "bit_depth", "quantizer")
        }
        configuration_vector_size = sum(
            len(choices) for choices in self._configuration_dimensions.values()
        )
        self.action_space = spaces.Discrete(len(self.catalog))
        history = self.episode_config.history_length
        self.observation_space = spaces.Dict(
            {
                "coverage": spaces.MultiBinary(len(self.backend.bin_names)),
                "recent_transactions": spaces.Box(
                    low=-1.0,
                    high=1.0,
                    shape=(history,),
                    dtype=np.float32,
                ),
                "protocol_state": spaces.MultiBinary(len(ProtocolState)),
                "current_configuration": spaces.MultiBinary(configuration_vector_size),
                "available_configurations": spaces.MultiBinary(len(self.catalog)),
                "remaining_budget": spaces.Box(
                    low=0.0,
                    high=1.0,
                    shape=(1,),
                    dtype=np.float32,
                ),
                "recent_rewards": spaces.Box(
                    low=-100.0,
                    high=100.0,
                    shape=(history,),
                    dtype=np.float32,
                ),
                "recent_coverage_gains": spaces.Box(
                    low=0.0,
                    high=1.0,
                    shape=(history,),
                    dtype=np.float32,
                ),
                "action_mask": spaces.MultiBinary(len(self.catalog)),
            }
        )
        self._snapshot = self.backend.snapshot()
        self._backend_seed = 0
        self._step_count = 0
        self._episode_reward = 0.0
        self._illegal_attempts = 0
        self._stale_steps = 0
        self._last_action: int | None = None
        self._done = False
        self._recent_actions: list[int] = []
        self._recent_rewards: list[float] = []
        self._recent_gains: list[int] = []

    def reset(
        self,
        *,
        seed: int | None = None,
        options: dict[str, object] | None = None,
    ) -> tuple[dict[str, np.ndarray], dict[str, object]]:
        super().reset(seed=seed, options=options)
        self._backend_seed = (
            int(seed)
            if seed is not None
            else int(self.np_random.integers(0, np.iinfo(np.int32).max))
        )
        self._snapshot = self.backend.reset(seed=self._backend_seed)
        self._validate_snapshot(self._snapshot)
        self._step_count = 0
        self._episode_reward = 0.0
        self._illegal_attempts = 0
        self._stale_steps = 0
        self._last_action = None
        self._done = False
        self._recent_actions.clear()
        self._recent_rewards.clear()
        self._recent_gains.clear()
        return self._observation(), self._info(coverage_gain=0, action_reached_backend=False)

    def step(
        self,
        action: int,
    ) -> tuple[dict[str, np.ndarray], float, bool, bool, dict[str, object]]:
        if self._done:
            raise RuntimeError("step() called after episode completion; call reset()")
        action_index = self._coerce_action(action)
        mask = self.action_masks()
        self._step_count += 1

        if not bool(mask[action_index]):
            return self._masked_illegal_step(action_index)

        previous_snapshot = self._snapshot
        backend_step = self.backend.execute(self.catalog[action_index])
        self.backend.validate_step(backend_step, previous_snapshot)
        self._snapshot = backend_step.snapshot
        gain = len(backend_step.newly_covered)
        reward = gain * self.reward_config.new_bin
        if gain == 0:
            reward += self.reward_config.redundant
            self._stale_steps += 1
        else:
            self._stale_steps = 0
        if self._last_action == action_index and gain == 0:
            reward += self.reward_config.repeated_action
        if backend_step.invalid_transition:
            reward += self.reward_config.invalid_transition
            self._illegal_attempts += 1
        if backend_step.timed_out:
            reward += self.reward_config.timeout
        if backend_step.infrastructure_failure:
            reward += self.reward_config.infrastructure_failure

        terminated, truncated, reason = self._episode_status(backend_step)
        if terminated and reason == "coverage_target":
            reward += self.reward_config.coverage_target_bonus
        self._record(action_index, reward, gain)
        self._done = terminated or truncated
        info = self._info(
            coverage_gain=gain,
            action_reached_backend=True,
            backend_step=backend_step,
            reason=reason,
        )
        return self._observation(), float(reward), terminated, truncated, info

    def action_masks(self) -> np.ndarray:
        """SB3-Contrib convention used during rollout and prediction."""

        return compute_action_mask(self.catalog, self._snapshot)

    @property
    def snapshot(self) -> CoverageSnapshot:
        return self._snapshot

    def _masked_illegal_step(
        self,
        action_index: int,
    ) -> tuple[dict[str, np.ndarray], float, bool, bool, dict[str, object]]:
        self._illegal_attempts += 1
        self._stale_steps += 1
        reward = self.reward_config.illegal_action
        if self._last_action == action_index:
            reward += self.reward_config.repeated_action
        reason: str | None = None
        if self._illegal_attempts >= self.episode_config.max_illegal_attempts:
            reason = "illegal_action_limit"
        elif self._step_count >= self.episode_config.max_steps:
            reason = "step_budget"
        elif (
            self.episode_config.stale_step_limit is not None
            and self._stale_steps >= self.episode_config.stale_step_limit
        ):
            reason = "stale_limit"
        truncated = reason is not None
        self._record(action_index, reward, 0)
        self._done = truncated
        info = self._info(
            coverage_gain=0,
            action_reached_backend=False,
            reason=reason,
        )
        info["illegal_action"] = True
        return self._observation(), float(reward), False, truncated, info

    def _episode_status(self, step: BackendStep) -> tuple[bool, bool, str | None]:
        if step.infrastructure_failure:
            return True, False, "infrastructure_failure"
        if step.timed_out:
            return False, True, "backend_timeout"
        if self._snapshot.coverage_fraction >= self.episode_config.coverage_target:
            return True, False, "coverage_target"
        if self._illegal_attempts >= self.episode_config.max_illegal_attempts:
            return False, True, "illegal_action_limit"
        if self._step_count >= self.episode_config.max_steps:
            return False, True, "step_budget"
        stale_limit = self.episode_config.stale_step_limit
        if stale_limit is not None and self._stale_steps >= stale_limit:
            return False, True, "stale_limit"
        return False, False, None

    def _record(self, action_index: int, reward: float, gain: int) -> None:
        history = self.episode_config.history_length
        self._last_action = action_index
        self._episode_reward += reward
        self._recent_actions = (self._recent_actions + [action_index])[-history:]
        self._recent_rewards = (self._recent_rewards + [reward])[-history:]
        self._recent_gains = (self._recent_gains + [gain])[-history:]

    def _observation(self) -> dict[str, np.ndarray]:
        history = self.episode_config.history_length
        coverage = np.zeros(len(self.backend.bin_names), dtype=np.int8)
        for name in self._snapshot.covered_bins:
            coverage[self._bin_index[name]] = 1
        state = np.zeros(len(ProtocolState), dtype=np.int8)
        state[int(self._snapshot.protocol_state)] = 1
        recent_actions = np.full(history, -1.0, dtype=np.float32)
        if self._recent_actions:
            scale = max(1, len(self.catalog) - 1)
            values = np.asarray(self._recent_actions, dtype=np.float32) / scale
            recent_actions[-len(values) :] = values
        recent_rewards = self._right_aligned(self._recent_rewards, history)
        gains = [value / max(1, len(self.backend.bin_names)) for value in self._recent_gains]
        recent_gains = self._right_aligned(gains, history)
        return {
            "coverage": coverage,
            "recent_transactions": recent_actions,
            "protocol_state": state,
            "current_configuration": self._configuration_vector(),
            "available_configurations": configuration_choice_mask(self.catalog, self._snapshot),
            "remaining_budget": np.asarray(
                [max(0.0, 1.0 - self._step_count / self.episode_config.max_steps)],
                dtype=np.float32,
            ),
            "recent_rewards": np.clip(recent_rewards, -100.0, 100.0),
            "recent_coverage_gains": recent_gains,
            "action_mask": self.action_masks().astype(np.int8),
        }

    def _info(
        self,
        *,
        coverage_gain: int,
        action_reached_backend: bool,
        backend_step: BackendStep | None = None,
        reason: str | None = None,
    ) -> dict[str, object]:
        info: dict[str, object] = {
            "backend": self._snapshot.metadata.get("backend", type(self.backend).__name__),
            "episode_seed": self._backend_seed,
            "coverage_count": self._snapshot.coverage_count,
            "coverage_total": self._snapshot.total_bins,
            "coverage_fraction": self._snapshot.coverage_fraction,
            "coverage_gain": coverage_gain,
            "protocol_state": self._snapshot.protocol_state.name.lower(),
            "step": self._step_count,
            "episode_reward": self._episode_reward,
            "action_reached_backend": action_reached_backend,
            "termination_reason": reason,
        }
        if backend_step is not None:
            info.update(
                {
                    "backend_status": backend_step.status,
                    "latency_cycles": backend_step.latency_cycles,
                    "new_bins": list(backend_step.newly_covered),
                    "timed_out": backend_step.timed_out,
                    "infrastructure_failure": backend_step.infrastructure_failure,
                }
            )
        return info

    def _validate_snapshot(self, snapshot: CoverageSnapshot) -> None:
        unknown = set(snapshot.covered_bins).difference(self._bin_index)
        if unknown:
            raise ValueError(f"initial snapshot contains unknown bins: {sorted(unknown)}")
        if snapshot.total_bins != len(self.backend.bin_names):
            raise ValueError("initial snapshot total_bins does not match backend bin_names")

    def _configuration_vector(self) -> np.ndarray:
        vector = np.zeros(
            sum(len(choices) for choices in self._configuration_dimensions.values()),
            dtype=np.int8,
        )
        configuration = self._snapshot.current_configuration
        if configuration is None:
            return vector
        offset = 0
        for field, choices in self._configuration_dimensions.items():
            value = configuration.get(field)
            if value in choices:
                vector[offset + choices.index(value)] = 1
            offset += len(choices)
        return vector

    def _coerce_action(self, action: int) -> int:
        array = np.asarray(action)
        if array.size != 1:
            raise ValueError("action must be one scalar discrete index")
        scalar = array.reshape(-1)[0].item()
        if not self.action_space.contains(scalar):
            raise ValueError(
                f"action {scalar!r} is outside the discrete integer range "
                f"[0, {len(self.catalog) - 1}]"
            )
        value = int(scalar)
        return value

    @staticmethod
    def _right_aligned(values: list[float], length: int) -> np.ndarray:
        array = np.zeros(length, dtype=np.float32)
        if values:
            suffix = np.asarray(values[-length:], dtype=np.float32)
            array[-len(suffix) :] = suffix
        return array
