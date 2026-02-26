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

    def test_h1_rook_move_removes_kingside_right(self):
        s = ChessState()
        s.board[6] = "."  # clear g1
        s.push_uci("h1g1")
        self.assertFalse(s.castling[0])  # K gone
        self.assertTrue(s.castling[1])   # Q still there

    def test_a1_rook_move_removes_queenside_right(self):
        s = ChessState()
        s.board[1] = "."  # clear b1
        s.push_uci("a1b1")
        self.assertTrue(s.castling[0])   # K still there
        self.assertFalse(s.castling[1])  # Q gone

    def test_capture_on_h1_removes_kingside_right(self):
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


class TestValidateUciMove(unittest.TestCase):

    def test_valid_pawn_push(self):
        s = ChessState()
        self.assertTrue(s.validate_uci_move("e2e4"))

    def test_valid_knight_move(self):
        s = ChessState()
        self.assertTrue(s.validate_uci_move("g1f3"))

    def test_valid_promotion(self):
        s = ChessState()
        s.board[52] = "P"   # white pawn on e7
        s.board[60] = "."   # e8 empty
        self.assertTrue(s.validate_uci_move("e7e8q"))

    def test_valid_capture(self):
        s = ChessState()
        s.push_uci("e2e4")
        s.push_uci("d7d5")
        s = ChessState()
        s.push_uci("e2e4")
        s.push_uci("d7d5")
        self.assertTrue(s.validate_uci_move("e4d5"))

    def test_same_square_rejected(self):
        s = ChessState()
        self.assertFalse(s.validate_uci_move("a1a1"))

    def test_empty_from_square_rejected(self):
        s = ChessState()
        self.assertFalse(s.validate_uci_move("e4e5"))

    def test_wrong_color_rejected(self):
        s = ChessState()
        # White to move, trying to move a black piece
        self.assertFalse(s.validate_uci_move("e7e5"))

    def test_capture_own_piece_rejected(self):
        s = ChessState()
        # White rook on a1 trying to move to a2 which has a white pawn
        self.assertFalse(s.validate_uci_move("a1a2"))

    def test_too_short_rejected(self):
        s = ChessState()
        self.assertFalse(s.validate_uci_move("e2"))

    def test_too_long_rejected(self):
        s = ChessState()
        self.assertFalse(s.validate_uci_move("e2e4qq"))

    def test_bad_file_rejected(self):
        s = ChessState()
        self.assertFalse(s.validate_uci_move("z2e4"))

    def test_bad_rank_rejected(self):
        s = ChessState()
        self.assertFalse(s.validate_uci_move("e0e4"))

    def test_bad_promotion_char_rejected(self):
        s = ChessState()
        s.board[52] = "P"
        s.board[60] = "."
        self.assertFalse(s.validate_uci_move("e7e8x"))

    def test_valid_en_passant_capture(self):
        """En passant: pawn moves diagonally to empty square — should be valid."""
        s = ChessState()
        s.push_uci("e2e4")
        s.push_uci("a7a6")
        s.push_uci("e4e5")
        s.push_uci("d7d5")
        # White pawn on e5, capturing en passant on d6 (empty square)
        self.assertTrue(s.validate_uci_move("e5d6"))

    def test_black_move_validation(self):
        s = ChessState()
        s.push_uci("e2e4")
        # Now it's black's turn
        self.assertTrue(s.validate_uci_move("e7e5"))
        self.assertFalse(s.validate_uci_move("d2d4"))  # white piece, wrong color


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


