import unittest
from unittest.mock import patch

from evaluate import (
    generate_elo_levels,
    evaluate_engine,
    evaluate_engine_linear,
    evaluate_engine_adaptive,
    evaluate_engine_bsearch,
    _resolve_warmup,
    _warmup_excluded,
    _resolve_elo_range,
    get_stockfish_elo_range,
    DEFAULT_MIN_ELO,
    DEFAULT_MAX_ELO,
)
from match_runner import MatchResult, GameResult


def make_match_result(num_games: int, total_score: float) -> MatchResult:
    """Create a MatchResult with minimal fields for testing."""
    games = []
    remaining = total_score
    for i in range(num_games):
        if remaining >= 1.0:
            score = 1.0
        elif remaining >= 0.5:
            score = 0.5
        else:
            score = 0.0
        remaining -= score
        games.append(GameResult(
            game_number=i + 1,
            white="engine" if i % 2 == 0 else "stockfish",
            result="1-0" if score == 1.0 else ("1/2-1/2" if score == 0.5 else "0-1"),
            engine_score=score,
            moves=["e2e4"],
            termination="checkmate",
        ))
    return MatchResult(total_score=total_score, num_games=num_games, games=games)


# --- generate_elo_levels ---


class TestGenerateEloLevels(unittest.TestCase):

    def test_five_matches(self):
        levels = generate_elo_levels(800, 2800, 5)
        self.assertEqual(levels, [800, 1300, 1800, 2300, 2800])

    def test_single_match(self):
        levels = generate_elo_levels(800, 2800, 1)
        self.assertEqual(levels, [1800])

    def test_two_matches(self):
        levels = generate_elo_levels(1000, 2000, 2)
        self.assertEqual(levels, [1000, 2000])

    def test_three_matches(self):
        levels = generate_elo_levels(1000, 2000, 3)
        self.assertEqual(levels, [1000, 1500, 2000])

    def test_same_min_max(self):
        levels = generate_elo_levels(1500, 1500, 3)
        self.assertEqual(levels, [1500, 1500, 1500])

    def test_many_matches(self):
        levels = generate_elo_levels(1000, 2000, 10)
        self.assertEqual(len(levels), 10)
        self.assertEqual(levels[0], 1000)
        self.assertEqual(levels[-1], 2000)
        for i in range(len(levels) - 1):
            self.assertLessEqual(levels[i], levels[i + 1])

    def test_zero_matches_raises(self):
        with self.assertRaises(ValueError):
            generate_elo_levels(800, 2800, 0)

    def test_min_greater_than_max_raises(self):
        with self.assertRaises(ValueError):
            generate_elo_levels(2800, 800, 5)


# --- evaluate_engine dispatcher ---


class TestEvaluateEngineDispatcher(unittest.TestCase):

    @patch("evaluate.run_match")
    def test_default_strategy_is_adaptive(self, mock_run):
        """Default strategy is adaptive — starts at midpoint."""
        mock_run.return_value = make_match_result(2, 1.0)

        evaluate_engine(
            engine_path="/test/engine",
            num_matches=1,
            games_per_match=2,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
        )

        # Adaptive starts at midpoint (1500)
        elo_called = mock_run.call_args.kwargs["stockfish_elo"]
        self.assertEqual(elo_called, 1500)

    @patch("evaluate.run_match")
    def test_linear_strategy_via_dispatcher(self, mock_run):
        """strategy='linear' uses linear spread."""
        mock_run.return_value = make_match_result(2, 1.0)

        evaluate_engine(
            strategy="linear",
            engine_path="/test/engine",
            num_matches=2,
            games_per_match=2,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
        )

        elos = [c.kwargs["stockfish_elo"] for c in mock_run.call_args_list]
        self.assertEqual(elos, [1000, 2000])

    def test_invalid_strategy_raises(self):
        with self.assertRaises(ValueError):
            evaluate_engine(
                strategy="random",
                engine_path="/test/engine",
                num_matches=1,
                games_per_match=2,
                movetime_ms=100,
            )


# --- evaluate_engine_linear ---


