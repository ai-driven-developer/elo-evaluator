"""Evaluate a chess engine's ELO by playing matches against Stockfish at various levels."""

import argparse
import logging
import sys
from dataclasses import dataclass

from match_runner import run_match, MatchResult
from performance_elo import performance_rating
from uci_engine import UCIEngine

logger = logging.getLogger("evaluate")

DEFAULT_MIN_ELO = 800
DEFAULT_MAX_ELO = 2800


def get_stockfish_elo_range(stockfish_path: str = "stockfish") -> tuple[int, int]:
    """Query Stockfish for the valid UCI_Elo range.

    Starts Stockfish, reads its UCI options, and returns (min_elo, max_elo)
    from the UCI_Elo spin option. Falls back to (DEFAULT_MIN_ELO, DEFAULT_MAX_ELO)
    if the option is not found or the process fails.
    """
    try:
        with UCIEngine(stockfish_path) as engine:
            opt = engine.get_option("UCI_Elo")
            if opt and "min" in opt and "max" in opt:
                min_elo = int(opt["min"])
                max_elo = int(opt["max"])
                logger.info(
                    "Stockfish UCI_Elo range: %d-%d", min_elo, max_elo,
                )
                return min_elo, max_elo
    except (OSError, EOFError, ValueError) as e:
        logger.warning("Could not detect Stockfish ELO range: %s", e)

    logger.info(
        "Using default ELO range: %d-%d", DEFAULT_MIN_ELO, DEFAULT_MAX_ELO,
    )
    return DEFAULT_MIN_ELO, DEFAULT_MAX_ELO


@dataclass
class EvaluationResult:
    """Results of an engine evaluation run."""

    estimated_elo: float
    total_score: float
    total_games: int
    match_results: list[tuple[int, MatchResult]]  # (elo_level, MatchResult)
    warmup_matches: int  # configured warmup count
    warmup_excluded: int  # actual number of warmup matches excluded from rating


