# Operational upgrade

Status recorded on **2026-09-08** from component handoffs and the linked local
documentation. This guide describes the proposed replacement build. It is not a
new full-release validation report, an account-connection audit, or proof of
feature parity with `main`. **Final post-fix gate r6 passed at
`2026-09-08T10:08:00Z`.** The completed
[dated acceptance report](OPERATIONAL-ACCEPTANCE-20260908.md) records the actual
gate, browser and installation evidence and their separate boundaries.

## Replacement review comes before changing main

The chosen path is a replacement pull request, not an attempt to reconcile and
merge every feature from the separate implementation on `main`. Opening the PR
does not replace `main`. An explicit review and approved merge are required;
deployment is a separate decision.

Review the complete proposed tree, including removals and workflows that may need
migration. **Not all functionality from `main` has been proven migrated.** Do not
infer parity from the new navigation, screenshots, local records or a previous
passing gate. This documentation pass performs no Git, merge, deployment or
browser actions.

The [replacement reviewer guide](REPLACEMENT-REVIEW.md) records the strategy and
review boundaries. Preserve real configuration, vault contents, databases,
exports and backups separately; they are not repository-release artifacts.

## What is ready, and what that means

| Area | Operational feature | Acceptance boundary |
| --- | --- | --- |
| [Daily flow](DAILY-FLOW.md) | A Home entry and guided review of saved priorities, open tasks and local calendar data, with links to existing editors and review tools. | Preserves operator priority positions. No automatic ranking, record creation, email inference or account sync. Source failures and date/timezone boundaries remain visible. |
| [Studio to products](STUDIO-PRO.md) | Edit original workbook/course content, review the generated PDF, save a PDF or ZIP to managed Files, then explicitly approve a personal product record and optional launch checklist. | Uses the actual ready file ID, artifact version and checksum. New products enter Review and approved launch tasks enter Backlog. Repeated handoffs avoid duplicates. No automatic publication. |
| [Personal records](PERSONAL-WORKFLOWS.md) | Local product versions, launch tasks, offers and client-work records. | Operator-entered planning and actual records remain distinct from estimates, external account activity and completed sales. |
| [Usage widget](USAGE-WIDGET.md) | Explicit selection of the general Codex usage bucket, separate from model buckets such as Spark. | Used percent is not remaining percent. Unknown or stale readings stay unavailable. Separate providers' subscription allowances are not combined. |
| [Safety rehearsal](SAFETY-REHEARSAL.md) | A reported component test result supports the documented application safety controls. | Application lock, managed-job pause and cancellation have separate coverage. This is not a system security audit or proof that external applications stop. |
| [Desktop tools](OSINT-TOOLS.md) | Native, bounded inventory with repository and Desktop mapping evidence. | Discovery only. No integrated tool launching, private-person search, automatic scan or runtime-health acceptance is claimed. |
| [Source intake](MEDIA-DOWNLOADS.md) | Supported source-URL validation, explicit rights/public-source confirmations, JSON provenance export and handoff to authorised local originals. | No direct downloads, remote media fetch, independent rights verification, watermark stripping or guaranteed output quality. |

The ready local workflows above do not establish live external-provider access.
Account-specific operations still require the appropriate setup, permissions,
operator consent and successful acceptance for that account.

## Studio handoff is a private record operation

The creation path is:

1. Supply the product's original content, title, brand settings and version.
2. Generate and review the actual PDF; export a PDF or bundle as needed.
3. Explicitly save it to managed Files and receive a completed `ready` result.
4. Review the saved artifact's identity and the proposed catalogue details.
5. Approve the private product record and only the optional checklist tasks wanted.

The record links to the saved file and version. Catalogue conflicts, archived
matches and partial checklist failures are surfaced for review or safe retry.
Editing the draft invalidates the previous handoff review. A record in Review or
a task in Backlog is not a public listing, a scheduled post, a sale or payment.

