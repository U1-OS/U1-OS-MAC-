# Operational acceptance: 2026-09-08

This records the operational additions to the cinematic local rebuild. It is
not a feature-parity certification for the separate Wave 10 tree on `main`.

## Final strict gate

The isolated release runner completed at **2026-09-08 10:08:00 UTC**, exit 0.

| Check | Result |
| --- | --- |
| Total tests and contracts | **516 PASS** |
| Python tests | 414 in 25 explicitly named modules |
| Node contracts | 102 in eight explicitly named suites |
| Syntax checks | **69 PASS** |
| Failures / errors / skips | 0 / 0 / 0 |
| Missing required modules | 0 |

Command: `bash scripts/check-personal-release.sh --require-all --report /private/tmp/u1-personal-release-sidecar-20260908-r6.json`.

The report is local evidence. See [Mac release notes](MAC-RELEASE.md) for the
explicit allowlists, process isolation and dated r5/r6 history. r6 supersedes r5
for this source state without erasing the earlier report.

The five new regressions after r5 cover the Spotify OAuth-publication race and
the late-created Control Centre label. Spotify now has 29 mocked tests,
operational polish 16 Node tests, operational Safety 40 tests, and operational
navigation nine contracts. This is bounded fixture coverage, not comprehensive
concurrency verification or real-account authorization.

The synthetic FFmpeg test is explicitly **OPT-IN NOT_RUN** in this gate, not a
hidden skip or part of its passing count. A separate media acceptance run in
this work session reported successful real synthetic MP4/WAV rendering and
decoding. User-selected playback in the actual application remains pending.

## Browser acceptance

The parent checked the restarted application at `http://127.0.0.1:8788/`.

- Home, Start my day, Tech & Gaming and Sports & News opened inside the native
  shell, without an iframe handoff or horizontal overflow in checked desktop views.
- The Codex widget displayed the general account bucket as **used percent**;
  unavailable Claude and Antigravity quotas remained `--`.
- The daily workflow showed actual empty local priorities/tasks with source
  timestamps rather than fabricated sample records.
- BBC technology and Guardian AFL headline snapshots returned with publisher,
  fetch and publication labels. Sports coverage is headlines, **not live scores**.
- Global search reached the grouped OSINT inventory. Its direct hash survived
  reload and rendered the inventory rather than a legacy fallback.
- Spotify, activation, OSINT inventory and source intake were checked at
  390 x 844 without horizontal overflow.
- Mobile accessibility exposed the Control Centre name exactly as
  `Control Centre`; the label persisted through the checked navigation.
- The Spotify widget cleared the utility shelf by 12 px on mobile and 12.5 px
  at 1440 x 1000. Usage and local-media controls remained separate.
- The final inspected browser error log was empty. This is a bounded observation,
  not a guarantee that every route or runtime path is error-free.

Actual 1440 x 1000 captures, taken after the layout correction:

![Operational Home](previews/operational-home-20260908.png)

![Operational Discovery](previews/operational-discovery-20260908.png)

The screenshots contain real observed UI states, not populated demo accounts.
The browser was returned to Home and its original viewport mode afterwards.

## Desktop and provider boundaries

The previously checked wrapper was installed at `~/Desktop/U1 OS.app` and
launched successfully. The replaced Desktop app was preserved in a timestamped
backup. It remains checkout-dependent and ad-hoc signed, not notarised. Native
visual, sleep/wake and end-user interaction acceptance remain pending. r6 did
not rebuild or reinstall the wrapper.

The Spotify native Keychain helper compiled and linked with the installed
`xcrun swiftc`, exit 0, in temporary storage. It was not executed; no Keychain
read/write, OAuth, provider request or account configuration occurred in that
check. Actual Client ID setup, consent and playback verification remain with
the operator. Auto-checking is off by default.

The safety rehearsal used isolated temporary state. No real lock was armed,
password configured, connection disabled or running user job cancelled. The
new central notification cancels Spotify work outside the Safety mutex; it
does not change assistant access-lock versus explicit pause/cancel semantics.

Canva remains unfinished. Direct platform downloading and watermark removal
are unavailable; Source intake provides reviewed links, provenance export and
local-original handoff. The OSINT inventory does not install or launch tools,
check their running services, or start investigations.

## Publication

The operator selected a **replacement pull request**, not an automatic merge.
Both histories are preserved and the review tree is the checked rebuild.
`main`, public deployment and account activation require separate acceptance.
Read [the replacement reviewer guide](REPLACEMENT-REVIEW.md) before merging.
