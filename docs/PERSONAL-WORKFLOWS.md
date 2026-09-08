# U1 OS personal, business and manual market workflows

This increment implements the assigned personal/day/business/market capability
groups of the approved 60-item release. It does not certify the other release
items or invent numeric roadmap IDs that were not supplied to this component.
There is no seeded business, personal, market or financial data.

## Ownership and integration

Only these five files belong to this increment:

- `utils/u1_personal_core.py`
- `static/js/u1-personal-workspaces.js`
- `static/css/u1-personal-workspaces.css`
- `tests/test_u1_personal_core.py`
- `docs/PERSONAL-WORKFLOWS.md`

The parent owns handler dispatch, script/style inclusion and navigation. Load
the script after `u1-data.js`, `u1-core-workspaces.js` and `u1-life-studio.js`.
It registers `life`, `income` and `research` through `U1CoreViews.register`.
`U1PersonalViews.install()` can be called explicitly after those dependencies
are ready. It does not register Studio, AI, Crypto, Trading, Media, OSINT or
Business, rewrite the rail, inject an iframe or replace another agent's views.
`data-go` links keep the three destinations connected. Tabs provide eleven
internal collections without adding rail links. Parent navigation must support
the `research` route, reached through `data-go="research"`. The actual manual
ledger uses `data-platform="business"`, handled by the existing
`U1Platform.open('business')` modal. It must not use `data-go="business"`,
because the parent's Business route aliases Income and would loop back here.

Dispatch only after the parent's existing safety gate:

```python
if not u1_safety.gate_request(self):
    return
if u1_personal_core.handle_request(self):
    return
# Continue the parent's remaining handlers.
```

`handle_request` returns `True` after responding and `False` for unrelated
paths. It additionally requires `handler.integration_request_allowed()` for
all its requests and checks `X-U1-CSRF` against the current
`integrations_hub.CSRF_TOKEN` for POST. The parent supplies the existing
same-origin/loopback checker and HTTP socket timeouts. Missing origin-check
support fails closed. The module does not import or start the legacy workspace
hub, background agents, live providers or account adapters.

The UI calls `U1Data.get/post`. Source panels consume existing
`/api/workspace/prism/summary` and `/api/workspace/business` snapshots. The
operator can request `/api/workspace/live/crypto` from the observation dialog.
The existing adapter owns any provider connection. This module never calls a
provider directly. Personal persistence succeeds independently of optional
ledger/calendar source-panel availability.

## Roadmap capability mapping

| Approved scope | Concrete implementation | Boundary |
| --- | --- | --- |
| Today priorities | Date-specific top-three slots, complete/reopen, task links | Exactly three active slots per date; completion keeps its slot |
| Time planning | Editable date/start/end blocks with calendar links | Workspace timezone; same-day blocks; local overlaps rejected |
| Household bills/renewals | Payee, due date, planned amount/currency, recurrence and paid/cancelled notes | Recurrence is an editable plan; no payments, automatic advancement or reminders |
| Simple wellbeing habits | Flexible/daily/weekly rhythm, cue, dated check-ins and undo | No streak penalties, missed-day scores or health advice |
| Product catalogue | Status, audience, outcome, version labels and actual local file links | Version metadata; binaries stay in PRISM Files |
| Launch workflow | Product-linked Backlog/Doing/Review/Done board | Operator managed; no storefront or publishing |
| Opportunities | Hypothesis, evidence/source/date, confidence and next research step | Operator assessment; validated requires evidence |
| Clients/offers/projects/notes | Linked contact records, scoped offers, delivery projects and contextual notes | No outgoing contact, payment, signature or CRM sync |
| Pricing assumptions | Decimal worksheet for sales, costs, fees, labour, result and break-even | Estimates only, never actual revenue or guaranteed demand |
| Social/content calendar | Dated/channel-specific drafts and operator-recorded published links | No social login, scheduled posting or automatic publishing |
| Faceless video workflow | Script, storyboard, asset/voice/caption plans, rights/content review and production stages | Operator-written drafts; no generation, rendering or distribution |
| Market watchlists | Instrument/currency/thesis/source/observation records | Manual paper research, not a research agent |
| Threshold checks | On-demand evaluation against reviewed timestamped observations, crossing deduplication and bounded evidence | No background monitor, push notification or trade trigger |
| Trading journal | Manual paper rationale, risk, assumed prices, direction and review | Closed-entry paper outcome only; separate from simulator and actual ledger |
| Local paper trading | Explicit simulated buys/sells, separate accounts, cash, holdings, weighted cost and realized outcomes | Long-only; no margin, broker, wallet, live execution or unrealized valuation |
| Record lifecycle | Validated create/read/update/archive/restore/delete, search, pagination and JSON export | Paper fill history is immutable; linked records cannot be deleted |

