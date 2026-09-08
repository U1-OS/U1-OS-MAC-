/* Native local planning extensions. Load after U1Data, U1CoreViews and U1Life. */
(function () {
  'use strict';
  const API = '/api/workspace/personal';
  const states = new WeakMap();
  const remembered = new Map();
  const tabs = {
    life: [['today', 'Today'], ['household', 'Household'], ['wellbeing', 'Wellbeing']],
    income: [['products', 'Products & launch'], ['clients', 'Clients & delivery'], ['opportunities', 'Opportunities'], ['pricing', 'Pricing'], ['content', 'Content & video']],
    research: [['watchlists', 'Watchlists & alerts'], ['journal', 'Paper journal'], ['paper', 'Paper trading']]
  };
  const headings = {
    life: ['LIFE / LOCAL PLANNING', 'Make room for your day.', 'A few priorities, a little structure, and space to begin again.'],
    income: ['INCOME / WORK IN PROGRESS', 'Build useful work.', 'Shape a product, serve a client, and keep the next step visible.'],
    research: ['MARKETS / MANUAL PAPER RESEARCH', 'Observe. Record. Review.', 'Keep evidence, threshold checks and simulated outcomes separate from real money.']
  };
  let rowSequence = 0;
  function esc(value) { return String(value == null ? '' : value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])); }
  function human(value) { return String(value || '').replace(/_/g, ' ').replace(/^./, c => c.toUpperCase()); }
  function stamp(value) { const d = new Date(Number(value) * 1000); return Number.isFinite(d.getTime()) ? d.toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) : 'Timestamp unavailable'; }
  function deviceTime(value) { const d = new Date(value * 1000); return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 19); }
  function button(label, attrs, primary) { return '<button type="button" ' + attrs + (primary ? ' class="u1p-primary"' : '') + '>' + esc(label) + '</button>'; }
  function route(id, label) { return button(label, 'data-go="' + id + '"'); }
  function message(s, text, error) {
    s.message = text || ''; s.error = !!error;
    const node = s.host.querySelector('[data-personal-status]');
    if (node) { node.textContent = s.message; node.setAttribute('role', error ? 'alert' : 'status'); }
  }
  function kindLabel(s, kind) { return s.data && s.data.schemas[kind] ? s.data.schemas[kind].label : human(kind); }
  function referenceLabel(s, id) { const item = s.data.references.find(r => r.id === id); return item ? item.title + (item.archived ? ' (archived/unavailable)' : '') : 'Linked record unavailable'; }
  function moneyText(currency, value) { return esc(currency) + ' ' + esc(value); }
  function getRecord(s, id) { return s.data.records.find(r => r.id === id); }
  function note(text) { return '<p class="u1p-note">' + esc(text) + '</p>'; }
  function meta(label, value) { return value === '' || value == null ? '' : '<div><dt>' + esc(label) + '</dt><dd>' + esc(value) + '</dd></div>'; }
  function download(value, name) {
    const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2) + '\n'], { type: 'application/json' }));
    const link = document.createElement('a'); link.href = url; link.download = name;
    document.body.appendChild(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 30000);
  }
  function query(s) {
    const q = new URLSearchParams({ collection: s.tab, archived: s.archived, limit: '100', offset: String(s.offset) });
    if (s.kind) q.set('kind', s.kind);
    if (s.search) q.set('q', s.search);
    if (s.tab === 'today' && s.day) q.set('day', s.day);
    return q;
  }
  async function load(s) {
    const serial = ++s.serial;
    const requestedQuery = query(s).toString();
    if (s.data && s.loadedQuery !== requestedQuery) s.data = null;
    s.loading = true;
    if (!s.data) render(s);
    const contextPath = s.view === 'life' ? '/api/workspace/prism/summary' : s.view === 'income' ? '/api/workspace/business' : null;
    const results = await Promise.allSettled([
      window.U1Data.get(API + '?' + requestedQuery, { fresh: true }),
      contextPath ? window.U1Data.get(contextPath, { fresh: true }) : Promise.resolve(null)
    ]);
    if (s.serial !== serial || states.get(s.host) !== s) return;
    s.loading = false;
    if (results[0].status === 'rejected') {
      s.message = results[0].reason.message; s.error = true; render(s); return;
    }
    s.data = results[0].value;
    s.loadedQuery = requestedQuery;
    s.context = results[1].status === 'fulfilled' ? results[1].value : null;
    s.contextError = results[1].status === 'rejected' ? results[1].reason.message : '';
    s.contextAt = Date.now() / 1000;
    if (!s.day) {
      s.day = s.data.today;
      if (s.tab === 'today') { await load(s); return; }
    }
    render(s);
  }
  function snapshotContext(s) {
    if (s.view === 'income') {
      if (!s.context) return '<aside class="u1p-source-panel">' + note('Actual manual ledger unavailable: ' + (s.contextError || 'no response')) + '</aside>';
      const totals = s.context.totals || {};
      const currencies = Object.keys(totals).filter(k => /^[A-Z]{3}$/.test(k)).sort();
      return '<aside class="u1p-source-panel"><div><span class="u1p-eyebrow">ACTUAL MANUAL LEDGER</span><h3>Recorded money, kept separate.</h3></div><div class="u1p-ledger">' +
        (currencies.length ? currencies.map(currency => {
          const t = totals[currency];
          const amount = key => typeof t[key] === 'number' && Number.isFinite(t[key]) ? (t[key] / 100).toFixed(2) : 'Unavailable';
          return '<div><strong>' + esc(currency) + '</strong><span>Recorded income ' + esc(amount('income_minor')) + '</span><span>Recorded expense ' + esc(amount('expense_minor')) + '</span></div>';
        }).join('') : note('No actual ledger entries recorded.')) + '</div>' + note((s.context.source || 'Operator-entered ledger') + '. Retrieved ' + stamp(s.contextAt) + '. Currencies are not combined; pricing and paper results never enter these totals.') + button('Open manual ledger', 'data-platform="business"') + '</aside>';
    }
    if (s.view === 'research') return '<aside class="u1p-source-panel u1p-research-notice"><strong>Manual research and explicit paper simulation</strong>' + note('Automated strategy evaluation is unavailable. Thresholds run only when you submit a reviewed observation. Paper fills use simulated cash; no broker, wallet or live execution is connected.') + '<div class="u1p-actions">' + route('crypto', 'Crypto snapshots') + route('trading', 'Market schedules') + '</div></aside>';
    if (s.tab !== 'today') return '';
    if (!s.context) return '<aside class="u1p-source-panel">' + note('Workspace tasks and calendar unavailable: ' + (s.contextError || 'no response')) + '</aside>';
    const rows = Array.isArray(s.context.records) ? s.context.records : [];
    const events = rows.filter(r => {
      if (r.kind !== 'event' || r.deleted) return false;
      const d = new Date((r.payload || {}).start);
      if (!Number.isFinite(d.getTime())) return false;
      const parts = new Intl.DateTimeFormat('en-CA', { timeZone: s.data.timezone, year: 'numeric', month: '2-digit', day: '2-digit' }).formatToParts(d);
      const get = type => parts.find(p => p.type === type).value;
      return get('year') + '-' + get('month') + '-' + get('day') === s.day;
    }).sort((a, b) => new Date(a.payload.start) - new Date(b.payload.start));
    const tasks = rows.filter(r => r.kind === 'task' && !r.deleted && !(r.payload || {}).done);
    return '<aside class="u1p-source-panel"><div class="u1p-section-title"><h3>From your workspace</h3><span>' + tasks.length + ' open tasks</span></div><div class="u1p-agenda">' +
      (events.length ? events.slice(0, 8).map(r => '<div><time>' + esc(new Date(r.payload.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', timeZone: s.data.timezone })) + '</time><strong>' + esc(r.title) + '</strong></div>').join('') : note('No saved workspace events for this date.')) + '</div>' + note('PRISM records retrieved ' + stamp(s.contextAt) + '. Times use ' + s.data.timezone + '. Select existing tasks in a priority to link your work.') + '<div class="u1p-actions">' + route('tasks', 'Open tasks') + route('calendar', 'Open calendar') + '</div></aside>';
  }
  function card(s, r) {
    const p = r.payload, kind = r.kind;
    let details = '', extra = '', quick = '';
    if (kind === 'priority') { details = meta('Date', p.day) + meta('Position', p.slot); quick = button(p.done ? 'Reopen priority' : 'Mark complete', 'data-toggle="' + r.id + '"'); }
    if (kind === 'time_block') details = meta('Date', p.day) + meta('Time', p.start + ' - ' + p.end);
    if (kind === 'bill') details = meta('Planned amount', p.currency + ' ' + p.amount) + meta('Due', p.due) + meta('Payee', p.payee) + meta('Repeat plan', human(p.recurrence));
    if (kind === 'habit') {
      details = meta('Rhythm', human(p.cadence)) + meta('Cue', p.cue);
      const checks = p.checkins || [], checked = checks.includes(s.data.today);
      extra = note(checks.length + ' recorded check-ins. Start again whenever it suits you.') + '<div class="u1p-checkin"><label>Check-in date<input type="date" data-habit-day="' + r.id + '" value="' + s.data.today + '"></label>' + button('Record check-in', 'data-checkin="' + r.id + '"') + button('Remove check-in', 'data-uncheck="' + r.id + '"') + '</div><details><summary>' + (checked ? 'Today is recorded' : 'Check-in history') + '</summary>' + note(checks.length ? checks.join(', ') : 'No dates recorded yet.') + '</details>';
    }
    if (kind === 'product') {
      details = meta('Audience', p.audience) + meta('Version', p.current_version) + meta('Planned release', p.release_date);
      extra = note(p.description) + ((p.versions || []).length ? '<details><summary>' + p.versions.length + ' linked version files</summary><ul>' + p.versions.map(v => '<li><strong>' + esc(v.version) + '</strong> / ' + esc(referenceLabel(s, v.file_id)) + note(v.notes) + '</li>').join('') + '</ul>' + route('files', 'Open local Files') + '</details>' : note('No version files linked. Import files through the Files workspace.'));
    }
    if (kind === 'launch') details = meta('Product', referenceLabel(s, p.product_id)) + meta('Due', p.due);
    if (kind === 'opportunity') {
      details = meta('Confidence', human(p.confidence)) + meta('Next step', p.next_action);
      extra = note(p.hypothesis) + '<details><summary>' + p.evidence.length + ' evidence entries</summary>' + p.evidence.map(e => '<div class="u1p-evidence"><strong>' + esc(e.source) + '</strong>' + note(e.observed_on + ' / ' + e.note) + (e.url ? '<a href="' + esc(e.url) + '" target="_blank" rel="noopener noreferrer">Open evidence source</a>' : '') + '</div>').join('') + '</details>';
    }
    if (kind === 'contact') details = meta('Organization', p.organization) + meta('Role', p.role) + meta('Email', p.email) + meta('Phone', p.phone);
    if (kind === 'offer') { details = meta('Client', p.contact_id ? referenceLabel(s, p.contact_id) : '') + meta('Draft quoted price', p.currency + ' ' + p.price); extra = note(p.scope) + note(p.outcome) + (p.assumptions ? '<details><summary>Assumptions and exclusions</summary>' + note(p.assumptions) + '</details>' : ''); }
    if (kind === 'client_project') { details = meta('Client', referenceLabel(s, p.contact_id)) + meta('Delivery', p.due) + meta('Next action', p.next_action); extra = note(p.deliverables); }
    if (kind === 'note') { details = meta('Related', p.parent_id ? referenceLabel(s, p.parent_id) : '') + meta('Tag', p.tag); extra = '<p class="u1p-prose">' + esc(p.text) + '</p>'; }
    if (kind === 'pricing') {
      const e = r.estimate;
      extra = '<div class="u1p-estimate"><span class="u1p-eyebrow">ESTIMATES / ' + esc(p.currency) + '</span><dl>' + meta('Assumed sales', e.assumed_sales) + meta('Assumed costs', e.assumed_costs) + meta('Estimated result', e.estimated_result) + meta('Break-even units', e.break_even_units == null ? 'No positive unit contribution' : e.break_even_units) + '</dl></div>' + note(p.assumptions) + note(e.notice);
    }
    if (kind === 'content') { details = meta('Channel', human(p.channel)) + meta('Planned date', p.scheduled_on || 'Unscheduled') + meta('Planned time', p.scheduled_time); extra = '<p class="u1p-prose">' + esc(p.copy) + '</p>' + note(p.cta) + (p.published_url ? '<a href="' + esc(p.published_url) + '" target="_blank" rel="noopener noreferrer">Operator-recorded published link</a>' : ''); }
    if (kind === 'video') { details = meta('Opening hook', p.hook) + meta('Rights review', p.rights_reviewed ? 'Operator confirmed' : 'Pending') + meta('Content review', p.content_reviewed ? 'Operator confirmed' : 'Pending'); extra = '<details><summary>Script and production notes</summary><p class="u1p-prose">' + esc(p.script) + '</p>' + note(p.shot_list) + note(p.voice_notes) + note(p.asset_notes) + '</details>'; }
    if (kind === 'watchlist') { details = meta('Symbol', p.symbol) + meta('Type', human(p.asset_type)) + meta('Currency', p.currency) + meta('Observed on', p.observed_on); extra = note(p.thesis) + (p.source_url ? '<a href="' + esc(p.source_url) + '" target="_blank" rel="noopener noreferrer">Open research source</a>' : ''); }
    if (kind === 'alert') {
      details = meta('Watchlist', referenceLabel(s, p.watch_id)) + meta('Threshold', human(p.condition) + ' ' + p.threshold) + meta('Local crossings', p.trigger_count || 0);
      const history = p.evaluations || [], last = history[history.length - 1];
      extra = last ? note((last.matched ? 'Matched' : 'Not matched') + ' at ' + stamp(last.quote.observed_at) + '. ' + last.quote.source + '. On-demand observation; not a current live status.') : note('Not evaluated. Submit a reviewed observation to check this threshold.');
      quick = button('Evaluate observation', 'data-evaluate="' + r.id + '"');
    }
    if (kind === 'journal') { details = meta('Paper instrument', p.symbol) + meta('Direction', human(p.side)) + meta('Entry date', p.day) + meta('Assumed entry', p.currency + ' ' + p.entry_price) + meta('Quantity', p.quantity); extra = note(p.thesis) + (r.estimate ? '<p class="u1p-result">Paper result <strong>' + moneyText(p.currency, r.estimate.paper_result) + '</strong></p>' : '') + '<details><summary>Risk plan and review</summary>' + note(p.risk_plan) + note(p.review) + '</details>'; }
    if (kind === 'paper_account') {
      const balance = s.data.paper_balances[r.id];
      if (balance) {
        extra = '<div class="u1p-estimate"><span class="u1p-eyebrow">SIMULATED BALANCES / ' + esc(balance.currency) + '</span><dl>' + meta('Available paper cash', balance.cash) + meta('Realized paper result', balance.realized_result) + meta('Recorded paper fills', balance.trade_count) + '</dl></div>' +
          (balance.holdings.length ? '<div class="u1p-table-scroll"><table><caption>Paper holdings at historical cost</caption><thead><tr><th>Symbol</th><th>Quantity</th><th>Cost basis</th></tr></thead><tbody>' + balance.holdings.map(h => '<tr><td>' + esc(h.symbol) + '</td><td>' + esc(h.quantity) + '</td><td>' + moneyText(balance.currency, h.cost_basis) + '</td></tr>').join('') + '</tbody></table></div>' : note('No open paper holdings.')) + note(balance.notice);
        quick = button('Simulate buy', 'data-paper="' + r.id + '" data-side="buy"', true) + button('Simulate sell', 'data-paper="' + r.id + '" data-side="sell"') + button('Fill history', 'data-history="' + r.id + '"');
      }
    }
    if (['launch', 'video'].includes(kind) && !r.archived) {
      const stages = s.data.schemas[kind].fields.status.options, index = stages.indexOf(p.status);
      if (index < stages.length - 1) quick += button('Move to ' + human(stages[index + 1]), 'data-advance="' + r.id + '"');
    }
    const status = r.archived ? 'Archived' : kind === 'priority' ? (p.done ? 'Completed' : 'Priority ' + p.slot) : p.status ? human(p.status) : kindLabel(s, kind);
    return '<article class="u1p-card" data-kind="' + kind + '"><div class="u1p-card-heading"><span class="u1p-eyebrow">' + esc(kindLabel(s, kind)) + '</span><span class="u1p-badge">' + esc(status) + '</span></div><h3>' + esc(r.title) + '</h3>' + (details ? '<dl>' + details + '</dl>' : '') + extra + (p.notes ? '<p class="u1p-prose u1p-card-notes">' + esc(p.notes) + '</p>' : '') + '<div class="u1p-card-actions">' + (r.archived ? button('Restore', 'data-restore="' + r.id + '"') + button('Delete permanently', 'data-delete="' + r.id + '"') : quick) + button('Edit', 'data-edit="' + r.id + '"') + (!r.archived ? button('Archive', 'data-archive="' + r.id + '"') : '') + '</div><small class="u1p-revision">Version ' + r.version + ' / Saved ' + esc(stamp(r.updated)) + '</small></article>';
  }
  function empty(s, kind) {
    return '<div class="u1p-empty"><span class="u1p-empty-mark" aria-hidden="true">+</span><h3>Start with one ' + esc(kindLabel(s, kind).toLowerCase()) + '.</h3>' + note(s.data.schemas[kind].description) + button('Create ' + kindLabel(s, kind).toLowerCase(), 'data-new="' + kind + '"', true) + '</div>';
  }
  function recordsView(s) {
    const rows = s.data.records;
    if (!rows.length && (s.search || s.archived !== 'active')) return '<div class="u1p-empty"><h3>No matching records.</h3>' + note('Adjust the search or archive filter. Existing records are not changed.') + '</div>';
    if (s.tab === 'today' && !s.kind && s.archived === 'active' && !s.search) {
      const priorities = rows.filter(r => r.kind === 'priority'), blocks = rows.filter(r => r.kind === 'time_block').sort((a, b) => a.payload.start.localeCompare(b.payload.start));
      return '<div class="u1p-section-title"><h3>Your top three</h3><span>' + esc(s.day) + '</span></div><div class="u1p-priorities">' + [1, 2, 3].map(slot => {
        const row = priorities.find(r => r.payload.slot === slot);
        return row ? card(s, row) : '<div class="u1p-priority-space"><span>0' + slot + '</span><h3>A little room to focus.</h3>' + button('Choose priority ' + slot, 'data-new="priority" data-slot="' + slot + '"') + '</div>';
      }).join('') + '</div><div class="u1p-section-title"><h3>Time, with intention</h3>' + button('Add time block', 'data-new="time_block"') + '</div><div class="u1p-grid">' + (blocks.length ? blocks.map(r => card(s, r)).join('') : empty(s, 'time_block')) + '</div>';
    }
    if (s.tab === 'products' && !s.kind && s.archived === 'active') {
      const products = rows.filter(r => r.kind === 'product'), launches = rows.filter(r => r.kind === 'launch');
      return '<div class="u1p-grid">' + (products.length ? products.map(r => card(s, r)).join('') : empty(s, 'product')) + '</div><div class="u1p-section-title"><h3>Launch board</h3>' + button('New launch task', 'data-new="launch"') + '</div>' + note('Columns show matching records on this page. Use the record-type filter and pagination for larger boards.') + '<div class="u1p-kanban">' + ['backlog', 'doing', 'review', 'done'].map(stage => {
        const items = launches.filter(r => r.payload.status === stage);
        return '<section><h4>' + human(stage) + '<span>' + items.length + '</span></h4>' + items.map(r => card(s, r)).join('') + (!items.length ? note('No matching tasks.') : '') + '</section>';
      }).join('') + '</div>';
    }
    if (s.tab === 'content' && s.archived === 'active') {
      const dated = rows.filter(r => r.kind === 'content' && r.payload.scheduled_on).sort((a, b) => (a.payload.scheduled_on + a.payload.scheduled_time).localeCompare(b.payload.scheduled_on + b.payload.scheduled_time));
      const other = rows.filter(r => r.kind !== 'content' || !r.payload.scheduled_on);
      return '<div class="u1p-section-title"><h3>Editorial calendar</h3><span>Operator-managed drafts</span></div>' + note('All dates and times are planning notes in ' + s.data.timezone + '. Posting is performed by you outside U1 OS.') + '<div class="u1p-calendar">' + dated.map(r => '<section><time>' + esc(r.payload.scheduled_on) + '</time>' + card(s, r) + '</section>').join('') + '</div><div class="u1p-section-title"><h3>Draft desk & video production</h3></div><div class="u1p-grid">' + (other.length ? other.map(r => card(s, r)).join('') : !dated.length ? empty(s, s.kind || 'content') : note('No unscheduled drafts on this page.')) + '</div>';
    }
    return '<div class="u1p-grid">' + (rows.length ? rows.map(r => card(s, r)).join('') : empty(s, s.kind || s.data.collections[s.tab].kinds[0])) + '</div>';
  }
  function render(s) {
    const h = headings[s.view], choices = s.data ? s.data.collections[s.tab].kinds : [];
    s.host.classList.add('u1-native-workspace', 'u1-personal');
    s.host.innerHTML = '<header class="u1p-hero"><div><span class="u1p-eyebrow">' + h[0] + '</span><h2>' + h[1] + '</h2><p>' + h[2] + '</p></div><div class="u1p-orbit" aria-hidden="true"><i></i><b>U1</b></div></header><nav class="u1p-destinations" aria-label="Planning destinations">' + ['life', 'income', 'research'].map(id => '<button type="button" data-go="' + id + '"' + (id === s.view ? ' aria-current="page"' : '') + '>' + ({ life: 'My day', income: 'Income & work', research: 'Research' }[id]) + '</button>').join('') + '</nav><div class="u1p-tabs" role="tablist" aria-label="' + esc(s.view) + ' workflows">' + tabs[s.view].map(([id, label]) => '<button type="button" role="tab" id="u1p-tab-' + s.view + '-' + id + '" aria-controls="u1p-panel-' + s.view + '" aria-selected="' + (id === s.tab) + '" tabindex="' + (id === s.tab ? '0' : '-1') + '" data-tab="' + id + '">' + esc(label) + '</button>').join('') + '</div><div class="u1p-toolbar">' +
      (s.data ? '<form data-search-form><label><span class="u1p-sr-only">Search titles and record contents</span><input type="search" name="q" maxlength="160" placeholder="Search this workspace" value="' + esc(s.search) + '"></label><button type="submit">Search</button></form><label>Show<select data-type><option value="">All record types</option>' + choices.map(kind => '<option value="' + kind + '"' + (kind === s.kind ? ' selected' : '') + '>' + esc(kindLabel(s, kind)) + '</option>').join('') + '</select></label><label>Records<select data-archive-filter>' + ['active', 'archived', 'all'].map(value => '<option value="' + value + '"' + (value === s.archived ? ' selected' : '') + '>' + human(value) + '</option>').join('') + '</select></label>' + (s.tab === 'today' ? '<label>Plan date<input type="date" data-plan-day value="' + esc(s.day) + '" required></label>' : '') : '') + button('Refresh', 'data-refresh') + button('Export all', 'data-export') + '</div><p class="u1p-status" data-personal-status role="' + (s.error ? 'alert' : 'status') + '" aria-live="polite">' + esc(s.message) + '</p>' +
      (s.data ? '<div class="u1p-freshness"><span class="u1p-dot"></span>Local database snapshot / ' + esc(stamp(s.data.generated_at)) + '<span>' + s.data.count + ' / ' + s.data.limits.records + ' records</span></div><div class="u1p-create-actions">' + choices.map(kind => button('New ' + kindLabel(s, kind).toLowerCase(), 'data-new="' + kind + '"', choices.length === 1)).join('') + '</div><section id="u1p-panel-' + s.view + '" role="tabpanel" aria-labelledby="u1p-tab-' + s.view + '-' + s.tab + '" tabindex="0">' + recordsView(s) + '</section><div class="u1p-pagination"><span>' + (s.data.total ? s.offset + 1 : 0) + '-' + (s.offset + s.data.records.length) + ' of ' + s.data.total + ' matching records</span>' + button('Previous', 'data-page="-1"' + (s.offset ? '' : ' disabled')) + button('Next', 'data-page="1"' + (s.data.has_more ? '' : ' disabled')) + '</div>' + snapshotContext(s) + '<footer class="u1p-footer">' + esc(s.data.notice) + '</footer>' : '<div class="u1p-empty"><h3>' + (s.loading ? 'Opening your local workspace...' : 'Planning service unavailable') + '</h3>' + note(s.loading ? 'Reading saved records.' : 'Use Refresh after the parent has wired the personal endpoint.') + '</div>');
  }
  function openDialog(s, title, description) {
    if (s.dialog && s.dialog.open) s.dialog.close();
    const source = document.activeElement, dialog = document.createElement('dialog');
    dialog.className = 'u1-personal-dialog';
    dialog.setAttribute('aria-labelledby', 'u1p-editor-heading');
    dialog.innerHTML = '<header><div><span class="u1p-eyebrow">PRIVATE / LOCAL</span><h2 id="u1p-editor-heading">' + esc(title) + '</h2></div>' + button('Close', 'data-dialog-close') + '</header>' + note(description) + '<div data-dialog-content></div>';
    document.body.appendChild(dialog); s.dialog = dialog;
    dialog.addEventListener('click', event => { if (event.target.closest('[data-dialog-close]')) dialog.close(); });
    dialog.addEventListener('cancel', event => { if (dialog.dataset.busy === 'true') event.preventDefault(); });
    dialog.addEventListener('close', () => { dialog.remove(); if (s.dialog === dialog) s.dialog = null; if (source && source.isConnected) source.focus({ preventScroll: true }); }, { once: true });
    dialog.showModal();
    return dialog;
  }
  function fieldMarkup(s, name, spec, value, prefix, lists) {
    const key = prefix + name, required = spec.required ? ' required' : '', label = esc(spec.label);
    if (spec.type === 'list') {
      lists.set(key, spec);
      return '<fieldset class="u1p-list" data-list="' + key + '"><legend>' + label + ' <small>Up to ' + spec.maximum + '</small></legend><div class="u1p-list-rows">' + (value || []).map(row => listRow(s, key, spec, row, lists)).join('') + '</div>' + button('Add entry', 'data-add-list="' + key + '"') + '</fieldset>';
    }
    if (spec.type === 'boolean') return '<label class="u1p-check"><input type="checkbox" name="' + key + '"' + (value ? ' checked' : '') + '>' + label + '</label>';
    let control;
    if (spec.type === 'textarea') control = '<textarea name="' + key + '" rows="4" maxlength="' + spec.maximum + '"' + required + '>' + esc(value) + '</textarea>';
    else if (spec.type === 'choice') control = '<select name="' + key + '">' + spec.options.map(option => '<option value="' + option + '"' + (value === option ? ' selected' : '') + '>' + esc(human(option)) + '</option>').join('') + '</select>';
    else if (spec.type === 'reference') {
      const options = s.data.references.filter(r => spec.references.includes(r.kind) && (!r.archived || r.id === value));
      control = '<select name="' + key + '"' + required + '><option value="">' + (spec.required ? 'Choose a saved record' : 'No link') + '</option>' + options.map(r => '<option value="' + r.id + '"' + (r.id === value ? ' selected' : '') + '>' + esc(r.title + (r.archived ? ' (archived/unavailable)' : '')) + '</option>').join('') + (value && !options.some(r => r.id === value) ? '<option value="' + esc(value) + '" selected>Linked record unavailable</option>' : '') + '</select>';
      if (!options.length) control += '<small>Create the related record first' + (spec.references.includes('file') ? ' in Files. File contents are not copied here.' : ' in its workspace tab.') + '</small>';
    } else {
      const type = ({ date: 'date', time: 'time', email: 'email', url: 'url', integer: 'number' })[spec.type] || 'text';
      let attrs = '';
      if (spec.type === 'integer') attrs = ' min="' + spec.minimum + '" max="' + spec.maximum + '" step="1"';
      else if (spec.type === 'decimal') attrs = ' inputmode="decimal" maxlength="24" placeholder="0"';
      else attrs = ' maxlength="' + (spec.maximum || (spec.type === 'url' ? 1000 : 160)) + '"';
      control = '<input name="' + key + '" type="' + type + '" value="' + esc(value) + '"' + attrs + required + '>';
    }
    return '<label class="' + (spec.type === 'textarea' ? 'u1p-wide' : '') + '">' + label + control + '</label>';
  }
  function listRow(s, key, spec, row, lists) {
    const prefix = key + '.' + (++rowSequence) + '.';
    return '<div class="u1p-list-row" data-row-prefix="' + prefix + '"><div class="u1p-form-grid">' + Object.entries(spec.fields).map(([name, f]) => fieldMarkup(s, name, f, row[name] == null ? f.default || '' : row[name], prefix, lists)).join('') + '</div>' + button('Remove entry', 'data-remove-row') + '</div>';
  }
  function readFields(root, specs, prefix) {
    const output = {};
    Object.entries(specs).forEach(([name, spec]) => {
      if (spec.type === 'list') {
        const list = root.querySelector('[data-list="' + prefix + name + '"]');
        output[name] = Array.from(list.querySelector('.u1p-list-rows').children).map(row => readFields(row, spec.fields, row.dataset.rowPrefix));
      } else {
        const input = root.querySelector('[name="' + prefix + name + '"]');
        output[name] = spec.type === 'boolean' ? input.checked : spec.type === 'integer' ? Number(input.value) : input.value;
      }
    });
    return output;
  }
  function dialogBusy(dialog, busy) {
    dialog.dataset.busy = String(busy);
    dialog.querySelectorAll('button').forEach(b => { b.disabled = busy; });
  }
  function dialogError(dialog, error) {
    const status = dialog.querySelector('[data-dialog-status]');
    if (status) { status.textContent = error.message || String(error); status.setAttribute('role', 'alert'); }
  }
  function editor(s, kind, row, slot) {
    const schema = s.data.schemas[kind], p = row ? row.payload : {}, lists = new Map();
    const dialog = openDialog(s, (row ? 'Edit ' : 'New ') + schema.label.toLowerCase(), schema.description);
    const content = dialog.querySelector('[data-dialog-content]');
    content.innerHTML = '<form class="u1p-editor"><label>Title<input name="title" maxlength="160" required value="' + esc(row ? row.title : '') + '"></label><div class="u1p-form-grid">' + Object.entries(schema.fields).map(([name, spec]) => {
      let value = p[name] == null ? (spec.type === 'list' ? [] : spec.default == null ? '' : spec.default) : p[name];
      if (!row && spec.type === 'date' && spec.required) value = name === 'day' ? s.day || s.data.today : s.data.today;
      if (!row && kind === 'priority' && name === 'slot') value = slot || [1, 2, 3].find(n => !s.data.records.some(r => r.kind === 'priority' && !r.archived && r.payload.day === s.day && r.payload.slot === n)) || 1;
      return fieldMarkup(s, name, spec, value, 'p.', lists);
    }).join('') + '</div><p data-dialog-status role="status" aria-live="polite"></p><footer>' + (row ? button('Load latest record', 'data-reload-record') : '') + button('Cancel', 'data-dialog-close') + '<button type="submit" class="u1p-primary">Save locally</button></footer></form>';
    dialog.addEventListener('click', async event => {
      const add = event.target.closest('[data-add-list]');
      if (add) {
        const key = add.dataset.addList, list = dialog.querySelector('[data-list="' + key + '"] .u1p-list-rows'), spec = lists.get(key);
        if (list.children.length >= spec.maximum) { dialogError(dialog, Error('This list holds at most ' + spec.maximum + ' entries.')); return; }
        list.insertAdjacentHTML('beforeend', listRow(s, key, spec, {}, lists));
        list.lastElementChild.querySelector('input,select,textarea').focus();
      }
      if (event.target.closest('[data-remove-row]')) event.target.closest('[data-row-prefix]').remove();
      if (event.target.closest('[data-reload-record]') && window.confirm('Replace this unsaved draft with the latest saved version?')) {
        try {
          const latest = await window.U1Data.get(API + '?id=' + row.id + '&archived=all', { fresh: true });
          if (!latest.records.length) throw Error('The record no longer exists. Your draft is still here.');
          s.data.references = latest.references;
          editor(s, kind, latest.records[0]);
        } catch (error) { dialogError(dialog, error); }
      }
    });
    dialog.querySelector('form').addEventListener('submit', async event => {
      event.preventDefault();
      if (dialog.dataset.busy === 'true') return;
      const body = { action: row ? 'update' : 'create', title: event.currentTarget.elements.title.value, payload: readFields(dialog, schema.fields, 'p.') };
      if (row) { body.id = row.id; body.expected_version = row.version; } else body.kind = kind;
      dialogBusy(dialog, true);
      try {
        await window.U1Data.post(API, body); dialog.close();
        message(s, schema.label + ' saved in the local database.'); await load(s);
      } catch (error) { dialogError(dialog, error); } finally { if (dialog.isConnected) dialogBusy(dialog, false); }
    });
    dialog.querySelector('[name="title"]').focus();
  }
  function quoteFields(symbol, currency) {
    return '<div class="u1p-form-grid"><label>Instrument symbol<input name="symbol" maxlength="40" value="' + esc(symbol || '') + '" required></label><label>Account / watch currency<input name="currency" maxlength="3" value="' + esc(currency) + '" readonly required></label><label>Reviewed price<input name="price" inputmode="decimal" maxlength="24" required></label><label>Observation time (this device)<input name="observed" type="datetime-local" step="1" value="' + deviceTime(Date.now() / 1000) + '" required></label><label>Source label<input name="source" maxlength="200" value="Operator-reviewed manual observation" required></label><label>Price basis<select name="basis"><option value="manual">Manual observation</option><option value="snapshot">Source-labelled snapshot</option></select></label></div><div class="u1p-observations">' + button('Load available crypto snapshot', 'data-load-quotes') + '<div data-quote-choices></div></div>';
  }
  async function observationDialog(s, row, side) {
    let symbol = '', currency = row.payload.currency;
    if (row.kind === 'alert') {
      const watch = await window.U1Data.get(API + '?id=' + row.payload.watch_id, { fresh: true });
      if (!watch.records.length) throw Error('The watchlist item must be active before evaluating.');
      symbol = watch.records[0].payload.symbol; currency = watch.records[0].payload.currency;
    }
    const paper = row.kind === 'paper_account';
    const dialog = openDialog(s, paper ? 'Simulated ' + side + ' / ' + row.title : 'Evaluate threshold / ' + row.title,
      'Review the source, price and timestamp. Observations must be from the last 15 minutes. This submits a local ' + (paper ? 'paper fill only. No live order is sent.' : 'threshold check only. It does not start monitoring.'));
    dialog.querySelector('[data-dialog-content]').innerHTML = '<form class="u1p-editor">' + quoteFields(symbol, currency) + (paper ? '<div class="u1p-form-grid"><label>Paper quantity<input name="quantity" inputmode="decimal" maxlength="24" required></label><label>Assumed fees<input name="fees" inputmode="decimal" maxlength="24" value="0" required></label></div>' : '') + '<label class="u1p-check"><input type="checkbox" name="reviewed" required>I reviewed this observation' + (paper ? ', quantity and simulated ' + side : ' and threshold') + '.</label><p data-dialog-status role="status" aria-live="polite"></p><footer>' + button('Cancel', 'data-dialog-close') + '<button type="submit" class="u1p-primary">' + (paper ? 'Confirm simulated ' + side : 'Evaluate once locally') + '</button></footer></form>';
    const form = dialog.querySelector('form');
    if (!paper) form.elements.symbol.readOnly = true;
    let quotes = [];
    form.addEventListener('input', event => {
      if (event.target.name !== 'reviewed') form.elements.reviewed.checked = false;
      if (form.elements.basis.value === 'snapshot' && ['price', 'symbol'].includes(event.target.name)) {
        form.elements.basis.value = 'manual'; form.elements.source.value = 'Operator-edited observation';
      }
    });
    dialog.addEventListener('click', async event => {
      const request = event.target.closest('[data-load-quotes]');
      if (request) {
        request.disabled = true;
        try {
          const data = await window.U1Data.get('/api/workspace/live/crypto', { fresh: true });
          const at = data.fetched_at;
          const fresh = !data.stale && typeof at === 'number' && Number.isFinite(at) && Date.now() / 1000 - at <= 900 && at <= Date.now() / 1000 + 30;
          quotes = (Array.isArray(data.quotes) ? data.quotes : []).filter(q => typeof q.price === 'number' && Number.isFinite(q.price) && q.price > 0 && String(q.currency).toUpperCase() === currency && (!symbol || String(q.symbol).toUpperCase() === symbol)).slice(0, 12).map(q => ({ symbol: String(q.symbol).toUpperCase(), price: q.price.toFixed(8).replace(/\.?0+$/, ''), at: at, source: String(data.source || 'Existing local crypto snapshot adapter').slice(0, 200) }));
          dialog.querySelector('[data-quote-choices]').innerHTML = note((fresh ? 'Adapter snapshot fetched ' : 'Unavailable or stale snapshot / ') + stamp(at) + '. Source: ' + (data.source || 'not supplied') + '. Review before use.') + (fresh && quotes.length ? quotes.map((q, i) => button(q.symbol + ' / ' + currency + ' ' + q.price, 'data-use-quote="' + i + '"')).join('') : note('No fresh matching-currency observations are available. Enter a reviewed manual observation.'));
        } catch (error) { dialogError(dialog, error); } finally { request.disabled = false; }
      }
      const use = event.target.closest('[data-use-quote]');
      if (use) {
        const q = quotes[Number(use.dataset.useQuote)];
        form.elements.symbol.value = q.symbol; form.elements.price.value = q.price;
        form.elements.observed.value = deviceTime(q.at); form.elements.source.value = q.source;
        form.elements.basis.value = 'snapshot'; form.elements.reviewed.checked = false;
      }
    });
    form.addEventListener('submit', async event => {
      event.preventDefault(); if (dialog.dataset.busy === 'true') return;
      const f = new FormData(form), body = { action: paper ? 'paper_trade' : 'evaluate_alert', id: row.id, expected_version: row.version, reviewed: f.has('reviewed'),
        quote: { symbol: f.get('symbol'), currency: f.get('currency'), price: f.get('price'), observed_at: new Date(f.get('observed')).getTime() / 1000, source: f.get('source'), basis: f.get('basis') } };
      if (paper) { body.side = side; body.quantity = f.get('quantity'); body.fees = f.get('fees'); }
      dialogBusy(dialog, true);
      try {
        const result = await window.U1Data.post(API, body); dialog.close();
        message(s, paper ? 'Simulated ' + side + ' recorded. Available paper cash: ' + currency + ' ' + result.paper_balance.cash + '.' : result.deduplicated ? 'Observation already evaluated. No duplicate crossing recorded.' : result.triggered ? 'A local threshold crossing was recorded for this observation.' : 'Observation evaluated. No new threshold crossing.');
        await load(s);
      } catch (error) { dialogError(dialog, error); } finally { if (dialog.isConnected) dialogBusy(dialog, false); }
    });
  }
  function historyDialog(s, row) {
    const records = s.data.paper_trades.filter(t => t.account_id === row.id);
    const dialog = openDialog(s, 'Paper fill history / ' + row.title, 'Immutable simulated fills. These observations and outcomes never enter the actual manual ledger. Export all includes the full paper history.');
    let offset = 0;
    function draw() {
      dialog.querySelector('[data-dialog-content]').innerHTML = '<div class="u1p-table-scroll"><table><caption>' + records.length + ' simulated fills / ' + esc(row.payload.currency) + '</caption><thead><tr><th>Recorded</th><th>Fill</th><th>Quantity / price</th><th>Cash after</th><th>Paper result</th><th>Observation</th></tr></thead><tbody>' + records.slice(offset, offset + 50).map(t => '<tr><td>' + esc(stamp(t.created)) + '</td><td>' + esc(human(t.side) + ' ' + t.symbol) + '</td><td>' + esc(t.quantity + ' / ' + t.price) + '</td><td>' + esc(t.cash_after) + '</td><td>' + esc(t.realized_result) + '</td><td>' + esc(t.source + ' / ' + stamp(t.observed_at) + ' / ' + t.price_basis) + '</td></tr>').join('') + '</tbody></table></div><div class="u1p-pagination">' + button('Previous 50', 'data-history-page="-1"' + (offset ? '' : ' disabled')) + button('Next 50', 'data-history-page="1"' + (offset + 50 < records.length ? '' : ' disabled')) + '</div>';
    }
    dialog.addEventListener('click', event => { const b = event.target.closest('[data-history-page]'); if (b) { offset += Number(b.dataset.historyPage) * 50; draw(); } });
    draw();
  }
  async function mutate(s, row, body) {
    if (s.busy.has(row.id)) return;
    s.busy.add(row.id);
    try { await window.U1Data.post(API, { ...body, id: row.id, expected_version: row.version }); message(s, 'Local record updated.'); await load(s); }
    finally { s.busy.delete(row.id); }
  }
  async function handleClick(s, event) {
    const b = event.target.closest('button'); if (!b || !s.host.contains(b)) return;
    try {
      if (b.dataset.tab) {
        s.tab = b.dataset.tab; remembered.set(s.view, s.tab); s.offset = 0; s.kind = ''; s.search = ''; s.message = ''; s.error = false;
        await load(s); const tab = s.host.querySelector('[data-tab="' + s.tab + '"]'); if (tab) tab.focus(); return;
      }
      if (b.hasAttribute('data-refresh')) { message(s, ''); await load(s); return; }
      if (b.hasAttribute('data-export')) {
        b.disabled = true; const data = await window.U1Data.get(API + '/export', { fresh: true });
        download(data, 'u1-personal-workflows-' + new Date().toISOString().slice(0, 10) + '.json');
        message(s, 'Export downloaded, including archived records and immutable paper fills. Linked file contents are not embedded.'); return;
      }
      if (!s.data) return;
      if (b.dataset.new) { editor(s, b.dataset.new, null, Number(b.dataset.slot) || null); return; }
      if (b.dataset.page) { s.offset = Math.max(0, s.offset + Number(b.dataset.page) * 100); await load(s); return; }
      const id = b.dataset.edit || b.dataset.archive || b.dataset.restore || b.dataset.delete || b.dataset.toggle || b.dataset.checkin || b.dataset.uncheck || b.dataset.advance || b.dataset.paper || b.dataset.evaluate || b.dataset.history;
      if (!id) return;
      const row = getRecord(s, id); if (!row) throw Error('Refresh to load this record before changing it.');
      if (b.dataset.edit) editor(s, row.kind, row);
      if (b.dataset.archive) await mutate(s, row, { action: 'archive' });
      if (b.dataset.restore) await mutate(s, row, { action: 'restore' });
      if (b.dataset.delete && window.confirm('Permanently delete this archived record? Export first if you need a copy. This cannot be undone.')) await mutate(s, row, { action: 'delete', confirmed: true });
      if (b.dataset.toggle) await mutate(s, row, { action: 'update', payload: { done: !row.payload.done } });
      if (b.dataset.checkin || b.dataset.uncheck) {
        const day = s.host.querySelector('[data-habit-day="' + id + '"]').value;
        await mutate(s, row, { action: 'habit_checkin', day: day, checked: !!b.dataset.checkin });
      }
      if (b.dataset.advance) {
        const choices = s.data.schemas[row.kind].fields.status.options;
        await mutate(s, row, { action: 'update', payload: { status: choices[choices.indexOf(row.payload.status) + 1] } });
      }
      if (b.dataset.paper || b.dataset.evaluate) await observationDialog(s, row, b.dataset.side);
      if (b.dataset.history) historyDialog(s, row);
    } catch (error) { message(s, error.message, true); } finally { if (b.isConnected) b.disabled = false; }
  }
  function mount(view, host) {
    let s = states.get(host);
    if (!s || s.view !== view) {
      s = { host: host, view: view, tab: remembered.get(view) || tabs[view][0][0], data: null, day: '', kind: '', search: '', archived: 'active', offset: 0, serial: 0, busy: new Set(), message: '', error: false };
      states.set(host, s);
    }
    if (!host.dataset.personalBound) {
      host.dataset.personalBound = 'true';
      host.addEventListener('click', event => handleClick(states.get(host), event));
      host.addEventListener('submit', event => {
        if (!event.target.matches('[data-search-form]')) return;
        event.preventDefault(); const current = states.get(host); current.search = new FormData(event.target).get('q'); current.offset = 0; load(current);
      });
      host.addEventListener('change', event => {
        const current = states.get(host), input = event.target;
        if (input.matches('[data-type]')) current.kind = input.value;
        else if (input.matches('[data-archive-filter]')) current.archived = input.value;
        else if (input.matches('[data-plan-day]')) { if (!input.value) return; current.day = input.value; }
        else return;
        current.offset = 0; load(current);
      });
      host.addEventListener('keydown', event => {
        if (!event.target.matches('[role="tab"]') || !['ArrowRight', 'ArrowLeft', 'Home', 'End'].includes(event.key)) return;
        event.preventDefault(); const all = Array.from(host.querySelectorAll('[role="tab"]')), index = all.indexOf(event.target);
        const next = event.key === 'Home' ? 0 : event.key === 'End' ? all.length - 1 : (index + (event.key === 'ArrowRight' ? 1 : -1) + all.length) % all.length;
        all[next].click();
      });
    }
    return load(s);
  }
  function install() {
    if (!window.U1CoreViews || !window.U1Data) return false;
    ['life', 'income', 'research'].forEach(id => window.U1CoreViews.register(id, host => mount(id, host)));
    return true;
  }
  window.U1PersonalViews = Object.freeze({ install: install, mount: mount });
  install();
})();
