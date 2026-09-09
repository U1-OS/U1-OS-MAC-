# Rounded U1 system

The visual refresh preserves the existing U1 identity and real data boundaries.
It adds a shared token bridge, softer cards and controls, and three widget
themes: **Orbit**, **Graphite**, and **Daylight**. Existing account status and
brand logos are not replaced with invented connected states or arbitrary marks.

Appearance preferences are browser-local, allowlisted, and versioned under
`u1.rounded.preferences.v1`. Storage failure applies changes for the current
session and reports that they were not saved. Spacing, corner radius and glow
can be adjusted without changing workspace data. Reduced-motion settings still
take priority over decorative animation.

## Startup

The startup screen is a rounded two-panel composition using the existing U1
SVG, CSS decoration, and actual local readiness results. Account verification
remains a separate state. Enter and Escape let the operator dismiss it; a
bounded timeout leaves the workspace accessible if checks are unavailable.

Each startup has a generation identifier. Old requests cannot overwrite a newer
preview or close it, and completion is emitted once. The shell becomes inert
during startup, focus stays inside the startup dialog, and dismissal preserves
an active Safety lock. Reopening a preview preserves its original return focus.

Startup audio uses a short synthesized tone from the existing `U1Feedback`
engine. It is opt-in, obeys interface mute/volume, and never blocks loading.
The explicit one-off tone preview does not change preferences. Browsers may
require a user gesture before audio is allowed. There are no external audio
requests, continuous sound loops, microphone permissions or new dependencies.

## Integration

- Assets: `static/css/u1-rounded-system.css` and `static/js/u1-rounded-system.js`.
- Native view: `appearance`; existing Settings remain accessible separately.
- Public API: `U1Rounded.preferences`, `save`, `apply`, `render`.
- Core registration supports the optional activation hook without requiring it.
- Audio preference changes emit `u1:audio-preferences` for the shell mute control.
- Create/Earn widgets consume the `--u1r-*` theme tokens.

The isolated test module is `tests/test_u1_rounded_system.cjs`. Browser and
integrated-release acceptance must be reported separately from these contracts.
