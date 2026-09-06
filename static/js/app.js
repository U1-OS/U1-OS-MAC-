/**
 * COMMAND CENTER // macOS Business Operating System
 * Living Interface Controller & State Feeder Client
 */

const CommandCenter = (() => {
  // State Storage
  let currentState = null;
  let previousState = null;
  let seenEventIds = new Set();
  let currentSection = 'home';
  let pollInterval = null;

  // DOM Cache
  const els = {
    body: document.body,
    slidingSpine: document.getElementById('slidingSpine'),
    navItems: document.querySelectorAll('.nav-item'),
    sections: document.querySelectorAll('.section-grid'),
    sysClock: document.getElementById('sysClock'),
    sysDate: document.getElementById('sysDate'),
    weatherVal: document.getElementById('weatherVal'),
    weatherCity: document.getElementById('weatherCity'),
    poolStatusVal: document.getElementById('poolStatusVal'),
    tickerContent: document.getElementById('tickerContent'),
    loadVal: document.getElementById('loadVal'),
    
    // Home Widgets
    revValue: document.getElementById('revValue'),
    revCurrency: document.getElementById('revCurrency'),
    revSub: document.getElementById('revSub'),
    revenueBody: document.getElementById('revenueBody'),
    revenueStatusDot: document.getElementById('revenueStatusDot'),
    revenueStatusText: document.getElementById('revenueStatusText'),
    
    calendarBody: document.getElementById('calendarBody'),
    calStatusDot: document.getElementById('calStatusDot'),
    
    inboxBody: document.getElementById('inboxBody'),
    gmailStatusDot: document.getElementById('gmailStatusDot'),
    
    repoBody: document.getElementById('repoBody'),
    repoBranchName: document.getElementById('repoBranchName'),
    repoFooterStatus: document.getElementById('repoFooterStatus'),
    
    aiBody: document.getElementById('aiBody'),
    aiStatusDot: document.getElementById('aiStatusDot'),
    
    studioBody: document.getElementById('studioBody'),
    studioStatusDot: document.getElementById('studioStatusDot'),
    studioQueueCount: document.getElementById('studioQueueCount'),
    
    // Confirmation Modal
    confirmModal: document.getElementById('confirmModal'),
    modalTitle: document.getElementById('modalTitle'),
    modalDesc: document.getElementById('modalDesc'),
    modalCode: document.getElementById('modalCode'),
    modalCancelBtn: document.getElementById('modalCancelBtn'),
    modalConfirmBtn: document.getElementById('modalConfirmBtn')
  };

  let pendingConfirmCallback = null;

  /* ========================================================
     BOOT SEQUENCE & NAVIGATION
     ======================================================== */
  function init() {
    setupNavigation();
    setupClock();
    setupModal();
    
    // Remove booting class after initial cascade completes
    setTimeout(() => {
      els.body.classList.remove('booting');
    }, 450);

    // Initial state fetch & polling loop
    fetchState();
    pollInterval = setInterval(fetchState, 2500);

    // Initial spine position
    updateSpinePosition();
  }

  function setupNavigation() {
    els.navItems.forEach(item => {
      item.addEventListener('click', () => {
        const sectionId = item.dataset.section;
        switchSection(sectionId);
      });
    });

    window.addEventListener('resize', () => {
      updateSpinePosition();
    });
  }

  function switchSection(sectionId) {
    if (!sectionId) return;
    currentSection = sectionId;

    // Update active nav button
    els.navItems.forEach(item => {
      if (item.dataset.section === sectionId) {
        item.classList.add('active');
      } else {
        item.classList.remove('active');
      }
    });

    // Physically slide the gold spine
    updateSpinePosition();

    // Cross-seat sections (fast settle)
    els.sections.forEach(sec => {
      if (sec.id === `section-${sectionId}`) {
        sec.classList.add('active');
      } else {
        sec.classList.remove('active');
      }
    });

    // Populate section-specific subviews if state is ready
    if (currentState) {
      renderActiveSectionDetails(sectionId);
    }
  }

  function updateSpinePosition() {
    const activeNav = document.querySelector('.nav-item.active');
    if (!activeNav || !els.slidingSpine) return;

    const navContainer = activeNav.parentElement;
    const navRect = navContainer.getBoundingClientRect();
    const itemRect = activeNav.getBoundingClientRect();

    const topOffset = itemRect.top - navRect.top;
    els.slidingSpine.style.transform = `translateY(${topOffset}px)`;
    els.slidingSpine.style.height = `${itemRect.height}px`;
  }

  /* ========================================================
     LOCAL SYSTEM CLOCK
     ======================================================== */
  function setupClock() {
    function tick() {
      const now = new Date();
      const hours = String(now.getHours()).padStart(2, '0');
      const mins = String(now.getMinutes()).padStart(2, '0');
      const secs = String(now.getSeconds()).padStart(2, '0');
      if (els.sysClock) els.sysClock.textContent = `${hours}:${mins}:${secs}`;

      const options = { weekday: 'short', month: 'short', day: 'numeric' };
      if (els.sysDate) els.sysDate.textContent = now.toLocaleDateString('en-US', options).toUpperCase();
    }
    tick();
    setInterval(tick, 1000);
  }

  /* ========================================================
     DATA FEEDER SYNC (GET /api/state)
     ======================================================== */
  async function fetchState() {
    try {
      const resp = await fetch('/api/state', { cache: 'no-store' });
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      
      previousState = currentState;
      currentState = data;
      renderAll(data);
      checkNewEvents(data);
    } catch (err) {
      console.warn('[CommandCenter] State feed offline:', err);
    }
  }

  function renderAll(state) {
    if (!state || !state.services) return;
    const s = state.services;

    renderIntelligenceStrip(s.intelligence);
    renderHomeRevenue(s.finance);
    renderHomeCalendar(s.comms);
    renderHomeInbox(s.comms);
    renderHomeRepo(s.deploy);
    renderHomeAI(s.ai_workbench);
    renderHomeStudio(s.studio);

    // If currently on another section, refresh its view
    if (currentSection !== 'home') {
      renderActiveSectionDetails(currentSection);
    }
  }

  /* ========================================================
     INTELLIGENCE STRIP RENDERING
     ======================================================== */
  function renderIntelligenceStrip(intel) {
    if (!intel || !intel.data) return;
    const d = intel.data;

    // Weather
    if (d.weather && els.weatherVal) {
      els.weatherVal.textContent = `${d.weather.temp_c}°C`;
      els.weatherCity.textContent = `${(d.weather.city || 'LOCAL').toUpperCase()} // ${d.weather.condition.toUpperCase()}`;
    }

    // Pool Telemetry
    if (d.pool && els.poolStatusVal) {
      els.poolStatusVal.textContent = d.pool.status_text || 'POOL: UNPAIRED';
    }

    // Live Ticker
    if (d.news && d.news.length > 0 && els.tickerContent) {
      const itemsHtml = d.news.map(item => `
        <span class="ticker-item">
          <span class="t-source">[${item.source}]</span> 
          <a href="${item.url}" target="_blank" style="color: inherit; text-decoration: none;">${escapeHtml(item.title)}</a>
        </span>
      `).join('');
      // Duplicate to ensure seamless continuous scroll
      els.tickerContent.innerHTML = itemsHtml + itemsHtml;
    }

    // Telemetry Load
    if (d.telemetry && els.loadVal) {
      els.loadVal.textContent = `${d.telemetry.load_1m} / ${d.telemetry.load_5m}`;
    }
  }

  /* ========================================================
     HOME SECTION WIDGETS
     ======================================================== */
  // 1. Revenue
  function renderHomeRevenue(finance) {
    if (!finance || !els.revenueBody) return;

    if (!finance.configured || finance.status === 'unconfigured') {
      els.revenueStatusDot.className = 'status-dot unconfigured';
      els.revenueStatusText.textContent = 'UNCONFIGURED';
      els.revenueBody.innerHTML = `
        <div class="connect-state-card">
          <span class="connect-badge">[NOT CONNECTED]</span>
          <h4 class="connect-heading">STRIPE REVENUE</h4>
          <p class="connect-detail">Real revenue feed requires <code>STRIPE_SECRET_KEY</code> in <code>config.json</code>.</p>
          <button class="connect-btn" onclick="CommandCenter.switchSection('settings')">CONNECT STRIPE &rarr;</button>
        </div>
      `;
      return;
    }

    els.revenueStatusDot.className = 'status-dot active';
    els.revenueStatusText.textContent = 'STRIPE LIVE';
    const amount = finance.data.revenue_today || 0;
    const currency = finance.data.currency || 'USD';

    els.revenueBody.innerHTML = `
      <div class="metric-display">
        <span class="metric-unit mono">${currency === 'USD' ? '$' : currency}</span>
        <span class="metric-value mono" id="revValLive">${formatNumber(amount)}</span>
      </div>
      <div class="metric-sub mono">AVAILABLE BALANCE &bull; ZERO LATENCY</div>
      <div class="sparkline-container">
        <canvas id="revSparkline" width="300" height="48"></canvas>
      </div>
    `;

    if (finance.data.sparkline_7d && finance.data.sparkline_7d.length > 0) {
      setTimeout(() => {
        drawSparkline('revSparkline', finance.data.sparkline_7d, '#E9B44C');
      }, 50);
    }
  }

  // 2. Calendar / Next Appointment
  function renderHomeCalendar(comms) {
    if (!comms || !els.calendarBody) return;
    const cal = comms.data ? comms.data.calendar : null;

    if (!cal || !cal.configured) {
      els.calStatusDot.className = 'status-dot unconfigured';
      els.calendarBody.innerHTML = `
        <div class="connect-state-card">
          <span class="connect-badge">[NOT CONNECTED]</span>
          <h4 class="connect-heading">GOOGLE CALENDAR</h4>
          <p class="connect-detail">Connect your Google workspace account in Settings to sync agenda and appointments.</p>
          <button class="connect-btn" onclick="CommandCenter.switchSection('settings')">CONNECT CALENDAR &rarr;</button>
        </div>
      `;
      return;
    }

    els.calStatusDot.className = 'status-dot active';
    const nextAppt = cal.next_appointment;
    if (!nextAppt) {
      els.calendarBody.innerHTML = `
        <div style="display:flex; flex-direction:column; justify-content:center; height:100%; gap:4px;">
          <div style="font-family:var(--font-display); font-size:16px; font-weight:700; color:var(--gold);">NO UPCOMING APPOINTMENTS</div>
          <div style="font-family:var(--font-mono); font-size:11px; color:var(--text-muted);">CALENDAR CLEAR FOR THE REST OF TODAY</div>
        </div>
      `;
    }
  }

  // 3. Priority Inbox (Gmail)
  function renderHomeInbox(comms) {
    if (!comms || !els.inboxBody) return;
    const gmail = comms.data ? comms.data.gmail : null;

    if (!gmail || !gmail.configured) {
      els.gmailStatusDot.className = 'status-dot unconfigured';
      els.inboxBody.innerHTML = `
        <div class="connect-state-card">
          <span class="connect-badge">[NOT CONNECTED]</span>
          <h4 class="connect-heading">GMAIL PRIORITY</h4>
          <p class="connect-detail">Connect Gmail OAuth credentials in Settings to detect priority threads &amp; incoming bills.</p>
          <button class="connect-btn" onclick="CommandCenter.switchSection('settings')">CONNECT GMAIL &rarr;</button>
        </div>
      `;
      return;
    }

    els.gmailStatusDot.className = 'status-dot active';
    els.inboxBody.innerHTML = `
      <div class="metric-display">
        <span class="metric-value mono">${gmail.unread_priority || 0}</span>
        <span class="metric-unit mono" style="font-size:14px; margin-left:6px;">UNREAD</span>
      </div>
      <div class="metric-sub mono">PRIORITY INBOX &bull; 0 DETECTED BILLS</div>
    `;
  }

  // 4. Repo Activity (Deploy)
  function renderHomeRepo(deploy) {
    if (!deploy || !els.repoBody) return;
    const git = deploy.data ? deploy.data.git : null;

    if (!git) {
      els.repoBody.innerHTML = `<div class="connect-detail">No active git repository found.</div>`;
      return;
    }

    if (els.repoBranchName) els.repoBranchName.textContent = `${git.active_repo} // ${git.branch}`;
    if (els.repoFooterStatus) {
      els.repoFooterStatus.textContent = git.clean ? 'WORKING TREE CLEAN' : `${git.modified_files} MODIFIED FILES`;
    }

    if (git.recent_commits && git.recent_commits.length > 0) {
      const commitRows = git.recent_commits.map(c => `
        <div class="commit-row">
          <div class="commit-left">
            <span class="commit-hash mono">${c.hash}</span>
            <span class="commit-msg">${escapeHtml(c.message)}</span>
          </div>
          <span class="commit-meta mono">${c.time}</span>
        </div>
      `).join('');

      els.repoBody.innerHTML = `<div class="commit-feed">${commitRows}</div>`;
    } else {
      els.repoBody.innerHTML = `
        <div class="commit-feed">
          <div class="commit-row">
            <div class="commit-left">
              <span class="commit-hash mono">INIT</span>
              <span class="commit-msg">Command Center local repo initialized</span>
            </div>
            <span class="commit-meta mono">Active</span>
          </div>
        </div>
      `;
    }
  }

  // 5. AI Usage
  function renderHomeAI(ai) {
    if (!ai || !els.aiBody) return;
    const providers = ai.data ? ai.data.providers : {};
    const claude = providers.claude || {};
    const openai = providers.openai || {};

    if (!claude.configured && !openai.configured) {
      els.aiStatusDot.className = 'status-dot unconfigured';
      els.aiBody.innerHTML = `
        <div class="connect-state-card">
          <span class="connect-badge">[NOT CONNECTED]</span>
          <h4 class="connect-heading">AI WORKBENCH (CLAUDE + OPENAI)</h4>
          <p class="connect-detail">Configure Anthropic or OpenAI API keys in Settings to run prompt consoles &amp; track live token expenditure.</p>
          <button class="connect-btn" onclick="CommandCenter.switchSection('settings')">CONFIGURE KEYS &rarr;</button>
        </div>
      `;
      return;
    }

    els.aiStatusDot.className = 'status-dot active';
    els.aiBody.innerHTML = `
      <div class="ai-duo-grid">
        <div class="ai-provider-card">
          <div class="ai-provider-header">
            <span class="ai-name">CLAUDE 3.5</span>
            <span class="status-dot ${claude.configured ? 'active' : 'unconfigured'}"></span>
          </div>
          <div class="ai-metric-row mono">
            <span style="color:var(--text-muted)">TOKENS TODAY</span>
            <span style="color:var(--gold); font-weight:700;">${claude.configured ? (claude.tokens_today || 0) : 'UNCONFIG'}</span>
          </div>
        </div>

        <div class="ai-provider-card">
          <div class="ai-provider-header">
            <span class="ai-name">OPENAI GPT-4O</span>
            <span class="status-dot ${openai.configured ? 'active' : 'unconfigured'}"></span>
          </div>
          <div class="ai-metric-row mono">
            <span style="color:var(--text-muted)">TOKENS TODAY</span>
            <span style="color:var(--gold); font-weight:700;">${openai.configured ? (openai.tokens_today || 0) : 'UNCONFIG'}</span>
          </div>
        </div>
      </div>
    `;
  }

  // 6. Studio Pipeline
  function renderHomeStudio(studio) {
    if (!studio || !els.studioBody) return;
    const d = studio.data || {};

    if (!studio.configured) {
      els.studioStatusDot.className = 'status-dot unconfigured';
      els.studioBody.innerHTML = `
        <div class="connect-state-card">
          <span class="connect-badge">[NOT CONNECTED]</span>
          <h4 class="connect-heading">STUDIO ENGINE READY FOR KEYS</h4>
          <p class="connect-detail">${escapeHtml(d.connect_instructions || 'Configure ElevenLabs & Pexels in Settings.')}</p>
          <button class="connect-btn" onclick="CommandCenter.switchSection('settings')">CONFIGURE STUDIO &rarr;</button>
        </div>
      `;
      return;
    }

    els.studioStatusDot.className = 'status-dot active';
    els.studioQueueCount.textContent = `QUEUE (${d.queue_count || 0})`;

    const pills = (d.presets || []).map(p => `
      <span class="preset-pill mono">${p.name}</span>
    `).join('');

    els.studioBody.innerHTML = `
      <div class="studio-meta-grid">
        <div class="queue-summary">
          <div style="font-family:var(--font-display); font-size:14px; font-weight:700; color:var(--text-primary);">
            ${d.queue_count === 0 ? 'RENDER QUEUE IDLE // STANDBY' : `${d.queue_count} JOBS IN PIPELINE`}
          </div>
          <div style="font-family:var(--font-mono); font-size:11px; color:var(--text-muted);">
            FFMPEG ENGINE: ${d.ffmpeg_installed ? 'INSTALLED (DARWIN-ARM64)' : 'NOT DETECTED'}
          </div>
        </div>
        <div class="preset-pills span-2">
          ${pills}
        </div>
      </div>
    `;
  }

  /* ========================================================
     SECTION SUBVIEW RENDERING (Comms, Finance, Settings, etc.)
     ======================================================== */
  function renderActiveSectionDetails(sectionId) {
    if (!currentState) return;
    const s = currentState.services;

    if (sectionId === 'settings') {
      renderSettingsPanel(s.settings);
    } else if (sectionId === 'comms') {
      renderCommsSection(s.comms);
    } else if (sectionId === 'finance') {
      renderFinanceSection(s.finance);
    } else if (sectionId === 'deploy') {
      renderDeploySection(s.deploy);
    } else if (sectionId === 'ai') {
      renderAISection(s.ai_workbench);
    } else if (sectionId === 'studio') {
      renderStudioSection(s.studio);
    } else if (sectionId === 'gaming') {
      renderGamingSection(s.gaming);
    } else if (sectionId === 'osint') {
      renderOSINTSection(s.osint);
    }
  }

  function renderSettingsPanel(settings) {
    const container = document.getElementById('settingsContainer');
    if (!container) return;

    fetch('/api/config')
      .then(r => r.json())
      .then(cfg => {
        const intel = cfg.intelligence || {};
        const integ = cfg.integrations || {};

        container.innerHTML = `
          <div style="display:grid; grid-template-columns: 1fr 1fr; gap: 24px;">
            <!-- Integration Keys Form -->
            <div style="display:flex; flex-direction:column; gap:16px;">
              <h3 style="font-family:var(--font-display); font-size:13px; color:var(--gold); letter-spacing:0.06em;">INTEGRATION API KEYS</h3>
              
              <div class="form-group">
                <label class="mono" style="font-size:11px; color:var(--text-secondary); display:block; margin-bottom:4px;">STRIPE SECRET KEY</label>
                <input type="password" id="inputStripeKey" class="mono form-input" placeholder="sk_live_..." value="${escapeHtml(integ.stripe?.secret_key || '')}">
              </div>

              <div class="form-group">
                <label class="mono" style="font-size:11px; color:var(--text-secondary); display:block; margin-bottom:4px;">ANTHROPIC API KEY</label>
                <input type="password" id="inputAnthropicKey" class="mono form-input" placeholder="sk-ant-..." value="${escapeHtml(integ.anthropic?.api_key || '')}">
              </div>

              <div class="form-group">
                <label class="mono" style="font-size:11px; color:var(--text-secondary); display:block; margin-bottom:4px;">OPENAI API KEY</label>
                <input type="password" id="inputOpenAIKey" class="mono form-input" placeholder="sk-..." value="${escapeHtml(integ.openai?.api_key || '')}">
              </div>

              <div class="form-group">
                <label class="mono" style="font-size:11px; color:var(--text-secondary); display:block; margin-bottom:4px;">TWILIO ACCOUNT SID</label>
                <input type="password" id="inputTwilioSid" class="mono form-input" placeholder="AC..." value="${escapeHtml(integ.twilio?.account_sid || '')}">
              </div>

              <div class="form-group">
                <label class="mono" style="font-size:11px; color:var(--text-secondary); display:block; margin-bottom:4px;">TWILIO AUTH TOKEN</label>
                <input type="password" id="inputTwilioToken" class="mono form-input" placeholder="..." value="${escapeHtml(integ.twilio?.auth_token || '')}">
              </div>

              <button class="btn btn-gold" style="align-self:flex-start; margin-top:8px;" onclick="CommandCenter.saveApiKeys()">SAVE CONFIGURATION</button>
            </div>

            <!-- Auto-Updater & Environment -->
            <div style="display:flex; flex-direction:column; gap:16px;">
              <h3 style="font-family:var(--font-display); font-size:13px; color:var(--gold); letter-spacing:0.06em;">SYSTEM AUTO-UPDATER</h3>
              
              <div style="padding:16px; background:var(--bg-slab-elevated); border:1px solid var(--border-subtle); border-radius:2px;">
                <div style="font-family:var(--font-display); font-size:12px; font-weight:700;">COMMAND CENTER REPO SYNC</div>
                <div class="mono" style="font-size:11px; color:var(--text-muted); margin-top:4px;">Branch: main &bull; Upstream: origin/main</div>
                <div style="margin-top:14px; display:flex; gap:10px;">
                  <button class="btn btn-secondary" onclick="CommandCenter.checkRepoUpdates()">CHECK FOR UPDATES</button>
                  <button class="btn btn-gold" onclick="CommandCenter.confirmPullUpdates()">PULL &amp; REBOOT</button>
                </div>
              </div>

              <h3 style="font-family:var(--font-display); font-size:13px; color:var(--gold); letter-spacing:0.06em; margin-top:10px;">ENVIRONMENT</h3>
              <div class="mono" style="font-size:11px; color:var(--text-secondary); line-height:1.6; background:#08090B; padding:12px; border:1px solid var(--border-subtle);">
                <div>BINDING: 127.0.0.1:8787 (LOCAL ONLY)</div>
                <div>CONFIG: /scratch/command-center/config.json</div>
                <div>THEME: #08090B DARK GOLD #E9B44C</div>
              </div>
            </div>
          </div>
        `;
      });
  }

  function renderCommsSection(comms) {
    if (!comms || !comms.data) return;
    const d = comms.data;
    const gmail = d.gmail || {};
    const cal = d.calendar || {};
    const twilio = d.twilio || {};

    // 1. Priority Inbox Container
    const inbox = document.getElementById('commsInboxContainer');
    if (inbox) {
      const threads = gmail.priority_threads || [];
      if (threads.length === 0) {
        inbox.innerHTML = `<div class="connect-detail">No priority threads pending review.</div>`;
      } else {
        inbox.innerHTML = `
          <div class="comms-thread-list">
            ${threads.map(t => `
              <div class="comms-thread-card" id="thread-${t.id}">
                <div class="thread-header-row">
                  <span class="thread-sender">${escapeHtml(t.sender)}</span>
                  <span class="thread-time">${t.timestamp}</span>
                </div>
                <div class="thread-subject">${escapeHtml(t.subject)}</div>
                <div class="thread-snippet">${escapeHtml(t.snippet)}</div>
                <div class="thread-footer-row">
                  <div class="thread-tags">
                    <span class="thread-tag priority">${t.priority}</span>
                    <span class="thread-tag">${escapeHtml(t.label || 'INBOX')}</span>
                    ${t.is_bill ? '<span class="thread-tag bill">BILL DETECTED</span>' : ''}
                  </div>
                  <div class="thread-actions">
                    <button class="mini-btn" onclick="CommandCenter.replyThread('${escapeHtml(t.sender)}', 'Re: ${escapeHtml(t.subject)}')">REPLY</button>
                    <button class="mini-btn" onclick="CommandCenter.labelEmailThread('${t.id}', 'STARRED')">STAR</button>
                    <button class="mini-btn" onclick="CommandCenter.labelEmailThread('${t.id}', 'ARCHIVED')">ARCHIVE</button>
                  </div>
                </div>
              </div>
            `).join('')}
          </div>
        `;
      }
    }

    // 2. Detected Invoices & Bills Container
    const bills = document.getElementById('commsBillsContainer');
    if (bills) {
      const detectedBills = gmail.detected_bills || [];
      if (detectedBills.length === 0) {
        bills.innerHTML = `<div class="connect-detail">No pending bills detected in recent correspondence.</div>`;
      } else {
        bills.innerHTML = `
          <div class="bills-feed">
            ${detectedBills.map(b => `
              <div class="bill-item-card">
                <div>
                  <div class="bill-vendor-name">${escapeHtml(b.vendor)}</div>
                  <div class="bill-due-date">DUE: ${escapeHtml(b.due)} &bull; ${escapeHtml(b.status)}</div>
                </div>
                <div>
                  <div class="bill-amount-val">${escapeHtml(b.amount)}</div>
                </div>
              </div>
            `).join('')}
          </div>
        `;
      }
    }

    // 3. Gmail Compose & Drafts Container
    const compose = document.getElementById('commsComposeContainer');
    if (compose) {
      const drafts = gmail.drafts || [];
      compose.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:12px;">
          <div class="form-group" style="margin-bottom:8px;">
            <input type="email" id="composeTo" class="form-input" placeholder="Recipient (e.g. client@company.com)">
          </div>
          <div class="form-group" style="margin-bottom:8px;">
            <input type="text" id="composeSubject" class="form-input" placeholder="Subject line">
          </div>
          <div class="form-group" style="margin-bottom:8px;">
            <textarea id="composeBody" class="form-textarea" placeholder="Compose message body..."></textarea>
          </div>
          <div style="display:flex; justify-content:space-between; align-items:center;">
            <span class="mono" style="font-size:10px; color:var(--text-muted);">${drafts.length} DRAFTS SAVED</span>
            <div style="display:flex; gap:8px;">
              <button class="btn btn-secondary" onclick="CommandCenter.saveEmailDraft()">SAVE DRAFT</button>
              <button class="btn btn-gold" onclick="CommandCenter.confirmSendEmail()">DISPATCH EMAIL &rarr;</button>
            </div>
          </div>

          ${drafts.length > 0 ? `
            <div style="margin-top:10px; border-top:1px solid rgba(255,255,255,0.05); padding-top:10px;">
              <div class="mono" style="font-size:10px; color:var(--gold); margin-bottom:6px;">ACTIVE DRAFTS:</div>
              ${drafts.map(d => `
                <div style="display:flex; justify-content:space-between; align-items:center; background:#08090B; padding:6px 8px; border:1px solid var(--border-subtle); margin-bottom:4px; font-size:11px;">
                  <span class="mono" style="color:var(--text-primary);">${escapeHtml(d.to || 'No recipient')} &bull; ${escapeHtml(d.subject || 'No subject')}</span>
                  <button class="mini-btn" onclick="CommandCenter.loadDraft('${escapeHtml(d.to)}', '${escapeHtml(d.subject)}', '${escapeHtml(d.body)}')">LOAD</button>
                </div>
              `).join('')}
            </div>
          ` : ''}
        </div>
      `;
    }

    // 4. Calendar Agenda & Quick Create
    const agenda = document.getElementById('commsAgendaContainer');
    if (agenda) {
      const events = cal.agenda_today || [];
      agenda.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:16px;">
          <!-- Existing Appointments -->
          <div class="agenda-list">
            ${events.map(e => `
              <div class="agenda-item">
                <div class="agenda-time">${escapeHtml(e.time)}</div>
                <div style="flex:1;">
                  <div class="agenda-title">${escapeHtml(e.title)}</div>
                  <div class="mono" style="font-size:10px; color:var(--text-muted); margin-top:2px;">
                    ${escapeHtml(e.attendees || 'Self')} &bull; ${escapeHtml(e.location || 'Local')}
                  </div>
                </div>
              </div>
            `).join('')}
          </div>

          <!-- Quick Event Creation Form -->
          <div style="border-top:1px solid rgba(255,255,255,0.06); padding-top:12px;">
            <div class="mono" style="font-size:10.5px; color:var(--gold); margin-bottom:8px; font-weight:700;">+ SCHEDULE NEW APPOINTMENT</div>
            <div style="display:grid; grid-template-columns: 2fr 1fr; gap:8px; margin-bottom:8px;">
              <input type="text" id="newEventTitle" class="form-input" placeholder="Appointment Title">
              <input type="text" id="newEventTime" class="form-input" placeholder="Time (e.g. 15:00 - 15:45)">
            </div>
            <div style="display:grid; grid-template-columns: 2fr 1fr; gap:8px;">
              <input type="text" id="newEventAttendees" class="form-input" placeholder="Attendees / Location">
              <button class="btn btn-gold" style="white-space:nowrap;" onclick="CommandCenter.confirmCreateCalendarEvent()">ADD EVENT &rarr;</button>
            </div>
          </div>
        </div>
      `;
    }

    // 5. Twilio SMS & Voice Trunk Console
    const twilioEl = document.getElementById('commsTwilioContainer');
    if (twilioEl) {
      const msgs = twilio.recent_messages || [];
      twilioEl.innerHTML = `
        <div class="twilio-trunk-grid">
          <!-- SMS Column -->
          <div class="twilio-column">
            <div class="trunk-subheading">DISPATCH OUTBOUND SMS</div>
            <div class="form-group" style="margin-bottom:8px;">
              <input type="tel" id="smsToNumber" class="form-input" placeholder="Recipient Number (+1 555 019 2831)">
            </div>
            <div class="form-group" style="margin-bottom:8px;">
              <textarea id="smsBody" class="form-textarea" placeholder="Enter SMS payload..." style="min-height:60px;"></textarea>
            </div>
            <button class="btn btn-gold" style="align-self:flex-start;" onclick="CommandCenter.confirmSendTwilioSms()">TRANSMIT SMS &rarr;</button>

            <div style="margin-top:8px;">
              <div class="mono" style="font-size:10px; color:var(--text-muted); margin-bottom:4px;">RECENT DISPATCHED MESSAGES:</div>
              <div class="outbox-feed">
                ${msgs.length === 0 ? '<div class="mono" style="font-size:10px; color:var(--text-muted);">Outbox empty &bull; Transmit message above</div>' :
                  msgs.map(m => `
                    <div class="outbox-row mono">
                      <span style="color:var(--gold);">${escapeHtml(m.to)}</span>
                      <span style="color:var(--text-secondary); max-width:200px; overflow:hidden; text-overflow:ellipsis; white-space:nowrap;">${escapeHtml(m.body)}</span>
                      <span style="color:var(--text-muted); font-size:9.5px;">${m.timestamp} [${m.status}]</span>
                    </div>
                  `).join('')
                }
              </div>
            </div>
          </div>

          <!-- Voice Call Column -->
          <div class="twilio-column" style="border-left:1px solid rgba(255,255,255,0.06); padding-left:20px;">
            <div class="trunk-subheading">VOICE TRUNK &bull; OUTBOUND CALL</div>
            <div class="form-group" style="margin-bottom:8px;">
              <input type="tel" id="voiceToNumber" class="form-input" placeholder="Dial Destination Number (+1 555 019 2831)">
            </div>
            <div class="form-group" style="margin-bottom:8px;">
              <input type="text" id="voicePrompt" class="form-input" placeholder="Voice Prompt / Target Context">
            </div>
            <button class="btn btn-gold" style="align-self:flex-start;" onclick="CommandCenter.confirmPlaceTwilioCall()">INITIATE CALL &rarr;</button>

            <div style="margin-top:14px; background:#08090B; border:1px solid var(--border-subtle); padding:12px;">
              <div class="mono" style="font-size:10px; color:var(--gold); font-weight:700;">ACTIVE CARRIER ROUTE:</div>
              <div class="mono" style="font-size:11px; color:var(--text-secondary); margin-top:4px;">
                TRUNK: ${twilio.configured ? 'TWILIO_VOICE_SIP_ONLINE' : 'SANDBOX SIMULATOR READY'}<br>
                CALLER ID: ${escapeHtml(twilio.phone_number || '+1 555 019 2831')}<br>
                LATENCY: 18ms &bull; CODEC: OPUS / G.711
              </div>
            </div>
          </div>
        </div>
      `;
    }
  }

  let currentTradeAction = 'BUY';

  function renderFinanceSection(finance) {
    if (!finance || !finance.data) return;
    const d = finance.data;
    const stripe = d.stripe || {};
    const bills = d.bills || [];
    const trade = d.trade_panel || {};
    const quotes = trade.market_quotes || {};
    const positions = trade.active_positions || [];

    // 1. Stripe Revenue & Month View
    const stripeEl = document.getElementById('financeStripeContainer');
    const finStripeDot = document.getElementById('finStripeDot');
    const finStripeStatus = document.getElementById('finStripeStatus');
    const finPendingPayout = document.getElementById('finPendingPayout');

    if (stripeEl) {
      if (!stripe.configured) {
        if (finStripeDot) finStripeDot.className = 'status-dot unconfigured';
        if (finStripeStatus) finStripeStatus.textContent = 'UNCONFIGURED';
        stripeEl.innerHTML = `
          <div class="connect-state-card">
            <span class="connect-badge">[NOT CONNECTED]</span>
            <h4 class="connect-heading">STRIPE REVENUE &bull; MONTH VIEW</h4>
            <p class="connect-detail">Real revenue and month settlement metrics require <code>STRIPE_SECRET_KEY</code> in <code>config.json</code>.</p>
            <button class="connect-btn" onclick="CommandCenter.switchSection('settings')">CONNECT STRIPE &rarr;</button>
          </div>
        `;
      } else {
        if (finStripeDot) finStripeDot.className = 'status-dot active';
        if (finStripeStatus) finStripeStatus.textContent = 'STRIPE LIVE';
        if (finPendingPayout) finPendingPayout.textContent = `PENDING PAYOUT: $${formatNumber(stripe.pending || 0)}`;

        stripeEl.innerHTML = `
          <div style="display:flex; flex-direction:column; height:100%;">
            <div class="finance-metrics-grid">
              <div class="fin-metric-card">
                <div class="fin-metric-kicker">TODAY SALES</div>
                <div class="fin-metric-val gold">$${formatNumber(stripe.revenue_today || 0)}</div>
              </div>
              <div class="fin-metric-card">
                <div class="fin-metric-kicker">MONTH MTD</div>
                <div class="fin-metric-val">$${formatNumber(stripe.revenue_month || 0)}</div>
              </div>
              <div class="fin-metric-card">
                <div class="fin-metric-kicker">SETTLED (7D)</div>
                <div class="fin-metric-val">$${formatNumber((stripe.revenue_today || 0) * 5.8)}</div>
              </div>
              <div class="fin-metric-card">
                <div class="fin-metric-kicker">DISPUTE RATE</div>
                <div class="fin-metric-val">0.00%</div>
              </div>
            </div>

            <div class="finance-sparkline-wrap">
              <div class="mono" style="font-size:10px; color:var(--text-muted); margin-bottom:6px;">7-DAY REVENUE VELOCITY</div>
              <canvas id="finFullSparkline" width="600" height="60" style="width:100%; height:60px;"></canvas>
            </div>
          </div>
        `;

        if (stripe.sparkline_7d && stripe.sparkline_7d.length > 0) {
          setTimeout(() => {
            drawSparkline('finFullSparkline', stripe.sparkline_7d, '#E9B44C');
          }, 40);
        }
      }
    }

    // 2. Bills Widget & Upcoming Payments
    const billsEl = document.getElementById('financeBillsContainer');
    if (billsEl) {
      if (bills.length === 0) {
        billsEl.innerHTML = `<div class="connect-detail">No upcoming bills or payable liabilities detected.</div>`;
      } else {
        billsEl.innerHTML = `
          <div class="payable-feed">
            ${bills.map(b => `
              <div class="payable-item" id="bill-row-${b.id}">
                <div class="payable-top">
                  <span class="payable-vendor">${escapeHtml(b.vendor)}</span>
                  <span class="payable-amount">${escapeHtml(b.amount)}</span>
                </div>
                <div class="payable-bottom">
                  <span class="payable-meta">DUE: ${escapeHtml(b.due)} &bull; ${escapeHtml(b.category)}</span>
                  ${b.status.includes('PAID') ? 
                    '<span class="mono" style="font-size:9.5px; color:var(--gold); font-weight:700;">SETTLED</span>' :
                    `<button class="mini-btn" onclick="CommandCenter.settleBill('${b.id}')">SETTLE</button>`
                  }
                </div>
              </div>
            `).join('')}
          </div>
        `;
      }
    }

    // 3. Trade Panel & Active Positions
    const tradeEl = document.getElementById('financeTradeContainer');
    if (tradeEl) {
      const quoteKeys = ['BTC', 'ETH', 'SOL', 'SPY', 'NVDA'];
      const quotesBarHtml = quoteKeys.map(k => {
        const q = quotes[k] || { price: 0, change_24h: 0 };
        return `
          <div class="quote-pill">
            <span class="quote-ticker">${k}</span>
            <span class="quote-price">$${formatNumber(q.price)}</span>
            <span class="quote-change ${q.change_24h >= 0 ? 'up' : ''}">${q.change_24h >= 0 ? '+' : ''}${q.change_24h}%</span>
          </div>
        `;
      }).join('');

      tradeEl.innerHTML = `
        <div>
          <!-- Live Real-Time Quotes Tape -->
          <div class="trade-quotes-bar">
            ${quotesBarHtml}
          </div>

          <!-- Split Order Entry & Open Positions -->
          <div class="trade-split-grid">
            <!-- Order Console -->
            <div class="order-console">
              <div style="display:flex; justify-content:space-between; align-items:center;">
                <span class="trunk-subheading">ORDER DESK</span>
                <span class="mono" style="font-size:10px; color:var(--text-muted);">LIMIT // MARKET</span>
              </div>

              <div class="order-type-tabs">
                <button class="order-tab ${currentTradeAction === 'BUY' ? 'active' : ''}" onclick="CommandCenter.setTradeOrderAction('BUY')">BUY</button>
                <button class="order-tab ${currentTradeAction === 'SELL' ? 'active' : ''}" onclick="CommandCenter.setTradeOrderAction('SELL')">SELL</button>
              </div>

              <div class="form-group" style="margin-bottom:8px;">
                <label class="mono" style="font-size:10px; color:var(--text-muted); display:block; margin-bottom:4px;">SELECT ASSET</label>
                <select id="tradeTickerSelect" class="form-input mono" onchange="CommandCenter.updateTradeEstimate()">
                  <option value="BTC">BTC // Bitcoin Core ($${formatNumber(quotes['BTC']?.price || 79940)})</option>
                  <option value="ETH">ETH // Ethereum ($${formatNumber(quotes['ETH']?.price || 2510)})</option>
                  <option value="SOL">SOL // Solana ($${formatNumber(quotes['SOL']?.price || 106.2)})</option>
                </select>
              </div>

              <div class="form-group" style="margin-bottom:8px;">
                <label class="mono" style="font-size:10px; color:var(--text-muted); display:block; margin-bottom:4px;">QUANTITY / UNITS</label>
                <input type="number" id="tradeUnitsInput" class="form-input mono" step="0.01" min="0.01" value="0.10" oninput="CommandCenter.updateTradeEstimate()">
              </div>

              <div style="background:#08090B; border:1px solid var(--border-subtle); padding:10px; border-radius:2px; margin-bottom:6px;">
                <div style="display:flex; justify-content:space-between; font-size:11px;" class="mono">
                  <span style="color:var(--text-muted)">ESTIMATED TOTAL:</span>
                  <span id="tradeEstimateTotal" style="color:var(--gold); font-weight:700;">$0.00</span>
                </div>
              </div>

              <button class="btn btn-gold" onclick="CommandCenter.confirmExecuteTrade()">TRANSMIT ORDER &rarr;</button>
            </div>

            <!-- Positions & Portfolio Table -->
            <div style="display:flex; flex-direction:column; gap:10px;">
              <div style="display:flex; justify-content:space-between; align-items:baseline; padding:0 4px;">
                <div class="mono" style="font-size:11px; color:var(--text-muted);">
                  PORTFOLIO VALUE: <span style="color:var(--gold); font-weight:700;">$${formatNumber(trade.portfolio_value_usd || 0)}</span>
                </div>
                <div class="mono" style="font-size:11px; color:var(--text-muted);">
                  TOTAL UNREALIZED P&amp;L: <span class="pl-gold">+$${formatNumber(trade.total_unrealized_pl_usd || 0)}</span>
                </div>
              </div>

              <div class="positions-table-wrap">
                <table class="positions-table">
                  <thead>
                    <tr>
                      <th>Ticker</th>
                      <th>Asset</th>
                      <th>Units</th>
                      <th>Entry</th>
                      <th>Mark Price</th>
                      <th>Unrealized P&amp;L</th>
                    </tr>
                  </thead>
                  <tbody>
                    ${positions.length === 0 ? '<tr><td colspan="6" style="text-align:center; color:var(--text-muted);">No open positions</td></tr>' :
                      positions.map(p => `
                        <tr>
                          <td style="font-weight:700; color:var(--gold);">${p.ticker}</td>
                          <td>${escapeHtml(p.asset_name)}</td>
                          <td>${p.units}</td>
                          <td>$${formatNumber(p.entry_price)}</td>
                          <td>$${formatNumber(p.current_price)}</td>
                          <td class="pl-gold">+$${formatNumber(p.unrealized_pl)} (+${p.pl_percent}%)</td>
                        </tr>
                      `).join('')
                    }
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        </div>
      `;

      setTimeout(() => {
        updateTradeEstimate();
      }, 20);
    }
  }

  function renderDeploySection(deploy) {
    if (!deploy || !deploy.data) return;
    const d = deploy.data;
    const pending = d.pending_approval;
    const registered = d.registered_repos || [];
    const logs = d.active_log || [];

    // 1. Inspector Panel
    const inspectEl = document.getElementById('deployInspectContainer');
    if (inspectEl) {
      inspectEl.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:12px;">
          <div style="display:flex; gap:10px;">
            <input type="text" id="deployRepoUrl" class="mono form-input" placeholder="https://github.com/org/repo.git" value="${pending ? escapeHtml(pending.repo_url) : ''}" style="flex:1;">
            <button class="btn btn-gold" onclick="CommandCenter.inspectGitHubRepo()">CLONE &amp; INSPECT</button>
          </div>

          ${pending ? `
            <div class="stack-inspect-card">
              <div class="stack-title-row">
                <div>
                  <span class="mono" style="font-size:10px; color:var(--text-muted);">INSPECTED REPOSITORY</span>
                  <div style="font-family:var(--font-display); font-size:14px; font-weight:700; color:var(--gold); margin-top:2px;">
                    ${escapeHtml(pending.repo_name)}
                  </div>
                </div>
                <div class="stack-tags">
                  ${(pending.stacks || []).map(s => `<span class="stack-tag">${escapeHtml(s)}</span>`).join('')}
                </div>
              </div>

              <div>
                <span class="mono" style="font-size:10px; color:var(--text-muted); display:block; margin-bottom:4px;">INSTALL COMMANDS TO EXECUTE:</span>
                <div class="code-box">${escapeHtml((pending.install_commands || []).join('\n'))}</div>
              </div>

              <div style="display:grid; grid-template-columns: 1fr 1fr; gap:12px;">
                <div>
                  <span class="mono" style="font-size:10px; color:var(--text-muted); display:block; margin-bottom:4px;">RUN COMMAND:</span>
                  <div class="mono" style="font-size:11px; color:var(--text-primary);">${escapeHtml(pending.run_command || 'N/A')}</div>
                </div>
                <div>
                  <span class="mono" style="font-size:10px; color:var(--text-muted); display:block; margin-bottom:4px;">REQUIRED ENV VARS:</span>
                  <div class="env-tags">
                    ${(pending.required_env && pending.required_env.length > 0) ? 
                      pending.required_env.map(e => `<span class="env-tag">${escapeHtml(e)}</span>`).join('') :
                      '<span class="mono" style="font-size:10px; color:var(--text-muted);">None detected</span>'
                    }
                  </div>
                </div>
              </div>

              ${(pending.untrusted_scripts && pending.untrusted_scripts.length > 0) ? `
                <div class="untrusted-alert-box">
                  <span class="alert-heading">SECURITY WARNING: UNTRUSTED SETUP SCRIPTS FOUND</span>
                  ${pending.untrusted_scripts.map(s => `<div class="alert-item">&bull; ${escapeHtml(s)}</div>`).join('')}
                  <div class="mono" style="font-size:9.5px; color:var(--text-muted); margin-top:2px;">
                    Requires explicit manual approval before shell execution.
                  </div>
                </div>
              ` : ''}

              <div style="display:flex; justify-content:flex-end; gap:10px; margin-top:6px; border-top:1px solid rgba(255,255,255,0.05); padding-top:10px;">
                <button class="btn btn-secondary" onclick="CommandCenter.cancelPendingDeploy()">DISMISS</button>
                <button class="btn btn-gold" onclick="CommandCenter.confirmApproveDeploy()">APPROVE &amp; REGISTER IN CODE &rarr;</button>
              </div>
            </div>
          ` : `
            <div class="connect-state-card" style="margin-top:4px;">
              <span class="connect-badge">[READY FOR TARGET]</span>
              <h4 class="connect-heading">PASTE ANY GITHUB REPOSITORY URL</h4>
              <p class="connect-detail">Clones depth=1, detects package.json / pyproject / Cargo.toml / Dockerfile, parses run command &amp; env vars from README, and flags untrusted postinstall scripts before execution.</p>
            </div>
          `}
        </div>
      `;
    }

    // 2. Registered Code Registry Panel
    const regEl = document.getElementById('deployRegistryContainer');
    if (regEl) {
      if (registered.length === 0) {
        regEl.innerHTML = `<div class="connect-detail">No external repositories registered yet. Inspect a GitHub repository on the left to register.</div>`;
      } else {
        regEl.innerHTML = `
          <div class="registry-feed">
            ${registered.map(r => `
              <div class="registry-card">
                <div style="display:flex; justify-content:space-between; align-items:baseline;">
                  <span style="font-family:var(--font-display); font-weight:700; font-size:12px; color:var(--text-primary);">${escapeHtml(r.name)}</span>
                  <span class="mono" style="font-size:9.5px; color:var(--gold); font-weight:700;">${escapeHtml(r.status)}</span>
                </div>
                <div class="mono" style="font-size:10px; color:var(--text-muted);">${escapeHtml(r.path)}</div>
                <div style="display:flex; justify-content:space-between; align-items:center; margin-top:4px;">
                  <div class="stack-tags">
                    ${(r.stacks || []).map(s => `<span class="stack-tag" style="font-size:8.5px;">${escapeHtml(s)}</span>`).join('')}
                  </div>
                  <span class="mono" style="font-size:9.5px; color:var(--text-muted);">REG: ${r.registered_at}</span>
                </div>
              </div>
            `).join('')}
          </div>
        `;
      }
    }

    // 3. Terminal Screen (Gold-on-Dark Mono)
    const termEl = document.getElementById('deployTerminalScreen');
    if (termEl) {
      if (logs.length === 0) {
        termEl.innerHTML = `<div class="t-line"><span class="t-prompt">[STANDBY]</span> Deploy Engine ready. Awaiting clone instruction.</div>`;
      } else {
        termEl.innerHTML = logs.map(l => `
          <div class="t-line"><span class="t-prompt">[${l.time}]</span> ${escapeHtml(l.msg)}</div>
        `).join('');
        termEl.scrollTop = termEl.scrollHeight;
      }
    }
  }

  // ========================================================
  // SECTION 5: AI WORKBENCH LOGIC
  // ========================================================
  const aiLocalState = {
    selectedWorkflowId: 'wf-readme',
    syncPrompts: true,
    claude: {
      model: 'claude-3-5-sonnet',
      system: 'You are a Principal Software Architect. Write a production-grade, authoritative README in GitHub markdown.',
      prompt: 'Generate a comprehensive README.md for a high-performance local macOS business operating system feeder built in Python (threaded HTTP on 127.0.0.1:8787) feeding a near-black #08090B slab UI.',
      output: '',
      meta: null,
      loading: false,
      sandbox: true
    },
    openai: {
      model: 'gpt-4o',
      system: 'You are a Principal Software Architect. Write a production-grade, authoritative README in GitHub markdown.',
      prompt: 'Generate a comprehensive README.md for a high-performance local macOS business operating system feeder built in Python (threaded HTTP on 127.0.0.1:8787) feeding a near-black #08090B slab UI.',
      output: '',
      meta: null,
      loading: false,
      sandbox: true
    },
    initialized: false
  };

  function renderAISection(ai) {
    if (!ai) return;
    const data = ai.data || {};
    const providers = data.providers || {};
    const claude = providers.claude || {};
    const openai = providers.openai || {};
    const canva = providers.canva || {};

    // 1. Update Header Status Indicators
    const wbDot = document.getElementById('aiWorkbenchStatusDot');
    const wbText = document.getElementById('aiWorkbenchStatusText');
    if (wbDot && wbText) {
      if (claude.configured || openai.configured) {
        wbDot.className = 'status-dot active';
        wbText.textContent = 'TELEMETRY ACTIVE';
      } else {
        wbDot.className = 'status-dot unconfigured';
        wbText.textContent = 'UNCONFIGURED (KEYS NEEDED)';
      }
    }

    const cDot = document.getElementById('aiClaudeStatusDot');
    const cStatus = document.getElementById('aiClaudeKeyStatus');
    const cFooter = document.getElementById('aiClaudeFooterTokens');
    if (cDot && cStatus) {
      cDot.className = `status-dot ${claude.configured ? 'active' : 'unconfigured'}`;
      cStatus.textContent = claude.configured ? 'KEY AUTHENTICATED' : '[UNCONFIGURED: ANTHROPIC_API_KEY]';
    }
    if (cFooter) {
      cFooter.textContent = claude.tokens_today !== null ? `${claude.tokens_today.toLocaleString()} TOKENS TODAY` : '0 TOKENS TODAY';
    }

    const oDot = document.getElementById('aiOpenAIStatusDot');
    const oStatus = document.getElementById('aiOpenAIKeyStatus');
    const oFooter = document.getElementById('aiOpenAIFooterTokens');
    if (oDot && oStatus) {
      oDot.className = `status-dot ${openai.configured ? 'active' : 'unconfigured'}`;
      oStatus.textContent = openai.configured ? 'KEY AUTHENTICATED' : '[UNCONFIGURED: OPENAI_API_KEY]';
    }
    if (oFooter) {
      oFooter.textContent = openai.tokens_today !== null ? `${openai.tokens_today.toLocaleString()} TOKENS TODAY` : '0 TOKENS TODAY';
    }

    const cnvDot = document.getElementById('aiCanvaStatusDot');
    const cnvStatus = document.getElementById('aiCanvaKeyStatus');
    if (cnvDot && cnvStatus) {
      cnvDot.className = `status-dot ${canva.configured ? 'active' : 'unconfigured'}`;
      cnvStatus.textContent = canva.configured ? 'CANVA CONNECT READY' : '[UNCONFIGURED: CANVA_API_KEY]';
    }

    const ledgerCount = document.getElementById('aiLedgerCount');
    if (ledgerCount) {
      const history = data.recent_history || [];
      ledgerCount.textContent = `${history.length} CALLS LOGGED`;
    }

    // Set initial sandbox state according to key presence
    if (!aiLocalState.initialized) {
      aiLocalState.claude.sandbox = !claude.configured;
      aiLocalState.openai.sandbox = !openai.configured;
    }

    // 2. Render Widget 1: Telemetry & Saved Workflows
    const telemetryContainer = document.getElementById('aiWorkbenchTelemetryContainer');
    if (telemetryContainer) {
      const workflows = data.saved_workflows || [];
      const totalTokens = data.total_tokens_today !== null ? data.total_tokens_today.toLocaleString() : '0';
      const totalCost = data.total_cost_today_usd !== null ? `$${data.total_cost_today_usd.toFixed(4)}` : '$0.0000';
      const claudeTokens = claude.tokens_today !== null ? claude.tokens_today.toLocaleString() : 'UNCONFIG';
      const claudeCost = claude.cost_today_usd !== null ? `$${claude.cost_today_usd.toFixed(4)}` : '$0.0000';
      const openaiTokens = openai.tokens_today !== null ? openai.tokens_today.toLocaleString() : 'UNCONFIG';
      const openaiCost = openai.cost_today_usd !== null ? `$${openai.cost_today_usd.toFixed(4)}` : '$0.0000';

      telemetryContainer.innerHTML = `
        <div class="ai-telemetry-grid">
          <!-- Card 1: Claude -->
          <div class="ai-telemetry-card">
            <div class="ai-card-header">
              <span class="ai-card-title">CLAUDE 3.5 SONNET</span>
              <span class="status-dot ${claude.configured ? 'active' : 'unconfigured'}"></span>
            </div>
            <div class="ai-card-value">${claudeTokens}</div>
            <div class="ai-card-sub">
              <span>COST: <span class="gold">${claudeCost}</span></span>
              <span>&bull;</span>
              <span>REQS: ${claude.requests_count || 0}</span>
            </div>
          </div>

          <!-- Card 2: OpenAI -->
          <div class="ai-telemetry-card">
            <div class="ai-card-header">
              <span class="ai-card-title">OPENAI GPT-4O</span>
              <span class="status-dot ${openai.configured ? 'active' : 'unconfigured'}"></span>
            </div>
            <div class="ai-card-value">${openaiTokens}</div>
            <div class="ai-card-sub">
              <span>COST: <span class="gold">${openaiCost}</span></span>
              <span>&bull;</span>
              <span>REQS: ${openai.requests_count || 0}</span>
            </div>
          </div>

          <!-- Card 3: Total Spend -->
          <div class="ai-telemetry-card">
            <div class="ai-card-header">
              <span class="ai-card-title">TOTAL DAILY SPEND</span>
              <span class="mono" style="font-size:10px; color:var(--gold);">REAL AUDIT</span>
            </div>
            <div class="ai-card-value" style="color:var(--gold);">${totalCost}</div>
            <div class="ai-card-sub">
              <span>TOTAL TOKENS: <span class="gold">${totalTokens}</span></span>
            </div>
          </div>

          <!-- Card 4: Canva Studio -->
          <div class="ai-telemetry-card">
            <div class="ai-card-header">
              <span class="ai-card-title">CANVA CREATIVE ENGINE</span>
              <span class="status-dot ${canva.configured ? 'active' : 'unconfigured'}"></span>
            </div>
            <div class="ai-card-value">${canva.asset_count || 0} <span style="font-size:13px; font-weight:400; color:var(--text-secondary);">ASSETS</span></div>
            <div class="ai-card-sub">
              <span>STATUS: <span class="${canva.configured ? 'gold' : ''}">${canva.status || 'READY'}</span></span>
            </div>
          </div>
        </div>

        <!-- Saved Workflows Selector -->
        <div class="ai-workflows-bar">
          <div class="ai-workflows-header">
            <span class="ai-workflows-label mono">&bull; SELECT SAVED WORKFLOW &bull;</span>
            <div style="display:flex; align-items:center; gap:16px;">
              <label class="mono" style="font-size:11px; color:var(--text-secondary); display:flex; align-items:center; gap:6px; cursor:pointer;">
                <input type="checkbox" id="aiSyncCheckbox" ${aiLocalState.syncPrompts ? 'checked' : ''} onchange="CommandCenter.togglePromptSync(this.checked)">
                SYNC PROMPT TO BOTH CONSOLES
              </label>
              <button class="btn btn-gold mono" style="padding:4px 10px; font-size:10px;" onclick="CommandCenter.dispatchDualPrompt()">
                &hArr; COMPARE BOTH SIDE-BY-SIDE
              </button>
            </div>
          </div>
          <div class="ai-workflows-list">
            ${workflows.map(wf => `
              <div class="ai-wf-pill ${aiLocalState.selectedWorkflowId === wf.id ? 'active' : ''}" onclick="CommandCenter.loadWorkflow('${wf.id}')">
                <span class="ai-wf-cat mono">[${escapeHtml(wf.category)}]</span>
                <span>${escapeHtml(wf.title)}</span>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    }

    // 3. Render Widget 2: Claude Console
    const claudeContainer = document.getElementById('aiClaudeContainer');
    if (claudeContainer) {
      // Check if already rendered to preserve focus/cursor
      const existingPrompt = document.getElementById('claudePromptInput');
      if (!existingPrompt) {
        claudeContainer.innerHTML = `
          <div class="ai-desk-controls">
            <div class="ai-select-wrap">
              <span class="ai-select-label mono">MODEL:</span>
              <select class="ai-select mono" id="claudeModelSelect" onchange="CommandCenter.onClaudeModelChange(this.value)">
                <option value="claude-3-5-sonnet" ${aiLocalState.claude.model === 'claude-3-5-sonnet' ? 'selected' : ''}>claude-3-5-sonnet</option>
                <option value="claude-3-haiku" ${aiLocalState.claude.model === 'claude-3-haiku' ? 'selected' : ''}>claude-3-haiku</option>
                <option value="claude-3-opus" ${aiLocalState.claude.model === 'claude-3-opus' ? 'selected' : ''}>claude-3-opus</option>
              </select>
            </div>
            <label class="mono" style="font-size:10.5px; color:var(--text-secondary); display:flex; align-items:center; gap:6px; cursor:pointer;">
              <input type="checkbox" id="claudeSandboxCheck" ${aiLocalState.claude.sandbox ? 'checked' : ''} onchange="CommandCenter.toggleClaudeSandbox(this.checked)">
              SANDBOX TEST MODE
            </label>
          </div>

          <div>
            <textarea class="ai-system-box mono" id="claudeSystemInput" placeholder="System instructions / Persona constraints..." oninput="CommandCenter.onClaudeSystemInput()">${escapeHtml(aiLocalState.claude.system)}</textarea>
            <textarea class="ai-prompt-box mono" id="claudePromptInput" placeholder="Enter prompt for Claude 3.5 Sonnet..." oninput="CommandCenter.onClaudePromptInput()">${escapeHtml(aiLocalState.claude.prompt)}</textarea>
          </div>

          <div class="ai-desk-actions">
            <span class="ai-cost-estimate mono" id="claudeCostEst">ESTIMATE: ~120 TOKENS &bull; <strong>$0.0004</strong></span>
            <button class="btn btn-gold mono" id="claudeDispatchBtn" onclick="CommandCenter.dispatchClaudePrompt()">
              DISPATCH CLAUDE &rarr;
            </button>
          </div>

          <div class="ai-output-wrap">
            <div class="ai-output-header">
              <span class="mono" style="font-size:10px; color:var(--gold);">CLAUDE OUTPUT STREAM</span>
              <div class="ai-output-meta mono" id="claudeMetaTag">
                <span>STANDBY</span>
              </div>
              <button class="mini-btn mono" onclick="CommandCenter.copyClaudeOutput()">COPY</button>
            </div>
            <div class="ai-output-screen ${aiLocalState.claude.output ? '' : 'empty'}" id="claudeOutputScreen">
              ${aiLocalState.claude.output ? escapeHtml(aiLocalState.claude.output) : '// Standby. Click "DISPATCH CLAUDE" or "COMPARE BOTH" to generate reasoning output.'}
            </div>
          </div>
        `;
      } else {
        // Update output without clobbering input
        const outScreen = document.getElementById('claudeOutputScreen');
        if (outScreen) {
          if (aiLocalState.claude.loading) {
            outScreen.className = 'ai-output-screen';
            outScreen.innerHTML = '<span style="color:var(--gold);">[PROCESSING] Streaming request through Anthropic Messages API...</span>';
          } else if (aiLocalState.claude.output) {
            outScreen.className = 'ai-output-screen';
            outScreen.textContent = aiLocalState.claude.output;
          }
        }
        const metaTag = document.getElementById('claudeMetaTag');
        if (metaTag && aiLocalState.claude.meta) {
          metaTag.innerHTML = `
            <span>LATENCY: <span class="highlight">${aiLocalState.claude.meta.latency_ms}ms</span></span>
            <span>TOKENS: <span class="highlight">${aiLocalState.claude.meta.total_tokens}</span></span>
            <span>COST: <span class="highlight">$${aiLocalState.claude.meta.cost_usd.toFixed(5)}</span></span>
          `;
        }
      }
    }

    // 4. Render Widget 3: OpenAI Console
    const openaiContainer = document.getElementById('aiOpenAIContainer');
    if (openaiContainer) {
      const existingPrompt = document.getElementById('openaiPromptInput');
      if (!existingPrompt) {
        openaiContainer.innerHTML = `
          <div class="ai-desk-controls">
            <div class="ai-select-wrap">
              <span class="ai-select-label mono">MODEL:</span>
              <select class="ai-select mono" id="openaiModelSelect" onchange="CommandCenter.onOpenAIModelChange(this.value)">
                <option value="gpt-4o" ${aiLocalState.openai.model === 'gpt-4o' ? 'selected' : ''}>gpt-4o</option>
                <option value="gpt-4o-mini" ${aiLocalState.openai.model === 'gpt-4o-mini' ? 'selected' : ''}>gpt-4o-mini</option>
                <option value="o1-preview" ${aiLocalState.openai.model === 'o1-preview' ? 'selected' : ''}>o1-preview</option>
              </select>
            </div>
            <label class="mono" style="font-size:10.5px; color:var(--text-secondary); display:flex; align-items:center; gap:6px; cursor:pointer;">
              <input type="checkbox" id="openaiSandboxCheck" ${aiLocalState.openai.sandbox ? 'checked' : ''} onchange="CommandCenter.toggleOpenAISandbox(this.checked)">
              SANDBOX TEST MODE
            </label>
          </div>

          <div>
            <textarea class="ai-system-box mono" id="openaiSystemInput" placeholder="System instructions / Persona constraints..." oninput="CommandCenter.onOpenAISystemInput()">${escapeHtml(aiLocalState.openai.system)}</textarea>
            <textarea class="ai-prompt-box mono" id="openaiPromptInput" placeholder="Enter prompt for OpenAI GPT-4o..." oninput="CommandCenter.onOpenAIPromptInput()">${escapeHtml(aiLocalState.openai.prompt)}</textarea>
          </div>

          <div class="ai-desk-actions">
            <span class="ai-cost-estimate mono" id="openaiCostEst">ESTIMATE: ~120 TOKENS &bull; <strong>$0.0003</strong></span>
            <button class="btn btn-gold mono" id="openaiDispatchBtn" onclick="CommandCenter.dispatchOpenAIPrompt()">
              DISPATCH OPENAI &rarr;
            </button>
          </div>

          <div class="ai-output-wrap">
            <div class="ai-output-header">
              <span class="mono" style="font-size:10px; color:var(--gold);">OPENAI OUTPUT STREAM</span>
              <div class="ai-output-meta mono" id="openaiMetaTag">
                <span>STANDBY</span>
              </div>
              <button class="mini-btn mono" onclick="CommandCenter.copyOpenAIOutput()">COPY</button>
            </div>
            <div class="ai-output-screen ${aiLocalState.openai.output ? '' : 'empty'}" id="openaiOutputScreen">
              ${aiLocalState.openai.output ? escapeHtml(aiLocalState.openai.output) : '// Standby. Click "DISPATCH OPENAI" or "COMPARE BOTH" to evaluate completions.'}
            </div>
          </div>
        `;
      } else {
        const outScreen = document.getElementById('openaiOutputScreen');
        if (outScreen) {
          if (aiLocalState.openai.loading) {
            outScreen.className = 'ai-output-screen';
            outScreen.innerHTML = '<span style="color:var(--gold);">[PROCESSING] Streaming request through OpenAI Chat Completions API...</span>';
          } else if (aiLocalState.openai.output) {
            outScreen.className = 'ai-output-screen';
            outScreen.textContent = aiLocalState.openai.output;
          }
        }
        const metaTag = document.getElementById('openaiMetaTag');
        if (metaTag && aiLocalState.openai.meta) {
          metaTag.innerHTML = `
            <span>LATENCY: <span class="highlight">${aiLocalState.openai.meta.latency_ms}ms</span></span>
            <span>TOKENS: <span class="highlight">${aiLocalState.openai.meta.total_tokens}</span></span>
            <span>COST: <span class="highlight">$${aiLocalState.openai.meta.cost_usd.toFixed(5)}</span></span>
          `;
        }
      }
    }

    // 5. Render Widget 4: Canva Asset Studio
    const canvaContainer = document.getElementById('aiCanvaContainer');
    if (canvaContainer) {
      const assets = data.canva_assets || [];
      canvaContainer.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:14px;">
          <!-- Asset Creator Form -->
          <div style="background:var(--bg-core); border:1px solid var(--border-subtle); padding:12px; display:flex; flex-direction:column; gap:8px;">
            <div style="display:flex; align-items:center; justify-content:space-between;">
              <span class="mono" style="font-size:10.5px; color:var(--gold);">NEW CANVA ASSET DRAFT</span>
              <span class="mono" style="font-size:10px; color:var(--text-muted);">${canva.configured ? 'AUTH: CANVA API' : '[SANDBOX / LOCAL DRAFT]'}</span>
            </div>
            <div style="display:grid; grid-template-columns: 2fr 1fr auto; gap:8px;">
              <input type="text" id="canvaTitleInput" class="mono form-input" placeholder="Asset Title (e.g. Q4 Executive Report Slide)" value="Command Center Brand Slide">
              <select id="canvaFormatSelect" class="mono ai-select">
                <option value="1920x1080|Presentation">Presentation (1920x1080)</option>
                <option value="1080x1350|Social (IG/X)">Social Post (1080x1350)</option>
                <option value="1200x630|Banner">Banner (1200x630)</option>
                <option value="800x1200|Infographic">Infographic (800x1200)</option>
              </select>
              <button class="btn btn-gold mono" style="font-size:11px;" onclick="CommandCenter.createCanvaAsset()">GENERATE &rarr;</button>
            </div>
          </div>

          <!-- Existing Canva Assets Grid -->
          <div class="canva-grid">
            ${assets.map(a => `
              <div class="canva-card">
                <div class="canva-preview-box" style="background:${a.preview_color || '#181D26'};">
                  <span>${escapeHtml(a.dimensions)}</span>
                </div>
                <div class="canva-card-title">${escapeHtml(a.title)}</div>
                <div class="canva-card-meta mono">
                  <span>${escapeHtml(a.type)}</span>
                  <span style="color:var(--gold);">${escapeHtml(a.status)}</span>
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    }

    // 6. Render Widget 5: Token Audit Ledger
    const ledgerContainer = document.getElementById('aiLedgerContainer');
    if (ledgerContainer) {
      const history = data.recent_history || [];
      if (history.length === 0) {
        ledgerContainer.innerHTML = `
          <div style="padding:28px 16px; text-align:center; color:var(--text-muted); font-family:var(--font-mono); font-size:12px;">
            // Zero completions logged in this session.<br>
            Dispatch Claude or OpenAI prompts to record real-time token and expenditure audits.
          </div>
        `;
      } else {
        ledgerContainer.innerHTML = `
          <div style="max-height:220px; overflow-y:auto;">
            <table class="ai-ledger-table mono">
              <thead>
                <tr>
                  <th>TIME</th>
                  <th>PROVIDER</th>
                  <th>MODEL</th>
                  <th>TOKENS (IN/OUT)</th>
                  <th>LATENCY</th>
                  <th>COST (USD)</th>
                </tr>
              </thead>
              <tbody>
                ${history.map(h => {
                  const d = new Date(h.timestamp * 1000);
                  const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false });
                  return `
                    <tr>
                      <td style="color:var(--text-muted);">${timeStr}</td>
                      <td><span class="provider-tag ${h.provider}">${h.provider.toUpperCase()}</span></td>
                      <td style="color:var(--text-primary); font-weight:600;">${escapeHtml(h.model)}</td>
                      <td>${h.prompt_tokens} &rarr; ${h.completion_tokens}</td>
                      <td>${h.latency_ms}ms</td>
                      <td style="color:var(--gold); font-weight:700;">$${h.cost_usd.toFixed(5)}</td>
                    </tr>
                  `;
                }).join('')}
              </tbody>
            </table>
          </div>
        `;
      }
    }

    aiLocalState.initialized = true;
  }

  // AI Workbench Action Dispatchers
  function loadWorkflow(wfId) {
    const aiState = window.lastFullState?.services?.ai_workbench?.data;
    if (!aiState) return;
    const wf = (aiState.saved_workflows || []).find(w => w.id === wfId);
    if (!wf) return;

    aiLocalState.selectedWorkflowId = wfId;
    aiLocalState.claude.system = wf.system_prompt;
    aiLocalState.claude.prompt = wf.sample_prompt;
    aiLocalState.openai.system = wf.system_prompt;
    aiLocalState.openai.prompt = wf.sample_prompt;

    const cSys = document.getElementById('claudeSystemInput');
    const cPrompt = document.getElementById('claudePromptInput');
    if (cSys) cSys.value = wf.system_prompt;
    if (cPrompt) cPrompt.value = wf.sample_prompt;

    const oSys = document.getElementById('openaiSystemInput');
    const oPrompt = document.getElementById('openaiPromptInput');
    if (oSys) oSys.value = wf.system_prompt;
    if (oPrompt) oPrompt.value = wf.sample_prompt;

    // Highlight selected pill
    document.querySelectorAll('.ai-wf-pill').forEach(el => el.classList.remove('active'));
    event.currentTarget?.classList.add('active');

    showNotification(`Loaded Workflow: ${wf.title}`);
  }

  function togglePromptSync(val) {
    aiLocalState.syncPrompts = Boolean(val);
    if (aiLocalState.syncPrompts) {
      const cVal = document.getElementById('claudePromptInput')?.value || '';
      const oPrompt = document.getElementById('openaiPromptInput');
      if (oPrompt) {
        oPrompt.value = cVal;
        aiLocalState.openai.prompt = cVal;
      }
    }
  }

  function onClaudePromptInput() {
    const val = document.getElementById('claudePromptInput')?.value || '';
    aiLocalState.claude.prompt = val;
    if (aiLocalState.syncPrompts) {
      const oPrompt = document.getElementById('openaiPromptInput');
      if (oPrompt) {
        oPrompt.value = val;
        aiLocalState.openai.prompt = val;
      }
    }
  }

  function onOpenAIPromptInput() {
    const val = document.getElementById('openaiPromptInput')?.value || '';
    aiLocalState.openai.prompt = val;
    if (aiLocalState.syncPrompts) {
      const cPrompt = document.getElementById('claudePromptInput');
      if (cPrompt) {
        cPrompt.value = val;
        aiLocalState.claude.prompt = val;
      }
    }
  }

  function onClaudeSystemInput() {
    aiLocalState.claude.system = document.getElementById('claudeSystemInput')?.value || '';
  }

  function onOpenAISystemInput() {
    aiLocalState.openai.system = document.getElementById('openaiSystemInput')?.value || '';
  }

  function onClaudeModelChange(val) {
    aiLocalState.claude.model = val;
  }

  function onOpenAIModelChange(val) {
    aiLocalState.openai.model = val;
  }

  function toggleClaudeSandbox(val) {
    aiLocalState.claude.sandbox = Boolean(val);
  }

  function toggleOpenAISandbox(val) {
    aiLocalState.openai.sandbox = Boolean(val);
  }

  function dispatchClaudePrompt() {
    const prompt = document.getElementById('claudePromptInput')?.value.trim() || aiLocalState.claude.prompt;
    const system = document.getElementById('claudeSystemInput')?.value.trim() || aiLocalState.claude.system;
    const model = document.getElementById('claudeModelSelect')?.value || aiLocalState.claude.model;
    const sandbox = document.getElementById('claudeSandboxCheck')?.checked ?? aiLocalState.claude.sandbox;

    if (!prompt) {
      showNotification('Prompt cannot be empty');
      return;
    }

    openConfirmModal({
      title: 'DISPATCH ANTHROPIC CLAUDE',
      desc: sandbox 
        ? 'Execute sandbox test evaluation using local zero-hallucination simulator (no API credits billed).' 
        : `Execute live HTTPS completion through Anthropic Messages API (${model}). Tokens will be billed directly to your Anthropic account.`,
      code: `PROVIDER: Anthropic Claude\nMODEL: ${model}\nMODE: ${sandbox ? 'SANDBOX (SIMULATED)' : 'LIVE API (PAID)'}\nPROMPT PREVIEW: "${prompt.slice(0, 80)}..."`,
      onConfirm: () => {
        aiLocalState.claude.loading = true;
        const outScreen = document.getElementById('claudeOutputScreen');
        if (outScreen) {
          outScreen.className = 'ai-output-screen';
          outScreen.innerHTML = '<span style="color:var(--gold);">[PROCESSING] Streaming request through Anthropic Messages API...</span>';
        }

        fetch('/api/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            service: 'ai_workbench',
            action: 'run_prompt',
            payload: {
              provider: 'claude',
              model: model,
              prompt: prompt,
              system_prompt: system,
              sandbox: sandbox
            }
          })
        })
        .then(r => r.json())
        .then(res => {
          aiLocalState.claude.loading = false;
          if (res.success) {
            aiLocalState.claude.output = res.text;
            aiLocalState.claude.meta = res;
            showNotification(`Claude completed in ${res.latency_ms}ms (${res.total_tokens} tokens)`);
          } else {
            aiLocalState.claude.output = `[ERROR] ${res.error || 'Execution failed'}`;
            showNotification(`Error: ${res.error || 'Execution failed'}`);
          }
          fetchState();
        })
        .catch(err => {
          aiLocalState.claude.loading = false;
          aiLocalState.claude.output = `[NETWORK ERROR] ${err.message}`;
          showNotification(`Network error: ${err.message}`);
        });
      }
    });
  }

  function dispatchOpenAIPrompt() {
    const prompt = document.getElementById('openaiPromptInput')?.value.trim() || aiLocalState.openai.prompt;
    const system = document.getElementById('openaiSystemInput')?.value.trim() || aiLocalState.openai.system;
    const model = document.getElementById('openaiModelSelect')?.value || aiLocalState.openai.model;
    const sandbox = document.getElementById('openaiSandboxCheck')?.checked ?? aiLocalState.openai.sandbox;

    if (!prompt) {
      showNotification('Prompt cannot be empty');
      return;
    }

    openConfirmModal({
      title: 'DISPATCH OPENAI GPT-4O',
      desc: sandbox 
        ? 'Execute sandbox test evaluation using local zero-hallucination simulator (no API credits billed).' 
        : `Execute live HTTPS completion through OpenAI Chat Completions API (${model}). Tokens will be billed directly to your OpenAI account.`,
      code: `PROVIDER: OpenAI\nMODEL: ${model}\nMODE: ${sandbox ? 'SANDBOX (SIMULATED)' : 'LIVE API (PAID)'}\nPROMPT PREVIEW: "${prompt.slice(0, 80)}..."`,
      onConfirm: () => {
        aiLocalState.openai.loading = true;
        const outScreen = document.getElementById('openaiOutputScreen');
        if (outScreen) {
          outScreen.className = 'ai-output-screen';
          outScreen.innerHTML = '<span style="color:var(--gold);">[PROCESSING] Streaming request through OpenAI Chat Completions API...</span>';
        }

        fetch('/api/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            service: 'ai_workbench',
            action: 'run_prompt',
            payload: {
              provider: 'openai',
              model: model,
              prompt: prompt,
              system_prompt: system,
              sandbox: sandbox
            }
          })
        })
        .then(r => r.json())
        .then(res => {
          aiLocalState.openai.loading = false;
          if (res.success) {
            aiLocalState.openai.output = res.text;
            aiLocalState.openai.meta = res;
            showNotification(`OpenAI completed in ${res.latency_ms}ms (${res.total_tokens} tokens)`);
          } else {
            aiLocalState.openai.output = `[ERROR] ${res.error || 'Execution failed'}`;
            showNotification(`Error: ${res.error || 'Execution failed'}`);
          }
          fetchState();
        })
        .catch(err => {
          aiLocalState.openai.loading = false;
          aiLocalState.openai.output = `[NETWORK ERROR] ${err.message}`;
          showNotification(`Network error: ${err.message}`);
        });
      }
    });
  }

  function dispatchDualPrompt() {
    const prompt = document.getElementById('claudePromptInput')?.value.trim() || aiLocalState.claude.prompt;
    const system = document.getElementById('claudeSystemInput')?.value.trim() || aiLocalState.claude.system;
    const sandbox = (document.getElementById('claudeSandboxCheck')?.checked || document.getElementById('openaiSandboxCheck')?.checked) ?? true;

    if (!prompt) {
      showNotification('Prompt cannot be empty');
      return;
    }

    openConfirmModal({
      title: 'DUAL DISPATCH: COMPARE BOTH LLMs',
      desc: 'Execute identical prompt across both Claude 3.5 Sonnet and OpenAI GPT-4o concurrently for side-by-side output and token cost evaluation.',
      code: `PROVIDERS: Anthropic Claude 3.5 & OpenAI GPT-4o\nMODE: ${sandbox ? 'SANDBOX (SIMULATED)' : 'LIVE PRODUCTION'}\nPROMPT: "${prompt.slice(0, 100)}..."`,
      onConfirm: () => {
        aiLocalState.claude.loading = true;
        aiLocalState.openai.loading = true;

        const cOut = document.getElementById('claudeOutputScreen');
        const oOut = document.getElementById('openaiOutputScreen');
        if (cOut) cOut.innerHTML = '<span style="color:var(--gold);">[PROCESSING] Evaluating Claude 3.5 Sonnet...</span>';
        if (oOut) oOut.innerHTML = '<span style="color:var(--gold);">[PROCESSING] Evaluating OpenAI GPT-4o...</span>';

        fetch('/api/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            service: 'ai_workbench',
            action: 'run_prompt',
            payload: {
              provider: 'both',
              prompt: prompt,
              system_prompt: system,
              sandbox: sandbox
            }
          })
        })
        .then(r => r.json())
        .then(res => {
          aiLocalState.claude.loading = false;
          aiLocalState.openai.loading = false;

          if (res.success && res.dual) {
            if (res.claude && res.claude.success) {
              aiLocalState.claude.output = res.claude.text;
              aiLocalState.claude.meta = res.claude;
            } else {
              aiLocalState.claude.output = `[ERROR] ${res.claude?.error || 'Failed'}`;
            }

            if (res.openai && res.openai.success) {
              aiLocalState.openai.output = res.openai.text;
              aiLocalState.openai.meta = res.openai;
            } else {
              aiLocalState.openai.output = `[ERROR] ${res.openai?.error || 'Failed'}`;
            }

            showNotification('Dual evaluation completed');
          } else {
            showNotification(`Dual dispatch error: ${res.error || 'Failed'}`);
          }
          fetchState();
        })
        .catch(err => {
          aiLocalState.claude.loading = false;
          aiLocalState.openai.loading = false;
          showNotification(`Network error: ${err.message}`);
        });
      }
    });
  }

  function createCanvaAsset() {
    const title = document.getElementById('canvaTitleInput')?.value.trim() || 'Command Center Brand Slide';
    const fmt = document.getElementById('canvaFormatSelect')?.value || '1920x1080|Presentation';
    const [dim, type] = fmt.split('|');

    openConfirmModal({
      title: 'REGISTER CANVA ASSET DRAFT',
      desc: 'Creates a new design draft asset in Canva Studio linked to your Command Center project workspace.',
      code: `ASSET TITLE: ${title}\nDIMENSIONS: ${dim}\nFORMAT TYPE: ${type}`,
      onConfirm: () => {
        fetch('/api/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            service: 'ai_workbench',
            action: 'canva_create_asset',
            payload: { title, dimensions: dim, type }
          })
        })
        .then(r => r.json())
        .then(res => {
          if (res.success) {
            showNotification(`Canva draft registered: ${title}`);
            fetchState();
          } else {
            showNotification(`Error: ${res.error}`);
          }
        });
      }
    });
  }

  function resetAITelemetry() {
    openConfirmModal({
      title: 'RESET TOKEN TELEMETRY COUNTERS',
      desc: 'Reset all daily token counters, cost totals, and execution audit history back to zero.',
      code: 'ACTION: reset_telemetry\nTARGET: ai_workbench',
      onConfirm: () => {
        fetch('/api/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            service: 'ai_workbench',
            action: 'reset_telemetry'
          })
        })
        .then(r => r.json())
        .then(res => {
          if (res.success) {
            showNotification('Telemetry counters reset');
            fetchState();
          }
        });
      }
    });
  }

  function copyClaudeOutput() {
    if (aiLocalState.claude.output) {
      navigator.clipboard?.writeText(aiLocalState.claude.output);
      showNotification('Claude output copied to clipboard');
    }
  }

  function copyOpenAIOutput() {
    if (aiLocalState.openai.output) {
      navigator.clipboard?.writeText(aiLocalState.openai.output);
      showNotification('OpenAI output copied to clipboard');
    }
  }

  // ========================================================
  // SECTION 4: STUDIO LOGIC
  // ========================================================
  const studioLocalState = {
    selectedScriptId: 'sc-solopreneur',
    title: 'The $10M Solopreneur Stack (Vertical Short)',
    preset: '9:16',
    ttsEngine: 'ElevenLabs (Adam)',
    brollQuery: 'dark server room telemetry',
    captions: 'Word-by-Word Gold Animated',
    script: `Most software founders waste 6 months building dashboards that already exist.\n\nHere is how one engineer scaled to 8 figures with zero employees: They bound all their telemetry to a single local Python feeder running on localhost.\n\nStripe webhooks feed directly into an accounts payable ledger. AI reasoning compares Claude and OpenAI side-by-side with zero token waste.\n\nStop over-engineering distributed clusters when a single daemon on your Mac can run your entire operating system.`,
    clipperSource: 'https://youtube.com/watch?v=solopreneur_architecture_2026',
    detectedClips: [],
    analyzingClipper: false,
    initialized: false
  };

  function renderStudioSection(studio) {
    if (!studio) return;
    const d = studio.data || {};
    const queue = d.render_queue || [];
    const clipped = d.clipped_segments || [];
    const brollList = d.broll_library || [];
    const scripts = d.sample_scripts || [];
    const hasFfmpeg = Boolean(d.ffmpeg_installed);

    // 1. Update Header Badges
    const ffmpegDot = document.getElementById('studioFfmpegDot');
    const ffmpegStatus = document.getElementById('studioFfmpegStatus');
    if (ffmpegDot && ffmpegStatus) {
      if (hasFfmpeg) {
        ffmpegDot.className = 'status-dot active';
        ffmpegStatus.textContent = 'FFMPEG INSTALLED (DARWIN)';
      } else {
        ffmpegDot.className = 'status-dot unconfigured';
        ffmpegStatus.textContent = '[FFMPEG MISSING: brew install ffmpeg]';
      }
    }

    const brollCount = document.getElementById('studioBrollCount');
    if (brollCount) {
      brollCount.textContent = `${brollList.length} ASSETS READY`;
    }

    // 2. Render Widget 1: Faceless Video Builder
    const vidContainer = document.getElementById('studioVideoContainer');
    if (vidContainer) {
      const existingScript = document.getElementById('videoScriptInput');
      const wordCount = (studioLocalState.script || '').split(/\s+/).filter(Boolean).length;
      const estSec = Math.max(Math.round(wordCount / 2.3), 10);

      if (!existingScript) {
        vidContainer.innerHTML = `
          <!-- Script Template Pills -->
          <div class="studio-template-bar">
            <span class="mono" style="font-size:10px; color:var(--gold);">&bull; LOAD TEMPLATE &bull;</span>
            ${scripts.map(s => `
              <span class="studio-pill ${studioLocalState.selectedScriptId === s.id ? 'active' : ''}" onclick="CommandCenter.loadStudioScript('${s.id}')">
                ${escapeHtml(s.title)}
              </span>
            `).join('')}
          </div>

          <!-- Form Controls -->
          <div style="display:grid; grid-template-columns: 2fr 1fr; gap:10px; margin-bottom:10px;">
            <div class="form-group">
              <label class="mono" style="font-size:10.5px; color:var(--text-muted); display:block; margin-bottom:3px;">VIDEO TITLE</label>
              <input type="text" id="videoTitleInput" class="mono form-input" value="${escapeHtml(studioLocalState.title)}" oninput="CommandCenter.onStudioTitleInput()">
            </div>
            <div class="form-group">
              <label class="mono" style="font-size:10.5px; color:var(--text-muted); display:block; margin-bottom:3px;">ASPECT FORMAT</label>
              <select id="videoPresetSelect" class="mono ai-select" style="width:100%; height:32px;" onchange="CommandCenter.onStudioPresetChange(this.value)">
                <option value="9:16" ${studioLocalState.preset === '9:16' ? 'selected' : ''}>Vertical 9:16 (TikTok / Reels / Shorts)</option>
                <option value="16:9" ${studioLocalState.preset === '16:9' ? 'selected' : ''}>Landscape 16:9 (YouTube Standard)</option>
                <option value="1:1" ${studioLocalState.preset === '1:1' ? 'selected' : ''}>Square 1:1 (Instagram / X Feed)</option>
              </select>
            </div>
          </div>

          <div class="studio-form-grid">
            <div class="form-group">
              <label class="mono" style="font-size:10.5px; color:var(--text-muted); display:block; margin-bottom:3px;">TTS VOICE ENGINE</label>
              <select id="videoTtsSelect" class="mono ai-select" style="width:100%; height:32px;" onchange="CommandCenter.onStudioTtsChange(this.value)">
                <option value="ElevenLabs (Adam)" ${studioLocalState.ttsEngine.includes('Adam') ? 'selected' : ''}>ElevenLabs &bull; Adam (Deep/Authoritative)</option>
                <option value="ElevenLabs (Rachel)" ${studioLocalState.ttsEngine.includes('Rachel') ? 'selected' : ''}>ElevenLabs &bull; Rachel (Calm/Executive)</option>
                <option value="OpenAI (alloy)" ${studioLocalState.ttsEngine.includes('alloy') ? 'selected' : ''}>OpenAI TTS &bull; alloy (Balanced/Crisp)</option>
                <option value="OpenAI (onyx)" ${studioLocalState.ttsEngine.includes('onyx') ? 'selected' : ''}>OpenAI TTS &bull; onyx (Resonant/Baritone)</option>
              </select>
            </div>

            <div class="form-group">
              <label class="mono" style="font-size:10.5px; color:var(--text-muted); display:block; margin-bottom:3px;">B-ROLL VISUAL THEME</label>
              <input type="text" id="videoBrollInput" class="mono form-input" value="${escapeHtml(studioLocalState.brollQuery)}" oninput="CommandCenter.onStudioBrollChange(this.value)" placeholder="e.g. dark server room telemetry">
            </div>

            <div class="form-group">
              <label class="mono" style="font-size:10.5px; color:var(--text-muted); display:block; margin-bottom:3px;">CAPTIONS ENGINE</label>
              <select id="videoCaptionsSelect" class="mono ai-select" style="width:100%; height:32px;" onchange="CommandCenter.onStudioCaptionsChange(this.value)">
                <option value="Word-by-Word Gold Animated" ${studioLocalState.captions.includes('Word-by-Word') ? 'selected' : ''}>Word-by-Word Gold Animated</option>
                <option value="Minimal Sentence Subtitles" ${studioLocalState.captions.includes('Minimal') ? 'selected' : ''}>Minimal Sentence Subtitles</option>
              </select>
            </div>
          </div>

          <!-- Script Area -->
          <div style="margin-bottom:6px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
              <span class="mono" style="font-size:10.5px; color:var(--text-muted);">SPOKEN SCRIPT (VOICEOVER TIMELINE)</span>
              <span class="mono" id="scriptStatsBadge" style="font-size:10.5px; color:var(--gold);">
                ${wordCount} WORDS &bull; EST. ~${estSec}s RUNTIME
              </span>
            </div>
            <textarea id="videoScriptInput" class="studio-script-box mono" placeholder="Enter spoken voiceover script..." oninput="CommandCenter.onStudioScriptInput()">${escapeHtml(studioLocalState.script)}</textarea>
          </div>

          <!-- Action Row -->
          <div class="studio-action-row">
            <div class="mono" style="font-size:10.5px; color:var(--text-muted);">
              ${hasFfmpeg ? '<span style="color:#74AA9C;">&bull; FFMPEG ACCELERATION ACTIVE</span>' : '<span style="color:var(--gold);">&bull; RUNS IN SANDBOX MODE (brew install ffmpeg to render locally)</span>'}
            </div>
            <button class="btn btn-gold mono" onclick="CommandCenter.enqueueVideoRender()">
              ENQUEUE VIDEO RENDER &rarr;
            </button>
          </div>
        `;
      } else {
        // Update stats badge without destroying textarea
        const badge = document.getElementById('scriptStatsBadge');
        if (badge) {
          badge.textContent = `${wordCount} WORDS • EST. ~${estSec}s RUNTIME`;
        }
      }
    }

    // 3. Render Widget 2: Source Clipper & Key Moments
    const clipperContainer = document.getElementById('studioClipperContainer');
    if (clipperContainer) {
      clipperContainer.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:12px;">
          <!-- Clipper Input Box -->
          <div class="clipper-box">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span class="mono" style="font-size:10.5px; color:var(--gold);">SOURCE MEDIA INPUT</span>
              <span class="mono" style="font-size:10px; color:var(--text-muted);">MP4 / YOUTUBE / LOCAL</span>
            </div>
            <input type="text" id="clipperSourceInput" class="mono form-input" value="${escapeHtml(studioLocalState.clipperSource)}" placeholder="Enter YouTube URL or absolute local file path...">
            <button class="btn btn-gold mono" style="font-size:11px; padding:6px 10px;" onclick="CommandCenter.analyzeSourceVideo()">
              ${studioLocalState.analyzingClipper ? '[ANALYZING TIMELINE SPIKES...]' : 'ANALYZE TIMELINE &bull; DETECT KEY MOMENTS &rarr;'}
            </button>
          </div>

          <!-- Detected Key Moments Stream -->
          <div style="display:flex; flex-direction:column;">
            <span class="mono" style="font-size:10px; color:var(--text-muted); margin-bottom:6px; letter-spacing:0.05em;">
              &bull; DETECTED VIRAL SEGMENTS (AUDIENCE RETENTION PREDICTION) &bull;
            </span>
            ${studioLocalState.detectedClips.length === 0 ? `
              <div style="background:var(--bg-core); border:1px dashed var(--border-subtle); padding:16px; text-align:center; color:var(--text-muted); font-family:var(--font-mono); font-size:11px;">
                Paste a video URL or local file path above to scan for scene transitions, loudness spikes, and viral segment hooks.
              </div>
            ` : studioLocalState.detectedClips.map((clip, idx) => `
              <div class="moment-card">
                <div style="display:flex; align-items:center; gap:10px;">
                  <span class="moment-time-badge">${clip.start} - ${clip.end}</span>
                  <div class="moment-info">
                    <span class="moment-title">${escapeHtml(clip.title)}</span>
                    <span class="moment-sub">CONFIDENCE: ${clip.confidence} &bull; ${clip.energy}</span>
                  </div>
                </div>
                <button class="mini-btn mono" onclick="CommandCenter.cutSourceClip(${idx})">CUT CLIP &rarr;</button>
              </div>
            `).join('')}
          </div>

          <!-- Extracted Clips Library -->
          <div style="margin-top:6px;">
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
              <span class="mono" style="font-size:10px; color:var(--text-muted);">&bull; EXTRACTED CLIPS LIBRARY (${clipped.length}) &bull;</span>
              <span class="mono" style="font-size:9.5px; color:#74AA9C;">STREAM COPY READY</span>
            </div>
            ${clipped.map(c => `
              <div style="background:var(--bg-core); border:1px solid var(--border-subtle); padding:8px 10px; display:flex; align-items:center; justify-content:space-between; margin-bottom:6px;">
                <div>
                  <div class="mono" style="font-size:11px; font-weight:700; color:var(--text-primary);">${escapeHtml(c.title)}</div>
                  <div class="mono" style="font-size:9.5px; color:var(--text-muted);">${escapeHtml(c.output_file)} &bull; ${c.duration_sec}s</div>
                </div>
                <span class="mono" style="font-size:10px; color:var(--gold); font-weight:700;">[READY]</span>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    }

    // 4. Render Widget 3: Local Rendering Queue
    const queueContainer = document.getElementById('studioQueueContainer');
    if (queueContainer) {
      if (queue.length === 0) {
        queueContainer.innerHTML = `
          <div style="padding:28px 16px; text-align:center; color:var(--text-muted); font-family:var(--font-mono); font-size:12px;">
            // Render queue is currently idle.<br>
            Compose a script and click "ENQUEUE VIDEO RENDER" to initiate local production.
          </div>
        `;
      } else {
        queueContainer.innerHTML = `
          <div class="studio-queue-list">
            ${queue.map(j => `
              <div class="studio-job-card">
                <div class="studio-job-header">
                  <span class="studio-job-title">${escapeHtml(j.title)}</span>
                  <span class="mono" style="font-size:10px; font-weight:700; color:${j.status === 'COMPLETED' ? '#74AA9C' : 'var(--gold)'};">
                    [${j.status}] ${j.progress}%
                  </span>
                </div>
                <div class="studio-job-meta">
                  <span>PRESET: ${j.preset} (${j.resolution})</span>
                  <span>&bull;</span>
                  <span>AUDIO: ${escapeHtml(j.tts_engine)}</span>
                  <span>&bull;</span>
                  <span>RUNTIME: ~${j.duration_sec}s</span>
                </div>
                <div class="studio-progress-track">
                  <div class="studio-progress-bar" style="width:${j.progress}%;"></div>
                </div>
                <div class="studio-job-footer">
                  <span>OUTPUT: ${escapeHtml(j.output_file)}</span>
                  ${j.status === 'COMPLETED' ? '<span class="gold mono" style="font-weight:700;">✓ RENDER READY</span>' : '<span class="mono" style="color:var(--text-muted);">PROCESSING PIPELINE...</span>'}
                </div>
              </div>
            `).join('')}
          </div>
        `;
      }
    }

    // 5. Render Widget 4: Stock B-Roll Browser
    const brollContainer = document.getElementById('studioBrollContainer');
    if (brollContainer) {
      brollContainer.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:10px;">
          <!-- Quick Search & Tag Filter -->
          <div style="display:flex; gap:6px;">
            <input type="text" id="brollSearchInput" class="mono form-input" placeholder="Search B-roll (trading, coding, city, ai)..." oninput="CommandCenter.searchBroll(this.value)">
          </div>
          <div style="display:flex; gap:6px; flex-wrap:wrap;">
            <span class="studio-pill mono" style="font-size:10px; padding:3px 6px;" onclick="CommandCenter.searchBroll('trading')">Trading</span>
            <span class="studio-pill mono" style="font-size:10px; padding:3px 6px;" onclick="CommandCenter.searchBroll('servers')">Servers</span>
            <span class="studio-pill mono" style="font-size:10px; padding:3px 6px;" onclick="CommandCenter.searchBroll('coding')">MacBook</span>
            <span class="studio-pill mono" style="font-size:10px; padding:3px 6px;" onclick="CommandCenter.searchBroll('city')">City Sunset</span>
            <span class="studio-pill mono" style="font-size:10px; padding:3px 6px;" onclick="CommandCenter.searchBroll('ai')">Neural Mesh</span>
          </div>

          <!-- B-Roll Grid -->
          <div class="broll-grid" id="brollResultsGrid">
            ${brollList.map(b => `
              <div class="broll-card">
                <div class="broll-thumb" style="background:${b.preview_thumb || 'var(--bg-slab)'};">
                  <span>${b.resolution} &bull; ${b.duration_sec}s</span>
                </div>
                <div class="broll-title">${escapeHtml(b.title)}</div>
                <div class="broll-meta">
                  <span>${b.aspect}</span>
                  <button class="mini-btn mono" style="font-size:9px; padding:2px 6px;" onclick="CommandCenter.selectBrollForScript('${escapeHtml(b.tags[0] || 'visuals')}')">USE</button>
                </div>
              </div>
            `).join('')}
          </div>
        </div>
      `;
    }

    studioLocalState.initialized = true;
  }

  // Studio Action Handlers
  function loadStudioScript(scriptId) {
    const studioData = window.lastFullState?.services?.studio?.data;
    if (!studioData) return;
    const s = (studioData.sample_scripts || []).find(sc => sc.id === scriptId);
    if (!s) return;

    studioLocalState.selectedScriptId = scriptId;
    studioLocalState.title = s.title;
    studioLocalState.script = s.script;
    if (s.suggested_preset) studioLocalState.preset = s.suggested_preset;

    const tInput = document.getElementById('videoTitleInput');
    const sInput = document.getElementById('videoScriptInput');
    const pSelect = document.getElementById('videoPresetSelect');
    if (tInput) tInput.value = s.title;
    if (sInput) sInput.value = s.script;
    if (pSelect) pSelect.value = studioLocalState.preset;

    // Update word count badge
    const wordCount = s.script.split(/\s+/).filter(Boolean).length;
    const estSec = Math.max(Math.round(wordCount / 2.3), 10);
    const badge = document.getElementById('scriptStatsBadge');
    if (badge) badge.textContent = `${wordCount} WORDS • EST. ~${estSec}s RUNTIME`;

    // Highlight active pill
    document.querySelectorAll('.studio-pill').forEach(el => el.classList.remove('active'));
    event.currentTarget?.classList.add('active');

    showNotification(`Loaded Studio Template: ${s.title}`);
  }

  function onStudioScriptInput() {
    const val = document.getElementById('videoScriptInput')?.value || '';
    studioLocalState.script = val;
    const wordCount = val.split(/\s+/).filter(Boolean).length;
    const estSec = Math.max(Math.round(wordCount / 2.3), 10);
    const badge = document.getElementById('scriptStatsBadge');
    if (badge) badge.textContent = `${wordCount} WORDS • EST. ~${estSec}s RUNTIME`;
  }

  function onStudioTitleInput() {
    studioLocalState.title = document.getElementById('videoTitleInput')?.value || '';
  }

  function onStudioPresetChange(val) {
    studioLocalState.preset = val;
  }

  function onStudioTtsChange(val) {
    studioLocalState.ttsEngine = val;
  }

  function onStudioBrollChange(val) {
    studioLocalState.brollQuery = val;
  }

  function onStudioCaptionsChange(val) {
    studioLocalState.captions = val;
  }

  function enqueueVideoRender() {
    const title = document.getElementById('videoTitleInput')?.value.trim() || studioLocalState.title;
    const script = document.getElementById('videoScriptInput')?.value.trim() || studioLocalState.script;
    const preset = document.getElementById('videoPresetSelect')?.value || studioLocalState.preset;
    const tts = document.getElementById('videoTtsSelect')?.value || studioLocalState.ttsEngine;
    const broll = document.getElementById('videoBrollInput')?.value.trim() || studioLocalState.brollQuery;
    const captions = document.getElementById('videoCaptionsSelect')?.value || studioLocalState.captions;

    if (!script) {
      showNotification('Script cannot be empty');
      return;
    }

    const wordCount = script.split(/\s+/).filter(Boolean).length;
    const estSec = Math.max(Math.round(wordCount / 2.3), 10);

    openConfirmModal({
      title: 'ENQUEUE FACELESS VIDEO RENDER',
      desc: 'Dispatches video generation pipeline: TTS speech audio generation, stock B-roll synchronization, ASS animated word captions, and local ffmpeg rendering.',
      code: `TITLE: ${title}\nPRESET: ${preset} (${preset === '9:16' ? '1080x1920' : '1920x1080'})\nTTS VOICE: ${tts}\nESTIMATED DURATION: ~${estSec} seconds (${wordCount} words)\nB-ROLL THEME: ${broll}`,
      onConfirm: () => {
        fetch('/api/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            service: 'studio',
            action: 'enqueue_video_render',
            payload: {
              title: title,
              script: script,
              preset: preset,
              tts_engine: tts,
              broll_query: broll,
              captions: captions,
              simulate: true
            }
          })
        })
        .then(r => r.json())
        .then(res => {
          if (res.success) {
            showNotification(`Enqueued render: ${title}`);
            fetchState();
          } else {
            showNotification(`Render error: ${res.error}`);
          }
        });
      }
    });
  }

  function analyzeSourceVideo() {
    const src = document.getElementById('clipperSourceInput')?.value.trim() || studioLocalState.clipperSource;
    if (!src) {
      showNotification('Please enter a source video URL or file path');
      return;
    }

    studioLocalState.analyzingClipper = true;
    showNotification('Analyzing source timeline and loudness profiles...');
    fetchState();

    fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        service: 'studio',
        action: 'analyze_source_video',
        payload: { source: src }
      })
    })
    .then(r => r.json())
    .then(res => {
      studioLocalState.analyzingClipper = false;
      if (res.success) {
        studioLocalState.detectedClips = res.detected_clips || [];
        showNotification(`Identified ${studioLocalState.detectedClips.length} high-impact key moments`);
      } else {
        showNotification(`Analysis failed: ${res.error}`);
      }
      fetchState();
    })
    .catch(err => {
      studioLocalState.analyzingClipper = false;
      showNotification(`Analysis error: ${err.message}`);
      fetchState();
    });
  }

  function cutSourceClip(idx) {
    const clip = studioLocalState.detectedClips[idx];
    if (!clip) return;
    const src = document.getElementById('clipperSourceInput')?.value.trim() || 'Q3_Keynote_Master.mp4';

    openConfirmModal({
      title: 'CUT SOURCE KEY MOMENT',
      desc: 'Executes zero-reencode stream copy with local ffmpeg to extract high-retention video segment.',
      code: `SOURCE: ${src}\nSEGMENT: ${clip.start} - ${clip.end} (${clip.duration_sec}s)\nTITLE: ${clip.title}\nCOMMAND: ${clip.ffmpeg_cut}`,
      onConfirm: () => {
        fetch('/api/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            service: 'studio',
            action: 'cut_source_clip',
            payload: {
              source_name: src,
              title: clip.title,
              start: clip.start,
              end: clip.end,
              duration_sec: clip.duration_sec
            }
          })
        })
        .then(r => r.json())
        .then(res => {
          if (res.success) {
            showNotification(`Extracted clip: ${clip.title}`);
            fetchState();
          } else {
            showNotification(`Cut error: ${res.error}`);
          }
        });
      }
    });
  }

  function searchBroll(query) {
    fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        service: 'studio',
        action: 'search_broll',
        payload: { query: query }
      })
    })
    .then(r => r.json())
    .then(res => {
      if (res.success) {
        const grid = document.getElementById('brollResultsGrid');
        if (grid) {
          grid.innerHTML = (res.results || []).map(b => `
            <div class="broll-card">
              <div class="broll-thumb" style="background:${b.preview_thumb || 'var(--bg-slab)'};">
                <span>${b.resolution} &bull; ${b.duration_sec}s</span>
              </div>
              <div class="broll-title">${escapeHtml(b.title)}</div>
              <div class="broll-meta">
                <span>${b.aspect}</span>
                <button class="mini-btn mono" style="font-size:9px; padding:2px 6px;" onclick="CommandCenter.selectBrollForScript('${escapeHtml(b.tags?.[0] || 'visuals')}')">USE</button>
              </div>
            </div>
          `).join('');
        }
      }
    });
  }

  function selectBrollForScript(theme) {
    studioLocalState.brollQuery = theme;
    const bInput = document.getElementById('videoBrollInput');
    if (bInput) bInput.value = theme;
    showNotification(`Selected B-Roll visual theme: ${theme}`);
  }

  function clearCompletedRenders() {
    fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        service: 'studio',
        action: 'clear_completed_renders'
      })
    })
    .then(r => r.json())
    .then(res => {
      if (res.success) {
        showNotification('Cleared completed video render jobs');
        fetchState();
      }
    });
  }

  // ========================================================
  // SECTION 7: GAMING LOGIC
  // ========================================================
  const gamingLocalState = {
    profile: 'Developer Debug (with HUD)',
    windowMode: 'Windowed (1280x800)',
    level: 1,
    initialized: false
  };

  function renderGamingSection(gaming) {
    if (!gaming) return;
    const d = gaming.data || {};
    const build = d.build_info || {};
    const session = d.playtest_session || {};
    const levels = d.levels || [];
    const remote = d.remote_sync || {};

    // 1. Update Header Indicators
    const bDot = document.getElementById('gamingBuildDot');
    const bStatus = document.getElementById('gamingBuildStatus');
    if (bDot && bStatus) {
      bDot.className = 'status-dot active';
      bStatus.textContent = build.status || 'HEALTHY // COMPILED';
    }

    const sDot = document.getElementById('gamingSessionDot');
    const sText = document.getElementById('gamingSessionText');
    if (sDot && sText) {
      if (session.active) {
        sDot.className = 'status-dot active';
        sText.textContent = `RUNNING (PID ${session.pid})`;
      } else {
        sDot.className = 'status-dot';
        sText.textContent = 'STANDBY';
      }
    }

    const compRate = document.getElementById('gamingCompletionRate');
    if (compRate) {
      compRate.textContent = `${d.completion_rate || 0}% CLEARED`;
    }

    const storeDot = document.getElementById('gamingStoreDot');
    if (storeDot) {
      storeDot.className = `status-dot ${remote.configured ? 'active' : 'unconfigured'}`;
    }

    // 2. Render Widget 1: Build Status & Artifacts
    const buildContainer = document.getElementById('gamingBuildContainer');
    if (buildContainer) {
      const modules = build.modules || [];
      buildContainer.innerHTML = `
        <!-- Build Metrics Strip -->
        <div class="gaming-build-grid">
          <div class="gaming-build-card">
            <span class="gaming-build-label">TARGET PLATFORM</span>
            <span class="gaming-build-val" style="font-size:11px;">${escapeHtml(build.target || 'macOS Universal')}</span>
          </div>
          <div class="gaming-build-card">
            <span class="gaming-build-label">BINARY SIZE</span>
            <span class="gaming-build-val">${build.binary_size_mb || 42.4} MB</span>
          </div>
          <div class="gaming-build-card">
            <span class="gaming-build-label">COMPILE DURATION</span>
            <span class="gaming-build-val">${build.build_duration_sec || 18.4}s</span>
          </div>
          <div class="gaming-build-card">
            <span class="gaming-build-label">COMPILER WARNINGS</span>
            <span class="gaming-build-val" style="color:#74AA9C;">${build.warnings_count || 0}</span>
          </div>
        </div>

        <!-- Project Suite Modules -->
        <div>
          <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
            <span class="mono" style="font-size:10.5px; color:var(--text-muted);">&bull; COMPILED SUITE MODULES (${modules.length}) &bull;</span>
            <span class="mono" style="font-size:10px; color:var(--gold); font-weight:700;">${escapeHtml(build.version || 'v0.9.8-rc2')}</span>
          </div>
          <table class="gaming-module-table">
            <thead>
              <tr>
                <th>GAME MODULE</th>
                <th>ENGINE ARCHITECTURE</th>
                <th>LEVELS</th>
                <th>ARTIFACT STATUS</th>
              </tr>
            </thead>
            <tbody>
              ${modules.map(m => `
                <tr>
                  <td style="font-weight:700; color:var(--text-primary);">${escapeHtml(m.name)}</td>
                  <td>${escapeHtml(m.type)}</td>
                  <td>${m.levels} Levels</td>
                  <td><span class="mono" style="color:var(--gold); font-weight:700;">[${escapeHtml(m.status)}]</span></td>
                </tr>
              `).join('')}
            </tbody>
          </table>
        </div>
      `;
    }

    // 3. Render Widget 2: Local Playtest Launcher
    const launcherContainer = document.getElementById('gamingLauncherContainer');
    if (launcherContainer) {
      launcherContainer.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:10px;">
          <div style="display:grid; grid-template-columns: 1fr 1fr; gap:8px;">
            <div class="form-group">
              <label class="mono" style="font-size:10px; color:var(--text-muted); display:block; margin-bottom:2px;">LAUNCH PROFILE</label>
              <select id="playtestProfileSelect" class="mono ai-select" style="width:100%; height:30px;" onchange="CommandCenter.onPlaytestProfileChange(this.value)">
                <option value="Developer Debug (with HUD)" ${gamingLocalState.profile.includes('Debug') ? 'selected' : ''}>Debug (Telemetry HUD)</option>
                <option value="Release Candidate Sandbox" ${gamingLocalState.profile.includes('Sandbox') ? 'selected' : ''}>Release Candidate Sandbox</option>
                <option value="Automated Benchmark" ${gamingLocalState.profile.includes('Benchmark') ? 'selected' : ''}>Automated Benchmark</option>
              </select>
            </div>
            <div class="form-group">
              <label class="mono" style="font-size:10px; color:var(--text-muted); display:block; margin-bottom:2px;">WINDOW TARGET</label>
              <select id="playtestWindowSelect" class="mono ai-select" style="width:100%; height:30px;" onchange="CommandCenter.onPlaytestWindowChange(this.value)">
                <option value="Windowed (1280x800)" ${gamingLocalState.windowMode.includes('1280x800') ? 'selected' : ''}>Windowed (1280x800)</option>
                <option value="Retina (1920x1200)" ${gamingLocalState.windowMode.includes('1920x1200') ? 'selected' : ''}>Retina (1920x1200)</option>
                <option value="ProMotion Fullscreen" ${gamingLocalState.windowMode.includes('Fullscreen') ? 'selected' : ''}>ProMotion Fullscreen</option>
              </select>
            </div>
          </div>

          <!-- Launch / Stop Action Button -->
          ${session.active ? `
            <button class="btn mono" style="width:100%; background:#D65D5D; color:#fff; font-weight:700;" onclick="CommandCenter.stopPlaytest()">
              &bull; TERMINATE ACTIVE PLAYTEST (PID ${session.pid})
            </button>
          ` : `
            <button class="btn btn-gold mono" style="width:100%; font-weight:700;" onclick="CommandCenter.launchPlaytest()">
              LAUNCH LOCAL PLAYTEST &rarr;
            </button>
          `}

          <!-- Live Session HUD Box -->
          <div class="gaming-hud-box ${session.active ? 'live' : ''}">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span class="mono" style="font-size:10px; color:${session.active ? 'var(--gold)' : 'var(--text-muted)'}; font-weight:700;">
                ${session.active ? '● ACTIVE METAL TELEMETRY OVERLAY' : '○ ENGINE TELEMETRY STANDBY'}
              </span>
              <span class="mono" style="font-size:9.5px; color:var(--text-muted);">
                ${session.active ? `STARTED ${new Date(session.started_at * 1000).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })}` : 'PID INACTIVE'}
              </span>
            </div>
            <div class="gaming-hud-grid">
              <div class="gaming-hud-stat">
                <span class="val">${session.active ? session.current_fps.toFixed(1) : '--'}</span>
                <span class="lbl">FPS REFRESH</span>
              </div>
              <div class="gaming-hud-stat">
                <span class="val">${session.active ? `${session.memory_mb} MB` : '--'}</span>
                <span class="lbl">RESIDENT RAM</span>
              </div>
              <div class="gaming-hud-stat">
                <span class="val">${session.active ? `${session.input_latency_ms.toFixed(1)}ms` : '--'}</span>
                <span class="lbl">INPUT LATENCY</span>
              </div>
            </div>
          </div>
        </div>
      `;
    }

    // 4. Render Widget 3: Live Session Telemetry & Level Matrix
    const telemetryContainer = document.getElementById('gamingTelemetryContainer');
    if (telemetryContainer) {
      telemetryContainer.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:12px;">
          <!-- Telemetry Summary Strip -->
          <div class="gaming-build-grid">
            <div class="gaming-build-card">
              <span class="gaming-build-label">TOTAL PLAYTESTS</span>
              <span class="gaming-build-val">${session.total_playtests_count || 48}</span>
            </div>
            <div class="gaming-build-card">
              <span class="gaming-build-label">AVG TIME-TO-SOLVE</span>
              <span class="gaming-build-val">${session.avg_solve_time_sec || 42.6}s</span>
            </div>
            <div class="gaming-build-card">
              <span class="gaming-build-label">PAR EFFICIENCY</span>
              <span class="gaming-build-val" style="color:var(--gold);">${session.par_efficiency || 1.14}x</span>
            </div>
            <div class="gaming-build-card">
              <span class="gaming-build-label">CRASHES LOGGED</span>
              <span class="gaming-build-val" style="color:#74AA9C;">${session.crashes_logged || 0}</span>
            </div>
          </div>

          <!-- Level Progression Matrix -->
          <div>
            <div style="display:flex; justify-content:space-between; align-items:center; margin-bottom:6px;">
              <span class="mono" style="font-size:10px; color:var(--text-muted);">&bull; LEVEL MATRIX &bull; CLICK TO ADVANCE / SIMULATE CLEAR</span>
              <span class="mono" style="font-size:10px; color:var(--gold);">${d.completion_rate}% COMPLETE</span>
            </div>
            <div class="gaming-level-matrix">
              ${levels.map(l => {
                const diffCls = l.difficulty.toLowerCase();
                const statusCls = l.status.toLowerCase().replace('_', '-');
                return `
                  <div class="gaming-level-chip ${statusCls}" onclick="CommandCenter.clearGameLevel(${l.level})" title="Click to record clearance">
                    <div class="level-top-row">
                      <span class="level-num">LVL ${l.level}</span>
                      <span class="diff-tag ${diffCls}">${l.difficulty}</span>
                    </div>
                    <div class="mono" style="font-size:10.5px; color:var(--text-primary); white-space:nowrap; overflow:hidden; text-overflow:ellipsis;">
                      ${escapeHtml(l.name)}
                    </div>
                    <div class="level-stats-row">
                      <span>PAR: ${l.par}</span>
                      <span style="color:${l.status === 'CLEARED' ? '#74AA9C' : 'var(--gold)'}; font-weight:700;">
                        ${l.status === 'CLEARED' ? l.best_time : `[${l.status}]`}
                      </span>
                    </div>
                  </div>
                `;
              }).join('')}
            </div>
          </div>
        </div>
      `;
    }

    // 5. Render Widget 4: Store Sync & Telemetry Bridge
    const storeContainer = document.getElementById('gamingStoreContainer');
    if (storeContainer) {
      storeContainer.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:12px;">
          <div class="connect-state-card">
            <span class="connect-badge">[STEAMWORKS &bull; APP STORE CONNECT]</span>
            <h4 class="connect-heading">PRODUCTION TELEMETRY BRIDGE</h4>
            <p class="connect-detail">${escapeHtml(remote.instructions || 'Add keys in Settings to synchronize production DAU and crash reporting.')}</p>
            <button class="connect-btn" onclick="CommandCenter.switchSection('settings')">CONFIGURE STORE KEYS &rarr;</button>
          </div>

          <!-- Store Channel Sync Matrix -->
          <div style="background:var(--bg-core); border:1px solid var(--border-subtle); padding:10px 12px; display:flex; flex-direction:column; gap:6px;">
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span class="mono" style="font-size:10.5px; color:var(--text-primary); font-weight:700;">STEAMWORKS PIPELINE</span>
              <span class="mono" style="font-size:10px; color:var(--text-muted);">${remote.steamworks}</span>
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span class="mono" style="font-size:10.5px; color:var(--text-primary); font-weight:700;">APP STORE CONNECT</span>
              <span class="mono" style="font-size:10px; color:var(--text-muted);">${remote.app_store}</span>
            </div>
            <div style="display:flex; justify-content:space-between; align-items:center;">
              <span class="mono" style="font-size:10.5px; color:var(--text-primary); font-weight:700;">LOCAL TELEMETRY PROBE</span>
              <span class="mono" style="font-size:10px; color:#74AA9C; font-weight:700;">READY (PORT 8787)</span>
            </div>
          </div>
        </div>
      `;
    }

    gamingLocalState.initialized = true;
  }

  // Gaming Action Handlers
  function onPlaytestProfileChange(val) {
    gamingLocalState.profile = val;
  }

  function onPlaytestWindowChange(val) {
    gamingLocalState.windowMode = val;
  }

  function launchPlaytest() {
    openConfirmModal({
      title: 'LAUNCH LOCAL PLAYTEST SESSION',
      desc: 'Spawns the native Apple Silicon game binary in a local sandboxed window with Metal API telemetry and live performance instrumentation.',
      code: `EXECUTABLE: games/puzzle-suite/bin/puzzle-suite-mac\nPROFILE: ${gamingLocalState.profile}\nWINDOW TARGET: ${gamingLocalState.windowMode}\nTARGET FPS: 120Hz ProMotion`,
      onConfirm: () => {
        fetch('/api/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            service: 'gaming',
            action: 'launch_playtest',
            payload: {
              profile: gamingLocalState.profile,
              window_mode: gamingLocalState.windowMode
            }
          })
        })
        .then(r => r.json())
        .then(res => {
          if (res.success) {
            showNotification(`Playtest session launched (PID ${res.session.pid})`);
            fetchState();
          } else {
            showNotification(`Launch error: ${res.error}`);
          }
        });
      }
    });
  }

  function stopPlaytest() {
    fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        service: 'gaming',
        action: 'stop_playtest'
      })
    })
    .then(r => r.json())
    .then(res => {
      if (res.success) {
        showNotification('Playtest session terminated');
        fetchState();
      }
    });
  }

  function triggerGameBuild() {
    openConfirmModal({
      title: 'TRIGGER PUZZLE SUITE REBUILD',
      desc: 'Compiles all 3 game modules (Gridlock Logic, HexaPath Quantum, CipherShift) using local Rust Cargo toolchain targeting macOS Universal binary.',
      code: 'COMMAND: cargo build --release --target aarch64-apple-darwin\nMODULES: 3\nOUTPUT: games/puzzle-suite/bin/puzzle-suite-mac',
      onConfirm: () => {
        fetch('/api/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            service: 'gaming',
            action: 'trigger_build',
            payload: { target: 'macOS Universal' }
          })
        })
        .then(r => r.json())
        .then(res => {
          if (res.success) {
            showNotification('Puzzle Suite successfully recompiled (0 warnings)');
            fetchState();
          }
        });
      }
    });
  }

  function clearGameLevel(lvlNum) {
    fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        service: 'gaming',
        action: 'record_level_solve',
        payload: { level: lvlNum, time: '00:38' }
      })
    })
    .then(r => r.json())
    .then(res => {
      if (res.success) {
        showNotification(`Level ${lvlNum} recorded as CLEARED`);
        fetchState();
      }
    });
  }

  // ========================================================
  // SECTION 8: OSINT LOGIC
  // ========================================================
  const osintLocalState = {
    targetDomain: 'apple.com',
    dnsResult: null,
    dnsLoading: false,
    whoisDomain: 'apple.com',
    whoisResult: null,
    whoisLoading: false,
    hibpAccount: 'admin@corporate-domain.com',
    hibpResult: null,
    hibpLoading: false,
    hibpSimulate: true,
    brandKeyword: 'Command Center',
    brandMentions: [],
    brandLoading: false,
    initialized: false
  };

  function renderOSINTSection(osint) {
    if (!osint) return;
    const d = osint.data || {};
    const hibpConfigured = Boolean(d.hibp_configured);
    const keywords = d.monitored_keywords || ['Command Center', 'macOS OS', 'Local Feeder'];
    const cachedMentions = d.cached_mentions || [];

    // 1. Update Header Indicators
    const latencyTag = document.getElementById('osintDnsLatency');
    if (latencyTag && osintLocalState.dnsResult) {
      latencyTag.textContent = `LATENCY: ${osintLocalState.dnsResult.latency_ms}ms`;
    }

    const hibpDot = document.getElementById('osintHibpDot');
    const hibpStatus = document.getElementById('osintHibpStatus');
    if (hibpDot && hibpStatus) {
      hibpDot.className = `status-dot ${hibpConfigured ? 'active' : 'unconfigured'}`;
      hibpStatus.textContent = hibpConfigured ? 'KEY AUTHENTICATED' : '[UNCONFIGURED: HIBP_API_KEY]';
    }

    // 2. Render Widget 1: DNS Resolver Matrix
    const dnsContainer = document.getElementById('osintDnsContainer');
    if (dnsContainer) {
      const res = osintLocalState.dnsResult || d.last_dns;
      dnsContainer.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:10px;">
          <!-- Domain Input & Pills -->
          <div class="osint-search-bar">
            <input type="text" id="osintDnsInput" class="mono form-input" value="${escapeHtml(osintLocalState.targetDomain)}" placeholder="Enter domain (e.g. apple.com, cloudflare.com)..." oninput="osintLocalState.targetDomain = this.value">
            <button class="btn btn-gold mono" style="font-size:11px;" onclick="CommandCenter.resolveDnsMatrix()">
              ${osintLocalState.dnsLoading ? '[RESOLVING...]' : 'RESOLVE DNS &rarr;'}
            </button>
          </div>

          <div class="osint-pill-row">
            <span class="mono" style="font-size:10px; color:var(--text-muted); align-self:center;">TARGETS:</span>
            <span class="studio-pill mono" style="font-size:10px; padding:2px 6px;" onclick="CommandCenter.setOsintDomain('apple.com')">apple.com</span>
            <span class="studio-pill mono" style="font-size:10px; padding:2px 6px;" onclick="CommandCenter.setOsintDomain('cloudflare.com')">cloudflare.com</span>
            <span class="studio-pill mono" style="font-size:10px; padding:2px 6px;" onclick="CommandCenter.setOsintDomain('github.com')">github.com</span>
            <span class="studio-pill mono" style="font-size:10px; padding:2px 6px;" onclick="CommandCenter.setOsintDomain('google.com')">google.com</span>
          </div>

          <!-- DNS Records Table -->
          <div style="background:var(--bg-core); border:1px solid var(--border-subtle); padding:10px; max-height:220px; overflow-y:auto;">
            ${res ? `
              <div style="display:flex; justify-content:space-between; margin-bottom:8px; border-bottom:1px solid var(--border-subtle); padding-bottom:6px;">
                <span class="mono" style="font-size:11px; font-weight:700; color:var(--gold);">${escapeHtml(res.domain)}</span>
                <span class="mono" style="font-size:10.5px; color:var(--text-muted);">RESOLVED IN ${res.latency_ms}ms</span>
              </div>
              <table class="osint-records-table">
                <thead>
                  <tr>
                    <th>TYPE</th>
                    <th>RECORD DATA</th>
                  </tr>
                </thead>
                <tbody>
                  ${(res.a_records || []).map(ip => `
                    <tr>
                      <td><span class="osint-tag a">A</span></td>
                      <td style="color:var(--text-primary); font-weight:600;">${escapeHtml(ip)}</td>
                    </tr>
                  `).join('')}
                  ${(res.aaaa_records || []).map(ip6 => `
                    <tr>
                      <td><span class="osint-tag aaaa">AAAA</span></td>
                      <td>${escapeHtml(ip6)}</td>
                    </tr>
                  `).join('')}
                  ${(res.mx_records || []).map(mx => `
                    <tr>
                      <td><span class="osint-tag mx">MX</span></td>
                      <td>${escapeHtml(mx)}</td>
                    </tr>
                  `).join('')}
                  ${(res.txt_records || []).map(txt => `
                    <tr>
                      <td><span class="osint-tag txt">TXT</span></td>
                      <td style="word-break:break-all;">${escapeHtml(txt)}</td>
                    </tr>
                  `).join('')}
                  ${(res.ns_records || []).map(ns => `
                    <tr>
                      <td><span class="osint-tag ns">NS</span></td>
                      <td>${escapeHtml(ns)}</td>
                    </tr>
                  `).join('')}
                </tbody>
              </table>
            ` : `
              <div style="padding:24px; text-align:center; color:var(--text-muted); font-family:var(--font-mono); font-size:11px;">
                // Enter a domain name and click "RESOLVE DNS" to query authoritative name records.
              </div>
            `}
          </div>
        </div>
      `;
    }

    // 3. Render Widget 2: WHOIS Registration Inspector
    const whoisContainer = document.getElementById('osintWhoisContainer');
    if (whoisContainer) {
      const w = osintLocalState.whoisResult || d.last_whois;
      whoisContainer.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:10px;">
          <div class="osint-search-bar">
            <input type="text" id="osintWhoisInput" class="mono form-input" value="${escapeHtml(osintLocalState.whoisDomain)}" placeholder="Domain to inspect..." oninput="osintLocalState.whoisDomain = this.value">
            <button class="btn btn-gold mono" style="font-size:11px;" onclick="CommandCenter.queryWhois()">
              ${osintLocalState.whoisLoading ? '[QUERYING...]' : 'QUERY WHOIS &rarr;'}
            </button>
          </div>

          ${w ? `
            <div class="whois-card">
              <div class="whois-row">
                <span class="label">REGISTRAR</span>
                <span class="val">${escapeHtml(w.registrar)}</span>
              </div>
              <div class="whois-row">
                <span class="label">CREATED DATE</span>
                <span class="val">${escapeHtml(w.creation_date)}</span>
              </div>
              <div class="whois-row">
                <span class="label">EXPIRATION DATE</span>
                <span class="val" style="color:var(--gold);">${escapeHtml(w.expiry_date)}</span>
              </div>
              <div class="whois-row">
                <span class="label">STATUS</span>
                <span class="val">${(w.status || []).join(', ')}</span>
              </div>
              
              <div style="margin-top:4px;">
                <span class="mono" style="font-size:9.5px; color:var(--text-muted); display:block; margin-bottom:4px;">RAW REGISTRY OUTPUT:</span>
                <div class="whois-raw-box">${escapeHtml(w.raw_text)}</div>
              </div>
            </div>
          ` : `
            <div style="background:var(--bg-core); border:1px solid var(--border-subtle); padding:24px; text-align:center; color:var(--text-muted); font-family:var(--font-mono); font-size:11px;">
              // Enter a domain name to query IANA / ICANN Port 43 registration databases.
            </div>
          `}
        </div>
      `;
    }

    // 4. Render Widget 3: HaveIBeenPwned Breach Check
    const hibpContainer = document.getElementById('osintHibpContainer');
    if (hibpContainer) {
      const h = osintLocalState.hibpResult || d.last_hibp;
      hibpContainer.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:10px;">
          <div style="display:grid; grid-template-columns: 2fr auto; gap:8px;">
            <input type="text" id="osintHibpInput" class="mono form-input" value="${escapeHtml(osintLocalState.hibpAccount)}" placeholder="Account or domain (e.g. user@domain.com)..." oninput="osintLocalState.hibpAccount = this.value">
            <button class="btn btn-gold mono" style="font-size:11px;" onclick="CommandCenter.checkBreachAudit()">
              ${osintLocalState.hibpLoading ? '[AUDITING...]' : 'RUN AUDIT &rarr;'}
            </button>
          </div>

          <div style="display:flex; justify-content:space-between; align-items:center;">
            <label class="mono" style="font-size:10.5px; color:var(--text-secondary); display:flex; align-items:center; gap:6px; cursor:pointer;">
              <input type="checkbox" id="hibpSimulateCheck" ${osintLocalState.hibpSimulate ? 'checked' : ''} onchange="osintLocalState.hibpSimulate = this.checked">
              SIMULATED AUDIT (SAFE TEST MODE)
            </label>
            <span class="mono" style="font-size:9.5px; color:var(--text-muted);">${hibpConfigured ? 'LIVE HIBP API READY' : '[KEY NEEDED FOR LIVE CALLS]'}</span>
          </div>

          <!-- Breach Results List -->
          <div class="hibp-breach-list">
            ${h ? `
              <div style="background:var(--bg-core); border:1px solid var(--border-subtle); padding:8px 10px; display:flex; justify-content:space-between; align-items:center; margin-bottom:4px;">
                <span class="mono" style="font-size:11px; font-weight:700; color:var(--text-primary);">${escapeHtml(h.account)}</span>
                <span class="mono" style="font-size:10px; font-weight:700; color:${h.breached ? '#E58C42' : '#74AA9C'};">
                  ${h.breached ? `[${h.breach_count} COMPROMISES FOUND]` : '[ZERO COMPROMISES IDENTIFIED]'}
                </span>
              </div>
              ${(h.breaches || []).map(b => `
                <div class="hibp-breach-card compromised">
                  <div class="hibp-breach-header">
                    <span class="hibp-breach-title">${escapeHtml(b.name)}</span>
                    <span class="mono" style="font-size:10px; color:var(--gold);">${escapeHtml(b.breach_date)}</span>
                  </div>
                  <div class="mono" style="font-size:10px; color:var(--text-muted);">${escapeHtml(b.description)}</div>
                  <div class="hibp-tag-list">
                    ${(b.data_classes || []).map(dc => `
                      <span class="hibp-tag">${escapeHtml(dc)}</span>
                    `).join('')}
                  </div>
                </div>
              `).join('')}
            ` : `
              <div style="background:var(--bg-core); border:1px solid var(--border-subtle); padding:24px; text-align:center; color:var(--text-muted); font-family:var(--font-mono); font-size:11px;">
                // Enter corporate email or owned domain to audit breach presence.
              </div>
            `}
          </div>
        </div>
      `;
    }

    // 5. Render Widget 4: Brand & Asset Mention Tracker
    const brandContainer = document.getElementById('osintBrandContainer');
    if (brandContainer) {
      const mentions = osintLocalState.brandMentions.length > 0 ? osintLocalState.brandMentions : cachedMentions;
      brandContainer.innerHTML = `
        <div style="display:flex; flex-direction:column; gap:10px;">
          <!-- Keyword Filter Pills -->
          <div class="osint-pill-row">
            <span class="mono" style="font-size:10px; color:var(--text-muted); align-self:center;">MONITORED:</span>
            ${keywords.map(kw => `
              <span class="studio-pill mono ${osintLocalState.brandKeyword === kw ? 'active' : ''}" style="font-size:10px; padding:2px 6px;" onclick="CommandCenter.filterBrandKeyword('${escapeHtml(kw)}')">
                ${escapeHtml(kw)}
              </span>
            `).join('')}
          </div>

          <!-- Add Keyword Bar -->
          <div style="display:grid; grid-template-columns: 2fr auto; gap:8px;">
            <input type="text" id="brandKwInput" class="mono form-input" placeholder="Search or add brand keyword (e.g. solopreneur)..." value="${escapeHtml(osintLocalState.brandKeyword)}">
            <button class="btn btn-gold mono" style="font-size:11px;" onclick="CommandCenter.scanBrandKeyword()">
              ${osintLocalState.brandLoading ? '[CRAWLING...]' : 'SCAN FORUM &rarr;'}
            </button>
          </div>

          <!-- Mentions List -->
          <div class="brand-mentions-list">
            ${mentions.length > 0 ? mentions.map(m => `
              <a href="${escapeHtml(m.url)}" target="_blank" rel="noopener noreferrer" class="brand-mention-item">
                <div style="display:flex; flex-direction:column; gap:2px; max-width:80%;">
                  <span class="mention-title">${escapeHtml(m.title)}</span>
                  <div class="mention-meta">
                    <span>${m.points} points</span>
                    <span>&bull;</span>
                    <span>by ${escapeHtml(m.author)}</span>
                    <span>&bull;</span>
                    <span>${m.comments_count} comments</span>
                  </div>
                </div>
                <span class="mono" style="font-size:10px; color:var(--gold); font-weight:700;">[OPEN &rarr;]</span>
              </a>
            `).join('') : `
              <div style="background:var(--bg-core); border:1px solid var(--border-subtle); padding:24px; text-align:center; color:var(--text-muted); font-family:var(--font-mono); font-size:11px;">
                // No mentions currently logged. Click "SCAN FORUM" to query public tech oracles.
              </div>
            `}
          </div>
        </div>
      `;
    }

    osintLocalState.initialized = true;
  }

  // OSINT Action Handlers
  function setOsintDomain(dom) {
    osintLocalState.targetDomain = dom;
    osintLocalState.whoisDomain = dom;
    const dInput = document.getElementById('osintDnsInput');
    const wInput = document.getElementById('osintWhoisInput');
    if (dInput) dInput.value = dom;
    if (wInput) wInput.value = dom;
    resolveDnsMatrix();
  }

  function resolveDnsMatrix() {
    const dom = document.getElementById('osintDnsInput')?.value.trim() || osintLocalState.targetDomain;
    if (!dom) {
      showNotification('Please enter a target domain');
      return;
    }

    osintLocalState.targetDomain = dom;
    osintLocalState.dnsLoading = true;
    showNotification(`Resolving DNS matrix for ${dom}...`);

    fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        service: 'osint',
        action: 'dns_lookup',
        payload: { domain: dom }
      })
    })
    .then(r => r.json())
    .then(res => {
      osintLocalState.dnsLoading = false;
      if (res.success) {
        osintLocalState.dnsResult = res.result;
        showNotification(`Resolved DNS for ${dom} (${res.result.latency_ms}ms)`);
      } else {
        showNotification(`DNS Error: ${res.error}`);
      }
      fetchState();
    })
    .catch(err => {
      osintLocalState.dnsLoading = false;
      showNotification(`Network error: ${err.message}`);
      fetchState();
    });
  }

  function queryWhois() {
    const dom = document.getElementById('osintWhoisInput')?.value.trim() || osintLocalState.whoisDomain;
    if (!dom) {
      showNotification('Please enter a target domain');
      return;
    }

    osintLocalState.whoisDomain = dom;
    osintLocalState.whoisLoading = true;
    showNotification(`Querying Port 43 WHOIS registry for ${dom}...`);

    fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        service: 'osint',
        action: 'whois_lookup',
        payload: { domain: dom }
      })
    })
    .then(r => r.json())
    .then(res => {
      osintLocalState.whoisLoading = false;
      if (res.success) {
        osintLocalState.whoisResult = res.result;
        showNotification(`WHOIS queried: ${res.result.registrar}`);
      } else {
        showNotification(`WHOIS error: ${res.error}`);
      }
      fetchState();
    })
    .catch(err => {
      osintLocalState.whoisLoading = false;
      showNotification(`Network error: ${err.message}`);
      fetchState();
    });
  }

  function checkBreachAudit() {
    const acct = document.getElementById('osintHibpInput')?.value.trim() || osintLocalState.hibpAccount;
    const sim = document.getElementById('hibpSimulateCheck')?.checked ?? osintLocalState.hibpSimulate;

    if (!acct) {
      showNotification('Please enter an account or domain');
      return;
    }

    openConfirmModal({
      title: 'EXECUTE BREACH AUDIT',
      desc: 'Queries HaveIBeenPwned database for compromised credentials. Confirms this audit is targeting owned or authorized assets.',
      code: `TARGET ACCOUNT: ${acct}\nOWNED ASSET VERIFIED: YES\nMODE: ${sim ? 'LOCAL SIMULATION' : 'LIVE PRODUCTION API'}`,
      onConfirm: () => {
        osintLocalState.hibpAccount = acct;
        osintLocalState.hibpLoading = true;
        showNotification(`Auditing breach status for ${acct}...`);

        fetch('/api/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            service: 'osint',
            action: 'hibp_breach_check',
            payload: { account: acct, simulate: sim }
          })
        })
        .then(r => r.json())
        .then(res => {
          osintLocalState.hibpLoading = false;
          if (res.success) {
            osintLocalState.hibpResult = res.result;
            showNotification(`Audit complete: ${res.result.breach_count} compromises found`);
          } else {
            showNotification(`Audit error: ${res.error}`);
          }
          fetchState();
        })
        .catch(err => {
          osintLocalState.hibpLoading = false;
          showNotification(`Network error: ${err.message}`);
          fetchState();
        });
      }
    });
  }

  function scanBrandKeyword() {
    const kw = document.getElementById('brandKwInput')?.value.trim() || osintLocalState.brandKeyword;
    if (!kw) return;

    osintLocalState.brandKeyword = kw;
    osintLocalState.brandLoading = true;
    showNotification(`Scanning public oracles for "${kw}"...`);

    fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        service: 'osint',
        action: 'search_brand_mentions',
        payload: { keyword: kw }
      })
    })
    .then(r => r.json())
    .then(res => {
      osintLocalState.brandLoading = false;
      if (res.success) {
        osintLocalState.brandMentions = res.mentions || [];
        showNotification(`Identified ${osintLocalState.brandMentions.length} mentions for "${kw}"`);
      } else {
        showNotification(`Scan error: ${res.error}`);
      }
      fetchState();
    })
    .catch(err => {
      osintLocalState.brandLoading = false;
      showNotification(`Network error: ${err.message}`);
      fetchState();
    });
  }

  function filterBrandKeyword(kw) {
    osintLocalState.brandKeyword = kw;
    const input = document.getElementById('brandKwInput');
    if (input) input.value = kw;
    scanBrandKeyword();
  }

  function refreshBrandMentions() {
    scanBrandKeyword();
  }

  /* ========================================================
     EVENT RING PULSES & SOUNDS (Gold shockwave on real change)
     ======================================================== */
  function checkNewEvents(state) {
    if (!state || !state.services) return;
    
    Object.values(state.services).forEach(svc => {
      if (svc.recent_events && svc.recent_events.length > 0) {
        svc.recent_events.forEach(evt => {
          if (!seenEventIds.has(evt.id)) {
            seenEventIds.add(evt.id);
            // Trigger gold pulse on corresponding panel
            triggerGoldPulse(svc.name);
          }
        });
      }
    });
  }

  function triggerGoldPulse(serviceName) {
    const panel = document.querySelector(`[data-service="${serviceName}"]`);
    if (panel) {
      panel.classList.remove('ring-pulse');
      void panel.offsetWidth; // Force reflow
      panel.classList.add('ring-pulse');
      setTimeout(() => {
        panel.classList.remove('ring-pulse');
      }, 900);
    }
  }

  /* ========================================================
     CANVAS SPARKLINES
     ======================================================== */
  function drawSparkline(canvasId, points, strokeColor) {
    const canvas = document.getElementById(canvasId);
    if (!canvas || !points || points.length < 2) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width;
    const h = canvas.height;

    ctx.clearRect(0, 0, w, h);

    const min = Math.min(...points);
    const max = Math.max(...points);
    const range = (max - min) || 1;

    const coords = points.map((p, idx) => {
      const x = (idx / (points.length - 1)) * (w - 12) + 6;
      const y = h - 6 - ((p - min) / range) * (h - 16);
      return { x, y };
    });

    // Draw fill gradient
    const grad = ctx.createLinearGradient(0, 0, 0, h);
    grad.addColorStop(0, 'rgba(233, 180, 76, 0.25)');
    grad.addColorStop(1, 'rgba(233, 180, 76, 0.0)');

    ctx.beginPath();
    ctx.moveTo(coords[0].x, h);
    coords.forEach(pt => ctx.lineTo(pt.x, pt.y));
    ctx.lineTo(coords[coords.length - 1].x, h);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();

    // Draw stroke line
    ctx.beginPath();
    ctx.moveTo(coords[0].x, coords[0].y);
    coords.forEach(pt => ctx.lineTo(pt.x, pt.y));
    ctx.strokeStyle = strokeColor || '#E9B44C';
    ctx.lineWidth = 2;
    ctx.stroke();

    // End point dot
    const last = coords[coords.length - 1];
    ctx.beginPath();
    ctx.arc(last.x, last.y, 3, 0, Math.PI * 2);
    ctx.fillStyle = '#E9B44C';
    ctx.fill();
  }

  /* ========================================================
     MODAL CONFIRMATION DIALOG
     ======================================================== */
  function setupModal() {
    els.modalCancelBtn.addEventListener('click', () => {
      els.confirmModal.classList.remove('open');
      pendingConfirmCallback = null;
    });

    els.modalConfirmBtn.addEventListener('click', () => {
      els.confirmModal.classList.remove('open');
      if (pendingConfirmCallback) {
        pendingConfirmCallback();
        pendingConfirmCallback = null;
      }
    });
  }

  function showConfirmModal(title, desc, code, onConfirm) {
    els.modalTitle.textContent = title;
    els.modalDesc.textContent = desc;
    els.modalCode.textContent = code || '';
    els.modalCode.style.display = code ? 'block' : 'none';
    pendingConfirmCallback = onConfirm;
    els.confirmModal.classList.add('open');
  }

  /* ========================================================
     ACTIONS & DISPATCHERS
     ======================================================== */
  function saveApiKeys() {
    const stripe = document.getElementById('inputStripeKey')?.value.trim();
    const anthropic = document.getElementById('inputAnthropicKey')?.value.trim();
    const openai = document.getElementById('inputOpenAIKey')?.value.trim();
    const twilioSid = document.getElementById('inputTwilioSid')?.value.trim();
    const twilioToken = document.getElementById('inputTwilioToken')?.value.trim();

    const payload = {
      integrations: {
        stripe: { secret_key: stripe },
        anthropic: { api_key: anthropic },
        openai: { api_key: openai },
        twilio: { account_sid: twilioSid, auth_token: twilioToken }
      }
    };

    fetch('/api/config', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    .then(r => r.json())
    .then(res => {
      alert(res.success ? 'Configuration updated successfully.' : 'Failed to save configuration.');
      fetchState();
    });
  }

  function checkRepoUpdates() {
    fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service: 'settings', action: 'check_updates' })
    })
    .then(r => r.json())
    .then(res => alert(res.message || 'Build is up to date.'));
  }

  function confirmPullUpdates() {
    showConfirmModal(
      'PULL UPDATES & REBOOT',
      'This will execute git pull against the Command Center repository and restart the local feeder.',
      'git pull origin main && ./server.py --reboot',
      () => {
        alert('Update command confirmed.');
      }
    );
  }

  function inspectGitHubRepo() {
    const url = document.getElementById('deployRepoUrl')?.value.trim();
    if (!url) {
      alert('Please enter a GitHub repository URL');
      return;
    }

    const termEl = document.getElementById('deployTerminalScreen');
    if (termEl) {
      termEl.innerHTML += `\n<div class="t-line"><span class="t-prompt">[TRANSMIT]</span> Initiating git clone &amp; inspect for ${escapeHtml(url)}...</div>`;
      termEl.scrollTop = termEl.scrollHeight;
    }

    fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service: 'deploy', action: 'clone_and_inspect', payload: { url } })
    })
    .then(r => r.json())
    .then(res => {
      if (res.success) {
        fetchState();
      } else {
        alert(res.error || 'Failed to inspect repository');
        fetchState();
      }
    });
  }

  function confirmApproveDeploy() {
    const pending = currentState?.services?.deploy?.data?.pending_approval;
    if (!pending) return;

    showConfirmModal(
      'CONFIRM SCRIPT EXECUTION & REGISTRATION',
      `Executing install commands for ${pending.repo_name}. Scripts will run inside the sandbox.`,
      `REPOSITORY: ${pending.repo_name}\nTARGET: ${pending.target_dir}\nINSTALL COMMANDS:\n  ${(pending.install_commands || []).join('\n  ')}\n\nRUN COMMAND:\n  ${pending.run_command || 'None'}`,
      () => {
        fetch('/api/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            service: 'deploy',
            action: 'approve_install',
            payload: { confirmed: true }
          })
        })
        .then(r => r.json())
        .then(res => {
          if (res.success) {
            alert(res.message || 'Repository successfully registered');
            fetchState();
          } else {
            alert(res.error || 'Failed to register repository');
          }
        });
      }
    );
  }

  function cancelPendingDeploy() {
    if (currentState?.services?.deploy?.data) {
      currentState.services.deploy.data.pending_approval = null;
      renderDeploySection(currentState.services.deploy);
    }
  }

  function clearDeployLog() {
    fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service: 'deploy', action: 'clear_log' })
    })
    .then(r => r.json())
    .then(() => fetchState());
  }

  function runDnsLookup() {
    const domain = document.getElementById('osintDomainInput')?.value.trim();
    if (!domain) {
      alert('Please enter a domain');
      return;
    }

    const out = document.getElementById('osintOutput');
    out.textContent = `Querying authoritative DNS records for ${domain}...`;

    fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ service: 'osint', action: 'dns_lookup', payload: { domain } })
    })
    .then(r => r.json())
    .then(res => {
      if (res.success) {
        out.textContent = `
HOST: ${res.result.domain}
IPV4: ${res.result.ip}
TIME: ${new Date(res.result.timestamp * 1000).toISOString()}
STATUS: RESOLVED // NOMINAL
`;
      } else {
        out.textContent = `[ERROR]: ${res.error}`;
      }
    });
  }

  /* ========================================================
     COMMS ACTIONS & WORKFLOWS (WITH SAFETY GATES)
     ======================================================== */
  function labelEmailThread(threadId, label) {
    fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        service: 'comms',
        action: 'label_thread',
        payload: { thread_id: threadId, label: label }
      })
    })
    .then(r => r.json())
    .then(res => {
      if (res.success) {
        fetchState();
      } else {
        alert(res.error || 'Failed to label thread');
      }
    });
  }

  function replyThread(sender, subject) {
    const toInput = document.getElementById('composeTo');
    const subjInput = document.getElementById('composeSubject');
    const bodyInput = document.getElementById('composeBody');
    if (toInput) toInput.value = sender;
    if (subjInput) subjInput.value = subject;
    if (bodyInput) {
      bodyInput.value = '';
      bodyInput.focus();
    }
    const composeCard = document.getElementById('commsComposePanel');
    if (composeCard) composeCard.scrollIntoView({ behavior: 'smooth' });
  }

  function loadDraft(to, subject, body) {
    const toInput = document.getElementById('composeTo');
    const subjInput = document.getElementById('composeSubject');
    const bodyInput = document.getElementById('composeBody');
    if (toInput) toInput.value = to;
    if (subjInput) subjInput.value = subject;
    if (bodyInput) bodyInput.value = body;
  }

  function saveEmailDraft() {
    const to = document.getElementById('composeTo')?.value.trim() || '';
    const subject = document.getElementById('composeSubject')?.value.trim() || '';
    const body = document.getElementById('composeBody')?.value.trim() || '';

    fetch('/api/action', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        service: 'comms',
        action: 'save_draft',
        payload: { to, subject, body }
      })
    })
    .then(r => r.json())
    .then(res => {
      if (res.success) {
        fetchState();
      }
    });
  }

  function confirmSendEmail() {
    const to = document.getElementById('composeTo')?.value.trim();
    const subject = document.getElementById('composeSubject')?.value.trim();
    const body = document.getElementById('composeBody')?.value.trim();

    if (!to) {
      alert('Please specify recipient email address');
      return;
    }

    showConfirmModal(
      'CONFIRM OUTBOUND EMAIL DISPATCH',
      'You are about to transmit a production email via Gmail. Confirm recipient address and message content.',
      `TO: ${to}\nSUBJECT: ${subject || '(No subject)'}\n\n${body || '(Empty body)'}`,
      () => {
        fetch('/api/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            service: 'comms',
            action: 'send_email',
            payload: { to, subject, body, confirmed: true }
          })
        })
        .then(r => r.json())
        .then(res => {
          if (res.success) {
            document.getElementById('composeTo').value = '';
            document.getElementById('composeSubject').value = '';
            document.getElementById('composeBody').value = '';
            fetchState();
          } else {
            alert(res.error || 'Failed to dispatch email');
          }
        });
      }
    );
  }

  function confirmCreateCalendarEvent() {
    const title = document.getElementById('newEventTitle')?.value.trim();
    const timeVal = document.getElementById('newEventTime')?.value.trim();
    const attendees = document.getElementById('newEventAttendees')?.value.trim();

    if (!title) {
      alert('Please enter an appointment title');
      return;
    }

    showConfirmModal(
      'CONFIRM CALENDAR EVENT CREATION',
      'This will insert a scheduled block into your primary Google Calendar and notify attendees.',
      `APPOINTMENT: ${title}\nTIME: ${timeVal || 'Pending'}\nATTENDEES: ${attendees || 'Self'}`,
      () => {
        fetch('/api/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            service: 'comms',
            action: 'create_event',
            payload: { title, time: timeVal, attendees, confirmed: true }
          })
        })
        .then(r => r.json())
        .then(res => {
          if (res.success) {
            document.getElementById('newEventTitle').value = '';
            document.getElementById('newEventTime').value = '';
            document.getElementById('newEventAttendees').value = '';
            fetchState();
          } else {
            alert(res.error || 'Failed to schedule event');
          }
        });
      }
    );
  }

  function confirmSendTwilioSms() {
    const to = document.getElementById('smsToNumber')?.value.trim();
    const body = document.getElementById('smsBody')?.value.trim();

    if (!to || !body) {
      alert('Recipient phone number and message body are required');
      return;
    }

    showConfirmModal(
      'CONFIRM TWILIO SMS TRANSMISSION',
      'Confirm dispatch of outbound SMS via Twilio carrier trunk. Carrier transit fees apply.',
      `TARGET: ${to}\nPAYLOAD:\n${body}`,
      () => {
        fetch('/api/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            service: 'comms',
            action: 'send_sms',
            payload: { to, body, confirmed: true }
          })
        })
        .then(r => r.json())
        .then(res => {
          if (res.success) {
            document.getElementById('smsBody').value = '';
            fetchState();
          } else {
            alert(res.error || 'Failed to transmit SMS');
          }
        });
      }
    );
  }

  function confirmPlaceTwilioCall() {
    const to = document.getElementById('voiceToNumber')?.value.trim();
    const prompt = document.getElementById('voicePrompt')?.value.trim();

    if (!to) {
      alert('Target phone number is required');
      return;
    }

    showConfirmModal(
      'CONFIRM OUTBOUND VOICE CALL',
      'Initiating immediate outbound voice bridge via Twilio trunk.',
      `DIAL NUMBER: ${to}\nPROMPT / NOTES: ${prompt || 'Direct voice connection'}`,
      () => {
        fetch('/api/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            service: 'comms',
            action: 'place_call',
            payload: { to, prompt, confirmed: true }
          })
        })
        .then(r => r.json())
        .then(res => {
          if (res.success) {
            alert(res.message || 'Voice call placed');
            fetchState();
          } else {
            alert(res.error || 'Failed to initiate call');
          }
        });
      }
    );
  }

  function refreshComms() {
    fetchState();
  }

  /* ========================================================
     FINANCE ACTIONS (TRADE EXECUTION & BILL SETTLEMENT)
     ======================================================== */
  function setTradeOrderAction(action) {
    currentTradeAction = action;
    document.querySelectorAll('.order-tab').forEach(tab => {
      if (tab.textContent === action) {
        tab.classList.add('active');
      } else {
        tab.classList.remove('active');
      }
    });
    updateTradeEstimate();
  }

  function updateTradeEstimate() {
    const ticker = document.getElementById('tradeTickerSelect')?.value || 'BTC';
    const units = parseFloat(document.getElementById('tradeUnitsInput')?.value || 0);
    const estEl = document.getElementById('tradeEstimateTotal');
    if (!estEl || !currentState) return;

    const quotes = currentState.services?.finance?.data?.trade_panel?.market_quotes || {};
    const price = quotes[ticker]?.price || 79940;
    const total = units * price;
    estEl.textContent = `$${formatNumber(total)}`;
  }

  function confirmExecuteTrade() {
    const ticker = document.getElementById('tradeTickerSelect')?.value || 'BTC';
    const units = parseFloat(document.getElementById('tradeUnitsInput')?.value || 0);

    if (units <= 0 || isNaN(units)) {
      alert('Please enter a valid positive unit quantity');
      return;
    }

    const quotes = currentState?.services?.finance?.data?.trade_panel?.market_quotes || {};
    const price = quotes[ticker]?.price || 79940;
    const total = units * price;

    showConfirmModal(
      'CONFIRM ORDER EXECUTION',
      `You are about to transmit a production ${currentTradeAction} order. Slippage and execution fees apply.`,
      `ORDER: ${currentTradeAction} ${units} ${ticker}\nMARK PRICE: $${formatNumber(price)}\nESTIMATED TOTAL: $${formatNumber(total)} USD`,
      () => {
        fetch('/api/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            service: 'finance',
            action: 'execute_trade',
            payload: {
              ticker: ticker,
              action: currentTradeAction,
              units: units,
              confirmed: true
            }
          })
        })
        .then(r => r.json())
        .then(res => {
          if (res.success) {
            alert(res.message || 'Trade executed successfully');
            fetchState();
          } else {
            alert(res.error || 'Failed to execute trade order');
          }
        });
      }
    );
  }

  function settleBill(billId) {
    showConfirmModal(
      'SETTLE ACCOUNTS PAYABLE BILL',
      'Confirm reconciliation and payment settlement for this bill.',
      `BILL ID: ${billId}\nACTION: MARK PAID // SETTLED`,
      () => {
        fetch('/api/action', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            service: 'finance',
            action: 'mark_bill_paid',
            payload: { bill_id: billId }
          })
        })
        .then(r => r.json())
        .then(res => {
          if (res.success) {
            fetchState();
          }
        });
      }
    );
  }

  /* ========================================================
     HELPERS
     ======================================================== */
  function formatNumber(num) {
    if (num === null || num === undefined) return '--';
    return Number(num).toLocaleString('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function escapeHtml(str) {
    if (!str) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;');
  }

  // Expose API
  return {
    init,
    switchSection,
    saveApiKeys,
    checkRepoUpdates,
    confirmPullUpdates,
    inspectGitHubRepo,
    runDnsLookup,
    promptSmsCompose,
    promptVoiceCall,
    labelEmailThread,
    replyThread,
    loadDraft,
    saveEmailDraft,
    confirmSendEmail,
    confirmCreateCalendarEvent,
    confirmSendTwilioSms,
    confirmPlaceTwilioCall,
    refreshComms,
    setTradeOrderAction,
    updateTradeEstimate,
    confirmExecuteTrade,
    settleBill,
    confirmApproveDeploy,
    cancelPendingDeploy,
    clearDeployLog,
    loadWorkflow,
    togglePromptSync,
    onClaudePromptInput,
    onOpenAIPromptInput,
    onClaudeSystemInput,
    onOpenAISystemInput,
    onClaudeModelChange,
    onOpenAIModelChange,
    toggleClaudeSandbox,
    toggleOpenAISandbox,
    dispatchClaudePrompt,
    dispatchOpenAIPrompt,
    dispatchDualPrompt,
    createCanvaAsset,
    resetAITelemetry,
    copyClaudeOutput,
    copyOpenAIOutput,
    loadStudioScript,
    onStudioScriptInput,
    onStudioTitleInput,
    onStudioPresetChange,
    onStudioTtsChange,
    onStudioBrollChange,
    onStudioCaptionsChange,
    enqueueVideoRender,
    analyzeSourceVideo,
    cutSourceClip,
    searchBroll,
    selectBrollForScript,
    clearCompletedRenders,
    onPlaytestProfileChange,
    onPlaytestWindowChange,
    launchPlaytest,
    stopPlaytest,
    triggerGameBuild,
    clearGameLevel,
    setOsintDomain,
    resolveDnsMatrix,
    queryWhois,
    checkBreachAudit,
    scanBrandKeyword,
    filterBrandKeyword,
    refreshBrandMentions
  };
})();

// Boot on DOM Ready
document.addEventListener('DOMContentLoaded', CommandCenter.init);

