(function () {
  'use strict';
  var key = 'u1.activation.operator.v1', ids = ['google', 'codex', 'images', 'canva'];
  var active = null, controller = null, serial = 0, manual = emptyManual(), storedLocally = true;
  var labels = { recorded_success: 'Past success recorded', configured_unverified: 'Configured / unverified', setup_needed: 'Setup needed', unknown: 'Metadata unavailable', not_installed: 'Not installed', installed_unverified: 'Installed / unverified', unfinished_handoff: 'Unfinished / manual handoff' };
  function emptyManual() { var out = {}; ids.forEach(function (id) { out[id] = { steps: [false, false, false], reviewed_at: null }; }); return out; }
  function normalize(value) {
    var out = emptyManual(); if (!value || value.version !== 1 || !value.providers || typeof value.providers !== 'object') return out;
    ids.forEach(function (id) { var row = value.providers[id]; if (!row || typeof row !== 'object') return; if (Array.isArray(row.steps)) out[id].steps = [0, 1, 2].map(function (i) { return row.steps[i] === true; }); if (out[id].steps.every(Boolean) && typeof row.reviewed_at === 'number' && Number.isFinite(row.reviewed_at) && row.reviewed_at > 0 && row.reviewed_at <= Date.now()) out[id].reviewed_at = row.reviewed_at; }); return out;
  }
  function loadManual() { try { var raw = localStorage.getItem(key); manual = raw && raw.length <= 4096 ? normalize(JSON.parse(raw)) : emptyManual(); } catch (_) { storedLocally = false; manual = emptyManual(); } }
  function saveManual() { try { localStorage.setItem(key, JSON.stringify({ version: 1, providers: manual })); storedLocally = true; } catch (_) { storedLocally = false; } }
  function esc(value) { return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function locked() { return document.documentElement.dataset.u1Safety === 'locked' || !!(window.U1Safety && window.U1Safety.isLocked()); }
  function current(state) { return active === state && state.host.isConnected && !!state.host.querySelector('[data-activation-root]'); }
  function status(state, text, error) { if (!current(state)) return; var node = state.host.querySelector('[data-activation-status]'); node.textContent = text; node.setAttribute('role', error ? 'alert' : 'status'); }
  function stop() { serial += 1; if (controller) controller.abort(); controller = null; }
  function stamp(value) { return value ? new Date(value).toLocaleString() : 'No recorded success available'; }
  function recordText(id) { return manual[id].reviewed_at ? 'Operator review recorded ' + stamp(manual[id].reviewed_at) + '. Not API-verified.' : 'No operator review recorded. Checkmarks do not verify an account.'; }
  function render(state, data) {
    if (!current(state)) return;
    state.data = data;
    state.host.querySelector('[data-activation-evidence]').textContent = 'Local metadata read ' + stamp(data.checked_at * 1000) + '. No account requests, authentication probes or credential reads were performed.';
    state.host.querySelector('[data-activation-cards]').innerHTML = data.providers.filter(function (p) { return ids.includes(p.id); }).map(function (provider) {
      var e = provider.evidence || {}, row = manual[provider.id];
      var details = '<p>' + esc(e.source) + '</p><p>Historical result: ' + esc(stamp(e.evidence_at ? e.evidence_at * 1000 : null)) + '</p>';
      if (typeof e.helper_installed === 'boolean') details += '<p>Native helper executable: ' + (e.helper_installed ? 'present' : 'not detected') + '. This does not confirm Keychain access.</p>';
      var links = (provider.links || []).filter(function (link) { return ['https://console.cloud.google.com/apis/credentials', 'https://www.canva.com/', 'https://www.canva.dev/docs/connect/'].includes(link.url); }).map(function (link) { return '<a href="' + link.url + '" target="_blank" rel="noopener noreferrer">' + esc(link.label) + '</a>'; }).join('');
      var navigation = provider.route && ['integrations', 'ai', 'images'].includes(provider.route) ? '<button type="button" data-go="' + provider.route + '">Open ' + (provider.id === 'google' ? 'Connections' : esc(provider.name)) + '</button>' : '';
      if (provider.id === 'google') navigation += '<button type="button" data-activation-google>Google OAuth setup</button>';
      return '<article class="u1-activation-card" data-provider="' + provider.id + '"><div class="u1-activation-card-heading"><h3>' + esc(provider.name) + '</h3><span class="u1-activation-badge">' + esc(labels[provider.status] || 'Unknown') + '</span></div><div class="u1-activation-evidence">' + details + '</div><p class="u1-activation-billing">' + esc(provider.billing) + '</p><div class="u1-activation-actions">' + navigation + links + '</div><fieldset><legend>Operator checklist / one reviewed action</legend>' + provider.steps.slice(0, 3).map(function (step, index) { return '<label><input type="checkbox" data-activation-step="' + index + '" data-provider-id="' + provider.id + '"' + (row.steps[index] ? ' checked' : '') + '><span><b>' + (index + 1) + '.</b> ' + esc(step) + '</span></label>'; }).join('') + '</fieldset><div class="u1-activation-actions"><button type="button" data-activation-record="' + provider.id + '">Record my manual review</button><button type="button" data-activation-clear="' + provider.id + '">Clear my checklist</button></div><p class="u1-activation-manual" data-manual-provider="' + provider.id + '">' + esc(recordText(provider.id)) + '</p></article>';
    }).join('');
    var queue = data.queue || {};
    state.host.querySelector('[data-activation-queue]').textContent = queue.available ? 'Managed queue: ' + (queue.paused ? 'paused' : 'enabled') + ' / ' + queue.active_count + ' pending or running. Activation does not resume, submit or cancel jobs.' : 'Managed queue has not been inspected because its runtime is not loaded. Activation does not start it.';
  }
  async function refresh(state) {
    if (!current(state) || locked()) return;
    stop(); var requestSerial = ++serial, mine = new AbortController(); controller = mine;
    var timer = setTimeout(function () { mine.abort(); }, 8000);
    status(state, 'Reading local setup metadata only...');
    try {
      var response = await fetch('/api/workspace/activation', { method: 'GET', credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: mine.signal });
      var data = await response.json();
      if (!response.ok || data.success !== true || !Array.isArray(data.providers) || data.read_only !== true) throw Error('Local activation metadata is unavailable.');
      if (!current(state) || requestSerial !== serial || locked()) return;
      render(state, data); status(state, 'Setup evidence loaded. Operator records stay in this browser and never change provider verification.');
    } catch (_) { if (current(state) && requestSerial === serial) status(state, 'Activation metadata is unavailable or Safety stopped the read. No account action was performed.', true); }
    finally { clearTimeout(timer); if (controller === mine) controller = null; }
  }
  function mount(host) {
    stop(); var state = { host: host, data: null }; active = state; loadManual();
    host.classList.add('u1-native-workspace', 'u1-activation-workspace');
    host.innerHTML = '<section data-activation-root><header class="u1-core-header"><div><span class="u1-core-eyebrow">U1 WORKSPACE / ACCOUNT ACTIVATION</span><h2>Activate</h2><p>Review setup, choose one action, inspect the result.</p></div><button type="button" data-activation-refresh>Refresh local evidence</button></header><div class="u1-activation-intro"><strong>You control each provider action.</strong><p>This page checks local metadata only. It does not connect accounts, inspect credentials, send prompts or generate images. Open the provider view to review and perform one action.</p><p>Keep credentials in the native setup forms. Never paste keys or tokens into chat.</p></div><p data-activation-evidence class="u1-activation-meta">No metadata read yet.</p><p data-activation-status class="u1-activation-status" role="status" aria-live="polite"></p><div class="u1-activation-grid" data-activation-cards></div><p data-activation-queue class="u1-activation-meta"></p><p class="u1-activation-footer">Operator checklists contain only checkmarks and timestamps. They are local to this browser, may be cleared by the browser, and are never proof of API authorisation.</p></section>';
    host.addEventListener('click', function (event) {
      if (!current(state)) return;
      if (locked()) { event.preventDefault(); return; }
      var button = event.target.closest('button'); if (!button) return;
      if (button.hasAttribute('data-activation-refresh')) refresh(state);
      if (button.hasAttribute('data-activation-google')) { if (window.U1Reliability && typeof window.U1Reliability.open === 'function') window.U1Reliability.open('google', button); else status(state, 'Google setup is not loaded. Open Connections to review the available setup controls.', true); }
      var id = button.dataset.activationRecord;
      if (ids.includes(id)) { if (!manual[id].steps.every(Boolean)) { status(state, 'Complete your three review checklist items before recording a manual review.', true); return; } manual[id].reviewed_at = Date.now(); saveManual(); state.host.querySelector('[data-manual-provider="' + id + '"]').textContent = recordText(id); status(state, storedLocally ? 'Your review was recorded in this browser only. Provider API status is unchanged.' : 'Your review is available for this page session only; browser storage is unavailable. Provider API status is unchanged.', !storedLocally); }
      id = button.dataset.activationClear;
      if (ids.includes(id)) { manual[id] = { steps: [false, false, false], reviewed_at: null }; saveManual(); if (state.data) render(state, state.data); status(state, 'Operator checklist cleared. Provider evidence was not changed.'); }
    });
    host.addEventListener('change', function (event) {
      if (!current(state) || locked()) return;
      var target = event.target, id = target.dataset.providerId, index = Number(target.dataset.activationStep);
      if (!ids.includes(id) || !target.hasAttribute('data-activation-step') || ![0, 1, 2].includes(index)) return;
      manual[id].steps[index] = target.checked === true; manual[id].reviewed_at = null; saveManual();
      state.host.querySelector('[data-manual-provider="' + id + '"]').textContent = recordText(id);
      if (!storedLocally) status(state, 'Checklist changes are available for this page session only; browser storage is unavailable.', true);
    });
    refresh(state);
  }
  function init() {
    loadManual();
    if (window.U1CoreViews) ['activate', 'activation'].forEach(function (id) { window.U1CoreViews.register(id, mount); });
    document.addEventListener('u1:safety-change', function (event) { if (event.detail && event.detail.locked) stop(); });
    new MutationObserver(function () { if (document.documentElement.dataset.u1Safety === 'locked') stop(); }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-u1-safety'] });
    window.addEventListener('pagehide', stop);
    window.addEventListener('u1:navigate', function (event) { if (event.detail && !['activate', 'activation'].includes(event.detail.id)) stop(); });
  }
  window.U1Activation = Object.freeze({ mount: mount, stop: stop, normalizeManual: normalize });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true }); else init();
})();
