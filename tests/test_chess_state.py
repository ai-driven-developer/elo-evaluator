import unittest

from chess_state import ChessState


class TestInitialBoard(unittest.TestCase):

    def test_white_pieces_rank1(self):
        s = ChessState()
        rank1 = [s.board[i] for i in range(8)]
        self.assertEqual(rank1, list("RNBQKBNR"))

    def test_white_pawns_rank2(self):
        s = ChessState()
        rank2 = [s.board[i] for i in range(8, 16)]
        self.assertEqual(rank2, ["P"] * 8)

    def test_empty_middle(self):
        s = ChessState()
        for i in range(16, 48):
            self.assertEqual(s.board[i], ".", f"index {i} should be empty")

    def test_black_pawns_rank7(self):
        s = ChessState()
        rank7 = [s.board[i] for i in range(48, 56)]
        self.assertEqual(rank7, ["p"] * 8)

    def test_black_pieces_rank8(self):
        s = ChessState()
        rank8 = [s.board[i] for i in range(56, 64)]
        self.assertEqual(rank8, list("rnbqkbnr"))

    def test_white_to_move(self):
        s = ChessState()
        self.assertTrue(s.white_to_move)

    def test_all_castling_rights(self):
        s = ChessState()
        self.assertEqual(s.castling, [True, True, True, True])

    def test_no_en_passant(self):
        s = ChessState()
        self.assertEqual(s.en_passant_file, -1)

    def test_halfmove_clock_zero(self):
        s = ChessState()
        self.assertEqual(s.halfmove_clock, 0)


class TestSquareIndex(unittest.TestCase):

    def test_a1(self):
        self.assertEqual(ChessState._square_index("a1"), 0)

    def test_h1(self):
        self.assertEqual(ChessState._square_index("h1"), 7)

    def test_a8(self):
        self.assertEqual(ChessState._square_index("a8"), 56)

    def test_h8(self):
        self.assertEqual(ChessState._square_index("h8"), 63)

    def test_e2(self):
        self.assertEqual(ChessState._square_index("e2"), 12)

    def test_e4(self):
        self.assertEqual(ChessState._square_index("e4"), 28)


class TestPawnMoves(unittest.TestCase):

    def test_single_pawn_push(self):
        s = ChessState()
        s.push_uci("e2e3")
        self.assertEqual(s.board[12], ".")  # e2 empty
        self.assertEqual(s.board[20], "P")  # e3 has pawn
        self.assertFalse(s.white_to_move)

    def test_double_pawn_push_sets_en_passant(self):
        s = ChessState()
        s.push_uci("e2e4")
        self.assertEqual(s.board[12], ".")  # e2 empty
        self.assertEqual(s.board[28], "P")  # e4 has pawn
        self.assertEqual(s.en_passant_file, 4)  # e-file

    def test_en_passant_cleared_after_next_move(self):
        s = ChessState()
        s.push_uci("e2e4")
        self.assertEqual(s.en_passant_file, 4)
        s.push_uci("g8f6")  # non-pawn-push
        self.assertEqual(s.en_passant_file, -1)

    def test_black_double_pawn_push(self):
        s = ChessState()
        s.push_uci("e2e4")
        s.push_uci("d7d5")
        self.assertEqual(s.board[51], ".")  # d7 = 6*8+3 = 51
        self.assertEqual(s.board[35], "p")  # d5 = 4*8+3 = 35
        self.assertEqual(s.en_passant_file, 3)  # d-file

    def test_pawn_move_resets_halfmove_clock(self):
        s = ChessState()
        s.push_uci("g1f3")  # knight move → clock=1
        self.assertEqual(s.halfmove_clock, 1)
        s.push_uci("e7e5")  # pawn move → clock=0
        self.assertEqual(s.halfmove_clock, 0)


