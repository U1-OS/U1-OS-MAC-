# Native Discovery v1

Owned assets: static/js/u1-discovery-workspace.js and static/css/u1-discovery-workspace.css.
Backend: utils/u1_discovery.py. Tests: tests/test_u1_discovery.py.

## Parent integration contract

Load CSS and classic JavaScript after U1CoreViews. The script automatically registers
tech-gaming and sports-news; exports window.U1Discovery.register(core) for explicit registration.
Both render functions receive the native host element. Add normal data-go navigation/search entries.
No iframe, legacy page, shared-shell edit, custom browser or package is required.

Add GET /api/workspace/discovery at the existing authenticated/read-gated workspace dispatch.
Import utils.u1_discovery and return u1_discovery.handle_get(query), where query is the existing
urllib.parse.parse_qs dictionary. Invalid input raises ValueError for the parent's standard 400 handling.
With no query, return the read-only source catalogue without fetching. With source=<id>, return one snapshot.
Source IDs: playstation, xbox, afl, cricket, boxing, mma. No other query parameters are accepted.
Do not add a POST route. Do not expose a URL parameter. Preserve the parent's safety/session gate.

Existing GET /api/workspace/live/news?category=technology|australia|world|business is consumed
directly by the UI and remains delegated to news_markets. No stock or usage code is touched.

Snapshot fields: success, stale, source, source_url, fetched_at, attempted_at,
refresh_seconds, items[{id,title,url,source,published_at}], newest_published_at,
feed_age_warning, notice and optional coverage. Times are Unix seconds; missing dates stay unknown.
The new module reuses news_markets.snapshot and its cache/coalescing/failure-retention semantics.
Refresh observes the existing 300-second TTL; it does not bypass the cache or start background polling.

## Actual coverage and verification

On 2026-09-08, six bounded, read-only public requests returned HTTP 200 and valid RSS:

| Topic | Official publisher endpoint | Items at verification | Newest publication at verification |
| --- | --- | --- | --- |
| PlayStation | https://blog.playstation.com/feed/ | 10 | 2026-09-04 16:00:40 UTC |
| Xbox | https://news.xbox.com/en-us/feed/ | 10 | 2026-09-07 20:00:00 UTC |
| AFL | https://www.theguardian.com/sport/afl/rss | 20 | 2026-09-08 04:28:48 UTC |
| Cricket | https://www.theguardian.com/sport/cricket/rss | 20 | 2026-09-08 08:52:07 UTC |
| Boxing | https://www.theguardian.com/sport/boxing/rss | 20 | 2026-09-05 22:18:48 UTC |
| UFC / MMA | https://www.theguardian.com/sport/ufc/rss | 20 | 2026-08-04 20:15:58 UTC |

Browser research could not render RSS MIME types; bounded direct XML reads verified these exact endpoints.
These are publisher feeds, not league-authorised scoreboard APIs or endorsements.
Sports coverage is headlines only. No live scores, fixtures, match statuses, all-promotion MMA coverage,
streaming rights or subscriptions are supplied. Empty feed and failed request are distinct states.
The older boxing/UFC/gaming feed publications receive the same 48-hour warning as any other old feed.
Feed availability and publication dates can change after this verification.

## Safety and setup limitations

No account, token, Keychain write, paid API, image download or media reproduction is required.
The backend fetches only six fixed HTTPS URLs, rejects redirects and compressed responses,
uses a five-second socket timeout and a twelve-second elapsed-read deadline checked between reads
(an in-flight read can extend to its socket timeout), caps XML at 1 MB and output at 24 headlines.
DTD/entities, non-UTF-8 XML and non-publisher/credential-bearing story URLs are rejected.
The legacy existing news adapter retains its own bounds; it is reused, not rewritten by this sidecar.
New feeds copy titles, source names and publication dates only, with links to the full original stories.
Publisher terms apply. This personal-use reader does not grant commercial syndication rights.

The UI uses textContent, validates link protocols, has explicit external-link names, topic and text
filters, disabled refresh/loading announcements and visible retrieval/publication times. Failed refresh
retains an available snapshot as stale. No freshness heartbeat or browser-background polling is added;
freshness is re-evaluated on render, filter change and refresh, not continuously while left idle.
Parent route/asset wiring, restarted-server HTTP acceptance, mobile layout, keyboard/screen-reader
acceptance and real-browser screenshots remain parent-owned and were not performed by this sidecar.

Offline test command: python3 -m unittest discover -s tests -p test_u1_discovery.py
The JavaScript contract subtest requires local Node.js. All unit-test feeds are fixtures; no test logs in or calls paid services.
