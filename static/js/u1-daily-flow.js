/* Start my day: local snapshots and explicit navigation, never account actions. */
(function () {
  'use strict';
  const PRIORITIES = '/api/workspace/personal';
  const PRISM = '/api/workspace/prism/summary';
  const HOME_ID = 'u1-daily-flow-home';
  const STEPS = ['Focus', 'Schedule', 'Review'];
  const hosts = new Map();
  let home = null, model = null, pending = null, generation = 0;
  let installed = false, bound = false, locked = false, observer = null;

  function esc(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }
  function text(value, limit) { return typeof value === 'string' ? value.slice(0, limit || 300) : ''; }
  function link(label, attribute, destination, primary) {
    return '<button type="button" ' + attribute + '="' + destination + '"' + (primary ? ' class="u1df-primary"' : '') + '>' + esc(label) + '</button>';
  }
  function route(label, destination, primary) { return link(label, 'data-go', destination, primary); }
  function localButton(label, action, primary) { return link(label, 'data-daily-action', action, primary); }
  function validZone(value) {
    if (typeof value !== 'string' || value.length > 80) return null;
    try { new Intl.DateTimeFormat('en', { timeZone: value }).format(new Date()); return value; } catch (_) { return null; }
  }
  function zoneParts(value, zone) {
    const parts = new Intl.DateTimeFormat('en-CA', { timeZone: zone, year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hourCycle: 'h23' }).formatToParts(value);
    const part = type => parts.find(p => p.type === type).value;
    return { day: part('year') + '-' + part('month') + '-' + part('day'), time: part('hour') + ':' + part('minute'), seconds: part('second') };
  }
  function validDay(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value)) return false;
    const d = new Date(value + 'T00:00:00Z');
    return Number.isFinite(d.getTime()) && d.toISOString().slice(0, 10) === value;
  }
  function nextDay(day) { return new Date(new Date(day + 'T00:00:00Z').getTime() + 86400000).toISOString().slice(0, 10); }
  function timestamp(value, zone) {
    if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) return 'Timestamp unavailable';
    return new Date(value * 1000).toLocaleString([], { timeZone: zone, dateStyle: 'medium', timeStyle: 'short' });
  }
  function moment(value, zone) {
    if (typeof value !== 'string' || value.length > 80) return null;
    const match = /^(\d{4}-\d{2}-\d{2})(?:[T ]([01]\d|2[0-3]):([0-5]\d)(?::([0-5]\d)(?:\.\d{1,6})?)?(Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)?)?$/.exec(value);
    if (!match || !validDay(match[1])) return null;
    let day = match[1], clock = match[2] ? match[2] + ':' + match[3] : '', seconds = match[4] || '00';
    if (match[5]) {
      const d = new Date(value);
      if (!Number.isFinite(d.getTime())) return null;
      const parts = zoneParts(d, zone); day = parts.day; clock = parts.time; seconds = parts.seconds;
    }
    return { day: day, time: clock, key: day + 'T' + (clock || '00:00') + ':' + seconds, offsetMissing: !!clock && !match[5] };
  }
  function record(r) { return r && typeof r === 'object' && typeof r.title === 'string' && r.title.trim() && r.payload && typeof r.payload === 'object' && !Array.isArray(r.payload); }
  function source(result, name) {
    if (!result.ok) return { name: name, ok: false, error: result.error, at: null, warning: '' };
    return { name: name, ok: true, error: '', at: result.at, snapshotAt: result.value.generated_at, warning: '', stale: result.value.stale === true };
  }
  function build(prism, personal, day, zone, zoneKnown) {
    const pSource = source(personal, 'Personal priorities'), wSource = source(prism, 'PRISM local calendar and tasks');
    let priorities = [], events = [], tasks = [], ignoredPriorities = 0, ignoredEvents = 0, ignoredTasks = 0;
    if (personal.ok) {
      const slots = new Set();
      personal.value.records.slice(0, 200).forEach(r => {
        if (r && (r.archived || r.deleted || r.kind !== 'priority')) return;
        if (!record(r) || r.payload.day !== day || !Number.isInteger(r.payload.slot) || r.payload.slot < 1 || r.payload.slot > 3 || typeof r.payload.done !== 'boolean' || slots.has(r.payload.slot)) { ignoredPriorities++; return; }
        slots.add(r.payload.slot);
        priorities.push({ title: text(r.title, 160), slot: r.payload.slot, done: r.payload.done, notes: text(r.payload.notes, 500) });
      });
      priorities.sort((a, b) => a.slot - b.slot);
      if (ignoredPriorities || personal.value.has_more === true) pSource.warning = 'Some priority records could not be shown. Open My Day to review the saved slots.';
    }
    if (prism.ok) {
      const dayStart = day + 'T00:00:00', dayEnd = nextDay(day) + 'T00:00:00';
      prism.value.records.slice(0, 1000).forEach(r => {
        if (!r || r.deleted) return;
        if (r.kind === 'task') {
          if (!record(r) || typeof r.payload.done !== 'boolean' || (r.payload.due && !validDay(r.payload.due))) { ignoredTasks++; return; }
          if (!r.payload.done) tasks.push({ title: text(r.title, 160), due: r.payload.due || '' });
        }
        if (r.kind === 'event') {
          if (!record(r)) { ignoredEvents++; return; }
          const start = moment(r.payload.start, zone), end = r.payload.end ? moment(r.payload.end, zone) : null;
          if (!start || (r.payload.end && !end) || (end && end.key < start.key)) { ignoredEvents++; return; }
          const intersects = end && end.key > start.key ? start.key < dayEnd && end.key > dayStart : start.day === day;
          if (intersects) events.push({ title: text(r.title, 160), location: text(r.payload.location, 200), start: start, end: end });
        }
      });
      events.sort((a, b) => a.start.key.localeCompare(b.start.key));
      if (ignoredEvents || ignoredTasks) wSource.warning = ignoredEvents + ' event(s) and ' + ignoredTasks + ' task(s) could not be read. Review the source workspace.';
    }
    return { day: day, zone: zone, zoneKnown: zoneKnown, priorities: priorities, events: events, tasks: tasks,
      personal: pSource, prism: wSource, loadedAt: Date.now() / 1000, locked: false };
  }
  async function read(path) {
    try {
      const value = await window.U1Data.get(path, { fresh: true });
      if (!value || value.success === false || !Array.isArray(value.records)) throw Error('The local source did not return a valid record snapshot.');
      return { ok: true, value: value, at: Date.now() / 1000 };
    } catch (error) { return { ok: false, error: text(error && error.message, 400) || 'Local source unavailable.' }; }
  }
  function priorityPath(day) {
    return PRIORITIES + '?collection=today&day=' + encodeURIComponent(day) + '&kind=priority&limit=3';
  }
  function refresh() {
    if (locked) { paint(); return Promise.resolve(null); }
    if (pending) return pending;
    const ticket = generation, deviceZone = validZone(Intl.DateTimeFormat().resolvedOptions().timeZone) || 'UTC';
    const initialZone = model && model.zone || deviceZone;
    const initialDay = zoneParts(new Date(), initialZone).day;
    paint(true);
    const request = (async () => {
      const responses = await Promise.all([read(PRISM), read(priorityPath(initialDay))]);
      if (ticket !== generation || locked) return null;
      const prism = responses[0]; let personal = responses[1];
      const pZone = personal.ok && validZone(personal.value.timezone);
      const wZone = prism.ok && prism.value.profile && validZone(prism.value.profile.timezone);
      const zone = pZone || wZone || deviceZone;
      let day = personal.ok && validDay(personal.value.today) ? personal.value.today : zoneParts(new Date(), zone).day;
      if (day !== initialDay) {
        personal = await read(priorityPath(day));
        if (ticket !== generation || locked) return null;
        if (personal.ok && validDay(personal.value.today) && personal.value.today !== day) {
          personal = { ok: false, error: 'The workspace date changed during refresh. Refresh again for the new day.' };
        }
      }
      model = build(prism, personal, day, zone, !!(pZone || wZone));
      paint(false);
      return model;
    })();
    pending = request;
    request.finally(() => { if (pending === request) pending = null; });
    return request;
  }
  function provenance(s, zone) {
    if (!s.ok) return '<p class="u1df-source u1df-error" role="status">' + esc(s.name) + ' unavailable. ' + esc(s.error) + '</p>';
    return '<p class="u1df-source">' + esc(s.name) + ' / Read ' + esc(timestamp(s.at, zone)) +
      (typeof s.snapshotAt === 'number' ? ' / Source snapshot ' + esc(timestamp(s.snapshotAt, zone)) : ' / Source snapshot timestamp not supplied') +
      (s.stale ? ' / SOURCE MARKED STALE' : '') + '. Refresh to read again.</p>' + (s.warning ? '<p class="u1df-source u1df-error">' + esc(s.warning) + '</p>' : '');
  }
  function prioritiesView(m, compact) {
    if (!m.personal.ok) return '<div class="u1df-empty"><h3>Priorities are unavailable.</h3><p>Your saved priorities have not been cleared. Refresh or open My Day.</p></div>';
    return '<ol class="u1df-priorities' + (compact ? ' u1df-compact' : '') + '">' + [1, 2, 3].map(slot => {
      const item = m.priorities.find(p => p.slot === slot);
      return '<li><span class="u1df-slot" aria-label="Priority ' + slot + '">0' + slot + '</span><div>' +
        (item ? '<h3>' + esc(item.title) + '</h3><span class="u1df-state">' + (item.done ? 'Marked complete in My Day' : 'Chosen by you') + '</span>' + (!compact && item.notes ? '<p>' + esc(item.notes) + '</p>' : '') : '<h3>' + (m.personal.warning ? 'Slot could not be confirmed' : 'Room for a priority') + '</h3><span class="u1df-state">' + (m.personal.warning ? 'Review My Day' : 'Choose it in My Day') + '</span>') + '</div></li>';
    }).join('') + '</ol>';
  }
  function tasksView(m, onlyToday) {
    if (!m.prism.ok) return '<p class="u1df-error">Local tasks unavailable. No empty task list is inferred.</p>';
    const rows = onlyToday ? m.tasks.filter(t => t.due === m.day) : m.tasks;
    return '<ul class="u1df-task-list">' + rows.slice(0, 8).map(t => '<li><strong>' + esc(t.title) + '</strong><span>' + esc(t.due ? (t.due === m.day ? 'Due today' : 'Due ' + t.due) : 'No due date saved') + '</span></li>').join('') + '</ul>' +
      (!rows.length ? '<p class="u1df-muted">' + (m.prism.warning ? 'No matching readable tasks. Review the source warning below.' : onlyToday ? 'No open tasks due today in this snapshot.' : 'No open tasks in this snapshot.') + '</p>' : '') +
      '<p class="u1df-source">Showing ' + Math.min(rows.length, 8) + ' of ' + rows.length + ' matching open tasks in the returned snapshot. Saved workspace order; no automatic ranking.</p>';
  }
  function agenda(m) {
    if (!m.prism.ok) return '<div class="u1df-empty"><h3>Calendar unavailable.</h3><p>No free time or appointments are inferred. Refresh or open Calendar.</p></div>';
    return '<ol class="u1df-agenda">' + m.events.slice(0, 20).map(e => {
      const start = (e.start.day < m.day ? 'From ' + e.start.day + ' / ' : '') + (e.start.time || 'Time not supplied');
      const end = e.end ? 'Ends ' + (e.end.day !== m.day ? e.end.day + ' / ' : '') + (e.end.time || 'time not supplied') : 'End time not supplied';
      return '<li><time>' + esc(start) + '</time><div><h3>' + esc(e.title) + '</h3><p>' + esc(end) + (e.location ? ' / ' + esc(e.location) : '') + '</p>' + (e.start.offsetMissing ? '<small>Saved without a UTC offset; shown as workspace local time.</small>' : '') + '</div></li>';
    }).join('') + '</ol>' + (!m.events.length ? '<div class="u1df-empty"><h3>' + (m.prism.warning ? 'No readable matching events.' : 'No local events saved for today.') + '</h3><p>' + (m.prism.warning ? 'Review the source warning below.' : 'This only describes the returned local calendar snapshot. External calendars may differ.') + '</p></div>' : '<p class="u1df-source">Showing ' + Math.min(m.events.length, 20) + ' of ' + m.events.length + ' matching local events, in chronological order.</p>');
  }
  function reviewView() {
    return '<div class="u1df-review-grid"><article class="u1df-panel"><span class="u1df-kicker">REVIEW FIRST</span><h3>Check the source, then decide.</h3><p>Open the actual review queue to inspect saved source material and suggested tasks or appointments. Adding anything to your calendar remains your decision.</p>' + link('Open review queue', 'data-platform', 'drafts', true) + '</article><article class="u1df-panel"><span class="u1df-kicker">EXISTING DAILY BRIEF</span><h3>Bring the available context together.</h3><p>Open the existing daily brief and review its sources. Starting this flow does not run an automation or generate an email summary.</p>' + link('Open daily brief', 'data-platform', 'briefing') + '</article></div><aside class="u1df-connection"><strong>Google email requires an authorised connection and a successful sync.</strong><p>This view does not read an email account, check connection status, sync a calendar or invent messages. Review connection permissions in Connections.</p>' + route('Open Connections', 'integrations') + '</aside>';
  }
  function render(host, state, busy) {
    host.classList.add('u1-native-workspace', 'u1-daily-flow');
    if (locked) {
      host.innerHTML = '<section class="u1df-panel"><h2>Your day is private.</h2><p>Unlock U1 OS before loading saved records.</p>' + route('Safety controls', 'security') + '</section>';
      return;
    }
    const m = model, step = state.step;
    host.innerHTML = '<header class="u1df-hero"><div><span class="u1df-kicker">START MY DAY / YOUR LOCAL WORKSPACE</span><h2>A clear place to begin.</h2><p>Review what matters, see your schedule, and decide what needs your attention.</p></div><span class="u1df-day-mark" aria-hidden="true">01 / 03</span></header><div class="u1df-datebar"><span>' + (m ? esc(m.day) + ' / ' + esc(m.zone) + (m.zoneKnown ? ' / Workspace date' : ' / Device date; workspace timezone unavailable') : 'Reading the workspace date...') + '</span>' + localButton(busy ? 'Refreshing...' : 'Refresh local snapshots', 'refresh') + '</div><nav class="u1df-steps" aria-label="Start my day steps">' + STEPS.map((label, i) => '<button type="button" data-daily-step="' + i + '"' + (i === step ? ' aria-current="step"' : '') + '><span>0' + (i + 1) + '</span>' + label + '</button>').join('') + '</nav><p class="u1df-status" role="status" aria-live="polite">' + (busy ? 'Reading local priorities, calendar and tasks. No account sync is requested.' : m ? 'Step ' + (step + 1) + ' of 3. ' + (m.personal.ok && m.prism.ok ? 'Saved local snapshots are ready to review.' : 'Some local sources are unavailable; available records are still shown.') : 'Local data has not loaded yet.') + '</p>' +
      '<section class="u1df-step-panel" tabindex="-1" aria-label="' + STEPS[step] + '">' +
      (step === 0 ? '<div class="u1df-section-heading"><div><span class="u1df-kicker">01 / FOCUS</span><h3>Your three, chosen by you.</h3><p>Keep your existing priorities in their saved positions. You decide what belongs here.</p></div>' + route('Edit priorities in My Day', 'life', true) + '</div>' + (m ? prioritiesView(m, false) + provenance(m.personal, m.zone) + '<section class="u1df-panel"><div class="u1df-section-heading"><h3>Tasks to consider</h3><label>Show<select data-daily-tasks><option value="all"' + (!state.onlyToday ? ' selected' : '') + '>All open tasks</option><option value="today"' + (state.onlyToday ? ' selected' : '') + '>Due today</option></select></label></div>' + tasksView(m, state.onlyToday) + route('Open Tasks', 'tasks') + '</section>' + provenance(m.prism, m.zone) : '<p class="u1df-muted">Your actual priorities will appear when the local source responds.</p>') :
      step === 1 ? '<div class="u1df-section-heading"><div><span class="u1df-kicker">02 / SCHEDULE</span><h3>See the shape of today.</h3><p>Saved local appointments, including events that continue into today.</p></div>' + route('Open native Calendar', 'calendar', true) + '</div>' + (m ? agenda(m) + provenance(m.prism, m.zone) : '<p class="u1df-muted">Waiting for the local calendar snapshot.</p>') + '<div class="u1df-actions">' + route('Plan time blocks in My Day', 'life') + '</div>' :
      '<div class="u1df-section-heading"><div><span class="u1df-kicker">03 / REVIEW</span><h3>Make the next decision yours.</h3><p>Use the existing review tools when you are ready. Nothing is approved or scheduled by this flow.</p></div></div>' + reviewView()) + '</section><footer class="u1df-flow-footer"><span>Focus / Schedule / Review</span><div class="u1df-actions">' + (step > 0 ? localButton('Back to ' + STEPS[step - 1].toLowerCase(), 'back') : route('Back to Home', 'home')) + (step < 2 ? localButton('Continue to ' + STEPS[step + 1].toLowerCase(), 'next', true) : route('Continue in My Day', 'life', true)) + '</div></footer><p class="u1df-source">Read-only local overview. Saved priorities and tasks are not auto-ranked or modified. PRISM returns up to 1,000 local records; this view is not a complete external calendar or inbox.</p>';
    const refreshButton = host.querySelector('[data-daily-action="refresh"]');
    if (refreshButton) refreshButton.disabled = !!busy;
    const mark = host.querySelector('.u1df-day-mark');
    if (mark) mark.textContent = '0' + (step + 1) + ' / 03';
  }
  function renderHome(busy) {
    if (!home || !home.isConnected) return;
    const m = model;
    home.innerHTML = '<div class="u1df-home-heading"><div><span class="u1df-kicker">A MOMENT TO GET YOUR BEARINGS</span><h2>Start my day.</h2><p>Focus, schedule, review. Your saved work, one step at a time.</p></div>' + route('Start my day', 'daily', true) + '</div>' +
      (locked ? '<p class="u1df-muted">Unlock U1 OS to read your saved daily records.</p>' : m ? '<div class="u1df-home-summary"><div>' + prioritiesView(m, true) + '</div><aside><strong>' + (m.prism.ok ? m.events.length + ' local event' + (m.events.length === 1 ? '' : 's') : 'Calendar unavailable') + '</strong><p>' + (m.prism.ok ? m.tasks.length + ' open tasks in the returned snapshot.' : 'Refresh to read the saved calendar and tasks.') + '</p><span>' + esc(m.day + ' / ' + m.zone) + '</span></aside></div>' + provenance(m.personal, m.zone) + provenance(m.prism, m.zone) : '<p class="u1df-muted">' + (busy ? 'Reading your local day...' : 'Open or refresh to read your actual local priorities and calendar.') + '</p>') +
      '<div class="u1df-actions">' + route('My Day', 'life') + route('Calendar', 'calendar') + link('Review queue', 'data-platform', 'drafts') + localButton(busy ? 'Refreshing...' : 'Refresh preview', 'refresh') + '</div>';
    const b = home.querySelector('[data-daily-action="refresh"]');
    if (b) b.disabled = !!busy || locked;
  }
  function paint(busy) {
    renderHome(busy);
    for (const [host, state] of hosts) {
      if (!host.isConnected) { hosts.delete(host); continue; }
      render(host, state, busy);
    }
  }
  function showStep(host, state, index) {
    state.step = Math.max(0, Math.min(2, index)); render(host, state, !!pending);
    const panel = host.querySelector('.u1df-step-panel'); if (panel) panel.focus({ preventScroll: true });
  }
  function mount(host) {
    let state = hosts.get(host);
    if (!state) {
      state = { step: 0, onlyToday: false }; hosts.set(host, state);
      host.addEventListener('click', event => {
        const b = event.target.closest('button'); if (!b || !host.contains(b)) return;
        if (b.hasAttribute('data-daily-step')) showStep(host, state, Number(b.dataset.dailyStep));
        if (b.dataset.dailyAction === 'next') showStep(host, state, state.step + 1);
        if (b.dataset.dailyAction === 'back') showStep(host, state, state.step - 1);
        if (b.dataset.dailyAction === 'refresh') refresh();
      });
      host.addEventListener('change', event => {
        if (event.target.matches('[data-daily-tasks]')) { state.onlyToday = event.target.value === 'today'; render(host, state, !!pending); }
      });
    }
    render(host, state, !!pending);
    return refresh();
  }
  function visible() {
    const id = document.body && document.body.dataset.u1View;
    return id === 'home' || id === 'daily';
  }
  function attachHome(target) {
    const parent = target || document.getElementById('v-home');
    if (!parent) return null;
    const existing = document.getElementById(HOME_ID);
    if (existing) { home = existing; return home; }
    home = document.createElement('section'); home.id = HOME_ID; home.className = 'u1-daily-flow u1df-home';
    home.setAttribute('aria-label', 'Start my day preview');
    parent.appendChild(home);
    home.addEventListener('click', event => { const b = event.target.closest('[data-daily-action="refresh"]'); if (b) refresh(); });
    renderHome(false);
    return home;
  }
  function setup() {
    attachHome();
    if (bound) return;
    bound = true;
    document.addEventListener('u1:safety-change', event => {
      locked = !!(event.detail && event.detail.locked);
      generation++; pending = null; model = null; paint(false);
      if (!locked && visible()) refresh();
    });
    document.addEventListener('u1:data-changed', event => {
      const path = event.detail && event.detail.path || '';
      if (path.startsWith(PRIORITIES) || path.startsWith('/api/workspace/prism/')) {
        generation++; pending = null; model = null; paint(false);
        if (visible() && !locked) refresh();
      }
    });
    document.addEventListener('visibilitychange', () => { if (!document.hidden && visible() && !locked) refresh(); });
    if (typeof MutationObserver === 'function' && document.body) {
      observer = new MutationObserver(() => { if (visible() && !locked) { attachHome(); refresh(); } });
      observer.observe(document.body, { attributes: true, attributeFilter: ['data-u1-view'] });
    }
    if (visible() && !locked) refresh();
  }
  function install() {
    if (!window.U1CoreViews || !window.U1Data) return false;
    if (!installed) { window.U1CoreViews.register('daily', mount); installed = true; }
    if (document.readyState === 'loading') {
      if (!bound) document.addEventListener('DOMContentLoaded', setup, { once: true });
    } else setup();
    return true;
  }
  window.U1DailyFlow = Object.freeze({ install: install, mount: mount, attachHome: attachHome, refresh: refresh,
    meta: Object.freeze({ daily: { t: 'Start my day', s: 'Focus, schedule and review your actual local day.' } }) });
  install();
})();
