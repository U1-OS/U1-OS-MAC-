# Operational Safety rehearsal

## Scope and non-negotiable boundary

This is an isolated application-access and managed-job rehearsal, not a live
emergency drill. It never configures the operator's Safety lock, uses an operator
password, disconnects the Internet, signals a real process, invokes a provider,
opens a browser, installs a Desktop app, or performs Git operations.

The sole test module is `tests/test_u1_operational_safety.py`. Every test creates a
fresh temporary Safety directory and assistant queue. The passphrase is a public,
synthetic fixture and must never be used for a real installation. The production
Safety and assistant global manager entry points are patched to these disposable
instances. Safety's monitor startup is suppressed; probes and time are injected.

The standard-library HTTP handler parses actual HTTP request bytes and emits
status lines, headers and JSON into in-memory streams. No TCP socket is bound.
The real `u1_safety.gate_request` and the real assistant GET handler run behind
that harness. Other downstream routes are inert sentinels, not export generators
or provider endpoints. Same-origin eligibility is an injected decision, not a
test of the shared server's Origin/Host validator or routing installation.

Managed-job cases use the real `AssistantManager` queue and worker state machine,
but replace `_execute` with an event-controlled synthetic worker. They demonstrate
queue/confirmation/cancellation transitions, not provider execution or actual
OS process termination. Network, subprocess, shell, and process-signal entry
points are patched to fail and are asserted unused. These are trusted-test
tripwires, not a security sandbox for arbitrary hostile Python.

## Acceptance contracts

| Scenario | Required observable result |
| --- | --- |
| Unconfigured status | No Safety state file, monitor or probe; not armed. |
| Configure | Explicit confirmation; temporary owner-only hashed state; initially locked. |
| Offline monitor | One injected failure does not lock; two consecutive failures do; a successful sample resets the counter. |
| Offline disabled | Injected failures do not activate offline locking. |
| Browser offline signal | An explicit `offline` action locks immediately when enabled; it is distinct from the monitor's two-probe threshold. |
| Reconnect | Updates network status but never unlocks. Correct phrase plus an online probe is needed when offline policy is enabled. |
| Check-in | Status polling does not extend the deadline; exact expiry blocks the next protected request; an explicit unlocked check-in renews it. |
| Unlock throttling | Five wrong phrases trigger a 60-second in-memory cooldown; even the correct phrase is rejected before expiry. Current action errors use HTTP 400, not HTTP 429. |
| Restart | A new instance loading configured temporary Safety state starts locked with a fresh token. Pending persisted jobs become interrupted and the recovered queue is paused, not retried. |
| Protected routes | Locked API GET/POST requests and exports return 423 without downstream execution; response byte length and no-store headers are asserted. |
| Recovery shell | Canonical `/` and static paths pass the gate; Safety status remains reachable only with same-origin eligibility. No classic paths are wired. |
| Action protection | Rejected origin eligibility, missing/stale token and malformed JSON do not unlock. |
| Lock while running | Does not cancel the already-running synthetic job. Its completion remains possible; the next queued job is prevented from dispatching and the queue pauses. |
| Pause | Explicitly confirmed dispatch pause, not termination or suspension of a running provider process. |
| Resume | Requires confirmation; a locked OS refuses it even with a correct phrase. Unlocking alone does not resume an explicitly paused queue. |
| Stop | Requires confirmation and, while locked, the phrase. Queued work becomes cancelled; running work first becomes cancelling and only becomes cancelled after fake execution returns. Lock stays engaged. |
| Repeated queued cancellation | Idempotent; removed payload is not executed or retried. |

Safety is an application access lock, not a firewall, macOS screen lock, stream
revocation mechanism, or exchange-order canceller. Neither a lock nor a pause
proves that an already-started external action stopped. A successful stop request
is not itself proof of termination; acceptance must distinguish `cancelling` from
`cancelled`. This rehearsal deliberately makes no claim about races occurring
inside a real provider launch or already-open HTTP streams.

## Run only this module

Use the existing runtime and explicit import-by-path. This avoids inherited test
discovery and avoids importing `tests/__init__.py`. It does not install anything.

