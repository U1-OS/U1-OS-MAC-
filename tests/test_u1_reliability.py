"""Isolated reliability contracts. No real account, Keychain or outbound access."""
import base64
import hashlib
import json
from pathlib import Path
import tempfile
import time
import unittest
import urllib.parse
from unittest.mock import patch
import zipfile

from utils import prism_workspace as workspace
from utils import u1_google as google
from utils import u1_recovery as recovery


class WorkspaceCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.addCleanup(patch.stopall)
        patch.object(workspace, 'DATA', self.root / 'workspace').start()
        patch.object(recovery, 'ROOT', self.root / 'recovery').start()
        patch.object(google, 'keychain', return_value={
            'client_id': 'isolated-test.apps.googleusercontent.com',
            'client_secret': 'test-only', 'refresh_token': 'test-only'
        }).start()
        patch.object(google, 'request', side_effect=AssertionError('Outbound requests are forbidden in this test')).start()
        patch.object(google, 'PENDING', None).start()
        patch.object(google, 'SESSION_VERIFIED', False).start()
        patch.object(google, 'GENERATION', 0).start()
        patch.object(google, 'JOB', None).start()

    def record(self, kind='note', title='Isolated test note', payload=None):
        return workspace.handle_post('prism/record', {
            'kind': kind, 'title': title,
            'payload': payload or {'text': 'Local test content'}
        })

    def upload(self, content=b'Isolated file content'):
        item = workspace.handle_post('prism/upload-start', {
            'name': 'isolated.txt', 'mime': 'text/plain', 'size': len(content), 'folder': 'Tests'
        })
        workspace.handle_post('prism/upload-chunk', {
            'id': item['id'], 'offset': 0,
            'content': base64.b64encode(content).decode()
        })
        return item['id']


class RecoveryTests(WorkspaceCase):
    def test_database_and_file_roundtrip_is_isolated(self):
        self.record()
        file_id = self.upload()
        recovery.make_backup()
        backup = recovery.snapshot()['backups'][0]
        before = (workspace.DATA / 'workspace.sqlite3').read_bytes()
        result = recovery.restore_backup(backup['id'])
        self.assertFalse(result['active_workspace_changed'])
        self.assertEqual(before, (workspace.DATA / 'workspace.sqlite3').read_bytes())
        restored = Path(result['path'])
        self.assertNotEqual(restored, workspace.DATA)
        self.assertEqual((restored / 'files' / file_id).read_bytes(), b'Isolated file content')

    def test_upload_in_progress_blocks_backup(self):
        workspace.handle_post('prism/upload-start', {
            'name': 'pending.txt', 'mime': 'text/plain', 'size': 10, 'folder': 'Tests'
        })
        with self.assertRaises(ValueError):
            recovery.make_backup()

    def test_trashed_abandoned_upload_does_not_block_backup(self):
        item = workspace.handle_post('prism/upload-start', {
            'name': 'abandoned.txt', 'mime': 'text/plain', 'size': 10, 'folder': 'Tests'
        })
        workspace.handle_post('prism/trash', {'id': item['id'], 'kind': 'file'})
        result = recovery.make_backup()
        self.assertIn('backup_id', result)

    def test_backup_rejects_changed_source_content(self):
        file_id = self.upload()
        (workspace.DATA / 'files' / file_id).write_bytes(b'Changed')
        with self.assertRaises(ValueError):
            recovery.make_backup()

    def test_backup_rejects_file_symlink(self):
        file_id = self.upload()
        original = workspace.DATA / 'files' / file_id
        target = self.root / 'external.txt'
        original.rename(target)
        original.symlink_to(target)
        with self.assertRaises((ValueError, OSError)):
            recovery.make_backup()

    def test_restore_rejects_extra_archive_entry(self):
        self.record()
        recovery.make_backup()
        backup = recovery.snapshot()['backups'][0]
        archive = recovery.ROOT / 'backups' / (backup['id'] + '.zip')
        with zipfile.ZipFile(archive, 'a') as zipped:
            zipped.writestr('../outside.txt', 'must not escape')
        with self.assertRaises(ValueError):
            recovery.restore_backup(backup['id'])
        self.assertFalse((recovery.ROOT / 'outside.txt').exists())

    def test_confirmation_required(self):
        with self.assertRaises(ValueError):
            recovery.action({'action': 'backup'})


