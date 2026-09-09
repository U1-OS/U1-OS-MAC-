# Native Create and Earn

Implementation handoff: 2026-09-08. These are local, operator-led workspaces, not a
publishing service, connected storefront or statement of earnings. Browser visual
acceptance belongs to the parent integration pass; the tests here use isolated
Node transports and DOM/storage fixtures.

## Integration contract

Load `static/css/u1-create-earn-workspaces.css` and
`static/js/u1-create-earn-workspaces.js` after U1Data and U1CoreViews. The parent
may load its rounded theme stylesheet last. The module registers **create** and
**earn**, never Studio or Income, and owns one `h1` inside each hub. Do not prepend
a generic view heading for these routes.

Public renderers are `window.U1CreateEarn.renderCreate(host)` and
`renderEarn(host)`. Both registrations provide optional third-argument hooks:
`{activate(host), deactivate(host)}`. `dispose(host)` is an alias for deactivate.
The first renderer constructs the host once. Cached activation restores handlers
without replacing the DOM or an unsaved review form. Deactivation prevents a
not-yet-submitted review from issuing its POST after route exit or Safety lock.
An already submitted, explicitly approved request may finish; no retry is automatic.

Native navigation uses `data-go="studio"`, `income`, `files`, and `integrations`.
The full Studio editor, original printable library and Income CRUD remain intact.
The hubs do not iframe the old shell or overwrite Studio's draft to select a template.

## Real workflows

- **Create:** a four-stage production guide, actual product shelf, inspected local Studio structures, real saved-file inbox, selected-version detail and approved launch work.
- **Earn:** an actual five-stage product pipeline and filtered catalogue, with selected-product versions and actionable launch-task status reviews. Counts come from saved records, not mock sales or inferred revenue.
- **Plan:** enter a title, audience and useful outcome, inspect the private-record review, then explicitly approve creation of an Idea product.
- **Produce:** open the advanced Studio editor to write, generate, inspect and explicitly save a PDF or ZIP. The hub never replaces its draft automatically.
- **Link:** select a real ready managed PDF/ZIP and a version label, review its ID/checksum and expected product revision, then approve linking it to an existing plan. This manual link is not a claim of Studio origin. Studio's own signed handoff remains the provenance-aware creation path.
- **Launch:** explicitly create Backlog tasks or review status changes. Marking a product Launched records the operator's assertion of publication elsewhere, not a verified sale or automatic post.
- **Download:** only an explicit selection reads file bytes. Size and SHA-256 must match the reviewed metadata before a download or version-link submission.

Opening, filtering, selecting, previewing a structure and refreshing use GET only.
No provider account, Keychain operation, model request or paid API call occurs.
Provider setup has its authorisation and subscription-versus-API-billing boundary
beside the Connections action. AI images and Canva sync are not claimed connected.

## Exact HTTP contract

All requests go through existing `window.U1Data.get/post`. U1Data retains the
host's same-origin and CSRF handling; the hubs do not read or construct tokens.

- `GET /api/workspace/personal/snapshot?kind=product&archived=active&limit=200&offset=N`
- `GET /api/workspace/personal/snapshot?kind=launch&archived=active&limit=200&offset=N`
- `GET /api/workspace/personal/snapshot?id=ID&archived=all` before an update or parent-product task creation.
- `GET /api/workspace/prism/summary` for the bounded recent Files inventory.
- `GET /api/workspace/prism/file?id=ID` only for an explicitly requested download or approved file-linked mutation.
- `GET /api/workspace/studio-pro` for actual supported structure descriptions.
- `POST /api/workspace/personal` with `action:"create"`, `kind:"product"` or `kind:"launch"`, title and validated payload, after review and approval.
- `POST /api/workspace/personal` with `action:"update"`, actual ID, `expected_version` and a minimal status/version payload, after review and approval.

Product/launch lists paginate in batches of 200, bounded to 2,000 records and ten
pages. Duplicate/nonadvancing pages, changing totals and malformed responses fail
visibly. Source failures show unavailable counts, never fabricated zeroes. The
Files inbox is explicitly a recent response window, not a complete library count.

A review cannot be submitted twice by one controller. Matching plans/tasks are
checked again before creation; stale revisions reject updates. These UI checks
are not a replacement for a server-side unique idempotency constraint across
multiple clients. An uncertain POST outcome requires checking real records before
starting a new review. No automatic resubmission is performed.

## Rounded themes and accessibility

The hubs inherit the parent's `--u1r-bg`, `--u1r-surface`, `--u1r-raised`,
`--u1r-text`, `--u1r-muted`, `--u1r-accent`, `--u1r-on-accent`, `--u1r-edge`,
`--u1r-tint`, `--u1r-radius`, `--u1r-control`, `--u1r-gap`, `--u1r-pad` and
`--u1r-shadow`. Navy/cyan is only a fallback. Orbit, Graphite and Daylight are owned
by the global Appearance settings; the hubs do not maintain a conflicting theme
preference or change `data-u1-widget-theme` themselves.

The rounded bento layout collapses its grids on smaller viewports, wraps record
IDs and long titles, retains labelled controls and visible focus, exposes status
messages and disables decorative arrival motion for reduced-motion preferences.
Actual desktop/mobile/theme screenshots must be captured by the parent; no browser
or native-app visual acceptance is claimed by this implementation pass.

## Related Studio reliability repairs

Studio now registers the same lifecycle hooks, keeps per-host DOM/state, checkpoints
edits immediately into separate browser recovery slots, flushes on deactivation,
and detects a changed shared draft before saving. Where available, Web Locks
serialize shared draft commits. Recovery copies also preserve competing editors
when Web Locks are unavailable. Replacing the shared draft requires explicit
confirmation and retains the displaced draft. Recovery copies contain private
answer notes; browser storage remains unencrypted and quota failures require an
explicit editable-project export. Recovery copies are not silently pruned.

Both Studio handoff review and confirmation call
`prism_workspace.read_verified_file(file_id)` and compare its exact bytes to the
signed artifact receipt. Missing, changed or corrupt files fail closed. Durable
`studio_product_origins` and `studio_launch_origins` tables live in the existing
managed SQLite database; new identity bindings no longer depend on editable notes.
Old markers/exact file links can be backfilled at an approved handoff. An OS file
lock serializes Studio handoffs between processes. A reserved seed file supports
recovery if product creation committed before its origin binding completed.

A stale reviewed product revision can return already-created checklist items, but
cannot create a new task. A partial checklist therefore needs the current review
revision before adding remaining tasks. Receipt signatures remain process-bound;
a server restart still requires generation of a fresh receipt. Recovery validates
stored integrity, not authorship, rights ownership or the quality of lesson content.

## Isolated validation commands

```sh
node --test tests/test_u1_create_earn.cjs
node --test tests/test_u1_studio_drafts.cjs
PYTHONDONTWRITEBYTECODE=1 TMPDIR=/private/tmp .runtime/bin/python3 -m unittest discover -s tests -p test_u1_studio_pro.py -v
```

Tests use fixture records, in-memory browser storage, mocked transports and temporary
managed databases. No real accounts, shared browser, global server operations or
real user-data mutation are required. The read-only audit counterexamples were
recorded separately before approved repairs; unrelated PRISM/personal/recovery
repairs remain under their assigned owner's control.
