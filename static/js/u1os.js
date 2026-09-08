/**
 * U1 OS // Command Centre controller
 * ------------------------------------------------------------------
 * Sound, motion, interaction and notifications for the workspace shell.
 *
 * Data rule carried over from the measurement floor: every figure shown
 * here comes from the server. Where a source is not connected the panel
 * says so plainly instead of displaying an invented number.
 */
(function () {
  'use strict';

  var $ = function (id) { return document.getElementById(id); };
  var reduced = false;
  try { reduced = matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) {}

  function esc(v) {
    return String(v === null || v === undefined ? '' : v)
      .replace(/[&<>"']/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
      });
  }
  function ls(k, d) { try { var v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) {} }

  /* ================================================================
     1. SOUND — Web Audio synthesis, no audio files
     ================================================================ */
  var Sound = (function () {
    var ctx = null, master = null;
    var on = ls('u1.sound', '0') === '1';
    var vol = parseFloat(ls('u1.vol', '0.22')); if (isNaN(vol)) vol = 0.22;

    function ac() {
      if (navigator.userActivation && !navigator.userActivation.hasBeenActive) return null;
      if (!ctx) {
        var C = window.AudioContext || window.webkitAudioContext;
        if (!C) return null;
        ctx = new C();
        master = ctx.createGain();
        master.gain.value = vol;
        master.connect(ctx.destination);
      }
      if (ctx.state === 'suspended') { try { ctx.resume(); } catch (e) {} }
      return ctx;
    }
    function tone(o) {
      if (!on) return;
      var c = ac(); if (!c) return;
      try {
        var t = c.currentTime + (o.delay || 0), d = o.dur || 0.06;
        var osc = c.createOscillator(), g = c.createGain();
        osc.type = o.type || 'sine';
        osc.frequency.setValueAtTime(o.from, t);
        if (o.to && o.to !== o.from) osc.frequency.exponentialRampToValueAtTime(Math.max(12, o.to), t + d);
        var peak = o.gain === undefined ? 0.045 : o.gain;
        g.gain.setValueAtTime(0.0001, t);
        g.gain.exponentialRampToValueAtTime(Math.max(0.0002, peak), t + Math.min(0.012, d * 0.3));
        g.gain.exponentialRampToValueAtTime(0.0001, t + d);
        osc.connect(g); g.connect(master);
        osc.start(t); osc.stop(t + d + 0.02);
      } catch (e) {}
    }
    function noise(o) {
      if (!on) return;
      var c = ac(); if (!c) return;
      try {
        var d = o.dur || 0.06, n = Math.max(1, Math.floor(c.sampleRate * d));
        var buf = c.createBuffer(1, n, c.sampleRate), data = buf.getChannelData(0);
        for (var i = 0; i < n; i++) data[i] = (Math.random() * 2 - 1) * (1 - i / n);
        var src = c.createBufferSource(); src.buffer = buf;
        var f = c.createBiquadFilter(); f.type = o.filter || 'bandpass';
        f.frequency.value = o.freq || 2000; f.Q.value = o.q || 1.1;
        var g = c.createGain(); g.gain.value = o.gain === undefined ? 0.03 : o.gain;
        src.connect(f); f.connect(g); g.connect(master);
        src.start(c.currentTime + (o.delay || 0));
      } catch (e) {}
    }
    function arp(freqs, step, dur, gain, type) {
      freqs.forEach(function (f, i) {
        tone({ from: f, to: f, dur: dur || 0.09, gain: gain || 0.04, type: type || 'sine', delay: i * (step || 0.06) });
      });
    }
    var api = {
      enabled: function () { return on; },
      volume: function () { return vol; },
      setVolume: function (v) { vol = Math.max(0, Math.min(1, +v || 0)); lsSet('u1.vol', vol); if (master) master.gain.value = vol; return vol; },
      toggle: function () { on = !on; lsSet('u1.sound', on ? '1' : '0'); return on; },
      unlock: ac,
      tap:    function () { tone({ from: 420, to: 220, dur: 0.03, gain: 0.038 }); },
      hover:  function () { tone({ from: 1750, to: 1750, dur: 0.012, gain: 0.011 }); },
      nav:    function () { tone({ from: 520, to: 300, dur: 0.05, gain: 0.038, type: 'triangle' }); noise({ dur: 0.05, freq: 3400, gain: 0.010 }); },
      open:   function () { tone({ from: 300, to: 820, dur: 0.13, gain: 0.038 }); },
      close:  function () { tone({ from: 820, to: 300, dur: 0.11, gain: 0.032 }); },
      ok:     function () { arp([523.25, 659.25, 783.99], 0.055, 0.1, 0.04); },
      warn:   function () { tone({ from: 660, to: 660, dur: 0.09, gain: 0.04, type: 'triangle' }); tone({ from: 660, to: 495, dur: 0.14, gain: 0.04, type: 'triangle', delay: 0.12 }); },
      bad:    function () { tone({ from: 240, to: 90, dur: 0.24, gain: 0.05, type: 'sawtooth' }); },
      ping:   function () { tone({ from: 880, to: 880, dur: 0.1, gain: 0.032 }); tone({ from: 1174.7, to: 1174.7, dur: 0.13, gain: 0.026, delay: 0.02 }); },
      boot:   function () { arp([196, 261.63, 329.63, 392, 523.25, 659.25], 0.075, 0.24, 0.036); noise({ dur: 0.55, freq: 380, filter: 'lowpass', gain: 0.018, delay: 0.04 }); },
      tick:   function () { tone({ from: 1500, to: 1200, dur: 0.016, gain: 0.02, type: 'square' }); }
    };
    return api;
  })();

  /* ================================================================
     2. NOTIFICATIONS + TOASTS
     ================================================================ */
  var Notify = (function () {
    var feed = [];
    var CAP = 60;
    try { feed = JSON.parse(ls('u1.feed', '[]')) || []; } catch (e) { feed = []; }

    var TONE = {
      info:  { c: 'var(--cyan)',  s: 'ping' },
      ok:    { c: 'var(--mint)',  s: 'ok' },
      warn:  { c: 'var(--amber)', s: 'warn' },
      bad:   { c: 'var(--rose)',  s: 'bad' }
    };

    function save() { try { lsSet('u1.feed', JSON.stringify(feed.slice(0, CAP))); } catch (e) {} }
    function rel(ts) {
      var s = Math.max(0, (Date.now() - ts) / 1000);
      if (s < 20) return 'just now';
      if (s < 60) return Math.floor(s) + 's ago';
      if (s < 3600) return Math.floor(s / 60) + 'm ago';
      if (s < 86400) return Math.floor(s / 3600) + 'h ago';
      return Math.floor(s / 86400) + 'd ago';
    }
    function unread() { return feed.filter(function (n) { return !n.read; }).length; }

    function paintPip() {
      var pip = $('bellPip'); if (!pip) return;
      var n = unread();
      pip.hidden = n === 0;
      pip.textContent = n > 99 ? '99+' : n;
    }
    function paintList() {
      var ul = $('notifList'); if (!ul) return;
      if (!feed.length) {
        ul.innerHTML = '<li style="display:block;padding:26px;text-align:center;color:var(--ink-3);' +
          'font-family:var(--mono);font-size:11px">Nothing yet. Activity will appear here.</li>';
        return;
      }
      ul.innerHTML = feed.slice(0, 40).map(function (n) {
        var t = TONE[n.tone] || TONE.info;
        return '<li><i style="color:' + t.c + ';background:' + t.c + ';' + (n.read ? 'opacity:.3;box-shadow:none' : '') + '"></i>' +
          '<div><div class="m">' + esc(n.msg) + '</div><div class="w">' + esc(n.src || 'System') + ' · ' + rel(n.at) + '</div></div></li>';
      }).join('');
    }

    function toast(msg, tone) {
      var box = $('toasts'); if (!box) return;
      var el = document.createElement('div');
      el.className = 'toast' + (tone === 'ok' ? ' ok' : tone === 'bad' ? ' bad' : '');
      el.textContent = msg;
      el.addEventListener('click', function () { dismiss(el); });
      box.appendChild(el);
      while (box.children.length > 4) dismiss(box.firstChild);
      setTimeout(function () { dismiss(el); }, tone === 'bad' ? 6500 : 4200);
    }
    function dismiss(el) {
      if (!el || el.classList.contains('leave')) return;
      el.classList.add('leave');
      setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 280);
    }

    function push(msg, opts) {
      opts = opts || {};
      var tone = TONE[opts.tone] ? opts.tone : 'info';
      feed.unshift({ msg: String(msg), tone: tone, src: opts.src || 'System', at: Date.now(), read: false });
      if (feed.length > CAP) feed.length = CAP;
      save(); paintPip(); paintList();
      if (opts.quiet !== true) toast(String(msg), tone);
      if (opts.silent !== true && Sound[TONE[tone].s]) Sound[TONE[tone].s]();
      return true;
    }

    return {
      push: push, toast: toast, paint: function () { paintPip(); paintList(); },
      readAll: function () { feed.forEach(function (n) { n.read = true; }); save(); paintPip(); paintList(); },
      count: unread
    };
  })();
  window.u1notify = Notify.push;

  /* ================================================================
     3. SERVER
     ================================================================ */
  function api(service, action, payload) {
    if (window.U1Workspaces) return window.U1Workspaces.action(service, action, payload);
    return fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service: service, action: action, payload: payload || {} })
    }).then(function (r) { return r.json(); })
      .catch(function (e) { return { success: false, error: e.message || 'unreachable' }; });
  }
  function state() {
    return fetch('/api/state').then(function (r) { return r.json(); })
      .catch(function () { return null; });
  }

  /* ================================================================
     4. CANVAS PIECES
     ================================================================ */
  function fit(cv) {
    var d = window.devicePixelRatio || 1;
    var r = cv.getBoundingClientRect();
    cv.width = Math.max(1, Math.round(r.width * d));
    cv.height = Math.max(1, Math.round(r.height * d));
    var g = cv.getContext('2d');
    g.setTransform(d, 0, 0, d, 0, 0);
    return { g: g, w: r.width, h: r.height };
  }

  /* --- starfield --- */
  function stars() {
    var cv = $('stars'); if (!cv) return;
    var pts = [];
    function build() {
      var c = fit(cv);
      pts = [];
      var n = Math.round((c.w * c.h) / 9000);
      for (var i = 0; i < n; i++) {
        pts.push({ x: Math.random() * c.w, y: Math.random() * c.h,
                   r: Math.random() * 1.15 + 0.25, p: Math.random() * Math.PI * 2,
                   s: 0.4 + Math.random() * 1.1 });
      }
      return c;
    }
    var c = build();
    window.addEventListener('resize', function () { c = build(); });
    var t = 0;
    (function draw() {
      t += 0.016;
      c.g.clearRect(0, 0, c.w, c.h);
      for (var i = 0; i < pts.length; i++) {
        var p = pts[i];
        var a = reduced ? 0.5 : 0.32 + 0.32 * Math.sin(t * p.s + p.p);
        c.g.beginPath();
        c.g.arc(p.x, p.y, p.r, 0, Math.PI * 2);
        c.g.fillStyle = 'rgba(180,225,255,' + a.toFixed(3) + ')';
        c.g.fill();
      }
      requestAnimationFrame(draw);
    })();
  }

  /* --- rotating earth: dot-mapped landmasses, city lights, HUD arcs --- */
  function globe() {
    var cv = $('globe'); if (!cv) return;
    var c = fit(cv);
    window.addEventListener('resize', function () { c = fit(cv); });

    /* Coarse land mask as lon/lat boxes (degrees). Enough resolution that
       the sphere reads as Earth without shipping an image asset. */
    var LAND = [
      [-168,-52,72,84],   // North America bulk
      [-130,-60,25,50],   // N America south
      [-92,-75,8,20],     // Central America
      [-82,-35,-56,12],   // South America
      [-25,60,35,71],     // Europe
      [-18,52,-35,37],    // Africa
      [26,60,12,42],      // Middle East
      [60,150,8,55],      // Asia south + China
      [60,180,50,75],     // Siberia
      [95,141,-11,7],     // Indonesia
      [113,154,-39,-11],  // Australia
      [166,179,-47,-34],  // New Zealand
      [-73,-12,59,83],    // Greenland
      [-180,180,-90,-63]  // Antarctica
    ];
    function isLand(lonDeg, latDeg) {
      for (var i = 0; i < LAND.length; i++) {
        var b = LAND[i];
        if (lonDeg >= b[0] && lonDeg <= b[1] && latDeg >= b[2] && latDeg <= b[3]) return true;
      }
      return false;
    }

    var pts = [], cities = [];
    var RINGS = 46;
    for (var i = 1; i < RINGS; i++) {
      var latDeg = 90 - (180 * i) / RINGS;
      var lat = latDeg * Math.PI / 180;
      var count = Math.max(8, Math.round(Math.cos(lat) * 96));
      for (var j = 0; j < count; j++) {
        var lonDeg = -180 + (360 * j) / count;
        var lon = lonDeg * Math.PI / 180;
        var land = isLand(lonDeg, latDeg);
        var p = [Math.cos(lat) * Math.cos(lon), Math.sin(lat), Math.cos(lat) * Math.sin(lon), land];
        pts.push(p);
        // sparse warm city lights on land
        if (land && Math.random() < 0.09) cities.push(p);
      }
    }

    var rot = 2.1;
    (function draw() {
      rot += reduced ? 0 : 0.0016;
      var w = c.w, h = c.h;
      var R = Math.min(w, h) * 0.405;
      var cx = w / 2, cy = h / 2;
      c.g.clearRect(0, 0, w, h);

      /* outer atmosphere bloom */
      var bloom = c.g.createRadialGradient(cx, cy, R * 0.9, cx, cy, R * 1.65);
      bloom.addColorStop(0, 'rgba(90,200,255,.26)');
      bloom.addColorStop(0.45, 'rgba(60,160,255,.10)');
      bloom.addColorStop(1, 'rgba(40,120,255,0)');
      c.g.fillStyle = bloom;
      c.g.beginPath(); c.g.arc(cx, cy, R * 1.65, 0, Math.PI * 2); c.g.fill();

      /* ocean body with terminator shading */
      var body = c.g.createRadialGradient(cx - R * 0.38, cy - R * 0.4, R * 0.06, cx, cy, R);
      body.addColorStop(0, 'rgba(38,96,168,.98)');
      body.addColorStop(0.55, 'rgba(14,44,92,.98)');
      body.addColorStop(1, 'rgba(4,10,26,.99)');
      c.g.save();
      c.g.beginPath(); c.g.arc(cx, cy, R, 0, Math.PI * 2); c.g.clip();
      c.g.fillStyle = body; c.g.fillRect(cx - R, cy - R, R * 2, R * 2);

      var sr = Math.sin(rot), cr = Math.cos(rot);
      function project(p) {
        var x = p[0] * cr - p[2] * sr;
        var z = p[0] * sr + p[2] * cr;
        return [cx + x * R, cy + p[1] * R * -1, z];
      }

      /* landmass dots */
      for (var k = 0; k < pts.length; k++) {
        var p = pts[k], q = project(p);
        if (q[2] < 0) continue;
        var lightSide = Math.max(0, Math.min(1, (q[2] * 0.55 + 0.55)));
        if (p[3]) {
          c.g.beginPath();
          c.g.arc(q[0], q[1], 1.15, 0, Math.PI * 2);
          c.g.fillStyle = 'rgba(120,215,255,' + (0.30 + lightSide * 0.55).toFixed(3) + ')';
          c.g.fill();
        } else if (k % 3 === 0) {
          c.g.beginPath();
          c.g.arc(q[0], q[1], 0.6, 0, Math.PI * 2);
          c.g.fillStyle = 'rgba(70,140,210,' + (0.10 + lightSide * 0.18).toFixed(3) + ')';
          c.g.fill();
        }
      }

      /* warm city lights, brighter toward the night edge */
      for (var m = 0; m < cities.length; m++) {
        var q2 = project(cities[m]);
        if (q2[2] < 0.02) continue;
        var night = Math.max(0, 1 - (q2[2] + 0.25));
        var a = 0.35 + night * 0.6;
        c.g.beginPath();
        c.g.arc(q2[0], q2[1], 1.15, 0, Math.PI * 2);
        c.g.fillStyle = 'rgba(255,198,120,' + a.toFixed(3) + ')';
        c.g.fill();
      }

      /* limb darkening toward the edge */
      var limb = c.g.createRadialGradient(cx, cy, R * 0.62, cx, cy, R);
      limb.addColorStop(0, 'rgba(0,0,0,0)');
      limb.addColorStop(1, 'rgba(2,5,14,.72)');
      c.g.fillStyle = limb; c.g.fillRect(cx - R, cy - R, R * 2, R * 2);
      c.g.restore();

      /* bright rim */
      c.g.beginPath(); c.g.arc(cx, cy, R, 0, Math.PI * 2);
      c.g.strokeStyle = 'rgba(150,235,255,.85)'; c.g.lineWidth = 1.4;
      c.g.shadowColor = 'rgba(90,205,255,.9)'; c.g.shadowBlur = 20;
      c.g.stroke(); c.g.shadowBlur = 0;

      /* HUD arc brackets */
      function arcBracket(radius, from, to, colour, width) {
        c.g.beginPath();
        c.g.arc(cx, cy, radius, from, to);
        c.g.strokeStyle = colour; c.g.lineWidth = width || 1.5; c.g.lineCap = 'round';
        c.g.stroke();
      }
      var swing = reduced ? 0 : Math.sin(rot * 0.7) * 0.12;
      arcBracket(R * 1.10, -1.55 + swing, -0.62 + swing, 'rgba(110,225,255,.75)', 2);
      arcBracket(R * 1.10, 1.62 + swing, 2.42 + swing, 'rgba(110,225,255,.45)', 2);
      arcBracket(R * 1.20, -1.15 + swing, -0.86 + swing, 'rgba(150,240,255,.9)', 3);
      arcBracket(R * 1.28, 0.42 - swing, 1.02 - swing, 'rgba(120,160,255,.35)', 1.5);

      /* equatorial orbit ellipse */
      c.g.save();
      c.g.translate(cx, cy);
      c.g.rotate(0.42);
      c.g.beginPath();
      c.g.ellipse(0, 0, R * 1.32, R * 0.30, 0, 0, Math.PI * 2);
      c.g.strokeStyle = 'rgba(140,200,255,.22)'; c.g.lineWidth = 1; c.g.stroke();
      c.g.restore();

      requestAnimationFrame(draw);
    })();
  }

  /* --- sparkline --- */
  function sparkline(cv, series, colour) {
    var c = fit(cv);
    var w = c.w, h = c.h;
    c.g.clearRect(0, 0, w, h);
    if (!series || series.length < 2) {
      c.g.fillStyle = 'rgba(159,178,206,.4)';
      c.g.font = '9px ui-monospace, monospace';
      c.g.fillText('no activity recorded', 2, h / 2 + 3);
      return;
    }
    var max = Math.max.apply(null, series), min = Math.min.apply(null, series);
    var span = (max - min) || 1;
    var pt = function (i) {
      return [ (i / (series.length - 1)) * (w - 2) + 1,
               h - 3 - ((series[i] - min) / span) * (h - 8) ];
    };
    var grad = c.g.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, colour.replace('1)', '.34)'));
    grad.addColorStop(1, colour.replace('1)', '0)'));
    c.g.beginPath();
    c.g.moveTo(1, h);
    for (var i = 0; i < series.length; i++) { var p = pt(i); c.g.lineTo(p[0], p[1]); }
    c.g.lineTo(w - 1, h); c.g.closePath();
    c.g.fillStyle = grad; c.g.fill();
    c.g.beginPath();
    for (var j = 0; j < series.length; j++) { var q = pt(j); j ? c.g.lineTo(q[0], q[1]) : c.g.moveTo(q[0], q[1]); }
    c.g.strokeStyle = colour; c.g.lineWidth = 1.6; c.g.lineJoin = 'round'; c.g.stroke();
    var last = pt(series.length - 1);
    c.g.beginPath(); c.g.arc(last[0], last[1], 2.4, 0, Math.PI * 2);
    c.g.fillStyle = colour; c.g.fill();
  }

  /* --- radial gauge --- */
  function gauge(cv, pct, colour) {
    if (!cv || cv.clientWidth <= 10 || cv.clientHeight <= 10) return;
    var c = fit(cv);
    var w = c.w, h = c.h, R = Math.min(w, h) / 2 - 5;
    if (!Number.isFinite(R) || R <= 0) return;
    var cx = w / 2, cy = h / 2;
    c.g.clearRect(0, 0, w, h);
    c.g.beginPath(); c.g.arc(cx, cy, R, 0, Math.PI * 2);
    c.g.strokeStyle = 'rgba(255,255,255,.075)'; c.g.lineWidth = 4.5; c.g.stroke();
    if (pct === null || pct === undefined) return;
    var end = -Math.PI / 2 + (Math.PI * 2 * Math.max(0, Math.min(100, pct))) / 100;
    c.g.beginPath(); c.g.arc(cx, cy, R, -Math.PI / 2, end);
    c.g.strokeStyle = colour; c.g.lineWidth = 4.5; c.g.lineCap = 'round';
    c.g.shadowColor = colour; c.g.shadowBlur = 9; c.g.stroke(); c.g.shadowBlur = 0;
  }

  /* --- trend line --- */
  function trend(cv, series) {
    var c = fit(cv);
    var w = c.w, h = c.h;
    c.g.clearRect(0, 0, w, h);
    c.g.strokeStyle = 'rgba(255,255,255,.05)'; c.g.lineWidth = 1;
    for (var k = 1; k < 4; k++) {
      var y = (h / 4) * k;
      c.g.beginPath(); c.g.moveTo(0, y); c.g.lineTo(w, y); c.g.stroke();
    }
    if (!series || series.length < 2) {
      c.g.fillStyle = 'rgba(159,178,206,.45)';
      c.g.font = '10px ui-monospace, monospace';
      c.g.fillText('Collecting samples…', 4, h / 2 + 3);
      return;
    }
    var max = Math.max.apply(null, series) || 1;
    c.g.beginPath();
    for (var i = 0; i < series.length; i++) {
      var x = (i / (series.length - 1)) * w;
      var yy = h - 4 - (series[i] / max) * (h - 10);
      i ? c.g.lineTo(x, yy) : c.g.moveTo(x, yy);
    }
    c.g.strokeStyle = 'rgba(79,216,255,.95)'; c.g.lineWidth = 1.8; c.g.lineJoin = 'round'; c.g.stroke();
    c.g.lineTo(w, h); c.g.lineTo(0, h); c.g.closePath();
    var gd = c.g.createLinearGradient(0, 0, 0, h);
    gd.addColorStop(0, 'rgba(79,216,255,.22)'); gd.addColorStop(1, 'rgba(79,216,255,0)');
    c.g.fillStyle = gd; c.g.fill();
  }

  function countUp(el, to, opts) {
    opts = opts || {};
    var from = opts.from || 0, dur = opts.dur || 850, dec = opts.dec || 0;
    if (reduced) { el.textContent = to.toFixed(dec) + (opts.suffix || ''); return; }
    var t0 = null;
    function step(ts) {
      if (t0 === null) t0 = ts;
      var p = Math.min(1, (ts - t0) / dur), e = 1 - Math.pow(1 - p, 3);
      el.textContent = (from + (to - from) * e).toFixed(dec) + (opts.suffix || '');
      if (p < 1) requestAnimationFrame(step);
    }
    requestAnimationFrame(step);
  }

  window.U1 = {
    sound: Sound, notify: Notify, api: api, state: state,
    sparkline: sparkline, gauge: gauge, trend: trend, countUp: countUp,
    esc: esc, reduced: reduced,
    // Ambient canvas scenes, started once the shell has booted.
    scenes: function () { if (window.U1Motion) window.U1Motion.start(); }
  };
})();

