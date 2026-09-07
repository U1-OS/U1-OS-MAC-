#!/usr/bin/env python3
"""
U1 OS — Jupiter Aggregator v6 Swap Router
Real on-chain swap execution: best-route quote → unsigned tx → sign → broadcast.
"""

import json
import urllib.request
import urllib.error
import base64
import os

JUPITER_QUOTE_URL  = "https://quote-api.jup.ag/v6/quote"
JUPITER_SWAP_URL   = "https://quote-api.jup.ag/v6/swap"
NATIVE_SOL_MINT    = "So11111111111111111111111111111111111111112"
USDC_MINT          = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"


def _http_get(url: str, timeout: int = 10) -> dict:
    try:
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"data": json.loads(resp.read().decode("utf-8")), "ok": True}
    except Exception as e:
        return {"data": None, "ok": False, "error": str(e)}


def _http_post(url: str, body: dict, timeout: int = 15) -> dict:
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {"data": json.loads(resp.read().decode("utf-8")), "ok": True}
    except Exception as e:
        return {"data": None, "ok": False, "error": str(e)}


def get_quote(
    input_mint:   str,
    output_mint:  str,
    amount:       int,          # in lamports (SOL) or smallest unit
    slippage_bps: int = 200,    # 200 = 2%
    only_direct:  bool = False
) -> dict:
    """Get best-route swap quote from Jupiter.
    
    Returns: {"quote": {...}, "out_amount": int, "price_impact_pct": float, "ok": bool}
    """
    params = (
        f"?inputMint={input_mint}"
        f"&outputMint={output_mint}"
        f"&amount={amount}"
        f"&slippageBps={slippage_bps}"
        f"&onlyDirectRoutes={'true' if only_direct else 'false'}"
    )
    res = _http_get(JUPITER_QUOTE_URL + params)
    if not res["ok"]:
        return {"quote": None, "ok": False, "error": res.get("error", "Quote fetch failed")}

    data = res["data"]
    if "error" in data:
        return {"quote": None, "ok": False, "error": data["error"]}

    out_amount = int(data.get("outAmount", 0))
    price_impact = float(data.get("priceImpactPct", 0))

    return {
        "quote":             data,
        "input_mint":        input_mint,
        "output_mint":       output_mint,
        "in_amount":         int(data.get("inAmount", amount)),
        "out_amount":        out_amount,
        "price_impact_pct":  round(price_impact * 100, 4),
        "slippage_bps":      slippage_bps,
        "route_plan":        data.get("routePlan", []),
        "ok":                True
    }


def get_swap_transaction(quote: dict, user_public_key: str, priority_fee_lamports: int = 5000) -> dict:
    """Get the unsigned swap transaction from Jupiter.
    
    Returns: {"swap_transaction": str (base64), "ok": bool}
    """
    if not quote.get("ok") or not quote.get("quote"):
        return {"swap_transaction": None, "ok": False, "error": "Invalid quote"}

    body = {
        "quoteResponse":          quote["quote"],
        "userPublicKey":          user_public_key,
        "wrapAndUnwrapSol":       True,
        "dynamicComputeUnitLimit":True,
        "prioritizationFeeLamports": priority_fee_lamports
    }
    res = _http_post(JUPITER_SWAP_URL, body)
    if not res["ok"]:
        return {"swap_transaction": None, "ok": False, "error": res.get("error")}

    data = res["data"]
    if "swapTransaction" not in data:
        return {"swap_transaction": None, "ok": False, "error": data.get("error", "No swapTransaction in response")}

    return {
        "swap_transaction": data["swapTransaction"],  # base64 encoded versioned tx
        "last_valid_block_height": data.get("lastValidBlockHeight"),
        "ok": True
    }