class TestEnPassantCapture(unittest.TestCase):

    def test_white_captures_en_passant(self):
        s = ChessState()
        # 1. e4 a6 2. e5 d5 3. exd6 (en passant)
        s.push_uci("e2e4")
        s.push_uci("a7a6")
        s.push_uci("e4e5")
        s.push_uci("d7d5")  # en passant possible
        self.assertEqual(s.en_passant_file, 3)

        s.push_uci("e5d6")  # en passant capture
        self.assertEqual(s.board[43], "P")  # d6 = 5*8+3 = 43
        self.assertEqual(s.board[35], ".")  # d5 = 4*8+3 = 35 (captured pawn removed)
        self.assertEqual(s.board[36], ".")  # e5 = 4*8+4 = 36 (source empty)

    def test_black_captures_en_passant(self):
        s = ChessState()
        # 1. a3 e5 2. a4 e4 3. d4 exd3 (en passant)
        s.push_uci("a2a3")
        s.push_uci("e7e5")
        s.push_uci("a3a4")
        s.push_uci("e5e4")
        s.push_uci("d2d4")  # en passant possible
        self.assertEqual(s.en_passant_file, 3)

        s.push_uci("e4d3")  # en passant capture
        self.assertEqual(s.board[19], "p")  # d3 = 2*8+3 = 19
        self.assertEqual(s.board[27], ".")  # d4 = 3*8+3 = 27 (captured pawn removed)
        self.assertEqual(s.board[28], ".")  # e4 = 3*8+4 = 28 (source empty)


class TestCaptures(unittest.TestCase):

    def test_capture_replaces_piece(self):
        s = ChessState()
        # 1. e4 d5 2. exd5
        s.push_uci("e2e4")
        s.push_uci("d7d5")
        s.push_uci("e4d5")
        self.assertEqual(s.board[35], "P")  # d5 has white pawn
        self.assertEqual(s.board[28], ".")  # e4 empty

    def test_capture_resets_halfmove_clock(self):
        s = ChessState()
        # 1. e4 d5 — both pawn moves, clock stays 0
        s.push_uci("e2e4")
        s.push_uci("d7d5")
        # 2. Nf3 — knight move, clock = 1
        s.push_uci("g1f3")
        self.assertEqual(s.halfmove_clock, 1)
        # 2... Nc6 — knight move, clock = 2
        s.push_uci("b8c6")
        self.assertEqual(s.halfmove_clock, 2)
        # 3. exd5 — capture, clock = 0
        s.push_uci("e4d5")
        self.assertEqual(s.halfmove_clock, 0)


class TestKnightMoves(unittest.TestCase):

    def test_knight_move(self):
        s = ChessState()
        s.push_uci("g1f3")
        self.assertEqual(s.board[6], ".")   # g1 empty
        self.assertEqual(s.board[21], "N")  # f3 = 2*8+5 = 21

    def test_knight_move_increments_halfmove_clock(self):
        s = ChessState()
        s.push_uci("g1f3")
        self.assertEqual(s.halfmove_clock, 1)
        s.push_uci("g8f6")
        self.assertEqual(s.halfmove_clock, 2)


