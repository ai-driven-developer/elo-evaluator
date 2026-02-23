import unittest

from performance_elo import expected_score, performance_rating, total_expected_score


class TestExpectedScore(unittest.TestCase):

    def test_equal_ratings(self):
        """Equal ratings → expected score is 0.5."""
        self.assertAlmostEqual(expected_score(1500, 1500), 0.5)

    def test_symmetry(self):
        """E(a, b) + E(b, a) = 1.0 for any a, b."""
        for a, b in [(1500, 1800), (2000, 1200), (1000, 3000)]:
            total = expected_score(a, b) + expected_score(b, a)
            self.assertAlmostEqual(total, 1.0, places=10)

    def test_stronger_opponent(self):
        """Stronger opponent → expected score < 0.5."""
        self.assertLess(expected_score(1500, 1800), 0.5)

    def test_weaker_opponent(self):
        """Weaker opponent → expected score > 0.5."""
        self.assertGreater(expected_score(1800, 1500), 0.5)

    def test_400_point_difference(self):
        """400 point advantage → expected score ≈ 0.9091."""
        self.assertAlmostEqual(expected_score(1900, 1500), 10 / 11, places=4)

    def test_same_rating_various_levels(self):
        """Equal ratings at any level → 0.5."""
        for r in [100, 1000, 2000, 3000]:
            self.assertAlmostEqual(expected_score(r, r), 0.5)


class TestTotalExpectedScore(unittest.TestCase):

    def test_single_opponent(self):
        """With one opponent, total expected == expected_score."""
        self.assertAlmostEqual(
            total_expected_score(1500, [1500]),
            expected_score(1500, 1500),
        )

    def test_multiple_equal_opponents(self):
        """N equal opponents → total expected = N * 0.5."""
        opponents = [1500] * 10
        self.assertAlmostEqual(total_expected_score(1500, opponents), 5.0)


class TestPerformanceRating(unittest.TestCase):

    def test_equal_score_gives_average_rating(self):
        """50% score against equal opponents → rating ≈ opponent average."""
        opponents = [1500, 1500, 1500, 1500]
        pr = performance_rating(opponents, 2.0)
        self.assertAlmostEqual(pr, 1500, delta=1)

    def test_50_percent_mixed_opponents(self):
        """50% score against mixed opponents → rating ≈ average opponent rating."""
        opponents = [1400, 1500, 1600, 1700]
        avg = sum(opponents) / len(opponents)  # 1550
        pr = performance_rating(opponents, 2.0)
        self.assertAlmostEqual(pr, avg, delta=1)

    def test_high_score(self):
        """High score → performance rating well above average opponent."""
        opponents = [1500, 1500, 1500, 1500]
        pr = performance_rating(opponents, 3.5)  # 87.5%
        self.assertGreater(pr, 1700)

    def test_low_score(self):
        """Low score → performance rating well below average opponent."""
        opponents = [1500, 1500, 1500, 1500]
        pr = performance_rating(opponents, 0.5)  # 12.5%
        self.assertLess(pr, 1300)

    def test_all_wins(self):
        """Perfect score → very high performance rating (boundary of search)."""
        opponents = [1500, 1500, 1500, 1500]
        pr = performance_rating(opponents, 4.0)
        self.assertGreater(pr, 2500)

    def test_all_losses(self):
        """Zero score → very low performance rating (boundary of search)."""
        opponents = [1500, 1500, 1500, 1500]
        pr = performance_rating(opponents, 0.0)
        self.assertLess(pr, 500)

    def test_known_fide_example(self):
        """Verify against a hand-calculated example.

        Player scores 7/10 against opponents rated:
        2400, 2500, 2550, 2600, 2450, 2500, 2600, 2650, 2500, 2550
        Average opponent = 2530, score = 70% → expected performance ≈ 2680.
        (FIDE dp table: 70% → +149, so ~2530+149 = 2679)
        We allow ±15 tolerance for the iterative method vs. FIDE dp table.
        """
        opponents = [2400, 2500, 2550, 2600, 2450, 2500, 2600, 2650, 2500, 2550]
        pr = performance_rating(opponents, 7.0)
        self.assertAlmostEqual(pr, 2679, delta=15)

    def test_empty_opponents_raises(self):
        """Empty opponent list → ValueError."""
        with self.assertRaises(ValueError):
            performance_rating([], 0)

    def test_negative_score_raises(self):
        """Negative score → ValueError."""
        with self.assertRaises(ValueError):
            performance_rating([1500], -1)

    def test_score_exceeds_games_raises(self):
        """Score > number of games → ValueError."""
        with self.assertRaises(ValueError):
            performance_rating([1500, 1500], 3)

    def test_single_game_win(self):
        """Win in a single game → performance well above opponent."""
        pr = performance_rating([1500], 1.0)
        self.assertGreater(pr, 2000)

    def test_single_game_draw(self):
        """Draw in a single game → performance ≈ opponent rating."""
        pr = performance_rating([1500], 0.5)
        self.assertAlmostEqual(pr, 1500, delta=1)

    def test_custom_tolerance(self):
        """Tighter tolerance produces more precise result."""
        opponents = [1500, 1600, 1700]
        avg = sum(opponents) / len(opponents)
        pr_coarse = performance_rating(opponents, 1.5, tolerance=0.1)
        pr_fine = performance_rating(opponents, 1.5, tolerance=0.0001)
        # Fine should be closer to the true value than coarse
        self.assertAlmostEqual(pr_fine, avg, delta=1)
        self.assertLessEqual(
            abs(pr_fine - avg),
            abs(pr_coarse - avg) + 1,  # fine at least as good as coarse
        )


