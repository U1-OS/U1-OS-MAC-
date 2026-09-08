const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const P = require('../static/js/u1-connection-policy.js');
const workspaceSource = fs.readFileSync(path.join(__dirname, '../static/js/u1-connections-workspace.js'), 'utf8');
const css = fs.readFileSync(path.join(__dirname, '../static/css/u1-connections-workspace.css'), 'utf8');
const now = 1800000000000;
const google = (extra = {}) => ({ success: true, configured: true, keychain_helper: true, session_verified: false, stale: true, oauth_status: 'idle', ...extra });
const registry = (extra = {}) => ({ success: true, csrf_token: 'fixture-csrf-not-a-credential', cards: [
  { id: 'gmail', name: 'Gmail', fields: [{ id: 'client_secret', secret: true, value: 'legacy-fixture-secret' }], status: 'settings_saved', saved_fields: 1 },
  { id: 'google_calendar', name: 'Google Calendar', fields: [{ id: 'calendar_id', value: 'legacy-calendar-fixture' }] },
  { id: 'stripe', name: 'Stripe', category: 'Finance', fields: [{ id: 'secret_key', secret: true, saved: true, value: 'must-never-render' }, { id: 'currency', value: 'AUD' }], saved_fields: 1, status: 'settings_saved', portal: 'https://dashboard.stripe.com/apikeys' },
  { id: 'ollama', name: 'Ollama', fields: [], stage: 'installed' }
], ...extra });

