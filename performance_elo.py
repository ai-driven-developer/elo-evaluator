"""Performance ELO rating calculation using iterative (FIDE-like) method.

Finds rating R such that the total expected score against all opponents
equals the actual score, using binary search.
"""


def expected_score(rating: float, opponent_rating: float) -> float:
    """Expected score of a player with `rating` against `opponent_rating`.

    Returns a value in (0, 1) based on the standard ELO formula.
    """
    return 1.0 / (1.0 + 10.0 ** ((opponent_rating - rating) / 400.0))


def total_expected_score(rating: float, opponents: list[float]) -> float:
    """Sum of expected scores against each opponent."""
    return sum(expected_score(rating, opp) for opp in opponents)


def performance_rating(
    opponents: list[float],
    score: float,
    tolerance: float = 0.001,
    lo: float = 0.0,
    hi: float = 5000.0,
    max_iterations: int = 1000,
) -> float:
    """Find the performance rating via binary search.

    Args:
        opponents: List of opponent ratings.
        score: Actual score achieved (wins=1, draws=0.5, losses=0).
        tolerance: Acceptable difference between expected and actual score.
        lo: Lower bound of the search range.
        hi: Upper bound of the search range.
        max_iterations: Maximum number of binary search iterations.

    Returns:
        The estimated performance rating.

    Raises:
        ValueError: If opponents is empty or score is out of [0, len(opponents)].
    """
    n = len(opponents)
    if n == 0:
        raise ValueError("opponents list must not be empty")
    if score < 0 or score > n:
        raise ValueError(
            f"score must be between 0 and {n} (number of games), got {score}"
        )

    # Edge cases: perfect score or zero score — binary search still works,
    # it will just converge to the boundary of the search range.

    for _ in range(max_iterations):
        mid = (lo + hi) / 2.0
        expected = total_expected_score(mid, opponents)
        if abs(expected - score) < tolerance:
            return mid
        if expected < score:
            lo = mid
        else:
            hi = mid

    return (lo + hi) / 2.0