class TestEvaluateEngineLinear(unittest.TestCase):

    @patch("evaluate.run_match")
    def test_calls_run_match_with_correct_elos(self, mock_run):
        mock_run.return_value = make_match_result(4, 2.0)

        evaluate_engine_linear(
            engine_path="/test/engine",
            num_matches=3,
            games_per_match=4,
            movetime_ms=200,
            min_elo=1000,
            max_elo=2000,
        )

        self.assertEqual(mock_run.call_count, 3)
        elos = [c.kwargs["stockfish_elo"] for c in mock_run.call_args_list]
        self.assertEqual(elos, [1000, 1500, 2000])

    @patch("evaluate.run_match")
    def test_total_score_and_games(self, mock_run):
        mock_run.side_effect = [
            make_match_result(10, 9.0),
            make_match_result(10, 5.0),
            make_match_result(10, 1.0),
        ]

        result = evaluate_engine_linear(
            engine_path="/test/engine",
            num_matches=3,
            games_per_match=10,
            movetime_ms=100,
            min_elo=800,
            max_elo=2800,
        )

        self.assertEqual(result.total_score, 15.0)
        self.assertEqual(result.total_games, 30)

    @patch("evaluate.run_match")
    def test_performance_50_percent(self, mock_run):
        mock_run.side_effect = [
            make_match_result(10, 5.0),
            make_match_result(10, 5.0),
            make_match_result(10, 5.0),
        ]

        result = evaluate_engine_linear(
            engine_path="/test/engine",
            num_matches=3,
            games_per_match=10,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
        )

        self.assertAlmostEqual(result.estimated_elo, 1500, delta=5)

    @patch("evaluate.run_match")
    def test_all_wins(self, mock_run):
        mock_run.side_effect = [
            make_match_result(10, 10.0),
            make_match_result(10, 10.0),
        ]

        result = evaluate_engine_linear(
            engine_path="/test/engine",
            num_matches=2,
            games_per_match=10,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
        )

        self.assertGreater(result.estimated_elo, 3000)

    @patch("evaluate.run_match")
    def test_all_losses(self, mock_run):
        mock_run.side_effect = [
            make_match_result(10, 0.0),
            make_match_result(10, 0.0),
        ]

        result = evaluate_engine_linear(
            engine_path="/test/engine",
            num_matches=2,
            games_per_match=10,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
        )

        self.assertLess(result.estimated_elo, 500)

    @patch("evaluate.run_match")
    def test_match_results_stored(self, mock_run):
        mock_run.side_effect = [
            make_match_result(4, 3.0),
            make_match_result(4, 1.0),
        ]

        result = evaluate_engine_linear(
            engine_path="/test/engine",
            num_matches=2,
            games_per_match=4,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
        )

        self.assertEqual(len(result.match_results), 2)
        self.assertEqual(result.match_results[0][0], 1000)
        self.assertEqual(result.match_results[1][0], 2000)

    @patch("evaluate.run_match")
    def test_stockfish_path_forwarded(self, mock_run):
        mock_run.return_value = make_match_result(2, 1.0)

        evaluate_engine_linear(
            engine_path="/test/engine",
            num_matches=1,
            games_per_match=2,
            movetime_ms=100,
            stockfish_path="/custom/stockfish",
        )

        self.assertEqual(mock_run.call_args.kwargs["stockfish_path"], "/custom/stockfish")


# --- evaluate_engine_adaptive ---


class TestEvaluateEngineAdaptive(unittest.TestCase):

    @patch("evaluate.run_match")
    def test_first_match_at_midpoint(self, mock_run):
        """First match is played at the midpoint of the range."""
        mock_run.return_value = make_match_result(4, 2.0)

        evaluate_engine_adaptive(
            engine_path="/test/engine",
            num_matches=1,
            games_per_match=4,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
        )

        self.assertEqual(mock_run.call_args.kwargs["stockfish_elo"], 1500)

    @patch("evaluate.run_match")
    def test_second_elo_rises_after_winning(self, mock_run):
        """After winning most games, next opponent ELO should be higher."""
        mock_run.side_effect = [
            make_match_result(10, 9.0),   # dominant win at 1500 → perf >> 1500
            make_match_result(10, 5.0),   # 2nd match at higher ELO
        ]

        evaluate_engine_adaptive(
            engine_path="/test/engine",
            num_matches=2,
            games_per_match=10,
            movetime_ms=100,
            min_elo=800,
            max_elo=2800,
        )

        elos = [c.kwargs["stockfish_elo"] for c in mock_run.call_args_list]
        self.assertEqual(elos[0], 1800)  # midpoint
        self.assertGreater(elos[1], 1800)  # raised after strong result

    @patch("evaluate.run_match")
    def test_second_elo_drops_after_losing(self, mock_run):
        """After losing most games, next opponent ELO should be lower."""
        mock_run.side_effect = [
            make_match_result(10, 1.0),   # bad result at 1500 → perf << 1500
            make_match_result(10, 5.0),
        ]

        evaluate_engine_adaptive(
            engine_path="/test/engine",
            num_matches=2,
            games_per_match=10,
            movetime_ms=100,
            min_elo=800,
            max_elo=2800,
        )

        elos = [c.kwargs["stockfish_elo"] for c in mock_run.call_args_list]
        self.assertEqual(elos[0], 1800)
        self.assertLess(elos[1], 1800)

    @patch("evaluate.run_match")
    def test_clamps_to_max_elo_on_all_wins(self, mock_run):
        """100% score → next ELO clamped to max_elo, not above."""
        mock_run.side_effect = [
            make_match_result(10, 10.0),  # perfect score → perf very high
            make_match_result(10, 10.0),
        ]

        evaluate_engine_adaptive(
            engine_path="/test/engine",
            num_matches=2,
            games_per_match=10,
            movetime_ms=100,
            min_elo=800,
            max_elo=2800,
        )

        elos = [c.kwargs["stockfish_elo"] for c in mock_run.call_args_list]
        self.assertEqual(elos[1], 2800)  # clamped to max

    @patch("evaluate.run_match")
    def test_clamps_to_min_elo_on_all_losses(self, mock_run):
        """0% score → next ELO clamped to min_elo, not below."""
        mock_run.side_effect = [
            make_match_result(10, 0.0),  # zero score → perf very low
            make_match_result(10, 0.0),
        ]

        evaluate_engine_adaptive(
            engine_path="/test/engine",
            num_matches=2,
            games_per_match=10,
            movetime_ms=100,
            min_elo=800,
            max_elo=2800,
        )

        elos = [c.kwargs["stockfish_elo"] for c in mock_run.call_args_list]
        self.assertEqual(elos[1], 800)  # clamped to min

    @patch("evaluate.run_match")
    def test_total_score_and_games(self, mock_run):
        """Total score and game count are correct across adaptive matches."""
        mock_run.side_effect = [
            make_match_result(4, 3.0),
            make_match_result(4, 2.0),
            make_match_result(4, 1.0),
        ]

        result = evaluate_engine_adaptive(
            engine_path="/test/engine",
            num_matches=3,
            games_per_match=4,
            movetime_ms=100,
        )

        self.assertEqual(result.total_score, 6.0)
        self.assertEqual(result.total_games, 12)
        self.assertEqual(len(result.match_results), 3)

    @patch("evaluate.run_match")
    def test_converges_on_50_percent(self, mock_run):
        """If engine always scores 50%, ELO stays near the starting midpoint."""
        mock_run.return_value = make_match_result(10, 5.0)

        evaluate_engine_adaptive(
            engine_path="/test/engine",
            num_matches=5,
            games_per_match=10,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
        )

        # All 5 matches should be at 1500 (50% → perf = opponent → no change)
        elos = [c.kwargs["stockfish_elo"] for c in mock_run.call_args_list]
        for elo in elos:
            self.assertAlmostEqual(elo, 1500, delta=5)

    @patch("evaluate.run_match")
    def test_single_match_no_crash(self, mock_run):
        """Single adaptive match works — no next-ELO calculation needed."""
        mock_run.return_value = make_match_result(4, 4.0)

        result = evaluate_engine_adaptive(
            engine_path="/test/engine",
            num_matches=1,
            games_per_match=4,
            movetime_ms=100,
        )

        self.assertEqual(mock_run.call_count, 1)
        self.assertEqual(result.total_score, 4.0)

    @patch("evaluate.run_match")
    def test_match_results_have_varying_elos(self, mock_run):
        """Adaptive matches are played at different ELOs unlike linear's fixed set."""
        mock_run.side_effect = [
            make_match_result(10, 8.0),   # strong at midpoint → go higher
            make_match_result(10, 3.0),   # weak at higher level → come back down
            make_match_result(10, 5.0),   # 50% at new level
        ]

        result = evaluate_engine_adaptive(
            engine_path="/test/engine",
            num_matches=3,
            games_per_match=10,
            movetime_ms=100,
            min_elo=800,
            max_elo=2800,
        )

        elos = [elo for elo, _ in result.match_results]
        # First is midpoint, second should be higher, third should adjust
        self.assertEqual(elos[0], 1800)
        self.assertGreater(elos[1], elos[0])
        # Third should be between first and second (came back down)
        self.assertLess(elos[2], elos[1])