def execute_swap_with_keypair(
    input_mint:     str,
    output_mint:    str,
    amount_lamports: int,
    private_key_b58: str,
    slippage_bps:   int = 200,
    dry_run:        bool = False
) -> dict:
    """Full swap flow: quote → unsigned tx → sign with keypair → broadcast.
    
    IMPORTANT: private_key_b58 is the base58-encoded private key.
    It is NEVER logged and is used only in memory for signing.
    
    Returns: {"signature": str, "explorer_url": str, "ok": bool}
    """
    # Step 1: Derive public key from private key using nacl/solders if available
    # We use a subprocess-safe approach via base58 decode + ed25519
    try:
        from utils.solana import send_transaction
        try:
            import base58 as _base58
        except ImportError:
            from utils import base58_util as _base58

        raw = _base58.b58decode(private_key_b58)
        # Solana keypair is 64 bytes: first 32 = private seed, last 32 = public key
        if len(raw) == 64:
            seed = raw[:32]
            pub_bytes = raw[32:]
        elif len(raw) == 32:
            seed = raw
            try:
                from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey as PK
                pub_bytes = PK.from_private_bytes(seed).public_key().public_bytes_raw()
            except ImportError:
                from utils.ed25519_util import public_key_from_seed
                pub_bytes = public_key_from_seed(seed)
        else:
            return {"ok": False, "error": f"Invalid keypair length: {len(raw)}"}

        public_key = _base58.b58encode(pub_bytes).decode("utf-8")

    except Exception as e:
        return {"ok": False, "error": f"Failed to initialize keypair: {e}"}

    # Step 2: Get quote
    quote = get_quote(input_mint, output_mint, amount_lamports, slippage_bps)
    if not quote["ok"]:
        return {"ok": False, "error": f"Quote failed: {quote.get('error')}"}

    # Safety: reject if price impact > 5%
    if quote["price_impact_pct"] > 5.0:
        return {"ok": False, "error": f"Price impact too high: {quote['price_impact_pct']}% (max 5%)"}

    # Step 3: Get unsigned transaction
    swap_tx = get_swap_transaction(quote, public_key)
    if not swap_tx["ok"]:
        return {"ok": False, "error": f"Swap tx failed: {swap_tx.get('error')}"}

    if dry_run:
        return {
            "ok":          True,
            "dry_run":     True,
            "quote":       quote,
            "public_key":  public_key,
            "out_amount":  quote["out_amount"],
            "price_impact": quote["price_impact_pct"],
            "message":     "DRY RUN: transaction NOT broadcast"
        }

    # Step 4: Sign the transaction
    try:
        tx_bytes = base64.b64decode(swap_tx["swap_transaction"])
        msg_start = 1 + 1 + 64  # version_prefix(1) + sig_count(1) + one_empty_sig(64)
        msg_bytes = tx_bytes[msg_start:]
        try:
            from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
            priv_key = Ed25519PrivateKey.from_private_bytes(seed)
            signature = priv_key.sign(msg_bytes)
        except ImportError:
            from utils.ed25519_util import sign as ed25519_sign
            signature = ed25519_sign(seed, msg_bytes)

        # Replace the empty signature placeholder with our real signature
        signed_bytes = bytearray(tx_bytes)
        signed_bytes[2:66] = signature
        signed_b64 = base64.b64encode(bytes(signed_bytes)).decode("utf-8")
    except Exception as e:
        return {"ok": False, "error": f"Signing failed: {e}"}

    # Step 5: Broadcast
    broadcast = send_transaction(signed_b64)
    if not broadcast["ok"]:
        return {"ok": False, "error": f"Broadcast failed: {broadcast.get('error')}"}

    return {
        "ok":           True,
        "signature":    broadcast["signature"],
        "explorer_url": broadcast["explorer_url"],
        "in_amount":    quote["in_amount"],
        "out_amount":   quote["out_amount"],
        "price_impact": quote["price_impact_pct"],
        "input_mint":   input_mint,
        "output_mint":  output_mint
    }


def sol_to_lamports(sol: float) -> int:
    """Convert SOL float to lamports integer."""
    return int(sol * 1_000_000_000)


def lamports_to_sol(lamports: int) -> float:
    """Convert lamports integer to SOL float."""
    return round(lamports / 1_000_000_000, 9)


def get_token_price_in_sol(token_mint: str, sol_amount_lamports: int = 1_000_000_000) -> dict:
    """Get how much of a token you get for 1 SOL (or custom amount)."""
    quote = get_quote(NATIVE_SOL_MINT, token_mint, sol_amount_lamports)
    if not quote["ok"]:
        return {"price": None, "ok": False, "error": quote.get("error")}
    decimals = 6  # most SPL tokens use 6
    token_amount = quote["out_amount"] / (10 ** decimals)
    sol_amount = sol_amount_lamports / 1_000_000_000
    price_per_token_in_sol = sol_amount / token_amount if token_amount > 0 else 0
    return {
        "ok": True,
        "token_mint": token_mint,
        "token_amount": token_amount,
        "sol_per_token": round(price_per_token_in_sol, 10),
        "price_impact_pct": quote["price_impact_pct"]
    }
