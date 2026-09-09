"""Measurement-floor tests.

The governing rule for this subsystem is that nothing is ever invented, so
most of these tests assert the *absence* of a number as much as its
presence: an unmeasured value must come back as None so the interface can
show NOT MEASURED.
"""
import os as _os
import sys as _sys

_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

import unittest
from unittest.mock import patch

from utils import metrics


class MetricsTests(unittest.TestCase):
    def setUp(self):
        metrics.reset()

    def tearDown(self):
        metrics.reset()

    # -- honesty ------------------------------------------------------
    def test_health_is_none_before_anything_is_measured(self):
        result = metrics.health()
        self.assertIsNone(result["score"])
        self.assertEqual(result["components"], {})
        self.assertIn("NOT MEASURED", result["note"])

    def test_unmeasured_components_are_listed_not_defaulted(self):
        result = metrics.health()
        # startup_ms is a fact of the running process and survives reset(),
        # so it may legitimately already be measured here.
        for component in ("reliability", "performance", "stability"):
            self.assertIn(component, result["unmeasured"])
        self.assertNotIn("reliability", result["components"])

    def test_startup_time_survives_a_reset(self):
        metrics.mark_ready()
        before = metrics.snapshot()["startup_ms"]
        metrics.reset()
        self.assertEqual(metrics.snapshot()["startup_ms"], before)

    def test_empty_snapshot_reports_none_not_zero_for_rates(self):
        snap = metrics.snapshot()
        self.assertIsNone(snap["requests"]["error_rate_pct"])
        self.assertIsNone(snap["requests"]["slowest_p95_ms"])

    def test_resources_declare_themselves_unavailable_without_psutil(self):
        with patch.dict("sys.modules", {"psutil": None}):
            self.assertIsNone(metrics.sample_resources())

    def test_comparison_refuses_without_a_baseline(self):
        result = metrics.compare_to_baseline()
        self.assertFalse(result["success"])
        self.assertFalse(result["available"])

    def test_comparison_marks_unmeasured_fields_rather_than_guessing(self):
        metrics.record_request("/api/state", "GET", 200, 10.0)
        metrics.capture_baseline("t")
        deltas = metrics.compare_to_baseline("t")["deltas"]
        for field in deltas.values():
            if not field["measured"]:
                self.assertIsNone(field["change_pct"])

    # -- recording ----------------------------------------------------
    def test_requests_are_timed_and_grouped_by_endpoint(self):
        for ms in (10.0, 20.0, 30.0):
            metrics.record_request("/api/state", "GET", 200, ms)
        rows = metrics.endpoint_report()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["count"], 3)
        self.assertEqual(rows[0]["endpoint"], "GET /api/state")

    def test_server_errors_count_toward_the_error_rate(self):
        metrics.record_request("/api/action", "POST", 200, 5.0)
        metrics.record_request("/api/action", "POST", 500, 5.0)
        row = metrics.endpoint_report()[0]
        self.assertEqual(row["errors"], 1)
        self.assertEqual(row["error_rate_pct"], 50.0)

    def test_query_strings_are_discarded(self):
        metrics.record_request("/api/state?token=secret", "GET", 200, 1.0)
        self.assertNotIn("secret", str(metrics.endpoint_report()))

    def test_numeric_and_long_segments_are_collapsed(self):
        self.assertEqual(metrics.normalise_path("/api/item/12345"), "/api/item/:n")
        self.assertEqual(metrics.normalise_path("/api/x/" + "a" * 60), "/api/x/:id")

    def test_endpoint_cardinality_is_capped(self):
        for i in range(metrics.MAX_ENDPOINTS + 40):
            metrics.record_request(f"/p{i}", "GET", 200, 1.0)
        self.assertLessEqual(len(metrics.endpoint_report()), metrics.MAX_ENDPOINTS)

    def test_exceptions_are_grouped_with_first_and_last_seen(self):
        metrics.record_exception("ValueError", "services.crypto", "bad")
        metrics.record_exception("ValueError", "services.crypto", "bad again")
        top = metrics.snapshot()["exceptions"]["top"]
        self.assertEqual(len(top), 1)
        self.assertEqual(top[0]["count"], 2)
        self.assertIn("first_seen", top[0])

    def test_frontend_and_backend_faults_are_kept_apart(self):
        metrics.record_exception("TypeError", "app.js:1", "x", origin="frontend")
        metrics.record_exception("OSError", "server.py", "y", origin="backend")
        exceptions = metrics.snapshot()["exceptions"]
        self.assertEqual(len(exceptions["recent_frontend"]), 1)
        self.assertEqual(len(exceptions["recent_backend"]), 1)

    def test_messages_are_truncated(self):
        metrics.record_exception("E", "w", "x" * 5000)
        self.assertLessEqual(len(metrics.snapshot()["exceptions"]["top"][0]["last_message"]), 300)

    def test_sse_sessions_are_counted(self):
        metrics.sse_opened()
        metrics.sse_opened()
        metrics.sse_closed(12.0)
        sse = metrics.snapshot()["sse"]
        self.assertEqual(sse["opened"], 2)
        self.assertEqual(sse["concurrent"], 1)
        self.assertEqual(sse["peak_concurrent"], 2)

    def test_percentiles_reflect_the_samples(self):
        for ms in range(1, 101):
            metrics.record_request("/api/x", "GET", 200, float(ms))
        row = metrics.endpoint_report()[0]
        self.assertEqual(row["max_ms"], 100.0)
        self.assertGreater(row["p95_ms"], row["p50_ms"])

    def test_startup_time_is_recorded_once(self):
        first = metrics.mark_ready()
        second = metrics.mark_ready()
        self.assertEqual(first, second)

    # -- scoring ------------------------------------------------------
    def test_a_clean_workload_scores_higher_than_a_failing_one(self):
        for _ in range(10):
            metrics.record_request("/api/ok", "GET", 200, 20.0)
        good = metrics.health()["score"]
        metrics.reset()
        for _ in range(10):
            metrics.record_request("/api/bad", "GET", 500, 20.0)
        bad = metrics.health()["score"]
        self.assertGreater(good, bad)

    def test_score_is_the_mean_of_measured_components_only(self):
        metrics.record_request("/api/ok", "GET", 200, 20.0)
        result = metrics.health()
        expected = sum(result["components"].values()) / len(result["components"])
        self.assertAlmostEqual(result["score"], round(expected, 1), places=1)

    def test_sse_contributes_no_score_component(self):
        metrics.sse_opened()
        metrics.sse_closed(5.0)
        self.assertNotIn("streams", metrics.health()["components"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