test('normalisation discards every legacy Google value and secret value', () => {
  const result = P.catalogue(registry());
  assert.deepEqual(result[0].fields, []); assert.deepEqual(result[1].fields, []);
  assert.equal(result[2].fields[0].value, '');
  assert.doesNotMatch(JSON.stringify(result), /legacy-fixture-secret|legacy-calendar-fixture|must-never-render/);
});
test('settings metadata can never grant connect, sync or disconnect', () => {
  const card = P.catalogue(registry())[2];
  assert.equal(P.settingsState(card).label, 'Settings saved / unverified');
  assert.deepEqual(P.settingsState(card).actions, []);
  assert.equal(P.settingsState({ ...card, settingsSaved: false, savedFields: 0, status: 'connected' }).label, 'API settings required');
});
test('Google needs explicit current verification and a plausible last-sync time', () => {
  assert.equal(P.googleState(google({ session_verified: true, stale: false, last_sync: now / 1000 - 10 }), now).verified, true);
  for (const extra of [{ stale: true }, { session_verified: false }, { configured: false }, { last_sync: now / 1000 + 1 }, { last_sync: 0 }, { last_sync: 'yesterday' }, { last_sync: now / 1000 - 660 }, { job: { status: 'failed' } }]) {
    assert.notEqual(P.googleState(google({ session_verified: true, stale: false, last_sync: now / 1000 - 10, ...extra }), now).verified, true);
  }
});
test('saved client and queued sync do not claim completed sync', () => {
  assert.equal(P.googleState(google(), now).label, 'Authorisation / sync required');
  assert.equal(P.googleState(google({ job: { status: 'queued' } }), now).label, 'Sync in progress');
  assert.deepEqual(P.googleState(google({ job: { status: 'running' } }), now).actions, ['disconnect']);
  assert.deepEqual(P.googleState(google({ configured: false }), now).actions, []);
  assert.deepEqual(P.googleState(google({ keychain_helper: false }), now).actions, []);
  assert.deepEqual(P.googleState({ success: false, configured: true }, now).actions, []);
});
test('Google reconnect requires reported prior authorisation or sync evidence', () => {
  assert.deepEqual(P.googleState(google(), now).actions, ['connect', 'sync', 'disconnect']);
  assert.deepEqual(P.googleState(google({ oauth_status: 'authorised' }), now).actions, ['reconnect', 'sync', 'disconnect']);
  assert.deepEqual(P.googleState(google({ oauth_status: 'authorising' }), now).actions, ['disconnect']);
});
test('requested scopes are never shown as granted permissions', () => {
  const h = P.googleState(google({ scopes: ['gmail.readonly'], account: 'fixture@example.invalid', last_sync: now / 1000 - 10 }), now).health;
  assert.deepEqual(h.permissions, []); assert.deepEqual(h.requestedScopes, ['gmail.readonly']);
  assert.equal(h.account, 'fixture@example.invalid'); assert.equal(h.lastSuccess, now - 10000);
  assert.deepEqual(P.health({ granted_scopes: ['calendar.events.readonly'] }).permissions, ['calendar.events.readonly']);
});
test('missing, future and malformed health timestamps stay unknown', () => {
  for (const value of [null, 0, -1, Infinity, '99', 'not-a-time', now / 1000 + 1]) assert.equal(P.timestamp(value, now), null);
  assert.equal(P.timestamp(new Date(now - 1000).toISOString(), now), now - 1000);
});
test('API save preserves blank secrets, allows empty nonsecret values and validates fields', () => {
  const card = P.catalogue(registry())[2];
  assert.deepEqual(P.settingsPayload(card, { secret_key: '  ', currency: '' }), { integration: 'stripe', values: { currency: '' }, clear: false });
  assert.deepEqual(P.settingsPayload(card, { secret_key: ' fixture ' }), { integration: 'stripe', values: { secret_key: 'fixture' }, clear: false });
  for (const values of [{ arbitrary: 'x' }, { currency: 3 }, { currency: 'x'.repeat(8193) }, { secret_key: '\u2022\u2022\u2022' }]) assert.throws(() => P.settingsPayload(card, values));
  assert.deepEqual(P.settingsPayload(card, {}, true), { integration: 'stripe', values: {}, clear: true });
  assert.throws(() => P.settingsPayload(P.catalogue(registry())[0], {}, true));
});
test('unsafe IDs, duplicate cards and invalid metadata cannot become controls', () => {
  const cards = P.catalogue(registry({ cards: [{ id: 'constructor' }, { id: 'bad"id' }, { id: 'stripe', fields: [] }, { id: 'stripe', fields: [] }] }));
  assert.equal(cards.length, 1); assert.equal(cards[0].id, 'stripe');
  assert.throws(() => P.catalogue({ cards: [] }));
});
test('portal links and OAuth links are constrained independently', () => {
  for (const value of ['javascript:alert(1)', 'http://example.com', 'https://user:pass@example.com', 'https://example.com/?api_key=fixture', '//example.com', 'https://example.com\\@other.test']) assert.equal(P.portal(value), null);
  assert.equal(P.portal('https://example.com/setup'), 'https://example.com/setup');
  assert.equal(P.authorizationURL('https://accounts.google.com/o/oauth2/v2/auth?state=fixture'), 'https://accounts.google.com/o/oauth2/v2/auth?state=fixture');
  for (const value of ['https://accounts.google.com.evil.test/o/oauth2/v2/auth', 'https://accounts.google.com/other', 'https://accounts.google.com:444/o/oauth2/v2/auth', 'http://accounts.google.com/o/oauth2/v2/auth']) assert.equal(P.authorizationURL(value), null);
});
test('local app detection never asserts installation, launch or authorisation', () => {
  const data = { success: true, providers: ['codex', 'claude', 'antigravity'].map(id => ({ id, ready: true })) };
  assert.match(P.providerState(data, 'codex').label, /CLI detected.*authorisation required/);
  assert.match(P.providerState(data, 'antigravity').label, /App data found.*authorisation required/);
  assert.deepEqual(P.providerState(data, 'claude').actions, []);
  assert.equal(P.providerState(null, 'codex').label, 'Detection unavailable');
});
test('capability catalogue is immutable and contains no setting or account values', () => {
  const rows = P.capabilities(P.catalogue(registry()), google({ account: 'private-fixture@example.invalid' }), null, now);
  assert.ok(Object.isFrozen(rows)); assert.ok(rows.every(row => Object.isFrozen(row) && Object.isFrozen(row.actions)));
  assert.doesNotMatch(JSON.stringify(rows), /private-fixture|must-never-render|AUD|csrf/);
});

