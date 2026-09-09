"""Fixed-path inventory fixtures and media DOM-handoff fixtures; no tool launches."""
import io
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from utils import u1_osint_tools as tools


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name).resolve()
        self.repos, self.desktop = root / 'repos', root / 'Desktop'
        self.repos.mkdir(); self.desktop.mkdir()
        for name, value in [('REPOSITORIES', self.repos), ('DESKTOP', self.desktop)]:
            patcher = patch.object(tools, name, value); patcher.start(); self.addCleanup(patcher.stop)
        for target in ['subprocess.Popen', 'urllib.request.urlopen']:
            patcher = patch(target, side_effect=AssertionError('Inventory must not execute or fetch'))
            patcher.start(); self.addCleanup(patcher.stop)

    def fixture(self, identifier='maigret'):
        spec = next(t for t in tools.TOOLS if t['id'] == identifier)
        repo = self.repos / identifier; repo.mkdir(exist_ok=True)
        (repo / spec['marker']).write_text('Synthetic metadata fixture')
        if spec['app'] and spec['executable']:
            app = self.desktop / spec['app']; mac = app / 'Contents' / 'MacOS'; mac.mkdir(parents=True)
            resources = app / 'Contents' / 'Resources'; resources.mkdir()
            (app / 'Contents' / 'Info.plist').write_bytes(plistlib.dumps(dict(CFBundleIdentifier=spec['bundle_id'], CFBundleExecutable=spec['executable'])))
            (mac / spec['executable']).write_text('# Synthetic fixture; never executed')
            if spec['config']:
                (resources / 'launcher.json').write_text(json.dumps(dict(repo=str(repo), url=spec['local_url'], command=['DO NOT EXECUTE'])))
        return spec

    def test_exact_eight_and_no_execution_or_query_capability(self):
        self.assertEqual({t['id'] for t in tools.TOOLS}, {'dfw1n-osint', 'gods-eye-view', 'holehe', 'maigret', 'osiris', 'ponytail', 'sherlock', 'spiderfoot'})
        for tool in tools.TOOLS: self.fixture(tool['id'])
        result = tools.snapshot()
        self.assertEqual(len(result['tools']), 8)
        self.assertTrue(result['capabilities']['read_only'])
        self.assertFalse(result['capabilities']['launch'])
        self.assertTrue(all(not t['launch_available'] and not t['query_available'] for t in result['tools']))
        self.assertEqual(sum(t['state'] == 'desktop_only' for t in result['tools']), 5)
        self.assertEqual(tools.snapshot('ponytail')['tools'][0]['state'], 'plugin_only')
        self.assertEqual(tools.snapshot('holehe')['tools'][0]['state'], 'setup_needed')

    def test_matched_launcher_metadata_does_not_imply_running(self):
        self.fixture()
        item = tools.snapshot('maigret')['tools'][0]
        self.assertEqual(item['configured_local_url'], 'http://127.0.0.1:4176/')
        self.assertEqual(item['runtime_status'], 'not_checked')
        self.assertEqual(item['launcher']['mapping'], 'matching_launcher_configuration')
        self.assertNotIn('command', json.dumps(item))

    def test_changed_mapping_does_not_expose_arbitrary_path_url_or_secret(self):
        self.fixture()
        config = self.desktop / 'Maigret.app/Contents/Resources/launcher.json'
        config.write_text(json.dumps(dict(repo='/private/unrelated', url='https://untrusted.example/', secret='never-return-this')))
        item = tools.snapshot('maigret')['tools'][0]
        self.assertEqual(item['state'], 'review_required')
        self.assertIsNone(item['configured_local_url'])
        self.assertNotIn('never-return-this', json.dumps(item))
        self.assertNotIn('/private/unrelated', json.dumps(item))

    def test_missing_symlink_and_oversized_metadata(self):
        self.assertEqual(tools.snapshot('maigret')['tools'][0]['state'], 'setup_needed')
        self.fixture()
        plist = self.desktop / 'Maigret.app/Contents/Info.plist'
        plist.write_bytes(b'x' * (tools.MAX_METADATA + 1))
        self.assertEqual(tools.snapshot('maigret')['tools'][0]['state'], 'review_required')
        plist.unlink(); external = self.repos / 'isolated-outside'; external.write_text('fixture')
        plist.symlink_to(external)
        with self.assertRaises(ValueError): tools.read_metadata(plist)
        self.assertEqual(tools.snapshot('maigret')['tools'][0]['state'], 'review_required')

    def test_directory_symlink_and_world_writable_are_unsafe(self):
        target = self.repos / 'target'; target.mkdir()
        (self.repos / 'maigret').symlink_to(target, target_is_directory=True)
        self.assertEqual(tools.snapshot('maigret')['tools'][0]['state'], 'review_required')
        target.chmod(0o777)
        self.assertEqual(tools.path_state(target, directory=True), 'unsafe')

    def test_request_paths_commands_urls_and_mutations_rejected(self):
        for query in ['?path=/etc/passwd', '?command=id', '?url=https://example.org', '?id=../outside', '?id=maigret&id=osiris', '?id=']:
            handler = Mock(path=tools.ENDPOINT + query, command='GET', headers={}, rfile=io.BytesIO())
            handler.integration_request_allowed.return_value = True
            tools.handle_request(handler)
            self.assertEqual(handler.send_json.call_args.args[1], 400, query)
        handler = Mock(path=tools.ENDPOINT, command='POST', headers={})
        handler.integration_request_allowed.return_value = True
        tools.handle_request(handler)
        self.assertEqual(handler.send_json.call_args.args[1], 405)
        handler.rfile.read.assert_not_called()

    def test_same_origin_and_exact_route(self):
        handler = Mock(path=tools.ENDPOINT, command='GET')
        handler.integration_request_allowed.return_value = False
        self.assertTrue(tools.handle_request(handler))
        self.assertEqual(handler.send_json.call_args.args[1], 403)
        handler.path = tools.ENDPOINT + '/launch'
        self.assertFalse(tools.handle_request(handler))


