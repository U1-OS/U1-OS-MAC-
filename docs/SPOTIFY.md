# Spotify read-only account widget

## Integration contract

- Route exact `/api/workspace/spotify` to `utils.u1_spotify.handle_request(handler)` **after the canonical Safety gate**. It returns `True` when handled, `False` otherwise. No other global file is changed here.
- GET returns cached local configuration/playback metadata only. It never starts OAuth, reads Keychain, compiles a helper, or contacts an account. Status initialization does not create data directories.
- POST requires the existing `handler.integration_request_allowed()` origin check, `X-U1-CSRF` matching `utils.integrations_hub.CSRF_TOKEN`, JSON content type, a body no larger than 4096 bytes, and literal `confirmed: true`.
- Actions: `configure` also takes the public 32-hex-character `client_id`; `connect` starts the temporary callback listener and returns `authorization_url`; `refresh` performs the reviewed read-only account check; `disconnect` removes this adapter's local Keychain item, not Spotify dashboard authorization.
- Load `/static/js/u1-spotify-widget.js` after core. It registers route `spotify`, injects scoped styles, and mounts a persistent collapsible account widget. No separate CSS file or local audio-player changes are required.
- Browser helpers: `window.U1Spotify.mount(host)`, `mountWidget(host?)`, `stop()`, and explicit `refresh()`. Automatic account checks are OFF by default and never persisted; the user can opt into a visible-tab, 20-second session loop. Backend minimum interval is 15 seconds and respects bounded Spotify rate-limit cooldowns.
- The frontend uses the existing integrations CSRF discovery endpoint `/api/integrations`, accepting `csrf_token` or `csrf`. No account token enters browser JavaScript or browser storage.
- Parent Safety should call `utils.u1_spotify.cancel_all()` **outside its mutex**. This never creates an instance; it cancels pending OAuth and invalidates in-flight results. Browser `document` event `u1:safety-change` with `{locked: true}` stops requests/auto-refresh. Unlock does not resume account polling automatically.

Example reviewed request:

```json
{"action":"refresh","confirmed":true}
```

The response includes `success`, `status`, `configured`, `credentials_saved`, `connected`, `live_verified`, `observed_at` (Unix seconds or null), `item`, `next_refresh_at`, `oauth_pending`, `scope`, `read_only: true`, and `controls_available: false`. `item`, when supplied by Spotify, includes bounded `title`, `artist`, `type`, `url`, `device`, `progress_ms`, and `duration_ms`. Progress is an observation, never extrapolated. Only actual Spotify track/episode HTTPS links are admitted.

## Operator setup and one reviewed check

1. In the [Spotify developer dashboard](https://developer.spotify.com/dashboard), create or select your own app and confirm current owner/account eligibility and any development-mode user allowlist. This code does not create an app or infer account eligibility.
2. Register **`http://127.0.0.1/spotify/callback`**, without a port. Spotify explicitly permits dynamically assigned ports for registered loopback IP literal redirects. `localhost` is not permitted. See the [official redirect policy](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri).
3. Open the native Spotify view. Enter only the public Client ID, then confirm Save setup. No client secret is needed. Never paste account tokens or passwords into chat.
4. Setup builds a small native Swift Security-framework helper using installed Apple developer tools. It does not read or probe a Keychain item. If compiler or Keychain permissions are unavailable, setup stays unavailable instead of falling back to plaintext credentials.
5. Choose Start authorization, then explicitly open the returned Spotify link. Review the single `user-read-playback-state` permission. The [official PKCE flow](https://developer.spotify.com/documentation/web-api/tutorials/code-pkce-flow) uses S256 and a fresh verifier/state held only in server memory.
6. Grant or deny permission in Spotify. On success, return to U1 OS and choose Check playback once. Compare the real song/artist/device against Spotify. Successful OAuth alone is `connected_unchecked`, not verified playback.
7. Only if desired, enable this-session visible-tab automatic checks. Opening the Spotify website alone never connects this adapter. For revocation beyond local disconnect, use [Spotify account app permissions](https://www.spotify.com/account/apps/).

## Callback and data boundaries

The adapter itself binds `127.0.0.1:0` and uses the assigned port in `http://127.0.0.1:<port>/spotify/callback`. **No callback route belongs on the main server.** The separate listener suppresses all request/error logging, validates exact Host plus a ten-minute, single-use state, consumes state before exchanging the code, and closes on completion/expiry/cancellation. It serves only a generic result page with no external resources, no-referrer and no-store headers. Authorization codes never pass through the main server access log.

Owned local runtime storage is `data/spotify/` (0700), containing public configuration (0600), helper source/executable and private compiler cache. OAuth access/refresh tokens are stored only under native macOS Keychain service `local.u1os.spotify.readonly`, with an account derived from this installation path and Client ID. Tokens travel over bounded stdin/stdout, never process arguments, environment, files, browser responses or error logs. Existing Google/image Keychain helpers and services are untouched. No broad credential migration occurs.

Outbound traffic is limited to `https://accounts.spotify.com/api/token` for the explicitly initiated authorization/refresh flow and `https://api.spotify.com/v1/me/player?additional_types=episode` for playback observations. Redirects and inherited proxies are disabled; TLS uses certificate verification. Requests have socket/read limits and response size bounds. Error bodies are not read or reflected. The [official playback-state API](https://developer.spotify.com/documentation/web-api/reference/get-information-about-the-users-current-playback) supplies the track/episode and active device in one read-only call, so a second currently-playing request is unnecessary. There is no playback SDK, streaming, account-profile read, device transfer, volume control, play, pause, skip, queue editing or playlist mutation.

## Honest states and limitations

- `setup_needed`: public Client ID/local helper not set up. `auth_required`: authorization needed, including after a server restart until the user explicitly checks saved credentials.
- `authorization_pending`: a real pending local OAuth flow, not connection evidence. `connected_unchecked`: OAuth completed, no playback observation yet.
- `playing` / `paused`: actual provider response. `nothing_playing`: successful HTTP 204, connected with no active playback. Private sessions and unsupported/missing items have separate non-playing states.
- `stale`: observations older than 45 seconds or retained after a failed request. `unavailable`, `rate_limited`, `keychain_unavailable` and `safety_blocked` remain explicit. Historical item metadata is labeled last observed, not current activity.
- Credentials-saved metadata is not proof of current authorization. Development-mode/account restrictions can produce 403 even after consent; see [Spotify quota modes](https://developer.spotify.com/documentation/web-api/concepts/quota-modes).
- Safety invalidates results and pending authorization, but cannot retract an HTTPS request already received by Spotify. Socket/helper operations finish under their timeouts. Disabling polling does not pause Spotify playback.
- This implementation has not performed real login, read real keys, compiled its native helper, contacted a Spotify account, or demonstrated live playback. Setup/client-ID/permission and parent browser integration remain operator steps. Mock tests are not live provider proof.

## Isolated tests

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_u1_spotify.py' -v
node --check static/js/u1-spotify-widget.js
```

Tests mock all subprocess calls, network requests, helper access and listener startup. They cover PKCE/state replay/expiry, origin/CSRF/body bounds, safety, playback/204/private/stale states, refresh rotation, rate limits, token redaction and private metadata. No paid call or account probe is needed.
