"""Extract real handler methods without importing the live server or its services."""
import ast
import hashlib
import io
import json
import mimetypes
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch
from urllib.parse import unquote, urlsplit

from utils import u1_safety
import utils

ROOT = Path(__file__).resolve().parents[1]
TREE = ast.parse((ROOT / "server.py").read_text(), filename="server.py")
FUNCTIONS = {"public_health_identity", "resolve_static_file", "do_GET", "do_POST", "send_json"}
EXTRACTED = ast.Module(body=[node for node in ast.walk(TREE)
                            if isinstance(node, ast.FunctionDef) and node.name in FUNCTIONS], type_ignores=[])
CODE = compile(ast.fix_missing_locations(EXTRACTED), "server.py", "exec")


class ServerBoundaryTests(unittest.TestCase):
    def setUp(self):
        # Use Python's built-in MIME mappings, never host /etc MIME configuration.
        with patch.object(mimetypes, "knownfiles", []):
            mimetypes.init(files=[])
        self.temp = tempfile.TemporaryDirectory(prefix="u1-server-boundaries-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.static = self.base / "static"
        (self.static / "js").mkdir(parents=True)
        (self.static / "u1os.html").write_text("CANONICAL-UNLOCK-SHELL")
        (self.static / "js/app.js").write_text("LEGITIMATE-ASSET")
        (self.static / "space name.txt").write_text("ENCODED-ASSET")
        self.outside = self.base / "outside-marker.txt"
        self.outside.write_text("SYNTHETIC-OUTSIDE-NOT-USER-DATA")
        self.guards = []
        for owner, name in ((socket, "socket"), (socket, "create_connection"),
                            (subprocess, "Popen"), (subprocess, "run"),
                            (os, "system"), (os, "kill"), (os, "killpg")):
            self.guards.append(self.mock(owner, name, side_effect=AssertionError("No live operation")))
        self.lock = u1_safety.SafetyLock(self.base / "safety", lambda: True, lambda: 1000.0)
        self.mock(self.lock, "start", return_value=None)
        self.mock(u1_safety, "_cancel_spotify_oauth", return_value=None)
        self.mock(u1_safety, "_cancel_google_operations", return_value=None)
        self.mock(u1_safety, "manager", return_value=self.lock)
        self.lock.action(dict(action="configure", confirmed=True, offline=False, minutes=5,
                              passphrase="temporary boundary fixture phrase"))
        self.native = self.mock(utils, "u1_native_routes", types.SimpleNamespace(handle_request=lambda _: False), create=True)
        life = types.ModuleType("utils.u1_life_studio")
        life.handle_request = lambda _: False
        module_patch = patch.dict(sys.modules, {"utils.u1_life_studio": life})
        module_patch.start()
        self.addCleanup(module_patch.stop)
        self.namespace = dict(os=os, json=json, mimetypes=mimetypes, Path=Path,
                              hashlib=hashlib, unquote=unquote, urlsplit=urlsplit,
                              STATIC_DIR=str(self.static), BASE_DIR=str(self.base))
        exec(CODE, self.namespace)

    def mock(self, owner, name, *args, **kwargs):
        patcher = patch.object(owner, name, *args, **kwargs)
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def tearDown(self):
        for guard in self.guards:
            guard.assert_not_called()

    def request(self, path, method="GET", allowed=True):
        class Request:
            def integration_request_allowed(self): return allowed
            def self_origin(self): return "http://127.0.0.1:8788"
            def send_response(self, status): self.status = status
            def send_header(self, key, value): self.response_headers[key] = value
            def end_headers(self): pass
            def send_error(self, status, message):
                self.status = status
                self.wfile.write(message.encode("utf-8"))
        handler = Request()
        handler.path, handler.command = path, method
        handler.status, handler.response_headers = None, {}
        handler.headers = {"Host": "127.0.0.1:8788"}
        handler.rfile, handler.wfile = io.BytesIO(), io.BytesIO()
        handler.send_json = types.MethodType(self.namespace["send_json"], handler)
        self.namespace["do_POST" if method == "POST" else "do_GET"](handler)
        return handler

    def assert_blocked(self, path):
        response = self.request(path)
        self.assertIn(response.status, (403, 404), path)
        self.assertNotIn(b"SYNTHETIC-OUTSIDE", response.wfile.getvalue())
        self.assertNotIn(str(self.base).encode(), response.wfile.getvalue())

    def test_locked_root_serves_canonical_unlock_shell(self):
        response = self.request("/")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.wfile.getvalue(), b"CANONICAL-UNLOCK-SHELL")
        self.assertTrue(self.lock.blocked())

    def test_index_remains_canonical_while_locked(self):
        self.assertEqual(self.request("/index.html").wfile.getvalue(), b"CANONICAL-UNLOCK-SHELL")

    def test_legitimate_asset_prefix_and_cache_query(self):
        for path in ("/js/app.js", "/static/js/app.js", "/js/app.js?v=20260908.7"):
            with self.subTest(path=path):
                response = self.request(path)
                self.assertEqual(response.status, 200)
                self.assertEqual(response.wfile.getvalue(), b"LEGITIMATE-ASSET")

    def test_encoded_legitimate_filename_is_decoded_once(self):
        self.assertEqual(self.request("/space%20name.txt").wfile.getvalue(), b"ENCODED-ASSET")

    def test_raw_parent_traversal_is_blocked_while_locked(self):
        self.assert_blocked("/../outside-marker.txt")

    def test_encoded_parent_traversal_is_blocked(self):
        self.assert_blocked("/%2e%2e/outside-marker.txt")

    def test_encoded_separator_traversal_is_blocked(self):
        self.assert_blocked("/..%2foutside-marker.txt")

    def test_static_prefix_parent_traversal_is_blocked(self):
        for path in ("/static/../outside-marker.txt", "/static/%2e%2e%2foutside-marker.txt"):
            with self.subTest(path=path): self.assert_blocked(path)

    def test_nested_encoded_traversal_never_reads_parent(self):
        for path in ("/%252e%252e/outside-marker.txt", "/%2f..%2foutside-marker.txt",
                     "/js/../../outside-marker.txt"):
            with self.subTest(path=path): self.assert_blocked(path)

    def test_file_symlink_escape_is_blocked(self):
        (self.static / "escape.txt").symlink_to(self.outside)
        self.assert_blocked("/escape.txt")

    def test_directory_symlink_escape_is_blocked(self):
        (self.static / "escape").symlink_to(self.base, target_is_directory=True)
        self.assert_blocked("/escape/outside-marker.txt")

    def test_contained_symlink_asset_stays_available(self):
        (self.static / "alias.js").symlink_to(self.static / "js/app.js")
        self.assertEqual(self.request("/alias.js").wfile.getvalue(), b"LEGITIMATE-ASSET")

    def test_absolute_request_targets_are_rejected(self):
        for path in ("http://example.test/../outside-marker.txt", "//example.test/outside-marker.txt"):
            with self.subTest(path=path): self.assert_blocked(path)

    def test_null_controls_backslashes_and_invalid_utf8_are_rejected(self):
        for path in ("/%00", "/%0a", "/..\\outside-marker.txt", "/%ff"):
            with self.subTest(path=path): self.assert_blocked(path)

    def test_directory_is_not_listed(self):
        self.assertEqual(self.request("/js/").status, 404)

    def test_missing_asset_remains_404(self):
        self.assertEqual(self.request("/missing.js").status, 404)

    def test_locked_health_is_nonsecret_identity_not_unlock(self):
        response = self.request("/healthz")
        self.assertEqual(response.status, 200)
        body = json.loads(response.wfile.getvalue())
        self.assertEqual(set(body), {"service", "protocol", "installation_id", "locked"})
        self.assertEqual(body, dict(service="u1-os", protocol=1, locked=True,
            installation_id=hashlib.sha256(str(self.base).encode("utf-8")).hexdigest()))
        self.assertNotIn(self.lock.token, response.wfile.getvalue().decode())
        self.assertNotIn(str(self.base), response.wfile.getvalue().decode())
        self.assertIn("no-store", response.response_headers["Cache-Control"])
        self.assertTrue(self.lock.blocked())

    def test_unlocked_health_has_same_identity_and_false_lock_status(self):
        before = json.loads(self.request("/healthz").wfile.getvalue())
        self.lock.action(dict(action="unlock", passphrase="temporary boundary fixture phrase"))
        after = json.loads(self.request("/healthz").wfile.getvalue())
        self.assertEqual(before["installation_id"], after["installation_id"])
        self.assertFalse(after["locked"])

    def test_health_rejected_origin_eligibility_returns_403(self):
        self.assertEqual(self.request("/healthz", allowed=False).status, 403)

    def test_health_post_cannot_mutate_or_unlock(self):
        self.assertEqual(self.request("/healthz", method="POST").status, 405)
        self.assertTrue(self.lock.blocked())

    def test_health_contract_is_get_only(self):
        self.assertEqual(self.request("/healthz", method="HEAD").status, 405)

    def test_health_route_is_exact_not_a_prefix_allowlist(self):
        self.assertEqual(self.request("/healthz/other").status, 404)
        self.assertEqual(self.request("/healthz-extra").status, 404)

    def test_protected_apis_and_exports_remain_locked(self):
        for method, path in (("GET", "/api/integrations"), ("GET", "/api/state"),
                             ("GET", "/api/workspace/jobs"), ("POST", "/api/workspace/spotify"),
                             ("POST", "/api/workspace/assistant"), ("GET", "/exports/synthetic.pdf")):
            with self.subTest(path=path, method=method):
                response = self.request(path, method)
                self.assertEqual(response.status, 423)
                self.assertTrue(json.loads(response.wfile.getvalue())["locked"])

    def test_identity_canonicalizes_root_and_has_no_authentication_claim(self):
        identity = self.namespace["public_health_identity"]
        self.assertEqual(identity(self.base), identity(self.base / "static/.."))
        self.assertNotEqual(identity(self.base), identity(self.base / "other"))

    def test_canonical_safety_gate_still_precedes_native_dispatch(self):
        for name in ("do_GET", "do_POST"):
            function = next(node for node in EXTRACTED.body if node.name == name)
            calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]
            gate = min(node.lineno for node in calls if isinstance(node.func, ast.Name) and node.func.id == "gate_request")
            native = min(node.lineno for node in calls if isinstance(node.func, ast.Attribute)
                         and isinstance(node.func.value, ast.Name) and node.func.value.id == "u1_native_routes")
            self.assertLess(gate, native)


if __name__ == "__main__":
    unittest.main(verbosity=2)
