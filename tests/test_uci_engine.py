import io
import subprocess
import unittest
from unittest.mock import patch, MagicMock

from uci_engine import UCIEngine, MATE_SCORE


def make_fake_process(stdout_lines: list[str]):
    """Create a mock Popen process with given stdout lines."""
    proc = MagicMock()
    proc.stdin = io.StringIO()
    proc.stdout = io.StringIO("\n".join(stdout_lines) + "\n")
    proc.wait = MagicMock()
    return proc


class TestUCIEngineStart(unittest.TestCase):

    @patch("uci_engine.subprocess.Popen")
    def test_start_sends_uci_and_waits_for_uciok(self, mock_popen):
        proc = make_fake_process([
            "id name FakeEngine",
            "id author Test",
            "uciok",
        ])
        mock_popen.return_value = proc

        engine = UCIEngine("/fake/engine")
        engine.start()

        written = proc.stdin.getvalue()
        self.assertIn("uci\n", written)

    @patch("uci_engine.subprocess.Popen")
    def test_start_skips_lines_before_uciok(self, mock_popen):
        proc = make_fake_process([
            "id name X",
            "option name Hash type spin default 16",
            "option name Threads type spin default 1",
            "uciok",
        ])
        mock_popen.return_value = proc

        engine = UCIEngine("/fake/engine")
        engine.start()
        # Should not raise — uciok found after several lines


class TestUCIEngineSetOption(unittest.TestCase):

    @patch("uci_engine.subprocess.Popen")
    def test_set_option_format(self, mock_popen):
        proc = make_fake_process(["uciok", "readyok"])
        mock_popen.return_value = proc

        engine = UCIEngine("/fake/engine")
        engine.start()

        # Reset stdin to capture only set_option output
        proc.stdin = io.StringIO()
        engine.set_option("UCI_LimitStrength", "true")

        written = proc.stdin.getvalue()
        self.assertEqual(written.strip(), "setoption name UCI_LimitStrength value true")

    @patch("uci_engine.subprocess.Popen")
    def test_set_option_elo(self, mock_popen):
        proc = make_fake_process(["uciok"])
        mock_popen.return_value = proc

        engine = UCIEngine("/fake/engine")
        engine.start()

        proc.stdin = io.StringIO()
        engine.set_option("UCI_Elo", "1500")

        written = proc.stdin.getvalue()
        self.assertEqual(written.strip(), "setoption name UCI_Elo value 1500")


class TestUCIEngineNewGame(unittest.TestCase):

    @patch("uci_engine.subprocess.Popen")
    def test_new_game_sends_commands(self, mock_popen):
        proc = make_fake_process(["uciok", "readyok"])
        mock_popen.return_value = proc

        engine = UCIEngine("/fake/engine")
        engine.start()

        proc.stdin = io.StringIO()
        engine.new_game()

        written = proc.stdin.getvalue()
        self.assertIn("ucinewgame\n", written)
        self.assertIn("isready\n", written)


