# U1 OS: transparent 60-item build status

Handoff snapshot: **2026-09-08**, updated with the latest parent report. All
remaining agent implementation files are reported present. B reports 47 tests;
C reports 35 native AI and 26 image tests, both mocked. E's strict gate reports
289 tests and 32 syntax checks; a separate real-FFmpeg agent test passed.
Native media/OSINT and AI assets/endpoints are wired, and the old iframe fallback is
retired. This tracker records attributed evidence, not full account acceptance,
a final release sign-off, or a claim that all 60 requested items are complete.

**Local implementation means a bounded implementation is reported or documented.
It does not mean full feature acceptance, configured accounts or release readiness.**

## Status vocabulary and current distribution

| State | Items | Meaning |
| --- | ---: | --- |
| Local implementation | 35 | A bounded local implementation is reported or documented. This does not mean full acceptance, account setup or release readiness. |
| Setup required | 4 | The adapter exists, but explicit account, consent or runtime setup is needed before the dependent workflow can be used. |
| Partial | 20 | Some working pieces are known, but the requested scope, integration, coverage or acceptance remains incomplete. |
| In progress | 1 | The responsible workstream is still landing. Final implementation and test evidence have not been supplied. |
| Unverified | 0 | No adequate final implementation or acceptance evidence was supplied for this specific item. |

These categories partition the requested scope. There is deliberately no
completion percentage, completion bar, total-completed counter or inferred
roll-up from test counts.

## Parent wiring

Load the single classic script after `U1CoreViews`:

```html
<script src="/js/u1-build-status.js"></script>
```

It calls `U1CoreViews.register('roadmap', mount)`. The parent owns main
navigation/search integration and can use a normal `data-go="roadmap"` button.
All styles are scoped to `.u1-build-status` and are inserted once from the owned
script. No shared CSS, global grid rules, README, backend or other sidecar is
modified. No old-shell page or iframe is required.

Status, area and text filters operate entirely in memory. Text search covers
item number, title, evidence, source and remaining boundaries. Native quicklinks
use an explicit route allowlist and appear enabled only when
`U1CoreViews.supports(route)` returns true. An unregistered route is shown as
unavailable rather than redirected to an old page. Items can remain marked
local while a native route is unavailable, because documented implementation and
parent routing are distinct evidence.

`window.U1BuildStatus` exposes frozen `items`, `states`, `sources`,
`testEvidence` and `areas`, along with `counts()`, `filter(items, options)`,
`renderRows(items, supports)`, `render(supports)` and `register(window)`.
Registration is idempotent; it can be called explicitly if the script was loaded
before the core. This API has no account, credential, job, release or backup
operation. The tracker performs no fetch, storage, login, CLI or paid API calls.

## Evidence received, not a combined acceptance result

| Suite | Result received | Provenance |
| --- | --- | --- |
| Existing parent suite | 90 tests PASS | Parent-reported; not rerun here |
| Safety | 12 tests PASS | Parent-reported; not rerun here |
| Private backup | 4 tests PASS | Parent-reported; not rerun here |
| ReleaseGuard | 4 tests PASS | Parent-reported; not rerun here |
| Native routing | 3 tests PASS | Parent-reported; not rerun here |
| Connections sidecar | 23 tests PASS | Observed earlier in this task; not rerun here |
| B: local workflows | 47 tests PASS | Parent and new workflow handoff report; not rerun here |
| E: strict gate | 289 tests PASS | Parent-reported strict gate; may include the separately listed suites |
| E: syntax checks | 32 syntax checks PASS | Parent-reported checks; not a test-suite count |
| Separate real FFmpeg agent test | PASS; count not supplied | Parent-reported real synthetic-fixture exports; separate from the strict gate; count not supplied |
| C: native AI | 35 tests PASS | Parent-reported mocked suite; no live CLI/account execution verified |
| C: paid image adapter | 26 tests PASS | Parent-reported mocked suite; no authorisation or live paid request verified |

