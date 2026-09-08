'use strict';
/* Bounded shell/DOM fixtures only. No feature asset loads, providers or records. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const { spawnSync } = require('node:child_process');
const root = path.resolve(__dirname, '..');
const read = file => fs.readFileSync(path.join(root, file), 'utf8');
const html = read('static/u1os.html');
const operations = read('static/js/u1-native-operations.js');
const shell = read('static/js/u1os.js');
const platform = read('static/js/u1-platform.js');
const ids = ['daily', 'activate', 'osint-tools', 'media-downloads', 'tech-gaming', 'sports-news', 'spotify'];

function metadataFixture() {
  const registered = new Map(), listeners = {};
  const window = {
    U1: { model: { VIEWS: {} } }, U1Life: { meta: {} },
    U1CoreViews: { register: (id, render) => registered.set(id, render) },
    addEventListener: (event, listener) => { (listeners[event] ||= []).push(listener); }
  };
  vm.runInNewContext(operations, {
    window, document: { readyState: 'loading' }, location: { hash: '#daily' },
    history: { replaceState() { throw Error('Normal hashes must not be rewritten during registration'); } }
  }, { filename: 'u1-native-operations.js' });
  return { window, registered, listeners };
}

test('declares every new asset once, with scoped cache busting and dependency order', () => {
  const scripts = ['u1os', 'u1-platform', 'u1-native-operations', 'u1-daily-flow',
    'u1-activation-workspace', 'u1-osint-tools', 'u1-media-download',
    'u1-discovery-workspace', 'u1-operational-polish', 'u1-spotify-widget'];
  for (const name of scripts) {
    const version = ['u1-operational-polish', 'u1-spotify-widget'].includes(name) ? '7' : '6';
    const tags = html.match(new RegExp('<script\\b[^>]*src="/js/' + name + '\\.js\\?v=20260908\\.' + version + '"[^>]*>', 'g')) || [];
    assert.equal(tags.length, 1, name);
  }
  for (const name of ['daily-flow', 'activation-workspace', 'discovery-workspace', 'operational-polish']) {
    assert.equal((html.match(new RegExp('/css/u1-' + name + '\\.css\\?v=20260908\\.6', 'g')) || []).length, 1);
  }
  assert.equal((html.match(/\/css\/u1-media-research\.css\?/g) || []).length, 1);
  assert.doesNotMatch(html, /u1-spotify-widget\.css/);
  for (const name of scripts.slice(3)) assert(html.indexOf('/js/u1-core-workspaces.js') < html.indexOf('/js/' + name + '.js'));
  assert(html.indexOf('/js/u1-native-operations.js') < html.indexOf('/js/u1-operational-polish.js'));
  assert(html.indexOf('/js/u1-media-research.js') < html.indexOf('/js/u1-operational-polish.js'));
});

test('metadata is ready before load, groups are compact, and agent views are not overwritten', () => {
  const e = metadataFixture();
  for (const id of ids) {
    assert(e.window.U1.model.VIEWS[id].t, id);
    assert(e.window.U1Life.meta[id].s, id);
    assert(!e.registered.has(id), 'The owner asset must retain its native renderer: ' + id);
  }
  assert.equal(e.window.U1Life.meta.activation, e.window.U1Life.meta.activate);
  const groups = Object.fromEntries(e.window.U1NativeNavigation.routes.map(row => [row[0], row[3]]));
  assert.equal(groups.daily, 'life');
  for (const id of ['activate', 'osint-tools', 'media-downloads']) assert.equal(groups[id], 'more');
  for (const id of ['tech-gaming', 'sports-news', 'spotify']) assert.equal(groups[id], 'discovery');
  for (const id of ['studio', 'ai', 'crypto', 'trading']) assert(!e.registered.has(id));
  assert.equal(e.listeners.load.length, 1);
});

function searchFixture(native = true) {
  const routes = platform.match(/^\s*var routes=.+;$/m);
  const navigate = platform.match(/^\s*function navigate\(route\)\{.+\}$/m);
  assert(routes && navigate, 'Search route registry and navigation function remain identifiable');
  const calls = [], location = { hash: '' };
  const dialog = { open: true, close() { this.open = false; } };
  const context = {
    window: native ? { U1: { navigate: id => calls.push(id) } } : {},
    document: { querySelector: () => null }, location, dialog
  };
  vm.runInNewContext(routes[0] + '\n' + navigate[0], context);
  return { ...context, calls };
}

test('real search navigates all new native destinations without a visible rail button', () => {
  const e = searchFixture();
  for (const id of ids) e.navigate(id);
  assert.deepEqual(e.calls, ids);
  assert.equal(e.dialog.open, false);
  assert.equal(new Set(e.routes.map(row => row[0])).size, e.routes.length);
  e.navigate('not-a-workspace'); e.navigate('../anything'); e.navigate('business');
  assert.deepEqual(e.calls, ids, 'Unknown routes and the actual ledger modal are not aliased');
});

test('search fallback changes the native hash rather than opening a legacy modal', () => {
  const e = searchFixture(false);
  e.navigate('media-downloads'); assert.equal(e.location.hash, 'media-downloads');
  e.navigate('unknown'); assert.equal(e.location.hash, 'media-downloads');
});

test('initial hashes wait for feature registration and subsequent hashes use native navigation', () => {
  assert.match(shell, /U\.navigate\s*=\s*go/);
  assert.match(shell, /setTimeout\(routeHash,\s*0\)/);
  assert.match(shell, /addEventListener\('hashchange',\s*routeHash\)/);
  const start = shell.indexOf('function routeHash()');
  const end = shell.indexOf('\n  }', start);
  assert(start >= 0 && end > start);
  const calls = [], location = { hash: '#daily' };
  const context = { location, go: (id, options) => calls.push([id, options.silent]) };
  vm.runInNewContext(shell.slice(start, end + 4), context);
  for (const id of [...ids, 'activation']) { location.hash = '#' + id; context.routeHash(); }
  assert.deepEqual(calls, [...ids, 'activation'].map(id => [id, true]));
  location.hash = '#%E0%A4%A'; context.routeHash(); assert.equal(calls.length, ids.length + 1);
  location.hash = ''; context.routeHash(); assert.deepEqual(calls.at(-1), ['home', true]);
});

test('shell palette includes extension metadata and refreshes when opened', () => {
  assert.match(shell, /Object\.keys\(VIEWS\)/);
  assert.match(shell, /function openPal\([^)]*\)\s*\{\s*buildPalette\(\)/);
  assert.match(shell, /setAttribute\('aria-current',\s*'page'\)/);
  assert.match(shell, /closest\('details'\)/);
  const palette = shell.slice(shell.indexOf('function buildPalette()'), shell.indexOf('function openPal()'));
  assert.doesNotMatch(palette, /Open classic shell/);
});

test('contextual links expose inventory/intake/activation while Business stays the actual ledger', () => {
  assert.match(operations, /osint:\[\['osint-tools','Local OSINT inventory'\]\]/);
  assert.match(operations, /media:\[\['media-downloads','Source intake'\]/);
  assert.match(operations, /integrations:\[\['activate','Activate connections'\]\]/);
  const nativeTools = operations.match(/var nativeTools=\{([^}]+)\}/)[1];
  assert.doesNotMatch(nativeTools, /business|drafts|briefing/);
  assert.match(platform, /business:'Business ledger'/);
  assert.match(platform, /drafts:'Review queue'/);
});

test('parent usage normalization fix is preserved', () => {
  const usage = platform.match(/^\s*function usageHTML\(\).+$/m)[0];
  assert.match(usage, /C\.selectWindow\(p,id,received\.usage\)/);
  assert.match(usage, /C\.allowance\(p,window,received\.usage\)/);
  assert.match(usage, /No fresh verified allowance available/);
  assert.match(usage, /window\.duration_minutes/);
  assert.match(usage, /window\.resets_at/);
  assert.match(usage, /Model-specific limits stay separate/);
});

test('exact backend dispatch, origin/CSRF/method guards and Discovery query adapter are isolated', () => {
  const code = String.raw`
import ast, importlib, pathlib, sys, types
from unittest.mock import patch
routes = importlib.import_module('utils.u1_native_routes')
fake_hub = types.ModuleType('utils.integrations_hub')
fake_hub.CSRF_TOKEN = 'fixture-local-token'
class Handler:
    def __init__(self, path, command='GET', allowed=True, token='fixture-local-token'):
        self.path, self.command, self.allowed = path, command, allowed
        self.headers, self.replies = {'X-U1-CSRF': token}, []
    def integration_request_allowed(self): return self.allowed
    def send_json(self, payload, status=200): self.replies.append((status, payload))
expected = {
    '/api/workspace/activation': 'utils.u1_connection_preflight',
    '/api/workspace/spotify': 'utils.u1_spotify',
    '/api/workspace/osint-tools': 'utils.u1_osint_tools',
    '/api/workspace/media-download': 'utils.u1_media_download',
    '/api/workspace/discovery': 'utils.u1_discovery',
}
assert routes.OPERATIONAL_HANDLERS == expected
seen = []
target = types.SimpleNamespace(handle_request=lambda h: seen.append(h) or True,
                               handle_get=lambda query: {'success': True, 'query': query})
with patch.dict(sys.modules, {'utils.integrations_hub': fake_hub}), patch.object(routes.importlib, 'import_module', return_value=target) as imported:
    for endpoint, module in expected.items():
        imported.reset_mock()
        h = Handler(endpoint)
        assert routes.handle_request(h) is True
        imported.assert_called_once_with(module)
        if endpoint.endswith('/discovery'): assert h.replies == [(200, {'success': True, 'query': {}})]
        else: assert seen[-1] is h
        imported.reset_mock()
        h = Handler(endpoint, allowed=False)
        assert routes.handle_request(h) is True and h.replies[0][0] == 403
        imported.assert_not_called()
        for suffix in ['/extra', '/callback', '-unexpected']:
            assert routes.handle_request(Handler(endpoint + suffix)) is False
        imported.assert_not_called()
        h = Handler(endpoint, 'DELETE')
        assert routes.handle_request(h) is True and h.replies[0][0] == 405
    for endpoint in ['/api/workspace/activation', '/api/workspace/osint-tools', '/api/workspace/discovery']:
        imported.reset_mock(); h = Handler(endpoint, 'POST')
        assert routes.handle_request(h) is True and h.replies[0][0] == 405
        imported.assert_not_called()
    for endpoint in ['/api/workspace/spotify', '/api/workspace/media-download']:
        for token in ['', 'incorrect', 'x' * 513]:
            imported.reset_mock(); h = Handler(endpoint, 'POST', token=token)
            assert routes.handle_request(h) is True and h.replies[0][0] == 403
            imported.assert_not_called()
        h = Handler(endpoint, 'POST')
        assert routes.handle_request(h) is True and seen[-1] is h
    h = Handler('/api/workspace/discovery?source=afl')
    assert routes.handle_request(h) is True
    assert h.replies == [(200, {'success': True, 'query': {'source': ['afl']}})]
    h = Handler('/api/workspace/discovery?source=afl&source=mma&empty=')
    routes.handle_request(h)
    assert h.replies[0][1]['query'] == {'source': ['afl', 'mma'], 'empty': ['']}
    for query in ['x=' + 'a' * 2049, '&'.join('x=' + str(i) for i in range(9))]:
        h = Handler('/api/workspace/discovery?' + query)
        routes.handle_request(h); assert h.replies[0][0] == 400
    with patch.object(target, 'handle_get', side_effect=ValueError('Select one supported source.')):
        h = Handler('/api/workspace/discovery?source=bad')
        routes.handle_request(h)
        assert h.replies == [(400, {'success': False, 'error': 'Select one supported source.'})]
    assert routes.handle_request(Handler('/spotify/callback')) is False
# Parse server source rather than importing it: no listeners, accounts or databases.
tree = ast.parse(pathlib.Path('server.py').read_text())
for method in ['do_GET', 'do_POST']:
    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == method]
    relevant = []
    for function in functions:
        safety, native = [], []
        for node in ast.walk(function):
            if not isinstance(node, ast.Call): continue
            if isinstance(node.func, ast.Name) and node.func.id == 'gate_request': safety.append(node.lineno)
            if isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == 'u1_native_routes' and node.func.attr == 'handle_request': native.append(node.lineno)
        if native:
            assert safety and min(safety) < min(native), method
            relevant.append(function)
    assert relevant, method
print('Exact routes, guarded adapter and canonical Safety ordering passed with fake handlers.')
`;
  const result = spawnSync('python3', ['-c', code], {
    cwd: root, encoding: 'utf8', timeout: 10000,
    env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' }
  });
  assert.equal(result.status, 0, (result.stdout || '') + (result.stderr || '') + (result.error || ''));
});