Automated strategy evaluation, backtesting and autonomous research agents are
**unavailable**. Static forms are not described as research agents. Media and
OSINT are owned by a separate component and are not implemented here.

## Storage, bounds and concurrency

All persistence uses `prism_workspace.database()`, hence the same
`workspace.DATA / "workspace.sqlite3"` database and owner-only permissions.
The module creates only `personal_records`, `personal_paper_trades` and their
indexes. PRISM `records`, `files`, `preferences`, existing business-ledger
entries and other agents' tables are not changed. Reads inspect canonical
records and file metadata for references. No browser storage is used for saved
planning data. Unsaved edits live only in the open editor.

- At most 2,000 planning records including archived items, and 300 per kind.
- At most 24 KiB serialized payload per record and 16 MiB total planning
  titles/payloads. These are logical content limits, not a physical SQLite
  database-file quota; SQLite pages, indexes and unrelated modules are separate.
- At most 1,000 immutable simulated fills across all accounts, separately
  bounded from planning payload storage. No fill history is silently evicted.
- At most 366 check-in dates per habit. Additional dates are rejected; the
  operator can export and remove old check-ins or create a new habit record.
- At most 20 evidence entries and 20 version-file entries per record.
- Thresholds retain their latest 20 evaluations and a bounded crossing count.
- POST accepts 1 byte through 64 KiB of JSON. Transfer encoding, duplicate JSON
  keys, unknown action/record fields, nonfinite numbers and oversized bodies
  are rejected. Query strings are bounded to 2,048 characters and 12 fields.
- Snapshot pages default to 100 records, maximum 200, with explicit counts,
  offsets and `has_more`. Reference options are bounded to the store limits.

`BEGIN IMMEDIATE` serializes mutations across SQLite connections/processes;
the existing workspace lock serializes threads. Every change requires the
positive integer `expected_version` last read from a snapshot. The database
also compares the version in updates. A stale edit returns HTTP 409 and never
overwrites the current version. The editor retains input and offers an explicit
load-latest action. Concurrent priority allocation is additionally protected
by a partial unique index on active day/slot.

Archive is reversible. Restoring rechecks slot/time constraints. Existing
historical references can remain while editing; new references must select an
active record of the correct type or a ready local file. Permanent deletion
requires an archived record, current version and `confirmed: true`, and is
blocked while any active or archived planning record still references it.
Paper accounts with fills can be archived and exported but never deleted by
this module.

## API

| Request | Behavior |
| --- | --- |
| `GET /api/workspace/personal` | Paginated snapshot, schemas, references, limits, source timestamps and paper summaries |
| `GET /api/workspace/personal/snapshot` | Same snapshot |
| `GET /api/workspace/personal/export` | Bounded JSON export, defaulting to active and archived records and all paper fills |
| `POST /api/workspace/personal` | One bounded versioned action |

