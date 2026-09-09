"""Bounded, versioned local planning. No workers, provider calls or account actions.

The parent calls its safety gate first, then ``handle_request(handler)``. This
module owns only personal_records inside prism_workspace.database().
"""
import hashlib
import hmac
import json
import math
import re
import sqlite3
import time
import uuid
from datetime import date, datetime
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP, localcontext
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from utils import integrations_hub
from utils import prism_workspace as workspace

ENDPOINT = "/api/workspace/personal"
MAX_RECORDS = 2000
MAX_PER_KIND = 300
MAX_PAYLOAD_BYTES = 24576
MAX_STORAGE_BYTES = 16 * 1024 * 1024
MAX_BODY_BYTES = 65536
MAX_PAGE = 200
MAX_PAPER_TRADES = 1000
SNAPSHOT_MAX_AGE = 900
SCHEMA_VERSION = 1


class PersonalError(ValueError):
    def __init__(self, message, status=400, code="invalid_input"):
        super().__init__(message)
        self.status = status
        self.code = code


def field(label, kind="text", **options):
    return {"label": label, "type": kind, **options}


def choice(label, values, default=None):
    return field(label, "choice", options=values.split(), default=default or values.split()[0])


def ref(label, kinds, required=False):
    return field(label, "reference", references=kinds.split(), required=required, default="")


def money(label, default="0", **options):
    return field(label, "decimal", precision=2, maximum="1000000000", default=default, **options)


def quantity(label, default="0", **options):
    return field(label, "decimal", precision=8, maximum="1000000000", default=default, **options)


