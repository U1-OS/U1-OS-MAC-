# Native Media and Research

This module owns only `utils/u1_media_research.py`, `static/js/u1-media-research.js`,
`static/css/u1-media-research.css`, `tests/test_u1_media_research.py`, and this document.
The parent owns the shell, navigation, script/style loading and server integration.

## Parent integration contract

1. Load `static/css/u1-media-research.css` with the shell's existing styles.
2. Load `static/js/u1-media-research.js` after `u1-core-workspaces.js`. It registers
   `media` and `osint` through `U1CoreViews.register(id, render)` immediately at
   script evaluation, before DOMContentLoaded router listeners run. Registration
   is idempotent and remains available as `U1MediaResearch.register()` if loading
   is deferred. A successful first registration dispatches the document event
   `u1:native-views-ready`, with `event.detail.ids` equal to `['media', 'osint']`.
   If the core registry itself loads later, dispatch `u1:core-views-ready` or call
   `U1MediaResearch.register()` explicitly after creating it.
3. Route `U1Platform.open('media')` and `U1Platform.open('osint')` into the native
   shell's corresponding view and `U1CoreViews.mount(id, host)`. No iframe or
   legacy platform dialog is needed. Native sidebar buttons use these same calls.
   Do not permanently mark a fallback placeholder as an already-mounted native
   view. On `u1:native-views-ready`, if the active route is in `detail.ids` and its
   host still contains a fallback, clear that host's fallback/cache marker and
   mount the newly registered native view. Route entry should also recheck
   `U1CoreViews.supports(id)` before reusing a cached fallback. Keep a successfully
   mounted native view intact; ordinary readiness or resize events should not
   replace its player, input fields or other active state.
4. Keep one persistent `#u1-player-mini` containing `#u1-local-media`. The module
   adopts that existing video element, displays it inside the Media view, and
   returns it to its original shelf on `U1MediaResearch.unmountMedia()`. Call
   this before replacing a Media host on navigation. A `body[data-u1-view]`
   observer provides a fallback, and opening OSINT also parks the player.
   If no player exists, the module creates the same IDs; initialise the shell's
   persistent shelf first to avoid duplicate IDs. Do not replace this video
   element when changing views. Browser autoplay rules may require pressing Play
   again after a DOM move. Selected playback and edit fields persist during view
   navigation, not a page reload. Managed files and research records survive reload.
5. In both server GET and POST dispatch, after the normal `gate_request`, and
   before generic workspace routing, import and call the following:

```python
from utils.u1_media_research import handle_request
if handle_request(self):
    return
```

The handler expects `path`, `command`, `headers`, `rfile`,
`integration_request_allowed()` and `send_json(payload, status=200)`. It returns
`False` for other routes, and handles only `/api/workspace/media-research`
(an optional trailing slash is accepted). The existing same-origin guard applies
to GET and POST. POST additionally compares `X-U1-CSRF` against
`utils.integrations_hub.CSRF_TOKEN`, requires JSON, and caps bodies at 65,536 bytes.
The browser obtains the token from the existing `/api/integrations` endpoint.

## Endpoint contracts

All successes contain `success: true`; validation failures contain `success: false`
and a friendly `error`. Validation returns 400, origin/CSRF failures 403, unsupported
methods 405, and local service failures 503. Query and action names are explicit.

| Request | Result or required fields |
| --- | --- |
| GET base endpoint | `capabilities`, case summaries, ready managed `media`, privacy notice |
| GET `?case_id=<id>` | Case and its full evidence trail |
| GET `?export=<id>` | Attributed casebook JSON download envelope |
| POST `case_save` | `title`, `scope` (`public`/`authorised`), `notes`, `authorised_confirmed: true`; updates also require `id`, `expected_updated` |
| POST `case_delete` | `id`, `expected_updated`; removes that case and its evidence |
| POST `evidence_save` | `case_id`, `title`, `source_url`, `note`, `label`; optional `observed_at`, `verification_note`; updates require `id`, `expected_updated` |
| POST `evidence_delete` | `case_id`, `id`, `expected_updated` |
| POST `inspect` | Managed `source_id`; returns FFmpeg duration and audio/video presence |
| POST `clip_export` | Managed `source_id`, numeric `clip_in`, `clip_out`, `format` (`mp4`/`wav`), `rights_confirmed: true` |
| POST `srt_export` | `captions`, `rights_confirmed: true`; optional `trim_to_clip: true` plus numeric clip range |

`expected_updated` is the exact `updated_at` string last read. Save responses return
the new timestamp. Evidence changes also update their parent case's timestamp.
Unknown IDs cannot create records through update actions. Verification defaults to
`unverified`; `verified` requires a written verification basis and remains the
author's assessment. URLs require HTTP(S), a hostname, and no credentials or
whitespace. They are stored as attribution and are never fetched by this backend.

Downloads contain `filename`, `mime`, `size` and base64 `content`. Clip downloads also
identify `engine: "FFmpeg"`, the executable provider, and selected clip times.
Case exports include source URLs, observation/creation/update timestamps, labels,
verification notes, export time and the privacy/verification notice.

