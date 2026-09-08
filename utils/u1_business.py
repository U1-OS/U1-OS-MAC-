"""Review-first local drafts and manual bookkeeping, never account execution."""
import json
import re
import threading
import time
import uuid
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo
from utils import prism_workspace as workspace
from utils import u1_documents

LOCK = threading.RLock()
KEY = "u1_business_v1"


def _load():
    with workspace.database() as conn:
        row = conn.execute("SELECT value FROM preferences WHERE key=?", (KEY,)).fetchone()
    return json.loads(row[0]) if row else {"drafts": [], "entries": []}


def _save(value):
    with workspace.database() as conn:
        conn.execute("INSERT OR REPLACE INTO preferences(key,value) VALUES(?,?)", (KEY, json.dumps(value)))


def clean(value, maximum, required=False):
    if not isinstance(value, str) or len(value) > maximum:
        raise ValueError("Use ordinary text within the field size limit.")
    value = value.strip()
    if required and not value:
        raise ValueError("Complete the required fields.")
    return value


def snapshot():
    with LOCK:
        state = _load()
        totals = {}
        for entry in state["entries"]:
            if entry.get("archived"):
                continue
            currency = entry["currency"]
            values = totals.setdefault(currency, {"income_minor": 0, "expense_minor": 0})
            values[entry["kind"]+"_minor"] += entry["amount_minor"]
        return {"success": True, **state, "totals": totals, "source": "Operator-entered local records, not bank transactions",
                "notice": "Unencrypted local workspace storage. No email, banking or social account is read by this module."}


def action(body):
    if not isinstance(body, dict):
        raise ValueError("A JSON object is required.")
    command = body.get("action")
    if command == "document":
        return u1_documents.create(body)
    with LOCK:
        state = _load()
        if command == "draft":
            if len(state["drafts"]) >= 200:
                raise ValueError("The local draft limit is 200. Export your records before reorganising them.")
            title = clean(body.get("title"), 160, True)
            content = clean(body.get("content"), 12000, True)
            source = clean(body.get("source", "Manually supplied text"), 200)
            item = {"id": uuid.uuid4().hex, "record_id": uuid.uuid4().hex, "title": title, "content": content, "source": source,
                    "status": "review", "created": time.time(), "date_candidates": list(dict.fromkeys(re.findall(r"\b20\d{2}-\d{2}-\d{2}(?:[T ]\d{2}:\d{2})?\b", content)))[:10]}
            state["drafts"].insert(0, item)
        elif command in {"approve", "discard"}:
            item = next((d for d in state["drafts"] if d["id"] == body.get("id")), None)
            if not item:
                raise ValueError("That draft was not found.")
            if item["status"] != "review":
                return {"success": True, "status": item["status"], "id": item["record_id"]}
            if command == "discard":
                item["status"] = "discarded"
            else:
                if body.get("confirmed") is not True:
                    raise ValueError("Review and confirm the draft before creating a workspace record.")
                kind = body.get("kind", "task")
                if kind not in {"task", "event"}:
                    raise ValueError("Create a task or calendar event.")
                title = clean(body.get("title", item["title"]), 160, True)
                notes = ("Source: "+item["source"]+"\n"+item["content"])[:3800]
                payload = {"notes": notes, "body": notes, "description": notes}
                if kind == "event":
                    try:
                        start = datetime.fromisoformat(clean(body.get("start"), 80, True))
                        if start.tzinfo is None:
                            start = start.replace(tzinfo=ZoneInfo(workspace.preferences()["timezone"]))
                    except (ValueError, TypeError, KeyError):
                        raise ValueError("Confirm a valid date and time in your workspace time zone.") from None
                    payload.update(start=start.isoformat(), end=(start+timedelta(hours=1)).isoformat(), location=clean(body.get("location", ""), 200))
                result = workspace.handle_post("prism/record", {"id": item["record_id"], "kind": kind, "title": title, "payload": payload})
                if result.get("success") is not True:
                    raise ValueError("The local record could not be created. The draft remains in review.")
                item.update(status="approved", approved=time.time(), kind=kind)
        elif command == "entry":
            if len(state["entries"]) >= 2000:
                raise ValueError("The manual ledger limit is 2,000 entries.")
            kind = body.get("kind")
            if kind not in {"income", "expense"}:
                raise ValueError("Choose income or expense.")
            currency = clean(body.get("currency", "AUD"), 3, True).upper()
            if not re.fullmatch(r"[A-Z]{3}", currency):
                raise ValueError("Use a three-letter currency code.")
            raw = str(body.get("amount", ""))
            if len(raw) > 18 or not re.fullmatch(r"\d{1,12}(?:\.\d{1,2})?", raw):
                raise ValueError("Enter a positive amount with at most two decimal places.")
            try:
                amount = Decimal(raw)
                if not amount.is_finite() or amount <= 0:
                    raise ValueError("The amount must be positive.")
            except InvalidOperation:
                raise ValueError("Enter a valid amount.") from None
            item = {"id": uuid.uuid4().hex, "kind": kind, "title": clean(body.get("title"), 160, True), "amount_minor": int(amount*100),
                    "currency": currency, "created": time.time(), "archived": False}
            state["entries"].insert(0, item)
        elif command == "archive_entry":
            item = next((e for e in state["entries"] if e["id"] == body.get("id")), None)
            if not item:
                raise ValueError("That ledger entry was not found.")
            item["archived"] = True
        else:
            raise ValueError("Choose a supported local business action.")
        _save(state)
        return {"success": True, "id": item.get("record_id", item["id"]), "status": item.get("status", "saved")}
