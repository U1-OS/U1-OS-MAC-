"""Local, read-only automation. No publishing, shell execution, or paid AI calls."""
import json
import logging
import threading
import time
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from utils import prism_workspace as workspace

LOG = logging.getLogger(__name__)
LOCK = threading.RLock()
DEFAULTS = {"enabled": True, "briefing": True, "reminders": True, "health": True}
INTERVAL = 60
_thread = None


def read_value(key, default):
    with workspace.database() as conn:
        row = conn.execute("SELECT value FROM preferences WHERE key=?", (key,)).fetchone()
    return json.loads(row[0]) if row else default


def save_value(key, value):
    with workspace.database() as conn:
        conn.execute("INSERT OR REPLACE INTO preferences(key,value) VALUES(?,?)", (key, json.dumps(value)))


def configuration():
    return {**DEFAULTS, **read_value("u1_autopilot_config", {})}


def configure(body):
    if not isinstance(body, dict):
        raise ValueError("Autopilot settings must be an object.")
    values = body.get("settings", {})
    if not isinstance(values, dict) or any(key not in DEFAULTS for key in values):
        raise ValueError("Choose a supported local automation setting.")
    if any(not isinstance(value, bool) for value in values.values()):
        raise ValueError("Automation switches must be true or false.")
    with LOCK:
        save_value("u1_autopilot_config", {**configuration(), **values})
        return tick()


def tick(now=None):
    with LOCK:
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        config = configuration()
        profile = workspace.preferences()
        zone = ZoneInfo(profile["timezone"])
        local = now.astimezone(zone)
        today = local.date().isoformat()
        activity = read_value("u1_autopilot_activity", [])
        previous = read_value("u1_autopilot_state", {})
        seen = {item["key"] for item in activity}
        records = workspace.records()
        tasks = [r for r in records if r["kind"] == "task" and not r["payload"].get("done")]
        due = [r for r in tasks if r["payload"].get("due") and r["payload"]["due"] <= today]
        projects = [r for r in records if r["kind"] == "project"]
        events = []
        for record in records:
            if record["kind"] != "event":
                continue
            try:
                start = datetime.fromisoformat(record["payload"]["start"])
                if start.tzinfo is None:
                    start = start.replace(tzinfo=zone)
                if start.astimezone(zone).date() == local.date():
                    events.append((start, record))
            except (TypeError, ValueError, KeyError):
                continue
        events.sort(key=lambda pair: pair[0])

        def notify(key, title, message, kind="info"):
            if key in seen:
                return
            seen.add(key)
            activity.insert(0, {"key": key, "title": title, "message": message,
                                "kind": kind, "created": now.timestamp(), "source": "Local U1 automation"})

        briefing = previous.get("briefing")
        if config["enabled"]:
            if config["briefing"]:
                text = (f"{len(projects)} local projects, {len(tasks)} open tasks, "
                        f"{len(due)} due or overdue, and {len(events)} calendar events today.")
                briefing = {"date": today, "generated_at": now.timestamp(), "text": text,
                            "events": [{"title": r["title"], "start": start.isoformat()} for start, r in events[:6]],
                            "source": "Local projects, tasks and calendar only. Email and cloud accounts are not read."}
                notify("briefing:" + today, "Your daily local briefing", text, "briefing")
            if config["reminders"]:
                for task in due:
                    notify("task:" + today + ":" + task["id"], "Task needs attention", task["title"], "reminder")
                for start, record in events:
                    minutes = (start - now).total_seconds() / 60
                    if 0 <= minutes <= 15:
                        notify("event:" + record["id"] + ":" + record["payload"]["start"], "Upcoming local event", record["title"], "reminder")
            if config["health"]:
                disk = workspace.system_metrics().get("disk", {})
                if disk.get("percent", 0) >= 90:
                    notify("disk:" + today, "Disk space is running low", "At least 90% of the local volume is used. Review storage before importing more files.", "warning")
        activity = activity[:100]
        result = {"success": True, "settings": config, "status": "running" if config["enabled"] else "paused",
                  "checked_at": now.timestamp(), "interval_seconds": INTERVAL, "briefing": briefing,
                  "counts": {"projects": len(projects), "open_tasks": len(tasks), "due_tasks": len(due), "events_today": len(events)},
                  "activity": activity[:30], "execution": "Local metadata only; no external actions",
                  "guarded_actions": ["Publishing posts", "Sending messages or email", "Paid AI requests", "Trading and payments", "Installing software", "Permanent deletion"],
                  "notice": "Runs while the local U1 server is running. Pauses when the Mac or server is stopped."}
        save_value("u1_autopilot_activity", activity)
        save_value("u1_autopilot_state", result)
        return result


def snapshot():
    with LOCK:
        result = read_value("u1_autopilot_state", {})
        if not result or time.time() - result.get("checked_at", 0) > INTERVAL + 5:
            return tick()
        return result


def start():
    global _thread
    with LOCK:
        if _thread and _thread.is_alive():
            return
        def run():
            while True:
                try:
                    tick()
                except Exception as error:
                    LOG.warning("U1 local autopilot check unavailable: %s", type(error).__name__)
                time.sleep(INTERVAL)
        _thread = threading.Thread(target=run, name="u1-local-autopilot", daemon=True)
        _thread.start()
