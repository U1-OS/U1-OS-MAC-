/* Native views. Load after u1-core-workspaces.js; the parent owns shell routing. */
(function () {
  'use strict';
  var API = '/api/workspace/media-research', LIMIT = 25 * 1024 * 1024;
  var mediaRoot, researchRoot, player, mini, parking, mediaURL, trackURL;
  var selected = null, sourceId = null, cap = null, busy = false, currentCase = null, evidenceEdit = null;
  var extensions = /\.(mp4|m4v|mov|m4a|mp3|wav|flac|ogg|oga|ogv|webm|mkv|avi|aac)$/i;
  var registration = false;

  function esc(value) { return String(value == null ? '' : value).replace(/[&<>"']/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]; }); }
  function qs(root, selector) { return root.querySelector(selector); }
  function stamp(value) { var d = new Date(value); return Number.isFinite(d.getTime()) ? d.toLocaleString() : 'Not recorded'; }
  function megabytes(size) { return (size / 1024 / 1024).toFixed(2) + ' MB'; }
  function status(root, value, error) { var el = qs(root, '[data-mr-status]'); if (el) { el.textContent = value; el.dataset.error = String(!!error); } }

  async function request(path, body) {
    var headers = {}, controller = new AbortController(), timer = setTimeout(function () { controller.abort(); }, 30000);
    try {
      if (body) {
        var tokenResponse = await fetch('/api/integrations', { credentials: 'same-origin', cache: 'no-store', signal: controller.signal });
        if (!tokenResponse.ok) throw Error('The local authorisation service is unavailable.');
        var registry = await tokenResponse.json();
        if (!registry.csrf_token) throw Error('Reload the page to obtain local authorisation.');
        headers = { 'Content-Type': 'application/json', 'X-U1-CSRF': registry.csrf_token };
      }
      var response = await fetch(path, { method: body ? 'POST' : 'GET', headers: headers, credentials: 'same-origin',
        cache: 'no-store', body: body ? JSON.stringify(body) : undefined, signal: controller.signal });
      var result = await response.json();
      if (!response.ok || result.success === false) throw Error(result.error || 'The local operation did not complete.');
      return result;
    } catch (error) {
      if (error.name === 'AbortError') throw Error('The request timed out. Reload saved records before retrying a save.');
      throw error;
    } finally { clearTimeout(timer); }
  }

  function saveDownload(result) {
    var binary = atob(result.content), bytes = new Uint8Array(binary.length);
    for (var i = 0; i < binary.length; i++) bytes[i] = binary.charCodeAt(i);
    var url = URL.createObjectURL(new Blob([bytes], { type: result.mime })), a = document.createElement('a');
    a.href = url; a.download = result.filename; document.body.appendChild(a); a.click(); a.remove();
    setTimeout(function () { URL.revokeObjectURL(url); }, 60000);
  }

  async function perform(root, operation) {
    if (busy) { status(root, 'A local operation is already running.'); return; }
    busy = true;
    var controls = Array.from(root.querySelectorAll('button, input[type=file]')).map(function (el) { var previous = el.disabled; el.disabled = true; return [el, previous]; });
    root.setAttribute('aria-busy', 'true');
    try { await operation(); }
    catch (error) { status(root, error.message || 'The operation did not complete.', true); }
    finally {
      busy = false; root.removeAttribute('aria-busy');
      controls.forEach(function (pair) { pair[0].disabled = pair[1]; });
      if (mediaRoot) availability();
    }
  }

  function chrome(view, title, description) {
    return '<aside class="u1-mr-nav" aria-label="Media and research"><p class="u1-mr-eyebrow">CREATE / INVESTIGATE</p>' +
      '<button type="button" data-mr-route="media"' + (view === 'media' ? ' aria-current="page"' : '') + '>Media studio<span>Local audio and video</span></button>' +
      '<button type="button" data-mr-route="osint"' + (view === 'osint' ? ' aria-current="page"' : '') + '>Research casebook<span>Sources and evidence</span></button>' +
      '<p class="u1-mr-note">Your files. Your sources.<br>Saved on this Mac.</p></aside><div class="u1-mr-main"><header class="u1-mr-heading"><p class="u1-mr-eyebrow">U1 / ' + (view === 'media' ? 'MEDIA' : 'OSINT') + '</p><h1>' + title + '</h1><p>' + description + '</p></header>';
  }

  function bindRoutes(root) {
    root.querySelectorAll('[data-mr-route]').forEach(function (button) {
      button.addEventListener('click', function () {
        if (window.U1Platform && typeof window.U1Platform.open === 'function') window.U1Platform.open(button.dataset.mrRoute);
        else document.dispatchEvent(new CustomEvent('u1:open-view', { detail: { id: button.dataset.mrRoute } }));
      });
    });
  }

  function hasPlayerSource() {
    if (!player) return false;
    // An empty HTMLMediaElement.src getter can resolve to the document URL.
    // Inspect authored attributes/currentSrc instead, excluding the page itself.
    var source = player.querySelector('source[src]');
    return [player.getAttribute('src'), source && source.getAttribute('src'), player.currentSrc].some(function (value) {
      if (typeof value !== 'string' || !value.trim()) return false;
      try {
        var url = new URL(value.trim(), document.baseURI); url.hash = '';
        var base = new URL(document.baseURI); base.hash = '';
        var page = new URL(document.URL || document.baseURI); page.hash = '';
        return url.href !== base.href && url.href !== page.href;
      } catch (error) { return false; }
    });
  }

  function syncPlayerState() {
    if (!player || !mini) return;
    var ready = hasPlayerSource();
    player.hidden = !ready;
    player.controls = ready;
    mini.hidden = !ready;
    mini.dataset.mrHasSource = String(ready);
    mini.classList.toggle('u1-mr-player-parked', !mediaRoot || !mediaRoot.contains(mini));
    if (mediaRoot) {
      qs(mediaRoot, '[data-mr-player-slot]').dataset.mrReady = String(ready);
      qs(mediaRoot, '[data-mr-player-empty]').hidden = ready;
    }
  }

  function ensurePlayer() {
    if (player) return;
    player = document.getElementById('u1-local-media');
    mini = document.getElementById('u1-player-mini');
    if (!mini) { mini = document.createElement('div'); mini.id = 'u1-player-mini'; document.body.appendChild(mini); }
    if (!player) { player = document.createElement('video'); player.id = 'u1-local-media'; mini.appendChild(player); }
    if (!mini.contains(player)) mini.appendChild(player);
    parking = mini.parentNode || document.body;
    player.controls = true; player.playsInline = true; player.preload = 'metadata';
    player.addEventListener('loadedmetadata', updateMetadata);
    player.addEventListener('emptied', updateMetadata);
    player.addEventListener('loadstart', updateMetadata);
    player.addEventListener('error', function () {
      syncPlayerState();
      if (mediaRoot && hasPlayerSource()) status(mediaRoot, 'This browser could not play that file. Try MP4/H.264, MP3 or WAV, or import it for an FFmpeg export.', true);
    });
    player.addEventListener('timeupdate', function () {
      if (!mediaRoot || !qs(mediaRoot, '[name=preview_clip]').checked) return;
      var end = Number(qs(mediaRoot, '[name=clip_out]').value);
      if (Number.isFinite(end) && end > 0 && player.currentTime >= end && !player.paused) player.pause();
    });
    syncPlayerState();
  }

  function movePlayer(destination) {
    if (mini.parentNode === destination) return;
    var resume = hasPlayerSource() && !player.paused;
    destination.appendChild(mini);
    syncPlayerState();
    if (resume) player.play().catch(function () { if (mediaRoot) status(mediaRoot, 'Press Play to resume after changing views.'); });
  }

  function unmountMedia() {
    if (!player || !mini) return;
    movePlayer(parking && parking.isConnected ? parking : document.body);
    syncPlayerState();
  }

  function updateMetadata() {
    if (!mediaRoot || !player) return;
    syncPlayerState();
    if (!hasPlayerSource()) {
      qs(mediaRoot, '[data-mr-metadata]').textContent = 'No file loaded. Choose local audio or video below to start.';
      return;
    }
    var duration = Number.isFinite(player.duration) ? player.duration : null;
    var lines = [selected ? selected.name : 'Existing persistent player source', selected ? megabytes(selected.size) : '',
      duration === null ? 'Duration unavailable' : duration.toFixed(2) + ' seconds',
      player.videoWidth ? player.videoWidth + ' x ' + player.videoHeight : 'Audio / no video dimensions',
      'Metadata reported by this browser'];
    qs(mediaRoot, '[data-mr-metadata]').textContent = lines.filter(Boolean).join(' / ');
    if (duration !== null && !qs(mediaRoot, '[name=clip_out]').value) qs(mediaRoot, '[name=clip_out]').value = Math.min(120, duration).toFixed(3);
  }

  function availability() {
    if (!mediaRoot) return;
    qs(mediaRoot, '[data-mr-export]').disabled = busy || !sourceId || !cap || !cap.ffmpeg_available;
    qs(mediaRoot, '[data-mr-inspect]').disabled = busy || !sourceId || !cap || !cap.ffmpeg_available;
    qs(mediaRoot, '[data-mr-import]').disabled = busy || !selected || !!sourceId;
  }

  function loadFile(file, id) {
    if (!file || !extensions.test(file.name) || file.size <= 0 || file.size > LIMIT) throw Error('Choose a supported audio or video file between 1 byte and 25 MB. Playlists are not supported.');
    ensurePlayer(); player.pause();
    if (mediaURL) URL.revokeObjectURL(mediaURL);
    selected = file; sourceId = id || null; mediaURL = URL.createObjectURL(file);
    player.src = mediaURL; player.dataset.video = String(!/^audio\//.test(file.type));
    clearTrack(); mini.hidden = false;
    qs(mediaRoot, '[name=rights]').checked = false;
    qs(mediaRoot, '[name=clip_in]').value = '0'; qs(mediaRoot, '[name=clip_out]').value = '';
    qs(mediaRoot, '[name=captions]').value = '';
    var title = document.getElementById('u1-player-title'); if (title) title.textContent = file.name;
    qs(mediaRoot, '[data-mr-metadata]').textContent = file.name + ' / ' + megabytes(file.size) + ' / Reading browser metadata...';
    qs(mediaRoot, '[data-mr-source]').textContent = sourceId ? 'Managed source ready for export.' : 'Playing from this device. Import a managed copy to enable FFmpeg export.';
    qs(mediaRoot, '[data-mr-progress]').hidden = true;
    player.load(); availability();
    status(mediaRoot, 'Loaded locally. Press Play to begin.');
  }

  function clipValues() {
    var a = qs(mediaRoot, '[name=clip_in]').value, b = qs(mediaRoot, '[name=clip_out]').value;
    var start = Number(a), end = Number(b);
    if (a === '' || b === '' || !Number.isFinite(start) || !Number.isFinite(end) || start < 0 || end <= start || end > 86400 || end - start > 120) throw Error('Choose an increasing clip range of at most 120 seconds.');
    if (Number.isFinite(player.duration) && end > player.duration + 0.05) throw Error('The clip ends after this media file.');
    return { clip_in: start, clip_out: end };
  }

  function rights() {
    if (!qs(mediaRoot, '[name=rights]').checked) throw Error('Confirm your permission to use and export this material.');
    return true;
  }

  function clearTrack() {
    if (player) player.querySelectorAll('track[data-mr-caption]').forEach(function (node) { node.remove(); });
    if (trackURL) URL.revokeObjectURL(trackURL);
    trackURL = null;
  }

  async function captionResult(trim) {
    var payload = { action: 'srt_export', captions: qs(mediaRoot, '[name=captions]').value, rights_confirmed: rights(), trim_to_clip: trim };
    if (trim) Object.assign(payload, clipValues());
    return request(API, payload);
  }

  async function refreshMedia() {
    var result = await request(API); cap = result.capabilities;
    qs(mediaRoot, '[data-mr-capability]').textContent = cap.ffmpeg_notice + ' Up to 120 seconds per clip; processing is limited to 4 seconds for inspection and 12 seconds for rendering.';
    var library = qs(mediaRoot, '[data-mr-library]');
    library.innerHTML = '<option value="">Choose an imported file</option>' + result.media.map(function (file) { return '<option value="' + esc(file.id) + '">' + esc(file.name) + ' (' + megabytes(file.size) + ')</option>'; }).join('');
    if (sourceId) library.value = sourceId;
    availability();
  }

  async function importSelected() {
    rights();
    if (!selected) throw Error('Choose a local file first.');
    var file = selected, progress = qs(mediaRoot, '[data-mr-progress]');
    var start = await request('/api/workspace/prism/upload-start', { name: file.name, mime: file.type || 'application/octet-stream', size: file.size, folder: 'Media' });
    progress.hidden = false; progress.max = file.size; progress.value = 0;
    var finalChunk;
    for (var offset = 0; offset < file.size; offset += 32768) {
      var chunk = new Uint8Array(await file.slice(offset, offset + 32768).arrayBuffer()), binary = '';
      for (var i = 0; i < chunk.length; i++) binary += String.fromCharCode(chunk[i]);
      finalChunk = await request('/api/workspace/prism/upload-chunk', { id: start.id, offset: offset, content: btoa(binary) });
      progress.value = finalChunk.received;
      status(mediaRoot, 'Imported ' + megabytes(finalChunk.received) + ' of ' + megabytes(file.size) + '.');
    }
    if (!finalChunk || finalChunk.status !== 'ready' || finalChunk.received !== file.size) throw Error('The managed upload is not complete. Import the file again.');
    sourceId = start.id;
    qs(mediaRoot, '[data-mr-source]').textContent = 'Managed source ready for export.';
    await refreshMedia(); status(mediaRoot, 'Imported into the local Media folder. Your original is unchanged.');
  }

  function createMedia() {
    mediaRoot = document.createElement('section'); mediaRoot.className = 'u1-mr'; mediaRoot.dataset.mrView = 'media';
    mediaRoot.innerHTML = chrome('media', 'Make something from your media.', 'Play a local file, mark a moment, and export a clip with captions.') +
      '<div class="u1-mr-player-slot" data-mr-player-slot data-mr-ready="false"><div class="u1-mr-player-empty" data-mr-player-empty><span class="u1-mr-empty-mark" aria-hidden="true">PLAY</span><div><h2>A place for your next clip.</h2><p>Choose a local audio or video file below. Your player will appear here.</p></div></div></div><p class="u1-mr-metadata" data-mr-metadata>No file loaded. Choose local audio or video below to start.</p>' +
      '<div class="u1-mr-grid"><section class="u1-mr-card"><h2>01 / Your source</h2><label class="u1-mr-file">Choose local audio or video<input type="file" data-mr-file accept="audio/*,video/*,.mkv,.m4a,.flac"></label>' +
      '<p class="u1-mr-note">Maximum 25 MB. Browser codec support varies. Playback stays available as you move around U1.</p><p data-mr-source>Choose a file to start. Nothing is uploaded automatically.</p>' +
      '<label class="u1-mr-check"><input name="rights" type="checkbox">I own this material or have permission to use and export it.</label>' +
      '<button type="button" data-mr-import>Import to local workspace</button><progress data-mr-progress hidden aria-label="Bytes imported"></progress>' +
      '<div class="u1-mr-divider"></div><label>Previously imported media<select data-mr-library><option value="">Loading local library...</option></select></label><div class="u1-mr-actions"><button type="button" data-mr-load>Load selected</button><button type="button" data-mr-refresh>Refresh library</button></div></section>' +
      '<section class="u1-mr-card"><h2>02 / Choose your clip</h2><div class="u1-mr-row"><label>In (seconds)<input name="clip_in" type="number" min="0" max="86400" step="0.001" value="0"></label><label>Out (seconds)<input name="clip_out" type="number" min="0" max="86400" step="0.001"></label></div>' +
      '<div class="u1-mr-actions"><button type="button" data-mr-mark="clip_in">Set in to playhead</button><button type="button" data-mr-mark="clip_out">Set out to playhead</button><button type="button" data-mr-preview>Play clip</button></div>' +
      '<label class="u1-mr-check"><input type="checkbox" name="preview_clip" checked>Pause at the out point during preview</label><label>Export format<select name="export_format"><option value="mp4">MP4 video (H.264 + AAC)</option><option value="wav">WAV audio (PCM)</option></select></label>' +
      '<p class="u1-mr-note" data-mr-capability>Checking the installed media engine...</p><div class="u1-mr-actions"><button type="button" data-mr-inspect disabled>Inspect with FFmpeg</button><button class="u1-mr-primary" type="button" data-mr-export disabled>Export clip</button></div></section></div>' +
      '<section class="u1-mr-card"><h2>03 / Give it a voice</h2><p>Write or edit SRT captions against the original file timeline. Preview uses the player above. Clip exports use a separate SRT file.</p>' +
      '<label>SRT captions<textarea name="captions" rows="9" maxlength="48000" spellcheck="false" placeholder="1&#10;00:00:01,000 --> 00:00:03,500&#10;Your first caption"></textarea></label>' +
      '<p class="u1-mr-note">Plain text, consecutive cue numbers and non-overlapping times. No automatic transcription.</p><label class="u1-mr-check"><input type="checkbox" name="trim_captions" checked>Trim exported captions to the clip and start their timeline at zero</label>' +
      '<div class="u1-mr-actions"><button type="button" data-mr-caption-preview>Preview captions</button><button type="button" data-mr-srt>Export SRT</button></div></section>' +
      '<p class="u1-mr-status" data-mr-status role="status" aria-live="polite"></p><footer class="u1-mr-footer">Local files and authorised exports. Spotify and YouTube subscriptions are not connected. No remote media download, DRM removal or watermark removal.</footer></div>';
    bindRoutes(mediaRoot);
    qs(mediaRoot, '[data-mr-file]').addEventListener('change', function (event) { try { if (!busy && event.target.files[0]) loadFile(event.target.files[0]); } catch (e) { status(mediaRoot, e.message, true); } });
    mediaRoot.addEventListener('click', function (event) {
      var button = event.target.closest('button'); if (!button || button.hasAttribute('data-mr-route')) return;
      perform(mediaRoot, async function () {
        if (button.hasAttribute('data-mr-import')) return importSelected();
        if (button.hasAttribute('data-mr-refresh')) { await refreshMedia(); status(mediaRoot, 'Local library refreshed.'); }
        if (button.hasAttribute('data-mr-load')) {
          var id = qs(mediaRoot, '[data-mr-library]').value; if (!id) throw Error('Choose an imported file.');
          var result = await request('/api/workspace/prism/file?id=' + encodeURIComponent(id));
          var raw = atob(result.content), bytes = new Uint8Array(raw.length);
          for (var i = 0; i < raw.length; i++) bytes[i] = raw.charCodeAt(i);
          loadFile(new File([bytes], result.name, { type: result.mime }), id);
        }
        if (button.dataset.mrMark) { if (!player.getAttribute('src')) throw Error('Load a file first.'); qs(mediaRoot, '[name=' + button.dataset.mrMark + ']').value = player.currentTime.toFixed(3); }
        if (button.hasAttribute('data-mr-preview')) { var range = clipValues(); player.currentTime = range.clip_in; await player.play(); status(mediaRoot, 'Playing the selected clip range.'); }
        if (button.hasAttribute('data-mr-inspect')) {
          status(mediaRoot, 'Inspecting with the installed FFmpeg...');
          var info = await request(API, { action: 'inspect', source_id: sourceId });
          status(mediaRoot, 'FFmpeg: ' + info.duration_seconds.toFixed(2) + ' seconds / ' + (info.video ? 'video' : '') + (info.audio ? ' audio' : '') + '.');
        }
        if (button.hasAttribute('data-mr-export')) {
          var payload = Object.assign({ action: 'clip_export', source_id: sourceId, rights_confirmed: rights(), format: qs(mediaRoot, '[name=export_format]').value }, clipValues());
          status(mediaRoot, 'FFmpeg is rendering. Progress is not measured; the render stops after 12 seconds if unfinished.');
          saveDownload(await request(API, payload)); status(mediaRoot, 'FFmpeg completed the clip. Download requested; export SRT separately for captions.');
        }
        if (button.hasAttribute('data-mr-srt')) { saveDownload(await captionResult(qs(mediaRoot, '[name=trim_captions]').checked)); status(mediaRoot, 'SRT created. Download requested.'); }
        if (button.hasAttribute('data-mr-caption-preview')) {
          var captions = await captionResult(false), decoded = new TextDecoder().decode(Uint8Array.from(atob(captions.content), function (c) { return c.charCodeAt(0); }));
          var vtt = 'WEBVTT\n\n' + decoded.replace(/(\d{2}:\d{2}:\d{2}),(\d{3})/g, '$1.$2');
          clearTrack(); trackURL = URL.createObjectURL(new Blob([vtt], { type: 'text/vtt' }));
          var track = document.createElement('track'); track.dataset.mrCaption = 'true'; track.kind = 'captions'; track.label = 'Edited captions'; track.srclang = 'en'; track.src = trackURL; track.default = true;
          player.appendChild(track); track.track.mode = 'showing'; status(mediaRoot, 'Edited captions are enabled in the player.');
        }
      });
    });
  }

  async function mountMedia(host) {
    if (!mediaRoot) createMedia();
    ensurePlayer(); if (mediaRoot.parentNode !== host) host.replaceChildren(mediaRoot);
    movePlayer(qs(mediaRoot, '[data-mr-player-slot]')); syncPlayerState();
    if (!cap) { try { await refreshMedia(); } catch (e) { status(mediaRoot, e.message, true); } }
    updateMetadata();
  }

  function localTime(value) {
    var d = value ? new Date(value) : new Date();
    return new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
  }

  function caseEditor() {
    var c = currentCase || {}, target = qs(researchRoot, '[data-mr-case-editor]');
    target.innerHTML = '<form data-mr-case-form class="u1-mr-card"><h2>' + (c.id ? 'Case details' : 'Start a case') + '</h2><label>Case title<input name="title" required maxlength="160" value="' + esc(c.title) + '"></label>' +
      '<label>Research scope<select name="scope"><option value="public"' + (c.scope !== 'authorised' ? ' selected' : '') + '>Public information</option><option value="authorised"' + (c.scope === 'authorised' ? ' selected' : '') + '>Information I am authorised to use</option></select></label>' +
      '<label>Case notes<textarea name="notes" rows="4" maxlength="8000">' + esc(c.notes) + '</textarea></label><label class="u1-mr-check"><input type="checkbox" name="authorised" required>I confirm this case uses public or authorised information.</label>' +
      '<div class="u1-mr-actions"><button type="submit" class="u1-mr-primary">Save case</button>' + (c.id ? '<button type="button" data-mr-case-export>Export case JSON</button><button type="button" data-mr-case-delete>Delete case</button>' : '') + '</div>' +
      (c.id ? '<p class="u1-mr-note">Created ' + esc(stamp(c.created_at)) + ' / Updated ' + esc(stamp(c.updated_at)) + '</p>' : '') + '</form>';
    evidenceEditor(); renderEvidence();
  }

  function evidenceEditor() {
    var target = qs(researchRoot, '[data-mr-evidence-editor]'), e = evidenceEdit || {};
    if (!currentCase) { target.innerHTML = '<div class="u1-mr-empty"><h2>Every finding starts with a source.</h2><p>Save your first case, then add a URL, what you observed, and when. New evidence starts unverified.</p></div>'; return; }
    target.innerHTML = '<form data-mr-evidence-form class="u1-mr-card"><h2>' + (e.id ? 'Edit evidence' : 'Add attributed evidence') + '</h2><label>Evidence title<input name="title" required maxlength="160" value="' + esc(e.title) + '"></label>' +
      '<label>Source URL<input name="source_url" type="url" required maxlength="2000" placeholder="https://example.org/source" value="' + esc(e.source_url) + '"></label>' +
      '<label>Observation or note<textarea name="note" rows="5" required maxlength="8000">' + esc(e.note) + '</textarea></label><div class="u1-mr-row"><label>Observed at (device time)<input name="observed_at" type="datetime-local" required value="' + localTime(e.observed_at) + '"></label>' +
      '<label>Evidence label<select name="label"><option value="unverified">Unverified</option><option value="verified"' + (e.label === 'verified' ? ' selected' : '') + '>Verified by me</option></select></label></div>' +
      '<label>Verification basis (required for verified evidence)<textarea name="verification_note" rows="2" maxlength="1200">' + esc(e.verification_note) + '</textarea></label><p class="u1-mr-note">Record how you checked a claim. Matching handles or names alone do not verify a person.</p>' +
      '<div class="u1-mr-actions"><button type="submit" class="u1-mr-primary">Save evidence</button>' + (e.id ? '<button type="button" data-mr-cancel-evidence>Cancel edit</button>' : '') + '</div></form>';
  }

  function renderEvidence() {
    var items = currentCase && currentCase.evidence || [];
    qs(researchRoot, '[data-mr-evidence-list]').innerHTML = items.length ? '<h2>Evidence trail</h2>' + items.map(function (e) {
      return '<article class="u1-mr-evidence"><header><h3>' + esc(e.title) + '</h3><span class="u1-mr-label" data-label="' + e.label + '">' + (e.label === 'verified' ? 'Verified by author' : 'Unverified') + '</span></header><a href="' + esc(e.source_url) + '" target="_blank" rel="noopener noreferrer">' + esc(e.source_url) + ' (external)</a>' +
        '<p class="u1-mr-prewrap">' + esc(e.note) + '</p>' + (e.verification_note ? '<p><strong>Verification basis:</strong> ' + esc(e.verification_note) + '</p>' : '') +
        '<p class="u1-mr-note">Observed ' + esc(stamp(e.observed_at)) + ' / Recorded ' + esc(stamp(e.created_at)) + ' / Updated ' + esc(stamp(e.updated_at)) + '</p><div class="u1-mr-actions"><button type="button" data-mr-evidence-edit="' + e.id + '">Edit</button><button type="button" data-mr-evidence-delete="' + e.id + '">Delete evidence</button></div></article>';
    }).join('') : '';
  }

  async function refreshCases(id) {
    var result = await request(API);
    qs(researchRoot, '[data-mr-case-list]').innerHTML = result.cases.length ? result.cases.map(function (c) { return '<button type="button" class="u1-mr-case-link" data-mr-case-open="' + c.id + '"><strong>' + esc(c.title) + '</strong><span>' + c.evidence_count + ' sources / ' + esc(c.scope) + '</span></button>'; }).join('') : '<p class="u1-mr-note">Your casebook is empty. Start with a question and a source you can attribute.</p>';
    if (id) { currentCase = (await request(API + '?case_id=' + encodeURIComponent(id))).case; evidenceEdit = null; caseEditor(); }
  }

  function createResearch() {
    researchRoot = document.createElement('section'); researchRoot.className = 'u1-mr'; researchRoot.dataset.mrView = 'osint';
    researchRoot.innerHTML = chrome('osint', 'Keep the source with the story.', 'A local casebook for public and authorised research, with an evidence trail you can review.') +
      '<section class="u1-mr-search"><label>Prepare a public web search<input type="search" data-mr-search maxlength="300" placeholder="A domain, organisation, topic or public claim"></label><a data-mr-search-link href="https://duckduckgo.com/" target="_blank" rel="noopener noreferrer">Search public web (external)</a><p class="u1-mr-note">Opens an external search provider when clicked. No search or source fetch runs in the background.</p></section>' +
      '<div class="u1-mr-case-layout"><aside class="u1-mr-case-index"><div class="u1-mr-actions"><button type="button" data-mr-new-case>New case</button><button type="button" data-mr-refresh-cases>Reload cases</button></div><div data-mr-case-list>Loading your local casebook...</div></aside><div><div data-mr-case-editor></div><div data-mr-evidence-editor></div><section data-mr-evidence-list></section></div></div>' +
      '<p class="u1-mr-status" data-mr-status role="status" aria-live="polite"></p><footer class="u1-mr-footer">Stored locally without encryption. Verification labels are your assessment. No hidden email discovery, private social data collection, automatic person dossiers or RDAP lookup. Case JSON includes your notes and source URLs.</footer></div>';
    bindRoutes(researchRoot); caseEditor();
    qs(researchRoot, '[data-mr-search]').addEventListener('input', function (event) { qs(researchRoot, '[data-mr-search-link]').href = 'https://duckduckgo.com/?q=' + encodeURIComponent(event.target.value.trim()); });
    researchRoot.addEventListener('submit', function (event) {
      var form = event.target; if (!form.matches('[data-mr-case-form], [data-mr-evidence-form]')) return;
      event.preventDefault();
      perform(researchRoot, async function () {
        var fields = Object.fromEntries(new FormData(form)), payload;
        if (form.hasAttribute('data-mr-case-form')) {
          payload = { action: 'case_save', title: fields.title, scope: fields.scope, notes: fields.notes, authorised_confirmed: form.elements.authorised.checked };
          if (currentCase) Object.assign(payload, { id: currentCase.id, expected_updated: currentCase.updated_at });
          var result = await request(API, payload); await refreshCases(result.id); status(researchRoot, 'Case saved in the local workspace database.');
        } else {
          payload = Object.assign(fields, { action: 'evidence_save', case_id: currentCase.id, observed_at: new Date(fields.observed_at).toISOString() });
          if (evidenceEdit) Object.assign(payload, { id: evidenceEdit.id, expected_updated: evidenceEdit.updated_at });
          await request(API, payload); await refreshCases(currentCase.id); status(researchRoot, 'Attributed evidence saved.');
        }
      });
    });
    researchRoot.addEventListener('click', function (event) {
      var button = event.target.closest('button'); if (!button || button.type === 'submit' || button.hasAttribute('data-mr-route')) return;
      perform(researchRoot, async function () {
        if (button.hasAttribute('data-mr-new-case')) { currentCase = null; evidenceEdit = null; caseEditor(); status(researchRoot, 'New case ready.'); }
        if (button.hasAttribute('data-mr-refresh-cases')) { await refreshCases(currentCase && currentCase.id); status(researchRoot, 'Casebook reloaded.'); }
        if (button.dataset.mrCaseOpen) { await refreshCases(button.dataset.mrCaseOpen); status(researchRoot, 'Case opened.'); }
        if (button.hasAttribute('data-mr-case-export') && currentCase) { saveDownload(await request(API + '?export=' + currentCase.id)); status(researchRoot, 'Case JSON created. Download requested.'); }
        if (button.hasAttribute('data-mr-case-delete') && currentCase) {
          if (!window.confirm('Delete this case and its evidence? Export it first if you need a copy.')) return;
          await request(API, { action: 'case_delete', id: currentCase.id, expected_updated: currentCase.updated_at });
          currentCase = null; evidenceEdit = null; caseEditor(); await refreshCases(); status(researchRoot, 'Case and evidence deleted.');
        }
        if (button.dataset.mrEvidenceEdit) { evidenceEdit = currentCase.evidence.find(function (e) { return e.id === button.dataset.mrEvidenceEdit; }); evidenceEditor(); qs(researchRoot, '[data-mr-evidence-form] input').focus(); }
        if (button.hasAttribute('data-mr-cancel-evidence')) { evidenceEdit = null; evidenceEditor(); }
        if (button.dataset.mrEvidenceDelete) {
          var evidence = currentCase.evidence.find(function (e) { return e.id === button.dataset.mrEvidenceDelete; });
          if (!window.confirm('Delete this evidence record from the case?')) return;
          await request(API, { action: 'evidence_delete', id: evidence.id, case_id: currentCase.id, expected_updated: evidence.updated_at });
          await refreshCases(currentCase.id); status(researchRoot, 'Evidence deleted.');
        }
      });
    });
  }

  async function mountResearch(host) {
    unmountMedia();
    var first = !researchRoot; if (first) createResearch();
    if (researchRoot.parentNode !== host) host.replaceChildren(researchRoot);
    if (first) { try { await refreshCases(); } catch (e) { status(researchRoot, e.message, true); } }
  }

  function register() {
    if (registration) return true;
    if (!window.U1CoreViews) return false;
    window.U1CoreViews.register('media', mountMedia); window.U1CoreViews.register('osint', mountResearch); registration = true;
    document.dispatchEvent(new CustomEvent('u1:native-views-ready', { detail: { ids: ['media', 'osint'] } }));
    return true;
  }

  window.U1MediaResearch = Object.freeze({ register: register, mountMedia: mountMedia, mountOSINT: mountResearch, unmountMedia: unmountMedia, refreshPlayer: updateMetadata });
  // Registration does not require DOM nodes. Make extensions visible before an
  // earlier DOMContentLoaded router listener chooses or caches a fallback view.
  register();
  document.addEventListener('u1:core-views-ready', register);
  function init() {
    register();
    new MutationObserver(function () {
      if (mediaRoot && player && document.body.dataset.u1View && document.body.dataset.u1View !== 'media') unmountMedia();
    }).observe(document.body, { attributes: true, attributeFilter: ['data-u1-view'] });
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, { once: true }); else init();
  window.addEventListener('pagehide', function () { if (mediaURL) URL.revokeObjectURL(mediaURL); if (trackURL) URL.revokeObjectURL(trackURL); });
})();
