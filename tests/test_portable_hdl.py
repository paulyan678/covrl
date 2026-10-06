"""Execute real toy RTL; mutations prove the bench catches broken behavior.

These tests do not compile the UVM environment or its concurrent assertions.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(shutil.which("iverilog") and shutil.which("vvp"), "Icarus not installed")
class PortableHDLTests(unittest.TestCase):
    def run_hdl(self, mutation: tuple[str, str] | None = None) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            source = (ROOT / "rtl/toy_codec.sv").read_text()
            if mutation:
                self.assertIn(mutation[0], source)
                source = source.replace(*mutation)
            rtl = output / "toy_codec.sv"
            rtl.write_text(source)
            binary = output / "smoke.vvp"
            compiled = subprocess.run(
                [
                    "iverilog",
                    "-g2012",
                    "-s",
                    "toy_codec_native_smoke_tb",
                    "-o",
                    str(binary),
                    str(ROOT / "rtl/codec_protocol_pkg.sv"),
                    str(rtl),
                    str(ROOT / "tb/smoke/toy_codec_native_smoke_tb.sv"),
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stderr)
            return subprocess.run(["vvp", str(binary)], capture_output=True, text=True, timeout=30)

    def test_real_rtl_completes_checked_transactions(self) -> None:
        result = self.run_hdl()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("TOY_CODEC_SMOKE_PASS responses=28", result.stdout)

    def test_corrupted_response_is_detected(self) -> None:
        result = self.run_hdl(
            ("rsp_data        <= evaluated_data;", "rsp_data <= ~evaluated_data;")
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("mismatch", result.stdout)

    def test_dropped_backpressured_response_is_detected(self) -> None:
        result = self.run_hdl(("if (rsp_valid && rsp_ready)", "if (rsp_valid)"))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("mismatch", result.stdout)
