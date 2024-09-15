"""Machine-readable JSON and escaped Markdown/HTML regression reports."""

from __future__ import annotations

import html
import json
import math
from collections.abc import Iterable
from pathlib import Path

from regression.models import Outcome, Provenance, RunSummary, TestResult


def _validate_loaded_summary(summary: RunSummary) -> None:
    if not summary.selected_tests:
        raise ValueError("selected_tests must not be empty")
    if len(set(summary.selected_tests)) != len(summary.selected_tests):
        raise ValueError("selected_tests contains duplicate names")
    selected = set(summary.selected_tests)
    attempts: set[tuple[str, int]] = set()
    by_test: dict[str, list[int]] = {name: [] for name in summary.selected_tests}
    for result in summary.results:
        if result.test_name not in selected:
            raise ValueError(f"result references unselected test {result.test_name!r}")
        key = (result.test_name, result.attempt)
        if key in attempts:
            raise ValueError(f"duplicate result attempt {result.test_name!r} #{result.attempt}")
        attempts.add(key)
        by_test[result.test_name].append(result.attempt)
        if result.attempt < 1:
            raise ValueError("result attempts must be positive")
        if result.simulator != summary.simulator:
            raise ValueError(f"result simulator differs for {result.test_name!r}")
        if result.provenance is not summary.provenance:
            raise ValueError(f"result provenance differs for {result.test_name!r}")
        if not 1 <= result.seed <= 2_147_483_646:
            raise ValueError(f"result seed is invalid for {result.test_name!r}")
        if result.expected_result not in {"pass", "fail"}:
            raise ValueError(f"expected_result is invalid for {result.test_name!r}")
        if summary.provenance is Provenance.DRY_RUN:
            if result.outcome not in {Outcome.DRY_RUN, Outcome.UNSUPPORTED}:
                raise ValueError(
                    f"dry-run provenance has executed outcome for {result.test_name!r}"
                )
        elif result.outcome is Outcome.DRY_RUN:
            raise ValueError(f"executed provenance has dry-run outcome for {result.test_name!r}")
        impossible_for_expectation = (
            result.expected_result == "pass"
            and result.outcome in {Outcome.EXPECTED_FAILURE, Outcome.UNEXPECTED_PASS}
        ) or (
            result.expected_result == "fail" and result.outcome in {Outcome.PASSED, Outcome.FAILED}
        )
        if impossible_for_expectation:
            raise ValueError(
                f"outcome is inconsistent with expected_result for {result.test_name!r}"
            )
        if result.outcome in {Outcome.PASSED, Outcome.EXPECTED_FAILURE}:
            if (
                result.command is None
                or result.returncode is None
                or not result.started_at
                or result.log_path is None
            ):
                raise ValueError(
                    f"successful result lacks execution evidence for {result.test_name!r}"
                )
        counters = (result.assertion_failures, result.uvm_errors, result.uvm_fatals)
        if any(value < 0 for value in counters):
            raise ValueError(f"failure counters are invalid for {result.test_name!r}")
        if result.outcome is Outcome.PASSED and (
            result.returncode != 0 or any(counters) or result.failure_reasons
        ):
            raise ValueError(f"passing result contains failure evidence for {result.test_name!r}")
        if result.outcome is Outcome.EXPECTED_FAILURE and not result.failure_reasons:
            raise ValueError(f"expected failure lacks failure evidence for {result.test_name!r}")
        if not math.isfinite(result.duration_seconds) or result.duration_seconds < 0:
            raise ValueError(f"duration is invalid for {result.test_name!r}")
    missing = [name for name, values in by_test.items() if not values]
    if missing:
        raise ValueError("missing result for selected test(s): " + ", ".join(missing))
    for name, values in by_test.items():
        ordered = sorted(values)
        if ordered != list(range(1, max(ordered) + 1)):
            raise ValueError(f"result attempts are not contiguous for {name!r}")
    if not summary.has_complete_results:
        raise ValueError("summary does not contain exactly one final result per selected test")


