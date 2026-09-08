# U1 OS: Orbital Glass and media

The shared Orbital Glass layer extends the Home and startup identity to page headers,
panels, forms, dialogs, existing specialist tools, and Creative Studio. It does not
replace data handlers, provider content, record IDs, or credentials.

## Music and video

Media now includes a source library and a persistent in-tab player. A compact Now
playing widget is visible only after a real playback event, and disappears when
paused or finished. Progress comes from the actual player; no timer fabricates it.
Local audio and video are read through browser object URLs and never uploaded.
Video playback pauses before its player is hidden. YouTube pauses when the U1 tab
is hidden. Provider APIs load only after the user chooses a corresponding link.

- Spotify uses its official iframe API. Playback scope is the selected embed,
  not the desktop app, all devices, account library or Spotify Connect. The mini
  widget uses the actual playing URI where a track title is not supplied; the
  official embed displays Spotify's own metadata and controls.
- YouTube and YouTube Music track links use the visible YouTube iframe player.
  This is not an authenticated YouTube Music account integration or audio ripping.
- SoundCloud uses its official widget, including real title, creator and progress
  events. Creator restrictions and account requirements remain in force.
- Stremio is an external web-app launcher. It does not report playback telemetry
  to U1 OS. A future authorized bridge would be needed for that.
- HTTPS browser-compatible audio/video links are supported without a proxy.

Subscriptions and login sessions do not automatically grant cross-app access.
No screen scraping, DRM bypass, watermarks removal, paid requests or publishing
is part of this implementation. Browser and provider restrictions may prevent
particular tracks from playing; the UI reports errors rather than a false stream.

Provider symbols are lightweight recognizable SVG identifiers styled inside U1
glass containers. They do not imply provider endorsement or account connection.

## Primary references

- https://developer.spotify.com/documentation/embeds/references/iframe-api
- https://developers.soundcloud.com/docs/api/html5-widget
- https://developers.google.com/youtube/iframe_api_reference
- https://github.com/Stremio/stremio-web

## Targeted checks

`node --test tests/test_u1_media.mjs` covers parsing, provider boundaries and time
display. Browser checks are required for layout and live provider sessions;
automated URL tests do not prove account authorization or playable subscriptions.
