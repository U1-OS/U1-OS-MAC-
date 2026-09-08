"""Updater service and improvement agent tests.

Nothing here touches the network or mutates the installation: every
action that would change files is checked for its confirmation gate
instead of being run.
"""
import os as _os
import sys as _sys

# Run from anywhere: put the project root on sys.path so `utils` and
# `services` import whether this file is run directly, via unittest
# discovery, or from another working directory.
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from services.updater import UpdaterService, read_version, DEFAULT_VERSION
from utils import improvement_agent


CONFIG = {"system": {"port": 8788, "host": "127.0.0.1"}}


class UpdaterServiceTests(unittest.TestCase):
    def setUp(self):
        self.svc = UpdaterService(dict(CONFIG))

    # -- identity -----------------------------------------------------
    def test_service_registers_as_updater(self):
        self.assertEqual(self.svc.name, "updater")
        self.assertTrue(self.svc.configured)

    def test_version_file_is_readable(self):
        version = read_version()
        self.assertTrue(version)
        self.assertRegex(version, r"^\d+\.\d+")

    def test_version_falls_back_when_file_is_missing(self):
        with patch("services.updater.VERSION_FILE", "/nonexistent/VERSION"):
            self.assertEqual(read_version(), DEFAULT_VERSION)

    # -- runtime snapshot ---------------------------------------------
    def test_runtime_snapshot_reports_the_configured_port(self):
        runtime = self.svc.runtime_snapshot()
        self.assertEqual(runtime["port"], 8788)
        self.assertIn("python", runtime)
        self.assertIn("optional_dependencies", runtime)

    def test_runtime_snapshot_lists_optional_dependencies(self):
        deps = self.svc.runtime_snapshot()["optional_dependencies"]
        for name in ("psutil", "reportlab", "pypdf"):
            self.assertIn(name, deps)
            self.assertIn("installed", deps[name])
            self.assertIn("purpose", deps[name])

    # -- git ----------------------------------------------------------
    def test_git_snapshot_never_leaks_fatal_text(self):
        snapshot = self.svc.git_snapshot()
        self.assertNotIn("fatal:", json.dumps(snapshot))

    def test_git_snapshot_reports_a_branch_name(self):
        snapshot = self.svc.git_snapshot()
        if snapshot.get("is_repo"):
            self.assertTrue(snapshot.get("branch"))

    def test_git_helper_handles_a_missing_binary(self):
        with patch("services.updater.subprocess.run", side_effect=FileNotFoundError):
            ok, out = self.svc.git_snapshot(), None
        self.assertIsInstance(ok, dict)

    # -- confirmation gates -------------------------------------------
    def test_every_mutating_action_requires_confirmation(self):
        for action in ("apply_update", "install_dependencies",
                       "rebuild_desktop_app", "restart_server"):
            result = self.svc.dispatch_action(action, {})
            self.assertFalse(result["success"], action)
            self.assertEqual(result["error"], "confirmation_required", action)

    def test_unknown_action_is_reported_not_raised(self):
        result = self.svc.dispatch_action("does_not_exist", {})
        self.assertFalse(result["success"])
        self.assertIn("not available", result["error"])

    def test_read_only_actions_need_no_confirmation(self):
        for action in ("get_status", "get_changelog", "agent_status"):
            result = self.svc.dispatch_action(action, {})
            self.assertIsInstance(result, dict)
            self.assertNotEqual(result.get("error"), "confirmation_required")

    def test_apply_update_refuses_a_dirty_working_tree(self):
        dirty = {"is_repo": True, "clean": False, "uncommitted_files": 3,
                 "branch": "main", "commit": "abc1234"}
        with patch.object(self.svc, "git_snapshot", return_value=dirty):
            result = self.svc.dispatch_action("apply_update", {"confirmed": True})
        self.assertFalse(result["success"])
        self.assertEqual(result["error"], "uncommitted_changes")

    def test_rebuild_is_refused_off_macos(self):
        with patch("services.updater.sys.platform", "linux"):
            result = self.svc.dispatch_action("rebuild_desktop_app", {"confirmed": True})
        self.assertFalse(result["success"])
        self.assertIn(result["error"], {"wrong_platform", "no_build_script"})

    # -- poll ---------------------------------------------------------
    def test_poll_populates_every_panel_payload(self):
        self.svc.poll()
        for key in ("runtime", "git", "changelog", "agent"):
            self.assertIn(key, self.svc.data)


class ImprovementAgentTests(unittest.TestCase):
    def loader(self):
        return {"tools": [
            {"id": "demo", "name": "Demo Tool", "installed": False, "ready": False, "setup_issue": ""},
            {"id": "ready", "name": "Ready Tool", "installed": True, "ready": True, "setup_issue": ""},
        ]}

    def test_inspect_flags_a_missing_tool(self):
        findings = improvement_agent.inspect(self.loader)
        ids = [f["id"] for f in findings]
        self.assertIn("missing-demo", ids)
        self.assertNotIn("missing-ready", ids)

    def test_every_finding_is_well_formed(self):
        for finding in improvement_agent.inspect(self.loader):
            for key in ("id", "priority", "title", "detail", "destination"):
                self.assertIn(key, finding)
            self.assertIn(finding["priority"], {"attention", "setup", "improvement"})

    def test_snapshot_declares_its_safeguards(self):
        snapshot = improvement_agent.snapshot()
        self.assertTrue(snapshot["success"])
        self.assertIn("No automatic repairs", snapshot["safeguards"])
        self.assertIn("No outbound requests", snapshot["safeguards"])

    def test_configure_rejects_an_unknown_mode(self):
        with self.assertRaises(ValueError):
            improvement_agent.configure({"action": "delete_everything"})

    def test_updater_surfaces_the_agent(self):
        svc = UpdaterService(dict(CONFIG))
        svc.agent = improvement_agent
        snapshot = svc.agent_snapshot()
        self.assertTrue(snapshot.get("available"))

    def test_updater_reports_a_detached_agent_without_raising(self):
        svc = UpdaterService(dict(CONFIG))
        svc.agent = None
        snapshot = svc.agent_snapshot()
        self.assertFalse(snapshot["success"])
        self.assertFalse(snapshot["available"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
