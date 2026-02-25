#!/usr/bin/env python3
"""
Stockfish wrapper that plays at a fixed ELO level.
Acts as a UCI engine, forwarding all commands to Stockfish
but injecting UCI_LimitStrength and UCI_Elo settings.

Usage:
    SF_FIXED_ELO=1800 ./sf_wrapper.py
    SF_FIXED_ELO=1800 SF_PATH=/usr/games/stockfish ./sf_wrapper.py
"""

import os
import subprocess
import sys
import threading


def main():
    """Run Stockfish as a fixed-ELO UCI engine proxy."""
    elo = int(os.environ.get("SF_FIXED_ELO", "1800"))
    sf_path = os.environ.get("SF_PATH", "stockfish")

    proc = subprocess.Popen(
        [sf_path],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
        bufsize=1,
    )

    # Forward stockfish output to our stdout
    def forward_output():
        try:
            for line in proc.stdout:
                sys.stdout.write(line)
                sys.stdout.flush()
        except (BrokenPipeError, OSError):
            pass

    t = threading.Thread(target=forward_output, daemon=True)
    t.start()

    elo_injected = False
    try:
        for line in sys.stdin:
            cmd = line.strip()

            # Inject ELO settings before the first isready
            if cmd == "isready" and not elo_injected:
                proc.stdin.write("setoption name UCI_LimitStrength value true\n")
                proc.stdin.write(f"setoption name UCI_Elo value {elo}\n")
                proc.stdin.flush()
                elo_injected = True

            proc.stdin.write(line)
            proc.stdin.flush()

            if cmd == "quit":
                break
    except (BrokenPipeError, OSError):
        pass

    try:
        proc.wait(timeout=3)
    except subprocess.TimeoutExpired:
        proc.kill()


if __name__ == "__main__":
    main()
