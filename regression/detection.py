"""Simulator-log failure detection and artifact verification."""

from __future__ import annotations

import re
from pathlib import Path

from regression.models import Detection, Outcome

_ASSERTION = re.compile(
    r"(?:assertion\s+(?:failure|failed|error|violation)|\bSVA\b.*\b(?:fail|error))",
    re.IGNORECASE,
)
_UVM_ERROR_SUMMARY = re.compile(r"\bUVM_ERROR\s*:\s*(\d+)\b")
_UVM_FATAL_SUMMARY = re.compile(r"\bUVM_FATAL\s*:\s*(\d+)\b")
_UVM_ERROR_EVENT = re.compile(r"\bUVM_ERROR(?:\s+@|\s*\[)")
_UVM_FATAL_EVENT = re.compile(r"\bUVM_FATAL(?:\s+@|\s*\[)")
_FAILURE_MARKER = re.compile(r"\[REGRESSION\]\s+FAILURE\s*:\s*(.*)", re.IGNORECASE)
_INFRASTRUCTURE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("explicit infrastructure failure", re.compile(r"REGRESSION_INFRA_FAILURE", re.I)),
    ("license checkout failure", re.compile(r"(?:license checkout|checkout.*license).*fail", re.I)),
    ("missing executable", re.compile(r"(?:command not found|no such file or directory)", re.I)),
    ("simulator internal error", re.compile(r"\binternal (?:error|exception)\b", re.I)),
    ("process crash", re.compile(r"(?:segmentation fault|core dumped|fatal signal)", re.I)),
)


def _summary_or_events(
    text: str, summary_pattern: re.Pattern[str], event_pattern: re.Pattern[str]
) -> int:
    summary_values = [int(value) for value in summary_pattern.findall(text)]
    events = sum(1 for line in text.splitlines() if event_pattern.search(line))
    return max((*summary_values, events), default=0)


def detect_failures(text: str) -> Detection:
    assertion_lines = {line.strip() for line in text.splitlines() if _ASSERTION.search(line)}
    infrastructure = tuple(
        label for label, pattern in _INFRASTRUCTURE_PATTERNS if pattern.search(text)
    )
    markers = tuple(
        match.group(1).strip() or "explicit failure marker"
        for match in _FAILURE_MARKER.finditer(text)
    )
    return Detection(
        assertion_failures=len(assertion_lines),
        uvm_errors=_summary_or_events(text, _UVM_ERROR_SUMMARY, _UVM_ERROR_EVENT),
        uvm_fatals=_summary_or_events(text, _UVM_FATAL_SUMMARY, _UVM_FATAL_EVENT),
        infrastructure_failures=infrastructure,
        failure_markers=markers,
    )


def classify_outcome(
    expected_result: str,
    returncode: int | None,
    timed_out: bool,
    detection: Detection,
) -> tuple[Outcome, tuple[str, ...]]:
    reasons: list[str] = []
    if timed_out:
        return Outcome.TIMEOUT, ("per-test timeout expired",)
    if detection.infrastructure_failures:
        return Outcome.ERROR, detection.infrastructure_failures
    if returncode is None:
        return Outcome.ERROR, ("process did not provide an exit status",)
    if returncode != 0:
        reasons.append(f"nonzero exit status {returncode}")
    if detection.assertion_failures:
        reasons.append(f"{detection.assertion_failures} assertion failure(s)")
    if detection.uvm_errors:
        reasons.append(f"{detection.uvm_errors} UVM error(s)")
    if detection.uvm_fatals:
        reasons.append(f"{detection.uvm_fatals} UVM fatal(s)")
    reasons.extend(detection.failure_markers)
    failed = bool(reasons)
    if expected_result == "fail":
        if failed:
            return Outcome.EXPECTED_FAILURE, tuple(reasons)
        return Outcome.UNEXPECTED_PASS, ("test was expected to fail but passed",)
    if failed:
        return Outcome.FAILED, tuple(reasons)
    return Outcome.PASSED, ()


def collect_artifacts(
    coverage_path: Path | None, waveform_path: Path | None
) -> tuple[Path | None, Path | None, tuple[str, ...]]:
    missing: list[str] = []
    collected_coverage = None
    collected_waveform = None
    if coverage_path:
        if coverage_path.exists():
            collected_coverage = coverage_path
        else:
            missing.append(f"coverage database not produced: {coverage_path}")
    if waveform_path:
        if waveform_path.exists():
            collected_waveform = waveform_path
        else:
            missing.append(f"waveform not produced: {waveform_path}")
    return collected_coverage, collected_waveform, tuple(missing)
