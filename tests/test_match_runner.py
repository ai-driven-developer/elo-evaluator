import unittest
from unittest.mock import patch, MagicMock

from uci_engine import MATE_SCORE
from match_runner import play_game, run_match, _compute_engine_score


def make_mock_engine(go_responses: list[tuple[str, int | None]]):
    """Create a mock UCIEngine that returns go_responses in order.

    Each element is (bestmove, score_cp).
    """
    engine = MagicMock()
    engine.path = "/mock/engine"
    engine.go = MagicMock(side_effect=go_responses)
    engine.new_game = MagicMock()
    engine.start = MagicMock()
    engine.quit = MagicMock()
    engine.set_option = MagicMock()
    engine.__enter__ = MagicMock(return_value=engine)
    engine.__exit__ = MagicMock(return_value=False)
    return engine


# --- play_game tests ---


class TestPlayGame(unittest.TestCase):

    def test_white_wins_by_checkmate(self):
        """White delivers checkmate — result is 1-0."""
        white = make_mock_engine([
            ("f2f3", 0),
            ("g2g4", -100),  # not great but let's say
        ])
        black = make_mock_engine([
            ("e7e5", 50),
            ("d8h4", MATE_SCORE),  # Actually black gives mate here
            # but let's simulate white getting mated:
        ])
        # Let me redo: simulate scholar's mate (4-move checkmate)
        # 1.e4 e5 2.Qh5 Nc6 3.Bc4 Nf6 4.Qxf7# — white mates
        white = make_mock_engine([
            ("e2e4", 30),
            ("d1h5", 100),
            ("f1c4", 200),
            ("h5f7", MATE_SCORE),
        ])
        # After Qxf7, black has no moves — checkmate
        black = make_mock_engine([
            ("e7e5", -30),
            ("b8c6", -100),
            ("g8f6", -200),
            ("(none)", -MATE_SCORE),  # checkmated
        ])
        result, moves, term = play_game(white, black, movetime_ms=100)
        self.assertEqual(result, "1-0")
        self.assertEqual(term, "checkmate")
        self.assertEqual(len(moves), 7)  # e2e4 e7e5 d1h5 b8c6 f1c4 g8f6 h5f7

    def test_black_wins_by_checkmate(self):
        """Black delivers checkmate — result is 0-1."""
        # Fool's mate: 1.f3 e5 2.g4 Qh4#
        white = make_mock_engine([
            ("f2f3", -10),
            ("g2g4", -200),
            ("(none)", -MATE_SCORE),  # white is mated
        ])
        black = make_mock_engine([
            ("e7e5", 50),
            ("d8h4", MATE_SCORE),
        ])
        result, moves, term = play_game(white, black, movetime_ms=100)
        self.assertEqual(result, "0-1")
        self.assertEqual(term, "checkmate")
        self.assertEqual(moves, ["f2f3", "e7e5", "g2g4", "d8h4"])

    def test_stalemate(self):
        """Side to move has no legal moves but is not in check — stalemate."""
        white = make_mock_engine([("e2e4", 10)])
        black = make_mock_engine([
            ("(none)", 0),  # no legal moves, score=0 → stalemate
        ])
        result, _moves, term = play_game(white, black, movetime_ms=100)
        self.assertEqual(result, "1/2-1/2")
        self.assertEqual(term, "stalemate")

    def test_draw_by_threefold_repetition(self):
        """Knight shuffle g1-f3-g1 / g8-f6-g8 triggers threefold repetition."""
        white = make_mock_engine([
            ("g1f3", 0), ("f3g1", 0), ("g1f3", 0), ("f3g1", 0),
        ])
        black = make_mock_engine([
            ("g8f6", 0), ("f6g8", 0), ("g8f6", 0), ("f6g8", 0),
        ])
        result, moves, term = play_game(white, black, movetime_ms=100)
        self.assertEqual(result, "1/2-1/2")
        self.assertEqual(term, "threefold_repetition")
        self.assertEqual(len(moves), 8)

    def test_stalemate_with_none_score(self):
        """bestmove (none) with score=None treated as stalemate."""
        white = make_mock_engine([("e2e4", 10)])
        black = make_mock_engine([("(none)", None)])
        result, _, term = play_game(white, black, movetime_ms=100)
        self.assertEqual(result, "1/2-1/2")
        self.assertEqual(term, "stalemate")

    # --- bestmove 0000 handling (alternative no-move indicator) ---

    def test_checkmate_via_0000_white_mated(self):
        """White returns 0000 when checkmated — black wins."""
        white = make_mock_engine([
            ("f2f3", -10),
            ("g2g4", -200),
            ("0000", -MATE_SCORE),
        ])
        black = make_mock_engine([
            ("e7e5", 50),
            ("d8h4", MATE_SCORE),
        ])
        result, moves, term = play_game(white, black, movetime_ms=100)
        self.assertEqual(result, "0-1")
        self.assertEqual(term, "checkmate")
        # 0000 is NOT appended to moves — it signals game over
        self.assertEqual(moves, ["f2f3", "e7e5", "g2g4", "d8h4"])

    def test_checkmate_via_0000_black_mated(self):
        """Black returns 0000 when checkmated — white wins."""
        white = make_mock_engine([
            ("e2e4", 30),
            ("d1h5", 100),
            ("f1c4", 200),
            ("h5f7", MATE_SCORE),
        ])
        black = make_mock_engine([
            ("e7e5", -30),
            ("b8c6", -100),
            ("g8f6", -200),
            ("0000", -MATE_SCORE),
        ])
        result, _moves, term = play_game(white, black, movetime_ms=100)
        self.assertEqual(result, "1-0")
        self.assertEqual(term, "checkmate")

    def test_stalemate_via_0000(self):
        """0000 with neutral score → stalemate."""
        white = make_mock_engine([("e2e4", 10)])
        black = make_mock_engine([("0000", 0)])
        result, _, term = play_game(white, black, movetime_ms=100)
        self.assertEqual(result, "1/2-1/2")
        self.assertEqual(term, "stalemate")

    def test_stalemate_via_0000_no_score(self):
        """0000 with no score info → stalemate."""
        white = make_mock_engine([("e2e4", 10)])
        black = make_mock_engine([("0000", None)])
        result, _, term = play_game(white, black, movetime_ms=100)
        self.assertEqual(result, "1/2-1/2")
        self.assertEqual(term, "stalemate")

    def test_illegal_move_forfeits_white(self):
        """White sends an invalid move (a1a1) — white forfeits, black wins."""
        white = make_mock_engine([("a1a1", 0)])
        black = make_mock_engine([])
        result, moves, term = play_game(white, black, movetime_ms=100)
        self.assertEqual(result, "0-1")
        self.assertEqual(term, "illegal_move")

    def test_illegal_move_forfeits_black(self):
        """Black sends an invalid move — black forfeits, white wins."""
        white = make_mock_engine([("e2e4", 10)])
        black = make_mock_engine([("x9z1", 0)])
        result, moves, term = play_game(white, black, movetime_ms=100)
        self.assertEqual(result, "1-0")
        self.assertEqual(term, "illegal_move")

    def test_illegal_move_with_mate_score_is_checkmate(self):
        """Engine sends garbage but reports being mated — treat as checkmate."""
        white = make_mock_engine([
            ("f2f3", -10),
            ("g2g4", -200),
            ("a1a1", -MATE_SCORE),  # should be (none) but sent garbage
        ])
        black = make_mock_engine([
            ("e7e5", 50),
            ("d8h4", MATE_SCORE),
        ])
        result, moves, term = play_game(white, black, movetime_ms=100)
        self.assertEqual(result, "0-1")
        self.assertEqual(term, "checkmate")

    def test_illegal_move_empty_square(self):
        """Moving from an empty square is rejected."""
        white = make_mock_engine([("e4e5", 10)])  # e4 is empty at start
        black = make_mock_engine([])
        result, moves, term = play_game(white, black, movetime_ms=100)
        self.assertEqual(result, "0-1")
        self.assertEqual(term, "illegal_move")

    def test_illegal_move_wrong_color(self):
        """White tries to move a black piece — illegal."""
        white = make_mock_engine([("e7e5", 10)])  # black pawn
        black = make_mock_engine([])
        result, moves, term = play_game(white, black, movetime_ms=100)
        self.assertEqual(result, "0-1")
        self.assertEqual(term, "illegal_move")

    def test_new_game_called_for_both_engines(self):
        """new_game() is called on both engines before playing."""
        white = make_mock_engine([("(none)", -MATE_SCORE)])
        black = make_mock_engine([])
        play_game(white, black, movetime_ms=100)
        white.new_game.assert_called_once()
        black.new_game.assert_called_once()

    def test_moves_passed_to_go(self):
        """Each go() call receives the accumulated move list."""
        white = make_mock_engine([("e2e4", 10), ("d2d4", 5)])
        black = make_mock_engine([("e7e5", -10), ("(none)", -MATE_SCORE)])

        play_game(white, black, movetime_ms=100)

        # White first call: no moves
        white.go.assert_any_call([], 100)
        # Black first call: ["e2e4"]
        black.go.assert_any_call(["e2e4"], 100)
        # White second call: ["e2e4", "e7e5"]
        white.go.assert_any_call(["e2e4", "e7e5"], 100)
        # Black second call: ["e2e4", "e7e5", "d2d4"]
        black.go.assert_any_call(["e2e4", "e7e5", "d2d4"], 100)