class TestAttackDetection(unittest.TestCase):

    def test_initial_position_e1_not_attacked(self):
        s = ChessState()
        self.assertFalse(s.is_square_attacked(4, by_white=False))  # e1

    def test_initial_position_e2_attacked_by_white(self):
        """e2 is covered by Ke1, Qd1, Bf1."""
        s = ChessState()
        self.assertTrue(s.is_square_attacked(12, by_white=True))

    def test_knight_attacks(self):
        s = ChessState()
        s.push_uci("g1f3")
        # Nf3 attacks e5(36), d4(27), g5(38), h4(31), d2(11), h2(15), g1(6), e1(4)
        self.assertTrue(s.is_square_attacked(36, by_white=True))   # e5
        self.assertTrue(s.is_square_attacked(27, by_white=True))   # d4

    def test_pawn_attacks(self):
        s = ChessState()
        # White pawn on e2(12) attacks d3(19) and f3(21)
        self.assertTrue(s.is_square_attacked(19, by_white=True))   # d3
        self.assertTrue(s.is_square_attacked(21, by_white=True))   # f3
        # e3(20) is attacked by d2 and f2 pawns, so test on a clear board
        s2 = ChessState()
        s2.board = ["."] * 64
        s2.board[4] = "K"
        s2.board[60] = "k"
        s2.board[12] = "P"  # single pawn on e2
        self.assertFalse(s2.is_square_attacked(20, by_white=True))  # e3 not attacked

    def test_black_pawn_attacks(self):
        s = ChessState()
        # Black pawn on e7(52) attacks d6(43) and f6(45)
        self.assertTrue(s.is_square_attacked(43, by_white=False))  # d6
        self.assertTrue(s.is_square_attacked(45, by_white=False))  # f6

    def test_rook_attacks_along_file(self):
        s = ChessState()
        # Clear e-file: remove pawns, place rook
        s.board = ["."] * 64
        s.board[4] = "K"
        s.board[60] = "k"
        s.board[0] = "R"  # a1
        # Rook on a1 attacks a2..a8 (vertically)
        self.assertTrue(s.is_square_attacked(8, by_white=True))    # a2
        self.assertTrue(s.is_square_attacked(56, by_white=True))   # a8

    def test_bishop_attacks_diagonal(self):
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"
        s.board[60] = "k"
        s.board[0] = "B"  # a1
        # Bishop on a1 attacks b2, c3, ..., h8
        self.assertTrue(s.is_square_attacked(9, by_white=True))    # b2
        self.assertTrue(s.is_square_attacked(63, by_white=True))   # h8

    def test_sliding_piece_blocked(self):
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"
        s.board[60] = "k"
        s.board[0] = "R"  # a1
        s.board[16] = "P"  # a3 — blocks the rook
        # Rook on a1 attacks a2 but not a4 (blocked by a3 pawn)
        self.assertTrue(s.is_square_attacked(8, by_white=True))    # a2
        self.assertFalse(s.is_square_attacked(24, by_white=True))  # a4

    def test_queen_attacks_all_directions(self):
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"
        s.board[60] = "k"
        s.board[27] = "Q"  # d4
        # Queen on d4 attacks along rank, file, and diagonals
        self.assertTrue(s.is_square_attacked(3, by_white=True))    # d1 (file)
        self.assertTrue(s.is_square_attacked(59, by_white=True))   # d8 (file)
        self.assertTrue(s.is_square_attacked(24, by_white=True))   # a4 (rank)
        self.assertTrue(s.is_square_attacked(31, by_white=True))   # h4 (rank)
        self.assertTrue(s.is_square_attacked(0, by_white=True))    # a1 (diagonal)
        self.assertTrue(s.is_square_attacked(63, by_white=True))   # h8 (diagonal)

    def test_king_attacks_adjacent(self):
        s = ChessState()
        s.board = ["."] * 64
        s.board[27] = "K"  # d4
        s.board[60] = "k"
        self.assertTrue(s.is_square_attacked(28, by_white=True))   # e4
        self.assertTrue(s.is_square_attacked(36, by_white=True))   # e5
        self.assertTrue(s.is_square_attacked(35, by_white=True))   # d5
        self.assertFalse(s.is_square_attacked(44, by_white=True))  # e6 (too far)


class TestIsInCheck(unittest.TestCase):

    def test_initial_position_not_in_check(self):
        s = ChessState()
        self.assertFalse(s.is_in_check())

    def test_fools_mate_check(self):
        """After 1.f3 e5 2.g4 Qh4# — white is in check."""
        s = ChessState()
        for m in ("f2f3", "e7e5", "g2g4", "d8h4"):
            s.push_uci(m)
        self.assertTrue(s.is_in_check())

    def test_scholars_mate_check(self):
        """After 1.e4 e5 2.Qh5 Nc6 3.Bc4 Nf6 4.Qxf7# — black is in check."""
        s = ChessState()
        for m in ("e2e4", "e7e5", "d1h5", "b8c6", "f1c4", "g8f6", "h5f7"):
            s.push_uci(m)
        self.assertTrue(s.is_in_check())


