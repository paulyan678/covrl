"""Small deterministic process used by the mock simulator adapter."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from collections.abc import Sequence
from pathlib import Path


def _write_mock_artifacts(
    test_name: str, seed: int, coverage_path: Path | None, waveform_path: Path | None
) -> None:
    if coverage_path:
        coverage_path.parent.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha256(f"{test_name}:{seed}".encode()).digest()
        bins = sorted({int(value) % 32 for value in digest[:12]})
        coverage_path.write_text(
            json.dumps(
                {"format": "mock-coverage-v1", "test": test_name, "seed": seed, "bins": bins},
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
    if waveform_path:
        waveform_path.parent.mkdir(parents=True, exist_ok=True)
        waveform_path.write_text(
            f"MOCK WAVEFORM test={test_name} seed={seed}\n", encoding="utf-8"
        )


def _run(args: argparse.Namespace) -> int:
    if args.behavior == "timeout":
        delay = max(args.delay, 60.0)
    else:
        delay = args.delay
    if delay:
        time.sleep(delay)
    _write_mock_artifacts(args.test, args.seed, args.coverage, args.waveform)
    print(f"[MOCK] test={args.test} seed={args.seed} behavior={args.behavior}", flush=True)
    if args.behavior == "pass":
        print("UVM_ERROR : 0")
        print("UVM_FATAL : 0")
        return 0
    if args.behavior == "fail":
        print("[REGRESSION] FAILURE: injected expected DUT mismatch")
        return 1
    if args.behavior == "assertion":
        print("Assertion failure: injected ready/valid stability violation")
        return 0
    if args.behavior == "uvm_error":
        print("UVM_ERROR @ 100: reporter [MOCK] injected scoreboard mismatch")
        return 0
    if args.behavior == "infra":
        print("REGRESSION_INFRA_FAILURE: injected simulator infrastructure failure")
        return 2
    print(f"unknown mock behavior: {args.behavior}", file=sys.stderr)
    return 2


def _merge(args: argparse.Namespace) -> int:
    all_bins: set[int] = set()
    sources: list[str] = []
    for database in args.databases:
        path = Path(database)
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("format") != "mock-coverage-v1":
            raise ValueError(f"not a mock coverage database: {path}")
        all_bins.update(int(value) for value in data.get("bins", []))
        sources.append(str(path))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "format": "mock-coverage-merged-v1",
        "bins": sorted(all_bins),
        "covered_bins": len(all_bins),
        "total_bins": 32,
        "sources": sources,
    }
    args.output.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    args.report_dir.mkdir(parents=True, exist_ok=True)
    percentage = 100.0 * len(all_bins) / 32
    (args.report_dir / "coverage.md").write_text(
        "# Mock Coverage\n\n"
        f"Covered {len(all_bins)} of 32 deterministic bins ({percentage:.1f}%).\n",
        encoding="utf-8",
    )
    print(f"[MOCK] merged {len(sources)} database(s); bins={len(all_bins)}/32")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("compile")
    subparsers.add_parser("elaborate")
    run = subparsers.add_parser("run")
    run.add_argument("--test", required=True)
    run.add_argument("--seed", type=int, required=True)
    run.add_argument(
        "--behavior",
        choices=("pass", "fail", "assertion", "uvm_error", "infra", "timeout"),
        default="pass",
    )
    run.add_argument("--delay", type=float, default=0.0)
    run.add_argument("--coverage", type=Path)
    run.add_argument("--waveform", type=Path)
    merge = subparsers.add_parser("merge")
    merge.add_argument("--output", type=Path, required=True)
    merge.add_argument("--report-dir", type=Path, required=True)
    merge.add_argument("databases", nargs="+")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command in {"compile", "elaborate"}:
        print(f"[MOCK] {args.command} completed")
        return 0
    if args.command == "run":
        return _run(args)
    if args.command == "merge":
        return _merge(args)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
