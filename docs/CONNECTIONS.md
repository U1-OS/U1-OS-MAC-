# Native Connections and Settings

Implementation for the U1 OS approved build, 2026-09-08. This contribution owns
only the two workspace assets, the pure policy helper, its Node tests and this
document. It does not wire the shared shell or change backend adapters.

## Parent wiring and hooks

Load `/css/u1-connections-workspace.css` after the existing core workspace styles.
Load these classic scripts in order, after `U1CoreViews`, `U1Platform` and the
reliability hub:

```html
<link rel="stylesheet" href="/css/u1-connections-workspace.css">
<script src="/js/u1-connection-policy.js"></script>
<script src="/js/u1-connections-workspace.js"></script>
```

The parent must also load the existing optional feature modules before users open
Settings: `U1Safety`, `U1Launch`, and `U1ReadyCore` followed by `U1Feedback`.
Missing optional modules produce disabled controls or an explicit setup message.
No defaults are written on mount. No script inserts another stylesheet or iframe.

| Hook | Contract |
| --- | --- |
| `U1CoreViews.register('integrations', mount)` | Native provider cards, Google actions and local AI detection |
| `U1CoreViews.register('settings', mount)` | Native privacy, appearance, sound, safety, attention and recovery |
| `U1Connections.ready` | False if the policy helper or core view registry was missing at load time |
| `U1Connections.capabilities()` | Frozen, read-only current capability rows; no settings, account values or tokens |
| `U1Connections.privacy()` | Current visual masking preference |
| `U1Connections.setPrivacy(boolean)` | Apply masks; return whether device persistence succeeded |
| `u1:privacy-change` on `window` | Detail `{enabled, persisted}`; contains no private data |
| `[data-u1-private]` / `[data-u1-sensitive]` | Parent opt-in masking hooks for additional private content |
| `data-go="security"` | Parent native encrypted-backup/export, restore-drill and permission workspace |
| `data-go="updater"` | Parent native release and recovery workspace |
| `data-go="jobs"` | Shown when `U1CoreViews.supports('jobs')` reports the assistant's native Jobs view |

The parent native nav/search registry mounts these views through `U1CoreViews`.
Normal `data-go` buttons are left to the parent's navigation handler. This module
does not patch shared routing or depend on the removed legacy shell/pages.
`u1:navigate`, page visibility and `pagehide` stop inactive Google status polling.

Encryption, restore drills and managed-job pause/resume/stop are parent-owned.
This module only links to those native workspaces. It does not implement crypto,
call `/api/safety` job actions or alter ReleaseGuard. Parent Updater operations
remain `U1Workspaces.action` calls to ReleaseGuard `prepare_update`,
`get_release_state` and `apply_update`.

The existing reliability export is `window.U1Reliability = Object.freeze({open})`.
`open('google'|'recovery', openerButton?)` opens a native dialog. Recovery uses
`GET /api/workspace/recovery` and `POST /api/workspace/recovery` bodies
`{action:'backup',confirmed:true}` or `{action:'restore',id,confirmed:true}`.
The native managed recovery tool remains directly accessible from Settings.

## Status and actions

Initial reads use same-origin, noncached GET requests to `/api/integrations`,
`/api/workspace/google` and `/api/workspace/providers`. Partial endpoint failures
leave the other controls usable. Refresh discards unsaved forms only after the
user confirms. Google job refreshes replace only the Google cards and capability
table, preserving API-setting drafts.

The current integration source exposes 18 providers. All non-Google cards use
catalogue metadata for field names, saved-value presence, category, notes and
provider portals. They offer **Save API settings** and, when applicable,
**Clear saved settings**. No non-Google account connect/sync/disconnect adapter is
implemented here. An installed adapter file or saved API key is not authentication.
Ollama has no editable fields and needs its separate runtime and model.

Settings writes obtain a fresh CSRF token from GET `/api/integrations`, then POST:

```json
{"integration":"provider_id","values":{"field_id":"user-entered value"},"clear":false}
```

The request sends `X-U1-CSRF`. Clearing uses empty values and `clear:true`, with
explicit confirmation. It only clears local settings; provider tokens are not
revoked. Blank secret inputs preserve saved secrets. Secret values from a GET are
discarded during normalisation, never populated back into fields, cached or
logged. Typed values are sent only after an explicit save. Native error messages
do not echo backend response bodies or submitted values. Ambiguous network/write
failures request a status refresh; mutations are never automatically retried.

## Google setup and constraints

Gmail and Google Calendar share the newer `utils/u1_google.py` connector.
Legacy Google catalogue fields are discarded, have no editor, and cannot be
submitted to the integration settings API through this view.

1. Build the existing helper with `bash macos/build-keychain.sh` on this Mac.
2. Enable Gmail and Google Calendar APIs in your Google Cloud project.
3. Configure consent and create a **Desktop app** OAuth client. Add your account
   as a test user if the consent project is in testing mode.
