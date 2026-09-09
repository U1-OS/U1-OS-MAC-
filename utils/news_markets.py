"""Attributed news headlines and indicative share-market snapshots, with explicit freshness."""
from concurrent.futures import ThreadPoolExecutor
import email.utils
import hashlib
import ipaddress
import json
import math
import re
import threading
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

LOCK = threading.RLock()
CACHE = {}
KEY_LOCKS = {}
POOL = ThreadPoolExecutor(max_workers=3, thread_name_prefix='u1-public-market')
SOURCES = {
    'australia': ('Guardian Australia', 'https://www.theguardian.com/australia-news/rss', 'https://www.theguardian.com/australia-news'),
    'world': ('BBC News', 'https://feeds.bbci.co.uk/news/world/rss.xml', 'https://www.bbc.com/news/world'),
    'business': ('BBC News', 'https://feeds.bbci.co.uk/news/business/rss.xml', 'https://www.bbc.com/news/business'),
    'technology': ('BBC News', 'https://feeds.bbci.co.uk/news/technology/rss.xml', 'https://www.bbc.com/news/technology'),
}
DEFAULT_SYMBOLS = ['BHP.AX', 'CBA.AX', 'AAPL', 'MSFT', 'NVDA', 'SPY']


MAX_CACHE_KEYS = 256
FAILURE_SECONDS = 60
MAX_FEED_BYTES = 2_000_000
KEY_USERS = {}
KEY_TOUCHED = {}
FETCH_HOSTS = frozenset({
    'feeds.bbci.co.uk', 'www.theguardian.com', 'query1.finance.yahoo.com',
    'wttr.in', 'news.ycombinator.com',
})


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Provider redirects require a reviewed endpoint change')


def safe_story_url(value, hosts=()):
    if not isinstance(value, str) or len(value) > 2000 or any(ord(c) < 32 for c in value):
        return None
    try:
        parsed = urllib.parse.urlsplit(value)
        host = (parsed.hostname or '').lower()
        if (parsed.scheme not in {'http', 'https'} or not host
                or parsed.username is not None or parsed.password is not None
                or parsed.port not in {None, 80, 443}):
            return None
        if hosts and not any(host == item or host.endswith('.' + item) for item in hosts):
            return None
        if host == 'localhost' or host.endswith(('.localhost', '.local')) or '.' not in host and ':' not in host:
            return None
        try:
            if not ipaddress.ip_address(host).is_global:
                return None
        except ValueError:
            pass
        return value
    except ValueError:
        return None


def published_time(value):
    try:
        date = email.utils.parsedate_to_datetime(value or '')
        result = date.timestamp() if date.tzinfo is not None else None
        return result if result is not None and math.isfinite(result) else None
    except (ValueError, TypeError, AttributeError, OverflowError):
        return None


def rss_channel(content):
    if not isinstance(content, (bytes, bytearray)) or len(content) > MAX_FEED_BYTES:
        raise ValueError('Provider response exceeds the size limit or is not bytes')
    # Decode before checking declarations. UTF-16/32 cannot hide markers behind NULs.
    text = content.decode('utf-8-sig', errors='strict')
    if '\x00' in text or '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise ValueError('Unsupported feed declaration or encoding')
    root = ET.fromstring(text)
    channel = root.find('channel')
    if root.tag != 'rss' or channel is None:
        raise ValueError('The provider did not return an RSS feed')
    return channel


def fetch(url):
    parsed = urllib.parse.urlsplit(url)
    if (parsed.scheme != 'https' or parsed.hostname not in FETCH_HOSTS
            or parsed.username is not None or parsed.password is not None
            or parsed.port not in {None, 443}):
        raise ValueError('Only fixed public provider endpoints are supported')
    request = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; U1OS/2.0; personal local dashboard)',
        'Accept': 'application/json, application/rss+xml, application/xml, text/xml',
        'Accept-Encoding': 'identity',
    })
    deadline = time.monotonic() + 12
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=8) as response:
        if response.geturl() != url or response.headers.get('Content-Encoding', 'identity').lower() != 'identity':
            raise ValueError('Unexpected provider destination or content encoding')
        read = getattr(response, 'read1', response.read)
        chunks, size = [], 0
        while True:
            if time.monotonic() >= deadline:
                raise ValueError('Provider read deadline exceeded')
            chunk = read(min(65536, MAX_FEED_BYTES + 1 - size))
            if not chunk:
                return b''.join(chunks)
            size += len(chunk)
            if size > MAX_FEED_BYTES:
                raise ValueError('Provider response exceeds the size limit')
            chunks.append(chunk)


def snapshot(key, seconds, loader):
    with LOCK:
        if key not in KEY_LOCKS:
            if len(KEY_LOCKS) >= MAX_CACHE_KEYS:
                unused = [item for item, lock in KEY_LOCKS.items()
                          if KEY_USERS.get(item, 0) == 0 and not lock.locked()]
                if not unused:
                    return dict(success=False, stale=False, refresh_seconds=1,
                                error='Feed cache is busy. Retry after the current requests finish.')
                victim = min(unused, key=lambda item: KEY_TOUCHED.get(item, 0))
                for mapping in (CACHE, KEY_LOCKS, KEY_USERS, KEY_TOUCHED):
                    mapping.pop(victim, None)
            KEY_LOCKS[key] = threading.Lock()
        guard = KEY_LOCKS[key]
        # Reserve before waiting on the per-key lock: queued callers prevent eviction too.
        KEY_USERS[key] = KEY_USERS.get(key, 0) + 1
        KEY_TOUCHED[key] = time.monotonic()
    try:
        with guard:
            with LOCK:
                previous = CACHE.get(key)
                ttl = min(seconds, FAILURE_SECONDS) if previous and previous.get('success') is False else seconds
                if previous and time.time() - previous['attempted_at'] < ttl:
                    return dict(previous)
            try:
                result = loader()
                if not isinstance(result, dict) or result.get('success') is False:
                    raise ValueError('The provider did not supply a successful snapshot')
                result.update(success=True, stale=False, fetched_at=time.time(), error=None)
            except Exception:
                result = dict(previous or {})
                result.update(success=False, stale=bool(previous and previous.get('fetched_at')),
                              error='Provider unavailable or access restricted. Any retained data is stale.')
            result.update(attempted_at=time.time(),
                          refresh_seconds=seconds if result['success'] else min(seconds, FAILURE_SECONDS))
            with LOCK:
                CACHE[key] = result
            return dict(result)
    finally:
        with LOCK:
            KEY_USERS[key] -= 1
            KEY_TOUCHED[key] = time.monotonic()


