/* Spotify account metadata only. Does not replace or control the local audio player. */
(function () {
  'use strict';
  const PATH = '/api/workspace/spotify';
  const labels = {setup_needed: 'Setup needed', auth_required: 'Authorization required', authorization_pending: 'Awaiting Spotify permission', connected_unchecked: 'Authorized; playback not checked', nothing_playing: 'Connected; nothing playing', playing: 'Playing on Spotify', paused: 'Paused on Spotify', stale: 'Stale: last observation only', unavailable: 'Spotify unavailable or account access restricted', rate_limited: 'Spotify rate limit; waiting', private_session: 'Connected; private session', playback_unavailable: 'Connected; playback details unavailable', keychain_unavailable: 'Keychain unavailable', keychain_setup_needed: 'Keychain helper setup needed', storage_unavailable: 'Local storage unavailable', safety_blocked: 'Stopped by Safety'};
  let state = null, widget = null, view = null, busy = false, auto = false, authURL = '', timer = null, generation = 0;
  let layoutActive = false, layoutFrame = 0, utilityShelf = null, shelfResize = null, shelfChanges = null, shelfDiscovery = null;
  const controllers = new Set();
  const esc = value => String(value == null ? '' : value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const locked = () => document.documentElement.dataset.u1Safety === 'locked';
  const when = value => typeof value === 'number' && Number.isFinite(value) ? new Date(value * 1000).toLocaleString() : 'Not checked';
  const safeLink = value => typeof value === 'string' && /^https:\/\/open\.spotify\.com\/(track|episode)\/[A-Za-z0-9]{1,64}$/.test(value) ? value : '';

  async function request(body) {
    if (locked()) throw new Error('Stopped by Safety');
    const controller = new AbortController(); controllers.add(controller);
    const deadline = setTimeout(() => controller.abort(), body && body.action === 'configure' ? 55000 : 45000);
    try {
      const headers = {'Accept':'application/json'};
      if (body) {
        const response = await fetch('/api/integrations', {credentials:'same-origin', cache:'no-store', redirect:'error', signal:controller.signal});
        if (!response.ok) throw new Error('Unable to load request protection');
        const data = await response.json();
        const csrf = data.csrf_token || data.csrf;
        if (typeof csrf !== 'string' || !csrf) throw new Error('Request protection unavailable');
        headers['X-U1-CSRF'] = csrf; headers['Content-Type'] = 'application/json';
      }
      if (locked()) throw new Error('Stopped by Safety');
      const response = await fetch(PATH, {method:body ? 'POST':'GET', headers, body:body ? JSON.stringify(body):undefined, credentials:'same-origin', cache:'no-store', redirect:'error', signal:controller.signal});
      const data = await response.json();
      if (!response.ok || data.success !== true) throw new Error(labels[data.error] || 'Spotify request could not complete. Review setup or retry.');
      return data;
    } finally { clearTimeout(deadline); controllers.delete(controller); }
  }
  function summary() {
    const value = state || {status:'setup_needed'};
    const expired = value.observed_at && Date.now() / 1000 - value.observed_at > 45;
    const stale = expired || ['stale','unavailable','rate_limited','safety_blocked','keychain_unavailable'].includes(value.status);
    const item = value.item;
    const label = locked() ? 'Stopped by Safety' : expired && ['playing','paused','nothing_playing','private_session','playback_unavailable'].includes(value.status) ? labels.stale : labels[value.status] || 'Status unavailable';
    return '<p class="u1-spotify-status" role="status">' + esc(label) + '</p>' +
      (item ? '<strong>' + (stale ? 'Last observed: ' : '') + esc(item.title || 'Untitled Spotify item') + '</strong><p>' + esc(item.artist) + '</p>' +
        (item.device ? '<p>Device: ' + esc(item.device) + '</p>' : '') +
        (safeLink(item.url) ? '<a target="_blank" rel="noopener noreferrer" href="' + esc(item.url) + '">Open this item in Spotify</a>' : '') : '') +
      '<p class="u1-spotify-muted">Observed: ' + esc(when(value.observed_at)) + '. No simulated progress.</p>';
  }
  function controls() {
    return '<div class="u1-spotify-actions"><button type="button" data-spotify-action="refresh" ' + (busy || locked() || !state || !state.credentials_saved ? 'disabled' : '') + '>Check playback</button>' +
      '<a href="https://open.spotify.com/" target="_blank" rel="noopener noreferrer">Open Spotify</a></div>' +
      '<label class="u1-spotify-opt"><input type="checkbox" data-spotify-auto ' + (auto ? 'checked ' : '') + (locked() || !state || !state.credentials_saved ? 'disabled' : '') + '> Allow read-only checks every 20 seconds while this tab is visible (this session only)</label>';
  }
  function render() {
    if (widget) {
      const content = widget.querySelector('[data-spotify-content]');
      content.innerHTML = summary() + controls() + '<p><a href="#spotify" data-go="spotify">Connection setup</a></p>';
    }
    if (view && view.isConnected && view.querySelector('[data-spotify-view]')) {
      view.querySelector('[data-spotify-live]').innerHTML = summary() + controls();
      const authorize = view.querySelector('[data-spotify-authorize]');
      authorize.innerHTML = authURL ? '<a class="u1-spotify-consent" href="' + esc(authURL) + '" target="_blank" rel="noopener noreferrer">Continue to Spotify to review permission</a>' : '';
      view.querySelectorAll('[data-spotify-action]').forEach(button => { button.disabled = busy || locked() || (button.dataset.spotifyAction === 'refresh' && (!state || !state.credentials_saved)); });
    }
  }
  function notify(message) {
    document.querySelectorAll('[data-spotify-message]').forEach(node => { node.textContent = message; });
  }
  async function update(body) {
    if (busy || locked()) return;
    const run = generation; busy = true; render(); notify(body ? 'Working on the requested action...' : 'Reading local status...');
    try {
      const result = await request(body);
      if (run !== generation || locked()) return;
      state = result;
      if (result.authorization_url) {
        const url = new URL(result.authorization_url);
        authURL = url.origin === 'https://accounts.spotify.com' && url.pathname === '/authorize' ? url.href : '';
      }
      if (body && ['disconnect','configure'].includes(body.action)) { authURL = ''; auto = false; }
      if (state.status === 'auth_required' || state.status === 'keychain_unavailable') auto = false;
      notify('Local status updated. Opening Spotify alone does not connect an account.');
    } catch (error) {
      if (run === generation) {
        if (state) state = Object.assign({}, state, {status:'unavailable',live_verified:false});
        notify(error.name === 'AbortError' ? 'Request stopped or timed out; no current playback claim.' : error.message);
      }
    } finally { busy = false; render(); }
  }
  function events(host) {
    host.addEventListener('click', event => {
      const button = event.target.closest('[data-spotify-action]'); if (!button || !host.contains(button)) return;
      const action = button.dataset.spotifyAction;
      if (action === 'configure') {
        const client = host.querySelector('[data-spotify-client]');
        if (!client || !/^[a-fA-F0-9]{32}$/.test(client.value.trim())) { notify('Enter the public 32-character Spotify Client ID, not a secret.'); return; }
        if (!window.confirm('Save this public Client ID and build the local macOS Keychain helper? No account request or token read occurs yet.')) return;
        update({action, client_id:client.value.trim(), confirmed:true});
      } else if (action === 'connect') {
        if (window.confirm('Start a temporary local callback listener and prepare Spotify read-only playback authorization? Review permission on Spotify before granting it.')) update({action,confirmed:true});
      } else if (action === 'disconnect') {
        if (window.confirm('Remove this app\'s local Spotify tokens from Keychain? This does not revoke Spotify dashboard permission.')) update({action,confirmed:true});
      } else if (action === 'refresh') update({action,confirmed:true});
    });
    host.addEventListener('change', event => {
      if (!event.target.matches('[data-spotify-auto]')) return;
      auto = event.target.checked && !locked(); render();
      if (auto) update({action:'refresh',confirmed:true});
    });
  }
  function mount(host) {
    view = host;
    host.innerHTML = '<section class="u1-spotify" data-spotify-view><header><p>ACCOUNT CONNECTION / READ ONLY</p><h1>Spotify</h1><p>Real playback observations from your account. This is not an audio player and does not control your separate local media player.</p></header><div data-spotify-live></div><p data-spotify-message role="status"></p><section class="u1-spotify-setup"><h2>Connect your Spotify app</h2><ol><li>Create or select your app in the <a href="https://developer.spotify.com/dashboard" target="_blank" rel="noopener noreferrer">Spotify developer dashboard</a>. Check your app owner/account eligibility and development-mode allowlist.</li><li>Register exactly <code>http://127.0.0.1/spotify/callback</code> with no port. A temporary loopback port is assigned at Connect. Do not use localhost.</li><li>Enter only your public Client ID below. No client secret, password, or token is requested. Native macOS Keychain setup requires Apple command line developer tools and may ask for permission.</li><li>Start authorization, open the returned Spotify link, then review <code>user-read-playback-state</code>. Afterwards use Check playback once and compare with Spotify.</li></ol><label>Public Spotify Client ID <input data-spotify-client maxlength="32" autocomplete="off" spellcheck="false" placeholder="32 hexadecimal characters"></label><div class="u1-spotify-actions"><button type="button" data-spotify-action="configure">Save setup</button><button type="button" data-spotify-action="connect">Start authorization</button><button type="button" data-spotify-action="disconnect">Disconnect locally</button></div><div data-spotify-authorize></div><p>Opening Spotify or marking a checklist is not account verification. A 204 response means connected with no active playback; access restrictions and stale data stay explicit.</p><p><a href="https://www.spotify.com/account/apps/" target="_blank" rel="noopener noreferrer">Manage or revoke Spotify app permissions</a></p></section></section>';
    if (!host.dataset.u1SpotifyEvents) { events(host); host.dataset.u1SpotifyEvents = '1'; }
    render(); update();
  }
  function queueLayout() {
    if (layoutActive && !layoutFrame) layoutFrame = window.requestAnimationFrame(positionWidget);
  }
  function observeShelf(next) {
    if (next === utilityShelf) return;
    if (shelfResize) shelfResize.disconnect();
    if (shelfChanges) shelfChanges.disconnect();
    shelfResize = null; shelfChanges = null; utilityShelf = next;
    if (!next) return;
    if (window.ResizeObserver) {
      shelfResize = new ResizeObserver(queueLayout);
      shelfResize.observe(next);
    }
    if (window.MutationObserver) {
      shelfChanges = new MutationObserver(queueLayout);
      shelfChanges.observe(next, {attributes:true, attributeFilter:['class','style','hidden'], childList:true, subtree:true});
    }
  }
  function positionWidget() {
    layoutFrame = 0;
    if (!layoutActive || !widget || !widget.isConnected) return;
    observeShelf(document.getElementById('u1-utility-shelf'));
    const height = window.innerHeight || document.documentElement.clientHeight;
    const rect = utilityShelf ? utilityShelf.getBoundingClientRect() : null;
    const visibleShelf = rect && rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.top < height;
    const bottom = visibleShelf ? Math.ceil(Math.max(12, height - rect.top + 12)) : 12;
    const available = Math.max(0, Math.floor(Math.min(height * 0.65, height - bottom - 12)));
    const bottomStyle = bottom + 'px', heightStyle = available + 'px';
    // Changed-only writes avoid ResizeObserver feedback and animated overlap.
    if (widget.style.bottom !== bottomStyle) widget.style.bottom = bottomStyle;
    if (widget.style.maxHeight !== heightStyle) widget.style.maxHeight = heightStyle;
  }
  function startLayout() {
    if (layoutActive) return;
    layoutActive = true;
    window.addEventListener('resize', queueLayout, {passive:true});
    if (window.visualViewport) window.visualViewport.addEventListener('resize', queueLayout, {passive:true});
    if (window.MutationObserver) {
      shelfDiscovery = new MutationObserver(() => {
        // Only react to shelf appearance/replacement, not unrelated app renders.
        if (document.getElementById('u1-utility-shelf') !== utilityShelf) queueLayout();
      });
      shelfDiscovery.observe(document.body, {childList:true, subtree:true});
    }
    positionWidget();
  }
  function stopLayout() {
    layoutActive = false;
    if (layoutFrame) window.cancelAnimationFrame(layoutFrame);
    layoutFrame = 0;
    if (shelfResize) shelfResize.disconnect();
    if (shelfChanges) shelfChanges.disconnect();
    if (shelfDiscovery) shelfDiscovery.disconnect();
    shelfResize = null; shelfChanges = null; shelfDiscovery = null; utilityShelf = null;
    window.removeEventListener('resize', queueLayout);
    if (window.visualViewport) window.visualViewport.removeEventListener('resize', queueLayout);
  }
  function mountWidget(host) {
    if (widget) return widget;
    widget = document.createElement('aside'); widget.className = 'u1-spotify u1-spotify-widget'; widget.setAttribute('aria-label','Spotify account playback');
    widget.innerHTML = '<details><summary>Spotify <span>Read-only account widget</span></summary><div data-spotify-content></div><p data-spotify-message role="status"></p></details>';
    (host || document.body).appendChild(widget); events(widget); render(); startLayout(); return widget;
  }
  function stop() {
    generation += 1; auto = false; authURL = ''; controllers.forEach(controller => controller.abort()); render();
  }
  function start() {
    if (!document.getElementById('u1-spotify-styles')) {
      const style = document.createElement('style'); style.id = 'u1-spotify-styles';
      style.textContent = '.u1-spotify{font:inherit;color:var(--text,#e8ede9);line-height:1.5}.u1-spotify p{margin:.45rem 0}.u1-spotify a{color:var(--accent,#87dca6);text-decoration:underline}.u1-spotify button,.u1-spotify input:not([type=checkbox]){font:inherit;border:1px solid var(--line,#47564c);border-radius:7px;padding:.55rem .8rem;background:var(--panel,#17211b);color:inherit}.u1-spotify button{cursor:pointer}.u1-spotify button:disabled{opacity:.5;cursor:default}.u1-spotify :focus-visible{outline:2px solid #79d99c;outline-offset:3px}.u1-spotify-status{font-weight:700}.u1-spotify-muted,.u1-spotify-widget summary span{font-size:.8rem;opacity:.75}.u1-spotify-opt{display:flex;gap:.55rem;align-items:flex-start;margin:.75rem 0;font-size:.82rem}.u1-spotify-opt input{width:auto;accent-color:#1db954;margin-top:.3rem}.u1-spotify-actions{display:flex;flex-wrap:wrap;align-items:center;gap:.7rem;margin:.8rem 0}.u1-spotify-setup{margin-top:1.5rem;padding:1rem;border:1px solid var(--line,#47564c);border-radius:12px}.u1-spotify-setup li{margin:.6rem 0}.u1-spotify-setup code{overflow-wrap:anywhere}.u1-spotify-setup label{display:grid;gap:.4rem;max-width:32rem}.u1-spotify-widget{position:fixed;right:18px;bottom:12px;z-index:70;box-sizing:border-box;width:min(350px,calc(100vw - 32px));background:var(--panel,#17211b);border:1px solid var(--line,#47564c);box-shadow:0 12px 35px #0003;border-radius:12px;padding:.75rem 1rem;font-size:.88rem;max-height:65vh;overflow:auto;transition:none}.u1-spotify-widget summary{cursor:pointer;font-weight:700}.u1-spotify-widget summary span{display:block}.u1-spotify-widget strong{overflow-wrap:anywhere}.u1-spotify-consent{display:inline-block;padding:.7rem;border:1px solid currentColor;border-radius:7px}@media(max-width:600px){.u1-spotify-widget{right:12px;width:min(320px,calc(100vw - 24px))}}@media(prefers-reduced-motion:reduce){.u1-spotify-widget,.u1-spotify-widget *{animation:none!important;transition:none!important}}';
      document.head.appendChild(style);
    }
    if (window.U1CoreViews) window.U1CoreViews.register('spotify', mount);
    mountWidget(); update();
    timer = setInterval(() => {
      render();
      if (document.hidden || locked() || busy) return;
      if (auto && state && state.credentials_saved && Date.now() / 1000 >= (state.next_refresh_at || 0)) update({action:'refresh',confirmed:true});
      else if (state && state.oauth_pending) update(); // Local cached GET only, never an auth probe.
    }, 20000);
  }
  document.addEventListener('u1:safety-change', event => { if (event.detail && event.detail.locked) stop(); else render(); });
  document.addEventListener('visibilitychange', () => { if (document.hidden) { generation += 1; controllers.forEach(controller => controller.abort()); } });
  window.addEventListener('pagehide', () => { stop(); stopLayout(); clearInterval(timer); });
  window.addEventListener('pageshow', event => { if (event.persisted) startLayout(); });
  window.U1Spotify = {mount, mountWidget, stop, refresh:() => update({action:'refresh',confirmed:true})};
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', start, {once:true}); else start();
}());
