'use strict';
const test = require('node:test');
const assert = require('node:assert/strict');
const polish = require('../static/js/u1-operational-polish.js');

function fixture() {
  const nodes = [], listeners = new Map();
  const doc = { baseURI: 'http://localhost:8000/', readyState: 'complete', documentElement: { dataset: {} },
    querySelector(selector) { return selector.includes('dialog') && this.modal ? {} : null; },
    querySelectorAll(selector) {
      if (selector.includes('data-platform="controls"')) return nodes.filter(n => n.control);
      if (selector === '#rail [data-go], #dock [data-go]') return nodes.filter(n => n.nav);
      return nodes.filter(n => n.mediaEntry);
    },
    getElementById(id) { return nodes.find(n => n.id === id) || null; },
    addEventListener(type, fn) { listeners.set(type, fn); }, removeEventListener(type) { listeners.delete(type); }
  };
  function node(id, extra = {}) {
    const attrs = new Map();
    const n = { id, tagName: 'BUTTON', dataset: {}, hidden: false, disabled: false, textContent: '', handlers: new Map(),
      getAttribute(key) { return attrs.has(key) ? attrs.get(key) : null; },
      setAttribute(key, value) { attrs.set(key, String(value)); }, removeAttribute(key) { attrs.delete(key); },
      querySelector() { return null; }, getClientRects() { return this.layoutHidden ? [] : [{}]; },
      closest(selector) { if (selector === '#u1-utility-shelf') return this.shelf ? shelf : null; return this.inert ? rail : null; },
      contains(other) { return this === other || !!(other && other.parent === this); },
      focus() { doc.activeElement = this; },
      addEventListener(type, fn) { this.handlers.set(type, fn); }, removeEventListener(type) { this.handlers.delete(type); },
      ...extra
    }; nodes.push(n); return n;
  }
  const body = node('body', { dataset: { u1View: 'media' } }); doc.body = body; doc.activeElement = body;
  const shelf = node('u1-utility-shelf'), rail = node('rail');
  const menu = node('u1-menu-toggle'); menu.setAttribute('aria-expanded', 'false');
  const control = node('controls', { control: true, textContent: 'ControlControlCentre' });
  const primary = node('u1-player-entry', { shelf: true, mediaEntry: true, dataset: { go: 'media' } });
  const duplicate = node('duplicate', { shelf: true, mediaEntry: true, dataset: { platform: 'media' } });
  const player = node('u1-local-media', { tagName: 'VIDEO', currentSrc: 'blob:http://localhost:8000/actual', paused: false, currentTime: 42, controls: true, readyState: 4, networkState: 1 });
  const win = { document: doc, mobile: true, requestAnimationFrame() {}, matchMedia() { return { matches: this.mobile }; },
    MutationObserver: class { observe() {} disconnect() {} }, addEventListener() {}, removeEventListener() {} };
  return { win, doc, node, nodes, listeners, primary, duplicate, player, control, menu, rail };
}