# --- evaluate_engine_bsearch ---


class TestEvaluateEngineBsearch(unittest.TestCase):

    @patch("evaluate.run_match")
    def test_first_match_at_midpoint(self, mock_run):
        """First match is played at (min+max)//2."""
        mock_run.return_value = make_match_result(4, 2.0)

        evaluate_engine_bsearch(
            engine_path="/test/engine",
            num_matches=1,
            games_per_match=4,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
        )

        self.assertEqual(mock_run.call_args.kwargs["stockfish_elo"], 1500)

    @patch("evaluate.run_match")
    def test_moves_up_after_win(self, mock_run):
        """>50% score → next ELO is higher."""
        mock_run.side_effect = [
            make_match_result(10, 8.0),   # 80% at 1500 → lo=1500
            make_match_result(10, 5.0),   # next at (1500+2000)//2 = 1750
        ]

        evaluate_engine_bsearch(
            engine_path="/test/engine",
            num_matches=2,
            games_per_match=10,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
        )

        elos = [c.kwargs["stockfish_elo"] for c in mock_run.call_args_list]
        self.assertEqual(elos[0], 1500)
        self.assertEqual(elos[1], 1750)

    @patch("evaluate.run_match")
    def test_moves_down_after_loss(self, mock_run):
        """<50% score → next ELO is lower."""
        mock_run.side_effect = [
            make_match_result(10, 2.0),   # 20% at 1500 → hi=1500
            make_match_result(10, 5.0),   # next at (1000+1500)//2 = 1250
        ]

        evaluate_engine_bsearch(
            engine_path="/test/engine",
            num_matches=2,
            games_per_match=10,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
        )

        elos = [c.kwargs["stockfish_elo"] for c in mock_run.call_args_list]
        self.assertEqual(elos[0], 1500)
        self.assertEqual(elos[1], 1250)

    @patch("evaluate.run_match")
    def test_stays_on_50_percent(self, mock_run):
        """Exactly 50% → bounds unchanged, next ELO same."""
        mock_run.return_value = make_match_result(10, 5.0)

        evaluate_engine_bsearch(
            engine_path="/test/engine",
            num_matches=3,
            games_per_match=10,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
        )

        elos = [c.kwargs["stockfish_elo"] for c in mock_run.call_args_list]
        self.assertEqual(elos, [1500, 1500, 1500])

    @patch("evaluate.run_match")
    def test_converges_to_narrow_range(self, mock_run):
        """Multiple wins narrow the range upward."""
        mock_run.side_effect = [
            make_match_result(10, 8.0),  # 80% at 1500 → lo=1500
            make_match_result(10, 8.0),  # 80% at 1750 → lo=1750
            make_match_result(10, 8.0),  # 80% at 1875 → lo=1875
            make_match_result(10, 5.0),  # at 1938
        ]

        evaluate_engine_bsearch(
            engine_path="/test/engine",
            num_matches=4,
            games_per_match=10,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
        )

        elos = [c.kwargs["stockfish_elo"] for c in mock_run.call_args_list]
        self.assertEqual(elos[0], 1500)
        self.assertEqual(elos[1], 1750)
        self.assertEqual(elos[2], 1875)
        self.assertEqual(elos[3], 1938)  # (1875+2000)//2

    @patch("evaluate.run_match")
    def test_elo_stays_in_range(self, mock_run):
        """ELO never goes below min or above max."""
        mock_run.side_effect = [
            make_match_result(10, 10.0),  # 100% → lo=mid
            make_match_result(10, 10.0),
            make_match_result(10, 10.0),
            make_match_result(10, 10.0),
            make_match_result(10, 10.0),
        ]

        evaluate_engine_bsearch(
            engine_path="/test/engine",
            num_matches=5,
            games_per_match=10,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
        )

        elos = [c.kwargs["stockfish_elo"] for c in mock_run.call_args_list]
        for elo in elos:
            self.assertGreaterEqual(elo, 1000)
            self.assertLessEqual(elo, 2000)

    @patch("evaluate.run_match")
    def test_total_score_and_games(self, mock_run):
        mock_run.side_effect = [
            make_match_result(4, 3.0),
            make_match_result(4, 1.0),
            make_match_result(4, 2.0),
        ]

        result = evaluate_engine_bsearch(
            engine_path="/test/engine",
            num_matches=3,
            games_per_match=4,
            movetime_ms=100,
        )

        self.assertEqual(result.total_score, 6.0)
        self.assertEqual(result.total_games, 12)
        self.assertEqual(len(result.match_results), 3)

    @patch("evaluate.run_match")
    def test_warmup_works(self, mock_run):
        mock_run.return_value = make_match_result(4, 2.0)

        result = evaluate_engine_bsearch(
            engine_path="/test/engine",
            num_matches=3,
            games_per_match=4,
            movetime_ms=100,
            warmup=1,
        )

        self.assertEqual(result.warmup_matches, 1)

    @patch("evaluate.run_match")
    def test_single_match_no_crash(self, mock_run):
        mock_run.return_value = make_match_result(4, 3.0)

        result = evaluate_engine_bsearch(
            engine_path="/test/engine",
            num_matches=1,
            games_per_match=4,
            movetime_ms=100,
        )

        self.assertEqual(mock_run.call_count, 1)
        self.assertEqual(result.total_score, 3.0)

    @patch("evaluate.run_match")
    def test_via_dispatcher(self, mock_run):
        mock_run.return_value = make_match_result(4, 2.0)

        evaluate_engine(
            strategy="bsearch",
            engine_path="/test/engine",
            num_matches=2,
            games_per_match=4,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
        )

        # Should use bsearch: first match at midpoint 1500
        elos = [c.kwargs["stockfish_elo"] for c in mock_run.call_args_list]
        self.assertEqual(elos[0], 1500)


