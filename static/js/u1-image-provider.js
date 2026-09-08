(function () {
  'use strict';
  var views = new Map();
  function esc(value) { return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function message(state, text, error) { var node = state.host.querySelector('[data-image-status]'); if (node) { node.textContent = text; node.setAttribute('role', error ? 'alert' : 'status'); } }
  function api(body, timeout) { return window.U1Assistant.request('/api/workspace/image-provider', body, timeout); }
  function clearImages() { views.forEach(function (state) { var gallery = state.host.querySelector('[data-image-gallery]'); if (gallery) gallery.replaceChildren(); }); }
  function clearCredentials(state) { var field = state.host.querySelector('[name=api_key]'); if (field) field.value = ''; }
  async function refresh(state) {
    if (state.refreshing || !state.host.isConnected || !state.host.querySelector('[data-image-provider]') || window.U1Assistant.isLocked()) return;
    state.refreshing = true;
    try {
      var data = await api(); if (views.get(state.host) !== state || !state.host.querySelector('[data-image-provider]')) return; state.data = data;
      state.host.querySelector('[data-image-provider]').textContent = 'OpenAI Images API / ' + data.model + ' / ' + data.state.replaceAll('_', ' ') + '. ' + (data.authorised === true ? 'Successful request evidence exists for this configuration.' : 'API authorisation and billing access have not been verified.');
      state.host.querySelector('[data-image-generate]').disabled = !data.ready_to_request || state.sending;
      state.host.querySelector('[data-image-pause]').textContent = data.paused ? 'Resume shared queue' : 'Pause shared queue';
      state.host.querySelector('[data-image-queue-state]').textContent = (data.paused ? 'Shared queue paused.' : 'Shared queue enabled.') + ' One provider worker at a time across text and images. Cancellation cannot undo remote processing or charges already incurred.';
      var jobs = data.jobs || [];
      state.host.querySelector('[data-image-jobs]').innerHTML = jobs.length ? jobs.map(function (job) {
        var pending = ['queued', 'running', 'cancelling'].includes(job.status);
        return '<article class="u1-ai-job"><div class="u1-ai-job-heading"><strong>' + esc(job.title) + '</strong><span class="u1-ai-badge" data-state="' + esc(job.status) + '">' + esc(job.status) + '</span></div><p>' + esc(job.evidence) + '</p>' + (job.error ? '<p class="u1-ai-error">' + esc(job.error) + '</p>' : '') + '<p class="u1-ai-muted">Job ' + esc(job.id) + ' / separate API billing</p>' + (pending ? '<button type="button" data-image-cancel="' + esc(job.id) + '"' + (job.status === 'cancelling' ? ' disabled' : '') + '>Cancel this image request</button>' : '') + '</article>';
      }).join('') : '<p class="u1-ai-empty">No image requests have been submitted.</p>';
      var signature = JSON.stringify(data.images);
      if (state.imageSignature !== signature) {
        state.imageSignature = signature;
        state.host.querySelector('[data-image-gallery]').innerHTML = data.images.length ? data.images.map(function (image) {
          // Image URLs are constructed from validated local job IDs, never provider URLs.
          var url = '/api/workspace/image-provider?image_id=' + encodeURIComponent(image.job_id);
          return '<figure class="u1-image-result"><img src="' + url + '" alt="' + esc(image.title) + '" width="1024" height="1024" loading="lazy" referrerpolicy="same-origin"><figcaption><strong>' + esc(image.title) + '</strong><p>API-generated PNG / ' + image.width + ' x ' + image.height + ' / ' + Math.ceil(image.bytes / 1024) + ' KB</p><a href="' + url + '" download="u1-image-' + esc(image.job_id) + '.png">Download original PNG</a></figcaption></figure>';
        }).join('') : '<p class="u1-ai-empty">Completed, validated PNGs appear here. No sample or simulated images are shown.</p>';
      }
    } catch (error) { message(state, error.message, true); }
    finally { state.refreshing = false; }
  }
  function mount(host) {
    var old = views.get(host); if (old) clearInterval(old.timer);
    var state = { host: host, data: null, sending: false, imageSignature: null }; views.set(host, state);
    host.classList.add('u1-native-workspace', 'u1-ai-workspace', 'u1-images-workspace');
    host.innerHTML = '<header class="u1-core-header"><div><span class="u1-core-eyebrow">U1 WORKSPACE / IMAGES</span><h2>Images</h2><p>Create one image from a reviewed prompt using the OpenAI Images API.</p></div><button type="button" data-image-refresh>Refresh evidence</button></header><div class="u1-core-source" data-image-provider>Checking local image-provider setup...</div><p data-image-status class="u1-ai-status" role="status" aria-live="polite"></p><div class="u1-image-columns"><section><details class="u1-image-setup"><summary>Separate API key and billing setup</summary><p>A ChatGPT/Codex sign-in does not cover Images API billing. Configure an OpenAI API key with Images access and review billing in your OpenAI API account. Saving a key does not test account access or generate an image.</p><form data-image-credentials><label>OpenAI Images API key<input name="api_key" type="password" autocomplete="off" spellcheck="false" maxlength="4096" required></label><label class="u1-ai-confirm"><input name="confirmed" type="checkbox" required><span>Store this key in this Mac\'s native Keychain for U1 Images. No plaintext fallback.</span></label><div class="u1-ai-actions"><button type="submit">Save to Keychain</button><button type="button" data-image-disconnect>Remove image credential</button></div></form><p class="u1-ai-muted">First setup builds a separate native helper and requires Apple command line tools. Keychain may request access. Existing Google credentials remain separate.</p></details><form data-image-form class="u1-ai-composer"><label>Image prompt<textarea name="prompt" rows="7" maxlength="8000" required placeholder="Describe the image you want to create."></textarea></label><div class="u1-image-spec"><span>gpt-image-1.5</span><span>1 image</span><span>1024 x 1024</span><span>Low quality / PNG</span></div><label class="u1-ai-confirm"><input name="billing" type="checkbox" required><span>I reviewed this prompt and confirm one separately billed OpenAI Images API request. This uses API billing, not my ChatGPT/Codex subscription allowance. Exact cost is not calculated here.</span></label><button type="submit" data-image-generate class="u1-core-primary" disabled>Confirm API billing and generate</button><p class="u1-ai-muted">The prompt is sent to api.openai.com. Generated PNGs are stored locally, up to 20 images. No repository, note or email content is attached automatically.</p></form></section><aside class="u1-ai-queue"><h3>Image request evidence</h3><p data-image-queue-state class="u1-ai-muted"></p><button type="button" data-image-pause>Pause shared queue</button><div data-image-jobs></div></aside></div><section class="u1-image-gallery" data-image-gallery aria-label="Generated images"></section>';
    var credentialsForm = host.querySelector('[data-image-credentials]');
    credentialsForm.onsubmit = async function (event) {
      event.preventDefault(); var button = credentialsForm.querySelector('[type=submit]'); button.disabled = true;
      message(state, 'Saving the image credential to native Keychain. First setup may need compiler and Keychain permission. No image API request is being made.');
      try { await api({ action: 'configure', api_key: credentialsForm.elements.api_key.value, confirmed: credentialsForm.elements.confirmed.checked }, 150000); credentialsForm.reset(); message(state, 'Image key saved to Keychain. API access remains unverified until a confirmed image request succeeds.'); await refresh(state); }
      catch (error) { message(state, error.message, true); }
      finally { credentialsForm.elements.api_key.value = ''; button.disabled = false; }
    };
    var form = host.querySelector('[data-image-form]');
    form.addEventListener('input', function (event) { if (event.target.name !== 'billing') form.elements.billing.checked = false; });
    form.onsubmit = async function (event) {
      event.preventDefault(); if (state.sending || window.U1Assistant.isLocked()) return;
      var prompt = form.elements.prompt.value.trim();
      if (!prompt || new TextEncoder().encode(prompt).length > 8000 || !form.elements.billing.checked) { message(state, 'Review a prompt of at most 8,000 UTF-8 bytes and confirm separate API billing.', true); return; }
      if (!state.pending || state.pending.prompt !== prompt) state.pending = { prompt: prompt, request_id: crypto.randomUUID() };
      state.sending = true; host.querySelector('[data-image-generate]').disabled = true;
      try {
        var result = await api({ action: 'generate', prompt: prompt, request_id: state.pending.request_id, confirmed_api_billing: true });
        state.pending = null; form.reset(); message(state, result.duplicate ? 'This request was already accepted. No duplicate image job was created.' : 'Image request queued with separate API billing confirmation. Actual status appears alongside.');
      } catch (error) { message(state, error.message + ' If acceptance is uncertain, retry the unchanged prompt to reuse its request identifier.', true); }
      finally { state.sending = false; await refresh(state); }
    };
    host.addEventListener('click', async function (event) {
      if (views.get(host) !== state) return;
      var button = event.target.closest('button'); if (!button) return;
      try {
        if (button.hasAttribute('data-image-refresh')) await refresh(state);
        if (button.dataset.imageCancel) { await window.U1Assistant.request('/api/workspace/jobs', { action: 'cancel', job_id: button.dataset.imageCancel }); await refresh(state); }
        if (button.hasAttribute('data-image-pause') && state.data) { await window.U1Assistant.request('/api/workspace/jobs', { action: 'pause', paused: !state.data.paused }); await refresh(state); }
        if (button.hasAttribute('data-image-disconnect') && window.confirm('Remove only the U1 Images API credential from Keychain? Cancel or finish image requests first.')) { await api({ action: 'disconnect', confirmed: true }, 45000); message(state, 'Image credential removal confirmed. Generated local images remain available.'); await refresh(state); }
      } catch (error) { message(state, error.message, true); }
    });
    state.timer = setInterval(function () { if (!host.isConnected || !host.querySelector('[data-image-provider]')) { clearInterval(state.timer); views.delete(host); return; } if (!document.hidden && host.getClientRects().length) refresh(state); }, 3000);
    refresh(state);
  }
  function init() {
    if (!window.U1Assistant || !window.U1CoreViews) return;
    ['images', 'image-generation'].forEach(function (id) { window.U1CoreViews.register(id, mount); });
    document.addEventListener('u1:safety-change', function (event) { if (event.detail && event.detail.locked) { clearImages(); views.forEach(function (state) { state.imageSignature = null; clearCredentials(state); }); } else views.forEach(refresh); });
    new MutationObserver(function () { if (document.documentElement.dataset.u1Safety === 'locked') { clearImages(); views.forEach(function (state) { state.imageSignature = null; clearCredentials(state); }); } }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-u1-safety'] });
    window.addEventListener('pagehide', function () { views.forEach(function (state) { clearInterval(state.timer); clearCredentials(state); }); clearImages(); });
  }
  window.U1ImageProvider = Object.freeze({ mount: mount });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true }); else init();
})();