NODE_HANDOFF = r'''
const fs=require('node:fs'), vm=require('node:vm'), assert=require('node:assert/strict');
let source=fs.readFileSync(process.argv[1],'utf8');
source=source.replace('window.U1MediaResearch = Object.freeze', 'window.__fixture={ensure:ensurePlayer, move:movePlayer, park:unmountMedia, sync:syncPlayerState, source:hasPlayerSource, bind:function(r){mediaRoot=r;}, player:function(){return player;}}; window.U1MediaResearch = Object.freeze');
let attr=null, creates=0, pauses=0, loads=0, plays=0;
const shelf={isConnected:true,appendChild(n){n.parentNode=this;}};
const slot={dataset:{},appendChild(n){n.parentNode=this;}};
const empty={hidden:false}, metadata={textContent:''};
const player={currentSrc:'',paused:false,currentTime:42,duration:60,videoWidth:0,
 getAttribute(){return attr;},querySelector(){return null;},addEventListener(){},
 pause(){pauses++;},load(){loads++;},play(){plays++;return Promise.resolve();},
 get src(){throw Error('Do not use the resolving src getter');}};
const mini={parentNode:shelf,isConnected:true,dataset:{},contains(n){return n===player;},classList:{toggle(){}}};
const root={contains(n){return n===mini&&mini.parentNode===slot;},querySelector(s){return {'[data-mr-player-slot]':slot,'[data-mr-player-empty]':empty,'[data-mr-metadata]':metadata}[s];}};
const document={readyState:'loading',baseURI:'http://localhost:8080/',URL:'http://localhost:8080/',body:shelf,
 getElementById(id){return {'u1-local-media':player,'u1-player-mini':mini}[id];},createElement(){creates++;throw Error('Do not create another player');},addEventListener(){},dispatchEvent(){}};
const window={addEventListener(){}};
vm.runInNewContext(source,{window,document,URL});
const f=window.__fixture;f.bind(root);f.ensure();assert.equal(f.player(),player);assert.equal(creates,0);
assert.equal(f.source(),false);assert.equal(player.hidden,true);assert.equal(mini.hidden,true);
player.currentSrc=document.URL;f.sync();assert.equal(f.source(),false);
attr='blob:http://localhost:8080/synthetic-handoff-fixture';player.currentSrc='';
f.move(slot);assert.equal(mini.parentNode,slot);assert.equal(player.controls,true);assert.equal(player.hidden,false);
f.park();assert.equal(mini.parentNode,shelf);assert.equal(mini.hidden,false);assert.equal(player.currentTime,42);
assert.equal(pauses,0);assert.equal(loads,0);assert.equal(plays,2);assert.equal(f.player(),player);
attr='';f.sync();assert.equal(mini.hidden,true);assert.equal(creates,0);
console.log('PASS: same persistent video, compact empty state, source detection, page/shelf handoff, retained playhead, no pause/reload/duplicate stream.');
'''


class MediaHandoffFixtureTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which('node'), 'Node is needed for the isolated DOM fixture')
    def test_existing_player_handoff_without_shared_browser(self):
        path = Path(__file__).resolve().parents[1] / 'static/js/u1-media-research.js'
        result = subprocess.run([shutil.which('node'), '-e', NODE_HANDOFF, str(path)],
                                shell=False, capture_output=True, text=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('PASS:', result.stdout)


if __name__ == '__main__':
    unittest.main()