def write_json(summary: RunSummary, path: Path) -> Path:
    _validate_loaded_summary(summary)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(summary.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return path


def load_json(path: Path) -> RunSummary:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError(f"cannot load regression results {path}: {error}") from error
    if not isinstance(data, dict):
        raise ValueError(f"regression results must contain a JSON object: {path}")
    try:
        summary = RunSummary.from_dict(data)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f"invalid regression result schema in {path}: {error}") from error
    if summary.schema_version != 1:
        raise ValueError(
            f"unsupported result schema_version {summary.schema_version} in {path}; expected 1"
        )
    _validate_loaded_summary(summary)
    return summary


def _md_cell(value: object) -> str:
    return html.escape(str(value), quote=False).replace("|", "\\|").replace("\n", " ")


def _reason(result: TestResult) -> str:
    return "; ".join(result.failure_reasons)


def _artifacts(result: TestResult) -> str:
    values = (
        ("log", result.log_path),
        ("coverage", result.coverage_path),
        ("wave", result.waveform_path),
    )
    return "; ".join(f"{label}={path}" for label, path in values if path)


def markdown_text(summary: RunSummary) -> str:
    lines = [
        "# Regression Report",
        "",
        f"- Simulator: `{_md_cell(summary.simulator)}`",
        f"- Provenance: `{summary.provenance.value}`",
        f"- Started: `{_md_cell(summary.started_at)}`",
        f"- Finished: `{_md_cell(summary.finished_at)}`",
        f"- Executed tests successful: `{'yes' if summary.successful else 'no'}`",
        f"- Plan only: `{'yes' if summary.plan_only else 'no'}`",
        "",
        "## Final results",
        "",
        "| Test | Attempt | Seed | Outcome | Runtime (s) | Assertions | UVM E/F | "
        "Artifacts | Reason |",
        "|---|---:|---:|---|---:|---:|---:|---|---|",
    ]
    for result in summary.final_results:
        lines.append(
            "| "
            + " | ".join(
                (
                    _md_cell(result.test_name),
                    str(result.attempt),
                    str(result.seed),
                    result.outcome.value,
                    f"{result.duration_seconds:.3f}",
                    str(result.assertion_failures),
                    f"{result.uvm_errors}/{result.uvm_fatals}",
                    _md_cell(_artifacts(result)),
                    _md_cell(_reason(result)),
                )
            )
            + " |"
        )
    if len(summary.results) > len(summary.final_results):
        lines.extend(
            [
                "",
                "## All attempts",
                "",
                "| Test | Attempt | Seed | Outcome | Runtime (s) |",
                "|---|---:|---:|---|---:|",
            ]
        )
        for result in summary.results:
            lines.append(
                f"| {_md_cell(result.test_name)} | {result.attempt} | {result.seed} | "
                f"{result.outcome.value} | {result.duration_seconds:.3f} |"
            )
    if summary.stages:
        lines.extend(
            [
                "",
                "## Build stages",
                "",
                "| Stage | Outcome | Runtime (s) | Log | Reason |",
                "|---|---|---:|---|---|",
            ]
        )
        for stage in summary.stages:
            lines.append(
                f"| {_md_cell(stage.name)} | {stage.outcome.value} | "
                f"{stage.duration_seconds:.3f} | "
                f"{_md_cell(stage.command.log_path or '')} | {_md_cell(stage.reason)} |"
            )
    lines.append("")
    return "\n".join(lines)


def write_markdown(summary: RunSummary, path: Path) -> Path:
    _validate_loaded_summary(summary)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(markdown_text(summary), encoding="utf-8")
    return path


