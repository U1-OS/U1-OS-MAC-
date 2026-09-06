"""Attributed news headlines and indicative share-market snapshots, with explicit freshness."""
from concurrent.futures import ThreadPoolExecutor
import email.utils
import hashlib
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


def fetch(url):
    request = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; U1OS/2.0; personal local dashboard)',
        'Accept': 'application/json, application/rss+xml, application/xml, text/xml',
    })
    with urllib.request.urlopen(request, timeout=8) as response:
        content = response.read(2_000_001)
    if len(content) > 2_000_000:
        raise ValueError('Provider response exceeds the size limit')
    return content


def snapshot(key, seconds, loader):
    with LOCK:
        # Keep user-selected symbol caches bounded without removing in-flight locks.
        if len(KEY_LOCKS) >= 256 and key not in KEY_LOCKS:
            return dict(success=False, stale=False, error='Too many distinct feed requests. Restart the app to clear the feed cache.')
        guard = KEY_LOCKS.setdefault(key, threading.Lock())
    with guard:
        with LOCK:
            previous = CACHE.get(key)
            if previous and time.time() - previous['attempted_at'] < seconds:
                return dict(previous)
        try:
            result = loader()
            result.update(success=True, stale=False, fetched_at=time.time(), error=None)
        except Exception:
            result = dict(previous or {})
            result.update(success=False, stale=bool(previous and previous.get('fetched_at')),
                          error='Provider unavailable or access restricted. Any retained data is stale.')
        result.update(attempted_at=time.time(), refresh_seconds=seconds)
        with LOCK:
            CACHE[key] = result
        return dict(result)


def news(category):
    if category not in SOURCES:
        raise ValueError('Choose australia, world, business or technology')
    name, endpoint, source_url = SOURCES[category]

    def load():
        content = fetch(endpoint)
        if b'<!DOCTYPE' in content.upper() or b'<!ENTITY' in content.upper():
            raise ValueError('Unsupported feed declaration')
        root = ET.fromstring(content)
        channel = root.find('channel')
        if root.tag != 'rss' or channel is None:
            raise ValueError('The provider did not return an RSS feed')
        items = []
        for row in channel.findall('item')[:40]:
            title = (row.findtext('title') or '').strip()[:400]
            link = (row.findtext('link') or '').strip()
            parsed = urllib.parse.urlsplit(link)
            allowed = ('theguardian.com',) if category == 'australia' else ('bbc.com', 'bbc.co.uk')
            if not title or parsed.scheme not in {'http', 'https'} or not any(parsed.hostname == host or (parsed.hostname or '').endswith('.' + host) for host in allowed):
                continue
            try:
                published = email.utils.parsedate_to_datetime(row.findtext('pubDate') or '').timestamp()
            except (ValueError, TypeError, AttributeError):
                published = None
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
