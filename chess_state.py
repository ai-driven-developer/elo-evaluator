"""Lightweight chess board state tracker with full move validation.

Tracks piece positions, castling rights, en passant, and halfmove clock
to detect threefold repetition, the 50-move rule, checkmate, and
stalemate — without any third-party chess libraries.
"""


class ChessState:
    """Incrementally updated board state from a sequence of UCI moves."""

    def __init__(self):
        self.board = self._initial_board()
        self.white_to_move = True
        # Castling rights: [K, Q, k, q]
        self.castling = [True, True, True, True]
        self.en_passant_file = -1  # file index 0-7, or -1 if none
        self.halfmove_clock = 0
        self._position_history: dict[tuple, int] = {}
        self._record_position()

    # --- Setup ---

    @staticmethod
    def _initial_board() -> list[str]:
        board = ["."] * 64
        for i, piece in enumerate("RNBQKBNR"):
            board[i] = piece
        for i in range(8, 16):
            board[i] = "P"
        for i in range(48, 56):
            board[i] = "p"
        for i, piece in enumerate("rnbqkbnr"):
            board[56 + i] = piece
        return board

    # --- Helpers ---

    @staticmethod
    def square_index(uci_sq: str) -> int:
        """'e2' -> 12"""
        return (int(uci_sq[1]) - 1) * 8 + (ord(uci_sq[0]) - ord("a"))

    @staticmethod
    def _to_uci(from_sq: int, to_sq: int) -> str:
        """Convert square indices to UCI move string."""
        return (
            chr(ord("a") + from_sq % 8)
            + str(from_sq // 8 + 1)
            + chr(ord("a") + to_sq % 8)
            + str(to_sq // 8 + 1)
        )

    # --- Position key & history ---

    def _position_key(self) -> tuple:
        return (
            tuple(self.board),
            self.white_to_move,
            tuple(self.castling),
            self.en_passant_file,
        )

    def _record_position(self) -> None:
        key = self._position_key()
        self._position_history[key] = self._position_history.get(key, 0) + 1

    def is_threefold_repetition(self) -> bool:
        """Return True if the current position has occurred 3+ times."""
        key = self._position_key()
        return self._position_history.get(key, 0) >= 3

    def is_fifty_move_rule(self) -> bool:
        """Return True if 50 moves passed without a capture or pawn move."""
        return self.halfmove_clock >= 100

    # --- Attack detection ---

    def _find_king(self, white: bool) -> int:
        """Find the square index of the king for the given side."""
        king = "K" if white else "k"
        for sq in range(64):
            if self.board[sq] == king:
                return sq
        raise ValueError(f"No {'white' if white else 'black'} king on the board")

    def is_square_attacked(self, sq: int, by_white: bool) -> bool:  # pylint: disable=too-many-return-statements
        """Check if the given square is attacked by any piece of the given color."""
        r, f = sq // 8, sq % 8

        # Knight attacks
        for dr, df in ((-2,-1),(-2,1),(-1,-2),(-1,2),(1,-2),(1,2),(2,-1),(2,1)):
            nr, nf = r + dr, f + df
            if 0 <= nr < 8 and 0 <= nf < 8:
                piece = self.board[nr * 8 + nf]
                if piece == ("N" if by_white else "n"):
                    return True

        # King attacks
        for dr in (-1, 0, 1):
            for df in (-1, 0, 1):
                if dr == 0 and df == 0:
                    continue
                nr, nf = r + dr, f + df
                if 0 <= nr < 8 and 0 <= nf < 8:
                    if self.board[nr * 8 + nf] == ("K" if by_white else "k"):
                        return True

        # Pawn attacks
        if by_white:
            pr = r - 1
            if pr >= 0:
                for pf in (f - 1, f + 1):
                    if 0 <= pf < 8 and self.board[pr * 8 + pf] == "P":
                        return True
        else:
            pr = r + 1
            if pr < 8:
                for pf in (f - 1, f + 1):
                    if 0 <= pf < 8 and self.board[pr * 8 + pf] == "p":
                        return True

        # Sliding pieces: rook/queen along ranks and files
        rook = "R" if by_white else "r"
        queen = "Q" if by_white else "q"
        for dr, df in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nr, nf = r + dr, f + df
            while 0 <= nr < 8 and 0 <= nf < 8:
                piece = self.board[nr * 8 + nf]
                if piece != ".":
                    if piece in (rook, queen):
                        return True
                    break
                nr += dr
                nf += df

        # Sliding pieces: bishop/queen along diagonals
        bishop = "B" if by_white else "b"
        for dr, df in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
            nr, nf = r + dr, f + df
            while 0 <= nr < 8 and 0 <= nf < 8:
                piece = self.board[nr * 8 + nf]
                if piece != ".":
                    if piece in (bishop, queen):
                        return True
                    break
                nr += dr
                nf += df

        return False

    def is_in_check(self) -> bool:
        """Return True if the side to move is in check."""
        king_sq = self._find_king(self.white_to_move)
        return self.is_square_attacked(king_sq, not self.white_to_move)

    # --- Piece movement validation ---

    def _is_path_clear(self, from_sq: int, to_sq: int) -> bool:
        """Check that no pieces block a straight or diagonal path (exclusive)."""
        fr, ff = from_sq // 8, from_sq % 8
        tr, tf = to_sq // 8, to_sq % 8
        dr = tr - fr
        df = tf - ff
        step_r = (1 if dr > 0 else -1) if dr != 0 else 0
        step_f = (1 if df > 0 else -1) if df != 0 else 0
        step = step_r * 8 + step_f
        sq = from_sq + step
        while sq != to_sq:
            if self.board[sq] != ".":
                return False
            sq += step
        return True

    def is_piece_move_pattern_valid(self, from_sq: int, to_sq: int) -> bool:  # pylint: disable=too-many-return-statements
        """Check if the move follows the piece's movement pattern.

        Validates piece-specific movement, sliding piece obstruction,
        pawn direction/capture/double push/en passant, and castling rules.
        Does NOT check pins or whether the move leaves the king in check.
        """
        piece = self.board[from_sq]
        piece_type = piece.upper()
        target = self.board[to_sq]
        is_capture = target != "."

        fr, ff = from_sq // 8, from_sq % 8
        tr, tf = to_sq // 8, to_sq % 8
        dr = tr - fr
        df = tf - ff

        if piece_type == "P":
            return self._is_pawn_move_valid(
                from_sq, to_sq, piece, dr, df, is_capture,
            )

        if piece_type == "N":
            return (abs(dr), abs(df)) in ((1, 2), (2, 1))

        if piece_type == "B":
            if abs(dr) != abs(df) or dr == 0:
                return False
            return self._is_path_clear(from_sq, to_sq)

        if piece_type == "R":
            if dr != 0 and df != 0:
                return False
            return self._is_path_clear(from_sq, to_sq)

        if piece_type == "Q":
            if dr != 0 and df != 0 and abs(dr) != abs(df):
                return False
            return self._is_path_clear(from_sq, to_sq)

        if piece_type == "K":
            if abs(dr) <= 1 and abs(df) <= 1:
                return True
            if dr == 0 and abs(df) == 2:
                return self._is_castling_valid(from_sq, to_sq)
            return False

        return False

    def _is_pawn_move_valid(self, from_sq: int, to_sq: int, piece: str,  # pylint: disable=too-many-return-statements
                            dr: int, df: int, is_capture: bool) -> bool:
        """Validate pawn move specifics."""
        is_white = piece == "P"
        direction = 1 if is_white else -1
        start_rank = 1 if is_white else 6

        fr = from_sq // 8

        # Forward push
        if df == 0:
            if is_capture:
                return False
            if dr == direction:
                return True
            if dr == 2 * direction and fr == start_rank:
                mid = from_sq + direction * 8
                return self.board[mid] == "."
            return False

        # Diagonal move (capture or en passant)
        if abs(df) == 1 and dr == direction:
            if is_capture:
                return True
            # En passant
            if self.en_passant_file == to_sq % 8:
                ep_rank = 5 if is_white else 2
                if to_sq // 8 == ep_rank:
                    return True
            return False

        return False

    def _is_castling_valid(self, from_sq: int, to_sq: int) -> bool:  # pylint: disable=too-many-return-statements
        """Check castling legality: rights, path clear, not through check."""
        is_white = self.white_to_move
        expected_from = 4 if is_white else 60
        if from_sq != expected_from:
            return False

        kingside = to_sq > from_sq

        if is_white:
            if kingside and not self.castling[0]:
                return False
            if not kingside and not self.castling[1]:
                return False
        else:
            if kingside and not self.castling[2]:
                return False
            if not kingside and not self.castling[3]:
                return False

        # Rook must be present
        rook_sq = from_sq + 3 if kingside else from_sq - 4
        expected_rook = "R" if is_white else "r"
        if self.board[rook_sq] != expected_rook:
            return False

        # Path must be clear
        if kingside:
            for sq in (from_sq + 1, from_sq + 2):
                if self.board[sq] != ".":
                    return False
        else:
            for sq in (from_sq - 1, from_sq - 2, from_sq - 3):
                if self.board[sq] != ".":
                    return False

        # King must not be in check, pass through check, or end in check
        enemy = not is_white
        if self.is_square_attacked(from_sq, enemy):
            return False
        if kingside:
            for sq in (from_sq + 1, from_sq + 2):
                if self.is_square_attacked(sq, enemy):
                    return False
        else:
            for sq in (from_sq - 1, from_sq - 2):
                if self.is_square_attacked(sq, enemy):
                    return False

        return True

    # --- Full move legality ---

    def would_leave_king_in_check(self, from_sq: int, to_sq: int,
                                    promotion: str | None = None) -> bool:
        """Simulate a move and check if it leaves own king in check."""
        # Save state
        board_backup = self.board[:]
        piece = self.board[from_sq]

        # En passant capture
        is_pawn = piece in ("P", "p")
        if is_pawn and (to_sq % 8) != (from_sq % 8) and self.board[to_sq] == ".":
            if self.white_to_move:
                self.board[to_sq - 8] = "."
            else:
                self.board[to_sq + 8] = "."

        # Move the piece
        self.board[to_sq] = piece
        self.board[from_sq] = "."

        # Promotion
        if promotion:
            self.board[to_sq] = (
                promotion.upper() if self.white_to_move else promotion.lower()
            )

        # Castling rook
        if piece in ("K", "k") and abs(to_sq - from_sq) == 2:
            if to_sq > from_sq:
                rook_from, rook_to = from_sq + 3, from_sq + 1
            else:
                rook_from, rook_to = from_sq - 4, from_sq - 1
            self.board[rook_to] = self.board[rook_from]
            self.board[rook_from] = "."

        # Check if own king is in check
        king_sq = self._find_king(self.white_to_move)
        in_check = self.is_square_attacked(king_sq, not self.white_to_move)

        # Restore state
        self.board = board_backup
        return in_check

    # --- Move validation ---

    def validate_uci_move(self, move: str) -> bool:  # pylint: disable=too-many-return-statements
        """Check that a UCI move is fully legal in the current position.

        Validates format, piece movement patterns, sliding piece obstruction,
        castling rules, en passant, promotion, pins, and check evasion.
        """
        if len(move) not in (4, 5):
            return False
        if move[0] not in "abcdefgh" or move[1] not in "12345678":
            return False
        if move[2] not in "abcdefgh" or move[3] not in "12345678":
            return False
        if len(move) == 5 and move[4] not in "nbrq":
            return False

        from_sq = self.square_index(move[:2])
        to_sq = self.square_index(move[2:4])
        promotion = move[4] if len(move) == 5 else None

        if from_sq == to_sq:
            return False

        piece = self.board[from_sq]
        if piece == ".":
            return False

        # Piece must belong to the side to move.
        if self.white_to_move and piece.islower():
            return False
        if not self.white_to_move and piece.isupper():
            return False

        # Cannot capture own piece.
        target = self.board[to_sq]
        if target != ".":
            if self.white_to_move and target.isupper():
                return False
            if not self.white_to_move and target.islower():
                return False

        # Promotion validation
        is_pawn = piece in ("P", "p")
        to_rank = to_sq // 8
        promo_rank = 7 if self.white_to_move else 0
        if is_pawn and to_rank == promo_rank and promotion is None:
            return False
        if is_pawn and to_rank != promo_rank and promotion is not None:
            return False
        if not is_pawn and promotion is not None:
            return False

        # Piece movement pattern
        if not self.is_piece_move_pattern_valid(from_sq, to_sq):
            return False

        # Must not leave own king in check
        if self.would_leave_king_in_check(from_sq, to_sq, promotion):
            return False

        return True

    # --- Legal move generation ---

    def has_legal_moves(self) -> bool:
        """Return True if the side to move has at least one legal move."""
        for from_sq in range(64):
            piece = self.board[from_sq]
            if piece == ".":
                continue
            if self.white_to_move and piece.islower():
                continue
            if not self.white_to_move and piece.isupper():
                continue

            for to_sq in self._candidate_targets(from_sq, piece):
                target = self.board[to_sq]
                if target != ".":
                    if self.white_to_move and target.isupper():
                        continue
                    if not self.white_to_move and target.islower():
                        continue

                if not self.is_piece_move_pattern_valid(from_sq, to_sq):
                    continue

                is_pawn = piece in ("P", "p")
                to_rank = to_sq // 8
                promo_rank = 7 if self.white_to_move else 0
                promo = "q" if is_pawn and to_rank == promo_rank else None

                if not self.would_leave_king_in_check(from_sq, to_sq, promo):
                    return True

        return False

    def generate_legal_moves(self) -> list[str]:
        """Generate all legal moves in the current position as UCI strings."""
        moves = []
        for from_sq in range(64):
            piece = self.board[from_sq]
            if piece == ".":
                continue
            if self.white_to_move and piece.islower():
                continue
            if not self.white_to_move and piece.isupper():
                continue

            for to_sq in self._candidate_targets(from_sq, piece):
                target = self.board[to_sq]
                if target != ".":
                    if self.white_to_move and target.isupper():
                        continue
                    if not self.white_to_move and target.islower():
                        continue

                if not self.is_piece_move_pattern_valid(from_sq, to_sq):
                    continue

                is_pawn = piece in ("P", "p")
                to_rank = to_sq // 8
                promo_rank = 7 if self.white_to_move else 0

                if is_pawn and to_rank == promo_rank:
                    for promo in "nbrq":
                        if not self.would_leave_king_in_check(
                            from_sq, to_sq, promo,
                        ):
                            moves.append(self._to_uci(from_sq, to_sq) + promo)
                else:
                    if not self.would_leave_king_in_check(from_sq, to_sq):
                        moves.append(self._to_uci(from_sq, to_sq))

        return moves

    def _candidate_targets(self, sq: int, piece: str) -> list[int]:
        """Generate candidate target squares for a piece (optimization)."""
        piece_type = piece.upper()
        r, f = sq // 8, sq % 8
        targets = []

        if piece_type == "N":
            for dr, df in ((-2,-1),(-2,1),(-1,-2),(-1,2),
                           (1,-2),(1,2),(2,-1),(2,1)):
                nr, nf = r + dr, f + df
                if 0 <= nr < 8 and 0 <= nf < 8:
                    targets.append(nr * 8 + nf)

        elif piece_type == "K":
            for dr in (-1, 0, 1):
                for df in (-1, 0, 1):
                    if dr == 0 and df == 0:
                        continue
                    nr, nf = r + dr, f + df
                    if 0 <= nr < 8 and 0 <= nf < 8:
                        targets.append(nr * 8 + nf)
            # Castling
            if self.white_to_move and sq == 4:
                targets.extend([2, 6])
            elif not self.white_to_move and sq == 60:
                targets.extend([58, 62])

        elif piece_type == "P":
            direction = 1 if piece == "P" else -1
            start_rank = 1 if piece == "P" else 6
            nr = r + direction
            if 0 <= nr < 8:
                targets.append(nr * 8 + f)
                if r == start_rank:
                    targets.append((r + 2 * direction) * 8 + f)
                for df in (-1, 1):
                    nf = f + df
                    if 0 <= nf < 8:
                        targets.append(nr * 8 + nf)

        else:  # R, B, Q
            directions = []
            if piece_type in ("R", "Q"):
                directions.extend(((1, 0), (-1, 0), (0, 1), (0, -1)))
            if piece_type in ("B", "Q"):
                directions.extend(((1, 1), (1, -1), (-1, 1), (-1, -1)))
            for dr, df in directions:
                nr, nf = r + dr, f + df
                while 0 <= nr < 8 and 0 <= nf < 8:
                    targets.append(nr * 8 + nf)
                    if self.board[nr * 8 + nf] != ".":
                        break
                    nr += dr
                    nf += df

        return targets

    # --- Checkmate / Stalemate ---

    def is_checkmate(self) -> bool:
        """Return True if the side to move is in checkmate."""
        return self.is_in_check() and not self.has_legal_moves()

    def is_stalemate(self) -> bool:
        """Return True if the side to move is in stalemate."""
        return not self.is_in_check() and not self.has_legal_moves()

    # --- Applying moves ---

    def push_uci(self, move: str) -> None:
        """Apply a UCI move (e.g. 'e2e4', 'e7e8q') and update all state."""
        from_sq = self.square_index(move[:2])
        to_sq = self.square_index(move[2:4])
        promotion = move[4] if len(move) == 5 else None

        piece = self.board[from_sq]
        captured = self.board[to_sq]

        is_pawn = piece in ("P", "p")
        is_capture = captured != "."

        # En passant capture
        if is_pawn and (to_sq % 8) != (from_sq % 8) and captured == ".":
            is_capture = True
            if self.white_to_move:
                self.board[to_sq - 8] = "."
            else:
                self.board[to_sq + 8] = "."

        # Move the piece
        self.board[to_sq] = piece
        self.board[from_sq] = "."

        # Promotion
        if promotion:
            self.board[to_sq] = (
                promotion.upper() if self.white_to_move else promotion.lower()
            )

        # Castling — move the rook
        if piece in ("K", "k") and abs(to_sq - from_sq) == 2:
            if to_sq > from_sq:  # kingside
                rook_from = from_sq + 3
                rook_to = from_sq + 1
            else:  # queenside
                rook_from = from_sq - 4
                rook_to = from_sq - 1
            self.board[rook_to] = self.board[rook_from]
            self.board[rook_from] = "."

        # Update castling rights — king moves
        if piece == "K":
            self.castling[0] = False
            self.castling[1] = False
        elif piece == "k":
            self.castling[2] = False
            self.castling[3] = False

        # Rook leaves or is captured on a corner square
        for sq in (from_sq, to_sq):
            if sq == 7:    # h1
                self.castling[0] = False
            elif sq == 0:  # a1
                self.castling[1] = False
            elif sq == 63: # h8
                self.castling[2] = False
            elif sq == 56: # a8
                self.castling[3] = False

        # En passant file
        self.en_passant_file = -1
        if is_pawn and abs(to_sq - from_sq) == 16:
            self.en_passant_file = from_sq % 8

        # Halfmove clock
        if is_pawn or is_capture:
            self.halfmove_clock = 0
        else:
            self.halfmove_clock += 1

        # Switch side
        self.white_to_move = not self.white_to_move

        # Record position for repetition detection
        self._record_position()