Snapshot/export filters: `id`, `collection`, `kind`, `q`, `archived`
(`active`, `archived`, `all`), and `day`. `limit` and `offset` apply only to
snapshots. `day` filters priority, time-block and journal dates. Content
calendar dates remain in `scheduled_on` and are grouped in the native view.
Search matches titles and JSON payload text using Unicode casefolding;
percent and underscore are literal, not wildcard operators. Paper summaries
and immutable fill history cover all accounts even in filtered snapshots or
exports, as indicated by their separate response fields.

```json
{"action":"create","kind":"priority","title":"Finish the outline","payload":{"day":"2026-09-08","slot":1,"done":false,"notes":"A focused first step"}}
```

```json
{"action":"update","id":"<32-character lowercase hex id>","expected_version":1,"payload":{"done":true}}
```

Updates are patches: omitted title and payload fields retain their saved
values. Nested lists replace the corresponding list and validate each entry.
Kind, IDs, creation time, archive flags, estimates, check-in arrays, threshold
histories, paper cash and fill results cannot be assigned through ordinary
updates. Required version fields accept integers, never booleans or strings.

```json
{"action":"archive","id":"<record id>","expected_version":2}
```

```json
{"action":"restore","id":"<record id>","expected_version":3}
```

```json
{"action":"delete","id":"<archived record id>","expected_version":4,"confirmed":true}
```

```json
{"action":"habit_checkin","id":"<habit id>","expected_version":1,"day":"2026-09-08","checked":true}
```

Responses use `success`. Mutations normally return `record`, `id`, `version`.
Invalid input is HTTP 400, stale versions/constraints HTTP 409, missing records
HTTP 404, origin/CSRF denial HTTP 403, unavailable storage HTTP 503. Malformed
body length, unsupported content type and unsupported method use 411/413,
415 and 405 respectively. Responses are `no-store`, JSON, `nosniff` and close
the connection. Storage exceptions do not expose local paths or credentials.

## Record fields

Each planning record has server-assigned `id`, `kind`, `title`, `payload`,
integer `version`, boolean `archived`, and Unix-second `created`/`updated`.
Titles contain 1-160 trimmed characters. The snapshot's `schemas` object is
the authoritative machine-readable field/label/required/default/bounds
contract used by the forms.

| Kind | Editable payload fields |
| --- | --- |
| `priority` | `day`, `slot` (1-3), `done`, `task_id`, `notes` |
| `time_block` | `day`, `start`, `end` (HH:MM), `event_id`, `notes` |
| `bill` | `category` (bill/renewal), `payee`, `due`, `amount`, `currency`, `recurrence`, `status`, `notes` |
| `habit` | `cadence`, `cue`, `notes`; server-managed `checkins` via the dedicated action |
| `product` | `status`, `audience`, `description`, `current_version`, `release_date`, `project_id`, `versions`, `notes` |
| `launch` | `product_id`, `status`, `due`, `notes` |
| `opportunity` | `status`, `hypothesis`, `confidence`, `next_action`, `evidence`, `notes` |
| `contact` | `organization`, `role`, `email`, `phone`, `status`, `notes`; contact name is the record title |
| `offer` | `contact_id`, `product_id`, `status`, `scope`, `outcome`, `price`, `currency`, `assumptions`, `notes` |
| `client_project` | `contact_id`, `offer_id`, `project_id`, `status`, `due`, `deliverables`, `next_action`, `notes` |
| `note` | `parent_id`, `tag`, `text` |
| `pricing` | `product_id`, `currency`, `unit_price`, `unit_cost`, `fixed_cost`, `units`, `hours`, `hourly_rate`, `fee_percent`, `assumptions` |
| `content` | `channel`, `status`, `scheduled_on`, `scheduled_time`, `copy`, `cta`, `published_url`, `notes` |
| `video` | `content_id`, `status`, `hook`, `script`, `shot_list`, `voice_notes`, `asset_notes`, `file_id`, `rights_reviewed`, `content_reviewed` |
| `watchlist` | `symbol`, `asset_type`, `currency`, `status`, `thesis`, `source_url`, `observed_on`, `notes` |
| `alert` | `watch_id`, `condition` (above/below), `threshold`, `status` (draft/configured/paused), `notes`; server-managed evaluation history/count |
| `journal` | `watch_id`, `symbol`, `currency`, `side`, `status`, `day`, `entry_price`, `exit_price`, `quantity`, `fees`, `closed_on`, `thesis`, `risk_plan`, `review` |
| `paper_account` | `currency`, `starting_cash`, `status`, `notes`; initial funding/currency lock after the first simulated fill |

