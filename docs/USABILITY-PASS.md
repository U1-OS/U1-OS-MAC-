# Bounded native chrome accessibility pass

Owned files: static/js/u1-operational-polish.js, static/css/u1-operational-polish.css,
tests/test_u1_operational_polish.cjs and this document. Parent wires CSS and classic JS after
the native operations/media chrome scripts. JS self-installs on DOM ready and observes late chrome.
No routes, shared shell files, provider/usage code, Git or shared browser are touched.

## Confirmed small fixes

- The actual runtime button #u1-control-open[data-platform="controls"] receives aria-label="Control Centre"
  regardless of its parent container; rail/utility shelf controls retain the same correction.
  The existing coalesced child-list observer handles late creation and replacement. A separate observer
  watches only the current runtime button's aria-label and schedules repair only if the value is wrong
  or removed. It disconnects on replacement/removal and teardown. Correct writes do not schedule more work.
  Visual markup and click handlers are preserved; the combined ControlControl Centre accessible name is replaced.
- The existing u1-player-entry remains the canonical Media entry only when present, visible and enabled.
  Redundant Media navigation buttons in the utility shelf/player mini are hidden with restored prior
  accessibility state when that primary entry is unavailable. Other Media navigation elsewhere stays intact.
- The actual video element is never created, moved, removed, played, paused, loaded or cleared by this script.
  Player labels reflect source presence, paused/playing/loading/ended/error state without showing private filenames.
- Current rail/dock routes receive aria-current="page" for exact data-go matches.
- Closing a mobile menu returns focus only when it would otherwise remain in the newly closed rail.
  Desktop, active dialogs, locked safety state and intentionally moved outside focus are excluded.
- Scoped cyan focus indicators and 44px mobile chrome targets augment the existing navy/cyan design.
  Disabled native buttons use not-allowed; explicitly busy regions use progress. No state is re-enabled.
  No animation is introduced; reduced-motion/forced-colors support is preserved without changing saved preferences.

## Evidence boundary

Source audit used native operations, shell/cinematic menu behavior and the existing Media/Research player contract.
DOM fixtures cover accessible names, current route, actual source/label states, duplicate restoration,
player identity/playback preservation, mobile focus, focus exclusions, idempotent listeners, cleanup
and unchanged loading/disabled/motion values. Run: node --test tests/test_u1_operational_polish.cjs.
Fixtures are targeted contracts, not a full browser or accessibility-tree implementation.

The confirmed duplicate-hiding observer defect is corrected: hidden is assigned only when the
button is not already hidden. A focused regression fixture models an attribute mutation on every
hidden setter call, drains the queued refresh and asserts that no further writes or animation
frames are scheduled. This tests observer convergence without running the shared browser.

Runtime Control Centre regressions use the real u1-control-open ID outside the original selector
containers, create the button after installation, replace it, remove/overwrite its label and check
changed-only convergence, unrelated-label exclusion and observer teardown. These address the parent's
confirmed 390x844 browser defect; the parent still owns the post-fix browser accessibility-tree check.

Still manual: VoiceOver names/order, keyboard traversal and Escape across actual mobile menus/dialogs;
phone-width wrapping/zoom and touch reach; CSS computed contrast and focus clipping; actual media import,
play/pause/seek, persistent playback across navigation and duplicate visibility at each breakpoint;
screen sharing/private filename exposure in other components; system and saved reduced motion;
offline/retry interaction and server-gated disabled states. Parent owns live-browser acceptance/screenshots.
This pass does not claim all accessibility criteria, all mobile browsers or all 60 build items are tested.
