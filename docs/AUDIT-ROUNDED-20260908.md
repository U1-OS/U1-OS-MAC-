# U1 OS: rounded rebuild and adverse audit

Date: 2026-09-08. Scope: the local U1 OS Mac checkout and its proposed replacement
branch, not a reconciliation of every feature in the separate Wave 10 `main`.
This is an engineering audit and dated acceptance record, not a security
certification or a promise of zero defects.

## Result at a glance

The complete strict R2 report is **PASS**: **805 tests/contracts**, comprising
**570 Python tests in 30 named modules** and **235 Node checks in 17 suites**.
All **116 syntax checks** passed. Required failures, errors, skips and missing
items are all zero. The source was frozen before this run; its report revision
field remains honestly `unrecorded` because publication had not occurred yet.

The audit began with a passing 516-test, 69-syntax-check baseline. Adverse fixtures
then exposed real defects beyond that coverage. The larger final count is not a
claim that all imaginable behaviours, providers or platforms were tested.

## The visible rebuild

- Dedicated native `create` and `earn` hubs, with their own headings, real local product counts, explicit review forms and links to advanced `studio` and `income`.
- Shared rounded shell/widget styling and Orbit, Graphite and Daylight preferences, with spacing, corner and glow controls.
- A native `appearance` workspace reached through Settings, plus consistent global sound preferences.
- A rebuilt, responsive loading screen using actual local readiness. Account access is never inferred from saved configuration.
- Normal startup completes automatically; explicit preview remains open until Enter, Escape or dismissal. Old readiness responses cannot close a newer preview.
- An optional startup tone that obeys master mute/volume. One-off preview is deliberate, does not alter saved audio choices, and does not require an external audio service.
- Compact phone allowance/Media controls and closed Spotify summary. Actual media controls remain available when a file is present.

The existing U1 identity, globe and advanced tools were retained. These changes
are not a claim that every legacy editor has been individually redesigned.

## Confirmed findings and repairs

Priorities describe the reproduced pre-repair behaviour. A targeted fixture PASS
means that reproduction is covered; it is not proof of universal safety.