# --- _resolve_warmup ---


class TestResolveWarmup(unittest.TestCase):

    def test_none_defaults_to_two(self):
        self.assertEqual(_resolve_warmup(None, 5), 2)

    def test_none_many_matches_gives_two(self):
        self.assertEqual(_resolve_warmup(None, 20), 2)

    def test_none_two_matches_gives_one(self):
        """With only 2 matches, warmup capped at 1 (num_matches - 1)."""
        self.assertEqual(_resolve_warmup(None, 2), 1)

    def test_none_one_match_gives_zero(self):
        """With only 1 match, warmup is 0."""
        self.assertEqual(_resolve_warmup(None, 1), 0)

    def test_explicit_zero(self):
        self.assertEqual(_resolve_warmup(0, 5), 0)

    def test_explicit_value(self):
        self.assertEqual(_resolve_warmup(3, 10), 3)

    def test_negative_raises(self):
        with self.assertRaises(ValueError):
            _resolve_warmup(-1, 5)

    def test_equal_to_num_matches_raises(self):
        with self.assertRaises(ValueError):
            _resolve_warmup(5, 5)

    def test_greater_than_num_matches_raises(self):
        with self.assertRaises(ValueError):
            _resolve_warmup(6, 5)


# --- _warmup_excluded ---


class TestWarmupExcluded(unittest.TestCase):

    def test_zero_warmup(self):
        self.assertEqual(_warmup_excluded(0, 10), 0)

    def test_warmup_2_below_threshold(self):
        """warmup=2, 3 matches: rated=1 < warmup → exclude 0."""
        self.assertEqual(_warmup_excluded(2, 3), 0)

    def test_warmup_2_at_threshold(self):
        """warmup=2, 4 matches: rated=2 = warmup → exclude 1."""
        self.assertEqual(_warmup_excluded(2, 4), 1)

    def test_warmup_2_drop_two(self):
        """warmup=2, 5 matches: rated=3 → exclude 2 (all warmup)."""
        self.assertEqual(_warmup_excluded(2, 5), 2)

    def test_warmup_2_many_matches(self):
        """warmup=2, 20 matches: all warmup excluded."""
        self.assertEqual(_warmup_excluded(2, 20), 2)

    def test_warmup_1_two_matches(self):
        """warmup=1, 2 matches: rated=1 = warmup → exclude 1."""
        self.assertEqual(_warmup_excluded(1, 2), 1)

    def test_warmup_1_three_matches(self):
        """warmup=1, 3 matches: rated=2 → exclude 1 (all warmup)."""
        self.assertEqual(_warmup_excluded(1, 3), 1)

    def test_warmup_3_five_matches(self):
        """warmup=3, 5 matches: rated=2 < warmup → exclude 0."""
        self.assertEqual(_warmup_excluded(3, 5), 0)

    def test_warmup_3_six_matches(self):
        """warmup=3, 6 matches: rated=3 = warmup → exclude 1."""
        self.assertEqual(_warmup_excluded(3, 6), 1)

    def test_warmup_3_eight_matches(self):
        """warmup=3, 8 matches: rated=5 → exclude 3 (all warmup)."""
        self.assertEqual(_warmup_excluded(3, 8), 3)

    def test_warmup_3_many_matches(self):
        """warmup=3, 12 matches: all warmup excluded."""
        self.assertEqual(_warmup_excluded(3, 12), 3)


