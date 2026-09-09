"""Isolated release contracts; no real application, Keychain, network or Desktop."""
import importlib.util
import io
import json
import os
from pathlib import Path
import plistlib
import tempfile
import threading
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / "macos" / (name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


support = load("release_support")
checks = load("release_checks")
launcher_spec = importlib.util.spec_from_file_location("release_launcher", ROOT / "launch_u1.py")
launcher = importlib.util.module_from_spec(launcher_spec)
launcher_spec.loader.exec_module(launcher)


class MacReleaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="u1-mac-release-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def bundle(self, name, identity=support.BUNDLE_ID):
        path = self.root / name
        (path / "Contents").mkdir(parents=True)
        with (path / "Contents/Info.plist").open("wb") as handle:
            plistlib.dump({"CFBundleIdentifier": identity}, handle)
        return path

    def test_metadata_is_local_only_and_has_a_recorded_version(self):
        info = support.metadata(self.root, "2.1.0", "2609.8.1", "a" * 40)
        self.assertEqual(info["U1WorkspaceRoot"], str(self.root.resolve()))
        self.assertEqual(info["CFBundleVersion"], "2609.8.1")
        self.assertEqual(info["U1SourceRevision"], "a" * 40)
        self.assertEqual(info["NSAppTransportSecurity"], {"NSAllowsLocalNetworking": True})
        self.assertNotIn("NSAllowsArbitraryLoads", info["NSAppTransportSecurity"])

    def test_metadata_rejects_invalid_release_values(self):
        for overrides in ({"version": "bad"}, {"build": "20260908"}, {"revision": "token-or-branch"}):
            with self.subTest(overrides=overrides), self.assertRaises(ValueError):
                support.metadata(self.root, **overrides)

    def test_replacement_needs_explicit_permission(self):
        old, new = self.bundle("old.app"), self.bundle("new.app")
        with self.assertRaises(FileExistsError):
            support.promote_bundle(new, old)
        self.assertTrue(old.exists()); self.assertTrue(new.exists())

    def test_replacement_preserves_old_bundle(self):
        old, new = self.bundle("old.app"), self.bundle("new.app")
        (old / "marker").write_text("previous")
        backup = support.promote_bundle(new, old, replace=True)
        self.assertEqual((backup / "marker").read_text(), "previous")
        self.assertTrue(old.exists()); self.assertFalse(new.exists())

    def test_unrelated_app_is_never_replaced(self):
        old, new = self.bundle("old.app", "another.app"), self.bundle("new.app")
        with self.assertRaises(ValueError):
            support.promote_bundle(new, old, replace=True)
        self.assertTrue(old.exists())

    def test_symlink_destination_is_rejected(self):
        old, new = self.bundle("old.app"), self.bundle("new.app")
        redirected = self.root / "redirected.app"
        redirected.symlink_to(old, target_is_directory=True)
        with self.assertRaises(ValueError):
            support.promote_bundle(new, redirected, replace=True)

    def test_failed_promotion_restores_existing_app(self):
        old, new = self.bundle("old.app"), self.bundle("new.app")
        rename = Path.rename
        def fail_staged(path, destination):
            if path == new:
                raise OSError("simulated interrupted promotion")
            return rename(path, destination)
        with patch.object(Path, "rename", fail_staged), self.assertRaises(OSError):
            support.promote_bundle(new, old, replace=True)
        self.assertTrue(old.exists()); self.assertTrue(new.exists())

    def test_installer_verifies_copy_before_replacing(self):
        app = self.bundle("source.app")
        desktop = self.root / "Desktop"
        desktop.mkdir()
        with patch.object(support.subprocess, "run", side_effect=OSError("invalid signature")):
            with self.assertRaises(OSError):
                support.install_bundle(app, desktop)
        self.assertFalse((desktop / "U1 OS.app").exists())
        self.assertFalse((desktop / ".u1-desktop-install.lock").exists())

    def test_selector_never_discovers_inherited_tests(self):
        (self.root / "tests").mkdir()
        (self.root / checks.TEST_FILES[0]).write_text("")
        (self.root / "tests/test_dangerous_inherited.py").write_text("raise RuntimeError('do not import')")
        present, missing = checks.select_tests(self.root)
        self.assertEqual(present, [checks.TEST_FILES[0]])
        self.assertEqual(len(missing), len(checks.TEST_FILES) - 1)

    def test_selector_rejects_symlinked_tests(self):
        (self.root / "tests").mkdir()
        source = self.root / "source.py"
        source.write_text("")
        (self.root / checks.TEST_FILES[0]).symlink_to(source)
        with self.assertRaises(ValueError):
            checks.select_tests(self.root)

    def test_missing_skipped_and_failing_results_are_honest(self):
        self.assertEqual(checks.result_status([{"status": "PASS"}], ["pending.py"]), "PARTIAL")
        self.assertEqual(checks.result_status([{"status": "PARTIAL"}], []), "PARTIAL")
        self.assertEqual(checks.result_status([{"status": "FAIL"}], []), "FAIL")
        self.assertEqual(checks.result_status([], []), "FAIL")
        self.assertEqual(checks.result_status([{"status": "PASS"}], []), "PASS")

    def test_actual_existing_names_and_media_are_selected(self):
        self.assertIn("tests/test_updater.py", checks.TEST_FILES)
        self.assertIn("tests/test_integrations_hub.py", checks.TEST_FILES)
        self.assertIn("tests/test_u1_media_research.py", checks.TEST_FILES)
        self.assertIn("tests/test_u1_image_provider.py", checks.TEST_FILES)
        self.assertEqual(checks.TEST_FIXTURES["tests/test_u1_image_provider.py"], ("tests/test_u1_assistant.py",))
        self.assertIn("utils/u1_credentials.py", checks.PYTHON_FILES)
        self.assertIn("utils/u1_image_provider.py", checks.PYTHON_FILES)
        self.assertIn("static/js/u1-image-provider.js", checks.JS_SYNTAX_FILES)
        self.assertNotIn("tests/test_u1_updater.py", checks.TEST_FILES)
        self.assertNotIn("tests/test_u1_integrations_hub.py", checks.TEST_FILES)

    def test_only_exact_real_ffmpeg_test_is_opt_in(self):
        class SyntheticFFmpegTests(unittest.TestCase):
            def test_generated_owned_video_exports_real_mp4_and_wav(self): pass
            def test_real_empty_outputs_are_rejected_even_when_ffmpeg_returns_zero(self): pass
            def test_real_short_audio_cannot_pass_a_longer_export_contract(self): pass
            def test_other_contract(self): pass
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(SyntheticFFmpegTests)
        selected, excluded = checks.unit_suite(suite, "tests/test_u1_media_research.py")
        self.assertEqual(selected.countTestCases(), 1)
        self.assertEqual(excluded, [
            "SyntheticFFmpegTests.test_generated_owned_video_exports_real_mp4_and_wav",
            "SyntheticFFmpegTests.test_real_empty_outputs_are_rejected_even_when_ffmpeg_returns_zero",
            "SyntheticFFmpegTests.test_real_short_audio_cannot_pass_a_longer_export_contract"])
        selected, excluded = checks.unit_suite(suite, "tests/test_updater.py")
        self.assertEqual(selected.countTestCases(), 4)
        self.assertEqual(excluded, [])

    def test_javascript_gate_has_exact_file_permissions(self):
        name = "tests/test_u1_connections.cjs"
        for relative in (name, *checks.JS_TESTS[name]):
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture")
        command = checks.js_command(name, self.root, "/node")
        self.assertIn("--permission", command)
        self.assertNotIn("--allow-net", command)
        self.assertNotIn("--allow-child-process", command)
        self.assertEqual(sum(value.startswith("--allow-fs-read=") for value in command), 4)
        with self.assertRaises(PermissionError):
            checks.js_command("tests/inherited.js", self.root, "/node")

    def test_shell_navigation_marker_requires_exact_output_and_success(self):
        self.assertEqual(checks.JS_TESTS["tests/test_u1_build_status.cjs"], ("static/js/u1-build-status.js", "docs/BUILD-STATUS.md"))
        name = "tests/test_u1_shell_navigation.cjs"
        self.assertEqual(checks.JS_TESTS[name], ("static/js/u1-core-workspaces.js",))
        marker = "PASS 6 native registration and direct-entry contracts\n"
        result = checks.javascript_result(name, 0, marker)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["tests"], 6)
        for code, output in ((1, marker), (0, ""), (0, "PASS 6"), (0, marker + "FAILED\n")):
            with self.subTest(code=code, output=output):
                result = checks.javascript_result(name, code, output)
                self.assertEqual(result["status"], "FAIL")
                self.assertEqual(result["tests"], 0)

    def test_javascript_permissions_canonicalise_the_temporary_root(self):
        name = "tests/test_u1_media.mjs"
        staged = self.root / "staged"
        for relative in (name, *checks.JS_TESTS[name]):
            path = staged / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("fixture")
        alias = self.root / "alias"
        alias.symlink_to(staged, target_is_directory=True)
        command = checks.js_command(name, alias, "/node")
        self.assertEqual(command[-1], str(staged.resolve() / name))
        self.assertTrue(all(str(alias) not in value for value in command))

    def test_guards_block_real_processes_and_network(self):
        for event in ("subprocess.Popen", "os.system", "os.fork", "socket.connect", "socket.bind", "socket.getaddrinfo"):
            with self.subTest(event=event), self.assertRaises(PermissionError):
                checks.guard_event(event, (), ROOT, self.root)

    def test_guards_keep_data_and_writes_in_fixtures(self):
        for event, arguments in (("open", (ROOT / "data/workspace.sqlite3", "r", 0)),
                                 ("open", (ROOT / ".env", "r", 0)),
                                 ("open", (ROOT / "server.py", "w", 0)),
                                 ("sqlite3.connect", (ROOT / "new.db",))):
            with self.subTest(event=event), self.assertRaises(PermissionError):
                checks.guard_event(event, arguments, ROOT, self.root)
        checks.guard_event("open", (self.root / "fixture.txt", "w", 0), ROOT, self.root)

    def test_sqlite_file_uri_is_confined_to_fixture(self):
        checks.guard_event("sqlite3.connect", ((self.root / "with space.db").as_uri() + "?mode=ro",), ROOT, self.root)
        with self.assertRaises(PermissionError):
            checks.guard_event("sqlite3.connect", ((ROOT / "data/private.db").as_uri() + "?mode=ro",), ROOT, self.root)

    def test_directory_fd_cleanup_resolves_the_actual_fixture(self):
        descriptor = os.open(self.root, os.O_RDONLY)
        try:
            checks.guard_event("os.remove", ("fixture.txt", descriptor), ROOT, self.root)
            with self.assertRaises(PermissionError):
                checks.guard_event("os.remove", ("../outside.txt", descriptor), ROOT, self.root)
        finally:
            os.close(descriptor)

    def test_system_timezone_symlink_is_read_only(self):
        checks.guard_event("open", (Path("/usr/share/zoneinfo/Australia/Melbourne"), "r", 0), ROOT, self.root)
        with self.assertRaises(PermissionError):
            checks.guard_event("open", (Path("/usr/share/zoneinfo/Australia/Melbourne"), "w", 0), ROOT, self.root)

    def test_node_exception_is_exact_and_permission_restricted(self):
        script = self.root / "static/js/u1-studio-pro.js"
        command = checks.node_command(["node", "-e", "void 0", str(script)], self.root, "/node")
        self.assertIn("--permission", command)
        self.assertIn("--allow-fs-read=" + str(script), command)
        self.assertNotIn("--allow-net", command)
        for args in (["bash", "-c", "anything"], ["node", "-e", "void 0", "/other.js"]):
            with self.assertRaises(PermissionError):
                checks.node_command(args, self.root, "/node")

    def test_studio_acceptance_stdio_pipes_keep_process_confinement(self):
        options = dict(stdin=checks.subprocess.PIPE, stdout=checks.subprocess.PIPE,
                       stderr=checks.subprocess.PIPE, text=True, bufsize=1,
                       env={"PRIVATE_TEST_TOKEN": "must-not-be-inherited"}, cwd="/outside")
        with patch.dict(os.environ, {"HOME": str(self.root), "PRISM_DATA_DIR": str(self.root / "prism")}, clear=True):
            confined = checks.node_launch_options(options, self.root)
        for key in ("stdin", "stdout", "stderr", "text", "bufsize"):
            self.assertEqual(confined[key], options[key])
        self.assertEqual(confined["cwd"], str(self.root))
        self.assertNotIn("PRIVATE_TEST_TOKEN", confined["env"])
        self.assertEqual(confined["env"]["PRISM_DATA_DIR"], str(self.root / "prism"))
        self.assertTrue(confined["close_fds"])
        self.assertFalse(confined["shell"])
        self.assertFalse(confined["start_new_session"])
        for forbidden in ({"shell": True}, {"executable": "/bin/bash"}, {"pass_fds": (99,)}, {"preexec_fn": lambda: None}):
            with self.assertRaises(PermissionError):
                checks.node_launch_options(forbidden, self.root)

    def test_workflow_has_read_only_permissions_and_exact_artifact(self):
        workflow = json.loads((ROOT / checks.WORKFLOW).read_text())
        self.assertEqual(workflow["permissions"], {"contents": "read"})
        self.assertEqual(set(workflow["on"]), {"push", "pull_request", "workflow_dispatch"})
        artifact_steps = []
        for job in workflow["jobs"].values():
            self.assertLessEqual(job["timeout-minutes"], 15)
            for step in job["steps"]:
                if "uses" in step:
                    self.assertRegex(step["uses"], r"^actions/[a-z-]+@[0-9a-f]{40}$")
                if step.get("uses", "").startswith("actions/checkout@"):
                    self.assertFalse(step["with"]["persist-credentials"])
                if step.get("uses", "").startswith("actions/upload-artifact@"):
                    artifact_steps.append(step)
        self.assertEqual(len(artifact_steps), 1)
        self.assertEqual(artifact_steps[0]["with"]["path"], "docs/MAC-RELEASE.md")
        self.assertEqual(artifact_steps[0]["if"], "${{ github.event_name == 'push' }}")
        self.assertFalse(artifact_steps[0]["with"]["include-hidden-files"])
        self.assertEqual(workflow["jobs"]["macos-build"]["needs"], "personal-tests")

    def test_operational_release_modules_are_explicit_not_discovered(self):
        for name in ("operational_safety", "usage_windows", "osint_tools", "media_download",
                     "discovery", "spotify", "connection_preflight"):
            self.assertIn("tests/test_u1_" + name + ".py", checks.TEST_FILES)
        for name in ("daily_flow", "usage_selection", "operational_polish", "operational_navigation"):
            self.assertIn("tests/test_u1_" + name + ".cjs", checks.JS_TESTS)

    def test_discovery_node_helper_is_exact_and_has_no_child_or_network_permission(self):
        command = checks.node_command(["node", "-e", "require('./static/js/u1-discovery-workspace.js')"],
                                      self.root, "/node", "tests/test_u1_discovery.py")
        self.assertIn("--allow-fs-read=" + str(self.root / "static/js/u1-discovery-workspace.js"), command)
        self.assertNotIn("--allow-child-process", command)
        self.assertNotIn("--allow-net", command)
        with self.assertRaises(PermissionError):
            checks.node_command(["node", "-e", "require('./other.js')"], self.root, "/node", "tests/test_u1_discovery.py")

    def test_osint_helper_accepts_resolved_node_but_not_another_source(self):
        script = self.root / "static/js/u1-media-research.js"
        command = checks.node_command(["/node", "-e", "void 0", str(script)], self.root, "/node", "tests/test_u1_osint_tools.py")
        self.assertEqual(command[-1], str(script))
        with self.assertRaises(PermissionError):
            checks.node_command(["/node", "-e", "void 0", "/other.js"], self.root, "/node", "tests/test_u1_osint_tools.py")

    def test_wrapper_health_probe_does_not_depend_on_a_protected_api(self):
        source = (ROOT / "macos/U1OS.swift").read_text()
        self.assertIn('base.appendingPathComponent("healthz")', source)
        self.assertNotIn('base.appendingPathComponent("api/integrations")', source)
        self.assertIn("NavigationPolicy.matchesHealthIdentity(object, root: self.root)", source)
        self.assertIn("self.web.load(URLRequest(url: self.lastLocalURL))", source)

    def test_native_policy_covers_both_locked_and_unlocked_health(self):
        source = (ROOT / "macos/PolicyChecks.swift").read_text()
        for contract in ("locked installation remains ready for unlock shell", "unlocked installation identity",
                         "foreign health identity", "unknown health protocol", "incomplete health identity"):
            self.assertIn(contract, source)

    def test_promotion_keyboard_interrupt_restores_previous_bundle(self):
        old, new = self.bundle("old.app"), self.bundle("new.app")
        (old / "marker").write_text("previous")
        rename = Path.rename
        def interrupt(path, destination):
            if path == new:
                raise KeyboardInterrupt("fixture interruption")
            return rename(path, destination)
        with patch.object(Path, "rename", interrupt), self.assertRaises(KeyboardInterrupt):
            support.promote_bundle(new, old, replace=True)
        self.assertEqual((old / "marker").read_text(), "previous")
        self.assertTrue(new.exists())

    def test_interruption_immediately_after_backup_rename_also_rolls_back(self):
        old, new = self.bundle("old.app"), self.bundle("new.app")
        (old / "marker").write_text("previous")
        rename = Path.rename
        def interrupt(path, destination):
            result = rename(path, destination)
            if path == old:
                raise KeyboardInterrupt("fixture after backup rename")
            return result
        with patch.object(Path, "rename", interrupt), self.assertRaises(KeyboardInterrupt):
            support.promote_bundle(new, old, replace=True)
        self.assertEqual((old / "marker").read_text(), "previous")
        self.assertTrue(new.exists())

    def test_promotion_system_exit_also_restores_previous_bundle(self):
        old, new = self.bundle("old.app"), self.bundle("new.app")
        rename = Path.rename
        def interrupt(path, destination):
            if path == new:
                raise SystemExit("fixture exit")
            return rename(path, destination)
        with patch.object(Path, "rename", interrupt), self.assertRaises(SystemExit):
            support.promote_bundle(new, old, replace=True)
        self.assertTrue(old.exists())
        self.assertTrue(new.exists())

    def test_interruption_after_successful_promotion_preserves_new_app_and_backup(self):
        old, new = self.bundle("old.app"), self.bundle("new.app")
        (old / "marker").write_text("previous")
        (new / "marker").write_text("new")
        rename, backups = Path.rename, []
        def interrupt(path, destination):
            result = rename(path, destination)
            if path == old:
                backups.append(destination)
            if path == new:
                raise KeyboardInterrupt("fixture after promotion")
            return result
        with patch.object(Path, "rename", interrupt), self.assertRaises(KeyboardInterrupt):
            support.promote_bundle(new, old, replace=True)
        self.assertEqual((old / "marker").read_text(), "new")
        self.assertEqual((backups[0] / "marker").read_text(), "previous")

    def test_rollback_never_overwrites_a_concurrent_destination(self):
        old, new = self.bundle("old.app"), self.bundle("new.app")
        rename, backups = Path.rename, []
        def interrupt(path, destination):
            if path == new:
                old.mkdir()
                (old / "concurrent-marker").write_text("do not overwrite")
                raise KeyboardInterrupt("fixture concurrent destination")
            result = rename(path, destination)
            if path == old:
                backups.append(destination)
            return result
        with patch.object(Path, "rename", interrupt), self.assertRaises(KeyboardInterrupt):
            support.promote_bundle(new, old, replace=True)
        self.assertEqual((old / "concurrent-marker").read_text(), "do not overwrite")
        self.assertTrue(backups[0].exists())

    def test_startup_lock_ignores_but_preserves_legacy_orphan_directory(self):
        legacy = self.root / ".u1-os-launch.lock"
        legacy.mkdir()
        with patch.object(launcher, "ROOT", self.root):
            with launcher.startup_lock():
                self.assertTrue(legacy.is_dir())
            with launcher.startup_lock():
                pass
        self.assertTrue(legacy.is_dir())
        self.assertEqual((self.root / ".u1-os-launch.flock").stat().st_mode & 0o777, 0o600)

    def test_startup_kernel_lock_refuses_a_second_owner(self):
        with patch.object(launcher, "ROOT", self.root), launcher.startup_lock():
            with self.assertRaisesRegex(SystemExit, "already in progress"):
                with launcher.startup_lock():
                    self.fail("A second owner must not enter")

    def test_startup_kernel_lock_releases_on_catchable_interruption(self):
        with patch.object(launcher, "ROOT", self.root):
            with self.assertRaises(KeyboardInterrupt):
                with launcher.startup_lock():
                    raise KeyboardInterrupt("fixture only")
            with launcher.startup_lock():
                pass

    def test_startup_lock_rejects_symlink_and_hardlink(self):
        target = self.root / "do-not-modify"
        target.write_text("fixture")
        guard = self.root / ".u1-os-launch.flock"
        with patch.object(launcher, "ROOT", self.root):
            guard.symlink_to(target)
            with self.assertRaises(OSError):
                with launcher.startup_lock():
                    pass
            guard.unlink()
            os.link(target, guard)
            with self.assertRaises(SystemExit):
                with launcher.startup_lock():
                    pass
        self.assertEqual(target.read_text(), "fixture")

    def test_launcher_rechecks_health_after_acquiring_lock_without_spawning(self):
        runtime = self.root / ".runtime/bin/python3"
        runtime.parent.mkdir(parents=True)
        runtime.touch()
        with patch.object(launcher, "ROOT", self.root), \
             patch.object(launcher, "running_here", side_effect=[False, True]) as health, \
             patch.object(launcher.sys, "argv", ["launch_u1.py", "--no-browser"]), \
             patch.object(launcher.subprocess, "Popen", side_effect=AssertionError("No real process")) as spawn:
            launcher.main()
        self.assertEqual(health.call_count, 2)
        spawn.assert_not_called()

    def test_launcher_accepts_only_exact_public_health_identity_locked_or_unlocked(self):
        with patch.object(launcher, "ROOT", self.root):
            identity = launcher.hashlib.sha256(str(self.root.resolve()).encode()).hexdigest()
            for locked in (False, True):
                value = dict(service="u1-os", protocol=1, installation_id=identity, locked=locked)
                with patch.object(launcher.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps(value).encode())) as request:
                    self.assertTrue(launcher.running_here())
                    request.assert_called_once_with(launcher.URL + "/healthz", timeout=1)
            for changes in ({"installation_id": "other"}, {"protocol": True}, {"locked": "true"}, {"service": "other"}):
                with patch.object(launcher.urllib.request, "urlopen", return_value=io.BytesIO(json.dumps({**value, **changes}).encode())):
                    self.assertFalse(launcher.running_here())

    def test_launcher_opens_only_canonical_workspace(self):
        runtime = self.root / ".runtime/bin/python3"
        runtime.parent.mkdir(parents=True)
        runtime.touch()
        with patch.object(launcher, "ROOT", self.root), patch.object(launcher, "running_here", return_value=True), \
             patch.object(launcher.sys, "argv", ["launch_u1.py"]), \
             patch.object(launcher.subprocess, "run") as opener:
            launcher.main()
        opener.assert_called_once_with(["/usr/bin/open", launcher.URL + "/"], check=True)

    def test_open_audit_uses_actual_fixture_directory_descriptor(self):
        descriptor = os.open(self.root, os.O_RDONLY)
        try:
            checks.guard_event("open", ("fixture.txt", None, os.O_WRONLY | os.O_CREAT),
                               ROOT, self.root, open_dir_fd=descriptor)
        finally:
            os.close(descriptor)

    def test_open_audit_rejects_outside_descriptor_traversal_and_symlink(self):
        allowed, outside = self.root / "allowed", self.root / "outside"
        allowed.mkdir(); outside.mkdir()
        (allowed / "redirect").symlink_to(outside, target_is_directory=True)
        inside_fd, outside_fd = os.open(allowed, os.O_RDONLY), os.open(outside, os.O_RDONLY)
        try:
            for path, descriptor in (("file", outside_fd), ("../outside/file", inside_fd),
                                     ("redirect/file", inside_fd), (outside / "file", inside_fd)):
                with self.subTest(path=path), self.assertRaises(PermissionError):
                    checks.guard_event("open", (path, None, os.O_WRONLY | os.O_CREAT),
                                       ROOT, allowed, open_dir_fd=descriptor)
        finally:
            os.close(inside_fd); os.close(outside_fd)

    def test_real_fixture_openat_keeps_original_descriptor_and_nofollow(self):
        directory = os.open(self.root, os.O_RDONLY)
        try:
            descriptor = os.open("openat-fixture", os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                 0o600, dir_fd=directory)
            try:
                os.write(descriptor, b"synthetic openat fixture")
            finally:
                os.close(descriptor)
        finally:
            os.close(directory)
        self.assertEqual((self.root / "openat-fixture").read_bytes(), b"synthetic openat fixture")

    def test_open_context_preserves_arguments_and_restores_after_failure(self):
        context, calls = threading.local(), []
        context.dir_fd = 17
        def original(path, flags, mode, *, dir_fd):
            calls.append((path, flags, mode, dir_fd, context.dir_fd))
            raise OSError("fixture-only open failure")
        flags = os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW
        with self.assertRaises(OSError):
            checks.scoped_open(original, context)(b"fixture", flags, 0o600, dir_fd=23)
        self.assertEqual(calls, [(b"fixture", flags, 0o600, 23, 23)])
        self.assertEqual(context.dir_fd, 17)

    def test_open_context_is_thread_local(self):
        context, observed = threading.local(), []
        context.dir_fd = 17
        def original(path, flags, mode, *, dir_fd):
            observed.append(context.dir_fd)
            return 101  # Synthetic descriptor, never used by the OS.
        def child():
            opened = checks.scoped_open(original, context)
            observed.append(opened("fixture", os.O_RDONLY, dir_fd=23))
            observed.append(context.dir_fd)
        thread = threading.Thread(target=child)
        thread.start(); thread.join(1)
        self.assertFalse(thread.is_alive())
        self.assertEqual(observed, [23, 101, None])
        self.assertEqual(context.dir_fd, 17)

    def test_boundary_and_rounded_gate_additions_are_explicit(self):
        self.assertIn("tests/test_u1_server_boundaries.py", checks.TEST_FILES)
        self.assertIn("tests/test_u1_provider_boundaries.py", checks.TEST_FILES)
        self.assertEqual(checks.JS_TESTS["tests/test_u1_assistant_workspace.js"],
                         ("static/js/u1-assistant-workspace.js",))
        marker, count = checks.JS_CONTRACT_MARKERS["tests/test_u1_assistant_workspace.js"]
        self.assertEqual(count, 7)
        self.assertEqual(checks.javascript_result("tests/test_u1_assistant_workspace.js", 0, marker)["status"], "PASS")
        self.assertEqual(checks.javascript_result("tests/test_u1_assistant_workspace.js", 0, marker.splitlines()[-1])["status"], "FAIL")
        self.assertEqual(checks.JS_TESTS["tests/test_u1_rounded_system.cjs"],
                         ("static/js/u1-rounded-system.js", "static/js/u1-cinematic.js", "static/js/u1-safety.js"))
        self.assertIn("static/js/u1-feedback.js", checks.JS_SYNTAX_FILES)
        for source in ("utils/u1_google.py", "server.py", "launch_u1.py"):
            self.assertIn(source, checks.PYTHON_FILES)


if __name__ == "__main__":
    unittest.main()
