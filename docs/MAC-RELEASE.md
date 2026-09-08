# Mac desktop and personal release contract

The desktop application is a local wrapper around the canonical workspace at
`http://127.0.0.1:8788/`. It requires this checkout, `start-u1-os.command`, and the
existing `.runtime/bin/python3` environment. It is not self-contained. Old shell
redirects belong to the parent's shared bridge; this app does not launch them.
The minimum deployment target is macOS 12; login controls require macOS 13 or later.
No Developer ID certificate is supplied or used. Ad-hoc signature integrity is
not notarisation, Gatekeeper approval, or proof of a trusted publisher.

## Desktop behaviour

- Check the minimal `/healthz` identity before loading the workspace: service
  `u1-os`, protocol `1`, a SHA-256 `installation_id` of the canonical workspace
  root, and a boolean `locked` flag. This works while protected APIs are locked,
  without returning a root path, credential, CSRF token or an unlock exemption.
  Canonical paths accept the same installation through a symlink. Health requests
  use an ephemeral session, bypass proxies and do not follow redirects.
- Connect to an already running workspace first. On connection failure invoke the
  existing launcher once per connection attempt. Its port and launch-lock guards
  remain authoritative. Never terminate another app or delete its lock.
- Retry up to 40 health requests, with two-second request and three-second resource
  timeouts. Failure shows a recoverable status page. Healthy sessions are checked
  every 20 seconds without reloading the page.
- Sleep cancels checks. Wake and focus reconnect without intentionally reloading
  a healthy page. Generation checks discard stale replies. Navigation errors and
  a terminated WebKit content process reload the last completed local URL.
- `View > Reload` checks ownership then reloads; this can discard unsaved edits.
  `View > Reconnect` checks availability without intentionally reloading a healthy
  page. Recovery after an actual WebKit failure can also lose unsaved page state.
- Closing the window keeps the app running. Reopen from the Dock or use
  `Window > Show U1 OS` (`Command-0`). Hide, minimise, remembered geometry and
  full-screen controls are available. `Command-Q` leaves the shared server running
  for browser sessions.
- Only the exact local origin stays inside the app. Local blob exports use a Save
  dialog. External HTTP, HTTPS and mail links need a main-workspace click and
  confirmation in a native dialog. Credential-bearing URLs, executable custom
  schemes, remote frame navigation and unsolicited external popups are rejected.
  These are navigation controls, not a sandbox for all web subresources.
- Login startup remains explicit and can require macOS approval. It depends on the
  installed app and workspace paths. Help menu commands reveal the workspace and
  this release guide in Finder rather than executing shell commands.

## Local build and safe updates

```bash
bash macos/build-desktop.sh
```

The builder uses the existing Xcode SDK and Swift compiler. It installs no tools,
signing identities or dependencies. It runs the native policy checks, compiles the
app and icon, validates the plist and verifies the ad-hoc signature. Work is staged
under `dist` with a build lock. Success promotes `dist/U1 OS.app`, preserving any
previous local build as a uniquely named sibling backup. Failed builds leave the
previous app intact. Promotion errors attempt rollback. A power loss between
renames may require manually restoring the backup; backups are never auto-pruned.

`macos/install-u1.sh` delegates to that builder and only builds without arguments.
The explicit `--with-personal-deps` option first runs `macos/bootstrap-personal.sh`
to install `requirements-personal.txt` into the existing virtual environment. The
bootstrap refuses system Python, uses binary wheels, and creates no new runtime.
It includes `requirements-prism.txt` through the parent's requirements file.
Ordinary builds and checks do not install packages or require this option when
the runtime is already provisioned.
A first Desktop installation requires `--install`. Replacing an existing Desktop
app requires both flags below, after explicit user authorisation and review of
the build. Quit the old wrapper before performing an authorised replacement:

```bash
bash macos/install-u1.sh --install --replace-desktop
```

The installer verifies a staged copy, rejects symlinked destinations and unrelated
bundle identifiers, and preserves a unique Desktop backup before promotion.
To install an already-built and reviewed app without rebuilding it, the user can
quit the old wrapper with Command-Q and explicitly run this from the workspace:

```bash
/usr/bin/python3 -B macos/release_support.py install \
  "$PWD/dist/U1 OS.app" "$HOME/Desktop" --replace-desktop
```

