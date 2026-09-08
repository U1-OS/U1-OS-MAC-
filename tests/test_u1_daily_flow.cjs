'use strict';
/* Isolated DOM fixtures only. No real DOM, accounts, backend or user records. */
const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const source = fs.readFileSync(path.join(__dirname, '../static/js/u1-daily-flow.js'), 'utf8');
const css = fs.readFileSync(path.join(__dirname, '../static/css/u1-daily-flow.css'), 'utf8');
const NOW = Date.parse('2026-09-08T00:30:00Z');
class Clock extends Date {
  constructor(...args) { super(...(args.length ? args : [NOW])); }
  static now() { return NOW; }
}
class Node {
  constructor() {
    this.innerHTML = ''; this.textContent = ''; this.dataset = {}; this.listeners = {};
    this.children = []; this.attributes = {}; this.isConnected = true; this.classList = { add() {} };
  }
  setAttribute(name, value) { this.attributes[name] = value; }
  addEventListener(name, callback) { (this.listeners[name] ||= []).push(callback); }
  appendChild(child) { this.children.push(child); child.parent = this; return child; }
  contains(child) { return child === this || child.owner === this || this.children.includes(child); }
  querySelector() { return null; }
  focus() { this.focused = true; }
  dispatch(name, event) { for (const listener of this.listeners[name] || []) listener(event); }
}
function priority(title, slot, extras = {}) { return { id: String(slot).repeat(32), kind: 'priority', title, archived: false, payload: { day: '2026-09-08', slot, done: false, ...extras } }; }
function task(title, due = '', done = false) { return { kind: 'task', title, payload: { due, done } }; }
function event(title, start, end = '', extras = {}) { return { kind: 'event', title, payload: { start, end, ...extras } }; }
function fixtures() {
  return {
    personal: { success: true, records: [priority('Second saved priority', 2), priority('First saved priority', 1)], timezone: 'Australia/Melbourne', today: '2026-09-08', generated_at: NOW / 1000 },
    prism: { success: true, profile: { timezone: 'Australia/Melbourne' }, records: [task('Saved first task'), task('Due today task', '2026-09-08'), event('Actual local appointment', '2026-09-08T01:00:00Z', '2026-09-08T02:00:00Z')] }
  };
}
function environment(options = {}) {
  const data = fixtures(), requests = [], views = new Map(), document = new Node(), home = new Node();
  document.readyState = options.readyState || 'complete'; document.hidden = false; document.body = new Node();
  document.body.dataset.u1View = options.visible || 'unrelated';
  document.createElement = () => new Node();
  document.getElementById = id => id === 'v-home' ? home : home.children.find(n => n.id === id) || null;
  const observers = [];
  class Observer { constructor(callback) { this.callback = callback; observers.push(this); } observe() {} }
  const U1Data = {
    get: async (url, config) => {
      requests.push({ url, config });
      if (options.read) return options.read(url, data, requests.length);
      return url.includes('/prism/') ? data.prism : data.personal;
    },
    post: () => { throw Error('Daily flow must never mutate records'); }
  };
  const context = { window: { U1Data, U1CoreViews: { register: (id, render) => views.set(id, render) } }, document, Date: Clock, Intl, MutationObserver: Observer, console };
  vm.runInNewContext(source, context, { filename: 'u1-daily-flow.js' });
  return { ...context, data, home, requests, views, observers, api: context.window.U1DailyFlow };
}
function click(host, dataset) {
  const button = { owner: host, dataset, hasAttribute: name => name === 'data-daily-step' && Object.hasOwn(dataset, 'dailyStep') };
  button.closest = () => button;
  host.dispatch('click', { target: button });
}
function change(host, value) { host.dispatch('change', { target: { value, matches: selector => selector === '[data-daily-tasks]' } }); }

