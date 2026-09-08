# Native AI Command and managed jobs

This module implements confirmed, textual Codex CLI requests using the existing
ChatGPT sign-in. The text assistant does not read, copy, return or log credential
contents. A separate real OpenAI Images API adapter is also implemented. Its
native credential setup and separate API billing must be explicitly confirmed.
Until configured it reports `state: "setup_needed"`. Codex CLI itself still
reports `images_available: false`, `image_state: "separate_api_adapter"`.

## Parent integration

Only the following ten files are owned by this change:

- `utils/u1_assistant.py`
- `static/js/u1-assistant-workspace.js`
- `static/css/u1-assistant-workspace.css`
- `tests/test_u1_assistant.py`
- `docs/AI-COMMAND.md`
- `utils/u1_credentials.py`
- `utils/u1_image_provider.py`
- `static/js/u1-image-provider.js`
- `static/css/u1-image-provider.css`
- `tests/test_u1_image_provider.py`

The new credential helper is image-specific. No server, router, Safety, legacy
integration, database or global grid file is changed.

In the parent GET and POST handlers, immediately after the canonical Safety gate
and before legacy `/api/workspace/` dispatch:

```python
from utils.u1_assistant import handle_request
if handle_request(self):
    return
```

`handle_request(handler) -> bool` returns `True` only after handling one of the
two exact owned paths. It returns `False` for other paths, including subpaths.
Handler requirements are `path`, `command`, `headers`, `rfile`, `wfile`,
`integration_request_allowed()`, `send_response`, `send_header`, `end_headers`.
Responses include JSON content type, `Content-Length`, `Cache-Control: no-store`,
`X-Content-Type-Options: nosniff`, and `Connection: close`; no CORS header is added.

Load the assistant CSS after core CSS and its JavaScript after
`u1-core-workspaces.js`. It registers these `U1CoreViews` IDs:

- `ai`, `assistant`, `ai-command`: native AI Command.
- `jobs`: actual assistant request queue.
- `war-room`, `warroom`: five textual roles and actual request evidence.

`window.U1Assistant.mount(hostElement, view = "ai")` also supports `"jobs"` and
`"war-room"` directly. `window.U1Assistant.stop()` stops voice, speech playback,
and outstanding browser fetches. It does not assert server cancellation.

## Safety and queue helpers

```python
from utils import u1_assistant

# Call after releasing the Safety mutex:
u1_assistant.pause(True)
u1_assistant.cancel_all()

# Only after the parent has authorized resumption:
u1_assistant.pause(False)

state = u1_assistant.snapshot()
# state["jobs"] is a list, newest first; state["paused"] is a boolean.
```

All helpers return the current snapshot. `pause(value=True)` changes dispatch
only; an already-running request continues until cancelled or timed out.
`cancel_all()` cancels queued requests and requests termination of the owned
running subprocess. A running job remains `cancelling` until its process is reaped.
Cancellation does not undo provider work or refund allowance already consumed.

The worker calls `utils.u1_safety.manager().blocked()` before selecting a queued
request and again immediately before process creation. Every call occurs outside
the assistant mutex, including after waiting for a paused queue to resume.
An unavailable Safety service fails closed. A blocked dispatch pauses the queue;
a request blocked at the final launch check is cancelled without starting Codex.
The parent must invoke its pause/cancel callbacks outside the Safety mutex.
The final check cannot atomically share the Safety mutex with process creation;
the parent's explicit cancellation callback closes that transition race.

The browser listens to document `u1:safety-change` with `{locked: boolean}` and
the HTML `data-u1-safety="locked"` attribute. It aborts microphone recognition,
speech playback and fetches, and discards late voice results. A gated browser
request cannot substitute for the parent's server-side cancellation callback.
Unlocking the UI does not automatically resume the queue.

The singleton is lazy: importing the module starts no worker and reads no auth.
An idle worker is created on the first accepted send. The queue is local to this
server process; deploy one parent server instance for this data directory.
Call `u1_assistant.manager().close()` for orderly shutdown. An `atexit` callback
also cancels pending work and waits briefly for the worker. Abrupt OS termination
cannot guarantee child cleanup; no arbitrary historical PID is ever killed.

## HTTP contracts

Both exact paths require the parent's `integration_request_allowed()` to pass,
including GET. POST additionally requires `X-U1-CSRF` to match
`utils.integrations_hub.CSRF_TOKEN`, `Content-Type: application/json`, a positive
`Content-Length` of at most 65,536 bytes, and a JSON object. Chunked transfer is
rejected. The browser obtains the token from `GET /api/integrations` on its first
explicit mutation. Safety gating remains the parent's responsibility.

