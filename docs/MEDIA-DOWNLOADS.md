# Media intake and download boundaries

Implemented: local validation of a user-supplied direct YouTube, Instagram or
TikTok post URL, explicit rights/public-unprotected confirmations, canonical
source attribution, an exportable JSON review, official-help links, and a native
Media Studio handoff for an authorised local original.

**Direct media downloading is not implemented or enabled.** Neither the
`yt_dlp` module in `.runtime` nor a `yt-dlp` executable on PATH was detected on
2026-09-08. No dependency was installed. Even if installed later, downloading
remains disabled until its network and file boundaries are implemented and tested.
This UI must not be described as a functioning YouTube/Instagram/TikTok downloader.

## Parent wiring and API

Owned files: `utils/u1_media_download.py`, `static/js/u1-media-download.js`,
`tests/test_u1_media_download.py`, and this document. Load the script after the
native core registry with existing `u1-media-research.css`. Native view ID is
`media-downloads`, labelled Source intake, registered immediately with the standard
`u1:native-views-ready` event. `U1MediaDownload.register()` and `mount(host)` are
available. The original-file button calls `U1Platform.open('media')`.

Call `utils.u1_media_download.handle_request(handler)` after the parent Safety
gate and before generic routing for GET and POST. The exact endpoint is
`/api/workspace/media-download`; there are no jobs, URL query parameters or nested
execution routes. GET returns actual dependency detection and explicit disabled
capabilities. POST requires same origin, `X-U1-CSRF`, JSON of at most 8192 bytes,
and only these fields:

```json
{
  "action": "review_source",
  "url": "https://youtu.be/AbCdEfG1234",
  "rights_confirmed": true,
  "public_unprotected_confirmed": true
}
```

The URL above is a synthetic format fixture, not a requested or downloaded video.
`export_manifest` accepts the same fields and returns base64 JSON, not media.
Unknown options including cookies, headers, proxies, paths and watermark removal
are rejected. Requested download/execution actions return an explicit 501 error.
Review states distinguish the user's confirmation from independently verified
rights, public availability, quality or download success. Nothing is fetched or
persisted server-side; the user can explicitly download their review as JSON.

## URL, quality and watermark policy

Only HTTPS and exact provider hostnames are accepted. Post-specific path shapes
are required. IP addresses, localhost, lookalike hosts, credentials, nonstandard
ports, backslashes, percent-encoded paths, fragments, profiles, playlists, arbitrary
redirect endpoints and shortened TikTok links are rejected. Permitted tracking
parameters are discarded during canonicalisation. No DNS resolution or redirect
expansion occurs, so no attacker-controlled network request is made.

User confirmation cannot prove that a post is public or downloadable; the response
labels that distinction. Official export options determine available quality.
Use the best authorised original within the existing 25 MiB local import limit;
there is no promise of 4K, a measured resolution, or automatic quality selection.
Existing Media Studio can render bounded local clips and separate SRT captions.

Third-party creator/platform watermarks are preserved. This module does not strip,
obscure or inpaint them. An unwatermarked source should be the user's own original
file. No crop editor or watermark-removal functionality is claimed.

## Official guidance reviewed

- [YouTube: download videos you uploaded](https://support.google.com/youtube/answer/56100?hl=en) describes YouTube Studio downloads and Google Takeout for a creator's own uploads; the download options do not guarantee original or 4K quality.
- [YouTube offline downloads](https://support.google.com/youtube/answer/7381437?hl=en) distinguishes in-app offline viewing from reusable local media files.
- [TikTok: download content](https://support.tiktok.com/en/using-tiktok/exploring-videos/video-downloads) describes Save video when the creator allows it, and keeping a local copy before posting. Its indexed official text was available; direct retrieval was blocked by robots.
- [Instagram Help Center](https://help.instagram.com/) is an official handoff only. The attempted export-help page returned HTTP 429, so current Instagram export steps were not verified or invented.
- [yt-dlp upstream documentation](https://github.com/yt-dlp/yt-dlp) documents extractor selection, configuration/plugin controls, download limits, external helpers and format selection. Availability of those options alone is not proof of safe network isolation.

## Work required before enabling direct downloads

Parent approval is needed before adding the missing dependency. A future executor
also needs a tested boundary covering every request, redirect and media/CDN URL,
including DNS rebinding, IPv4/IPv6 local/link-local/private ranges and protocol
restrictions. Checking only the user's initial provider hostname is insufficient.
Pin a reviewed extractor set; disable generic extractors, plugins, configuration,
cookies, account credentials, external downloader hooks and private/DRM content.

Use an owned cancellable process, a managed temporary output directory, strict
file-count/25 MiB output limits, measured timeouts, no playlists, bounded logs and
actual format selection within budgets. Reject encrypted/authenticated or unknown
sources instead of bypassing access controls. Test all egress and output limits
with synthetic/mocked sources before any authorised live download. This is planned
work, not a feature silently waiting to activate when yt-dlp is installed.

## Tests

```sh
.runtime/bin/python -m unittest tests.test_u1_media_download -v
node --check static/js/u1-media-download.js
```

Fixtures validate canonicalisation, rights confirmation, SSRF-shaped inputs,
profiles/playlists/redirects, request/CSRF limits, manifest honesty and the invariant
that dependency presence does not enable downloads. Network resolution, requests
and subprocess launches are mocked to fail if attempted. No real media, account,
browser-cookie or paid action is performed.
