# Personal OS rebuild: release validation

Recorded 8 September 2026 on the local macOS development machine. This document
supersedes the earlier test totals in the attributed BUILD-STATUS handoff. It is
not a claim that all 60 roadmap items, external accounts or unattended workflows
are production-complete.

## Final combined gate

| Check | Observed outcome |
| --- | --- |
| Required Python suites | 290 passed across all 18 named modules |
| JavaScript suites | 54 contracts passed across four suites |
| Combined tests | **344 passed, zero failures, errors, skips or missing modules** |
| Python, JavaScript, Bash and workflow syntax/contracts | 40 passed |
| Native navigation policy checks | 23 passed, separate from the combined test count |
| Final Mac wrapper build | Compilation, icon assembly, plist checks and ad-hoc signature verification passed |
| Working-tree whitespace check | `git diff --check` passed before staging |

The release sidecar executed the explicit, isolated gate:

```sh
bash scripts/check-personal-release.sh --require-all \
  --report /private/tmp/u1-personal-release-sidecar-20260908-r4.json
```

The local r4 JSON report is deliberately not a portable repository link. The
commands and detailed native-build boundaries are documented in
[MAC-RELEASE.md](MAC-RELEASE.md). The workflow added by this build runs explicit
checks on pushes and pull requests; a local pass is not a GitHub Actions pass.

## Functional acceptance beyond syntax

- Studio's 18-test focused suite includes its actual JavaScript upload helper,
  Python handlers and a temporary PRISM database. A generated 99-page PDF with
  216 form fields and a ZIP bundle survived chunked upload and download with
  matching bytes and SHA-256 checksums. Invalid offsets, partial downloads and
  tampered signed previews were rejected. The real user's Files were untouched.
- Personal workflows have 47 isolated tests covering local persistence,
  optimistic versions, record references, pricing, paper accounting and
  on-demand threshold deduplication. Paper trades are simulations, not orders.
- AI and image tests mock subprocesses, provider network access and Keychain.
  They do not establish live Codex authentication or a successful billed image.
- The Media agent separately ran the opt-in real FFmpeg test against a synthetic
  one-second colour-and-tone fixture. Actual MP4 and WAV outputs were generated
  and decoded. This separate result is not included in 344: the regular r4 gate
  explicitly records the FFmpeg integration as `OPT-IN NOT_RUN`.
- Safety tests used isolated state. Encrypted-backup acceptance restored into a
  separate temporary destination and did not overwrite the active workspace.
- A focused static review of the new assistant, credentials and image backends
  found no actionable security defect in the reviewed snapshot. This is not a
  comprehensive security audit or proof of live CLI sandbox enforcement.

## Integrated local server checks

After restarting the owned server at `http://127.0.0.1:8788`, all nine new
endpoints returned HTTP 200 and `success: true` for read-only requests:

- `/api/workspace/studio-pro`
- `/api/workspace/personal`
- `/api/workspace/personal/export`
- `/api/workspace/personal/snapshot`
- `/api/workspace/assistant`
- `/api/workspace/jobs`
- `/api/workspace/image-provider`
- `/api/workspace/media-research`
- `/api/workspace/private-backup`

The old `/classic`, `/studio.html`, `/integrations.html` and `/prism.html` entry
URLs returned the controlled hand-off to the new shell. The old iframe shell
fallback was removed from native navigation. Historical source files remain for
compatibility; underlying data was not deleted. Studio's PDF reader is a document
viewer, not an embedded legacy application shell.

## Browser acceptance and actual previews

The real local application was inspected at desktop widths up to 1440 by 1000
and at 390 by 844. Native Media, OSINT, Studio and Income rendered without
horizontal document overflow in the checked views. AI Command, Connections and
the War Room were inspected in their unconfigured/no-request states.

Confirmed defects corrected during integration:

- Inherited shell grid areas created a squeezed/implicit workspace column.
- Direct-hash startup could cache an old-route fallback before a native module
  registered. A registry recovery contract and immediate Media registration now
  handle this case; a mobile Media reload rendered the native page correctly.
- Global search did not navigate to the War Room without a corresponding rail
  entry. The repaired search result opened `#war-room` in the browser.
- Closing global search could previously reopen it through restored focus. The
  checked close left the dialog closed, with focus returned to the search field.
- The empty media player displayed an unusable video rectangle and misleading
  source metadata. It now shows a labelled empty state until a source is loaded.
- Studio inherited near-white text on a cream editor. Its interface now uses
  explicit navy/cyan contrast; generated PDF page surfaces remain unchanged.

The repository previews are actual application captures, not concept mockups:

- [Home](screenshots/personal-home.png)
- [Studio](screenshots/personal-studio.png)
- [Income](screenshots/personal-income.png)
- [Media](screenshots/personal-media.png)

Empty records are intentional. No fake sales, projects, account connections,
agent activity or imported research were added to make the screenshots busier.

## Remaining boundaries

- The Mac wrapper is built and ad-hoc signed, not notarised or self-contained.
  It still uses this checkout and runtime. Interactive sleep/wake, offline,
  recovery and full desktop acceptance remain separate.
- No real Codex request, paid image generation, Google OAuth flow, microphone
  recording, social publication, payment or live trade was performed.
- Media playback controls and persistence are implemented, with isolated source
  and hand-off coverage. A real user-selected browser file and every browser
  codec/device combination have not been accepted end to end.
- OSINT is a local public/authorised-source casebook, not hidden-email discovery,
  private-account collection or automatic personal dossiers. Case data is not
  automatically encrypted.
- Provider subscriptions and API billing remain separate. Missing usage data
  remains unavailable; no universal combined allowance is claimed.
- The safety system was not armed against the real account during tests. It is
  an application boundary, not a Mac-wide lock or a guarantee of stopping remote
  work already submitted.
- GitHub publication uses the rebuild branch. Merging to `main`, a successful
  hosted CI run and an updated public Pages deployment are separate outcomes.

Use [BUILD-STATUS.md](BUILD-STATUS.md) for the full 60-item capability catalogue
and its explicit local/setup/partial boundaries.
