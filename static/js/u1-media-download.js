/* Explicit source review and official export links. No automatic remote media fetch. */
(function () {
  'use strict';
  var API = '/api/workspace/media-download', root, registered = false, revision = 0, busy = false;
  function esc(value) { return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function status(message, error) { var node = root.querySelector('[data-intake-status]'); node.textContent = message; node.dataset.error = String(!!error); }
  async function request(body) {
    var controller = new AbortController(), timer = setTimeout(function () { controller.abort(); }, 10000), headers = {};
    try {
      if (body) {
        var response = await fetch('/api/integrations', { credentials: 'same-origin', cache: 'no-store', signal: controller.signal });
        if (!response.ok) throw Error('Local authorisation is unavailable.');
        var registry = await response.json(); if (!registry.csrf_token) throw Error('Reload the page for local authorisation.');
        headers = { 'Content-Type': 'application/json', 'X-U1-CSRF': registry.csrf_token };
      }
      var result = await fetch(API, { method: body ? 'POST' : 'GET', credentials: 'same-origin', cache: 'no-store', headers: headers, body: body ? JSON.stringify(body) : undefined, signal: controller.signal });
      var data = await result.json(); if (!result.ok || data.success !== true) throw Error(data.error || 'Source review did not complete.');
      return data;
    } finally { clearTimeout(timer); }
  }
  function payload(action) {
    var form = root.querySelector('form');
    return { action: action, url: form.elements.url.value.trim(), rights_confirmed: form.elements.rights.checked, public_unprotected_confirmed: form.elements.public.checked };
  }
  function safeLink(value, help) {
    try { var url = new URL(value), hosts = help ? ['support.google.com', 'help.instagram.com', 'support.tiktok.com'] : ['www.youtube.com', 'www.instagram.com', 'www.tiktok.com'];
      return url.protocol === 'https:' && !url.username && !url.password && hosts.includes(url.hostname) ? esc(url.href) : '';
    } catch (error) { return ''; }
  }
  async function review(event) {
    event.preventDefault(); if (busy) return; busy = true;
    var button = root.querySelector('[data-intake-review]'), serial = revision; button.disabled = true;
    try {
      status('Reviewing the URL format and your confirmation locally. No source is being fetched.');
      var result = await request(payload('review_source'));
      if (serial !== revision) { status('The source or confirmation changed. Review again.'); return; }
      root.querySelector('[data-intake-result]').innerHTML = '<section class="u1-mr-card"><h2>' + esc(result.provider_name) + ' / source review</h2><p>' + esc(result.guidance) + '</p>' +
        '<p class="u1-mr-note">Public access and rights are your confirmation, not an independent check. No media was downloaded.</p><p>' + esc(result.watermark_policy) + '</p>' +
        '<div class="u1-mr-actions"><a href="' + safeLink(result.canonical_url, false) + '" target="_blank" rel="noopener noreferrer">Open source (external)</a><a href="' + safeLink(result.help_url, true) + '" target="_blank" rel="noopener noreferrer">Official export help (external)</a></div>' +
        '<button type="button" data-intake-manifest>Export source review JSON</button></section>';
      status('Review ready. Choose an official export or your original file; automatic downloads are unavailable.');
    } catch (error) { status(error.name === 'AbortError' ? 'The local review timed out.' : error.message, true); }
    finally { busy = false; button.disabled = false; }
  }
  async function exportManifest() {
    if (busy) return; busy = true;
    try {
      var serial = revision, result = await request(payload('export_manifest'));
      if (serial !== revision) { status('Source changed. Review it again before export.'); return; }
      var bytes = Uint8Array.from(atob(result.content), function (c) { return c.charCodeAt(0); });
      var url = URL.createObjectURL(new Blob([bytes], { type: result.mime })), link = document.createElement('a');
      link.href = url; link.download = result.filename; document.body.appendChild(link); link.click(); link.remove();
      setTimeout(function () { URL.revokeObjectURL(url); }, 30000);
      status('Source review JSON created. This is an attribution record, not a media file.');
    } catch (error) { status(error.message, true); }
    finally { busy = false; }
  }
  async function mount(host) {
    var first = !root;
    if (first) {
      root = document.createElement('section'); root.className = 'u1-mr';
      root.innerHTML = '<aside class="u1-mr-nav"><p class="u1-mr-eyebrow">MEDIA / INTAKE</p><button type="button" data-intake-local>Media studio<span>Open a local original</span></button><button type="button" aria-current="page">Source intake<span>Rights and official exports</span></button></aside>' +
        '<div class="u1-mr-main"><header class="u1-mr-heading"><p class="u1-mr-eyebrow">YOUTUBE / INSTAGRAM / TIKTOK</p><h1>Start with a source you can use.</h1><p>Review a direct post link, use an official export, then bring your authorised original into Media Studio.</p></header>' +
        '<section class="u1-mr-card"><h2>Automatic downloads are unavailable</h2><p data-intake-availability>Checking the local downloader status...</p><p class="u1-mr-note">No 4K promise. Use the best original or official export available within the 25 MB local import limit. Creator and platform watermarks are preserved.</p></section>' +
        '<form class="u1-mr-card"><label>Direct video, post or reel URL<input name="url" type="url" maxlength="2000" required placeholder="https://..."></label>' +
        '<label class="u1-mr-check"><input type="checkbox" name="rights" required>I own this media or have explicit permission to download and reuse it.</label>' +
        '<label class="u1-mr-check"><input type="checkbox" name="public" required>This is a public, unprotected post. I am not requesting access to private or DRM-protected media.</label>' +
        '<button type="submit" class="u1-mr-primary" data-intake-review>Review source and export options</button></form><div data-intake-result></div>' +
        '<p class="u1-mr-status" data-intake-status role="status" aria-live="polite"></p><footer class="u1-mr-footer">No browser cookies, account credentials, private profiles, redirect expansion or remote media requests are used. For an unwatermarked result, use an original file you own. Watermark removal and cropping are not implemented here.</footer></div>';
      root.querySelector('form').addEventListener('submit', review);
      root.querySelector('form').addEventListener('input', function () { revision++; root.querySelector('[data-intake-result]').replaceChildren(); });
      root.addEventListener('click', function (event) {
        if (event.target.closest('[data-intake-local]') && window.U1Platform) window.U1Platform.open('media');
        if (event.target.closest('[data-intake-manifest]')) exportManifest();
      });
    }
    if (root.parentNode !== host) host.replaceChildren(root);
    if (first) {
      try { var info = await request(); root.querySelector('[data-intake-availability]').textContent = (info.yt_dlp_detected ? 'yt-dlp was detected but is not enabled. ' : 'yt-dlp is not installed. ') + info.reason; }
      catch (error) { root.querySelector('[data-intake-availability]').textContent = 'Local downloader status is unavailable. Direct downloads remain disabled.'; }
    }
  }
  function register() {
    if (registered) return true; if (!window.U1CoreViews) return false;
    window.U1CoreViews.register('media-downloads', mount); registered = true;
    document.dispatchEvent(new CustomEvent('u1:native-views-ready', { detail: { ids: ['media-downloads'] } })); return true;
  }
  window.U1MediaDownload = Object.freeze({ register: register, mount: mount });
  register(); document.addEventListener('u1:core-views-ready', register);
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', register, { once: true });
})();
