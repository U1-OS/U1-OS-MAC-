"""Provider security regression fixtures: no real accounts, Keychain or children."""
import ast
import copy
import importlib.util
import io
import json
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
import urllib.parse
import urllib.request
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
from utils import u1_spotify as spotify
import utils


def google_fixture(root):
    spec = importlib.util.spec_from_file_location('google_boundary_fixture', ROOT / 'utils/u1_google.py')
    module = importlib.util.module_from_spec(spec)
    workspace, business = types.ModuleType('utils.prism_workspace'), types.ModuleType('utils.u1_business')
    business.import_source = MagicMock()
    with patch.dict(sys.modules, {'utils.prism_workspace':workspace, 'utils.u1_business':business}), \
         patch.object(utils,'prism_workspace',workspace,create=True), patch.object(utils,'u1_business',business,create=True):
        spec.loader.exec_module(module)
    module.ROOT = root
    return module


class ProviderBoundaries(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='u1-provider-boundary-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.process = patch('subprocess.run', side_effect=AssertionError('No real subprocess')).start()
        self.child = patch('subprocess.Popen', side_effect=AssertionError('No real child')).start()
        self.network = patch('urllib.request.OpenerDirector.open', side_effect=AssertionError('No network')).start()
        patch('urllib.request.urlopen', side_effect=AssertionError('No network')).start()
        patch('socket.create_connection', side_effect=AssertionError('No socket')).start()
        self.addCleanup(patch.stopall)

    def google(self):
        module = google_fixture(self.root)
        self.config = dict(configured=True,auto_sync=True,include_pdfs=False,last_sync=0,messages=[],events=[],bindings={})
        self.metadata = patch.object(module,'stored',side_effect=lambda:copy.deepcopy(self.config)).start()
        self.save = patch.object(module,'save',side_effect=lambda value:self.config.update(value)).start()
        self.keychain = patch.object(module,'keychain',return_value={'client_id':'fixture.apps.googleusercontent.com','refresh_token':'FIXTURE-REFRESH'}).start()
        self.request = patch.object(module,'request',side_effect=AssertionError('Account calls require a fixture')).start()
        self.blocked = patch.object(module,'_safety_blocked',return_value=False).start()
        return module

    def spotify(self):
        module = spotify.SpotifyManager(self.root)
        module.config = dict(client_id='a'*32,credentials_saved=True)
        self.keychain = patch.object(module,'_keychain',return_value=dict(access_token='FIXTURE-ACCESS',refresh_token='FIXTURE-REFRESH',scope=spotify.SCOPE,expires_at=time.time()+3600)).start()
        self.save = patch.object(module,'_save').start()
        self.request = patch.object(spotify,'_http',return_value=(204,{},0)).start()
        patch.object(spotify,'_blocked',return_value=False).start()
        return module

    def google_start(self,module):
        self.targets=[]
        def thread(**kwargs):
            self.targets.append(kwargs['target'])
            return types.SimpleNamespace(start=lambda:None)
        return patch.object(module.threading,'Thread',side_effect=thread)

    def callback(self,module):
        with patch.object(module,'ThreadingHTTPServer') as server, self.google_start(module):
            server.return_value.server_port=49124
            module.begin()
            klass=server.call_args.args[1]
        handler=object.__new__(klass)
        handler.path='/oauth2callback?'+urllib.parse.urlencode({'state':module.PENDING['state'],'code':'FIXTURE'})
        handler.headers={'Host':'127.0.0.1:49124'}
        handler.server=types.SimpleNamespace(server_port=49124)
        handler.wfile=io.BytesIO()
        handler.send_response=MagicMock();handler.send_header=MagicMock();handler.end_headers=MagicMock()
        return handler

    def test_legacy_ai_is_retired_for_every_payload(self):
        # Extract only the retired function; never import the hub's startup workers.
        tree=ast.parse((ROOT/'utils/workspace_hub.py').read_text())
        function=next(node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=='run_ai')
        namespace={'subprocess':subprocess,'job_start':MagicMock(side_effect=AssertionError('No unmanaged queue'))}
        exec(compile(ast.Module(body=[function],type_ignores=[]),'legacy_ai_boundary','exec'),namespace)
        for payload in ({},{'provider':'codex','prompt':'fixture'},{'provider':'claude','prompt':'fixture','confirmed':True}):
            with self.assertRaisesRegex(ValueError,'Legacy AI execution is retired.*No provider request was started'):
                namespace['run_ai'](payload)
        self.process.assert_not_called();self.child.assert_not_called()

    def test_google_locked_auto_loop_does_not_start_job_or_read_credentials(self):
        google=self.google();self.blocked.return_value=True
        with self.google_start(google), patch.object(google.time,'sleep',side_effect=RuntimeError('one iteration')):
            google.start()
            with self.assertRaisesRegex(RuntimeError,'one iteration'):self.targets[0]()
        self.assertIsNone(google.JOB);self.assertEqual(len(self.targets),1)
        self.metadata.assert_not_called();self.keychain.assert_not_called();self.request.assert_not_called()

    def test_google_cancel_hook_is_local_and_pauses_without_safety_inversion(self):
        google=self.google();stop=threading.Event()
        google.PENDING={'status':'authorising','stop':stop}
        google.JOB={'id':'fixture','status':'running'}
        result=google.cancel_all()
        self.assertTrue(stop.is_set());self.assertIsNone(google.PENDING)
        self.assertTrue(google.paused());self.assertEqual(result['job']['status'],'cancelling')
        self.blocked.assert_not_called();self.metadata.assert_not_called();self.keychain.assert_not_called();self.request.assert_not_called()

    def test_google_unlock_does_not_automatically_resume_cancelled_sync(self):
        google=self.google();google.cancel_all()
        with self.google_start(google):
            with self.assertRaisesRegex(ValueError,'cancelled or paused'):google.sync(resume=False)
        self.assertEqual(self.targets,[])
        self.keychain.assert_not_called()

    def test_google_explicit_sync_can_resume_after_unlock(self):
        google=self.google();google.cancel_all()
        with self.google_start(google):result=google.sync(resume=True)
        self.assertTrue(result['success']);self.assertFalse(google.paused());self.assertEqual(len(self.targets),1)
        self.keychain.assert_not_called()

    def test_google_safety_check_runs_outside_provider_lock(self):
        google=self.google()
        def blocked():
            self.assertFalse(google.LOCK._is_owned())
            return False
        self.blocked.side_effect=blocked
        with self.google_start(google):google.sync()

    def test_google_callback_rejects_lock_before_exchange(self):
        google=self.google();handler=self.callback(google)
        self.blocked.return_value=True;self.keychain.reset_mock()
        handler.do_GET()
        handler.send_response.assert_called_once_with(400)
        self.request.assert_not_called();self.keychain.assert_not_called()

    def test_google_callback_cancellation_between_last_check_and_commit(self):
        google=self.google();handler=self.callback(google)
        self.request.side_effect=None;self.request.return_value={'refresh_token':'FIXTURE-NEW'}
        original=google._allowed;count=[]
        def allowed(epoch):
            original(epoch);count.append(epoch)
            if len(count)==4:google.cancel_all()
        self.keychain.reset_mock()
        with patch.object(google,'_allowed',side_effect=allowed):handler.do_GET()
        self.assertEqual(len(count),4)
        handler.send_response.assert_called_once_with(400)
        self.keychain.assert_not_called();self.assertFalse(google.SESSION_VERIFIED)

    def test_google_callback_replay_exchanges_only_once(self):
        google=self.google();handler=self.callback(google)
        self.request.side_effect=None;self.request.return_value={'refresh_token':'FIXTURE-NEW'}
        handler.do_GET();handler.do_GET()
        self.request.assert_called_once()
        self.assertEqual(google.PENDING['status'],'authorised')

    def test_google_disconnect_during_refresh_prevents_subsequent_account_reads(self):
        google=self.google();reads=[]
        def request(url,*args,**kwargs):
            if url.endswith('/revoke'):raise ValueError('fixture revocation unavailable')
            if url.endswith('/token'):
                google.action({'action':'disconnect'})
                return {'access_token':'FIXTURE-ACCESS'}
            reads.append(url);return {}
        self.request.side_effect=request
        with self.google_start(google):
            google.sync();self.targets[0]()
        self.assertEqual(reads,[]);self.assertEqual(google.JOB['status'],'cancelled')
        self.assertFalse(self.config['configured']);self.assertFalse(google.SESSION_VERIFIED)

    def test_google_cancel_before_worker_starts_does_not_read_keychain(self):
        google=self.google()
        with self.google_start(google):
            google.sync();google.cancel_all();self.targets[0]()
        self.keychain.assert_not_called();self.request.assert_not_called()
        self.assertEqual(google.JOB['status'],'cancelled')

    def test_google_disconnect_without_refresh_token_does_not_claim_revocation(self):
        google=self.google();self.keychain.return_value={'client_id':'fixture.apps.googleusercontent.com'}
        result=google.action({'action':'disconnect'})
        self.request.assert_not_called()
        self.assertFalse(self.config['configured'])
        self.assertIn('revocation was not confirmed',result['message'])
        self.keychain.assert_any_call('delete')

    def test_google_disconnect_confirms_only_successful_revoke_response(self):
        google=self.google();self.request.side_effect=None;self.request.return_value=b''
        result=google.action({'action':'disconnect'})
        self.request.assert_called_once_with('https://oauth2.googleapis.com/revoke',{'token':'FIXTURE-REFRESH'},raw=True)
        self.assertIn('revocation confirmed',result['message'])

    def test_google_disconnect_failed_revoke_does_not_claim_confirmation(self):
        google=self.google();self.request.side_effect=ValueError('fixture failure')
        result=google.action({'action':'disconnect'})
        self.assertIn('revocation was not confirmed',result['message'])
        self.assertNotIn('fixture failure',result['message'])
        self.keychain.assert_any_call('delete')

    def test_google_cancel_at_listener_publication_closes_unpublished_server(self):
        google=self.google();original=google._allowed;count=[]
        def allowed(epoch):
            original(epoch);count.append(epoch)
            if len(count)==2:google.cancel_all()
        with patch.object(google,'ThreadingHTTPServer') as server, self.google_start(google), patch.object(google,'_allowed',side_effect=allowed):
            server.return_value.server_port=49124
            with self.assertRaisesRegex(ValueError,'cancelled or paused'):google.begin()
        self.assertIsNone(google.PENDING);self.assertEqual(self.targets,[])
        server.return_value.server_close.assert_called_once()

    def test_spotify_refresh_last_epoch_commit_is_rejected(self):
        service=self.spotify();original=service._allowed;count=[]
        def allowed(epoch):
            original(epoch);count.append(epoch)
            if len(count)==4:service.cancel()
        with patch.object(service,'_allowed',side_effect=allowed):result=service.refresh()
        self.assertEqual(len(count),4);self.assertFalse(result['live_verified'])
        self.assertNotEqual(result['status'],'nothing_playing');self.assertIsNone(result['observed_at'])

    def test_spotify_callback_last_epoch_commit_is_rejected(self):
        service=self.spotify();service.config['credentials_saved']=False
        service.pending=dict(state='s'*43,verifier='v'*86,deadline=time.monotonic()+60,epoch=service.epoch,
            redirect='http://127.0.0.1:49123/spotify/callback',stop=threading.Event())
        self.request.return_value=(200,dict(access_token='FIXTURE-ACCESS',refresh_token='FIXTURE-REFRESH',token_type='Bearer',scope=spotify.SCOPE,expires_in=3600),0)
        original=service._allowed;count=[]
        def allowed(epoch):
            original(epoch);count.append(epoch)
            if len(count)==3:service.cancel()
        with patch.object(service,'_allowed',side_effect=allowed):
            result=service.callback('/spotify/callback?state='+'s'*43+'&code=FIXTURE','127.0.0.1:49123')
        self.assertFalse(result);self.assertFalse(service.config['credentials_saved'])
        self.assertNotEqual(service.status,'connected_unchecked');self.save.assert_not_called()

    def test_spotify_cancel_before_keychain_commit_prevents_write(self):
        service=self.spotify();original=service._allowed
        def allowed(epoch):original(epoch);service.cancel()
        with patch.object(service,'_allowed',side_effect=allowed):
            with self.assertRaisesRegex(spotify.SpotifyError,'safety_blocked'):
                service._keychain_checked(service.epoch,'set',{'fixture':True})
        self.keychain.assert_not_called()

    def test_spotify_cancel_during_helper_setup_does_not_publish_configuration(self):
        service=self.spotify();service.config={}
        with patch.object(service,'_ensure_helper',side_effect=service.cancel):
            with self.assertRaisesRegex(spotify.SpotifyError,'safety_blocked'):service.configure('a'*32)
        self.assertEqual(service.config,{});self.save.assert_not_called()

    def test_spotify_disconnect_epoch_recheck_prevents_late_delete(self):
        service=self.spotify();original=service._allowed
        def allowed(epoch):original(epoch);service.cancel()
        with patch.object(service,'_allowed',side_effect=allowed):
            with self.assertRaisesRegex(spotify.SpotifyError,'safety_blocked'):service.disconnect()
        self.keychain.assert_not_called();self.save.assert_not_called()


if __name__=='__main__':unittest.main()
