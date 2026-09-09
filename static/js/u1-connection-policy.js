/* Pure policy for the native Connections workspace. No I/O or credentials. */
(function (root, factory) {
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else root.U1ConnectionPolicy = api;
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  function object(value) { return !!value && typeof value === 'object' && !Array.isArray(value); }
  function text(value, limit) { return typeof value === 'string' ? value.slice(0, limit || 400) : ''; }
  function id(value) { return typeof value === 'string' && /^[a-z][a-z0-9_]{0,63}$/.test(value) && !['constructor', 'prototype', '__proto__'].includes(value); }
  function googleId(value) { return value === 'gmail' || value === 'google_calendar'; }
  function secret(field) { return field.secret === true || /secret|token|password|api_key|publisher_key|bearer/i.test(field.id); }
  function escape(value) { return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function portal(value) {
    if (typeof value !== 'string' || /[\u0000-\u0020\\]/.test(value)) return null;
    try {
      var url = new URL(value);
      if (url.protocol !== 'https:' || url.username || url.password) return null;
      if (Array.from(url.searchParams.keys()).some(function (key) { return /token|secret|password|api.?key|authorization|code/i.test(key); })) return null;
      return url.href;
    } catch (_) { return null; }
  }
  function authorizationURL(value) {
    try {
      if (typeof value !== 'string' || /[\u0000-\u0020\\]/.test(value)) return null;
      var url = new URL(value);
      return url.protocol === 'https:' && url.hostname === 'accounts.google.com' && !url.port && !url.username && !url.password && !url.hash && url.pathname === '/o/oauth2/v2/auth' ? url.href : null;
    } catch (_) { return null; }
  }
  function timestamp(value, now) {
    now = now == null ? Date.now() : now;
    var result = typeof value === 'number' ? value * 1000 : typeof value === 'string' && /^\d{4}-\d\d-\d\dT/.test(value) ? Date.parse(value) : NaN;
    return Number.isFinite(result) && result > 0 && result <= now ? result : null;
  }
  function permissions(value) {
    if (typeof value === 'string') return value.trim() ? [text(value, 1200)] : [];
    return Array.isArray(value) ? value.filter(function (v) { return typeof v === 'string' && v.trim(); }).slice(0, 30).map(function (v) { return text(v); }) : [];
  }
  function health(value, google, now) {
    value = object(value) ? value : {};
    var account = typeof value.account === 'string' ? value.account : object(value.account) ? value.account.email || value.account.name || value.account.id : '';
    return {
      account: text(account, 300),
      permissions: permissions(value.permissions || value.granted_scopes),
      requestedScopes: google ? permissions(value.scopes) : [],
      lastSuccess: timestamp(value.last_success || value.last_success_at || (google ? value.last_sync : null), now)
    };
  }
  function catalogue(data) {
    if (!object(data) || data.success !== true || !Array.isArray(data.cards)) throw new Error('The integration catalogue did not return usable metadata.');
    var seen = new Set();
    return data.cards.filter(function (card) {
      if (!object(card) || !id(card.id) || seen.has(card.id)) return false;
      seen.add(card.id); return true;
    }).map(function (card) {
      var fields = [], fieldIds = new Set();
      // Discard the legacy Google fields before they can enter UI state.
      if (!googleId(card.id)) (Array.isArray(card.fields) ? card.fields : []).forEach(function (field) {
        if (!object(field) || !id(field.id) || fieldIds.has(field.id)) return;
        fieldIds.add(field.id);
        var sensitive = secret(field);
        fields.push({ id: field.id, label: text(field.label, 120) || field.id, secret: sensitive, saved: field.saved === true, value: sensitive ? '' : text(field.value, 8192) });
      });
      return {
        id: card.id, name: text(card.name, 120) || card.id, category: text(card.category, 100) || 'Other',
        fields: fields, savedFields: Number.isInteger(card.saved_fields) && card.saved_fields > 0 ? card.saved_fields : fields.filter(function (f) { return f.saved; }).length,
        settingsSaved: card.status === 'settings_saved', stage: text(card.stage, 60), note: text(card.note, 1000), portal: portal(card.portal), health: health(card, false)
      };
    });
  }
  function googleState(snapshot, now) {
    now = now == null ? Date.now() : now;
    if (!object(snapshot) || snapshot.success !== true) return { label: 'Status unavailable', tone: 'unknown', actions: [], health: health(null), pending: false, configured: false, helper: false };
    var configured = snapshot.configured === true, helper = snapshot.keychain_helper === true;
    var details = health(snapshot, true, now), lastSync = timestamp(snapshot.last_sync, now);
    var oauth = text(snapshot.oauth_status, 40), job = object(snapshot.job) ? snapshot.job.status || snapshot.job.state : '';
    var syncing = ['running', 'queued', 'pending'].includes(job), authorising = ['authorising', 'exchanging'].includes(oauth);
    var verified = configured && snapshot.session_verified === true && snapshot.stale === false && lastSync !== null && now - lastSync < 660000 && !syncing && !authorising && job !== 'failed';
    var label = !configured ? helper ? 'Not connected' : 'Keychain setup required' : !helper ? 'Keychain helper unavailable' : syncing ? 'Sync in progress' : authorising ? 'Authorisation in progress' : job === 'failed' || oauth === 'needs_attention' || oauth === 'expired' ? 'Connection needs attention' : verified ? 'Last sync verified' : oauth === 'authorised' ? 'Authorised / sync required' : lastSync ? 'Previous sync / verification required' : 'Authorisation / sync required';
    var actions = [];
    if (configured && helper) {
      if (!syncing && !authorising) actions.push(lastSync || snapshot.session_verified === true || oauth === 'authorised' || oauth === 'needs_attention' || oauth === 'expired' ? 'reconnect' : 'connect', 'sync');
      actions.push('disconnect');
    }
    return { label: label, tone: verified ? 'verified' : 'setup', actions: actions, health: details, pending: syncing || authorising, configured: configured, helper: helper, oauth: oauth, job: text(job, 40), stale: snapshot.stale !== false, verified: verified };
  }
  function settingsState(card) {
    var saved = card.settingsSaved || card.savedFields > 0;
    return { label: saved ? 'Settings saved / unverified' : card.stage === 'setup_slot' ? 'Adapter pending / settings only' : card.stage === 'adapter_files' ? 'Adapter files / setup required' : card.fields.length ? 'API settings required' : 'Runtime setup required', tone: 'setup', actions: [] };
  }
  function settingsPayload(card, values, clear) {
    if (!card || !id(card.id) || googleId(card.id)) throw new Error('Google credentials must use the Keychain-backed Google Connect workflow.');
    if (!object(values)) throw new Error('Settings must be a field/value object.');
    if (clear === true) return { integration: card.id, values: {}, clear: true };
    if (!card.fields.length) throw new Error('This adapter does not expose editable API settings.');
    var result = {}, fields = new Map(card.fields.map(function (field) { return [field.id, field]; }));
    Object.keys(values).forEach(function (key) {
      var field = fields.get(key), value = values[key];
      if (!field || !id(key)) throw new Error('An unsupported settings field was supplied.');
      if (typeof value !== 'string' || value.length > 8192) throw new Error('Each setting must be text of at most 8192 characters.');
      value = value.trim();
      if (/\u2022/.test(value)) throw new Error('Enter a real value, not a saved-value mask.');
      if (!field.secret || value) result[key] = value;
    });
    return { integration: card.id, values: result, clear: false };
  }
  function providerState(data, key) {
    var row = object(data) && data.success === true && Array.isArray(data.providers) ? data.providers.find(function (p) { return object(p) && p.id === key; }) : null;
    var name = { codex: 'Codex', claude: 'Claude', antigravity: 'Antigravity' }[key] || key;
    return {
      id: key, name: name, portal: row ? portal(row.url) : null,
      label: !row || typeof row.ready !== 'boolean' ? 'Detection unavailable' : key === 'antigravity' ? row.ready ? 'App data found / authorisation required' : 'App data not detected' : row.ready ? 'CLI detected / authorisation required' : 'CLI not detected',
      detail: key === 'antigravity' ? 'The adapter checks a local app-data directory. Installation, app launch and account access are not verified.' : 'The adapter checks the local CLI path. A detected executable does not verify sign-in or subscription access.',
      actions: []
    };
  }
  function capabilities(cards, google, providers, now) {
    var gs = googleState(google, now);
    var rows = cards.map(function (card) {
      var isGoogle = googleId(card.id);
      return Object.freeze({ id: card.id, name: card.name, interface: isGoogle ? 'Read-only Gmail / primary Calendar; reviewed local imports' : card.fields.length ? 'API settings only' : 'Runtime setup only', status: isGoogle ? gs.label : settingsState(card).label, actions: Object.freeze(isGoogle ? gs.actions.slice() : []), storage: isGoogle ? 'Credentials: Mac Keychain. Imported data: local workspace.' : card.fields.length ? 'Owner-only local configuration; not encrypted.' : 'No account storage in this view.' });
    });
    ['codex', 'claude', 'antigravity'].forEach(function (key) {
      var p = providerState(providers, key);
      rows.push(Object.freeze({ id: key, name: p.name, interface: 'Local detection and provider website', status: p.label, actions: Object.freeze([]), storage: 'No account credentials managed by this view.' }));
    });
    return Object.freeze(rows);
  }
  return Object.freeze({ escape: escape, portal: portal, authorizationURL: authorizationURL, timestamp: timestamp, catalogue: catalogue, health: health, googleId: googleId, googleState: googleState, settingsState: settingsState, settingsPayload: settingsPayload, providerState: providerState, capabilities: capabilities });
});
