"""Temporary fixtures only: all subprocess, network and callback listeners mocked."""
import base64
import hashlib
import io
import json
import os
import tempfile
import time
import types
import unittest
import urllib.parse
from pathlib import Path
from unittest.mock import MagicMock, patch

from utils import u1_spotify as spotify

CLIENT = 'a' * 32
TOKEN = {'access_token': 'fixture-access', 'refresh_token': 'fixture-refresh',
         'scope': spotify.SCOPE, 'expires_at': 9999999999}
RESPONSE = {'access_token': 'fixture-access-new', 'refresh_token': 'fixture-refresh-new',
            'scope': spotify.SCOPE, 'token_type': 'Bearer', 'expires_in': 3600}
TRACK = {'is_playing': True, 'device': {'name': 'Fixture computer'}, 'progress_ms': 12000,
         'item': {'type': 'track', 'name': 'Fixture song', 'artists': [{'name': 'Fixture artist'}],
                  'duration_ms': 180000, 'external_urls': {'spotify': 'https://open.spotify.com/track/ABC123'}}}


class Handler:
    def __init__(self, method='GET', body=None, path=spotify.PATH, allowed=True):
        self.command, self.path, self.allowed = method, path, allowed
        raw = json.dumps(body or {}).encode()
        self.headers = {'Content-Type': 'application/json', 'Content-Length': str(len(raw)), 'X-U1-CSRF': 'fixture-csrf'}
        self.rfile, self.wfile = io.BytesIO(raw), io.BytesIO()
        self.response_headers = {}

    def integration_request_allowed(self):
        return self.allowed

    def send_response(self, code):
        self.status = code

    def send_header(self, key, value):
        self.response_headers[key] = value

    def end_headers(self):
        pass

    def json(self):
        return json.loads(self.wfile.getvalue())


