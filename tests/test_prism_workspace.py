"""Isolated PRISM tests. Never invoke legacy actions or contact providers."""
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
import unittest
from unittest.mock import patch

_bootstrap = tempfile.TemporaryDirectory(prefix="prism-test-bootstrap-")
os.environ.setdefault("PRISM_DATA_DIR", _bootstrap.name)
from utils import prism_workspace as prism


class PrismWorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="prism-unit-")
        self.data_patch = patch.object(prism, "DATA", Path(self.temp.name))
        self.data_patch.start()

    def tearDown(self):
        self.data_patch.stop()
        self.temp.cleanup()

    def get(self, action, query=None):
        return prism.handle_get("/api/workspace/prism/" + action, query or {})

    def post(self, action, body):
        return prism.handle_post("/api/workspace/prism/" + action, body)

    def rejected(self, action, body):
        try:
            result = self.post(action, body)
        except (ValueError, FileNotFoundError):
            return
        self.assertFalse(result.get("success"), result)

    def create(self, kind="project", **fields):
        result = self.post("record", {"kind": kind, "title": "Isolated test record", "payload": fields})
        self.assertTrue(result["success"], result)
        return result

    def test_empty_workspace_and_australian_profile(self):
        result = self.get("summary")
        self.assertTrue(result["success"])
        self.assertEqual(result["records"], [])
        self.assertEqual(result["files"], [])
        self.assertEqual(result["profile"]["country"], "AU")
        self.assertEqual(result["profile"]["city"], "Beveridge, Victoria")
        self.assertEqual(result["profile"]["timezone"], "Australia/Melbourne")
        self.assertEqual(result["storage"]["used"], 0)

    def test_create_edit_and_conflict(self):
        original = self.create(progress=25, status="active")
        record = self.get("summary")["records"][0]
        self.assertEqual(record["id"], original["id"])
        self.assertEqual(record["title"], "Isolated test record")
        self.assertEqual(record["payload"]["progress"], 25)
        edited = self.post("record", {"id": original["id"], "kind": "project", "title": "Renamed", "expected_updated": original["updated"], "payload": {"progress": 80}})
        self.assertTrue(edited["success"], edited)
        self.assertEqual(self.get("summary")["records"][0]["title"], "Renamed")
        self.rejected("record", {"id": original["id"], "kind": "project", "title": "Stale edit", "expected_updated": original["updated"]})

    def test_trash_and_restore(self):
        record = self.create("note", text="Recoverable content")
        self.assertTrue(self.post("trash", {"id": record["id"]})["success"])
        self.assertEqual(self.get("summary")["records"], [])
        self.assertEqual(self.get("trash")["records"][0]["id"], record["id"])
        self.assertTrue(self.post("restore", {"id": record["id"]})["success"])
        self.assertEqual(self.get("summary")["records"][0]["id"], record["id"])

    def test_all_record_types_persist(self):
        self.create("project", progress=0)
        self.create("task", done=False, due="2026-09-09", priority="high")
        self.create("note", text="A real local note", tag="test")
        self.create("event", start="2026-09-09T08:00:00+10:00", end="2026-09-09T09:00:00+10:00")
        self.assertEqual({r["kind"] for r in self.get("summary")["records"]}, {"project", "task", "note", "event"})

    def test_invalid_record_values(self):
        self.rejected("record", {"kind": "unknown", "title": "Test"})
        self.rejected("record", {"kind": "note", "title": ""})
        self.rejected("record", {"kind": "project", "title": "Test", "payload": {"progress": 101}})
        self.rejected("record", {"kind": "project", "title": "Test", "payload": {"progress": float("nan")}})
        self.rejected("record", {"kind": "project", "title": "Test", "payload": {"url": "javascript:alert(1)"}})
        self.rejected("record", {"kind": "event", "title": "Test", "payload": {"start": "2026-09-09T09:00:00Z", "end": "2026-09-09T08:00:00Z"}})

    def test_profile_settings_and_validation(self):
        result = self.post("profile", {"profile": {"name": "PRISM Test", "city": "Beveridge, Victoria", "country": "AU", "timezone": "Australia/Melbourne", "effects": "reduced", "focus": True, "contrast": True}})
        self.assertTrue(result["success"], result)
        profile = self.get("summary")["profile"]
        self.assertEqual(profile["name"], "PRISM Test")
        self.assertTrue(profile["focus"])
        self.assertTrue(profile["contrast"])
        self.rejected("profile", {"profile": {"timezone": "Not/A_Timezone"}})
        self.rejected("profile", {"profile": {"country": "AUS"}})

    def test_file_chunk_roundtrip(self):
        payload = b"PRISM isolated upload test\n"
        start = self.post("upload-start", {"name": "prism-test.txt", "mime": "text/plain", "size": len(payload), "folder": "Test"})
        self.assertTrue(start["success"], start)
        uploaded = self.post("upload-chunk", {"id": start["id"], "offset": 0, "content": base64.b64encode(payload).decode("ascii")})
        self.assertTrue(uploaded["success"], uploaded)
        files = self.get("summary")["files"]
        self.assertEqual(len(files), 1)
        self.assertEqual(files[0]["name"], "prism-test.txt")
        self.assertEqual(files[0]["size"], len(payload))
        result = self.get("file", {"id": [start["id"]]})
        self.assertTrue(result["success"], result)
        self.assertEqual(base64.b64decode(result["content"]), payload)

    def test_upload_rejects_bad_names_and_sizes(self):
        for name in ("../escape.txt", "/tmp/escape.txt", "bad/name.txt", "bad\\name.txt"):
            with self.subTest(name=name):
                self.rejected("upload-start", {"name": name, "size": 1, "mime": "text/plain"})
        for size in (-1, 25 * 1024 * 1024 + 1):
            self.rejected("upload-start", {"name": "test.txt", "size": size, "mime": "text/plain"})

    def test_upload_rejects_out_of_order_and_overrun(self):
        start = self.post("upload-start", {"name": "bounded.txt", "size": 3, "mime": "text/plain"})
        self.assertTrue(start["success"], start)
        self.rejected("upload-chunk", {"id": start["id"], "offset": 1, "content": "YQ=="})
        self.rejected("upload-chunk", {"id": start["id"], "offset": 0, "content": "YWJjZA=="})
        self.rejected("upload-chunk", {"id": start["id"], "offset": 0, "content": "invalid base64!!"})

    def test_export_is_metadata_not_secrets(self):
        self.create("note", text="Exported note")
        result = self.get("export")
        self.assertTrue(result["success"], result)
        text = str(result).lower()
        for private_key in ("csrf_token", "api_key", "access_token", "refresh_token"):
            self.assertNotIn(private_key, text)
        self.assertIn("Exported note", str(result))

    def test_actual_disk_metrics_without_fabricated_gpu(self):
        result = self.get("system")
        self.assertTrue(result["success"], result)
        self.assertNotIn("simulated", str(result).lower())
        self.assertIsNone(result["gpu"])
        self.assertGreater(result["disk"]["total"], 0)

    def test_weather_filters_out_same_named_us_location(self):
        locations = {"results": [
            {"name": "Beveridge", "country_code": "US", "admin1": "California", "latitude": 36.7, "longitude": -117.9},
            {"name": "Beveridge", "country_code": "AU", "admin1": "Victoria", "latitude": -37.47, "longitude": 144.99},
        ]}
        forecast = {"current": {"temperature_2m": 14, "weather_code": 0, "is_day": 1, "time": "2026-09-06T12:00"}, "daily": {}, "timezone": "Australia/Melbourne"}
        with patch.object(prism, "_weather", {}), patch.object(prism, "get_json", side_effect=[locations, forecast]) as request:
            result = prism.weather("Beveridge, Victoria", "AU")
        self.assertTrue(result["success"], result)
        self.assertEqual(result["country"], "AU")
        self.assertEqual(result["region"], "Victoria")
        self.assertIn("countryCode=AU", request.call_args_list[0].args[0])
        self.assertIn("latitude=-37.47", request.call_args_list[1].args[0])

    def test_weather_rejects_wrong_country_without_inventing_values(self):
        locations = {"results": [{"name": "Beveridge", "country_code": "US"}]}
        with patch.object(prism, "_weather", {}), patch.object(prism, "get_json", return_value=locations) as request:
            result = prism.weather("Beveridge, Victoria", "AU")
        self.assertFalse(result["success"])
        self.assertNotIn("current", result)
        self.assertEqual(request.call_count, 1)


if __name__ == "__main__":
    unittest.main()
