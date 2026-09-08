(function (global) {
  'use strict';
  var instances = new WeakMap();
  function hasSource(values, base) {
    return values.some(function (value) {
      if (!value || !String(value).trim()) return false;
      try { var url = new URL(value, base), page = new URL(base); url.hash = ''; page.hash = '';
        return /^(https?:|blob:|file:)$/.test(url.protocol) && url.href !== page.href;
      } catch (_) { return false; }
    });
  }
  function playerLabel(player, base) {
    var source = player && player.querySelector('source[src]');
    if (!player || !hasSource([player.getAttribute('src'), player.currentSrc, source && source.getAttribute('src')], base)) return 'Media / choose music or video';
    if (player.error) return 'Media / playback error';
    if (player.ended) return 'Media / playback ended';
    if (player.networkState === 2 && player.readyState < 2) return 'Media / loading';
    return player.paused ? 'Media / paused' : 'Media / playing';
  }
  function install(win) {
    if (instances.has(win)) return instances.get(win);
    var doc = win.document, hidden = new Map(), bound = new Map(), pending = false, stopped = false;
    var expanded = null, lastRailFocus = false, watchedControl = null;
    var events = ['loadedmetadata', 'play', 'pause', 'emptied', 'ended', 'error', 'loadstart', 'canplay'];
    function attr(node, key, value) { if (node.getAttribute(key) !== value) node.setAttribute(key, value); }
    function canFocus() { return !doc.querySelector('dialog[open], [role="dialog"][aria-modal="true"]') && doc.documentElement.dataset.u1Safety !== 'locked'; }
    function visible(node) { return node && !node.hidden && !node.disabled && !node.closest('[hidden], [inert]') && node.getClientRects().length > 0; }
    function restore(node, old) {
      node.hidden = old.hidden;
      ['aria-hidden', 'tabindex'].forEach(function (key) { if (old[key] === null) node.removeAttribute(key); else node.setAttribute(key, old[key]); });
      node.removeAttribute('data-u1-redundant-entry');
    }
    function refresh() {
      pending = false; if (stopped || !doc.body) return;
      doc.body.dataset.u1OperationalPolish = 'true';
      var runtimeControl = doc.getElementById('u1-control-open');
      if (runtimeControl && (runtimeControl.tagName !== 'BUTTON' || runtimeControl.dataset.platform !== 'controls')) runtimeControl = null;
      if (runtimeControl !== watchedControl) {
        controlObserver.disconnect(); watchedControl = runtimeControl;
        if (watchedControl) controlObserver.observe(watchedControl, { attributes: true, attributeFilter: ['aria-label'] });
      }
      if (runtimeControl) attr(runtimeControl, 'aria-label', 'Control Centre');
      doc.querySelectorAll('#rail button[data-platform="controls"], #u1-utility-shelf button[data-platform="controls"]').forEach(function (button) {
        attr(button, 'aria-label', 'Control Centre');
      });
      doc.querySelectorAll('#rail [data-go], #dock [data-go]').forEach(function (node) {
        if (node.dataset.go === doc.body.dataset.u1View) attr(node, 'aria-current', 'page'); else node.removeAttribute('aria-current');
      });
      var entry = doc.getElementById('u1-player-entry'), player = doc.getElementById('u1-local-media');
      var canonical = entry && entry.tagName === 'BUTTON' && entry.dataset.go === 'media' && entry.closest('#u1-utility-shelf');
      if (canonical) {
        var label = playerLabel(player, doc.baseURI);
        if (entry.textContent !== label) entry.textContent = label;
        attr(entry, 'aria-label', label + '. Open Media studio.');
      }
      if (player && !bound.has(player)) { events.forEach(function (event) { player.addEventListener(event, schedule); }); bound.set(player, true); }
      var candidates = new Set();
      if (canonical && visible(entry)) doc.querySelectorAll('#u1-utility-shelf button[data-go="media"], #u1-utility-shelf button[data-platform="media"], #u1-player-mini button[data-go="media"], #u1-player-mini button[data-platform="media"]').forEach(function (button) {
        if (button !== entry) candidates.add(button);
      });
      hidden.forEach(function (old, node) { if (!candidates.has(node)) { restore(node, old); hidden.delete(node); } });
      candidates.forEach(function (button) {
        if (!hidden.has(button)) hidden.set(button, { hidden: button.hidden, 'aria-hidden': button.getAttribute('aria-hidden'), tabindex: button.getAttribute('tabindex') });
        if (doc.activeElement === button && canFocus()) entry.focus({ preventScroll: true });
        if (!button.hidden) button.hidden = true;
        attr(button, 'aria-hidden', 'true'); attr(button, 'tabindex', '-1'); attr(button, 'data-u1-redundant-entry', 'true');
      });
      var menu = doc.getElementById('u1-menu-toggle'), rail = doc.getElementById('rail');
      if (menu && rail) {
        var open = menu.getAttribute('aria-expanded') === 'true';
        var active = doc.activeElement, inside = rail.contains(active);
        if (expanded === true && !open && win.matchMedia('(max-width: 700px)').matches && canFocus() && visible(menu)
            && (inside || (lastRailFocus && (!active || active === doc.body)))) menu.focus({ preventScroll: true });
        expanded = open; lastRailFocus = rail.contains(doc.activeElement);
      }
    }
    function schedule() { if (!pending && !stopped) { pending = true; win.requestAnimationFrame(refresh); } }
    function focus(event) { var rail = doc.getElementById('rail'); if (rail && rail.contains(event.target)) lastRailFocus = true;
      else if (event.target !== doc.body) lastRailFocus = false; }
    // Watch only the current runtime button's label. Our own correct write is a no-op here.
    var controlObserver = new win.MutationObserver(function () {
      if (watchedControl && watchedControl.getAttribute('aria-label') !== 'Control Centre') schedule();
    });
    var observer = new win.MutationObserver(schedule);
    observer.observe(doc.body, { childList: true, subtree: true, characterData: true, attributes: true,
      attributeFilter: ['aria-expanded', 'data-u1-view', 'hidden', 'disabled', 'inert', 'src'] });
    win.addEventListener('u1:navigate', schedule); win.addEventListener('resize', schedule); doc.addEventListener('focusin', focus);
    var api = { refresh: refresh, destroy: function () { stopped = true; observer.disconnect(); controlObserver.disconnect(); watchedControl = null;
      win.removeEventListener('u1:navigate', schedule); win.removeEventListener('resize', schedule); doc.removeEventListener('focusin', focus);
      bound.forEach(function (_, media) { events.forEach(function (event) { media.removeEventListener(event, schedule); }); });
      hidden.forEach(function (old, node) { restore(node, old); }); delete doc.body.dataset.u1OperationalPolish; instances.delete(win);
    } };
    instances.set(win, api); refresh(); return api;
  }
  var api = Object.freeze({ hasSource: hasSource, playerLabel: playerLabel, install: install });
  if (typeof module === 'object' && module.exports) module.exports = api;
  else { global.U1OperationalPolish = api; if (global.document.readyState === 'loading') global.document.addEventListener('DOMContentLoaded', function () { install(global); }, { once: true }); else install(global); }
})(typeof window !== 'undefined' ? window : globalThis);