| Method and path | Contract |
| --- | --- |
| `GET /api/workspace/assistant` | Snapshot with provider, roles, job evidence, conversation summaries, limits, paused and storage-fault state. No provider call. |
| `GET /api/workspace/assistant?conversation_id=<uuid>` | Same snapshot plus the selected conversation and its retained messages/context. Missing conversation: 404. |
| `POST /api/workspace/assistant` | `action: "send"` or `action: "delete_conversation"`. |
| `GET /api/workspace/jobs` | Same snapshot, including `jobs` and `paused`. No provider call. |
| `POST /api/workspace/jobs` | `action: "pause"`, `"cancel"`, or `"cancel_all"`. |

Send request:

```json
{
  "action": "send",
  "request_id": "bc7031c1-d3c8-465a-b083-2e60474397c7",
  "role": "Creator",
  "prompt": "Draft an outline using this selected note.",
  "context": [{"label": "Selected note", "text": "Text explicitly selected by the user."}],
  "confirmed": true
}
```

Optionally include `conversation_id` to continue a displayed conversation. An
omitted or empty identifier creates a new one. `role` defaults to `Creator` and
must be one of `Creator`, `Research`, `Admin`, `Business`, `Design`. These are
textual role instructions, not independently acting agents. No generated
command is executed by the application. Research has no live browsing capability.

Successful acceptance returns HTTP 202:

```json
{"success":true,"duplicate":false,"job":{"id":"...","status":"queued"},"conversation_id":"..."}
```

The actual job object also contains `request_id`, `fingerprint`, `role`, `title`,
`conversation_id`, `created_at`, `confirmed_at`, `started_at`, `finished_at`,
`evidence`, `error`, and `output_bytes`. Timestamps are Unix seconds or null.
The fingerprint is a digest of normalized request content, not a credential.
An exact repeat of a retained `request_id` returns the same job with
`duplicate: true`; changed text with that identifier returns 409. There are no
automatic provider retries. Browser retries preserve the identifier for an
unchanged draft when acceptance is uncertain. Idempotency lasts only while the
job remains within the bounded 64-job history.

Other POST bodies:

```json
{"action":"delete_conversation","conversation_id":"<uuid>","confirmed":true}
{"action":"pause","paused":true}
{"action":"pause","paused":false}
{"action":"cancel","job_id":"<uuid>"}
{"action":"cancel_all"}
```

Mutations other than send return HTTP 200 snapshots. Deleting a conversation
requires no active job for it and explicit confirmation. Its job evidence,
including the shortened prompt title, remains until job retention removes it.
Invalid input is 400, bad origin/CSRF is 403, missing identifiers are 404,
conflicting/full queues are 409, oversized bodies are 413, wrong content type is
415, and service/storage failure is 503. Unsupported methods reaching this
handler return 405. Public errors use fixed text; subprocess stderr and exception
details are discarded.

## Execution, evidence and persistence

The executable is fixed at `/Users/u1/.local/bin/codex`. The subprocess uses
`shell=False`, a fresh session, closed inherited file descriptors and umask 077.
The prompt is supplied on stdin; it is absent from process arguments. Both stdout
and stderr go to `DEVNULL`. The response is read from an owner-only private file.
The non-interactive invocation includes:

```text
exec --sandbox read-only --skip-git-repo-check --ephemeral
--ignore-user-config --ignore-rules --cd <isolated-work>
--output-last-message <private-response> -c approval_policy="never" ... -
```

Explicit CLI overrides require ChatGPT auth, disable shell/unified-exec, hooks,
apps, multi-agent execution, memories, goals, remote plugins, web search, project
instruction ingestion and user login shells. MCP/plugin configuration is empty;
the run is untrusted, with a dedicated project-root marker. Developer instructions
restrict the assistant to text based on the supplied JSON. The environment is
constructed from an allowlist: private HOME/TMPDIR, existing CODEX_HOME, a fixed
system/interpreter PATH, locale and TERM. API keys, custom provider URLs, proxies,
shell startup variables, NODE_OPTIONS and parent tool/thread metadata are not
inherited. The application never opens auth files; Codex owns authentication.
`forced_login_method="chatgpt"` prevents an intentional API-key billing fallback.

Read-only sandboxing does **not** mean files are readable only under the working
directory. The isolated directory avoids accidental project ingestion; explicit
tool/config restrictions and user-selected text provide the application boundary.
This is not an OS container or a claim that the CLI cannot read anything elsewhere.
Installed CLI versions and administrator-managed requirements may affect behavior;
an incompatible CLI fails the request without relaxing the selected flags.