## Local media and bounds

File selection immediately loads a browser object URL into the real native video
element. It can play audio or video formats supported by the browser. File name,
size, duration and video dimensions come from the selected file/browser metadata.
The user explicitly presses Play. Existing imported files are loaded through
`/api/workspace/prism/file?id=<id>`.

Import is an explicit action requiring the rights checkbox. It uses the existing
`/api/workspace/prism/upload-start` and `upload-chunk` endpoints, with base64 chunks
of at most 32,768 bytes, the returned source ID, and exact byte offsets. Progress
reports acknowledged bytes only. Source and output limits are 25 MiB. Interrupted
imports may leave incomplete managed uploads under the existing workspace's quota
policy; this module does not delete another component's files or change that policy.

Server exports accept only 32-character managed IDs referring to completed, live
workspace uploads. Files are opened relative to held directory descriptors using
`O_NOFOLLOW`, checked for regular-file status, exact size, and checksum. No client
path is accepted. The process works on a private temporary copy and deletes both
source copy and output when finished. Playlists and remote input URLs are rejected.
The demuxer is forced from a small local-media extension allowlist; FFmpeg input
protocols are limited to file/pipe and MOV external data references are disabled.

FFmpeg discovery checks system PATH and then calls `imageio_ffmpeg.get_ffmpeg_exe()`
from an already installed wheel. It does not download or install anything.
Availability means an executable was found; an actual export still checks whether
that binary supports the chosen codecs and source. No ffprobe dependency is needed.
The parent installed `imageio-ffmpeg==0.6.0` into `.runtime`. The Python wrapper is
BSD-licensed; the bundled FFmpeg executable has separate LGPL/GPL build terms.
The dependency and binary remain in the local runtime and are not vendored into
this repository. Review that binary's build/license terms before redistribution.

One FFmpeg operation runs at a time per server process. Inspection has a 4-second
timeout; rendering has a 12-second timeout. Processes use argument arrays without
a shell or inherited input, with at most 64 KiB of combined diagnostic output.
Processes are killed on timeout or log overflow. Output size is capped and a clip
that reaches the cap is rejected rather than handed back as an apparently complete
result. Export duration is at most 120 seconds and must fit within the source.

MP4 uses H.264/AAC, fits video inside 1280 x 720, and strips metadata/chapters;
WAV uses stereo 44.1 kHz PCM. Only the first selected video/audio streams are used.
There is no simulated render percentage: the UI names the active operation and
the backend only returns success after FFmpeg completes and produces a file.
Large, difficult or unsupported files may fail within the limit. SRT is a separate
sidecar, not burned into or muxed into the media. No automatic transcription runs.

Captions use plain SRT text, at most 48,000 characters and 500 ordered,
non-overlapping cues, within 24 hours. Optional clipping intersects cues with the
selected range, rebases timestamps to zero, and renumbers them. Browser preview
uses a local WebVTT track derived from the validated SRT.

## Research storage and limitations

`u1_mr_cases` and `u1_mr_evidence` are the module's only tables, created through
`prism_workspace.database()` inside `workspace.sqlite3`. There are at most 200 cases
and 100 evidence records per case. Case/evidence note limits are 8,000 characters;
verification notes are 1,200 characters. Observed timestamps are timezone-aware;
creation and update timestamps are generated in UTC by the server. Existing
workspace records, preferences, legacy casebook databases and OSINT services are
not changed or imported.

The public search control only builds a clearly labelled external DuckDuckGo link.
Clicking it sends the entered search to that external provider. No backend network
requests, RDAP lookup, hidden email discovery, private social dumps, automatic
person dossiers, subscription syncing, remote media download, DRM bypass or
watermark removal are implemented. Capabilities explicitly report these limits.
Local casebook storage is unencrypted; exported JSON contains the user's notes.

## Isolated validation

```sh
.runtime/bin/python -m unittest tests.test_u1_media_research -v
node --check static/js/u1-media-research.js
U1_MR_REAL_FFMPEG=1 .runtime/bin/python -m unittest tests.test_u1_media_research.SyntheticFFmpegTests -v
```

Tests patch the workspace data directory into a temporary directory, use synthetic
fixture bytes, and mock subprocesses and network access. They cover CRUD, concurrent
edit conflicts, cross-case isolation, limits, attribution export, CSRF/origin/body
guards, unsafe sources, symlinks, checksums, time/caption validation, process timeout,
bounded logs, failed exports and installed-wheel discovery. Mocked media fixtures
prove contracts and safety behavior; they do not prove real codec/render output.
The opt-in real test generates its own one-second colour/sine-wave video in a
temporary directory, imports it into an isolated workspace, performs actual MP4
and WAV exports, verifies WAV duration and decodes both outputs with FFmpeg.
This fixture is synthetic test material, never app demo content. The parent owns
the integrated browser, persistent-player navigation and live server smoke test
after shell wiring.