def generate_elo_levels(min_elo: int, max_elo: int, num_matches: int) -> list[int]:
    """Generate evenly spaced ELO levels for matches.

    Returns:
        List of integer ELO ratings.

    Raises:
        ValueError: If num_matches < 1 or min_elo > max_elo.
    """
    if num_matches < 1:
        raise ValueError("num_matches must be at least 1")
    if min_elo > max_elo:
        raise ValueError(f"min_elo ({min_elo}) must be <= max_elo ({max_elo})")

    if num_matches == 1:
        return [(min_elo + max_elo) // 2]

    step = (max_elo - min_elo) / (num_matches - 1)
    return [round(min_elo + i * step) for i in range(num_matches)]


def _resolve_warmup(warmup: int | None, num_matches: int) -> int:
    """Determine effective warmup count and validate."""
    if warmup is None:
        warmup = min(2, num_matches - 1)
    if warmup < 0:
        raise ValueError(f"warmup must be >= 0, got {warmup}")
    if warmup >= num_matches:
        raise ValueError(
            f"warmup ({warmup}) must be less than num_matches ({num_matches})"
        )
    return warmup


def _warmup_excluded(warmup: int, total_matches: int) -> int:
    """Return the number of warmup matches to exclude given total matches played.

    Exclusion starts once rated matches equal the warmup count (i.e.
    total_matches >= 2 * warmup), then drops one warmup match per
    subsequent match until all warmup matches are excluded.
    """
    if warmup <= 0:
        return 0
    rated = total_matches - warmup
    return min(warmup, max(0, rated - warmup + 1))


def _run_single_match(
    engine_path: str,
    elo: int,
    games_per_match: int,
    movetime_ms: int,
    stockfish_path: str,
    match_results: list[tuple[int, MatchResult]],
) -> float:
    """Run one match and accumulate results. Returns the match score."""
    logger.info("Starting match vs Stockfish ELO %d", elo)

    result = run_match(
        engine_path=engine_path,
        stockfish_elo=elo,
        num_games=games_per_match,
        movetime_ms=movetime_ms,
        stockfish_path=stockfish_path,
    )

    match_results.append((elo, result))

    pct = result.total_score / games_per_match * 100
    logger.info(
        "vs ELO %d: %.1f/%d (%.0f%%)",
        elo, result.total_score, games_per_match, pct,
    )

    return result.total_score


def _build_result(
    total_score: float,
    match_results: list[tuple[int, MatchResult]],
    warmup: int,
) -> EvaluationResult:
    """Compute performance rating and build the final result.

    Warmup matches are gradually excluded using the same formula as
    adaptive ELO selection: exclusion starts once rated matches reach
    2x the warmup count, dropping one warmup match per subsequent match.

    total_score and total_games reflect ALL matches including warmup.
    """
    excluded = _warmup_excluded(warmup, len(match_results))
    rated_matches = match_results[excluded:]
    rated_opponents: list[float] = []
    rated_score = 0.0
    for elo, mr in rated_matches:
        rated_opponents.extend([float(elo)] * mr.num_games)
        rated_score += mr.total_score

    total_games = sum(mr.num_games for _, mr in match_results)

    estimated_elo = performance_rating(rated_opponents, rated_score)
    logger.info(
        "Performance ELO: %.0f (warmup: %d/%d matches excluded)",
        estimated_elo, excluded, warmup,
    )
    return EvaluationResult(
        estimated_elo=estimated_elo,
        total_score=total_score,
        total_games=total_games,
        match_results=match_results,
        warmup_matches=warmup,
        warmup_excluded=excluded,
    )


def evaluate_engine_linear(
    engine_path: str,
    num_matches: int,
    games_per_match: int,
    movetime_ms: int,
    min_elo: int = 800,
    max_elo: int = 2800,
    stockfish_path: str = "stockfish",
    warmup: int | None = None,
) -> EvaluationResult:
    """Linear strategy: play matches at evenly spaced ELO levels."""
    warmup = _resolve_warmup(warmup, num_matches)
    elo_levels = generate_elo_levels(min_elo, max_elo, num_matches)

    total_score = 0.0
    match_results: list[tuple[int, MatchResult]] = []

    for elo in elo_levels:
        total_score += _run_single_match(
            engine_path, elo, games_per_match, movetime_ms,
            stockfish_path, match_results,
        )

    return _build_result(total_score, match_results, warmup)


def evaluate_engine_adaptive(
    engine_path: str,
    num_matches: int,
    games_per_match: int,
    movetime_ms: int,
    min_elo: int = 800,
    max_elo: int = 2800,
    stockfish_path: str = "stockfish",
    warmup: int | None = None,
) -> EvaluationResult:
    """Adaptive strategy: pick next opponent ELO based on current performance.

    Starts at the midpoint of [min_elo, max_elo]. After each match, recalculates
    performance rating and uses it as the next opponent ELO (clamped to
    [min_elo, max_elo]).

    Early on, all games (including warmup) are used for ELO selection so
    that the estimate has enough data. Once the number of rated matches
    reaches 2x the warmup count, warmup matches are gradually excluded
    from selection — one per subsequent match — until all are removed.

    The same gradual exclusion applies to the final performance rating.
    """
    warmup = _resolve_warmup(warmup, num_matches)

    total_score = 0.0
    match_results: list[tuple[int, MatchResult]] = []

    next_elo = (min_elo + max_elo) // 2

    for match_num in range(num_matches):
        total_score += _run_single_match(
            engine_path, next_elo, games_per_match, movetime_ms,
            stockfish_path, match_results,
        )

        if match_num < num_matches - 1:
            excluded = _warmup_excluded(warmup, match_num + 1)
            sel_matches = match_results[excluded:]

            sel_opponents: list[float] = []
            sel_score = 0.0
            for elo, mr in sel_matches:
                sel_opponents.extend([float(elo)] * mr.num_games)
                sel_score += mr.total_score

            estimated = performance_rating(sel_opponents, sel_score)
            next_elo = max(min_elo, min(max_elo, round(estimated)))
            logger.info(
                "Adaptive: current estimate %.0f, next opponent ELO %d (using %d/%d matches)",
                estimated, next_elo, len(sel_matches), len(match_results),
            )

    return _build_result(total_score, match_results, warmup)


def evaluate_engine_bsearch(
    engine_path: str,
    num_matches: int,
    games_per_match: int,
    movetime_ms: int,
    min_elo: int = 800,
    max_elo: int = 2800,
    stockfish_path: str = "stockfish",
    warmup: int | None = None,
) -> EvaluationResult:
    """Binary search strategy: narrow the ELO range by halving each step.

    Starts at the midpoint of [min_elo, max_elo]. After each match, moves
    the search boundary based on the match score:
    - >50% → engine is stronger, raise the lower bound
    - <50% → engine is weaker, lower the upper bound
    - =50% → keep both bounds (converged)
    """
    warmup = _resolve_warmup(warmup, num_matches)

    total_score = 0.0
    match_results: list[tuple[int, MatchResult]] = []

    lo, hi = float(min_elo), float(max_elo)

    for match_num in range(num_matches):
        mid = round((lo + hi) / 2)
        total_score += _run_single_match(
            engine_path, mid, games_per_match, movetime_ms,
            stockfish_path, match_results,
        )

        if match_num < num_matches - 1:
            _, last_result = match_results[-1]
            pct = last_result.total_score / games_per_match
            if pct > 0.5:
                lo = mid
            elif pct < 0.5:
                hi = mid
            # pct == 0.5: no change
            logger.info(
                "Bsearch: score %.0f%%, range [%d, %d], next %d",
                pct * 100, round(lo), round(hi), round((lo + hi) / 2),
            )

    return _build_result(total_score, match_results, warmup)


def _resolve_elo_range(
    min_elo: int | None,
    max_elo: int | None,
    stockfish_path: str,
) -> tuple[int, int]:
    """Resolve min/max ELO, querying Stockfish if either is None."""
    if min_elo is not None and max_elo is not None:
        return min_elo, max_elo

    detected_min, detected_max = get_stockfish_elo_range(stockfish_path)
    if min_elo is None:
        min_elo = detected_min
    if max_elo is None:
        max_elo = detected_max
    return min_elo, max_elo


def evaluate_engine(
    strategy: str = "adaptive",
    **kwargs,
) -> EvaluationResult:
    """Evaluate an engine using the specified strategy.

    Args:
        strategy: "adaptive" (default), "linear", or "bsearch".
        **kwargs: Arguments forwarded to the strategy function.
            If min_elo or max_elo is None, the range is auto-detected
            from Stockfish's UCI_Elo option.

    Returns:
        EvaluationResult with estimated ELO and detailed results.

    Raises:
        ValueError: If strategy is unknown.
    """
    # Resolve min/max ELO before forwarding to strategy
    stockfish_path = kwargs.get("stockfish_path", "stockfish")
    min_elo, max_elo = _resolve_elo_range(
        kwargs.pop("min_elo", None),
        kwargs.pop("max_elo", None),
        stockfish_path,
    )
    kwargs["min_elo"] = min_elo
    kwargs["max_elo"] = max_elo

    if strategy == "adaptive":
        return evaluate_engine_adaptive(**kwargs)
    if strategy == "linear":
        return evaluate_engine_linear(**kwargs)
    if strategy == "bsearch":
        return evaluate_engine_bsearch(**kwargs)
    raise ValueError(
        f"Unknown strategy '{strategy}'. Use 'adaptive', 'linear', or 'bsearch'."
    )


def print_results(result: EvaluationResult) -> None:
    """Print a summary table of match results."""
    print()
    print(f"{'ELO':>5}  {'Score':>6}  {'Games':>5}  {'Pct':>4}")
    for i, (elo, match) in enumerate(result.match_results):
        pct = match.total_score / match.num_games * 100
        suffix = "  (warmup)" if i < result.warmup_excluded else ""
        print(f"{elo:>5}  {match.total_score:>6.1f}  {match.num_games:>5}  {pct:>3.0f}%{suffix}")

    print()
    print(f"Total: {result.total_score:.1f} / {result.total_games}")
    if result.warmup_excluded > 0:
        print(f"Warmup: {result.warmup_excluded} match(es) excluded from rating")
    print(f"Performance ELO: {result.estimated_elo:.0f}")


def main(argv: list[str] | None = None) -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Evaluate a chess engine's ELO rating via matches against Stockfish.",
    )
    parser.add_argument("engine_path", help="Path to the engine binary")
    parser.add_argument("--matches", type=int, required=True, help="Number of matches")
    parser.add_argument("--games", type=int, required=True, help="Games per match")
    parser.add_argument("--movetime", type=int, required=True, help="Time per move (ms)")
    parser.add_argument(
        "--strategy", choices=["adaptive", "linear", "bsearch"], default="adaptive",
        help="ELO selection strategy (default: adaptive)",
    )
    parser.add_argument(
        "--min-elo", type=int, default=None,
        help="Min opponent ELO (default: auto-detect from Stockfish)",
    )
    parser.add_argument(
        "--max-elo", type=int, default=None,
        help="Max opponent ELO (default: auto-detect from Stockfish)",
    )
    parser.add_argument(
        "--stockfish", default="stockfish",
        help="Path to Stockfish (default: stockfish)",
    )
    parser.add_argument(
        "--warmup", type=int, default=None,
        help="Number of warmup matches to exclude from rating (default: 2)",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(message)s",
        stream=sys.stderr,
    )

    result = evaluate_engine(
        strategy=args.strategy,
        engine_path=args.engine_path,
        num_matches=args.matches,
        games_per_match=args.games,
        movetime_ms=args.movetime,
        min_elo=args.min_elo,
        max_elo=args.max_elo,
        stockfish_path=args.stockfish,
        warmup=args.warmup,
    )

    print_results(result)


if __name__ == "__main__":
    main()
