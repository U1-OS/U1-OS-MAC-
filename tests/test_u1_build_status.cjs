const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const tracker = require('../static/js/u1-build-status.js');
const source = fs.readFileSync(path.join(__dirname, '../static/js/u1-build-status.js'), 'utf8');
const documentText = fs.readFileSync(path.join(__dirname, '../docs/BUILD-STATUS.md'), 'utf8');
const expectedTitles = [
  "Studio fixes",
  "Safety validation",
  "AI Command",
  "Navigation/search",
  "Job centre",
  "Release process",
  "Morning brief",
  "Top 3 priorities",
  "Day planning",
  "Life/business layouts",
  "Household organiser",
  "Wellbeing",
  "Visual document editor",
  "Actual PDF preview",
  "Fillable PDF",
  "Hyperlinked planner",
  "Course builder",
  "AI images",
  "Mockups",
  "Brand kit",
  "Product ZIP bundle",
  "Asset library",
  "Product catalogue",
  "Opportunity inbox",
  "Offers",
  "Pricing worksheet",
  "Launch board",
  "Actual sales/expenses",
  "Clients",
  "Selected AI context",
  "Voice",
  "Action previews",
  "Specialist roles",
  "War Room",
  "Improvement review",
  "Branded connections",
  "Connection health",
  "Google workflow",
  "Provider capability checks",
  "Separate usage dashboard",
  "Deduplicated 10% alerts",
  "Email PDF briefing",
  "Appointment review",
  "Social calendar",
  "Rights-aware media",
  "Actual clips",
  "Faceless workflow",
  "Market watchlists",
  "Price alerts",
  "Trading journal",
  "Paper research",
  "Lock/Pause/Stop",
  "Permission centre",
  "Keychain credentials",
  "Encrypted backups",
  "Privacy mode",
  "Shared design",
  "Purposeful motion/sounds",
  "Mac app",
  "GitHub presentation"
];

