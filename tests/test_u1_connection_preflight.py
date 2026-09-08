"""Preflight tests use temporary public metadata; never live provider state."""
import io
import json
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from utils import u1_connection_preflight as preflight


class Handler:
    def __init__(self, method='GET', path='/api/workspace/activation', allowed=True):
        self.command, self.path, self.allowed = method, path, allowed
        self.headers = {}
        self.wfile = io.BytesIO()
        self.rfile = io.BytesIO(b'not consumed')
        self.response_headers = {}

    def integration_request_allowed(self):
        return self.allowed

    def send_response(self, code):
        self.status = code

    def send_header(self, key, value):
        self.response_headers[key] = value

    def end_headers(self):
        pass


class PreflightTests(unittest.TestCase):
    def setUp(self):
        fixture = tempfile.TemporaryDirectory()
        self.addCleanup(fixture.cleanup)
        self.root = Path(fixture.name)
        self.process = patch('subprocess.run', side_effect=AssertionError('No auth probe')).start()
        self.network = patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('No network')).start()
        patch.dict(os.environ, {'PRISM_DATA_DIR': str(self.root / 'data' / 'prism')}).start()
        self.addCleanup(patch.stopall)

    def snapshot(self):
        return preflight.snapshot(self.root, modules={}, codex_path=self.root / 'codex')

    def database(self):
        directory = self.root / 'data' / 'prism'
        directory.mkdir(parents=True)
        connection = sqlite3.connect(directory / 'workspace.sqlite3')
        connection.execute('CREATE TABLE preferences (key TEXT PRIMARY KEY, value TEXT)')
        connection.execute('INSERT INTO preferences VALUES (?, ?)', ('u1_google_readonly_v1', json.dumps({
            'configured': True, 'last_sync': 1700000000, 'auto_sync': False,
            'messages': [{'subject': 'PRIVATE-MAIL-FIXTURE'}], 'token': 'PRIVATE-TOKEN-FIXTURE'})))
        connection.commit()
        connection.close()
        return directory

    def test_empty_install_stays_unverified_without_side_effects(self):
        data = self.snapshot()
        self.assertTrue(data['read_only'])
        self.assertEqual(data['live_verification'], 'not_performed')
        self.assertFalse((self.root / 'data').exists())
        self.process.assert_not_called()
        self.network.assert_not_called()

    def test_installed_cli_is_not_authorized(self):
        binary = self.root / 'codex'
        binary.write_text('fixture only')
        binary.chmod(0o700)
        encoded = json.dumps(self.snapshot())
        self.assertIn('installed_unverified', encoded)
        self.process.assert_not_called()

    def test_google_projection_never_returns_email_or_tokens(self):
        directory = self.database()
        before = set(directory.iterdir())
        data = preflight._google_metadata(directory)
        self.assertTrue(data['configured'])
        self.assertEqual(data['last_sync'], 1700000000)
        self.assertNotIn('PRIVATE', json.dumps(data))
        self.assertEqual(before, set(directory.iterdir()))

    def test_google_live_wal_is_unknown_not_stale_claim(self):
        directory = self.database()
        (directory / 'workspace.sqlite3-wal').write_bytes(b'fixture-not-a-real-wal')
        self.assertFalse(preflight._google_metadata(directory)['available'])

    def test_image_metadata_only_known_scalars(self):
        directory = self.root / 'data' / 'assistant'
        directory.mkdir(parents=True, mode=0o700)
        path = directory / 'image-provider.json'
        path.write_text(json.dumps({'configured': True, 'updated_at': 1700000000, 'ignored': 'PRIVATE-FIXTURE'}))
        path.chmod(0o600)
        data = preflight._image_metadata(directory)
        self.assertTrue(data['configured'])
        self.assertNotIn('PRIVATE', json.dumps(data))

    def test_image_symlink_not_read(self):
        directory = self.root / 'data' / 'assistant'
        directory.mkdir(parents=True)
        target = self.root / 'fixture.json'
        target.write_text('{"configured":true}')
        (directory / 'image-provider.json').symlink_to(target)
        self.assertFalse(preflight._image_metadata(directory)['available'])

    def test_canva_remains_unfinished(self):
        self.assertIn('unfinished_handoff', json.dumps(self.snapshot()))

    def test_exact_get_route(self):
        with patch.object(preflight, 'snapshot', return_value={'success': True, 'read_only': True}):
            handler = Handler()
            self.assertTrue(preflight.handle_request(handler))
            self.assertEqual(handler.status, 200)
            self.assertEqual(handler.response_headers['Cache-Control'], 'no-store')
            self.assertFalse(preflight.handle_request(Handler(path='/api/workspace/activation/other')))

    def test_post_does_not_record_manual_completion(self):
        handler = Handler('POST')
        self.assertTrue(preflight.handle_request(handler))
        self.assertEqual(handler.status, 405)
        self.assertEqual(handler.rfile.tell(), 0)

    def test_cross_origin_get_denied(self):
        handler = Handler(allowed=False)
        preflight.handle_request(handler)
        self.assertEqual(handler.status, 403)


if __name__ == '__main__':
    unittest.main()
