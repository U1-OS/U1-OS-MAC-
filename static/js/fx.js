/**
 * U1 OS // SENSORY LAYER  (Wave 9)
 * ---------------------------------------------------------------
 * Global, dependency-free interface feedback engine:
 *   U1FX.audio   — Web Audio synth sound pack (no binary assets)
 *   U1FX.notify  — toast stack + notification centre + desktop bridge
 *   U1FX.motion  — ripples, reveals, count-ups, value flashes
 *
 * Loaded BEFORE app.js so `showNotification()` resolves globally for
 * every existing call site in the application controller.
 */
(function () {
  'use strict';

  var LS_AUDIO = 'u1os.fx.audio';
  var LS_VOL = 'u1os.fx.volume';
  var LS_MOTION = 'u1os.fx.motion';
  var LS_FEED = 'u1os.fx.feed';
  var FEED_CAP = 120;

  function lsGet(k, d) {
    try { var v = localStorage.getItem(k); return v === null ? d : v; } catch (e) { return d; }
  }
  function lsSet(k, v) {
    try { localStorage.setItem(k, v); } catch (e) { /* private mode */ }
  }
  function prefersReducedMotion() {
    try { return window.matchMedia('(prefers-reduced-motion: reduce)').matches; } catch (e) { return false; }
  }

  /* =============================================================
     1. AUDIO ENGINE — Web Audio API synthesizer
     ============================================================= */
  var Audio = (function () {
    var ctx = null;
    var master = null;
    var enabled = lsGet(LS_AUDIO, '1') === '1';
    var volume = parseFloat(lsGet(LS_VOL, '0.6'));
    if (isNaN(volume)) volume = 0.6;

    function ac() {
      if (!ctx) {
        var C = window.AudioContext || window.webkitAudioContext;
        if (!C) return null;
        ctx = new C();
        master = ctx.createGain();
        master.gain.value = volume;
        master.connect(ctx.destination);
      }
      if (ctx.state === 'suspended') { try { ctx.resume(); } catch (e) {} }
      return ctx;
    }

    // Single shaped oscillator voice.
    function tone(opts) {
      if (!enabled) return;
      var c = ac();
      if (!c) return;
      try {
        var t0 = c.currentTime + (opts.delay || 0);
        var dur = opts.dur || 0.06;
        var osc = c.createOscillator();
        var g = c.createGain();
        osc.type = opts.type || 'sine';
        osc.frequency.setValueAtTime(opts.from, t0);
        if (opts.to && opts.to !== opts.from) {
          osc.frequency.exponentialRampToValueAtTime(Math.max(12, opts.to), t0 + dur);
        }
        var peak = Math.max(0.0001, (opts.gain === undefined ? 0.05 : opts.gain));
        g.gain.setValueAtTime(0.0001, t0);
        g.gain.exponentialRampToValueAtTime(peak, t0 + Math.min(0.012, dur * 0.3));
        g.gain.exponentialRampToValueAtTime(0.0001, t0 + dur);
        osc.connect(g);
        g.connect(master);
        osc.start(t0);
        osc.stop(t0 + dur + 0.02);
      } catch (e) { /* audio blocked */ }
    }

    // Filtered white-noise burst — used for transient/mechanical cues.
    function noise(opts) {
      if (!enabled) return;
      var c = ac();
      if (!c) return;
      try {
        var dur = opts.dur || 0.06;
        var frames = Math.max(1, Math.floor(c.sampleRate * dur));
        var buf = c.createBuffer(1, frames, c.sampleRate);
        var data = buf.getChannelData(0);
        for (var i = 0; i < frames; i++) {
          data[i] = (Math.random() * 2 - 1) * (1 - i / frames);
        }
        var src = c.createBufferSource();
        src.buffer = buf;
        var filt = c.createBiquadFilter();
        filt.type = opts.filter || 'bandpass';
        filt.frequency.value = opts.freq || 2200;
        filt.Q.value = opts.q || 1.2;
        var g = c.createGain();
        g.gain.value = opts.gain === undefined ? 0.035 : opts.gain;
        src.connect(filt); filt.connect(g); g.connect(master);
        src.start(c.currentTime + (opts.delay || 0));
      } catch (e) { /* noop */ }
    }

    function chord(freqs, dur, gain, type) {
      freqs.forEach(function (f, i) {
        tone({ from: f, to: f, dur: dur || 0.14, gain: (gain || 0.04) / (i + 1.2), type: type || 'sine', delay: i * 0.012 });
      });
    }

    function arp(freqs, step, dur, gain, type) {
      freqs.forEach(function (f, i) {
        tone({ from: f, to: f, dur: dur || 0.09, gain: gain || 0.045, type: type || 'sine', delay: i * (step || 0.07) });
      });
    }

    var api = {
      isEnabled: function () { return enabled; },
      getVolume: function () { return volume; },
      setVolume: function (v) {
        volume = Math.max(0, Math.min(1, parseFloat(v) || 0));
        lsSet(LS_VOL, String(volume));
        if (master) master.gain.value = volume;
        return volume;
      },
      setEnabled: function (on) {
        enabled = !!on;
        lsSet(LS_AUDIO, enabled ? '1' : '0');
        return enabled;
      },
      toggle: function () { return api.setEnabled(!enabled); },
      unlock: function () { ac(); },

      /* --- transport / UI --- */
      click:   function () { tone({ from: 360, to: 180, dur: 0.035, gain: 0.045, type: 'sine' }); },
      tick:    function () { tone({ from: 1400, to: 1100, dur: 0.018, gain: 0.028, type: 'square' }); },
      haptic:  function () { tone({ from: 880, to: 440, dur: 0.022, gain: 0.032, type: 'triangle' }); },
      nav:     function () { tone({ from: 480, to: 240, dur: 0.045, gain: 0.038, type: 'triangle' }); noise({ dur: 0.04, freq: 3200, gain: 0.012 }); },
      hover:   function () { tone({ from: 1800, to: 1800, dur: 0.012, gain: 0.012, type: 'sine' }); },
      open:    function () { tone({ from: 300, to: 760, dur: 0.14, gain: 0.04, type: 'sine' }); },
      close:   function () { tone({ from: 760, to: 300, dur: 0.12, gain: 0.035, type: 'sine' }); },

      /* --- outcomes --- */
      success: function () { arp([523.25, 659.25, 783.99], 0.06, 0.11, 0.045, 'sine'); },
      error:   function () { tone({ from: 240, to: 90, dur: 0.26, gain: 0.06, type: 'sawtooth' }); tone({ from: 120, to: 60, dur: 0.3, gain: 0.04, type: 'square', delay: 0.05 }); },
      warn:    function () { tone({ from: 660, to: 660, dur: 0.1, gain: 0.045, type: 'triangle' }); tone({ from: 660, to: 495, dur: 0.16, gain: 0.045, type: 'triangle', delay: 0.14 }); },
      alert:   function () { tone({ from: 180, to: 80, dur: 0.25, gain: 0.07, type: 'sawtooth' }); },

      /* --- domain cues --- */
      trade:   function () { tone({ from: 920, to: 220, dur: 0.18, gain: 0.055, type: 'sawtooth' }); noise({ dur: 0.09, freq: 900, gain: 0.02 }); },
      cash:    function () { arp([1046.5, 1318.5, 1568, 2093], 0.045, 0.08, 0.038, 'sine'); },
      execute: function () { tone({ from: 140, to: 620, dur: 0.13, gain: 0.05, type: 'square' }); noise({ dur: 0.07, freq: 1600, gain: 0.022, delay: 0.05 }); },
      signal:  function () { arp([523.25, 659.25, 783.99], 0.07, 0.1, 0.045, 'sine'); },
      notify:  function () { chord([880, 1174.7], 0.12, 0.04, 'sine'); },
      whoosh:  function () { noise({ dur: 0.22, freq: 700, filter: 'lowpass', gain: 0.028 }); },
      boot:    function () {
        arp([196, 261.63, 329.63, 392, 523.25], 0.085, 0.22, 0.04, 'sine');
        noise({ dur: 0.5, freq: 400, filter: 'lowpass', gain: 0.02, delay: 0.05 });
      },
      toggleSound: function (on) { on ? api.success() : api.close(); }
    };
    return api;
  })();

  /* =============================================================
     2. NOTIFICATION CENTRE + TOAST STACK
     ============================================================= */
  var Notify = (function () {
    var feed = [];
    var unread = 0;
    var stackEl = null;
    var listeners = [];

    var TYPES = {
      info:    { glyph: '◈', kicker: 'SYSTEM',  sound: 'notify' },
      success: { glyph: '✓', kicker: 'SUCCESS', sound: 'success' },
      error:   { glyph: '✕', kicker: 'FAULT',   sound: 'error' },
      warn:    { glyph: '⚠', kicker: 'WARNING', sound: 'warn' },
      trade:   { glyph: '⇄', kicker: 'EXECUTION', sound: 'trade' },
      event:   { glyph: '◉', kicker: 'LIVE',    sound: 'tick' }
    };

    function loadFeed() {
      try {
        var raw = lsGet(LS_FEED, '[]');
        var parsed = JSON.parse(raw);
        if (Object.prototype.toString.call(parsed) === '[object Array]') feed = parsed.slice(0, FEED_CAP);
      } catch (e) { feed = []; }
      unread = feed.filter(function (n) { return !n.read; }).length;
    }
    function saveFeed() { try { lsSet(LS_FEED, JSON.stringify(feed.slice(0, FEED_CAP))); } catch (e) {} }

    function relTime(ts) {
      var d = Math.max(0, Date.now() - ts);
      var s = Math.floor(d / 1000);
      if (s < 10) return 'now';
      if (s < 60) return s + 's ago';
      var m = Math.floor(s / 60);
      if (m < 60) return m + 'm ago';
      var h = Math.floor(m / 60);
      if (h < 24) return h + 'h ago';
      return Math.floor(h / 24) + 'd ago';
    }

    /* ---------- toast stack ---------- */
    function ensureStack() {
      if (stackEl && document.body.contains(stackEl)) return stackEl;
      stackEl = document.getElementById('fxToastStack');
      if (!stackEl) {
        stackEl = document.createElement('div');
        stackEl.id = 'fxToastStack';
        stackEl.setAttribute('role', 'status');
        stackEl.setAttribute('aria-live', 'polite');
        document.body.appendChild(stackEl);
      }
      return stackEl;
    }

    function dismiss(el) {
      if (!el || el.classList.contains('fx-leaving')) return;
      el.classList.add('fx-leaving');
      setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 280);
    }

    function toast(message, type, kicker, ttl) {
      var meta = TYPES[type] || TYPES.info;
      var stack = ensureStack();
      var el = document.createElement('div');
      el.className = 'fx-toast t-' + (type === 'event' ? 'info' : type);
      var life = ttl || (type === 'error' ? 7000 : 4200);

      var g = document.createElement('span');
      g.className = 'fx-toast-glyph';
      g.textContent = meta.glyph;

      var body = document.createElement('div');
      body.className = 'fx-toast-body';
      var k = document.createElement('span');
      k.className = 'fx-toast-kicker';
      k.textContent = kicker || meta.kicker;
      var m = document.createElement('div');
      m.className = 'fx-toast-msg';
      m.textContent = message;
      body.appendChild(k);
      body.appendChild(m);

      var bar = document.createElement('span');
      bar.className = 'fx-toast-life';
      bar.style.animationDuration = life + 'ms';

      el.appendChild(g);
      el.appendChild(body);
      el.appendChild(bar);
      el.addEventListener('click', function () { dismiss(el); });

      stack.insertBefore(el, stack.firstChild);
      while (stack.children.length > 5) dismiss(stack.lastChild);
      setTimeout(function () { dismiss(el); }, life);
      return el;
    }

    /* ---------- notification centre ---------- */
    function badgeEl() { return document.getElementById('notifBadge'); }
    function panelEl() { return document.getElementById('notifPanel'); }

    function renderBadge() {
      var b = badgeEl();
      if (!b) return;
      if (unread > 0) {
        b.textContent = unread > 99 ? '99+' : String(unread);
        b.hidden = false;
      } else {
        b.hidden = true;
      }
      var btn = document.getElementById('btnNotifCenter');
      if (btn && unread > 0) {
        btn.classList.remove('fx-ringing');
        void btn.offsetWidth;
        btn.classList.add('fx-ringing');
      }
    }

    function renderList() {
      var panel = panelEl();
      if (!panel) return;
      var list = panel.querySelector('.notif-list');
      if (!list) return;
      if (!feed.length) {
        list.innerHTML = '<div class="notif-empty"><span>◇</span>No signals yet. The command centre is quiet.</div>';
      } else {
        list.innerHTML = feed.map(function (n) {
          var t = TYPES[n.type] ? n.type : 'info';
          return '<div class="notif-item t-' + t + (n.read ? '' : ' unread') + '">' +
            '<i class="notif-dot"></i>' +
            '<div class="notif-body">' +
              '<div class="notif-msg"></div>' +
              '<div class="notif-meta"><span class="notif-src">' + escapeHtml(n.source || (TYPES[t].kicker)) + '</span>' +
              '<span>' + relTime(n.ts) + '</span></div>' +
            '</div></div>';
        }).join('');
        // Inject message text safely (avoids HTML injection from event payloads).
        var nodes = list.querySelectorAll('.notif-msg');
        for (var i = 0; i < nodes.length && i < feed.length; i++) nodes[i].textContent = feed[i].message;
      }
      var count = panel.querySelector('[data-notif-count]');
      if (count) count.textContent = feed.length + ' signal' + (feed.length === 1 ? '' : 's');
    }

    function escapeHtml(s) {
      return String(s).replace(/[&<>"']/g, function (c) {
        return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
      });
    }

    function push(message, opts) {
      opts = opts || {};
      var type = TYPES[opts.type] ? opts.type : 'info';
      var entry = {
        id: 'n' + Date.now() + Math.random().toString(36).slice(2, 7),
        message: String(message),
        type: type,
        source: opts.source || TYPES[type].kicker,
        ts: Date.now(),
        read: false
      };
      feed.unshift(entry);
      if (feed.length > FEED_CAP) feed.length = FEED_CAP;
      unread++;
      saveFeed();
      renderBadge();
      if (isOpen()) renderList();
      listeners.forEach(function (fn) { try { fn(entry); } catch (e) {} });
      return entry;
    }

    function isOpen() {
      var p = panelEl();
      return !!(p && p.classList.contains('open'));
    }

    function open() {
      var p = panelEl();
      if (!p) return;
      renderList();
      p.classList.add('open');
      Audio.open();
      markAllRead();
    }
    function close() {
      var p = panelEl();
      if (!p || !p.classList.contains('open')) return;
      p.classList.remove('open');
      Audio.close();
    }
    function togglePanel() { isOpen() ? close() : open(); }

    function markAllRead() {
      if (!unread) return;
      feed.forEach(function (n) { n.read = true; });
      unread = 0;
      saveFeed();
      renderBadge();
      renderList();
    }
    function clearAll() {
      feed = [];
      unread = 0;
      saveFeed();
      renderBadge();
      renderList();
      Audio.close();
    }

    /* ---------- desktop bridge ---------- */
    function desktop(title, message) {
      try {
        if (!('Notification' in window)) return false;
        if (Notification.permission === 'granted') {
          new Notification(title || 'U1 OS', { body: message, silent: true });
          return true;
        }
        if (Notification.permission !== 'denied') {
          Notification.requestPermission().then(function (p) {
            if (p === 'granted') new Notification(title || 'U1 OS', { body: message, silent: true });
          });
        }
      } catch (e) {}
      return false;
    }

    /* ---------- public entry point ---------- */
    function show(message, opts) {
      if (message === undefined || message === null) return;
      if (typeof opts === 'string') opts = { type: opts };
      opts = opts || {};
      var type = TYPES[opts.type] ? opts.type : inferType(String(message));
      var entry = push(message, { type: type, source: opts.source });
      toast(String(message), type, opts.kicker || opts.source, opts.ttl);
      if (opts.silent !== true) {
        var s = TYPES[type].sound;
        if (Audio[s]) Audio[s]();
      }
      if (opts.desktop) desktop(opts.title || 'U1 OS', String(message));
      return entry;
    }

    // Infers severity from message wording so the ~40 legacy
    // showNotification() call sites get correct colour + sound for free.
    function inferType(msg) {
      var m = msg.toLowerCase();
      if (/(failed|failure|error|invalid|denied|unable|offline|rejected|not able)/.test(m)) return 'error';
      if (/(warn|caution|must remain|please enter|at least one|expired)/.test(m)) return 'warn';
      if (/(swap|trade|executed|position|bought|sold|order|backtest)/.test(m)) return 'trade';
      if (/(complete|success|activated|created|deleted|updated|engaged|verified|copied|dispatched|processed|synced|saved)/.test(m)) return 'success';
      return 'info';
    }

    return {
      show: show,
      toast: toast,
      push: push,
      open: open,
      close: close,
      toggle: togglePanel,
      isOpen: isOpen,
      markAllRead: markAllRead,
      clear: clearAll,
      desktop: desktop,
      render: renderList,
      count: function () { return { total: feed.length, unread: unread }; },
      onPush: function (fn) { if (typeof fn === 'function') listeners.push(fn); },
      _load: loadFeed,
      _renderBadge: renderBadge,
      TYPES: TYPES
    };
  })();

  /* =============================================================
     3. MOTION ENGINE
     ============================================================= */
  var Motion = (function () {
    var motionOn = lsGet(LS_MOTION, '1') === '1' && !prefersReducedMotion();

    function setEnabled(on) {
      motionOn = !!on;
      lsSet(LS_MOTION, motionOn ? '1' : '0');
      document.body.classList.toggle('fx-motion-off', !motionOn);
      return motionOn;
    }

    function ripple(e) {
      if (!motionOn) return;
      var t = e.target.closest('button, .btn, .nav-item, .bezel-widget, .tab, [data-fx-ripple]');
      if (!t || t.disabled) return;
      var cs = window.getComputedStyle(t);
      if (cs.position === 'static') t.style.position = 'relative';
      if (cs.overflow !== 'hidden') t.style.overflow = 'hidden';
      var r = t.getBoundingClientRect();
      var size = Math.max(r.width, r.height);
      var el = document.createElement('span');
      el.className = 'fx-ripple';
      el.style.width = el.style.height = size + 'px';
      el.style.left = (e.clientX - r.left - size / 2) + 'px';
      el.style.top = (e.clientY - r.top - size / 2) + 'px';
      t.appendChild(el);
      setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 560);
    }

    function reveal(el, delay) {
      if (!el || !motionOn) return;
      el.style.animationDelay = (delay || 0) + 'ms';
      el.classList.remove('fx-reveal');
      void el.offsetWidth;
      el.classList.add('fx-reveal');
    }

    function revealAll(selector, stagger) {
      var nodes = document.querySelectorAll(selector);
      for (var i = 0; i < nodes.length; i++) reveal(nodes[i], i * (stagger || 45));
      return nodes.length;
    }

    function flash(el, direction) {
      if (!el || !motionOn) return;
      var cls = direction === 'down' ? 'fx-flash-down' : 'fx-flash-up';
      el.classList.remove('fx-flash-up', 'fx-flash-down');
      void el.offsetWidth;
      el.classList.add(cls);
      setTimeout(function () { el.classList.remove(cls); }, 950);
    }

    function countUp(el, to, opts) {
      if (!el) return;
      opts = opts || {};
      var from = opts.from !== undefined ? opts.from : (parseFloat(String(el.textContent).replace(/[^0-9.\-]/g, '')) || 0);
      var target = parseFloat(to) || 0;
      var dur = opts.duration || 700;
      var dec = opts.decimals === undefined ? 0 : opts.decimals;
      var pre = opts.prefix || '';
      var suf = opts.suffix || '';
      if (!motionOn || from === target) {
        el.textContent = pre + target.toFixed(dec) + suf;
        return;
      }
      var start = null;
      function step(ts) {
        if (start === null) start = ts;
        var p = Math.min(1, (ts - start) / dur);
        var eased = 1 - Math.pow(1 - p, 3);
        el.textContent = pre + (from + (target - from) * eased).toFixed(dec) + suf;
        if (p < 1) requestAnimationFrame(step);
      }
      requestAnimationFrame(step);
    }

    function sectionEnter(el) {
      if (!el || !motionOn) return;
      el.classList.remove('fx-section-enter');
      void el.offsetWidth;
      el.classList.add('fx-section-enter');
    }

    function bootSweep() {
      if (!motionOn) return;
      var el = document.createElement('div');
      el.className = 'fx-boot-sweep';
      document.body.appendChild(el);
      setTimeout(function () { if (el.parentNode) el.parentNode.removeChild(el); }, 1300);
    }

    return {
      isEnabled: function () { return motionOn; },
      setEnabled: setEnabled,
      toggle: function () { return setEnabled(!motionOn); },
      ripple: ripple,
      reveal: reveal,
      revealAll: revealAll,
      flash: flash,
      countUp: countUp,
      sectionEnter: sectionEnter,
      bootSweep: bootSweep
    };
  })();

  /* =============================================================
     4. WIRING
     ============================================================= */
  function buildNotificationCentre() {
    if (document.getElementById('notifPanel')) return;

    // Bell button — injected into the top bezel beside the audio toggle.
    var audioBtn = document.getElementById('btnToggleAudio');
    if (audioBtn && !document.getElementById('btnNotifCenter')) {
      var btn = document.createElement('button');
      btn.className = 'bezel-widget btn-palette-trigger mono';
      btn.id = 'btnNotifCenter';
      btn.title = 'Notification Centre (Cmd+Shift+N)';
      btn.setAttribute('aria-label', 'Notification Centre');
      btn.style.cssText = 'padding:0 10px; display:inline-flex; align-items:center; gap:5px; color:var(--gold, #e9b44c);';
      btn.innerHTML =
        '<svg class="w-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" style="width:15px;height:15px;">' +
          '<path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>' +
          '<path d="M13.73 21a2 2 0 0 1-3.46 0"></path>' +
        '</svg>' +
        '<span id="notifBadge" hidden>0</span>';
      btn.addEventListener('click', function (e) { e.stopPropagation(); Notify.toggle(); });
      audioBtn.parentNode.insertBefore(btn, audioBtn);
    }

    var panel = document.createElement('div');
    panel.id = 'notifPanel';
    panel.setAttribute('role', 'dialog');
    panel.setAttribute('aria-label', 'Notification Centre');
    panel.innerHTML =
      '<div class="notif-head">' +
        '<span class="notif-title">Notification Centre</span>' +
        '<span class="notif-actions">' +
          '<button class="notif-act" data-notif-action="read">Mark read</button>' +
          '<button class="notif-act" data-notif-action="clear">Clear</button>' +
        '</span>' +
      '</div>' +
      '<div class="notif-list"></div>' +
      '<div class="notif-foot">' +
        '<span data-notif-count>0 signals</span>' +
        '<span class="notif-live"><i></i>Live feed active</span>' +
      '</div>';
    document.body.appendChild(panel);

    panel.addEventListener('click', function (e) {
      e.stopPropagation();
      var a = e.target.closest('[data-notif-action]');
      if (!a) return;
      if (a.dataset.notifAction === 'read') { Notify.markAllRead(); Audio.tick(); }
      if (a.dataset.notifAction === 'clear') Notify.clear();
    });

    document.addEventListener('click', function (e) {
      if (!Notify.isOpen()) return;
      if (e.target.closest('#notifPanel') || e.target.closest('#btnNotifCenter')) return;
      Notify.close();
    });
  }

  function buildVolumeControl() {
    var audioBtn = document.getElementById('btnToggleAudio');
    if (!audioBtn || document.getElementById('fxVolume')) return;
    var wrap = document.createElement('span');
    wrap.className = 'bezel-widget fx-vol-wrap';
    wrap.title = 'Interface sound level';
    var input = document.createElement('input');
    input.type = 'range';
    input.id = 'fxVolume';
    input.min = '0';
    input.max = '1';
    input.step = '0.05';
    input.value = String(Audio.getVolume());
    input.addEventListener('input', function () { Audio.setVolume(this.value); });
    input.addEventListener('change', function () { Audio.tick(); });
    wrap.appendChild(input);
    audioBtn.parentNode.insertBefore(wrap, audioBtn.nextSibling);
    audioBtn.classList.toggle('muted', !Audio.isEnabled());
  }

  function wireGlobalFeedback() {
    // Ripple + tactile click on every interactive control, once, globally.
    document.addEventListener('pointerdown', function (e) {
      var t = e.target.closest('button, .btn, .nav-item, .bezel-widget, .tab, [data-fx-ripple]');
      if (!t || t.disabled) return;
      Audio.unlock();
      Motion.ripple(e);
      if (t.classList.contains('nav-item')) Audio.nav();
      else Audio.click();
    }, true);

    // Keyboard: Cmd/Ctrl+Shift+N toggles the centre, Esc closes it.
    document.addEventListener('keydown', function (e) {
      if ((e.metaKey || e.ctrlKey) && e.shiftKey && (e.key === 'n' || e.key === 'N')) {
        e.preventDefault();
        Notify.toggle();
      } else if (e.key === 'Escape' && Notify.isOpen()) {
        Notify.close();
      }
    });

    // Keep relative timestamps honest while the panel is open.
    setInterval(function () { if (Notify.isOpen()) Notify.render(); }, 30000);
  }

  function boot() {
    Notify._load();
    buildNotificationCentre();
    buildVolumeControl();
    wireGlobalFeedback();
    Notify._renderBadge();
    Motion.setEnabled(Motion.isEnabled());
    Motion.bootSweep();
    // Browsers gate audio until first gesture — arm the pack on any input.
    var arm = function () {
      Audio.unlock();
      Audio.boot();
      document.removeEventListener('pointerdown', arm);
      document.removeEventListener('keydown', arm);
    };
    document.addEventListener('pointerdown', arm);
    document.addEventListener('keydown', arm);
  }

  /* =============================================================
     5. EXPORTS
     ============================================================= */
  window.U1FX = {
    audio: Audio,
    notify: Notify,
    motion: Motion,
    version: '9.0.0'
  };

  // Global entry point used throughout app.js (previously undefined).
  window.showNotification = function (message, opts) {
    return Notify.show(message, opts);
  };
  window.showToast = function (message, type) {
    return Notify.toast(String(message), type || 'info');
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', boot);
  } else {
    boot();
  }
})();
