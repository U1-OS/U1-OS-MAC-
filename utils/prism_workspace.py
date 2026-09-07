"""Local PRISM workspace records and honest, read-only system telemetry.

The parent HTTP server retains its loopback, origin and CSRF checks. No provider
credentials are stored here, and uploaded documents are never executed.
"""
import base64
import hashlib
import json
import logging
import math
import os
import platform
import re
import shutil
import sqlite3
import threading
import time
import urllib.parse
import urllib.request
import uuid
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

ROOT = Path(__file__).resolve().parents[1]
DATA = Path(os.environ.get("PRISM_DATA_DIR", ROOT / "data" / "prism"))
LOCK = threading.RLock()
LOG = logging.getLogger("PRISM.workspace")
KINDS = {"project", "task", "note", "event"}
MAX_FILE = 25 * 1024 * 1024
MAX_STORAGE = 1024 * 1024 * 1024
PROFILE = {"name": "Andrew", "city": "Beveridge, Victoria", "country": "AU",
           "timezone": "Australia/Melbourne", "effects": "balanced", "focus": False,
           "contrast": False, "drive_plan_tb": 5}
_telemetry = {"at": 0, "value": None, "net": None}
_weather = {}


@contextmanager
def database():
    with LOCK:
        DATA.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(DATA, 0o700)
        path = DATA / "workspace.sqlite3"
        conn = sqlite3.connect(path, timeout=8)
        conn.row_factory = sqlite3.Row
        try:
            os.chmod(path, 0o600)
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS records (
                    id TEXT PRIMARY KEY, kind TEXT NOT NULL, title TEXT NOT NULL,
                    payload TEXT NOT NULL, created REAL NOT NULL, updated REAL NOT NULL,
                    deleted REAL
                );
                CREATE INDEX IF NOT EXISTS records_kind ON records(kind, deleted, updated);
                CREATE TABLE IF NOT EXISTS preferences (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                CREATE TABLE IF NOT EXISTS files (
                    id TEXT PRIMARY KEY, name TEXT NOT NULL, mime TEXT NOT NULL,
                    size INTEGER NOT NULL, received INTEGER NOT NULL DEFAULT 0,
                    folder TEXT NOT NULL, status TEXT NOT NULL, created REAL NOT NULL,
                    checksum TEXT, deleted REAL
                );
            """)
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


def clean(value, maximum, required=False):
    if not isinstance(value, str):
        value = ""
    value = value.strip()
    if len(value) > maximum:
        raise ValueError("That field is too long. Please shorten it.")
    if required and not value:
        raise ValueError("A title is required.")
    return value


def identifier(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{32}", value):
        raise ValueError("That workspace item is not valid.")
    return value


def iso_day(value):
    value = clean(value, 10)
    if value:
        try:
            date.fromisoformat(value)
        except ValueError:
            raise ValueError("Choose a valid date.") from None
    return value


def record_payload(kind, value):
    if not isinstance(value, dict):
        raise ValueError("The item content must be an object.")
    if kind == "project":
        status = value.get("status", "planned")
        if status not in {"planned", "active", "paused", "done"}:
            raise ValueError("Choose a valid project status.")
        progress = value.get("progress")
        if progress is not None:
            if isinstance(progress, bool) or not isinstance(progress, (int, float)) or not math.isfinite(progress) or not 0 <= progress <= 100:
                raise ValueError("Progress must be between 0 and 100, or left blank.")
            progress = round(progress)
        url = clean(value.get("url"), 1000)
        if url:
            parsed = urllib.parse.urlsplit(url)
            if parsed.scheme not in {"https", "http"} or not parsed.hostname or parsed.username or parsed.password:
                raise ValueError("Project links must be ordinary HTTP or HTTPS URLs without credentials.")
        return {"category": clean(value.get("category"), 80) or "Personal", "status": status,
                "progress": progress, "notes": clean(value.get("notes"), 12000), "url": url}
    if kind == "task":
        priority = value.get("priority", "normal")
        if priority not in {"low", "normal", "high"}:
            raise ValueError("Choose a valid priority.")
        return {"done": value.get("done") is True, "due": iso_day(value.get("due")),
                "priority": priority, "notes": clean(value.get("notes"), 8000),
                "project": clean(value.get("project"), 32)}
    if kind == "note":
        return {"text": clean(value.get("text"), 24000), "tag": clean(value.get("tag"), 70)}
    start = clean(value.get("start"), 30, True)
    end = clean(value.get("end"), 30)
    try:
        start_date = datetime.fromisoformat(start)
        if end and datetime.fromisoformat(end) < start_date:
            raise ValueError()
    except (ValueError, TypeError):
        raise ValueError("Choose valid event times; the end cannot precede the start.") from None
    return {"start": start, "end": end, "location": clean(value.get("location"), 200),
            "notes": clean(value.get("notes"), 8000), "source": "local"}


def decode_record(row):
    return {"id": row["id"], "kind": row["kind"], "title": row["title"],
            "payload": json.loads(row["payload"]), "created": row["created"],
            "updated": row["updated"], "deleted": row["deleted"]}


def records(include_trash=False):
    with database() as conn:
        rows = conn.execute("SELECT * FROM records WHERE deleted IS " + ("NOT NULL" if include_trash else "NULL") + " ORDER BY updated DESC LIMIT 1000").fetchall()
    return [decode_record(row) for row in rows]


def preferences():
    with database() as conn:
        row = conn.execute("SELECT value FROM preferences WHERE key='profile'").fetchone()
    return {**PROFILE, **(json.loads(row[0]) if row else {})}


def files(include_trash=False):
    with database() as conn:
        rows = conn.execute("SELECT id,name,mime,size,received,folder,status,created,checksum,deleted FROM files WHERE deleted IS " + ("NOT NULL" if include_trash else "NULL") + " ORDER BY created DESC LIMIT 1000").fetchall()
    return [dict(row) for row in rows]


def inventory():
    """Shallow directory metadata only; never index document contents or secrets."""
    result = []
    try:
        for folder in sorted(ROOT.parent.iterdir(), key=lambda p: p.name.casefold()):
            if folder.name.startswith(".") or folder.is_symlink() or not folder.is_dir():
                continue
            result.append({"name": folder.name, "modified": folder.stat().st_mtime,
                           "current": folder == ROOT, "source": "workspace sibling folder"})
            if len(result) >= 40:
                break
    except OSError:
        pass
    return result


def system_metrics():
    with LOCK:
        now = time.monotonic()
        if _telemetry["value"] and now - _telemetry["at"] < 5:
            return _telemetry["value"]
        disk = shutil.disk_usage(ROOT)
        result = {"success": True, "sampled_at": time.time(), "platform": platform.system(),
                  "architecture": platform.machine(), "cpu": None, "memory": None,
                  "gpu": None, "temperature": None, "network": None,
                  "disk": {"total": disk.total, "used": disk.used, "free": disk.free,
                           "percent": round(disk.used / disk.total * 100, 1)},
                  "source": "Local OS / Python standard library", "notice": "GPU and temperature readers are not installed."}
        try:
            import psutil
            cpu = psutil.cpu_percent(interval=None)
            result["cpu"] = cpu if _telemetry["at"] else None
            memory = psutil.virtual_memory()
            result["memory"] = {"percent": memory.percent, "total": memory.total, "available": memory.available}
            net = psutil.net_io_counters()
            prior = _telemetry["net"]
            elapsed = now - _telemetry["at"]
            result["network"] = {"received": net.bytes_recv, "sent": net.bytes_sent,
                                 "receive_rate": max(0, (net.bytes_recv-prior[0])/elapsed) if prior and elapsed > 0 else None,
                                 "send_rate": max(0, (net.bytes_sent-prior[1])/elapsed) if prior and elapsed > 0 else None}
            _telemetry["net"] = (net.bytes_recv, net.bytes_sent)
            result["source"] = "Local OS / psutil"
        except (ImportError, OSError, RuntimeError):
            result["notice"] = "CPU, memory, GPU and network telemetry require a supported local reader. Unavailable metrics are not estimated."
        _telemetry.update(at=now, value=result)
        return result


def get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": "PRISM-OS/1.0 local personal workspace"})
    with urllib.request.urlopen(request, timeout=9) as response:
        raw = response.read(2 * 1024 * 1024 + 1)
    if len(raw) > 2 * 1024 * 1024:
        raise ValueError("Provider response exceeded the size limit.")
    return json.loads(raw)


def weather(city, country):
    city = clean(city, 120) or PROFILE["city"]
    country = clean(country, 2).upper() or "AU"
    if not re.fullmatch(r"[A-Z]{2}", country):
        raise ValueError("Use a two-letter weather country code.")
    key = (city.casefold(), country)
    with LOCK:
        previous = _weather.get(key)
        if previous and time.time()-previous["checked_at"] < 600:
            return previous
    try:
        query = urllib.parse.urlencode({"name": city, "countryCode": country, "count": 10, "language": "en", "format": "json"})
        locations = get_json("https://geocoding-api.open-meteo.com/v1/search?"+query).get("results", [])
        locations = [location for location in locations if location.get("country_code") == country]
        if not locations:
            raise ValueError("No matching location in the selected country.")
        location = locations[0]
        query = urllib.parse.urlencode({"latitude": location["latitude"], "longitude": location["longitude"],
                                       "current": "temperature_2m,weather_code,is_day,wind_speed_10m,relative_humidity_2m",
                                       "daily": "temperature_2m_max,temperature_2m_min", "forecast_days": 3, "timezone": "auto"})
        data = get_json("https://api.open-meteo.com/v1/forecast?"+query)
        if not isinstance(data.get("current", {}).get("temperature_2m"), (int, float)):
            raise ValueError("Weather measurements were unavailable.")
        result = {"success": True, "checked_at": time.time(), "stale": False, "source": "Open-Meteo / GeoNames",
                  "source_url": "https://open-meteo.com/", "city": location["name"], "region": location.get("admin1", ""),
                  "country": country, "timezone": data.get("timezone"), "current": data["current"], "daily": data.get("daily", {})}
        with LOCK:
            if len(_weather) >= 24:
                _weather.pop(next(iter(_weather)))
            _weather[key] = result
        return result
    except Exception as error:
        LOG.warning("PRISM weather unavailable: %s", type(error).__name__)
        return {**(previous or {}), "success": False, "stale": bool(previous), "error": "Weather is temporarily unavailable. Check the location or try again later."}


def handle_get(path, query):
    action = path.rstrip("/").rsplit("/", 1)[-1]
    if action == "summary":
        stored = records()
        local_files = files()
        return {"success": True, "profile": preferences(), "records": stored, "files": local_files,
                "folders": inventory(), "storage": {"used": sum(f["size"] for f in local_files if f["status"] == "ready"),
                                                       "scope": "Files imported into PRISM", "limit": MAX_STORAGE},
                "privacy": "Local, unencrypted workspace database. Existing services and credentials are stored separately."}
    if action == "system":
        return system_metrics()
    if action == "weather":
        profile = preferences()
        return weather(query.get("city", [profile["city"]])[0], query.get("country", [profile["country"]])[0])
    if action == "trash":
        return {"success": True, "records": records(True), "files": files(True)}
    if action == "export":
        return {"success": True, "format": "prism-workspace-backup", "version": 1, "exported_at": time.time(),
                "records": records(), "trash": records(True), "files": files(), "profile": preferences(),
                "notice": "File metadata only. Download important file contents separately. Provider credentials are not included."}
    if action == "file":
        file_id = identifier(query.get("id", [""])[0])
        with database() as conn:
            row = conn.execute("SELECT * FROM files WHERE id=? AND deleted IS NULL AND status='ready'", (file_id,)).fetchone()
        if not row:
            raise ValueError("That file is unavailable.")
        file_path = DATA / "files" / file_id
        if file_path.is_symlink() or not file_path.is_file() or file_path.stat().st_size > MAX_FILE:
            raise ValueError("That file is unavailable.")
        return {"success": True, "id": file_id, "name": row["name"], "mime": row["mime"],
                "content": base64.b64encode(file_path.read_bytes()).decode("ascii")}
    raise ValueError("That PRISM route is not available.")


def handle_post(path, body):
    action = path.rstrip("/").rsplit("/", 1)[-1]
    if not isinstance(body, dict):
        raise ValueError("A JSON object is required.")
    if action == "record":
        kind = body.get("kind")
        if kind not in KINDS:
            raise ValueError("Choose a supported workspace item.")
        title = clean(body.get("title"), 160, True)
        payload = record_payload(kind, body.get("payload", {}))
        item_id = identifier(body["id"]) if body.get("id") else uuid.uuid4().hex
        now = time.time()
        with database() as conn:
            row = conn.execute("SELECT kind,updated FROM records WHERE id=?", (item_id,)).fetchone()
            if row and row["kind"] != kind:
                raise ValueError("The item type cannot be changed.")
            if row and body.get("expected_updated") is not None and row["updated"] != body["expected_updated"]:
                raise ValueError("This item changed elsewhere. Reload it before saving to avoid replacing newer work.")
            if row:
                conn.execute("UPDATE records SET title=?,payload=?,updated=? WHERE id=?", (title, json.dumps(payload), now, item_id))
            else:
                count = conn.execute("SELECT COUNT(*) FROM records").fetchone()[0]
                if count >= 1000:
                    raise ValueError("This workspace has reached its 1,000-item limit. Export a backup before reorganizing it.")
                conn.execute("INSERT INTO records VALUES(?,?,?,?,?,?,NULL)", (item_id, kind, title, json.dumps(payload), now, now))
        return {"success": True, "id": item_id, "updated": now}
    if action in {"trash", "restore"}:
        item_id = identifier(body.get("id"))
        table = "files" if body.get("kind") == "file" else "records"
        with database() as conn:
            found = conn.execute(f"SELECT id FROM {table} WHERE id=?", (item_id,)).fetchone()
            if not found:
                raise ValueError("That item was not found.")
            conn.execute(f"UPDATE {table} SET deleted=? WHERE id=?", (time.time() if action == "trash" else None, item_id))
        return {"success": True}
    if action == "profile":
        value = body.get("profile", {})
        if not isinstance(value, dict):
            raise ValueError("Profile settings must be an object.")
        profile = preferences()
        for key, maximum in {"name": 70, "city": 120, "country": 2, "timezone": 80}.items():
            if key in value:
                profile[key] = clean(value[key], maximum, True)
        profile["country"] = profile["country"].upper()
        if not re.fullmatch(r"[A-Z]{2}", profile["country"]):
            raise ValueError("Use a two-letter country code.")
        try:
            ZoneInfo(profile["timezone"])
        except (ZoneInfoNotFoundError, ValueError):
            raise ValueError("Choose a valid time zone, such as Australia/Melbourne.") from None
        if "effects" in value:
            if value["effects"] not in {"reduced", "balanced", "maximum"}:
                raise ValueError("Choose a supported effects level.")
            profile["effects"] = value["effects"]
        for key in ("focus", "contrast"):
            if key in value:
                profile[key] = value[key] is True
        with database() as conn:
            conn.execute("INSERT OR REPLACE INTO preferences VALUES('profile',?)", (json.dumps(profile),))
        return {"success": True, "profile": profile}
    if action == "upload-start":
        name = clean(body.get("name"), 200, True)
        if "/" in name or "\\" in name or any(ord(c) < 32 for c in name) or name in {".", ".."}:
            raise ValueError("Choose a file with an ordinary filename.")
        size = body.get("size")
        if isinstance(size, bool) or not isinstance(size, int) or not 0 <= size <= MAX_FILE:
            raise ValueError("Files must be 25 MB or smaller.")
        folder = clean(body.get("folder"), 80) or "Files"
        mime = clean(body.get("mime"), 100) or "application/octet-stream"
        file_id = uuid.uuid4().hex
        with database() as conn:
            allocated = conn.execute("SELECT COALESCE(SUM(size),0) FROM files").fetchone()[0]
            if allocated + size > MAX_STORAGE:
                raise ValueError("PRISM's local import allowance is full. Files in Trash still count toward storage.")
            file_dir = DATA / "files"
            file_dir.mkdir(mode=0o700, exist_ok=True)
            with open(file_dir / file_id, "xb") as stream:
                os.chmod(stream.name, 0o600)
            conn.execute("INSERT INTO files(id,name,mime,size,folder,status,created) VALUES(?,?,?,?,?,'uploading',?)", (file_id, name, mime, size, folder, time.time()))
        return {"success": True, "id": file_id, "chunk_size": 32768}
    if action == "upload-chunk":
        file_id = identifier(body.get("id"))
        encoded = body.get("content")
        if not isinstance(encoded, str) or len(encoded) > 44000:
            raise ValueError("That upload chunk is too large.")
        try:
            chunk = base64.b64decode(encoded, validate=True)
        except (ValueError, TypeError):
            raise ValueError("That upload chunk is invalid.") from None
        if len(chunk) > 32768:
            raise ValueError("That upload chunk is too large.")
        with database() as conn:
            row = conn.execute("SELECT * FROM files WHERE id=? AND status='uploading' AND deleted IS NULL", (file_id,)).fetchone()
            if not row or body.get("offset") != row["received"] or row["received"] + len(chunk) > row["size"]:
                raise ValueError("The upload position changed. Start this file again.")
            file_path = DATA / "files" / file_id
            if file_path.is_symlink():
                raise ValueError("The upload destination is unavailable.")
            with open(file_path, "r+b") as stream:
                stream.seek(row["received"])
                stream.write(chunk)
                stream.truncate(row["received"] + len(chunk))
            received = row["received"] + len(chunk)
            checksum = None
            status = "uploading"
            if received == row["size"]:
                checksum = hashlib.sha256(file_path.read_bytes()).hexdigest()
                status = "ready"
            conn.execute("UPDATE files SET received=?,status=?,checksum=? WHERE id=?", (received, status, checksum, file_id))
        return {"success": True, "received": received, "status": status}
    raise ValueError("That PRISM action is not available.")