`versions` entries contain `version`, `file_id`, `notes`. Several files can
share a version label; an identical version/file pair cannot repeat. When
files are linked, `current_version` must match a version label. File references
must identify real ready PRISM files, not a path, remote asset or fictitious
filename. Imports/downloads remain the responsibility of the Files workspace.

`evidence` entries contain required `source`, `observed_on`, `note` and an
optional `url`. Validated opportunities require at least one evidence entry.
URLs allow HTTP(S) with no credentials; no URL is fetched by the backend.
Structured fields reject unknown keys rather than silently dropping them.
User content is HTML-escaped in every native display/form.

Amounts are decimal **strings** without exponent notation. Monetary inputs
allow two decimal places; instrument prices and quantities allow eight. Most
amounts are bounded to 1,000,000,000; fees to 100 percent; worksheet unit counts
to 1,000,000. Currency codes are three uppercase letters and are never
automatically combined or converted. This release uses two-decimal settlement
for the paper cash model even for currency labels with other market conventions.

Dates use YYYY-MM-DD and real calendar validation. Daily planning uses the
saved workspace timezone, defaulting to Australia/Melbourne. Observation
dialogs label their datetime inputs as device-local and send Unix timestamps.

## Pricing and journal calculations

Pricing uses Python Decimal, not browser arithmetic:

```text
assumed_sales = unit_price * units
assumed_fees = assumed_sales * fee_percent / 100
assumed_labour = hours * hourly_rate
assumed_costs = unit_cost * units + fixed_cost + assumed_labour + assumed_fees
estimated_result = assumed_sales - assumed_costs
unit_contribution = unit_price * (1 - fee_percent / 100) - unit_cost
break_even_units = ceil((fixed_cost + assumed_labour) / unit_contribution)
```

Break-even is `null` if unit contribution is not positive. Display amounts
round half up to two decimals. Taxes, refunds, demand, revenue recognition and
exchange rates are not inferred. These outputs carry
`basis: manual_assumptions_only` and never change the business ledger.

A closed journal entry needs an exit price and a valid close date. Its separate
manual paper result is `(exit - entry) * quantity * direction - fees`, where
direction is +1 for long and -1 for short. This journal arithmetic does not
create simulator holdings or orders. The paper simulator itself is long-only.

## Explicit local paper trading

Create an empty scenario through the Paper trading tab, entering a title,
currency and simulated starting cash. No account or starting balance exists
until the operator saves one. A buy/sell dialog requires the operator's review
checkbox and a source-labelled observation:

```json
{
  "action": "paper_trade",
  "id": "<paper account id>",
  "expected_version": 1,
  "side": "buy",
  "quantity": "2",
  "fees": "1.00",
  "reviewed": true,
  "quote": {
    "symbol": "BTC",
    "currency": "AUD",
    "price": "100.00",
    "observed_at": 1788825600,
    "source": "Operator-reviewed observation",
    "basis": "manual"
  }
}
```

The example timestamp is illustrative; supply an actual observation within
the last 900 seconds. More than 30 seconds in the future is rejected. Both
`manual` and `snapshot` observations require this freshness and explicit review.
Existing crypto-adapter snapshots can populate the dialog only when the
adapter supplies a recent numeric `fetched_at`, is not marked stale, and a
quote matches the paper account currency (and watch symbol for thresholds).
That timestamp is labelled as the adapter fetch time, not an exchange trade
timestamp. The server validates the supplied observation but does not
authenticate it with a provider; it remains an operator-reviewed simulation.

