"""Fixed public RSS sources for Discovery; existing news/cache adapters are reused."""
import email.utils
import hashlib
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from utils import news_markets

MAX_BYTES = 1_000_000
MAX_ITEMS = 24
REFRESH_SECONDS = 300
SOURCES = {
    'playstation': ('PlayStation Blog', 'gaming', 'https://blog.playstation.com/feed/', 'https://blog.playstation.com/', ('playstation.com',)),
    'xbox': ('Xbox Wire', 'gaming', 'https://news.xbox.com/en-us/feed/', 'https://news.xbox.com/en-us/', ('xbox.com',)),
    'afl': ('The Guardian / AFL', 'afl', 'https://www.theguardian.com/sport/afl/rss', 'https://www.theguardian.com/sport/afl', ('theguardian.com',)),
    'cricket': ('The Guardian / Cricket', 'cricket', 'https://www.theguardian.com/sport/cricket/rss', 'https://www.theguardian.com/sport/cricket', ('theguardian.com',)),
    'boxing': ('The Guardian / Boxing', 'boxing', 'https://www.theguardian.com/sport/boxing/rss', 'https://www.theguardian.com/sport/boxing', ('theguardian.com',)),
    'mma': ('The Guardian / UFC', 'mma', 'https://www.theguardian.com/sport/ufc/rss', 'https://www.theguardian.com/sport/ufc', ('theguardian.com',)),
}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    """A publisher redirect requires a reviewed catalogue change, not another fetch."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Feed redirects are not allowed')


def source_info(source):
    name, category, endpoint, page, _ = SOURCES[source]
    return dict(id=source, source=name, category=category, source_url=page,
                feed_url=endpoint, kind='publisher_headlines',
                coverage='UFC headlines only; not all MMA promotions.' if source == 'mma'
                else 'Publisher headlines only; no scores, fixtures or match-state service.')


def fetch_feed(source):
    """No URL argument: six code-owned HTTPS targets, no redirects, no credentials."""
    endpoint = SOURCES[source][2]
    request = urllib.request.Request(endpoint, headers={
        'User-Agent': 'U1OS/2.0 personal-local-dashboard',
        'Accept': 'application/rss+xml, application/xml, text/xml',
        'Accept-Encoding': 'identity',
    })
    deadline = time.monotonic() + 12
    with urllib.request.build_opener(NoRedirect()).open(request, timeout=5) as response:
        if response.geturl() != endpoint:
            raise ValueError('Unexpected feed destination')
        if response.headers.get('Content-Encoding', 'identity').lower() != 'identity':
            raise ValueError('Compressed feed responses are not accepted')
        chunks, size = [], 0
        read = getattr(response, 'read1', response.read)
        while True:
            if time.monotonic() >= deadline:
                raise ValueError('Feed read deadline exceeded')
            chunk = read(min(65536, MAX_BYTES + 1 - size))
            if not chunk:
                return b''.join(chunks)
            size += len(chunk)
            if size > MAX_BYTES:
                raise ValueError('Feed exceeds the size limit')
            chunks.append(chunk)


def safe_link(value, hosts):
    if not isinstance(value, str) or len(value) > 2000 or any(ord(c) < 32 for c in value):
        return None
    try:
        parsed = urllib.parse.urlsplit(value)
        host = (parsed.hostname or '').lower()
        if (parsed.scheme not in {'http', 'https'} or parsed.username is not None
                or parsed.password is not None or parsed.port not in {None, 80, 443}
                or not any(host == h or host.endswith('.' + h) for h in hosts)):
            return None
        return value
    except ValueError:
        return None


def parse_feed(source, raw):
    if len(raw) > MAX_BYTES:
        raise ValueError('Feed exceeds the size limit')
    # UTF-8 only prevents UTF-16/32 encodings bypassing declaration checks.
    xml = raw.decode('utf-8-sig', errors='strict')
    if '\x00' in xml or '<!DOCTYPE' in xml.upper() or '<!ENTITY' in xml.upper():
        raise ValueError('Unsupported XML declaration')
    root = ET.fromstring(xml)
    channel = root.find('channel')
    if root.tag != 'rss' or channel is None:
        raise ValueError('Expected a publisher RSS feed')
    name, category, _, page, hosts = SOURCES[source]
    items, seen = [], set()
    for row in channel.findall('item')[:60]:
        title = ' '.join((row.findtext('title') or '').split())[:400]
        link = safe_link((row.findtext('link') or '').strip(), hosts)
        if not title or not link or link in seen:
            continue
        seen.add(link)
        try:
            date = email.utils.parsedate_to_datetime(row.findtext('pubDate') or '')
            published = date.timestamp() if date.tzinfo is not None else None
        except (TypeError, ValueError, OverflowError, AttributeError):
            published = None
        items.append(dict(id=hashlib.sha256(link.encode()).hexdigest()[:24],
                          title=title, url=link, source=name, published_at=published))
    items.sort(key=lambda item: item['published_at'] or 0, reverse=True)
    newest = max((item['published_at'] or 0 for item in items), default=0)
    return dict(source=name, source_url=page, category=category, items=items[:MAX_ITEMS],
                newest_published_at=newest or None,
                feed_age_warning=bool(newest and time.time() - newest > 172800),
                coverage=source_info(source)['coverage'],
                notice='Attributed publisher headlines and links only. No copied articles or images. '
                       'Personal use; publisher terms apply. A successful fetch is not a live score feed.')


def handle_get(query):
    """Parent: GET /api/workspace/discovery -> handle_get(parse_qs(query))."""
    if not isinstance(query, dict) or set(query) - {'source'}:
        raise ValueError('Only a fixed source ID is accepted')
    if 'source' not in query:
        return dict(success=True, sources=[source_info(key) for key in SOURCES],
                    refresh_seconds=REFRESH_SECONDS, read_only=True)
    values = query['source']
    if not isinstance(values, list) or len(values) != 1 or values[0] not in SOURCES:
        raise ValueError('Unknown Discovery source')
    source = values[0]
    result = news_markets.snapshot('discovery:' + source, REFRESH_SECONDS,
                                  lambda: parse_feed(source, fetch_feed(source)))
    result.setdefault('items', [])
    for key, value in source_info(source).items():
        result.setdefault(key, value)
    return result