class GoogleReviewTests(WorkspaceCase):
    def save_events(self, events, bindings=None):
        with workspace.database() as db:
            db.execute('INSERT OR REPLACE INTO preferences(key,value) VALUES (?,?)', (
                'u1_google_readonly_v1', json.dumps({'configured': True, 'events': events, 'bindings': bindings or {}, 'messages': []})
            ))

    def event(self, version='v1', status='confirmed'):
        return {'id': 'google-test-event', 'version': version, 'title': 'Isolated meeting',
                'status': status, 'start': '2026-09-10T10:00:00+10:00',
                'end': '2026-09-10T10:30:00+10:00', 'location': 'Test room', 'notes': '',
                'url': 'https://calendar.google.com/calendar/event?eid=isolated-test'}

    def approve(self, version='v1'):
        return google.action({'action': 'approve_event', 'id': 'google-test-event', 'version': version, 'confirmed': True})

    def test_unconfigured_snapshot_does_not_read_keychain(self):
        with patch.object(google, 'keychain', side_effect=AssertionError('No unsolicited Keychain access')):
            state = google.snapshot()
        self.assertFalse(state['configured'])
        self.assertFalse(state['auto_sync'])

    def test_configuration_is_not_a_verified_connection(self):
        google.action({'action': 'configure', 'client': {'installed': {
            'client_id': 'isolated-test.apps.googleusercontent.com', 'client_secret': 'test-only'
        }}})
        state = google.snapshot()
        self.assertTrue(state['configured'])
        self.assertFalse(state['session_verified'])

    def test_configuration_cannot_replace_pending_sign_in(self):
        google.PENDING = {'status': 'authorising', 'expires': time.time() + 300}
        with self.assertRaises(ValueError):
            google.action({'action': 'configure', 'client': {'installed': {
                'client_id': 'isolated-test.apps.googleusercontent.com', 'client_secret': 'test-only'
            }}})

    def test_configuration_clears_previous_account_snapshot_and_verification(self):
        self.save_events([self.event()])
        google.SESSION_VERIFIED = True
        google.action({'action': 'configure', 'client': {'installed': {
            'client_id': 'isolated-test.apps.googleusercontent.com', 'client_secret': 'test-only'
        }}})
        state = google.snapshot()
        self.assertFalse(state['session_verified'])
        self.assertEqual(state['events'], [])
        self.assertEqual(state['bindings'], {})
        self.assertEqual(google.GENERATION, 1)

    def test_web_client_is_rejected(self):
        with self.assertRaises(ValueError):
            google.action({'action': 'configure', 'client': {'web': {'client_id': 'wrong-kind'}}})

    def test_oauth_uses_pkce_state_and_loopback_without_browser_tokens(self):
        with patch.object(google, 'ThreadingHTTPServer') as server_type, patch.object(google.threading, 'Timer'):
            server_type.return_value.server_port = 43891
            result = google.begin()
        parts = urllib.parse.urlsplit(result['authorization_url'])
        query = urllib.parse.parse_qs(parts.query)
        self.assertEqual(parts.hostname, 'accounts.google.com')
        self.assertEqual(query['code_challenge_method'], ['S256'])
        expected = base64.urlsafe_b64encode(hashlib.sha256(google.PENDING['verifier'].encode()).digest()).rstrip(b'=').decode()
        self.assertEqual(query['code_challenge'], [expected])
        self.assertEqual(query['redirect_uri'], ['http://127.0.0.1:43891/oauth2callback'])
        self.assertGreater(len(query['state'][0]), 30)
        self.assertNotIn('client_secret', query)
        self.assertNotIn('refresh_token', query)

    def test_calendar_requires_confirmation(self):
        self.save_events([self.event()])
        with self.assertRaises(ValueError):
            google.action({'action': 'approve_event', 'id': 'google-test-event', 'version': 'v1'})

    def test_calendar_review_deduplicates(self):
        self.save_events([self.event()])
        self.approve()
        self.approve()
        with workspace.database() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM records WHERE kind='event'").fetchone()[0], 1)

    def test_stale_provider_version_is_rejected(self):
        self.save_events([self.event('v2')])
        with self.assertRaises(ValueError):
            self.approve('v1')

    def test_local_edit_is_not_overwritten_by_provider(self):
        self.save_events([self.event()])
        self.approve()
        state = google.snapshot()
        with workspace.database() as db:
            db.execute("UPDATE records SET title='Local change', updated=updated+10 WHERE kind='event'")
        self.save_events([self.event('v2')], state['bindings'])
        with self.assertRaises(ValueError):
            self.approve('v2')

    def test_cancellation_requires_review_and_trashes_only_local_copy(self):
        self.save_events([self.event()])
        self.approve()
        state = google.snapshot()
        self.save_events([self.event('v2', 'cancelled')], state['bindings'])
        with workspace.database() as db:
            self.assertIsNone(db.execute("SELECT deleted FROM records WHERE kind='event'").fetchone()[0])
        self.approve('v2')
        with workspace.database() as db:
            self.assertIsNotNone(db.execute("SELECT deleted FROM records WHERE kind='event'").fetchone()[0])

    def test_plain_text_mime_is_data_not_html(self):
        payload = {'mimeType': 'multipart/alternative', 'parts': [
            {'mimeType': 'text/html', 'body': {'data': base64.urlsafe_b64encode(b'<script>unsafe()</script>').decode()}},
            {'mimeType': 'text/plain', 'body': {'data': base64.urlsafe_b64encode(b'Review this meeting.').decode()}}
        ]}
        result = google.decode_body(payload)
        self.assertIn('Review this meeting.', str(result))
        self.assertNotIn('<script>', str(result))


if __name__ == '__main__':
    unittest.main()
