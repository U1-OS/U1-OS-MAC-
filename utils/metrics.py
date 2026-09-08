"""U1 OS // Measurement floor.

The foundation the Improvement Engine stands on: real, locally-collected
measurements about how this workspace actually behaves. Nothing here
estimates, models or fabricates a number. A value that has not been
measured is reported as None so the interface can say NOT MEASURED
rather than invent one.

What is recorded:
  * request latency per endpoint (count, p50, p95, max, error rate)
  * backend exceptions (type, where, count, first and last seen)
  * frontend exceptions reported by the browser
  * process startup time
  * SSE stream reliability (opens, closes, concurrent, session length)
  * CPU and memory sampling, when psutil is installed

Everything is bounded: fixed-size ring buffers, capped cardinality and a
capped on-disk file, so this can run forever without growing without end.

Privacy: measurements stay on this machine. No outbound requests are made
from this module, and no request bodies, query strings, credentials or
user content are stored — only paths, status codes and durations.
"""

import json
import os
import threading
import time
from collections import deque

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STORE_DIR = os.environ.get("PRISM_DATA_DIR") or os.path.join(ROOT, "data")
STORE = os.path.join(STORE_DIR, "metrics.json")

# Bounds — keep memory and disk predictable.
MAX_SAMPLES_PER_ENDPOINT = 200
MAX_ENDPOINTS = 120
MAX_ERROR_KINDS = 80
MAX_RECENT_ERRORS = 60
MAX_RESOURCE_SAMPLES = 120
MAX_BASELINES = 40

_LOCK = threading.RLock()
_STARTED_MONOTONIC = time.monotonic()

_STATE = {
    "process_started_at": time.time(),
    "startup_ms": None,          # set once the server is listening
    "endpoints": {},             # path -> {"samples": deque, "errors": int, "count": int}
    "errors": {},                # signature -> {...}
    "recent_errors": deque(maxlen=MAX_RECENT_ERRORS),
    "frontend_errors": deque(maxlen=MAX_RECENT_ERRORS),
    "sse": {"opened": 0, "closed": 0, "concurrent": 0, "peak_concurrent": 0,
            "session_seconds": deque(maxlen=MAX_SAMPLES_PER_ENDPOINT)},
    "resources": deque(maxlen=MAX_RESOURCE_SAMPLES),
    "baselines": [],
}


# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------
def _percentile(values, pct):
    """Nearest-rank percentile. Returns None for an empty sample."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 2)
    rank = max(1, int(round(pct / 100.0 * len(ordered))))
    return round(ordered[min(rank, len(ordered)) - 1], 2)


def normalise_path(path):
    """Collapse a request path to a low-cardinality label.

    Query strings are dropped entirely (they can carry user input) and long
    or numeric path segments become placeholders, so one endpoint hit with
    many ids stays one row rather than thousands.
    """
    path = (path or "/").split("?")[0].split("#")[0]
    parts = []
    for segment in path.split("/"):
        if not segment:
            continue
        if segment.isdigit():
            parts.append(":n")
        elif len(segment) > 40:
            parts.append(":id")
        else:
            parts.append(segment)
    return "/" + "/".join(parts[:6]) if parts else "/"


# ----------------------------------------------------------------------
# Recording
# ----------------------------------------------------------------------
def mark_ready():
    """Called once the HTTP server is accepting connections."""
    with _LOCK:
        if _STATE["startup_ms"] is None:
            _STATE["startup_ms"] = round((time.monotonic() - _STARTED_MONOTONIC) * 1000, 1)
        return _STATE["startup_ms"]


def record_request(path, method, status, duration_ms):
    label = f"{method} {normalise_path(path)}"
    with _LOCK:
        endpoints = _STATE["endpoints"]
        if label not in endpoints:
            if len(endpoints) >= MAX_ENDPOINTS:
                return
            endpoints[label] = {"samples": deque(maxlen=MAX_SAMPLES_PER_ENDPOINT),
                                "count": 0, "errors": 0, "last_seen": 0.0}
        row = endpoints[label]
        row["samples"].append(float(duration_ms))
        row["count"] += 1
        row["last_seen"] = time.time()
        try:
            if int(status) >= 500:
                row["errors"] += 1
        except (TypeError, ValueError):
            pass


def record_exception(kind, where, message="", origin="backend"):
    """Record a fault. `message` is truncated and never parsed."""
    signature = f"{origin}:{kind}@{where}"
    now = time.time()
    with _LOCK:
        errors = _STATE["errors"]
        if signature not in errors:
            if len(errors) >= MAX_ERROR_KINDS:
                return
            errors[signature] = {"kind": kind, "where": where, "origin": origin,
                                 "count": 0, "first_seen": now, "last_seen": now,
                                 "last_message": ""}
        row = errors[signature]
        row["count"] += 1
        row["last_seen"] = now
        row["last_message"] = str(message)[:300]
        entry = {"kind": kind, "where": where, "origin": origin,
                 "message": str(message)[:300], "at": now}
        if origin == "frontend":
            _STATE["frontend_errors"].append(entry)
        else:
            _STATE["recent_errors"].append(entry)


def sse_opened():
    with _LOCK:
        s = _STATE["sse"]
        s["opened"] += 1
        s["concurrent"] += 1
        s["peak_concurrent"] = max(s["peak_concurrent"], s["concurrent"])


def sse_closed(session_seconds=None):
    with _LOCK:
        s = _STATE["sse"]
        s["closed"] += 1
        s["concurrent"] = max(0, s["concurrent"] - 1)
        if session_seconds is not None:
            s["session_seconds"].append(round(float(session_seconds), 1))


def sample_resources():
    """One CPU/memory sample. Silently does nothing without psutil."""
    try:
        import psutil
    except Exception:
        return None
    try:
        process = psutil.Process(os.getpid())
        with process.oneshot():
            sample = {
                "at": time.time(),
                "cpu_percent": round(process.cpu_percent(interval=None), 1),
                "rss_mb": round(process.memory_info().rss / 1048576, 1),
                "threads": process.num_threads(),
            }
        with _LOCK:
            _STATE["resources"].append(sample)
        return sample
    except Exception:
        return None


# ----------------------------------------------------------------------
# Reading
# ----------------------------------------------------------------------
def endpoint_report():
    with _LOCK:
        rows = []
        for label, row in _STATE["endpoints"].items():
            samples = list(row["samples"])
            rows.append({
                "endpoint": label,
                "count": row["count"],
                "errors": row["errors"],
                "error_rate_pct": round(row["errors"] / row["count"] * 100, 1) if row["count"] else 0.0,
                "p50_ms": _percentile(samples, 50),
                "p95_ms": _percentile(samples, 95),
                "max_ms": round(max(samples), 2) if samples else None,
                "samples": len(samples),
                "last_seen": row["last_seen"],
            })
    rows.sort(key=lambda r: (r["p95_ms"] is None, -(r["p95_ms"] or 0)))
    return rows


def snapshot():
    """Everything measured so far. Unmeasured values are None, never zero."""
    with _LOCK:
        sse = _STATE["sse"]
        sessions = list(sse["session_seconds"])
        resources = list(_STATE["resources"])
        errors = sorted(_STATE["errors"].values(), key=lambda e: -e["count"])
        endpoints = endpoint_report()
        total_requests = sum(r["count"] for r in endpoints)
        total_errors = sum(r["errors"] for r in endpoints)
        latencies = [r["p95_ms"] for r in endpoints if r["p95_ms"] is not None]

        return {
            "success": True,
            "measured_since": _STATE["process_started_at"],
            "uptime_seconds": round(time.monotonic() - _STARTED_MONOTONIC, 1),
            "startup_ms": _STATE["startup_ms"],
            "requests": {
                "total": total_requests,
                "errors": total_errors,
                "error_rate_pct": round(total_errors / total_requests * 100, 2) if total_requests else None,
                "slowest_p95_ms": max(latencies) if latencies else None,
                "endpoints": endpoints[:25],
            },
            "exceptions": {
                "distinct": len(errors),
                "total": sum(e["count"] for e in errors),
                "top": errors[:10],
                "recent_backend": list(_STATE["recent_errors"])[-10:],
                "recent_frontend": list(_STATE["frontend_errors"])[-10:],
            },
            "sse": {
                "opened": sse["opened"],
                "closed": sse["closed"],
                "concurrent": sse["concurrent"],
                "peak_concurrent": sse["peak_concurrent"],
                "median_session_seconds": _percentile(sessions, 50),
                "sessions_recorded": len(sessions),
            },
            "resources": {
                "available": bool(resources),
                "samples": len(resources),
                "cpu_percent": resources[-1]["cpu_percent"] if resources else None,
                "rss_mb": resources[-1]["rss_mb"] if resources else None,
                "threads": resources[-1]["threads"] if resources else None,
                "peak_rss_mb": max((r["rss_mb"] for r in resources), default=None),
                "note": None if resources else "psutil is not installed, so CPU and memory are NOT MEASURED.",
            },
            "baselines": list(_STATE["baselines"])[-MAX_BASELINES:],
        }


def health():
    """A health score derived only from measured values.

    Each component returns None when its input has not been measured, and
    the score is the mean of the components that exist. With nothing
    measured the score itself is None — never a flattering default.
    """
    snap = snapshot()
    components = {}

    error_rate = snap["requests"]["error_rate_pct"]
    if error_rate is not None:
        components["reliability"] = max(0.0, 100.0 - error_rate * 10)

    slowest = snap["requests"]["slowest_p95_ms"]
    if slowest is not None:
        # 100 at or under 100ms, 0 at or over 2000ms, linear between.
        components["performance"] = max(0.0, min(100.0, 100.0 - (slowest - 100) / 19.0))

    startup = snap["startup_ms"]
    if startup is not None:
        components["startup"] = max(0.0, min(100.0, 100.0 - (startup - 250) / 27.5))

    # SSE deliberately has no score component. Opens and closes alone do not
    # distinguish a healthy stream from a dropped one, and a component that
    # always returns 100 would be a fabricated number dressed as a measurement.
    # The raw stream counters are reported in snapshot() instead.

    exceptions = snap["exceptions"]["total"]
    requests = snap["requests"]["total"]
    if requests:
        components["stability"] = max(0.0, 100.0 - (exceptions / requests) * 100 * 5)

    scored = {k: round(v, 1) for k, v in components.items() if v is not None}
    return {
        "success": True,
        "score": round(sum(scored.values()) / len(scored), 1) if scored else None,
        "components": scored,
        "unmeasured": [k for k in ("reliability", "performance", "startup", "stability")
                       if k not in scored],
        "basis": {
            "requests_observed": requests,
            "exceptions_observed": exceptions,
            "uptime_seconds": snap["uptime_seconds"],
        },
        "note": None if scored else "Nothing has been measured yet — the score is NOT MEASURED.",
    }


def capture_baseline(label="baseline"):
    """Freeze the current measurements so a later change can be compared."""
    snap = snapshot()
    entry = {
        "label": str(label)[:60],
        "at": time.time(),
        "startup_ms": snap["startup_ms"],
        "slowest_p95_ms": snap["requests"]["slowest_p95_ms"],
        "error_rate_pct": snap["requests"]["error_rate_pct"],
        "rss_mb": snap["resources"]["rss_mb"],
        "requests_observed": snap["requests"]["total"],
        "health_score": health()["score"],
    }
    with _LOCK:
        _STATE["baselines"].append(entry)
        _STATE["baselines"] = _STATE["baselines"][-MAX_BASELINES:]
    save()
    return entry


def compare_to_baseline(label=None):
    """Compare the live measurements against a stored baseline.

    Returns explicit nulls where either side is unmeasured, so a caller can
    never present a percentage that was not actually computed.
    """
    with _LOCK:
        baselines = list(_STATE["baselines"])
    if not baselines:
        return {"success": False, "available": False,
                "message": "No baseline has been captured yet."}
    base = next((b for b in reversed(baselines) if label is None or b["label"] == label), None)
    if base is None:
        return {"success": False, "available": False,
                "message": f"No baseline named {label!r}."}

    snap = snapshot()
    now = {
        "startup_ms": snap["startup_ms"],
        "slowest_p95_ms": snap["requests"]["slowest_p95_ms"],
        "error_rate_pct": snap["requests"]["error_rate_pct"],
        "rss_mb": snap["resources"]["rss_mb"],
        "health_score": health()["score"],
    }
    deltas = {}
    for key, current in now.items():
        before = base.get(key)
        if before is None or current is None:
            deltas[key] = {"before": before, "after": current,
                           "change_pct": None, "measured": False}
            continue
        change = None if before == 0 else round((current - before) / before * 100, 1)
        deltas[key] = {"before": before, "after": current,
                       "change_pct": change, "measured": True}
    return {"success": True, "available": True, "baseline": base, "current": now, "deltas": deltas}


# ----------------------------------------------------------------------
# Persistence
# ----------------------------------------------------------------------
def save():
    """Persist the durable parts. Sampled latencies stay in memory."""
    try:
        os.makedirs(STORE_DIR, exist_ok=True)
        with _LOCK:
            payload = {
                "saved_at": time.time(),
                "baselines": list(_STATE["baselines"])[-MAX_BASELINES:],
                "errors": _STATE["errors"],
                "sse": {k: v for k, v in _STATE["sse"].items() if k != "session_seconds"},
            }
        tmp = STORE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2)
        os.replace(tmp, STORE)
        return True
    except Exception:
        return False


def load():
    try:
        with open(STORE, encoding="utf-8") as handle:
            payload = json.load(handle)
    except (OSError, ValueError):
        return False
    with _LOCK:
        _STATE["baselines"] = payload.get("baselines", [])[-MAX_BASELINES:]
        stored_errors = payload.get("errors", {})
        if isinstance(stored_errors, dict):
            _STATE["errors"].update({k: v for k, v in list(stored_errors.items())[:MAX_ERROR_KINDS]})
    return True


def reset():
    """Clear the collected measurements.

    `startup_ms` deliberately survives: it is a fact about this running
    process that cannot be re-measured without a restart, and blanking it
    would replace a true value with NOT MEASURED.
    """
    with _LOCK:
        _STATE["endpoints"].clear()
        _STATE["errors"].clear()
        _STATE["recent_errors"].clear()
        _STATE["frontend_errors"].clear()
        _STATE["resources"].clear()
        _STATE["baselines"] = []
        _STATE["sse"] = {"opened": 0, "closed": 0, "concurrent": 0, "peak_concurrent": 0,
                         "session_seconds": deque(maxlen=MAX_SAMPLES_PER_ENDPOINT)}


def start_sampler(interval=60):
    """Background CPU/memory sampling. No-op without psutil."""
    try:
        import psutil  # noqa: F401
    except Exception:
        return False

    def loop():
        while True:
            sample_resources()
            time.sleep(interval)

    threading.Thread(target=loop, name="u1-metrics-sampler", daemon=True).start()
    return True
