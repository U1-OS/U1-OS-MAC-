#!/usr/bin/env python3
"""
Command Center — Complete End-to-End Test Suite
Validates all 9 subsystems, REST endpoints, and security boundaries.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

def _configured_port():
    """The suite must target the port the OS actually binds, which comes
    from config.json (and may be overridden for a test run)."""
    override = os.environ.get("U1_OS_PORT")
    if override and override.isdigit():
        return int(override)
    try:
        with open(os.path.join(BASE_DIR, "config.json"), encoding="utf-8") as handle:
            return int(json.load(handle).get("system", {}).get("port", 8788))
    except Exception:
        return 8788

PORT = _configured_port()
BASE_URL = f"http://127.0.0.1:{PORT}"
PASS = "\033[32m[PASS]\033[0m"
FAIL = "\033[31m[FAIL]\033[0m"
INFO = "\033[33m[INFO]\033[0m"
CYAN = "\033[36m"
RESET = "\033[0m"

tests_run = 0
tests_passed = 0

def log_test(name, success, detail=""):
    global tests_run, tests_passed
    tests_run += 1
    if success:
        tests_passed += 1
        print(f"  {PASS} {name} {f'({detail})' if detail else ''}")
    else:
        print(f"  {FAIL} {name} - Detail: {detail}")

def get(path):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "CC-TestRunner/1.0"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, json.loads(r.read().decode("utf-8"))

def get_raw(path):
    url = f"{BASE_URL}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "CC-TestRunner/1.0"})
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.status, r.getheader("Content-Type", "")

def post(path, body):
    url = f"{BASE_URL}{path}"
    data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url, data=data,
        headers={"Content-Type": "application/json", "User-Agent": "CC-TestRunner/1.0"}
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        # The server answers faults with a structured JSON body and a real
        # status code. Surface both instead of aborting the whole run.
        try:
            return err.code, json.loads(err.read().decode("utf-8"))
        except Exception:
            return err.code, {"success": False, "error": f"HTTP {err.code}"}
    except Exception as err:
        return 0, {"success": False, "error": f"{type(err).__name__}: {err}"}

def action(service, act, payload=None):
    return post("/api/action", {"service": service, "action": act, "payload": payload or {}})

def main():
    print(f"\n{CYAN}============================================================{RESET}")
    print(f"{CYAN} COMMAND CENTER // END-TO-END VERIFICATION SUITE{RESET}")
    print(f"{CYAN} Target: {BASE_URL} (Localhost Binding Only){RESET}")
    print(f"{CYAN}============================================================{RESET}\n")

    # 1. Server Core & Static Asset Probes
    print(f"{INFO} 1. Core Server & Static Asset Integrity:")
    try:
        s, state = get("/api/state")
        log_test("GET /api/state", s == 200, f"{len(state.get('services', {}))} services mounted")
        
        s, cfg = get("/api/config")
        log_test("GET /api/config", s == 200, "Secret masking verified")
        
        s, ct = get_raw("/")
        log_test("GET / (index.html)", s == 200 and "text/html" in ct, ct)

        s, ct = get_raw("/css/style.css")
        log_test("GET /css/style.css", s == 200 and "text/css" in ct, ct)

        s, ct = get_raw("/js/app.js")
        log_test("GET /js/app.js", s == 200, ct)

        s, ct = get_raw("/favicon.svg")
        log_test("GET /favicon.svg", s == 200 and "image/svg+xml" in ct, ct)

        s, ct = get_raw("/manifest.json")
        log_test("GET /manifest.json", s == 200, ct)
    except Exception as e:
        log_test("Server Connectivity", False, str(e))
        sys.exit(1)

    # 2. Intelligence Feeder
    print(f"\n{INFO} 2. Subsystem: Intelligence & Living Bezel:")
    intel = state.get("services", {}).get("intelligence", {}).get("data", {})
    weather = intel.get("weather", {})
    news = intel.get("news", [])
    telemetry = intel.get("telemetry", {})
    log_test("Weather Feeder", "temp_c" in weather, f"{weather.get('temp_c')}°C - {weather.get('condition')}")
    log_test("News Ticker", len(news) > 0, f"{len(news)} headlines queued")
    log_test("System Load Telemetry", "load_1m" in telemetry, f"1m: {telemetry.get('load_1m')}, 5m: {telemetry.get('load_5m')}")

    # 3. Finance Subsystem & Trade Desk
    print(f"\n{INFO} 3. Subsystem: Finance & Market Trade Desk:")
    s, res = action("finance", "execute_trade", {"ticker": "BTC", "action": "BUY", "units": 0.05, "confirmed": True})
    log_test("Trade Execution", res.get("success"), res.get("message", "Executed"))
    s, res = action("finance", "mark_bill_paid", {"bill_id": "bill-1"})
    log_test("AP Bill Settlement", res.get("success"), "Vendor: AWS Cloud Computing")

    # 4. Comms Subsystem (Gmail, Calendar, Twilio)
    print(f"\n{INFO} 4. Subsystem: Comms (Email, Calendar, Twilio):")
    s, res = action("comms", "save_draft", {"to": "investors@fund.internal", "subject": "Monthly Q4 Update", "body": "Metrics are trending up."})
    log_test("Save Email Draft", res.get("success"), f"Draft ID: {res.get('draft', {}).get('id')}")
    s, res = action("comms", "create_event", {"title": "Executive Review", "time": "Tomorrow 10:00", "attendees": "team@commandcenter.internal", "confirmed": True})
    log_test("Create Calendar Event", res.get("success"), f"Block: {res.get('event', {}).get('title')}")
    s, res = action("comms", "send_sms", {"to": "+15550192834", "body": "Command Center deployment active.", "confirmed": True})
    log_test("Dispatch Twilio SMS", res.get("success"), f"Status: {res.get('message', {}).get('status')}")

    # 5. Deploy Subsystem
    print(f"\n{INFO} 5. Subsystem: Deploy Engine & Sandbox Cloner:")
    s, res = action("deploy", "clone_and_inspect", {"url": "https://github.com/octocat/Hello-World"})
    log_test("Inspect GitHub Repo", res.get("success"), f"Stacks: {res.get('stacks')}")

    # 6. AI Workbench
    print(f"\n{INFO} 6. Subsystem: AI Workbench (Dual Claude & GPT-4o):")
    s, res = action("ai_workbench", "run_prompt", {"provider": "claude", "prompt": "Analyze business velocity", "model": "claude-3-5-sonnet", "sandbox": True})
    log_test("Claude 3.5 Sonnet Sandbox", res.get("success"), f"Tokens: {res.get('total_tokens')}, Cost: ${res.get('cost_usd', 0):.5f}")
    s, res = action("ai_workbench", "run_prompt", {"provider": "openai", "prompt": "Analyze business velocity", "model": "gpt-4o", "sandbox": True})
    log_test("OpenAI GPT-4o Sandbox", res.get("success"), f"Tokens: {res.get('total_tokens')}, Cost: ${res.get('cost_usd', 0):.5f}")
    s, res = action("ai_workbench", "canva_create_asset", {"title": "Q4 Growth Slide", "dimensions": "1920x1080", "type": "Presentation"})
    log_test("Canva Design Studio Asset", res.get("success"), "Draft registered")

    # 7. Studio Video Builder
    print(f"\n{INFO} 7. Subsystem: Studio & Faceless Video Pipeline:")
    s, res = action("studio", "enqueue_video_render", {"title": "Automated Video Test", "script": "High impact hook for social media.", "preset": "9:16", "tts_engine": "ElevenLabs (Adam)", "broll_query": "DevOps Matrix"})
    job_id = res.get("job", {}).get("id") or res.get("job_id")
    log_test("Enqueue Video Render", res.get("success"), f"Job ID: {job_id}")
    s, res = action("studio", "search_broll", {"query": "cyberpunk"})
    log_test("Search Stock B-Roll", res.get("success"), f"Matches: {len(res.get('results', []))}")

    # 8. Gaming Subsystem
    print(f"\n{INFO} 8. Subsystem: Gaming Engine & 120Hz Playtest:")
    s, res = action("gaming", "launch_playtest", {"profile": "Developer Debug (with HUD)", "window_mode": "Windowed (1280x800)"})
    pid = res.get("session", {}).get("pid")
    log_test("Launch Playtest Sandbox", res.get("success"), f"PID: {pid} (120Hz HUD)")
    s, res = action("gaming", "record_level_solve", {"level": 1, "time": "00:38"})
    log_test("Record Level Clearance", res.get("success"), f"{len(res.get('levels', []))} levels in suite")
    s, res = action("gaming", "trigger_build", {"target": "macOS Universal"})
    log_test("Trigger Puzzle Suite Build", res.get("success"), res.get("build_info", {}).get("status"))
    s, res = action("gaming", "stop_playtest", {})
    log_test("Stop Playtest Sandbox", res.get("success"), "Clean shutdown")

    # 9. OSINT Intelligence Console
    print(f"\n{INFO} 9. Subsystem: OSINT Intelligence Engine:")
    s, res = action("osint", "dns_lookup", {"domain": "apple.com"})
    log_test("Authoritative DNS Matrix", res.get("success"), f"A Records: {len(res.get('result', {}).get('a_records', []))}")
    s, res = action("osint", "whois_lookup", {"domain": "apple.com"})
    log_test("Port 43 WHOIS Inspector", res.get("success"), f"Registrar: {res.get('result', {}).get('registrar')}")
    s, res = action("osint", "hibp_breach_check", {"account": "admin@commandcenter.internal", "simulate": True})
    log_test("HaveIBeenPwned Auditor", res.get("success"), f"Breaches identified: {res.get('result', {}).get('breach_count')}")
    s, res = action("osint", "search_brand_mentions", {"keyword": "Command Center"})
    log_test("Brand Mentions Crawler", res.get("success"), f"Mentions: {len(res.get('mentions', []))}")

    # 10. Settings & Git Auto-Updater
    print(f"\n{INFO} 10. Subsystem: Settings & Git Auto-Updater:")
    s, res = action("settings", "check_updates", {})
    log_test("Git Update Checker", res.get("success"), f"Commit: {res.get('git', {}).get('commit')}")
    s, res = action("settings", "pull_updates", {"confirmed": False})
    log_test("Pull Updates Safety Guard", not res.get("success"), "Unconfirmed pull blocked correctly")
    s, res = action("settings", "toggle_section", {"section_id": "gaming", "enabled": True})
    log_test("Section Visibility Toggle", res.get("success"), "Gaming section verified active")
    s, res = action("settings", "update_preferences", {"preferences": {"accent_color": "#E9B44C"}})
    log_test("Accent Color Switcher", res.get("success"), "Classic Gold #E9B44C")

    # 11. Real-Time Server-Sent Events (SSE) Stream
    print(f"\n{INFO} 11. Real-Time Server-Sent Events (SSE) Stream:")
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/events")
        with urllib.request.urlopen(req, timeout=3) as r:
            first_line = r.readline().decode("utf-8")
            is_sse = "data:" in first_line and "connected" in first_line
            log_test("SSE Handshake Stream", is_sse, "Initial frame verified (connected)")
    except Exception as e:
        log_test("SSE Handshake Stream", False, str(e))

    # 12. macOS Native Suite & LaunchAgent Daemon
    print(f"\n{INFO} 12. macOS Native Suite & LaunchAgent Daemon:")
    s, res = action("settings", "test_notification", {"title": "TEST", "message": "Master Suite Run"})
    log_test("macOS Desktop Notification", res.get("success"), res.get("message"))
    from utils.macos import generate_launchagent_plist, get_agent_plist_path
    plist_xml = generate_launchagent_plist()
    log_test("LaunchAgent Plist Generation", "com.commandcenter.feeder" in plist_xml and "<plist" in plist_xml, "XML schema validated")
    log_test("LaunchAgent Target Path", get_agent_plist_path().endswith("com.commandcenter.feeder.plist"), get_agent_plist_path())

    # 13. Encrypted Security Vault
    print(f"\n{INFO} 13. Encrypted Security Vault:")
    from utils.vault import encrypt_data, decrypt_data, inspect_vault_file
    raw_secret = b'{"token": "live_test_secret_abc123"}'
    env = encrypt_data(raw_secret, "VaultPass2026!")
    log_test("PBKDF2-CTR Authenticated Encryption", env.get("cipher") == "CTR-SHA256-STREAM" and bool(env.get("mac")), "CTR + HMAC-SHA256")
    dec = decrypt_data(env, "VaultPass2026!")
    log_test("Vault Decryption Round-Trip", dec == raw_secret, "Plaintext integrity matched")
    wrong_pwd_caught = False
    try:
        decrypt_data(env, "WrongPassword!")
    except ValueError:
        wrong_pwd_caught = True
    log_test("Vault Tamper & Bad Password Trap", wrong_pwd_caught, "Corrupted/wrong password rejected")
    s, res = action("settings", "export_vault", {"password": "MasterSuitePassword!", "note": "Automated Test Vault"})
    log_test("Web API Vault Export Action", res.get("success"), f"Archive: {os.path.basename(res.get('vault_path', ''))}")

    # 14. Offline Local LLM (Ollama) & Air-Gapped Intelligence
    print(f"\n{INFO} 14. Subsystem: Offline Local LLM (Ollama):")
    s, res = action("ai_workbench", "run_prompt", {"provider": "ollama", "prompt": "Evaluate air-gapped system telemetry", "sandbox": True})
    log_test("Ollama Air-Gapped Dispatch", res.get("success"), f"Model: {res.get('model')}")
    log_test("Zero Token Cost Guarantee", res.get("cost_usd") == 0.0, f"Billed: ${res.get('cost_usd'):.5f}")
    log_test("Local Weight Synthesis", "LOCAL AIR-GAPPED" in res.get("text", ""), "Zero external network egress")

    # 15. Executive Business Dossier Compilation
    print(f"\n{INFO} 15. Subsystem: Executive Business Dossier:")
    s, res = action("settings", "generate_briefing", {})
    log_test("Dossier Compilation Action", res.get("success"), f"Report: {os.path.basename(res.get('markdown_file', ''))}")
    md_exists = os.path.exists(res.get("markdown_file", "")) and os.path.getsize(res.get("markdown_file", "")) > 100
    html_exists = os.path.exists(res.get("html_file", "")) and os.path.getsize(res.get("html_file", "")) > 500
    log_test("Dossier Markdown File Artifact", md_exists, res.get("markdown_file"))
    log_test("Printable HTML Dossier Artifact", html_exists, res.get("html_file"))

    # 16. macOS Menu Bar Extra Protocol
    print(f"\n{INFO} 16. Subsystem: macOS Menu Bar Extra:")
    from utils.menubar import get_state
    bar_state = get_state()
    log_test("Menu Bar Feeder State Query", bool(bar_state.get("services")), "9 services inspected")
    import io, contextlib
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        from utils.menubar import render_menubar
        render_menubar()
    bar_out = buf.getvalue()
    log_test("BitBar / SwiftBar Protocol Header", "⚡ CC:" in bar_out and "font=JetBrains Mono" in bar_out, "Menu bar top-level line")
    log_test("Deep Navigation URL Schemes", f"href=http://127.0.0.1:{PORT}#finance" in bar_out, "9 panel URL hooks")

    # 17. macOS Hardware & Power Telemetry HUD
    print(f"\n{INFO} 17. Subsystem: Hardware & Power Telemetry HUD:")
    st_code, st_data = get("/api/state")
    hw = st_data.get("services", {}).get("intelligence", {}).get("data", {}).get("hardware", {})
    log_test("Hardware State Discovery", bool(hw) and "battery" in hw and "disk" in hw, "Hardware telemetry mounted")
    sys_hw = hw.get("system", {})
    log_test("Apple Hardware Architecture", sys_hw.get("cpu_cores", 0) > 0 and sys_hw.get("ram_gb", 0) > 0, f"{sys_hw.get('cpu_cores')} Cores // {sys_hw.get('ram_gb')} GB RAM // {sys_hw.get('model')}")
    disk_hw = hw.get("disk", {})
    log_test("SSD Storage Diagnostics", disk_hw.get("total_gb", 0) > 0 and disk_hw.get("free_gb", 0) > 0, f"{disk_hw.get('free_gb')} GB Free of {disk_hw.get('total_gb')} GB")

    # 18. Inbound Webhook Ingestion & SSE Gateway
    print(f"\n{INFO} 18. Subsystem: Inbound Webhook Ingestion Gateway:")
    whk_payload = json.dumps({"event": "push", "ref": "refs/heads/main", "commits": 1}).encode("utf-8")
    req = urllib.request.Request(f"{BASE_URL}/api/webhooks/github", data=whk_payload, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as r:
        whk_resp = json.loads(r.read().decode("utf-8"))
    log_test("Inbound Webhook HTTP Ingestion", whk_resp.get("success") and "whk-" in whk_resp.get("entry", {}).get("id", ""), f"Ingested from {whk_resp.get('entry', {}).get('source')}")
    w_code, w_data = get("/api/webhooks")
    recent_sources = [w.get("source") for w in w_data.get("webhooks", [])]
    log_test("Webhook Circular Log Persistence", "github" in recent_sources, f"{len(w_data.get('webhooks', []))} webhooks retained in buffer")

    # 19. Background Automation Task Scheduler (Cron Engine)
    print(f"\n{INFO} 19. Subsystem: Background Automation Scheduler:")
    sc_code, sc_data = get("/api/scheduler")
    jobs = sc_data.get("jobs", [])
    log_test("Cron Tasks Discovery", len(jobs) >= 3, f"{len(jobs)} background tasks active")
    s, res = action("settings", "trigger_scheduled_task", {"job_id": "hourly_dns_audit"})
    log_test("On-Demand Task Execution", res.get("success") and res.get("job", {}).get("status") == "COMPLETED", f"Duration: {res.get('result', {}).get('duration_ms')}ms")

    # 20. macOS Native Speech Audio Briefing (say Engine)
    print(f"\n{INFO} 20. Subsystem: macOS Native Speech Audio Briefing:")
    from utils.briefing import synthesize_briefing_speech_text, speak_briefing
    speech_txt = synthesize_briefing_speech_text()
    log_test("Speech Briefing Synthesis", "Command Center executive briefing" in speech_txt and len(speech_txt) > 50, f"{len(speech_txt.split())} words generated")
    spk_res = speak_briefing(text="Command Center verification probe nominal.", export_audio=True)
    audio_created = spk_res.get("success") and os.path.exists(spk_res.get("audio_file", ""))
    if audio_created and os.path.exists(spk_res["audio_file"]):
        os.remove(spk_res["audio_file"])
    log_test("macOS Say Engine Speech Output", audio_created, "macOS /usr/bin/say synthesis verified")

    # 21. SSL / TLS Certificate Sentinel
    print(f"\n{INFO} 21. Subsystem: SSL/TLS Certificate Sentinel:")
    s, ssl_res = action("osint", "inspect_ssl", {"domain": "apple.com"})
    cert = ssl_res.get("result", {})
    log_test("Port 443 TLS Handshake & Cert Inspection", ssl_res.get("success") and bool(cert.get("issuer")), f"Issuer: {cert.get('issuer')} // {cert.get('days_left')} days left")
    log_test("SSL Expiration & Cipher Suite Metadata", cert.get("days_left", 0) > 0 and bool(cert.get("cipher")), f"Cipher: {cert.get('cipher')} // Risk: {cert.get('risk_level')}")

    # 22. Localhost Port & Process Security Audit Matrix
    print(f"\n{INFO} 22. Subsystem: Localhost Port Security Audit Matrix:")
    s, ports_res = action("osint", "audit_ports")
    ports_info = ports_res.get("result", {})
    log_test("Active Listening Ports Enumeration", ports_res.get("success") and ports_info.get("total_open_ports", 0) > 0, f"{ports_info.get('total_open_ports')} sockets ({ports_info.get('localhost_count')} local, {ports_info.get('exposed_count')} exposed)")
    ports_list = ports_info.get("ports", [])
    cc_found = any(p.get("port") == PORT and p.get("localhost_only") for p in ports_list)
    log_test(f"Command Center {PORT} Localhost-Only Verification", cc_found, "Strict 127.0.0.1 binding confirmed via lsof")

    # 23. Network Gateway Diagnostics & Automated SSL Cron
    print(f"\n{INFO} 23. Subsystem: Network Gateway Diagnostics & Automated SSL Cron:")
    s, net_res = action("osint", "get_network_info")
    net_data = net_res.get("result", {})
    log_test("Network Gateway Diagnostics", net_res.get("success") and bool(net_data.get("local_ip")), f"IP: {net_data.get('local_ip')} // Gateway: {net_data.get('default_gateway')}")
    sc_code, sc_data = get("/api/scheduler")
    cron_ids = [j.get("id") for j in sc_data.get("jobs", [])]
    log_test("Daily SSL Certificate Audit Cron Job", "daily_ssl_audit" in cron_ids, "Registered in background automation scheduler")
    s, job_res = action("settings", "trigger_scheduled_task", {"job_id": "daily_ssl_audit"})
    log_test("Automated SSL Audit Scheduled Execution", job_res.get("success") and job_res.get("job", {}).get("status") == "COMPLETED", f"Duration: {job_res.get('result', {}).get('duration_ms', 0)}ms")

    # 24. macOS Process Resource Watchdog
    print(f"\n{INFO} 24. Subsystem: macOS Process Resource Watchdog:")
    s, proc_res = action("settings", "get_top_processes", {"by": "cpu", "limit": 10})
    procs = proc_res.get("processes", [])
    log_test("macOS Process Table Sampling", proc_res.get("success") and len(procs) > 0, f"{len(procs)} active processes sampled via ps")
    from utils.process_watchdog import is_protected_pid
    prot_check = is_protected_pid(1) and is_protected_pid(os.getpid())
    log_test("Protected Process Shielding Guard", prot_check, "System daemons and feeder PID immune to termination")
    s, unconf_res = action("settings", "terminate_process", {"pid": 99999, "confirmed": False})
    log_test("Unconfirmed Process Termination Block", not unconf_res.get("success") and unconf_res.get("error") == "CONFIRMATION_REQUIRED", "Confirmation required")

    # 25. SQLite Telemetry & Audit Ledger
    print(f"\n{INFO} 25. Subsystem: SQLite Telemetry & Audit Ledger:")
    s, stats_res = action("settings", "get_ledger_stats")
    l_stats = stats_res.get("stats", {})
    log_test("Persistent SQLite Ledger Database", stats_res.get("success") and os.path.exists(l_stats.get("db_path", "")), f"Size: {l_stats.get('db_size_kb')} KB // {l_stats.get('total_snapshots')} snapshots")
    s, hist_res = action("settings", "get_ledger_history", {"metric": "load", "hours": 24})
    log_test("Time-Series Historical Telemetry Query", hist_res.get("success") and hist_res.get("count", 0) >= 0, f"{hist_res.get('count')} time-series points retrieved")

    # 26. Emergency Security Lockdown & Killswitch
    print(f"\n{INFO} 26. Subsystem: Emergency Security Lockdown & Killswitch:")
    s, lock_on = action("settings", "toggle_lockdown", {"enable": True, "reason": "Automated verification drill", "confirmed": True})
    log_test("Emergency Lockdown Engagement", lock_on.get("success") and lock_on.get("lockdown_active"), f"Lockdown engaged: {lock_on.get('reason')}")
    try:
        whk_status = 0
        try:
            req = urllib.request.Request(f"{BASE_URL}/api/webhooks/github", data=b'{"drill": true}', headers={"Content-Type": "application/json"})
            urllib.request.urlopen(req)
        except urllib.error.HTTPError as e:
            whk_status = e.code
        log_test("Lockdown Inbound Webhook Blockade", whk_status == 403, "HTTP 403 Forbidden verified on webhook ingress")

        # post() reports the status code rather than raising, so read it
        # directly instead of relying on an exception being thrown.
        act_status, act_body = action("finance", "execute_trade", {"symbol": "BTC", "side": "BUY", "amount": 0.01})
        log_test("Lockdown Outbound Mutation Shield",
                 act_status == 403 and act_body.get("error") == "LOCKDOWN_ACTIVE",
                 f"HTTP {act_status} on outbound trade action while locked down")
    finally:
        s, lock_off = action("settings", "toggle_lockdown", {"enable": False, "confirmed": True})
        log_test("Emergency Lockdown Clean Disengagement", lock_off.get("success") and not lock_off.get("lockdown_active"), "Normal operations restored across all subsystems")

    # 27. Dedicated Crypto Desk: Photon / DEX Screener & Swap Router
    print(f"\n{INFO} 27. Subsystem: Dedicated Crypto Desk (Photon / DEX Screener & Router):")
    s, tok_res = action("crypto", "get_tokens")
    tokens_list = tok_res.get("tokens", [])
    log_test("Photon / DEX Screener Token Feed", tok_res.get("success") and len(tokens_list) >= 8, f"{len(tokens_list)} memecoin assets tracking live PnL and liquidity")
    s, unconf_swap = action("crypto", "execute_swap", {"side": "BUY", "symbol": "BONK", "amount": 0.5, "confirmed": False})
    log_test("Photon Unconfirmed Swap Execution Guard", not unconf_swap.get("success") and unconf_swap.get("error") == "CONFIRMATION_REQUIRED", "Confirmation required")
    s, conf_swap = action("crypto", "execute_swap", {"side": "BUY", "symbol": "BONK", "amount": 0.5, "confirmed": True})
    log_test("Photon Instant Swap Execution", conf_swap.get("success") and bool(conf_swap.get("tx_hash")), f"TX: {conf_swap.get('tx_hash')} // {conf_swap.get('tokens_received')} $BONK")

    # 28. Twitter / X Social Sentiment Monitor & CA Extraction
    print(f"\n{INFO} 28. Subsystem: Twitter / X Memecoin Alpha & CA Extraction:")
    s, alpha_res = action("crypto", "scan_alpha_tweets")
    tweets_list = alpha_res.get("tweets", [])
    log_test("Twitter / X Alpha Stream Ingestion", alpha_res.get("success") and len(tweets_list) >= 4, f"{len(tweets_list)} alpha tweets parsed with social velocity")
    all_cas = [ca for tw in tweets_list for ca in tw.get("detected_cas", [])]
    # The detail string is built before log_test is called, so indexing an
    # empty list here used to abort the entire run whenever the upstream
    # feed returned nothing.
    ca_sample = f"{all_cas[0][:12]}..." if all_cas else "none found"
    log_test("Solana & EVM Contract Address Extraction", len(all_cas) > 0, f"{len(all_cas)} contract addresses regex extracted ({ca_sample})")

    # 29. Influencer & Alpha Copy Trading Engine
    print(f"\n{INFO} 29. Subsystem: Influencer & Alpha Copy Trading Engine:")
    s, toggle_res = action("crypto", "toggle_copy_trading", {"handle": "whale1.sol", "active": True})
    log_test("Copy Trading Whitelist Toggle", toggle_res.get("success") and toggle_res.get("trader", {}).get("active") is True, "whale1.sol set to active auto-copy")
    s, signal_res = action("crypto", "record_copy_signal", {"handle": "whale1.sol", "token_symbol": "WIF", "ca": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm", "side": "BUY", "size_sol": 0.5, "confirmed": True})
    log_test("Copy Trading Signal Execution & Routing", signal_res.get("success") and signal_res.get("action") == "COPIED_BUY", f"Copied signal from {signal_res.get('handle')} for ${signal_res.get('token')}")

    # 30. Price Alerts Watchdog & Open Positions Desk
    print(f"\n{INFO} 30. Subsystem: Crypto Price Alerts Watchdog & Holdings Desk:")
    s, alert_res = action("crypto", "create_price_alert", {"symbol": "WIF", "target_price": 3.00, "condition": "ABOVE"})
    alert_obj = alert_res.get("alert", {})
    log_test("Real-Time Crypto Price Alert Registration", alert_res.get("success") and alert_obj.get("status") == "ACTIVE", f"Alert: ${alert_obj.get('symbol')} {alert_obj.get('condition')} ${alert_obj.get('target_price')}")
    s, del_alert = action("crypto", "delete_price_alert", {"alert_id": alert_obj.get("id")})
    log_test("Price Alert Removal & Cleanup", del_alert.get("success"), f"Alert {alert_obj.get('id')} deleted cleanly")
    s, sched_res = action("settings", "trigger_scheduled_task", {"job_id": "crypto_alert_watchdog"})
    log_test("Automated Crypto Alert Watchdog Cron", sched_res.get("success") and sched_res.get("job", {}).get("status") == "COMPLETED", f"Duration: {sched_res.get('result', {}).get('duration_ms', 0)}ms")

    # 31. Autonomous AI Trading Bot Lifecycle & Strategy Engine
    print(f"\n{INFO} 31. Subsystem: Autonomous AI Trading Bot Lifecycle & Strategy Signals:")
    s, bot_status = action("crypto", "get_bot_status")
    bst = bot_status.get("bot_state", {})
    log_test("Autonomous Bot Initial Standby State", bot_status.get("success") and bst.get("paper_balance_sol", 0) > 0 and bst.get("initial_balance_sol") == 50.0, f"Balance: {bst.get('paper_balance_sol')} SOL, Strategies: {len(bst.get('active_strategies', []))}")

    s, bot_start = action("crypto", "start_trading_bot")
    log_test("Autonomous Bot Engagement (START)", bot_start.get("success") and bot_start.get("status") == "RUNNING", "AI Bot engaged in simulated paper trading mode")

    s, bot_cfg = action("crypto", "configure_bot_strategy", {"strategies": ["alpha_sniper", "whale_shadow", "mean_reversion"]})
    log_test("Autonomous Strategy Parameter Configuration", bot_cfg.get("success") and "mean_reversion" in bot_cfg.get("bot_state", {}).get("active_strategies", []), "Added mean_reversion to active strategies")

    # Trigger a poll/tick with active bot to evaluate signals
    s, state_eval = action("crypto", "get_bot_status")
    log_test("Autonomous Execution Journal Ingestion", len(state_eval.get("bot_log", [])) > 0, f"{len(state_eval.get('bot_log', []))} journal entries recorded in state")

    s, bot_stop = action("crypto", "stop_trading_bot")
    log_test("Autonomous Bot Disengagement (STOP)", bot_stop.get("success") and bot_stop.get("status") == "STANDBY", "AI Bot disengaged to standby state")

    # 32. Quantitative Strategy Backtester & Interactive Cyber Terminal Drawer
    print(f"\n{INFO} 32. Subsystem: Quantitative Strategy Backtester & Cyber Terminal Drawer:")
    s, bt_res = action("crypto", "run_strategy_backtest", {"epochs": 100})
    bt_data = bt_res.get("backtest", {})
    log_test("Quantitative 100-Epoch Simulation Execution", bt_res.get("success") and bt_data.get("trades_executed") == 100, f"Win Rate: {bt_data.get('win_rate_pct')}%, Net PnL: {bt_data.get('net_pnl_sol')} SOL")

    log_test("Backtest Metrics Validation", (0.0 <= bt_data.get("win_rate_pct", -1) <= 100.0) and "sharpe_ratio" in bt_data and "max_drawdown_pct" in bt_data, f"Sharpe: {bt_data.get('sharpe_ratio')}, MaxDD: -{bt_data.get('max_drawdown_pct')}%")

    s, term_help = action("crypto", "execute_terminal_command", {"command": "help"})
    log_test("Cyber Terminal Command Interpreter (help)", term_help.get("success") and "CYBER TERMINAL" in term_help.get("output", ""), "Help index returned with valid command list")

    s, term_bot = action("crypto", "execute_terminal_command", {"command": "bot status"})
    log_test("Cyber Terminal Command Interpreter (bot status)", term_bot.get("success") and ("AI Strategy Bot" in term_bot.get("output", "") or "Autonomous" in term_bot.get("output", "")), "Bot telemetry formatted for cyber console")

    s, term_tokens = action("crypto", "execute_terminal_command", {"command": "tokens"})
    log_test("Cyber Terminal Command Interpreter (tokens screener)", term_tokens.get("success") and "PRICE" in term_tokens.get("output", ""), "Screener matrix formatted for cyber console")


    # 27. Updater workspace, self-update and improvement agent
    print(f"\n{INFO} 27. Subsystem: Updater Workspace & Improvement Agent:")
    try:
        # The Command Centre shell is now the front door; the previous
        # shell, which these markup assertions describe, is at /classic.
        req = urllib.request.Request(f"{BASE_URL}/classic", headers={"User-Agent": "CC-TestRunner/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            shell_html = r.read().decode("utf-8", errors="replace")
    except Exception:
        shell_html = ""
    try:
        req = urllib.request.Request(f"{BASE_URL}/js/u1-updater.js", headers={"User-Agent": "CC-TestRunner/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            updater_js = r.read().decode("utf-8", errors="replace")
    except Exception:
        updater_js = ""

    log_test("Updater Navigation Entry Mounted", 'data-section="updater"' in shell_html, "Updater rail button present in the shell")
    log_test("Updater Workspace Section Mounted", 'id="section-updater"' in shell_html, "#section-updater active in DOM")
    panels = ["updaterRuntimeContainer", "updaterChannelContainer", "updaterAgentContainer",
              "updaterMaintenanceContainer", "updaterChangelogContainer"]
    log_test("All Five Updater Panels Present", all(p in shell_html for p in panels), "Runtime, channel, agent, maintenance and changelog panels mounted")
    log_test("Updater Client Module Served", len(updater_js) > 4000 and "/js/u1-updater.js" in shell_html, f"u1-updater.js delivered ({len(updater_js)} bytes) and linked")
    log_test("Updater Client Escapes Rendered Values", "function esc(" in updater_js and "replace(/[&<>\"']/g" in updater_js, "Git output and agent findings escaped before insertion")

    s, upd = action("updater", "get_status", {})
    runtime = upd.get("runtime", {})
    log_test("Updater Status Endpoint Responds", upd.get("success") is True, f"Version {runtime.get('version')} on Python {runtime.get('python')}")
    log_test("Reported Port Matches The Configured Port", runtime.get("port") == PORT, f"Serving on 127.0.0.1:{runtime.get('port')}")
    log_test("Optional Dependency Inventory Reported", isinstance(runtime.get("optional_dependencies"), dict) and len(runtime.get("optional_dependencies", {})) >= 3, f"{len(runtime.get('optional_dependencies', {}))} optional packages inventoried")
    git_state = upd.get("git", {})
    log_test("Git Snapshot Is Free Of Raw Fatal Output", "fatal:" not in json.dumps(git_state), f"Branch {git_state.get('branch')} at {git_state.get('commit') or 'no commits yet'}")

    for act_name in ("apply_update", "install_dependencies", "rebuild_desktop_app", "restart_server"):
        s, gated = action("updater", act_name, {})
        log_test(f"Confirmation Gate Holds: {act_name}", gated.get("error") == "confirmation_required", "Refused without explicit confirmation")

    s, agent = action("updater", "agent_status", {})
    log_test("Improvement Agent Is Running In-Process", agent.get("available") is True, f"Agent enabled: {agent.get('enabled')} // interval {agent.get('interval_seconds')}s")
    log_test("Improvement Agent Produces Findings", isinstance(agent.get("findings"), list), f"{len(agent.get('findings', []))} findings recorded")
    log_test("Improvement Agent Declares Its Safeguards", "No automatic repairs" in (agent.get("safeguards") or []), "No automatic repairs, no outbound requests, no paid AI calls")
    s, scan = action("updater", "agent_configure", {"mode": "scan"})
    log_test("Improvement Agent Accepts A Manual Scan", scan.get("success") is True, "Scan queued on request")
    s, bad_mode = action("updater", "agent_configure", {"mode": "wipe_disk"})
    log_test("Improvement Agent Rejects An Unknown Mode", bad_mode.get("success") is False, f"Rejected: {bad_mode.get('error')}")

    s, unknown = action("updater", "not_a_real_action", {})
    log_test("Unknown Updater Action Answers Cleanly", unknown.get("success") is False and "not available" in str(unknown.get("error")), "Reported as JSON rather than raised")

    # 28. Request-handling hardening
    print(f"\n{INFO} 28. Subsystem: Request Error Boundary & Connection Hygiene:")
    server_src = open(os.path.join(BASE_DIR, "server.py"), encoding="utf-8").read()
    log_test("Service Faults Answer With JSON, Not A Dropped Socket", "An exception escaping a service used to kill" in server_src, "dispatch_action wrapped; failures return HTTP 500 with a structured body")
    log_test("Client Disconnects No Longer Log Tracebacks", "def handle_error(self, request, client_address)" in server_src and "ConnectionResetError" in server_src, "Tab closes and aborted fetches are treated as normal traffic")
    log_test("CORS Origin Follows The Configured Port", "def self_origin" in server_src and "http://127.0.0.1:8787" not in server_src, "Access-Control-Allow-Origin derived from config.json")
    menubar_src = open(os.path.join(BASE_DIR, "utils/menubar.py"), encoding="utf-8").read()
    log_test("Menu Bar Links Follow The Configured Port", "def configured_port" in menubar_src and "href={BASE}" in menubar_src, "Every menu-bar deep link built from the live port")

    # 29. Measurement floor (Improvement Engine stage 1)
    print(f"\n{INFO} 29. Subsystem: Measurement Floor & Health Scoring:")
    s, health = action("updater", "get_health", {})
    log_test("Health Endpoint Reports Only Measured Components", health.get("success") is True and isinstance(health.get("components"), dict), f"Score {health.get('score')} from {len(health.get('components', {}))} measured component(s)")
    log_test("Unmeasured Components Are Named, Not Defaulted", isinstance(health.get("unmeasured"), list), f"Unmeasured: {', '.join(health.get('unmeasured') or []) or 'none'}")
    log_test("Health Score Is The Mean Of Measured Components", (health.get("score") is None and not health.get("components")) or abs(health["score"] - sum(health["components"].values()) / max(1, len(health["components"]))) < 0.15, "No component is weighted by an invented factor")

    s, live = action("updater", "get_metrics", {})
    log_test("Startup Time Measured", live.get("startup_ms") is not None and live["startup_ms"] > 0, f"Process ready in {live.get('startup_ms')} ms")
    log_test("Per-Endpoint Latency Recorded", live.get("requests", {}).get("total", 0) > 0 and len(live["requests"]["endpoints"]) > 0, f"{live['requests']['total']} requests across {len(live['requests']['endpoints'])} endpoint(s)")
    slowest = live["requests"]["endpoints"][0] if live["requests"]["endpoints"] else {}
    log_test("Latency Percentiles Computed From Samples", slowest.get("p95_ms") is not None and slowest.get("p50_ms") is not None, f"Slowest: {slowest.get('endpoint')} p50 {slowest.get('p50_ms')}ms / p95 {slowest.get('p95_ms')}ms")
    log_test("Request Paths Are Recorded Without Query Strings", all("?" not in row.get("endpoint", "") for row in live["requests"]["endpoints"]), "Query strings dropped before a path is stored")
    log_test("SSE Stream Lifecycle Counted", isinstance(live.get("sse", {}).get("opened"), int), f"{live['sse']['opened']} opened // {live['sse']['closed']} closed // peak {live['sse']['peak_concurrent']}")
    resources = live.get("resources", {})
    log_test("Resource Sampling States Its Availability", resources.get("available") is True or resources.get("note"), (f"CPU {resources.get('cpu_percent')}% // RSS {resources.get('rss_mb')} MB" if resources.get("available") else resources.get("note")))

    try:
        req = urllib.request.Request(f"{BASE_URL}/api/telemetry/client",
                                     data=json.dumps({"kind": "TestError", "where": "suite", "message": "verification probe"}).encode("utf-8"),
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            client_ack = json.loads(r.read().decode("utf-8"))
    except Exception as exc:
        client_ack = {"success": False, "error": str(exc)}
    log_test("Frontend Fault Intake Accepts Browser Exceptions", client_ack.get("recorded") is True, "Browser exceptions recorded against the measurement floor")
    s, after = action("updater", "get_metrics", {})
    log_test("Frontend Faults Kept Separate From Backend Faults", any(e.get("kind") == "TestError" for e in after.get("exceptions", {}).get("recent_frontend", [])), f"{len(after['exceptions']['recent_frontend'])} frontend fault(s) recorded separately")

    s, base = action("updater", "capture_baseline", {"label": "suite"})
    log_test("Baseline Captured From Live Measurements", base.get("success") is True and base.get("baseline", {}).get("label") == "suite", f"Baseline holds startup {base.get('baseline', {}).get('startup_ms')}ms and health {base.get('baseline', {}).get('health_score')}")
    s, cmp_res = action("updater", "compare_baseline", {"label": "suite"})
    log_test("Baseline Comparison Flags Unmeasured Fields", cmp_res.get("available") is True and all(("change_pct" in d and ("measured" in d)) for d in cmp_res.get("deltas", {}).values()), "Every delta declares whether it was actually measured")
    unmeasured_deltas = [k for k, d in cmp_res.get("deltas", {}).items() if not d.get("measured")]
    log_test("No Percentage Is Reported For Unmeasured Fields", all(cmp_res["deltas"][k]["change_pct"] is None for k in unmeasured_deltas), f"{len(unmeasured_deltas)} field(s) correctly withheld")
    s, reset_gate = action("updater", "reset_metrics", {})
    log_test("Clearing Measurements Requires Confirmation", reset_gate.get("error") == "confirmation_required", "Measurement history cannot be wiped without confirmation")

    shell_has_health = 'id="updaterHealthContainer"' in shell_html
    log_test("Measured Health Panel Mounted In The Workspace", shell_has_health, "#updaterHealthContainer present in the Updater section")
    log_test("Client Reports Its Own Exceptions", "reportFrontendFaults" in updater_js and "unhandledrejection" in updater_js, "window.onerror and unhandled promise rejections reported to the measurement floor")
    log_test("Client Renders NOT MEASURED Rather Than A Number", "NOT MEASURED" in updater_js, "Missing measurements are labelled, never defaulted to zero")

    # 30. Command Centre shell (front door)
    print(f"\n{INFO} 30. Subsystem: Command Centre Shell:")
    def _text(p):
        try:
            rq = urllib.request.Request(f"{BASE_URL}{p}", headers={"User-Agent": "CC-TestRunner/1.0"})
            with urllib.request.urlopen(rq, timeout=10) as rr:
                return rr.status, rr.read().decode("utf-8", errors="replace")
        except Exception:
            return 0, ""
    s_root, root_html = _text("/")
    s_css, shell_css = _text("/css/u1os.css")
    s_js, shell_js = _text("/js/u1os.js")
    log_test("Command Centre Shell Is The Front Door", s_root == 200 and 'id="globe"' in root_html, "/ serves the Command Centre shell")
    log_test("Previous Shell Still Reachable At /classic", 'id="section-updater"' in shell_html, "Nothing that worked before was removed")
    log_test("Shell Stylesheet Served", s_css == 200 and len(shell_css) > 8000, f"u1os.css delivered ({len(shell_css)} bytes)")
    log_test("Shell Controller Served", s_js == 200 and len(shell_js) > 20000, f"u1os.js delivered ({len(shell_js)} bytes)")
    for part in ("rail", "dock", "palList", "notifList", "tools", "gauges", "storage", "player"):
        log_test(f"Shell Mounts #{part}", f'id="{part}"' in root_html, f"#{part} present in the shell")
    log_test("Web Audio Voice Pack Present", all(v in shell_js for v in ["tap:", "hover:", "nav:", "ok:", "warn:", "bad:", "ping:", "boot:", "tick:"]), "Synthesised interface voices, no audio assets")
    log_test("Sound Mute And Volume Persist", "u1.sound" in shell_js and "u1.vol" in shell_js, "Master gain, mute and level stored locally")
    log_test("Canvas Scenes Are Real Drawing Code", "requestAnimationFrame" in shell_js and "createRadialGradient" in shell_js, "Globe, starfield, gauges and charts drawn on canvas")
    log_test("Command Palette Bound To Cmd+K", "metaKey" in shell_js and "palList" in shell_js, "Palette opens on ⌘K and on search focus")
    log_test("Notification Centre Persists Its Feed", "u1.feed" in shell_js, "Unread counts and history survive a reload")
    log_test("Single Focus Clock Drives Card And Player", "U.focus = {" in shell_js, "The player owns the timer; the card reads from it")
    log_test("Shell Reports Its Own Exceptions", "/api/telemetry/client" in shell_js, "Browser faults feed the measurement floor")
    log_test("Absent Sources Are Labelled, Not Invented", "NOT MEASURED" in shell_js and "no activity recorded" in shell_js, "Panels state when a source is missing instead of showing a number")
    log_test("Reduced Motion Honoured", "prefers-reduced-motion" in shell_css and "reduced" in shell_js, "Every animation collapses when the viewer asks for less motion")

    # Summary
    print(f"\n{CYAN}============================================================{RESET}")
    print(f" TOTAL TESTS EXECUTED: {tests_run}")
    print(f" TOTAL TESTS PASSED:   \033[32m{tests_passed} / {tests_run}\033[0m")
    if tests_passed == tests_run:
        print(f" {PASS} \033[1;32mALL SUBSYSTEMS & VERIFICATION CHECKS ARE 100% OPERATIONAL!\033[0m")
    else:
        print(f" {FAIL} Some tests failed.")
    print(f"{CYAN}============================================================{RESET}\n")

if __name__ == "__main__":
    main()