NOTES = field("Notes", "textarea", maximum=8000, default="")
DAY = field("Date", "date", required=True)
CURRENCY = field("Currency code", "currency", default="AUD")
EVIDENCE = field("Evidence", "list", maximum=20, fields={
    "source": field("Source / author", maximum=200, required=True),
    "url": field("Source URL (optional)", "url", default=""),
    "observed_on": field("Observed on", "date", required=True),
    "note": field("What this supports or contradicts", "textarea", maximum=2000, required=True),
})
SCHEMAS = {
    "priority": {"label": "Priority", "description": "Choose up to three priorities per day. Completed priorities retain their place.", "fields": {
        "day": DAY, "slot": field("Top-three position", "integer", minimum=1, maximum=3, default=1),
        "done": field("Completed", "boolean", default=False),
        "task_id": ref("Related workspace task", "prism:task"), "notes": NOTES}},
    "time_block": {"label": "Time block", "description": "Times belong to your workspace timezone. Local blocks cannot overlap.", "fields": {
        "day": DAY, "start": field("Starts", "time", required=True), "end": field("Ends", "time", required=True),
        "event_id": ref("Related calendar event", "prism:event"), "notes": NOTES}},
    "bill": {"label": "Bill or renewal", "description": "Manual household planning. Marking paid records your note and never moves money.", "fields": {
        "category": choice("Type", "bill renewal"), "payee": field("Payee / service", maximum=160, default=""),
        "due": field("Due date", "date", required=True), "amount": money("Planned amount"), "currency": CURRENCY,
        "recurrence": choice("Repeat plan", "once weekly monthly quarterly yearly"),
        "status": choice("Recorded status", "planned paid cancelled"), "notes": NOTES}},
    "habit": {"label": "Gentle habit", "description": "Record a check-in when it helps. No streak loss, penalties, reminders or missed-day scores.", "fields": {
        "cadence": choice("Preferred rhythm", "flexible daily weekly"),
        "cue": field("A helpful cue", maximum=300, default=""), "notes": NOTES}},
    "product": {"label": "Product", "description": "Keep product versions linked to actual ready files in your local Files library.", "fields": {
        "status": choice("Product status", "idea building review ready launched"),
        "audience": field("Audience", maximum=300, default=""),
        "description": field("Useful outcome / description", "textarea", maximum=4000, default=""),
        "current_version": field("Current version", maximum=60, default=""),
        "release_date": field("Planned release", "date", default=""),
        "project_id": ref("Workspace project", "prism:project"),
        "versions": field("Version files", "list", maximum=20, fields={
            "version": field("Version label", maximum=60, required=True),
            "file_id": ref("Local file", "file", required=True),
            "notes": field("Version notes", "textarea", maximum=1000, default=""),
        }), "notes": NOTES}},
    "launch": {"label": "Launch task", "description": "Move work through Backlog, Doing, Review and Done. Launch remains operator managed.", "fields": {
        "product_id": ref("Product", "product", required=True), "status": choice("Column", "backlog doing review done"),
        "due": field("Due date", "date", default=""), "notes": NOTES}},
    "opportunity": {"label": "Opportunity", "description": "Keep claims tied to evidence you have reviewed. Validation is your own assessment.", "fields": {
        "status": choice("Assessment", "researching validated parked closed"),
        "hypothesis": field("Hypothesis", "textarea", maximum=4000, required=True),
        "confidence": choice("Your confidence", "unassessed low medium high"),
        "next_action": field("Next research step", maximum=500, default=""), "evidence": EVIDENCE, "notes": NOTES}},
    "contact": {"label": "Client contact", "description": "A private contact record. Saving does not contact anyone or connect an address book.", "fields": {
        "organization": field("Organization", maximum=160, default=""), "role": field("Role", maximum=120, default=""),
        "email": field("Email (optional)", "email", default=""), "phone": field("Phone (optional)", maximum=80, default=""),
        "status": choice("Relationship", "prospect active inactive"), "notes": NOTES}},
    "offer": {"label": "Offer", "description": "Scope and quoted amounts are operator drafts. Status records what you did outside this workspace.", "fields": {
        "contact_id": ref("Client", "contact"), "product_id": ref("Product", "product"),
        "status": choice("Recorded status", "draft review ready sent accepted declined"),
        "scope": field("Scope and deliverables", "textarea", maximum=5000, required=True),
        "outcome": field("Intended outcome", "textarea", maximum=2000, default=""),
        "price": money("Draft quoted price"), "currency": CURRENCY,
        "assumptions": field("Assumptions and exclusions", "textarea", maximum=4000, default=""), "notes": NOTES}},
    "client_project": {"label": "Client project", "description": "Track delivery, related offers and the next agreed action.", "fields": {
        "contact_id": ref("Client", "contact", required=True), "offer_id": ref("Related offer", "offer"),
        "project_id": ref("Workspace project", "prism:project"),
        "status": choice("Delivery status", "planned active paused complete"),
        "due": field("Delivery date", "date", default=""),
        "deliverables": field("Deliverables", "textarea", maximum=4000, required=True),
        "next_action": field("Next action", maximum=500, default=""), "notes": NOTES}},
    "note": {"label": "Business note", "description": "Capture private notes and attach them to an offer, client, product or project.", "fields": {
        "parent_id": ref("Related record", "contact offer client_project product opportunity"),
        "tag": field("Tag", maximum=70, default=""), "text": field("Note", "textarea", maximum=12000, required=True)}},
    "pricing": {"label": "Pricing worksheet", "description": "ESTIMATES ONLY. Assumed sales are not orders or revenue; tax and currency conversion are not inferred.", "fields": {
        "product_id": ref("Product", "product"), "currency": CURRENCY,
        "unit_price": money("Assumed unit price"), "unit_cost": money("Assumed variable cost per unit"),
        "fixed_cost": money("Assumed fixed costs"),
        "units": field("Assumed units sold", "integer", minimum=0, maximum=1000000, default=0),
        "hours": money("Assumed work hours"), "hourly_rate": money("Assumed hourly cost"),
        "fee_percent": field("Assumed selling fee (%)", "decimal", precision=2, maximum="100", default="0"),
        "assumptions": field("Evidence, exclusions and assumptions", "textarea", maximum=6000, required=True)}},
    "content": {"label": "Content draft", "description": "A local editorial calendar. Dates and statuses do not schedule posts on any platform.", "fields": {
        "channel": choice("Planned channel", "website newsletter instagram youtube tiktok linkedin other"),
        "status": choice("Editorial stage", "idea drafting review ready published_manually"),
        "scheduled_on": field("Planned date", "date", default=""),
        "scheduled_time": field("Planned time (optional)", "time", default=""),
        "copy": field("Draft copy", "textarea", maximum=12000, default=""),
        "cta": field("Call to action", maximum=400, default=""),
        "published_url": field("Manually published URL", "url", default=""), "notes": NOTES}},
    "video": {"label": "Faceless video draft", "description": "An operator-managed production checklist. No voice, video, posting or account automation runs here.", "fields": {
        "content_id": ref("Calendar draft", "content"),
        "status": choice("Production stage", "idea script storyboard assets edit review ready"),
        "hook": field("Opening hook", maximum=500, default=""),
        "script": field("Operator-written script", "textarea", maximum=10000, default=""),
        "shot_list": field("Shot list / storyboard", "textarea", maximum=5000, default=""),
        "voice_notes": field("Voice and captions plan", "textarea", maximum=2000, default=""),
        "asset_notes": field("Asset sources and music rights", "textarea", maximum=2000, default=""),
        "file_id": ref("Working local video / asset file", "file"),
        "rights_reviewed": field("I reviewed asset and music rights", "boolean", default=False),
        "content_reviewed": field("I reviewed the finished content", "boolean", default=False)}},
    "watchlist": {"label": "Watchlist item", "description": "Manual paper research. Symbols and source links are labels, not subscriptions or orders.", "fields": {
        "symbol": field("Symbol / instrument", "symbol", required=True),
        "asset_type": choice("Instrument type", "crypto equity fund forex other"), "currency": CURRENCY,
        "status": choice("Research status", "watching paused"),
        "thesis": field("Research thesis", "textarea", maximum=5000, default=""),
        "source_url": field("Research source", "url", default=""),
        "observed_on": field("Source observed on", "date", default=""), "notes": NOTES}},
    "alert": {"label": "Research threshold", "description": "Evaluate on demand against a reviewed timestamped snapshot. Local threshold crossings only; no background monitoring or notifications.", "fields": {
        "watch_id": ref("Watchlist item", "watchlist", required=True),
        "condition": choice("Manual threshold condition", "above below"),
        "threshold": quantity("Threshold in watchlist currency", positive=True),
        "status": choice("Configuration state", "draft configured paused"), "notes": NOTES}},
    "journal": {"label": "Paper journal entry", "description": "Manual paper research only. Prices are operator inputs; results never enter the actual ledger.", "fields": {
        "watch_id": ref("Watchlist item (optional)", "watchlist"), "symbol": field("Symbol / instrument", "symbol", required=True),
        "currency": CURRENCY, "side": choice("Paper direction", "long short"),
        "status": choice("Paper status", "planned open closed"), "day": DAY,
        "entry_price": quantity("Assumed entry price", positive=True),
        "exit_price": field("Assumed exit price (when closed)", "decimal", precision=8, maximum="1000000000", default="", optional=True),
        "quantity": quantity("Paper quantity", positive=True), "fees": money("Assumed total fees"),
        "closed_on": field("Paper close date", "date", default=""),
        "thesis": field("Entry rationale", "textarea", maximum=4000, required=True),
        "risk_plan": field("Risk and invalidation plan", "textarea", maximum=3000, default=""),
        "review": field("What you learned", "textarea", maximum=5000, default="")}},
    "paper_account": {"label": "Paper account", "description": "Simulated cash only. Explicit reviewed buys and sells; long-only, no leverage. Starting cash and currency lock after the first fill.", "fields": {
        "currency": CURRENCY, "starting_cash": money("Simulated starting cash", positive=True),
        "status": choice("Paper account state", "active paused"), "notes": NOTES}},
}
COLLECTIONS = {
    "today": {"label": "Today", "view": "life", "kinds": ["priority", "time_block"]},
    "household": {"label": "Household", "view": "life", "kinds": ["bill"]},
    "wellbeing": {"label": "Wellbeing", "view": "life", "kinds": ["habit"]},
    "products": {"label": "Products & launch", "view": "income", "kinds": ["product", "launch"]},
    "clients": {"label": "Clients & delivery", "view": "income", "kinds": ["contact", "offer", "client_project", "note"]},
    "opportunities": {"label": "Opportunities", "view": "income", "kinds": ["opportunity"]},
    "pricing": {"label": "Pricing", "view": "income", "kinds": ["pricing"]},
    "content": {"label": "Content & video", "view": "income", "kinds": ["content", "video"]},
    "watchlists": {"label": "Watchlists & alerts", "view": "research", "kinds": ["watchlist", "alert"]},
    "journal": {"label": "Paper journal", "view": "research", "kinds": ["journal"]},
    "paper": {"label": "Paper trading", "view": "research", "kinds": ["paper_account"]},
}