test('the requested tracker has exactly 60 unique, ordered IDs and exact titles', () => {
  assert.equal(tracker.items.length, 60);
  assert.deepEqual(tracker.items.map(item => item.id), Array.from({ length: 60 }, (_, index) => index + 1));
  assert.equal(new Set(tracker.items.map(item => item.id)).size, 60);
  assert.deepEqual(tracker.items.map(item => item.title), expectedTitles);
});
test('all rows have valid statuses, known sources, evidence and explicit limitations', () => {
  const allowed = ['local', 'setup', 'partial', 'in_progress', 'unverified'];
  assert.deepEqual(Object.keys(tracker.states).sort(), allowed.sort());
  for (const item of tracker.items) {
    assert.ok(allowed.includes(item.status), item.title);
    assert.ok(Object.hasOwn(tracker.sources, item.source), item.title);
    assert.ok(item.evidence.length > 20 && item.limitation.length > 20, item.title);
    assert.ok(item.route === null || tracker.safeRoute(item.route), item.title);
    assert.equal(Object.hasOwn(item, 'completed'), false);
  }
});
test('tracker metadata is immutable and has no completed status', () => {
  assert.ok(Object.isFrozen(tracker) && Object.isFrozen(tracker.items) && Object.isFrozen(tracker.states));
  assert.ok(tracker.items.every(Object.isFrozen));
  assert.ok(Object.values(tracker.states).every(Object.isFrozen));
  assert.ok(Object.values(tracker.sources).every(Object.isFrozen));
  assert.ok(tracker.testEvidence.every(Object.isFrozen));
  assert.equal(tracker.states.complete, undefined);
  assert.equal(tracker.states.done, undefined);
});
test('specific constrained features remain partial and Google remains setup-required', () => {
  for (const id of [35, 39, 51, 53, 54, 57, 58, 59]) assert.equal(tracker.items[id - 1].status, 'partial', 'Item ' + id);
  for (const id of [18, 38, 42, 43]) assert.equal(tracker.items[id - 1].status, 'setup', 'Item ' + id);
  assert.match(tracker.items[34].limitation, /not automated self-coding/);
  assert.match(tracker.items[52].limitation, /not a complete granular capability engine/);
  assert.match(tracker.items[53].limitation, /Legacy API-setting fields remain/);
  assert.match(tracker.items[58].limitation, /not notarised/);
  assert.match(tracker.items[54].evidence, /AES-GCM.*scrypt/);
  assert.match(tracker.items[54].limitation, /16 MiB.*without overwriting active data/);
});
test('status counts partition the scope without a completion percentage', () => {
  const counts = tracker.counts();
  assert.deepEqual(counts, { local: 35, setup: 4, partial: 20, in_progress: 1, unverified: 0 });
  assert.equal(Object.values(counts).reduce((sum, value) => sum + value, 0), 60);
  assert.ok(Object.isFrozen(counts));
  const html = tracker.render(() => true);
  assert.doesNotMatch(html, /<progress|\b60\s*\/\s*60\b|\b100\s*%|\d+(?:\.\d+)?%\s*(?:complete|done|finished)/i);
  assert.match(html, /Local implementation does not mean full acceptance/);
  assert.match(html, /This page performs no live checks/);
});
test('filters select every valid state independently and combine area with state', () => {
  for (const status of Object.keys(tracker.states)) {
    const result = tracker.filter(tracker.items, { status });
    assert.equal(result.length, tracker.counts()[status]);
    assert.ok(result.every(item => item.status === status));
  }
  const result = tracker.filter(tracker.items, { status: 'local', area: 'Creation' });
  assert.ok(result.length > 0 && result.every(item => item.area === 'Creation' && item.status === 'local'));
  assert.equal(tracker.filter(tracker.items, { status: 'completed' }).length, 0);
  assert.equal(tracker.filter(tracker.items, { area: 'invented area' }).length, 0);
});
test('case-insensitive word search includes IDs, sources and remaining boundaries', () => {
  assert.deepEqual(tracker.filter(tracker.items, { query: '#35' }).map(item => item.id), [35]);
  assert.deepEqual(tracker.filter(tracker.items, { query: '  GOOGLE   configured ', status: 'setup' }).map(item => item.id), [38, 42, 43]);
  assert.ok(tracker.filter(tracker.items, { query: 'handoff' }).length > 0);
  assert.equal(tracker.filter(tracker.items, { query: 'no-such-feature-fixture' }).length, 0);
  assert.equal(tracker.filter(tracker.items, {}).length, 60);
  assert.deepEqual(tracker.filter(null), []);
});
test('rendering escapes hostile text and rejects unsafe routes and states', () => {
  const hostile = { ...tracker.items[0], id: '" onclick="bad', title: '<img src=x onerror="bad">', area: '<script>bad</script>', evidence: '<svg onload="bad">', limitation: '"><script>bad</script>', source: 'constructor', route: 'settings" onclick="bad', status: 'local" onclick="bad' };
  const html = tracker.renderRows([hostile], () => true);
  assert.doesNotMatch(html, /<(?:img|script|svg)\b|<[^>]+\son[a-z]+\s*=/i);
  assert.match(html, /&lt;img/);
  assert.match(html, /data-build-state="unverified"/);
  assert.doesNotMatch(html, /data-go=/);
  assert.equal(tracker.escape('"&<>\''), '&quot;&amp;&lt;&gt;&#39;');
});
test('quicklinks require both a safe native route and an affirmative registry result', () => {
  for (const value of ['javascript:alert(1)', '/classic', 'https://example.test', '__proto__', 'constructor', 'jobs" onclick="bad']) assert.equal(tracker.safeRoute(value), null);
  assert.equal(tracker.safeRoute('security'), 'security');
  const allowed = tracker.renderRows([tracker.items[51]], route => route === 'security');
  assert.match(allowed, /data-go="security"/);
  const missing = tracker.renderRows([tracker.items[51]], () => false);
  assert.doesNotMatch(missing, /data-go=/); assert.match(missing, /disabled/);
  assert.doesNotMatch(tracker.renderRows([tracker.items[51]], () => { throw Error('Fixture'); }), /data-go=/);
});
test('empty filters produce an accessible table row rather than a false success state', () => {
  const html = tracker.renderRows([], () => true);
  assert.match(html, /<tr><td colspan="5"/);
  assert.match(html, /No items match/);
  assert.doesNotMatch(html, /complete|success/i);
});
test('parent evidence stays separately attributed and is not aggregated into acceptance', () => {
  assert.deepEqual(tracker.testEvidence.slice(0, 5).map(entry => [entry.id, entry.count]), [['existing', 90], ['safety', 12], ['private_backup', 4], ['release_guard', 4], ['routing', 3]]);
  assert.ok(tracker.testEvidence.slice(0, 5).every(entry => entry.provenance.includes('Parent-reported')));
  assert.equal(tracker.testEvidence[5].count, 23);
  assert.match(tracker.testEvidence[5].provenance, /Observed earlier/);
  assert.match(tracker.render(), /not a combined unique-test total/);
});
test('latest parent evidence distinguishes tests, syntax checks and real FFmpeg without inventing counts', () => {
  assert.equal(tracker.testEvidence.find(e => e.id === 'personal_workflows').count, 47);
  assert.equal(tracker.testEvidence.find(e => e.id === 'strict_gate').count, 289);
  assert.equal(tracker.testEvidence.find(e => e.id === 'strict_syntax').count, 32);
  assert.equal(tracker.testEvidence.find(e => e.id === 'strict_syntax').unit, 'syntax checks');
  assert.equal(tracker.testEvidence.find(e => e.id === 'real_ffmpeg').count, null);
  assert.equal(tracker.testEvidence.find(e => e.id === 'native_ai').count, 35);
  assert.equal(tracker.testEvidence.find(e => e.id === 'image_adapter').count, 26);
  assert.match(tracker.testEvidence.find(e => e.id === 'image_adapter').provenance, /mocked/);
  assert.equal(tracker.items[17].status, 'setup');
  assert.match(tracker.items[17].evidence, /gpt-image-1\.5/);
  assert.match(tracker.items[17].limitation, /live paid request are not verified/);
  assert.equal(tracker.items[45].status, 'local');
  assert.equal(tracker.items[48].status, 'partial');
  assert.equal(tracker.items[50].status, 'partial');
  assert.match(tracker.items[48].limitation, /no background live monitor/);
  assert.match(tracker.items[50].evidence, /Actual on-demand paper buys\/sells/);
  assert.equal(tracker.items[22].route, 'income');
  assert.equal(tracker.items[47].route, 'research');
  assert.match(tracker.render(), /32 syntax checks/);
  assert.doesNotMatch(tracker.render(), /32 tests \/ PASS/);
});
test('the documentation preserves the same 60 rows, statuses and no completion percentage', () => {
  const lines = documentText.split('\n').filter(line => /^\| \d+ \|/.test(line));
  assert.equal(lines.length, 60);
  for (const item of tracker.items) {
    const row = lines.find(line => line.startsWith('| ' + item.id + ' |'));
    assert.ok(row && row.includes('| ' + item.title + ' |') && row.includes('| ' + tracker.states[item.status].label + ' |'), item.title);
  }
  assert.match(documentText, /parent README/i);
  assert.doesNotMatch(documentText, /\b100\s*%|\b60\s*\/\s*60\b/);
});
function harness() {
  const views = {}, styles = new Map();
  const controls = {
    '[data-build-filters]': { listeners: {}, addEventListener(name, handler) { this.listeners[name] = handler; } },
    '[data-build-query]': { value: '' },
    '[data-build-status]': { value: 'all' },
    '[data-build-area]': { value: 'all' },
    '[data-build-rows]': { innerHTML: '' },
    '[data-build-results]': { textContent: '' }
  };
  const host = { innerHTML: '', classList: { add() {} }, querySelector(selector) { return controls[selector]; } };
  const root = {
    document: {
      head: { appendChild(style) { styles.set(style.id, style); } },
      getElementById(id) { return styles.get(id); }, createElement() { return {}; }
    },
    U1CoreViews: { register(id, mount) { views[id] = mount; }, supports(id) { return ['roadmap', 'studio', 'settings', 'integrations', 'security', 'updater', 'jobs'].includes(id); } },
    fetch() { throw Error('The tracker must not fetch.'); },
    localStorage: { getItem() { throw Error('The tracker must not access storage.'); }, setItem() { throw Error('The tracker must not write storage.'); } }
  };
  vm.runInNewContext(source, { window: root, fetch: root.fetch, localStorage: root.localStorage, console }, { filename: 'u1-build-status.js' });
  return { root, views, styles, controls, host };
}
test('the browser sidecar registers only the native roadmap without network or storage', () => {
  const h = harness();
  assert.deepEqual(Object.keys(h.views), ['roadmap']);
  h.views.roadmap(h.host);
  assert.match(h.host.innerHTML, /Build roadmap/);
  assert.match(h.host.innerHTML, /data-go="security"/);
  assert.doesNotMatch(h.host.innerHTML, /<iframe|\/classic|studio\.html/);
  assert.equal(h.styles.size, 1);
  assert.match(h.styles.get('u1-build-status-styles').textContent, /\.u1-build-status/);
  assert.match(h.styles.get('u1-build-status-styles').textContent, /prefers-reduced-motion:reduce/);
});
test('actual filter handlers update rows and reset without replacing the input form', () => {
  const h = harness(); h.views.roadmap(h.host);
  const form = h.controls['[data-build-filters]'], originalShell = h.host.innerHTML;
  h.controls['[data-build-status]'].value = 'setup'; form.listeners.change();
  assert.equal((h.controls['[data-build-rows]'].innerHTML.match(/data-build-item=/g) || []).length, 4);
  assert.match(h.controls['[data-build-results]'].textContent, /Showing 4 of 60/);
  assert.equal(h.host.innerHTML, originalShell);
  let prevented = false;
  form.listeners.reset({ preventDefault() { prevented = true; } });
  assert.ok(prevented); assert.equal(h.controls['[data-build-status]'].value, 'all');
  assert.equal((h.controls['[data-build-rows]'].innerHTML.match(/data-build-item=/g) || []).length, 60);
});
test('registration is idempotent and fails cleanly before the native core is loaded', () => {
  assert.equal(tracker.register({ document: {} }), false);
  const h = harness();
  assert.equal(h.root.U1BuildStatus.register(h.root), true);
  h.views.roadmap(h.host); h.views.roadmap(h.host);
  assert.equal(h.styles.size, 1);
  assert.deepEqual(Object.keys(h.views), ['roadmap']);
});
