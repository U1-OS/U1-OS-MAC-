#!/usr/bin/env python3
"""
Command Center // macOS Menu Bar Extra
Generates live status bar items compatible with SwiftBar, xbar, BitBar,
or terminal status line displays.
"""

import os
import sys
import json
import urllib.request

def get_state(host="127.0.0.1", port=8787) -> dict:
    url = f"http://{host}:{port}/api/state"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "CCMenuBar/1.0"})
        with urllib.request.urlopen(req, timeout=2) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:
        return {}

def render_menubar():
    state = get_state()
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    cli_bin = os.path.join(base_dir, "command-center")

    if not state:
        print("⚡ CC: OFFLINE | color=#FF5555")
        print("---")
        print("Command Center is currently stopped")
        print(f"Start Feeder | bash={cli_bin} param1=start terminal=false refresh=true")
        return

    services = state.get("services", {})
    fin = services.get("finance", {}).get("data", {})
    trade = fin.get("trade_panel", {})
    port_val = trade.get("portfolio_value_usd", 0)
    
    intel = services.get("intelligence", {}).get("data", {})
    weather = intel.get("weather", {})
    temp_c = weather.get("temp_c", "--")
    load = intel.get("telemetry", {}).get("load_1m", "--")

    # Format menu bar top-level line
    port_k = f"${port_val/1000.0:.1f}k" if port_val else "$0.0k"
    print(f"⚡ CC: {port_k} | {temp_c}°C | font=JetBrains Mono size=12")
    print("---")

    # Dropdown Header
    print(f"COMMAND CENTER // macOS Business OS | font=Archivo Expanded size=13 color=#E9B44C")
    print(f"Feeder Status: ONLINE (127.0.0.1:8787) | color=#E9B44C")
    print(f"System Load: 1m: {load} | color=#8A92A6")
    print("---")

    # Financial Vitals
    btc_price = fin.get("market_quotes", {}).get("BTC", {}).get("price", 0)
    eth_price = fin.get("market_quotes", {}).get("ETH", {}).get("price", 0)
    print(f"Market Trade Desk | font=Archivo Expanded size=11 color=#E9B44C")
    print(f"--BTC: ${btc_price:,.2f} | href=http://127.0.0.1:8787#finance")
    print(f"--ETH: ${eth_price:,.2f} | href=http://127.0.0.1:8787#finance")
    print(f"--Portfolio: ${port_val:,.2f} USD | href=http://127.0.0.1:8787#finance")
    print("---")

    # Navigation Shortcuts
    print("Navigation Panels | font=Archivo Expanded size=11 color=#E9B44C")
    print("Open Dashboard (Home) | href=http://127.0.0.1:8787")
    print("Open Comms (Gmail & Twilio) | href=http://127.0.0.1:8787#comms")
    print("Open Finance (Stripe & Trade) | href=http://127.0.0.1:8787#finance")
    print("Open Studio (Video Pipeline) | href=http://127.0.0.1:8787#studio")
    print("Open AI Workbench (Claude & GPT) | href=http://127.0.0.1:8787#ai")
    print("Open Deploy & Terminal | href=http://127.0.0.1:8787#deploy")
    print("Open Gaming (120Hz Playtest) | href=http://127.0.0.1:8787#gaming")
    print("Open OSINT (DNS & WHOIS) | href=http://127.0.0.1:8787#osint")
    print("Open Settings & Vault | href=http://127.0.0.1:8787#settings")
    print("---")

    # System Actions
    print("Quick Actions | font=Archivo Expanded size=11 color=#E9B44C")
    print(f"Generate Executive Dossier | bash={cli_bin} param1=briefing terminal=false refresh=false")
    print(f"Export Security Vault | bash={cli_bin} param1=vault param2=export param3=--password param4=QuickVault2026! terminal=false")
    print(f"Restart Local Feeder | bash={cli_bin} param1=restart terminal=false refresh=true")
    print(f"Stop Feeder | bash={cli_bin} param1=stop terminal=false refresh=true")

if __name__ == "__main__":
    render_menubar()