For a first installation, omit `--replace-desktop`; an existing destination will
then be refused. Replacement preserves the old Desktop app as
`$HOME/Desktop/U1 OS.backup-<UTC timestamp>-<8-character unique suffix>.app`.
The helper verifies the staged copy's signature before promotion and attempts to
restore the backup if promotion raises an error. It does not prune backups or
roll back workspace data. This command is provided for the user's explicit use;
the sidecar agent does not execute it or modify files outside the workspace.
This documentation does not authorise an agent to run that command. Implementing
the sidecar requires no Desktop replacement. Restoring an older wrapper does not
roll back workspace source or databases; assess their compatibility separately.

Optional build values: `U1_DESKTOP_VERSION` (default `2.1.0`),
`U1_DESKTOP_BUILD_ID` (default `1`, for example `2609.8.1`), and
`U1_SOURCE_REVISION` (full hexadecimal commit ID). Without a supplied revision the
app records `unrecorded`. The builder does not run Git or infer a clean tree.

## Conservative release gate

```bash
bash scripts/check-personal-release.sh
bash scripts/check-personal-release.sh --require-all --report /tmp/u1-release-evidence.json
```

The runner uses the standard library on Python 3.9 or later and Bash. It prefers
the existing `.runtime/bin/python3`; `U1_RELEASE_PYTHON` overrides that selection.
Private backup tests additionally require the parent's crypto dependency. The
local gate installs nothing. CI installs the parent's `requirements-personal.txt`
and its included `requirements-prism.txt`, using binary wheels, without invoking
inherited dependency/install scripts. The inspected local runtime had Python
3.12.14, reportlab 4.4.9, pypdf 6.10.0, cryptography 48.0.1, Pillow 12.3.0,
imageio-ffmpeg 0.6.0 and psutil 7.2.2. That confirms local availability, not a
completed installation on a GitHub runner.
Report paths must not already exist. Reports contain only timestamps, validated
revision IDs, relative source names, statuses and counts. A Python-only report
explicitly labels native build and interactive Mac checks `NOT_RUN`.

The original sidecar modules under `tests/` are shown below as historical
context. The current authoritative explicit allowlist is in
`macos/release_checks.py`; the [rounded audit record](AUDIT-ROUNDED-20260908.md)
records the expanded 30-module, 17-Node-suite acceptance result.

```text
test_u1_business          test_u1_reliability      test_u1_autopilot
test_u1_reminders         test_u1_launcher         test_u1_agent_centre
test_updater              test_integrations_hub    test_u1_studio_pro
test_u1_personal_core     test_u1_assistant        test_u1_safety
test_u1_private_backup    test_u1_release_guard    test_u1_native_routes
test_u1_media_research    test_u1_image_provider   test_u1_macos_release
```

Each present file loads explicitly in its own interpreter with a 90-second limit.
The runner never discovers the inherited suite or imports `tests/__init__.py`.
An existing file that fails to import fails the gate.
The image-provider suite explicitly imports `tests/test_u1_assistant.py` as its
fixture dependency; those assistant tests are not run twice. The runner does not
add the entire tests directory to the import path. Native credential operations
and provider requests remain mocked in the image-provider unit suite.

Workers start with a cleared environment and temporary home, cache, data and temp
directories. A Python audit guard rejects real subprocess/Keychain access,
network connections/listeners, writes outside fixtures and reads of runtime data,
databases and common credential paths. Tests must mock those effects. The guard
is a regression tripwire for trusted tests, not an OS boundary against hostile
Python or native extensions. Unmocked access fails rather than using live data.

