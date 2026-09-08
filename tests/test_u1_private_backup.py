import base64
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from utils import prism_workspace as workspace, u1_recovery as recovery, u1_private_backup as private


class PrivateBackupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        self.addCleanup(patch.stopall)
        patch.object(workspace, 'DATA', root / 'workspace').start()
        patch.object(recovery, 'ROOT', root / 'recovery').start()

    def test_authenticated_encryption_roundtrip_and_randomness(self):
        raw = b'private local record'
        a = private.encrypt(raw, 'isolated backup passphrase')
        b = private.encrypt(raw, 'isolated backup passphrase')
        self.assertNotEqual(a, b)
        self.assertNotIn(raw, a)
        self.assertEqual(private.decrypt(a, 'isolated backup passphrase'), raw)

    def test_wrong_passphrase_or_modified_bytes_rejected(self):
        encrypted = private.encrypt(b'important source', 'isolated backup passphrase')
        for value, phrase in ((encrypted, 'incorrect passphrase'), (encrypted[:-1]+bytes([encrypted[-1]^1]), 'isolated backup passphrase')):
            with self.assertRaises(ValueError):
                private.decrypt(value, phrase)

    def test_bounded_input_and_confirmation(self):
        with self.assertRaises(ValueError): private.encrypt(b'data', 'short')
        with self.assertRaises(ValueError): private.decrypt(b'not an archive', 'isolated passphrase')
        with self.assertRaises(ValueError): private.action({'action':'encrypt','passphrase':'isolated passphrase'})
        with self.assertRaises(ValueError): private.archive_bytes('../private')

    def test_restore_drill_preserves_active_database(self):
        workspace.handle_post('prism/record', {'kind':'note','title':'Isolated test','payload':{'text':'Private backup fixture'}})
        recovery.make_backup()
        source = recovery.snapshot()['backups'][0]['id']
        copy = private.action({'action':'encrypt','id':source,'passphrase':'isolated backup passphrase','confirmed':True})
        before = (workspace.DATA/'workspace.sqlite3').read_bytes()
        result = private.action({'action':'restore_drill','content':copy['content'],'passphrase':'isolated backup passphrase','confirmed':True})
        self.assertTrue(result['success'])
        self.assertFalse(result['active_workspace_changed'])
        self.assertEqual(before, (workspace.DATA/'workspace.sqlite3').read_bytes())
        self.assertEqual(len(recovery.snapshot()['backups']), 1)
        self.assertTrue((recovery.ROOT/'backups'/(source+'.zip')).exists())


if __name__ == '__main__': unittest.main()