A buy debits rounded notional plus fees and adds quantity with fee-inclusive
cost basis. A sell requires sufficient existing holdings, credits rounded
notional minus fees, and allocates weighted historical cost to the quantity
sold. Sells cannot open short positions. Insufficient cash/holdings, wrong
currency, stale versions, stale observations and invalid inputs reject the
whole transaction. The account version and fill persist atomically. Repeating
a submitted fill with its old version cannot produce a second fill.

Paper cash, historical-cost holdings and realized results are returned per
account in `paper_balances`. There is no live mark-to-market equity or inferred
unrealized profit. Immutable fills include account/version, side, symbol,
quantity, price, fees, notional, source/basis/observation timestamp, cash after,
realized-result delta and creation time. The UI pages history in batches of
50; JSON export contains the entire bounded history. Paused/archived accounts
cannot trade. No simulator action mutates the actual manual ledger.

## Actual threshold evaluation and deduplication

Set a threshold to `configured`, then submit `evaluate_alert` with its current
version, `reviewed: true` and the same quote structure used by paper trading.
The symbol/currency must match its active linked watchlist item. A price must
be strictly above/below the threshold; equality is not a match.

```json
{"action":"evaluate_alert","id":"<alert id>","expected_version":2,"reviewed":true,"quote":{"symbol":"BTC","currency":"AUD","price":"101","observed_at":1788825600,"source":"Reviewed snapshot","basis":"snapshot"}}
```

Exact observation/rule fingerprints within the retained history return
`deduplicated: true` without a version bump or a new crossing. Nonduplicate
observations must have a newer timestamp than the latest evaluated one. A
crossing is recorded on the first match or on a transition from nonmatch to
match; repeated newer matches do not retrigger until a nonmatch rearms it.
Changing a rule resets crossing comparison for the next newer observation.
History includes the exact rule, observation, match/crossing result and local
evaluation time. Older fingerprints outside the history window are still
rejected as out of order. There is no polling, scheduler, provider call,
notification delivery or connection from thresholds to paper/live trades.

## UX and validation

The forms are generated from the backend schema, including nested version and
evidence lists and real-record selectors. The views provide title/content
search, active/archive/all filters, pagination, explicit empty states, source
freshness labels, accessible native dialogs, keyboard-operable tabs, focus
styles and reduced-motion handling. CSS is scoped to `.u1-personal` and
`.u1-personal-dialog`; global design-system changes belong to the parent.
Boards/calendars show the matching current page, not an invented full-dataset
summary. Export all includes archived planning records and all paper history;
it does not embed PRISM file contents, provider credentials or other modules'
private preferences. There is no import/restore-from-export endpoint in this
increment; archive restoration is supported.

Run the isolated tests from the root:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p test_u1_personal_core.py -v
node --check static/js/u1-personal-workspaces.js
```

Each test patches `workspace.DATA` to its own temporary directory. Coverage
includes all kinds, persistence, partial updates, archive/delete rules,
concurrent version conflicts and priority allocation, validation/size bounds,
references, existing PRISM preservation, estimates, check-ins, source freshness,
threshold matching/rearming/deduplication, paper accounting and double-spend
prevention, isolated currencies, HTTP origin/CSRF guards and honest errors.

Parent handler/navigation integration, safety-lock behavior through the full
server, native browser rendering, mobile layout and platform packaging require
the parent's integrated checks. Passing this component's isolated tests is
not evidence that all 60 release items, live integrations or native media and
OSINT are complete.

Component check evidence, 2026-09-08: all 47 isolated Python tests passed in
2.313 seconds. JavaScript passed `node --check`. These checks used temporary
planning databases and did not read production planning data, call providers
or perform browser visual checks.