def _schema(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS personal_records (
            id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL,
            payload TEXT NOT NULL, version INTEGER NOT NULL CHECK(version > 0),
            archived INTEGER NOT NULL DEFAULT 0 CHECK(archived IN (0,1)),
            created REAL NOT NULL, updated REAL NOT NULL, day TEXT, slot INTEGER
        );
        CREATE INDEX IF NOT EXISTS personal_kind ON personal_records(kind,archived,updated);
        CREATE UNIQUE INDEX IF NOT EXISTS personal_top_three
            ON personal_records(day,slot) WHERE kind='priority' AND archived=0;
        CREATE TABLE IF NOT EXISTS personal_paper_trades (
            id TEXT PRIMARY KEY, account_id TEXT NOT NULL, account_version INTEGER NOT NULL,
            symbol TEXT NOT NULL, side TEXT NOT NULL, quantity TEXT NOT NULL,
            price TEXT NOT NULL, fees TEXT NOT NULL, notional TEXT NOT NULL,
            source TEXT NOT NULL, observed_at REAL NOT NULL, price_basis TEXT NOT NULL,
            cash_after TEXT NOT NULL, realized_result TEXT NOT NULL, created REAL NOT NULL,
            UNIQUE(account_id,account_version)
        );
        CREATE INDEX IF NOT EXISTS personal_paper_account ON personal_paper_trades(account_id,account_version);
    """)


def _text(value, maximum=160, required=False):
    if not isinstance(value, str) or len(value) > maximum:
        raise PersonalError("Use text within the stated field limit.")
    value = value.strip()
    if any(ord(c) < 32 and c not in "\n\t" for c in value):
        raise PersonalError("Control characters are not supported.")
    if required and not value:
        raise PersonalError("Complete the required fields.")
    return value


def _id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{32}", value):
        raise PersonalError("Choose a valid local record identifier.")
    return value


def _date(value, required=False):
    value = _text(value, 10, required)
    if value:
        try:
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
                raise ValueError()
            date.fromisoformat(value)
        except ValueError:
            raise PersonalError("Choose a valid calendar date.") from None
    return value


def _decimal(value, spec):
    if value == "" and spec.get("optional"):
        return ""
    if not isinstance(value, str) or len(value) > 24 or not re.fullmatch(
            r"\d{1,10}(?:\.\d{1," + str(spec["precision"]) + r"})?", value):
        raise PersonalError(spec["label"] + ": use a non-negative decimal string with at most " + str(spec["precision"]) + " decimal places.")
    number = Decimal(value)
    if number > Decimal(spec["maximum"]) or (spec.get("positive") and number <= 0):
        raise PersonalError(spec["label"] + ": amount is outside the supported range.")
    return format(number, "f")


def _reference(conn, value, spec, previous=""):
    value = _text(value, 32, spec.get("required", False))
    if not value:
        return value
    _id(value)
    for kind in spec["references"]:
        if kind == "file":
            found = conn.execute("SELECT id FROM files WHERE id=? AND status='ready' AND (deleted IS NULL OR ?)", (value, value == previous)).fetchone()
        elif kind.startswith("prism:"):
            found = conn.execute("SELECT id FROM records WHERE id=? AND kind=? AND (deleted IS NULL OR ?)", (value, kind.split(":")[1], value == previous)).fetchone()
        else:
            found = conn.execute("SELECT id FROM personal_records WHERE id=? AND kind=? AND (archived=0 OR ?)", (value, kind, value == previous)).fetchone()
        if found:
            return value
    raise PersonalError(spec["label"] + ": choose an existing active record or ready local file.")


def _value(conn, value, spec, previous=None):
    kind = spec["type"]
    required = spec.get("required", False)
    if kind == "boolean":
        if type(value) is not bool:
            raise PersonalError(spec["label"] + ": choose true or false.")
        return value
    if kind == "integer":
        if type(value) is not int or not spec["minimum"] <= value <= spec["maximum"]:
            raise PersonalError(spec["label"] + ": choose a whole number within the stated range.")
        return value
    if kind == "decimal":
        return _decimal(value, spec)
    if kind == "reference":
        return _reference(conn, value, spec, previous)
    if kind == "date":
        return _date(value, required)
    if kind == "list":
        if not isinstance(value, list) or len(value) > spec["maximum"]:
            raise PersonalError(spec["label"] + ": too many entries or invalid list.")
        rows = []
        for i, row in enumerate(value):
            old = previous[i] if isinstance(previous, list) and i < len(previous) else {}
            rows.append(_fields(conn, row, spec["fields"], old))
        return rows
    value = _text(value, spec.get("maximum", 1000 if kind == "url" else 160), required)
    if kind == "choice" and value not in spec["options"]:
        raise PersonalError(spec["label"] + ": choose a supported value.")
    if kind == "time" and value and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", value):
        raise PersonalError("Choose times in HH:MM format.")
    if kind == "currency":
        value = value.upper()
        if not re.fullmatch(r"[A-Z]{3}", value):
            raise PersonalError("Use a three-letter currency code.")
    if kind == "symbol":
        value = value.upper()
        if not re.fullmatch(r"[A-Z0-9][A-Z0-9./:_ -]{0,39}", value):
            raise PersonalError("Use an ordinary symbol up to 40 characters.")
    if kind == "email" and value and not re.fullmatch(r"[^\s@<>]+@[^\s@<>]+\.[^\s@<>]+", value):
        raise PersonalError("Enter an ordinary email address or leave it blank.")
    if kind == "url" and value:
        try:
            parsed = urlsplit(value)
            if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password or any(c.isspace() for c in value):
                raise ValueError()
            parsed.port
        except ValueError:
            raise PersonalError("Use an HTTP(S) URL without credentials. Links are never fetched by this module.") from None
    return value


def _fields(conn, payload, specs, previous=None):
    if not isinstance(payload, dict) or set(payload) - set(specs):
        raise PersonalError("Payload contains unsupported fields or is not an object.")
    previous = previous or {}
    output = {}
    for name, spec in specs.items():
        default = [] if spec["type"] == "list" else spec.get("default", "")
        value = payload.get(name, previous.get(name, default))
        try:
            output[name] = _value(conn, value, spec, previous.get(name))
        except PersonalError as exc:
            raise PersonalError(spec["label"] + ": " + str(exc), exc.status, exc.code) from None
    return output


def _validate(conn, kind, payload, previous=None, item_id="", archived=False):
    result = _fields(conn, payload, SCHEMAS[kind]["fields"], previous)
    if kind == "habit":
        result["checkins"] = list((previous or {}).get("checkins", []))
    if kind == "alert":
        result["evaluations"] = list((previous or {}).get("evaluations", []))
        result["trigger_count"] = (previous or {}).get("trigger_count", 0)
    if kind == "paper_account" and previous:
        traded = conn.execute("SELECT 1 FROM personal_paper_trades WHERE account_id=? LIMIT 1", (item_id,)).fetchone()
        if traded and any(result[k] != previous[k] for k in ("currency", "starting_cash")):
            raise PersonalError("Starting cash and currency are fixed after the first paper fill. Create a separate paper account for a new scenario.")
    if kind == "time_block":
        if result["end"] <= result["start"]:
            raise PersonalError("A time block must end after it starts on the same day.")
        if not archived:
            rows = conn.execute("SELECT payload FROM personal_records WHERE kind='time_block' AND archived=0 AND day=? AND id<>?", (result["day"], item_id)).fetchall()
            for row in rows:
                other = json.loads(row[0])
                if result["start"] < other["end"] and result["end"] > other["start"]:
                    raise PersonalError("This time overlaps another active local block. Choose another time.", 409, "schedule_conflict")
    if kind == "opportunity" and result["status"] == "validated" and not result["evidence"]:
        raise PersonalError("Add reviewed evidence before marking an opportunity validated.")
    if kind == "product":
        labels = [v["version"] for v in result["versions"]]
        pairs = [(v["version"], v["file_id"]) for v in result["versions"]]
        if len(set(pairs)) != len(pairs):
            raise PersonalError("A file can appear only once per product version.")
        if result["current_version"] and labels and result["current_version"] not in labels:
            raise PersonalError("The current version must match a linked version file.")
    if kind == "content":
        if result["scheduled_time"] and not result["scheduled_on"]:
            raise PersonalError("Choose a calendar date for the planned time.")
        if result["status"] == "published_manually" and not result["published_url"]:
            raise PersonalError("Record the published URL before marking this manually published.")
    if kind == "video" and result["status"] == "ready":
        if not result["script"] or not result["rights_reviewed"] or not result["content_reviewed"]:
            raise PersonalError("A ready video needs a script and your content and rights reviews.")
    if kind == "journal":
        if result["status"] == "closed" and (not result["closed_on"] or result["exit_price"] == ""):
            raise PersonalError("A closed paper entry needs an exit price and close date.")
        if result["closed_on"] and result["closed_on"] < result["day"]:
            raise PersonalError("The paper close date cannot precede the entry date.")
    if kind == "client_project" and result["offer_id"]:
        offer = conn.execute("SELECT payload FROM personal_records WHERE id=?", (result["offer_id"],)).fetchone()
        client = json.loads(offer[0]).get("contact_id")
        if client and client != result["contact_id"]:
            raise PersonalError("The selected offer belongs to a different client.")
    return result


def _fixed(value):
    return format(value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), "f")


def _estimates(kind, payload):
    with localcontext() as context:
        context.prec = 50
        p = payload
        if kind == "pricing":
            price, units = Decimal(p["unit_price"]), Decimal(p["units"])
            sales = price * units
            fees = sales * Decimal(p["fee_percent"]) / 100
            labour = Decimal(p["hours"]) * Decimal(p["hourly_rate"])
            fixed = Decimal(p["fixed_cost"]) + labour
            costs = Decimal(p["unit_cost"]) * units + fixed + fees
            contribution = price * (1 - Decimal(p["fee_percent"]) / 100) - Decimal(p["unit_cost"])
            return {"basis": "manual_assumptions_only", "currency": p["currency"],
                    "assumed_sales": _fixed(sales), "assumed_fees": _fixed(fees),
                    "assumed_labour": _fixed(labour), "assumed_costs": _fixed(costs),
                    "estimated_result": _fixed(sales - costs),
                    "break_even_units": int((fixed / contribution).to_integral_value(rounding=ROUND_CEILING)) if contribution > 0 else None,
                    "notice": "Estimates only. Taxes, refunds, demand and currency conversion are not inferred."}
        if kind == "journal" and p["status"] == "closed":
            direction = 1 if p["side"] == "long" else -1
            result = (Decimal(p["exit_price"]) - Decimal(p["entry_price"])) * Decimal(p["quantity"]) * direction - Decimal(p["fees"])
            return {"basis": "manual_paper_research_only", "currency": p["currency"], "paper_result": _fixed(result)}
    return None


def _decode(row):
    result = dict(row)
    result.pop("day", None)
    result.pop("slot", None)
    result["payload"] = json.loads(result["payload"])
    result["archived"] = bool(result["archived"])
    estimate = _estimates(result["kind"], result["payload"])
    if estimate is not None:
        result["estimate"] = estimate
    return result


def _references(payload, specs):
    for name, spec in specs.items():
        value = payload.get(name)
        if spec["type"] == "reference" and value and not any(k.startswith("prism:") or k == "file" for k in spec["references"]):
            yield value
        if spec["type"] == "list":
            for row in value or []:
                yield from _references(row, spec["fields"])


def _quote(value):
    """Validate operator-supplied observations without fetching a provider."""
    keys = {"symbol", "currency", "price", "observed_at", "source", "basis"}
    if not isinstance(value, dict) or set(value) != keys:
        raise PersonalError("Supply symbol, currency, price, observed_at, source and basis for the reviewed observation.")
    symbol = _value(None, value["symbol"], SCHEMAS["watchlist"]["fields"]["symbol"])
    currency = _value(None, value["currency"], CURRENCY)
    price = _decimal(value["price"], quantity("Observed price", positive=True))
    source = _text(value["source"], 200, True)
    basis = value["basis"]
    if not isinstance(basis, str) or basis not in {"manual", "snapshot"}:
        raise PersonalError("Label the observation manual or snapshot.")
    observed = value["observed_at"]
    if type(observed) not in (int, float) or not math.isfinite(observed):
        raise PersonalError("Supply a finite Unix observation timestamp.")
    age = time.time() - observed
    if age < -30 or age > SNAPSHOT_MAX_AGE:
        raise PersonalError("Use a reviewed observation from the last 15 minutes; future timestamps are rejected.", 409, "stale_observation")
    return {"symbol": symbol, "currency": currency, "price": price, "observed_at": observed, "source": source, "basis": basis}


def _paper_balance(conn, account):
    """Cash and weighted cost from immutable fills; never a live valuation."""
    trades = conn.execute("SELECT * FROM personal_paper_trades WHERE account_id=? ORDER BY account_version", (account["id"],)).fetchall()
    with localcontext() as context:
        context.prec = 50
        cash, realized = Decimal(account["payload"]["starting_cash"]), Decimal(0)
        positions = {}
        for trade in trades:
            symbol = trade["symbol"]
            position = positions.setdefault(symbol, {"quantity": Decimal(0), "cost": Decimal(0)})
            units, notional, fees = Decimal(trade["quantity"]), Decimal(trade["notional"]), Decimal(trade["fees"])
            if trade["side"] == "buy":
                position["quantity"] += units
                position["cost"] += notional + fees
                cash -= notional + fees
            else:
                allocated = position["cost"] * units / position["quantity"]
                position["quantity"] -= units
                position["cost"] -= allocated
                cash += notional - fees
                realized += notional - fees - allocated
        return {"cash": _fixed(cash), "realized_result": _fixed(realized), "currency": account["payload"]["currency"],
                "holdings": [{"symbol": symbol, "quantity": format(p["quantity"], "f"), "cost_basis": _fixed(p["cost"]),
                              "average_cost": format((p["cost"] / p["quantity"]).quantize(Decimal("0.00000001"), rounding=ROUND_HALF_UP), "f")}
                             for symbol, p in sorted(positions.items()) if p["quantity"] > 0],
                "trade_count": len(trades), "basis": "simulated_cash_and_historical_cost_only",
                "notice": "Paper simulation. Holdings are historical cost, not current market value. No unrealized return or live execution is claimed."}


def _simulate(conn, body, row):
    if row["kind"] != "paper_account" or row["archived"]:
        raise PersonalError("Choose an active paper account.")
    account = _decode(row)
    if account["payload"]["status"] != "active":
        raise PersonalError("Resume this paper account before recording a simulated fill.")
    if body.get("reviewed") is not True:
        raise PersonalError("Explicitly review the price, timestamp, quantity and paper direction before submitting.")
    side = body.get("side")
    if not isinstance(side, str) or side not in {"buy", "sell"}:
        raise PersonalError("Choose a simulated buy or sell.")
    quote = _quote(body.get("quote"))
    if quote["currency"] != account["payload"]["currency"]:
        raise PersonalError("The observation and paper account must use the same currency. No conversion is performed.")
    units = Decimal(_decimal(body.get("quantity"), quantity("Paper quantity", positive=True)))
    fees = Decimal(_decimal(body.get("fees", "0"), money("Paper fees")))
    count = conn.execute("SELECT COUNT(*) FROM personal_paper_trades").fetchone()[0]
    if count >= MAX_PAPER_TRADES:
        raise PersonalError("The immutable paper fill limit is 1,000. Export the account history; no further fills can be recorded in this release.", 409, "paper_limit")
    balance = _paper_balance(conn, account)
    with localcontext() as context:
        context.prec = 50
        notional = Decimal(_fixed(units * Decimal(quote["price"])))
        if notional < Decimal("0.01"):
            raise PersonalError("The simulated fill must have at least 0.01 account-currency notional.")
        cash = Decimal(balance["cash"])
        holding = next((p for p in balance["holdings"] if p["symbol"] == quote["symbol"]), None)
        if side == "buy" and notional + fees > cash:
            raise PersonalError("Insufficient simulated cash. Paper accounts do not use leverage.", 409, "paper_cash")
        if side == "sell" and (not holding or units > Decimal(holding["quantity"])):
            raise PersonalError("Insufficient paper holdings. This simulator does not open short positions.", 409, "paper_holdings")
        if side == "sell" and fees > notional:
            raise PersonalError("Paper sale fees cannot exceed the sale notional.")
        cash_after = cash - notional - fees if side == "buy" else cash + notional - fees
        trade_id, version, now = uuid.uuid4().hex, row["version"] + 1, time.time()
        conn.execute("INSERT INTO personal_paper_trades VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", (
            trade_id, row["id"], version, quote["symbol"], side, format(units, "f"), quote["price"], _fixed(fees),
            _fixed(notional), quote["source"], quote["observed_at"], quote["basis"], _fixed(cash_after), "0.00", now))
        updated_balance = _paper_balance(conn, account)
        delta = Decimal(updated_balance["realized_result"]) - Decimal(balance["realized_result"])
        conn.execute("UPDATE personal_paper_trades SET realized_result=? WHERE id=?", (_fixed(delta), trade_id))
        conn.execute("UPDATE personal_records SET version=?,updated=? WHERE id=? AND version=?", (version, now, row["id"], row["version"]))
        trade = dict(conn.execute("SELECT * FROM personal_paper_trades WHERE id=?", (trade_id,)).fetchone())
        record = _decode(conn.execute("SELECT * FROM personal_records WHERE id=?", (row["id"],)).fetchone())
        return {"success": True, "record": record, "trade": trade, "paper_balance": updated_balance,
                "id": row["id"], "version": version, "simulated": True}


def _evaluate(conn, body, row):
    if row["kind"] != "alert" or row["archived"]:
        raise PersonalError("Choose an active research threshold.")
    payload = json.loads(row["payload"])
    if payload["status"] != "configured" or body.get("reviewed") is not True:
        raise PersonalError("Set the threshold to configured and explicitly review the observation.")
    quote = _quote(body.get("quote"))
    watch = conn.execute("SELECT payload FROM personal_records WHERE id=? AND kind='watchlist' AND archived=0", (payload["watch_id"],)).fetchone()
    if not watch:
        raise PersonalError("Restore the linked watchlist item before evaluating.")
    watch = json.loads(watch[0])
    if quote["symbol"] != watch["symbol"] or quote["currency"] != watch["currency"]:
        raise PersonalError("The observation must match the watchlist symbol and currency.")
    rule = {"condition": payload["condition"], "threshold": payload["threshold"], "watch_id": payload["watch_id"]}
    fingerprint = hashlib.sha256(json.dumps({"quote": quote, "rule": rule}, sort_keys=True).encode()).hexdigest()
    history = payload.get("evaluations", [])
    if any(e["fingerprint"] == fingerprint for e in history):
        return {"success": True, "record": _decode(row), "id": row["id"], "version": row["version"], "deduplicated": True, "triggered": False}
    if history and quote["observed_at"] <= history[-1]["quote"]["observed_at"]:
        raise PersonalError("Use a newer observation for the next threshold evaluation.", 409, "observation_order")
    matched = Decimal(quote["price"]) > Decimal(payload["threshold"]) if payload["condition"] == "above" else Decimal(quote["price"]) < Decimal(payload["threshold"])
    prior = history[-1] if history and history[-1]["rule"] == rule else None
    triggered = matched and not (prior and prior["matched"])
    evaluation = {"fingerprint": fingerprint, "quote": quote, "rule": rule, "matched": matched, "triggered": triggered, "evaluated_at": time.time()}
    payload["evaluations"] = (history + [evaluation])[-20:]
    payload["trigger_count"] = min(1000000000, payload.get("trigger_count", 0) + int(triggered))
    encoded = json.dumps(payload, separators=(",", ":"))
    if len(encoded.encode()) > MAX_PAYLOAD_BYTES:
        raise PersonalError("Threshold history exceeds the record limit. Shorten notes before evaluating.", 413, "payload_limit")
    used = conn.execute("SELECT COALESCE(SUM(length(CAST(payload AS BLOB))+length(CAST(title AS BLOB))),0) FROM personal_records WHERE id<>?", (row["id"],)).fetchone()[0]
    if used + len(encoded.encode()) + len(row["title"].encode()) > MAX_STORAGE_BYTES:
        raise PersonalError("Planning content has reached its storage limit.", 409, "storage_limit")
    conn.execute("UPDATE personal_records SET payload=?,version=version+1,updated=? WHERE id=? AND version=?", (encoded, time.time(), row["id"], row["version"]))
    saved = _decode(conn.execute("SELECT * FROM personal_records WHERE id=?", (row["id"],)).fetchone())
    return {"success": True, "record": saved, "id": row["id"], "version": saved["version"], "evaluation": evaluation, "triggered": triggered, "deduplicated": False}


def action(body):
    """Perform one atomic command; updates are patches and always version checked."""
    if not isinstance(body, dict):
        raise PersonalError("A JSON object is required.")
    try:
        encoded = json.dumps(body, allow_nan=False).encode("utf-8")
    except (TypeError, ValueError, RecursionError):
        raise PersonalError("Use finite JSON values.") from None
    if len(encoded) > MAX_BODY_BYTES:
        raise PersonalError("The request exceeds 64 KiB.", 413, "request_limit")
    command = body.get("action")
    commands = {"create", "update", "archive", "restore", "delete", "habit_checkin", "paper_trade", "evaluate_alert"}
    if not isinstance(command, str) or command not in commands:
        raise PersonalError("Choose a supported local planning action.")
    allowed = {"action", "kind", "title", "payload"} if command == "create" else {"action", "id", "expected_version"}
    if command == "update":
        allowed |= {"title", "payload"}
    if command == "delete":
        allowed.add("confirmed")
    if command == "habit_checkin":
        allowed |= {"day", "checked"}
    if command in {"paper_trade", "evaluate_alert"}:
        allowed |= {"quote", "reviewed"}
    if command == "paper_trade":
        allowed |= {"side", "quantity", "fees"}
    if set(body) - allowed:
        raise PersonalError("The action contains unsupported fields.")
    with workspace.database() as conn:
        _schema(conn)
        conn.execute("BEGIN IMMEDIATE")
        if command == "create":
            kind = body.get("kind")
            if not isinstance(kind, str) or kind not in SCHEMAS:
                raise PersonalError("Choose a supported planning record type.")
            count = conn.execute("SELECT COUNT(*) FROM personal_records").fetchone()[0]
            kind_count = conn.execute("SELECT COUNT(*) FROM personal_records WHERE kind=?", (kind,)).fetchone()[0]
            if count >= MAX_RECORDS or kind_count >= MAX_PER_KIND:
                raise PersonalError("The local record limit is reached. Export, then remove unneeded archived records.", 409, "record_limit")
            item_id = uuid.uuid4().hex
            title = _text(body.get("title"), 160, True)
            payload = _validate(conn, kind, body.get("payload", {}), item_id=item_id)
            now = time.time()
            version, archived, created = 1, False, now
        else:
            item_id = _id(body.get("id"))
            expected = body.get("expected_version")
            if type(expected) is not int or not 1 <= expected <= 2 ** 53 - 1:
                raise PersonalError("Supply the positive integer expected_version from the last snapshot.")
            row = conn.execute("SELECT * FROM personal_records WHERE id=?", (item_id,)).fetchone()
            if not row:
                raise PersonalError("That planning record was not found.", 404, "not_found")
            if row["version"] != expected:
                raise PersonalError("This record changed elsewhere. Your draft is preserved; reload the latest version before saving.", 409, "version_conflict")
            if command == "paper_trade":
                return _simulate(conn, body, row)
            if command == "evaluate_alert":
                return _evaluate(conn, body, row)
            kind, title, payload = row["kind"], row["title"], json.loads(row["payload"])
            archived, created, version, now = bool(row["archived"]), row["created"], expected + 1, time.time()
            if command == "delete":
                if not archived or body.get("confirmed") is not True:
                    raise PersonalError("Archive first, export if needed, then explicitly confirm permanent deletion.")
                if conn.execute("SELECT 1 FROM personal_paper_trades WHERE account_id=? LIMIT 1", (item_id,)).fetchone():
                    raise PersonalError("Accounts with immutable paper fills can be archived and exported, but cannot be deleted.", 409, "paper_history")
                others = conn.execute("SELECT kind,payload FROM personal_records WHERE id<>?", (item_id,)).fetchall()
                if any(item_id in set(_references(json.loads(r["payload"]), SCHEMAS[r["kind"]]["fields"])) for r in others):
                    raise PersonalError("This record is still linked from another active or archived record. Remove that link first.", 409, "reference_conflict")
                conn.execute("DELETE FROM personal_records WHERE id=? AND version=?", (item_id, expected))
                return {"success": True, "id": item_id, "deleted": True, "previous_version": expected}
            if command == "update":
                title = _text(body.get("title", title), 160, True)
                payload = _validate(conn, kind, body.get("payload", {}), payload, item_id, archived)
            if command in {"archive", "restore"}:
                archived = command == "archive"
                if not archived:
                    editable = {k: v for k, v in payload.items() if k in SCHEMAS[kind]["fields"]}
                    payload = _validate(conn, kind, editable, payload, item_id, False)
            if command == "habit_checkin":
                if kind != "habit" or archived:
                    raise PersonalError("Check-ins require an active habit.")
                day = _date(body.get("day"), True)
                if type(body.get("checked")) is not bool:
                    raise PersonalError("Choose whether this date is checked in.")
                days = set(payload.get("checkins", []))
                days.add(day) if body["checked"] else days.discard(day)
                if len(days) > 366:
                    raise PersonalError("This habit holds up to 366 dates. Export and remove an older check-in, or start a new habit record.", 409, "checkin_limit")
                payload["checkins"] = sorted(days)
        encoded_payload = json.dumps(payload, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
        if len(encoded_payload.encode("utf-8")) > MAX_PAYLOAD_BYTES:
            raise PersonalError("This record exceeds the 24 KiB content limit.", 413, "payload_limit")
        used = conn.execute("SELECT COALESCE(SUM(length(CAST(payload AS BLOB))+length(CAST(title AS BLOB))),0) FROM personal_records WHERE id<>?", (item_id,)).fetchone()[0]
        if used + len(encoded_payload.encode("utf-8")) + len(title.encode("utf-8")) > MAX_STORAGE_BYTES:
            raise PersonalError("Planning content has reached its 16 MiB limit. Export and remove unneeded archived records.", 409, "storage_limit")
        values = (kind, title, encoded_payload, version, int(archived), created, now, payload.get("day"), payload.get("slot"))
        try:
            if command == "create":
                conn.execute("INSERT INTO personal_records(kind,title,payload,version,archived,created,updated,day,slot,id) VALUES(?,?,?,?,?,?,?,?,?,?)", (*values, item_id))
            else:
                changed = conn.execute("UPDATE personal_records SET kind=?,title=?,payload=?,version=?,archived=?,created=?,updated=?,day=?,slot=? WHERE id=? AND version=?", (*values, item_id, body["expected_version"]))
                if changed.rowcount != 1:
                    raise PersonalError("This record changed elsewhere. Reload before saving.", 409, "version_conflict")
        except sqlite3.IntegrityError:
            raise PersonalError("That top-three position is already used on this date. Choose a free position or archive the existing priority.", 409, "priority_conflict") from None
        saved = conn.execute("SELECT * FROM personal_records WHERE id=?", (item_id,)).fetchone()
        return {"success": True, "record": _decode(saved), "id": item_id, "version": version}


def _filters(query, export=False):
    if not isinstance(query, dict) or set(query) - {"id", "collection", "kind", "q", "archived", "day", "limit", "offset"}:
        raise PersonalError("Unsupported snapshot filters.")
    values = {}
    for key, value in query.items():
        if isinstance(value, list):
            if len(value) != 1:
                raise PersonalError("Each filter may appear only once.")
            value = value[0]
        values[key] = _text(value, 160)
    collection, kind = values.get("collection", ""), values.get("kind", "")
    if collection and collection not in COLLECTIONS:
        raise PersonalError("Unknown planning collection.")
    if kind and (kind not in SCHEMAS or (collection and kind not in COLLECTIONS[collection]["kinds"])):
        raise PersonalError("The record type does not belong to this collection.")
    archived = values.get("archived", "all" if export else "active")
    if archived not in {"active", "archived", "all"}:
        raise PersonalError("Choose active, archived or all records.")
    day = _date(values.get("day", ""))
    limit, offset = MAX_RECORDS if export else 100, 0
    for name, maximum in (("limit", MAX_PAGE), ("offset", MAX_RECORDS)):
        if name in values:
            if export or not re.fullmatch(r"\d{1,4}", values[name]):
                raise PersonalError("Invalid pagination.")
            number = int(values[name])
            if not (1 if name == "limit" else 0) <= number <= maximum:
                raise PersonalError("Pagination is outside the supported range.")
            if name == "limit":
                limit = number
            else:
                offset = number
    clauses, params = [], []
    if values.get("id"):
        clauses.append("id=?")
        params.append(_id(values["id"]))
    kinds = [kind] if kind else COLLECTIONS[collection]["kinds"] if collection else []
    if kinds:
        clauses.append("kind IN (" + ",".join("?" for _ in kinds) + ")")
        params.extend(kinds)
    if archived != "all":
        clauses.append("archived=?")
        params.append(int(archived == "archived"))
    if day:
        clauses.append("day=?")
        params.append(day)
    if values.get("q"):
        clauses.append("personal_contains(title, payload, ?)")
        params.append(values["q"])
    return " AND ".join(clauses) or "1", params, limit, offset


def snapshot(query=None, export=False):
    where, params, limit, offset = _filters({} if query is None else query, export)
    with workspace.database() as conn:
        _schema(conn)
        conn.execute("BEGIN")
        conn.create_function("personal_contains", 3, lambda title, payload, needle: int(needle.casefold() in (title + " " + json.dumps(json.loads(payload), ensure_ascii=False)).casefold()))
        total = conn.execute("SELECT COUNT(*) FROM personal_records WHERE " + where, params).fetchone()[0]
        if export and total > limit:
            raise PersonalError("The complete selected export exceeds the record limit. Narrow the filters; nothing was exported.")
        rows = conn.execute("SELECT * FROM personal_records WHERE " + where + " ORDER BY updated DESC,id LIMIT ? OFFSET ?", (*params, limit, offset)).fetchall()
        profile = conn.execute("SELECT value FROM preferences WHERE key='profile'").fetchone()
        timezone = json.loads(profile[0]).get("timezone", "Australia/Melbourne") if profile else "Australia/Melbourne"
        try:
            zone = ZoneInfo(timezone)
        except (ZoneInfoNotFoundError, ValueError, TypeError):
            timezone, zone = "Australia/Melbourne", ZoneInfo("Australia/Melbourne")
        result = {"success": True, "schema_version": SCHEMA_VERSION, "records": [_decode(r) for r in rows],
                  "total": total, "limit": limit, "offset": offset, "has_more": offset + len(rows) < total,
                  "generated_at": time.time(), "timezone": timezone, "today": datetime.now(zone).date().isoformat(),
                  "source": "Operator-entered local planning records", "notice": "Local unencrypted storage. Drafts, estimates and manual paper simulation only; no background monitoring, publishing, payments or live trades. Automated strategy evaluation is unavailable."}
        if export:
            account_rows = [row for row in rows if row["kind"] == "paper_account"]
            account_ids = [row["id"] for row in account_rows]
            trade_rows = conn.execute("SELECT * FROM personal_paper_trades WHERE account_id IN (" +
                                      ",".join("?" for _ in account_ids) + ") ORDER BY created DESC,id LIMIT ?",
                                      (*account_ids, MAX_PAPER_TRADES + 1)).fetchall() if account_ids else []
            if len(trade_rows) > MAX_PAPER_TRADES:
                raise PersonalError("The complete selected export exceeds the paper-trade limit. Narrow the account filters; nothing was exported.")
            result["paper_balances"] = {r["id"]: _paper_balance(conn, _decode(r)) for r in account_rows}
            result["paper_trades"] = [dict(row) for row in trade_rows]
            return {**result, "format": "u1-personal-workflows", "exported_at": result["generated_at"],
                    "export_notice": "Planning records only. Linked PRISM records and file contents are not embedded. Protect this export as private personal and business data."}
        account_rows = conn.execute("SELECT * FROM personal_records WHERE kind='paper_account' ORDER BY title,id LIMIT ?", (MAX_PER_KIND,)).fetchall()
        result["paper_balances"] = {r["id"]: _paper_balance(conn, _decode(r)) for r in account_rows}
        result["paper_trades"] = [dict(r) for r in conn.execute("SELECT * FROM personal_paper_trades ORDER BY created DESC,id LIMIT ?", (MAX_PAPER_TRADES,)).fetchall()]
        personal = conn.execute("SELECT id,kind,title,archived FROM personal_records ORDER BY title,id LIMIT ?", (MAX_RECORDS,)).fetchall()
        canonical = conn.execute("SELECT id,kind,title,deleted FROM records WHERE kind IN ('task','event','project') ORDER BY updated DESC LIMIT 1000").fetchall()
        files = conn.execute("SELECT id,name,deleted,status FROM files ORDER BY created DESC LIMIT 1000").fetchall()
        result.update(schemas=SCHEMAS, collections=COLLECTIONS,
                      references=[dict(r) for r in personal] + [{"id": r["id"], "kind": "prism:" + r["kind"], "title": r["title"], "archived": r["deleted"] is not None} for r in canonical] + [{"id": r["id"], "kind": "file", "title": r["name"], "archived": r["deleted"] is not None or r["status"] != "ready"} for r in files],
                      limits={"records": MAX_RECORDS, "per_kind": MAX_PER_KIND, "payload_bytes": MAX_PAYLOAD_BYTES,
                              "storage_bytes": MAX_STORAGE_BYTES, "page": MAX_PAGE, "habit_dates": 366,
                              "paper_trades": MAX_PAPER_TRADES, "observation_max_age_seconds": SNAPSHOT_MAX_AGE},
                      count=conn.execute("SELECT COUNT(*) FROM personal_records").fetchone()[0])
        return result


def _reply(handler, data, status=200):
    content = json.dumps(data, allow_nan=False).encode("utf-8")
    handler.send_response(status)
    for name, value in (("Content-Type", "application/json; charset=utf-8"), ("Content-Length", str(len(content))),
                        ("Cache-Control", "no-store"), ("X-Content-Type-Options", "nosniff"), ("Connection", "close")):
        handler.send_header(name, value)
    handler.end_headers()
    handler.close_connection = True
    handler.wfile.write(content)


def handle_request(handler):
    """Return True only when handled. Parent safety gate MUST precede this call."""
    try:
        parsed = urlsplit(handler.path)
    except ValueError:
        return False
    path = parsed.path.rstrip("/")
    if path not in {ENDPOINT, ENDPOINT + "/snapshot", ENDPOINT + "/export"}:
        return False
    if not callable(getattr(handler, "integration_request_allowed", None)) or not handler.integration_request_allowed():
        _reply(handler, {"success": False, "error": "Local same-origin request required.", "code": "origin_rejected"}, 403)
        return True
    try:
        if len(parsed.query) > 2048:
            raise PersonalError("Snapshot filters are too long.", 413)
        query = parse_qs(parsed.query, keep_blank_values=True, max_num_fields=12)
        if handler.command == "GET":
            _reply(handler, snapshot(query, export=path.endswith("/export")))
        elif handler.command == "POST" and path == ENDPOINT:
            token = handler.headers.get("X-U1-CSRF", "")
            if not isinstance(token, str) or not hmac.compare_digest(token.encode("utf-8"), integrations_hub.CSRF_TOKEN.encode("utf-8")):
                raise PersonalError("Reload U1 OS for local authorisation before saving.", 403, "csrf_rejected")
            if query:
                raise PersonalError("POST actions do not accept query filters.")
            if handler.headers.get("Transfer-Encoding") or handler.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
                raise PersonalError("Send a bounded application/json body with Content-Length.", 415)
            length_text = handler.headers.get("Content-Length", "")
            if not re.fullmatch(r"\d{1,8}", length_text):
                raise PersonalError("A valid Content-Length is required.", 411)
            length = int(length_text)
            if not 0 < length <= MAX_BODY_BYTES:
                raise PersonalError("The request must be between 1 byte and 64 KiB.", 413)
            raw = handler.rfile.read(length)
            if len(raw) != length:
                raise PersonalError("The request body is incomplete.")
            def object_pairs(pairs):
                value = {}
                for key, entry in pairs:
                    if key in value:
                        raise PersonalError("Duplicate JSON fields are not supported.")
                    value[key] = entry
                return value
            body = json.loads(raw, object_pairs_hook=object_pairs)
            _reply(handler, action(body))
        else:
            raise PersonalError("Use GET for snapshots/exports and POST on /api/workspace/personal for actions.", 405, "method_not_allowed")
    except PersonalError as exc:
        _reply(handler, {"success": False, "error": str(exc), "code": exc.code}, exc.status)
    except (ValueError, TypeError, UnicodeError, RecursionError):
        _reply(handler, {"success": False, "error": "The request is not valid bounded JSON or query data.", "code": "invalid_input"}, 400)
    except (sqlite3.Error, OSError):
        _reply(handler, {"success": False, "error": "Local planning storage is unavailable. Retry after the service recovers.", "code": "storage_unavailable"}, 503)
    return True
