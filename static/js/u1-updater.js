/**
 * U1 OS // Updater section
 * ---------------------------------------------------------------
 * Renders the Updater workspace: what version is running, whether the
 * checkout is behind its remote, the always-on improvement agent's
 * findings, maintenance actions, and the recent change history.
 *
 * Every action that changes the installation asks for confirmation
 * first, and no action runs on its own.
 */
(function () {
  'use strict';

  var SECTION = 'updater';
  var POLL_MS = 30000;
  var timer = null;
  var busy = false;
  var state = null;

  function el(id) { return document.getElementById(id); }

  function esc(value) {
    return String(value === null || value === undefined ? '' : value)
      .replace(/[&<>"']/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
      });
  }

  function toast(message, type) {
    if (typeof window.showNotification === 'function') return window.showNotification(message, type);
    if (window.U1FX && window.U1FX.notify) return window.U1FX.notify.show(message, { type: type });
    console.log('[updater]', message);
  }

  function isActive() {
    var section = el('section-' + SECTION);
    return !!(section && section.classList.contains('active'));
  }

  function row(label, value, tone) {
    var colour = tone === 'good' ? 'var(--ok, #10b981)'
      : tone === 'bad' ? 'var(--danger, #ff3366)'
      : tone === 'warn' ? 'var(--gold, #e9b44c)'
      : 'var(--text-primary, #e6e9ef)';
    return '<div class="kv-row" style="display:flex;justify-content:space-between;gap:14px;padding:6px 0;' +
      'border-bottom:1px solid rgba(255,255,255,0.05);">' +
      '<span class="mono" style="font-size:10px;letter-spacing:0.06em;text-transform:uppercase;' +
      'color:var(--text-muted,#767e8e);">' + esc(label) + '</span>' +
      '<span class="mono" style="font-size:11.5px;color:' + colour + ';text-align:right;">' +
      esc(value) + '</span></div>';
  }

  function button(action, label, opts) {
    opts = opts || {};
    return '<button class="btn ' + (opts.primary ? 'btn-primary' : 'btn-secondary') + ' mono" ' +
      'data-updater-action="' + esc(action) + '" ' +
      (opts.confirm ? 'data-confirm="' + esc(opts.confirm) + '" ' : '') +
      (opts.disabled ? 'disabled ' : '') +
      'style="font-size:10.5px;padding:7px 13px;">' + esc(label) + '</button>';
  }

  /* ---------------- API ---------------- */

  function call(action, payload) {
    return fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service: 'updater', action: action, payload: payload || {} })
    }).then(function (r) {
      return r.json().catch(function () { return { success: false, error: 'Unreadable response' }; });
    }).catch(function (err) {
      return { success: false, error: err && err.message ? err.message : 'Network unreachable' };
    });
  }

  /* ---------------- Renderers ---------------- */

  function metric(label, value, unit, note) {
    var shown = (value === null || value === undefined) ? 'NOT MEASURED'
      : (typeof value === 'number' ? value : String(value)) + (unit || '');
    var muted = (value === null || value === undefined);
    return '<div style="flex:1 1 130px;min-width:120px;padding:10px 12px;' +
      'border:1px solid rgba(255,255,255,0.07);border-radius:3px;background:rgba(255,255,255,0.015);">' +
      '<div class="mono" style="font-size:9px;letter-spacing:0.08em;text-transform:uppercase;' +
      'color:var(--text-muted,#767e8e);">' + esc(label) + '</div>' +
      '<div class="mono" style="margin-top:5px;font-size:' + (muted ? '11px' : '18px') + ';' +
      'color:' + (muted ? 'var(--text-muted,#767e8e)' : 'var(--text-primary,#e6e9ef)') + ';">' +
      esc(shown) + '</div>' +
      (note ? '<div class="mono" style="margin-top:3px;font-size:9px;color:var(--text-muted,#767e8e);">' +
        esc(note) + '</div>' : '') +
      '</div>';
  }

  function renderHealth(data) {
    var box = el('updaterHealthContainer');
    if (!box) return;
    var h = (data && data.health) || {};
    var badge = el('updaterHealthBadge');
    var dot = el('updaterHealthDot');
    var score = (h.score === null || h.score === undefined) ? null : h.score;

    if (badge) badge.textContent = score === null ? 'NOT MEASURED' : score + ' / 100';
    if (dot) dot.className = 'status-dot' + (score !== null && score >= 70 ? ' active' : '');

    var components = h.components || {};
    var tiles = Object.keys(components).map(function (k) {
      return metric(k, components[k], '', null);
    }).join('');
    var missing = (h.unmeasured || []).map(function (k) {
      return metric(k, null, '', 'no data yet');
    }).join('');

    var basis = h.basis || {};
    box.innerHTML =
      '<div style="display:flex;gap:10px;flex-wrap:wrap;margin-bottom:10px;">' +
        metric('Health score', score, ' / 100', score === null ? 'nothing measured yet' : null) +
        tiles + missing +
      '</div>' +
      '<div class="mono" style="font-size:10px;line-height:1.6;color:var(--text-muted,#767e8e);">' +
        'From ' + esc(basis.requests_observed === undefined ? '—' : basis.requests_observed) +
        ' observed request(s) and ' + esc(basis.exceptions_observed === undefined ? '—' : basis.exceptions_observed) +
        ' recorded exception(s) over ' +
        esc(basis.uptime_seconds === undefined ? '—' : Math.round(basis.uptime_seconds)) + 's of uptime. ' +
        'Every figure here is measured on this machine; anything without data reads NOT MEASURED.' +
      '</div>' +
      '<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px;">' +
        button('capture_baseline', 'CAPTURE BASELINE') +
        button('reset_metrics', 'CLEAR MEASUREMENTS', {
          confirm: 'Clear every measurement collected so far? Collection starts again from now.'
        }) +
      '</div>';
  }

  function renderRuntime(data) {
    var box = el('updaterRuntimeContainer');
    if (!box) return;
    var r = (data && data.runtime) || {};
    var deps = r.optional_dependencies || {};
    var badge = el('updaterVersionBadge');
    if (badge) badge.textContent = 'v' + (r.version || '—');
    var dot = el('updaterRuntimeDot');
    if (dot) dot.className = 'status-dot' + (r.python_supported ? ' active' : '');

    var depRows = Object.keys(deps).map(function (name) {
      var d = deps[name];
      return row(name, d.installed ? 'installed' : 'not installed', d.installed ? 'good' : 'warn');
    }).join('');

    box.innerHTML =
      row('Version', r.version || '—') +
      row('Python', r.python || '—', r.python_supported ? 'good' : 'bad') +
      row('Platform', r.platform || '—') +
      row('Serving on', '127.0.0.1:' + (r.port || '—')) +
      row('Uptime', r.uptime_seconds !== undefined ? Math.round(r.uptime_seconds) + 's' : '—') +
      row('Desktop app', r.desktop_app_built ? 'built' : 'not built', r.desktop_app_built ? 'good' : 'warn') +
      '<div class="mono" style="margin:12px 0 6px;font-size:9.5px;letter-spacing:0.08em;' +
      'text-transform:uppercase;color:var(--text-muted,#767e8e);">Optional dependencies</div>' +
      depRows;
  }

  function renderChannel(data) {
    var box = el('updaterChannelContainer');
    if (!box) return;
    var g = (data && data.git) || {};
    var badge = el('updaterBranchBadge');
    if (badge) badge.textContent = g.branch ? g.branch.toUpperCase() : '—';
    var dot = el('updaterGitDot');
    if (dot) dot.className = 'status-dot' + (g.is_repo && g.clean ? ' active' : '');

    if (!g.is_repo) {
      box.innerHTML = '<p class="mono" style="font-size:11.5px;color:var(--text-muted,#767e8e);">' +
        esc(g.message || 'This installation is not a git checkout, so updates must be applied manually.') +
        '</p>';
      return;
    }

    var updateAvailable = g.update_available;
    var summary = !g.has_commits ? 'No commits yet — nothing to compare against.'
      : !g.remote_configured ? 'No remote configured. Add one to receive updates.'
      : !g.tracking_remote ? 'This branch is not tracking the remote yet.'
      : updateAvailable ? g.commits_behind + ' update(s) waiting to be applied.'
      : 'This workspace is up to date.';

    box.innerHTML =
      row('Branch', g.branch || '—') +
      row('Commit', g.commit || 'none yet') +
      row('Latest change', g.subject || '—') +
      row('Committed', g.committed || '—') +
      row('Remote', g.remote || 'not configured', g.remote_configured ? 'good' : 'warn') +
      row('Working tree', g.clean ? 'clean' : g.uncommitted_files + ' uncommitted file(s)', g.clean ? 'good' : 'warn') +
      row('Behind remote', g.commits_behind || 0, updateAvailable ? 'warn' : 'good') +
      row('Ahead of remote', g.commits_ahead || 0) +
      '<p class="mono" style="margin:12px 0;font-size:11.5px;color:' +
        (updateAvailable ? 'var(--gold,#e9b44c)' : 'var(--text-muted,#767e8e)') + ';">' + esc(summary) + '</p>' +
      '<div style="display:flex;gap:8px;flex-wrap:wrap;">' +
        button('check_for_updates', 'CHECK FOR UPDATES') +
        button('apply_update', 'APPLY UPDATE', {
          primary: true,
          disabled: !updateAvailable,
          confirm: 'Apply the waiting update? This changes the installed files, then the workspace needs a restart.'
        }) +
      '</div>';
  }

  function renderAgent(data) {
    var box = el('updaterAgentContainer');
    if (!box) return;
    var a = (data && data.agent) || {};
    var badge = el('updaterAgentBadge');
    var dot = el('updaterAgentDot');

    if (a.available === false) {
      if (badge) badge.textContent = 'OFFLINE';
      if (dot) dot.className = 'status-dot';
      box.innerHTML = '<p class="mono" style="font-size:11.5px;color:var(--text-muted,#767e8e);">' +
        esc(a.message || a.error || 'The improvement agent is not running.') + '</p>';
      return;
    }

    var findings = a.findings || [];
    if (badge) badge.textContent = a.enabled ? findings.length + ' FINDINGS' : 'PAUSED';
    if (dot) dot.className = 'status-dot' + (a.enabled ? ' active' : '');

    var order = { attention: 0, setup: 1, improvement: 2 };
    var sorted = findings.slice().sort(function (x, y) {
      return (order[x.priority] === undefined ? 3 : order[x.priority]) -
             (order[y.priority] === undefined ? 3 : order[y.priority]);
    });

    var tone = { attention: 'var(--danger,#ff3366)', setup: 'var(--gold,#e9b44c)', improvement: 'var(--text-muted,#767e8e)' };
    var list = sorted.length ? sorted.map(function (f) {
      return '<div style="padding:9px 0;border-bottom:1px solid rgba(255,255,255,0.05);">' +
        '<div style="display:flex;gap:8px;align-items:baseline;">' +
          '<span class="mono" style="font-size:9px;letter-spacing:0.08em;text-transform:uppercase;' +
          'color:' + (tone[f.priority] || tone.improvement) + ';">' + esc(f.priority) + '</span>' +
          '<span class="mono" style="font-size:11.5px;color:var(--text-primary,#e6e9ef);">' + esc(f.title) + '</span>' +
        '</div>' +
        '<div class="mono" style="margin-top:3px;font-size:10.5px;line-height:1.5;color:var(--text-muted,#767e8e);">' +
          esc(f.detail) + '</div>' +
      '</div>';
    }).join('') : '<p class="mono" style="font-size:11.5px;color:var(--text-muted,#767e8e);">' +
      'Nothing needs attention right now.</p>';

    var checked = a.checked_at ? new Date(a.checked_at * 1000).toLocaleTimeString() : 'not yet';
    box.innerHTML =
      row('Status', a.checking ? 'scanning…' : (a.enabled ? 'watching' : 'paused'), a.enabled ? 'good' : 'warn') +
      row('Last check', checked) +
      row('Interval', a.interval_seconds ? Math.round(a.interval_seconds / 60) + ' min' : '—') +
      row('Mode', a.mode || '—') +
      '<div style="display:flex;gap:8px;flex-wrap:wrap;margin:12px 0;">' +
        button('agent_scan', 'SCAN NOW') +
        button(a.enabled ? 'agent_pause' : 'agent_resume', a.enabled ? 'PAUSE AGENT' : 'RESUME AGENT') +
      '</div>' +
      '<div class="mono" style="margin:6px 0;font-size:9.5px;letter-spacing:0.08em;text-transform:uppercase;' +
      'color:var(--text-muted,#767e8e);">Findings</div>' + list +
      (a.safeguards ? '<div class="mono" style="margin-top:12px;font-size:9.5px;line-height:1.6;' +
        'color:var(--text-muted,#767e8e);">' + a.safeguards.map(esc).join(' · ') + '</div>' : '');
  }

  function renderMaintenance(data) {
    var box = el('updaterMaintenanceContainer');
    if (!box) return;
    var r = (data && data.runtime) || {};
    box.innerHTML =
      '<p class="mono" style="font-size:11px;line-height:1.6;color:var(--text-muted,#767e8e);margin-bottom:12px;">' +
      'Each action below changes this installation and asks you to confirm first. Nothing runs on its own.</p>' +
      '<div style="display:flex;flex-direction:column;gap:8px;">' +
        button('install_dependencies', 'RESTORE OPTIONAL DEPENDENCIES', {
          confirm: 'Install the optional Python packages from requirements-prism.txt into this runtime?'
        }) +
        button('rebuild_desktop_app', 'REBUILD U1 OS.APP', {
          disabled: r.platform !== 'darwin',
          confirm: 'Rebuild the macOS app from source? This replaces dist/U1 OS.app.'
        }) +
        button('restart_server', 'RESTART WORKSPACE', {
          confirm: 'Restart the workspace now? Every open connection is dropped and the page reconnects.'
        }) +
      '</div>' +
      (r.platform !== 'darwin' ? '<p class="mono" style="margin-top:10px;font-size:10px;' +
        'color:var(--text-muted,#767e8e);">The app rebuild is only available on macOS.</p>' : '');
  }

  function renderChangelog(data) {
    var box = el('updaterChangelogContainer');
    if (!box) return;
    var entries = (data && data.changelog) || [];
    if (!entries.length) {
      box.innerHTML = '<p class="mono" style="font-size:11.5px;color:var(--text-muted,#767e8e);">' +
        'No change history yet.</p>';
      return;
    }
    box.innerHTML = entries.map(function (e) {
      return '<div style="display:flex;gap:14px;padding:7px 0;border-bottom:1px solid rgba(255,255,255,0.05);">' +
        '<span class="mono" style="flex:0 0 62px;font-size:10.5px;color:var(--gold,#e9b44c);">' + esc(e.commit) + '</span>' +
        '<span class="mono" style="flex:1 1 auto;font-size:11.5px;color:var(--text-primary,#e6e9ef);">' + esc(e.subject) + '</span>' +
        '<span class="mono" style="flex:0 0 auto;font-size:10px;color:var(--text-muted,#767e8e);">' + esc(e.when) + '</span>' +
      '</div>';
    }).join('');
  }

  function renderAll(data) {
    state = data;
    renderHealth(data);
    renderRuntime(data);
    renderChannel(data);
    renderAgent(data);
    renderMaintenance(data);
    renderChangelog(data);
  }

  /* ---------------- Refresh & actions ---------------- */

  function refresh(silent) {
    if (busy) return Promise.resolve();
    busy = true;
    return call('get_status').then(function (res) {
      busy = false;
      if (res && res.success) {
        renderAll(res);
      } else if (!silent) {
        toast('Could not read updater status: ' + (res.error || res.message || 'unknown'), 'error');
      }
    });
  }

  var ACTIONS = {
    check_for_updates: { call: 'check_for_updates' },
    apply_update: { call: 'apply_update', payload: { confirmed: true } },
    install_dependencies: { call: 'install_dependencies', payload: { confirmed: true } },
    rebuild_desktop_app: { call: 'rebuild_desktop_app', payload: { confirmed: true } },
    restart_server: { call: 'restart_server', payload: { confirmed: true } },
    agent_scan: { call: 'agent_configure', payload: { mode: 'scan' } },
    agent_pause: { call: 'agent_configure', payload: { mode: 'pause' } },
    agent_resume: { call: 'agent_configure', payload: { mode: 'resume' } },
    capture_baseline: { call: 'capture_baseline', payload: { label: 'manual' } },
    reset_metrics: { call: 'reset_metrics', payload: { confirmed: true } }
  };

  function run(name, node) {
    var spec = ACTIONS[name];
    if (!spec) return;
    var confirmText = node && node.getAttribute('data-confirm');
    if (confirmText && !window.confirm(confirmText)) return;

    var label = node ? node.textContent : '';
    if (node) { node.disabled = true; node.textContent = 'WORKING…'; }

    call(spec.call, spec.payload).then(function (res) {
      if (node) { node.disabled = false; node.textContent = label; }
      var ok = res && res.success;
      toast(res && (res.message || res.error) ? (res.message || res.error)
        : (ok ? 'Done.' : 'That did not complete.'), ok ? 'success' : 'error');
      if (name === 'restart_server' && ok) {
        setTimeout(function () { window.location.reload(); }, 4000);
        return;
      }
      setTimeout(function () { refresh(true); }, name.indexOf('agent') === 0 ? 1200 : 250);
    });
  }

  document.addEventListener('click', function (e) {
    var node = e.target.closest('[data-updater-action]');
    if (node) {
      e.preventDefault();
      run(node.getAttribute('data-updater-action'), node);
      return;
    }
    var nav = e.target.closest('[data-section="' + SECTION + '"]');
    if (nav) setTimeout(function () { refresh(); }, 60);
  });

  function tick() {
    if (isActive()) refresh(true);
  }

  function boot() {
    if (!el('section-' + SECTION)) return;
    if (timer) clearInterval(timer);
    timer = setInterval(tick, POLL_MS);
    if (isActive() || (window.location.hash || '').indexOf(SECTION) > -1) refresh(true);
  }


  /* ---------------- Frontend fault reporting ----------------
   * Browser exceptions are reported to the measurement floor so the health
   * score reflects what actually breaks in the interface, not just on the
   * server. Only the error type, a location and a truncated message are
   * sent — never page content, form values or credentials.
   */
  (function reportFrontendFaults() {
    var sent = 0;
    var MAX_PER_SESSION = 25;

    function report(kind, where, message) {
      if (sent >= MAX_PER_SESSION) return;
      sent++;
      try {
        fetch('/api/telemetry/client', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            kind: String(kind || 'Error').slice(0, 80),
            where: String(where || 'frontend').slice(0, 120),
            message: String(message || '').slice(0, 300)
          })
        }).catch(function () { /* never let reporting break the page */ });
      } catch (e) { /* ignore */ }
    }

    window.addEventListener('error', function (e) {
      var where = (e.filename ? String(e.filename).split('/').pop() : 'window');
      if (e.lineno) where += ':' + e.lineno;
      report(e.error && e.error.name ? e.error.name : 'Error', where, e.message);
    });

    window.addEventListener('unhandledrejection', function (e) {
      var reason = e.reason;
      report(reason && reason.name ? reason.name : 'UnhandledRejection',
             'promise', reason && reason.message ? reason.message : String(reason));
    });
  })();

  window.U1Updater = { refresh: refresh, run: run, state: function () { return state; } };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
