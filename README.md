# ELO Evaluator

Estimate a UCI chess engine's ELO rating by playing matches against Stockfish at
various strength levels. No third-party Python libraries required — only the
standard library and a Stockfish binary.

## How It Works

1. The evaluator launches your engine and Stockfish as UCI subprocesses.
2. A series of matches is played at different Stockfish ELO levels, chosen by
   the selected strategy.
3. After all matches, a **performance rating** is calculated using an iterative
   FIDE-like method (binary search for the rating where expected score equals
   actual score).

**More games = more accurate results.** The performance rating is a statistical
estimate, and its precision improves with sample size. Aim for at least
**1000 total games** for a reliable rating. With fewer games the estimate can
fluctuate significantly between runs. For a quick sanity check 100-200 games may
suffice, but for a publishable result use 1000+.

## Requirements

- Python 3.10+
- [Stockfish](https://stockfishchess.org/) installed and available on `PATH`
  (or pass a custom path via `--stockfish`)
- Your engine must speak the [UCI protocol](https://www.chessprogramming.org/UCI)

## Quick Start

```bash
# Quick test (~60 games, rough estimate)
python evaluate.py ./my_engine --matches 10 --games 6 --movetime 50

# Reliable estimate (~1000 games)
python evaluate.py ./my_engine --matches 50 --games 20 --movetime 50
```

The ELO range is auto-detected from Stockfish's `UCI_Elo` option.

### Example Output

```
  ELO   Score  Games   Pct
 1320     5.0      6   83%  (warmup)
 1528     4.5      6   75%  (warmup)
 1735     3.5      6   58%
 1890     3.0      6   50%
 1920     2.5      6   42%
 1880     3.0      6   50%
 1900     3.0      6   50%
 1910     2.5      6   42%
 1895     3.0      6   50%
 1900     3.0      6   50%

Total: 33.0 / 60
Warmup: 2 match(es) excluded from rating
Performance ELO: 1892
```

## Strategies

### Adaptive (default)

Starts at the midpoint of the ELO range. After each match, recalculates the
performance rating from all games so far and uses it as the next opponent ELO.
Converges quickly toward the engine's true strength.

```bash
python evaluate.py ./my_engine --matches 10 --games 6 --movetime 50 --strategy adaptive
```

### Linear

Plays matches at evenly spaced ELO levels across the full range. Good for
getting a broad picture of performance at every level.

```bash
python evaluate.py ./my_engine --matches 10 --games 6 --movetime 50 --strategy linear
```

### Binary Search

Classic binary search: starts at the midpoint, then narrows the range by half
based on whether the engine scores above or below 50%.

```bash
python evaluate.py ./my_engine --matches 10 --games 6 --movetime 50 --strategy bsearch
```

## CLI Options

| Option | Description |
|---|---|
| `engine_path` | Path to the UCI engine binary |
| `--matches N` | Number of matches to play (required) |
| `--games N` | Games per match (required) |
| `--movetime MS` | Time per move in milliseconds (required) |
| `--strategy` | `adaptive` (default), `linear`, or `bsearch` |
| `--min-elo N` | Minimum opponent ELO (default: auto-detect from Stockfish) |
| `--max-elo N` | Maximum opponent ELO (default: auto-detect from Stockfish) |
| `--stockfish PATH` | Path to Stockfish binary (default: `stockfish`) |
| `--warmup N` | Warmup matches excluded from rating (default: 2) |

## Warmup Matches

The first few matches may produce unreliable results because the adaptive and
binary search strategies haven't converged yet. By default, the first 2 matches
are designated as "warmup". You can override this with `--warmup N`.

Warmup matches are **gradually excluded** from both ELO selection and the final
performance rating. Exclusion begins once the number of rated (non-warmup)
matches equals the warmup count, dropping one warmup match per subsequent match
until all warmup matches are excluded. This prevents losing too much data when
the total number of matches is small.

For example, with `--warmup 2`:

| Total matches | Rated matches | Warmup excluded |
|:---:|:---:|:---:|
| 3 | 1 | 0 |
| 4 | 2 | 1 |
| 5+ | 3+ | 2 (all) |

Warmup matches are still played and always affect strategy decisions (e.g.,
adaptive ELO selection early on).

## ELO Range Auto-Detection

When `--min-elo` or `--max-elo` are not specified, the evaluator queries
Stockfish's UCI options to determine the valid range for `UCI_Elo`. This ensures
the evaluator uses the exact limits supported by your Stockfish version. If
detection fails, it falls back to 800-2800.

## Stockfish Wrapper

`sf_wrapper.py` wraps Stockfish to behave as a fixed-ELO UCI engine. Useful for
testing the evaluator against a known-strength opponent:

```bash
SF_FIXED_ELO=1800 python sf_wrapper.py
```

The wrapper intercepts the UCI handshake and injects `UCI_LimitStrength` and
`UCI_Elo` settings automatically.

## Project Structure

```
evaluate.py          Main entry point and evaluation strategies
match_runner.py      Runs matches between two UCI engines
uci_engine.py        UCI protocol wrapper (subprocess-based)
chess_state.py       Lightweight board tracker for draw detection
performance_elo.py   Performance rating calculation (FIDE-like)
sf_wrapper.py        Stockfish wrapper for fixed-ELO play
tests/               Unit tests for all modules
```

## Draw Detection

Games end on checkmate, stalemate, threefold repetition, or the 50-move rule.
Draw detection is handled by `chess_state.py`, a lightweight board state tracker
that maintains piece positions, castling rights, en passant state, and a position
history — without any third-party chess libraries.

## Running Tests

```bash
python -m unittest discover -s tests -v
```