test('registers only daily; installs one additive Home entry', () => {
  const e = environment();
  assert.deepEqual([...e.views.keys()], ['daily']);
  assert.equal(e.home.children.length, 1);
  assert.match(e.home.children[0].innerHTML, /data-go="daily"/);
  e.api.install(); e.api.attachHome();
  assert.equal(e.home.children.length, 1);
  assert.equal(e.requests.length, 0, 'hidden Home does not read sources on installation');
});
test('reads only local GET snapshots and retains chosen priority positions', async () => {
  const e = environment(), host = new Node();
  await e.views.get('daily')(host);
  assert.match(host.innerHTML, /First saved priority/);
  assert(host.innerHTML.indexOf('First saved priority') < host.innerHTML.indexOf('Second saved priority'));
  assert.match(host.innerHTML, /data-go="life"/);
  assert(e.requests.every(r => r.config.fresh === true));
  assert(e.requests.every(r => r.url === '/api/workspace/prism/summary' || /^\/api\/workspace\/personal\?collection=today&day=\d{4}-\d{2}-\d{2}&kind=priority&limit=3$/.test(r.url)));
  assert(!e.requests.some(r => /google|email|business|brief|integrations/.test(r.url)));
});
test('corrects date from server instead of trusting device date', async () => {
  const e = environment({ read: async (url, data) => {
    if (url.includes('/prism/')) return data.prism;
    return { ...data.personal, today: '2026-09-09', records: [priority('Correct server day', 1, { day: '2026-09-09' })] };
  } });
  const host = new Node(); await e.api.mount(host);
  assert(e.requests.some(r => r.url.includes('day=2026-09-09')));
  assert.match(host.innerHTML, /Correct server day/);
  assert.match(host.innerHTML, /2026-09-09 \/ Australia\/Melbourne/);
});
test('partial source failure does not become fake empty priorities or hide calendar', async () => {
  const e = environment({ read: async (url, data) => { if (!url.includes('/prism/')) throw Error('Local planning offline'); return data.prism; } });
  const host = new Node(); await e.api.mount(host);
  assert.match(host.innerHTML, /Priorities are unavailable/);
  assert.doesNotMatch(host.innerHTML, /Room for a priority/);
  click(host, { dailyStep: '1' });
  assert.match(host.innerHTML, /Actual local appointment/);
});
test('calendar failure is not labelled a free day and tasks are not invented', async () => {
  const e = environment({ read: async (url, data) => { if (url.includes('/prism/')) throw Error('Calendar reader offline'); return data.personal; } });
  const host = new Node(); await e.api.mount(host);
  assert.match(host.innerHTML, /Local tasks unavailable/);
  click(host, { dailyStep: '1' });
  assert.match(host.innerHTML, /Calendar unavailable/);
  assert.doesNotMatch(host.innerHTML, /No local events saved for today/);
});
test('three explicit steps link to the actual review queue and daily brief', async () => {
  const e = environment(), host = new Node(); await e.api.mount(host);
  click(host, { dailyAction: 'next' });
  assert.match(host.innerHTML, /data-go="calendar"/);
  click(host, { dailyAction: 'next' });
  assert.match(host.innerHTML, /data-platform="drafts"/);
  assert.match(host.innerHTML, /data-platform="briefing"/);
  assert.match(host.innerHTML, /Google email requires an authorised connection and a successful sync/);
  assert.match(host.innerHTML, /data-go="integrations"/);
  assert.doesNotMatch(host.innerHTML, /data-go="(?:drafts|briefing|business)"/);
  click(host, { dailyAction: 'back' });
  assert.match(host.innerHTML, /02 \/ SCHEDULE/);
});
test('genuine empty snapshots show explicit empty states without sample data', async () => {
  const e = environment(); e.data.personal.records = []; e.data.prism.records = [];
  const host = new Node(); await e.api.mount(host);
  assert.equal((host.innerHTML.match(/Room for a priority/g) || []).length, 3);
  assert.match(host.innerHTML, /No open tasks in this snapshot/);
  click(host, { dailyStep: '1' });
  assert.match(host.innerHTML, /No local events saved for today/);
  assert.doesNotMatch(host.innerHTML, /Actual local appointment|Saved first task/);
});
test('filters complete/deleted tasks, preserves saved order, and supports due-today selection', async () => {
  const e = environment();
  e.data.prism.records = [task('Z saved first'), task('A saved second', '2026-09-08'), task('Completed hidden', '', true), { ...task('Deleted hidden'), deleted: 1 }];
  const host = new Node(); await e.api.mount(host);
  assert(host.innerHTML.indexOf('Z saved first') < host.innerHTML.indexOf('A saved second'));
  assert.doesNotMatch(host.innerHTML, /Completed hidden|Deleted hidden/);
  change(host, 'today');
  assert.match(host.innerHTML, /A saved second/); assert.doesNotMatch(host.innerHTML, /Z saved first/);
});
test('calendar uses workspace date, includes overnight events and excludes midnight-exclusive ends', async () => {
  const e = environment();
  e.data.prism.records = [
    event('Overnight retained', '2026-09-07T23:00:00+10:00', '2026-09-08T01:00:00+10:00'),
    event('Ends at midnight hidden', '2026-09-07T23:00:00+10:00', '2026-09-08T00:00:00+10:00'),
    event('UTC previous date local today', '2026-09-07T23:00:00Z', '2026-09-08T00:00:00Z'),
    event('Tomorrow hidden', '2026-09-09T10:00:00+10:00'),
    event('Naive workspace local', '2026-09-08T12:30:00'),
    event('Invalid time hidden', 'not a date')
  ];
  const host = new Node(); await e.api.mount(host); click(host, { dailyStep: '1' });
  assert.match(host.innerHTML, /Overnight retained/); assert.match(host.innerHTML, /UTC previous date local today/);
  assert.match(host.innerHTML, /Naive workspace local/); assert.match(host.innerHTML, /Saved without a UTC offset/);
  assert.doesNotMatch(host.innerHTML, /Ends at midnight hidden|Tomorrow hidden|Invalid time hidden/);
  assert.match(host.innerHTML, /1 event\(s\) and 0 task\(s\) could not be read/);
});
test('escapes untrusted titles, notes, locations and source errors', async () => {
  const e = environment();
  e.data.personal.records = [priority('<img src=x onerror=alert(1)>', 1, { notes: '<script>bad()</script>' })];
  e.data.prism.records = [event('Meeting <svg onload=bad()>', '2026-09-08T12:00:00+10:00', '', { location: '<iframe src=x>' })];
  const host = new Node(); await e.api.mount(host);
  assert.match(host.innerHTML, /&lt;img/); assert.doesNotMatch(host.innerHTML, /<img|<script/);
  click(host, { dailyStep: '1' }); assert.doesNotMatch(host.innerHTML, /<svg|<iframe/);
  assert.match(host.innerHTML, /&lt;iframe/);
});
test('malformed snapshots are unavailable and malformed priorities are flagged', async () => {
  const e = environment(); e.data.prism.records = {}; e.data.personal.records = [priority('Good', 1), priority('Duplicate', 1), priority('Wrong date', 2, { day: '2026-09-07' })];
  const host = new Node(); await e.api.mount(host);
  assert.match(host.innerHTML, /Some priority records could not be shown/);
  assert.match(host.innerHTML, /Slot could not be confirmed/);
  assert.match(host.innerHTML, /Local tasks unavailable/);
});
test('labels real source timestamps, retrieval times and source-declared staleness', async () => {
  const e = environment(); e.data.personal.stale = true;
  const host = new Node(); await e.api.mount(host);
  assert.match(host.innerHTML, /Source snapshot/); assert.match(host.innerHTML, /SOURCE MARKED STALE/);
  assert.match(host.innerHTML, /Source snapshot timestamp not supplied/);
  assert.match(host.innerHTML, /Refresh to read again/);
});
test('Home preview uses actual record counts and links to native daily view', async () => {
  const e = environment(); await e.api.refresh();
  const html = e.home.children[0].innerHTML;
  assert.match(html, /First saved priority/); assert.match(html, /1 local event/);
  assert.match(html, /2 open tasks/); assert.match(html, /data-go="daily"/);
});
test('refresh is shared across mounts and does not add duplicate handlers', async () => {
  let releases = [];
  const e = environment({ read: (url, data) => new Promise(resolve => releases.push(() => resolve(url.includes('/prism/') ? data.prism : data.personal))) });
  const a = new Node(), b = new Node();
  const requests = [e.api.mount(a), e.api.mount(a), e.api.mount(b)];
  assert.equal(e.requests.length, 2);
  releases.forEach(done => done()); await Promise.all(requests);
  assert.equal(a.listeners.click.length, 1); assert.equal(b.listeners.click.length, 1);
});
test('safety lock clears visible private content and discards in-flight results', async () => {
  let releases = [];
  const e = environment({ read: (url, data) => new Promise(resolve => releases.push(() => resolve(url.includes('/prism/') ? data.prism : data.personal))) });
  const host = new Node(), work = e.api.mount(host);
  e.document.dispatch('u1:safety-change', { detail: { locked: true } });
  releases.forEach(done => done()); await work;
  assert.match(host.innerHTML, /Unlock U1 OS/);
  assert.doesNotMatch(host.innerHTML, /First saved priority/);
  const before = e.requests.length; await e.api.refresh(); assert.equal(e.requests.length, before);
});
test('CSS stays scoped, supplies contrast tokens, mobile layout and reduced motion', () => {
  assert.match(css, /--u1df-ink:#f1f8ff/); assert.match(css, /--u1df-bg:#071626/);
  assert.match(css, /prefers-reduced-motion:reduce/); assert.match(css, /max-width:600px/);
  assert.match(css, /:focus-visible/); assert.doesNotMatch(css, /(?:^|\n)(?:body|:root|\.view|button)\s*[{,]/);
  function luminance(hex) {
    const n = hex.match(/../g).map(v => parseInt(v, 16) / 255).map(v => v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
    return .2126 * n[0] + .7152 * n[1] + .0722 * n[2];
  }
  function contrast(a, b) { const values = [luminance(a), luminance(b)].sort((x, y) => y - x); return (values[0] + .05) / (values[1] + .05); }
  assert(contrast('b5cadc', '0c2337') >= 4.5, 'muted body text meets AA on the panel');
  assert(contrast('052333', '91e7ff') >= 4.5, 'primary button text meets AA');
});