Counts remain separate: the strict gate can contain the smaller suites, and
syntax checks are not test cases. The real-FFmpeg result is separately reported
without an invented count. The parent owns final source-state attribution and
any rerun needed after later edits. The Roadmap suite validates this catalogue,
its rendering and filters; it does not validate the other feature implementations.

The following sources were used:

- Parent status supplied in the task: safety, encrypted backup, ReleaseGuard,
  native routing and current workstream boundaries.
- [Studio Pro handoff](STUDIO-PRO.md), read once: structured document editing,
  real ReportLab PDFs, signed exact-byte PDFium previews, forms, internal
  navigation, local SVG artwork and ZIP bundles. Its documented implementation
  is not a final parent runtime or UI test result.
- [Mac release handoff](MAC-RELEASE.md), read once: local-wrapper requirements,
  bounded build/release workflow, signing limits and manual acceptance still
  required. No build or GitHub result was inferred from commands in that guide.
- Native Connections/Settings code and 23 passing fixture tests observed earlier
  in this task, plus the earlier inspected native platform boundaries. They were
  not reread or rerun for this sidecar while other agents change shared files.
- [Personal workflow handoff](PERSONAL-WORKFLOWS.md), read once: native Life,
  Income and Research; 47 isolated tests; actual operator-requested threshold
  checks and long-only paper accounting, without a background live service.
- [Native media handoff](MEDIA-RESEARCH.md), read once: local source casebooks,
  bounded real FFmpeg export and its synthetic-fixture test contract. The parent
  reports native media/OSINT wiring and a separate real-FFmpeg test pass.
- C's final handoff reports 35 mocked native AI tests and 26 mocked image tests.
  Native AI includes queued jobs, read-only Codex CLI requests, selected context
  and explicit voice/transcript review. The image adapter is real and uses
  Keychain setup plus official paid gpt-image-1.5 requests; no authorisation or
  live paid call is verified. Parent assets and endpoints are wired.

The parent README owns the existing historical-documents archive link. This
sidecar does not replace, move or rewrite older documents, invent an archive
destination, or edit the README. Use the parent README archive link for earlier
build descriptions.

## The 60 requested items

