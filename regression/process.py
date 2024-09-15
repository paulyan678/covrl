"""Timeout-aware, shell-free subprocess execution."""

from __future__ import annotations

import os
import signal
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

from regression.models import Command, ProcessResult


class ProcessExecutor:
    """Execute one command while capturing a complete combined log."""

    termination_grace_seconds = 1.0

    def run(self, command: Command, timeout_seconds: float) -> ProcessResult:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        if not command.argv:
            raise ValueError("cannot execute an empty command")
        command.cwd.mkdir(parents=True, exist_ok=True)
        log_path = command.log_path or command.cwd / "process.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        environment = os.environ.copy()
        environment.update(command.env)
        started_at = datetime.now(timezone.utc).isoformat()
        start = time.monotonic()
        timed_out = False
        with log_path.open("w", encoding="utf-8") as log:
            log.write(f"$ {command.display()}\n")
            log.flush()
            process = subprocess.Popen(  # noqa: S603 - argv is never passed through a shell
                list(command.argv),
                cwd=command.cwd,
                env=environment,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                start_new_session=os.name != "nt",
            )
            try:
                returncode = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                self._terminate(process)
                returncode = process.returncode
                log.write(f"\n[REGRESSION] TIMEOUT after {timeout_seconds:.3f} seconds\n")
        return ProcessResult(
            returncode=returncode,
            duration_seconds=time.monotonic() - start,
            timed_out=timed_out,
            started_at=started_at,
            log_path=log_path,
        )

    def _terminate(self, process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        if os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                return
        else:
            process.terminate()
        try:
            process.wait(timeout=self.termination_grace_seconds)
            return
        except subprocess.TimeoutExpired:
            pass
        if os.name != "nt":
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                return
        else:
            process.kill()
        process.wait()


def read_log(path: Path, max_bytes: int = 8 * 1024 * 1024) -> str:
    """Read a bounded log tail for display; failure detection streams the full file."""

    try:
        with path.open("rb") as handle:
            if max_bytes <= 0:
                raise ValueError("max_bytes must be positive")
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            handle.seek(max(0, size - max_bytes), os.SEEK_SET)
            return handle.read().decode("utf-8", errors="replace")
    except OSError:
        return ""
