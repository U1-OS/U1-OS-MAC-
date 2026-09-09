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


ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def configured_port(default=8788):
    """The port the OS actually binds, from config.json.

    Every menu-bar link used to hardcode 8787 while the server had moved
    to 8788, so each one opened a dead URL.
    """
    override = os.environ.get("U1_OS_PORT")
    if override and override.isdigit():
        return int(override)
    try:
        with open(os.path.join(ROOT, "config.json"), encoding="utf-8") as handle:
            return int(json.load(handle).get("system", {}).get("port", default))
    except Exception:
        return default


PORT = configured_port()
BASE = f"http://127.0.0.1:{PORT}"

def get_state(host="127.0.0.1", port=None) -> dict:
    port = PORT if port is None else port
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
    print(f"Feeder Status: ONLINE (127.0.0.1:{PORT}) | color=#E9B44C")
    print(f"System Load: 1m: {load} | color=#8A92A6")
    print("---")

    # Financial Vitals
    btc_price = fin.get("market_quotes", {}).get("BTC", {}).get("price", 0)
    eth_price = fin.get("market_quotes", {}).get("ETH", {}).get("price", 0)
    print(f"Market Trade Desk | font=Archivo Expanded size=11 color=#E9B44C")
    print(f"--BTC: ${btc_price:,.2f} | href={BASE}#finance")
    print(f"--ETH: ${eth_price:,.2f} | href={BASE}#finance")
    print(f"--Portfolio: ${port_val:,.2f} USD | href={BASE}#finance")
    print("---")

    # Navigation Shortcuts
    print("Navigation Panels | font=Archivo Expanded size=11 color=#E9B44C")
    print(f"Open Dashboard (Home) | href={BASE}")
    print(f"Open Comms (Gmail & Twilio) | href={BASE}#comms")
    print(f"Open Finance (Stripe & Trade) | href={BASE}#finance")
    print(f"Open Studio (Video Pipeline) | href={BASE}#studio")
    print(f"Open AI Workbench (Claude & GPT) | href={BASE}#ai")
    print(f"Open Deploy & Terminal | href={BASE}#deploy")
    print(f"Open Gaming (120Hz Playtest) | href={BASE}#gaming")
    print(f"Open OSINT (DNS & WHOIS) | href={BASE}#osint")
    print(f"Open Settings & Vault | href={BASE}#settings")
    print("---")

    # System Actions
    print("Quick Actions | font=Archivo Expanded size=11 color=#E9B44C")
    print(f"Generate Executive Dossier | bash={cli_bin} param1=briefing terminal=false refresh=false")
    print(f"Export Security Vault | bash={cli_bin} param1=vault param2=export param3=--password param4=QuickVault2026! terminal=false")
    print(f"Restart Local Feeder | bash={cli_bin} param1=restart terminal=false refresh=true")
    print(f"Stop Feeder | bash={cli_bin} param1=stop terminal=false refresh=true")

if __name__ == "__main__":
    render_menubar()
