# Account activation: operator preflight, not account verification

## Parent integration

- Exact GET `/api/workspace/activation` delegates to `utils.u1_connection_preflight.handle_request(handler)` after the canonical Safety gate. Return value is handled `True` or unrelated-path `False`.
- Uses `handler.integration_request_allowed()`; responses are no-store JSON. POST and other methods return 405 and do not read a request body or persist checklist changes.
- Load `/static/css/u1-activation-workspace.css` and `/static/js/u1-activation-workspace.js` after core. Registered views are `activate` and `activation`.
- `window.U1Activation.mount(host)` mounts the view; `stop()` aborts its active GET; `normalizeManual(value)` normalizes the bounded non-secret operator checklist.
- Existing provider routes remain unchanged: Google `/api/workspace/google` via native Connections; AI `/api/workspace/assistant`; Images `/api/workspace/image-provider`. Navigation targets are `integrations`, `ai`, and `images`. Google setup uses `window.U1Reliability.open('google', button)` when available.
- The optional Spotify workstream is separate: `/api/workspace/spotify`, view `spotify`, and `docs/SPOTIFY.md`. Activation does not call Spotify or infer its authorization.

## What the read-only endpoint actually checks

`snapshot(root=None, *, modules=None, codex_path=...)` is fixture-injectable. Production checks installed CLI/helper file metadata, whitelisted public image configuration, selected Google preference scalars through a read-only immutable SQLite connection, and already-loaded assistant runtime evidence. It never imports/initializes assistant manager state, invokes a provider snapshot that can create a database, starts a subprocess, opens a Keychain item, reads authentication files, or calls an account/API.

Google SQL projects only configured/last-sync/auto-sync scalars from the known preference row. It never returns full stored JSON, mail, calendar entries or tokens. Missing, malformed, symlinked or actively WAL-backed metadata produces unknown/setup states, not a misleading old snapshot. Public image metadata is size-bounded, owner-only and opened without following symlinks. Assistant runtime metadata uses a bounded lock acquisition and selects timestamps/status only, never prompts, context or generated text.

The response has `read_only: true` and `live_verification: "not_performed"`. Provider `live_verified` is always false. Installed/configured flags and recorded historical success remain distinct from successful current API authorization. A missing unavailable metadata source does not trigger repair, auth probing or account requests.

## One explicitly reviewed action per provider

1. **Google:** use native Connections to configure the user's own Desktop OAuth app. Review read-only consent/scopes in Google. Explicitly run one Sync, then compare the returned observation and timestamp against the intended account. Existing success markers are historical evidence, not a live check.
2. **AI Command:** confirm the installed Codex setup through the existing native AI view. Select only the intended prompt/context, review the subscription-allowance notice, and send once only when the operator approves. Inspect the actual completed job/response, not simulated agent actions.
3. **Images:** use native Images setup, never chat, for a separately billed API credential. Review prompt and explicit separate API billing confirmation before one real generation. Confirm the actual returned image/job. A configured marker alone never proves key validity, eligibility or balance.
4. **Canva:** this is an **unfinished external handoff**, not a native API connection. Open Canva deliberately and perform/review a manual design action there if desired. The [official Canva Connect documentation](https://www.canva.dev/docs/connect/) describes a real integration; merely opening the website does not implement or authorize one. Native OAuth/token/API integration remains unfinished here.

The view provides a stepwise checklist and a separate explicit Record review button. Records contain only normalized booleans and a review timestamp under browser-local key `u1.activation.operator.v1`, at most 4 KiB. They do not alter any provider's backend status, do not send a request, and do not claim verified API status. No secrets, free-form account notes or prompt contents are collected. Reset clears only these checklist records. If browser storage is unavailable, persistence is unavailable; account status remains unaffected.

The view fetches only the activation GET on mount/manual refresh, not a polling account check. Safety/page lifecycle cancels active requests. It never enables always-listening voice, auto-sends a prompt, starts OAuth, generates an image, or requests token entry in chat.

## Test boundary

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_u1_connection_preflight.py' -v
node --check static/js/u1-activation-workspace.js
```

Temporary fixture tests cover no-side-effect missing state, installed-vs-authorized distinction, Google scalar projection/WAL handling, image metadata/symlink protection, honest Canva status and exact read-only HTTP routing. Subprocess/network operations are mocked to fail if attempted. No real account calls, credential probes or paid actions are used. These checks do not replace an operator-approved real action per provider or parent shell/browser verification.