// Minimal DOM boundary: exercise the actual registered renderer/event handlers
// against stubbed local fetch. No server, login, Keychain, audio or CLI is used.
function harness(options = {}) {
  const calls = [], hooks = [], registrations = {}, windowEvents = {}, documentEvents = {}, stored = new Map();
  const nodes = new Map();
  const host = { isConnected: true, dataset: {}, innerHTML: '', listeners: {}, classList: { add() {} }, setAttribute() {}, contains(node) { return node.owner === host; }, addEventListener(name, fn) { this.listeners[name] = fn; }, querySelector(selector) { if (!nodes.has(selector)) nodes.set(selector, { innerHTML: '', textContent: '', dataset: {}, setAttribute() {} }); return nodes.get(selector); }, querySelectorAll() { return []; } };
  const document = { documentElement: { dataset: {} }, hidden: false, querySelectorAll() { return []; }, addEventListener(name, fn) { documentEvents[name] = fn; } };
  let snapshot = google({ configured: false });
  const window = {
    U1ConnectionPolicy: P, U1CoreViews: { register(name, fn) { registrations[name] = fn; }, supports(name) { return name === 'jobs' && options.jobs === true; } },
    U1Platform: { open(name) { hooks.push(['platform', name]); } }, U1Reliability: { open(name) { hooks.push(['hub', name]); } }, U1Safety: { open() { hooks.push(['safety']); } },
    U1Launch: { preferences() { return { quality: 'auto', motion: 'full', skipBoot: false }; }, preview() { hooks.push(['boot']); } },
    U1Feedback: { preferences() { return { enabled: false, volume: 0.14 }; }, save(value) { hooks.push(['feedback-save', value]); }, async play(...args) { hooks.push(['sound', ...args]); return true; } },
    confirm() { return options.confirm !== false; }, addEventListener(name, fn) { windowEvents[name] = fn; }, dispatchEvent() {}
  };
  const context = { window, document, URL, AbortController, CustomEvent: class { constructor(type, data) { this.type = type; this.detail = data.detail; } }, localStorage: { getItem(key) { return stored.get(key) || null; }, setItem(key, value) { if (options.storageFails) throw Error('Fixture storage error'); stored.set(key, value); } }, setTimeout() { return 1; }, clearTimeout() {}, fetch: async (url, init) => {
    calls.push({ url, ...init });
    if (options.fetch) return options.fetch(url, init);
    const data = url === '/api/integrations' ? init.method === 'POST' ? { success: true } : registry() : url === '/api/workspace/google' ? snapshot : { success: true, providers: [] };
    return { ok: true, status: 200, async json() { return data; } };
  } };
  vm.runInNewContext(workspaceSource, context, { filename: 'u1-connections-workspace.js' });
  async function click(action, extra = {}) { const node = { owner: host, disabled: false, dataset: { ucAction: action, ...extra }, closest() { return this; } }; await host.listeners.click({ target: node }); }
  async function submit(values) {
    const inputs = Object.entries(values).map(([name, value]) => ({ name, value }));
    const form = { owner: host, dataset: { ucSettings: 'stripe' }, hasAttribute(name) { return name === 'data-uc-settings'; }, closest() { return this; }, querySelectorAll(selector) { return selector === '[data-uc-field]' ? inputs : inputs.filter(i => i.name === 'secret_key'); } };
    await host.listeners.submit({ target: form, preventDefault() {} }); return inputs;
  }
  return { window, document, registrations, host, nodes, calls, hooks, stored, click, submit, windowEvents, setGoogle(value) { snapshot = value; } };
}
test('both native views register and load only three local read endpoints', async () => {
  const h = harness(); assert.deepEqual(Object.keys(h.registrations), ['integrations', 'settings']);
  await h.registrations.integrations(h.host);
  assert.deepEqual(h.calls.map(c => c.url).sort(), ['/api/integrations', '/api/workspace/google', '/api/workspace/providers'].sort());
  assert.ok(h.calls.every(c => c.method === 'GET' && c.credentials === 'same-origin' && c.cache === 'no-store'));
  assert.doesNotMatch(h.host.innerHTML, /iframe|legacy-fixture-secret|legacy-calendar-fixture|must-never-render/);
  assert.match(h.host.innerHTML, /Settings saved \/ unverified/);
  assert.equal(h.hooks.length, 0);
});
test('native API save gets fresh CSRF, uses exact body and clears typed secret after success', async () => {
  const h = harness(); await h.registrations.integrations(h.host);
  const inputs = await h.submit({ secret_key: 'fixture-new-key', currency: 'AUD' });
  const post = h.calls.find(c => c.method === 'POST');
  assert.equal(post.url, '/api/integrations'); assert.equal(post.headers['X-U1-CSRF'], 'fixture-csrf-not-a-credential');
  assert.deepEqual(JSON.parse(post.body), { integration: 'stripe', values: { secret_key: 'fixture-new-key', currency: 'AUD' }, clear: false });
  assert.equal(inputs[0].value, ''); assert.match(h.nodes.get('[data-uc-status]').textContent, /Settings saved; account access not verified/);
  assert.equal(h.calls[h.calls.indexOf(post) - 1].method, 'GET');
});
test('clearing settings requires confirmation and is never a provider disconnect', async () => {
  const h = harness({ confirm: false }); await h.registrations.integrations(h.host); await h.click('clear', { ucProvider: 'stripe' });
  assert.ok(h.calls.every(c => c.method === 'GET'));
  const confirmed = harness(); await confirmed.registrations.integrations(confirmed.host); await confirmed.click('clear', { ucProvider: 'stripe' });
  assert.deepEqual(JSON.parse(confirmed.calls.find(c => c.method === 'POST').body), { integration: 'stripe', values: {}, clear: true });
});
test('unsupported Google actions do not send writes', async () => {
  const h = harness(); await h.registrations.integrations(h.host); await h.click('google', { ucGoogle: 'sync' });
  assert.ok(h.calls.every(c => c.method === 'GET'));
  assert.match(h.nodes.get('[data-uc-status]').textContent, /unavailable/);
});
test('a sync request uses the newer Google adapter and does not announce Synced', async () => {
  const h = harness(); h.setGoogle(google({ job: null })); await h.registrations.integrations(h.host);
  await h.click('google', { ucGoogle: 'sync' });
  const post = h.calls.find(c => c.method === 'POST'); assert.equal(post.url, '/api/workspace/google'); assert.deepEqual(JSON.parse(post.body), { action: 'sync' });
  assert.match(h.nodes.get('[data-uc-status]').textContent, /Sync requested/);
  assert.doesNotMatch(h.nodes.get('[data-uc-status]').textContent, /Synced|sync completed/);
});
test('Settings delegates controls, security, recovery and previews to existing APIs', async () => {
  const h = harness(); await h.registrations.settings(h.host);
  for (const target of ['controls', 'usage', 'notifications']) await h.click('platform', { ucTarget: target });
  await h.click('hub', { ucTarget: 'recovery' }); await h.click('safety'); await h.click('boot'); await h.click('sound');
  assert.deepEqual(h.hooks, [['platform', 'controls'], ['platform', 'usage'], ['platform', 'notifications'], ['hub', 'recovery'], ['safety'], ['boot'], ['sound', 'success', true]]);
  assert.ok(h.calls.every(c => c.method === 'GET'));
});
test('Settings uses parent native security/updater routes and offers Jobs only when registered', async () => {
  const h = harness(); await h.registrations.settings(h.host);
  assert.match(h.host.innerHTML, /data-go="security"/); assert.match(h.host.innerHTML, /data-go="updater"/);
  assert.doesNotMatch(h.host.innerHTML, /data-go="jobs"|iframe|\/classic|updater\.html/);
  const withJobs = harness({ jobs: true }); await withJobs.registrations.settings(withJobs.host);
  assert.match(withJobs.host.innerHTML, /data-go="jobs"/);
  assert.match(withJobs.host.innerHTML, /data-uc-target="recovery"/);
});
test('privacy applies real masking state and blocks API form submission', async () => {
  const h = harness(); await h.registrations.integrations(h.host);
  assert.equal(h.window.U1Connections.setPrivacy(true), true);
  assert.equal(h.document.documentElement.dataset.u1Sharing, 'true');
  assert.equal(h.stored.get('u1.connections.privacy.v1'), 'true');
  await h.submit({ secret_key: 'fixture' }); assert.ok(h.calls.every(c => c.method === 'GET'));
  assert.match(css, /html\[data-u1-sharing=true\] \[data-u1-private\]/);
  assert.match(css, /visibility:hidden!important;user-select:none!important;pointer-events:none!important/);
  assert.match(css, /prefers-reduced-motion:reduce/);
  assert.match(css, /data-u1-motion=reduced/);
});
test('privacy still applies when persistence is unavailable', () => {
  const h = harness({ storageFails: true });
  assert.equal(h.window.U1Connections.setPrivacy(true), false);
  assert.equal(h.document.documentElement.dataset.u1Sharing, 'true');
});
test('missing CSRF prevents POST and backend error bodies never enter the UI', async () => {
  const h = harness({ fetch: async url => ({ ok: true, status: 200, json: async () => url === '/api/integrations' ? registry({ csrf_token: '' }) : google({ configured: false }) }) });
  await h.registrations.integrations(h.host); await h.submit({ currency: 'AUD' });
  assert.ok(h.calls.every(c => c.method === 'GET'));
  assert.match(h.nodes.get('[data-uc-status]').textContent, /authorisation is unavailable/);
  const failed = harness({ fetch: async () => ({ ok: false, status: 503, json: async () => ({ error: 'credential-fixture-must-not-appear' }) }) });
  await failed.registrations.settings(failed.host);
  assert.doesNotMatch(failed.host.innerHTML + failed.nodes.get('[data-uc-status]').textContent, /credential-fixture/);
  assert.match(failed.host.innerHTML, /Safety Centre|Screen-sharing privacy/);
});
test('provider text is escaped and leaving a native view invalidates its actions', async () => {
  assert.equal(P.escape('<script>"&'), '&lt;script&gt;&quot;&amp;');
  const h = harness(); await h.registrations.integrations(h.host);
  h.windowEvents['u1:navigate']({ detail: { id: 'projects' } });
  await h.click('clear', { ucProvider: 'stripe' }); assert.ok(h.calls.every(c => c.method === 'GET'));
});
