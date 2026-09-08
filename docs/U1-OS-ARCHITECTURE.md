# U1 OS architecture

The canonical entry is `/` -> `static/u1os.html`. The existing Python server,
service registry, database and compatible `/api/state`, `/api/config`,
`/api/events`, `/api/action` contracts remain in place.

## Frontend ownership

- `u1os.js`: existing navigation, command palette, sound and focus session.
- `u1-cinematic.js`: readiness checks, preference storage, adaptive WebGL Earth,
  pointer depth, visibility suspension and responsive navigation controls.
- `u1-workspaces.js`: truthful Home data adapters, CSRF-aware actions, event
  stream and embedded existing feature workspaces.
- `u1-cinematic.css`: canonical VOID / BLUE tokens and responsive presentation.
- `u1-agent-centre.js`: existing evidence-first advisers and local review history.

The old decorative canvas loops and misleading Home render path are no longer
called by the canonical shell. Shared request promises avoid duplicate startup
calls. Main data refreshes are paused while the document is hidden.

## Local operation

`Launch U1 OS.command` invokes `utils/u1_launcher.py`, which uses the existing
startup routine. A successful response must identify this installation before
the launcher reports readiness. Stop/restart additionally require a matching
saved PID and command path. There is no port-only kill or forced kill.

The Mac wrapper is AppKit + WKWebView. `macos/install-u1.sh` selects Xcode's SDK,
builds the native wrapper/icon and can install it with `--install`, preserving
the previous Desktop bundle. It depends on this workspace and Python runtime.
It is not a signed/notarised, self-contained distribution.

## Remaining architectural work

Embedded legacy workspaces are a transitional compatibility boundary. Full
component extraction, a unified provider-verification backend, full CRUD
regression coverage and production isolation of every legacy demo path remain
separate work. Nothing here proves all requested integrations are connected.
