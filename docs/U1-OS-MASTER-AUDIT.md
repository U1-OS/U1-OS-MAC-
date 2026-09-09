# U1 OS master audit

Audit baseline: `ca192bb`, clean local `main`, 8 September 2026. The canonical
repository is `U1-OS/U1-OS-MAC-`. Rebuild branch:
`codex/u1-cinematic-rebuild-20260908`. This is an evidence log, not a certification.

## Discovery

- Python backend, static HTML/CSS/JavaScript frontend; no package manager or
  frontend framework manifest was found in the bounded instruction search.
- `/` now serves `static/u1os.html`, not the older PRISM-based front door.
- The tracked history contains the newer Command Centre, measurement floor,
  updater and earlier desktop implementation. Their boundaries must be kept.
- No dedicated `CLAUDE.md`, `GEMINI.md`, `AGENTS.md` or provider handoff file was
  found in the project-scoped instruction search. Provider references exist in
  adapters, installation documentation, terminal code and UI. They do not prove
  authorship or current account access. Unrelated home folders were not searched.
- GitHub history was fetched. Remote `main`, the earlier desktop rebuild branch
  and tag `v2.4.0` are available. No abandoned code was blindly restored.
- Private runtime/configuration, databases, account sessions and credentials are
  excluded from source publication.

## Subsystem map

| Area | Evidence / status at audit |
| --- | --- |
| Canonical frontend | PARTIAL: newer shell existed, most routes were placeholders pointing back to `/` |
| Backend / APIs | WORKING read-only probes: `/api/state`, workspace summary/system, integrations registry |
| Authentication | PARTIAL audit: existing origin/CSRF mechanisms retained; not a penetration test |
| Database | WORKING summary contract: records, profile, files, folders and storage; mutation coverage pending this pass |
| Projects / tasks / notes | Existing server-backed workspaces preserved; new Home previously substituted services for projects |
| Calendar | Local records available; external account access NEEDS ACCOUNT CONNECTION |
| Files / Drive | Local feature retained; Drive usage cannot be assumed from a plan or login |
| System telemetry | Real CPU/memory/disk/network endpoint exists; unsupported metrics return null |
| Provider status | BROKEN interpretation: `configured` was displayed as `Connected` in the new shell |
| Provider sparklines | MISLEADING: unrelated endpoint quantiles were being styled as provider activity |
| Boot | SIMULATED completion: 900 ms timeout and timed progress, not readiness checks |
| Globe / motion | PARTIAL: box-based continent approximation and continuously running canvas loops |
| Notifications / SSE | Local notification history exists; canonical shell needed a stream connection |
| Sound | Existing Web Audio engine; default volume/autoplay handling needed restraint |
| Terminal / OSINT / vault | Existing backend retained; not independently re-audited or declared fully verified |
| Crypto / finance | Legacy simulation risk remains; not used as the new Home's evidence |
| AI | Adapters exist; logos and settings do not verify models or subscription access |
| Automation / updater | Existing implementations retained; no background code modification added |
| Agent Centre | Existing read-only advisers preserved; known disabled-button defect repaired in this pass |
| Mac launcher | Existing native wrapper retained; new ownership-checked CLI and SDK-explicit installer added |

## Decisions

Use one outer Command Centre. Host established feature workspaces inside it as
a transitional integration instead of deleting them or presenting empty pages.
This does not finish the requested extraction of all old renderers into one
component system. That consolidation remains explicitly open.

The new Home consumes actual local records and measured telemetry, labels
saved connections unverified, and does not display fictional business figures.
Old dormant functions have not been broadly deleted without regression evidence.
