"""PGN game logging — writes each game as a standard PGN file."""

import logging
import os
from datetime import datetime, timezone

from chess_state import ChessState
from match_runner import GameResult

logger = logging.getLogger("pgn_logger")


# --- UCI to SAN conversion ---


def uci_to_san(state: ChessState, uci_move: str) -> str:
    """Convert a UCI move to Standard Algebraic Notation given the current board.

    The state is NOT modified — the caller must push the move separately.
    """
    from_sq = state.square_index(uci_move[:2])
    to_sq = state.square_index(uci_move[2:4])
    promotion = uci_move[4] if len(uci_move) == 5 else None

    piece = state.board[from_sq]
    piece_type = piece.upper()
    target = state.board[to_sq]
    is_capture = target != "."

    # En passant capture
    if piece_type == "P" and (to_sq % 8) != (from_sq % 8) and target == ".":
        is_capture = True

    # Castling
    if piece_type == "K" and abs(to_sq - from_sq) == 2:
        return "O-O" if to_sq > from_sq else "O-O-O"

    san = ""

    if piece_type == "P":
        if is_capture:
            san = chr(ord("a") + from_sq % 8) + "x"
        san += _sq_name(to_sq)
        if promotion:
            san += "=" + promotion.upper()
    else:
        san = piece_type
        san += _disambiguate(state, piece, from_sq, to_sq)
        if is_capture:
            san += "x"
        san += _sq_name(to_sq)

    return san


def _sq_name(sq: int) -> str:
    return chr(ord("a") + sq % 8) + str(sq // 8 + 1)


def _disambiguate(state: ChessState, piece: str, from_sq: int, to_sq: int) -> str:
    """Return disambiguation string (file, rank, or both) if needed."""
    ambiguous = []
    for sq in range(64):
        if sq == from_sq:
            continue
        if state.board[sq] != piece:
            continue
        # Can this piece also legally reach to_sq?
        target = state.board[to_sq]
        if target != ".":
            if state.white_to_move and target.isupper():
                continue
            if not state.white_to_move and target.islower():
                continue
        if not state.is_piece_move_pattern_valid(sq, to_sq):
            continue
        if state.would_leave_king_in_check(sq, to_sq):
            continue
        ambiguous.append(sq)

    if not ambiguous:
        return ""

    same_file = any(sq % 8 == from_sq % 8 for sq in ambiguous)
    same_rank = any(sq // 8 == from_sq // 8 for sq in ambiguous)

    if not same_file:
        return chr(ord("a") + from_sq % 8)
    if not same_rank:
        return str(from_sq // 8 + 1)
    return chr(ord("a") + from_sq % 8) + str(from_sq // 8 + 1)


def _add_check_suffix(san: str, state: ChessState) -> str:
    """Append + or # based on the position after the move was pushed."""
    if state.is_in_check():
        if not state.has_legal_moves():
            return san + "#"
        return san + "+"
    return san


def moves_to_san(uci_moves: list[str]) -> str:
    """Convert a full UCI move list to PGN move text with numbered moves."""
    state = ChessState()
    san_parts: list[str] = []

    for i, uci_move in enumerate(uci_moves):
        san = uci_to_san(state, uci_move)
        state.push_uci(uci_move)
        san = _add_check_suffix(san, state)

        if i % 2 == 0:
            san_parts.append(f"{i // 2 + 1}. {san}")
        else:
            san_parts.append(san)

    return " ".join(san_parts)


# --- PGN generation ---


def game_to_pgn(
    game: GameResult,
    match_number: int,
    stockfish_elo: int,
    engine_name: str,
    date: str,
) -> str:
    """Generate a complete PGN string for a single game."""
    if game.white == "engine":
        white_name = engine_name
        black_name = f"Stockfish {stockfish_elo}"
        white_elo = "?"
        black_elo = str(stockfish_elo)
    else:
        white_name = f"Stockfish {stockfish_elo}"
        black_name = engine_name
        white_elo = str(stockfish_elo)
        black_elo = "?"

    move_text = moves_to_san(game.moves)

    tags = [
        ("Event", f"ELO Evaluation vs Stockfish {stockfish_elo}"),
        ("Date", date),
        ("Round", f"{match_number}.{game.game_number}"),
        ("White", white_name),
        ("Black", black_name),
        ("Result", game.result),
        ("WhiteElo", white_elo),
        ("BlackElo", black_elo),
        ("Termination", game.termination),
    ]

    lines = [f'[{key} "{value}"]' for key, value in tags]
    lines.append("")
    lines.append(f"{move_text} {game.result}")
    lines.append("")

    return "\n".join(lines)


# --- File I/O ---


def create_log_dir(engine_path: str) -> str:
    """Create game_logs/{engine_name}_{timestamp}/ and return the path."""
    engine_name = os.path.splitext(os.path.basename(engine_path))[0]
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H%M%S")
    dir_name = f"{engine_name}_{timestamp}"

    base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "game_logs")
    log_dir = os.path.join(base_dir, dir_name)
    os.makedirs(log_dir, exist_ok=True)

    logger.info("Game logs: %s", log_dir)
    return log_dir


def write_game_pgn(
    log_dir: str,
    match_number: int,
    game: GameResult,
    stockfish_elo: int,
    engine_name: str,
    date: str,
) -> None:
    """Write a single game PGN to {log_dir}/{match_number}-{game_number}.pgn."""
    pgn = game_to_pgn(game, match_number, stockfish_elo, engine_name, date)
    filename = f"{match_number}-{game.game_number}.pgn"
    filepath = os.path.join(log_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(pgn)

    logger.debug("Wrote %s", filepath)
