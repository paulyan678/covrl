"""Command-line interface for test discovery, execution, reports, and coverage."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from collections.abc import Sequence
from pathlib import Path

from regression.adapters import adapter_names, create_adapter
from regression.config import Manifest, ManifestError, load_manifest
from regression.coverage import coverage_databases, merge_coverage
from regression.models import Outcome, Provenance
from regression.reporting import load_json, terminal_summary, write_reports
from regression.runner import RegressionRunner

DEFAULT_MANIFEST = Path("sim/manifests/regression.json")


def _manifest_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)


def _run_options(parser: argparse.ArgumentParser) -> None:
    _manifest_option(parser)
    parser.add_argument("--simulator", choices=adapter_names(), default="mock")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--jobs", type=int)
    parser.add_argument("--seed-base", type=int)
    parser.add_argument("--reruns", type=int)
    parser.add_argument("--dry-run", action="store_true")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="list discovered tests or one suite")
    _manifest_option(list_parser)
    list_parser.add_argument("--suite")

    run_parser = subparsers.add_parser("run", help="run one named test")
    run_parser.add_argument("test")
    _run_options(run_parser)

    suite_parser = subparsers.add_parser("suite", help="run a named suite")
    suite_parser.add_argument("suite")
    _run_options(suite_parser)

    full_parser = subparsers.add_parser("full", help="run every manifest test")
    _run_options(full_parser)

    rerun_parser = subparsers.add_parser("rerun", help="rerun failures from results JSON")
    rerun_parser.add_argument("--results", type=Path, required=True)
    _run_options(rerun_parser)

    merge_parser = subparsers.add_parser("merge", help="merge coverage databases")
    _manifest_option(merge_parser)
    merge_parser.add_argument("--simulator", choices=adapter_names(), required=True)
    merge_parser.add_argument("--results", type=Path)
    merge_parser.add_argument("--database", type=Path, action="append", default=[])
    merge_parser.add_argument("--output", type=Path)
    merge_parser.add_argument("--dry-run", action="store_true")

    report_parser = subparsers.add_parser("report", help="regenerate human-readable reports")
    report_parser.add_argument("--results", type=Path, required=True)
    report_parser.add_argument("--output", type=Path)
    report_parser.add_argument("--formats", default="md,html")

    clean_parser = subparsers.add_parser("clean", help="remove generated output safely")
    _manifest_option(clean_parser)
    clean_parser.add_argument("--output", type=Path)
    return parser


def _default_output(manifest: Manifest, simulator: str) -> Path:
    return manifest.project_root / "outputs" / "regression" / simulator


def _execute_run(
    args: argparse.Namespace,
    manifest: Manifest,
    names: tuple[str, ...],
    *,
    rerun: bool = False,
    seed_overrides: dict[str, int] | None = None,
) -> int:
    output = args.output
    if output is None:
        output = _default_output(manifest, args.simulator)
        if rerun:
            output = output.parent / f"{args.simulator}-rerun"
    runner = RegressionRunner(
        manifest,
        args.simulator,
        output,
        dry_run=args.dry_run,
        jobs=args.jobs,
        base_seed=args.seed_base,
        reruns=args.reruns,
        seed_overrides=seed_overrides,
        console=print,
    )
    summary = runner.run_names(names)
    paths = write_reports(summary, summary.output_dir)
    print(terminal_summary(summary))
    print("Reports: " + ", ".join(str(path) for path in paths))
    if any(result.outcome is Outcome.UNAVAILABLE for result in summary.final_results):
        return 2
    return 0 if summary.completed_without_failures else 1


def _list(args: argparse.Namespace, manifest: Manifest) -> int:
    if args.suite:
        tests = manifest.suite_tests(args.suite)
    else:
        tests = manifest.tests
    for test in tests:
        suite_text = ",".join(test.suites) or "-"
        print(
            f"{test.name:<30} flow={test.flow:<5} timeout={test.timeout_seconds:g}s "
            f"expected={test.expected_result:<4} suites={suite_text}"
        )
    return 0


def _merge(args: argparse.Namespace, manifest: Manifest) -> int:
    databases = list(path.expanduser().resolve() for path in args.database)
    if args.results:
        summary = load_json(args.results.expanduser().resolve())
        if summary.simulator != args.simulator:
            raise ValueError(f"results use simulator {summary.simulator!r}, not {args.simulator!r}")
        if summary.provenance is Provenance.DRY_RUN and not args.dry_run:
            raise ValueError("dry-run results may only be used with merge --dry-run")
        databases.extend(
            coverage_databases(
                summary,
                existing_only=not args.dry_run,
                include_plans=args.dry_run,
            )
        )
    databases = list(dict.fromkeys(databases))
    if not databases:
        raise ValueError("provide --results or at least one --database")
    if args.simulator not in manifest.simulators:
        raise ValueError(f"simulator {args.simulator!r} is not configured in the manifest")
    adapter = create_adapter(
        args.simulator, manifest.project_root, manifest.simulators[args.simulator]
    )
    output = args.output or (manifest.project_root / "outputs" / "coverage" / args.simulator)
    result = merge_coverage(
        adapter,
        tuple(databases),
        output,
        dry_run=args.dry_run,
        console=print,
    )
    result_path = output.expanduser().resolve() / "merge-results.json"
    result_path.write_text(
        json.dumps(result.to_dict(), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(f"Coverage merge: {result.outcome.value}; metadata={result_path}")
    if result.outcome is Outcome.UNAVAILABLE:
        return 2
    return 0 if result.outcome.is_success else 1


def safe_clean(target: Path, allowed_root: Path) -> bool:
    """Delete only the configured output root or one of its descendants."""

    target = target.expanduser().resolve()
    allowed_root = allowed_root.expanduser().resolve()
    if target != allowed_root and allowed_root not in target.parents:
        raise ValueError(
            f"refusing to clean outside generated-output root {allowed_root}: {target}"
        )
    if target == target.parent:
        raise ValueError("refusing to clean a filesystem root")
    if not target.exists():
        return False
    if target == allowed_root:
        removed = False
        for child in target.iterdir():
            if child.name == ".gitkeep":
                continue
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
            removed = True
        return removed
    shutil.rmtree(target)
    return True


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.command == "report":
            summary = load_json(args.results.expanduser().resolve())
            output = args.output or args.results.expanduser().resolve().parent
            formats = tuple(value.strip() for value in args.formats.split(",") if value.strip())
            if not formats:
                raise ValueError("at least one report format is required")
            paths = write_reports(summary, output, formats)
            print("Reports: " + ", ".join(str(path) for path in paths))
            return 0
        manifest = load_manifest(args.manifest)
        if args.command == "list":
            return _list(args, manifest)
        if args.command == "run":
            return _execute_run(args, manifest, (args.test,))
        if args.command == "suite":
            names = tuple(test.name for test in manifest.suite_tests(args.suite))
            return _execute_run(args, manifest, names)
        if args.command == "full":
            return _execute_run(args, manifest, tuple(test.name for test in manifest.tests))
        if args.command == "rerun":
            previous = load_json(args.results.expanduser().resolve())
            names = tuple(
                result.test_name
                for result in previous.final_results
                if result.outcome.is_rerunnable
            )
            if not names:
                print("No rerunnable failures were found.")
                return 0
            seed_overrides = {
                result.test_name: result.seed
                for result in previous.final_results
                if result.test_name in names
            }
            return _execute_run(args, manifest, names, rerun=True, seed_overrides=seed_overrides)
        if args.command == "merge":
            return _merge(args, manifest)
        if args.command == "clean":
            allowed_root = manifest.project_root / "outputs"
            target = args.output or allowed_root
            removed = safe_clean(target, allowed_root)
            print(f"{'Removed' if removed else 'Nothing to clean at'} {target}")
            return 0
        parser.error(f"unhandled command: {args.command}")
    except (ManifestError, ValueError, OSError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