# --- play_game opening_moves tests ---


class TestPlayGameOpenings(unittest.TestCase):

    def test_opening_moves_prepended(self):
        """When opening_moves are given, engines see them in the move list."""
        white = make_mock_engine([("d2d4", 5)])
        black = make_mock_engine([("(none)", -MATE_SCORE)])

        play_game(white, black, movetime_ms=100, opening_moves=["e2e4", "e7e5"])

        # White's first go() should see the opening moves
        white.go.assert_any_call(["e2e4", "e7e5"], 100)
        # Black sees opening + white's move
        black.go.assert_any_call(["e2e4", "e7e5", "d2d4"], 100)

    def test_opening_moves_in_result(self):
        """Returned moves list includes opening moves."""
        white = make_mock_engine([("(none)", -MATE_SCORE)])
        black = make_mock_engine([])

        _, moves, _ = play_game(
            white, black, movetime_ms=100, opening_moves=["e2e4", "e7e5"],
        )

        self.assertEqual(moves[:2], ["e2e4", "e7e5"])

    def test_no_opening_moves_default(self):
        """Without opening_moves, first engine call gets empty list."""
        white = make_mock_engine([("(none)", -MATE_SCORE)])
        black = make_mock_engine([])

        play_game(white, black, movetime_ms=100)

        white.go.assert_called_with([], 100)

    def test_opening_side_to_move_correct(self):
        """After odd-length opening, black moves first."""
        # 3-move opening: e2e4 e7e5 g1f3 → black to move
        white = make_mock_engine([])
        black = make_mock_engine([("(none)", -MATE_SCORE)])

        play_game(
            white, black, movetime_ms=100,
            opening_moves=["e2e4", "e7e5", "g1f3"],
        )

        # Black should be called (side=1 because len(moves)=3 is odd)
        black.go.assert_called_once()
        white.go.assert_not_called()


