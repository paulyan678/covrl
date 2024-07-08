from __future__ import annotations

import unittest

from rl.actions import (
    DEFAULT_ACTION_CATALOG,
    ActionCatalog,
    CodecAction,
    CodecCapabilities,
    TransactionType,
    build_default_catalog,
    configuration_is_supported,
)


class ActionCatalogTests(unittest.TestCase):
    def test_indexes_names_and_digest_are_stable(self) -> None:
        rebuilt = build_default_catalog()
        self.assertEqual(len(rebuilt), 135)
        self.assertEqual([item.index for item in rebuilt], list(range(len(rebuilt))))
        self.assertEqual(rebuilt.digest, DEFAULT_ACTION_CATALOG.digest)
        self.assertEqual(
            rebuilt.digest,
            "6984b0c682d1944d713a5920caf1ff9fa056bcf5b9e89f17b2e4ec47abcf40ea",
        )
        self.assertEqual(rebuilt.to_list(), DEFAULT_ACTION_CATALOG.to_list())

    def test_serialization_contains_plain_enum_values(self) -> None:
        payload = DEFAULT_ACTION_CATALOG[0].to_dict()
        self.assertEqual(payload["transaction_type"], "configure")
        self.assertIsNone(payload["control"])

    def test_relational_configuration_legality_is_explicit(self) -> None:
        baseline_ten_bit = next(
            action
            for action in DEFAULT_ACTION_CATALOG
            if action.transaction_type is TransactionType.CONFIGURE
            and action.profile == "baseline"
            and action.resolution == "hd"
            and action.bit_depth == 10
        )
        self.assertFalse(configuration_is_supported(baseline_ten_bit, CodecCapabilities()))

    def test_invalid_capability_and_catalog_inputs_are_actionable(self) -> None:
        with self.assertRaisesRegex(ValueError, "no advertised bit depth"):
            CodecCapabilities(profiles=("unknown",))
        with self.assertRaisesRegex(ValueError, "missing fields"):
            ActionCatalog(
                [
                    CodecAction(
                        index=0,
                        name="incomplete-frame",
                        transaction_type=TransactionType.FRAME,
                    )
                ]
            )


if __name__ == "__main__":
    unittest.main()
