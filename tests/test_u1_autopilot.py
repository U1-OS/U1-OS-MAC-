import os as _os
import sys as _sys

# Run from anywhere: put the project root on sys.path so `utils` and
# `services` import whether this file is run directly, via unittest
# discovery, or from another working directory.
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

import tempfile
import unittest
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import patch
from utils import prism_workspace as workspace
from utils import u1_autopilot as agent


class AutopilotTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="u1-autopilot-test-")
        self.data = patch.object(workspace, "DATA", Path(self.temp.name))
        self.data.start()
        self.metrics = patch.object(workspace, "system_metrics", return_value={"disk": {"percent": 30}})
        self.metrics.start()
        self.now = datetime(2026, 9, 6, 2, 0, tzinfo=timezone.utc)

    def tearDown(self):
        self.metrics.stop()
        self.data.stop()
        self.temp.cleanup()

    def test_daily_briefing_deduplicates(self):
        first = agent.tick(self.now)
        second = agent.tick(self.now)
        self.assertEqual(first["briefing"]["date"], "2026-09-06")
        self.assertEqual(len(second["activity"]), 1)
        self.assertIn("Local projects", second["briefing"]["source"])

    def test_due_task_creates_one_reminder(self):
        workspace.handle_post("record", {"kind": "task", "title": "Local test", "payload": {"due": "2026-09-05"}})
        agent.tick(self.now)
        result = agent.tick(self.now)
        reminders = [entry for entry in result["activity"] if entry["kind"] == "reminder"]
        self.assertEqual(len(reminders), 1)
        self.assertEqual(reminders[0]["message"], "Local test")

    def test_paused_agent_emits_nothing(self):
        agent.save_value("u1_autopilot_config", {"enabled": False})
        result = agent.tick(self.now)
        self.assertEqual(result["status"], "paused")
        self.assertEqual(result["activity"], [])

    def test_nearby_event_reminder(self):
        workspace.handle_post("record", {"kind": "event", "title": "Soon", "payload": {"start": "2026-09-06T12:10:00+10:00"}})
        result = agent.tick(self.now)
        self.assertTrue(any(item["message"] == "Soon" for item in result["activity"]))

    def test_high_disk_usage_is_an_alert_not_a_repair(self):
        with patch.object(workspace, "system_metrics", return_value={"disk": {"percent": 93}}):
            result = agent.tick(self.now)
        self.assertTrue(any(item["kind"] == "warning" for item in result["activity"]))
        self.assertIn("no external actions", result["execution"])

    def test_unknown_automation_actions_rejected(self):
        with self.assertRaises(ValueError):
            agent.configure({"settings": {"publish": True}})
        with self.assertRaises(ValueError):
            agent.configure({"settings": {"enabled": "yes"}})


if __name__ == "__main__":
    unittest.main()
