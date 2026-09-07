#!/usr/bin/env python3
"""
U1 OS — DexScreener Real-Time Price Engine
Live on-chain prices, volume, liquidity, PnL for any token.
"""

import json
import urllib.request
import time

BASE_URL = "https://api.dexscreener.com/latest/dex/tokens"
SEARCH_URL = "https://api.dexscreener.com/latest/dex/search"


def _get(url: str, timeout: int = 8) -> dict:
    try:
        req = urllib.request.Request(
            url, headers={"Accept": "application/json", "User-Agent": "U1OS/1.0"}
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"data": json.loads(resp.read().decode("utf-8")), "ok": True}
    except Exception as e:
        return {"data": None, "ok": False, "error": str(e)}


def _best_pair(pairs: list) -> dict:
    """Select the highest-liquidity pair from DexScreener response."""
    if not pairs:
        return {}
    # Prefer pairs with verified liquidity, sorted by USD liquidity descending
    sorted_pairs = sorted(
        pairs,
        key=lambda p: float(p.get("liquidity", {}).get("usd", 0) or 0),
        reverse=True
    )
    return sorted_pairs[0]


def fetch_token_price(ca: str) -> dict:
    """Fetch real-time price data for a token by contract address.
    
    Returns: {"price_usd": float, "pnl_5m": float, "pnl_1h": float, 
              "pnl_24h": float, "volume_24h_usd": float, 
              "liquidity_usd": float, "market_cap_usd": float, "ok": bool}
    """
    res = _get(f"{BASE_URL}/{ca}")
    if not res["ok"] or not res["data"]:
        return {"ok": False, "error": res.get("error", "No data")}

    pairs = res["data"].get("pairs") or []
    if not pairs:
        return {"ok": False, "error": "No trading pairs found"}

    pair = _best_pair(pairs)

    price_usd    = float(pair.get("priceUsd") or 0)
    price_change = pair.get("priceChange") or {}
    volume       = pair.get("volume") or {}
    liquidity    = pair.get("liquidity") or {}

    return {
        "ok":               True,
        "price_usd":        price_usd,
        "pnl_5m":           float(price_change.get("m5")  or 0),
        "pnl_1h":           float(price_change.get("h1")  or 0),
        "pnl_6h":           float(price_change.get("h6")  or 0),
        "pnl_24h":          float(price_change.get("h24") or 0),
        "volume_5m_usd":    float(volume.get("m5")  or 0),
        "volume_1h_usd":    float(volume.get("h1")  or 0),
        "volume_24h_usd":   float(volume.get("h24") or 0),
        "liquidity_usd":    float(liquidity.get("usd") or 0),
        "market_cap_usd":   float(pair.get("marketCap") or pair.get("fdv") or 0),
        "dex":              pair.get("dexId", ""),
        "chain":            pair.get("chainId", ""),
        "pair_address":     pair.get("pairAddress", ""),
        "pair_url":         pair.get("url", ""),
        "base_symbol":      pair.get("baseToken", {}).get("symbol", ""),
        "base_name":        pair.get("baseToken", {}).get("name", ""),
        "fetched_at":       time.time()
    }


def fetch_multiple_prices(token_list: list) -> list:
    """Batch-fetch prices for multiple tokens. 
    token_list: [{"symbol": str, "ca": str, ...}, ...]
    Returns the same list with live price data merged in.
    """
    updated = []
    for token in token_list:
        ca = token.get("ca", "")
        if not ca:
            updated.append(token)
            continue
        live = fetch_token_price(ca)
        merged = dict(token)
        if live["ok"]:
            merged["price_usd"]       = live["price_usd"]
            merged["pnl_5m"]          = live["pnl_5m"]
            merged["pnl_1h"]          = live["pnl_1h"]
            merged["pnl_24h"]         = live["pnl_24h"]
            merged["volume_24h_usd"]  = live["volume_24h_usd"]
            merged["liquidity_usd"]   = live["liquidity_usd"]
            merged["market_cap_usd"]  = live["market_cap_usd"]
            merged["pair_url"]        = live["pair_url"] or token.get("photon_url", "")
            merged["live"]            = True
            merged["fetched_at"]      = live["fetched_at"]
        else:
            merged["live"] = False
        updated.append(merged)
    return updated


def search_token(query: str, limit: int = 5) -> list:
    """Search DexScreener for a token by name or symbol."""
    import urllib.parse
    res = _get(f"{SEARCH_URL}?q={urllib.parse.quote(query)}")
    if not res["ok"] or not res["data"]:
        return []
    pairs = res["data"].get("pairs") or []
    results = []
    seen_cas = set()
    for pair in pairs:
        base = pair.get("baseToken", {})
        ca = base.get("address", "")
        if ca in seen_cas:
            continue
        seen_cas.add(ca)
        results.append({
            "symbol":       base.get("symbol", ""),
            "name":         base.get("name", ""),
            "ca":           ca,
            "price_usd":    float(pair.get("priceUsd") or 0),
            "liquidity_usd": float((pair.get("liquidity") or {}).get("usd") or 0),
            "volume_24h_usd": float((pair.get("volume") or {}).get("h24") or 0),
            "chain":        pair.get("chainId", ""),
            "pair_url":     pair.get("url", "")
        })
        if len(results) >= limit:
            break
    return results
