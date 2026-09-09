"""Offline truth/freshness/parser/cache regressions. Network and OS side effects blocked."""
import ast
import io
import itertools
import json
import math
from pathlib import Path
import sys
import threading
import time
import types
import unittest
from contextlib import ExitStack
from unittest.mock import patch

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from utils import news_markets as feeds


class LocalBase:
    def __init__(self, name, config):
        self.config = config
        self.lock = threading.RLock()
        self.data = {}
        self.events = []

    def add_event(self, *args):
        self.events.append(args)

    def dispatch_action(self, *args):
        return {"success": False}


def service(filename, name):
    tree = ast.parse((ROOT / filename).read_text())
    tree.body = [node for node in tree.body if not (
        isinstance(node, ast.ImportFrom) and node.module in {"services.base", "utils"})]
    namespace = {"BaseService": LocalBase, "news_markets": feeds,
                 "macos": types.SimpleNamespace(notify=lambda *a: (_ for _ in ()).throw(AssertionError("OS call")))}
    exec(compile(tree, filename, "exec"), namespace)
    return namespace[name]


Intelligence = service("services/intelligence.py", "IntelligenceService")
Crypto = service("services/crypto.py", "CryptoService")
speech_tree = ast.parse((ROOT / "utils/briefing.py").read_text())
speech_tree.body = [node for node in speech_tree.body if isinstance(node, ast.FunctionDef)
                    and node.name == "synthesize_briefing_speech_text"]
speech_env = {"math": math, "time": time,
              "fetch_state": lambda *a: (_ for _ in ()).throw(AssertionError("Local server call"))}
exec(compile(speech_tree, "briefing-speech", "exec"), speech_env)
speech = speech_env["synthesize_briefing_speech_text"]


def cache_state(limit=256):
    stack = ExitStack()
    for name in ("CACHE", "KEY_LOCKS", "KEY_USERS", "KEY_TOUCHED"):
        stack.enter_context(patch.object(feeds, name, {}))
    stack.enter_context(patch.object(feeds, "MAX_CACHE_KEYS", limit))
    return stack


def rss(link="https://www.bbc.com/news/fixture", count=1):
    row = "<item><title>Fixture only</title><link>" + link + "</link><pubDate>Tue, 08 Sep 2026 09:00:00 +0000</pubDate></item>"
    return ("<rss><channel><title>Fixture</title>" + row * count + "</channel></rss>").encode()


def weather():
    return json.dumps({"current_condition": [{"temp_C": "17", "weatherDesc": [{"value": "Cloudy"}],
        "localObsDateTime": "2026-09-08 07:00 PM", "humidity": "65", "windspeedKmph": "12"}],
        "nearest_area": [{"areaName": [{"value": "Fixture town"}]}]}).encode()


