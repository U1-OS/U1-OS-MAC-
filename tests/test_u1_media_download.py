"""Source-only fixtures. No downloads, source fetches, cookies or accounts."""
import base64
import io
import json
import unittest
from unittest.mock import Mock, patch

from utils import u1_media_download as media


class IntakeTests(unittest.TestCase):
    def setUp(self):
        for target in ['urllib.request.urlopen', 'socket.getaddrinfo', 'subprocess.Popen']:
            blocker = patch(target, side_effect=AssertionError('Network/process actions are forbidden'))
            blocker.start(); self.addCleanup(blocker.stop)

    def body(self, **extra):
        value = dict(action='review_source', url='https://youtu.be/AbCdEfG1234', rights_confirmed=True, public_unprotected_confirmed=True)
        value.update(extra); return value

    def test_canonical_direct_sources_and_discarded_tracking(self):
        for url, provider, canonical in [
            ('https://youtu.be/AbCdEfG1234?si=tracking', 'youtube', 'https://www.youtube.com/watch?v=AbCdEfG1234'),
            ('https://www.youtube.com/shorts/AbCdEfG1234', 'youtube', 'https://www.youtube.com/watch?v=AbCdEfG1234'),
            ('https://instagram.com/reel/AbCdE12/?igsh=tracking', 'instagram', 'https://www.instagram.com/reel/AbCdE12/'),
            ('https://www.tiktok.com/@synthetic.fixture/video/1234567890123456789?_r=1', 'tiktok', 'https://www.tiktok.com/@synthetic.fixture/video/1234567890123456789')]:
            with self.subTest(url=url):
                result = media.action(self.body(url=url))
                self.assertEqual((result['provider'], result['canonical_url']), (provider, canonical))
                self.assertFalse(result['media_downloaded'])
                self.assertFalse(result['quality_checked'])

    def test_ssrf_protocol_credentials_redirect_profiles_and_playlist_rejected(self):
        invalid = ['http://youtube.com/watch?v=AbCdEfG1234', 'file:///etc/passwd', 'https://127.0.0.1/video',
            'https://[::1]/', 'https://169.254.169.254/latest/meta-data', 'https://2130706433/',
            'https://youtube.com.evil.example/watch?v=AbCdEfG1234', 'https://youtube.com@127.0.0.1/',
            'https://www.youtube.com:444/watch?v=AbCdEfG1234', 'https://www.youtube.com./watch?v=AbCdEfG1234',
            'https://youtube.com/redirect?q=https://127.0.0.1', 'https://youtu.be/AbCdEfG1234?list=private',
            'https://www.youtube.com/watch?v=AbCdEfG1234&v=OtherId1234', 'https://www.instagram.com/private_profile/',
            'https://vm.tiktok.com/short/', 'https://www.tiktok.com/@synthetic.fixture/',
            'https://www.instagram.com/reel/AbCdE12/%2f..', 'https://www.youtube.com\\@127.0.0.1/',
            'https://youtu.be/AbCdEfG1234\n', 'https://youtu.be/AbCdEfG1234#fragment', 'x' * 2001]
        for url in invalid:
            with self.subTest(url=url), self.assertRaises(media.IntakeError): media.action(self.body(url=url))

    def test_confirmation_and_unsupported_execution_options(self):
        for extra in [dict(rights_confirmed=False), dict(rights_confirmed='true'), dict(public_unprotected_confirmed=False),
                      dict(cookies='private'), dict(proxy='http://localhost'), dict(path='/tmp/file'),
                      dict(headers={}), dict(strip_watermark=True), dict(action='download')]:
            with self.subTest(extra=extra), self.assertRaises(media.IntakeError): media.action(self.body(**extra))

    def test_review_manifest_is_not_media_or_independent_verification(self):
        result = media.action(self.body(action='export_manifest'))
        data = json.loads(base64.b64decode(result['content']))
        self.assertEqual(data['format'], 'u1-media-intake-review')
        self.assertEqual(result['mime'], 'application/json')
        self.assertFalse(data['review']['media_downloaded'])
        self.assertIn('not_independently_verified', data['review']['rights_status'])
        self.assertIn('Preserve', data['review']['watermark_policy'])

    def test_installation_does_not_implicitly_enable_downloading(self):
        for installed in [False, True]:
            with patch.object(media.importlib.util, 'find_spec', return_value=Mock() if installed else None), patch.object(media.shutil, 'which', return_value=None):
                result = media.capabilities()
                self.assertEqual(result['yt_dlp_detected'], installed)
                self.assertFalse(result['direct_download_available'])
                self.assertFalse(result['network_requests'])
                self.assertFalse(result['watermark_removal'])


class HandlerTests(unittest.TestCase):
    def handler(self, **headers):
        raw = json.dumps(dict(action='review_source', url='https://youtu.be/AbCdEfG1234', rights_confirmed=True, public_unprotected_confirmed=True)).encode()
        handler = Mock(path=media.ENDPOINT, command='POST', rfile=io.BytesIO(raw))
        handler.headers = {'Content-Length': str(len(raw)), 'Content-Type': 'application/json', 'X-U1-CSRF': media.integrations_hub.CSRF_TOKEN}
        handler.headers.update(headers); handler.integration_request_allowed.return_value = True
        return handler

    def test_origin_csrf_body_and_content_type(self):
        for headers, expected in [({'X-U1-CSRF': ''}, 403), ({'Content-Length': '8193'}, 400),
                                  ({'Content-Length': '0'}, 400), ({'Transfer-Encoding': 'chunked'}, 400),
                                  ({'Content-Type': 'text/plain'}, 415), ({'Content-Length': 'nan'}, 400)]:
            handler = self.handler(**headers); media.handle_request(handler)
            self.assertEqual(handler.send_json.call_args.args[1], expected)
        handler = self.handler(); handler.integration_request_allowed.return_value = False
        media.handle_request(handler); self.assertEqual(handler.send_json.call_args.args[1], 403)

    def test_exact_routes_no_url_queries_and_valid_review(self):
        handler = self.handler(); self.assertTrue(media.handle_request(handler))
        self.assertFalse(handler.send_json.call_args.args[0]['media_downloaded'])
        handler = self.handler(); handler.path += '?url=https://localhost/'
        media.handle_request(handler); self.assertEqual(handler.send_json.call_args.args[1], 400)
        handler.path = '/api/workspace/media-download/execute'
        self.assertFalse(media.handle_request(handler))


if __name__ == '__main__': unittest.main()