# --- warmup integration ---


class TestWarmupLinear(unittest.TestCase):

    @patch("evaluate.run_match")
    def test_warmup_default_always_two(self, mock_run):
        """warmup=None → warmup_matches=2 regardless of match count."""
        mock_run.return_value = make_match_result(4, 2.0)

        result = evaluate_engine_linear(
            engine_path="/test/engine",
            num_matches=3,
            games_per_match=4,
            movetime_ms=100,
        )

        self.assertEqual(result.warmup_matches, 2)

    @patch("evaluate.run_match")
    def test_warmup_explicit_value(self, mock_run):
        """warmup=1 → first match excluded from ELO."""
        mock_run.side_effect = [
            make_match_result(10, 2.0),   # warmup: bad result at ELO 1000
            make_match_result(10, 5.0),   # rated: 50% at ELO 1500
            make_match_result(10, 5.0),   # rated: 50% at ELO 2000
        ]

        result = evaluate_engine_linear(
            engine_path="/test/engine",
            num_matches=3,
            games_per_match=10,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
            warmup=1,
        )

        self.assertEqual(result.warmup_matches, 1)
        # ELO should be based on matches 2 and 3 only (50% at 1500 and 2000)
        # → performance ≈ 1750
        self.assertAlmostEqual(result.estimated_elo, 1750, delta=10)

    @patch("evaluate.run_match")
    def test_warmup_total_score_includes_all(self, mock_run):
        """total_score and total_games include warmup matches."""
        mock_run.side_effect = [
            make_match_result(4, 4.0),   # warmup
            make_match_result(4, 2.0),   # rated
        ]

        result = evaluate_engine_linear(
            engine_path="/test/engine",
            num_matches=2,
            games_per_match=4,
            movetime_ms=100,
            warmup=1,
        )

        self.assertEqual(result.total_score, 6.0)
        self.assertEqual(result.total_games, 8)

    @patch("evaluate.run_match")
    def test_warmup_match_results_include_all(self, mock_run):
        """match_results contains all matches including warmup."""
        mock_run.return_value = make_match_result(4, 2.0)

        result = evaluate_engine_linear(
            engine_path="/test/engine",
            num_matches=3,
            games_per_match=4,
            movetime_ms=100,
            warmup=1,
        )

        self.assertEqual(len(result.match_results), 3)

    @patch("evaluate.run_match")
    def test_warmup_excludes_from_elo(self, mock_run):
        """ELO calculated without warmup matches — different from warmup=0.

        With gradual exclusion, warmup=1 needs 3+ matches to actually exclude:
        _warmup_excluded(1, 3) = 1 (rated=2, 2 >= 2*1 → drop 1).
        """
        mock_run.side_effect = [
            make_match_result(10, 10.0),   # warmup: perfect score at 1000
            make_match_result(10, 5.0),    # rated: 50% at 1500
            make_match_result(10, 5.0),    # rated: 50% at 2000
        ]

        result_with_warmup = evaluate_engine_linear(
            engine_path="/test/engine",
            num_matches=3,
            games_per_match=10,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
            warmup=1,
        )

        mock_run.reset_mock()
        mock_run.side_effect = [
            make_match_result(10, 10.0),
            make_match_result(10, 5.0),
            make_match_result(10, 5.0),
        ]

        result_no_warmup = evaluate_engine_linear(
            engine_path="/test/engine",
            num_matches=3,
            games_per_match=10,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
            warmup=0,
        )

        # With warmup=1 (excluded=1): ELO based on 50% vs 1500 + 50% vs 2000 → ≈1750
        # Without warmup: ELO based on 100% vs 1000 + 50% vs 1500 + 50% vs 2000 → higher
        self.assertEqual(result_with_warmup.warmup_excluded, 1)
        self.assertAlmostEqual(result_with_warmup.estimated_elo, 1750, delta=10)
        self.assertGreater(result_no_warmup.estimated_elo, result_with_warmup.estimated_elo)


