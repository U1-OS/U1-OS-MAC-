#!/usr/bin/env python3
"""
Command Center OS — Operator Command Line Interface (CLI)
Provides fast terminal access to:
- Credentials configuration for all 18 integrations (Telegram, Solana, GitHub, Stripe, OpenAI, etc.)
- Autonomous trading controls and status queries
- Headless browser page inspections
- Live system telemetry
"""

import sys
import os
import json
import time
import urllib.request
import urllib.parse

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
BASE_URL = "http://127.0.0.1:8787"

def post_action(service, action, payload=None):
    url = f"{BASE_URL}/api/action"
    data = json.dumps({"service": service, "action": action, "payload": payload or {}}).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", "User-Agent": "CCOS-CLI/1.0"})
    with urllib.request.urlopen(req, timeout=12) as r:
        return json.loads(r.read().decode("utf-8"))

def get_state():
    url = f"{BASE_URL}/api/state"
    req = urllib.request.Request(url, headers={"User-Agent": "CCOS-CLI/1.0"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.loads(r.read().decode("utf-8"))

def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, indent=2)

def print_help():
    print("""
\033[1;36m============================================================
 COMMAND CENTER OS // OPERATOR CLI TERMINAL
============================================================\033[0m
Usage:
  python3 cli.py status                        View system & trading bot status
  python3 cli.py integrations                  List all configured integrations
  python3 cli.py set-key <integration> <key> <val>  Save API credential to config
  python3 cli.py test <integration>            Test connectivity to an integration
  python3 cli.py tg send "<message>"           Send alert via Telegram Bot
  python3 cli.py tg cmd "/status"              Simulate or execute Telegram command
  python3 cli.py buy <symbol> [amount_sol]     Execute Photon/Solana crypto swap
  python3 cli.py crawl <url>                   Inspect webpage via Headless Chrome
  python3 cli.py bot [start|stop|status]       Control Autonomous AI Trading Bot
  python3 cli.py lockdown [on|off]             Engage or disengage security lockdown
============================================================
    """)

def main():
    if len(sys.argv) < 2 or sys.argv[1] in ["-h", "--help", "help"]:
        print_help()
        sys.exit(0)

    cmd = sys.argv[1].lower()

    # 1. Status
    if cmd == "status":
        try:
            st = get_state()
            print("\n\033[32m[OK] Command Center Feeder Online (127.0.0.1:8787)\033[0m")
            crypto = st.get("services", {}).get("crypto", {}).get("data", {})
            bot = crypto.get("bot_state", {})
            print(f"  • Autonomous Bot: {bot.get('status')} (Mode: {bot.get('autonomous_mode')})")
            print(f"  • SOL Balance:    {bot.get('paper_balance_sol')} SOL")
            print(f"  • Realized PnL:   {bot.get('realized_pnl_sol'):+} SOL (${bot.get('realized_pnl_usd', 0):+,.2f})")
            print(f"  • Open Positions: {len(crypto.get('positions', []))}")
            tg = st.get("services", {}).get("telegram", {}).get("data", {})
            print(f"  • Telegram Bot:   {tg.get('connect_notice')}")
        except Exception as e:
            print(f"\033[31m[ERR] Server unreachable: {e}\033[0m")

    # 2. Integrations
    elif cmd == "integrations":
        cfg = load_config()
        ints = cfg.get("integrations", {})
        print("\n\033[1;33m--- Configured Integrations in config.json ---\033[0m")
        for k, v in ints.items():
            if isinstance(v, dict):
                has_keys = [subk for subk, subv in v.items() if bool(subv)]
                print(f"  [{'✓' if has_keys else ' '}] {k:<20} Keys: {', '.join(has_keys) if has_keys else 'none'}")

    # 3. Set Key
    elif cmd == "set-key":
        if len(sys.argv) < 5:
            print("Usage: python3 cli.py set-key <integration_id> <key_name> <value>")
            sys.exit(1)
        int_id = sys.argv[2].lower()
        key_name = sys.argv[3]
        val = sys.argv[4]

        # Use backend action to update both file and hot-reloaded memory
        try:
            res = post_action("settings", "save_integration", {
                "id": int_id,
                "values": {key_name: val}
            })
            if res.get("success"):
                print(f"\033[32m[PASS] Credential saved: integrations.{int_id}.{key_name} (Hot-reloaded)\033[0m")
            else:
                print(f"\033[31m[FAIL] {res.get('error')}\033[0m")
        except Exception:
            # Direct file fallback
            cfg = load_config()
            cfg.setdefault("integrations", {}).setdefault(int_id, {})[key_name] = val
            save_config(cfg)
            print(f"\033[32m[PASS] Credential written directly to config.json: integrations.{int_id}.{key_name}\033[0m")

    # 4. Test Integration
    elif cmd == "test":
        if len(sys.argv) < 3:
            print("Usage: python3 cli.py test <integration_id>")
            sys.exit(1)
        int_id = sys.argv[2].lower()
        res = post_action("settings", "test_integration_connection", {"id": int_id})
        status_color = "\033[32m" if res.get("success") else "\033[31m"
        print(f"\n  {status_color}[{'PASS' if res.get('success') else 'FAIL'}]\033[0m {res.get('message')} ({res.get('latency_ms', 0)}ms)")

    # 5. Telegram operations
    elif cmd == "tg":
        if len(sys.argv) < 3:
            print("Usage: python3 cli.py tg send \"<msg>\" | python3 cli.py tg cmd \"<command>\"")
            sys.exit(1)
        sub = sys.argv[2].lower()
        if sub == "send":
            msg = sys.argv[3] if len(sys.argv) > 3 else "Command Center test alert"
            res = post_action("telegram", "send_message", {"text": msg})
            print(f"Telegram response: {res}")
        elif sub == "cmd":
            tcmd = sys.argv[3] if len(sys.argv) > 3 else "/help"
            res = post_action("telegram", "execute_command", {"command": tcmd})
            print(f"\n{res.get('output')}\n")

    # 6. Buy swap
    elif cmd == "buy":
        if len(sys.argv) < 3:
            print("Usage: python3 cli.py buy <symbol> [amount_sol]")
            sys.exit(1)
        sym = sys.argv[2].upper()
        amount = float(sys.argv[3]) if len(sys.argv) > 3 else 0.2
        res = post_action("crypto", "execute_swap", {"symbol": sym, "side": "BUY", "amount": amount, "confirmed": True})
        if res.get("success"):
            print(f"\033[32m[PASS] Photon Swap Executed! Tx: {res.get('tx_hash')} | Received: {res.get('tokens_received')} ${sym}\033[0m")
        else:
            print(f"\033[31m[FAIL] Swap error: {res.get('error')}\033[0m")

    # 7. Crawl URL
    elif cmd == "crawl":
        if len(sys.argv) < 3:
            print("Usage: python3 cli.py crawl <url>")
            sys.exit(1)
        url = sys.argv[2]
        from utils import browser_crawler
        print(f"Crawling {url} via Headless Chrome...")
        res = browser_crawler.inspect_page(url)
        print(f"Engine:  {res.get('engine')} ({res.get('latency_ms')}ms)")
        print(f"Title:   {res.get('title')}")
        print(f"Preview: {res.get('text_preview', '')[:200]}...")
        if res.get("detected_solana_cas"):
            print(f"Detected Solana CAs: {res.get('detected_solana_cas')}")

    # 8. Bot control
    elif cmd == "bot":
        action = sys.argv[2].lower() if len(sys.argv) > 2 else "status"
        if action == "start":
            res = post_action("crypto", "start_trading_bot")
            print(f"\033[32m[PASS] Bot Started: {res.get('message')}\033[0m")
        elif action == "stop":
            res = post_action("crypto", "stop_trading_bot")
            print(f"\033[33m[PASS] Bot Paused: {res.get('message')}\033[0m")
        else:
            res = post_action("crypto", "get_bot_status")
            s = res.get("bot_state", {})
            print(f"Bot Status: {s.get('status')} | Balance: {s.get('paper_balance_sol')} SOL | Realized: {s.get('realized_pnl_sol'):+} SOL")

    # 9. Lockdown
    elif cmd == "lockdown":
        mode = sys.argv[2].lower() if len(sys.argv) > 2 else "on"
        enable = mode in ["on", "true", "enable", "1"]
        res = post_action("settings", "toggle_lockdown", {"enable": enable, "confirmed": True, "reason": "CLI override"})
        print(f"Lockdown engaged: {res.get('lockdown_active')}")

if __name__ == "__main__":
    main()