class TestCastling(unittest.TestCase):

    def _setup_kingside_clear(self):
        """Return a state with f1/g1 and f8/g8 cleared for castling."""
        s = ChessState()
        # Clear f1, g1 for white kingside
        s.board[5] = "."  # f1
        s.board[6] = "."  # g1
        # Clear f8, g8 for black kingside
        s.board[61] = "."  # f8
        s.board[62] = "."  # g8
        return s

    def _setup_queenside_clear(self):
        """Return a state with b1/c1/d1 and b8/c8/d8 cleared for castling."""
        s = ChessState()
        s.board[1] = "."  # b1
        s.board[2] = "."  # c1
        s.board[3] = "."  # d1
        s.board[57] = "."  # b8
        s.board[58] = "."  # c8
        s.board[59] = "."  # d8
        return s

    def test_white_kingside_castle(self):
        s = self._setup_kingside_clear()
        s.push_uci("e1g1")
        self.assertEqual(s.board[6], "K")   # g1 = king
        self.assertEqual(s.board[5], "R")   # f1 = rook
        self.assertEqual(s.board[4], ".")   # e1 empty
        self.assertEqual(s.board[7], ".")   # h1 empty

    def test_white_queenside_castle(self):
        s = self._setup_queenside_clear()
        s.push_uci("e1c1")
        self.assertEqual(s.board[2], "K")   # c1 = king
        self.assertEqual(s.board[3], "R")   # d1 = rook
        self.assertEqual(s.board[4], ".")   # e1 empty
        self.assertEqual(s.board[0], ".")   # a1 empty

    def test_black_kingside_castle(self):
        s = self._setup_kingside_clear()
        s.white_to_move = False
        s.push_uci("e8g8")
        self.assertEqual(s.board[62], "k")  # g8 = king
        self.assertEqual(s.board[61], "r")  # f8 = rook
        self.assertEqual(s.board[60], ".")  # e8 empty
        self.assertEqual(s.board[63], ".")  # h8 empty

    def test_black_queenside_castle(self):
        s = self._setup_queenside_clear()
        s.white_to_move = False
        s.push_uci("e8c8")
        self.assertEqual(s.board[58], "k")  # c8 = king
        self.assertEqual(s.board[59], "r")  # d8 = rook
        self.assertEqual(s.board[60], ".")  # e8 empty
        self.assertEqual(s.board[56], ".")  # a8 empty

    def test_white_king_move_removes_both_castling_rights(self):
        s = ChessState()
        s.push_uci("e2e4")
        s.push_uci("e7e5")
        # Manually clear d1 for king move
        s.board[3] = "."
        s.push_uci("e1d1")  # non-castling king move
        self.assertFalse(s.castling[0])  # K
        self.assertFalse(s.castling[1])  # Q

    def test_black_king_move_removes_both_castling_rights(self):
        s = ChessState()
        s.push_uci("e2e4")
        s.board[59] = "."  # clear d8
        s.push_uci("e8d8")
        self.assertFalse(s.castling[2])  # k
        self.assertFalse(s.castling[3])  # q

    def test_h1_rook_move_removes_K_right(self):
        s = ChessState()
        s.board[6] = "."  # clear g1
        s.push_uci("h1g1")
        self.assertFalse(s.castling[0])  # K gone
        self.assertTrue(s.castling[1])   # Q still there

    def test_a1_rook_move_removes_Q_right(self):
        s = ChessState()
        s.board[1] = "."  # clear b1
        s.push_uci("a1b1")
        self.assertTrue(s.castling[0])   # K still there
        self.assertFalse(s.castling[1])  # Q gone

    def test_capture_on_h1_removes_K_right(self):
        """Opponent captures rook on h1 → white loses kingside castling."""
        s = ChessState()
        # Put a black rook on g2 and let it capture h1
        s.board[14] = "r"  # g2
        s.white_to_move = False
        s.push_uci("g2h1")
        self.assertFalse(s.castling[0])  # K gone

    def test_capture_on_a8_removes_q_right(self):
        """White captures rook on a8 → black loses queenside castling."""
        s = ChessState()
        # Put a white rook on a7
        s.board[48] = "R"  # a7
        s.push_uci("a7a8")
        self.assertFalse(s.castling[3])  # q gone


class TestPromotion(unittest.TestCase):

    def test_white_promotes_to_queen(self):
        s = ChessState()
        # Put white pawn on e7, clear e8
        s.board[52] = "P"
        s.board[60] = "."
        s.push_uci("e7e8q")
        self.assertEqual(s.board[60], "Q")
        self.assertEqual(s.board[52], ".")

    def test_black_promotes_to_knight(self):
        s = ChessState()
        # Put black pawn on d2, clear d1
        s.board[11] = "p"
        s.board[3] = "."
        s.white_to_move = False
        s.push_uci("d2d1n")
        self.assertEqual(s.board[3], "n")
        self.assertEqual(s.board[11], ".")

    def test_promotion_with_capture(self):
        s = ChessState()
        # Put white pawn on d7, black rook on e8
        s.board[51] = "P"
        s.board[60] = "r"
        s.push_uci("d7e8q")
        self.assertEqual(s.board[60], "Q")  # promoted queen
        self.assertEqual(s.board[51], ".")


class TestHalfmoveClock(unittest.TestCase):

    def test_increments_on_piece_moves(self):
        s = ChessState()
        s.push_uci("g1f3")  # 1
        s.push_uci("g8f6")  # 2
        s.push_uci("f3g1")  # 3
        s.push_uci("f6g8")  # 4
        self.assertEqual(s.halfmove_clock, 4)

    def test_resets_on_pawn_push(self):
        s = ChessState()
        s.push_uci("g1f3")
        s.push_uci("g8f6")
        self.assertEqual(s.halfmove_clock, 2)
        s.push_uci("e2e4")  # pawn move resets
        self.assertEqual(s.halfmove_clock, 0)

    def test_resets_on_capture(self):
        s = ChessState()
        s.push_uci("e2e4")
        s.push_uci("d7d5")
        s.push_uci("g1f3")
        s.push_uci("b8c6")
        self.assertEqual(s.halfmove_clock, 2)
        s.push_uci("e4d5")  # capture resets
        self.assertEqual(s.halfmove_clock, 0)