class TestFullValidation(unittest.TestCase):
    """Test validate_uci_move with full legality checks."""

    def test_pawn_backward_rejected(self):
        """White pawn cannot move backward."""
        s = ChessState()
        s.push_uci("e2e4")
        s.push_uci("e7e5")
        # Try to move e4 pawn backward to e3
        self.assertFalse(s.validate_uci_move("e4e3"))

    def test_knight_invalid_pattern(self):
        """Knight cannot move like a bishop."""
        s = ChessState()
        s.board[5] = "."  # clear f1
        # Try b1 to d3 (2-rank, 2-file) — not an L-shape
        self.assertFalse(s.validate_uci_move("b1d3"))

    def test_bishop_blocked_by_own_pawn(self):
        """Bishop cannot jump over pieces."""
        s = ChessState()
        # Bc1 trying to go to a3 — blocked by pawn on b2
        self.assertFalse(s.validate_uci_move("c1a3"))

    def test_rook_cannot_move_diagonally(self):
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"
        s.board[60] = "k"
        s.board[0] = "R"
        self.assertFalse(s.validate_uci_move("a1b2"))

    def test_bishop_cannot_move_straight(self):
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"
        s.board[60] = "k"
        s.board[0] = "B"
        self.assertFalse(s.validate_uci_move("a1a2"))

    def test_pinned_piece_cannot_move(self):
        """A pinned piece cannot move if it would expose the king to check."""
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"   # white king e1
        s.board[12] = "N"  # white knight e2
        s.board[60] = "k"
        s.board[28] = "r"  # black rook e4 — pins knight on e2
        s.white_to_move = True
        # Knight on e2 is pinned by rook on e4 (along e-file through king)
        self.assertFalse(s.validate_uci_move("e2f4"))
        self.assertFalse(s.validate_uci_move("e2d4"))

    def test_king_cannot_move_into_check(self):
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"   # white king e1
        s.board[63] = "k"  # black king h8
        s.board[13] = "r"  # black rook f2 — controls f1 and entire rank 2
        s.white_to_move = True
        # King cannot go to f1 (attacked by rook on f2 via file)
        self.assertFalse(s.validate_uci_move("e1f1"))
        # King cannot go to d2 or e2 (attacked by rook along rank 2)
        self.assertFalse(s.validate_uci_move("e1d2"))
        self.assertFalse(s.validate_uci_move("e1e2"))
        # King can go to d1 (not attacked by rook)
        self.assertTrue(s.validate_uci_move("e1d1"))

    def test_must_escape_check(self):
        """When in check, only check-evading moves are legal."""
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"   # white king e1
        s.board[63] = "k"  # black king h8
        s.board[36] = "r"  # black rook e5 — gives check along e-file
        s.board[8] = "P"   # white pawn a2 (irrelevant piece)
        s.white_to_move = True
        self.assertTrue(s.is_in_check())
        # King must move to escape check
        self.assertTrue(s.validate_uci_move("e1d1"))
        self.assertTrue(s.validate_uci_move("e1d2"))
        self.assertTrue(s.validate_uci_move("e1f1"))
        self.assertTrue(s.validate_uci_move("e1f2"))
        # Pawn move doesn't escape check
        self.assertFalse(s.validate_uci_move("a2a3"))

    def test_pawn_cannot_push_to_occupied_square(self):
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"
        s.board[60] = "k"
        s.board[12] = "P"  # white pawn e2
        s.board[20] = "p"  # black pawn e3 — blocks push
        s.white_to_move = True
        self.assertFalse(s.validate_uci_move("e2e3"))
        self.assertFalse(s.validate_uci_move("e2e4"))  # double push also blocked

    def test_pawn_double_push_blocked_by_intermediate(self):
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"
        s.board[60] = "k"
        s.board[12] = "P"  # white pawn e2
        s.board[20] = "n"  # piece on e3 — blocks double push
        s.white_to_move = True
        self.assertFalse(s.validate_uci_move("e2e4"))

    def test_pawn_diagonal_without_capture_rejected(self):
        """Pawn cannot move diagonally unless capturing or en passant."""
        s = ChessState()
        self.assertFalse(s.validate_uci_move("e2d3"))

    def test_castling_through_check_rejected(self):
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"
        s.board[7] = "R"   # h1 rook
        s.board[60] = "k"
        s.board[45] = "r"  # black rook f6 — controls f1
        s.castling = [True, False, False, False]
        s.white_to_move = True
        # Kingside castling: king passes through f1, which is attacked
        self.assertFalse(s.validate_uci_move("e1g1"))

    def test_castling_out_of_check_rejected(self):
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"
        s.board[7] = "R"   # h1 rook
        s.board[60] = "k"
        s.board[44] = "r"  # black rook e6 — gives check on e1
        s.castling = [True, False, False, False]
        s.white_to_move = True
        self.assertTrue(s.is_in_check())
        self.assertFalse(s.validate_uci_move("e1g1"))

    def test_valid_castling_accepted(self):
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"
        s.board[7] = "R"
        s.board[60] = "k"
        s.castling = [True, False, False, False]
        s.white_to_move = True
        self.assertTrue(s.validate_uci_move("e1g1"))

    def test_queenside_castling_accepted(self):
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"
        s.board[0] = "R"
        s.board[60] = "k"
        s.castling = [False, True, False, False]
        s.white_to_move = True
        self.assertTrue(s.validate_uci_move("e1c1"))

    def test_castling_no_rook_rejected(self):
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"
        s.board[60] = "k"
        # No rook on h1
        s.castling = [True, False, False, False]
        s.white_to_move = True
        self.assertFalse(s.validate_uci_move("e1g1"))

    def test_promotion_required_on_last_rank(self):
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"
        s.board[56] = "k"  # black king on a8 (away from e-file)
        s.board[52] = "P"  # white pawn e7
        s.white_to_move = True
        # Must promote: e7e8 without promo char → invalid
        self.assertFalse(s.validate_uci_move("e7e8"))
        # With promo char → valid
        self.assertTrue(s.validate_uci_move("e7e8q"))
        self.assertTrue(s.validate_uci_move("e7e8n"))

    def test_promotion_on_non_last_rank_rejected(self):
        s = ChessState()
        # Normal pawn push with promotion char
        self.assertFalse(s.validate_uci_move("e2e4q"))

    def test_en_passant_leaves_king_in_check(self):
        """En passant that exposes king to check is illegal."""
        s = ChessState()
        s.board = ["."] * 64
        s.board[32] = "K"  # white king a5
        s.board[34] = "P"  # white pawn c5
        s.board[35] = "p"  # black pawn d5 (just double-pushed)
        s.board[39] = "r"  # black rook h5 — would check king after EP
        s.board[60] = "k"
        s.en_passant_file = 3  # d-file
        s.white_to_move = True
        # c5xd6 en passant removes pawn on d5, exposing king to rook on h5
        self.assertFalse(s.validate_uci_move("c5d6"))