/* ==================================================================
   U1 OS // shell wiring (a): icons, nav model, view scaffolding
   ================================================================== */
(function () {
  'use strict';
  var U = window.U1, esc = U.esc;

  var ICON = {
    home:'<path d="M3 11 12 3l9 8"/><path d="M5 10v10h14V10"/>',
    ai:'<circle cx="12" cy="12" r="3"/><path d="M12 2v4M12 18v4M2 12h4M18 12h4M4.9 4.9l2.8 2.8M16.3 16.3l2.8 2.8M19.1 4.9l-2.8 2.8M7.7 16.3l-2.8 2.8"/>',
    projects:'<path d="M3 7h6l2 2h10v11H3z"/>',
    files:'<path d="M4 4h6l2 2h8v14H4z"/><path d="M4 11h16"/>',
    integrations:'<path d="M12 2 3 7v10l9 5 9-5V7z"/><path d="M12 22V12M3 7l9 5 9-5"/>',
    calendar:'<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M8 3v4M16 3v4M3 10h18"/>',
    tasks:'<path d="m4 12 4 4 8-9"/><path d="M20 6v14H4"/>',
    notes:'<path d="M5 3h14v18H5z"/><path d="M9 8h6M9 12h6M9 16h4"/>',
    media:'<rect x="3" y="5" width="18" height="14" rx="2"/><path d="m10 9 5 3-5 3z"/>',
    automation:'<circle cx="6" cy="6" r="3"/><circle cx="18" cy="18" r="3"/><path d="M9 6h6a3 3 0 0 1 3 3v6"/>',
    system:'<rect x="4" y="4" width="16" height="16" rx="2"/><path d="M9 9h6v6H9z"/>',
    updater:'<path d="M21 2v6h-6"/><path d="M3 12a9 9 0 0 1 15-6.7L21 8"/><path d="M3 22v-6h6"/><path d="M21 12a9 9 0 0 1-15 6.7L3 16"/>',
    settings:'<circle cx="12" cy="12" r="3"/><path d="M4 12a8 8 0 0 1 .6-3l-1.4-2 2.8-2.8 2 1.4A8 8 0 0 1 11 4.6L11.4 2h3.2L15 4.6a8 8 0 0 1 3 1.2l2-1.4L22.8 7l-1.4 2a8 8 0 0 1 0 6l1.4 2-2.8 2.8-2-1.4a8 8 0 0 1-3 1.2L14.6 22h-3.2L11 19.4a8 8 0 0 1-3-1.2l-2 1.4L3.2 17l1.4-2a8 8 0 0 1-.6-3z"/>',
    code:'<path d="m8 8-4 4 4 4M16 8l4 4-4 4"/>',
    design:'<path d="M12 3 3 12l9 9 9-9z"/><circle cx="12" cy="12" r="2.5"/>',
    web:'<circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3a15 15 0 0 1 0 18 15 15 0 0 1 0-18"/>'
  };

  function svg(name) {
    return '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" ' +
      'stroke-linecap="round" stroke-linejoin="round">' + (ICON[name] || ICON.home) + '</svg>';
  }

  var NAV = [
    { id:'home', label:'Home', icon:'home' },
    { id:'ai', label:'AI Command', icon:'ai' },
    { id:'projects', label:'Projects', icon:'projects' },
    { id:'files', label:'Files & Drive', icon:'files' },
    { id:'integrations', label:'Integrations', icon:'integrations' },
    { id:'calendar', label:'Calendar', icon:'calendar' },
    { id:'tasks', label:'Tasks', icon:'tasks' },
    { id:'notes', label:'Notes', icon:'notes' },
    { id:'media', label:'Media', icon:'media' },
    { id:'automation', label:'Automation', icon:'automation' },
    { sep:true },
    { id:'system', label:'System', icon:'system' },
    { id:'updater', label:'Updater', icon:'updater' },
    { id:'settings', label:'Settings', icon:'settings' }
  ];

  var DOCK = [
    { id:'ai', label:'AI', icon:'ai' },
    { id:'system', label:'Code', icon:'code' },
    { id:'media', label:'Design', icon:'design' },
    { id:'files', label:'Files', icon:'files' },
    { orb:true },
    { id:'integrations', label:'Web', icon:'web' },
    { id:'notes', label:'Notes', icon:'notes' },
    { id:'projects', label:'Projects', icon:'projects' },
    { id:'settings', label:'Settings', icon:'settings' }
  ];

  var VIEWS = {
    ai:{ t:'AI Command', s:'Prompt console and provider handoffs. Providers come from your saved configuration — none is assumed connected.' },
    projects:{ t:'Projects', s:'Work tracked in this workspace.' },
    files:{ t:'Files & Drive', s:'Local workspace files and any connected drive.' },
    integrations:{ t:'Integrations', s:'Accounts and services this workspace can reach.' },
    calendar:{ t:'Calendar', s:'Your agenda, once a calendar provider is connected.' },
    tasks:{ t:'Tasks', s:'Things to do across the workspace.' },
    notes:{ t:'Notes', s:'Local notes and the research casebook.' },
    media:{ t:'Media', s:'Studio output and the media library.' },
    automation:{ t:'Automation', s:'Scheduled jobs and background workers.' },
    system:{ t:'System', s:'Runtime, services and measured performance.' },
    updater:{ t:'Updater', s:'Version, update channel, improvement agent and maintenance.' },
    settings:{ t:'Settings', s:'Preferences, sound, motion and configuration.' }
  };

  U.icons = { svg: svg, set: ICON };
  U.model = { NAV: NAV, DOCK: DOCK, VIEWS: VIEWS };
})();

