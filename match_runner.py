"""Run a match between a test engine and Stockfish via UCI."""

import logging
from dataclasses import dataclass, field

from chess_state import ChessState
from uci_engine import UCIEngine, MATE_SCORE

logger = logging.getLogger("match_runner")


@dataclass
class GameResult:
    game_number: int
    white: str  # "engine" or "stockfish"
    result: str  # "1-0", "0-1", "1/2-1/2"
    engine_score: float  # points for the test engine: 1.0 / 0.5 / 0.0
    moves: list[str]
    termination: str  # "checkmate", "stalemate", "max_moves"


@dataclass
class MatchResult:
    total_score: float
    num_games: int
    games: list[GameResult] = field(default_factory=list)


def play_game(
    white: UCIEngine,
    black: UCIEngine,
    movetime_ms: int,
) -> tuple[str, list[str], str]:
    """Play a single game between two engines.

    The game ends on checkmate, stalemate, threefold repetition,
    or the 50-move rule.

    Returns:
        (result, moves, termination) where result is "1-0", "0-1", or "1/2-1/2".
    """
    white.new_game()
    black.new_game()

    state = ChessState()
    moves: list[str] = []
    engines = [white, black]

    while True:
        side = len(moves) % 2  # 0=white, 1=black
        engine = engines[side]

        bestmove, score = engine.go(list(moves), movetime_ms)

        if bestmove in ("(none)", "0000"):
            # No legal moves: checkmate or stalemate
            # Note: "(none)" is Stockfish's convention, "0000" is used by many other engines
            if score is not None and score <= -MATE_SCORE // 2:
                # Side to move is checkmated
                if side == 0:
                    return "0-1", moves, "checkmate"
                else:
                    return "1-0", moves, "checkmate"
            else:
                return "1/2-1/2", moves, "stalemate"

        moves.append(bestmove)
        state.push_uci(bestmove)
        logger.debug("ply %d: %s", len(moves), bestmove)

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

            game_result_str, moves, termination = play_game(
                white, black, movetime_ms
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

    return result


def _compute_engine_score(result: str, engine_is_white: bool) -> float:
    if result == "1/2-1/2":
        return 0.5
    if result == "1-0":
        return 1.0 if engine_is_white else 0.0
    if result == "0-1":
        return 0.0 if engine_is_white else 1.0
    raise ValueError(f"Unknown result: {result}")
