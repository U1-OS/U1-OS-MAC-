"""Socket-free Safety/HTTP/job rehearsal. Only disposable state and fake work.

Load this exact module with unittest or the explicitly allowlisted release gate.
Do not discover the inherited test suite or instantiate either global manager.
"""
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import urllib.request
import uuid

from utils import u1_assistant, u1_safety, u1_spotify


class MemoryConnection:
    """The stdlib HTTP handler reads/writes bytes, never a network socket."""

    def __init__(self, request):
        self.input = io.BytesIO(request)
        self.output = io.BytesIO()

    def makefile(self, mode, buffering):
        return self.input if mode == "rb" else self.output


class RehearsalHandler(BaseHTTPRequestHandler):
    wbufsize = 1

    def integration_request_allowed(self):
        # The parent server's Origin/Host implementation is outside this fixture.
        return self.server.allowed

    def log_message(self, *args):
        pass

    def finish(self):
        self.wfile.flush()

    def dispatch(self):
        if not u1_safety.gate_request(self):
            return
        self.server.downstream.append((self.command, self.path))
        if u1_assistant.handle_request(self):
            return
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()

    do_GET = dispatch
    do_POST = dispatch


class OperationalSafetyTests(unittest.TestCase):
    PHRASE = "disposable rehearsal passphrase only"

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="u1-operational-safety-")
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.guards = []
        for owner, name in ((socket, "socket"), (socket, "create_connection"),
                            (socket, "getaddrinfo"), (subprocess, "Popen"),
                            (subprocess, "run"), (os, "system"), (os, "kill"),
                            (os, "killpg"), (urllib.request, "urlopen"),
                            (urllib.request.OpenerDirector, "open")):
            self.guards.append(self.mock(owner, name,
                side_effect=AssertionError("Real network/process operation forbidden")))
        self.start_monitor = self.mock(u1_safety.SafetyLock, "start", return_value=None)
        self.now = 1000.0
        self.online = True
        self.probe_calls = 0
        self.lock = u1_safety.SafetyLock(self.base / "safety", self.probe, lambda: self.now)
        self.mock(u1_safety, "manager", side_effect=lambda: self.lock)
        self.spotify = u1_spotify.SpotifyManager(self.base)
        self.mock(u1_spotify, "_instance", self.spotify)
        self.mock(u1_spotify, "manager", side_effect=AssertionError("No Spotify manager startup"))
        self.guards.append(self.mock(u1_spotify, "_http", side_effect=AssertionError("No account calls")))
        self.guards.append(self.mock(u1_spotify, "QuietLoopbackServer", side_effect=AssertionError("No OAuth listener")))
        self.guards.append(self.mock(self.spotify, "_keychain", side_effect=AssertionError("No Keychain calls")))
        placeholder = self.base / "never-run-provider"
        placeholder.write_text("Fake provider placeholder; never execute.\n", encoding="ascii")
        placeholder.chmod(0o700)
        self.jobs = u1_assistant.AssistantManager(self.base / "assistant",
            codex=placeholder, autostart=False, safety_check=lambda: self.lock.blocked())
        self.mock(u1_assistant, "manager", return_value=self.jobs)
        self.release = threading.Event()
        self.started = threading.Event()
        self.executed = []
        self.worker = None
        self.mock(self.jobs, "_execute", side_effect=self.fake_execute)
        self.addCleanup(self.stop_worker)

    def mock(self, owner, name, *args, **kwargs):
        patcher = patch.object(owner, name, *args, **kwargs)
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def tearDown(self):
        for guard in self.guards:
            guard.assert_not_called()
        self.assertFalse(self.lock.started, "Real Safety monitor must never start")

    def probe(self):
        self.probe_calls += 1
        return self.online

    def fake_execute(self, job):
        self.executed.append(job["id"])
        self.started.set()
        if not self.release.wait(2):
            return "failed", "", "Rehearsal worker was not released within two seconds."
        return "succeeded", "Synthetic rehearsal answer, not provider evidence.", None

    def stop_worker(self):
        self.release.set()
        with self.jobs.condition:
            self.jobs.closed = True
            self.jobs.cancel_requested.set()
            self.jobs.condition.notify_all()
        if self.worker is not None:
            self.worker.join(2)
            self.assertFalse(self.worker.is_alive(), "Owned fake worker did not finish")

    def wait_for(self, predicate):
        until = time.monotonic() + 2
        while time.monotonic() < until:
            if predicate():
                return
            threading.Event().wait(.005)
        self.fail("Owned fake queue did not reach the asserted state within two seconds")

    def request(self, path="/api/safety", method="GET", body=None,
                *, token=True, allowed=True, raw=None, headers=None):
        content = raw if raw is not None else (json.dumps(body).encode() if body is not None else b"")
        fields = {"Host": "127.0.0.1:8788", "Origin": "http://127.0.0.1:8788",
                  "Connection": "close", "Content-Type": "application/json",
                  "Content-Length": str(len(content))}
        if token:
            fields["X-U1-Safety"] = self.lock.token
        fields.update(headers or {})
        wire = (method + " " + path + " HTTP/1.1\r\n" +
                "".join(key + ": " + value + "\r\n" for key, value in fields.items()) +
                "\r\n").encode("ascii") + content
        connection = MemoryConnection(wire)
        server = SimpleNamespace(allowed=allowed, downstream=[])
        RehearsalHandler(connection, ("127.0.0.1", 0), server)
        head, payload = connection.output.getvalue().split(b"\r\n\r\n", 1)
        lines = head.decode("iso-8859-1").split("\r\n")
        status = int(lines[0].split()[1])
        response_headers = dict(line.split(": ", 1) for line in lines[1:])
        self.assertEqual(len(payload), int(response_headers["Content-Length"]))
        return SimpleNamespace(status=status, headers=response_headers,
            body=json.loads(payload) if payload else None, downstream=server.downstream)

    def action(self, action, expected=200, **values):
        response = self.request(method="POST", body=dict(action=action, **values))
        self.assertEqual(response.status, expected, response.body)
        self.assertEqual(response.downstream, [])
        self.assertEqual(response.headers["Cache-Control"], "no-store")
        return response.body

    def configure(self, *, offline=True, minutes=5):
        return self.action("configure", confirmed=True, passphrase=self.PHRASE,
                           offline=offline, minutes=minutes)

    def unlock(self):
        return self.action("unlock", passphrase=self.PHRASE)

    def armed_session(self):
        self.configure()
        self.unlock()

    def submit(self):
        return self.jobs.submit(dict(confirmed=True, request_id=uuid.uuid4().hex,
            prompt="Synthetic local rehearsal only", role="Creator", context=[]))["job"]["id"]

    def job(self, identifier):
        return next(item for item in self.jobs.snapshot()["jobs"] if item["id"] == identifier)

    def running_and_queued(self):
        self.armed_session()
        first, second = self.submit(), self.submit()
        self.worker = threading.Thread(target=self.jobs._worker, name="u1-rehearsal-fake-worker", daemon=True)
        self.jobs.worker = self.worker
        self.worker.start()
        self.assertTrue(self.started.wait(2))
        self.assertEqual(self.job(first)["status"], "running")
        self.assertEqual(self.job(second)["status"], "queued")
        return first, second

    def test_unconfigured_status_does_not_arm_or_create_state(self):
        response = self.request()
        self.assertEqual(response.status, 200)
        self.assertFalse(response.body["configured"])
        self.assertFalse(response.body["locked"])
        self.assertFalse(self.lock.path.exists())
        self.start_monitor.assert_not_called()
        self.assertEqual(self.probe_calls, 0)

    def test_setup_requires_explicit_confirmation(self):
        self.action("configure", 400, passphrase=self.PHRASE, offline=True, minutes=5)
        self.assertFalse(self.lock.path.exists())
        self.assertFalse(self.lock.blocked())

    def test_setup_persists_only_private_disposable_hash_and_starts_locked(self):
        self.assertTrue(self.configure()["locked"])
        state = self.lock.path.read_text()
        self.assertNotIn(self.PHRASE, state)
        self.assertNotIn(json.loads(state)["hash"], json.dumps(self.request().body))
        self.assertEqual(self.lock.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.lock.directory.stat().st_mode & 0o777, 0o700)
        self.assertTrue(self.lock.path.is_relative_to(self.base))

    def test_two_consecutive_fake_probe_failures_lock_new_requests(self):
        self.armed_session()
        self.online = False
        self.lock.tick(self.probe())
        self.assertFalse(self.request().body["locked"])
        self.lock.tick(self.probe())
        self.assertTrue(self.request().body["locked"])
        self.assertEqual(self.request("/api/workspace/jobs").status, 423)

    def test_successful_probe_resets_failure_threshold(self):
        self.armed_session()
        for state in (False, True, False):
            self.online = state
            self.lock.tick(self.probe())
            self.assertFalse(self.lock.blocked())
        self.lock.tick(False)
        self.assertTrue(self.lock.blocked())

    def test_disabled_offline_policy_does_not_lock_from_failed_probes(self):
        self.configure(offline=False, minutes=0)
        self.unlock()
        self.online = False
        for _ in range(3):
            self.lock.tick(self.probe())
        self.assertFalse(self.lock.blocked())
        self.assertIsNone(self.request().body["deadline"])

    def test_explicit_browser_offline_signal_locks_without_probe_threshold(self):
        self.armed_session()
        self.assertTrue(self.action("offline")["locked"])
        self.assertEqual(self.lock.network_failures, 0)

    def test_reconnect_reports_online_but_never_unlocks(self):
        self.armed_session()
        self.action("lock")
        self.lock.tick(True)
        state = self.request().body
        self.assertTrue(state["network"])
        self.assertTrue(state["locked"])
        self.assertEqual(self.request("/api/workspace/assistant").status, 423)
        self.assertFalse(self.unlock()["locked"])

    def test_offline_correct_passphrase_is_not_a_successful_unlock(self):
        self.configure()
        self.online = False
        response = self.action("unlock", 400, passphrase=self.PHRASE)
        self.assertFalse(response["success"])
        self.assertTrue(self.lock.blocked())

    def test_status_polling_does_not_renew_checkin_and_exact_expiry_locks(self):
        self.armed_session()
        deadline = self.request().body["deadline"]
        for elapsed in (1, 100, 299):
            self.now = 1000 + elapsed
            self.assertEqual(self.request().body["deadline"], deadline)
            self.assertFalse(self.lock.blocked())
        self.now = deadline
        self.assertEqual(self.request("/api/workspace/jobs").status, 423)
        self.assertIn("expired", self.request().body["reason"])

    def test_explicit_checkin_renews_only_an_unlocked_session(self):
        self.armed_session()
        first = self.request().body["deadline"]
        self.now += 120
        self.assertEqual(self.action("checkin")["deadline"], first + 120)
        self.action("lock")
        self.action("checkin", 400)
        self.assertIsNone(self.request().body["deadline"])

    def test_five_bad_unlocks_rate_limit_correct_phrase_until_sixty_seconds(self):
        self.configure()
        for _ in range(5):
            self.action("unlock", 400, passphrase="wrong rehearsal phrase")
        self.assertEqual(self.request().body["retry_after"], 60)
        self.action("unlock", 400, passphrase=self.PHRASE)
        self.now += 59
        self.assertEqual(self.request().body["retry_after"], 1)
        self.action("unlock", 400, passphrase=self.PHRASE)
        self.now += 1
        self.assertFalse(self.unlock()["locked"])
        self.assertEqual(self.request().body["retry_after"], 0)

    def test_restart_reloads_temp_configuration_locked_with_new_token(self):
        self.armed_session()
        old_token = self.lock.token
        self.lock = u1_safety.SafetyLock(self.lock.directory, self.probe, lambda: self.now)
        self.assertTrue(self.request().body["locked"])
        self.assertNotEqual(self.lock.token, old_token)
        response = self.request(method="POST", body=dict(action="unlock", passphrase=self.PHRASE),
                                headers={"X-U1-Safety": old_token})
        self.assertEqual(response.status, 403)
        self.assertEqual(self.request("/exports/synthetic.pdf").status, 423)
        self.assertFalse(self.unlock()["locked"])

    def test_api_reads_writes_and_exports_block_without_downstream_execution(self):
        self.configure()
        for method, path in (("GET", "/api/workspace/jobs"),
                             ("POST", "/api/workspace/assistant"),
                             ("POST", "/api/workspace/image-provider"),
                             ("GET", "/api/integrations?rehearsal=1"),
                             ("GET", "/exports/synthetic.pdf?token=fake")):
            with self.subTest(method=method, path=path):
                response = self.request(path, method, body={"action": "send"})
                self.assertEqual(response.status, 423)
                self.assertTrue(response.body["locked"])
                self.assertEqual(response.downstream, [])
                self.assertEqual(response.headers["Cache-Control"], "no-store")

    def test_locked_canonical_shell_and_static_assets_remain_reachable(self):
        self.configure()
        for path in ("/", "/static/js/u1-safety.js", "/assets/u1-logo.svg"):
            with self.subTest(path=path):
                response = self.request(path)
                self.assertEqual(response.status, 204)
                self.assertEqual(response.downstream, [("GET", path)])
        self.assertTrue(self.request().body["locked"])

    def test_unlocked_assistant_handler_can_return_disposable_queue(self):
        self.armed_session()
        identifier = self.submit()
        response = self.request("/api/workspace/jobs")
        self.assertEqual(response.status, 200)
        self.assertEqual(response.body["jobs"][0]["id"], identifier)
        self.assertEqual(response.body["jobs"][0]["status"], "queued")
        self.assertEqual(self.executed, [])

    def test_safety_origin_and_csrf_rejections_do_not_unlock(self):
        self.configure()
        for allowed, token in ((False, True), (True, False)):
            with self.subTest(allowed=allowed, token=token):
                response = self.request(method="POST", body=dict(action="unlock", passphrase=self.PHRASE),
                                        allowed=allowed, token=token)
                self.assertEqual(response.status, 403)
                self.assertTrue(self.lock.blocked())
                self.assertEqual(response.downstream, [])
        self.assertEqual(self.request(allowed=False).status, 403)

    def test_invalid_action_bodies_fail_without_unlock(self):
        self.configure()
        for content in (b"{broken", b"[]", b"null", b"{}", b""):
            with self.subTest(content=content):
                response = self.request(method="POST", raw=content)
                self.assertEqual(response.status, 400)
                self.assertTrue(self.lock.blocked())
                self.assertEqual(response.downstream, [])

    def test_lock_during_fake_job_does_not_cancel_it_and_blocks_next_dispatch(self):
        first, second = self.running_and_queued()
        self.action("lock")
        self.assertEqual(self.job(first)["status"], "running")
        self.assertFalse(self.jobs.cancel_requested.is_set())
        self.assertEqual(self.request("/api/workspace/jobs").status, 423)
        self.release.set()
        self.wait_for(lambda: self.job(first)["status"] == "succeeded" and self.jobs.paused)
        self.assertEqual(self.job(second)["status"], "queued")
        self.assertEqual(self.executed, [first])

    def test_pause_is_dispatch_only_and_resume_releases_queued_work(self):
        first, second = self.running_and_queued()
        state = self.action("pause_jobs", confirmed=True)
        self.assertTrue(state["managed_jobs"]["paused"])
        self.assertEqual(self.job(first)["status"], "running")
        self.assertFalse(self.jobs.cancel_requested.is_set())
        self.release.set()
        self.wait_for(lambda: self.job(first)["status"] == "succeeded")
        self.assertEqual(self.job(second)["status"], "queued")
        self.assertFalse(self.action("resume_jobs", confirmed=True)["managed_jobs"]["paused"])
        self.wait_for(lambda: self.job(second)["status"] == "succeeded")
        self.assertEqual(self.executed, [first, second])

    def test_job_controls_require_confirmation_without_state_changes(self):
        self.armed_session()
        identifier = self.submit()
        for action in ("pause_jobs", "resume_jobs", "stop_jobs"):
            with self.subTest(action=action):
                self.action(action, 400)
                self.assertFalse(self.jobs.paused)
                self.assertEqual(self.job(identifier)["status"], "queued")

    def test_locked_pause_and_stop_require_passphrase_and_do_not_unlock(self):
        self.armed_session()
        identifier = self.submit()
        self.action("lock")
        for action in ("pause_jobs", "stop_jobs"):
            self.action(action, 400, confirmed=True, passphrase="wrong rehearsal phrase")
        self.assertFalse(self.jobs.paused)
        self.assertEqual(self.job(identifier)["status"], "queued")
        self.assertTrue(self.action("pause_jobs", confirmed=True, passphrase=self.PHRASE)["managed_jobs"]["paused"])
        self.action("stop_jobs", confirmed=True, passphrase=self.PHRASE)
        self.assertEqual(self.job(identifier)["status"], "cancelled")
        self.assertTrue(self.lock.blocked())

    def test_locked_resume_is_rejected_even_with_correct_passphrase(self):
        self.armed_session()
        self.action("pause_jobs", confirmed=True)
        self.action("lock")
        self.action("resume_jobs", 400, confirmed=True, passphrase=self.PHRASE)
        self.assertTrue(self.jobs.paused)
        self.assertTrue(self.lock.blocked())

    def test_unlock_does_not_silently_resume_an_explicitly_paused_queue(self):
        self.armed_session()
        identifier = self.submit()
        self.action("pause_jobs", confirmed=True)
        self.action("lock")
        self.unlock()
        self.assertTrue(self.jobs.paused)
        self.assertEqual(self.job(identifier)["status"], "queued")
        self.assertEqual(self.executed, [])

    def test_cancel_marks_running_pending_and_queued_final_without_real_signals(self):
        first, second = self.running_and_queued()
        self.action("lock")
        self.action("stop_jobs", confirmed=True, passphrase=self.PHRASE)
        self.assertEqual(self.job(first)["status"], "cancelling")
        self.assertEqual(self.job(second)["status"], "cancelled")
        self.assertTrue(self.jobs.cancel_requested.is_set())
        self.assertNotIn(second, self.jobs.payloads)
        self.release.set()
        self.wait_for(lambda: self.job(first)["status"] == "cancelled")
        self.assertEqual(self.executed, [first])
        self.assertTrue(self.lock.blocked())

    def test_cancel_queued_work_is_idempotent_and_never_executes(self):
        self.armed_session()
        identifier = self.submit()
        for _ in range(2):
            self.action("stop_jobs", confirmed=True)
            self.assertEqual(self.job(identifier)["status"], "cancelled")
        self.assertNotIn(identifier, self.jobs.payloads)
        self.assertEqual(self.executed, [])

    def test_restart_interrupts_pending_jobs_and_does_not_retry_or_unlock(self):
        self.armed_session()
        identifier = self.submit()
        self.lock = u1_safety.SafetyLock(self.lock.directory, self.probe, lambda: self.now)
        restarted = u1_assistant.AssistantManager(self.jobs.root, codex=self.jobs.codex,
            autostart=False, safety_check=lambda: self.lock.blocked())
        state = restarted.snapshot()
        self.assertTrue(state["paused"])
        self.assertEqual(state["jobs"][0]["id"], identifier)
        self.assertEqual(state["jobs"][0]["status"], "interrupted")
        self.assertIsNone(restarted.worker)
        self.assertTrue(self.lock.blocked())
        self.assertEqual(self.executed, [])


    def pending_oauth(self):
        pending = {"stop": threading.Event(), "epoch": self.spotify.epoch}
        self.spotify.pending = pending
        return pending

    def assert_oauth_stopped(self, pending):
        self.assertTrue(pending["stop"].is_set())
        self.assertIsNone(self.spotify.pending)
        self.assertGreater(self.spotify.epoch, pending["epoch"])
        self.assertTrue(self.lock.blocked())
        self.assertFalse(self.request().body["spotify_oauth_cancel_pending"])

    def test_spotify_manual_lock_invalidates_pending_without_assistant_cancellation(self):
        first, second = self.running_and_queued()
        pending = self.pending_oauth()
        self.action("lock")
        self.assert_oauth_stopped(pending)
        self.assertEqual(self.job(first)["status"], "running")
        self.assertEqual(self.job(second)["status"], "queued")
        self.assertFalse(self.jobs.cancel_requested.is_set())

    def test_spotify_monitor_offline_threshold_notifies_only_when_locked(self):
        self.armed_session()
        pending = self.pending_oauth()
        self.lock.tick(False)
        self.assertFalse(pending["stop"].is_set())
        self.lock.tick(False)
        self.assert_oauth_stopped(pending)

    def test_spotify_browser_offline_action_cancels_pending(self):
        self.armed_session()
        pending = self.pending_oauth()
        self.action("offline")
        self.assert_oauth_stopped(pending)

    def test_spotify_checkin_expiry_via_status_cancels_pending(self):
        self.armed_session()
        pending = self.pending_oauth()
        self.now = self.lock.deadline
        self.request()
        self.assert_oauth_stopped(pending)

    def test_spotify_checkin_expiry_via_gate_cancels_pending(self):
        self.armed_session()
        pending = self.pending_oauth()
        self.now = self.lock.deadline
        self.assertEqual(self.request("/exports/synthetic.pdf").status, 423)
        self.assert_oauth_stopped(pending)

    def test_spotify_checkin_expiry_via_tick_cancels_pending(self):
        self.armed_session()
        pending = self.pending_oauth()
        self.now = self.lock.deadline
        self.lock.tick()
        self.assert_oauth_stopped(pending)

    def test_spotify_expired_checkin_action_cancels_even_when_action_raises(self):
        self.armed_session()
        pending = self.pending_oauth()
        self.now = self.lock.deadline
        self.action("checkin", 400)
        self.assert_oauth_stopped(pending)

    def test_spotify_monitor_fault_and_restart_both_cancel_pending(self):
        self.armed_session()
        pending = self.pending_oauth()
        self.lock._monitor_failure()
        self.assert_oauth_stopped(pending)
        self.unlock()
        pending = self.pending_oauth()
        self.lock = u1_safety.SafetyLock(self.lock.directory, self.probe, lambda: self.now)
        self.request()
        self.assert_oauth_stopped(pending)

    def test_spotify_callback_runs_after_outermost_mutex_and_allows_reentry(self):
        self.armed_session()
        pending = self.pending_oauth()
        original = u1_spotify.cancel_all
        acquired = threading.Event()
        def cancel():
            def inspect_mutex():
                if self.lock.mutex.acquire(timeout=.25):
                    acquired.set()
                    self.lock.mutex.release()
            inspector = threading.Thread(target=inspect_mutex)
            inspector.start()
            inspector.join(.5)
            self.assertTrue(acquired.is_set(), "Spotify callback executed under Safety mutex")
            self.assertTrue(self.lock.blocked(), "Callback may safely re-enter Safety")
            original()
        callback = self.mock(u1_spotify, "cancel_all", side_effect=cancel)
        self.action("lock")
        self.assert_oauth_stopped(pending)
        callback.assert_called_once()

    def test_spotify_cancellation_exception_is_visible_and_retried_without_unlock(self):
        self.armed_session()
        pending = self.pending_oauth()
        original = u1_spotify.cancel_all
        callback = self.mock(u1_spotify, "cancel_all", side_effect=RuntimeError("fixture-private-detail"))
        state = self.action("lock")
        self.assertTrue(state["locked"])
        self.assertTrue(state["spotify_oauth_cancel_pending"])
        self.assertIn("pending", state["spotify_oauth_cancel_error"])
        self.assertNotIn("fixture-private-detail", json.dumps(state))
        self.assertFalse(pending["stop"].is_set())
        callback.side_effect = original
        self.lock.tick()
        self.assert_oauth_stopped(pending)
        self.assertIsNone(self.request().body["spotify_oauth_cancel_error"])

    def test_spotify_busy_mutex_defers_bounded_attempt_and_retries(self):
        self.armed_session()
        pending = self.pending_oauth()
        held, release = threading.Event(), threading.Event()
        def hold_provider():
            with self.spotify.lock:
                held.set()
                release.wait(2)
        holder = threading.Thread(target=hold_provider)
        holder.start()
        self.assertTrue(held.wait(1))
        try:
            state = self.action("lock")
            self.assertTrue(state["spotify_oauth_cancel_pending"])
            self.assertFalse(pending["stop"].is_set())
        finally:
            release.set()
            holder.join(2)
        self.assertFalse(holder.is_alive())
        self.lock.tick()
        self.assert_oauth_stopped(pending)

    def test_spotify_successful_notification_is_not_repeated_by_polling(self):
        self.armed_session()
        pending = self.pending_oauth()
        callback = self.mock(u1_spotify, "cancel_all", wraps=u1_spotify.cancel_all)
        self.action("lock")
        for _ in range(3):
            self.request()
            self.lock.blocked()
            self.lock.tick(True)
        self.assert_oauth_stopped(pending)
        callback.assert_called_once()

    def test_spotify_uninitialised_provider_is_not_started_by_lock(self):
        self.armed_session()
        self.mock(u1_spotify, "_instance", None)
        state = self.action("lock")
        self.assertFalse(state["spotify_oauth_cancel_pending"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
