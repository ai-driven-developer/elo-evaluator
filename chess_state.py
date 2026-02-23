"""Lightweight chess board state tracker for draw detection.

Tracks piece positions, castling rights, en passant, and halfmove clock
to detect threefold repetition and the 50-move rule — without any
third-party chess libraries.
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
        key = self._position_key()
        return self._position_history.get(key, 0) >= 3

    def is_fifty_move_rule(self) -> bool:
        return self.halfmove_clock >= 100

    # --- Applying moves ---

    @staticmethod
    def _square_index(uci_sq: str) -> int:
        """'e2' -> 12"""
        return (int(uci_sq[1]) - 1) * 8 + (ord(uci_sq[0]) - ord("a"))

    def push_uci(self, move: str) -> None:
        """Apply a UCI move (e.g. 'e2e4', 'e7e8q') and update all state."""
        from_sq = self._square_index(move[:2])
        to_sq = self._square_index(move[2:4])
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
