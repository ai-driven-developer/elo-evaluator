import os
import shutil
import tempfile
import unittest

from chess_state import ChessState
from match_runner import GameResult
from pgn_logger import (
    uci_to_san,
    moves_to_san,
    game_to_pgn,
    create_log_dir,
    write_game_pgn,
    _add_check_suffix,
)


class TestUciToSan(unittest.TestCase):

    def test_pawn_single_push(self):
        s = ChessState()
        self.assertEqual(uci_to_san(s, "e2e4"), "e4")

    def test_pawn_single_push_e3(self):
        s = ChessState()
        self.assertEqual(uci_to_san(s, "e2e3"), "e3")

    def test_knight_move(self):
        s = ChessState()
        self.assertEqual(uci_to_san(s, "g1f3"), "Nf3")

    def test_pawn_capture(self):
        s = ChessState()
        s.push_uci("e2e4")
        s.push_uci("d7d5")
        self.assertEqual(uci_to_san(s, "e4d5"), "exd5")

    def test_bishop_move(self):
        s = ChessState()
        s.push_uci("e2e4")
        s.push_uci("e7e5")
        self.assertEqual(uci_to_san(s, "f1c4"), "Bc4")

    def test_queen_move(self):
        s = ChessState()
        s.push_uci("e2e4")
        s.push_uci("e7e5")
        self.assertEqual(uci_to_san(s, "d1h5"), "Qh5")

    def test_kingside_castling(self):
        s = ChessState()
        s.board[5] = "."  # f1
        s.board[6] = "."  # g1
        self.assertEqual(uci_to_san(s, "e1g1"), "O-O")

    def test_queenside_castling(self):
        s = ChessState()
        s.board[1] = "."  # b1
        s.board[2] = "."  # c1
        s.board[3] = "."  # d1
        self.assertEqual(uci_to_san(s, "e1c1"), "O-O-O")

    def test_promotion(self):
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"
        s.board[56] = "k"
        s.board[52] = "P"  # white pawn e7
        self.assertEqual(uci_to_san(s, "e7e8q"), "e8=Q")

    def test_promotion_with_capture(self):
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"
        s.board[56] = "k"
        s.board[52] = "P"  # white pawn e7
        s.board[61] = "r"  # black rook f8
        self.assertEqual(uci_to_san(s, "e7f8q"), "exf8=Q")

    def test_knight_disambiguation_by_file(self):
        """Two knights on different files can reach the same square."""
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"
        s.board[60] = "k"
        s.board[1] = "N"   # knight b1
        s.board[5] = "N"   # knight f1
        # Both can go to d2: b1->d2 (L-shape), f1->d2 (L-shape)
        san = uci_to_san(s, "b1d2")
        self.assertEqual(san, "Nbd2")

    def test_knight_disambiguation_by_rank(self):
        """Two knights on same file, different ranks."""
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"
        s.board[60] = "k"
        s.board[21] = "N"  # knight f3
        s.board[37] = "N"  # knight f5
        # Both can go to e3... actually f3->e1/g1/d2/h2/d4/h4/e5/g5
        # and f5->e3/g3/d4/h4/d6/h6/e7/g7
        # f3 can go to d4, f5 can go to d4. Same file (f). Need rank disambig.
        san = uci_to_san(s, "f3d4")
        self.assertEqual(san, "N3d4")

    def test_rook_capture(self):
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"
        s.board[60] = "k"
        s.board[0] = "R"   # white rook a1
        s.board[56] = "r"  # black rook a8 (wait, that's where k is)
        s.board[56] = "k"
        s.board[48] = "r"  # black rook a7
        # white rook captures a7
        san = uci_to_san(s, "a1a7")
        self.assertEqual(san, "Rxa7")

    def test_en_passant_san(self):
        s = ChessState()
        s.push_uci("e2e4")
        s.push_uci("a7a6")
        s.push_uci("e4e5")
        s.push_uci("d7d5")
        self.assertEqual(uci_to_san(s, "e5d6"), "exd6")


class TestAddCheckSuffix(unittest.TestCase):

    def test_check_suffix(self):
        s = ChessState()
        for m in ("f2f3", "e7e5", "g2g4"):
            s.push_uci(m)
        san = uci_to_san(s, "d8h4")
        s.push_uci("d8h4")
        san = _add_check_suffix(san, s)
        self.assertEqual(san, "Qh4#")

    def test_no_check_suffix(self):
        s = ChessState()
        san = uci_to_san(s, "e2e4")
        s.push_uci("e2e4")
        san = _add_check_suffix(san, s)
        self.assertEqual(san, "e4")

    def test_check_not_mate(self):
        """Check without checkmate gets + suffix."""
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"
        s.board[63] = "k"  # h8
        s.board[0] = "R"   # a1
        s.white_to_move = True
        san = uci_to_san(s, "a1a8")
        s.push_uci("a1a8")
        san = _add_check_suffix(san, s)
        # Rook on a8 checks king on h8 along the rank
        # King can escape to g7, g8, h7
        self.assertEqual(san, "Ra8+")


class TestMovesToSan(unittest.TestCase):

    def test_scholars_mate(self):
        moves = ["e2e4", "e7e5", "d1h5", "b8c6", "f1c4", "g8f6", "h5f7"]
        san = moves_to_san(moves)
        self.assertEqual(
            san,
            "1. e4 e5 2. Qh5 Nc6 3. Bc4 Nf6 4. Qxf7#",
        )

    def test_fools_mate(self):
        moves = ["f2f3", "e7e5", "g2g4", "d8h4"]
        san = moves_to_san(moves)
        self.assertEqual(san, "1. f3 e5 2. g4 Qh4#")

    def test_single_move(self):
        san = moves_to_san(["e2e4"])
        self.assertEqual(san, "1. e4")

    def test_empty_moves(self):
        san = moves_to_san([])
        self.assertEqual(san, "")