| Priority | Confirmed defect | Repair and evidence boundary |
| --- | --- | --- |
| P1 | Static path traversal could serve a file outside `static`, even during a lock. | Decoded canonical containment rejects traversal and symlink escapes. Isolated HTTP boundary fixtures passed; no real private files were requested. |
| P1 | Cached private search/ledger content could open above Safety. | Locked opens and hotkeys are refused; private snapshots and late responses are invalidated; suspended dirty forms stay closed/inert. Positive adversarial regressions passed. |
| P1 | Legacy AI execution bypassed the reviewed native queue. | The legacy route fails closed with an actionable native AI Command message. It cannot launch an unmanaged request, even with a legacy confirmed flag. |
| P1 | Google sync/OAuth work could continue or publish across a lock/disconnect. | Per-dispatch Safety checks, epoch-checked commits and bounded outside-mutex cancellation. Unlock alone does not resume Google work. Provider I/O was mocked. |
| P1 | Spotify final credential/state publication could race cancellation. | Final commits recheck cancellation epochs. Provider/Keychain operations were mocked; no live OAuth acceptance is claimed. |
| P1 | A successful backup could exceed the restore member limit; metadata export could silently truncate. | Shared 2,000-file plus two-metadata-member archive limits; complete bounded exports or explicit rejection. A real temporary 2,000-file archive was exported and restored. |
| P1 | Ready file metadata could outlive corrupted bytes, including a Studio handoff. | Pinned no-follow managed-file reads validate type, size and SHA-256 against the exact bytes. Studio checks integrity during review and confirmation. |
| P1 | Studio could lose the last debounced edit or overwrite another tab's draft. | Immediate recovery checkpoints, safe flush, per-host lifecycle preservation and conflict retention. Browser recovery copies remain plaintext and quota-limited. |
| P1/P2 | Mutable notes served as handoff identity; stale reviews could create new checklist work. | Durable origin records replace editable-note identity; new task writes require the reviewed version while completed idempotent retries remain valid. |
| P1/P2 | Legacy failure paths could present seeded prices/social posts, weather or news as current data. | Fail-closed unavailable states replace fabricated fallbacks. This does not establish live availability for those legacy services. |
| P2 | Cancelled/abandoned uploads could reserve a full quota without useful bytes. | Explicit abort, Trash cancellation, idle lease expiry and historical reservation recovery. Partial bytes are retained and charged; no broad file deletion. |
| P2 | Filtered product exports included unrelated paper balances/trades. | Filtered exports exclude unrelated financial records; intentionally unfiltered exports preserve their documented coverage. |
| P2 | Cached route reentry left controls inert or detached, and invalidation could reuse a stale pending GET. | Optional per-host activate/deactivate hooks preserve editor DOM and resume listeners; cache generations reject stale in-flight reads. |
| P2 | AI displayed conversation history could differ from the conversation being sent. | Frontend generation/identity/signature checks and renewed consent bind the displayed review. Full cross-tab backend version pinning remains a follow-up. |
| P2 | A retained generated image became inaccessible after unrelated job pruning. | Authorised retained image jobs stay pinned within existing capacity limits. Previously orphaned files are not automatically reauthorised. |
| P2 | An oversized recent answer could discard all older fitting history. | Bounded message selection continues past non-fitting messages and measures the encoded JSON envelope. Omitted context is still an intentional limit. |
| P2 | Media metadata could spoof duration; exit-zero export could contain no actual frames/samples. | Bounded structured decode evidence replaces diagnostic-text parsing; output is independently decoded and checked before success. Real owned synthetic MP4/WAV cases passed separately. |
| P2 | Media source changes retained stale export identity/rights; tiny clips could create invalid SRT cues. | Source changes invalidate review; failed imports can abort reservations without bypassing Safety. Unrepresentable sub-millisecond SRT ranges reject explicitly. |
| P2 | Failed discovery refreshes hid staleness or discarded the last good result. | Timestamped stale/error states, failure cooldown, correct success-false handling and weather place/provider/timezone/fetch labels. Sports discovery remains headlines, not scores. |
| P2 | XML encoding could evade declaration guards; permanent feed locks could exhaust capacity. | Encoding/declaration checks, fixed destinations, bounded cache/idle-lock eviction and URL dedup. No external-entity file-access exploit is claimed. |
| P2 | Clock rollback prolonged a Safety deadline; orphan launcher locks blocked startup; interrupted promotion could remove the expected app path. | Monotonic-plus-wall expiry, locked restart semantics, kernel-owned launcher locking and catchable-interruption rollback. Power-loss/native GUI acceptance is separate. |
| P1/P2 | A locked Mac wrapper could not reach the unlock shell through a protected health probe. | Minimal `/healthz` identity uses a canonical-root hash, protocol and lock flag without exposing a path or token. Native policy checks and temporary compilation passed; Desktop was not replaced. |
| P3 | Detached media players retained listeners. | Changed-only cleanup removes old listeners while preserving connected moves and playback state. |
| P2/P3 | Phone menu clicks hit the backdrop; Daylight retained illegible legacy colours; loading and Safety ownership could conflict. | Same-shell menu backdrop, scoped semantic colour bridges, distinct inert ownership and generation-safe loading. Actual phone hit-testing/navigation and primary-route contrast were checked. |

During repair, the new storage fallback briefly introduced an `ls` reference
outside its defining closure. A fresh browser load caught this before publication.
The fix uses a local guarded read, and a full-file DOMContentLoaded regression
now runs without injected private helpers. The historical `.9` browser error was
retained; no new runtime errors were observed after the corrected `.10` bootstrap.

## Executed release evidence

| Record | Observed result |
| --- | --- |
| Initial expanded run | `2026-09-08T11:34:17.379237+00:00`; 802 run, 46 errors, two skips; all 235 Node checks and 116 syntax checks passed. This run is FAIL, not release acceptance. |
| Cause of the initial gate errors | The runner's audit hook lacked directory-descriptor context for hardened temporary `os.open(..., dir_fd=...)` calls. Its guard incorrectly treated safe fixture opens as workspace-relative. |
| Harness correction | Thread-local descriptor context preserves the actual `dir_fd` and `O_NOFOLLOW` operation and existing allowed roots. Five added regressions cover safe opens, outside/traversal/symlink rejection, exception restoration and thread isolation. |
| Explicit integration exclusions | Three `SyntheticFFmpegTests` methods are separately NOT_RUN in this strict unit gate, not hidden skips or counted passes. Two newly added methods had initially appeared as skips and are now classified explicitly. |
| Final strict R2 report | PASS at `2026-09-08T11:42:22.619604+00:00`; 805 tests/contracts, 116 syntax checks, zero required failures/errors/skips/missing. Wall time 166.27 seconds. |
| Console transport | The outer pipeline returned 1 because sandboxed `tee` could not open `/dev/fd/3`. The complete report and all suite records are PASS; an independent inner exit code was not captured. Full console chunks were retained separately. |
| Separate real-media evidence | 38 tests passed with the real-FFmpeg opt-in enabled, including generated owned video/audio, spoofed-duration rejection, empty/truncated export rejection and valid MP4/WAV decoding. Not added to the 805 total. |
| Native policy/build evidence | 31 policy checks passed and a temporary full Swift executable compiled. No final Desktop replacement, native sleep/wake/menu acceptance, Developer ID signing or notarisation was performed in this audit. |

