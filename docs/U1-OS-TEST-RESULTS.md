# U1 OS validation record

Date: 2026-09-08.

## Previously completed launcher pass

- Eight launcher unit tests passed.
- Twelve Agent Centre unit tests passed.
- Native app compiled and installed on the Desktop.
- Local readiness endpoint identified the expected installation.
- Browser checks found recursive workspace loading and a hidden-canvas exception.

## Current installation pass

The recursive route has been changed from `/index.html` to `/classic`, with a
nested-frame guard. Gauges now skip hidden or undersized canvases.

New tests cover local draft approval, canonical record persistence, duplicate
approval, ledger precision/currency separation, static PDF structure, event lead
times/deduplication, preference validation, quiet hours and allowance freshness.

### Current execution results

| Check | Result |
| --- | --- |
| Business and PDF unit tests | 13 passed |
| New reminder-window tests | 6 passed |
| Existing autopilot tests | 5 passed, 1 failed |
| Launcher tests | 8 passed |
| Agent Centre tests | 12 passed |
| Platform JavaScript tests | 8 passed |
| JavaScript syntax checks | Passed for platform, core, workspace adapter and canonical shell |
| Launcher shell syntax | Passed |
| Git whitespace check | Passed |
| Native compilation and Desktop installation | Passed; previous Desktop app preserved locally |
| Restart and installation-ownership readiness | Passed |
| Live PDF endpoint | Returned a one-page application/pdf document |
| Local business endpoint | Responded successfully; no QA ledger entries or drafts created |

Aggregate: **52 passed, 1 failed** across the selected 53 unit tests.

The failing existing `test_nearby_event_reminder` assertion expects the message
to equal `Soon`. The new message includes the event date/time after the title.
This compatibility expectation remains unresolved; the existing test was not
silently changed or reported as passing.

### Browser observations

- Projects finished loading through `/classic?u1-frame=1#projects`, without a recursively embedded canonical shell.
- Global search opened and remained closed after dismissal, including restored focus on the header input.
- Control Centre displayed the expected settings and confirmed appearance saving.
- A 390 x 844 viewport reported document width 390, dialog width about 374,
  a single-column settings grid and 23px title text. The viewport was reset.
- Home showed local briefing counts, source-labelled price snapshots, weather,
  system measurements, server event connectivity and available provider usage.
- An unattributed `MutationObserver.observe` exception was captured while an
  embedded workspace was loading. Its origin has not been isolated. No clean
  browser-console claim is made.

Remaining: complete responsive/4K visual acceptance, all embedded dialogs,
native GUI interaction, PDF visual rendering, real account workflows, media
playback and complete accessibility/performance testing. The PDF checks cover
all six template outputs and cross-reference structure, not visual acceptance.

The inherited full suite performs system and outbound actions, so it is not run
as an unrestricted default. Provider login, live trading, paid AI, auto publishing,
macOS login-item approval and notification permission are not exercised by unit
tests. No complete production, security or accessibility audit is claimed.