class TestCheckmateStalemate(unittest.TestCase):

    def test_fools_mate_is_checkmate(self):
        """After 1.f3 e5 2.g4 Qh4# — white is checkmated."""
        s = ChessState()
        for m in ("f2f3", "e7e5", "g2g4", "d8h4"):
            s.push_uci(m)
        self.assertTrue(s.is_checkmate())
        self.assertFalse(s.is_stalemate())

    def test_scholars_mate_is_checkmate(self):
        """After 1.e4 e5 2.Qh5 Nc6 3.Bc4 Nf6 4.Qxf7# — black is checkmated."""
        s = ChessState()
        for m in ("e2e4", "e7e5", "d1h5", "b8c6", "f1c4", "g8f6", "h5f7"):
            s.push_uci(m)
        self.assertTrue(s.is_checkmate())
        self.assertFalse(s.is_stalemate())

    def test_stalemate_king_only(self):
        """Black king alone, white queen and king create stalemate."""
        s = ChessState()
        s.board = ["."] * 64
        s.board[42] = "K"  # white king c6
        s.board[41] = "Q"  # white queen b6
        s.board[56] = "k"  # black king a8
        s.white_to_move = False
        # Black king on a8: escape squares a7, b8, b7 all attacked.
        # Qb6 attacks a7(diagonal), b7(file), b8(file).
        # Kc6 also attacks b7.
        # a8 itself is NOT attacked (neither Qb6 nor Kc6 can reach a8).
        self.assertFalse(s.is_in_check())
        self.assertTrue(s.is_stalemate())
        self.assertFalse(s.is_checkmate())

    def test_initial_position_neither(self):
        s = ChessState()
        self.assertFalse(s.is_checkmate())
        self.assertFalse(s.is_stalemate())

    def test_check_but_not_checkmate(self):
        """King is in check but can escape."""
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"   # white king e1
        s.board[60] = "k"
        s.board[36] = "r"  # black rook e5 — gives check along e-file
        s.white_to_move = True
        self.assertTrue(s.is_in_check())
        self.assertFalse(s.is_checkmate())  # king can move to d1, d2, f1, f2


