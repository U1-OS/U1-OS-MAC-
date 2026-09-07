#!/usr/bin/env python3
"""
U1 OS — Solana RPC Client
Real on-chain data: balances, token accounts, transactions, broadcast.
"""

import json
import urllib.request
import urllib.error
import base64
import os

# Default to public mainnet RPC — override via SOLANA_RPC_URL env var or settings
DEFAULT_RPC = os.environ.get("SOLANA_RPC_URL", "https://api.mainnet-beta.solana.com")

# Known SPL token mint → (symbol, decimals) for display
KNOWN_MINTS = {
    "So11111111111111111111111111111111111111112":  ("SOL",      9),
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263": ("BONK",   5),
    "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm": ("WIF",    6),
    "7GCihgDB8fe6KNjn2MYtkzZcRjQy3t9GHdC8uHYmW2hr": ("POPCAT", 6),
    "2qEHjNxggBi1DtNc8WEC8MJfSoSuJaVxZ18xxFIpump":  ("PNUT",   6),
    "GJAFwWjJ3vnTsrQVabjBVK2TYB1YtRCQXRDfDgqupump": ("ACT",    6),
    "9BB6NFEcjBCtnNLFko2FqVQBq8HHM13kCyYcdQbgpump": ("FARTCOIN",6),
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": ("USDC",   6),
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB":  ("USDT",   6),
}

def _rpc_post(method, params, rpc_url=None):
    """Send a JSON-RPC POST request to the Solana RPC endpoint."""
    url = rpc_url or DEFAULT_RPC
    payload = json.dumps({
        "jsonrpc": "2.0",
        "id":      1,
        "method":  method,
        "params":  params
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"error": str(e)}


def get_sol_balance(address: str, rpc_url=None) -> dict:
    """Return SOL balance for a wallet address.
    
    Returns: {"address": str, "lamports": int, "sol": float, "ok": bool}
    """
    result = _rpc_post("getBalance", [address], rpc_url)
    if "error" in result or "result" not in result:
        return {"address": address, "lamports": 0, "sol": 0.0, "ok": False,
                "error": result.get("error", "RPC error")}
    lamports = result["result"].get("value", 0)
    return {
        "address": address,
        "lamports": lamports,
        "sol": round(lamports / 1_000_000_000, 6),
        "ok": True
    }


def get_token_accounts(address: str, rpc_url=None) -> dict:
    """Return all SPL token accounts owned by address.
    
    Returns: {"accounts": [...], "ok": bool}
    """
    result = _rpc_post("getTokenAccountsByOwner", [
        address,
        {"programId": "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"},
        {"encoding": "jsonParsed"}
    ], rpc_url)

    if "error" in result or "result" not in result:
        return {"accounts": [], "ok": False, "error": result.get("error", "RPC error")}

    accounts = []
    for item in result["result"].get("value", []):
        try:
            info = item["account"]["data"]["parsed"]["info"]
            mint = info.get("mint", "")
            amount_raw = int(info["tokenAmount"]["amount"])
            decimals = info["tokenAmount"]["decimals"]
            amount = amount_raw / (10 ** decimals) if decimals > 0 else amount_raw
            symbol, _ = KNOWN_MINTS.get(mint, ("UNKNOWN", decimals))
            if amount > 0:
                accounts.append({
                    "mint":     mint,
                    "symbol":   symbol,
                    "amount":   round(amount, 6),
                    "decimals": decimals,
                    "pubkey":   item.get("pubkey", "")
                })
        except (KeyError, TypeError, ValueError):
            continue

    return {"accounts": accounts, "ok": True}


def get_recent_transactions(address: str, limit: int = 20, rpc_url=None) -> dict:
    """Return recent transaction signatures for a wallet.
    
    Returns: {"transactions": [...], "ok": bool}
    """
    result = _rpc_post("getSignaturesForAddress", [
        address,
        {"limit": min(limit, 50)}
    ], rpc_url)

    if "error" in result or "result" not in result:
        return {"transactions": [], "ok": False, "error": result.get("error", "RPC error")}

    txs = []
    for item in result["result"]:
        txs.append({
            "signature":   item.get("signature", ""),
            "slot":        item.get("slot", 0),
            "block_time":  item.get("blockTime"),
            "err":         item.get("err"),
            "memo":        item.get("memo"),
            "explorer_url": f"https://solscan.io/tx/{item.get('signature', '')}"
        })

    return {"transactions": txs, "ok": True}


def send_transaction(signed_tx_b64: str, rpc_url=None) -> dict:
    """Broadcast a base64-encoded signed transaction to the network.
    
    Returns: {"signature": str, "ok": bool}
    """
    result = _rpc_post("sendTransaction", [
        signed_tx_b64,
        {
            "encoding":             "base64",
            "skipPreflight":        False,
            "preflightCommitment":  "confirmed",
            "maxRetries":           3
        }
    ], rpc_url)

    if "error" in result:
        return {"signature": None, "ok": False, "error": result["error"]}
    if "result" not in result:
        return {"signature": None, "ok": False, "error": "No result in RPC response"}

    sig = result["result"]
    return {
        "signature":    sig,
        "ok":           True,
        "explorer_url": f"https://solscan.io/tx/{sig}"
    }


def get_account_info(address: str, rpc_url=None) -> dict:
    """Check if an address is a valid funded account."""
    result = _rpc_post("getAccountInfo", [address, {"encoding": "base58"}], rpc_url)
    if "error" in result or result.get("result", {}).get("value") is None:
        return {"exists": False, "ok": False}
    return {"exists": True, "ok": True, "data": result["result"]["value"]}
