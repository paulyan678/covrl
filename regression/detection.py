"""Simulator-log failure detection and artifact verification."""

from __future__ import annotations

import re
from collections.abc import Iterable
from pathlib import Path

from regression.models import Detection, Outcome

_ASSERTION = re.compile(
    r"(?:\bassertions?\b[^\n]*\b(?:fail(?:ed|s|ures?)?|errors?|violations?)\b|"
    r"\bSVA\b[^\n]*\b(?:fail(?:ed|s|ures?)?|errors?|violations?)\b)",
    re.IGNORECASE,
)
_ZERO_ASSERTION_SUMMARY = re.compile(
    r"\b(?:assertions?|SVA)(?:\s+(?:errors?|fail(?:ed|s|ures?)?|violations?))?"
    r"\s*[:=]\s*0\b",
    re.IGNORECASE,
)
_ASSERTION_SUMMARY = re.compile(
    r"\b(?:assertions?|SVA)\s+(?:errors?|fail(?:ed|s|ures?)?|violations?)"
    r"\s*[:=]\s*(\d+)\b",
    re.IGNORECASE,
)
_UVM_ERROR_SUMMARY = re.compile(r"\bUVM_ERROR\s*:\s*(\d+)\b")
_UVM_FATAL_SUMMARY = re.compile(r"\bUVM_FATAL\s*:\s*(\d+)\b")
_UVM_ERROR_EVENT = re.compile(r"\bUVM_ERROR(?:\s+@|\s*\[|\s+\S+\(\d+\)\s+@)")
_UVM_FATAL_EVENT = re.compile(r"\bUVM_FATAL(?:\s+@|\s*\[|\s+\S+\(\d+\)\s+@)")
_FAILURE_MARKER = re.compile(r"\[REGRESSION\]\s+FAILURE\s*:\s*(.*)", re.IGNORECASE)
_INFRASTRUCTURE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("explicit infrastructure failure", re.compile(r"REGRESSION_INFRA_FAILURE", re.I)),
    ("license checkout failure", re.compile(r"(?:license checkout|checkout.*license).*fail", re.I)),
    ("missing executable", re.compile(r"(?:command not found|no such file or directory)", re.I)),
    ("simulator internal error", re.compile(r"\binternal (?:error|exception)\b", re.I)),
    ("process crash", re.compile(r"(?:segmentation fault|core dumped|fatal signal)", re.I)),
)


def _detect_lines(lines: Iterable[str]) -> Detection:
    assertion_lines: set[str] = set()
    assertion_summary = 0
    uvm_error_summary = 0
    uvm_fatal_summary = 0
    uvm_error_events = 0
    uvm_fatal_events = 0
    infrastructure_labels: set[str] = set()
    markers: list[str] = []
    for line in lines:
        if _ASSERTION.search(line) and not _ZERO_ASSERTION_SUMMARY.search(line):
            assertion_lines.add(line.strip())
        assertion_summary = max(
            [assertion_summary, *(int(value) for value in _ASSERTION_SUMMARY.findall(line))]
        )
        uvm_error_summary = max(
            [uvm_error_summary, *(int(value) for value in _UVM_ERROR_SUMMARY.findall(line))]
        )
        uvm_fatal_summary = max(
            [uvm_fatal_summary, *(int(value) for value in _UVM_FATAL_SUMMARY.findall(line))]
        )
        uvm_error_events += int(bool(_UVM_ERROR_EVENT.search(line)))
        uvm_fatal_events += int(bool(_UVM_FATAL_EVENT.search(line)))
        for label, pattern in _INFRASTRUCTURE_PATTERNS:
            if pattern.search(line):
                infrastructure_labels.add(label)
        markers.extend(
            match.group(1).strip() or "explicit failure marker"
            for match in _FAILURE_MARKER.finditer(line)
        )
    return Detection(
        assertion_failures=max(assertion_summary, len(assertion_lines)),
        uvm_errors=max(uvm_error_summary, uvm_error_events),
        uvm_fatals=max(uvm_fatal_summary, uvm_fatal_events),
        infrastructure_failures=tuple(
            label for label, _ in _INFRASTRUCTURE_PATTERNS if label in infrastructure_labels
        ),
        failure_markers=tuple(markers),
    )


def detect_failures(text: str) -> Detection:
    return _detect_lines(text.splitlines())


def detect_failures_file(path: Path) -> Detection:
    """Parse an arbitrarily large simulator log without loading it into memory."""

    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return _detect_lines(handle)


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