/* ==================================================================
   U1 OS // shell wiring (b): panel renderers
   Every panel prefers real server data and states plainly when a
   source is absent, rather than filling the space with a number.
   ================================================================== */
(function () {
  'use strict';
  var U = window.U1, esc = U.esc;
  var $ = function (id) { return document.getElementById(id); };

  function title(k) {
    return String(k).replace(/_/g, ' ').replace(/\b\w/g, function (c) { return c.toUpperCase(); });
  }

  function toolCards(st) {
    var services = (st && st.services) || {};
    var box = $('tools'); if (!box) return;
    var defs = [
      { k:'ai_workbench', name:'ChatGPT / Codex', role:'Research · Code · Create', glyph:'G', a:'#10A37F', b:'#0B6E56', colour:'rgba(87,231,181,1)', go:'ai' },
      { k:'ai_workbench', name:'Claude',          role:'Analyse · Plan · Write',   glyph:'C', a:'#D97757', b:'#A44F33', colour:'rgba(255,160,110,1)', go:'ai' },
      { k:'deploy',       name:'Antigravity',     role:'Build · Deploy · Automate',glyph:'A', a:'#A98BFF', b:'#6D4BD8', colour:'rgba(169,139,255,1)', go:'automation' },
      { k:'studio',       name:'Canva',           role:'Design · Visualise · Present', glyph:'C', a:'#4FD8FF', b:'#1E7FB8', colour:'rgba(79,216,255,1)', go:'media' }
    ];
    box.innerHTML = defs.map(function (d, i) {
      var live = !!(services[d.k] && services[d.k].configured);
      return '<article class="card tool" data-go="' + d.go + '" style="animation-delay:' + (0.05 * i).toFixed(2) + 's">' +
        '<div class="th"><span class="glyph" style="background:linear-gradient(140deg,' + d.a + ',' + d.b + ')">' + d.glyph + '</span>' +
        '<div><h4>' + esc(d.name) + '</h4><div class="state' + (live ? ' live' : '') + '"><i></i>' +
        (live ? 'Connected' : 'Not connected') + '</div></div></div>' +
        '<p class="role">' + esc(d.role) + '</p><canvas data-spark="' + i + '"></canvas></article>';
    }).join('') +
    '<article class="card tool add" data-go="integrations" style="animation-delay:.22s"><div><span>+</span>Add tool</div></article>';

    // Sparklines are drawn only where activity was actually measured.
    U.api('updater', 'get_metrics', {}).then(function (m) {
      var eps = (m && m.requests && m.requests.endpoints) || [];
      defs.forEach(function (d, i) {
        var cv = box.querySelector('[data-spark="' + i + '"]');
        if (!cv) return;
        var row = eps[i % Math.max(1, eps.length)];
        var series = row && row.samples > 1
          ? [row.p50_ms, (row.p50_ms + row.p95_ms) / 2, row.p95_ms, row.max_ms].filter(function (v) { return v !== null && v !== undefined; })
          : null;
        U.sparkline(cv, series && series.length > 1 ? series : null, d.colour);
      });
    });
  }

  function projects(st) {
    var box = $('projects'); if (!box) return;
    var services = (st && st.services) || {};
    var keys = Object.keys(services);
    if (!keys.length) {
      box.innerHTML = '<div class="empty"><b>No services reporting</b>The server returned no subsystem state.</div>';
      return;
    }
    var live = keys.filter(function (k) { return services[k].configured; });
    box.innerHTML = keys.slice(0, 5).map(function (k) {
      var s = services[k];
      return '<div class="prow"><span class="ico">' + (s.configured ? '◆' : '◇') + '</span>' +
        '<div class="body"><div class="t">' + esc(title(k)) + '</div>' +
        '<div class="s">' + esc(s.status || 'unknown') + '</div>' +
        '<div class="meter"><i data-w="' + (s.configured ? 100 : 8) + '"></i></div></div>' +
        '<span class="pct">' + (s.configured ? 'live' : 'setup') + '</span></div>';
    }).join('') +
    '<div style="font-family:var(--mono);font-size:9.5px;color:var(--ink-3);margin-top:5px">' +
    live.length + ' of ' + keys.length + ' subsystems configured</div>';
    setTimeout(function () {
      box.querySelectorAll('.meter i').forEach(function (i) { i.style.width = i.dataset.w + '%'; });
    }, 60);
  }

  var trendSeries = [];
  function system() {
    U.api('updater', 'get_metrics', {}).then(function (m) {
      var res = (m && m.resources) || {}, req = (m && m.requests) || {};
      var gs = [
        { lab:'CPU',  pct: res.cpu_percent, text: res.cpu_percent === null || res.cpu_percent === undefined ? null : Math.round(res.cpu_percent) + '%', colour:'#4FD8FF' },
        { lab:'MEM',  pct: (res.rss_mb === null || res.rss_mb === undefined) ? null : Math.min(100, res.rss_mb / 5.12), text: (res.rss_mb === null || res.rss_mb === undefined) ? null : Math.round(res.rss_mb) + 'M', colour:'#A98BFF' },
        { lab:'REQ',  pct: req.total ? Math.min(100, req.total) : null, text: req.total === undefined ? null : String(req.total), colour:'#57E7B5' },
        { lab:'ERR',  pct: req.error_rate_pct, text: (req.error_rate_pct === null || req.error_rate_pct === undefined) ? null : req.error_rate_pct.toFixed(1) + '%', colour:'#FF6B8A' }
      ];
      var box = $('gauges'); if (!box) return;
      box.innerHTML = gs.map(function (g, i) {
        return '<div class="gauge"><div class="ring"><canvas data-g="' + i + '"></canvas>' +
          '<span class="val" style="color:' + (g.text === null ? 'var(--ink-4)' : g.colour) + '">' +
          esc(g.text === null ? '—' : g.text) + '</span></div><div class="lab">' + g.lab + '</div></div>';
      }).join('');
      gs.forEach(function (g, i) {
        var cv = box.querySelector('[data-g="' + i + '"]'); if (!cv) return;
        if (g.pct === null || g.pct === undefined) { U.gauge(cv, null, g.colour); return; }
        if (U.reduced) { U.gauge(cv, g.pct, g.colour); return; }
        var t0 = null;
        (function anim(ts) {
          if (t0 === null) t0 = ts;
          var p = Math.min(1, (ts - t0) / 900);
          U.gauge(cv, g.pct * (1 - Math.pow(1 - p, 3)), g.colour);
          if (p < 1) requestAnimationFrame(anim);
        })();
      });

      if (req.slowest_p95_ms !== null && req.slowest_p95_ms !== undefined) {
        trendSeries.push(req.slowest_p95_ms);
        if (trendSeries.length > 40) trendSeries.shift();
      }
      if ($('trend')) U.trend($('trend'), trendSeries.length > 1 ? trendSeries : null);

      var tag = $('sysTag');
      if (tag) {
        var er = req.error_rate_pct;
        tag.textContent = (er === null || er === undefined) ? 'NO DATA'
          : (er === 0 ? 'ALL OPERATIONAL' : er.toFixed(1) + '% ERRORS');
        tag.className = 'tag ' + ((er === null || er === undefined) ? 'idle' : er === 0 ? 'ok' : 'warn');
      }
      if ($('sysFoot')) {
        $('sysFoot').innerHTML =
          '<div>Startup<b>' + ((m.startup_ms === null || m.startup_ms === undefined) ? 'NOT MEASURED' : m.startup_ms + ' ms') + '</b></div>' +
          '<div>Uptime<b>' + (m.uptime_seconds === undefined ? '—' : Math.round(m.uptime_seconds) + ' s') + '</b></div>' +
          '<div>Requests<b>' + (req.total === undefined ? '—' : req.total) + '</b></div>';
      }
    });
  }

  function weather(st) {
    var box = $('weather'); if (!box) return;
    var intel = st && st.services && st.services.intelligence;
    var w = intel && intel.data ? intel.data.weather : null;
    if (!w) {
      box.innerHTML = '<div class="empty"><b>No weather source</b>Connect a provider in Integrations.</div>';
      return;
    }
    box.innerHTML =
      '<div class="place">' + esc(w.city || 'Local') + '</div>' +
      '<div class="wx" style="margin-top:9px">' +
      '<svg class="sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round">' +
      '<circle cx="12" cy="12" r="4.2"/><path d="M12 2v3M12 19v3M2 12h3M19 12h3M4.9 4.9 7 7M17 17l2.1 2.1M19.1 4.9 17 7M7 17l-2.1 2.1"/></svg>' +
      '<div><div class="deg">' + esc(w.temp_c) + '°C</div><div class="cond">' + esc(w.condition || '') + '</div></div></div>' +
      '<div style="display:flex;gap:13px;margin-top:11px;font-family:var(--mono);font-size:10px;color:var(--ink-3)">' +
      '<span>Feels ' + esc(w.feels_like || '—') + '</span><span>Hum ' + esc(w.humidity || '—') + '</span><span>Wind ' + esc(w.wind || '—') + '</span></div>';
  }

  function agenda(st) {
    var comms = st && st.services && st.services.comms;
    var cal = comms && comms.data ? comms.data.calendar : null;
    var events = (cal && (cal.events || cal.today)) || [];
    var html;
    if (!comms || !comms.configured || !events.length) {
      html = '<div class="empty"><b>No calendar connected</b>Connect a calendar provider and today’s agenda appears here.</div>';
    } else {
      var tones = ['var(--cyan)', 'var(--amber)', 'var(--violet)', 'var(--mint)'];
      html = events.slice(0, 5).map(function (e, i) {
        return '<div class="ag"><i class="dotm" style="color:' + tones[i % 4] + ';background:' + tones[i % 4] + '"></i>' +
          '<span class="tt">' + esc(e.title || e.summary || 'Event') + '</span>' +
          '<span class="hh">' + esc(e.time || e.start || '') + '</span></div>';
      }).join('');
    }
    if ($('agenda')) $('agenda').innerHTML = html;
    if ($('agendaMini')) $('agendaMini').innerHTML = html;
  }

  function integrations(st) {
    var box = $('integrations'); if (!box) return;
    var services = (st && st.services) || {};
    var glyphs = { intelligence:'◎', comms:'✉', finance:'$', crypto:'◈', ai_workbench:'✧',
                   studio:'▶', deploy:'⤴', osint:'⌕', gaming:'◉', settings:'⚙', updater:'⟳' };
    var rows = Object.keys(services).map(function (k) {
      var s = services[k];
      return '<div class="intg"><span class="gl">' + (glyphs[k] || '·') + '</span>' +
        '<span class="nm">' + esc(title(k)) + '</span>' +
        (s.configured ? '<span class="st on">Connected</span>'
                      : '<span class="st off" data-go="integrations">Connect</span>') + '</div>';
    }).join('');
    box.innerHTML = rows || '<div class="empty">No subsystems reported.</div>';
  }

  function healthMini() {
    U.api('updater', 'get_health', {}).then(function (h) {
      var box = $('healthMini'); if (!box) return;
      if (!h || h.score === null || h.score === undefined) {
        box.innerHTML = '<div class="empty"><b>NOT MEASURED</b>' +
          esc((h && h.note) || 'Nothing has been measured yet.') + '</div>';
        return;
      }
      var comps = h.components || {};
      box.innerHTML =
        '<div style="display:flex;align-items:baseline;gap:9px">' +
        '<span id="hScore" style="font-size:32px;font-weight:800;letter-spacing:-.02em;color:var(--cyan)">0</span>' +
        '<span style="font-family:var(--mono);font-size:10px;color:var(--ink-3)">/ 100 measured</span></div>' +
        Object.keys(comps).map(function (k) {
          return '<div class="prow" style="margin-top:8px"><div class="body">' +
            '<div class="s">' + esc(k) + '</div>' +
            '<div class="meter"><i data-w="' + comps[k] + '"></i></div></div>' +
            '<span class="pct">' + comps[k].toFixed(0) + '</span></div>';
        }).join('') +
        ((h.unmeasured && h.unmeasured.length)
          ? '<div style="margin-top:9px;font-family:var(--mono);font-size:9.5px;color:var(--ink-4)">NOT MEASURED: ' +
            esc(h.unmeasured.join(', ')) + '</div>' : '');
      U.countUp($('hScore'), h.score, { dec: 1 });
      setTimeout(function () {
        box.querySelectorAll('.meter i').forEach(function (i) { i.style.width = i.dataset.w + '%'; });
      }, 60);
    });
  }

  U.render = { toolCards: toolCards, projects: projects, system: system,
               weather: weather, agenda: agenda, integrations: integrations,
               healthMini: healthMini, title: title };
})();

