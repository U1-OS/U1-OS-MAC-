"""Isolated personal-workflow tests; no providers, live data or account actions.

    python3 -m unittest discover -s tests -p test_u1_personal_core.py -v
"""
import io
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils import u1_personal_core as personal
from utils import prism_workspace as workspace


class Handler:
    def __init__(self, method="GET", path=personal.ENDPOINT, body=None, allowed=True, headers=None, raw=None):
        self.command, self.path, self.allowed = method, path, allowed
        data = raw if raw is not None else json.dumps(body or {}).encode()
        self.rfile, self.wfile = io.BytesIO(data), io.BytesIO()
        self.headers = {"Content-Type": "application/json", "Content-Length": str(len(data)),
                        "X-U1-CSRF": personal.integrations_hub.CSRF_TOKEN}
        self.headers.update(headers or {})
        self.response_headers = {}
        self.status = None
        self.close_connection = False

    def integration_request_allowed(self):
        return self.allowed

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.response_headers[name] = value

    def end_headers(self):
        pass

    def result(self):
        return json.loads(self.wfile.getvalue())


class PersonalCoreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="u1-personal-test-")
        self.addCleanup(self.temp.cleanup)
        self.data_patch = patch.object(workspace, "DATA", Path(self.temp.name))
        self.data_patch.start()
        self.addCleanup(self.data_patch.stop)

    def create(self, kind="contact", title="Local test record", **payload):
        return personal.action({"action": "create", "kind": kind, "title": title, "payload": payload})["record"]

    def change(self, row, command="update", **body):
        return personal.action({"action": command, "id": row["id"], "expected_version": row["version"], **body})

    def current(self, row):
        return personal.snapshot({"id": row["id"], "archived": "all"})["records"][0]

    def assertError(self, body, status=400, code=None):
        with self.assertRaises(personal.PersonalError) as caught:
            personal.action(body)
        self.assertEqual(caught.exception.status, status)
        if code:
            self.assertEqual(caught.exception.code, code)

    def quote(self, symbol="BTC", price="100", currency="AUD", observed=None, basis="manual"):
        return {"symbol": symbol, "currency": currency, "price": price, "observed_at": time.time() if observed is None else observed,
                "source": "Operator-reviewed test observation", "basis": basis}

    def trade(self, account, side="buy", quantity="2", price="100", fees="0", **options):
        return self.change(account, "paper_trade", side=side, quantity=quantity, fees=fees,
                           quote=self.quote(price=price, **options), reviewed=True)

    def test_empty_storage_has_no_seeds_and_uses_only_workspace_db(self):
        state = personal.snapshot()
        self.assertEqual(state["records"], [])
        self.assertEqual(state["paper_trades"], [])
        self.assertEqual(state["paper_balances"], {})
        self.assertEqual(state["count"], 0)
        self.assertEqual(state["timezone"], "Australia/Melbourne")
        self.assertEqual(sorted(p.name for p in Path(self.temp.name).iterdir()), ["workspace.sqlite3"])

    def test_persistence_across_connections_and_partial_update(self):
        row = self.create(organization="Original organization", notes="Retain this")
        updated = self.change(row, title="Renamed", payload={"role": "Owner"})["record"]
        self.assertEqual(updated["version"], 2)
        self.assertEqual(updated["created"], row["created"])
        self.assertEqual(updated["payload"]["notes"], "Retain this")
        conn = sqlite3.connect(Path(self.temp.name) / "workspace.sqlite3")
        try:
            saved = conn.execute("SELECT title,version FROM personal_records WHERE id=?", (row["id"],)).fetchone()
        finally:
            conn.close()
        self.assertEqual(saved, ("Renamed", 2))

    def test_all_types_persist_with_required_fields(self):
        contact = self.create()
        product = self.create("product")
        watch = self.create("watchlist", symbol="BTC")
        offer = self.create("offer", contact_id=contact["id"], scope="A reviewed delivery scope")
        payloads = {
            "priority": {"day": "2026-09-08", "slot": 1},
            "time_block": {"day": "2026-09-08", "start": "09:00", "end": "10:00"},
            "bill": {"due": "2026-09-09"}, "habit": {},
            "launch": {"product_id": product["id"]}, "opportunity": {"hypothesis": "A testable need"},
            "client_project": {"contact_id": contact["id"], "offer_id": offer["id"], "deliverables": "A document"},
            "note": {"parent_id": product["id"], "text": "A private note"},
            "pricing": {"assumptions": "Manual assumptions"}, "content": {}, "video": {},
            "alert": {"watch_id": watch["id"], "threshold": "120"},
            "journal": {"symbol": "BTC", "day": "2026-09-08", "entry_price": "100", "quantity": "1", "thesis": "Paper thesis"},
            "paper_account": {"starting_cash": "1000"},
        }
        for kind, payload in payloads.items():
            with self.subTest(kind=kind):
                row = self.create(kind, **payload)
                self.assertEqual(row["kind"], kind)
                self.assertEqual(row["version"], 1)
        self.assertEqual({r["kind"] for r in personal.snapshot()["records"]}, set(personal.SCHEMAS))

    def test_conflict_does_not_replace_saved_data(self):
        row = self.create()
        self.change(row, title="First editor wins")
        self.assertError({"action": "update", "id": row["id"], "expected_version": 1, "title": "Stale editor"}, 409, "version_conflict")
        self.assertEqual(self.current(row)["title"], "First editor wins")

    def test_concurrent_writers_have_one_winner(self):
        row = self.create()
        barrier = threading.Barrier(2)

        def worker(title):
            barrier.wait(timeout=5)
            try:
                return self.change(row, title=title)["record"]["title"]
            except personal.PersonalError as exc:
                return exc.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, ["Editor A", "Editor B"]))
        self.assertEqual(results.count("version_conflict"), 1)
        self.assertEqual(self.current(row)["version"], 2)

    def test_every_mutation_requires_a_valid_version(self):
        row = self.create()
        for command in ["update", "archive", "restore", "delete", "habit_checkin", "paper_trade", "evaluate_alert"]:
            for version in [None, True, 0, -1, "1", 1.5, 2 ** 60]:
                with self.subTest(command=command, version=version):
                    self.assertError({"action": command, "id": row["id"], "expected_version": version})

    def test_archive_restore_and_confirmed_delete(self):
        row = self.create()
        archived = self.change(row, "archive")["record"]
        self.assertTrue(archived["archived"])
        self.assertEqual(personal.snapshot()["records"], [])
        self.assertEqual(personal.snapshot({"archived": "archived"})["records"][0]["id"], row["id"])
        self.assertError({"action": "delete", "id": row["id"], "expected_version": archived["version"]})
        restored = self.change(archived, "restore")["record"]
        self.assertFalse(restored["archived"])
        archived = self.change(restored, "archive")["record"]
        self.assertTrue(self.change(archived, "delete", confirmed=True)["deleted"])
        self.assertEqual(personal.snapshot({"archived": "all"})["records"], [])

    def test_active_record_cannot_be_permanently_deleted(self):
        row = self.create()
        with self.assertRaises(personal.PersonalError):
            self.change(row, "delete", confirmed=True)

    def test_unknown_kind_fields_actions_and_non_objects_rejected(self):
        for body in [None, [], "value", {"action": []}, {"action": "execute", "command": "do nothing"},
                     {"action": "create", "kind": [], "title": "Test"},
                     {"action": "create", "kind": "contact", "title": "Test", "payload": {"api_key": "not a credential"}},
                     {"action": "create", "kind": "contact", "title": "Test", "payload": []},
                     {"action": "create", "kind": "contact", "title": "Test", "unexpected": True}]:
            with self.subTest(body=body):
                self.assertError(body)
        self.assertEqual(personal.snapshot()["count"], 0)

    def test_scalar_validation_and_non_finite_values(self):
        bad_payloads = [("priority", {"day": "2026-09-08", "slot": True}),
                        ("priority", {"day": "2026-09-08", "slot": 4}),
                        ("priority", {"day": "2026-02-30"}),
                        ("priority", {"day": "2026-09-08", "done": "true"}),
                        ("contact", {"status": []}), ("contact", {"email": "not an email"}),
                        ("bill", {"due": "2026-09-08", "currency": "AU"}),
                        ("bill", {"due": "2026-09-08", "amount": float("nan")}),
                        ("bill", {"due": "2026-09-08", "amount": "Infinity"}),
                        ("bill", {"due": "2026-09-08", "amount": "-1"}),
                        ("bill", {"due": "2026-09-08", "amount": "1e5"}),
                        ("bill", {"due": "2026-09-08", "amount": "1.001"}),
                        ("bill", {"due": "2026-09-08", "amount": "1000000001"}),
                        ("contact", {"notes": "bad\x00control"})]
        for kind, payload in bad_payloads:
            with self.subTest(kind=kind, payload=payload):
                self.assertError({"action": "create", "kind": kind, "title": "Test", "payload": payload})

    def test_priority_slots_are_bounded_and_restore_is_checked(self):
        rows = [self.create("priority", day="2026-09-08", slot=slot) for slot in (1, 2, 3)]
        with self.assertRaises(personal.PersonalError) as caught:
            self.create("priority", day="2026-09-08", slot=1)
        self.assertEqual(caught.exception.code, "priority_conflict")
        archived = self.change(rows[0], "archive")["record"]
        self.create("priority", day="2026-09-08", slot=1)
        with self.assertRaises(personal.PersonalError):
            self.change(archived, "restore")
        self.assertTrue(self.current(archived)["archived"])
        self.create("priority", day="2026-09-09", slot=1)

    def test_concurrent_priority_creation_respects_unique_slot(self):
        barrier = threading.Barrier(2)

        def worker(_):
            barrier.wait(timeout=5)
            try:
                self.create("priority", day="2026-09-08", slot=1)
                return "saved"
            except personal.PersonalError as exc:
                return exc.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(worker, range(2)))
        self.assertCountEqual(result, ["saved", "priority_conflict"])

    def test_time_blocks_validate_order_overlap_and_adjacency(self):
        self.create("time_block", day="2026-09-08", start="09:00", end="10:00")
        self.create("time_block", day="2026-09-08", start="10:00", end="11:00")
        for start, end in [("09:30", "10:30"), ("23:00", "01:00"), ("09:00", "09:00"), ("25:00", "26:00")]:
            with self.subTest(start=start), self.assertRaises(personal.PersonalError):
                self.create("time_block", day="2026-09-08", start=start, end=end)
        self.create("time_block", day="2026-09-09", start="09:00", end="10:00")

    def test_habit_checkins_are_reversible_and_not_punitive(self):
        row = self.create("habit")
        row = self.change(row, "habit_checkin", day="2026-09-01", checked=True)["record"]
        row = self.change(row, "habit_checkin", day="2026-09-08", checked=True)["record"]
        row = self.change(row, "update", payload={"cue": "When I feel ready"})["record"]
        self.assertEqual(row["payload"]["checkins"], ["2026-09-01", "2026-09-08"])
        row = self.change(row, "habit_checkin", day="2026-09-01", checked=False)["record"]
        self.assertEqual(row["payload"]["checkins"], ["2026-09-08"])
        self.assertNotIn("streak", row["payload"])
        with self.assertRaises(personal.PersonalError):
            self.change(row, payload={"checkins": []})

    def test_habit_date_limit_never_evicts_history(self):
        from datetime import date, timedelta
        row = self.create("habit")
        dates = [(date(2025, 1, 1) + timedelta(days=i)).isoformat() for i in range(366)]
        with workspace.database() as conn:
            payload = dict(row["payload"], checkins=dates)
            conn.execute("UPDATE personal_records SET payload=? WHERE id=?", (json.dumps(payload), row["id"]))
        with self.assertRaises(personal.PersonalError) as caught:
            self.change(row, "habit_checkin", day="2026-09-08", checked=True)
        self.assertEqual(caught.exception.code, "checkin_limit")
        self.assertEqual(self.current(row)["payload"]["checkins"], dates)

    def test_reference_validation_and_deletion_preserve_links(self):
        contact = self.create()
        project = self.create("client_project", contact_id=contact["id"], deliverables="A useful delivery")
        archived = self.change(contact, "archive")["record"]
        self.change(project, title="Can edit a historic linked project")
        with self.assertRaises(personal.PersonalError):
            self.create("offer", contact_id=contact["id"], scope="New link to archive")
        with self.assertRaises(personal.PersonalError) as caught:
            self.change(archived, "delete", confirmed=True)
        self.assertEqual(caught.exception.code, "reference_conflict")
        with self.assertRaises(personal.PersonalError):
            self.create("launch", product_id=contact["id"])
        with self.assertRaises(personal.PersonalError):
            self.create("offer", contact_id="a" * 32, scope="Missing client")

    def test_existing_prism_records_are_linked_without_mutation(self):
        canonical = workspace.handle_post("prism/record", {"kind": "task", "title": "Canonical task", "payload": {"notes": "Keep this"}})
        self.create("priority", day="2026-09-08", task_id=canonical["id"])
        saved = workspace.records()
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0]["payload"]["notes"], "Keep this")
        self.assertTrue(any(r["kind"] == "prism:task" for r in personal.snapshot()["references"]))

    def test_product_versions_require_actual_ready_files(self):
        with self.assertRaises(personal.PersonalError):
            self.create("product", versions=[{"version": "v1", "file_id": "b" * 32}])
        upload = workspace.handle_post("prism/upload-start", {"name": "local-product.txt", "size": 0, "mime": "text/plain"})
        workspace.handle_post("prism/upload-chunk", {"id": upload["id"], "offset": 0, "content": ""})
        row = self.create("product", current_version="v1", versions=[{"version": "v1", "file_id": upload["id"], "notes": "Reviewed"}])
        self.assertEqual(row["payload"]["versions"][0]["file_id"], upload["id"])
        with self.assertRaises(personal.PersonalError):
            self.change(row, payload={"current_version": "v2"})

    def test_opportunity_evidence_is_bounded_and_validation_requires_it(self):
        with self.assertRaises(personal.PersonalError):
            self.create("opportunity", hypothesis="An idea", status="validated")
        evidence = {"source": "Reviewed interview", "url": "https://example.com/research", "observed_on": "2026-09-08", "note": "Supports the need"}
        row = self.create("opportunity", hypothesis="An idea", status="validated", evidence=[evidence])
        self.assertEqual(len(row["payload"]["evidence"]), 1)
        with self.assertRaises(personal.PersonalError):
            self.change(row, payload={"evidence": [evidence] * 21})

    def test_urls_reject_active_schemes_credentials_and_bad_ports(self):
        for url in ["javascript:alert(1)", "file:///etc/passwd", "https://user:password@example.com", "https://example.com:invalid", "https://example.com/ bad"]:
            with self.subTest(url=url), self.assertRaises(personal.PersonalError):
                self.create("watchlist", symbol="BTC", source_url=url)

    def test_pricing_uses_decimal_estimates_and_does_not_touch_ledger(self):
        row = self.create("pricing", unit_price="20", unit_cost="5", fixed_cost="100", units=10,
                          hours="2", hourly_rate="25", fee_percent="10", assumptions="Ten assumed units, tax excluded")
        self.assertEqual(row["estimate"]["assumed_sales"], "200.00")
        self.assertEqual(row["estimate"]["assumed_costs"], "220.00")
        self.assertEqual(row["estimate"]["estimated_result"], "-20.00")
        self.assertEqual(row["estimate"]["break_even_units"], 12)
        self.assertEqual(row["estimate"]["basis"], "manual_assumptions_only")
        with workspace.database() as conn:
            self.assertIsNone(conn.execute("SELECT value FROM preferences WHERE key='u1_business_v1'").fetchone())

    def test_pricing_zero_contribution_has_no_false_break_even(self):
        row = self.create("pricing", unit_price="5", unit_cost="5", assumptions="No contribution")
        self.assertIsNone(row["estimate"]["break_even_units"])

    def test_content_and_video_readiness_are_operator_assertions(self):
        with self.assertRaises(personal.PersonalError):
            self.create("content", status="published_manually")
        with self.assertRaises(personal.PersonalError):
            self.create("content", scheduled_time="09:30")
        with self.assertRaises(personal.PersonalError):
            self.create("video", status="ready", script="An operator script")
        row = self.create("video", status="ready", script="An operator script", rights_reviewed=True, content_reviewed=True)
        self.assertEqual(row["payload"]["status"], "ready")
        self.assertNotIn("published", row)

    def test_journal_closed_results_remain_paper_and_dates_validate(self):
        row = self.create("journal", symbol="ABC", day="2026-09-08", status="closed", closed_on="2026-09-09", side="short",
                          entry_price="20", exit_price="15", quantity="2", fees="1", thesis="Manual paper thesis")
        self.assertEqual(row["estimate"]["paper_result"], "9.00")
        with self.assertRaises(personal.PersonalError):
            self.change(row, payload={"closed_on": "2026-09-07"})
        with self.assertRaises(personal.PersonalError):
            self.change(row, payload={"exit_price": ""})

    def test_client_project_cannot_use_another_clients_offer(self):
        a, b = self.create(title="A"), self.create(title="B")
        offer = self.create("offer", contact_id=a["id"], scope="For client A")
        with self.assertRaises(personal.PersonalError):
            self.create("client_project", contact_id=b["id"], offer_id=offer["id"], deliverables="Wrong client")

    def test_search_unicode_literal_wildcards_pagination_and_filters(self):
        self.create(title="Caf\u00e9 review", notes="R\u00c9SUM\u00c9 100%_literal")
        self.create(title="Second record")
        result = personal.snapshot({"q": "r\u00e9sum\u00e9"})
        self.assertEqual(result["total"], 1)
        self.assertEqual(personal.snapshot({"q": "%_literal"})["total"], 1)
        self.assertEqual(personal.snapshot({"q": "' OR 1=1 --"})["total"], 0)
        first = personal.snapshot({"limit": "1"})
        second = personal.snapshot({"limit": "1", "offset": "1"})
        self.assertTrue(first["has_more"])
        self.assertNotEqual(first["records"][0]["id"], second["records"][0]["id"])
        self.assertEqual(personal.snapshot({"collection": "today"})["total"], 0)

    def test_snapshot_rejects_invalid_filters(self):
        for query in [[], {"limit": "201"}, {"limit": "0"}, {"offset": "-1"}, {"q": ["a", "b"]},
                      {"collection": "unknown"}, {"collection": "today", "kind": "offer"}, {"archived": "yes"},
                      {"day": "2026-02-30"}, {"id": "bad"}, {"extra": "ignored"}]:
            with self.subTest(query=query), self.assertRaises(personal.PersonalError):
                personal.snapshot(query)

    def test_limits_reject_without_clearing_records(self):
        row = self.create()
        with patch.object(personal, "MAX_PER_KIND", 1), self.assertRaises(personal.PersonalError):
            self.create()
        with patch.object(personal, "MAX_RECORDS", 1), self.assertRaises(personal.PersonalError):
            self.create("habit")
        with patch.object(personal, "MAX_STORAGE_BYTES", 1), self.assertRaises(personal.PersonalError):
            self.change(row, payload={"notes": "Too much for this patched limit"})
        self.assertEqual(self.current(row)["version"], 1)

    def test_payload_size_and_title_bounds(self):
        with self.assertRaises(personal.PersonalError):
            self.create(title="x" * 161)
        with self.assertRaises(personal.PersonalError):
            self.create(title="   ")
        with self.assertRaises(personal.PersonalError):
            self.create("contact", notes="x" * 8001)
        with patch.object(personal, "MAX_PAYLOAD_BYTES", 10), self.assertRaises(personal.PersonalError):
            self.create()

    def test_export_includes_archive_and_omits_external_credentials(self):
        row = self.create(notes="Private export content")
        self.change(row, "archive")
        with workspace.database() as conn:
            conn.execute("INSERT INTO preferences VALUES('unrelated_secret',?)", (json.dumps({"token": "PRIVATE_DO_NOT_EXPORT"}),))
        result = personal.snapshot(export=True)
        self.assertEqual(result["format"], "u1-personal-workflows")
        self.assertTrue(result["records"][0]["archived"])
        self.assertNotIn("PRIVATE_DO_NOT_EXPORT", json.dumps(result))
        self.assertNotIn("csrf_token", result)
        self.assertFalse(result["has_more"])

    def test_paper_buy_sell_cash_holdings_and_realized_results(self):
        account = self.create("paper_account", starting_cash="1000")
        buy = self.trade(account, quantity="2", price="100", fees="2")
        self.assertEqual(buy["paper_balance"]["cash"], "798.00")
        self.assertEqual(buy["paper_balance"]["holdings"][0]["cost_basis"], "202.00")
        sale = self.trade(buy["record"], side="sell", quantity="1", price="120", fees="1")
        self.assertEqual(sale["paper_balance"]["cash"], "917.00")
        self.assertEqual(sale["paper_balance"]["realized_result"], "18.00")
        self.assertEqual(sale["paper_balance"]["holdings"][0]["quantity"], "1")
        self.assertEqual(sale["paper_balance"]["holdings"][0]["cost_basis"], "101.00")
        self.assertEqual(sale["trade"]["realized_result"], "18.00")
        final = self.trade(sale["record"], side="sell", quantity="1", price="90")
        self.assertEqual(final["paper_balance"]["cash"], "1007.00")
        self.assertEqual(final["paper_balance"]["realized_result"], "7.00")
        self.assertEqual(final["paper_balance"]["holdings"], [])
        state = personal.snapshot(export=True)
        self.assertEqual(len(state["paper_trades"]), 3)
        self.assertEqual(state["paper_balances"][account["id"]]["cash"], "1007.00")

    def test_paper_weighted_cost_basis(self):
        account = self.create("paper_account", starting_cash="1000")
        first = self.trade(account, quantity="1", price="100")
        second = self.trade(first["record"], quantity="1", price="200")
        sale = self.trade(second["record"], side="sell", quantity="1", price="180")
        self.assertEqual(sale["paper_balance"]["realized_result"], "30.00")
        self.assertEqual(sale["paper_balance"]["holdings"][0]["cost_basis"], "150.00")

    def test_paper_negative_cash_shorts_and_currency_conversion_rejected(self):
        account = self.create("paper_account", starting_cash="100")
        for options in [{"quantity": "2", "price": "100"}, {"side": "sell", "quantity": "1", "price": "1"},
                        {"quantity": "1", "price": "1", "currency": "USD"}, {"quantity": "0", "price": "1"},
                        {"quantity": "0.00000001", "price": "0.00000001"}]:
            with self.subTest(options=options), self.assertRaises(personal.PersonalError):
                self.trade(account, **options)
        self.assertEqual(personal.snapshot()["paper_trades"], [])

    def test_paper_review_staleness_and_version_guards(self):
        account = self.create("paper_account", starting_cash="1000")
        with self.assertRaises(personal.PersonalError):
            self.change(account, "paper_trade", side="buy", quantity="1", quote=self.quote(), reviewed=False)
        for observed in [time.time() - 901, time.time() + 60, float("inf"), True]:
            with self.subTest(observed=observed), self.assertRaises(personal.PersonalError):
                self.trade(account, observed=observed)
        self.trade(account, quantity="1")
        with self.assertRaises(personal.PersonalError) as caught:
            self.trade(account, quantity="1")
        self.assertEqual(caught.exception.code, "version_conflict")
        self.assertEqual(len(personal.snapshot()["paper_trades"]), 1)

    def test_paper_accounts_pause_archive_lock_inputs_and_preserve_history(self):
        account = self.create("paper_account", starting_cash="1000")
        account = self.trade(account, quantity="1")["record"]
        for payload in [{"starting_cash": "2000"}, {"currency": "USD"}]:
            with self.assertRaises(personal.PersonalError):
                self.change(account, payload=payload)
        account = self.change(account, payload={"status": "paused"})["record"]
        with self.assertRaises(personal.PersonalError):
            self.trade(account)
        account = self.change(account, "archive")["record"]
        with self.assertRaises(personal.PersonalError) as caught:
            self.change(account, "delete", confirmed=True)
        self.assertEqual(caught.exception.code, "paper_history")
        self.assertEqual(len(personal.snapshot(export=True)["paper_trades"]), 1)

    def test_paper_fill_limit_has_no_partial_balance_change(self):
        account = self.create("paper_account", starting_cash="1000")
        with patch.object(personal, "MAX_PAPER_TRADES", 0), self.assertRaises(personal.PersonalError):
            self.trade(account)
        balance = personal.snapshot()["paper_balances"][account["id"]]
        self.assertEqual(balance["cash"], "1000.00")
        self.assertEqual(balance["trade_count"], 0)
        self.assertEqual(self.current(account)["version"], 1)

    def test_concurrent_paper_fills_cannot_double_spend(self):
        account = self.create("paper_account", starting_cash="100")
        barrier = threading.Barrier(2)

        def worker(_):
            barrier.wait(timeout=5)
            try:
                self.trade(account, quantity="1", price="80")
                return "filled"
            except personal.PersonalError as exc:
                return exc.code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(worker, range(2)))
        self.assertCountEqual(results, ["filled", "version_conflict"])
        self.assertEqual(personal.snapshot()["paper_balances"][account["id"]]["cash"], "20.00")

    def test_paper_accounts_and_currencies_remain_separate(self):
        a = self.create("paper_account", title="AUD paper", starting_cash="500", currency="AUD")
        b = self.create("paper_account", title="USD paper", starting_cash="800", currency="USD")
        self.trade(a, quantity="1", price="100")
        self.trade(b, quantity="1", price="50", currency="USD")
        balances = personal.snapshot()["paper_balances"]
        self.assertEqual(balances[a["id"]]["cash"], "400.00")
        self.assertEqual(balances[b["id"]]["cash"], "750.00")
        with workspace.database() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM records").fetchone()[0], 0)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM preferences").fetchone()[0], 0)

    def test_threshold_crossings_deduplicate_and_rearm_on_nonmatch(self):
        watch = self.create("watchlist", symbol="BTC", currency="AUD")
        alert = self.create("alert", watch_id=watch["id"], threshold="100", status="configured")
        start = time.time() - 10
        quote = self.quote(price="101", observed=start, basis="snapshot")
        first = self.change(alert, "evaluate_alert", quote=quote, reviewed=True)
        self.assertTrue(first["triggered"])
        duplicate = self.change(first["record"], "evaluate_alert", quote=quote, reviewed=True)
        self.assertTrue(duplicate["deduplicated"])
        self.assertEqual(duplicate["version"], first["version"])
        same = self.change(first["record"], "evaluate_alert", quote=self.quote(price="102", observed=start + 1), reviewed=True)
        self.assertFalse(same["triggered"])
        below = self.change(same["record"], "evaluate_alert", quote=self.quote(price="99", observed=start + 2), reviewed=True)
        again = self.change(below["record"], "evaluate_alert", quote=self.quote(price="101", observed=start + 3), reviewed=True)
        self.assertTrue(again["triggered"])
        self.assertEqual(again["record"]["payload"]["trigger_count"], 2)
        edited = self.change(again["record"], payload={"notes": "Keep evaluation evidence"})["record"]
        self.assertEqual(len(edited["payload"]["evaluations"]), 4)

    def test_threshold_rejects_wrong_stale_or_out_of_order_observations(self):
        watch = self.create("watchlist", symbol="BTC")
        alert = self.create("alert", watch_id=watch["id"], threshold="100", status="configured")
        start = time.time() - 10
        saved = self.change(alert, "evaluate_alert", quote=self.quote(observed=start), reviewed=True)["record"]
        for quote in [self.quote(symbol="ETH"), self.quote(currency="USD"), self.quote(observed=start - 1), self.quote(observed=time.time() - 901)]:
            with self.subTest(quote=quote), self.assertRaises(personal.PersonalError):
                self.change(saved, "evaluate_alert", quote=quote, reviewed=True)
        self.assertEqual(self.current(saved)["version"], saved["version"])

    def test_threshold_draft_pause_and_manual_review_are_enforced(self):
        watch = self.create("watchlist", symbol="BTC")
        alert = self.create("alert", watch_id=watch["id"], threshold="100")
        with self.assertRaises(personal.PersonalError):
            self.change(alert, "evaluate_alert", quote=self.quote(), reviewed=True)
        alert = self.change(alert, payload={"status": "configured"})["record"]
        with self.assertRaises(personal.PersonalError):
            self.change(alert, "evaluate_alert", quote=self.quote(), reviewed=False)
        with self.assertRaises(personal.PersonalError):
            self.change(alert, payload={"evaluations": []})

    def test_threshold_history_is_bounded_without_resetting_crossing_count(self):
        watch = self.create("watchlist", symbol="BTC")
        alert = self.create("alert", watch_id=watch["id"], threshold="100", condition="below", status="configured")
        start = time.time() - 100
        for i in range(25):
            alert = self.change(alert, "evaluate_alert", quote=self.quote(price="99" if i % 2 == 0 else "101", observed=start + i), reviewed=True)["record"]
        self.assertEqual(len(alert["payload"]["evaluations"]), 20)
        self.assertEqual(alert["payload"]["trigger_count"], 13)

    def test_http_snapshot_action_and_response_headers(self):
        h = Handler("POST", body={"action": "create", "kind": "contact", "title": "HTTP record"})
        self.assertTrue(personal.handle_request(h))
        self.assertEqual(h.status, 200)
        self.assertTrue(h.result()["success"])
        self.assertEqual(h.response_headers["Cache-Control"], "no-store")
        self.assertEqual(h.response_headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(int(h.response_headers["Content-Length"]), len(h.wfile.getvalue()))
        self.assertTrue(h.close_connection)
        get = Handler(path=personal.ENDPOINT + "/snapshot?collection=clients")
        personal.handle_request(get)
        self.assertEqual(get.result()["total"], 1)
        export = Handler(path=personal.ENDPOINT + "/export")
        personal.handle_request(export)
        self.assertEqual(export.result()["format"], "u1-personal-workflows")

    def test_http_origin_and_csrf_deny_before_body_read_or_db_creation(self):
        for h in [Handler("GET", allowed=False), Handler("POST", allowed=False),
                  Handler("POST", headers={"X-U1-CSRF": "wrong"}), Handler("POST", headers={"X-U1-CSRF": "\u2603"})]:
            personal.handle_request(h)
            self.assertEqual(h.status, 403)
            self.assertEqual(h.rfile.tell(), 0)
        self.assertFalse((Path(self.temp.name) / "workspace.sqlite3").exists())

    def test_http_bounded_json_duplicate_fields_and_content_types(self):
        cases = [({"Content-Length": str(personal.MAX_BODY_BYTES + 1)}, b"{}", 413),
                 ({"Content-Length": "-1"}, b"{}", 411), ({"Content-Length": "0"}, b"", 413),
                 ({"Content-Length": "3"}, b"{}", 400), ({"Content-Type": "text/plain"}, b"{}", 415),
                 ({"Transfer-Encoding": "chunked"}, b"{}", 415), ({}, b"not json", 400),
                 ({}, b'{"action":"create","action":"delete"}', 400), ({}, b"[]", 400),
                 ({}, b'{"action":"create","kind":"contact","title":"T","payload":{"notes":NaN}}', 400)]
        for headers, raw, expected in cases:
            with self.subTest(headers=headers, raw=raw):
                h = Handler("POST", raw=raw, headers=headers)
                personal.handle_request(h)
                self.assertEqual(h.status, expected)
                self.assertFalse(h.result()["success"])

    def test_http_unrelated_paths_fall_through_and_methods_are_restricted(self):
        for path in ["/api/workspace/business", personal.ENDPOINT + "-other", personal.ENDPOINT + "/run"]:
            h = Handler(path=path)
            self.assertFalse(personal.handle_request(h))
            self.assertIsNone(h.status)
        h = Handler("DELETE")
        personal.handle_request(h)
        self.assertEqual(h.status, 405)
        h = Handler("POST", path=personal.ENDPOINT + "/export")
        personal.handle_request(h)
        self.assertEqual(h.status, 405)

    def test_http_conflict_and_storage_failure_are_honest(self):
        row = self.create()
        self.change(row, title="Updated")
        h = Handler("POST", body={"action": "archive", "id": row["id"], "expected_version": 1})
        personal.handle_request(h)
        self.assertEqual(h.status, 409)
        self.assertEqual(h.result()["code"], "version_conflict")
        h = Handler()
        with patch.object(workspace, "database", side_effect=sqlite3.OperationalError("private path detail")):
            personal.handle_request(h)
        self.assertEqual(h.status, 503)
        self.assertNotIn("private path detail", h.wfile.getvalue().decode())


if __name__ == "__main__":
    unittest.main()
