#!/usr/bin/env python3
"""Audit repository history and hygiene."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

SECRET_PATTERNS = (
    (
        "private key",
        re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE\s+KEY-----"),
    ),
    ("AWS access key", re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")),
    ("GitHub token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{30,}\b")),
    ("Slack token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{20,}\b")),
    ("Stripe live key", re.compile(r"\bsk_live_[A-Za-z0-9]{16,}\b")),
)
GENERATED_DIRECTORY_NAMES = {
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "checkpoints",
    "csrc",
    "htmlcov",
    "tensorboard",
}
GENERATED_SUFFIXES = {
    ".ckpt",
    ".fsdb",
    ".jou",
    ".log",
    ".pt",
    ".pth",
    ".pyc",
    ".ucdb",
    ".vcd",
    ".wlf",
    ".zip",
}
SENSITIVE_SUFFIXES = {".key", ".pem", ".token"}
IGNORE_PROBES = (
    ".env.local",
    "license.dat",
    "outputs/example/results.json",
    "simv",
    "coverage.vdb/data",
    "waves.vcd",
    ".venv/bin/python",
    "package/__pycache__/module.pyc",
    ".DS_Store",
)


@dataclass(frozen=True, slots=True)
class AuditConfig:
    require_clean: bool = True
    check_ignore_rules: bool = True


@dataclass(frozen=True, slots=True)
class AuditCheck:
    name: str
    passed: bool
    detail: str


class GitCommandError(RuntimeError):
    """Raised when a required Git query fails."""


def git_output(root: Path, *args: str) -> str:
    process = subprocess.run(
        ("git", *args),
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if process.returncode != 0:
        detail = process.stderr.strip() or process.stdout.strip()
        raise GitCommandError(f"git {' '.join(args)} failed: {detail}")
    return process.stdout


def tracked_paths(root: Path) -> tuple[Path, ...]:
    raw = git_output(root, "ls-files", "-z")
    return tuple(Path(value) for value in raw.split("\0") if value)


def secret_hits(text: str, location: str) -> tuple[str, ...]:
    hits: list[str] = []
    for label, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            hits.append(f"{location}: {label}")
    return tuple(hits)


def is_generated_path(path: Path) -> bool:
    parts = set(path.parts)
    if path.parts and path.parts[0] == "outputs":
        return path.as_posix() != "outputs/.gitkeep"
    if parts.intersection(GENERATED_DIRECTORY_NAMES):
        return True
    if path.suffix.lower() in GENERATED_SUFFIXES:
        return True
    return path.name.startswith("simv") or path.name in {"transcript", "vsim.wlf"}


def is_sensitive_path(path: Path) -> bool:
    lowered_parts = {part.lower() for part in path.parts}
    if lowered_parts.intersection({"licenses", "secrets"}):
        return True
    if path.suffix.lower() in SENSITIVE_SUFFIXES:
        return True
    if path.name == "license.dat":
        return True
    return path.name == ".env" or (path.name.startswith(".env.") and path.name != ".env.example")


def _check(name: str, passed: bool, success: str, failure: str) -> AuditCheck:
    return AuditCheck(name=name, passed=passed, detail=success if passed else failure)


def _hygiene_checks(root: Path, config: AuditConfig) -> list[AuditCheck]:
    paths = tracked_paths(root)
    generated = sorted(path.as_posix() for path in paths if is_generated_path(path))
    sensitive = sorted(path.as_posix() for path in paths if is_sensitive_path(path))
    checks = [
        _check(
            "tracked generated files",
            not generated,
            "no generated artifacts are tracked",
            "tracked generated paths: " + ", ".join(generated),
        ),
        _check(
            "tracked sensitive paths",
            not sensitive,
            "no credential or license paths are tracked",
            "tracked sensitive paths: " + ", ".join(sensitive),
        ),
    ]

    secret_findings: list[str] = []
    for relative in paths:
        path = root / relative
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue
        secret_findings.extend(secret_hits(text, relative.as_posix()))
    history_patch = git_output(root, "log", "--all", "-p", "--pretty=format:")
    secret_findings.extend(secret_hits(history_patch, "Git patch history"))
    checks.append(
        _check(
            "high-confidence secret scan",
            not secret_findings,
            "no high-confidence key or token patterns found in tracked files or patches",
            "findings: " + ", ".join(sorted(set(secret_findings))),
        )
    )

    if config.check_ignore_rules:
        missing_ignores: list[str] = []
        for probe in IGNORE_PROBES:
            process = subprocess.run(
                ("git", "check-ignore", "--no-index", "--quiet", probe),
                cwd=root,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            if process.returncode != 0:
                missing_ignores.append(probe)
        checks.append(
            _check(
                "ignore rules",
                not missing_ignores,
                "credentials, licenses, build products, coverage, waves, caches, "
                "and outputs are ignored",
                "representative paths not ignored: " + ", ".join(missing_ignores),
            )
        )

    if config.require_clean:
        status = git_output(root, "status", "--porcelain=v1", "--untracked-files=all").strip()
        checks.append(
            _check(
                "working tree",
                not status,
                "working tree is clean",
                "working tree changes:\n" + status,
            )
        )
    return checks


def audit_repository(root: Path, config: AuditConfig | None = None) -> tuple[AuditCheck, ...]:
    root = root.expanduser().resolve()
    selected = config or AuditConfig()
    git_output(root, "rev-parse", "--is-inside-work-tree")
    checks = _hygiene_checks(root, selected)
    return tuple(checks)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--allow-dirty", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = AuditConfig(require_clean=not args.allow_dirty)
    try:
        checks = audit_repository(args.root, config)
    except (GitCommandError, OSError, ValueError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    for check in checks:
        print(f"[{'PASS' if check.passed else 'FAIL'}] {check.name}: {check.detail}")
    passed = sum(check.passed for check in checks)
    print(f"Audit summary: {passed}/{len(checks)} checks passed")
    return 0 if passed == len(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