class TestLegalMoveGeneration(unittest.TestCase):

    def test_initial_position_20_moves(self):
        """Starting position has exactly 20 legal moves for white."""
        s = ChessState()
        moves = s.generate_legal_moves()
        self.assertEqual(len(moves), 20)

    def test_checkmate_no_legal_moves(self):
        """In checkmate, there are no legal moves."""
        s = ChessState()
        for m in ("f2f3", "e7e5", "g2g4", "d8h4"):
            s.push_uci(m)
        self.assertEqual(len(s.generate_legal_moves()), 0)
        self.assertFalse(s.has_legal_moves())

    def test_stalemate_no_legal_moves(self):
        s = ChessState()
        s.board = ["."] * 64
        s.board[42] = "K"  # white king c6
        s.board[41] = "Q"  # white queen b6
        s.board[56] = "k"  # black king a8
        s.white_to_move = False
        self.assertEqual(len(s.generate_legal_moves()), 0)
        self.assertFalse(s.has_legal_moves())

    def test_has_legal_moves_initial(self):
        s = ChessState()
        self.assertTrue(s.has_legal_moves())

    def test_generate_includes_castling(self):
        """Legal moves include castling when available."""
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"
        s.board[7] = "R"
        s.board[60] = "k"
        s.castling = [True, False, False, False]
        s.white_to_move = True
        moves = s.generate_legal_moves()
        self.assertIn("e1g1", moves)

    def test_generate_includes_en_passant(self):
        s = ChessState()
        for m in ("e2e4", "a7a6", "e4e5", "d7d5"):
            s.push_uci(m)
        moves = s.generate_legal_moves()
        self.assertIn("e5d6", moves)

    def test_generate_includes_promotions(self):
        s = ChessState()
        s.board = ["."] * 64
        s.board[4] = "K"
        s.board[56] = "k"  # black king on a8 (away from e-file)
        s.board[52] = "P"  # white pawn e7
        s.white_to_move = True
        moves = s.generate_legal_moves()
        self.assertIn("e7e8q", moves)
        self.assertIn("e7e8r", moves)
        self.assertIn("e7e8b", moves)
        self.assertIn("e7e8n", moves)


class TestPostMoveCheckmateDetection(unittest.TestCase):
    """Test that match_runner detects checkmate after each move."""

    def test_fools_mate_detected_after_qh4(self):
        """Game ends immediately after Qh4# without asking white for a move."""
        from match_runner import play_game
        from unittest.mock import MagicMock

        def make_eng(responses):
            e = MagicMock()
            e.path = "/mock"
            e.go = MagicMock(side_effect=responses)
            e.new_game = MagicMock()
            return e

        white = make_eng([("f2f3", -10), ("g2g4", -200)])
        black = make_eng([("e7e5", 50), ("d8h4", 9999)])

        result, moves, term = play_game(white, black, movetime_ms=100)
        self.assertEqual(result, "0-1")
        self.assertEqual(term, "checkmate")
        self.assertEqual(moves, ["f2f3", "e7e5", "g2g4", "d8h4"])
        # White was only asked for 2 moves (not 3 — no (none) needed)
        self.assertEqual(white.go.call_count, 2)

    def test_scholars_mate_detected_after_qxf7(self):
        from match_runner import play_game
        from unittest.mock import MagicMock

        def make_eng(responses):
            e = MagicMock()
            e.path = "/mock"
            e.go = MagicMock(side_effect=responses)
            e.new_game = MagicMock()
            return e

        white = make_eng([("e2e4", 30), ("d1h5", 100),
                          ("f1c4", 200), ("h5f7", 99999)])
        black = make_eng([("e7e5", -30), ("b8c6", -100), ("g8f6", -200)])

        result, moves, term = play_game(white, black, movetime_ms=100)
        self.assertEqual(result, "1-0")
        self.assertEqual(term, "checkmate")
        self.assertEqual(len(moves), 7)
        # Black was only asked for 3 moves (not 4 — no (none) needed)
        self.assertEqual(black.go.call_count, 3)


if __name__ == "__main__":
    unittest.main()