class InformationTruth(unittest.TestCase):
    def setUp(self):
        self.stack = ExitStack()
        self.addCleanup(self.stack.close)
        for target in ("urllib.request.urlopen", "urllib.request.OpenerDirector.open"):
            self.stack.enter_context(patch(target, side_effect=AssertionError("Network prohibited in fixtures")))

    def test_crypto_has_no_sample_market_or_social_data_even_without_setup_mode(self):
        for config in ({}, {"system": {"setup_mode": True}}, {"system": {"setup_mode": False}}):
            value = Crypto(config)
            value.poll()
            self.assertFalse(value.configured)
            self.assertTrue(value.setup_required)
            self.assertEqual(value.status, "unavailable")
            self.assertFalse(value.data["success"])
            for key in ("tokens", "positions", "alpha_tweets", "copy_traders", "price_alerts", "bot_log"):
                self.assertEqual(value.data[key], [])
            self.assertEqual(value.data["portfolio_summary"], {})
            self.assertIsNone(value.data["fetched_at"])

    def test_cold_intelligence_failures_are_not_seeded(self):
        value = Intelligence({})
        with patch.object(feeds, "fetch", side_effect=OSError("offline")):
            self.assertIsNone(value._fetch_weather()["temp_c"])
            self.assertEqual(value._fetch_news(), [])
        self.assertFalse(value.news_status["success"])
        self.assertIsNone(value.weather_cache["condition"])

    def test_failed_intelligence_calls_are_throttled(self):
        for method in ("_fetch_weather", "_fetch_news"):
            value = Intelligence({})
            with patch.object(feeds, "fetch", side_effect=OSError("offline")) as fetch, patch("time.time", return_value=1000):
                for _ in range(4):
                    getattr(value, method)()
                self.assertEqual(fetch.call_count, 1)
            with patch.object(feeds, "fetch", side_effect=OSError("offline")) as fetch, patch("time.time", return_value=1061):
                getattr(value, method)()
                self.assertEqual(fetch.call_count, 1)

    def test_weather_incomplete_numbers_fail_closed(self):
        for temperature in (None, True, "NaN", "Infinity"):
            payload = json.loads(weather())
            payload["current_condition"][0]["temp_C"] = temperature
            with patch.object(feeds, "fetch", return_value=json.dumps(payload).encode()):
                value = Intelligence({})._fetch_weather()
                self.assertFalse(value["success"])
                self.assertIsNone(value["temp_c"])

    def test_weather_retains_real_observation_and_original_success_time(self):
        value = Intelligence({})
        with patch.object(feeds, "fetch", return_value=weather()), patch("time.time", return_value=1000):
            good = value._fetch_weather()
        self.assertEqual(good["temp_c"], 17)
        self.assertEqual(good["city"], "Fixture town")
        self.assertEqual(good["observed_at"], "2026-09-08 07:00 PM")
        self.assertIsNone(good["timezone"])
        self.assertIsNone(good["feels_like"])
        with patch.object(feeds, "fetch", side_effect=OSError()), patch("time.time", return_value=1400):
            stale = value._fetch_weather()
        self.assertFalse(stale["success"])
        self.assertTrue(stale["stale"])
        self.assertEqual(stale["temp_c"], 17)
        self.assertEqual(stale["fetched_at"], 1000)
        self.assertEqual(stale["attempted_at"], 1400)

    def test_changed_weather_location_cannot_reuse_previous_measurement(self):
        value = Intelligence({"intelligence": {"weather_city": "First"}})
        with patch.object(feeds, "fetch", return_value=weather()):
            value._fetch_weather()
        value.config["intelligence"]["weather_city"] = "Second"
        with patch.object(feeds, "fetch", side_effect=OSError()):
            result = value._fetch_weather()
        self.assertIsNone(result["temp_c"])
        self.assertFalse(result["stale"])

    def test_known_news_reuses_shared_adapter(self):
        category, spec = next(iter(feeds.SOURCES.items()))
        value = Intelligence({"intelligence": {"news_feeds": [spec[1]]}})
        with patch.object(feeds, "news", return_value={"success": True, "source": spec[0], "fetched_at": 1000, "items": []}) as shared, patch.object(feeds, "fetch") as fetch:
            value._fetch_news()
        shared.assert_called_once_with(category)
        fetch.assert_not_called()
        self.assertTrue(value.news_status["success"])

    def test_unreviewed_feed_urls_are_rejected_before_fetch(self):
        for url in ("http://127.0.0.1/private", "file:///etc/passwd", "https://example.com/rss"):
            value = Intelligence({"intelligence": {"news_feeds": [url]}})
            with patch.object(feeds, "fetch") as fetch:
                self.assertEqual(value._fetch_news(), [])
            fetch.assert_not_called()
            self.assertFalse(value.news_status["success"])

    def test_retained_news_items_have_stale_metadata(self):
        value = Intelligence({})
        with patch.object(feeds, "fetch", return_value=rss()), patch("time.time", return_value=1000):
            self.assertEqual(len(value._fetch_news()), 1)
        with patch.object(feeds, "fetch", side_effect=OSError()), patch("time.time", return_value=1700):
            result = value._fetch_news()
        self.assertTrue(result[0]["stale"])
        self.assertFalse(value.news_status["success"])
        self.assertEqual(value.news_status["fetched_at"], 1000)

    def test_failed_refresh_actions_do_not_report_success(self):
        value = Intelligence({})
        with patch.object(feeds, "fetch", side_effect=OSError()):
            self.assertFalse(value.dispatch_action("refresh_weather")["success"])
            self.assertFalse(value.dispatch_action("refresh_news")["success"])

    def test_speech_does_not_invent_conditions_balances_or_connectivity(self):
        for state in ({}, {"services": {}}, {"services": None}):
            result = speech(state)
            self.assertIn("Weather unavailable", result)
            self.assertIn("Portfolio value unavailable", result)
            self.assertNotIn("20 degrees", result)
            self.assertNotIn("Clear", result)
            self.assertNotIn("All 9", result)

    def test_speech_uses_only_recent_sourced_weather(self):
        current = {"success": True, "stale": False, "temp_c": 17, "source": "Fixture", "fetched_at": 1000}
        state = {"services": {"intelligence": {"data": {"weather": current}}}}
        with patch("time.time", return_value=1100):
            self.assertIn("17 degrees Celsius", speech(state))
        with patch("time.time", return_value=1400):
            self.assertIn("Weather unavailable", speech(state))
        current["stale"] = True
        with patch("time.time", return_value=1100):
            self.assertIn("Weather unavailable", speech(state))

    def test_xml_declarations_and_utf16_utf32_are_rejected(self):
        xml = '<!DOCTYPE rss [<!ENTITY x "expanded">]><rss><channel><title>&x;</title></channel></rss>'
        for encoding in ("utf-8", "utf-16", "utf-16-le", "utf-16-be", "utf-32"):
            with self.subTest(encoding=encoding), self.assertRaises((ValueError, UnicodeError)):
                feeds.rss_channel(xml.encode(encoding))
        self.assertEqual(feeds.rss_channel(b"\xef\xbb\xbf" + rss()).tag, "channel")

    def test_xml_size_and_wrong_document_rejected(self):
        with patch.object(feeds, "MAX_FEED_BYTES", 10), self.assertRaises(ValueError):
            feeds.rss_channel(rss())
        with self.assertRaises(ValueError):
            feeds.rss_channel(b"<html><channel/></html>")

    def test_news_deduplicates_links_and_rejects_credentials(self):
        with cache_state(), patch.object(feeds, "fetch", return_value=rss(count=3)):
            self.assertEqual(len(feeds.news("technology")["items"]), 1)
        with cache_state(), patch.object(feeds, "fetch", return_value=rss("https://name:secret@www.bbc.com/news/fixture")):
            self.assertEqual(feeds.news("technology")["items"], [])

    def test_story_urls_and_undated_items_fail_safely(self):
        for url in ("javascript:alert(1)", "file:///etc/passwd", "https://localhost/a",
                    "https://127.0.0.1/a", "https://[::1]/a", "https://x:y@bbc.com/a",
                    "https://bbc.com:bad/a", "https://bbc.com.evil.test/a", "https://bbc.com/a\n"):
            self.assertIsNone(feeds.safe_story_url(url, ("bbc.com",)))
        self.assertIsNone(feeds.published_time("not a date"))
        self.assertIsNone(feeds.published_time("Tue, 08 Sep 2026 09:00:00"))

    def test_fetch_disallows_arbitrary_destinations_and_redirects(self):
        for url in ("http://wttr.in/", "https://example.com/", "https://user:secret@wttr.in/"):
            with self.assertRaises(ValueError):
                feeds.fetch(url)
        with self.assertRaises(ValueError):
            feeds.NoRedirect().redirect_request(None, None, 302, "", {}, "https://localhost")

    def test_fetch_bounds_bytes_and_rejects_compression(self):
        class Response(io.BytesIO):
            headers = {}
            def geturl(self):
                return "https://wttr.in/?format=j1"
        for content, headers in ((b"x" * 17, {}), (b"x", {"Content-Encoding": "gzip"})):
            response = Response(content)
            response.headers = headers
            opener = types.SimpleNamespace(open=lambda *a, **k: response)
            with patch.object(feeds, "MAX_FEED_BYTES", 16), patch("urllib.request.build_opener", return_value=opener), self.assertRaises(ValueError):
                feeds.fetch("https://wttr.in/?format=j1")

    def test_failed_cache_preserves_last_good_and_limits_retry(self):
        with cache_state(), patch("time.time", return_value=1000):
            feeds.snapshot("a", 300, lambda: {"items": ["actual fixture"]})
            with patch("time.time", return_value=1400):
                loader = unittest.mock.Mock(side_effect=OSError())
                for _ in range(4):
                    value = feeds.snapshot("a", 300, loader)
                self.assertEqual(loader.call_count, 1)
                self.assertFalse(value["success"])
                self.assertTrue(value["stale"])
                self.assertEqual(value["fetched_at"], 1000)
                self.assertEqual(value["items"], ["actual fixture"])
                self.assertEqual(value["refresh_seconds"], 60)
            with patch("time.time", return_value=1461):
                feeds.snapshot("a", 300, loader)
                self.assertEqual(loader.call_count, 2)

    def test_explicit_provider_failure_is_not_promoted_to_success(self):
        with cache_state():
            self.assertFalse(feeds.snapshot("a", 300, lambda: {"success": False})["success"])

    def test_lru_evicts_all_unused_key_metadata(self):
        with cache_state(2), patch("time.monotonic", side_effect=itertools.count()):
            for key in ("a", "b", "a", "c"):
                feeds.snapshot(key, 300, lambda: {})
            for mapping in (feeds.CACHE, feeds.KEY_LOCKS, feeds.KEY_USERS, feeds.KEY_TOUCHED):
                self.assertEqual(set(mapping), {"a", "c"})

    def test_cache_capacity_never_requires_restart(self):
        with cache_state():
            for key in range(260):
                self.assertTrue(feeds.snapshot(key, 300, lambda: {})["success"])
            self.assertTrue(feeds.snapshot("new-provider", 300, lambda: {})["success"])
            for mapping in (feeds.CACHE, feeds.KEY_LOCKS, feeds.KEY_USERS, feeds.KEY_TOUCHED):
                self.assertLessEqual(len(mapping), 256)

    def test_reserved_or_locked_key_cannot_be_evicted(self):
        with cache_state(1):
            feeds.snapshot("a", 300, lambda: {})
            feeds.KEY_USERS["a"] = 1
            self.assertFalse(feeds.snapshot("b", 300, lambda: {})["success"])
            feeds.KEY_USERS["a"] = 0
            feeds.KEY_LOCKS["a"].acquire()
            try:
                self.assertFalse(feeds.snapshot("b", 300, lambda: {})["success"])
            finally:
                feeds.KEY_LOCKS["a"].release()
            self.assertTrue(feeds.snapshot("b", 300, lambda: {})["success"])


if __name__ == "__main__":
    unittest.main()
