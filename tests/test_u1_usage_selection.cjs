'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const core = require('../static/js/u1-platform-core.js');
const now = 1900000000000;
const row = (id, used, period = 'primary', reset = now / 1000 + 3600) => ({
  limit_id: id, name: id, used_percent: used, period, resets_at: reset,
});
const provider = windows => ({success: true, checked_at: now / 1000, windows});

test('Codex display never selects the separate Spark quota', () => {
  for (const windows of [[row('spark', 0), row('codex', 35)],
    [row('codex', 35), row('spark', 0)]]) {
    assert.equal(core.selectWindow(provider(windows), 'codex', now, now).used_percent, 35);
  }
});
test('Primary and secondary remain independently selectable', () => {
  const p = provider([row('codex', 60, 'secondary'), row('codex', 20)]);
  assert.equal(core.selectWindow(p, 'codex', now, now).used_percent, 20);
});
test('An expired general quota cannot fall back to Spark', () => {
  const p = provider([row('codex', 35, 'primary', now / 1000 - 1), row('spark', 0)]);
  assert.equal(core.selectWindow(p, 'codex', now, now), null);
});
test('Missing general quota stays unavailable', () => {
  assert.equal(core.selectWindow(provider([row('spark', 0)]), 'codex', now, now), null);
});
test('Provider timestamps, not merely fetch timestamps, bound freshness', () => {
  const p = provider([row('codex', 35)]);
  p.checked_at -= 121;
  assert.equal(core.selectWindow(p, 'codex', now, now), null);
  p.checked_at = now / 1000 + 31;
  assert.equal(core.selectWindow(p, 'codex', now, now), null);
});
test('Unknown, stale and invalid allowances are not zero', () => {
  for (const used of [null, undefined, NaN, Infinity, true, '35', -1, 101]) {
    assert.equal(core.selectWindow(provider([row('codex', used)]), 'codex', now, now), null);
  }
  assert.equal(core.selectWindow({...provider([row('codex', 35)]), stale: true}, 'codex', now, now), null);
  assert.equal(core.selectWindow(provider([row('codex', 35)]), 'codex', now - 121000, now), null);
});
test('A real zero and legacy named general windows remain supported', () => {
  assert.equal(core.selectWindow(provider([row('codex', 0)]), 'codex', now, now).used_percent, 0);
  const legacy = row('codex', 35);
  delete legacy.limit_id;
  assert.equal(core.selectWindow(provider([legacy]), 'codex', now, now).used_percent, 35);
});