def html_text(summary: RunSummary) -> str:
    rows: list[str] = []
    for result in summary.final_results:
        cells = (
            result.test_name,
            result.attempt,
            result.seed,
            result.outcome.value,
            f"{result.duration_seconds:.3f}",
            result.assertion_failures,
            f"{result.uvm_errors}/{result.uvm_fatals}",
            _artifacts(result),
            _reason(result),
        )
        rows.append(
            "<tr>" + "".join(f"<td>{html.escape(str(cell))}</td>" for cell in cells) + "</tr>"
        )
    stage_rows = "".join(
        "<tr>"
        f"<td>{html.escape(stage.name)}</td>"
        f"<td>{html.escape(stage.outcome.value)}</td>"
        f"<td>{stage.duration_seconds:.3f}</td>"
        f"<td>{html.escape(str(stage.command.log_path or ''))}</td>"
        f"<td>{html.escape(stage.reason)}</td>"
        "</tr>"
        for stage in summary.stages
    )
    status = "yes" if summary.successful else "no"
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Regression Report</title>
<style>
body {{ font-family: sans-serif; margin: 2rem; color: #172033; }}
table {{ border-collapse: collapse; width: 100%; }}
th, td {{ border: 1px solid #b7beca; padding: .45rem; text-align: left; }}
th {{ background: #eef2f7; }}
code {{ background: #eef2f7; padding: .1rem .25rem; }}
</style>
</head>
<body>
<h1>Regression Report</h1>
<ul>
<li>Simulator: <code>{simulator}</code></li>
<li>Provenance: <code>{provenance}</code></li>
<li>Started: <code>{started}</code></li>
<li>Finished: <code>{finished}</code></li>
<li>Executed tests successful: <code>{status}</code></li>
<li>Plan only: <code>{plan_only}</code></li>
</ul>
<table>
<thead><tr><th>Test</th><th>Attempt</th><th>Seed</th><th>Outcome</th>
<th>Runtime (s)</th><th>Assertions</th><th>UVM E/F</th><th>Artifacts</th>
<th>Reason</th></tr></thead>
<tbody>{rows}</tbody>
</table>
<h2>Build stages</h2>
<table>
<thead><tr><th>Stage</th><th>Outcome</th><th>Runtime (s)</th><th>Log</th>
<th>Reason</th></tr></thead>
<tbody>{stage_rows}</tbody>
</table>
</body>
</html>
""".format(
        simulator=html.escape(summary.simulator),
        provenance=html.escape(summary.provenance.value),
        started=html.escape(summary.started_at),
        finished=html.escape(summary.finished_at),
        status=status,
        plan_only="yes" if summary.plan_only else "no",
        rows="".join(rows),
        stage_rows=stage_rows,
    )


def write_html(summary: RunSummary, path: Path) -> Path:
    _validate_loaded_summary(summary)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text(summary), encoding="utf-8")
    return path


def write_reports(
    summary: RunSummary, output_dir: Path, formats: Iterable[str] = ("json", "md", "html")
) -> tuple[Path, ...]:
    writers = {
        "json": ("results.json", write_json),
        "md": ("report.md", write_markdown),
        "html": ("report.html", write_html),
    }
    paths: list[Path] = []
    for report_format in formats:
        if report_format not in writers:
            raise ValueError(f"unknown report format {report_format!r}")
        filename, writer = writers[report_format]
        paths.append(writer(summary, output_dir / filename))
    return tuple(paths)


def terminal_summary(summary: RunSummary) -> str:
    rows = [
        f"Regression: simulator={summary.simulator} provenance={summary.provenance.value}",
        f"Output: {summary.output_dir}",
    ]
    for result in summary.final_results:
        rows.append(
            f"  {result.test_name:<30} {result.outcome.value:<18} "
            f"seed={result.seed:<10} {result.duration_seconds:7.3f}s"
        )
    counts = ", ".join(f"{key}={value}" for key, value in summary.outcome_counts().items())
    rows.append(f"Final: {counts or 'no results'}")
    return "\n".join(rows)