```bash
cd "/Users/u1/Documents/ChatGPT/U1 OS ( MAC )"
.runtime/bin/python3 -I -B - <<'PY'
import importlib.util
from pathlib import Path
import signal
import sys
import unittest

def expired(signum, frame):
    raise TimeoutError("Isolated Safety rehearsal exceeded 90 seconds")

signal.signal(signal.SIGALRM, expired)
signal.alarm(90)
root = Path.cwd().resolve()
sys.path.insert(0, str(root))
spec = importlib.util.spec_from_file_location(
    "u1_operational_safety_rehearsal", root / "tests/test_u1_operational_safety.py")
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
result = unittest.TextTestRunner(verbosity=2).run(
    unittest.defaultTestLoader.loadTestsFromModule(module))
signal.alarm(0)
print('SAFETY_REHEARSAL tests=%d failures=%d errors=%d skips=%d' %
      (result.testsRun, len(result.failures), len(result.errors), len(result.skipped)))
raise SystemExit(0 if result.wasSuccessful() and result.testsRun and not result.skipped else 1)
PY
```

The alarm is a bounded timeout for this disposable Python test process only. It
does not signal other processes. Individual fake-worker waits and joins are also
bounded. No real clock waiting is used to exercise the five-minute deadline or
sixty-second authentication cooldown.

## Release evidence and parent handoff

- Record date, exact command, module test count, failures, errors and skips.
- Describe this result as isolated in-memory HTTP/handler plus fake-job coverage,
  never as a browser, live networking or real provider cancellation acceptance.
- Do not include fixture state files, hashes, passwords, tokens, private paths,
  live exports or user data in published artifacts. Aggregate counts and this
  documentation are sufficient.
- The parent may explicitly add `tests/test_u1_operational_safety.py` to the
  release allowlist when all concurrent work is complete. This sidecar does not
  edit that allowlist and does not run the combined release gate before approval.
- The earlier r4 strict release result and native app build predate this new
  rehearsal. Do not silently add this module's count to those historical totals.
- Any confirmed backend defect must be reported to the parent before a shared
  edit. The rehearsal owner changes only this guide and its named test module.

### Execution record

On 2026-09-08, the explicit isolated runtime command above completed with exit 0:

```text
Ran 27 tests in 4.932s
OK
SAFETY_REHEARSAL tests=27 failures=0 errors=0 skips=0
```

All network, subprocess, shell and process-signal tripwires remained unused.
No backend defect was confirmed by this bounded rehearsal. The two new files are
the entire change scope; no shared backend, release allowlist or existing test
was changed.

### Spotify-only central lock notification

The parent subsequently approved a narrow change in `utils/u1_safety.py`.
Manual locks, browser/monitor offline locks, check-in expiry, monitor faults and
restart-locked state now deliver a Spotify-only cancellation notification after
the outermost Safety operation releases its mutex. Assistant access-lock versus
explicit pause/cancel semantics remain unchanged.

Delivery uses one serialized attempt per outer operation, no new worker or
listener, and at most a 50 ms wait for the existing Spotify state mutex. It does
not import or initialize a provider. The existing provider's `cancel_all()` sets
the pending stop event and invalidates its epoch. Busy or exceptional delivery
remains visible in `spotify_oauth_cancel_pending` / `spotify_oauth_cancel_error`
and is retried on the next Safety operation or monitor tick. This is a stop
request, not proof that a listener thread has already joined or that an in-flight
remote exchange has been undone.

The extended isolated run on 2026-09-08 passed 40 tests in 7.116 seconds:

```text
SAFETY_HOOK tests=40 failures=0 errors=0 skips=0
```

The added fixtures exercise each lock path, callback re-entry, another thread
acquiring the Safety mutex during notification, busy/error retries, deduplication,
no lazy provider startup, and unchanged running assistant jobs. No live state,
listener, provider or Keychain operation is used.

A separate isolated ordering reproduction confirmed that Spotify could publish
pending OAuth after cancellation between its Safety check and pending assignment.
That provider-side race was reported to the parent/C; this central hook alone
does not claim to resolve it. The provider owner must report its fix separately.

Combined strict gate r5 completed on 2026-09-08 at 09:54:08 UTC with exit 0:
511 tests/contracts (412 Python across 25 modules, 99 Node across eight suites),
69 syntax checks, zero failures/errors/skips/missing required tests. This includes
the 40-test operational Safety module. Evidence is
`/private/tmp/u1-personal-release-sidecar-20260908-r5.json`.

The real-FFmpeg opt-in test remains explicitly NOT_RUN, not a passing or skipped
test. The separately reproduced OAuth publication race is not covered by a
passing regression in r5 and remains a provider-owner release follow-up.
Live Safety drill, browser acceptance, actual provider termination, Desktop
installation and native rebuild: NOT RUN by this rehearsal. Existing r4/build
evidence remains historical and is not relabelled as coverage of this module.

### Dated r6 targeted regression closure