def news(category):
    if category not in SOURCES:
        raise ValueError('Choose australia, world, business or technology')
    name, endpoint, source_url = SOURCES[category]

    def load():
        channel = rss_channel(fetch(endpoint))
        items, seen = [], set()
        for row in channel.findall('item')[:40]:
            title = (row.findtext('title') or '').strip()[:400]
            link = (row.findtext('link') or '').strip()
            allowed = ('theguardian.com',) if category == 'australia' else ('bbc.com', 'bbc.co.uk')
            link = safe_story_url(link, allowed)
            if not title or not link or link in seen:
                continue
            seen.add(link)
            published = published_time(row.findtext('pubDate'))
            items.append(dict(id=hashlib.sha256(link.encode()).hexdigest()[:24], title=title,
                              url=link, published_at=published, source=name))
        items.sort(key=lambda item: item['published_at'] or 0, reverse=True)
        newest = max((item['published_at'] or 0 for item in items), default=0)
        return dict(category=category, items=items[:24], source=name, source_url=source_url,
                    newest_published_at=newest or None,
                    feed_age_warning=bool(newest and time.time() - newest > 172800),
                    notice='Publisher RSS headlines only. Article text and images are not copied. Personal use; publisher terms apply.')
    result = snapshot('news:' + category, 300, load)
    result.setdefault('source', name)
    result.setdefault('source_url', source_url)
    return result


def finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def stock(symbol):
    def load():
        endpoint = 'https://query1.finance.yahoo.com/v8/finance/chart/' + urllib.parse.quote(symbol, safe='') + '?range=1d&interval=5m'
        data = json.loads(fetch(endpoint))
        chart = data.get('chart', {})
        if chart.get('error') or not chart.get('result'):
            raise ValueError('Quote unavailable')
        payload = chart['result'][0]
        meta = payload.get('meta', {})
        price, quoted_at = meta.get('regularMarketPrice'), meta.get('regularMarketTime')
        currency = meta.get('currency')
        if not finite(price) or price <= 0 or not finite(quoted_at) or not isinstance(currency, str) or not re.fullmatch(r'[A-Za-z]{3}', currency):
            raise ValueError('Quote is missing its price, timestamp or currency')
        previous_close = meta.get('previousClose', meta.get('chartPreviousClose'))
        change = (price / previous_close - 1) * 100 if finite(previous_close) and previous_close > 0 else None
        bars = (payload.get('indicators', {}).get('quote') or [{}])[0].get('close') or []
        timestamps = payload.get('timestamp') or []
        points = [dict(at=at, price=value) for at, value in zip(timestamps, bars)
                  if finite(at) and finite(value) and value > 0][-100:]
        return dict(symbol=symbol, name=str(meta.get('longName') or meta.get('shortName') or symbol)[:150],
                    price=price, currency=currency, quoted_at=quoted_at, previous_close=previous_close if finite(previous_close) else None,
                    change_percent=change, exchange=str(meta.get('fullExchangeName') or meta.get('exchangeName') or '')[:80],
                    instrument=str(meta.get('instrumentType') or '')[:40], points=points,
                    source='Yahoo Finance', source_url='https://finance.yahoo.com/quote/' + urllib.parse.quote(symbol, safe='') + '/',
                    status='INDICATIVE / MAY BE DELAYED',
                    notice='Latest regular-session snapshot. Public chart access is not a guaranteed or licensed real-time feed. Quote time can predate retrieval, especially outside trading hours.')
    result = snapshot('stock:' + symbol, 300, load)
    result.setdefault('symbol', symbol)
    result.setdefault('source_url', 'https://finance.yahoo.com/quote/' + urllib.parse.quote(symbol, safe='') + '/')
    return result


def stocks(raw):
    if not isinstance(raw, str) or len(raw) > 200:
        raise ValueError('Watchlist is too long')
    symbols = list(dict.fromkeys(item.strip().upper() for item in raw.split(',') if item.strip())) or DEFAULT_SYMBOLS
    if len(symbols) > 8 or any(not re.fullmatch(r'[A-Z0-9^][A-Z0-9.^=\-]{0,15}', symbol) for symbol in symbols):
        raise ValueError('Use up to eight ticker symbols, such as BHP.AX, AAPL and SPY')
    futures = [POOL.submit(stock, symbol) for symbol in symbols]
    rows = [future.result() for future in futures]
    return dict(success=True, quotes=rows, partial=any(not row.get('success') for row in rows),
                fetched_at=time.time(), refresh_seconds=300,
                notice='Indicative quotes; not a broker feed or trading recommendation. Each item retains its own source and observation time.')


def handle_get(path, query):
    if path == 'news':
        return news(query.get('category', ['australia'])[0])
    if path == 'stocks':
        return stocks(query.get('symbols', [','.join(DEFAULT_SYMBOLS)])[0])
    raise ValueError('Unknown news or market endpoint')