class SpotifyTests(unittest.TestCase):
    def setUp(self):
        fixture = tempfile.TemporaryDirectory()
        self.addCleanup(fixture.cleanup)
        self.root = Path(fixture.name)
        self.manager = spotify.SpotifyManager(self.root)
        self.blocked = patch.object(spotify, '_blocked', return_value=False).start()
        self.http = patch.object(spotify, '_http', side_effect=AssertionError('Network must be explicitly mocked')).start()
        self.process = patch.object(spotify.subprocess, 'run', side_effect=AssertionError('Subprocess must be explicitly mocked')).start()
        self.listener = patch.object(spotify, 'QuietLoopbackServer').start()
        self.listener.return_value.server_port = 49123
        patch.object(spotify.threading.Thread, 'start').start()
        patch.dict('sys.modules', {'utils.integrations_hub': types.SimpleNamespace(CSRF_TOKEN='fixture-csrf')}).start()
        self.addCleanup(patch.stopall)

    def configured(self):
        self.manager._prepare()
        self.manager.helper.write_bytes(b'fixture-not-executable-code')
        self.manager.helper.chmod(0o700)
        self.manager.config = {'client_id': CLIENT, 'credentials_saved': True}
        self.manager.status = 'connected_unchecked'
        self.keychain = patch.object(self.manager, '_keychain', return_value=dict(TOKEN)).start()

    def allow_http(self, *responses):
        self.http.side_effect = list(responses)

    def test_status_is_read_only_and_honestly_setup_needed(self):
        data = self.manager.snapshot()
        self.assertEqual(data['status'], 'setup_needed')
        self.assertFalse(data['connected'])
        self.assertFalse((self.root / 'data').exists())
        self.process.assert_not_called()
        self.http.assert_not_called()
        self.listener.assert_not_called()

    def test_public_setup_does_not_probe_keychain(self):
        self.configured()
        self.manager.config = {}
        result = self.manager.action({'action': 'configure', 'confirmed': True, 'client_id': CLIENT})
        self.assertEqual(result['status'], 'auth_required')
        self.keychain.assert_not_called()
        self.http.assert_not_called()
        self.assertEqual((self.manager.directory / 'config.json').stat().st_mode & 0o777, 0o600)
        self.assertEqual(self.manager.directory.stat().st_mode & 0o777, 0o700)

    def test_confirmation_is_required(self):
        with self.assertRaisesRegex(spotify.SpotifyError, 'confirmation_required'):
            self.manager.action({'action': 'connect'})
        self.listener.assert_not_called()

    def test_safety_prevents_dispatch(self):
        self.blocked.return_value = True
        with self.assertRaisesRegex(spotify.SpotifyError, 'safety_blocked'):
            self.manager.action({'action': 'connect', 'confirmed': True})
        self.http.assert_not_called()

    def test_pkce_and_separate_loopback_callback(self):
        self.configured()
        result = self.manager.action({'action': 'connect', 'confirmed': True})
        query = urllib.parse.parse_qs(urllib.parse.urlsplit(result['authorization_url']).query)
        expected = base64.urlsafe_b64encode(hashlib.sha256(self.manager.pending['verifier'].encode()).digest()).rstrip(b'=').decode()
        self.assertEqual(query['code_challenge'], [expected])
        self.assertEqual(query['scope'], [spotify.SCOPE])
        self.assertEqual(query['redirect_uri'], ['http://127.0.0.1:49123/spotify/callback'])
        self.assertEqual(query['code_challenge_method'], ['S256'])
        self.assertNotIn('verifier', json.dumps(result))
        self.listener.assert_called_once()
        self.keychain.assert_not_called()
        self.http.assert_not_called()

    def begin(self):
        self.configured()
        self.manager.action({'action': 'connect', 'confirmed': True})
        return '/spotify/callback?' + urllib.parse.urlencode({'state': self.manager.pending['state'], 'code': 'fixture-code'})

    def test_callback_exchange_is_single_use(self):
        path = self.begin()
        self.allow_http((200, RESPONSE, 0))
        self.assertTrue(self.manager.callback(path, '127.0.0.1:49123'))
        self.assertFalse(self.manager.callback(path, '127.0.0.1:49123'))
        self.http.assert_called_once()
        self.assertEqual(self.manager.snapshot()['status'], 'connected_unchecked')
        self.assertFalse(self.manager.snapshot()['live_verified'])
        self.assertNotIn('fixture-access', json.dumps(self.manager.snapshot()))
        self.assertNotIn('fixture-access', (self.manager.directory / 'config.json').read_text())

    def test_callback_rejects_wrong_host_state_and_expiry(self):
        path = self.begin()
        self.assertFalse(self.manager.callback(path, 'evil.example'))
        self.assertFalse(self.manager.callback('/spotify/callback?state=' + 'x' * 43 + '&code=fixture', '127.0.0.1:49123'))
        self.manager.pending['deadline'] = 0
        self.assertFalse(self.manager.callback(path, '127.0.0.1:49123'))
        self.http.assert_not_called()

    def test_safety_cancels_pending_callback(self):
        path = self.begin()
        pending = self.manager.pending
        self.manager.cancel()
        self.assertTrue(pending['stop'].is_set())
        self.assertFalse(self.manager.callback(path, '127.0.0.1:49123'))
        self.http.assert_not_called()

    def test_cancel_between_safety_check_and_publication_rejects_listener(self):
        self.configured()
        stop = spotify.threading.Event()
        with patch.object(spotify.threading, 'Event', return_value=stop), \
                patch.object(self.manager, '_allowed', side_effect=lambda epoch: self.manager.cancel()), \
                patch.object(spotify.threading.Thread, 'start') as start:
            with self.assertRaisesRegex(spotify.SpotifyError, 'safety_blocked'):
                self.manager.connect()
        self.assertIsNone(self.manager.pending)
        self.assertTrue(stop.is_set())
        self.assertFalse(self.manager.snapshot()['oauth_pending'])
        self.assertNotEqual(self.manager.status, 'authorization_pending')
        self.listener.return_value.server_close.assert_called_once_with()
        start.assert_not_called()
        self.keychain.assert_not_called()
        self.http.assert_not_called()
        self.process.assert_not_called()

    def test_listener_start_failure_cleans_up_published_pending(self):
        self.configured()
        published = []
        def fail_start():
            published.append(self.manager.pending)
            raise RuntimeError('fixture start failure')
        with patch.object(spotify.threading.Thread, 'start', side_effect=fail_start):
            with self.assertRaisesRegex(RuntimeError, 'fixture start failure'):
                self.manager.connect()
        self.assertEqual(len(published), 1)
        self.assertTrue(published[0]['stop'].is_set())
        self.assertIsNone(self.manager.pending)
        self.assertEqual(self.manager.status, 'auth_required')
        self.listener.return_value.server_close.assert_called_once_with()
        self.keychain.assert_not_called()
        self.http.assert_not_called()
        self.process.assert_not_called()

    def test_204_is_connected_nothing_playing(self):
        self.configured()
        self.allow_http((204, {}, 0))
        data = self.manager.action({'action': 'refresh', 'confirmed': True})
        self.assertEqual(data['status'], 'nothing_playing')
        self.assertTrue(data['connected'])
        self.assertTrue(data['live_verified'])
        self.assertIsNone(data['item'])

    def test_actual_track_and_artist(self):
        self.configured()
        self.allow_http((200, TRACK, 0))
        data = self.manager.refresh()
        self.assertEqual(data['status'], 'playing')
        self.assertEqual(data['item']['title'], 'Fixture song')
        self.assertEqual(data['item']['artist'], 'Fixture artist')
        self.assertEqual(data['item']['progress_ms'], 12000)
        self.assertFalse(data['controls_available'])

    def test_paused_is_not_playing(self):
        self.assertEqual(spotify._playback(dict(TRACK, is_playing=False))[0], 'paused')

    def test_private_session_hides_track(self):
        self.assertEqual(spotify._playback(dict(TRACK, device={'is_private_session': True})), ('private_session', None))

    def test_untrusted_provider_link_is_removed(self):
        payload = dict(TRACK, item=dict(TRACK['item'], external_urls={'spotify': 'javascript:alert(1)'}))
        self.assertIsNone(spotify._playback(payload)[1]['url'])

    def test_age_marks_snapshot_stale_without_network(self):
        self.manager.status = 'playing'
        self.manager.observed_at = time.time() - 50
        data = self.manager.snapshot()
        self.assertEqual(data['status'], 'stale')
        self.assertFalse(data['live_verified'])
        self.http.assert_not_called()

    def test_network_failure_retains_only_stale_evidence(self):
        self.configured()
        self.manager.observed_at = time.time()
        self.manager.item = spotify._playback(TRACK)[1]
        self.http.side_effect = OSError('fixture secret must not escape')
        data = self.manager.refresh()
        self.assertEqual(data['status'], 'stale')
        self.assertFalse(data['live_verified'])
        self.assertNotIn('fixture secret', json.dumps(data))

    def test_rate_limit_cooldown_prevents_more_requests(self):
        self.configured()
        self.allow_http((429, {}, 120))
        data = self.manager.refresh()
        self.assertEqual(data['status'], 'rate_limited')
        self.assertGreater(data['next_refresh_at'], time.time() + 110)
        self.manager.refresh()
        self.http.assert_called_once()

    def test_401_refreshes_once_then_stops(self):
        self.configured()
        self.allow_http((401, {}, 0), (200, RESPONSE, 0), (401, {}, 0))
        data = self.manager.refresh()
        self.assertEqual(data['status'], 'auth_required')
        self.assertFalse(data['connected'])
        self.assertEqual(self.http.call_count, 3)

    def test_refresh_token_rotation_can_be_omitted(self):
        payload = dict(RESPONSE)
        del payload['refresh_token']
        self.assertEqual(spotify._tokens(payload, TOKEN)['refresh_token'], TOKEN['refresh_token'])

    def test_rejects_extra_scope_and_header_injection(self):
        with self.assertRaises(spotify.SpotifyError):
            spotify._tokens(dict(RESPONSE, scope=spotify.SCOPE + ' user-modify-playback-state'))
        with self.assertRaises(spotify.SpotifyError):
            spotify._token_string('fake\r\nHeader: bad')

    def test_disconnect_deletes_locally_without_network(self):
        self.configured()
        self.manager.disconnect()
        self.keychain.assert_called_once_with('delete')
        self.assertFalse(self.manager.snapshot()['credentials_saved'])
        self.http.assert_not_called()

    def test_restart_does_not_infer_authorization(self):
        self.configured()
        self.manager._save()
        restarted = spotify.SpotifyManager(self.root)
        self.assertEqual(restarted.snapshot()['status'], 'auth_required')
        self.assertFalse(restarted.snapshot()['connected'])
        self.process.assert_not_called()

    def test_symlink_metadata_rejected(self):
        self.manager._prepare()
        target = self.root / 'nonsecret.json'
        target.write_text(json.dumps({'client_id': CLIENT}))
        (self.manager.directory / 'config.json').symlink_to(target)
        self.assertEqual(spotify.SpotifyManager(self.root).snapshot()['status'], 'storage_unavailable')

    def test_handler_exact_route_read_only_get(self):
        with patch.object(spotify, 'manager', return_value=self.manager):
            self.assertFalse(spotify.handle_request(Handler(path=spotify.PATH + '/other')))
            handler = Handler()
            self.assertTrue(spotify.handle_request(handler))
            self.assertEqual(handler.status, 200)
            self.assertEqual(handler.response_headers['Cache-Control'], 'no-store')
        self.http.assert_not_called()
        self.process.assert_not_called()

    def test_handler_rejects_cross_origin_and_missing_csrf(self):
        handler = Handler(allowed=False)
        spotify.handle_request(handler)
        self.assertEqual(handler.status, 403)
        handler = Handler('POST', {'action': 'connect', 'confirmed': True})
        handler.headers['X-U1-CSRF'] = 'wrong'
        spotify.handle_request(handler)
        self.assertEqual(handler.status, 403)
        self.listener.assert_not_called()

    def test_handler_rejects_oversized_body(self):
        handler = Handler('POST')
        handler.headers['Content-Length'] = '50000'
        spotify.handle_request(handler)
        self.assertEqual(handler.status, 400)
        self.assertEqual(handler.rfile.tell(), 0)

    def test_no_redirect_following(self):
        self.assertIsNone(spotify.NoRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.example'))

    def test_keychain_secrets_use_stdin_not_arguments(self):
        self.configured()
        patch.stopall()
        with patch.object(spotify.subprocess, 'run', return_value=types.SimpleNamespace(returncode=0)) as run:
            spotify.SpotifyManager._keychain(self.manager, 'set', TOKEN)
        args, options = run.call_args
        self.assertNotIn('fixture-access', repr(args))
        self.assertIn(b'fixture-access', options['input'])
        self.assertFalse(options['shell'])
        self.assertEqual(options['stderr'], spotify.subprocess.DEVNULL)


if __name__ == '__main__':
    unittest.main()
