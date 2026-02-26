import random
import re
import unittest

from openings import OPENINGS, get_random_opening


class TestOpeningsData(unittest.TestCase):

    def test_openings_not_empty(self):
        self.assertGreater(len(OPENINGS), 0)

    def test_each_opening_is_nonempty_list(self):
        for opening in OPENINGS:
            self.assertIsInstance(opening, list)
            self.assertGreater(len(opening), 0)

    def test_all_moves_are_valid_uci(self):
        uci_pattern = re.compile(r"^[a-h][1-8][a-h][1-8][qrbn]?$")
        for opening in OPENINGS:
            for move in opening:
                self.assertRegex(
                    move, uci_pattern,
                    f"Invalid UCI move '{move}' in opening {opening}",
                )

    def test_no_duplicate_openings(self):
        tuples = [tuple(o) for o in OPENINGS]
        self.assertEqual(len(tuples), len(set(tuples)))


class TestGetRandomOpening(unittest.TestCase):

    def test_returns_list_from_openings(self):
        result = get_random_opening()
        self.assertIn(result, OPENINGS)

    def test_with_seed_is_reproducible(self):
        rng1 = random.Random(42)
        rng2 = random.Random(42)
        self.assertEqual(get_random_opening(rng1), get_random_opening(rng2))

    def test_different_seeds_can_differ(self):
        results = set()
        for seed in range(100):
            rng = random.Random(seed)
            results.add(tuple(get_random_opening(rng)))
        self.assertGreater(len(results), 1)


if __name__ == "__main__":
    unittest.main()
