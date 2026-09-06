#!/usr/bin/env python3
"""
U1 OS — Nitter Alpha Feed Scraper
Real Twitter/X alpha from crypto influencers via Nitter RSS (free, no API key).
"""

import urllib.request
import urllib.error
import re
import time
import xml.etree.ElementTree as ET

# Public Nitter instances (fallback chain)
NITTER_INSTANCES = [
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://nitter.net",
    "https://nitter.1d4.us",
]

SOL_CA_REGEX = re.compile(r'\b[1-9A-HJ-NP-Za-km-z]{32,44}pump\b|\b[1-9A-HJ-NP-Za-km-z]{43,44}\b')
EVM_CA_REGEX = re.compile(r'\b0x[a-fA-F0-9]{40}\b')
TICKER_REGEX = re.compile(r'\$([A-Z]{2,10})\b')
PRICE_REGEX  = re.compile(r'\$[\d,]+\.?\d*[KMB]?')

# Alpha callers to monitor
ALPHA_CALLERS = [
    {"username": "lookonchain",   "display": "Lookonchain Smart Money",     "tier": "WHALE_TRACKER"},
    {"username": "blknoiz06",     "display": "Ansem Alpha Feed",             "tier": "INFLUENCER"},
    {"username": "MustStopMurad", "display": "Murad Supercycle",             "tier": "INFLUENCER"},
    {"username": "dexscreener",   "display": "DEXScreener Trending",         "tier": "DATA"},
    {"username": "solana_alpha",  "display": "Solana Alpha Calls",           "tier": "CALLER"},
    {"username": "DegenSpartan",  "display": "DegenSpartan Alpha",           "tier": "DEGEN"},
]


def _fetch_nitter_rss(username: str, instance: str, timeout: int = 6) -> list:
    """Fetch RSS feed for a username from a Nitter instance."""
    url = f"{instance}/{username}/rss"
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "U1OS/1.0 (RSS Reader)", "Accept": "application/rss+xml"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            content = resp.read().decode("utf-8", errors="replace")
            return _parse_rss(content, username)
    except Exception:
        return []


def _parse_rss(xml_content: str, username: str) -> list:
    """Parse Nitter RSS XML into tweet dicts."""
    items = []
    try:
        root = ET.fromstring(xml_content)
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        channel = root.find("channel")
        if channel is None:
            return []
        for item in channel.findall("item")[:8]:
            title_el  = item.find("title")
            desc_el   = item.find("description")
            link_el   = item.find("link")
            pubdate_el = item.find("pubDate")

            title   = title_el.text  if title_el  is not None else ""
            desc    = desc_el.text   if desc_el   is not None else ""
            link    = link_el.text   if link_el   is not None else ""
            pubdate = pubdate_el.text if pubdate_el is not None else ""

            # Strip HTML from description
            text = re.sub(r'<[^>]+>', ' ', desc or title or "").strip()
            text = re.sub(r'\s+', ' ', text)

            if not text or len(text) < 20:
                continue

            # Extract metadata
            tickers  = list(set(TICKER_REGEX.findall(text)))
            sol_cas  = SOL_CA_REGEX.findall(text)
            evm_cas  = EVM_CA_REGEX.findall(text)
            cas      = list(set(sol_cas + evm_cas))

            # Score sentiment
            bull_words = ["buy", "long", "bullish", "moon", "ath", "pump", "accumulate", "breakout", "whale bought"]
            bear_words = ["sell", "short", "bearish", "dump", "rug", "exit", "caution", "warning"]
            text_lower = text.lower()
            bull_score = sum(1 for w in bull_words if w in text_lower)
            bear_score = sum(1 for w in bear_words if w in text_lower)
            if bull_score > bear_score:
                sentiment = "BULLISH"
            elif bear_score > bull_score:
                sentiment = "BEARISH"
            else:
                sentiment = "NEUTRAL"

            # Velocity from engagement signals
            if any(w in text_lower for w in ["ath", "breaking", "just bought", "whale", "alert"]):
                velocity = "HIGH_SPIKE"
            elif any(w in text_lower for w in ["accumulate", "conviction", "hold"]):
                velocity = "STEADY"
            else:
                velocity = "MODERATE"

            # Parse time
            try:
                import email.utils
                ts = email.utils.parsedate_to_datetime(pubdate).timestamp() if pubdate else time.time()
            except Exception:
                ts = time.time()
            age_secs = time.time() - ts
            if age_secs < 60:
                time_ago = f"{int(age_secs)}s ago"
            elif age_secs < 3600:
                time_ago = f"{int(age_secs/60)}m ago"
            elif age_secs < 86400:
                time_ago = f"{int(age_secs/3600)}h ago"
            else:
                time_ago = f"{int(age_secs/86400)}d ago"

            tweet_id = link.split("/")[-1] if link else f"tw-{int(ts)}"

            items.append({
                "id":                  f"tw-{tweet_id}",
                "username":            f"@{username}",
                "display_name":        username,
                "handle":              f"@{username}",
                "content":             text[:400],
                "text":                text[:400],
                "time_ago":            time_ago,
                "timestamp":           ts,
                "sentiment":           sentiment,
                "velocity":            velocity,
                "tickers":             tickers,
                "contract_addresses":  cas,
                "ca":                  cas[0] if cas else "",
                "token":               tickers[0] if tickers else "",
                "link":                link,
                "engagement":          "Live feed",
                "likes":               0,
                "retweets":            0,
                "source":              "nitter_rss"
            })
    except ET.ParseError:
        pass
    return items


def fetch_all_alpha(max_per_caller: int = 4, timeout: int = 6) -> list:
    """Fetch real alpha tweets from all configured callers.
    
    Tries each Nitter instance until one works per caller.
    Returns merged, time-sorted list of tweets.
    """
    all_tweets = []
    for caller in ALPHA_CALLERS:
        username = caller["username"]
        tweets = []
        for instance in NITTER_INSTANCES:
            tweets = _fetch_nitter_rss(username, instance, timeout)
            if tweets:
                # Enrich with caller metadata
                for tw in tweets[:max_per_caller]:
                    tw["display_name"] = caller["display"]
                    tw["tier"] = caller["tier"]
                all_tweets.extend(tweets[:max_per_caller])
                break

    # Sort by timestamp descending (newest first)
    all_tweets.sort(key=lambda x: x.get("timestamp", 0), reverse=True)

    # Deduplicate by content similarity
    seen = set()
    unique = []
    for tw in all_tweets:
        key = tw["content"][:60]
        if key not in seen:
            seen.add(key)
            unique.append(tw)

    return unique[:30]


def fetch_caller_alpha(username: str, limit: int = 8) -> list:
    """Fetch alpha for a specific caller username."""
    for instance in NITTER_INSTANCES:
        tweets = _fetch_nitter_rss(username.lstrip("@"), instance)
        if tweets:
            return tweets[:limit]
    return []
