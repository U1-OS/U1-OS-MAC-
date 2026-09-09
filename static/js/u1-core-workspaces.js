(function () {
  'use strict';
  var views = { projects: ['project', 'Projects', 'Give your next idea a clear direction.'], tasks: ['task', 'Tasks', 'A clear list. A focused day.'], calendar: ['event', 'Calendar', 'Your schedule, with room for what matters.'], notes: ['note', 'Notes', 'Capture an idea before it disappears.'], files: ['file', 'Files', 'Your private, local working library.'] };
  var hosts = new Map(), extensions = new Map(), snapshot = null, dialog = null, activeRecord = null, sourceButton = null, routeEpoch = 0;
  var lifecycle = new WeakMap(), activeExtension = null;
  function own(object, id) { return Object.prototype.hasOwnProperty.call(object, id); }
  function locked() { return !!((document.documentElement && document.documentElement.dataset.u1Safety === 'locked') || (window.U1Safety && window.U1Safety.isLocked && window.U1Safety.isLocked())); }
  function deactivate(id, host) {
    var item = host && lifecycle.get(host);
    if (!item || item.id !== id || !item.active) return;
    item.active = false; item.epoch++;
    if (activeExtension === item) activeExtension = null;
    if (item.entry.deactivate) {
      try { var stopped = Promise.resolve(item.entry.deactivate(host)).catch(function () {}); item.pending = Promise.allSettled([item.pending, stopped]); }
      catch (_) { /* Deactivation must not prevent navigation or the Safety lock. */ }
    }
  }
  function activate(id, host) {
    if (!host || locked() || !extensions.has(id)) return Promise.resolve();
    var entry = extensions.get(id), item = lifecycle.get(host);
    if (!item || item.id !== id || item.entry !== entry) {
      if (item) deactivate(item.id, host);
      item = { id: id, host: host, entry: entry, active: false, initialized: false, epoch: 0, pending: null };
      lifecycle.set(host, item);
    }
    if (item.active) return item.pending || Promise.resolve();
    if (activeExtension && activeExtension !== item) deactivate(activeExtension.id, activeExtension.host);
    activeExtension = item; item.active = true;
    var serial = ++item.epoch, previous = item.pending;
    function run() {
      if (!item.active || serial !== item.epoch || locked()) return;
      if (!item.initialized) { item.initialized = true; return entry.render(host); }
      if (entry.activate) return entry.activate(host);
    }
    var operation = (previous ? Promise.resolve(previous).then(run) : Promise.resolve().then(run)).catch(function (error) {
      if (item.active && serial === item.epoch && !locked()) {
        item.initialized = false;
        host.innerHTML = '<section class="u1-core-empty"><h2>Workspace unavailable</h2><p>' + esc(error.message || 'The workspace could not open.') + '</p></section>';
      }
    }).finally(function () { if (item.pending === operation) item.pending = null; });
    item.pending = operation; return operation;
  }
  var icons = {
    project: '<path d="M3 7h6l2 2h10v11H3zM3 7V4h7l2 3"/>',
    task: '<rect x="4" y="3" width="16" height="18" rx="3"/><path d="m8 12 3 3 6-7"/>',
    event: '<rect x="3" y="5" width="18" height="16" rx="3"/><path d="M7 3v4m10-4v4M3 11h18m-13 4h2m4 0h2"/>',
    note: '<path d="M14 3H4v18h16V11M10 14l1-5 8-8 4 4-8 8z"/>',
    file: '<path d="M14 2H5v20h14V7zM14 2v6h5M8 13h8m-8 4h6"/>',
    ai: '<path d="M12 3v18M8 5C2 3 2 11 5 12c-4 4 0 10 4 7m7-14c6-2 6 6 3 7 4 4 0 10-4 7M5 12h3m8 0h3"/>',
    automation: '<path d="m13 2-9 12h7l-1 8L21 9h-8z"/>'
  };
  function esc(value) { return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function icon(kind) { return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">' + (icons[kind] || icons.file) + '</svg>'; }
  function allRecords() {
    var raw = snapshot && snapshot.records || [];
    return Array.isArray(raw) ? raw : Object.values(raw).flat().filter(function (r) { return r && r.id; });
  }
  function records(kind) { return allRecords().filter(function (r) { return r.kind === kind && !r.deleted; }); }
  function date(value) { if (!value) return 'Not scheduled'; var d = new Date(typeof value === 'number' ? value * 1000 : value); return Number.isNaN(d.getTime()) ? String(value) : d.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }); }
  function bytes(n) { return n >= 1048576 ? (n / 1048576).toFixed(1) + ' MB' : Math.ceil(n / 1024) + ' KB'; }
  function localDate(value) { if (!value) return ''; var d = new Date(value); if (Number.isNaN(d.getTime())) return ''; return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16); }
  function showError(host, error) { var target = host.querySelector('[data-core-status]'); if (target) { target.textContent = error.message || String(error); target.setAttribute('role', 'alert'); } }
  function card(row, kind) {
    var p = row.payload || {}, subtitle = '', extra = '';
    if (kind === 'project') {
      subtitle = (p.category || 'Personal') + ' / ' + (p.status || 'planned');
      extra = p.progress == null ? '<span class="u1-core-meta">Progress not set</span>' : '<div class="u1-core-progress"><progress max="100" value="' + Number(p.progress) + '" aria-label="' + esc(row.title) + ' progress"></progress><span>' + Number(p.progress) + '%</span></div>';
    }
    if (kind === 'task') { subtitle = (p.done ? 'Completed' : p.priority === 'high' ? 'High priority' : 'To do') + (p.due ? ' / Due ' + p.due : ''); extra = '<button class="u1-core-subtle" data-core-toggle="' + esc(row.id) + '">' + (p.done ? 'Reopen task' : 'Mark complete') + '</button>'; }
    if (kind === 'event') { subtitle = date(p.start); extra = '<span class="u1-core-meta">' + esc(p.location || 'No location set') + '</span>'; }
    if (kind === 'note') { subtitle = p.tag || 'Personal note'; extra = '<p class="u1-core-excerpt">' + esc(p.text || 'No content yet.') + '</p>'; }
    return '<article class="u1-core-card" data-record-id="' + esc(row.id) + '"><div class="u1-core-card-top"><span class="u1-core-icon">' + icon(kind) + '</span><span class="u1-core-meta">LOCAL</span></div><h3>' + esc(row.title) + '</h3><p class="u1-core-subtitle">' + esc(subtitle) + '</p>' + extra + '<div class="u1-core-card-actions"><button data-core-edit="' + esc(row.id) + '">Open ' + esc(kind) + '</button><button class="u1-core-subtle" data-core-trash="' + esc(row.id) + '">Move to Trash</button></div></article>';
  }
  function render(id, host) {
    var config = views[id], kind = config[0], rows = kind === 'file' ? (snapshot.files || []).filter(function (f) { return !f.deleted; }) : records(kind);
    if (kind === 'event') rows.sort(function (a, b) { return String(a.payload.start).localeCompare(String(b.payload.start)); });
    host.classList.add('u1-native-workspace');
    host.innerHTML = '<section class="u1-core-header"><div><span class="u1-core-eyebrow">U1 WORKSPACE / ' + esc(config[1].toUpperCase()) + '</span><h2>' + esc(config[1]) + '<span class="u1-core-count">' + rows.length + '</span></h2><p>' + esc(config[2]) + '</p></div><div class="u1-core-toolbar">' + (kind === 'event' ? '<button data-u1-hub="google">Connect calendar</button>' : '') + '<button data-core-restore>Trash</button><button data-core-new class="u1-core-primary">' + (kind === 'file' ? 'Upload files' : 'New ' + kind) + '</button></div></section><div class="u1-core-source"><span class="u1-core-online-dot"></span>Local workspace database<span>Updated ' + esc(new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })) + '</span><button data-core-refresh>Refresh</button></div><p data-core-status class="u1-core-status" aria-live="polite"></p><div class="u1-core-grid">' + (rows.length ? rows.map(function (row) {
      if (kind !== 'file') return card(row, kind);
      return '<article class="u1-core-card"><div class="u1-core-card-top"><span class="u1-core-icon">' + icon('file') + '</span><span class="u1-core-meta">' + esc(row.status) + '</span></div><h3>' + esc(row.name) + '</h3><p class="u1-core-subtitle">' + esc(bytes(row.size)) + ' / ' + esc(row.folder || 'Files') + '</p><p class="u1-core-meta">' + esc(row.mime || 'Unknown type') + '</p><div class="u1-core-card-actions">' + (row.status === 'ready' ? '<button data-core-download="' + esc(row.id) + '">Download</button>' : '') + '<button class="u1-core-subtle" data-core-trash-file="' + esc(row.id) + '">Move to Trash</button></div></article>';
    }).join('') : '<div class="u1-core-empty"><span class="u1-core-empty-icon">' + icon(kind) + '</span><h3>Your ' + esc(config[1].toLowerCase()) + ' start here.</h3><p>' + (kind === 'file' ? 'Upload documents, images or media. Originals stay on this Mac.' : 'Create your first ' + kind + '. Real records, saved locally. No sample data.') + '</p><button class="u1-core-primary" data-core-new>' + (kind === 'file' ? 'Choose files' : 'Create ' + kind) + '</button></div>') + '</div>';
  }
  async function mount(id, host) {
    if (locked()) return;
    if (extensions.has(id)) return activate(id, host);
    if (!own(views, id)) return;
    hosts.set(id, host);
    var serial = ++routeEpoch;
    if (!snapshot) host.innerHTML = '<div class="u1-core-loading" role="status">Opening your workspace...</div>';
    try { var result = await window.U1Data.get('/api/workspace/prism/summary'); if (serial !== routeEpoch || locked()) return; snapshot = result; render(id, host); }
    catch (error) { if (serial !== routeEpoch || locked()) return; host.innerHTML = '<section class="u1-core-empty"><h2>Workspace unavailable</h2><p>' + esc(error.message) + '</p><button data-core-refresh>Try again</button></section>'; }
    if (!host.dataset.coreBound) { host.dataset.coreBound = 'true'; host.addEventListener('click', function (event) { handle(event, id, host); }); }
  }
  function getDialog() {
    if (dialog) return dialog;
    dialog = document.createElement('dialog'); dialog.className = 'u1-core-dialog'; dialog.id = 'u1-core-editor'; dialog.setAttribute('aria-labelledby', 'u1-core-editor-title'); document.body.appendChild(dialog);
    dialog.addEventListener('click', function (event) { if (event.target.closest('[data-core-close]')) dialog.close(); });
    dialog.addEventListener('close', function () { if (sourceButton && sourceButton.isConnected && sourceButton.id !== 'omni') sourceButton.focus({ preventScroll: true }); });
    return dialog;
  }
  function field(label, name, value, type, required) { return '<label>' + esc(label) + '<input name="' + name + '" type="' + (type || 'text') + '" value="' + esc(value || '') + '"' + (required ? ' required' : '') + (name === 'title' ? ' maxlength="180"' : '') + '></label>'; }
  function select(label, name, value, values) { return '<label>' + esc(label) + '<select name="' + name + '">' + values.map(function (v) { return '<option value="' + v + '"' + (v === value ? ' selected' : '') + '>' + v.charAt(0).toUpperCase() + v.slice(1) + '</option>'; }).join('') + '</select></label>'; }
  function editor(kind, row, button, id, host) {
    if (locked()) return;
    sourceButton = button; activeRecord = row || null; var p = row && row.payload || {}, form = field('Title', 'title', row && row.title, 'text', true);
    if (kind === 'project') form += '<div class="u1-core-form-row">' + field('Category', 'category', p.category || 'Personal') + select('Status', 'status', p.status || 'planned', ['planned', 'active', 'paused', 'done']) + '</div><label>Progress (%)<input type="number" name="progress" min="0" max="100" step="1" value="' + esc(p.progress == null ? '' : p.progress) + '" placeholder="Leave blank if not measured"></label>' + field('Project link (optional)', 'url', p.url, 'url');
    if (kind === 'task') form += '<div class="u1-core-form-row">' + field('Due date (optional)', 'due', p.due, 'date') + select('Priority', 'priority', p.priority || 'normal', ['low', 'normal', 'high']) + '</div><label class="u1-core-check"><input type="checkbox" name="done"' + (p.done ? ' checked' : '') + '>Completed</label>';
    if (kind === 'event') form += '<p class="u1-core-meta">Times use this device\'s timezone: ' + esc(Intl.DateTimeFormat().resolvedOptions().timeZone) + '.</p><div class="u1-core-form-row">' + field('Starts', 'start', localDate(p.start), 'datetime-local', true) + field('Ends (optional)', 'end', localDate(p.end), 'datetime-local') + '</div>' + field('Location', 'location', p.location);
    if (kind === 'note') form += field('Tag', 'tag', p.tag);
    form += '<label>' + (kind === 'note' ? 'Note' : 'Notes') + '<textarea name="notes" rows="6" maxlength="' + (kind === 'note' ? '24000' : kind === 'task' || kind === 'event' ? '8000' : '12000') + '">' + esc(kind === 'note' ? p.text : p.notes) + '</textarea></label>';
    getDialog().innerHTML = '<header><div><span class="u1-core-eyebrow">PRIVATE / LOCAL</span><h2 id="u1-core-editor-title">' + (row ? 'Edit ' : 'New ') + kind + '</h2></div><button type="button" data-core-close aria-label="Close editor">Close</button></header><form class="u1-core-form">' + form + '<p data-core-status class="u1-core-status" role="status"></p><footer><button type="button" data-core-close>Cancel</button><button type="submit" class="u1-core-primary">Save ' + kind + '</button></footer></form>';
    dialog.querySelector('form').addEventListener('submit', async function (event) {
      event.preventDefault(); var formNode = event.currentTarget, submit = formNode.querySelector('[type=submit]'); submit.disabled = true;
      var f = new FormData(formNode), payload = Object.assign({}, p), data = { kind: kind, title: String(f.get('title')).trim(), payload: payload };
      if (kind === 'project') Object.assign(payload, { category: f.get('category'), status: f.get('status'), progress: f.get('progress') === '' ? null : Number(f.get('progress')), url: f.get('url'), notes: f.get('notes') });
      if (kind === 'task') Object.assign(payload, { done: f.has('done'), due: f.get('due'), priority: f.get('priority'), notes: f.get('notes') });
      if (kind === 'note') Object.assign(payload, { tag: f.get('tag'), text: f.get('notes') });
      if (kind === 'event') Object.assign(payload, { start: new Date(f.get('start')).toISOString(), end: f.get('end') ? new Date(f.get('end')).toISOString() : '', location: f.get('location'), notes: f.get('notes') });
      if (row) { data.id = row.id; data.expected_updated = row.updated; }
      try { await window.U1Data.post('/api/workspace/prism/record', data); dialog.close(); await mount(id, host); }
      catch (error) { showError(dialog, error); } finally { submit.disabled = false; }
    });
    dialog.showModal();
  }
  async function trashView(id, host, button) {
    if (locked()) return;
    var serial = routeEpoch;
    sourceButton = button;
    var result = await window.U1Data.get('/api/workspace/prism/trash', { fresh: true });
    if (locked() || serial !== routeEpoch) return;
    var items = (Array.isArray(result.records) ? result.records : Object.values(result.records || {}).flat()).concat((result.files || []).map(function (f) { return Object.assign({}, f, { kind: 'file', title: f.name }); }));
    getDialog().innerHTML = '<header><h2 id="u1-core-editor-title">Trash</h2><button data-core-close>Close</button></header><p class="u1-core-meta">Restoring returns a record to this workspace. Nothing is permanently deleted here.</p><div class="u1-core-trash-list">' + (items.length ? items.map(function (r) { return '<article><div><strong>' + esc(r.title) + '</strong><p>' + esc(r.kind) + '</p></div><button data-restore-id="' + esc(r.id) + '" data-restore-kind="' + esc(r.kind) + '">Restore</button></article>'; }).join('') : '<p>Your Trash is empty.</p>') + '</div><p data-core-status aria-live="polite"></p>';
    dialog.querySelectorAll('[data-restore-id]').forEach(function (b) { b.addEventListener('click', async function () { b.disabled = true; try { await window.U1Data.post('/api/workspace/prism/restore', { id: b.dataset.restoreId, kind: b.dataset.restoreKind }); b.closest('article').remove(); await mount(id, host); } catch (e) { showError(dialog, e); b.disabled = false; } }); });
    dialog.showModal();
  }
  async function upload(id, host) {
    var input = document.createElement('input'); input.type = 'file'; input.multiple = true;
    input.addEventListener('change', async function () {
      var status = host.querySelector('[data-core-status]');
      for (var file of input.files) {
        try {
          if (file.size > 25 * 1024 * 1024) throw new Error(file.name + ' exceeds the 25 MB file limit.');
          status.textContent = 'Uploading ' + file.name + '...';
          var start = await window.U1Data.post('/api/workspace/prism/upload-start', { name: file.name, mime: file.type || 'application/octet-stream', size: file.size, folder: 'Files' });
          var offset = 0;
          do {
            var chunk = new Uint8Array(await file.slice(offset, offset + 32768).arrayBuffer()), binary = '';
            for (var i = 0; i < chunk.length; i++) binary += String.fromCharCode(chunk[i]);
            await window.U1Data.post('/api/workspace/prism/upload-chunk', { id: start.id, offset: offset, content: btoa(binary) });
            offset += chunk.length;
          } while (offset < file.size);
        } catch (error) { showError(host, error); return; }
      }
      await mount(id, host);
    }, { once: true });
    input.click();
  }
  async function handle(event, id, host) {
    if (locked()) return;
    var button = event.target.closest('button'); if (!button) return;
    var kind = views[id][0];
    try {
      if (button.hasAttribute('data-core-refresh')) { window.U1Data.invalidate(); await mount(id, host); }
      if (button.hasAttribute('data-core-new')) { if (kind === 'file') await upload(id, host); else editor(kind, null, button, id, host); }
      if (button.dataset.coreEdit) editor(kind, allRecords().find(function (r) { return r.id === button.dataset.coreEdit; }), button, id, host);
      if (button.dataset.coreToggle) {
        var row = allRecords().find(function (r) { return r.id === button.dataset.coreToggle; });
        await window.U1Data.post('/api/workspace/prism/record', { id: row.id, kind: 'task', title: row.title, expected_updated: row.updated, payload: Object.assign({}, row.payload, { done: !row.payload.done }) }); await mount(id, host);
      }
      if (button.dataset.coreTrash || button.dataset.coreTrashFile) {
        if (!window.confirm('Move this item to Trash? You can restore it later.')) return;
        await window.U1Data.post('/api/workspace/prism/trash', { id: button.dataset.coreTrash || button.dataset.coreTrashFile, kind: button.dataset.coreTrashFile ? 'file' : kind }); await mount(id, host);
      }
      if (button.hasAttribute('data-core-restore')) await trashView(id, host, button);
      if (button.dataset.coreDownload) {
        button.disabled = true;
        var file = await window.U1Data.get('/api/workspace/prism/file?id=' + encodeURIComponent(button.dataset.coreDownload));
        var binary = atob(file.content), content = new Uint8Array(binary.length); for (var j = 0; j < binary.length; j++) content[j] = binary.charCodeAt(j);
        var url = URL.createObjectURL(new Blob([content], { type: 'application/octet-stream' })), link = document.createElement('a'); link.href = url; link.download = file.name; link.click(); setTimeout(function () { URL.revokeObjectURL(url); }, 30000);
      }
    } catch (error) { showError(host, error); } finally { button.disabled = false; }
  }
  function suspendFrames() {
    document.querySelectorAll('iframe.u1-workspace-frame').forEach(function (frame) {
      var view = frame.closest('[id^="v-"]'); if (!view) return;
      var visible = view.id === 'v-' + document.body.dataset.u1View;
      if (!visible && frame.dataset.u1Dirty !== 'true' && frame.getAttribute('src') && frame.getAttribute('src') !== 'about:blank') { frame.dataset.u1SuspendedSrc = frame.getAttribute('src'); frame.src = 'about:blank'; }
      if (visible && frame.dataset.u1SuspendedSrc) { frame.src = frame.dataset.u1SuspendedSrc; delete frame.dataset.u1SuspendedSrc; }
    });
  }
  function init() {
    document.querySelectorAll('.u1-quick-actions [data-go]').forEach(function (b) { var symbol = b.querySelector('.u1-action-symbol'); var kind = { projects: 'project', calendar: 'event', files: 'file', tasks: 'task' }[b.dataset.go] || b.dataset.go; if (symbol && icons[kind]) symbol.innerHTML = icon(kind); });
    var rail = document.getElementById('rail'), toolsGroup;
    function groupTools() {
      if (!rail) return;
      var secondary = Array.from(rail.querySelectorAll(':scope > button[data-platform], :scope > button[data-u1-open-agents]'));
      if (!secondary.length) return;
      if (!toolsGroup) { toolsGroup = document.createElement('details'); toolsGroup.className = 'u1-core-tools'; toolsGroup.innerHTML = '<summary>Workspace tools</summary>'; secondary[0].before(toolsGroup); }
      secondary.forEach(function (b) { toolsGroup.appendChild(b); });
    }
    if (rail) { new MutationObserver(groupTools).observe(rail, { childList: true }); groupTools(); }
    function refreshActive() { var id = document.body.dataset.u1View, host = hosts.get(id); if (host && (!dialog || !dialog.open)) mount(id, host); }
    new MutationObserver(function () { setTimeout(function () { suspendFrames(); refreshActive(); }, 100); }).observe(document.body, { attributes: true, attributeFilter: ['data-u1-view'] });
    document.addEventListener('visibilitychange', function () { document.body.classList.toggle('u1-page-idle', document.hidden); if (!document.hidden) { window.U1Data.invalidate(); refreshActive(); } });
  }
  window.U1CoreViews = Object.freeze({
    supports: function (id) { return typeof id === 'string' && (own(views, id) || extensions.has(id)); },
    register: function (id, render, hooks) {
      if (typeof id !== 'string' || !/^[a-z][a-z0-9_-]{0,63}$/.test(id) || typeof render !== 'function' || own(views, id)) return;
      hooks = hooks || {};
      extensions.set(id, { render: render, activate: typeof hooks.activate === 'function' ? hooks.activate : null, deactivate: typeof hooks.deactivate === 'function' ? hooks.deactivate : null });
      // A direct hash entry can precede a DOM-ready extension registration.
      // Retire that cached fallback rather than leaving a valid route stranded.
      var host = document.getElementById('body-' + id);
      if (host) {
        delete host.dataset.filled;
        if (document.body.dataset.u1View === id) {
          host.dataset.filled = '1';
          mount(id, host);
        }
      }
    },
    mount: mount,
    activate: activate,
    deactivate: deactivate,
    icon: icon
  });
  window.addEventListener('u1:navigate', function (event) { if (activeExtension && event.detail && event.detail.id !== activeExtension.id) deactivate(activeExtension.id, activeExtension.host); });
  document.addEventListener('u1:safety-change', function (event) {
    if (!event.detail || !event.detail.locked) return;
    routeEpoch++; snapshot = null; activeRecord = null;
    if (activeExtension) deactivate(activeExtension.id, activeExtension.host);
    if (dialog && dialog.open) dialog.close();
  });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init); else init();
})();
