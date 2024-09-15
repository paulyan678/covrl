from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class SystemVerilogStructureTests(unittest.TestCase):
    def test_source_manifests_reference_existing_files(self) -> None:
        for relative in ("sim/manifests/uvm.f", "sim/manifests/rtl_smoke.f"):
            manifest = ROOT / relative
            entries = [
                line.strip()
                for line in manifest.read_text(encoding="utf-8").splitlines()
                if line.strip() and not line.lstrip().startswith("+")
            ]
            self.assertTrue(entries, relative)
            for entry in entries:
                self.assertTrue((ROOT / entry).is_file(), f"missing {entry} from {relative}")

    def test_uvm_package_includes_existing_components(self) -> None:
        package = (ROOT / "tb/codec_uvm_pkg.sv").read_text(encoding="utf-8")
        includes = re.findall(r'`include\s+"([^"]+)"', package)
        self.assertGreater(len(includes), 20)
        for include in includes:
            if include == "uvm_macros.svh":
                continue
            self.assertTrue((ROOT / "tb" / include).is_file(), f"missing include {include}")

    def test_five_representative_tests_are_registered(self) -> None:
        package = (ROOT / "tb/codec_uvm_pkg.sv").read_text(encoding="utf-8")
        expected = {
            "codec_normal_test.sv",
            "codec_random_test.sv",
            "codec_backpressure_test.sv",
            "codec_reset_recovery_test.sv",
            "codec_invalid_test.sv",
        }
        self.assertTrue(all(name in package for name in expected))

    def test_reserved_keywords_are_not_declared_as_identifiers(self) -> None:
        declarations = re.compile(
            r"\b(?:bit|int|integer|logic|longint|uvm_sequence_base)"
            r"(?:\s+unsigned)?\s+(?:matches|sequence)\b"
        )
        offenders: list[str] = []
        for path in (ROOT / "tb").rglob("*.sv"):
            if declarations.search(path.read_text(encoding="utf-8")):
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual(offenders, [])

    def test_reference_model_uses_dut_specific_factory_override(self) -> None:
        environment = (ROOT / "tb/env/codec_env.sv").read_text(encoding="utf-8")
        reusable_package = (ROOT / "tb/codec_uvm_pkg.sv").read_text(encoding="utf-8")
        toy_package = (ROOT / "tb/adapters/toy_codec_uvm_pkg.sv").read_text(encoding="utf-8")
        top = (ROOT / "tb/top/tb_top.sv").read_text(encoding="utf-8")
        self.assertIn("codec_reference_model::type_id::create", environment)
        self.assertNotIn("toy_codec_reference_model.sv", reusable_package)
        self.assertIn("toy_codec_reference_model.sv", toy_package)
        self.assertIn("toy_codec_reference_model::get_type", top)

    def test_protocol_assertion_categories_are_present(self) -> None:
        source = (ROOT / "tb/assertions/codec_protocol_sva.sv").read_text(encoding="utf-8")
        source += (ROOT / "tb/adapters/toy_codec_state_sva.sv").read_text(encoding="utf-8")
        properties = {
            "p_request_held_until_ready",
            "p_request_stable_when_stalled",
            "p_response_stable_when_backpressured",
            "p_request_timeout",
            "p_response_timeout",
            "p_response_order",
            "p_legal_config",
            "p_config_before_traffic",
            "p_reset_clears_outputs",
            "p_response_status_legal",
            "p_configured_rise_has_legal_config",
            "p_configured_fall_has_stop",
        }
        self.assertTrue(all(f"property {name}" in source for name in properties))

    def test_seed_override_controls_every_randomized_child_item(self) -> None:
        base = (ROOT / "tb/sequences/codec_base_sequence.sv").read_text(encoding="utf-8")
        test = (ROOT / "tb/tests/codec_base_test.sv").read_text(encoding="utf-8")
        self.assertIn("function void set_deterministic_seed", base)
        self.assertIn("function void seed_random_item", base)
        self.assertIn("function int unsigned choose_index", base)
        self.assertIn("main_sequence.set_deterministic_seed", test)
        for name in (
            "codec_random_sequence.sv",
            "codec_backpressure_sequence.sv",
            "codec_reset_sequence.sv",
        ):
            source = (ROOT / "tb/sequences" / name).read_text(encoding="utf-8")
            self.assertEqual(source.count(".randomize()"), source.count("seed_random_item("), name)

    def test_scoreboard_uses_monitor_cycle_and_protects_response_boundary(self) -> None:
        item = (ROOT / "tb/agents/codec_seq_item.sv").read_text(encoding="utf-8")
        monitor = (ROOT / "tb/agents/codec_monitor.sv").read_text(encoding="utf-8")
        scoreboard = (ROOT / "tb/scoreboard/codec_scoreboard.sv").read_text(encoding="utf-8")
        self.assertIn("observed_cycle", item)
        self.assertIn("item.observed_cycle", monitor)
        self.assertIn("expected_cycle_q.push_back(item.observed_cycle)", scoreboard)
        self.assertIn("rsp_valid && cfg.vif.mon_cb.rsp_ready", scoreboard)


if __name__ == "__main__":
    unittest.main()