class TestGameToPgn(unittest.TestCase):

    def _make_game(self, **overrides):
        defaults = dict(
            game_number=1,
            white="engine",
            result="1-0",
            engine_score=1.0,
            moves=["e2e4", "e7e5", "d1h5", "b8c6", "f1c4", "g8f6", "h5f7"],
            termination="checkmate",
        )
        defaults.update(overrides)
        return GameResult(**defaults)

    def test_pgn_has_required_tags(self):
        game = self._make_game()
        pgn = game_to_pgn(game, match_number=1, stockfish_elo=1500,
                          engine_name="myengine", date="2026.02.26")
        self.assertIn('[Event "ELO Evaluation vs Stockfish 1500"]', pgn)
        self.assertIn('[Date "2026.02.26"]', pgn)
        self.assertIn('[Round "1.1"]', pgn)
        self.assertIn('[White "myengine"]', pgn)
        self.assertIn('[Black "Stockfish 1500"]', pgn)
        self.assertIn('[Result "1-0"]', pgn)
        self.assertIn('[Termination "checkmate"]', pgn)

    def test_pgn_engine_black(self):
        game = self._make_game(white="stockfish", result="0-1", engine_score=1.0)
        pgn = game_to_pgn(game, match_number=2, stockfish_elo=1200,
                          engine_name="testeng", date="2026.01.01")
        self.assertIn('[White "Stockfish 1200"]', pgn)
        self.assertIn('[Black "testeng"]', pgn)
        self.assertIn('[WhiteElo "1200"]', pgn)
        self.assertIn('[BlackElo "?"]', pgn)

    def test_pgn_has_move_text(self):
        game = self._make_game()
        pgn = game_to_pgn(game, match_number=1, stockfish_elo=1500,
                          engine_name="eng", date="2026.02.26")
        # Move text should end with result
        self.assertIn("Qxf7# 1-0", pgn)

    def test_pgn_ends_with_newline(self):
        game = self._make_game()
        pgn = game_to_pgn(game, match_number=1, stockfish_elo=1500,
                          engine_name="eng", date="2026.02.26")
        self.assertTrue(pgn.endswith("\n"))

    def test_pgn_draw(self):
        game = self._make_game(
            result="1/2-1/2", engine_score=0.5,
            moves=["g1f3", "g8f6", "f3g1", "f6g8",
                   "g1f3", "g8f6", "f3g1", "f6g8"],
            termination="threefold_repetition",
        )
        pgn = game_to_pgn(game, match_number=3, stockfish_elo=1000,
                          engine_name="eng", date="2026.02.26")
        self.assertIn('[Result "1/2-1/2"]', pgn)
        self.assertIn("1/2-1/2", pgn.split("\n")[-2])


class TestCreateLogDir(unittest.TestCase):

    def test_creates_directory(self):
        # Use a temp path to avoid creating real dirs in project
        tmpdir = tempfile.mkdtemp()
        try:
            fake_engine = os.path.join(tmpdir, "myengine.sh")
            open(fake_engine, "w").close()
            log_dir = create_log_dir(fake_engine)
            self.assertTrue(os.path.isdir(log_dir))
            # Dir name starts with engine basename
            basename = os.path.basename(log_dir)
            self.assertTrue(basename.startswith("myengine_"))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
            # Clean up created game_logs if it's under the project
            if "game_logs" in log_dir:
                parent = os.path.dirname(log_dir)
                shutil.rmtree(parent, ignore_errors=True)

    def test_strips_extension(self):
        tmpdir = tempfile.mkdtemp()
        try:
            fake_engine = os.path.join(tmpdir, "engine.sh")
            open(fake_engine, "w").close()
            log_dir = create_log_dir(fake_engine)
            basename = os.path.basename(log_dir)
            self.assertTrue(basename.startswith("engine_"))
            self.assertNotIn(".sh", basename)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
            if "game_logs" in log_dir:
                parent = os.path.dirname(log_dir)
                shutil.rmtree(parent, ignore_errors=True)


class TestWriteGamePgn(unittest.TestCase):

    def test_writes_file(self):
        tmpdir = tempfile.mkdtemp()
        try:
            game = GameResult(
                game_number=2,
                white="engine",
                result="1-0",
                engine_score=1.0,
                moves=["e2e4", "e7e5"],
                termination="checkmate",
            )
            write_game_pgn(tmpdir, 3, game, 1500, "eng", "2026.02.26")
            filepath = os.path.join(tmpdir, "3-2.pgn")
            self.assertTrue(os.path.isfile(filepath))
            with open(filepath) as f:
                content = f.read()
            self.assertIn('[Round "3.2"]', content)
            self.assertIn("1. e4 e5", content)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)

    def test_filename_format(self):
        tmpdir = tempfile.mkdtemp()
        try:
            game = GameResult(
                game_number=5,
                white="stockfish",
                result="0-1",
                engine_score=1.0,
                moves=["e2e4"],
                termination="checkmate",
            )
            write_game_pgn(tmpdir, 7, game, 2000, "eng", "2026.02.26")
            self.assertTrue(os.path.isfile(os.path.join(tmpdir, "7-5.pgn")))
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
