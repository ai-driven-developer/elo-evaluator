"""Collection of common chess opening lines for game randomization."""

import random

# Each opening is a list of UCI moves from the starting position.
OPENINGS = [
    # Open games (1.e4 e5)
    ["e2e4", "e7e5"],
    ["e2e4", "e7e5", "g1f3", "b8c6"],
    ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4"],     # Italian
    ["e2e4", "e7e5", "g1f3", "b8c6", "d2d4"],     # Scotch
    ["e2e4", "e7e5", "f1c4"],                       # Bishop's Opening
    # Sicilian (1.e4 c5)
    ["e2e4", "c7c5"],
    ["e2e4", "c7c5", "g1f3", "d7d6"],              # Najdorf setup
    # French (1.e4 e6)
    ["e2e4", "e7e6"],
    # Caro-Kann (1.e4 c6)
    ["e2e4", "c7c6"],
    # Queen's Pawn (1.d4 d5)
    ["d2d4", "d7d5"],
    ["d2d4", "d7d5", "c2c4"],                       # Queen's Gambit
    # Indian systems (1.d4 Nf6)
    ["d2d4", "g8f6"],
    ["d2d4", "g8f6", "c2c4", "g7g6"],              # King's Indian
    ["d2d4", "g8f6", "c2c4", "e7e6"],              # Nimzo/QID area
    # English (1.c4)
    ["c2c4", "e7e5"],
    # Reti (1.Nf3)
    ["g1f3", "d7d5"],
]


def get_random_opening(rng: random.Random | None = None) -> list[str]:
    """Return a random opening line from the book.

    Args:
        rng: Optional Random instance for reproducibility.

    Returns:
        A list of UCI moves representing an opening position.
    """
    if rng is None:
        return random.choice(OPENINGS)
    return rng.choice(OPENINGS)
