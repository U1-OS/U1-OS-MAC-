import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from utils import u1_launcher as launcher


class LauncherTests(unittest.TestCase):
    def response(self, payload):
        response = MagicMock()
        response.__enter__.return_value = io.BytesIO(json.dumps(payload).encode())
        return response

    def test_readiness_requires_correct_installation(self):
        with patch.object(launcher.urllib.request, 'build_opener') as factory:
            factory.return_value.open.return_value = self.response({'installation_root': '/another/project'})
            self.assertFalse(launcher.status()['ready'])
            factory.return_value.open.return_value = self.response({'installation_root': str(launcher.ROOT)})
            self.assertTrue(launcher.status()['ready'])

    def test_offline_is_not_success(self):
        with patch.object(launcher.urllib.request, 'build_opener', side_effect=OSError('offline')):
            self.assertFalse(launcher.status()['ready'])

    def test_missing_runtime_does_not_install_globally(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(launcher, 'ROOT', Path(directory)), patch.object(launcher.subprocess, 'run') as run:
            with self.assertRaises(RuntimeError):
                launcher.start()
            run.assert_not_called()

    def test_stop_refuses_unverified_port_owner(self):
        with patch.object(launcher, 'status', return_value={'ready': False}), patch.object(launcher.os, 'kill') as kill:
            with self.assertRaises(RuntimeError):
                launcher.stop()
            kill.assert_not_called()

    def test_stop_refuses_mismatched_pid(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / '.u1-os.pid').write_text('12345')
            with patch.object(launcher, 'ROOT', root), patch.object(launcher, 'status', return_value={'ready': True}), patch.object(launcher.subprocess, 'check_output', return_value='/another/server.py'), patch.object(launcher.os, 'kill') as kill:
                with self.assertRaises(RuntimeError):
                    launcher.stop()
                kill.assert_not_called()

    def test_no_open_never_opens_window(self):
        with patch.object(launcher, 'start', return_value={'ready': True, 'reason': 'Ready'}), patch.object(launcher, 'open_workspace') as open_window, patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(launcher.main(['open', '--no-open']), 0)
            open_window.assert_not_called()

    def test_status_exit_code_matches_readiness(self):
        with patch.object(launcher, 'status', return_value={'ready': False, 'reason': 'Offline'}), patch('sys.stdout', new_callable=io.StringIO):
            self.assertEqual(launcher.main(['status', '--json']), 1)

    def test_launch_errors_return_failure(self):
        with patch.object(launcher, 'start', side_effect=RuntimeError('Startup failed')), patch('sys.stderr', new_callable=io.StringIO):
            self.assertEqual(launcher.main(['start']), 1)


if __name__ == '__main__':
    unittest.main()
