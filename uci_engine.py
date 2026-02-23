"""UCI engine wrapper using subprocess."""

import subprocess


MATE_SCORE = 100_000


class UCIEngine:
    """Communicates with a UCI chess engine via stdin/stdout."""

    def __init__(self, path: str):
        self.path = path
        self._process: subprocess.Popen | None = None
        self.options: dict[str, dict[str, str]] = {}

    # --- Lifecycle ---

    def start(self) -> None:
        """Launch the engine process and initialize UCI protocol.

        Parses all 'option' lines emitted before 'uciok' and stores them
        in self.options, keyed by option name.
        """
        self._process = subprocess.Popen(
            [self.path],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
        )
        self._send("uci")
        self.options = {}
        while True:
            line = self._read_line()
            if line.startswith("option "):
                parsed = self._parse_option_line(line)
                if parsed:
                    name, info = parsed
                    self.options[name] = info
            if line.startswith("uciok"):
                break

    def quit(self) -> None:
        """Send quit command and terminate the process."""
        if self._process is None:
            return
        try:
            self._send("quit")
            self._process.wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            self._process.kill()
            self._process.wait()
        finally:
            self._process = None

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.quit()
        return False

    # --- Option parsing ---

    @staticmethod
    def _parse_option_line(line: str) -> tuple[str, dict[str, str]] | None:
        """Parse a UCI 'option' line into (name, info_dict).

        Example input:
            option name UCI_Elo type spin default 1320 min 1320 max 3190
        Returns:
            ("UCI_Elo", {"type": "spin", "default": "1320", "min": "1320", "max": "3190"})
        """
        tokens = line.split()
        if len(tokens) < 4 or tokens[0] != "option" or tokens[1] != "name":
            return None

        keywords = {"type", "default", "min", "max", "var"}
        name_parts: list[str] = []
        i = 2
        while i < len(tokens) and tokens[i] not in keywords:
            name_parts.append(tokens[i])
            i += 1

        if not name_parts:
            return None

        name = " ".join(name_parts)
        info: dict[str, str] = {}

        while i < len(tokens):
            key = tokens[i]
            i += 1
            if key in ("type", "default", "min", "max") and i < len(tokens):
                info[key] = tokens[i]
                i += 1

        return name, info

    def get_option(self, name: str) -> dict[str, str] | None:
        """Return parsed info for a UCI option, or None if not found."""
        return self.options.get(name)

    # --- UCI commands ---

    def set_option(self, name: str, value: str) -> None:
        """Send 'setoption name <name> value <value>'."""
        self._send(f"setoption name {name} value {value}")

    def new_game(self) -> None:
        """Signal the start of a new game."""
        self._send("ucinewgame")
        self._send("isready")
        self._read_until("readyok")

    def go(self, moves: list[str], movetime_ms: int) -> tuple[str, int | None]:
        """Search the given position and return (bestmove, score_cp).

        Args:
            moves: List of moves from startpos in UCI notation (e.g. ["e2e4", "e7e5"]).
            movetime_ms: Time to search in milliseconds.

        Returns:
            A tuple of (bestmove, score_cp).
            bestmove is "(none)" when no legal moves exist.
            score_cp is centipawns from the engine's perspective, or None if unavailable.
            Mate scores are converted to ±MATE_SCORE.
        """
        if moves:
            self._send(f"position startpos moves {' '.join(moves)}")
        else:
            self._send("position startpos")
        self._send(f"go movetime {movetime_ms}")

        score_cp: int | None = None
        while True:
            line = self._read_line()
            if line.startswith("bestmove"):
                bestmove = line.split()[1]
                return bestmove, score_cp
            if "score cp " in line:
                score_cp = self._parse_score_cp(line)
            elif "score mate " in line:
                score_cp = self._parse_score_mate(line)

    # --- Internal helpers ---

    def _send(self, command: str) -> None:
        assert self._process is not None and self._process.stdin is not None
        self._process.stdin.write(command + "\n")
        self._process.stdin.flush()

    def _read_line(self) -> str:
        assert self._process is not None and self._process.stdout is not None
        line = self._process.stdout.readline()
        if not line:
            raise EOFError("Engine process closed stdout")
        return line.strip()

    def _read_until(self, prefix: str) -> str:
        """Read lines until one starts with prefix, return that line."""
        while True:
            line = self._read_line()
            if line.startswith(prefix):
                return line

    @staticmethod
    def _parse_score_cp(line: str) -> int:
        parts = line.split()
        idx = parts.index("cp")
        return int(parts[idx + 1])

    @staticmethod
    def _parse_score_mate(line: str) -> int:
        parts = line.split()
        idx = parts.index("mate")
        mate_in = int(parts[idx + 1])
        if mate_in > 0:
            return MATE_SCORE
        elif mate_in < 0:
            return -MATE_SCORE
        else:
            # mate 0 means the side to move is checkmated
            return -MATE_SCORE