class TestWarmupAdaptive(unittest.TestCase):

    @patch("evaluate.run_match")
    def test_warmup_used_for_selection_early(self, mock_run):
        """Before rated matches reach 2x warmup, warmup is included in selection."""
        mock_run.side_effect = [
            make_match_result(10, 9.0),   # warmup: strong result → ELO should rise
            make_match_result(10, 5.0),   # rated (1 rated < 2*1 warmup)
            make_match_result(10, 5.0),   # rated
        ]

        evaluate_engine_adaptive(
            engine_path="/test/engine",
            num_matches=3,
            games_per_match=10,
            movetime_ms=100,
            min_elo=800,
            max_elo=2800,
            warmup=1,
        )

        elos = [c.kwargs["stockfish_elo"] for c in mock_run.call_args_list]
        # Match 0 (warmup) at midpoint, match 1 still influenced by warmup win
        self.assertEqual(elos[0], 1800)
        self.assertGreater(elos[1], 1800)

    @patch("evaluate.run_match")
    def test_warmup_gradually_excluded_from_selection(self, mock_run):
        """Warmup matches are gradually dropped once rated >= warmup.

        warmup=2: matches 0-1 are warmup, 2+ are rated.
        Rated count thresholds for exclusion:
          rated < 2:  exclude 0 (all included)
          rated = 2:  exclude 1 (match 0 dropped)
          rated = 3:  exclude 2 (matches 0-1 dropped, all warmup gone)
        """
        # 6 matches total: 2 warmup + 4 rated
        mock_run.side_effect = [
            make_match_result(10, 9.0),   # match 0 (warmup): strong
            make_match_result(10, 9.0),   # match 1 (warmup): strong
            make_match_result(10, 5.0),   # match 2 (rated #1): excluded=0
            make_match_result(10, 1.0),   # match 3 (rated #2): excluded=1
            make_match_result(10, 1.0),   # match 4 (rated #3): excluded=2
            make_match_result(10, 5.0),   # match 5 (rated #4): excluded=2
        ]

        evaluate_engine_adaptive(
            engine_path="/test/engine",
            num_matches=6,
            games_per_match=10,
            movetime_ms=100,
            min_elo=800,
            max_elo=2800,
            warmup=2,
        )

        elos = [c.kwargs["stockfish_elo"] for c in mock_run.call_args_list]

        # Match 0: midpoint
        self.assertEqual(elos[0], 1800)

        # After match 2 (total=3): excluded=0, warmup 9.0 still included → high ELO
        # After match 3 (total=4): excluded=1, one warmup dropped
        # After match 4 (total=5): excluded=2, both warmup dropped
        # With warmup gone, only rated data (5.0 + 1.0 + 1.0 scores)
        # → ELO should drop vs match 2 (which had all warmup included)
        self.assertLess(elos[5], elos[2])

    @patch("evaluate.run_match")
    def test_warmup_zero_always_uses_all(self, mock_run):
        """warmup=0 → all matches always used for selection."""
        mock_run.return_value = make_match_result(10, 5.0)

        evaluate_engine_adaptive(
            engine_path="/test/engine",
            num_matches=5,
            games_per_match=10,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
            warmup=0,
        )

        # With 50% everywhere, all ELOs should be at midpoint
        elos = [c.kwargs["stockfish_elo"] for c in mock_run.call_args_list]
        for elo in elos:
            self.assertAlmostEqual(elo, 1500, delta=5)

    @patch("evaluate.run_match")
    def test_warmup_adaptive_default_many_matches(self, mock_run):
        """warmup=None with 12 matches → warmup_matches=2."""
        mock_run.return_value = make_match_result(4, 2.0)

        result = evaluate_engine_adaptive(
            engine_path="/test/engine",
            num_matches=12,
            games_per_match=4,
            movetime_ms=100,
        )

        self.assertEqual(result.warmup_matches, 2)

    @patch("evaluate.run_match")
    def test_warmup_via_dispatcher(self, mock_run):
        """warmup passes through evaluate_engine dispatcher."""
        mock_run.side_effect = [
            make_match_result(4, 4.0),
            make_match_result(4, 2.0),
            make_match_result(4, 2.0),
        ]

        result = evaluate_engine(
            strategy="linear",
            engine_path="/test/engine",
            num_matches=3,
            games_per_match=4,
            movetime_ms=100,
            warmup=1,
        )

        self.assertEqual(result.warmup_matches, 1)
        self.assertEqual(result.warmup_excluded, 1)


