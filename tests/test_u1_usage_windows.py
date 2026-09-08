"""Pure allowance contract tests. Never starts an account client or the server."""
import math
import unittest

from utils.u1_usage_windows import normalize_rate_limits


def bucket(ident, used=35, name=None):
    return {"limitId": ident, "limitName": name,
            "primary": {"usedPercent": used, "windowDurationMins": 10080,
                        "resetsAt": 2000000000}}


class UsageWindowsTests(unittest.TestCase):
    def test_general_allowance_precedes_other_models(self):
        result = normalize_rate_limits({"rateLimitsByLimitId": {
            "spark": bucket("spark", 0, "GPT-5.3-Codex-Spark"),
            "codex": bucket("codex")}})
        self.assertEqual([row["limit_id"] for row in result], ["codex", "spark"])
        self.assertEqual([row["used_percent"] for row in result], [35, 0])

    def test_legacy_fills_missing_general_bucket(self):
        result = normalize_rate_limits({"rateLimitsByLimitId": {
            "spark": bucket("spark", 0)}, "rateLimits": bucket("codex", 42)})
        self.assertEqual(result[0]["used_percent"], 42)

    def test_multibucket_wins_over_duplicate_legacy(self):
        result = normalize_rate_limits({"rateLimitsByLimitId": {
            "codex": bucket("codex", 35)}, "rateLimits": bucket("codex", 80)})
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["used_percent"], 35)

    def test_no_general_quota_is_invented(self):
        result = normalize_rate_limits({"rateLimitsByLimitId": {
            "spark": bucket("spark", 0)}})
        self.assertEqual([row["limit_id"] for row in result], ["spark"])

    def test_unknown_and_invalid_percentages_stay_unknown(self):
        for value in (None, True, "35", -1, 101, math.nan, math.inf):
            with self.subTest(value=value):
                result = normalize_rate_limits({"rateLimits": bucket("codex", value)})
                self.assertIsNone(result[0]["used_percent"])

    def test_zero_is_real_usage(self):
        result = normalize_rate_limits({"rateLimits": bucket("codex", 0)})
        self.assertEqual(result[0]["used_percent"], 0)

    def test_primary_secondary_remain_separate(self):
        data = bucket("codex", 20)
        data["secondary"] = {"usedPercent": 60, "windowDurationMins": 300,
                             "resetsAt": 2000000001}
        result = normalize_rate_limits({"rateLimits": data})
        self.assertEqual([row["period"] for row in result], ["primary", "secondary"])
        self.assertEqual([row["used_percent"] for row in result], [20, 60])

    def test_invalid_payloads_are_empty(self):
        for value in (None, [], "bad", {}, {"rateLimitsByLimitId": []},
                      {"rateLimitsByLimitId": {"codex": None}}):
            self.assertEqual(normalize_rate_limits(value), [])


if __name__ == "__main__":
    unittest.main()
