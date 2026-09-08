/* Fixed local-tool inventory. No tool execution, automatic research or network probing. */
(function () {
  'use strict';
  var registered = false, root, inFlight = null;
  function esc(value) { return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function stateLabel(value) { return { desktop_only: 'Desktop only', plugin_only: 'Developer plugin', setup_needed: 'Setup needed', review_required: 'Review needed' }[value] || 'Not checked'; }
  function card(tool) {
    var link = '';
    try { var url = new URL(tool.documentation_url); if (url.protocol === 'https:' && url.hostname === 'github.com' && !url.username && !url.password) link = '<a href="' + esc(url.href) + '" target="_blank" rel="noopener noreferrer">Project documentation (external)</a>'; } catch (error) { /* No documentation URL supplied. */ }
    return '<article class="u1-mr-card"><header><h2>' + esc(tool.name) + '</h2><span class="u1-mr-label">' + stateLabel(tool.state) + '</span></header>' +
      '<p>' + esc(tool.kind) + '</p><p class="u1-mr-note"><strong>Repository / ' + esc(tool.repository.state) + '</strong><br><code>' + esc(tool.repository.path) + '</code></p>' +
      '<p class="u1-mr-note"><strong>Desktop launcher / ' + esc(tool.launcher.state) + '</strong><br>' + (tool.launcher.path ? '<code>' + esc(tool.launcher.path) + '</code>' : 'No Desktop launcher associated with this repository.') + '</p>' +
      (tool.configured_local_url ? '<p class="u1-mr-note">Configured address: <code>' + esc(tool.configured_local_url) + '</code><br>Address read from launcher metadata; service availability is not checked.</p>' : '') +
      '<p>' + esc(tool.note) + '</p><p class="u1-mr-note">' + esc(tool.limitation) + '</p>' + link + '</article>';
  }
  async function refresh() {
    if (inFlight) return inFlight;
    var status = root.querySelector('[data-tools-status]'), button = root.querySelector('[data-tools-refresh]');
    status.textContent = 'Reading fixed local paths and launcher metadata...'; button.disabled = true;
    inFlight = (async function () {
      var controller = new AbortController(), timer = setTimeout(function () { controller.abort(); }, 10000);
      try {
        var response = await fetch('/api/workspace/osint-tools', { cache: 'no-store', credentials: 'same-origin', signal: controller.signal });
        var result = await response.json();
        if (!response.ok || result.success !== true || !Array.isArray(result.tools)) throw Error(result.error || 'The local inventory is unavailable.');
        root.querySelector('[data-tools-cards]').innerHTML = result.tools.map(card).join('');
        status.textContent = 'Metadata checked ' + new Date(result.checked_at).toLocaleString() + '. No tool or network query was started.';
        status.dataset.error = 'false';
      } catch (error) {
        status.textContent = error.name === 'AbortError' ? 'The local metadata request timed out. Try refreshing.' : error.message;
        status.dataset.error = 'true';
      } finally { clearTimeout(timer); button.disabled = false; inFlight = null; }
    })();
    return inFlight;
  }
  async function mount(host) {
    var first = !root;
    if (first) {
      root = document.createElement('section'); root.className = 'u1-mr';
      root.innerHTML = '<aside class="u1-mr-nav"><p class="u1-mr-eyebrow">RESEARCH / LOCAL TOOLS</p><button type="button" data-tools-casebook>Research casebook<span>Sources and evidence</span></button><button type="button" aria-current="page">Desktop tools<span>Inventory and setup</span></button></aside>' +
        '<div class="u1-mr-main"><header class="u1-mr-heading"><p class="u1-mr-eyebrow">U1 / TOOL INVENTORY</p><h1>Know what is actually here.</h1><p>Eight repository candidates, with their actual Desktop mapping. Five matching launchers were found in the discovery snapshot; Ponytail is a developer plugin.</p></header>' +
        '<div class="u1-mr-actions"><button type="button" data-tools-refresh>Refresh local inventory</button></div><p class="u1-mr-status" data-tools-status role="status" aria-live="polite"></p>' +
        '<div class="u1-mr-grid" data-tools-cards></div><footer class="u1-mr-footer">This starter reads fixed metadata paths only. Launches, account checks, private-person searches and automatic scans are unavailable. Documentation links open external sites only when clicked.</footer></div>';
      root.querySelector('[data-tools-refresh]').addEventListener('click', refresh);
      root.querySelector('[data-tools-casebook]').addEventListener('click', function () { if (window.U1Platform) window.U1Platform.open('osint'); });
    }
    if (root.parentNode !== host) host.replaceChildren(root);
    if (first) await refresh();
  }
  function register() {
    if (registered) return true;
    if (!window.U1CoreViews) return false;
    window.U1CoreViews.register('osint-tools', mount); registered = true;
    document.dispatchEvent(new CustomEvent('u1:native-views-ready', { detail: { ids: ['osint-tools'] } }));
    return true;
  }
  window.U1OSINTTools = Object.freeze({ register: register, mount: mount, refresh: function () { return root ? refresh() : Promise.resolve(); } });
  register(); document.addEventListener('u1:core-views-ready', register);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', register, { once: true });
})();
