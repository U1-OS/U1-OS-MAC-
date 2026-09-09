# Desktop tools: discovery and native inventory

Discovery on 2026-09-08 used bounded top-level directory listings, the five
existing relevant Desktop plists, their launcher scripts, referenced launcher
configuration, and selected repository metadata. No repository tool, launcher,
search, account, package installation or network probe was executed.

The eight repository candidates are present. There are currently five matching
Desktop bundles, two missing former bundles, and one developer plugin. Do not
describe this as eight working Desktop OSINT apps. TikTok LIVE Studio and U1 OS
also appear on the Desktop but are not substituted for missing tools.

| Candidate | Exact repository | Current Desktop evidence |
| --- | --- | --- |
| DFW1N OSINT | `/Users/u1/Documents/ChatGPT/Repo's/dfw1n-osint` | `/Users/u1/Desktop/DFW1N OSINT.app`; launcher opens that repository's `.local-guide.html` |
| God's Eye View | `/Users/u1/Documents/ChatGPT/Repo's/gods-eye-view` | `/Users/u1/Desktop/Gods Eye View.app` is absent; package metadata identifies the repository |
| Holehe | `/Users/u1/Documents/ChatGPT/Repo's/holehe` | `/Users/u1/Desktop/Holehe.app` is absent; README identifies the repository |
| Maigret | `/Users/u1/Documents/ChatGPT/Repo's/maigret` | `/Users/u1/Desktop/Maigret.app`; `launcher.json` matches the repository and `http://127.0.0.1:4176/` |
| Osiris AI | `/Users/u1/Documents/ChatGPT/Repo's/osiris` | `/Users/u1/Desktop/Osiris AI.app`; configuration matches the repository and `http://localhost:4175/` |
| Ponytail | `/Users/u1/Documents/ChatGPT/Repo's/ponytail` | No corresponding Desktop launcher; package is `@dietrichgebert/ponytail`, a developer plugin |
| Sherlock | `/Users/u1/Documents/ChatGPT/Repo's/sherlock` | `/Users/u1/Desktop/Sherlock.app`; Terminal wrapper changes into this exact repository |
| SpiderFoot | `/Users/u1/Documents/ChatGPT/Repo's/spiderfoot` | `/Users/u1/Desktop/SpiderFoot.app`; configuration matches the repository and `http://127.0.0.1:5001/` |

Configured addresses are evidence from metadata, not tested services. Runtime,
dependency, port ownership, accounts, billing and external-data readiness remain
unchecked. Existing launchers can start separate processes or external requests;
they are not exposed as U1 execution actions in this starter.

## Parent wiring

The module owns only `utils/u1_osint_tools.py`, `static/js/u1-osint-tools.js`,
`tests/test_u1_osint_tools.py` and this document. It does not modify Media or the
research casebook, the shell, Desktop launchers, repositories, or Git state.

Load `u1-osint-tools.js` after the native core registry and retain the existing
`u1-media-research.css` stylesheet. The script immediately registers native view
`osint-tools`; it exports `U1OSINTTools.register()`, `mount(host)` and `refresh()`.
It uses the same `u1:native-views-ready` event and late-core registration contract
as Media. Parent navigation can expose it as Desktop tools next to the `osint`
casebook; route `U1Platform.open('osint-tools')` to this native view.

After the parent safety gate and before generic workspace routing:

```python
from utils.u1_osint_tools import handle_request
if handle_request(self):
    return
```

`GET /api/workspace/osint-tools` returns the eight fixed entries, check time,
explicit capabilities and limitations. Optional `?id=maigret` selects a known ID.
Only GET is accepted; POST and other methods return 405 without reading a body.
Same-origin checks are required for reads. Unknown IDs, duplicated IDs, paths,
commands, URLs and extra query arguments are rejected. There is no launch API,
shell argument builder, arbitrary-file endpoint, health probe or tool import.

Each entry reports repository/marker presence, Desktop presence, mapping evidence,
`runtime_status: not_checked`, `launch_available: false`, and `query_available:
false`. States are `desktop_only`, `setup_needed`, `plugin_only` or
`review_required`. Source files are never executed. Metadata reads have a 16 KiB
limit, reject symlinks, nonregular files, multiple hard links, unexpected ownership
and group/world-writable files. Changed bundle IDs, executable names or configured
repository/URL mappings produce a review state without returning unexpected
configuration content or secrets. No package files or credentials are read by
the runtime inventory.

The only clickable handoffs are fixed external project documentation URLs. Local
service addresses are displayed as text. No private-person search, email account
enumeration, dossier aggregation, account bypass or automatic scan is connected.

## Acceptance

```sh
.runtime/bin/python -m unittest tests.test_u1_osint_tools -v
node --check static/js/u1-osint-tools.js
U1_MR_REAL_FFMPEG=1 .runtime/bin/python -m unittest tests.test_u1_media_research -v
```

Inventory tests use temporary repositories and synthetic plists/configuration,
and reject any attempted process launch or external network request. The Node DOM
fixture tests existing-player reuse, an empty source/document URL, page-to-shelf
handoff, source visibility, retained playhead and absence of pause/reload/duplicate
players. It does not use a shared browser or a real user-selected file.

The 27 Media tests, including actual MP4 and WAV rendering from a generated owned
one-second fixture and decoding their outputs, passed during this task. These
fixtures are test material, not application demo content. Real user-selected audio
and video playback remains pending an interactive acceptance check; no claim of
that acceptance is made from a synthetic export or DOM fixture.
