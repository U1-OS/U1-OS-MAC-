(function (global) {
  'use strict';
  var TOPICS = Object.freeze({
    'tech-gaming': Object.freeze([
      { id: 'technology', name: 'Technology / BBC News', existing: true },
      { id: 'playstation', name: 'Gaming / PlayStation Blog' },
      { id: 'xbox', name: 'Gaming / Xbox Wire' }
    ]),
    'sports-news': Object.freeze([
      { id: 'afl', name: 'AFL / The Guardian' },
      { id: 'cricket', name: 'Cricket / The Guardian' },
      { id: 'mma', name: 'UFC / MMA / The Guardian' },
      { id: 'boxing', name: 'Boxing / The Guardian' },
      { id: 'australia', name: 'Australian news / The Guardian', existing: true },
      { id: 'world', name: 'World news / BBC News', existing: true },
      { id: 'business', name: 'Business news / BBC News', existing: true }
    ])
  });
  function endpoint(topic) {
    return topic.existing ? '/api/workspace/live/news?category=' + encodeURIComponent(topic.id)
      : '/api/workspace/discovery?source=' + encodeURIComponent(topic.id);
  }
  function safeURL(value) {
    try {
      var url = new URL(value);
      return /^(https?:)$/.test(url.protocol) && !url.username && !url.password ? url.href : null;
    } catch (_) { return null; }
  }
  function date(value) {
    if (typeof value !== 'number' || !Number.isFinite(value) || value <= 0) return 'Not supplied';
    var parsed = new Date(value * 1000);
    return Number.isFinite(parsed.getTime()) ? parsed.toLocaleString() : 'Not supplied';
  }
  function freshness(data, now) {
    var observed = typeof data.fetched_at === 'number' && Number.isFinite(data.fetched_at) && data.fetched_at > 0;
    var aged = observed && now / 1000 - data.fetched_at > (data.refresh_seconds || 300);
    if (data.stale || aged || (data.success !== true && observed)) return 'Stale snapshot';
    if (data.success !== true) return 'Unavailable';
    if (!observed) return 'Timestamp unavailable';
    return (data.items || []).length ? 'Received snapshot' : 'No headlines returned';
  }
  function entries(data, query) {
    var needle = query.trim().toLowerCase();
    return (Array.isArray(data.items) ? data.items : []).slice(0, 24).filter(function (item) {
      return item && typeof item.title === 'string' && safeURL(item.url) &&
        (!needle || item.title.toLowerCase().indexOf(needle) !== -1);
    });
  }
  function element(doc, tag, text, className) {
    var node = doc.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  }
  function mount(host, id) {
    var doc = host.ownerDocument, win = doc.defaultView, topics = TOPICS[id];
    var root = element(doc, 'section', undefined, 'u1-discovery u1-native-workspace');
    root.setAttribute('aria-label', id === 'tech-gaming' ? 'Tech & Gaming' : 'Sports & News');
    var head = element(doc, 'header', undefined, 'u1-discovery-heading');
    head.append(element(doc, 'p', 'U1 / DISCOVERY', 'u1-discovery-eyebrow'),
      element(doc, 'h1', id === 'tech-gaming' ? 'Tech & Gaming' : 'Sports & News'),
      element(doc, 'p', 'Source-first headlines. Open the original story for the full context.'));
    var tools = element(doc, 'div', undefined, 'u1-discovery-tools');
    var label = element(doc, 'label', 'Topic and source');
    var select = element(doc, 'select');
    topics.forEach(function (topic) { var option = element(doc, 'option', topic.name); option.value = topic.id; select.append(option); });
    label.append(select);
    var searchLabel = element(doc, 'label', 'Filter received headlines');
    var search = element(doc, 'input'); search.type = 'search'; search.maxLength = 160;
    search.placeholder = 'Search these headlines'; searchLabel.append(search);
    var refresh = element(doc, 'button', 'Refresh'); refresh.type = 'button';
    tools.append(label, searchLabel, refresh);
    var state = element(doc, 'p', 'Not requested', 'u1-discovery-status');
    state.setAttribute('role', 'status'); state.setAttribute('aria-live', 'polite');
    var meta = element(doc, 'div', undefined, 'u1-discovery-meta');
    var list = element(doc, 'div', undefined, 'u1-discovery-grid');
    var notice = element(doc, 'p', 'Public headline snapshots, not live scores, fixtures or a match-state service. '
      + 'UFC coverage is not all MMA. Refresh checks a five-minute shared cache; no background polling.', 'u1-discovery-notice');
    root.append(head, tools, state, meta, list, notice); host.replaceChildren(root);
    var cache = new Map(), current = null, serial = 0, controller = null, busy = false;
    function selected() { return topics.find(function (topic) { return topic.id === select.value; }) || topics[0]; }
    function render() {
      var topic = selected(); meta.replaceChildren(); list.replaceChildren();
      if (!current) { state.textContent = busy ? 'Loading ' + topic.name + '...' : 'No snapshot available'; return; }
      var status = freshness(current, Date.now());
      state.textContent = (busy ? 'Refreshing. ' : '') + status + ' / ' + topic.name;
      root.dataset.freshness = status === 'Stale snapshot' ? 'stale' : status === 'Unavailable' ? 'unavailable' : 'snapshot';
      meta.append(element(doc, 'p', 'Source: ' + (current.source || topic.name)),
        element(doc, 'p', 'Fetched: ' + date(current.fetched_at) + ' / Attempted: ' + date(current.attempted_at)));
      var sourceURL = safeURL(current.source_url);
      if (sourceURL) { var source = element(doc, 'a', 'Open publisher (external)'); source.href = sourceURL; source.target = '_blank'; source.rel = 'noopener noreferrer'; meta.append(source); }
      if (current.success !== true) meta.append(element(doc, 'p', 'Provider or local route unavailable. Retained headlines, if any, are not current.'));
      if (current.feed_age_warning) meta.append(element(doc, 'p', 'Publisher feed is older than 48 hours. A recent fetch does not make these stories new.'));
      if (current.coverage) meta.append(element(doc, 'p', current.coverage));
      if (current.notice) meta.append(element(doc, 'p', String(current.notice).slice(0, 800)));
      var rows = entries(current, search.value);
      rows.forEach(function (item) {
        var card = element(doc, 'article', undefined, 'u1-discovery-card');
        var title = element(doc, 'h2'), link = element(doc, 'a', item.title.slice(0, 400));
        link.href = safeURL(item.url); link.target = '_blank'; link.rel = 'noopener noreferrer';
        link.setAttribute('aria-label', item.title.slice(0, 400) + ' (opens publisher in a new tab)'); title.append(link);
        card.append(element(doc, 'p', item.source || current.source || topic.name, 'u1-discovery-eyebrow'), title,
          element(doc, 'p', 'Published: ' + date(item.published_at)), element(doc, 'span', 'Read original story / external'));
        list.append(card);
      });
      if (!rows.length) list.append(element(doc, 'p', search.value ? 'No received headlines match this filter.'
        : current.success === true ? 'The publisher returned no usable headlines. This does not indicate whether a match is scheduled or live.'
          : 'No retained headlines. Try again later or open the publisher.'));
    }
    async function load() {
      var token = ++serial, topic = selected();
      if (controller) controller.abort();
      controller = new win.AbortController(); var request = controller;
      busy = true; refresh.disabled = true; refresh.textContent = 'Refreshing...'; list.setAttribute('aria-busy', 'true');
      current = cache.get(topic.id) || null; render();
      var timer = win.setTimeout(function () { request.abort(); }, 15000);
      try {
        var response = await win.fetch(endpoint(topic), { credentials: 'same-origin', signal: request.signal, headers: { Accept: 'application/json' } });
        if (!response.ok) throw new Error('Request unavailable');
        var payload = await response.json();
        if (!payload || typeof payload !== 'object' || typeof payload.success !== 'boolean' || (payload.items !== undefined && !Array.isArray(payload.items))) throw new Error('Invalid snapshot');
        if (token !== serial) return;
        current = payload; cache.set(topic.id, payload);
      } catch (_) {
        if (token !== serial) return;
        current = Object.assign({}, cache.get(topic.id) || {}, { success: false, stale: !!(cache.get(topic.id) || {}).fetched_at });
      } finally {
        win.clearTimeout(timer);
        if (token === serial) { busy = false; refresh.disabled = false; refresh.textContent = 'Refresh'; list.setAttribute('aria-busy', 'false'); render(); }
      }
    }
    refresh.addEventListener('click', load); select.addEventListener('change', load);
    search.addEventListener('input', render); load();
    return root;
  }
  function register(core) {
    if (!core || typeof core.register !== 'function') return false;
    Object.keys(TOPICS).forEach(function (id) { core.register(id, function (host) { return mount(host, id); }); });
    return true;
  }
  var api = Object.freeze({ topics: TOPICS, endpoint: endpoint, safeURL: safeURL, date: date, freshness: freshness, entries: entries, mount: mount, register: register });
  if (typeof module === 'object' && module.exports) module.exports = api;
  else { global.U1Discovery = api; register(global.U1CoreViews); }
})(typeof window !== 'undefined' ? window : globalThis);