4. Open **Google setup & review**, which calls `U1Reliability.open('google')`.
   Use its existing JSON upload to place client credentials in Mac Keychain.
5. Explicitly select **Connect** or **Reconnect**. The native view posts
   `{action:'connect'}` to `/api/workspace/google`, then displays the approved
   Google consent URL. It never opens a login or accepts consent automatically.
6. Return after consent and select **Sync**. This requests the existing bounded
   read-only sync job. The response accepting a job is never labelled a completed
   sync. Local status polling runs every four seconds for at most two minutes
   for a sync, or until the returned sign-in expiry, capped at ten minutes.

Connect/reconnect, sync and disconnect appear only with a configured client and
an available Keychain helper. A pending sign-in or sync suppresses duplicate
connect/sync controls. Explicit disconnect applies to Gmail and Calendar together
and keeps imported local data. Provider revocation is reported as confirmed only
when the backend explicitly confirms it; otherwise Google Account permission
review remains necessary.

`Last sync verified` requires all of `configured:true`,
`session_verified:true`, `stale:false`, a nonfuture positive `last_sync` less than
660 seconds old, and no pending/failed job. It describes a successful snapshot,
not an ongoing live connection. Old account identity and timestamps are labelled
as last-reported evidence, including after disconnect. Missing information stays
**Not reported**. The backend's `scopes` are requested connector permissions;
they are never presented as granted account permissions. Actual grants are shown
only if `permissions` or `granted_scopes` are explicitly returned.

This connector reads Gmail and primary-calendar events. It cannot send email or
write Google events. Optional PDF imports, consent, sync preferences and reviewed
local-calendar changes remain in the existing reliability hub. See
[the existing Google/recovery guide](U1-OS-CONNECTIONS-RECOVERY.md) for bounds,
Keychain approval, unencrypted imported data, and managed recovery exclusions.

## AI application detection

`/api/workspace/providers` checks Codex/Claude CLI paths and an Antigravity data
directory. The native cards accurately say **CLI detected / authorisation
required**, **App data found / authorisation required**, not detected, or detection
unavailable. The source does not verify a runnable installation, app launch,
current sign-in, account permissions or successful account checks. It exposes no
native launch adapter, so only a safe **Open provider website** link is offered.

Provider credentials, subscriptions and allowances remain separate. Saving an
OpenAI or Anthropic API key does not sign into Codex or Claude. Usage and 10%
threshold alerts are delegated to `U1Platform.open('usage')`; this module neither
combines quotas nor claims unavailable allowance data. Plain, styled provider
wordmarks are used without downloading or modifying company logos.

## Settings behaviour

- Privacy uses `u1.connections.privacy.v1` and
  `html[data-u1-sharing="true"]`. Masked text uses `visibility:hidden`, blocks
  selection/pointer interaction, and has a neutral placeholder where appropriate.
- Masks cover owned account/input values, opted-in parent elements, native core
  record grids/forms/Trash, and Google/recovery dialog contents. They do not cover
  other apps, unmarked workspaces, downloads, source/DOM
  inspection or logs. This is visual masking, not encryption or access control.
- API form submission is blocked while masking is on. Storage failures still
  apply the preference for the session and are reported honestly.
- Appearance and quiet hours open `U1Platform.open('controls')`; notification
  history opens `U1Platform.open('notifications')`.
- Startup preview uses `U1Launch.preview()`. Connection sound preferences use
  `U1Feedback.preferences()` and `.save({enabled,volume})`. Explicit saved-sound
  preview calls `.play('success',true)` and reports when playback was suppressed.
- Security and Updater use the parent's `data-go` routes. The separate Safety
  Centre button calls `U1Safety.open()`; managed recovery tools call
  `U1Reliability.open('recovery')`. No backup/restore runs from Settings itself.
- Existing engine quality, glow, depth, boot and sound defaults are untouched.
  The new card animation respects system reduced motion, the saved reduced-motion
  mode and the engine's low-power setting.

## Safe validation

```sh
node --test tests/test_u1_connections.cjs
```

The tests cover policy evidence, unsafe metadata/URLs, legacy-field suppression,
CSRF writes, settings clearing/secret handling, native view registration, supported
Google actions, existing Settings hooks, masking/persistence and partial failures.
The browser-boundary tests use a minimal DOM and fully stubbed `fetch`, module
hooks and storage. They perform no real login, credential/token write, Google
sync, provider CLI execution, audio playback or paid provider request.

This suite does not establish live account acceptance, actual installed-app
launch, browser layout/accessibility-tree behaviour, Keychain consent, revocation
or network sync. Parent script/style wiring and desktop/mobile visual acceptance
remain separate checks. Do not use real credentials for fixture validation.