# --- _compute_engine_score tests ---


class TestComputeEngineScore(unittest.TestCase):

    def test_white_wins_engine_is_white(self):
        self.assertEqual(_compute_engine_score("1-0", engine_is_white=True), 1.0)

    def test_white_wins_engine_is_black(self):
        self.assertEqual(_compute_engine_score("1-0", engine_is_white=False), 0.0)

    def test_black_wins_engine_is_white(self):
        self.assertEqual(_compute_engine_score("0-1", engine_is_white=True), 0.0)

    def test_black_wins_engine_is_black(self):
        self.assertEqual(_compute_engine_score("0-1", engine_is_white=False), 1.0)

    def test_draw(self):
        self.assertEqual(_compute_engine_score("1/2-1/2", engine_is_white=True), 0.5)
        self.assertEqual(_compute_engine_score("1/2-1/2", engine_is_white=False), 0.5)

    def test_unknown_result_raises(self):
        with self.assertRaises(ValueError):
            _compute_engine_score("*", engine_is_white=True)


# --- run_match tests ---


class TestRunMatch(unittest.TestCase):

    @patch("match_runner.UCIEngine")
    def test_stockfish_receives_elo_options(self, mock_cls):
        """Stockfish engine gets UCI_LimitStrength and UCI_Elo set."""
        engine_inst = make_mock_engine([("(none)", -MATE_SCORE)])
        sf_inst = make_mock_engine([])

        # UCIEngine is called twice: first for engine, second for stockfish
        mock_cls.side_effect = [engine_inst, sf_inst]

        run_match(
            engine_path="/test/engine",
            stockfish_elo=1500,
            num_games=1,
            movetime_ms=100,
        )

        sf_inst.set_option.assert_any_call("UCI_LimitStrength", "true")
        sf_inst.set_option.assert_any_call("UCI_Elo", "1500")

    @patch("match_runner.UCIEngine")
    def test_color_alternation(self, mock_cls):
        """Engine alternates colors: game 0 white, game 1 black, etc."""
        # Game 0: engine=white, gets mated immediately (0-1)
        # Game 1: engine=black, SF (white) gets mated immediately (0-1, engine wins)
        engine_inst = make_mock_engine([
            ("(none)", -MATE_SCORE),  # game 0: engine white, mated
            # game 1: engine black, moves second — not called first
            ("(none)", -MATE_SCORE),  # game 2: engine white, mated
        ])
        sf_inst = make_mock_engine([
            # game 0: SF black, never called (white mated on move 1)
            ("(none)", -MATE_SCORE),  # game 1: SF white, mated
            # game 2: SF black, never called
        ])

        mock_cls.side_effect = [engine_inst, sf_inst]

        result = run_match(
            engine_path="/test/engine",
            stockfish_elo=1500,
            num_games=3,
            movetime_ms=100,
        )

        self.assertEqual(result.games[0].white, "engine")
        self.assertEqual(result.games[1].white, "stockfish")
        self.assertEqual(result.games[2].white, "engine")

    @patch("match_runner.UCIEngine")
    def test_score_counting_engine_wins_as_white(self, mock_cls):
        """Engine wins as white — gets 1.0 point."""
        # Simple: SF (black) gets mated
        engine_inst = make_mock_engine([("e2e4", 30)])
        sf_inst = make_mock_engine([("(none)", -MATE_SCORE)])

        mock_cls.side_effect = [engine_inst, sf_inst]

        result = run_match(
            engine_path="/test/engine",
            stockfish_elo=1500,
            num_games=1,
            movetime_ms=100,
        )

        self.assertEqual(result.total_score, 1.0)
        self.assertEqual(result.games[0].engine_score, 1.0)
        self.assertEqual(result.games[0].result, "1-0")

    @patch("match_runner.UCIEngine")
    def test_score_counting_engine_loses_as_white(self, mock_cls):
        """Engine gets mated as white — gets 0.0 points."""
        engine_inst = make_mock_engine([("(none)", -MATE_SCORE)])
        sf_inst = make_mock_engine([])

        mock_cls.side_effect = [engine_inst, sf_inst]

        result = run_match(
            engine_path="/test/engine",
            stockfish_elo=1500,
            num_games=1,
            movetime_ms=100,
        )

        self.assertEqual(result.total_score, 0.0)
        self.assertEqual(result.games[0].engine_score, 0.0)

    @patch("match_runner.play_game")
    @patch("match_runner.UCIEngine")
    def test_score_counting_draw(self, mock_cls, mock_play):
        """Draw — engine gets 0.5."""
        engine_inst = make_mock_engine([])
        sf_inst = make_mock_engine([])
        mock_cls.side_effect = [engine_inst, sf_inst]

        mock_play.return_value = ("1/2-1/2", ["g1f3", "g8f6"], "threefold_repetition")

        result = run_match(
            engine_path="/test/engine",
            stockfish_elo=1500,
            num_games=1,
            movetime_ms=100,
        )

        self.assertEqual(result.total_score, 0.5)
        self.assertEqual(result.games[0].termination, "threefold_repetition")

    @patch("match_runner.play_game")
    @patch("match_runner.UCIEngine")
    def test_total_score_aggregation(self, mock_cls, mock_play):
        """Total score is summed correctly across multiple games."""
        engine_inst = make_mock_engine([])
        sf_inst = make_mock_engine([])
        mock_cls.side_effect = [engine_inst, sf_inst]

        # 3 games: win, loss, draw
        mock_play.side_effect = [
            ("1-0", ["e2e4", "e7e5"], "checkmate"),  # game 0: engine white, 1-0 → 1.0
            ("0-1", ["d2d4", "d7d5"], "checkmate"),  # game 1: engine black, 0-1 → 1.0
            ("1/2-1/2", ["c2c4"], "max_moves"),       # game 2: engine white → 0.5
        ]

        result = run_match(
            engine_path="/test/engine",
            stockfish_elo=1500,
            num_games=3,
            movetime_ms=100,
        )

        self.assertEqual(result.total_score, 2.5)
        self.assertEqual(result.num_games, 3)
        self.assertEqual(len(result.games), 3)
        self.assertEqual(result.games[0].engine_score, 1.0)
        self.assertEqual(result.games[1].engine_score, 1.0)
        self.assertEqual(result.games[2].engine_score, 0.5)

    @patch("match_runner.play_game")
    @patch("match_runner.UCIEngine")
    def test_all_losses(self, mock_cls, mock_play):
        """Engine loses all games — total score is 0."""
        engine_inst = make_mock_engine([])
        sf_inst = make_mock_engine([])
        mock_cls.side_effect = [engine_inst, sf_inst]

        mock_play.side_effect = [
            ("0-1", [], "checkmate"),  # game 0: engine white, 0-1 → 0.0
            ("1-0", [], "checkmate"),  # game 1: engine black, 1-0 → 0.0
        ]

        result = run_match(
            engine_path="/test/engine",
            stockfish_elo=1500,
            num_games=2,
            movetime_ms=100,
        )

        self.assertEqual(result.total_score, 0.0)

    @patch("match_runner.play_game")
    @patch("match_runner.UCIEngine")
    def test_game_result_fields(self, mock_cls, mock_play):
        """GameResult fields are populated correctly."""
        engine_inst = make_mock_engine([])
        sf_inst = make_mock_engine([])
        mock_cls.side_effect = [engine_inst, sf_inst]

        mock_play.return_value = ("1-0", ["e2e4", "e7e5", "d1h5"], "checkmate")

        result = run_match(
            engine_path="/test/engine",
            stockfish_elo=1500,
            num_games=1,
            movetime_ms=100,
        )

        game = result.games[0]
        self.assertEqual(game.game_number, 1)
        self.assertEqual(game.white, "engine")
        self.assertEqual(game.result, "1-0")
        self.assertEqual(game.engine_score, 1.0)
        self.assertEqual(game.moves, ["e2e4", "e7e5", "d1h5"])
        self.assertEqual(game.termination, "checkmate")


