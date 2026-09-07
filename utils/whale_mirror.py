"""
Whale Copy-Trading & Shadow Wallet Mirror
Monitors high-alpha smart money wallets across Solana and Base.
Calculates proportional copy-trade sizing and simulates shadow front-running orders.
"""
import time
import secrets

TRACKED_WHALES = [
    {
        "id": "whale_sol_alpha_1",
        "label": "Meme Kingpin (30D PnL: +$1.4M)",
        "address": "7xKXtg2CW87d97TXJSDpbD5jBkheTqA83TZRuJosgAsU",
        "chain": "solana",
        "win_rate_pct": 74.2,
        "total_profit_usd": 1420500.0,
        "recent_trades_count": 18,
        "status": "MIRRORING_ENABLED"
    },
    {
        "id": "whale_base_degen_2",
        "label": "Base Aerodrome Whale (+$680k)",
        "address": "0x4838B106FCe9647Bdf1E7877BF73cE8B0BAD5f97",
        "chain": "base",
        "win_rate_pct": 68.5,
        "total_profit_usd": 684200.0,
        "recent_trades_count": 24,
        "status": "MIRRORING_ENABLED"
    },
    {
        "id": "whale_sol_snip_3",
        "label": "Raydium Flash Sniper (+$910k)",
        "address": "4Nd1mBQwGQtFq7Z3qTpx5oV7bKkL3pX2mQ8jW9vY7z1A",
        "chain": "solana",
        "win_rate_pct": 81.0,
        "total_profit_usd": 912000.0,
        "recent_trades_count": 12,
        "status": "MIRRORING_ENABLED"
    }
]

_MIRRORED_ORDERS = []

def get_tracked_whales():
    """Returns the list of monitored smart money whale wallets."""
    return list(TRACKED_WHALES)

def add_tracked_whale(address, chain="solana", label="New Smart Money"):
    """Registers a new whale address to the shadow mirror engine."""
    wid = f"whale_{secrets.token_hex(4)}"
    rec = {
        "id": wid,
        "label": label,
        "address": address,
        "chain": chain,
        "win_rate_pct": 70.0,
        "total_profit_usd": 100000.0,
        "recent_trades_count": 1,
        "status": "MIRRORING_ENABLED"
    }
    TRACKED_WHALES.append(rec)
    return {"success": True, "whale": rec, "tracked_whales": list(TRACKED_WHALES)}

def execute_shadow_trade(whale_id="whale_sol_alpha_1", mirror_fraction=0.05, max_slippage_pct=1.0):
    """
    Simulates / mirrors a trade executed by the target whale with proportional sizing.
    """
    target = next((w for w in TRACKED_WHALES if w["id"] == whale_id), None)
    if not target and TRACKED_WHALES:
        target = TRACKED_WHALES[0]
    if not target:
        return {"success": False, "error": f"Whale '{whale_id}' not found"}

    simulated_whale_action = {
        "token_symbol": "BONK" if target["chain"] == "solana" else "AERO",
        "action": "BUY",
        "whale_amount_usd": 20000.0,
        "entry_price": 0.0000245 if target["chain"] == "solana" else 1.24
    }

    mirror_stake_usd = round(simulated_whale_action["whale_amount_usd"] * float(mirror_fraction), 2)
    order_id = f"shadow_ord_{secrets.token_hex(6)}"
    order_rec = {
        "order_id": order_id,
        "whale_id": target["id"],
        "whale_label": target["label"],
        "chain": target["chain"],
        "action": simulated_whale_action["action"],
        "token": simulated_whale_action["token_symbol"],
        "price": simulated_whale_action["entry_price"],
        "whale_stake_usd": simulated_whale_action["whale_amount_usd"],
        "mirror_fraction": float(mirror_fraction),
        "executed_stake_usd": mirror_stake_usd,
        "slippage_pct": 0.22,
        "status": "FILLED_IN_SAME_BLOCK",
        "timestamp": time.time()
    }
    _MIRRORED_ORDERS.insert(0, order_rec)

    return {
        "success": True,
        "shadow_order": order_rec,
        "order": order_rec,
        "message": f"Mirrored {target['label']}: Bought ${mirror_stake_usd} {order_rec['token']} at ${order_rec['price']}"
    }

def get_shadow_trade_history():
    """Returns history of mirrored shadow orders."""
    return list(_MIRRORED_ORDERS)