class TestPerformanceRatingAdvanced(unittest.TestCase):
    """Complex and edge-case scenarios for performance_rating."""

    # --- Monotonicity & ordering ---

    def test_monotonicity_score_increase(self):
        """Higher score against same opponents → higher performance rating."""
        opponents = [1500, 1600, 1700, 1800]
        scores = [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]
        ratings = [performance_rating(opponents, s) for s in scores]
        for i in range(len(ratings) - 1):
            self.assertLess(ratings[i], ratings[i + 1])

    def test_monotonicity_opponent_strength(self):
        """Same percentage score against stronger field → higher performance."""
        weak_field = [1200, 1300, 1400, 1500]
        strong_field = [1800, 1900, 2000, 2100]
        pr_weak = performance_rating(weak_field, 2.0)
        pr_strong = performance_rating(strong_field, 2.0)
        self.assertLess(pr_weak, pr_strong)

    # --- Round-trip / inverse consistency ---

    def test_round_trip_consistency(self):
        """performance_rating result fed back into total_expected_score ≈ original score."""
        opponents = [1400, 1550, 1600, 1750, 1900]
        score = 3.0
        pr = performance_rating(opponents, score, tolerance=0.0001)
        reconstructed = total_expected_score(pr, opponents)
        self.assertAlmostEqual(reconstructed, score, places=3)

    def test_round_trip_various_scores(self):
        """Round-trip consistency across a range of scores."""
        opponents = [2000, 2100, 2200, 2300]
        for score in [0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5]:
            pr = performance_rating(opponents, score, tolerance=0.0001)
            reconstructed = total_expected_score(pr, opponents)
            self.assertAlmostEqual(reconstructed, score, places=3,
                                   msg=f"Round-trip failed for score={score}")

    # --- Wide rating spread ---

    def test_wide_rating_spread(self):
        """Opponents from 800 to 2800 — algorithm handles extreme spread."""
        opponents = [800, 1200, 1600, 2000, 2400, 2800]
        pr = performance_rating(opponents, 3.0, tolerance=0.0001)
        reconstructed = total_expected_score(pr, opponents)
        self.assertAlmostEqual(reconstructed, 3.0, places=3)

    def test_very_low_rated_opponents(self):
        """All opponents near the bottom of the scale."""
        opponents = [100, 150, 200, 250, 300]
        pr = performance_rating(opponents, 2.5)
        avg = sum(opponents) / len(opponents)
        self.assertAlmostEqual(pr, avg, delta=5)

    def test_very_high_rated_opponents(self):
        """All opponents near the top of the scale."""
        opponents = [2700, 2750, 2800, 2850]
        pr = performance_rating(opponents, 2.0)
        avg = sum(opponents) / len(opponents)
        self.assertAlmostEqual(pr, avg, delta=5)

    # --- Many games ---

    def test_large_number_of_games(self):
        """100 games — result should still be accurate."""
        opponents = [1500] * 100
        pr = performance_rating(opponents, 50.0, tolerance=0.0001)
        self.assertAlmostEqual(pr, 1500, delta=1)

    def test_large_number_mixed(self):
        """100 games against varied opponents, 60% score."""
        opponents = list(range(1400, 1500)) + list(range(1500, 1600))
        score = 60.0  # 60%
        pr = performance_rating(opponents, score, tolerance=0.0001)
        reconstructed = total_expected_score(pr, opponents)
        self.assertAlmostEqual(reconstructed, score, places=2)

    # --- Fractional / draw-heavy results ---

    def test_all_draws(self):
        """All draws (score = N/2) → performance ≈ average opponent."""
        opponents = [1400, 1500, 1600, 1700, 1800]
        avg = sum(opponents) / len(opponents)
        pr = performance_rating(opponents, 2.5)
        self.assertAlmostEqual(pr, avg, delta=5)

    def test_mostly_draws_slight_plus(self):
        """Mostly draws with a slight plus score."""
        opponents = [1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500, 1500]
        # 10 games, score 5.5 (9 draws + 1 win = 5.5)
        pr = performance_rating(opponents, 5.5)
        self.assertGreater(pr, 1500)
        self.assertLess(pr, 1600)  # slight plus, shouldn't jump too much

    def test_mostly_draws_slight_minus(self):
        """Mostly draws with a slight minus score."""
        opponents = [1500] * 10
        pr = performance_rating(opponents, 4.5)
        self.assertLess(pr, 1500)
        self.assertGreater(pr, 1400)

    # --- Near-boundary scores ---

    def test_near_zero_score(self):
        """Score just above 0 → very low but finite rating."""
        opponents = [1500, 1500, 1500, 1500]
        pr = performance_rating(opponents, 0.01)
        self.assertLess(pr, 500)

    def test_near_perfect_score(self):
        """Score just below N → very high but finite rating."""
        opponents = [1500, 1500, 1500, 1500]
        pr = performance_rating(opponents, 3.99)
        self.assertGreater(pr, 2500)

    # --- Asymmetric opponent pools ---

    def test_one_strong_rest_weak(self):
        """One GM-level opponent among club players."""
        opponents = [1200, 1200, 1200, 1200, 2700]
        pr_all_wins = performance_rating(opponents, 5.0)
        pr_4_wins = performance_rating(opponents, 4.0)
        # Beating the GM too should push rating much higher
        self.assertGreater(pr_all_wins, pr_4_wins + 100)

    def test_identical_opponents_different_count(self):
        """Same % score against N identical opponents — rating stays the same."""
        for n in [2, 5, 10, 50]:
            opponents = [1500] * n
            pr = performance_rating(opponents, n * 0.7, tolerance=0.0001)
            reconstructed = total_expected_score(pr, opponents)
            self.assertAlmostEqual(reconstructed, n * 0.7, places=2,
                                   msg=f"Failed for n={n}")

    # --- Symmetry of result ---

    def test_symmetric_score_symmetric_field(self):
        """Score=N/2 against symmetric field → rating = center of field."""
        opponents = [1400, 1600]  # average = 1500
        pr = performance_rating(opponents, 1.0)
        self.assertAlmostEqual(pr, 1500, delta=5)

    def test_score_zero_and_full_are_symmetric(self):
        """0/N and N/N deviate equally when search range is symmetric around avg."""
        # Use 2500 (center of default [0, 5000] range) so boundaries are equidistant
        opponents = [2500, 2500, 2500, 2500]
        avg = 2500
        pr_zero = performance_rating(opponents, 0.0)
        pr_full = performance_rating(opponents, 4.0)
        self.assertAlmostEqual(avg - pr_zero, pr_full - avg, delta=1)


if __name__ == "__main__":
    unittest.main()