Provider installation is a filesystem/executable check. `authorised` is `null`
until a successful confirmed request provides evidence, then `true` with
`authorised_at`. It is not a token validity probe or a measurement of remaining
allowance. A later provider failure clears that evidence; historical success
does not guarantee continued account access. The separate image adapter has its
own setup and successful-request evidence.

The queue permits at most eight pending/active requests and one owned running
provider worker across text and images. The same conversation cannot have two
active sends. Job states are
`queued`, `running`, `cancelling`, `succeeded`, `failed`, `cancelled`, `timed_out`,
and `interrupted`. `started_at` is set only after Popen succeeds. Evidence reports
worker/process events and response bytes, never invented progress percentages,
agent actions, citations, completed business actions or measured token usage.

Each request has a 180-second provider-process limit. Cancellation sends SIGKILL
only to the new session's process group while the owned child is unreaped. The
worker waits for that child before freeing its slot. If signaling is unavailable,
the queue pauses and cancellation remains unconfirmed until the process exits.
There is no broad process-name kill or use of externally supplied PIDs.

Local storage lives under `data/assistant` with directories mode 0700 and atomic
state files mode 0600. Symlink/unsafe state files are refused, reads are bounded,
and per-request temporary directories are removed after completion. This is local
plaintext storage, not encryption. The implementation retains at most 20
conversations, 20 messages per conversation, 64 job records and 4 MiB of serialized
state. Old inactive conversations and terminal jobs are pruned. Each conversation's
serialized messages are also trimmed to 140,000 bytes. Requests must be saved
before a process starts; subsequent storage failure pauses further dispatch.

Prompt limit: 8,000 UTF-8 bytes. Explicit selected context: at most eight items
and 16,000 combined UTF-8 bytes; each label is at most 180 bytes. Prior completed
turns: at most 24,000 serialized bytes. Response: at most 32,768 UTF-8 bytes.
The private response file is monitored during process polling and read with a
strict cap; a very fast writer can exceed the limit between polls before it is
stopped. No partial oversized response is returned or persisted in conversations.

After restart, previously queued/running/cancelling jobs become `interrupted` and
the queue is paused. Paid work is never silently retried. Live child ownership is
not reconstructed from historical PIDs. Review an interrupted request before
submitting a fresh, explicitly confirmed send.

## Voice and selected context

Notes are fetched only when the user opens the note picker. The user chooses
individual notes; selected text is previewable/removable. Text files are read
only from an explicit browser file selection, with a 16,000-byte size cap. No
backend file-path ingestion or repository/email autoimport endpoint exists.
Prior selected context is not automatically reattached on later turns.

SpeechRecognition is opt-in, one-shot, limited to 45 seconds, and never sends a
Codex request. The browser may process voice remotely; the user sees and confirms
that disclosure before recording. Transcripts land in a separate editable field.
The user explicitly inserts the reviewed transcript into the prompt, reviews the
allowance checkbox and submits. Speech synthesis is optional and also requires
an explicit click and remote-voice disclosure. There is no always-listening mode,
automatic playback, background microphone or voice-triggered submission.

## Validation and remaining integration work

