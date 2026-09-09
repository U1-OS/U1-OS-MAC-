/* Shared, bounded reads. Credentials and errors are never cached. */
(function () {
  'use strict';
  var cache = new Map(), pending = new Map(), inflight = new Set(), epoch = 0, safetyEpoch = 0;
  function locked() { return !!((document.documentElement && document.documentElement.dataset.u1Safety === 'locked') || (window.U1Safety && window.U1Safety.isLocked && window.U1Safety.isLocked())); }
  function cancelled(code) { var error = new Error(code === 'U1_LOCKED' ? 'Unlock U1 OS before reading or changing workspace data.' : 'This read was superseded. Request a fresh workspace snapshot.'); error.code = code; return error; }
  async function request(path, options, controller) {
    if (locked()) throw cancelled('U1_LOCKED');
    var access = safetyEpoch;
    controller = controller || new AbortController();
    var timer = setTimeout(function () { controller.abort(); }, 20000);
    try {
      var response = await fetch(path, Object.assign({ credentials: 'same-origin', cache: 'no-store', signal: controller.signal }, options));
      var data = await response.json();
      if (locked() || access !== safetyEpoch) throw cancelled('U1_LOCKED');
      if (!response.ok || data.success === false) throw new Error(data.error || data.message || 'The local service could not complete this request.');
      return data;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('The local service took too long. Your existing data has not been cleared.');
      throw error;
    } finally { clearTimeout(timer); }
  }
  function get(path, options) {
    if (locked()) return Promise.reject(cancelled('U1_LOCKED'));
    var fresh = options && options.fresh, entry = cache.get(path);
    var cacheable = /^\/api\/workspace\//.test(path) && !/file\?|google|recovery|export|trash/.test(path);
    if (!fresh && cacheable && entry && Date.now() - entry.at < 12000) return Promise.resolve(entry.data);
    if (!fresh && pending.has(path) && pending.get(path).epoch === epoch) return pending.get(path).promise;
    var generation = epoch, entryRequest = { epoch: epoch, controller: new AbortController(), promise: null };
    var promise = request(path, undefined, entryRequest.controller).then(function (data) {
      if (generation !== epoch) throw cancelled('U1_INVALIDATED');
      if (cacheable) {
        if (cache.size >= 24) cache.delete(cache.keys().next().value);
        cache.set(path, { at: Date.now(), data: data });
      }
      return data;
    }).catch(function (error) { if (generation !== epoch && error.code !== 'U1_LOCKED') throw cancelled('U1_INVALIDATED'); throw error; }).finally(function () { inflight.delete(entryRequest); if (pending.get(path) === entryRequest) pending.delete(path); });
    entryRequest.promise = promise;
    inflight.add(entryRequest); pending.set(path, entryRequest);
    return promise;
  }
  async function post(path, data) {
    var catalog = await request('/api/integrations');
    if (!catalog.csrf_token) throw new Error('Local authorisation is unavailable. Reload U1 OS and try again.');
    var result = await request(path, { method: 'POST', headers: { 'Content-Type': 'application/json', 'X-U1-CSRF': catalog.csrf_token }, body: JSON.stringify(data) });
    invalidate();
    document.dispatchEvent(new CustomEvent('u1:data-changed', { detail: { path: path } }));
    return result;
  }
  function invalidate() { epoch++; cache.clear(); pending.clear(); inflight.forEach(function (entry) { entry.controller.abort(); }); inflight.clear(); }
  document.addEventListener('u1:safety-change', function (event) { if (event.detail && event.detail.locked) { safetyEpoch++; invalidate(); } });
  window.U1Data = Object.freeze({ get: get, post: post, invalidate: invalidate });
})();
