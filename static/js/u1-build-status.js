/* Static, evidence-labelled 60-item tracker. No network, storage or job actions. */
(function (root, factory) {
  'use strict';
  var api = factory();
  if (typeof module === 'object' && module.exports) module.exports = api;
  else { root.U1BuildStatus = api; api.register(root); }
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';
  var asOf = '2026-09-08';
  var states = {
  "local": {
    "label": "Local implementation",
    "meaning": "A bounded local implementation is reported or documented. This does not mean full acceptance, account setup or release readiness."
  },
  "setup": {
    "label": "Setup required",
    "meaning": "The adapter exists, but explicit account, consent or runtime setup is needed before the dependent workflow can be used."
  },
  "partial": {
    "label": "Partial",
    "meaning": "Some working pieces are known, but the requested scope, integration, coverage or acceptance remains incomplete."
  },
  "in_progress": {
    "label": "In progress",
    "meaning": "The responsible workstream is still landing. Final implementation and test evidence have not been supplied."
  },
  "unverified": {
    "label": "Unverified",
    "meaning": "No adequate final implementation or acceptance evidence was supplied for this specific item."
  }
};
  var sources = {
  "parent": {
    "label": "Parent handoff",
    "detail": "User-supplied parent status in this task on 2026-09-08. Not independently rerun by the Roadmap sidecar."
  },
  "studio": {
    "label": "Studio Pro handoff document",
    "detail": "docs/STUDIO-PRO.md read once for this tracker. It describes implementation and tests, but supplies no final combined acceptance result."
  },
  "mac": {
    "label": "Mac release handoff document",
    "detail": "docs/MAC-RELEASE.md read once for this tracker. Native build, interactive acceptance, signing and GitHub execution remain separate evidence."
  },
  "assistant": {
    "label": "Native AI/image handoff / mocked tests",
    "detail": "C reports 35 native AI tests and 26 image tests passing with mocked boundaries. Assets and endpoints are parent-wired. Queued jobs, read-only Codex CLI requests and explicit voice/transcript review are implemented; no account authorisation or live image paid call is verified."
  },
  "workflows": {
    "label": "Local workflow handoff / 47 tests",
    "detail": "docs/PERSONAL-WORKFLOWS.md read once. The parent and handoff report 47 isolated tests passing, including actual on-demand paper accounting and threshold evaluation. No background live monitor or automated strategy agent."
  },
  "media": {
    "label": "Native media handoff / real FFmpeg pass",
    "detail": "docs/MEDIA-RESEARCH.md read once. Parent reports native media/OSINT wiring, old iframe fallback retirement and a separate real-FFmpeg agent test passing; its test count is not supplied."
  },
  "connections": {
    "label": "Connections sidecar evidence",
    "detail": "Native Connections/Settings implementation and 23 passing fixture tests observed earlier in this task. Not rerun as part of the Roadmap tests."
  },
  "platform": {
    "label": "Known native platform boundary",
    "detail": "Earlier inspected local platform contracts in this task. Not reread while parallel agents change shared files; final integrated evidence is pending."
  },
  "unknown": {
    "label": "Evidence not supplied",
    "detail": "No final handoff or acceptance evidence for this specific item was provided."
  }
};
  var evidence = [
  {
    "id": "existing",
    "label": "Existing parent suite",
    "count": 90,
    "result": "PASS",
    "provenance": "Parent-reported; not rerun here"
  },
  {
    "id": "safety",
    "label": "Safety",
    "count": 12,
    "result": "PASS",
    "provenance": "Parent-reported; not rerun here"
  },
  {
    "id": "private_backup",
    "label": "Private backup",
    "count": 4,
    "result": "PASS",
    "provenance": "Parent-reported; not rerun here"
  },
  {
    "id": "release_guard",
    "label": "ReleaseGuard",
    "count": 4,
    "result": "PASS",
    "provenance": "Parent-reported; not rerun here"
  },
  {
    "id": "routing",
    "label": "Native routing",
    "count": 3,
    "result": "PASS",
    "provenance": "Parent-reported; not rerun here"
  },
  {
    "id": "connections",
    "label": "Connections sidecar",
    "count": 23,
    "result": "PASS",
    "provenance": "Observed earlier in this task; not rerun here"
  },
  {
    "id": "personal_workflows",
    "label": "B: local workflows",
    "count": 47,
    "result": "PASS",
    "provenance": "Parent and new workflow handoff report; not rerun here"
  },
  {
    "id": "strict_gate",
    "label": "E: strict gate",
    "count": 289,
    "result": "PASS",
    "provenance": "Parent-reported strict gate; may include the separately listed suites"
  },
  {
    "id": "strict_syntax",
    "label": "E: syntax checks",
    "count": 32,
    "unit": "syntax checks",
    "result": "PASS",
    "provenance": "Parent-reported checks; not a test-suite count"
  },
  {
    "id": "real_ffmpeg",
    "label": "Separate real FFmpeg agent test",
    "count": null,
    "result": "PASS",
    "provenance": "Parent-reported real synthetic-fixture exports; separate from the strict gate; count not supplied"
  }
];
  evidence = evidence.concat([{"id":"native_ai","label":"C: native AI","count":35,"result":"PASS","provenance":"Parent-reported mocked suite; no live CLI/account execution verified"},{"id":"image_adapter","label":"C: paid image adapter","count":26,"result":"PASS","provenance":"Parent-reported mocked suite; no authorisation or live paid request verified"}]);
  var raw = [
    [1,"Studio fixes","partial","Creation","studio","studio","Studio Pro documents native structured editing and bounded artifact generation; the parent reports the old iframe fallback retired.","Full cross-workspace visual and interactive Studio acceptance remains separate from the automated gate."],
    [2,"Safety validation","local","Trust","security","parent","The parent reports 12 safety tests passing.","This is reported test evidence for the U1 application safety boundary, not a full security audit or a Mac-wide lock."],
    [3,"AI Command","local","AI","ai","assistant","Native AI Command queues explicit read-only Codex CLI requests; C reports 35 mocked native AI tests passing.","CLI installation/sign-in and successful live provider execution are not established by mocked tests."],
    [4,"Navigation/search","partial","Workspace","home","parent","The parent reports native media/OSINT wiring, retirement of the old iframe fallback and three routing tests passing.","Automated routing evidence does not establish every interactive navigation/search flow across the combined workspace."],
    [5,"Job centre","local","AI","jobs","assistant","The native assistant includes queued managed jobs; C reports 35 mocked native AI tests passing and the parent has wired assets/endpoints.","The scope is explicitly managed jobs, not arbitrary Mac processes; live CLI execution and full interactive acceptance remain separate."],
    [6,"Release process","partial","Workspace","updater","parent","The parent reports four ReleaseGuard tests plus a strict gate passing 289 tests and 32 syntax checks.","These local results do not establish a reviewed final source revision, interactive Mac acceptance or a successful GitHub workflow."],
    [7,"Morning brief","partial","Workspace","briefing","platform","The known native platform exposes a Daily Command Brief.","Final source coverage and usefulness are not accepted; Google-backed material requires a configured account."],
    [8,"Top 3 priorities","local","Workspace","life","workflows","The local workflow implements date-specific Top 3 slots, complete/reopen and links to real tasks; B reports 47 tests passing.","Exactly three active slots are supported per date. This does not automatically choose priorities for the user."],
    [9,"Day planning","local","Workspace","life","workflows","The local workflow implements editable dated time blocks, calendar links and overlap rejection.","Blocks are same-day and use the workspace timezone; no automatic rescheduling or remote calendar write is claimed."],
    [10,"Life/business layouts","local","Workspace","life","workflows","Native Life, Income and Research views provide separate personal, business and manual-market collections.","The handoff establishes bounded native collections, not full desktop/mobile visual acceptance or external account integration."],
    [11,"Household organiser","local","Workspace","life","workflows","Household bills and renewals support due dates, planned amounts, editable recurrence and paid/cancelled notes; B reports 47 tests passing.","Recurrence is an operator-managed plan, without payments, automatic advancement or background reminders."],
    [12,"Wellbeing","local","Workspace","life","workflows","The local workflow implements flexible/daily/weekly habits, dated check-ins and undo.","No streak penalties, health advice or medical interpretation is provided; check-in history is bounded."],
    [13,"Visual document editor","local","Creation","studio","studio","Studio Pro documents a local title, brand and ordered-section editor with preview invalidation.","It is a structured document editor, not an arbitrary freeform page-layout canvas; parent integration remains to be accepted."],
    [14,"Actual PDF preview","local","Creation","studio","studio","Studio Pro documents page images rendered from the exact returned PDF bytes using PDFium.","The page-image preview needs pypdfium2; signed previews expire on server restart, and parent browser acceptance is pending."],
    [15,"Fillable PDF","local","Creation","studio","studio","Studio Pro documents real ReportLab AcroForm response fields and form-preserving PDF output.","PDF-reader support varies; filled reader copies do not update the editable Studio source."],
    [16,"Hyperlinked planner","local","Creation","studio","studio","Studio Pro documents internal contents links, bookmarks and section/footer navigation in generated workbooks.","This is bounded section-based navigation, not an arbitrary planner interaction or external-link editor."],
    [17,"Course builder","local","Creation","studio","studio","Studio Pro documents operator-authored lessons, activities, quizzes and optional answer notes.","No automatic marking, AI lesson authoring, course hosting or checkout is established."],
    [18,"AI images","setup","AI","images","assistant","A real official paid gpt-image-1.5 request adapter with Keychain setup is present; C reports 26 mocked image tests passing.","Provider authorisation and a live paid request are not verified. The user must configure credentials and explicitly request billable generation."],
    [19,"Mockups","local","Creation","studio","studio","Studio Pro documents real local cover and mockup SVG artifacts.","These are SVG cover mockups, not product photography, a 3D renderer or generated company artwork."],
    [20,"Brand kit","partial","Creation","studio","studio","Studio Pro documents reusable browser-local brand name, accent and font preferences.","A full brand asset library, font licensing controls and external brand-kit synchronisation are not established."],
    [21,"Product ZIP bundle","local","Creation","studio","studio","Studio Pro documents ZIP output containing the PDF, SVG artwork, operator instructions, licence and metadata.","A bundle requires operator-supplied instructions and licence text; it does not publish a product or establish rights."],
    [22,"Asset library","partial","Creation","files","platform","Managed Files provides local asset storage, and Studio Pro documents explicit artifact saves.","Final integrated upload acceptance, richer asset metadata and rights verification remain outside this evidence."],
    [23,"Product catalogue","local","Business","income","workflows","Product records support status, audience, outcome, version labels and links to actual ready local files.","File binaries remain in managed Files; no storefront, checkout or inventory sync is claimed."],
    [24,"Opportunity inbox","local","Business","income","workflows","Opportunity records capture hypotheses, dated source evidence, confidence and next research steps.","Validation requires operator evidence; confidence is an assessment, not an automated opportunity or demand guarantee."],
    [25,"Offers","local","Business","income","workflows","Scoped offers link local contacts, products, delivery projects and contextual notes.","No outgoing customer contact, signatures, payments or external CRM synchronisation is performed."],
    [26,"Pricing worksheet","local","Business","income","workflows","A Decimal-based worksheet calculates assumed sales, fees, labour, costs, result and break-even.","These are pricing assumptions, not actual sales, guaranteed demand or verified revenue."],
    [27,"Launch board","local","Business","income","workflows","A product-linked launch board supports Backlog, Doing, Review and Done stages.","The board is operator-managed; moving a card does not publish a product or run a launch."],
    [28,"Actual sales/expenses","partial","Business","income","platform","The known native platform includes a local ledger and explicit entry workflow.","Records must come from real user input or verified imports. Live payments, bank feeds and actual sales totals are not established here."],
    [29,"Clients","local","Business","income","workflows","Local contacts, offers, client projects and notes have linked record lifecycles.","There is no outgoing contact or external CRM sync; parent browser acceptance remains a separate check."],
    [30,"Selected AI context","local","AI","ai","assistant","The delivered native AI workflow uses user-selected context for explicit queued requests; C reports its 35-test mocked suite passing.","Mocked tests do not establish successful live provider execution. No hidden email context or expanded account permissions are assumed."],
    [31,"Voice","local","AI","ai","assistant","The delivered voice workflow requires explicit input and transcript review before submission; C reports 35 mocked AI tests passing.","Actual microphone/browser permissions and live device acceptance remain separate; there is no always-listening service."],
    [32,"Action previews","partial","AI","ai","parent","Known managed operations have explicit confirmations and bounded request bodies.","Confirmation dialogs alone do not establish a consistent preview-before-action workflow for every module."],
    [33,"Specialist roles","local","AI","ai","assistant","The delivered native AI workstream includes selectable specialist-role context alongside explicit queued requests.","Roles are local request context, not autonomous agents, expanded provider permissions or proof of successful account execution."],
    [34,"War Room","partial","AI","ai","assistant","The assistant role/collaboration implementation files are now present.","A fully accepted War Room workflow or autonomous multi-agent orchestration has not been established."],
    [35,"Improvement review","partial","AI","ai","parent","The existing improvement scanner produces reports for operator review.","It is report-only, not automated self-coding, unattended fixes, autonomous commits or self-deployment."],
    [36,"Branded connections","local","Connections","integrations","connections","The native Connections sidecar provides consistent U1 cards and clear provider wordmarks.","Its 23 fixture tests passed earlier in this task; final parent asset wiring and browser visual acceptance remain separate."],
    [37,"Connection health","local","Connections","integrations","connections","Connection cards show returned account, permissions and last-success evidence without inventing missing values.","Most providers only save settings. Requested scopes and saved credentials are not verified account health."],
    [38,"Google workflow","setup","Connections","integrations","parent","The newer read-only Gmail/Calendar adapter and Keychain workflow exist.","No Google account is configured. Desktop OAuth client setup, consent and a successful explicit sync are still required."],
    [39,"Provider capability checks","partial","Connections","integrations","connections","A read-only capability catalogue separates supported Google actions, API settings and local tool detection.","Most adapters do not expose account checks. CLI paths or app-data directories do not verify sign-in, launch or entitlements."],
    [40,"Separate usage dashboard","local","Connections","usage","platform","The known native platform keeps provider usage and allowances separate.","Only supported, returned allowance data is usable; local Claude/Antigravity activity does not establish subscription quota."],
    [41,"Deduplicated 10% alerts","local","Connections","notifications","platform","The known platform supports deduplicated ten-percent thresholds for available provider allowance windows.","Alerts depend on fresh supported allowance data and the local server; unavailable provider quotas cannot produce verified thresholds."],
    [42,"Email PDF briefing","setup","Connections","integrations","parent","The Google adapter supports bounded optional PDF imports and local review-briefing sources.","No Google account is configured. PDF import is opt-in and bounded; it is not full mailbox coverage or scanned-document OCR."],
    [43,"Appointment review","setup","Connections","calendar","parent","The Google adapter supports explicit approval of returned calendar versions into local records.","No Google account is configured. Absent events are not cancellations, and this connector does not edit Google Calendar."],
    [44,"Social calendar","local","Media","income","workflows","The local workflow implements dated, channel-specific content drafts and operator-recorded published links.","There is no social login, scheduled posting, automatic publishing or verification that a published link was posted by this app."],
    [45,"Rights-aware media","partial","Media","media","media","Native Media/OSINT provide a local source casebook, attribution and operator rights/verification notes; parent wiring is reported complete.","Operator assessments do not automatically verify legal rights. There are no hidden email sources or unsolicited remote source fetches."],
    [46,"Actual clips","local","Media","media","media","Native local FFmpeg clip export is implemented; the parent reports a separate real-FFmpeg agent test passing.","The real test uses synthetic local fixtures. Supported codecs, 25 MiB files, 120-second clips and bounded rendering apply; broad interactive media acceptance is separate."],
    [47,"Faceless workflow","partial","Media","income","workflows","Local script/storyboard/asset/voice/caption planning and rights review can be combined with the native real-FFmpeg tools.","This remains an operator-led workflow, not autonomous narration, generation, distribution or a complete unattended video pipeline."],
    [48,"Market watchlists","local","Markets","research","workflows","Manual watchlists record instrument, currency, thesis, source and timestamped observations.","Observations are operator reviewed; there is no continuous live market feed or automated research agent."],
    [49,"Price alerts","partial","Markets","research","workflows","Actual on-demand threshold evaluation checks reviewed timestamped observations and deduplicates crossings; B reports 47 tests passing.","There is no background live monitor, push-notification delivery or trade trigger. A user must explicitly request each check."],
    [50,"Trading journal","local","Markets","research","workflows","The local trading journal records paper rationale, risk, assumed prices and reviewed closed-entry outcomes.","It is separate from the paper simulator and actual ledger; no brokerage execution or verified investment return is implied."],
    [51,"Paper research","partial","Markets","research","workflows","Actual on-demand paper buys/sells maintain separate accounts, cash, holdings, weighted cost and realised outcomes; threshold checks are explicit.","This is long-only operator-reviewed simulation, not a background live service, automated strategy agent, broker execution or verified backtest."],
    [52,"Lock/Pause/Stop","local","Trust","security","parent","The parent reports application-lock and explicitly managed pause/resume/stop operations with safety tests passing.","The boundary is U1-managed work, not every Mac process. Confirmation is required and locked-state actions require the passphrase."],
    [53,"Permission centre","partial","Trust","security","parent","The parent provides permission information and bounded operations.","This is not a complete granular capability engine or universal policy enforcement across inherited adapters."],
    [54,"Keychain credentials","partial","Trust","integrations","parent","Google and the new AI credential paths use Keychain.","Legacy API-setting fields remain. Do not claim all credentials were migrated or all configuration is encrypted."],
    [55,"Encrypted backups","local","Trust","security","parent","The parent reports real AES-GCM copies with scrypt and four private-backup tests passing.","The workflow is bounded to 16 MiB and restores separately without overwriting active data; it is not whole-Mac or unlimited backup."],
    [56,"Privacy mode","local","Trust","settings","connections","Native Settings applies real masking styles and a persisted screen-sharing preference.","Masks cover documented native/opted-in surfaces, not other apps, unmarked content, downloads or source inspection; this is not encryption."],
    [57,"Shared design","partial","Experience","settings","parent","The parent coordinates the shared U1 design and global grid fix; sidecars use the existing visual language.","Cross-workspace desktop/mobile and accessibility acceptance is still pending."],
    [58,"Purposeful motion/sounds","partial","Experience","settings","connections","Native Settings uses the existing feedback/boot APIs and preserves reduced-motion and engine defaults.","The sidecar tests are stubbed; final playback, motion and accessibility acceptance across every view remain pending."],
    [59,"Mac app","partial","Experience","system","mac","The Mac handoff documents a local wrapper with ownership checks and bounded reconnect behaviour.","It depends on this checkout/runtime, is not notarised, and still needs final native-build and interactive acceptance evidence."],
    [60,"GitHub presentation","in_progress","Experience",null,"parent","The parent owns the current README, historical-documents archive link and final presentation.","This sidecar changes no README or archive. No push, GitHub CI run, signed release or public deployment is established here."]
  ];

  var routes = Object.freeze({
    roadmap: 'Roadmap', studio: 'Studio', security: 'Security', ai: 'AI Command',
    jobs: 'Jobs', updater: 'Updater', briefing: 'Morning brief', tasks: 'Tasks',
    calendar: 'Calendar', home: 'Home', life: 'Life', files: 'Files',
    business: 'Business', images: 'AI images', integrations: 'Connections',
    settings: 'Settings', usage: 'Usage', notifications: 'Notifications',
    media: 'Media', trading: 'Trading', system: 'System', income: 'Income', research: 'Research', osint: 'OSINT'
  });
  Object.keys(states).forEach(function (key) { Object.freeze(states[key]); });
  Object.keys(sources).forEach(function (key) { Object.freeze(sources[key]); });
  Object.freeze(states); Object.freeze(sources);
  var items = Object.freeze(raw.map(function (row) {
    return Object.freeze({ id: row[0], title: row[1], status: row[2], area: row[3],
      route: row[4], source: row[5], evidence: row[6], limitation: row[7] });
  }));
  var testEvidence = Object.freeze(evidence.map(function (entry) { return Object.freeze(entry); }));
  var areas = Object.freeze(Array.from(new Set(items.map(function (item) { return item.area; }))).sort());
  var registered = new WeakSet();
  function own(object, key) { return Object.prototype.hasOwnProperty.call(object, key); }
  function text(value) { return typeof value === 'string' ? value : ''; }
  function escape(value) {
    return String(value == null ? '' : value).replace(/[&<>"']/g, function (char) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[char];
    });
  }
  function safeRoute(value) { return typeof value === 'string' && own(routes, value) ? value : null; }
  function validStatus(value) { return typeof value === 'string' && own(states, value); }
  function counts(list) {
    var result = {};
    Object.keys(states).forEach(function (key) { result[key] = 0; });
    (Array.isArray(list) ? list : items).forEach(function (item) {
      if (item && validStatus(item.status)) result[item.status]++;
    });
    return Object.freeze(result);
  }
  function filter(list, options) {
    options = options && typeof options === 'object' ? options : {};
    var selected = text(options.status) || 'all', area = text(options.area) || 'all';
    if (selected !== 'all' && !validStatus(selected)) return [];
    var words = text(options.query).trim().toLowerCase().split(/\s+/).filter(Boolean);
    return (Array.isArray(list) ? list : []).filter(function (item) {
      if (!item || !validStatus(item.status)) return false;
      if (selected !== 'all' && item.status !== selected || area !== 'all' && item.area !== area) return false;
      var source = own(sources, item.source) ? sources[item.source].label : '';
      var haystack = ['#' + item.id, String(item.id), item.title, item.area, states[item.status].label, source, item.evidence, item.limitation].join(' ').toLowerCase();
      return words.every(function (word) { return haystack.includes(word); });
    });
  }
  function sourceLabel(item) { return own(sources, item.source) ? sources[item.source].label : 'Evidence not supplied'; }
  function available(route, supports) {
    if (!safeRoute(route) || typeof supports !== 'function') return false;
    try { return supports(route) === true; } catch (_) { return false; }
  }
  function routeButton(route, supports) {
    route = safeRoute(route);
    if (!route) return '<span class="u1-build-muted">Parent handoff</span>';
    var label = routes[route];
    return available(route, supports)
      ? '<button type="button" class="u1-build-link" data-go="' + route + '">' + escape(label) + '</button>'
      : '<button type="button" class="u1-build-link" disabled title="This native workspace has not registered a view yet.">' + escape(label) + ' unavailable</button>';
  }
  function renderRows(list, supports) {
    if (!Array.isArray(list) || !list.length) return '<tr><td colspan="5" class="u1-build-empty">No items match these filters. Change the status, area or search text.</td></tr>';
    return list.map(function (item) {
      var status = validStatus(item.status) ? item.status : 'unverified';
      var number = Number.isInteger(item.id) && item.id >= 1 && item.id <= 60 ? item.id : '?';
      return '<tr data-build-item="' + number + '"><td class="u1-build-number">' + String(number).padStart(2, '0') + '</td>' +
        '<th scope="row"><span class="u1-build-area">' + escape(item.area) + '</span><span class="u1-build-title">' + escape(item.title) + '</span></th>' +
        '<td><span class="u1-build-pill" data-build-state="' + status + '">' + states[status].label + '</span></td>' +
        '<td class="u1-build-evidence"><p>' + escape(item.evidence) + '</p><p class="u1-build-limit"><strong>Remaining boundary:</strong> ' + escape(item.limitation) + '</p><small>' + escape(sourceLabel(item)) + '</small></td>' +
        '<td>' + routeButton(item.route, supports) + '</td></tr>';
    }).join('');
  }
  function testTable() {
    return '<details class="u1-build-details"><summary>Recorded test evidence and its limits</summary><p>Separate suite reports, not a combined unique-test total. The parent owns the final integrated run. Roadmap tests validate this tracker, not the other 60 features.</p><div class="u1-build-table-scroll" tabindex="0" role="region" aria-label="Recorded test evidence"><table><caption>Evidence received for this handoff</caption><thead><tr><th scope="col">Suite</th><th scope="col">Reported result</th><th scope="col">Provenance</th></tr></thead><tbody>' +
      testEvidence.map(function (entry) { return '<tr><th scope="row">' + escape(entry.label) + '</th><td>' + (entry.count == null ? '' : entry.count + ' ' + escape(entry.unit || 'tests') + ' / ') + escape(entry.result) + '</td><td>' + escape(entry.provenance) + '</td></tr>'; }).join('') +
      '</tbody></table></div><p>No test count establishes a configured Google account, successful paid-provider call, notarised Mac app or completed GitHub release.</p></details>';
  }
  function shell(supports) {
    var totals = counts();
    return '<header class="u1-build-header"><div><span class="u1-build-eyebrow">U1 OS / BUILD HANDOFF</span><h2>Build roadmap</h2><p>60 requested items. Each status carries its evidence and remaining boundary.</p></div><span class="u1-build-date">Snapshot: ' + asOf + '</span></header>' +
      '<aside class="u1-build-notice"><strong>Local implementation does not mean full acceptance.</strong><p>All agent implementation files are reported present. This static snapshot includes the reported strict gate and separate real-FFmpeg pass. Account setup, interactive checks and final release evidence remain separate. This page performs no live checks.</p></aside>' +
      '<div class="u1-build-counts" aria-label="Items by status">' + Object.keys(states).map(function (key) {
        return '<div class="u1-build-count" data-build-state="' + key + '"><strong>' + totals[key] + '</strong><span>' + states[key].label + '</span></div>';
      }).join('') + '</div>' +
      '<details class="u1-build-details"><summary>What each status means</summary><dl class="u1-build-legend">' + Object.keys(states).map(function (key) {
        return '<div><dt>' + states[key].label + '</dt><dd>' + escape(states[key].meaning) + '</dd></div>';
      }).join('') + '</dl></details>' +
      '<nav class="u1-build-shortcuts" aria-label="Native workspace shortcuts">' + ['studio', 'life', 'income', 'research', 'media', 'osint', 'ai', 'jobs', 'integrations', 'security', 'updater', 'settings'].map(function (route) { return routeButton(route, supports); }).join('') + '</nav>' +
      '<form class="u1-build-filters" data-build-filters role="search" aria-label="Filter build items"><label>Search items<input type="search" name="query" data-build-query placeholder="Title, number, evidence or limitation" maxlength="200" autocomplete="off" aria-controls="u1-build-table"></label>' +
      '<label>Status<select name="status" data-build-status aria-controls="u1-build-table"><option value="all">All statuses</option>' + Object.keys(states).map(function (key) { return '<option value="' + key + '">' + states[key].label + '</option>'; }).join('') + '</select></label>' +
      '<label>Area<select name="area" data-build-area aria-controls="u1-build-table"><option value="all">All areas</option>' + areas.map(function (area) { return '<option value="' + escape(area) + '">' + escape(area) + '</option>'; }).join('') + '</select></label><button type="reset">Reset filters</button></form>' +
      '<p class="u1-build-results" data-build-results role="status" aria-live="polite" aria-atomic="true">Showing 60 of 60 items. This is an item count, not completion.</p>' +
      '<div class="u1-build-table-scroll" tabindex="0" role="region" aria-label="60-item build tracker"><table id="u1-build-table"><caption>Requested scope, status and evidence</caption><thead><tr><th scope="col">#</th><th scope="col">Requested item</th><th scope="col">Status</th><th scope="col">Evidence and remaining work</th><th scope="col">Native workspace</th></tr></thead><tbody data-build-rows>' + renderRows(items, supports) + '</tbody></table></div>' +
      testTable() + '<footer class="u1-build-footer">Parent integration may change these statuses. Refreshing or reopening this view does not collect new feature evidence. Disabled links mean the native route is not registered. Historical documentation remains under the archive link maintained in the parent README.</footer>';
  }
  var css = [
    '.u1-build-status{--build-ink:var(--u1-core-ink,#edf6ff);--build-muted:var(--u1-core-muted,#a2b8cd);--build-accent:var(--u1-core-accent,#6be4ff);--build-edge:var(--u1-core-edge,rgba(98,180,236,.22));color:var(--build-ink);font:inherit;min-width:0;padding-bottom:24px}',
    '.u1-build-status *{box-sizing:border-box}.u1-build-status .u1-build-header{display:flex;justify-content:space-between;align-items:flex-start;gap:24px;padding:22px 0;border-bottom:1px solid var(--build-edge)}',
    '.u1-build-status .u1-build-eyebrow{font-size:10px;letter-spacing:.14em;color:var(--build-accent);font-weight:600}.u1-build-status h2{font-size:clamp(30px,4vw,44px);line-height:1.15;letter-spacing:-.045em;font-weight:600;margin:12px 0}.u1-build-status .u1-build-header p{font-size:13px;line-height:1.8;color:var(--build-muted);margin:0}.u1-build-status .u1-build-date{font-size:11px;color:var(--build-muted);white-space:nowrap;padding-top:10px}',
    '.u1-build-status .u1-build-notice{margin:22px 0;padding:20px 24px;border:1px solid var(--build-edge);border-left:3px solid var(--build-accent);border-radius:14px;background:radial-gradient(ellipse at 0 0,#154e7045,transparent 75%),#081a2aca}.u1-build-status .u1-build-notice strong{font-size:14px;font-weight:600}.u1-build-status .u1-build-notice p{margin:8px 0 0;color:var(--build-muted);font-size:12px;line-height:1.8;max-width:900px}',
    '.u1-build-status .u1-build-counts{display:flex;flex-wrap:wrap;gap:12px;margin:20px 0}.u1-build-status .u1-build-count{flex:1 1 135px;border:1px solid var(--build-edge);border-radius:14px;padding:16px;background:linear-gradient(135deg,#0b2033,#061221)}.u1-build-status .u1-build-count strong{display:block;font-size:28px;line-height:1.2;font-weight:550;letter-spacing:-.04em;font-variant-numeric:tabular-nums}.u1-build-status .u1-build-count span{display:block;font-size:11px;margin-top:8px;color:var(--build-muted)}',
    '.u1-build-status .u1-build-details{border:1px solid var(--build-edge);border-radius:12px;padding:12px 18px;margin:18px 0;background:#081a2a66}.u1-build-status summary{cursor:pointer;font-size:13px;line-height:1.8;padding:5px 0;min-height:34px}.u1-build-status .u1-build-details>p{font-size:12px;color:var(--build-muted);line-height:1.8}.u1-build-status .u1-build-legend>div{display:flex;gap:18px;margin:15px 0;font-size:12px;line-height:1.8}.u1-build-status .u1-build-legend dt{flex:0 0 145px;font-weight:600}.u1-build-status .u1-build-legend dd{margin:0;color:var(--build-muted)}',
    '.u1-build-status .u1-build-shortcuts{display:flex;flex-wrap:wrap;gap:8px;margin:22px 0}.u1-build-status button{font:inherit;font-size:12px;min-height:40px;border-radius:9px;border:1px solid var(--build-edge);background:#14304499;color:var(--build-ink);padding:9px 12px;cursor:pointer}.u1-build-status button:disabled{opacity:.48;cursor:not-allowed}.u1-build-status button:hover:not(:disabled){border-color:var(--build-accent)}.u1-build-status :focus-visible{outline:2px solid var(--build-accent);outline-offset:4px}',
    '.u1-build-status .u1-build-filters{display:flex;flex-wrap:wrap;align-items:flex-end;gap:14px;margin:26px 0 12px}.u1-build-status .u1-build-filters label{display:flex;flex-direction:column;gap:7px;flex:1 1 160px;font-size:11px;line-height:1.7;color:var(--build-muted)}.u1-build-status .u1-build-filters label:first-child{flex:3 1 250px}.u1-build-status input,.u1-build-status select{font:inherit;font-size:14px;min-height:44px;min-width:0;width:100%;padding:10px 12px;color:var(--build-ink);background:#061423;border:1px solid var(--build-edge);border-radius:9px;color-scheme:dark}.u1-build-status input::placeholder{color:#91a8bc}.u1-build-status .u1-build-results{font-size:12px;line-height:1.8;color:var(--build-muted)}',
    '.u1-build-status .u1-build-table-scroll{max-width:100%;overflow:auto;border:1px solid var(--build-edge);border-radius:14px;background:#061422b0}.u1-build-status table{width:100%;min-width:850px;border-collapse:collapse;text-align:left;font-size:12px;line-height:1.7}.u1-build-status caption{text-align:left;padding:14px 18px;font-size:11px;color:var(--build-muted)}.u1-build-status th,.u1-build-status td{padding:17px 16px;vertical-align:top;border-top:1px solid var(--build-edge)}.u1-build-status thead th{font-size:10px;text-transform:uppercase;letter-spacing:.08em;font-weight:600;color:var(--build-accent);background:#0c2337}.u1-build-status tbody th{min-width:180px;max-width:260px;font-weight:550}.u1-build-status .u1-build-number{font-variant-numeric:tabular-nums;color:var(--build-muted);font-size:11px}.u1-build-status .u1-build-area{display:block;color:var(--build-muted);font-size:10px;font-weight:400;margin-bottom:5px}.u1-build-status .u1-build-title{font-size:14px;line-height:1.6;overflow-wrap:anywhere}',
    '.u1-build-status .u1-build-pill{display:inline-block;white-space:nowrap;border:1px solid #8eb7d33d;border-radius:7px;padding:5px 9px;font-size:10px;color:#bed6e7;background:#25456022}.u1-build-status .u1-build-pill[data-build-state=local]{color:#a0e9fa;border-color:#6be4ff44;background:#1880ab18}.u1-build-status .u1-build-pill[data-build-state=setup]{color:#f4c995;border-color:#c79b6244;background:#79551b18}.u1-build-status .u1-build-pill[data-build-state=partial]{color:#eadab1;border-color:#c1af6644;background:#796a1b14}.u1-build-status .u1-build-pill[data-build-state=in_progress]{color:#b7ccfb;border-color:#84a7f344;background:#37619718}',
    '.u1-build-status .u1-build-evidence{min-width:300px;max-width:600px;overflow-wrap:anywhere}.u1-build-status .u1-build-evidence p{margin:0 0 10px}.u1-build-status .u1-build-limit{color:var(--build-muted);font-size:11px}.u1-build-status .u1-build-limit strong{font-weight:550;color:#d6e5f2}.u1-build-status .u1-build-evidence small{font-size:10px;color:#8faabd}.u1-build-status .u1-build-muted{font-size:11px;color:var(--build-muted)}.u1-build-status .u1-build-empty{padding:28px;color:var(--build-muted)}.u1-build-status .u1-build-footer{margin-top:24px;padding-top:18px;border-top:1px solid var(--build-edge);color:var(--build-muted);font-size:11px;line-height:1.8}',
    '@media(max-width:700px){.u1-build-status .u1-build-header{flex-direction:column;gap:6px}.u1-build-status .u1-build-notice{padding:18px}.u1-build-status .u1-build-legend>div{display:block}.u1-build-status .u1-build-legend dd{margin-top:5px}.u1-build-status .u1-build-filters button{width:100%}.u1-build-status .u1-build-count{flex-basis:130px}}',
    '@media(prefers-reduced-motion:reduce){.u1-build-status button{transition:none}}html[data-u1-motion=reduced] .u1-build-status button,html[data-u1-quality=low] .u1-build-status button{transition:none}'
  ].join('\n');
  function register(root) {
    if (!root || !root.document || !root.U1CoreViews || typeof root.U1CoreViews.register !== 'function') return false;
    if (registered.has(root)) return true;
    var doc = root.document;
    function supports(route) { return typeof root.U1CoreViews.supports === 'function' && root.U1CoreViews.supports(route); }
    root.U1CoreViews.register('roadmap', function (host) {
      if (!doc.getElementById('u1-build-status-styles')) {
        var style = doc.createElement('style'); style.id = 'u1-build-status-styles'; style.textContent = css; doc.head.appendChild(style);
      }
      host.classList.add('u1-native-workspace', 'u1-build-status');
      host.innerHTML = shell(supports);
      var form = host.querySelector('[data-build-filters]'), query = host.querySelector('[data-build-query]'),
        status = host.querySelector('[data-build-status]'), area = host.querySelector('[data-build-area]'),
        body = host.querySelector('[data-build-rows]'), result = host.querySelector('[data-build-results]');
      function update() {
        var selected = filter(items, { query: query.value, status: status.value, area: area.value });
        body.innerHTML = renderRows(selected, supports);
        result.textContent = 'Showing ' + selected.length + ' of 60 items. This is an item count, not completion.';
      }
      form.addEventListener('submit', function (event) { event.preventDefault(); update(); });
      form.addEventListener('input', update);
      form.addEventListener('change', update);
      form.addEventListener('reset', function (event) { event.preventDefault(); query.value = ''; status.value = 'all'; area.value = 'all'; update(); });
    });
    registered.add(root); return true;
  }
  return Object.freeze({ asOf: asOf, items: items, states: states, sources: sources,
    testEvidence: testEvidence, areas: areas, counts: counts, filter: filter,
    escape: escape, safeRoute: safeRoute, renderRows: renderRows, render: shell, register: register });

});
