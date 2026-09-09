# U1 OS: the next 60 improvements

Planning document, 2026-09-08. These are proposed follow-up work, not claims of
implemented features, working integrations, future income or complete security.
The immediate audit repairs and rounded-interface changes are tracked separately
in the dated audit report. Each item should have an explicit acceptance check
before it is described as ready.

## 1. Protect the work first

1. Add a recovery dashboard showing the last successful backup, its coverage, and the last separate-folder restore drill.
2. Make all editors revision-aware, with a visible conflict resolver and a recoverable local draft rather than silent last-writer-wins saves.
3. Add an immutable local change journal for important record edits, linking the actor, source, previous version and undo eligibility.
4. Offer an encrypted research vault and redacted exports, with documented key recovery and no implication that ordinary local databases are encrypted.
5. Add a storage inspector for completed files, partial uploads, trash and retained versions, with reviewed cleanup and accurate reclaimed-space estimates.
6. Build a migration rehearsal against a copy of existing data before accepting the proposed replacement of GitHub's separate main implementation.

## 2. Make AI Command dependable

7. Bind every reviewed AI request to an immutable context manifest, including conversation version, attachments, provider and explicit consent.
8. Offer reviewed recovery for older image artifacts whose authorisation record was already pruned, without automatically reauthorising arbitrary PNG files.
9. Add a context-budget inspector showing exactly what will be included, omitted or summarised before a reviewed AI request.
10. Add provider-specific job timelines with measured queue, execution and cancellation states; never present generated timing as live telemetry.
11. Build an agent review queue that proposes patches, shows diffs and evidence, and requires approval before installation, publishing or destructive changes.
12. Add a voice assistant with visible listening state, push-to-talk, text fallback, editable transcripts and separate confirmation for consequential actions.

## 3. Turn Create into a complete workshop

13. Add a unified asset library with actual file previews, version history, licensing notes and links back to source projects.
14. Offer a template library for planners, courses, workbooks and original printable products, with a complete edit-review-export loop for every template.
15. Add accessible PDF preflight for page overflow, missing fonts, contrast, form labels and final-file integrity.
16. Introduce reusable brand kits with approved logos, colour tokens, typography and preview-safe sample data.
17. Add an explicit image-generation review step showing the selected provider, prompt, output size and billing boundary before sending.
18. Implement Canva handoff through documented capabilities, with clear distinctions between opening Canva, exporting a file and genuinely synchronising an account.

## 4. Help Earn organise real work

19. Link each product to its current verified deliverable, pricing assumptions, launch checklist and operator-entered sales records.
20. Add a client delivery workspace with scoped briefs, milestones, approvals, revisions and downloadable handover bundles.
21. Build a quotes-and-invoices workflow with editable records, payment-status reconciliation and jurisdiction-specific setup left to the operator.
22. Add profitability views that separately label cash received, costs, unpaid invoices and estimates, with traceable source records.
23. Provide a content-to-product planning board, connecting researched demand, original assets, draft offers and reviewed launch tasks without promising revenue.
24. Add a review-only opportunity inbox that ranks saved ideas by operator-defined effort and fit, not fabricated market certainty or automatic spending.

## 5. Connect accounts with clear consent

25. Give every connector a consistent lifecycle: not configured, ready to authorise, authorised, checked, stale, paused, failed and disconnected.
26. Show the exact scopes and data destinations before each account connection, with a readable record of what was accepted.
27. Add per-provider sync controls, last-success timestamps, next-check timing and an explicit offline queue that cannot silently resume after a lock.
28. Build a connector health panel with actionable error categories and safe diagnostics that omit tokens, message content and private paths.
29. Make disconnect distinguish local credential removal, cancelled in-flight work and independently confirmed provider-side grant revocation.
30. Add fixture-based contract suites for every supported provider; retain account-based acceptance as a separate, explicitly approved check.

## 6. Improve usage, alerts and daily flow