class TestWarmupGradualFinalRating(unittest.TestCase):
    """Test gradual warmup exclusion in the final performance rating."""

    @patch("evaluate.run_match")
    def test_warmup_2_below_threshold(self, mock_run):
        """warmup=2, 3 matches: rated=1 < warmup → exclude 0."""
        mock_run.side_effect = [
            make_match_result(10, 10.0),  # warmup 0
            make_match_result(10, 10.0),  # warmup 1
            make_match_result(10, 5.0),   # rated
        ]

        result = evaluate_engine_linear(
            engine_path="/test/engine",
            num_matches=3,
            games_per_match=10,
            movetime_ms=100,
            warmup=2,
        )

        self.assertEqual(result.warmup_matches, 2)
        self.assertEqual(result.warmup_excluded, 0)

    @patch("evaluate.run_match")
    def test_warmup_2_at_threshold_drop_one(self, mock_run):
        """warmup=2, 4 matches: rated=2 = warmup → exclude 1."""
        mock_run.side_effect = [
            make_match_result(10, 10.0),  # warmup 0 (excluded)
            make_match_result(10, 10.0),  # warmup 1 (still included)
            make_match_result(10, 5.0),   # rated
            make_match_result(10, 5.0),   # rated
        ]

        result = evaluate_engine_linear(
            engine_path="/test/engine",
            num_matches=4,
            games_per_match=10,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
            warmup=2,
        )

        self.assertEqual(result.warmup_excluded, 1)

    @patch("evaluate.run_match")
    def test_warmup_2_full_exclusion(self, mock_run):
        """warmup=2, 5 matches: rated=3 → exclude 2 (all warmup).

        Linear ELOs for 5 matches in [1000,2000]: 1000, 1250, 1500, 1750, 2000.
        After excluding 2 warmup: rated at 1500, 1750, 2000 with 50% each → ≈1750.
        """
        mock_run.side_effect = [
            make_match_result(10, 10.0),  # warmup 0 (excluded) at 1000
            make_match_result(10, 10.0),  # warmup 1 (excluded) at 1250
            make_match_result(10, 5.0),   # rated: 50% at 1500
            make_match_result(10, 5.0),   # rated: 50% at 1750
            make_match_result(10, 5.0),   # rated: 50% at 2000
        ]

        result = evaluate_engine_linear(
            engine_path="/test/engine",
            num_matches=5,
            games_per_match=10,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
            warmup=2,
        )

        self.assertEqual(result.warmup_excluded, 2)
        # Rating based on 50% at 1500, 1750, 2000 → ≈1750
        self.assertAlmostEqual(result.estimated_elo, 1750, delta=10)

    @patch("evaluate.run_match")
    def test_warmup_1_excludes_at_2_matches(self, mock_run):
        """warmup=1, 2 matches: rated=1 = warmup → exclude 1."""
        mock_run.side_effect = [
            make_match_result(10, 10.0),  # warmup (excluded)
            make_match_result(10, 5.0),   # rated: 50% at 2000
        ]

        result = evaluate_engine_linear(
            engine_path="/test/engine",
            num_matches=2,
            games_per_match=10,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
            warmup=1,
        )

        self.assertEqual(result.warmup_excluded, 1)
        self.assertAlmostEqual(result.estimated_elo, 2000, delta=10)

    @patch("evaluate.run_match")
    def test_bsearch_gradual_warmup(self, mock_run):
        """Gradual warmup applies to bsearch strategy too."""
        mock_run.side_effect = [
            make_match_result(10, 10.0),  # warmup (excluded)
            make_match_result(10, 5.0),   # rated
        ]

        result = evaluate_engine_bsearch(
            engine_path="/test/engine",
            num_matches=2,
            games_per_match=10,
            movetime_ms=100,
            warmup=1,
        )

        self.assertEqual(result.warmup_excluded, 1)

    @patch("evaluate.run_match")
    def test_warmup_zero_always_excludes_nothing(self, mock_run):
        """warmup=0 → warmup_excluded always 0."""
        mock_run.return_value = make_match_result(10, 5.0)

        result = evaluate_engine_linear(
            engine_path="/test/engine",
            num_matches=5,
            games_per_match=10,
            movetime_ms=100,
            warmup=0,
        )

        self.assertEqual(result.warmup_excluded, 0)


# --- get_stockfish_elo_range ---


class TestGetStockfishEloRange(unittest.TestCase):

    @patch("evaluate.UCIEngine")
    def test_detects_elo_range(self, mock_cls):
        engine = mock_cls.return_value.__enter__.return_value
        engine.get_option.return_value = {
            "type": "spin", "default": "1320", "min": "1320", "max": "3190",
        }

        min_elo, max_elo = get_stockfish_elo_range("/fake/stockfish")
        self.assertEqual(min_elo, 1320)
        self.assertEqual(max_elo, 3190)

    @patch("evaluate.UCIEngine")
    def test_fallback_when_no_option(self, mock_cls):
        engine = mock_cls.return_value.__enter__.return_value
        engine.get_option.return_value = None

        min_elo, max_elo = get_stockfish_elo_range("/fake/stockfish")
        self.assertEqual(min_elo, DEFAULT_MIN_ELO)
        self.assertEqual(max_elo, DEFAULT_MAX_ELO)

    @patch("evaluate.UCIEngine")
    def test_fallback_when_option_missing_min_max(self, mock_cls):
        engine = mock_cls.return_value.__enter__.return_value
        engine.get_option.return_value = {"type": "spin", "default": "1320"}

        min_elo, max_elo = get_stockfish_elo_range("/fake/stockfish")
        self.assertEqual(min_elo, DEFAULT_MIN_ELO)
        self.assertEqual(max_elo, DEFAULT_MAX_ELO)

    @patch("evaluate.UCIEngine")
    def test_fallback_on_oserror(self, mock_cls):
        mock_cls.return_value.__enter__.side_effect = OSError("not found")

        min_elo, max_elo = get_stockfish_elo_range("/fake/stockfish")
        self.assertEqual(min_elo, DEFAULT_MIN_ELO)
        self.assertEqual(max_elo, DEFAULT_MAX_ELO)

    @patch("evaluate.UCIEngine")
    def test_uses_stockfish_path(self, mock_cls):
        engine = mock_cls.return_value.__enter__.return_value
        engine.get_option.return_value = {
            "type": "spin", "min": "1000", "max": "3000",
        }

        get_stockfish_elo_range("/my/stockfish")
        mock_cls.assert_called_once_with("/my/stockfish")


# --- _resolve_elo_range ---


