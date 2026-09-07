#!/usr/bin/env python3
"""
Command Center — Telegram Bot & Alpha Channel Client
Pure-Python HTTP implementation (zero external packages).
Communicates directly with the official Telegram Bot API:
- Outbound trade alerts, price triggers, and daily briefings.
- Inbound remote command polling (/status, /pnl, /buy, /quote, /lockdown).
"""

import json
import time
import urllib.request
import urllib.parse
import urllib.error

TELEGRAM_API_BASE = "https://api.telegram.org"

def get_me(bot_token, timeout=5):
    """Verifies bot token validity and retrieves bot identity from Telegram."""
    if not bot_token:
        return {"ok": False, "error": "MISSING_BOT_TOKEN"}
    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/getMe"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CommandCenterOS/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except urllib.error.HTTPError as e:
        err_msg = e.read().decode("utf-8", errors="ignore")
        return {"ok": False, "error": f"HTTP {e.code}: {err_msg}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def send_message(bot_token, chat_id, text, parse_mode="HTML", disable_web_page_preview=False, timeout=6):
    """Dispatches a message to a specific user chat_id or alpha broadcast channel."""
    if not bot_token or not chat_id:
        return {"ok": False, "error": "MISSING_BOT_TOKEN_OR_CHAT_ID"}
    
    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": disable_web_page_preview
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "User-Agent": "CommandCenterOS/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="ignore")
        return {"ok": False, "error": f"HTTP {e.code}: {err_body}"}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def get_updates(bot_token, offset=0, timeout=0, request_timeout=6):
    """Fetches updates from Telegram for incoming user commands."""
    if not bot_token:
        return {"ok": False, "error": "MISSING_BOT_TOKEN", "result": []}
    
    url = f"{TELEGRAM_API_BASE}/bot{bot_token}/getUpdates?offset={offset}&timeout={timeout}"
    req = urllib.request.Request(url, headers={"User-Agent": "CommandCenterOS/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=request_timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        return {"ok": False, "error": str(e), "result": []}

def format_trade_alert(token_symbol, action, amount_sol, price_usd, tokens_qty, tx_hash=None, engine="Photon / Jupiter"):
    """Builds a formatted HTML message for trade executions."""
    tx_line = f"\n🔗 <b>Tx:</b> <code>{tx_hash}</code>" if tx_hash else ""
    return (
        f"⚡ <b>COMMAND CENTER // TRADE EXECUTED</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🪙 <b>Asset:</b> <code>${token_symbol}</code>\n"
        f"🎯 <b>Action:</b> <b>{action.upper()}</b>\n"
        f"💰 <b>Capital:</b> {amount_sol} SOL\n"
        f"📦 <b>Tokens:</b> {tokens_qty:,.2f} ${token_symbol}\n"
        f"💵 <b>Price:</b> ${price_usd}\n"
        f"⚙️ <b>Router:</b> {engine}{tx_line}\n"
        f"⏱ <b>Timestamp:</b> {time.strftime('%H:%M:%S UTC', time.gmtime())}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<i>Autonomous AI Trading Desk Active</i>"
    )

def format_price_alert(symbol, current_price, condition, target_price):
    """Builds a formatted HTML message for price alerts."""
    emoji = "🚀" if condition == "ABOVE" else "🔻"
    return (
        f"{emoji} <b>CRYPTO PRICE TARGET TRIGGERED</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🪙 <b>Asset:</b> <code>${symbol}</code>\n"
        f"🎯 <b>Condition:</b> {condition} ${target_price}\n"
        f"💵 <b>Current Price:</b> <b>${current_price}</b>\n"
        f"⏱ <b>Time:</b> {time.strftime('%H:%M:%S UTC', time.gmtime())}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"<i>Check Command Center Desk to execute swap</i>"
    )

def format_bot_signal(strategy, symbol, action, alloc_sol, reason=""):
    """Builds an alert for autonomous AI bot signals."""
    reason_str = f"\n💡 <b>Rationale:</b> <i>{reason}</i>" if reason else ""
    return (
        f"🤖 <b>AI BOT SIGNAL TRIGGERED</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🧠 <b>Strategy:</b> {strategy}\n"
        f"🪙 <b>Symbol:</b> <code>${symbol}</code>\n"
        f"🎯 <b>Action:</b> {action.upper()}\n"
        f"💰 <b>Allocation:</b> {alloc_sol} SOL{reason_str}\n"
        f"⏱ <b>Time:</b> {time.strftime('%H:%M:%S UTC', time.gmtime())}"
    )

def format_lockdown_notice(active, reason=""):
    """Builds a security lockdown alert."""
    if active:
        return (
            f"🚨🚨 <b>EMERGENCY LOCKDOWN ENGAGED</b> 🚨🚨\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>Status:</b> OS MUTATIONS & TRANSFERS BLOCKED\n"
            f"<b>Reason:</b> {reason or 'Manual operator command / trigger'}\n"
            f"<b>Time:</b> {time.strftime('%H:%M:%S UTC', time.gmtime())}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"Send <code>/unlock</code> to restore normal operation."
        )
    else:
        return (
            f"✅ <b>LOCKDOWN DISENGAGED</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"<b>Status:</b> All trading desks and OS mutation gates restored.\n"
            f"<b>Time:</b> {time.strftime('%H:%M:%S UTC', time.gmtime())}"
        )
