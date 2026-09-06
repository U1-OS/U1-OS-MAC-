"""Public snapshots and explicitly scheduled market sessions for the live bar."""
import datetime as dt
import email.utils
import hashlib
import json
import math
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

LOCK = threading.RLock()
CACHE = {}
FETCH_LOCK = threading.Lock()
ASX_SOURCE = 'https://www.asx.com.au/markets/market-resources/trading-hours-calendar/cash-market-trading-hours/trading-calendar'
NYSE_SOURCE = 'https://www.nyse.com/trade/hours-calendars'
# Published 2026 calendars, retrieved 2026-09-06. Unknown years fail closed.
HOLIDAYS = {
    'ASX': {2026: set('01-01 01-26 04-03 04-06 04-25 06-08 12-25 12-28'.split())},
    'NYSE': {2026: set('01-01 01-19 02-16 04-03 05-25 06-19 07-03 09-07 11-26 12-25'.split())},
}
EARLY = {'ASX': {'2026-12-24': (14, 10), '2026-12-31': (14, 10)},
         'NYSE': {'2026-11-27': (13, 0), '2026-12-24': (13, 0)}}


def fetch(url, limit=2_000_000):
    request = urllib.request.Request(url, headers={'User-Agent': 'U1OS/2.0 personal-local-dashboard'})
    with urllib.request.urlopen(request, timeout=9) as response:
        body = response.read(limit + 1)
    if len(body) > limit:
        raise ValueError('Provider response is too large')
    return body


def cached(key, ttl, loader):
    # Coalesce concurrent tabs; failures retain the original observation timestamp.
    with FETCH_LOCK:
        now = time.time()
        with LOCK:
            old = CACHE.get(key)
            if old and now - old['attempted_at'] < ttl:
                return dict(old)
        try:
            value = loader()
            value.update(success=True, stale=False, fetched_at=time.time(), error=None)
        except Exception:
            value = dict(old or {})
            value.update(success=False, stale=bool(old and old.get('fetched_at')),
                         error='Provider unavailable. Previously received data is not live.')
        value.update(attempted_at=time.time(), refresh_seconds=ttl)
        with LOCK:
            CACHE[key] = value
        return dict(value)


def crypto():
    def load():
        data = json.loads(fetch('https://api.kraken.com/0/public/Ticker?pair=XBTUSD,ETHUSD,SOLUSD'))
        if data.get('error'):
            raise ValueError('Kraken rejected the snapshot request')
        quotes = []
        for key, item in data.get('result', {}).items():
            symbol = 'BTC' if 'XBT' in key else 'ETH' if 'ETH' in key else 'SOL' if 'SOL' in key else None
            price = float(item['c'][0])
            if symbol and math.isfinite(price) and price > 0:
                quotes.append(dict(symbol=symbol, price=price, currency='USD', change_pct=None))
        if not quotes:
            raise ValueError('No usable prices returned')
        return dict(quotes=quotes, source='Kraken REST snapshot', source_url='https://www.kraken.com/prices',
                    notice='Snapshot received at the displayed time, not an execution quote. No 24-hour change is inferred from REST opening prices.')
    return cached('crypto', 30, load)


def warnings():
    def load():
        raw = fetch('https://www.bom.gov.au/fwo/IDZ00059.warnings_vic.xml')
        if b'<!DOCTYPE' in raw.upper() or b'<!ENTITY' in raw.upper():
            raise ValueError('Unsupported XML declaration')
        root = ET.fromstring(raw)
        channel = root.find('channel')
        if root.tag != 'rss' or channel is None:
            raise ValueError('Expected the official RSS feed')
        items = []
        for item in channel.findall('item')[:60]:
            title = (item.findtext('title') or '').strip()[:400]
            link = (item.findtext('link') or '').strip()
            parsed = urllib.parse.urlsplit(link)
            if parsed.scheme not in {'http', 'https'} or not (parsed.hostname == 'bom.gov.au' or (parsed.hostname or '').endswith('.bom.gov.au')):
                continue
            lower = title.lower()
            cancelled = any(word in lower for word in ['cancelled', 'cancellation', 'final warning', 'no warnings'])
            major = not cancelled and any(word in lower for word in ['severe', 'major flood', 'tsunami', 'tropical cyclone', 'extreme', 'catastrophic'])
            try:
                issued = email.utils.parsedate_to_datetime(item.findtext('pubDate') or '').timestamp()
            except (TypeError, ValueError, AttributeError):
                issued = None
            items.append(dict(id=hashlib.sha256((title + link).encode()).hexdigest()[:24], title=title, url=link,
                              issued_at=issued, major=major, classification='Headline-based attention flag, not an official severity rating'))
        return dict(items=items, region='Victoria', source='Australian Bureau of Meteorology',
                    source_url='https://www.bom.gov.au/vic/warnings.shtml',
                    notice='State-wide land and marine warnings, not a location-specific emergency service. Check official warnings directly. RSS is for personal, non-commercial use.')
    return cached('bom-vic', 600, load)


def markets():
    now = dt.datetime.now(dt.timezone.utc)
    rows = []
    for name, zone, opening, closing, source in [
        ('ASX', 'Australia/Sydney', (9, 59, 45), (16, 0), ASX_SOURCE),
        ('NYSE', 'America/New_York', (9, 30), (16, 0), NYSE_SOURCE),
    ]:
        local = now.astimezone(ZoneInfo(zone))
        row = dict(name=name, timezone=zone, source_url=source, mode='Published schedule, not live exchange status',
                   state='unknown', next_event=None, next_at=None, early_close=False)
        if local.year not in HOLIDAYS[name]:
            row['notice'] = 'Calendar update needed for this year. Confirm hours with the exchange.'
            rows.append(row)
            continue
        for offset in range(15):
            day = local.date() + dt.timedelta(days=offset)
            if day.year not in HOLIDAYS[name]:
                break
            if day.weekday() >= 5 or day.strftime('%m-%d') in HOLIDAYS[name][day.year]:
                continue
            start = dt.datetime.combine(day, dt.time(*opening), ZoneInfo(zone))
            end_time = EARLY[name].get(day.isoformat(), closing)
            end = dt.datetime.combine(day, dt.time(*end_time), ZoneInfo(zone))
            if end <= local:
                continue
            is_open = start <= local < end
            row.update(state='scheduled_open' if is_open else 'scheduled_closed', next_event='close' if is_open else 'open',
                       next_at=(end if is_open else start).timestamp(), session_open_at=start.timestamp(),
                       session_close_at=end.timestamp(), early_close=day.isoformat() in EARLY[name])
            break
        row['notice'] = ('Normal cash session; ASX opening has a randomised 15-second window. ' if name == 'ASX' else 'NYSE core equity session only. ') + 'Published 2026 holidays and early closes included. Auctions, extended hours, halts and emergency closures are not monitored.'
        rows.append(row)
    return dict(success=True, generated_at=now.timestamp(), markets=rows, calendar_as_of='2026-09-06')


def handle_get(path):
    if path == 'crypto': return crypto()
    if path == 'warnings': return warnings()
    if path == 'markets': return markets()
    raise ValueError('Unknown live bar feed')
