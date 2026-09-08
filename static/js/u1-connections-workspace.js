/* Native Connections and Settings. The parent owns script/style inclusion. */
(function () {
  'use strict';
  var P = window.U1ConnectionPolicy, active = null, sequence = 0, poll = null, busy = false;
  var privacyKey = 'u1.connections.privacy.v1', sharing = false, bound = new WeakSet();
  var readPaths = ['/api/integrations', '/api/workspace/google', '/api/workspace/providers'];
  var writePaths = ['/api/integrations', '/api/workspace/google'];
  if (!P || !window.U1CoreViews || typeof window.U1CoreViews.register !== 'function') {
    window.U1Connections = Object.freeze({ ready: false, setupNeeded: 'Load U1ConnectionPolicy and U1CoreViews before the Connections workspace.' });
    return;
  }
  var esc = P.escape;
  try { sharing = localStorage.getItem(privacyKey) === 'true'; } catch (_) { /* Session preference remains available. */ }
  function applyPrivacy() { document.documentElement.dataset.u1Sharing = String(sharing); }
  function setPrivacy(value) {
    sharing = value === true; applyPrivacy();
    var persisted = true;
    try { localStorage.setItem(privacyKey, String(sharing)); } catch (_) { persisted = false; }
    document.querySelectorAll('[data-uc-privacy]').forEach(function (input) { input.checked = sharing; });
    document.querySelectorAll('[data-uc-sharing-state]').forEach(function (node) { node.textContent = sharing ? 'Screen-sharing masks on' : 'Private details visible'; });
    window.dispatchEvent(new CustomEvent('u1:privacy-change', { detail: { enabled: sharing, persisted: persisted } }));
    return persisted;
  }
  applyPrivacy();
  function current(state) { return active === state && state.host.isConnected && state.host.dataset.ucView === state.view; }
  function method(object, name) { return !!object && typeof object[name] === 'function'; }
  function button(label, action, extra, enabled) {
    return '<button type="button" data-uc-action="' + action + '"' + (extra || '') + (enabled === false ? ' disabled data-uc-disabled="true"' : '') + '>' + esc(label) + '</button>';
  }
  function routeButton(label, view) { return '<button type="button" data-go="' + view + '">' + esc(label) + '</button>'; }
  function link(label, url) { return url ? '<a href="' + esc(url) + '" target="_blank" rel="noopener noreferrer" referrerpolicy="no-referrer">' + esc(label) + '</a>' : ''; }
  function pill(state) { return '<span class="uc-state" data-tone="' + state.tone + '">' + esc(state.label) + '</span>'; }
  function brand(name) { return '<span class="uc-wordmark">' + esc(name) + '</span>'; }
  function stamp(value) { return value ? new Date(value).toLocaleString() : 'Not reported'; }
  function health(details) {
    return '<dl class="uc-health"><div><dt>Last reported account</dt><dd class="uc-private"><span data-u1-private>' + esc(details.account || 'Not reported') + '</span></dd></div><div><dt>Granted permissions</dt><dd>' + esc(details.permissions.length ? details.permissions.join(', ') : 'Not reported by this adapter') + '</dd></div><div><dt>Last successful operation</dt><dd>' + esc(stamp(details.lastSuccess)) + '</dd></div></dl>';
  }
  function status(state, message, error) {
    if (!current(state)) return;
    var node = state.host.querySelector('[data-uc-status]');
    if (node) { node.textContent = message; node.dataset.error = String(!!error); node.setAttribute('role', error ? 'alert' : 'status'); }
  }
  async function request(path, body, csrf) {
    var writing = body !== undefined;
    if (!(writing ? writePaths : readPaths).includes(path)) throw new Error('This workspace does not support that endpoint.');
    var controller = new AbortController(), timer = setTimeout(function () { controller.abort(); }, writing ? 45000 : 12000);
    try {
      var response = await fetch(path, { method: writing ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store', redirect: 'error', signal: controller.signal, headers: writing ? { 'Content-Type': 'application/json', 'X-U1-CSRF': csrf } : { Accept: 'application/json' }, body: writing ? JSON.stringify(body) : undefined });
      if (!response.ok) throw new Error(response.status === 403 ? 'The local server requires a fresh authorisation check. Refresh status before retrying.' : 'The local service declined the request (HTTP ' + response.status + ').');
      var data;
      try { data = await response.json(); } catch (_) { throw new Error('The local service returned an unreadable response. Refresh status before retrying.'); }
      if (!data || typeof data !== 'object' || Array.isArray(data) || data.success !== true) throw new Error('The local service did not confirm success. Review setup and refresh status before retrying.');
      return data;
    } catch (error) {
      if (error.name === 'AbortError' || error instanceof TypeError) throw new Error(writing ? 'The action outcome is unknown because the local request did not finish. Refresh status before retrying.' : 'Local status is unavailable. Start U1 OS with its launcher and refresh.');
      throw error;
    } finally { clearTimeout(timer); }
  }
  async function mutate(state, path, payload) {
    var registry = await request('/api/integrations');
    if (!current(state)) throw new Error('The view changed before the action was sent.');
    if (typeof registry.csrf_token !== 'string' || !registry.csrf_token || registry.csrf_token.length > 512) throw new Error('Local authorisation is unavailable. Refresh before retrying.');
    return request(path, payload, registry.csrf_token);
  }
  function busyUI(state) {
    if (!current(state)) return;
    state.host.setAttribute('aria-busy', String(busy));
    state.host.querySelectorAll('[data-uc-mutating], [data-uc-action="refresh"], [data-uc-settings] input').forEach(function (node) { node.disabled = busy || node.dataset.ucDisabled === 'true'; });
  }
  async function perform(state, action) {
    if (busy || !current(state)) return;
    busy = true; busyUI(state); status(state, 'Requesting the selected action...');
    try { status(state, await action()); }
    catch (error) { status(state, error.message, true); }
    finally { busy = false; if (active) busyUI(active); }
  }
  function googleCards(state) {
    var model = P.googleState(state.google), cards = state.cards.filter(function (card) { return P.googleId(card.id); });
    if (!cards.length) cards = [{ id: 'gmail', name: 'Gmail' }, { id: 'google_calendar', name: 'Google Calendar' }];
    return cards.map(function (card, index) {
      var actions = model.actions.map(function (action) { return button({ connect: 'Connect', reconnect: 'Reconnect', sync: 'Sync', disconnect: 'Disconnect' }[action], 'google', ' data-uc-google="' + action + '" data-uc-mutating'); }).join('');
      var setup = !model.helper ? 'Build the local Keychain helper, then open Google setup.' : !model.configured ? 'Add a Desktop app OAuth client in Google setup. Account consent is still required.' : 'Connect opens a consent link. Sync requests a read-only job; completion is shown only when reported.';
      return '<article class="uc-card uc-google"><div class="uc-card-top">' + brand(card.name) + pill(model) + '</div><h3>' + (card.id === 'gmail' ? 'Your inbox, with permission.' : 'A calendar you can review.') + '</h3><p>' + (card.id === 'gmail' ? 'Read recent Gmail messages and review local drafts. This connector cannot send email.' : 'Read the primary calendar. Changes to your local calendar require review; Google events are not edited.') + '</p>' + health(model.health) + '<details class="uc-permissions"><summary>Requested connector scopes</summary><p>' + esc(model.health.requestedScopes.length ? model.health.requestedScopes.join(', ') : 'Not returned. Open Google setup to review the connector.') + '</p><p>Requested scopes are not evidence of granted account permissions.</p></details><p class="uc-note">' + esc(setup) + '</p><p class="uc-note">Gmail and Calendar share one Google connection. Disconnect affects both; imported local records remain.</p><div class="uc-actions">' + actions + button('Google setup & review', 'hub', ' data-uc-target="google"', method(window.U1Reliability, 'open')) + '</div>' + (index === 0 && state.authURL && Date.now() < state.authExpires ? '<div class="uc-auth">' + link('Continue to Google in your browser', state.authURL) + '<p>Review consent, return here, then choose Sync. Account access is not yet verified.</p></div>' : '') + '</article>';
    }).join('');
  }
  function providerCard(card) {
    var model = P.settingsState(card);
    var editor = card.fields.length ? '<details class="uc-editor"><summary>Edit API settings</summary><form data-uc-settings="' + card.id + '" autocomplete="off"><p>Settings are saved in owner-only local configuration, which is not encrypted. Blank secret fields keep the saved secret. Saving does not verify account access.</p><div class="uc-fields">' + card.fields.map(function (field) {
      return '<label>' + esc(field.label) + '<span class="uc-field-state">' + (field.saved ? 'Saved value present' : 'No saved value reported') + '</span><span class="uc-private"><input data-u1-private data-uc-field name="' + field.id + '" type="' + (field.secret ? 'password' : 'text') + '" value="' + esc(field.secret ? '' : field.value) + '" maxlength="8192" autocomplete="' + (field.secret ? 'new-password' : 'off') + '" spellcheck="false" autocapitalize="none"' + (field.secret ? ' placeholder="Leave blank to keep a saved secret"' : '') + '></span></label>';
    }).join('') + '</div><div class="uc-actions"><button type="submit" data-uc-mutating>Save API settings</button>' + (card.savedFields || card.settingsSaved ? button('Clear saved settings', 'clear', ' data-uc-provider="' + card.id + '" data-uc-mutating') : '') + '</div></form></details>' : '<p class="uc-note">No editable account settings are exposed by this adapter. Install and configure the runtime separately.</p>';
    return '<article class="uc-card" data-uc-card="' + card.id + '"><div class="uc-card-top">' + brand(card.name) + pill(model) + '</div><span class="uc-category">' + esc(card.category) + '</span><h3>' + esc(card.name) + '</h3><p>' + esc(card.note || 'Account access is not verified by saving API settings.') + '</p>' + health(card.health) + editor + '<div class="uc-actions uc-card-footer">' + link('Provider setup website', card.portal) + '</div></article>';
  }
  function agentCards(state) {
    return ['codex', 'claude', 'antigravity'].map(function (key) {
      var provider = P.providerState(state.providers, key);
      return '<article class="uc-card"><div class="uc-card-top">' + brand(provider.name) + pill({ label: provider.label, tone: 'setup' }) + '</div><h3>' + provider.name + '</h3><p>' + provider.detail + '</p><dl class="uc-health"><div><dt>Account permissions</dt><dd>Not reported</dd></div><div><dt>Last successful account check</dt><dd>Not reported</dd></div><div><dt>Native launch adapter</dt><dd>Not exposed by this status endpoint</dd></div></dl><div class="uc-actions">' + link('Open provider website', provider.portal) + button('Usage & alerts', 'platform', ' data-uc-target="usage"', method(window.U1Platform, 'open')) + '</div></article>';
    }).join('');
  }
  function capabilityTable(state) {
    var rows = P.capabilities(state.cards, state.google, state.providers);
    return '<details class="uc-capabilities"><summary>Read-only capability catalogue</summary><p>Available interfaces from the loaded adapters. This catalogue does not run actions or verify provider access.</p><div class="uc-table-scroll" tabindex="0" role="region" aria-label="Connection capabilities"><table><caption>Connection interfaces and current evidence</caption><thead><tr><th scope="col">Provider</th><th scope="col">Interface</th><th scope="col">Reported state</th><th scope="col">Account actions available here</th><th scope="col">Storage</th></tr></thead><tbody>' + rows.map(function (row) { return '<tr><th scope="row">' + esc(row.name) + '</th><td>' + esc(row.interface) + '</td><td>' + esc(row.status) + '</td><td>' + esc(row.actions.length ? row.actions.join(', ') : 'None') + '</td><td>' + esc(row.storage) + '</td></tr>'; }).join('') + '</tbody></table></div><p>' + (state.catalogueOK ? state.cards.length + ' providers returned by the local catalogue.' : 'Provider catalogue unavailable; only available local detection interfaces are listed.') + '</p></details>';
  }
  function header(title, detail) {
    return '<header class="uc-header"><div><span class="uc-eyebrow">U1 OS / YOUR WORKSPACE</span><h2>' + title + '</h2><p>' + detail + '</p></div><div class="uc-header-tools"><span class="uc-sharing-state" data-uc-sharing-state>' + (sharing ? 'Screen-sharing masks on' : 'Private details visible') + '</span>' + button('Refresh status', 'refresh') + '</div></header><p data-uc-status class="uc-status" role="status" aria-live="polite" aria-atomic="true"></p>';
  }
  function settingsCards() {
    var launch = method(window.U1Launch, 'preferences') ? window.U1Launch.preferences() : null;
    var sound = method(window.U1Feedback, 'preferences') ? window.U1Feedback.preferences() : null;
    return '<div class="uc-grid uc-settings-grid"><article class="uc-card"><span class="uc-category">PRIVACY</span><h3>Share your screen with care.</h3><label class="uc-switch"><input type="checkbox" role="switch" data-uc-privacy' + (sharing ? ' checked' : '') + '><span>Screen-sharing privacy</span></label><p>Masks account details, API inputs, native record cards, and Google/recovery details in this U1 window. Other apps, unmarked views and downloaded files are not covered.</p><p class="uc-note">This is a visual privacy preference, not encryption or an access lock. Turn it off to edit masked fields.</p></article>' +
      '<article class="uc-card"><span class="uc-category">APPEARANCE & STARTUP</span><h3>Your existing visual settings.</h3><p>' + (launch ? 'Rendering: ' + esc(launch.quality) + '. Motion preference: ' + esc(launch.motion) + '. Startup animation: ' + (launch.skipBoot ? 'skipped' : 'enabled') + '.' : 'The launch preferences module is unavailable.') + '</p><p>System reduced-motion settings continue to take precedence. Appearance controls use the existing engine.</p><div class="uc-actions">' + button('Open controls', 'platform', ' data-uc-target="controls"', method(window.U1Platform, 'open')) + button('Preview startup', 'boot', '', method(window.U1Launch, 'preview')) + '</div></article>' +
      '<article class="uc-card"><span class="uc-category">SOUND</span><h3>Small signals, your choice.</h3>' + (sound ? '<form data-uc-sound><label class="uc-switch"><input type="checkbox" name="enabled"' + (sound.enabled ? ' checked' : '') + '><span>Connection feedback sounds</span></label><label>Feedback volume <output data-uc-volume>' + Math.round(sound.volume * 100) + '%</output><input type="range" name="volume" min="0" max="0.5" step="0.01" value="' + Number(sound.volume) + '"></label><p>The preview uses your saved feedback volume and plays only after you select it. Startup audio is managed in controls.</p><div class="uc-actions"><button type="submit">Save sound preferences</button>' + button('Preview saved sound', 'sound', '', method(window.U1Feedback, 'play')) + '</div></form>' : '<p>Load U1ReadyCore and U1Feedback to enable sound preferences.</p>') + '</article>' +
      '<article class="uc-card"><span class="uc-category">SECURITY</span><h3>Your security workspace.</h3><p>Review permissions, encrypted backup/export and restore drills in the native Security workspace. Its managed-job controls report the current pause and stop state.</p><div class="uc-actions">' + routeButton('Open Security', 'security') + (method(window.U1CoreViews, 'supports') && window.U1CoreViews.supports('jobs') ? routeButton('Open Jobs', 'jobs') : '') + button('Safety Centre', 'safety', '', method(window.U1Safety, 'open')) + '</div><p class="uc-note">Passphrase, check-in and offline-lock controls remain in the Safety Centre.</p></article>' +
      '<article class="uc-card"><span class="uc-category">ATTENTION & ALLOWANCES</span><h3>Keep each provider in view.</h3><p>Use the existing allowance display and 10% threshold alerts where verified usage is available. Quiet hours and notification preferences live in the platform controls.</p><div class="uc-actions">' + button('Usage & 10% alerts', 'platform', ' data-uc-target="usage"', method(window.U1Platform, 'open')) + button('Notifications', 'platform', ' data-uc-target="notifications"', method(window.U1Platform, 'open')) + button('Quiet hours', 'platform', ' data-uc-target="controls"', method(window.U1Platform, 'open')) + '</div></article>' +
      '<article class="uc-card"><span class="uc-category">UPDATES & MANAGED RECOVERY</span><h3>A route back to your data.</h3><p>Open the native Updater for release preparation and recovery. The managed backup library and isolated restore tools also remain directly accessible.</p><div class="uc-actions">' + routeButton('Updates & recovery', 'updater') + button('Managed recovery tools', 'hub', ' data-uc-target="recovery"', method(window.U1Reliability, 'open')) + '</div><p class="uc-note">Review coverage and exclusions before acting. Managed recovery archives are owner-only local files; use Security for the separate encrypted-backup workflow.</p></article></div>';
  }
  function render(state) {
    if (!current(state)) return;
    var content = state.view === 'settings' ? settingsCards() : '<section aria-label="Google read-only connection"><div class="uc-section-heading"><h3>Google, with explicit permission</h3><p>One Keychain-backed connection for Gmail and Calendar.</p></div><div class="uc-grid uc-google-grid" data-uc-google-area>' + googleCards(state) + '</div></section><section aria-label="Provider API settings"><div class="uc-section-heading"><h3>Provider API settings</h3><p>Saving configuration does not connect or sync an account.</p></div>' + (state.catalogueOK ? '<div class="uc-grid">' + state.cards.filter(function (card) { return !P.googleId(card.id); }).map(providerCard).join('') + '</div>' : '<p class="uc-empty">' + (state.loading ? 'Reading the local provider catalogue...' : 'The local provider catalogue is unavailable. Refresh to retry.') + '</p>') + '</section><section aria-label="AI applications"><div class="uc-section-heading"><h3>Your AI applications</h3><p>Provider sign-in, permissions and usage remain separate. OpenAI and Anthropic API settings do not authorise Codex or Claude.</p></div><div class="uc-grid uc-agent-grid">' + agentCards(state) + '</div></section>';
    state.host.innerHTML = header(state.view === 'settings' ? 'Settings' : 'Connections', state.view === 'settings' ? 'Privacy, attention and recovery. All in your workspace.' : 'Clear permissions. Honest status. You choose each action.') + content + '<div data-uc-capability-area>' + capabilityTable(state) + '</div><footer class="uc-footer">Provider names identify compatibility and setup destinations; they do not imply endorsement. ' + (state.loadedAt ? 'Local metadata read ' + esc(new Date(state.loadedAt).toLocaleTimeString()) + '. Refresh to check for changes.' : '') + '</footer>';
    busyUI(state);
  }
  function updateGoogle(state) {
    if (!current(state)) return;
    var area = state.host.querySelector('[data-uc-google-area]'); if (area) area.innerHTML = googleCards(state);
    var table = state.host.querySelector('[data-uc-capability-area]'); if (table) table.innerHTML = capabilityTable(state);
    busyUI(state);
  }
  async function refreshGoogle(state) {
    try { state.google = await request('/api/workspace/google'); }
    catch (_) { state.google = null; }
    if (!current(state)) return false;
    if (state.google && (state.google.configured !== true || ['authorised', 'expired', 'needs_attention'].includes(state.google.oauth_status))) state.authURL = null;
    updateGoogle(state); schedule(state); return !!state.google;
  }
  function stopPolling() { clearTimeout(poll); poll = null; }
  function schedule(state) {
    stopPolling();
    if (!current(state) || document.hidden || Date.now() >= state.pollUntil || !P.googleState(state.google).pending) return;
    poll = setTimeout(function () { if (current(state) && !document.hidden && !busy) refreshGoogle(state); else if (current(state) && busy) schedule(state); }, 4000);
  }
  async function load(state) {
    var serial = ++state.loadSerial;
    var results = await Promise.allSettled(readPaths.map(function (path) { return request(path); }));
    if (!current(state) || serial !== state.loadSerial) return;
    var errors = [];
    try { if (results[0].status !== 'fulfilled') throw results[0].reason; state.cards = P.catalogue(results[0].value); state.catalogueOK = true; }
    catch (_) { state.cards = []; state.catalogueOK = false; errors.push('Provider catalogue unavailable.'); }
    state.google = results[1].status === 'fulfilled' ? results[1].value : null;
    state.providers = results[2].status === 'fulfilled' ? results[2].value : null;
    if (!state.google) errors.push('Google status unavailable.');
    if (!state.providers) errors.push('Local AI detection unavailable.');
    state.loading = false; state.loadedAt = Date.now();
    if (state.view === 'settings' && state.dirty) updateGoogle(state); else render(state);
    status(state, errors.length ? errors.join(' ') + ' Available controls remain usable; refresh to retry.' : 'Local metadata loaded. Account actions run only when you select them.', errors.length > 0);
    state.pollUntil = Date.now() + 120000; schedule(state);
  }
  async function reloadCard(state, key) {
    try {
      var cards = P.catalogue(await request('/api/integrations')), updated = cards.find(function (card) { return card.id === key; });
      if (!current(state) || !updated) return false;
      state.cards = state.cards.map(function (card) { return card.id === key ? updated : card; });
      var cardNode = state.host.querySelector('[data-uc-card="' + key + '"]'); if (cardNode) cardNode.outerHTML = providerCard(updated);
      var table = state.host.querySelector('[data-uc-capability-area]'); if (table) table.innerHTML = capabilityTable(state);
      busyUI(state); return true;
    } catch (_) { return false; }
  }
  async function googleAction(state, action) {
    if (!P.googleState(state.google).actions.includes(action)) throw new Error('This Google action is unavailable. Refresh status and review Google setup.');
    if (action === 'disconnect' && !window.confirm('Disconnect the shared Gmail and Calendar connection and remove its Keychain credentials? Imported local data remains. Provider revocation may need review in Google Account permissions.')) return 'No disconnect requested.';
    var result = await mutate(state, '/api/workspace/google', { action: action === 'reconnect' ? 'connect' : action });
    var message;
    if (action === 'connect' || action === 'reconnect') {
      var url = P.authorizationURL(result.authorization_url || result.auth_url || result.url);
      if (!url) throw new Error('The connector did not return an approved Google sign-in URL. Open Google setup to review status.');
      state.authURL = url; state.authExpires = Math.min(typeof result.expires === 'number' ? result.expires * 1000 : Date.now() + 600000, Date.now() + 600000);
      state.pollUntil = state.authExpires; message = 'Sign-in link ready. Continue to Google, review consent, then request Sync. Account access is not yet verified.';
    } else if (action === 'sync') {
      state.pollUntil = Date.now() + 120000; message = 'Sync requested. A queued or running job is not a completed sync. Refresh status if the job takes longer than two minutes.';
    } else {
      state.authURL = null; state.pollUntil = 0;
      message = result.message === 'Local connection removed. Google grant revocation confirmed. Existing imported data was retained.' ? 'Local connection removed. Google grant revocation confirmed. Imported local data remains.' : 'Local disconnect accepted. Provider revocation is not confirmed; review Google Account permissions. Imported local data remains.';
    }
    var available = await refreshGoogle(state);
    return message + (available ? '' : ' Current Google status is unavailable; refresh to confirm the result.');
  }
  async function handleClick(event, host) {
    var node = event.target.closest('button[data-uc-action]'), state = active;
    if (!node || !state || state.host !== host || !host.contains(node) || node.disabled) return;
    var action = node.dataset.ucAction;
    try {
      if (action === 'refresh') {
        if (busy) return;
        if (state.dirty && !window.confirm('Discard unsaved settings in this view and refresh status?')) return;
        state.dirty = false; state.loading = true; status(state, 'Refreshing local metadata...'); await load(state); return;
      }
      if (action === 'google') { await perform(state, function () { return googleAction(state, node.dataset.ucGoogle); }); return; }
      if (action === 'clear') {
        var card = state.cards.find(function (c) { return c.id === node.dataset.ucProvider && !P.googleId(c.id); });
        if (!card || !window.confirm('Clear the saved ' + card.name + ' API settings from local configuration? This does not revoke credentials at the provider or disconnect an account.')) return;
        await perform(state, async function () {
          await mutate(state, '/api/integrations', P.settingsPayload(card, {}, true));
          var refreshed = await reloadCard(state, card.id);
          return 'Local API settings cleared. Provider credentials were not revoked.' + (refreshed ? '' : ' Refresh to update the displayed fields.');
        }); return;
      }
      if (action === 'platform' && ['controls', 'usage', 'notifications'].includes(node.dataset.ucTarget) && method(window.U1Platform, 'open')) { await window.U1Platform.open(node.dataset.ucTarget); return; }
      if (action === 'hub' && ['google', 'recovery'].includes(node.dataset.ucTarget) && method(window.U1Reliability, 'open')) { window.U1Reliability.open(node.dataset.ucTarget, node); return; }
      if (action === 'safety' && method(window.U1Safety, 'open')) { window.U1Safety.open(); return; }
      if (action === 'boot' && method(window.U1Launch, 'preview')) { window.U1Launch.preview(); return; }
      if (action === 'sound' && method(window.U1Feedback, 'play')) { var played = await window.U1Feedback.play('success', true); status(state, played ? 'Saved sound preview played.' : 'Sound preview was not played. Check saved volume, browser audio support and window visibility.'); return; }
      status(state, 'This control requires its existing U1 module to be loaded.', true);
    } catch (_) { status(state, 'The selected control could not open. Check the existing module and try again.', true); }
  }
  async function handleSubmit(event, host) {
    var form = event.target.closest('form'), state = active;
    if (!form || !state || state.host !== host || !host.contains(form)) return;
    if (!form.hasAttribute('data-uc-settings') && !form.hasAttribute('data-uc-sound')) return;
    event.preventDefault();
    if (form.hasAttribute('data-uc-sound')) {
      try {
        if (!method(window.U1Feedback, 'save')) throw new Error('Sound preferences are unavailable.');
        window.U1Feedback.save({ enabled: form.elements.enabled.checked, volume: Number(form.elements.volume.value) });
        state.dirty = false;
        status(state, 'Feedback sound preferences saved on this device.');
      } catch (_) { status(state, 'Sound preferences could not be saved. They may apply only for this session.', true); }
      return;
    }
    if (sharing) { status(state, 'Turn off screen-sharing privacy before editing API settings.', true); return; }
    var card = state.cards.find(function (c) { return c.id === form.dataset.ucSettings; });
    await perform(state, async function () {
      var values = {};
      form.querySelectorAll('[data-uc-field]').forEach(function (input) { values[input.name] = input.value; });
      var payload = P.settingsPayload(card, values, false);
      await mutate(state, '/api/integrations', payload);
      form.querySelectorAll('input[type="password"]').forEach(function (input) { input.value = ''; });
      var refreshed = await reloadCard(state, card.id);
      return 'Settings saved; account access not verified.' + (refreshed ? '' : ' Refresh to update the displayed fields.');
    });
  }
  function mount(view, host) {
    stopPolling();
    var state = { host: host, view: view, sequence: ++sequence, loadSerial: 0, cards: [], google: null, providers: null, catalogueOK: false, loading: true, dirty: false, authURL: null, authExpires: 0, pollUntil: 0 };
    active = state; host.dataset.ucView = view; host.classList.add('u1-native-workspace', 'u1-connections-workspace');
    if (!bound.has(host)) {
      bound.add(host);
      host.addEventListener('click', function (event) { return handleClick(event, host); });
      host.addEventListener('submit', function (event) { return handleSubmit(event, host); });
      host.addEventListener('input', function (event) {
        if (!active || active.host !== host) return;
        if (event.target.closest('[data-uc-settings], [data-uc-sound]')) active.dirty = true;
        if (event.target.name === 'volume') { var output = host.querySelector('[data-uc-volume]'); if (output) output.textContent = Math.round(Number(event.target.value) * 100) + '%'; }
      });
      host.addEventListener('change', function (event) {
        if (!active || active.host !== host || !event.target.hasAttribute('data-uc-privacy')) return;
        var persisted = setPrivacy(event.target.checked);
        status(active, (sharing ? 'Screen-sharing masks enabled.' : 'Private details are visible again.') + (persisted ? ' Preference saved on this device.' : ' Applied for this session; local storage is unavailable.'));
      });
    }
    render(state); return load(state);
  }
  document.addEventListener('visibilitychange', function () { if (document.hidden) stopPolling(); else if (active) schedule(active); });
  window.addEventListener('pagehide', stopPolling);
  window.addEventListener('u1:navigate', function (event) { if (active && event.detail && event.detail.id !== active.view) { stopPolling(); active = null; } });
  window.addEventListener('storage', function (event) { if (event.key === privacyKey || event.key === null) { sharing = event.key !== null && event.newValue === 'true'; applyPrivacy(); document.querySelectorAll('[data-uc-privacy]').forEach(function (input) { input.checked = sharing; }); } });
  window.U1CoreViews.register('integrations', function (host) { return mount('integrations', host); });
  window.U1CoreViews.register('settings', function (host) { return mount('settings', host); });
  window.U1Connections = Object.freeze({ ready: true, privacy: function () { return sharing; }, setPrivacy: setPrivacy, capabilities: function () { return active ? P.capabilities(active.cards, active.google, active.providers) : Object.freeze([]); } });
})();
