from __future__ import annotations

import unittest
from unittest.mock import patch

from regression.config import SeedSpec
from regression.seeds import MAX_SEED, derived_seed, resolve_seed


class SeedTests(unittest.TestCase):
    def test_derived_seed_is_reproducible_and_test_specific(self) -> None:
        self.assertEqual(derived_seed("alpha", 99), derived_seed("alpha", 99))
        self.assertNotEqual(derived_seed("alpha", 99), derived_seed("beta", 99))

    def test_fixed_seed_is_returned_exactly(self) -> None:
        self.assertEqual(resolve_seed(SeedSpec("fixed", 123), "test", 99), 123)

    def test_random_policy_uses_crypto_entropy_source(self) -> None:
        with patch("regression.seeds.secrets.randbelow", return_value=41) as random_value:
            self.assertEqual(resolve_seed(SeedSpec("random"), "test", 99), 42)
        random_value.assert_called_once_with(MAX_SEED)

    def test_invalid_base_seed_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "base seed"):
            derived_seed("test", 0)


if __name__ == "__main__":
    unittest.main()