class TestUCIEngineGo(unittest.TestCase):

    @patch("uci_engine.subprocess.Popen")
    def test_go_returns_bestmove(self, mock_popen):
        proc = make_fake_process([
            "uciok",
            "readyok",
            "info depth 1 score cp 30 pv e2e4",
            "bestmove e2e4 ponder e7e5",
        ])
        mock_popen.return_value = proc

        engine = UCIEngine("/fake/engine")
        engine.start()
        engine.new_game()

        bestmove, _score = engine.go([], 100)
        self.assertEqual(bestmove, "e2e4")

    @patch("uci_engine.subprocess.Popen")
    def test_go_parses_score_cp(self, mock_popen):
        proc = make_fake_process([
            "uciok",
            "readyok",
            "info depth 1 score cp 45 pv d2d4",
            "info depth 5 score cp 62 pv d2d4 d7d5",
            "bestmove d2d4",
        ])
        mock_popen.return_value = proc

        engine = UCIEngine("/fake/engine")
        engine.start()
        engine.new_game()

        bestmove, score = engine.go([], 100)
        self.assertEqual(bestmove, "d2d4")
        # Should return the LAST score cp seen
        self.assertEqual(score, 62)

    @patch("uci_engine.subprocess.Popen")
    def test_go_parses_negative_score_cp(self, mock_popen):
        proc = make_fake_process([
            "uciok",
            "readyok",
            "info depth 10 score cp -150 pv a7a6",
            "bestmove a7a6",
        ])
        mock_popen.return_value = proc

        engine = UCIEngine("/fake/engine")
        engine.start()
        engine.new_game()

        _, score = engine.go(["e2e4"], 100)
        self.assertEqual(score, -150)

    @patch("uci_engine.subprocess.Popen")
    def test_go_parses_score_mate_positive(self, mock_popen):
        proc = make_fake_process([
            "uciok",
            "readyok",
            "info depth 20 score mate 3 pv e5f7",
            "bestmove e5f7",
        ])
        mock_popen.return_value = proc

        engine = UCIEngine("/fake/engine")
        engine.start()
        engine.new_game()

        _, score = engine.go(["e2e4", "e7e5"], 100)
        self.assertEqual(score, MATE_SCORE)

    @patch("uci_engine.subprocess.Popen")
    def test_go_parses_score_mate_negative(self, mock_popen):
        proc = make_fake_process([
            "uciok",
            "readyok",
            "info depth 20 score mate -2 pv a1a2",
            "bestmove a1a2",
        ])
        mock_popen.return_value = proc

        engine = UCIEngine("/fake/engine")
        engine.start()
        engine.new_game()

        _, score = engine.go(["e2e4"], 100)
        self.assertEqual(score, -MATE_SCORE)

    @patch("uci_engine.subprocess.Popen")
    def test_go_parses_score_mate_zero(self, mock_popen):
        proc = make_fake_process([
            "uciok",
            "readyok",
            "info depth 0 score mate 0",
            "bestmove (none)",
        ])
        mock_popen.return_value = proc

        engine = UCIEngine("/fake/engine")
        engine.start()
        engine.new_game()

        bestmove, score = engine.go(["e2e4", "f7f6", "d2d4", "g7g5", "d1h5"], 100)
        self.assertEqual(bestmove, "(none)")
        self.assertEqual(score, -MATE_SCORE)

    @patch("uci_engine.subprocess.Popen")
    def test_go_bestmove_none(self, mock_popen):
        proc = make_fake_process([
            "uciok",
            "readyok",
            "bestmove (none)",
        ])
        mock_popen.return_value = proc

        engine = UCIEngine("/fake/engine")
        engine.start()
        engine.new_game()

        bestmove, score = engine.go([], 100)
        self.assertEqual(bestmove, "(none)")
        self.assertIsNone(score)

    @patch("uci_engine.subprocess.Popen")
    def test_go_with_moves_sends_position(self, mock_popen):
        proc = make_fake_process([
            "uciok",
            "readyok",
            "info depth 1 score cp 10 pv e7e5",
            "bestmove e7e5",
        ])
        mock_popen.return_value = proc

        engine = UCIEngine("/fake/engine")
        engine.start()
        engine.new_game()

        proc.stdin = io.StringIO()
        engine.go(["e2e4"], 200)

        written = proc.stdin.getvalue()
        self.assertIn("position startpos moves e2e4\n", written)
        self.assertIn("go movetime 200\n", written)

    @patch("uci_engine.subprocess.Popen")
    def test_go_no_moves_sends_startpos(self, mock_popen):
        proc = make_fake_process([
            "uciok",
            "readyok",
            "info depth 1 score cp 20 pv e2e4",
            "bestmove e2e4",
        ])
        mock_popen.return_value = proc

        engine = UCIEngine("/fake/engine")
        engine.start()
        engine.new_game()

        proc.stdin = io.StringIO()
        engine.go([], 100)

        written = proc.stdin.getvalue()
        self.assertIn("position startpos\n", written)


class TestUCIEngineQuit(unittest.TestCase):

    @patch("uci_engine.subprocess.Popen")
    def test_quit_sends_quit(self, mock_popen):
        proc = make_fake_process(["uciok"])
        mock_popen.return_value = proc

        engine = UCIEngine("/fake/engine")
        engine.start()

        proc.stdin = io.StringIO()
        engine.quit()

        written = proc.stdin.getvalue()
        self.assertIn("quit\n", written)
        proc.wait.assert_called_once()

    @patch("uci_engine.subprocess.Popen")
    def test_quit_when_not_started(self, mock_popen):
        engine = UCIEngine("/fake/engine")
        engine.quit()  # Should not raise

    @patch("uci_engine.subprocess.Popen")
    def test_quit_handles_timeout(self, mock_popen):
        proc = make_fake_process(["uciok"])
        proc.wait.side_effect = subprocess.TimeoutExpired("engine", 5)
        proc.kill = MagicMock()
        proc.wait = MagicMock(side_effect=[subprocess.TimeoutExpired("engine", 5), None])
        mock_popen.return_value = proc

        engine = UCIEngine("/fake/engine")
        engine.start()
        engine.quit()  # Should not raise, should kill

        proc.kill.assert_called_once()


class TestUCIEngineContextManager(unittest.TestCase):

    @patch("uci_engine.subprocess.Popen")
    def test_context_manager(self, mock_popen):
        proc = make_fake_process(["uciok"])
        mock_popen.return_value = proc

        with UCIEngine("/fake/engine") as engine:
            self.assertIsNotNone(engine._process)

        # After exiting context, quit should have been called
        proc.wait.assert_called()