Local evidence paths, not GitHub upload content:

```text
/private/tmp/u1-massive-audit-20260908-baseline.json
/private/tmp/u1-massive-audit-20260908-final.json
/private/tmp/u1-massive-audit-20260908-final-r2.json
/private/tmp/u1-massive-audit-20260908-final-r2.log
```

The canonical R2 report records `source_revision: unrecorded`, native build and
interactive Mac checks as NOT_RUN, and notarisation as NOT_PERFORMED. The earlier
temporary native compilation above is separate evidence, not a rewritten field
in the unit report. Provider tests used temporary/mocked fixtures; no paid AI,
Keychain, trade, social-posting or real account-authorisation action was performed.

## Actual browser acceptance

The parent used a separate temporary in-app tab, not the user's active tab.
The local server was restarted through its confirmed owned updater action.
Checks used 1440 x 1000 desktop and 390 x 844 phone viewports.

- Fresh corrected startup reaches the requested native route; preview settles actual checks, remains open and returns to Appearance with Enter.
- The phone loading Enter control ended at approximately y=705 inside an 844-pixel viewport; page width remained 390 pixels.
- Create and Earn render a single main workspace heading, real zero catalogue counts and explicit unsaved planning forms.
- A temporary unsaved Create title survived a visit to Earn and return. The form was dismissed without saving a business record.
- Advanced Studio remains in the OS; AI Command and the persistent Media shortcut open native workspaces without sending a provider request.
- Orbit/Graphite/Daylight selection and spacing/corner/glow controls update their rendered preferences. Original quiet audio and 14% volume were restored after the check.
- A deliberate tone preview was accepted by the browser audio engine. Header mute synchronised back to Appearance. This is not a claim of human-confirmed speaker output.
- The phone drawer now hit-tests the actual Create button, opens `#create`, closes the drawer and produces no horizontal overflow.
- The compact phone allowance shelf measured 60 pixels and the closed Spotify widget approximately 54.84 pixels. The Media button retained its descriptive accessible label.
- Corrected Daylight AI/Media headings rendered `rgb(23,43,46)` and their subtitles `rgb(77,100,103)`. The shared declared palette passed 30 text-pair checks with a minimum ratio of 5.23:1; this is not a whole-UI WCAG certification.

The temporary viewport was reset and audit tab closed. The user's original tab
was not navigated. Six real preview PNGs were captured and visually reviewed:

| Preview | Capture |
| --- | --- |
| Startup, Orbit | [Open](previews/rounded-startup-20260908.png) |
| Home, Orbit | [Open](previews/rounded-home-20260908.png) |
| Create, Orbit | [Open](previews/rounded-create-20260908.png) |
| Earn, Orbit | [Open](previews/rounded-earn-20260908.png) |
| Appearance, Daylight | [Open](previews/rounded-appearance-20260908.png) |
| Phone, Orbit | [Open](previews/rounded-phone-20260908.png) |

## Remaining boundaries and follow-up

- Full native keyboard/screen-reader, sleep/wake, login-item, installed-app and rollback acceptance is not complete. Browser DOM-bridge focus inspection is not equivalent to native keyboard testing.
- Some legacy editors retain dark palettes in Daylight. A secondary empty-player hint still needs a light-theme contrast follow-up; the full route-by-route accessibility matrix is not complete.
- Actual user-selected browser media playback and real provider/Keychain activation were not exercised. Direct remote downloading, watermark removal and integrated OSINT execution remain unavailable, not silently enabled.
- Generic cross-client create idempotency and backend conversation-version pinning remain follow-up work. Frontend duplicate/consent guards are not substitutes for those server contracts.
- Old Studio origins already removed from legacy notes and images orphaned before retention repair require explicit recovery/reassociation, not guessed authorisation.
- Browser draft recovery remains plaintext, local and quota-limited. It is not included in ordinary managed-file backups. Cancelled partial uploads remain on disk and are disclosed as excluded from backups.
- Safety is an application access lock, not disk encryption, a firewall or an exchange-order kill switch. Lock, managed-job pause and cancellation remain distinct.
- No claim is made that every feature from the separate `main` implementation has migrated. The existing replacement PR preserves both histories; `main` is not merged or rewritten by this audit.

See [the next 60 proposals](NEXT-60-IMPROVEMENTS.md) for a prioritised roadmap.
Source publication includes code, documentation and reviewed previews, not live
databases, runtime environments, credentials, exports, app bundles or temporary
audit logs. GitHub workflow execution after publication is a separate result.