Run the isolated suite without writing bytecode into unrelated directories:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_u1_assistant.py' -v
node --check static/js/u1-assistant-workspace.js
```

The test suite mocks all subprocess calls, process-group signals, sockets and
HTTP entry points. It covers secure invocation, environment isolation, selected
context, allowance confirmation, duplicate protection, serial dispatch, pause,
cancel, timeout, dispatch/launch safety and lock ordering, generic errors,
retention/restart, private files, and exact same-origin/CSRF endpoint contracts.
It does not call a paid model, inspect authentication, access an external network,
or validate a live browser speech service. The parent owns route/script wiring,
global sizing and full browser integration. A real signed-in paid request remains
an explicit user action after those pieces are connected.

Official references checked for the CLI integration:
[Non-interactive mode](https://learn.chatgpt.com/docs/non-interactive-mode) and
[Configuration Reference](https://learn.chatgpt.com/docs/config-file/config-reference).

## Optional real image provider: parent contract

The additional native Images view and API adapter are implemented, with no live
credential access or paid API call performed during development. Route the exact
`/api/workspace/image-provider` path to
`utils.u1_image_provider.handle_request(handler)` after the same canonical Safety
gate and before legacy workspace dispatch. Its handled/unhandled boolean and
handler interface match the assistant module.

Load `static/js/u1-image-provider.js` after `u1-assistant-workspace.js`, and
`static/css/u1-image-provider.css` after assistant CSS. It registers native view
IDs `images` and `image-generation`. Direct mounting is available through
`window.U1ImageProvider.mount(host)`. Both frontends share the abortable
`window.U1Assistant.request(path, body?, timeoutMs?)` helper and Safety state.

| Request | Result |
| --- | --- |
| `GET /api/workspace/image-provider` | Setup status, model/options, image jobs, retained image metadata, shared paused/storage-fault state. No key read or provider request. |
| `GET /api/workspace/image-provider?image_id=<job-id>` | A retained successful image as binary `image/png`, with no-store/nosniff headers; IDs are UUIDs, never paths. |
| `POST` with `action: "configure"`, `api_key`, `confirmed: true` | Builds the scoped native helper if needed and stores the key in Keychain. No image generation or account test. |
| `POST` with `action: "disconnect"`, `confirmed: true` | Deletes the image credential only. Active image jobs must first finish or be cancelled. |
| `POST` with `action: "generate"`, `prompt`, `request_id`, `confirmed_api_billing: true` | HTTP 202 managed-job acceptance, with the same duplicate protection as text. |

All POSTs use the integrations `X-U1-CSRF` token and the same bounded JSON,
same-origin and generic-error rules. A generation body may contain only those
four fields. One request produces one `gpt-image-1.5` image at `1024x1024`,
`quality: "low"`, `output_format: "png"`. User-supplied model, destination,
quality, size, count, provider URLs and credential overrides are rejected.

Example generation body:

```json
{
  "action": "generate",
  "request_id": "a3dc3c52-0f09-4adc-b1dd-88f7c2e8e5c",
  "prompt": "A calm abstract landscape in blue and warm ivory.",
  "confirmed_api_billing": true
}
```

Images API billing is separate from the Codex/ChatGPT subscription. No price or
remaining budget is guessed. Saving a key reports `configured_unverified` and
`authorised: null`; success from the actual image endpoint is the evidence for
`authorised: true`. A missing helper/key setup reports `setup_needed` and disables
the Generate button. Codex sign-in does not set image-provider authorisation,
and an image success does not set Codex authorisation.

Image requests use the same queue, job IDs, pause/cancel helpers, dispatch/launch
Safety checks and process-group ownership as text. The worker is a separate
isolated Python child with stdout/stderr discarded. It reads the image key through
the native helper only when running a confirmed job. The request goes exclusively
to `https://api.openai.com/v1/images/generations` over certificate-verified HTTPS.
Proxy inheritance and redirects are disabled, and returned URLs are never fetched.
The worker reads at most 12 MiB of JSON and accepts only one bounded base64 PNG.
API failures are not automatically retried, including after timeouts.

PNG validation checks signature, chunk lengths, CRCs, fixed dimensions, 8-bit
non-interlaced grayscale/RGB/grayscale-alpha/RGBA encoding, bounded decompression,
scanline filters and terminal IEND. Palette/interlaced/animated PNGs are not
accepted by this initial adapter. PNGs are at most 8 MiB each, stored owner-only
under `data/assistant/images`, with at most 20 retained files. Gallery metadata is
derived from successful job evidence. The job `artifact` object contains `url`,
`mime`, `width`, `height`, `bytes`, and `available`. Cancellation stops the local
owned process; a provider request already submitted may continue remotely and
may still incur API charges. The UI states this limitation.

`utils/u1_credentials.py` embeds the native Swift/Security helper source and
builds it only during explicit configuration, using Apple command line tools.
Runtime helper/source/cache files stay under `data/assistant/credentials`.
The Keychain service is `local.u1os.openai.images`, account `openai-images-api`.
Keys travel in bounded stdin/stdout pipes, never process arguments, environment
variables, app logs, local config JSON or browser storage. The existing
Google-specific helper is neither modified nor reused. Native compiler and
Keychain permission behavior remain unverified because tests are mocked only.

Additional isolated checks:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_u1_image_provider.py' -v
node --check static/js/u1-image-provider.js
```

Tests mock all subprocess/network/Keychain operations and use locally constructed
PNG fixtures. No real API key is read, no compiler is invoked, and no paid image
is generated. They cover shared text/image serialization, native stdin credential
transport, independent billing/auth states, fixed HTTPS/no-redirect requests,
malformed/oversized responses, real PNG decoding, cancellation, retention, and
same-origin/CSRF-protected JSON/binary contracts. The parent owns final routing,
script wiring, browser verification and any explicitly confirmed live request.

Official image contract:
[Create image API reference](https://developers.openai.com/api/reference/resources/images/methods/generate).

Development evidence: the isolated suites passed 35 assistant tests and 26 image
tests (61 total). Both JavaScript entry points passed `node --check`. This is
mocked backend and JavaScript syntax evidence, not a claim of live browser,
native Keychain compilation, signed-in Codex execution or image API verification.