test('Control Centre receives one accessible name without rewriting visible content', () => {
  const f = fixture(); polish.install(f.win); assert.equal(f.control.getAttribute('aria-label'), 'Control Centre'); assert.equal(f.control.textContent, 'ControlControlCentre');
});
test('blank and document URLs are not playable sources', () => {
  assert.equal(polish.hasSource(['', null, 'http://localhost:8000/#media'], 'http://localhost:8000/'), false);
  assert.equal(polish.hasSource(['javascript:x'], 'http://localhost:8000/'), false);
  assert.equal(polish.hasSource(['/api/media/file?id=1'], 'http://localhost:8000/'), true);
});
test('player label reports actual states without leaking filenames', () => {
  const f = fixture(); f.player.currentSrc = '/private-file.mp4';
  assert.equal(polish.playerLabel(f.player, f.doc.baseURI), 'Media / playing');
  f.player.paused = true; assert.equal(polish.playerLabel(f.player, f.doc.baseURI), 'Media / paused');
  f.player.networkState = 2; f.player.readyState = 1; assert.equal(polish.playerLabel(f.player, f.doc.baseURI), 'Media / loading');
  f.player.error = {}; assert.equal(polish.playerLabel(f.player, f.doc.baseURI), 'Media / playback error');
});
test('consolidation never changes player identity, position, playback or controls', () => {
  const f = fixture(), before = { parent: f.player.parent, currentTime: f.player.currentTime, paused: f.player.paused, controls: f.player.controls, currentSrc: f.player.currentSrc };
  f.player.play = f.player.pause = f.player.load = () => { throw Error('Forbidden media action'); };
  polish.install(f.win);
  for (const key of Object.keys(before)) assert.equal(f.player[key], before[key]);
  assert.equal(f.doc.getElementById('u1-local-media'), f.player); assert.equal(f.duplicate.hidden, true); assert.equal(f.player.hidden, false);
});
test('duplicate original accessibility state restored when primary unavailable', () => {
  const f = fixture(); f.duplicate.setAttribute('tabindex', '0');
  const instance = polish.install(f.win); f.primary.disabled = true; instance.refresh();
  assert.equal(f.duplicate.hidden, false); assert.equal(f.duplicate.getAttribute('tabindex'), '0'); assert.equal(f.duplicate.getAttribute('aria-hidden'), null);
});
test('hidden primary leaves other media entry usable', () => {
  const f = fixture(); f.primary.layoutHidden = true; polish.install(f.win); assert.equal(f.duplicate.hidden, false);
});
test('focused redundant entry moves focus to canonical entry', () => {
  const f = fixture(); f.doc.activeElement = f.duplicate; polish.install(f.win); assert.equal(f.doc.activeElement, f.primary);
});
test('exact navigation route gets aria-current', () => {
  const f = fixture(); const active = f.node('navmedia', { nav: true, dataset: { go: 'media' } });
  const other = f.node('navjobs', { nav: true, dataset: { go: 'jobs' } }); other.setAttribute('aria-current', 'page');
  polish.install(f.win); assert.equal(active.getAttribute('aria-current'), 'page'); assert.equal(other.getAttribute('aria-current'), null);
});
test('mobile menu close returns stranded rail focus to toggle', () => {
  const f = fixture(); f.menu.setAttribute('aria-expanded', 'true'); const item = f.node('railitem', { parent: f.rail }); f.doc.activeElement = item;
  const instance = polish.install(f.win); f.menu.setAttribute('aria-expanded', 'false'); instance.refresh(); assert.equal(f.doc.activeElement, f.menu);
});
test('no desktop, dialog, lock or outside focus stealing', () => {
  for (const mode of ['desktop', 'dialog', 'locked', 'outside']) {
    const f = fixture(); f.menu.setAttribute('aria-expanded', 'true'); const item = f.node('railitem', { parent: f.rail }); f.doc.activeElement = item;
    const instance = polish.install(f.win);
    if (mode === 'desktop') f.win.mobile = false;
    if (mode === 'dialog') f.doc.modal = true;
    if (mode === 'locked') f.doc.documentElement.dataset.u1Safety = 'locked';
    if (mode === 'outside') f.doc.activeElement = f.primary;
    const before = f.doc.activeElement; f.menu.setAttribute('aria-expanded', 'false'); instance.refresh(); assert.equal(f.doc.activeElement, before, mode);
  }
});
test('installation idempotent; cleanup restores duplicates and events', () => {
  const f = fixture(), instance = polish.install(f.win); assert.equal(polish.install(f.win), instance);
  instance.refresh(); assert.equal(f.player.handlers.size, 8); instance.destroy(); assert.equal(f.duplicate.hidden, false); assert.equal(f.player.handlers.size, 0);
});
test('does not overwrite loading, disabled, safety or motion preferences', () => {
  const f = fixture(); f.doc.body.dataset.motion = 'reduced'; f.control.disabled = true; f.control.setAttribute('aria-busy', 'true');
  polish.install(f.win); assert.equal(f.control.disabled, true); assert.equal(f.control.getAttribute('aria-busy'), 'true'); assert.equal(f.doc.body.dataset.motion, 'reduced');
});

test('observer-triggered refresh settles without rewriting the hidden attribute', () => {
  const f = fixture(), frames = [];
  let observer, isHidden = false, writes = 0;
  f.win.requestAnimationFrame = callback => { frames.push(callback); };
  f.win.MutationObserver = class {
    constructor(callback) { observer = callback; }
    observe() {}
    disconnect() { observer = null; }
  };
  // Reflect the browser behavior: even a same-value hidden assignment emits a mutation.
  Object.defineProperty(f.duplicate, 'hidden', {
    get() { return isHidden; },
    set(value) { isHidden = Boolean(value); writes++; if (observer) observer([{ type: 'attributes', attributeName: 'hidden', target: f.duplicate }]); }
  });
  const instance = polish.install(f.win);
  assert.equal(writes, 1);
  assert.equal(frames.length, 1);
  frames.shift()();
  assert.equal(writes, 1, 'The observer follow-up must not repeat the hidden write');
  assert.equal(frames.length, 0, 'The observer follow-up must settle rather than schedule another frame');
  instance.refresh();
  assert.equal(writes, 1);
  assert.equal(frames.length, 0);
  instance.destroy();
  assert.equal(isHidden, false, 'Cleanup still restores the original visibility');
});

