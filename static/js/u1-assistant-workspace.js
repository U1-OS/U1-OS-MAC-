(function () {
  'use strict';
  var instances = new Map(), csrf = '', speech = null, speechTimer = null, voiceEpoch = 0;
  var controllers = new Set(), lastConversation = '', safetyLocked = false;
  var roleDescriptions = {
    Creator: 'Ideas, outlines and writing drafts.', Research: 'Analysis of selected sources. No live browsing.',
    Admin: 'Checklists and correspondence drafts.', Business: 'Proposals and analysis with stated assumptions.',
    Design: 'Visual directions and design briefs as text.'
  };
  function esc(value) { return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function size(text) { return new TextEncoder().encode(text).length; }
  function locked() { return safetyLocked || document.documentElement.dataset.u1Safety === 'locked' || !!(window.U1Safety && window.U1Safety.isLocked()); }
  function status(state, text, error) { var el = state.host.querySelector('[data-ai-status]'); if (el) { el.textContent = text; el.setAttribute('role', error ? 'alert' : 'status'); } }
  function when(value) { return value ? new Date(value * 1000).toLocaleString() : 'Not started'; }
  async function request(path, body, timeoutMs, validate) {
    if (locked()) throw Error('Safety is locked. Unlock the workspace before continuing.');
    if (validate && !validate()) throw Error('The reviewed conversation changed. Reload its history and confirm again.');
    var controller = new AbortController(); controllers.add(controller);
    var timeout = setTimeout(function () { controller.abort(); }, timeoutMs || 12000);
    try {
      var response = await fetch(path, { method: body ? 'POST' : 'GET', credentials: 'same-origin',
        cache: 'no-store', redirect: 'error', signal: controller.signal,
        headers: body ? { 'Content-Type': 'application/json', 'X-U1-CSRF': csrf } : {},
        body: body ? JSON.stringify(body) : undefined });
      var result = await response.json();
      if (!response.ok || result.success !== true) throw Error(result.error || 'The assistant service is unavailable.');
      if (locked()) throw Error('Safety is locked. Request status will be available after unlock.');
      return result;
    } finally { clearTimeout(timeout); controllers.delete(controller); }
  }
  async function api(path, body, timeoutMs, validate) {
    if (body && !csrf) { var registry = await request('/api/integrations'); csrf = registry.csrf_token || ''; if (!csrf) throw Error('Reload the workspace to obtain its action token.'); }
    return request(path, body, timeoutMs, validate);
  }
  function clearConsent(state) { var field = state.host.querySelector('[name=allowance]'); if (field) field.checked = false; }
  function reviewCurrent(state) { return !!(state.active && state.review && state.review.conversation === state.conversation && state.review.generation === state.generation && state.review.signature === state.transcriptSignature); }
  function composerReady(state) {
    var ready = reviewCurrent(state) && !state.refreshing && !state.sending && !locked();
    var button = state.host.querySelector('form [type=submit]'), field = state.host.querySelector('[name=allowance]');
    if (button) button.disabled = !ready;
    if (field) field.disabled = !ready;
  }
  function invalidateReview(state) {
    state.generation += 1; state.review = null; clearConsent(state); composerReady(state);
  }
  function selectConversation(state, identifier) {
    state.conversation = lastConversation = identifier || ''; state.pendingSend = null;
    invalidateReview(state); state.transcriptSignature = null; state.messages = [];
    var node = state.host.querySelector('[data-ai-transcript]');
    if (node) node.textContent = state.conversation ? 'Loading the selected conversation for review. Sending is disabled until it is current.' : 'New conversation selected. Confirm after its local status finishes loading.';
  }
  function stopVoice(discard) {
    voiceEpoch += 1;
    clearTimeout(speechTimer);
    if (speech) { speech.onresult = null; speech.onerror = null; speech.onend = null; try { speech.abort(); } catch (ignore) {} speech = null; }
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    instances.forEach(function (s) {
      var button = s.host.querySelector('[data-ai-mic]'); if (button) button.textContent = 'Record a voice draft';
      if (discard) { var transcript = s.host.querySelector('[name=voice]'); if (transcript) transcript.value = ''; }
    });
  }
  function contain() {
    stopVoice(true); controllers.forEach(function (controller) { controller.abort(); }); csrf = '';
    instances.forEach(function (s) { invalidateReview(s); status(s, 'Safety stopped browser activity. The server Safety integration controls queued and running jobs.', true); });
  }
  function voiceDraft(state) {
    if (speech) { stopVoice(false); return; }
    if (locked()) return;
    var Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (!Recognition) { status(state, 'Speech recognition is unavailable in this browser. Type your draft instead.', true); return; }
    if (!window.confirm('Your browser may process voice remotely through its speech service. Record one draft, review the transcript, then choose whether to use it. Recording never sends a Codex request.')) return;
    stopVoice(false);
    var epoch = voiceEpoch, transcript = state.host.querySelector('[name=voice]');
    transcript.value = '';
    speech = new Recognition(); speech.continuous = false; speech.interimResults = true; speech.maxAlternatives = 1;
    speech.lang = document.documentElement.lang || navigator.language || 'en-AU';
    speech.onresult = function (event) {
      if (epoch !== voiceEpoch || locked()) return;
      var text = '';
      for (var i = 0; i < event.results.length; i++) text += event.results[i][0].transcript + ' ';
      transcript.value = text.trim().slice(0, 8000);
      status(state, 'Review and edit the voice transcript. It has not been sent.');
    };
    speech.onerror = function () { if (epoch === voiceEpoch) { stopVoice(false); status(state, 'Voice recording stopped or was unavailable. Your draft has not been sent.', true); } };
    speech.onend = function () { if (epoch === voiceEpoch) { speech = null; clearTimeout(speechTimer); var button = state.host.querySelector('[data-ai-mic]'); if (button) button.textContent = 'Record a voice draft'; } };
    try { speech.start(); state.host.querySelector('[data-ai-mic]').textContent = 'Stop recording'; speechTimer = setTimeout(function () { stopVoice(false); }, 45000); }
    catch (ignore) { stopVoice(false); status(state, 'The browser could not start voice recording.', true); }
  }
  function contextView(state) {
    var node = state.host.querySelector('[data-ai-context]'); if (!node) return;
    node.innerHTML = state.context.length ? state.context.map(function (item, i) {
      return '<details class="u1-ai-context-item"><summary>' + esc(item.label) + ' / ' + size(item.text) + ' bytes</summary><pre>' + esc(item.text) + '</pre><button type="button" data-ai-remove="' + i + '">Remove selected context</button></details>';
    }).join('') : '<p class="u1-ai-muted">No context selected. Only your prompt and the displayed conversation history will be sent.</p>';
    var confirm = state.host.querySelector('[name=allowance]'); if (confirm) confirm.checked = false;
  }
  function addContext(state, label, text) {
    if (!text.trim()) throw Error('Selected context is empty.');
    if (state.context.length >= 8 || size(text) + state.context.reduce(function (n, c) { return n + size(c.text); }, 0) > 16000) throw Error('Select at most eight context items with a combined limit of 16,000 UTF-8 bytes.');
    state.context.push({ label: label.slice(0, 90), text: text }); contextView(state);
  }
  async function chooseNotes(state) {
    status(state, 'Loading local notes for your selection. No note has been sent to Codex.');
    var data = await api('/api/workspace/prism/summary'), rows = data.records || [];
    if (!Array.isArray(rows)) rows = Object.values(rows).flat();
    state.notes = rows.filter(function (r) { return r && r.kind === 'note' && !r.deleted; }).slice(0, 100);
    var node = state.host.querySelector('[data-ai-notes]');
    node.innerHTML = state.notes.length ? state.notes.map(function (note, index) {
      return '<details><summary>' + esc(note.title) + '</summary><pre>' + esc((note.payload || {}).text || '') + '</pre><button type="button" data-ai-note="' + index + '">Select this note</button></details>';
    }).join('') : '<p>No local notes are available.</p>';
    status(state, 'Choose the notes to include. Review selected context before confirming a send.');
  }
  function renderEvidence(state, data) {
    state.data = data;
    var provider = data.provider || {}, node = state.host.querySelector('[data-ai-provider]');
    node.textContent = (provider.installed ? 'Codex installed' : 'Codex not installed') + ' / ' + (provider.authorised === true ? 'Sign-in evidenced by a successful request at ' + when(provider.authorised_at) : 'Authorisation unverified') + '. Image generation uses separate API setup in Images.';
    var pause = state.host.querySelector('[data-ai-pause]'); pause.textContent = data.paused ? 'Resume queue' : 'Pause queue';
    state.host.querySelector('[data-ai-queue-state]').textContent = (data.paused ? 'Queue paused.' : 'Queue enabled.') + ' One owned provider worker at a time, shared by text and images. Pausing leaves a running request active; cancel to stop it.' + (data.storage_fault ? ' Local persistence failed; dispatch is disabled.' : '');
    var jobs = data.jobs || [], jobsNode = state.host.querySelector('[data-ai-jobs]');
    jobsNode.innerHTML = jobs.length ? jobs.map(function (job) {
      var active = ['queued', 'running', 'cancelling'].includes(job.status);
      var elapsed = job.started_at ? Math.max(0, Math.floor((job.finished_at || Date.now() / 1000) - job.started_at)) + 's elapsed' : 'Provider not started';
      return '<article class="u1-ai-job"><div class="u1-ai-job-heading"><strong>' + esc(job.title) + '</strong><span class="u1-ai-badge" data-state="' + esc(job.status) + '">' + esc(job.status) + '</span></div><p>' + esc(job.role) + ' / ' + esc(elapsed) + '</p><p>' + esc(job.evidence) + '</p>' + (job.error ? '<p class="u1-ai-error">' + esc(job.error) + '</p>' : '') + '<details><summary>Request evidence</summary><dl><dt>Request</dt><dd>' + esc(job.request_id) + '</dd><dt>Job</dt><dd>' + esc(job.id) + '</dd><dt>Confirmed</dt><dd>' + esc(when(job.confirmed_at)) + '</dd><dt>Process started</dt><dd>' + esc(when(job.started_at)) + '</dd><dt>Finished</dt><dd>' + esc(job.finished_at ? when(job.finished_at) : 'Not finished') + '</dd><dt>Response size</dt><dd>' + Number(job.output_bytes || 0) + ' bytes</dd></dl></details><div class="u1-ai-actions"><button type="button" data-ai-review="' + esc(job.conversation_id) + '">Review conversation</button>' + (active ? '<button type="button" data-ai-cancel="' + esc(job.id) + '"' + (job.status === 'cancelling' ? ' disabled' : '') + '>Cancel request</button>' : '') + '</div></article>';
    }).join('') : '<div class="u1-ai-empty">No assistant requests have been submitted. Confirm a prompt in AI Command to create a real job.</div>';
    var roles = state.host.querySelector('[data-ai-roles]');
    if (roles) roles.innerHTML = Object.keys(roleDescriptions).map(function (role) {
      var matching = jobs.filter(function (j) { return j.role === role; }), current = matching.filter(function (j) { return ['queued', 'running', 'cancelling'].includes(j.status); });
      return '<article class="u1-ai-role"><h3>' + role + '</h3><p>' + roleDescriptions[role] + '</p><strong>' + matching.length + ' recorded requests / ' + current.length + ' active</strong><p>' + (matching.length ? 'Latest recorded state: ' + esc(matching[0].status) : 'No request evidence yet.') + '</p></article>';
    }).join('');
    var select = state.host.querySelector('[name=conversation]');
    if (select) { select.innerHTML = '<option value="">New conversation</option>' + (data.conversations || []).map(function (c) { return '<option value="' + esc(c.id) + '">' + esc(c.title) + ' (' + c.message_count + ' messages)</option>'; }).join(''); select.value = state.conversation; }
    if (data.conversation) transcriptView(state, data.conversation);
  }
  function transcriptView(state, conversation) {
    var node = state.host.querySelector('[data-ai-transcript]'), signature = JSON.stringify(conversation);
    if (signature === state.transcriptSignature) return;
    state.transcriptSignature = signature;
    node.innerHTML = conversation ? '<h3>Conversation history</h3><p class="u1-ai-muted">Up to 24,000 bytes of completed prior turns may accompany your next send. Context selections from earlier turns are not automatically attached again.</p>' + conversation.messages.map(function (message, index) {
      return '<article class="u1-ai-message" data-speaker="' + esc(message.role) + '"><div class="u1-ai-message-heading"><strong>' + (message.role === 'user' ? 'You' : esc(message.assistant_role || 'Assistant')) + '</strong><time>' + esc(when(message.created_at)) + '</time></div><pre>' + esc(message.text) + '</pre>' + (message.context && message.context.length ? '<details><summary>Context selected for this request</summary>' + message.context.map(function (c) { return '<h4>' + esc(c.label) + '</h4><pre>' + esc(c.text) + '</pre>'; }).join('') + '</details>' : '') + (message.role === 'assistant' && window.speechSynthesis ? '<button type="button" data-ai-speak="' + index + '">Read this response aloud</button>' : '') + '</article>';
    }).join('') : '<p class="u1-ai-muted">A new conversation starts with no history.</p>';
    state.messages = conversation ? conversation.messages : [];
  }
  async function refresh(state) {
    if (!state.active || state.sending || !state.host.isConnected || !state.host.querySelector('[data-ai-provider]') || locked()) return;
    if (state.refreshing && state.refreshing.generation === state.generation && state.refreshing.conversation === state.conversation) return;
    var selected = state.conversation, generation = state.generation;
    var pending = { conversation: selected, generation: generation, serial: ++state.refreshSerial };
    state.refreshing = pending; composerReady(state);
    function current() { return state.active && !locked() && instances.get(state.host) === state && state.host.querySelector('[data-ai-provider]') && state.generation === generation && state.conversation === selected && state.refreshSerial === pending.serial; }
    try {
      var path = selected ? '/api/workspace/assistant?conversation_id=' + encodeURIComponent(selected) : '/api/workspace/' + (state.view === 'jobs' ? 'jobs' : 'assistant');
      var data = await api(path);
      if (!current()) return;
      if (selected && (!data.conversation || data.conversation.id !== selected)) throw Error('Conversation identity did not match. Refresh and review before sending.');
      var signature = JSON.stringify(data.conversation || null);
      if (!state.review || state.review.signature !== signature) clearConsent(state);
      renderEvidence(state, data);
      if (!selected) transcriptView(state, null);
      state.review = { conversation: selected, generation: generation, signature: signature };
    } catch (error) { if (current()) { state.review = null; clearConsent(state); status(state, error.message, true); } }
    finally {
      if (state.refreshing === pending) state.refreshing = null;
      composerReady(state);
      if (state.active && !locked() && state.generation !== generation && !state.refreshing && !reviewCurrent(state)) refresh(state);
    }
  }
  async function send(state, form) {
    if (state.sending || locked() || !state.active) return;
    if (state.refreshing || !reviewCurrent(state)) { clearConsent(state); status(state, 'Wait for the selected conversation to finish loading, review its current history, then confirm again.', true); return; }
    var prompt = form.elements.prompt.value.trim(), role = form.elements.role.value;
    if (!prompt || size(prompt) > 8000) { status(state, 'Enter a prompt of at most 8,000 UTF-8 bytes.', true); return; }
    if (!form.elements.allowance.checked) { status(state, 'Review the prompt, selected context and conversation history, then confirm allowance use.', true); return; }
    stopVoice(false);
    var payload = { action: 'send', role: role, prompt: prompt, context: state.context.map(function (item) { return { label: item.label, text: item.text }; }),
      confirmed: true, conversation_id: state.conversation || undefined };
    var reviewed = state.review, generation = state.generation;
    function stillReviewed() { return state.active && !locked() && state.generation === generation && state.review === reviewed && reviewCurrent(state) && !state.refreshing && form.elements.allowance.checked && form.elements.prompt.value.trim() === prompt && form.elements.role.value === role && JSON.stringify(state.context) === JSON.stringify(payload.context); }
    var signature = JSON.stringify(payload);
    if (!state.pendingSend || state.pendingSend.signature !== signature) state.pendingSend = { signature: signature, request_id: crypto.randomUUID() };
    payload.request_id = state.pendingSend.request_id;
    state.sending = true; form.querySelector('[type=submit]').disabled = true;
    try {
      var result = await api('/api/workspace/assistant', payload, undefined, stillReviewed);
      if (!state.active || locked() || state.generation !== generation) return;
      selectConversation(state, result.conversation_id);
      form.elements.prompt.value = ''; form.elements.allowance.checked = false;
      state.context = []; state.pendingSend = null; contextView(state);
      status(state, result.duplicate ? 'This request was already accepted. No duplicate request was created.' : 'Confirmed request queued. Its actual state is shown in Jobs.');
      state.sending = false;
      await refresh(state);
    } catch (error) { if (state.active && state.generation === generation) status(state, error.message + ' If acceptance is uncertain, retry the unchanged draft; its request identifier prevents duplicate sends while retained.', true); }
    finally { state.sending = false; composerReady(state); }
  }
  function composer() {
    return '<form class="u1-ai-composer"><div class="u1-ai-form-row"><label>Conversation<select name="conversation"><option value="">New conversation</option></select></label><label>Text assistant role<select name="role">' + Object.keys(roleDescriptions).map(function (r) { return '<option>' + r + '</option>'; }).join('') + '</select></label></div><label>Your prompt<textarea name="prompt" rows="6" maxlength="8000" required placeholder="What would you like help thinking through?"></textarea></label><fieldset><legend>Choose context to send</legend><p class="u1-ai-muted">Only selected text is attached. Repository files and email are not automatically imported.</p><div class="u1-ai-actions"><button type="button" data-ai-choose-notes>Choose local notes</button><label class="u1-ai-file">Choose a text file<input type="file" data-ai-file accept=".txt,.md,.csv,.json,.log,text/plain,text/markdown,text/csv,application/json"></label></div><div data-ai-notes class="u1-ai-note-picker"></div><label>Paste additional context<textarea name="contextDraft" rows="3" maxlength="16000"></textarea></label><button type="button" data-ai-add-context>Select pasted context</button><div data-ai-context></div></fieldset><details class="u1-ai-voice"><summary>Voice draft and read-aloud</summary><p>Your browser may process voice remotely. Recording is explicit and stops after one utterance or 45 seconds. Review the transcript before using it. Nothing is sent automatically.</p><button type="button" data-ai-mic>Record a voice draft</button><label>Review and edit voice transcript<textarea name="voice" rows="3" maxlength="8000"></textarea></label><div class="u1-ai-actions"><button type="button" data-ai-use-voice>Use reviewed transcript in prompt</button><button type="button" data-ai-stop-voice>Stop voice and read-aloud</button></div></details><label class="u1-ai-confirm"><input type="checkbox" name="allowance" required><span>I reviewed the prompt, selected context and displayed conversation history. Send this request using my signed-in Codex subscription allowance.</span></label><p class="u1-ai-muted">Responses are text for your review. Generated commands are never executed. Exact allowance consumption is unavailable.</p><div class="u1-ai-actions"><button type="submit" class="u1-core-primary">Confirm and send</button><button type="button" data-ai-new>New conversation</button><button type="button" data-ai-delete>Delete local conversation</button></div></form>';
  }
  function mount(host, view) {
    if (!host) return;
    var old = instances.get(host); if (old) clearInterval(old.timer);
    if (old && old.view === (view || 'ai') && host.querySelector('[data-ai-provider]')) { activate(host); return; }
    if (old) old.active = false;
    var state = { host: host, view: view || 'ai', conversation: lastConversation, context: [], notes: [], messages: [], data: null, active: true, generation: 0, refreshSerial: 0, review: null, refreshing: null };
    instances.set(host, state); host.classList.add('u1-native-workspace', 'u1-ai-workspace');
    var title = state.view === 'jobs' ? 'Managed Jobs' : state.view === 'war-room' ? 'War Room' : 'AI Command';
    host.innerHTML = '<header class="u1-core-header"><div><span class="u1-core-eyebrow">U1 WORKSPACE / NATIVE ASSISTANT</span><h2>' + title + '</h2><p>' + (state.view === 'war-room' ? 'Five text roles. Evidence from your actual requests.' : state.view === 'jobs' ? 'Confirmed requests, real process states and direct controls.' : 'Think, draft and plan with your existing Codex sign-in.') + '</p></div><button type="button" data-ai-refresh>Refresh evidence</button></header><div class="u1-core-source" data-ai-provider>Checking installed provider status...</div><p data-ai-status class="u1-ai-status" role="status" aria-live="polite"></p>' + (state.view === 'war-room' ? '<section class="u1-ai-roles" data-ai-roles aria-label="Text assistant roles"></section>' : '') + '<div class="u1-ai-layout' + (state.view === 'jobs' ? ' u1-ai-jobs-only' : '') + '"><section class="u1-ai-main">' + (state.view !== 'jobs' ? composer() : '') + '<div data-ai-transcript aria-label="Reviewed conversation"></div></section><aside class="u1-ai-queue"><h3>Request queue</h3><p data-ai-queue-state class="u1-ai-muted"></p><div class="u1-ai-actions"><button type="button" data-ai-pause>Pause queue</button><button type="button" data-ai-cancel-all>Cancel all requests</button></div><div data-ai-jobs></div></aside></div>';
    contextView(state); transcriptView(state, null);
    host.onclick = async function (event) {
      var button = event.target.closest('button'); if (!button || state.sending) return;
      try {
        if (button.hasAttribute('data-ai-refresh')) await refresh(state);
        if (button.hasAttribute('data-ai-choose-notes')) await chooseNotes(state);
        if (button.dataset.aiNote != null) { var note = state.notes[Number(button.dataset.aiNote)]; addContext(state, note.title || 'Selected note', (note.payload || {}).text || ''); }
        if (button.dataset.aiRemove != null) { state.context.splice(Number(button.dataset.aiRemove), 1); contextView(state); }
        if (button.hasAttribute('data-ai-add-context')) { var draft = host.querySelector('[name=contextDraft]'); addContext(state, 'Selected pasted text', draft.value); draft.value = ''; }
        if (button.hasAttribute('data-ai-mic')) voiceDraft(state);
        if (button.hasAttribute('data-ai-stop-voice')) stopVoice(false);
        if (button.hasAttribute('data-ai-use-voice')) { stopVoice(false); var text = host.querySelector('[name=voice]').value.trim(), prompt = host.querySelector('[name=prompt]'); if (size(prompt.value + '\n' + text) > 8000) throw Error('The combined prompt exceeds 8,000 bytes.'); prompt.value = (prompt.value + '\n' + text).trim(); host.querySelector('[name=allowance]').checked = false; status(state, 'Transcript added to the editable prompt. Review and confirm to send.'); }
        if (button.dataset.aiSpeak != null && !locked()) { stopVoice(false); var message = state.messages[Number(button.dataset.aiSpeak)]; if (message && message.role === 'assistant') { if (window.confirm('Read this response using your browser speech voice? Some voices may use a remote service.')) window.speechSynthesis.speak(new SpeechSynthesisUtterance(message.text)); } }
        if (button.dataset.aiReview) { selectConversation(state, button.dataset.aiReview); await refresh(state); }
        if (button.hasAttribute('data-ai-new')) { selectConversation(state, ''); state.context = []; contextView(state); await refresh(state); }
        if (button.hasAttribute('data-ai-delete') && state.conversation && window.confirm('Delete this local conversation? Its bounded job evidence remains until history retention removes it.')) { await api('/api/workspace/assistant', { action: 'delete_conversation', conversation_id: state.conversation, confirmed: true }); selectConversation(state, ''); await refresh(state); }
        if (button.hasAttribute('data-ai-pause') && state.data) { await api('/api/workspace/jobs', { action: 'pause', paused: !state.data.paused }); await refresh(state); }
        if (button.dataset.aiCancel) { await api('/api/workspace/jobs', { action: 'cancel', job_id: button.dataset.aiCancel }); await refresh(state); }
        if (button.hasAttribute('data-ai-cancel-all') && window.confirm('Cancel every queued assistant request and stop its owned running Codex process? Work already performed may still consume allowance.')) { await api('/api/workspace/jobs', { action: 'cancel_all' }); await refresh(state); }
      } catch (error) { status(state, error.message, true); }
    };
    host.onchange = async function (event) {
      try {
        if (event.target.name === 'conversation') { if (state.sending) { event.target.value = state.conversation; return; } selectConversation(state, event.target.value); await refresh(state); }
        if (event.target.hasAttribute('data-ai-file')) { var file = event.target.files[0]; if (file) { if (file.size > 16000) throw Error('Choose a text file no larger than 16,000 bytes.'); var text = await file.text(); if (text.includes('\u0000')) throw Error('Choose a text file.'); addContext(state, file.name, text); } event.target.value = ''; }
      } catch (error) { status(state, error.message, true); }
    };
    var form = host.querySelector('form'); if (form) { form.onsubmit = function (event) { event.preventDefault(); send(state, form); }; form.addEventListener('input', function (event) { if (event.target.name !== 'allowance') form.elements.allowance.checked = false; }); }
    armTimer(state);
    refresh(state);
  }
  function armTimer(state) {
    clearInterval(state.timer);
    state.timer = setInterval(function () { if (!state.active || !state.host.isConnected || !state.host.querySelector('[data-ai-provider]')) { clearInterval(state.timer); return; } if (!document.hidden && state.host.getClientRects().length) refresh(state); }, 2500);
  }
  function deactivate(host) {
    var state = instances.get(host); if (!state) return;
    state.active = false; clearInterval(state.timer); invalidateReview(state); state.refreshSerial += 1; state.refreshing = null;
    stopVoice(locked());
  }
  function activate(host) {
    var state = instances.get(host); if (!state || !host.querySelector('[data-ai-provider]')) return;
    state.active = true; invalidateReview(state); armTimer(state); refresh(state);
  }
  function init() {
    if (window.U1CoreViews) {
      var lifecycle = { activate: activate, deactivate: deactivate };
      ['ai', 'assistant', 'ai-command'].forEach(function (id) { window.U1CoreViews.register(id, function (host) { mount(host, 'ai'); }, lifecycle); });
      window.U1CoreViews.register('jobs', function (host) { mount(host, 'jobs'); }, lifecycle);
      ['war-room', 'warroom'].forEach(function (id) { window.U1CoreViews.register(id, function (host) { mount(host, 'war-room'); }, lifecycle); });
    }
    document.addEventListener('u1:safety-change', function (event) { safetyLocked = !!(event.detail && event.detail.locked); if (safetyLocked) contain(); else instances.forEach(refresh); });
    new MutationObserver(function () { if (document.documentElement.dataset.u1Safety === 'locked') contain(); }).observe(document.documentElement, { attributes: true, attributeFilter: ['data-u1-safety'] });
    document.addEventListener('visibilitychange', function () { if (document.hidden) stopVoice(false); });
    window.addEventListener('pagehide', function () { contain(); instances.forEach(function (s) { clearInterval(s.timer); }); });
  }
  window.U1Assistant = Object.freeze({ mount: mount, activate: activate, deactivate: deactivate, stop: contain, request: api, isLocked: locked });
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true }); else init();
})();
