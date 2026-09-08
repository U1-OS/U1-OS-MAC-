(function () {
  'use strict';
  var dialog, current = 'google', opener, poll, loadId = 0, busy = false;
  function esc(value) { return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function date(value) { if (!value) return 'Not yet'; var d = new Date(typeof value === 'number' ? value * 1000 : value); return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString(); }
  function ensure() {
    if (dialog) return;
    dialog = document.createElement('dialog'); dialog.className = 'u1-hub-dialog'; dialog.id = 'u1-reliability-dialog'; dialog.setAttribute('aria-labelledby', 'u1-hub-title');
    dialog.innerHTML = '<header><div><span class="u1-core-eyebrow">U1 OS / TRUSTED WORKSPACE</span><h2 id="u1-hub-title">Connections &amp; recovery</h2></div><button data-hub-close>Close</button></header><nav class="u1-hub-tabs" aria-label="Connection and recovery tools"><button data-hub-tab="google">Google Connect</button><button data-hub-tab="recovery">Workspace recovery</button></nav><div data-hub-body></div><p data-hub-status class="u1-core-status" role="status" aria-live="polite"></p>';
    document.body.appendChild(dialog);
    dialog.addEventListener('click', handle);
    dialog.addEventListener('close', function () { clearTimeout(poll); loadId++; if (opener && opener.isConnected && opener.id !== 'omni') opener.focus({ preventScroll: true }); });
  }
  function status(value) { dialog.querySelector('[data-hub-status]').textContent = value; }
  function google(s) {
    var verified = !!s.session_verified, state = verified ? 'LAST SYNC VERIFIED' : s.configured ? 'AUTHORISATION / SYNC REQUIRED' : 'NOT CONNECTED';
    var events = s.events || [], bindings = s.bindings || {}, messages = s.messages || [];
    return '<div class="u1-hub-grid"><section class="u1-hub-panel"><span class="u1-hub-status" data-ready="' + verified + '">' + state + '</span><h3>Your Google account, with boundaries.</h3><p>Read Gmail and your primary calendar. Important email enters a review queue; calendar changes require your approval. U1 OS never sends email or edits Google Calendar through this connector.</p><p><strong>Account:</strong> ' + esc(s.account || 'Not verified') + '<br><strong>Last successful sync:</strong> ' + esc(date(s.last_sync)) + '<br><strong>Snapshot:</strong> ' + (s.stale ? 'Stale or not yet available' : 'Recent') + '<br><strong>OAuth:</strong> ' + esc(s.oauth_status || 'idle') + '</p><div class="u1-core-toolbar"><button data-google-connect' + (!s.configured ? ' disabled' : '') + '>Sign in with Google</button><button data-google-sync' + (!s.configured ? ' disabled' : '') + '>Sync now</button><button data-google-disconnect' + (!s.configured ? ' disabled' : '') + '>Disconnect</button></div><div data-google-auth-link></div><p>Job: ' + esc(s.job ? s.job.status || s.job.state || 'Requested' : 'No sync running') + '</p></section><section class="u1-hub-panel"><h3>Private connection setup</h3><p>Enable the Gmail and Google Calendar APIs in your Google Cloud project, configure consent, then choose a <strong>Desktop app</strong> OAuth client JSON. Client credentials and tokens go into this Mac\'s Keychain, not browser storage.</p><p>Keychain helper: <strong>' + (s.keychain_helper ? 'Installed' : 'Not installed') + '</strong></p><label>Desktop OAuth client JSON<input type="file" accept="application/json,.json" data-google-client' + (!s.keychain_helper ? ' disabled' : '') + '></label><button data-google-configure' + (!s.keychain_helper ? ' disabled' : '') + '>Save client to Keychain</button><label class="u1-core-check"><input type="checkbox" data-google-auto' + (s.auto_sync ? ' checked' : '') + '>Sync every five minutes while the local server is running</label><label class="u1-core-check"><input type="checkbox" data-google-pdfs' + (s.include_pdfs ? ' checked' : '') + '>Import PDF attachments and extract bounded text locally</label><button data-google-settings>Save sync preferences</button></section><section class="u1-hub-panel"><h3>Email briefing sources <span class="u1-core-count">' + messages.length + '</span></h3><p>Latest 20 messages from the past 14 days, excluding Spam and Trash. Important-message detection is a heuristic, not a guarantee.</p><button data-hub-drafts>Open review queue</button><div class="u1-hub-list">' + (messages.length ? messages.map(function (m) { return '<article><strong>' + esc(m.subject || m.title || 'Untitled message') + '</strong><p>' + esc(m.from || '') + '<br>' + esc(m.snippet || m.text || '').slice(0, 500) + '</p></article>'; }).join('') : '<p>No email has been retrieved. Authorise the account and run a successful sync first.</p>') + '</div></section><section class="u1-hub-panel"><h3>Calendar review <span class="u1-core-count">' + events.length + '</span></h3><p>Up to 100 primary-calendar events from seven days ago to 90 days ahead. Missing events are never treated as cancellations.</p><div class="u1-hub-list">' + (events.length ? events.map(function (e) {
      var binding = bindings[e.id], same = binding && binding.version === e.version;
      return '<article><strong>' + esc(e.title || 'Untitled event') + '</strong><p>' + esc(date(e.start)) + '<br>' + esc(e.status === 'cancelled' ? 'Provider reports cancellation' : e.location || 'No location') + '</p>' + (same ? '<span class="u1-core-meta">Reviewed version saved locally</span>' : '<button data-google-event="' + esc(e.id) + '" data-google-version="' + esc(e.version) + '" data-google-cancelled="' + (e.status === 'cancelled') + '">' + (e.status === 'cancelled' ? 'Review cancellation' : binding ? 'Review update' : 'Add to local calendar') + '</button>') + '</article>';
    }).join('') : '<p>No calendar proposals yet. Local appointments remain available in Calendar.</p>') + '</div></section></div><p class="u1-hub-footer">' + esc(s.notice || '') + ' PDF import is limited to three attachments per sync, 5 MB each, with text from the first ten pages. Scanned documents need OCR, which is not included. Messages and document text are untrusted source material, never executable instructions.</p>' + ((s.warnings || []).length ? '<p class="u1-core-status">' + (s.warnings || []).map(esc).join(' / ') + '</p>' : '');
  }
  function recovery(s) {
    var backups = s.backups || [], jobs = s.jobs || [];
    return '<div class="u1-hub-grid"><section class="u1-hub-panel"><span class="u1-hub-status" data-ready="true">LOCAL / ISOLATED RESTORE</span><h3>A real copy of your working data.</h3><p>Archive the managed SQLite database and imported file contents, including Trash. Every archived file has a SHA-256 integrity record. Restores are extracted to a separate directory, never over the running workspace.</p><p><strong>Included:</strong> ' + esc(s.coverage || '') + '</p><p><strong>Excluded:</strong> Keychain tokens, configuration secrets, source code, third-party plugin databases and other folders on your Mac.</p><button class="u1-core-primary" data-recovery-backup>Create managed backup</button><p>Archives are owner-only local files, not encrypted cloud backups. Protect this Mac and any copies you export.</p></section><section class="u1-hub-panel"><h3>Recovery activity</h3><div class="u1-hub-list">' + (jobs.length ? jobs.map(function (j) { return '<article><strong>' + esc(j.action || j.kind || 'Recovery job') + ' / ' + esc(j.status || j.state || '') + '</strong><p>' + esc(j.error || j.message || '') + '</p>' + (j.result && j.result.path ? '<p>Isolated restore: ' + esc(j.result.path) + '</p>' : '') + '</article>'; }).join('') : '<p>No backup or recovery jobs have been requested.</p>') + '</div></section><section class="u1-hub-panel u1-hub-wide"><h3>Managed backup library <span class="u1-core-count">' + backups.length + '</span></h3><div class="u1-hub-list">' + (backups.length ? backups.map(function (b) { return '<article><strong>' + esc(b.name || b.id || 'Workspace archive') + '</strong><p>' + esc(date(b.created || b.modified)) + ' / ' + esc(((b.size || 0) / 1048576).toFixed(2)) + ' MB</p><button data-recovery-restore="' + esc(b.id) + '">Restore to a separate folder</button></article>'; }).join('') : '<p>No managed backups yet. Creating one does not alter your active records or imported files.</p>') + '</div></section></div><p class="u1-hub-footer">' + esc(s.notice || '') + ' Recovery does not switch the active database, install software or roll back a release. Active uploads must finish before a snapshot can be taken.</p>';
  }
  async function load(quiet) {
    var token = ++loadId;
    clearTimeout(poll);
    dialog.querySelectorAll('[data-hub-tab]').forEach(function (b) { b.setAttribute('aria-pressed', String(b.dataset.hubTab === current)); });
    if (!quiet) { dialog.querySelector('[data-hub-body]').innerHTML = '<p class="u1-core-loading">Reading local status...</p>'; status(''); }
    try {
      var data = await window.U1Data.get('/api/workspace/' + current, { fresh: true });
      if (token !== loadId || !dialog.open) return;
      var focused = dialog.contains(document.activeElement) && /INPUT|SELECT|TEXTAREA/.test(document.activeElement.tagName);
      if (!quiet || !focused && !busy) dialog.querySelector('[data-hub-body]').innerHTML = current === 'google' ? google(data) : recovery(data);
      var jobs = current === 'recovery' ? data.jobs || [] : data.job ? [data.job] : [];
      if (jobs.some(function (j) { return /running|queued|pending/.test(j.status || j.state || ''); }) || /authorising|exchanging/.test(data.oauth_status || '')) poll = setTimeout(function () { if (dialog.open && !document.hidden) load(true); }, 4000);
    } catch (error) { if (token === loadId) status(error.message); }
  }
  async function action(path, payload) { var result = await window.U1Data.post('/api/workspace/' + path, payload); return result; }
  async function handle(event) {
    var b = event.target.closest('button'); if (!b || busy) return;
    if (b.hasAttribute('data-hub-close')) { dialog.close(); return; }
    if (b.dataset.hubTab) { current = b.dataset.hubTab; await load(); return; }
    if (b.hasAttribute('data-hub-drafts')) { dialog.close(); if (window.U1Platform) window.U1Platform.open('drafts'); return; }
    busy = true; b.disabled = true; status('Working...');
    try {
      var result;
      if (b.hasAttribute('data-google-configure')) {
        var file = dialog.querySelector('[data-google-client]').files[0];
        if (!file || file.size > 32000) throw new Error('Choose a Desktop OAuth client JSON file smaller than 32 KB.');
        var client; try { client = JSON.parse(await file.text()); } catch (_) { throw new Error('That file is not valid JSON.'); }
        result = await action('google', { action: 'configure', client: client });
      } else if (b.hasAttribute('data-google-connect')) {
        result = await action('google', { action: 'connect' });
        var auth = result.authorization_url || result.auth_url || result.url;
        var url = new URL(auth);
        if (url.protocol !== 'https:' || url.hostname !== 'accounts.google.com') throw new Error('The connector did not return an approved Google sign-in URL.');
        var target = dialog.querySelector('[data-google-auth-link]'); target.innerHTML = '<p><a target="_blank" rel="noopener noreferrer" href="' + esc(url.href) + '">Continue to Google in your browser</a></p><p>Keep U1 OS running. Return here after approval and select Sync now.</p>';
        status('Sign-in link is ready. Account access is not yet confirmed.'); return;
      } else if (b.hasAttribute('data-google-sync')) result = await action('google', { action: 'sync' });
      else if (b.hasAttribute('data-google-settings')) result = await action('google', { action: 'settings', auto_sync: dialog.querySelector('[data-google-auto]').checked, include_pdfs: dialog.querySelector('[data-google-pdfs]').checked });
      else if (b.hasAttribute('data-google-disconnect')) {
        if (!window.confirm('Disconnect Google and remove its credentials from Keychain? Previously imported local records and files will remain.')) { status('No changes made.'); return; }
        result = await action('google', { action: 'disconnect' });
      } else if (b.dataset.googleEvent) {
        var cancelled = b.dataset.googleCancelled === 'true';
        if (!window.confirm(cancelled ? 'Confirm this Google cancellation locally? The linked local event will move to Trash. Google Calendar will not be changed.' : 'Save this reviewed event version to your local calendar? Google Calendar will not be changed.')) { status('No changes made.'); return; }
        result = await action('google', { action: 'approve_event', id: b.dataset.googleEvent, version: b.dataset.googleVersion, confirmed: true });
      } else if (b.hasAttribute('data-recovery-backup')) {
        if (!window.confirm('Create an unencrypted owner-only backup of the managed database and imported files on this Mac? Credentials and other application stores are excluded.')) { status('No backup requested.'); return; }
        result = await action('recovery', { action: 'backup', confirmed: true });
      } else if (b.dataset.recoveryRestore) {
        if (!window.confirm('Validate and restore this backup to a NEW isolated folder? The active workspace will not be overwritten.')) { status('No restore requested.'); return; }
        result = await action('recovery', { action: 'restore', id: b.dataset.recoveryRestore, confirmed: true });
      }
      busy = false; await load(); status(result && (result.message || result.notice) || 'Request accepted. Status above shows the local result.');
    } catch (error) { status(error.message); } finally { busy = false; if (b.isConnected) b.disabled = false; }
  }
  function open(name, button) { ensure(); current = name === 'recovery' ? 'recovery' : 'google'; opener = button || document.activeElement; if (!dialog.open) dialog.showModal(); load(); }
  function init() {
    document.addEventListener('click', function (event) { var button = event.target.closest('[data-u1-hub]'); if (button) { event.preventDefault(); open(button.dataset.u1Hub, button); } });
    var rail = document.getElementById('rail');
    if (rail) {
      var group = document.createElement('details'); group.className = 'u1-core-tools'; group.innerHTML = '<summary>Connections &amp; recovery</summary><button class="u1-hub-entry" data-u1-hub="google">Google Connect</button><button class="u1-hub-entry" data-u1-hub="recovery">Workspace recovery</button>'; rail.appendChild(group);
    }
    document.addEventListener('visibilitychange', function () { if (document.hidden) clearTimeout(poll); else if (dialog && dialog.open && !busy) load(true); });
  }
  window.U1Reliability = Object.freeze({ open: open });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