The [Studio guide](STUDIO-PRO.md) documents receipt expiry, duplicate checks,
request limits and the existing personal-record integration. It also distinguishes
original local SVG artwork from unconnected AI-image or Canva capabilities.

## Desktop tools: the actual inventory

The 2026-09-08 inventory reports **eight repository candidates**, with:

- **Five matching Desktop bundles present:** DFW1N OSINT, Maigret, Osiris AI, Sherlock and SpiderFoot.
- **Two former Desktop bundles missing:** God's Eye View and Holehe. Their repositories are present.
- **Ponytail:** the eighth repository is a developer helper/plugin, without a corresponding Desktop OSINT launcher.

This is not eight working Desktop OSINT applications. Installed U1 OS and TikTok
LIVE Studio bundles do not substitute for the missing tools. Configured localhost
addresses are metadata, not verified running services. Runtime readiness,
dependency health, port ownership and external-data access were not established
by inventory discovery. Exact mappings and limitations remain in
[OSINT tools](OSINT-TOOLS.md).

## Direct media downloading is UNAVAILABLE

The Source intake feature accepts a supported direct-post URL, checks its format,
records the operator's explicit confirmations and can export a JSON review with
source attribution. That JSON is provenance, not downloaded media. Existing local
originals remain the practical route into Media Studio.

No claim is made that the intake feature downloads YouTube, Instagram or TikTok
media, verifies a remote post's availability, independently establishes ownership,
or removes watermarks. It does not strip, obscure or inpaint creator/platform
watermarks. Adding a downloader dependency later would not by itself enable a
working, accepted download capability. The executor and its boundaries would
require their own implementation and validation.

Read [Media intake and download boundaries](MEDIA-DOWNLOADS.md) for the supported
URL shapes, explicit unavailable state, provenance format and local-original flow.

## Implemented components, setup and coverage boundaries

| Workstream | Status at this handoff | Evidence still needed |
| --- | --- | --- |
| C: Spotify | **Implemented but unactivated / setup needed.** Official PKCE, a Keychain-helper adapter, a native Spotify view and a persistent widget are reported implemented; native helper compilation passed and browser layout was accepted. | User setup and consent, the explicit first account check, and live helper/account runtime acceptance. Compilation, browser layout and mocked tests do not prove a connected account, playback or live widget data. |
| C: account activation | **Native preflight implemented and fixture-tested.** Setup checks help the operator prepare connections; **Canva remains unfinished**. | Provider-specific activation and successful account acceptance. Native preflight is not proof of authorisation or sync. |
| D: tech/gaming and sports news | **Headline discovery implemented; component, source and browser reports received; final gate r6 passed.** Six fixed RSS feeds, existing news adapters, bounded five-minute caching and timestamps. | Headline coverage does not establish live scores, fixtures, match status, complete sports coverage or continuous freshness. |

### Spotify and activation: implemented is not connected

Spotify remains unactivated until the operator supplies their **public Spotify
Client ID**, configures the redirect in the Spotify dashboard, completes consent
and explicitly requests the first account check. **Automatic checking is off by
default.** Metadata GET requests return cached metadata only; reading the view is
not evidence of a fresh account check or an active connection.

The reported implementation includes official PKCE, the Keychain-helper adapter,
the native Spotify view and its persistent widget. The reported native helper
compile check **passed on 2026-09-08**: the installed `xcrun swiftc` toolchain exited
`0` and linked a temporary binary. The binary was not executed; no Keychain,
OAuth or account access occurred, and temporary artifacts were cleaned up.
Nonfatal file-event/cache-fallback diagnostics were reported. This is compile-only
evidence, not runtime or real-authorisation acceptance. Mocked Spotify and
activation tests establish component behaviour, not live account authorisation
or playback. Activation's native preflight does not make the unfinished Canva
integration connected or complete.

See [Spotify](SPOTIFY.md) and [Account activation](ACCOUNT-ACTIVATION.md) for setup
and permissions. The general [Connections guide](CONNECTIONS.md) distinguishes
installed software, configuration, authorisation and successful sync.

### Discovery: dated headlines, not a live sports service