On 2026-09-08 at 10:08:00 UTC, the frozen-source strict gate completed with exit 0.
Evidence: `/private/tmp/u1-personal-release-sidecar-20260908-r6.json`.

```text
PASS: 414 Python tests and 102 JavaScript tests
25 of 25 named Python modules present; eight explicit JavaScript suites
516 total tests/contracts; 69 syntax checks
failures=0 errors=0 skips=0 missing_required=0
```

The operational Safety module remains 40 passing tests. C's updated Spotify
suite now passes 29 tests, including its reported OAuth publication-race
regressions; D's updated polish suite passes 16 Node tests, including its
reported late-created mobile-label regressions. Nine operational-navigation
contracts pass with Mill's final cache-version expectations. The separately
reported fixes are therefore accepted at this isolated fixture-coverage level.
The earlier r5 race warning remains accurate as dated history; it is not erased
or retroactively relabelled as passing race coverage.

No real OAuth/account request, listener startup, Keychain operation, live Safety
configuration or provider termination was exercised. The widget layout source
passes syntax checking; the parent owns its actual browser/layout acceptance.
The real-FFmpeg fixture remains OPT-IN NOT_RUN. No native rebuild, Desktop
installation or Git operation was performed by this run.

### Subsequent massive-audit repairs, 2026-09-08

The earlier 516-test r6 and massive-audit baseline are historical, pre-repair
evidence. They do not validate the following changes. Targeted results are
reported separately; the next combined gate waits for parent consolidation.

Safety now notifies both already-loaded providers independently after releasing
its mutex. Google uses its module `LOCK` and local-only `cancel_all()` contract:
invalidate the epoch and pending flow, set cancellation markers for running work,
invalidate session verification, and set `PAUSED=True`. The helper performs no
startup, database, Keychain, provider request or listener shutdown. Each provider
lock acquisition is bounded to 50 ms. No thread is spawned and no callback is
imported lazily. Provider code must preserve this bounded local-only contract.
Google failure/busy delivery is visible as `google_cancel_pending` and
`google_cancel_error`; Spotify retains its existing fields. One provider failure
cannot suppress the other's notification. Failed delivery retries on a later
Safety update, without leaking exception details.

Google auto-sync remains paused after locking until an explicit reviewed Sync or
Connect action. Reconnection and unlocking alone do not resume it. These provider
invalidation requests do not change assistant semantics: an access lock is not
automatic assistant cancellation, dispatch pause is not process suspension, and
unlock is not queue resume. Provider-owner race regressions remain separate from
these fake-provider central-hook fixtures. Locked `POST
/api/workspace/prism/upload-abort` remains protected like other workspace writes;
no public or Safety exemption is added for it.

An active check-in now expires at the earlier of its process-local monotonic
deadline and its wall-clock deadline. Moving wall time backward cannot extend
the monotonic lease; ordinary forward wall time also accounts for sleep on
platforms whose monotonic clock pauses in suspend. This does not claim a tested
platform continuous-suspend clock under simultaneous sleep and wall-clock edits.
Explicit unlock/check-in atomically persists `checkin_deadline_wall` alongside
the existing configuration, then publishes the new in-memory deadlines. A failed
write neither unlocks nor renews the previous lease. Monotonic values are never
persisted. Every configured restart still starts locked, with no resumed lease,
even if the persisted wall deadline is in the future or the clock moved back.
The new optional field is backward-compatible with version-1 configurations.
The existing authentication cooldown is unchanged and remains process-local.

The desktop launcher now uses the same minimal `/healthz` identity contract as
the wrapper and opens only `/`. A persistent owner-only `.u1-os-launch.flock`
regular file is protected by a nonblocking kernel lock. Process exit releases
ownership; the file is deliberately not unlinked, avoiding split-inode locks.
The old ownerless directory is left intact and ignored by updated launchers.
This does not retrofit coordination into an already-running older launcher.
No process is killed and port conflicts remain errors, not takeover requests.

Bundle promotion now rolls back catchable `KeyboardInterrupt`/`SystemExit` as
well as ordinary failures, including interruption immediately after the backup
rename. If promotion already completed, or another actor created a destination,
that destination is not overwritten during rollback. Backups remain available.
This is not a SIGKILL/power-loss-atomic filesystem exchange; interruption of the
rollback itself still requires explicit operator recovery from the backup.

New fixture coverage is explicit in the existing two owned test modules:
Google lock paths and mutex/retry boundaries, unchanged assistant execution,
dual-clock expiry/persistence failures, kernel lock ownership and canonical
launcher readiness, and catchable promotion interruption. All fixture state and
bundles are temporary. No real Safety, provider or Desktop operation is used.