31. Show separate provider and model allowance windows, reset times, timestamps and unknown states rather than presenting subscriptions as one combined limit.
32. Add deduplicated 10-percent usage alerts keyed by provider, limit window and reset epoch, with quiet hours and a local alert history.
33. Build a permission-aware notification centre with source links, acknowledgement, snooze and severity that does not depend on flashing colour.
34. Offer an email briefing review inbox that extracts proposed appointments and PDF summaries without immediately modifying the calendar.
35. Add approved appointment reminders at three days, one day and eight hours, accounting for timezone, cancellations and changed event versions.
36. Make Start My Day combine the operator's selected priorities, real calendar records and unfinished work with clear source timestamps.

## 7. Make Media and research trustworthy

37. Add resumable, cancellable imports with accurate reserved and retained storage, explicit expiry and recoverable partial-upload status.
38. Carry source-bound media consent through saved, resumed and multi-provider editing sessions, with a visible source-change history.
39. Add bounded export jobs with measured progress, cancellation, resource limits and final stream validation before offering a download.
40. Build a non-destructive timeline with waveform previews, keyboard trimming, precise subtitles and a reviewable export range.
41. Consider a separately approved provider downloader only for authorised content, using tested URL, DNS, redirect and egress controls while preserving creator marks.
42. Add research provenance, purpose, retention and redaction controls; do not infer hidden emails, collect private personal details or represent repository presence as a working OSINT integration.

## 8. Make live information honest

43. Add a source-status strip that distinguishes fresh, cached, delayed, unavailable and offline data across weather, news, markets and sports.
44. Integrate an authorised live-score source with event IDs, competition coverage, timezone-correct fixtures and explicit delay labels; headlines are not scores.
45. Add a configurable moving ticker with pause, keyboard access, reduced-motion support and category-specific freshness limits.
46. Build a market-session calendar using explicit exchange calendars, holiday exceptions and the operator's timezone rather than generic open/closed timers.
47. Separate market research, paper trading and live account connections visually and operationally, with no automatic order routing from an AI suggestion.
48. Add alert provenance so a major warning shows its source, observed time, expiry and acknowledgement history instead of an unexplained flashing banner.

## 9. Finish the Mac experience

49. Embed source revision and build identity in the native app, then display the exact installed and running versions in the updater.
50. Add signed release manifests and guarded update/rollback flows that preserve the last launchable bundle when installation is interrupted.
51. Rehearse startup after an unclean exit, a locked restart, sleep/wake and an unavailable local service using isolated fixtures and a separate native acceptance pass.
52. Package the supported runtime deliberately and document architecture support, signing and notarisation instead of treating a checkout-dependent wrapper as a standalone installer.
53. Add a first-run assistant for permissions, storage location, backup setup and optional accounts, with working skip and offline paths.
54. Build an exportable support bundle containing redacted configuration and errors, never credentials or private records by default.

## 10. Polish consistently and prove it

55. Extend the rounded themes through every legacy and native workspace using shared semantic tokens, not another stack of conflicting overrides.
56. Add a widget-layout editor with reversible arrangements, useful size limits, saved preferences and a reset that does not delete workspace data.
57. Introduce an accessible motion budget: restrained transitions, reduced motion, no rapidly flashing warnings and no animation that obscures status.
58. Complete the audio language with separately previewable startup, success, warning and error cues that obey one master mute and volume control.
59. Maintain a route-by-route keyboard, screen-reader, mobile and contrast acceptance matrix, including dialogs, reentry, drafts and locked states.
60. Publish each release with dated test evidence, authentic privacy-reviewed screenshots, explicit setup gaps and a reviewed pull request rather than a silent replacement of main.

## Suggested sequence

Finish confirmed security, consent and data-integrity repairs first. Then complete
the rounded Create/Earn workflows and their acceptance checks. Follow with
recovery, integration lifecycle and daily-flow work. Add live providers only after
their authentication, consent, freshness and failure paths are implemented.
Monetisation experiments and autonomous recommendations belong after reliable
storage and reviewed publishing, not ahead of them.

Each proposed item should name an owner, a bounded scope, an isolated regression
test, any account setup required, and the evidence needed for user acceptance.