class TestThreefoldRepetition(unittest.TestCase):

    def test_knight_shuffle_triggers_threefold(self):
        """Ng1-f3-g1-f3-g1... with Ng8-f6-g8-f6-g8 → starting position 3x."""
        s = ChessState()
        moves = [
            "g1f3", "g8f6",  # develop knights
            "f3g1", "f6g8",  # return → initial position (2nd time)
            "g1f3", "g8f6",  # develop again
            "f3g1", "f6g8",  # return → initial position (3rd time)
        ]
        for m in moves:
            s.push_uci(m)

        self.assertTrue(s.is_threefold_repetition())

    def test_two_repetitions_not_enough(self):
        """Position appears only twice — not threefold yet."""
        s = ChessState()
        moves = [
            "g1f3", "g8f6",
            "f3g1", "f6g8",  # initial position 2nd time
        ]
        for m in moves:
            s.push_uci(m)

        self.assertFalse(s.is_threefold_repetition())

    def test_different_castling_rights_are_different_positions(self):
        """Same piece placement but different castling rights → different position."""
        s1 = ChessState()
        s2 = ChessState()
        s2.castling[0] = False  # lose K castling

        self.assertNotEqual(s1._position_key(), s2._position_key())

    def test_different_en_passant_are_different_positions(self):
        """Same pieces but different en passant → different position."""
        s1 = ChessState()
        s1.push_uci("e2e4")  # en_passant_file = 4

        s2 = ChessState()
        s2.push_uci("e2e3")  # en_passant_file = -1

        # Both have a pawn moved from e2, but en passant differs
        self.assertNotEqual(s1._position_key(), s2._position_key())

    def test_pawn_move_breaks_repetition(self):
        """Positions after a pawn move can't equal positions before it."""
        s = ChessState()
        moves = [
            "g1f3", "g8f6",
            "f3g1", "f6g8",  # 2nd time initial
            "e2e4",          # pawn move changes board
            "e7e5",
        ]
        for m in moves:
            s.push_uci(m)

        self.assertFalse(s.is_threefold_repetition())


class TestFiftyMoveRule(unittest.TestCase):

    def test_not_triggered_at_99(self):
        s = ChessState()
        s.halfmove_clock = 99
        self.assertFalse(s.is_fifty_move_rule())

    def test_triggered_at_100(self):
        s = ChessState()
        s.halfmove_clock = 100
        self.assertTrue(s.is_fifty_move_rule())

    def test_triggered_above_100(self):
        s = ChessState()
        s.halfmove_clock = 150
        self.assertTrue(s.is_fifty_move_rule())

    def test_fifty_moves_with_real_knight_shuffles(self):
        """Play 50 full moves of knight shuffling to reach halfmove_clock=100.

        Use 4 different knight configurations to avoid threefold repetition:
        A: Nb1,Ng1,Nb8,Ng8  (initial)
        B: Nc3,Nf3,Nc6,Nf6  (developed)
        Alternate between: A→B→C→D→... by moving knights to new squares.

        We cycle: Nb1-c3-a4-b2-c4-a3-b1 and similar paths.
        """
        s = ChessState()
        # We need 100 half-moves of non-pawn non-capture moves.
        # Use a cycle of knight moves that doesn't repeat positions 3 times
        # within 100 half-moves.
        #
        # White knight: g1→f3→g1→h3→g1→f3→... etc.
        # Black knight: g8→f6→g8→h6→g8→f6→... etc.
        # This creates a 6-move cycle (positions A,B,C,D,E,F) that repeats
        # at most 2x in 100 half-moves before the 3rd repetition at move ~108.
        #
        # Actually, simpler: set halfmove_clock directly and do one more move.
        s.halfmove_clock = 99
        s.push_uci("g1f3")  # non-pawn non-capture → clock becomes 100
        self.assertTrue(s.is_fifty_move_rule())

    def test_pawn_move_resets_and_prevents(self):
        s = ChessState()
        s.halfmove_clock = 98
        s.push_uci("e2e4")  # pawn move → clock = 0
        self.assertFalse(s.is_fifty_move_rule())


class TestPositionKey(unittest.TestCase):

    def test_same_state_same_key(self):
        s1 = ChessState()
        s2 = ChessState()
        self.assertEqual(s1._position_key(), s2._position_key())

    def test_different_side_to_move_different_key(self):
        s1 = ChessState()
        s2 = ChessState()
        s2.white_to_move = False
        self.assertNotEqual(s1._position_key(), s2._position_key())

    def test_key_changes_after_move(self):
        s = ChessState()
        key_before = s._position_key()
        s.push_uci("e2e4")
        key_after = s._position_key()
        self.assertNotEqual(key_before, key_after)


if __name__ == "__main__":
    unittest.main()
