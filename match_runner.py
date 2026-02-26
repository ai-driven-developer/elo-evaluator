"""Run a match between a test engine and Stockfish via UCI."""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from chess_state import ChessState
from openings import get_random_opening
from uci_engine import UCIEngine, MATE_SCORE

logger = logging.getLogger("match_runner")


@dataclass
class GameResult:
    """Result of a single game between two engines."""

    game_number: int
    white: str  # "engine" or "stockfish"
    result: str  # "1-0", "0-1", "1/2-1/2"
    engine_score: float  # points for the test engine: 1.0 / 0.5 / 0.0
    moves: list[str]
    termination: str  # "checkmate", "stalemate", "max_moves"


@dataclass
class MatchResult:
    """Aggregated result of a multi-game match."""

    total_score: float
    num_games: int
    games: list[GameResult] = field(default_factory=list)


def play_game(  # pylint: disable=too-many-return-statements
    white: UCIEngine,
    black: UCIEngine,
    movetime_ms: int,
    opening_moves: list[str] | None = None,
) -> tuple[str, list[str], str]:
    """Play a single game between two engines.

    The game ends on checkmate, stalemate, threefold repetition,
    or the 50-move rule.

    Args:
        white: Engine playing white.
        black: Engine playing black.
        movetime_ms: Time per move in milliseconds.
        opening_moves: Optional list of UCI moves to pre-play as an opening.

    Returns:
        (result, moves, termination) where result is "1-0", "0-1", or "1/2-1/2".
    """
    white.new_game()
    black.new_game()

    state = ChessState()
    moves: list[str] = []
    engines = [white, black]

    if opening_moves:
        for move in opening_moves:
            moves.append(move)
            state.push_uci(move)

    while True:
        side = len(moves) % 2  # 0=white, 1=black
        engine = engines[side]

        bestmove, score = engine.go(list(moves), movetime_ms)

        if bestmove in ("(none)", "0000"):
            # Engine claims no legal moves — use independent check detection,
            # falling back to engine score when board detection is ambiguous.
            if state.is_in_check():
                if side == 0:
                    return "0-1", moves, "checkmate"
                return "1-0", moves, "checkmate"
            if score is not None and score <= -MATE_SCORE // 2:
                if side == 0:
                    return "0-1", moves, "checkmate"
                return "1-0", moves, "checkmate"
            return "1/2-1/2", moves, "stalemate"

        if not state.validate_uci_move(bestmove):
            logger.warning("illegal move from %s: %s", engine.path, bestmove)
            # Independently check if the position is checkmate or stalemate.
            if not state.has_legal_moves():
                if state.is_in_check():
                    if side == 0:
                        return "0-1", moves, "checkmate"
                    return "1-0", moves, "checkmate"
                return "1/2-1/2", moves, "stalemate"
            # Position has legal moves but engine sent an illegal one — forfeit.
            if side == 0:
                return "0-1", moves, "illegal_move"
            return "1-0", moves, "illegal_move"

        moves.append(bestmove)
        state.push_uci(bestmove)
        logger.debug("ply %d: %s", len(moves), bestmove)

        # Independent checkmate / stalemate detection after each move.
        if not state.has_legal_moves():
            if state.is_in_check():
                if side == 0:
                    return "1-0", moves, "checkmate"
                return "0-1", moves, "checkmate"
            return "1/2-1/2", moves, "stalemate"

        if state.is_threefold_repetition():
            return "1/2-1/2", moves, "threefold_repetition"

        if state.is_fifty_move_rule():
            return "1/2-1/2", moves, "fifty_move_rule"


def run_match(
    engine_path: str,
    stockfish_elo: int,
    num_games: int,
    movetime_ms: int,
    stockfish_path: str = "stockfish",
    use_openings: bool = False,
    on_game_complete: Callable[[GameResult], None] | None = None,
) -> MatchResult:
    """Run a match of num_games between engine and Stockfish.

    The test engine alternates colors: game 0 — engine is white, game 1 — black, etc.
    Games end on checkmate, stalemate, threefold repetition, or the 50-move rule.

    Args:
        engine_path: Path to the test engine binary.
        stockfish_elo: ELO rating for Stockfish (UCI_LimitStrength).
        num_games: Number of games to play.
        movetime_ms: Time per move in milliseconds.
        stockfish_path: Path to stockfish binary (default: "stockfish").
        use_openings: Start each game from a random opening position.

    Returns:
        MatchResult with total score and individual game results.
    """
    result = MatchResult(total_score=0.0, num_games=num_games)

    with UCIEngine(engine_path) as engine, UCIEngine(stockfish_path) as stockfish:
        stockfish.set_option("UCI_LimitStrength", "true")
        stockfish.set_option("UCI_Elo", str(stockfish_elo))

        for game_num in range(num_games):
            engine_is_white = game_num % 2 == 0

            if engine_is_white:
                white, black = engine, stockfish
                white_label = "engine"
            else:
                white, black = stockfish, engine
                white_label = "stockfish"

            opening = get_random_opening() if use_openings else None
            game_result_str, moves, termination = play_game(
                white, black, movetime_ms, opening_moves=opening,
            )

            engine_score = _compute_engine_score(
                game_result_str, engine_is_white
            )

            game = GameResult(
                game_number=game_num + 1,
                white=white_label,
                result=game_result_str,
                engine_score=engine_score,
                moves=moves,
                termination=termination,
            )
            result.games.append(game)
            result.total_score += engine_score

            logger.info(
                "Game %d: %s (engine=%s) %s [%s] %d moves",
                game.game_number,
                game.result,
                "white" if engine_is_white else "black",
                termination,
                engine_score,
                len(moves),
            )

            if on_game_complete is not None:
                on_game_complete(game)

    return result


def _compute_engine_score(result: str, engine_is_white: bool) -> float:
    if result == "1/2-1/2":
        return 0.5
    if result == "1-0":
        return 1.0 if engine_is_white else 0.0
    if result == "0-1":
        return 0.0 if engine_is_white else 1.0
    raise ValueError(f"Unknown result: {result}")