The reported sources are:

- **Tech & Gaming:** official PlayStation and Xbox RSS.
- **Sports & News:** Guardian AFL, cricket, boxing and UFC RSS, plus existing news adapters.

The six fixed feeds were reported to return **HTTP 200 with valid RSS on
2026-09-08**. Discovery uses a bounded **five-minute cache** and timestamps.
Successful source observations on that date do not guarantee that every later
request is current, available or complete.

Sports output is **headlines only, not live scores, fixtures or match status**.
UFC coverage is a subset and must not be described as all MMA coverage. The
component report also records the observer-guard fix and the focused results in
the evidence table below. See [Discovery Hub](DISCOVERY-HUB.md) for source and
coverage details.

C and D's component reports are recorded and **integration wiring is complete**.
Spotify's widget-layout and OAuth-publication-race fixes are reported complete;
the accepted browser recaptures follow the fixes. The latest Spotify component
report records 29 mocked tests passing. This does not establish real OAuth
authorisation. Final post-fix gate r6 passed at `2026-09-08T10:08:00Z`; its exact
result is recorded below and in the completed acceptance report.

## Browser screenshots and Mac acceptance

Ad-hoc checks of the installed Desktop app have been reported. **Native visual
acceptance is still pending.** An installed wrapper and an ad-hoc signature do not
establish notarisation, independent packaging, successful app launch, correct
native rendering or live provider access. Follow [Mac release](MAC-RELEASE.md) for
the launcher/runtime and packaging boundaries.

The actual [operational Home](previews/operational-home-20260908.png) and
[operational Discovery](previews/operational-discovery-20260908.png) browser
screenshots were recaptured and accepted on **2026-09-08**, after the widget-layout
and mobile-label fixes. Both are **1440 x 1000** and are embedded in the README.
Earlier development screenshots remain available in its expandable section.

The parent reports the following browser acceptance:

- **Desktop, 1440px wide:** Home, daily flow and Discovery accepted without overflow, including Tech & Gaming and Sports views with real BBC/Guardian feeds.
- **Mobile, 390 x 844:** Spotify, activation, OSINT and Source intake accepted without horizontal overflow.
- **Navigation:** direct reload of the native OSINT workspace and global Search verified in the browser.
- **Accessibility:** the mobile Control Centre ARIA label verified.
- **Widget spacing:** Spotify clears the usage widget, with reported gaps of 12px on mobile and 12.5px on desktop.
- **Browser error logs:** `[]` in the reported acceptance session.

These are browser UI and source-display observations. They do **not** establish
live OAuth/account access, media or file playback, or native Mac-app visual
acceptance. A native workspace rendered in the browser is not native Desktop-app
acceptance. The wrapper's native visual acceptance remains pending.

## Dated evidence, not a new combined gate

