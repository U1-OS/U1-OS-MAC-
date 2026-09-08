# PRISM OS

**Your world. Amplified.**

PRISM is the new desktop layer over the existing local AI Command Centre. It does not replace the HTTP server, integration catalog, credentials manager, provider adapters, Creative Studio, or existing specialist modules.

## Architecture

- `static/js/prism-os.js`: desktop shell, routes, command palette, local command routing, workspace forms, file import, provider handoffs, live-data polling, and standalone-page branding.
- `static/js/prism-ui.js`: escaped UI primitives, line icons, provider identifiers, and original PRISM mark.
- `static/js/prism-globe.js`: local-texture WebGL Earth with bounded rendering, visibility suspension, and reduced-motion support.
- `static/css/prism-os.css`: shared visual tokens, responsive desktop and mobile layouts, accessibility modes, and standalone-tool styling.
- `utils/prism_workspace.py`: SQLite workspace persistence, profile preferences, local file storage, actual host metrics, and location-qualified weather.
- `utils/workspace_hub.py`: dispatches the new `/api/workspace/prism/` namespace while preserving existing handlers.

The browser imports the PRISM module from the existing Home, Studio, and Integrations entry points. The original stage is retained inside the new shell. Specialist tools remain reachable from App Library. Existing data and configuration are not migrated, erased, or renamed.

## Navigation and working features

Home combines the user's real clock, public weather, local projects, actual host metrics, local upcoming events, and honest provider status. The Earth is a decorative animation, not a live satellite feed. Its illumination is artistic rather than a current day/night terminator.

Projects, Tasks, Notes, and Calendar have create/edit workflows backed by SQLite. Project completion is user-entered, not an inferred health or progress estimate. Calendar events are local records, not Google invitations. Folder inventory lists shallow sibling project-folder metadata only; it does not index or read those folders' contents.

Files & Drive imports files into PRISM's local library and supports metadata, downloads, supported image/audio/video previews, and soft deletion. Media uses the same real library and links to Creative Studio and existing video tools. Import is not a cloud upload. File contents are not sent to an AI provider.

The global command palette searches PRISM records, filenames, pages, and tools. AI Command supports deterministic local shortcuts and explicit handoff to existing AI tools. It is not a simulated language model. AI requests are not automatically sent or billed by navigating or selecting a provider.

Settings stores profile/location/timezone, motion, contrast, and focus preferences. JSON export contains workspace records, file metadata, and preferences; it is not a complete binary-file backup and excludes provider credentials. Trash supports recovery, not permanent deletion.

## Real-data boundaries

- Weather uses Open-Meteo geocoding with a country filter and a region-qualified location. The initial preference is Beveridge, Victoria, Australia. Failed refreshes are marked stale or unavailable.
- System disk measurements come from the actual host. CPU, RAM, and network require `psutil`; missing telemetry stays unavailable. GPU and temperature are not fabricated. CPU history appears only after samples are collected.
- Codex quota status uses the existing local usage adapter. Claude and Antigravity telemetry is not misrepresented as subscription quota.
- Saved credential fields are not proof of authorized connectivity. An integration is not labeled connected merely because it appears in the catalog.
- The displayed Google Drive 5 TB plan is user-reported. Storage usage and cloud-file access remain unavailable until a supported authorized connection exists.
- Existing public live-bar feeds remain owned by their existing adapters. Their source, stale state, and setup requirements still apply.
- PRISM does not bypass subscriptions, access controls, platform protections, or account authorization. Logging into a provider website does not automatically authorize an unrelated local application.
- No trading, paid API calls, cloud publication, emails, downloads of third-party copyrighted media, or unattended repair jobs are triggered by this rebuild.

## Local data and safety

By default, PRISM writes under `data/prism/`. Set `PRISM_DATA_DIR` to an isolated directory for tests or a separate workspace. The database and imported files are local, permission-restricted files. This is not application-level encryption; use the Mac's disk encryption and account protections for sensitive material.

Record edits include an expected update timestamp to reject stale edits. Record/file deletion is soft deletion. File uploads use fixed-size chunks with sequential offsets, random storage identifiers, a per-file size limit of 25 MiB, and a total allocation limit of 1 GiB. User filenames are display metadata, not filesystem paths. Completed files have a SHA-256 checksum.

The existing server's origin, host, CSRF, request-size, and lockdown protections apply to the new endpoints. Provider credentials stay in the existing credential system, not the workspace database, exports, browser local storage, or client-visible source.

Do not publish `data/`, databases, imported files, configuration, credentials, logs, or runtime environments to GitHub. Preserve the existing ignore rules and source-only publication workflow.

## Visual asset attribution

Earth texture: **Land ocean ice 2048**, NASA/GSFC, Reto Stockli; enhancements by Robert Simmon. Distributed via Wikimedia Commons by Brosen. The downloaded JPEG is used unchanged; the application applies rendering-time color and lighting. Attribution does not imply NASA endorsement.

- Asset: https://commons.wikimedia.org/wiki/File:Land_ocean_ice_2048.jpg
- License chosen from the Commons licensing options: Creative Commons Attribution-ShareAlike 3.0, https://creativecommons.org/licenses/by-sa/3.0/
- NASA Blue Marble background and scientific credits: https://svs.gsfc.nasa.gov/2915/

The PRISM mark is an original code-native SVG. Provider marks are stylized identifiers, not claims of partnership or certification. Fonts are Space Grotesk and Manrope via Google Fonts, with local Avenir fallbacks when offline.

## Running and verification

Use the existing `start-u1-os.command --no-browser` launcher for the local service on port 8788. Restart the Python service after backend changes. Reload the browser after frontend changes. No JavaScript bundler is required.

For CPU, memory, and network telemetry, install the optional reader into the app's existing virtual environment with `.runtime/bin/python3 -m pip install -r requirements-prism.txt`. Disk telemetry works without it. This installs a local operating-system reader, not a paid provider or cloud account connector.

Use isolated targeted tests for PRISM rather than invoking legacy service actions that can have external effects. Test CRUD, stale-edit conflicts, trash recovery, file chunk bounds, export privacy, Australian weather selection, keyboard navigation, responsive layout, and preserved entry points. Avoid using real private user records as test fixtures.

Signing/notarizing a macOS application, full provider OAuth synchronization, real Google Drive inventory, and complete verification of every retained legacy tool are separate deliverables. The existing launcher and installation paths remain intact.