class TestResolveEloRange(unittest.TestCase):

    def test_both_provided(self):
        """When both are provided, no detection needed."""
        min_elo, max_elo = _resolve_elo_range(1000, 2000, "stockfish")
        self.assertEqual(min_elo, 1000)
        self.assertEqual(max_elo, 2000)

    @patch("evaluate.get_stockfish_elo_range", return_value=(1320, 3190))
    def test_both_none_detects(self, mock_detect):
        min_elo, max_elo = _resolve_elo_range(None, None, "/fake/sf")
        self.assertEqual(min_elo, 1320)
        self.assertEqual(max_elo, 3190)
        mock_detect.assert_called_once_with("/fake/sf")

    @patch("evaluate.get_stockfish_elo_range", return_value=(1320, 3190))
    def test_only_min_none(self, mock_detect):
        min_elo, max_elo = _resolve_elo_range(None, 2500, "/fake/sf")
        self.assertEqual(min_elo, 1320)
        self.assertEqual(max_elo, 2500)

    @patch("evaluate.get_stockfish_elo_range", return_value=(1320, 3190))
    def test_only_max_none(self, mock_detect):
        min_elo, max_elo = _resolve_elo_range(900, None, "/fake/sf")
        self.assertEqual(min_elo, 900)
        self.assertEqual(max_elo, 3190)

    def test_both_provided_no_detection(self):
        """Should not call get_stockfish_elo_range when both are given."""
        with patch("evaluate.get_stockfish_elo_range") as mock_detect:
            _resolve_elo_range(800, 2800, "stockfish")
            mock_detect.assert_not_called()


# --- auto-detect through dispatcher ---


class TestAutoDetectViaDispatcher(unittest.TestCase):

    @patch("evaluate.run_match")
    @patch("evaluate.get_stockfish_elo_range", return_value=(1320, 3190))
    def test_dispatcher_auto_detects_when_none(self, mock_detect, mock_run):
        """evaluate_engine() detects ELO range when min/max not provided."""
        mock_run.return_value = make_match_result(4, 2.0)

        evaluate_engine(
            strategy="adaptive",
            engine_path="/test/engine",
            num_matches=1,
            games_per_match=4,
            movetime_ms=100,
        )

        mock_detect.assert_called_once()
        # Midpoint of detected range: (1320+3190)//2 = 2255
        elo_called = mock_run.call_args.kwargs["stockfish_elo"]
        self.assertEqual(elo_called, 2255)

    @patch("evaluate.run_match")
    @patch("evaluate.get_stockfish_elo_range")
    def test_dispatcher_skips_detect_when_provided(self, mock_detect, mock_run):
        """evaluate_engine() does not detect when min/max explicitly given."""
        mock_run.return_value = make_match_result(4, 2.0)

        evaluate_engine(
            strategy="adaptive",
            engine_path="/test/engine",
            num_matches=1,
            games_per_match=4,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
        )

        mock_detect.assert_not_called()

    @patch("evaluate.run_match")
    @patch("evaluate.get_stockfish_elo_range", return_value=(1320, 3190))
    def test_dispatcher_linear_auto_detect(self, mock_detect, mock_run):
        mock_run.return_value = make_match_result(4, 2.0)

        evaluate_engine(
            strategy="linear",
            engine_path="/test/engine",
            num_matches=3,
            games_per_match=4,
            movetime_ms=100,
        )

        elos = [c.kwargs["stockfish_elo"] for c in mock_run.call_args_list]
        self.assertEqual(elos[0], 1320)
        self.assertEqual(elos[-1], 3190)

    @patch("evaluate.run_match")
    @patch("evaluate.get_stockfish_elo_range", return_value=(1320, 3190))
    def test_dispatcher_bsearch_auto_detect(self, mock_detect, mock_run):
        mock_run.return_value = make_match_result(4, 2.0)

        evaluate_engine(
            strategy="bsearch",
            engine_path="/test/engine",
            num_matches=1,
            games_per_match=4,
            movetime_ms=100,
        )

        elo_called = mock_run.call_args.kwargs["stockfish_elo"]
        self.assertEqual(elo_called, 2255)

    @patch("evaluate.run_match")
    @patch("evaluate.get_stockfish_elo_range", return_value=(1320, 3190))
    def test_dispatcher_passes_stockfish_path(self, mock_detect, mock_run):
        mock_run.return_value = make_match_result(4, 2.0)

        evaluate_engine(
            engine_path="/test/engine",
            num_matches=1,
            games_per_match=4,
            movetime_ms=100,
            stockfish_path="/my/stockfish",
        )

        mock_detect.assert_called_once_with("/my/stockfish")


class TestUseOpeningsForwarding(unittest.TestCase):

    @patch("evaluate.run_match")
    def test_use_openings_forwarded_to_run_match(self, mock_run):
        mock_run.return_value = make_match_result(2, 1.0)

        evaluate_engine(
            engine_path="/test/engine",
            num_matches=1,
            games_per_match=2,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
            use_openings=True,
        )

        mock_run.assert_called_once()
        self.assertTrue(mock_run.call_args.kwargs["use_openings"])

    @patch("evaluate.run_match")
    def test_use_openings_default_false(self, mock_run):
        mock_run.return_value = make_match_result(2, 1.0)

        evaluate_engine(
            engine_path="/test/engine",
            num_matches=1,
            games_per_match=2,
            movetime_ms=100,
            min_elo=1000,
            max_elo=2000,
        )

        mock_run.assert_called_once()
        self.assertFalse(mock_run.call_args.kwargs["use_openings"])


if __name__ == "__main__":
    unittest.main()
