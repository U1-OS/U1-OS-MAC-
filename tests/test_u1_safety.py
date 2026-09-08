"""Isolated application-lock tests. Never arm the operator's real workspace."""
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from utils import u1_safety


class SafetyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.time = [1000.0]
        self.online = True
        self.lock = u1_safety.SafetyLock(Path(self.temp.name) / "safety", lambda: self.online, lambda: self.time[0])
        self.starter = patch.object(self.lock, 'start')
        self.starter.start()
        self.addCleanup(self.starter.stop)

    def configure(self, **kwargs):
        return self.lock.action(dict(action='configure', passphrase='isolated passphrase', confirmed=True, offline=True, minutes=5, **kwargs))

    def unlock(self):
        return self.lock.action({'action': 'unlock', 'passphrase': 'isolated passphrase'})

    def test_unconfigured_is_not_armed_and_emits_no_secret(self):
        state = self.lock.snapshot()
        self.assertFalse(state['configured'])
        self.assertFalse(state['locked'])
        self.assertNotIn('hash', state)
        with self.assertRaises(ValueError):
            self.lock.action({'action': 'lock'})

    def test_setup_requires_confirmation_and_long_passphrase(self):
        for values in ({'passphrase': 'isolated passphrase'}, {'passphrase': 'short', 'confirmed': True}):
            with self.assertRaises(ValueError):
                self.lock.action(dict(action='configure', **values))
        self.assertFalse(self.lock.snapshot()['configured'])

    def test_setup_locks_and_owner_only_hash_persists(self):
        state = self.configure()
        self.assertTrue(state['locked'])
        self.assertEqual(self.lock.path.stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.lock.directory.stat().st_mode & 0o777, 0o700)
        content = self.lock.path.read_text()
        self.assertNotIn('isolated passphrase', content)
        self.assertEqual(len(json.loads(content)['hash']), 64)
        self.assertNotIn(json.loads(content)['hash'], json.dumps(state))

    def test_reconnect_never_unlocks_and_restart_is_locked(self):
        self.configure()
        self.unlock()
        self.lock.action({'action': 'lock'})
        self.lock.tick(True)
        self.assertTrue(self.lock.snapshot()['locked'])
        self.unlock()
        restarted = u1_safety.SafetyLock(self.lock.directory, lambda: True)
        self.assertTrue(restarted.snapshot()['locked'])

    def test_two_network_failures_lock_but_one_does_not(self):
        self.configure()
        self.unlock()
        self.lock.tick(False)
        self.assertFalse(self.lock.blocked())
        self.lock.tick(False)
        self.assertTrue(self.lock.blocked())

    def test_offline_policy_can_be_disabled_with_authentication(self):
        self.configure()
        self.online = False
        with self.assertRaises(ValueError):
            self.unlock()
        with self.assertRaises(ValueError):
            self.lock.action({'action': 'configure', 'passphrase': 'replacement password', 'offline': False, 'confirmed': True})
        self.lock.action({'action': 'configure', 'current_passphrase': 'isolated passphrase', 'passphrase': 'isolated passphrase', 'offline': False, 'minutes': 0, 'confirmed': True})
        self.unlock()
        self.lock.tick(False)
        self.lock.tick(False)
        self.assertFalse(self.lock.blocked())

    def test_passphrase_rate_limit(self):
        self.configure()
        for _ in range(5):
            with self.assertRaises(ValueError):
                self.lock.action({'action': 'unlock', 'passphrase': 'incorrect'})
        with self.assertRaises(ValueError):
            self.unlock()
        self.time[0] += 61
        self.assertFalse(self.unlock()['locked'])

    def test_polling_does_not_extend_deadman_timer(self):
        self.configure()
        self.unlock()
        deadline = self.lock.snapshot()['deadline']
        for _ in range(3):
            self.time[0] += 99
            self.assertEqual(self.lock.snapshot()['deadline'], deadline)
        self.time[0] += 4
        self.assertTrue(self.lock.blocked())
        with self.assertRaises(ValueError):
            self.lock.action({'action': 'checkin'})

    def test_checkin_explicitly_renews_deadline(self):
        self.configure()
        self.unlock()
        first = self.lock.snapshot()['deadline']
        self.time[0] += 100
        second = self.lock.action({'action': 'checkin'})['deadline']
        self.assertEqual(second, first + 100)

    def test_invalid_config_fails_closed(self):
        self.lock.directory.mkdir()
        self.lock.path.write_text('{broken')
        broken = u1_safety.SafetyLock(self.lock.directory)
        self.assertTrue(broken.blocked())
        with self.assertRaises(ValueError):
            broken.action({'action': 'configure', 'passphrase': 'new password', 'confirmed': True})

    def test_symlink_config_fails_closed(self):
        self.lock.directory.mkdir()
        other = Path(self.temp.name) / 'other'
        other.write_text('{}')
        self.lock.path.symlink_to(other)
        self.assertTrue(u1_safety.SafetyLock(self.lock.directory).blocked())

    def test_gate_locks_other_api_and_checks_origin_and_csrf(self):
        class Handler:
            command = 'GET'
            path = '/api/integrations'
            headers = {}
            close_connection = False
            def __init__(self):
                self.rfile = io.BytesIO()
                self.wfile = io.BytesIO()
                self.allowed = True
                self.code = None
            def integration_request_allowed(self): return self.allowed
            def send_response(self, code): self.code = code
            def send_header(self, *args): pass
            def end_headers(self): pass
        self.configure()
        with patch.object(u1_safety, 'manager', return_value=self.lock):
            blocked = Handler()
            self.assertFalse(u1_safety.gate_request(blocked))
            self.assertEqual(blocked.code, 423)
            static = Handler()
            static.path = '/assets/u1-logo.svg'
            self.assertTrue(u1_safety.gate_request(static))
            for allowed, method in ((False, 'GET'), (True, 'POST')):
                rejected = Handler()
                rejected.path = '/api/safety'
                rejected.allowed = allowed
                rejected.command = method
                self.assertFalse(u1_safety.gate_request(rejected))
                self.assertEqual(rejected.code, 403)
            valid = Handler()
            valid.path = '/api/safety'
            valid.command = 'POST'
            content = json.dumps({'action':'unlock','passphrase':'isolated passphrase'}).encode()
            valid.headers = {'X-U1-Safety': self.lock.token, 'Content-Length': str(len(content))}
            valid.rfile = io.BytesIO(content)
            self.assertFalse(u1_safety.gate_request(valid))
            self.assertEqual(valid.code, 200)
            self.assertFalse(json.loads(valid.wfile.getvalue())['locked'])


if __name__ == '__main__':
    unittest.main()
