import io
import unittest
from unittest.mock import patch
from utils import u1_native_routes as routes


class Handler:
    command = 'GET'
    def __init__(self, path):
        self.path = path
        self.wfile = io.BytesIO()
        self.code = None
    def send_response(self, code): self.code = code
    def send_header(self, *args): pass
    def end_headers(self): pass


class NativeRouteTests(unittest.TestCase):
    def test_old_entry_points_use_canonical_redirect_not_old_shell(self):
        for path in routes.OLD_ENTRIES:
            handler = Handler(path)
            self.assertTrue(routes.handle_request(handler))
            source = handler.wfile.getvalue().decode()
            self.assertIn("location.replace('/#'", source)
            self.assertNotIn('<iframe', source)
            self.assertNotIn('prism-shell', source)

    def test_unknown_routes_are_not_claimed(self):
        self.assertFalse(routes.handle_request(Handler('/api/workspace/prism/summary')))

    def test_optional_failure_is_json_error_not_false_success(self):
        with patch.object(routes.importlib, 'import_module', side_effect=ImportError('not installed')):
            handler = Handler('/api/workspace/assistant')
            self.assertTrue(routes.handle_request(handler))
            self.assertEqual(handler.code, 503)
            self.assertIn(b'"success": false', handler.wfile.getvalue())


if __name__ == '__main__': unittest.main()


class PersonalReleaseRouteContracts(unittest.TestCase):
    def test_every_native_feature_and_export_has_explicit_dispatch(self):
        from utils import u1_native_routes
        expected = {
            '/api/workspace/studio-pro': 'utils.u1_studio_pro',
            '/api/workspace/personal': 'utils.u1_personal_core',
            '/api/workspace/personal/export': 'utils.u1_personal_core',
            '/api/workspace/personal/snapshot': 'utils.u1_personal_core',
            '/api/workspace/assistant': 'utils.u1_assistant',
            '/api/workspace/jobs': 'utils.u1_assistant',
            '/api/workspace/image-provider': 'utils.u1_image_provider',
            '/api/workspace/private-backup': 'utils.u1_private_backup',
            '/api/workspace/media-research': 'utils.u1_media_research',
        }
        for path, module in expected.items():
            with self.subTest(path=path):
                self.assertEqual(u1_native_routes.HANDLERS.get(path), module)
