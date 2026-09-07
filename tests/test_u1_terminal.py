import os as _os
import sys as _sys

# Run from anywhere: put the project root on sys.path so `utils` and
# `services` import whether this file is run directly, via unittest
# discovery, or from another working directory.
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

import base64
import os
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch
from utils import u1_terminal as terminal


class TerminalTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.patches = [patch.object(terminal, "ROOT", Path(self.temp.name)), patch.object(terminal, "SHELL", "/bin/sh"), patch.dict(os.environ, {"HOME": self.temp.name})]
        for item in self.patches:
            item.start()

    def tearDown(self):
        terminal.close_all()
        for item in reversed(self.patches):
            item.stop()
        self.temp.cleanup()

    def start(self):
        result = terminal.handle_post(dict(action="start", acknowledge=True, cols=80, rows=24))
        return {"session": result["session"], "capability": result["capability"]}

    def test_requires_explicit_acknowledgement(self):
        with self.assertRaises(ValueError):
            terminal.handle_post(dict(action="start"))

    def test_rejects_bad_dimensions(self):
        for body in ({"cols": 0}, {"rows": 10000}, {"cols": True}):
            with self.assertRaises(ValueError):
                terminal.dimensions(body)

    def test_unknown_actions_are_rejected(self):
        with self.assertRaises(ValueError):
            terminal.handle_post(dict(action="execute-arbitrary-remote"))

    def test_session_capability_required(self):
        session = self.start()
        with self.assertRaises(ValueError):
            terminal.handle_post({**session, "action": "poll", "capability": "incorrect"})

    def test_input_and_output_are_real_pty_data(self):
        session = self.start()
        terminal.handle_post({**session, "action": "input", "input": "pwd\n"})
        data = b""
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            result = terminal.handle_post({**session, "action": "poll", "cursor": 0})
            data = base64.b64decode(result["output"])
            if self.temp.name.encode() in data:
                break
            time.sleep(.03)
        self.assertIn(self.temp.name.encode(), data)

    def test_close_revokes_access(self):
        session = self.start()
        terminal.handle_post({**session, "action": "close"})
        with self.assertRaises(ValueError):
            terminal.handle_post({**session, "action": "poll"})

    def test_input_size_limit(self):
        session = self.start()
        with self.assertRaises(ValueError):
            terminal.handle_post({**session, "action": "input", "input": "x" * 9000})


if __name__ == "__main__":
    unittest.main()