The reviewed Studio JavaScript contract is an explicit subprocess exception.
It runs Node 26 or later with `--permission`, read access to exactly
`static/js/u1-studio-pro.js`, a cleared environment and a temporary working
directory. No write, network, child-process, native-addon or worker permission is
granted. CI selects Node 26.8.1, matching the inspected local executable, and
disables package-manager caching. See the official
[Node permission model](https://nodejs.org/api/permissions.html). No npm install
or inherited JavaScript test suite is invoked. Four further explicit suites,
`tests/test_u1_connections.cjs`, `tests/test_u1_media.mjs` and
`tests/test_u1_shell_navigation.cjs`, plus `tests/test_u1_build_status.cjs`, run directly under
Node with permission to read only their named fixture/source dependencies. The
gate stages only those explicit files into each suite's temporary directory,
preserving relative source paths without granting access to the whole checkout.
It records TAP counts for the connections/media/build-status suites. The build
tracker also receives its exact `docs/BUILD-STATUS.md` fixture; Markdown and CSS
fixtures are read as data and are not submitted to the JavaScript syntax checker.
Shell navigation requires
exit code zero and the exact `PASS 6 native registration and direct-entry contracts`
marker; missing, altered or contradictory output fails the gate. All named
JavaScript files receive syntax checks.

The three explicitly named `SyntheticFFmpegTests` integration methods, including
`test_generated_owned_video_exports_real_mp4_and_wav`, are excluded from the unit
gate and reported separately as `OPT-IN NOT_RUN`. Real FFmpeg processes require a
separate deliberately opted-in run. These exclusions do not waive any other
skipped test or count a real integration as passed. The parent records a separate
38-test opted-in synthetic-media run in the rounded audit; the strict gate does
not reassert that separate run as its own evidence.
The existing runtime also contains `pypdfium2 5.13.0` for Studio PDF previews;
the parent confirmed its matching pin in `requirements-personal.txt`. Dependency
installation follows that requirements file.

Syntax checks cover the selected tests, the two sidecar Python helpers, and
`utils/u1_studio_pro.py`, `utils/u1_personal_core.py` and `utils/u1_assistant.py`.
They also cover `utils/u1_credentials.py` and `utils/u1_image_provider.py`.
`static/js/u1-image-provider.js` receives an explicit Node syntax check, separately
from the executable connections and media JavaScript suites. Syntax validation
does not establish interactive image UI or real provider acceptance.
Bash syntax checks cover this gate, the build/install scripts and optional
personal bootstrap. The workflow uses
JSON-form YAML so it can be parsed without a third-party YAML dependency. Unit
tests check triggers, immutable action references, permissions and the exact
artifact path. Native Swift behaviour is exercised by the Mac builder separately.

While parent agents create modules, missing files are listed as `PARTIAL`; the
default development command may exit zero for a partial run. Failures always
exit nonzero. `--require-all` rejects missing modules or listed Python source files,
skipped tests and zero-test modules. CI uses strict mode. The parent must rerun
strict mode after every module lands. A partial run is not complete acceptance
of the 60-item build.

## GitHub on each source update

The workflow runs on every push, pull request and manual dispatch with only
`contents: read`, no persisted checkout credentials, bounded jobs and cancellation
of superseded runs on the same ref. The Linux job runs the complete named gate.
Only after it succeeds does the Mac job build the wrapper.

After both jobs succeed on a push, the workflow can upload exactly this guide as
a seven-day documentation artifact. Pull requests do not upload it. Sanitised
test evidence and separate Mac build evidence appear in job summaries. No app,
source archive, database, runtime, log, environment file or credential is uploaded.
The app is not uploaded because it embeds a machine-local workspace path.

There is no Pages change, public deployment, automatic Release, source-write
permission, Git add/commit/push or unattended source synchronisation. The parent
must review and explicitly push intended source updates; CI checks them once on
GitHub. A cancelled superseded run is not a pass. Local execution does not prove
that the GitHub workflow has run.

Official action references, pinned to these verified release commits (not a claim
that these are the latest available releases):

- [actions/checkout v6.0.2](https://github.com/actions/checkout/releases/tag/v6.0.2):
  `de0fac2e4500dabe0009e67214ff5f5447ce83dd`.
- [actions/setup-python v6.1.0](https://github.com/actions/setup-python/releases/tag/v6.1.0):
  `83679a892e2d95755f2dac6acb0bfd1e9ac5d548`.
- [actions/setup-node v6.0.0](https://github.com/actions/setup-node/releases/tag/v6.0.0):
  `2028fbc5c25fe9cf00d9f06a71cc4710d4507903`.
- [actions/upload-artifact v4.6.2](https://github.com/actions/upload-artifact/releases/tag/v4.6.2):
  `ea165f8d65b6e75b540449e92b4886f43607fa02`.

## Parent changelog and evidence contract

Use these fields in the parent's GitHub presentation/release note. Tie each result
to one reviewed source revision and replace placeholders only with observations:

```text
Release: <version and build ID>
Source: <reviewed commit ID, or uncommitted local checkout>
Changes: <concrete user-visible before/after behaviour>
Personal gate: PASS / PARTIAL / FAIL, timestamp, Python version, command
Tests: <modules present/expected, tests run, failures/errors/skips>
Missing modules: <exact names or none>
Syntax: <specific Python, Bash and workflow results>
Native build: PASS / FAIL / NOT_RUN, macOS version, architecture, SDK/compiler
Native policy checks: <observed count and result>
Signature: ad-hoc integrity PASS / FAIL / NOT_RUN; Developer ID not used
Notarisation: NOT_PERFORMED
Manual desktop: <each acceptance result below, or NOT_RUN>
Installation: local dist only / explicitly installed, backup location if changed
GitHub: <actual workflow URL and commit, or NOT_RUN>
Deployment: unchanged; no public deployment
Limitations: workspace dependency, signing, manual checks, outstanding failures
Rollback: <previous app backup; workspace/data compatibility assessed separately>
```

Suggested changelog scope: ownership-checked reconnect on focus/wake; cancelled
stale requests; WebKit recovery and window/menu controls; explicit external
openers; consolidated staged build/install with backups; isolated named-test
release gate; read-only CI with a documentation-only artifact. This describes
implementation, not evidence that every acceptance item passed.

## Manual acceptance still required

1. Launch with the server stopped, then already running. Confirm canonical root
   startup and correct ownership, using disposable data where needed.
2. Exercise an occupied port or different installation. Confirm the recoverable
   error and that no unrelated process is stopped.
3. Leave a harmless unsaved edit, sleep/wake the Mac and switch focus. Confirm a
   healthy page stays intact and menu controls remain responsive.
4. Restart a disposable server and exercise reconnect, navigation failure and
   WebKit recovery. Confirm the last completed local route is recovered.
5. Close, minimise, reopen from Dock, use Command-0, full screen, Reload and
   Reconnect. Check geometry/focus and that quitting leaves browser sessions usable.
6. Cancel and approve an external-link dialog, try a local export, and confirm
   file/custom schemes and unsolicited external popups fail.
7. Explicitly enable/disable login startup on supported macOS. Inspect approval
   state and confirm a fresh login still finds the workspace.
8. Only if authorised, verify installation refusal without replacement permission,
   a verified replacement, the retained backup and deliberate rollback.

Do not infer interactive acceptance from compilation or unit-test counts. No
Keychain helper is edited, compiled or invoked by this sidecar.

## Observed sidecar evidence: 2026-09-08

The original sidecar's frozen-source `r4` record and the later operational runs
below are preserved history. The newer rounded-rebuild R2 evidence at the end of
this guide supersedes their counts for the current audit, without rewriting them.

Source state: local checkout; no commit or push performed and no source revision
asserted. This observation is dated and does not automatically cover later parent
changes or a future pushed commit.

The first recorded gate run is superseded: the runner incorrectly prefixed the
existing updater and integrations test names with `u1_`. Their actual files are
`tests/test_updater.py` and `tests/test_integrations_hub.py`; no alias fixtures are
needed and this naming mistake is not missing product coverage. The corrected
gate includes those files, the media unit module and both named Node suites.
The corrected strict run is recorded independently below; the erroneous earlier
test-name entries must not be presented as missing coverage.

The local app build passed on macOS 26.7, x86_64, Apple Swift 6.3.2 and SDK 26.5.
The initial sandboxed build compiled Swift but Apple's icon utility failed.
A bounded retry outside that sandbox passed all 23 native policy checks, app and
icon compilation, plist validation, icon assembly and ad-hoc signature integrity.
The resulting app is `dist/U1 OS.app`; the previous local app was preserved as
`dist/U1 OS.backup-20260908T082315Z-cafc9cde.app`. Desktop was not replaced.

Interactive startup, sleep/wake, menus, login-item registration and installation
remain `NOT_RUN`. No Developer ID identity was used, notarisation was not performed,
and no GitHub workflow execution, public deployment or publication was performed.

### Strict gate before image-provider coverage: PASS (superseded)

Command: `bash scripts/check-personal-release.sh --require-all --report /private/tmp/u1-personal-release-sidecar-20260908-final.json`.
Exit status: 0. All 17 named Python modules were present: 257 Python tests passed.
Both named JavaScript suites passed: 23 connections tests and nine media tests.
Total: 289 passing tests, zero failures/errors/skips, with no required test modules
missing. All 32 specified Python, Bash, workflow and JavaScript syntax checks passed.

The corrected existing modules contributed 20 updater and six integrations tests.
Studio contributed 15 tests; personal-core was present and contributed 47 passing
tests in this snapshot. Media research contributed 26 unit tests, and the Mac
release module contributed 21 tests. Subsequent parent changes require a fresh
strict run before reusing this result for a release.

The single synthetic real-FFmpeg test is explicitly `OPT-IN NOT_RUN` in this gate;
it is not included in the 289 passes. Its separately reported parent run is not
claimed as verification performed here. The local evidence file is
`/private/tmp/u1-personal-release-sidecar-20260908-final.json`; CI does not upload it.
The native app build was not rerun for these test-list/runner corrections; its
separate successful build evidence and remaining manual acceptance limits above
still apply. No Git operation or change outside the owned sidecar files was made.
The final rerun includes the landed personal-core and assistant tests. The parent's
separate optional-image report was not required to execute this fixed gate; image
acceptance beyond these named tests remains separate release evidence.

### Expansion history before frozen-source r4

The current gate additionally selects `tests/test_u1_image_provider.py`, syntax
checks the credential/image-provider backends and image JavaScript, and supports
the suite's explicit assistant-fixture import. The parent reports 35 assistant
and 26 image tests passing independently and the image API wired at
`/api/workspace/image-provider`. Those are parent-reported results, not a completed
run of this expanded gate.

At this intermediate handoff, tests and syntax checks were held for the focused
security review, managed-files acceptance fixes and the parent's explicit go-ahead.
The previous 289-test report did not validate the expanded gate or subsequent
fixes. The final rerun after that go-ahead is recorded below.

A subsequently reported three added Studio managed-files acceptance tests (18
Studio tests total) and four native-route tests. The Studio acceptance runner uses
the already permitted `node -e` command and exact Studio script, exchanging only
generated fixtures and replies over inherited stdin/stdout pipes. The Python
worker owns its temporary PRISM database. The Node launch adapter preserves those
pipe options while enforcing the cleared environment, temporary working directory,
closed unrelated file descriptors and membership in the worker's bounded process
group. Node receives no filesystem write, network or child-process permission.
A regression contract for those launch options was added for the final gate.

The parent required the tracker and empty-player fixes before the strict rerun,
followed by one final bounded local build after a passing gate. Desktop installation
and overwriting files outside the workspace were excluded from that build.

The parent also added the six-contract shell-navigation suite for late registry
registration/direct-entry fallback. It is now an explicit Node suite with the
staging and exact-result handling above. The parent held execution for A's contrast
CSS and D's tracker fixes, then issued FINALGATEGO after freezing the other agents.
Prior passing totals did not validate those later changes.

### Final frozen-source r4: gate PASS and local build PASS

The strict gate completed at `2026-09-08T08:54:26Z`, exit 0:

```bash
bash scripts/check-personal-release.sh --require-all \
  --report /private/tmp/u1-personal-release-sidecar-20260908-r4.json
```

| Evidence | Observed result |
| --- | --- |
| Python modules | All 18 present; 290 tests passed |
| Connections Node suite | 23 tests passed |
| Media Node suite | 9 tests passed |
| Shell-navigation Node suite | 6 asserted contracts passed |
| Build-status Node suite | 16 tests passed |
| Combined Python/JavaScript count | 344 passed |
| Failures / errors / skips | 0 / 0 / 0 |
| Required missing modules | None |
| Python, Bash, workflow and JavaScript syntax | All 40 checks passed |
| Real synthetic FFmpeg integration | OPT-IN NOT_RUN; excluded from the 344 passes |

The final Python results include Studio 18, personal-core 47, assistant 35,
image-provider 26, media-research 26, native routes 4, updater 20, integrations 6,
and Mac release contracts 24. Other named modules are listed with individual
counts in the JSON report. Image-provider tests use mocked network and native
credential operations; no live paid request or Keychain operation was performed.

The real Studio helper passed the isolated Python/Node pipe acceptance: a
314,004-byte PDF reached ready state through 10 chunks, and a 54,419-byte ZIP
through two chunks. The PDF had 99 pages and 216 form fields; the signed preview
of downloaded page 96 passed. Both files' metadata appeared in the isolated export.
These were temporary generated fixtures, not live workspace files or a browser
acceptance run.

The first r4 attempt passed its Python tests but failed before the standalone Node
suites because macOS's `/var` temporary-path alias conflicted with exact read
permissions. The guard now canonicalises the staged root, with a regression test.
The failed attempt is preserved separately as
`/private/tmp/u1-personal-release-sidecar-20260908-r4-initial-node-path-failure.json`.
The `r4.json` file contains the subsequent passing full run. No alias test fixtures
or broad filesystem permissions were introduced to bypass the failure.

After the gate passed, exactly one bounded final build ran successfully using the
previously working native build environment. It passed 23 native policy checks,
app/icon compilation, icon assembly, plist validation and ad-hoc signature
integrity. These native checks are separate from the 344 Python/JavaScript passes.
The resulting app is `dist/U1 OS.app`. The prior local app is preserved at
`dist/U1 OS.backup-20260908T085555Z-752078f0.app`.

The build used the observed macOS 26.7 x86_64 / Swift 6.3.2 / SDK 26.5 environment.
No Developer ID certificate was supplied or used; notarisation was not performed.
The app still depends on the local workspace and runtime. Interactive startup,
sleep/wake, login controls, Desktop installation and live provider acceptance
remain NOT_RUN. The JSON report is intentionally gate-only and retains its
separate native-build NOT_RUN field; this section records the subsequent build.
No Git operation, GitHub workflow execution, public deployment or Desktop
replacement was performed. The exact user-authorised installation command and
backup behaviour are documented above.

### Operational release r5: explicit gate PASS, provider race still open

The parent authorised this combined run after Mill's operational wiring report.
On 2026-09-08 at 09:54:08 UTC the following command exited 0:

```bash
cd "/Users/u1/Documents/ChatGPT/U1 OS ( MAC )"
bash scripts/check-personal-release.sh --require-all \
  --report /private/tmp/u1-personal-release-sidecar-20260908-r5.json
```

Evidence: `/private/tmp/u1-personal-release-sidecar-20260908-r5.json`.
The exclusive report writer preserved prior r4 evidence.

- PASS 511 tests/contracts: 412 Python tests in 25 explicitly named modules and
  99 JavaScript contracts in eight explicitly named suites.
- PASS 69 syntax checks; zero failures, errors, skips or missing required tests.
- Studio now reports 24 tests; macOS release contracts report 27 tests.
- Operational Safety reports 40, usage windows 8, OSINT tools 8, media intake 7,
  Discovery 13, Spotify 27, and connection preflight 10 Python tests.
- New standalone Node suites report daily flow 16, usage selection 7, operational
  polish 13 and operational navigation 9. Existing Node suites retain 23
  connections, 9 media, 6 shell navigation and 16 build-status contracts.
- The embedded OSINT and Discovery Node assertions remain part of their Python
  module counts. They run with exact helper-file permissions and no network,
  filesystem write or child-process permission. Studio's pipe acceptance is
  preserved. No broad test discovery or unrestricted Node exception was added.
- Mill's exact embedded routing Python assertions execute separately in a
  disposable, audit-guarded Python process against staged source copies. The
  unchanged Node assertion consumes that actual result through an exact-call,
  single-consumption preload. Node receives no child-process permission. This
  tests the supplied Python assertions, not live server startup or HTTP traffic.
- `SyntheticFFmpegTests.test_generated_owned_video_exports_real_mp4_and_wav`
  remains OPT-IN NOT_RUN. It is neither added to the passing count nor hidden
  among skips.

The new central Safety notification is Spotify-only and is delivered outside
Safety's mutex. It does not change assistant access-lock versus explicit
pause/cancel semantics. Its standalone fixture run passed 40 tests in 7.116
seconds before r5. See `docs/SAFETY-REHEARSAL.md` for the bounded retry behavior,
coverage and limitations.

**Open security follow-up, separate from the passing gate:** a disposable
ordering reproduction found that Spotify can publish a pending OAuth listener
if cancellation occurs between its Safety check and pending assignment. The
result was `stale_pending=True`, `listener_stop_set=False`. This was reported
for the parent/provider owner before shared edits. The central notification
alone does not close that provider publication race, and r5 must not be cited
as proof that it does. A provider-side epoch recheck at pending publication and
an isolated regression are still required before calling that exposure resolved.

No native rebuild, Desktop installation, live account/Keychain operation,
interactive browser acceptance, Git operation or GitHub workflow execution was
performed by r5. Its `native_build` field is correctly NOT_RUN. The previous
native build remains dated historical evidence; the parent owns installation,
browser acceptance and the replacement-PR publication preserving main.

### Frozen operational release r6: strict gate PASS

After C's Spotify fixes, D's late-created control-label fixes, and Mill's final
cache-version/fixture update, the parent authorised a frozen-source strict run.
It completed on 2026-09-08 at 10:08:00 UTC with exit 0:

```bash
cd "/Users/u1/Documents/ChatGPT/U1 OS ( MAC )"
bash scripts/check-personal-release.sh --require-all \
  --report /private/tmp/u1-personal-release-sidecar-20260908-r6.json
```

Evidence: `/private/tmp/u1-personal-release-sidecar-20260908-r6.json`.

- PASS 516 tests/contracts: 414 Python tests across all 25 named modules and
  102 JavaScript contracts across all eight named suites.
- PASS 69 syntax checks. Zero failures, errors, skips or missing required tests.
- Spotify now passes 29 isolated tests, versus 27 in r5. Operational polish now
  passes 16 Node tests, versus 13 in r5. These five additional tests account for
  the increase from 511 to 516; no projected count is substituted for execution.
- The 40-test central Safety-hook rehearsal and nine operational-navigation
  contracts also pass. The latter includes the updated mixed cache-version
  expectations: only operational polish and Spotify widget use 20260908.7.
- The exact real-FFmpeg fixture remains OPT-IN NOT_RUN, separate from the zero
  skipped-test count.

Targeted closure: C reported the OAuth pending-publication race fixed and added
isolated Spotify regressions; D reported the late-created mobile Control Centre
label fixed and added isolated polish regressions. Their updated suites passed
in r6. The r5 open-race follow-up above is therefore superseded at this targeted
fixture-coverage level, not rewritten as if r5 had tested the fix. This is not
proof of a real OAuth exchange, live listener termination, paid-provider access,
Keychain access, or comprehensive concurrency correctness.

C's measured shelf-plus-12px widget layout fix is included in the frozen source
and its JavaScript passes syntax checking. Actual widget overlap, browser/mobile
accessibility and screenshots remain the parent's separate browser acceptance;
they are not inferred from these test counts.

The existing r5 JSON and its dated open-race record were preserved unchanged.
No source edits, native rebuild, Desktop installation, account action or Git
operation occurred during r6. Only this guide and the Safety rehearsal guide
received post-run evidence appendices. Native build and interactive Mac checks
remain NOT_RUN in the r6 JSON; historical native build evidence stays separate.

## Rounded rebuild audit R2: 2026-09-08

The complete strict report passed at `2026-09-08T11:42:22.619604+00:00`:
**805 tests/contracts** (570 Python across 30 named modules, 235 Node across 17
suites), **116 syntax checks**, zero required failures/errors/skips/missing.
Its source revision is explicitly `unrecorded`. The initial expanded failing
report is retained, not relabelled as a pass.

The first run exposed a runner-only mismatch around safe directory-descriptor
opens. Thread-local audit context was corrected without widening allowed roots
or changing actual `dir_fd`/`O_NOFOLLOW` operations; five new guard regressions
passed. Three synthetic FFmpeg integration methods are now explicitly separate
NOT_RUN entries, not silent skips in the unit total.

The outer R2 console-mirroring pipeline returned 1 because sandboxed `tee` could
not open `/dev/fd/3`. All canonical report and suite records are PASS, and the
full console was retained separately. A separate inner-process exit code was
not captured; do not describe the outer command as recorded exit zero.

The new minimal-identity policy separately passed 31 native checks and temporary
Swift compilation. This audit did not replace Desktop, run native interactive
acceptance, perform Developer ID signing or notarise the app. See the
[dated audit report](AUDIT-ROUNDED-20260908.md) for evidence paths, browser captures,
known remaining limitations and the replacement-PR publication boundary.
