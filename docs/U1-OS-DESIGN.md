# U1 OS: Orbital Glass

The product name is **U1 OS**. "Your world. Amplified." remains the supporting tagline. The older internal `prism` module names, routes, and data directory are implementation identifiers, not the product name. They are intentionally retained to avoid breaking saved records or integrations.

## Identity

The original U1 monogram combines a faceted cyan U with a silver-blue number one. The angular lower bowl suggests a protective workspace, while the upright one gives the identity a clear reading at icon sizes. It is not derived from a provider logo.

- Transparent vector mark: `static/assets/u1-logo.svg`.
- Dark rounded app-icon variant: `static/assets/u1-app-icon.svg`.
- Horizontal wordmark: `static/assets/u1-wordmark.svg`.
- The favicon and desktop shell use the same geometry.

## Interface direction

The supplied reference informs the overall composition: a compact left navigation, luminous search field, central Earth, four provider cards, project/system/storage panels, right-hand daily overview, and floating dock. The design uses near-black navy, icy blue text, electric cyan edges, and restrained provider-specific orange and violet accents.

`static/css/u1-reference.css` contains the reference-led identity refinements. `static/css/prism-os.css` retains the base components and responsive behavior. New cards use the shared system instead of arbitrary visual treatments.

The background landscape is an original AI-generated decorative asset, stored locally as `static/assets/u1-landscape.png`. It is artwork, not a photograph of a location or a live feed.

The globe is rendered in WebGL by `static/js/u1-globe.js`, combining the existing archived daytime texture with NASA's 2016 Black Marble night-light map. Its rotation and lighting are decorative; no claim of live satellite imagery or current city-light observations is made. Reduced-motion preferences freeze the animation. Rendering is suspended while offscreen or hidden.

Night texture source: NASA Earth Observatory, **Earth at Night/Black Marble: Flat Maps**, 2016 Color, 3600 x 1800:
https://science.nasa.gov/earth/earth-observatory/earth-at-night/maps/

Daytime image attribution and licensing, backend architecture, local-data limits, and account-access boundaries are documented in `docs/PRISM-OS.md`.

## Truthful presentation

The reference contains illustrative progress values, appointments, storage usage, music, and connection badges. These are not seeded into the working app. Live data is shown only when returned by a real reader; unavailable services remain visibly unconfigured. Local imported files are labeled separately from Google Drive data.

## Verification scope

The initial workspace pass passed 13 isolated backend tests. Browser checks covered project creation, note creation and content search with Command-K, task completion, local calendar creation, recoverable deletion/restoration, local file import, and download preparation. The final downloaded browser file was not independently verified in this pass. Retained specialist integrations still need their own authorization and end-to-end checks.

This visual pass does not sign/notarize a native macOS app or publish source to GitHub. It does not implement the separately requested Instagram curator, automatic likes/saves collection, watermark removal, or automatic reposting.

## Local autopilot

U1 now runs a local, metadata-only autopilot while its server is running. It generates a daily local briefing, emits deduplicated due-task and upcoming-event reminders, and reports high disk usage. Each routine can be paused independently in Automation. This is deterministic local automation, not a paid AI model or an Instagram/Gmail integration.

Posting, messaging, paid AI requests, trading/payments, software installation and permanent deletion are not executable actions in this agent. The existing live-feed readers retain their own real refresh schedules and setup requirements. The local engine stops when the Mac or U1 server stops.

## Startup, notification audio, and icon motion

The U1 startup screen appears once per browser session, reports actual interface/local-server readiness, and can be skipped. It has no invented completion percentage. Preview it from Settings, under Sound, motion & startup.

Notification tones are generated locally with Web Audio. Browser rules require a user interaction before sound can play. Sound, volume, icon motion, and startup preferences are browser-local settings; system reduced-motion preferences take precedence. Initial notification history is silent, and repeated sounds are throttled. BTC, ETH, and SOL receive distinct decorative currency identifiers in the existing live bar; these do not imply fresh quotes or a trading connection. Competition/team imagery remains dependent on the actual sports provider and is not fabricated.
