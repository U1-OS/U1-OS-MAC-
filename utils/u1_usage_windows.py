"""Pure normalization of separate Codex allowance buckets; no account access."""
import math


def _number(value, minimum=0, maximum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if not math.isfinite(value) or value < minimum:
        return None
    return value if maximum is None or value <= maximum else None


def normalize_rate_limits(result):
    if not isinstance(result, dict):
        return []
    supplied = result.get('rateLimitsByLimitId')
    buckets = dict(supplied) if isinstance(supplied, dict) else {}
    legacy = result.get('rateLimits')
    if isinstance(legacy, dict) and legacy:
        ident = legacy.get('limitId') or 'codex'
        if isinstance(ident, str):
            buckets.setdefault(ident, legacy)
    windows = []
    for key in sorted(buckets, key=lambda item: (item != 'codex', str(item))):
        bucket = buckets[key]
        if not isinstance(key, str) or not isinstance(bucket, dict):
            continue
        ident = bucket.get('limitId') or key
        if not isinstance(ident, str):
            continue
        name = bucket.get('limitName')
        name = name[:120] if isinstance(name, str) and name else ident
        for period in ('primary', 'secondary'):
            window = bucket.get(period)
            if not isinstance(window, dict) or not window:
                continue
            windows.append(dict(
                limit_id=ident, name=name, period=period,
                used_percent=_number(window.get('usedPercent'), maximum=100),
                duration_minutes=_number(window.get('windowDurationMins'), minimum=1),
                resets_at=_number(window.get('resetsAt'), minimum=1),
            ))
    return sorted(windows, key=lambda row: (
        row['limit_id'] != 'codex', row['limit_id'], row['period'] != 'primary'))
