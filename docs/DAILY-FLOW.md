# Start my day

An additive native daily overview and Home preview. It reads existing local
snapshots, preserves the operator's priority positions, and links to the
existing editing/review tools. It performs no writes, account reads, Google
syncs, email inference, appointment creation, automatic ranking or automation.

## Owned files

- `static/js/u1-daily-flow.js`
- `static/css/u1-daily-flow.css`
- `tests/test_u1_daily_flow.cjs`
- `docs/DAILY-FLOW.md`

No previous personal-workflow files or other shared files are changed. No
backend addition is required.

## Parent integration contract

Load the stylesheet and script after `U1Data` and `U1CoreViews`. The script
registers **`daily`** only. Parent native navigation and search should expose
`daily` as **Start my day**. Metadata is available at
`U1DailyFlow.meta.daily`. The parent owns the shell's route/search registration.

`U1DailyFlow.install()` is idempotent and can be called after late-loaded
dependencies. `U1DailyFlow.attachHome()` adds one section with ID
`u1-daily-flow-home` to `#v-home`; it never replaces existing Home content or
adds rail links. If the parent creates Home later, call `attachHome(homeNode)`.
The normal body `data-u1-view` navigation observer also attempts attachment
when Home/daily becomes visible. The Home entry uses `data-go="daily"`.

| Destination | Existing navigation contract |
| --- | --- |
| Start my day | `data-go="daily"` |
| My Day / editing priorities / time blocks | `data-go="life"` |
| Native Calendar | `data-go="calendar"` |
| Native Tasks | `data-go="tasks"` |
| Actual source review queue | `data-platform="drafts"` |
| Actual daily brief | `data-platform="briefing"` |
| Google connection setup | `data-go="integrations"` |
| Safety controls | `data-go="security"` |

The review queue and briefing intentionally use their existing platform
modals. They do not navigate to invented native routes or to the Business
alias. Opening a modal is an explicit operator action, not a startup effect.

## Sources and date handling

Only these requests are issued, using `U1Data.get(path, {fresh: true})`:

```text
GET /api/workspace/prism/summary
GET /api/workspace/personal?collection=today&day=YYYY-MM-DD&kind=priority&limit=3
```

The existing personal API supports the collection/day/kind/limit filters and
returns `today`, `timezone`, `generated_at` and records. The PRISM response
provides `profile.timezone` and canonical `task`/`event` records. There are no
new subpaths, POST actions or integration/Google/briefing API reads here.

The first requests run together. The initial query uses the last known
workspace timezone, otherwise the device timezone. Before rendering results,
the flow reconciles the date with the personal server's `today` and workspace
timezone, falling back to PRISM's profile when necessary. It rereads priorities
for the authoritative date if the initial device date differs. A second date
rollover during this correction is reported as unavailable and needs refresh.
No priorities from the wrong day are shown as today's priorities. If neither
source supplies a valid timezone, the device-date fallback is explicitly
labelled.

Top-three positions come from `payload.slot`, with no automatic selection,
ranking or reassignment. Completed priorities keep their slots. Missing data
is distinguished from a successfully returned empty list. Invalid or duplicate
slots produce a source warning instead of silently choosing new priorities.

Local calendar entries use workspace-timezone dates and chronological order.
Events continuing into today are included; an event ending exactly at today's
midnight is excluded. Offsetless legacy event times are explicitly labelled
as workspace local time. Invalid dates/times are omitted with a warning.
No Google calendar state is inferred from the local snapshot.

Open tasks retain the order returned by PRISM; the operator may switch from
all open tasks to tasks due today. Completed/deleted tasks are excluded.
Display bounds are eight tasks and twenty events, with counts and links to
their source workspaces. PRISM's existing response limit is 1,000 records;
the view does not claim completeness beyond that returned snapshot.

Both the Home preview and daily view label local source names, retrieval times,
available source timestamps and source-declared staleness. A fresh local read
does not assert that an external account or calendar is current. Failures show
unavailable states, retain the independently available source and offer manual
refresh/navigation. Google email is described as requiring an authorised
connection and successful sync; this component never checks account status.

## Cohesive flow

1. **Focus:** review actual top-three priorities and saved open tasks; edit in
   My Day or Tasks.
2. **Schedule:** review today's actual local calendar and open native Calendar
   or My Day to make changes.
3. **Review:** open the actual source review queue or daily brief when ready,
   or visit Connections for authorised Google setup.

Back/Continue controls and numbered step buttons work with native keyboard
navigation. Step selection is transient UI state, not a saved completion score
or claim that the operator reviewed a source. The final action continues into
My Day. There are no seeded priorities, tasks, messages or appointments.

Home and daily share one in-flight local read. Refresh occurs on explicit
refresh, view entry, returning to a visible page, relevant local data changes
and safety unlock while visible. There is no interval or background account
polling. Safety-lock events clear cached records and visible private content;
generation checks discard pending responses after lock or invalidation. The
parent remains responsible for the server safety gate and initial lock state.

## Styling and isolated tests

All CSS is scoped to `.u1-daily-flow`. Navy surfaces, cyan actions, explicit
light text, visible keyboard focus, 44-pixel controls, responsive grids,
reduced-motion support and forced-colors support match the existing shell.
The test checks core muted-text and primary-button color-pair contrast against
the WCAG AA 4.5:1 threshold; this is not a whole-page accessibility audit.

```sh
node --test tests/test_u1_daily_flow.cjs
node --check static/js/u1-daily-flow.js
```

Tests evaluate the script against a small isolated DOM fixture, stubbed local
responses and a fixed clock. They do not access the real backend, browser,
production database or any account. Coverage includes additive Home mounting,
native/modal link contracts, correct-day refetch, actual priority order,
calendar boundaries, source failures, escaping, task filters, source labels,
in-flight deduplication and safety invalidation.

Full-shell navigation, platform modal behavior, responsive browser rendering
and screen-reader usability require the parent's integrated validation. This
increment does not alter or certify the rest of the 60-item release.

Component validation on 2026-09-08: all 16 isolated Node tests passed, with
zero failures, and `node --check static/js/u1-daily-flow.js` passed. Only
fixtures were used; no real user data or shared browser was accessed.