| # | Requested item | State | Evidence | Remaining boundary | Source |
| ---: | --- | --- | --- | --- | --- |
| 1 | Studio fixes | Partial | Studio Pro documents native structured editing and bounded artifact generation; the parent reports the old iframe fallback retired. | Full cross-workspace visual and interactive Studio acceptance remains separate from the automated gate. | Studio Pro handoff document |
| 2 | Safety validation | Local implementation | The parent reports 12 safety tests passing. | This is reported test evidence for the U1 application safety boundary, not a full security audit or a Mac-wide lock. | Parent handoff |
| 3 | AI Command | Local implementation | Native AI Command queues explicit read-only Codex CLI requests; C reports 35 mocked native AI tests passing. | CLI installation/sign-in and successful live provider execution are not established by mocked tests. | Native AI/image handoff / mocked tests |
| 4 | Navigation/search | Partial | The parent reports native media/OSINT wiring, retirement of the old iframe fallback and three routing tests passing. | Automated routing evidence does not establish every interactive navigation/search flow across the combined workspace. | Parent handoff |
| 5 | Job centre | Local implementation | The native assistant includes queued managed jobs; C reports 35 mocked native AI tests passing and the parent has wired assets/endpoints. | The scope is explicitly managed jobs, not arbitrary Mac processes; live CLI execution and full interactive acceptance remain separate. | Native AI/image handoff / mocked tests |
| 6 | Release process | Partial | The parent reports four ReleaseGuard tests plus a strict gate passing 289 tests and 32 syntax checks. | These local results do not establish a reviewed final source revision, interactive Mac acceptance or a successful GitHub workflow. | Parent handoff |
| 7 | Morning brief | Partial | The known native platform exposes a Daily Command Brief. | Final source coverage and usefulness are not accepted; Google-backed material requires a configured account. | Known native platform boundary |
| 8 | Top 3 priorities | Local implementation | The local workflow implements date-specific Top 3 slots, complete/reopen and links to real tasks; B reports 47 tests passing. | Exactly three active slots are supported per date. This does not automatically choose priorities for the user. | Local workflow handoff / 47 tests |
| 9 | Day planning | Local implementation | The local workflow implements editable dated time blocks, calendar links and overlap rejection. | Blocks are same-day and use the workspace timezone; no automatic rescheduling or remote calendar write is claimed. | Local workflow handoff / 47 tests |
| 10 | Life/business layouts | Local implementation | Native Life, Income and Research views provide separate personal, business and manual-market collections. | The handoff establishes bounded native collections, not full desktop/mobile visual acceptance or external account integration. | Local workflow handoff / 47 tests |
| 11 | Household organiser | Local implementation | Household bills and renewals support due dates, planned amounts, editable recurrence and paid/cancelled notes; B reports 47 tests passing. | Recurrence is an operator-managed plan, without payments, automatic advancement or background reminders. | Local workflow handoff / 47 tests |
| 12 | Wellbeing | Local implementation | The local workflow implements flexible/daily/weekly habits, dated check-ins and undo. | No streak penalties, health advice or medical interpretation is provided; check-in history is bounded. | Local workflow handoff / 47 tests |
| 13 | Visual document editor | Local implementation | Studio Pro documents a local title, brand and ordered-section editor with preview invalidation. | It is a structured document editor, not an arbitrary freeform page-layout canvas; parent integration remains to be accepted. | Studio Pro handoff document |
| 14 | Actual PDF preview | Local implementation | Studio Pro documents page images rendered from the exact returned PDF bytes using PDFium. | The page-image preview needs pypdfium2; signed previews expire on server restart, and parent browser acceptance is pending. | Studio Pro handoff document |
| 15 | Fillable PDF | Local implementation | Studio Pro documents real ReportLab AcroForm response fields and form-preserving PDF output. | PDF-reader support varies; filled reader copies do not update the editable Studio source. | Studio Pro handoff document |
| 16 | Hyperlinked planner | Local implementation | Studio Pro documents internal contents links, bookmarks and section/footer navigation in generated workbooks. | This is bounded section-based navigation, not an arbitrary planner interaction or external-link editor. | Studio Pro handoff document |
| 17 | Course builder | Local implementation | Studio Pro documents operator-authored lessons, activities, quizzes and optional answer notes. | No automatic marking, AI lesson authoring, course hosting or checkout is established. | Studio Pro handoff document |
| 18 | AI images | Setup required | A real official paid gpt-image-1.5 request adapter with Keychain setup is present; C reports 26 mocked image tests passing. | Provider authorisation and a live paid request are not verified. The user must configure credentials and explicitly request billable generation. | Native AI/image handoff / mocked tests |
| 19 | Mockups | Local implementation | Studio Pro documents real local cover and mockup SVG artifacts. | These are SVG cover mockups, not product photography, a 3D renderer or generated company artwork. | Studio Pro handoff document |
| 20 | Brand kit | Partial | Studio Pro documents reusable browser-local brand name, accent and font preferences. | A full brand asset library, font licensing controls and external brand-kit synchronisation are not established. | Studio Pro handoff document |
| 21 | Product ZIP bundle | Local implementation | Studio Pro documents ZIP output containing the PDF, SVG artwork, operator instructions, licence and metadata. | A bundle requires operator-supplied instructions and licence text; it does not publish a product or establish rights. | Studio Pro handoff document |
| 22 | Asset library | Partial | Managed Files provides local asset storage, and Studio Pro documents explicit artifact saves. | Final integrated upload acceptance, richer asset metadata and rights verification remain outside this evidence. | Known native platform boundary |
| 23 | Product catalogue | Local implementation | Product records support status, audience, outcome, version labels and links to actual ready local files. | File binaries remain in managed Files; no storefront, checkout or inventory sync is claimed. | Local workflow handoff / 47 tests |
| 24 | Opportunity inbox | Local implementation | Opportunity records capture hypotheses, dated source evidence, confidence and next research steps. | Validation requires operator evidence; confidence is an assessment, not an automated opportunity or demand guarantee. | Local workflow handoff / 47 tests |
| 25 | Offers | Local implementation | Scoped offers link local contacts, products, delivery projects and contextual notes. | No outgoing customer contact, signatures, payments or external CRM synchronisation is performed. | Local workflow handoff / 47 tests |
| 26 | Pricing worksheet | Local implementation | A Decimal-based worksheet calculates assumed sales, fees, labour, costs, result and break-even. | These are pricing assumptions, not actual sales, guaranteed demand or verified revenue. | Local workflow handoff / 47 tests |
| 27 | Launch board | Local implementation | A product-linked launch board supports Backlog, Doing, Review and Done stages. | The board is operator-managed; moving a card does not publish a product or run a launch. | Local workflow handoff / 47 tests |
| 28 | Actual sales/expenses | Partial | The known native platform includes a local ledger and explicit entry workflow. | Records must come from real user input or verified imports. Live payments, bank feeds and actual sales totals are not established here. | Known native platform boundary |
| 29 | Clients | Local implementation | Local contacts, offers, client projects and notes have linked record lifecycles. | There is no outgoing contact or external CRM sync; parent browser acceptance remains a separate check. | Local workflow handoff / 47 tests |
| 30 | Selected AI context | Local implementation | The delivered native AI workflow uses user-selected context for explicit queued requests; C reports its 35-test mocked suite passing. | Mocked tests do not establish successful live provider execution. No hidden email context or expanded account permissions are assumed. | Native AI/image handoff / mocked tests |
| 31 | Voice | Local implementation | The delivered voice workflow requires explicit input and transcript review before submission; C reports 35 mocked AI tests passing. | Actual microphone/browser permissions and live device acceptance remain separate; there is no always-listening service. | Native AI/image handoff / mocked tests |
| 32 | Action previews | Partial | Known managed operations have explicit confirmations and bounded request bodies. | Confirmation dialogs alone do not establish a consistent preview-before-action workflow for every module. | Parent handoff |
| 33 | Specialist roles | Local implementation | The delivered native AI workstream includes selectable specialist-role context alongside explicit queued requests. | Roles are local request context, not autonomous agents, expanded provider permissions or proof of successful account execution. | Native AI/image handoff / mocked tests |
| 34 | War Room | Partial | The assistant role/collaboration implementation files are now present. | A fully accepted War Room workflow or autonomous multi-agent orchestration has not been established. | Native AI/image handoff / mocked tests |
| 35 | Improvement review | Partial | The existing improvement scanner produces reports for operator review. | It is report-only, not automated self-coding, unattended fixes, autonomous commits or self-deployment. | Parent handoff |
| 36 | Branded connections | Local implementation | The native Connections sidecar provides consistent U1 cards and clear provider wordmarks. | Its 23 fixture tests passed earlier in this task; final parent asset wiring and browser visual acceptance remain separate. | Connections sidecar evidence |
| 37 | Connection health | Local implementation | Connection cards show returned account, permissions and last-success evidence without inventing missing values. | Most providers only save settings. Requested scopes and saved credentials are not verified account health. | Connections sidecar evidence |
| 38 | Google workflow | Setup required | The newer read-only Gmail/Calendar adapter and Keychain workflow exist. | No Google account is configured. Desktop OAuth client setup, consent and a successful explicit sync are still required. | Parent handoff |
| 39 | Provider capability checks | Partial | A read-only capability catalogue separates supported Google actions, API settings and local tool detection. | Most adapters do not expose account checks. CLI paths or app-data directories do not verify sign-in, launch or entitlements. | Connections sidecar evidence |
| 40 | Separate usage dashboard | Local implementation | The known native platform keeps provider usage and allowances separate. | Only supported, returned allowance data is usable; local Claude/Antigravity activity does not establish subscription quota. | Known native platform boundary |
| 41 | Deduplicated 10% alerts | Local implementation | The known platform supports deduplicated ten-percent thresholds for available provider allowance windows. | Alerts depend on fresh supported allowance data and the local server; unavailable provider quotas cannot produce verified thresholds. | Known native platform boundary |
| 42 | Email PDF briefing | Setup required | The Google adapter supports bounded optional PDF imports and local review-briefing sources. | No Google account is configured. PDF import is opt-in and bounded; it is not full mailbox coverage or scanned-document OCR. | Parent handoff |
| 43 | Appointment review | Setup required | The Google adapter supports explicit approval of returned calendar versions into local records. | No Google account is configured. Absent events are not cancellations, and this connector does not edit Google Calendar. | Parent handoff |
| 44 | Social calendar | Local implementation | The local workflow implements dated, channel-specific content drafts and operator-recorded published links. | There is no social login, scheduled posting, automatic publishing or verification that a published link was posted by this app. | Local workflow handoff / 47 tests |
| 45 | Rights-aware media | Partial | Native Media/OSINT provide a local source casebook, attribution and operator rights/verification notes; parent wiring is reported complete. | Operator assessments do not automatically verify legal rights. There are no hidden email sources or unsolicited remote source fetches. | Native media handoff / real FFmpeg pass |
| 46 | Actual clips | Local implementation | Native local FFmpeg clip export is implemented; the parent reports a separate real-FFmpeg agent test passing. | The real test uses synthetic local fixtures. Supported codecs, 25 MiB files, 120-second clips and bounded rendering apply; broad interactive media acceptance is separate. | Native media handoff / real FFmpeg pass |
| 47 | Faceless workflow | Partial | Local script/storyboard/asset/voice/caption planning and rights review can be combined with the native real-FFmpeg tools. | This remains an operator-led workflow, not autonomous narration, generation, distribution or a complete unattended video pipeline. | Local workflow handoff / 47 tests |
| 48 | Market watchlists | Local implementation | Manual watchlists record instrument, currency, thesis, source and timestamped observations. | Observations are operator reviewed; there is no continuous live market feed or automated research agent. | Local workflow handoff / 47 tests |
| 49 | Price alerts | Partial | Actual on-demand threshold evaluation checks reviewed timestamped observations and deduplicates crossings; B reports 47 tests passing. | There is no background live monitor, push-notification delivery or trade trigger. A user must explicitly request each check. | Local workflow handoff / 47 tests |
| 50 | Trading journal | Local implementation | The local trading journal records paper rationale, risk, assumed prices and reviewed closed-entry outcomes. | It is separate from the paper simulator and actual ledger; no brokerage execution or verified investment return is implied. | Local workflow handoff / 47 tests |
| 51 | Paper research | Partial | Actual on-demand paper buys/sells maintain separate accounts, cash, holdings, weighted cost and realised outcomes; threshold checks are explicit. | This is long-only operator-reviewed simulation, not a background live service, automated strategy agent, broker execution or verified backtest. | Local workflow handoff / 47 tests |
| 52 | Lock/Pause/Stop | Local implementation | The parent reports application-lock and explicitly managed pause/resume/stop operations with safety tests passing. | The boundary is U1-managed work, not every Mac process. Confirmation is required and locked-state actions require the passphrase. | Parent handoff |
| 53 | Permission centre | Partial | The parent provides permission information and bounded operations. | This is not a complete granular capability engine or universal policy enforcement across inherited adapters. | Parent handoff |
| 54 | Keychain credentials | Partial | Google and the new AI credential paths use Keychain. | Legacy API-setting fields remain. Do not claim all credentials were migrated or all configuration is encrypted. | Parent handoff |
| 55 | Encrypted backups | Local implementation | The parent reports real AES-GCM copies with scrypt and four private-backup tests passing. | The workflow is bounded to 16 MiB and restores separately without overwriting active data; it is not whole-Mac or unlimited backup. | Parent handoff |
| 56 | Privacy mode | Local implementation | Native Settings applies real masking styles and a persisted screen-sharing preference. | Masks cover documented native/opted-in surfaces, not other apps, unmarked content, downloads or source inspection; this is not encryption. | Connections sidecar evidence |
| 57 | Shared design | Partial | The parent coordinates the shared U1 design and global grid fix; sidecars use the existing visual language. | Cross-workspace desktop/mobile and accessibility acceptance is still pending. | Parent handoff |
| 58 | Purposeful motion/sounds | Partial | Native Settings uses the existing feedback/boot APIs and preserves reduced-motion and engine defaults. | The sidecar tests are stubbed; final playback, motion and accessibility acceptance across every view remain pending. | Connections sidecar evidence |
| 59 | Mac app | Partial | The Mac handoff documents a local wrapper with ownership checks and bounded reconnect behaviour. | It depends on this checkout/runtime, is not notarised, and still needs final native-build and interactive acceptance evidence. | Mac release handoff document |
| 60 | GitHub presentation | In progress | The parent owns the current README, historical-documents archive link and final presentation. | This sidecar changes no README or archive. No push, GitHub CI run, signed release or public deployment is established here. | Parent handoff |