/* ==================================================================
   U1 OS // shell wiring (c): navigation, palette, focus, boot
   ================================================================== */
(function () {
  'use strict';
  var U = window.U1, esc = U.esc, Sound = U.sound, Notify = U.notify;
  var $ = function (id) { return document.getElementById(id); };
  var svg = U.icons.svg, NAV = U.model.NAV, DOCK = U.model.DOCK, VIEWS = U.model.VIEWS;
  var current = 'home';

  /* ---------------- chrome ---------------- */
  function buildRail() {
    var d = 0;
    $('rail').innerHTML = NAV.map(function (n) {
      if (n.sep) return '<div class="railsep"></div>';
      d += 0.03;
      return '<button class="navitem' + (n.id === current ? ' on' : '') + '" data-go="' + n.id +
        '" style="animation-delay:' + d.toFixed(2) + 's">' + svg(n.icon) +
        '<span>' + esc(n.label) + '</span></button>';
    }).join('') +
    '<div class="railquote"><p>"A brighter tomorrow builds today."</p><span>U1 OS</span></div>';
  }

  function buildDock() {
    $('dock').innerHTML = DOCK.map(function (d) {
      if (d.orb) return '<button class="dockorb" data-go="ai" title="Open AI Command" aria-label="Open AI Command"></button>';
      return '<button class="dockitem" data-go="' + d.id + '" data-label="' + esc(d.label) + '">' +
        svg(d.icon) + '<span class="u1-sr-only">' + esc(d.label) + '</span></button>';
    }).join('');
  }

  function ensureView(id) {
    if (id === 'home') return $('v-home');
    var el = $('v-' + id);
    if (el) return el;
    var meta = (window.U1Life && window.U1Life.meta[id]) || VIEWS[id] || { t: id, s: '' };
    el = document.createElement('section');
    el.className = 'view';
    el.id = 'v-' + id;
    el.innerHTML = '<h2 class="vhead">' + esc(meta.t) + '</h2>' +
      '<p class="vsub">' + esc(meta.s) + '</p>' +
      '<div class="row r-3" id="body-' + id + '"></div>';
    $('views').appendChild(el);
    return el;
  }

  function fillView(id) {
    var body = $('body-' + id);
    if (!body || body.dataset.filled) return;
    if (window.U1Workspaces) { window.U1Workspaces.mount(id, body); body.dataset.filled = '1'; return; }
    body.dataset.filled = '1';
    var meta = VIEWS[id] || {};
    var nav = NAV.filter(function (n) { return n.id === id; })[0] || {};
    if (id === 'updater') {
      body.innerHTML = '<article class="card" style="grid-column:1/-1"><div class="chead">' +
        svg('updater') + '<h3>Updater</h3></div>' +
        '<div class="empty"><b>Live in the classic shell</b>' +
        'Measured health, the update channel, the improvement agent, maintenance and change history are all working at ' +
        '<code>/</code> → Updater. Porting those panels into this shell is the next step.</div>' +
        '<div style="margin-top:12px"><button class="btn pri" data-open="/">Open classic shell</button></div></article>';
      return;
    }
    body.innerHTML = '<article class="card" style="grid-column:1/-1"><div class="chead">' +
      svg(nav.icon || 'home') + '<h3>' + esc(meta.t || id) + '</h3></div>' +
      '<div class="empty"><b>Not wired into this shell yet</b>' + esc(meta.s || '') +
      ' The working panels for this area are in the classic shell at <code>/</code> while the rebuild continues.</div>' +
      '<div style="margin-top:12px"><button class="btn" data-open="/">Open classic shell</button></div></article>';
  }

  function go(id, opts) {
    if (!id) return;
    opts = opts || {};
    var target = ensureView(id);
    if (!target) return;
    Array.prototype.forEach.call(document.querySelectorAll('.view'), function (v) { v.classList.remove('on'); });
    target.classList.add('on');
    Array.prototype.forEach.call(document.querySelectorAll('.navitem'), function (b) {
      b.classList.toggle('on', b.dataset.go === id);
    });
    current = id;
    document.body.dataset.u1View = id;
    window.dispatchEvent(new CustomEvent('u1:navigate', { detail: { id: id } }));
    try { history.replaceState(null, '', '#' + id); } catch (e) {}
    $('main').scrollTop = 0;
    if (!opts.silent) Sound.nav();
    if (id !== 'home') fillView(id);
  }

  /* ---------------- clock ---------------- */
  function tick() {
    var d = new Date(), h = d.getHours(), m = d.getMinutes();
    $('clock').textContent = (h % 12 || 12) + ':' + String(m).padStart(2, '0');
    $('meridiem').textContent = h >= 12 ? 'PM' : 'AM';
    $('today').textContent = d.toLocaleDateString('en-AU',
      { weekday:'short', day:'numeric', month:'short', year:'numeric' }).toUpperCase();
    var greet = h < 12 ? 'Good morning' : h < 18 ? 'Good afternoon' : 'Good evening';
    var name = (window.U1Workspaces && window.U1Workspaces.profile.name) || localStorage.getItem('u1.name') || 'Operator';
    var g = document.querySelector('.greet');
    if (g) g.innerHTML = esc(greet) + ', <em>' + esc(name) + '</em>';
  }

  /* ---------------- palette ---------------- */
  var items = [], sel = 0;
  function buildPalette() {
    items = NAV.filter(function (n) { return !n.sep; }).map(function (n) {
      return { label: n.label, hint: 'Section', run: function () { go(n.id); } };
    }).concat([
      { label:'Toggle interface sound', hint:'Sound', run: toggleSound },
      { label:'Start or pause focus session', hint:'Focus', run: function () { if (U.focus) U.focus.toggle(); } },
      { label:'Mark all notifications read', hint:'Notifications', run: function () { Notify.readAll(); Sound.tap(); } },
      { label:'Check for updates', hint:'Updater', run: function () {
          U.api('updater','check_for_updates',{}).then(function (r) {
            Notify.push(r.message || 'Update check finished.', { tone: r.success ? 'ok' : 'warn', src:'Updater' });
          });
        } },
      { label:'Capture performance baseline', hint:'Measurement', run: function () {
          U.api('updater','capture_baseline',{ label:'manual' }).then(function (r) {
            Notify.push(r.message || 'Baseline captured.', { tone: r.success ? 'ok' : 'bad', src:'Measurement' });
          });
        } },
      { label:'Open classic shell', hint:'Navigate', run: function () { window.location.href = '/'; } }
    ]);
  }
  function paint(q) {
    var list = $('palList');
    var f = items.filter(function (i) { return i.label.toLowerCase().indexOf((q || '').toLowerCase()) > -1; });
    list._filtered = f;
    if (!f.length) { list.innerHTML = '<div class="none">Nothing matches that.</div>'; return; }
    if (sel >= f.length) sel = 0;
    list.innerHTML = f.map(function (i, ix) {
      return '<li class="' + (ix === sel ? 'sel' : '') + '" data-ix="' + ix + '">' +
        esc(i.label) + '<span class="k">' + esc(i.hint) + '</span></li>';
    }).join('');
  }
  function openPal() {
    $('scrim').classList.add('on');
    $('palInput').value = ''; sel = 0; paint('');
    setTimeout(function () { $('palInput').focus(); }, 30);
    Sound.open();
  }
  function closePal() { $('scrim').classList.remove('on'); Sound.close(); }

  /* ---------------- focus ----------------
     The clock itself lives in the session-player module so the card and
     the player can never drift apart. Nothing to keep here. */

  function toggleSound() {
    var on = Sound.toggle();
    $('soundBtn').style.opacity = on ? '1' : '.4';
    if (on) Sound.ok();
    Notify.push('Interface sound ' + (on ? 'on' : 'muted') + '.', { tone:'info', src:'Sound', silent:!on });
  }

  /* ---------------- data refresh ---------------- */
  function refresh(first) {
    if (window.U1Workspaces) return window.U1Workspaces.refresh(first);
    fetch('/api/state').then(function (r) { return r.json(); }).then(function (st) {
      U.render.toolCards(st);
      U.render.projects(st);
      U.render.weather(st);
      U.render.agenda(st);
      U.render.integrations(st);
      U.render.system();
      U.render.healthMini();
      if (first) {
        var keys = Object.keys((st && st.services) || {});
        var live = keys.filter(function (k) { return st.services[k].configured; }).length;
        Notify.push(live + ' of ' + keys.length + ' subsystems configured and reporting.',
                    { tone:'info', src:'Workspace', quiet:true, silent:true });
      }
    }).catch(function () {
      Notify.push('Cannot reach the workspace server.', { tone:'bad', src:'Network' });
    });
  }

  /* ---------------- boot ---------------- */
  function boot() {
    document.body.dataset.u1View = 'home';
    buildRail(); buildDock(); buildPalette();
    tick(); setInterval(tick, 1000);
    Notify.paint();
    $('soundBtn').style.opacity = Sound.enabled() ? '1' : '.4';
    var name = localStorage.getItem('u1.name') || 'Operator';
    $('avatar').textContent = name.charAt(0).toUpperCase();
    $('whoName').textContent = name;

    document.addEventListener('click', function (e) {
      var open = e.target.closest('[data-open]');
      if (open) { window.location.href = open.dataset.open; return; }
      if (e.target.closest('#bell')) {
        var n = $('notif');
        n.classList.toggle('on');
        if (n.classList.contains('on')) { Sound.open(); Notify.readAll(); } else Sound.close();
        return;
      }
      if (e.target.closest('#soundBtn')) { toggleSound(); return; }
      if (e.target.closest('#notifClear')) { Notify.readAll(); Sound.tap(); return; }
      // #focusStart and #focusReset are handled by the session player,
      // which owns the single focus clock. Nothing to do here.
      var li = e.target.closest('#palList li');
      if (li) {
        var f = $('palList')._filtered || [], item = f[+li.dataset.ix];
        closePal(); if (item) item.run();
        return;
      }
      if (e.target === $('scrim')) { closePal(); return; }
      var goEl = e.target.closest('[data-go]');
      if (goEl) { go(goEl.dataset.go); return; }
      if (!e.target.closest('#notif')) $('notif').classList.remove('on');
    });

    document.addEventListener('pointerdown', function (e) {
      if (e.target.closest('button,.dockitem,.dockorb,.navitem,.tool')) Sound.unlock();
    }, true);
    document.addEventListener('mouseover', function (e) {
      if (e.target.closest('.dockitem,.navitem')) Sound.hover();
    });

    $('omni').addEventListener('focus', openPal);
    $('palInput').addEventListener('input', function () { sel = 0; paint(this.value); });

    document.addEventListener('keydown', function (e) {
      if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) { e.preventDefault(); openPal(); return; }
      if (!$('scrim').classList.contains('on')) return;
      var f = $('palList')._filtered || [];
      if (e.key === 'Escape') { closePal(); $('omni').blur(); }
      else if (e.key === 'ArrowDown') { e.preventDefault(); sel = Math.min(f.length - 1, sel + 1); paint($('palInput').value); Sound.tick(); }
      else if (e.key === 'ArrowUp') { e.preventDefault(); sel = Math.max(0, sel - 1); paint($('palInput').value); Sound.tick(); }
      else if (e.key === 'Enter') {
        e.preventDefault();
        var item = f[sel];
        closePal(); $('omni').blur();
        if (item) item.run();
      }
    });

    window.addEventListener('error', function (e) {
      fetch('/api/telemetry/client', {
        method:'POST', headers:{ 'Content-Type':'application/json' },
        body: JSON.stringify({
          kind: (e.error && e.error.name) || 'Error',
          where: String(e.filename || 'shell').split('/').pop() + ':' + (e.lineno || 0),
          message: String(e.message || '').slice(0, 300)
        })
      }).catch(function () {});
    });

    if (U.scenes) U.scenes();

    var hash = (location.hash || '').replace('#', '');
    if (hash && hash !== 'home') go(hash, { silent: true });

    refresh(true);
    setInterval(function () { if (!document.hidden) refresh(false); }, 20000);

    if (window.U1Launch) window.U1Launch.start();
    else $('boot').classList.add('gone');
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();

/* ==================================================================
   U1 OS // premium pass: dock labels, storage panel, session player
   ================================================================== */
(function () {
  'use strict';
  var U = window.U1, esc = U.esc, Sound = U.sound, Notify = U.notify;
  var $ = function (id) { return document.getElementById(id); };

  /* ---- dock labels under each icon ---- */
  function labelDock() {
    Array.prototype.forEach.call(document.querySelectorAll('.dockitem'), function (b) {
      if (b.querySelector('b')) return;
      var t = document.createElement('b');
      t.textContent = b.dataset.label || '';
      b.appendChild(t);
    });
  }

  /* ---- first tool card carries the active highlight ---- */
  function markFirstTool() {
    var t = document.querySelector('#tools .tool');
    if (t) t.classList.add('first');
  }

  /* ---- Drive & storage, from the real workspace disk ---- */
  function storage() {
    var box = $('storage'); if (!box) return;
    U.api('updater', 'get_status', {}).then(function (st) {
      var rt = (st && st.runtime) || {};
      var git = (st && st.git) || {};
      var deps = rt.optional_dependencies || {};
      var installed = Object.keys(deps).filter(function (k) { return deps[k].installed; }).length;
      var total = Object.keys(deps).length;
      var pct = total ? Math.round((installed / total) * 100) : 0;

      box.innerHTML =
        '<div style="display:flex;align-items:center;gap:11px">' +
          '<span style="width:34px;height:34px;border-radius:10px;display:grid;place-items:center;' +
          'background:linear-gradient(140deg,#4FD8FF,#1E7FB8);color:#04060D;font-weight:800;font-size:15px">W</span>' +
          '<div><div style="font-size:13px;font-weight:600">Workspace</div>' +
          '<div style="font-family:var(--mono);font-size:9.5px;color:var(--ink-3)">' +
          esc(rt.root ? String(rt.root).split('/').slice(-1)[0] : 'local') + ' · v' + esc(rt.version || '—') + '</div></div>' +
        '</div>' +
        '<div class="bar-lg"><i data-w="' + pct + '"></i></div>' +
        '<div style="display:flex;justify-content:space-between;font-family:var(--mono);font-size:9.5px;color:var(--ink-3)">' +
          '<span>' + installed + ' of ' + total + ' optional packages</span>' +
          '<span>' + esc(git.branch || '—') + ' @ ' + esc(git.commit || 'no commits') + '</span>' +
        '</div>' +
        '<div class="folders">' +
          ['services', 'utils', 'static', 'tests', 'docs'].map(function (f) {
            return '<div class="folder"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">' +
              '<path d="M3 7h6l2 2h10v10H3z"/></svg>' + f + '</div>';
          }).join('') +
        '</div>';
      setTimeout(function () {
        var i = box.querySelector('.bar-lg i');
        if (i) i.style.width = i.dataset.w + '%';
      }, 60);
    });
  }

  /* ---- session player: drives the same focus timer, no fake audio ---- */
  var TOTAL = 25 * 60, left = TOTAL, running = false, timer = null;

  function paint() {
    var done = TOTAL - left;
    var bar = $('plBar'); if (bar) bar.style.width = ((done / TOTAL) * 100).toFixed(2) + '%';
    var mm = function (s) { return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); };
    if ($('plNow')) $('plNow').textContent = mm(done);
    if ($('plTotal')) $('plTotal').textContent = mm(TOTAL);
    if ($('plSub')) $('plSub').textContent = running ? 'Focus session · running' : (left === TOTAL ? 'Focus session · ready' : 'Focus session · paused');
    var icon = $('plIcon');
    if (icon) icon.innerHTML = running ? '<path d="M7 5h4v14H7zM13 5h4v14h-4z"/>' : '<path d="M8 5v14l11-7z"/>';
    // keep the home-card ring in step
    var ring = $('focusRing');
    if (ring) U.gauge(ring, (done / TOTAL) * 100, running ? '#57E7B5' : '#4FD8FF');
    if ($('focusTime')) $('focusTime').textContent = mm(left);
    if ($('focusTag')) {
      $('focusTag').textContent = running ? 'RUNNING' : (left === TOTAL ? 'READY' : 'PAUSED');
      $('focusTag').className = 'tag ' + (running ? 'ok' : 'idle');
    }
    if ($('focusNote')) $('focusNote').textContent = running ? 'Session in progress' : (left === TOTAL ? 'Nothing running' : 'Paused');
    if ($('focusStart')) $('focusStart').textContent = running ? 'Pause' : 'Start';
  }

  function toggle() {
    running = !running;
    if (running) {
      Sound.ok();
      Notify.push('Focus session started — 25 minutes.', { tone: 'ok', src: 'Focus', silent: true });
      timer = setInterval(function () {
        left--;
        if (left > 0 && left % 300 === 0) Sound.tick();
        if (left <= 0) {
          clearInterval(timer); running = false; left = 0; Sound.ok();
          Notify.push('Focus session complete. Take a break.', { tone: 'ok', src: 'Focus', silent: true });
        }
        paint();
      }, 1000);
    } else { clearInterval(timer); Sound.close(); }
    paint();
  }
  function reset() { clearInterval(timer); running = false; left = TOTAL; Sound.close(); paint(); }
  function finish() {
    clearInterval(timer); running = false; left = 0; Sound.ok(); paint();
    Notify.push('Focus session ended early.', { tone: 'info', src: 'Focus', silent: true });
  }

  function boot() {
    labelDock();
    paint();
    storage();
    setTimeout(markFirstTool, 400);
    setInterval(storage, 60000);

    document.addEventListener('click', function (e) {
      if (e.target.closest('#plPlay') || e.target.closest('#focusStart')) { toggle(); return; }
      if (e.target.closest('#plBack') || e.target.closest('#focusReset')) { reset(); return; }
      if (e.target.closest('#plFwd')) { finish(); return; }
      if (e.target.closest('#plCollapse')) {
        var p = $('player');
        p.dataset.min = p.dataset.min ? '' : '1';
        p.style.height = p.dataset.min ? '62px' : '';
        p.style.overflow = 'hidden';
        Sound.tap();
      }
    });

    // The session player owns the focus timer; the home card and the
    // command palette drive it through here so there is only one clock.
    U.focus = { toggle: toggle, reset: reset, finish: finish, paint: paint };

    // re-label the dock after any rebuild
    var dock = $('dock');
    if (dock && window.MutationObserver) {
      new MutationObserver(labelDock).observe(dock, { childList: true });
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', function () { setTimeout(boot, 60); });
  else setTimeout(boot, 60);
})();