class TestOptionParsing(unittest.TestCase):

    def test_parse_spin_option(self):
        line = "option name UCI_Elo type spin default 1320 min 1320 max 3190"
        result = UCIEngine._parse_option_line(line)
        self.assertIsNotNone(result)
        name, info = result
        self.assertEqual(name, "UCI_Elo")
        self.assertEqual(info["type"], "spin")
        self.assertEqual(info["default"], "1320")
        self.assertEqual(info["min"], "1320")
        self.assertEqual(info["max"], "3190")

    def test_parse_check_option(self):
        line = "option name UCI_LimitStrength type check default false"
        result = UCIEngine._parse_option_line(line)
        self.assertIsNotNone(result)
        name, info = result
        self.assertEqual(name, "UCI_LimitStrength")
        self.assertEqual(info["type"], "check")
        self.assertEqual(info["default"], "false")

    def test_parse_option_with_spaces_in_name(self):
        line = "option name Debug Log File type string default"
        result = UCIEngine._parse_option_line(line)
        self.assertIsNotNone(result)
        name, info = result
        self.assertEqual(name, "Debug Log File")
        self.assertEqual(info["type"], "string")

    def test_parse_hash_option(self):
        line = "option name Hash type spin default 16 min 1 max 33554432"
        result = UCIEngine._parse_option_line(line)
        self.assertIsNotNone(result)
        name, info = result
        self.assertEqual(name, "Hash")
        self.assertEqual(info["min"], "1")
        self.assertEqual(info["max"], "33554432")

    def test_parse_invalid_line_returns_none(self):
        self.assertIsNone(UCIEngine._parse_option_line("id name Stockfish"))
        self.assertIsNone(UCIEngine._parse_option_line("uciok"))

    def test_parse_empty_name_returns_none(self):
        self.assertIsNone(UCIEngine._parse_option_line("option name type spin"))

    @patch("uci_engine.subprocess.Popen")
    def test_start_collects_options(self, mock_popen):
        proc = make_fake_process([
            "id name Stockfish",
            "option name Hash type spin default 16 min 1 max 33554432",
            "option name UCI_Elo type spin default 1320 min 1320 max 3190",
            "option name UCI_LimitStrength type check default false",
            "uciok",
        ])
        mock_popen.return_value = proc

        engine = UCIEngine("/fake/stockfish")
        engine.start()

        self.assertIn("Hash", engine.options)
        self.assertIn("UCI_Elo", engine.options)
        self.assertIn("UCI_LimitStrength", engine.options)
        self.assertEqual(engine.options["UCI_Elo"]["min"], "1320")
        self.assertEqual(engine.options["UCI_Elo"]["max"], "3190")

    @patch("uci_engine.subprocess.Popen")
    def test_get_option_existing(self, mock_popen):
        proc = make_fake_process([
            "option name UCI_Elo type spin default 1320 min 1320 max 3190",
            "uciok",
        ])
        mock_popen.return_value = proc

        engine = UCIEngine("/fake/stockfish")
        engine.start()

        opt = engine.get_option("UCI_Elo")
        self.assertIsNotNone(opt)
        self.assertEqual(opt["min"], "1320")

    @patch("uci_engine.subprocess.Popen")
    def test_get_option_missing(self, mock_popen):
        proc = make_fake_process(["uciok"])
        mock_popen.return_value = proc

        engine = UCIEngine("/fake/stockfish")
        engine.start()

        self.assertIsNone(engine.get_option("UCI_Elo"))

    @patch("uci_engine.subprocess.Popen")
    def test_start_no_options(self, mock_popen):
        proc = make_fake_process(["id name FakeEngine", "uciok"])
        mock_popen.return_value = proc

        engine = UCIEngine("/fake/engine")
        engine.start()

        self.assertEqual(engine.options, {})


class TestScoreParsing(unittest.TestCase):
    """Test the static score parsing methods directly."""

    def test_parse_score_cp_positive(self):
        line = "info depth 15 seldepth 20 score cp 125 nodes 50000 pv e2e4"
        self.assertEqual(UCIEngine._parse_score_cp(line), 125)

    def test_parse_score_cp_negative(self):
        line = "info depth 10 score cp -89 pv d7d5"
        self.assertEqual(UCIEngine._parse_score_cp(line), -89)

    def test_parse_score_cp_zero(self):
        line = "info depth 5 score cp 0 pv e2e4 e7e5"
        self.assertEqual(UCIEngine._parse_score_cp(line), 0)

    def test_parse_score_mate_positive(self):
        line = "info depth 30 score mate 5 pv e5f7"
        self.assertEqual(UCIEngine._parse_score_mate(line), MATE_SCORE)

    def test_parse_score_mate_negative(self):
        line = "info depth 30 score mate -3 pv a1a2"
        self.assertEqual(UCIEngine._parse_score_mate(line), -MATE_SCORE)

    def test_parse_score_mate_zero(self):
        line = "info depth 0 score mate 0"
        self.assertEqual(UCIEngine._parse_score_mate(line), -MATE_SCORE)

    def test_parse_score_mate_one(self):
        line = "info depth 1 score mate 1 pv d1h5"
        self.assertEqual(UCIEngine._parse_score_mate(line), MATE_SCORE)


if __name__ == "__main__":
    unittest.main()