class TestRunMatchOpenings(unittest.TestCase):

    @patch("match_runner.get_random_opening", return_value=["e2e4", "e7e5"])
    @patch("match_runner.play_game")
    @patch("match_runner.UCIEngine")
    def test_use_openings_passes_opening_moves(
        self, mock_cls, mock_play, mock_opening,
    ):
        engine_inst = make_mock_engine([])
        sf_inst = make_mock_engine([])
        mock_cls.side_effect = [engine_inst, sf_inst]
        mock_play.return_value = ("1/2-1/2", [], "stalemate")

        run_match(
            engine_path="/test/engine",
            stockfish_elo=1500,
            num_games=1,
            movetime_ms=100,
            use_openings=True,
        )

        mock_opening.assert_called_once()
        _, kwargs = mock_play.call_args
        self.assertEqual(kwargs["opening_moves"], ["e2e4", "e7e5"])

    @patch("match_runner.get_random_opening")
    @patch("match_runner.play_game")
    @patch("match_runner.UCIEngine")
    def test_no_openings_by_default(self, mock_cls, mock_play, mock_opening):
        engine_inst = make_mock_engine([])
        sf_inst = make_mock_engine([])
        mock_cls.side_effect = [engine_inst, sf_inst]
        mock_play.return_value = ("1/2-1/2", [], "stalemate")

        run_match(
            engine_path="/test/engine",
            stockfish_elo=1500,
            num_games=1,
            movetime_ms=100,
        )

        mock_opening.assert_not_called()
        _, kwargs = mock_play.call_args
        self.assertIsNone(kwargs["opening_moves"])


class TestRunMatchLogging(unittest.TestCase):

    @patch("match_runner.play_game")
    @patch("match_runner.UCIEngine")
    def test_game_results_are_logged(self, mock_cls, mock_play):
        """Each game result is logged at INFO level."""
        engine_inst = make_mock_engine([])
        sf_inst = make_mock_engine([])
        mock_cls.side_effect = [engine_inst, sf_inst]

        mock_play.side_effect = [
            ("1-0", ["e2e4"], "checkmate"),
            ("1/2-1/2", ["d2d4", "d7d5"], "max_moves"),
        ]

        with self.assertLogs("match_runner", level="INFO") as cm:
            run_match(
                engine_path="/test/engine",
                stockfish_elo=1500,
                num_games=2,
                movetime_ms=100,
            )

        # Should have 2 INFO log messages
        self.assertEqual(len(cm.output), 2)
        self.assertIn("Game 1", cm.output[0])
        self.assertIn("1-0", cm.output[0])
        self.assertIn("Game 2", cm.output[1])
        self.assertIn("1/2-1/2", cm.output[1])


if __name__ == "__main__":
    unittest.main()
