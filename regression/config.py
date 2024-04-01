"""Strict JSON manifest parsing with actionable validation errors."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class ManifestError(ValueError):
    """Raised when a regression manifest is malformed or inconsistent."""


_NAME = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]*$")
_EXPECTED_RESULTS = {"pass", "fail"}
_FLOWS = {"uvm", "smoke"}
_SEED_POLICIES = {"fixed", "derived", "random"}
_MOCK_BEHAVIORS = {"pass", "fail", "assertion", "uvm_error", "infra", "timeout"}


@dataclass(frozen=True)
class SeedSpec:
    policy: str = "derived"
    value: int | None = None


@dataclass(frozen=True)
class Defaults:
    timeout_seconds: float = 300.0
    parallel_jobs: int = 1
    reruns: int = 0
    seed: SeedSpec = field(default_factory=SeedSpec)
    seed_base: int = 20_230_921
    coverage: bool = True
    waveform: bool = False
    uvm_verbosity: str = "UVM_MEDIUM"


@dataclass(frozen=True)
class SimulatorConfig:
    source_manifest: Path
    top: str
    compile_options: tuple[str, ...] = ()
    elaborate_options: tuple[str, ...] = ()
    run_options: tuple[str, ...] = ()
    coverage_options: tuple[str, ...] = ()


@dataclass(frozen=True)
class TestSpec:
    name: str
    uvm_test: str
    suites: tuple[str, ...]
    flow: str
    timeout_seconds: float
    expected_result: str
    coverage: bool
    waveform: bool
    uvm_verbosity: str
    uvm_args: tuple[str, ...]
    seed: SeedSpec
    simulator_options: Mapping[str, tuple[str, ...]]
    mock_behavior: str = "pass"
    mock_delay_seconds: float = 0.0


@dataclass(frozen=True)
class Manifest:
    path: Path
    project_root: Path
    defaults: Defaults
    simulators: Mapping[str, SimulatorConfig]
    tests: tuple[TestSpec, ...]
    suites: Mapping[str, tuple[str, ...]]

    @property
    def tests_by_name(self) -> dict[str, TestSpec]:
        return {test.name: test for test in self.tests}

    def require_tests(self, names: tuple[str, ...] | list[str]) -> tuple[TestSpec, ...]:
        by_name = self.tests_by_name
        unknown = [name for name in names if name not in by_name]
        if unknown:
            raise ManifestError(f"unknown test(s): {', '.join(unknown)}")
        return tuple(by_name[name] for name in names)

    def suite_tests(self, suite: str) -> tuple[TestSpec, ...]:
        if suite not in self.suites:
            choices = ", ".join(sorted(self.suites)) or "<none>"
            raise ManifestError(f"unknown suite {suite!r}; available suites: {choices}")
        return self.require_tests(self.suites[suite])


def _object(value: Any, location: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ManifestError(f"{location} must be a JSON object")
    return dict(value)


def _reject_unknown(data: Mapping[str, Any], allowed: set[str], location: str) -> None:
    unknown = sorted(set(data) - allowed)
    if unknown:
        raise ManifestError(f"{location} contains unknown field(s): {', '.join(unknown)}")


def _array(value: Any, location: str) -> list[Any]:
    if not isinstance(value, list):
        raise ManifestError(f"{location} must be a JSON array")
    return list(value)


def _string(value: Any, location: str) -> str:
    if not isinstance(value, str) or not value:
        raise ManifestError(f"{location} must be a non-empty string")
    return value


def _boolean(value: Any, location: str) -> bool:
    if not isinstance(value, bool):
        raise ManifestError(f"{location} must be true or false")
    return value


def _integer(value: Any, location: str, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ManifestError(f"{location} must be an integer >= {minimum}")
    return value


def _positive_number(value: Any, location: str, allow_zero: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ManifestError(f"{location} must be a number")
    result = float(value)
    if result < 0.0 or (not allow_zero and result == 0.0):
        operator = ">=" if allow_zero else ">"
        raise ManifestError(f"{location} must be {operator} 0")
    return result


def _string_list(value: Any, location: str) -> tuple[str, ...]:
    items = _array(value, location)
    result = tuple(_string(item, f"{location}[{index}]") for index, item in enumerate(items))
    if len(set(result)) != len(result):
        raise ManifestError(f"{location} contains duplicate values")
    return result


def _name(value: Any, location: str) -> str:
    result = _string(value, location)
    if not _NAME.fullmatch(result):
        raise ManifestError(f"{location} contains unsupported characters: {result!r}")
    return result


def _seed(value: Any, location: str) -> SeedSpec:
    if isinstance(value, int) and not isinstance(value, bool):
        if not 1 <= value <= 2_147_483_646:
            raise ManifestError(f"{location} fixed seed must be between 1 and 2147483646")
        return SeedSpec("fixed", value)
    data = _object(value, location)
    _reject_unknown(data, {"policy", "value"}, location)
    policy = _string(data.get("policy", "derived"), f"{location}.policy")
    if policy not in _SEED_POLICIES:
        raise ManifestError(f"{location}.policy must be one of {sorted(_SEED_POLICIES)}")
    raw_value = data.get("value")
    seed_value = None
    if raw_value is not None:
        seed_value = _integer(raw_value, f"{location}.value", 1)
        if seed_value > 2_147_483_646:
            raise ManifestError(f"{location}.value must be <= 2147483646")
    if policy == "fixed" and seed_value is None:
        raise ManifestError(f"{location}.value is required for fixed seed policy")
    if policy != "fixed" and seed_value is not None:
        raise ManifestError(f"{location}.value is only valid for fixed seed policy")
    return SeedSpec(policy, seed_value)


def _options(value: Any, location: str) -> tuple[str, ...]:
    return _string_list(value, location)


def _parse_defaults(raw: Any) -> Defaults:
    data = _object(raw, "defaults")
    _reject_unknown(
        data,
        {
            "timeout_seconds",
            "parallel_jobs",
            "reruns",
            "seed",
            "seed_base",
            "coverage",
            "waveform",
            "uvm_verbosity",
        },
        "defaults",
    )
    return Defaults(
        timeout_seconds=_positive_number(
            data.get("timeout_seconds", 300.0), "defaults.timeout_seconds"
        ),
        parallel_jobs=_integer(data.get("parallel_jobs", 1), "defaults.parallel_jobs", 1),
        reruns=_integer(data.get("reruns", 0), "defaults.reruns"),
        seed=_seed(data.get("seed", {"policy": "derived"}), "defaults.seed"),
        seed_base=_integer(data.get("seed_base", 20_230_921), "defaults.seed_base", 1),
        coverage=_boolean(data.get("coverage", True), "defaults.coverage"),
        waveform=_boolean(data.get("waveform", False), "defaults.waveform"),
        uvm_verbosity=_string(
            data.get("uvm_verbosity", "UVM_MEDIUM"), "defaults.uvm_verbosity"
        ),
    )


def _parse_simulators(
    raw: Any, project_root: Path
) -> dict[str, SimulatorConfig]:
    data = _object(raw, "simulators")
    result: dict[str, SimulatorConfig] = {}
    for simulator, raw_config in data.items():
        name = _name(simulator, f"simulators key {simulator!r}")
        config = _object(raw_config, f"simulators.{name}")
        _reject_unknown(
            config,
            {
                "source_manifest",
                "top",
                "compile_options",
                "elaborate_options",
                "run_options",
                "coverage_options",
            },
            f"simulators.{name}",
        )
        raw_source = _string(
            config.get("source_manifest", "uvm.f"), f"simulators.{name}.source_manifest"
        )
        source_path = Path(raw_source)
        if not source_path.is_absolute():
            source_path = (project_root / source_path).resolve()
        if not source_path.is_file():
            raise ManifestError(
                f"simulators.{name}.source_manifest does not exist: {source_path}"
            )
        result[name] = SimulatorConfig(
            source_manifest=source_path,
            top=_name(config.get("top", "tb_top"), f"simulators.{name}.top"),
            compile_options=_options(
                config.get("compile_options", []), f"simulators.{name}.compile_options"
            ),
            elaborate_options=_options(
                config.get("elaborate_options", []), f"simulators.{name}.elaborate_options"
            ),
            run_options=_options(
                config.get("run_options", []), f"simulators.{name}.run_options"
            ),
            coverage_options=_options(
                config.get("coverage_options", []), f"simulators.{name}.coverage_options"
            ),
        )
    if not result:
        raise ManifestError("simulators must define at least one adapter configuration")
    return result


def _parse_test(raw: Any, index: int, defaults: Defaults) -> TestSpec:
    location = f"tests[{index}]"
    data = _object(raw, location)
    _reject_unknown(
        data,
        {
            "name",
            "uvm_test",
            "suites",
            "flow",
            "timeout_seconds",
            "expected_result",
            "coverage",
            "waveform",
            "uvm_verbosity",
            "uvm_args",
            "seed",
            "simulator_options",
            "mock_behavior",
            "mock_delay_seconds",
        },
        location,
    )
    name = _name(data.get("name"), f"{location}.name")
    suites = _string_list(data.get("suites", []), f"{location}.suites")
    flow = _string(data.get("flow", "uvm"), f"{location}.flow")
    if flow not in _FLOWS:
        raise ManifestError(f"{location}.flow must be one of {sorted(_FLOWS)}")
    expected_result = _string(
        data.get("expected_result", "pass"), f"{location}.expected_result"
    )
    if expected_result not in _EXPECTED_RESULTS:
        raise ManifestError(
            f"{location}.expected_result must be one of {sorted(_EXPECTED_RESULTS)}"
        )
    simulator_options_data = _object(
        data.get("simulator_options", {}), f"{location}.simulator_options"
    )
    simulator_options = {
        _name(key, f"{location}.simulator_options key"): _options(
            value, f"{location}.simulator_options.{key}"
        )
        for key, value in simulator_options_data.items()
    }
    mock_behavior = _string(data.get("mock_behavior", "pass"), f"{location}.mock_behavior")
    if mock_behavior not in _MOCK_BEHAVIORS:
        raise ManifestError(
            f"{location}.mock_behavior must be one of {sorted(_MOCK_BEHAVIORS)}"
        )
    return TestSpec(
        name=name,
        uvm_test=_name(data.get("uvm_test", name), f"{location}.uvm_test"),
        suites=suites,
        flow=flow,
        timeout_seconds=_positive_number(
            data.get("timeout_seconds", defaults.timeout_seconds),
            f"{location}.timeout_seconds",
        ),
        expected_result=expected_result,
        coverage=_boolean(data.get("coverage", defaults.coverage), f"{location}.coverage"),
        waveform=_boolean(data.get("waveform", defaults.waveform), f"{location}.waveform"),
        uvm_verbosity=_string(
            data.get("uvm_verbosity", defaults.uvm_verbosity), f"{location}.uvm_verbosity"
        ),
        uvm_args=_options(data.get("uvm_args", []), f"{location}.uvm_args"),
        seed=_seed(data.get("seed", {"policy": defaults.seed.policy, **(
            {"value": defaults.seed.value} if defaults.seed.value is not None else {}
        )}), f"{location}.seed"),
        simulator_options=simulator_options,
        mock_behavior=mock_behavior,
        mock_delay_seconds=_positive_number(
            data.get("mock_delay_seconds", 0.0),
            f"{location}.mock_delay_seconds",
            allow_zero=True,
        ),
    )


def _parse_suites(raw: Any, tests: tuple[TestSpec, ...]) -> dict[str, tuple[str, ...]]:
    explicit_data = _object(raw, "suites")
    test_names = {test.name for test in tests}
    result: dict[str, list[str]] = {}
    for suite, raw_names in explicit_data.items():
        suite_name = _name(suite, f"suites key {suite!r}")
        names = _string_list(raw_names, f"suites.{suite_name}")
        if not names:
            raise ManifestError(f"suites.{suite_name} must contain at least one test")
        unknown = sorted(set(names) - test_names)
        if unknown:
            raise ManifestError(
                f"suites.{suite_name} references unknown test(s): {', '.join(unknown)}"
            )
        result[suite_name] = list(names)
    for test in tests:
        for suite in test.suites:
            _name(suite, f"suite membership on test {test.name}")
            members = result.setdefault(suite, [])
            if test.name not in members:
                members.append(test.name)
    return {key: tuple(value) for key, value in result.items()}


def load_manifest(path: str | Path) -> Manifest:
    """Read and validate a JSON regression manifest."""

    manifest_path = Path(path).expanduser().resolve()
    try:
        raw_text = manifest_path.read_text(encoding="utf-8")
    except OSError as error:
        raise ManifestError(f"cannot read manifest {manifest_path}: {error}") from error
    try:
        raw = json.loads(raw_text)
    except json.JSONDecodeError as error:
        raise ManifestError(
            f"invalid JSON in {manifest_path}:{error.lineno}:{error.colno}: {error.msg}"
        ) from error
    data = _object(raw, "manifest")
    _reject_unknown(
        data,
        {"schema_version", "project_root", "defaults", "simulators", "suites", "tests"},
        "manifest",
    )
    version = _integer(data.get("schema_version"), "schema_version", 1)
    if version != 1:
        raise ManifestError(f"unsupported schema_version {version}; expected 1")
    raw_root = _string(data.get("project_root", "../.."), "project_root")
    project_root_path = Path(raw_root)
    if not project_root_path.is_absolute():
        project_root_path = (manifest_path.parent / project_root_path).resolve()
    defaults = _parse_defaults(data.get("defaults", {}))
    simulators = _parse_simulators(data.get("simulators", {}), project_root_path)
    raw_tests = _array(data.get("tests"), "tests")
    tests = tuple(_parse_test(value, index, defaults) for index, value in enumerate(raw_tests))
    if not tests:
        raise ManifestError("tests must define at least one test")
    names = [test.name for test in tests]
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ManifestError(f"duplicate test name(s): {', '.join(duplicates)}")
    unknown_option_simulators = sorted(
        {
            simulator
            for test in tests
            for simulator in test.simulator_options
            if simulator not in simulators
        }
    )
    if unknown_option_simulators:
        raise ManifestError(
            "test simulator_options reference unconfigured simulator(s): "
            + ", ".join(unknown_option_simulators)
        )
    suites = _parse_suites(data.get("suites", {}), tests)
    return Manifest(
        path=manifest_path,
        project_root=project_root_path,
        defaults=defaults,
        simulators=simulators,
        tests=tests,
        suites=suites,
    )