## Constraints that must survive final integration

- Item 35 is report-only improvement review. It is not automated self-coding,
  unattended commits or autonomous deployment.
- Item 53 supplies permission information and bounded operations. It is not a
  complete granular capability or policy engine across inherited adapters.
- Item 54 covers Google and new AI Keychain paths. Legacy API-setting fields
  remain; not all configuration or stored credentials are encrypted.
- Item 55 is parent-owned real AES-GCM encrypted copying with scrypt, bounded
  to 16 MiB, and a separate restore destination without active-data overwrite.
  The tracker implements no encryption and runs no backup or restore.
- Item 52 concerns U1 application access and explicitly managed jobs. Parent
  safety pause/resume/stop actions require confirmation and the passphrase when
  locked; this page does not invoke them or control arbitrary Mac processes.
- Google code exists but no account is configured. Gmail/PDF/appointment
  workflows require Desktop OAuth setup, consent and a successful explicit sync.
  Requested scopes and saved settings never prove granted account access.
- The real AI image adapter is setup-required: Keychain credentials and explicit
  provider authorisation are needed before a billable gpt-image-1.5 request.
  Its 26 tests are mocked; no live paid image request or authorisation is verified.
- Local paper buys/sells perform real on-demand simulation with separate cash,
  holdings, weighted cost and realised outcomes. Reviewed threshold checks
  deduplicate crossings. Neither is a background live monitor, push-alert
  service, automated strategy agent, broker execution or verified backtest.
- Local FFmpeg clips and a source casebook do not prove a complete autonomous
  faceless-video pipeline or legal rights. No hidden email source is assumed.
- The Mac app is a checkout-dependent local wrapper, not a self-contained or
  notarised distribution. Native and interactive acceptance remain separate.
- Private-screen masks, shared design and motion/sound controls still require
  final integrated desktop/mobile and accessibility acceptance.
- The parent owns final README/GitHub presentation and the legacy-doc archive.
  No source push, public deployment or successful GitHub workflow is implied.

## Safe sidecar tests

```sh
node --test tests/test_u1_build_status.cjs
```

The suite checks all 60 IDs and titles, valid states, immutable metadata,
mandatory partial/setup boundaries, filter results, safe HTML rendering, strict
native quicklinks, separately attributed test evidence, documentation parity
and actual native registration/filter handlers with a minimal DOM.

All browser-boundary tests use stubs. No live server, credential, Keychain,
provider account, job, encryption operation, FFmpeg process or paid call is used.
Visual browser acceptance and the parent's final combined evidence remain
outside this sidecar's test result.