function controlLifecycleFixture() {
  const f = fixture(), observers = [], frames = [];
  f.win.requestAnimationFrame = callback => { frames.push(callback); };
  f.win.MutationObserver = class {
    constructor(callback) { this.callback = callback; observers.push(this); }
    observe(target, options) { this.target = target; this.options = options; }
    disconnect() { this.target = null; }
  };
  function mutate(target, type, attributeName) {
    observers.forEach(observer => {
      const options = observer.options;
      if (!observer.target || (target !== observer.target && !options.subtree)) return;
      if (type === 'childList' && options.childList || type === 'attributes' && options.attributes && (!options.attributeFilter || options.attributeFilter.includes(attributeName))) {
        observer.callback([{ target, type, attributeName }]);
      }
    });
  }
  function addControl() {
    // Real runtime ID, deliberately outside both original container-selector fixtures.
    const button = f.node('u1-control-open', { dataset: { platform: 'controls' }, textContent: 'Control Centre' });
    button.labelWrites = 0;
    const set = button.setAttribute, remove = button.removeAttribute;
    button.setAttribute = function (key, value) { set.call(this, key, value); if (key === 'aria-label') this.labelWrites++; mutate(this, 'attributes', key); };
    button.removeAttribute = function (key) { remove.call(this, key); mutate(this, 'attributes', key); };
    mutate(f.doc.body, 'childList');
    return button;
  }
  function flush() {
    let count = 0;
    while (frames.length) {
      assert.ok(++count <= 4, 'Observer work must settle without a frame loop');
      frames.shift()();
    }
  }
  return { ...f, observers, frames, mutate, addControl, flush };
}

test('actual u1-control-open runtime ID gets one name outside the rail and shelf', () => {
  const f = controlLifecycleFixture(), button = f.addControl();
  const instance = polish.install(f.win); f.flush();
  assert.equal(button.getAttribute('aria-label'), 'Control Centre');
  assert.equal(button.labelWrites, 1);
  assert.equal(button.textContent, 'Control Centre');
  assert.equal(button.dataset.platform, 'controls');
  instance.destroy();
});

test('late-created and replaced runtime Control Centre buttons are repaired', () => {
  const f = controlLifecycleFixture(), instance = polish.install(f.win);
  const first = f.addControl();
  assert.equal(first.getAttribute('aria-label'), null);
  f.flush(); assert.equal(first.getAttribute('aria-label'), 'Control Centre');
  f.nodes.splice(f.nodes.indexOf(first), 1);
  const replacement = f.addControl(); f.flush();
  assert.equal(replacement.getAttribute('aria-label'), 'Control Centre');
  assert.equal(replacement.labelWrites, 1);
  assert.ok(!f.observers.some(observer => observer.target === first), 'Old button observer must be detached');
  instance.destroy();
});

test('runtime label repair is changed-only, scoped and stops on teardown', () => {
  const f = controlLifecycleFixture(), button = f.addControl(), instance = polish.install(f.win);
  f.flush(); assert.equal(f.frames.length, 0);
  const initialWrites = button.labelWrites;
  instance.refresh(); assert.equal(button.labelWrites, initialWrites);
  button.removeAttribute('aria-label');
  assert.equal(f.frames.length, 1); f.flush();
  assert.equal(button.getAttribute('aria-label'), 'Control Centre');
  assert.equal(button.labelWrites, initialWrites + 1);
  button.setAttribute('aria-label', 'ControlControl Centre'); f.flush();
  assert.equal(button.getAttribute('aria-label'), 'Control Centre');
  assert.equal(f.frames.length, 0);
  button.setAttribute('aria-label', 'Control Centre'); assert.equal(f.frames.length, 0, 'Correct-value writes must not schedule repair');
  f.mutate(f.control, 'attributes', 'aria-label'); assert.equal(f.frames.length, 0, 'Unrelated labels are not observed');
  instance.destroy(); button.removeAttribute('aria-label');
  assert.equal(f.frames.length, 0); assert.ok(f.observers.every(observer => !observer.target));
});
