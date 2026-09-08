/* Shared, bounded reads. Credentials and errors are never cached. */
(function () {
  'use strict';
  var cache = new Map(), pending = new Map(), epoch = 0;
  async function request(path, options) {
    var controller = new AbortController(), timer = setTimeout(function () { controller.abort(); }, 20000);
    try {
      var response = await fetch(path, Object.assign({ credentials: 'same-origin', cache: 'no-store', signal: controller.signal }, options));
      var data = await response.json();
      if (!response.ok || data.success === false) throw new Error(data.error || data.message || 'The local service could not complete this request.');
      return data;
    } catch (error) {
      if (error.name === 'AbortError') throw new Error('The local service took too long. Your existing data has not been cleared.');
      throw error;
    } finally { clearTimeout(timer); }
  }
  function get(path, options) {
    var fresh = options && options.fresh, entry = cache.get(path);
    var cacheable = /^\/api\/workspace\//.test(path) && !/file\?|google|recovery|export|trash/.test(path);
    if (!fresh && cacheable && entry && Date.now() - entry.at < 12000) return Promise.resolve(entry.data);
    if (!fresh && pending.has(path)) return pending.get(path);
    var generation = epoch;
    var promise = request(path).then(function (data) {
      if (cacheable && generation === epoch) {
        if (cache.size >= 24) cache.delete(cache.keys().next().value);
        cache.set(path, { at: Date.now(), data: data });
      }
      return data;
    }).finally(function () { if (pending.get(path) === promise) pending.delete(path); });
    pending.set(path, promise);
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
  function invalidate() { epoch++; cache.clear(); }
  window.U1Data = Object.freeze({ get: get, post: post, invalidate: invalidate });
})();