| Component | Reported evidence dated 2026-09-08 | Scope |
| --- | --- | --- |
| Studio | 24 focused tests passed in the recorded Studio handoff. | Includes reviewed catalogue creation, duplicate avoidance, actual JS upload chunking through fixtures, temporary PRISM storage, and PDF/signature/export checks. No real-account acceptance follows from these fixtures. |
| Daily flow | 16 isolated Node tests and JavaScript syntax check passed in its component guide. | Local-response and DOM fixtures; no real user-data or account writes. |
| Codex usage selection | 15 isolated tests reported for explicit general-bucket selection. | Component regression evidence, not a live account usage snapshot or an overall release total. |
| Safety | Latest component report: 40 safety tests passed. | Separate component evidence; retain the detailed safety/rehearsal coverage limits. Do not add this count to a gate total. |
| Spotify | Latest component report: 29 mocked Spotify tests passed after the race and widget-layout fixes. | PKCE/helper-adapter/view/widget component evidence, not live activation or playback. |
| Spotify native helper | Compile PASS reported: installed `xcrun swiftc` exited `0` and linked a temporary binary; temporary artifacts cleaned up. | No helper execution, Keychain, OAuth or account access. Nonfatal file-event/cache-fallback diagnostics only; runtime and real authorisation remain unverified. |
| Account activation | 10 native-preflight / activation tests reported passed. | These are the reported 10 activation tests, not a second suite to count again. Preflight does not activate accounts; Canva remains unfinished. |
| Discovery | 13 Python tests, including a JavaScript subtest, and 13 polish Node tests reported passed; observer guard fixed. | Separate component reports, not a combined gate total. Headline discovery only; no scores, fixtures or match-status acceptance. |
| Discovery sources | Six fixed feeds reported HTTP 200 with valid RSS; five-minute bounded cache and timestamps implemented. | Dated PlayStation/Xbox and Guardian AFL/cricket/boxing/UFC source observations, not continuous freshness or complete coverage. |
| OSINT inventory | Eight repository candidates, five present and two missing matching Desktop bundles, plus the Ponytail developer helper classification. | Discovery metadata, not tool execution or service health. |
| Installed Mac app | Ad-hoc checks reported; native visual acceptance pending. | Packaging/check evidence is distinct from rendering and real-account acceptance. |
| Gate r5 | Dated PASS reported: 511 tests, comprising 412 Python and 99 Node; 69 syntax checks, 25 Python modules, eight Node suites and zero skips. | Historical gate evidence retained separately from the final post-fix r6 rerun. It is not an r6 result. |
| Final gate r6 | **PASS at `2026-09-08T10:08:00Z`: 516 tests, comprising 414 Python tests across 25 modules and 102 Node tests across eight suites; 69 syntax checks; zero failures, errors, skips or missing items.** | Accepted final post-fix gate. Exact evidence and browser/installation boundaries are recorded in [Operational acceptance](OPERATIONAL-ACCEPTANCE-20260908.md). This does not establish live accounts, media/file playback, native Mac-app visual acceptance or parity with `main`. |
| FFmpeg / separate F evidence | Opt-in FFmpeg gate **NOT RUN**; F separately reported real tests passed. | The separate report does not mean the opt-in gate ran or passed, and is not added to r5's total. |

These are dated handoff reports, including the explicitly labelled historical r5
gate, accepted final r6 gate and separate component checks. They were not rerun
by this documentation-only assignment. Component counts may overlap with gate
suites and must not be added to the reported gate total. Separate F test evidence
is not added to either gate total. Earlier cinematic release-gate and hosted-CI
successes do not automatically cover later operational additions. **Final
post-fix gate r6 passed with the exact result recorded above.**

### Final post-fix acceptance report

The completed [Operational acceptance, 2026-09-08](OPERATIONAL-ACCEPTANCE-20260908.md)
records the accepted exact r6 result, actual screenshots, browser checks,
installation evidence and remaining limitations. The browser screenshots and
checks above are accepted evidence; native Mac-app visual acceptance remains
separate and pending. The dated r5 result is retained rather than relabelled as
r6. [Mac release](MAC-RELEASE.md) also records r6 while preserving r5's history.

Keep the detailed references available:

- [60-item build status](BUILD-STATUS.md) and [personal release validation](PERSONAL-RELEASE-VALIDATION.md).
- [Earlier test results](U1-OS-TEST-RESULTS.md) and [rebuild progress](U1-OS-REBUILD-PROGRESS.md).
- [Safety setup](SAFETY-LOCK.md), [safety rehearsal](SAFETY-REHEARSAL.md) and [private backups](PRIVATE-BACKUPS.md).
- [Architecture](U1-OS-ARCHITECTURE.md), [design system](U1-OS-DESIGN-SYSTEM.md) and [archived technical README](README-ARCHIVE-20260908.md).

The final post-fix operational report and accepted browser captures are available
for replacement review. Native Mac-app visual acceptance remains pending, and the
reviewer must still decide how to handle any `main` workflows that require
migration. Setup-dependent capabilities need their own account acceptance before
being described as connected; Canva remains unfinished. Neither a passing gate
nor this documentation update replaces explicit review and merge approval.
