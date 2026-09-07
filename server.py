#!/usr/bin/env python3
"""
Command Center — macOS Business Operating System Local Feeder
Binds strictly to 127.0.0.1:8787
Feeds shared state across all services to the living slab UI
"""

import os
import sys
import json
import time
import queue
import threading
import mimetypes
from http.server import HTTPServer, SimpleHTTPRequestHandler
from socketserver import ThreadingMixIn

# Add current directory to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from utils import macos
from utils.scheduler import AutomationScheduler
from services.intelligence import IntelligenceService
from services.finance import FinanceService
from services.comms import CommsService
from services.deploy import DeployService
from services.ai_workbench import AIWorkbenchService
from services.studio import StudioService
from services.gaming import GamingService
from services.osint import OSINTService
from services.crypto import CryptoService
from services.settings import SettingsService
from services.telegram_bot import TelegramService
from utils import telegram

CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
STATIC_DIR = os.path.join(BASE_DIR, "static")

class SSEEventBroker:
    """Thread-safe publish/subscribe broker for real-time Server-Sent Events."""
    def __init__(self):
        self.subscribers = []
        self.lock = threading.Lock()

    def subscribe(self):
        q = queue.Queue(maxsize=100)
        with self.lock:
            self.subscribers.append(q)
        return q

    def unsubscribe(self, q):
        with self.lock:
            if q in self.subscribers:
                self.subscribers.remove(q)

    def publish(self, event_type, payload):
        data = {
            "type": event_type,
            "timestamp": time.time(),
            "payload": payload
        }
        with self.lock:
            dead = []
            for q in self.subscribers:
                try:
                    q.put_nowait(data)
                except queue.Full:
                    dead.append(q)
            for d in dead:
                if d in self.subscribers:
                    self.subscribers.remove(d)

class ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True

class CommandCenterFeeder:
    def __init__(self, config_path):
        self.config_path = config_path
        self.config = self.load_config()
        self.lock = threading.RLock()
        self.running = True
        self.sse_broker = SSEEventBroker()
        self.webhook_log = []
        self.webhook_lock = threading.Lock()

        # Initialize all modular services
        self.services = {}
        self.services["intelligence"] = IntelligenceService(self.config)
        self.services["finance"] = FinanceService(self.config)
        self.services["comms"] = CommsService(self.config)
        self.services["deploy"] = DeployService(self.config)
        self.services["ai_workbench"] = AIWorkbenchService(self.config)
        self.services["studio"] = StudioService(self.config)
        self.services["gaming"] = GamingService(self.config)
        self.services["osint"] = OSINTService(self.config)
        self.services["crypto"] = CryptoService(self.config)
        self.services["telegram"] = TelegramService(self.config)
        self.services["settings"] = SettingsService(self.config, self.config_path, self.services)
        for svc in self.services.values():
            svc.feeder = self

        # Initialize Automation Scheduler
        self.scheduler = AutomationScheduler(feeder=self)
        self.scheduler.on_job_completed = self._handle_scheduler_job_completed
        self.services["settings"].scheduler = self.scheduler
        self.scheduler.start()

        # Wire real-time event callbacks for streaming & notifications
        for svc_name, svc in self.services.items():
            svc.on_event = self._handle_service_event

    def record_webhook(self, source, payload, headers):
        with self.webhook_lock:
            entry_id = f"whk-{int(time.time() * 1000)}"
            summary = f"Webhook received from {source.upper()}"
            if isinstance(payload, dict):
                if "event" in payload:
                    summary += f": {payload['event']}"
                elif "type" in payload:
                    summary += f": {payload['type']}"
                elif "action" in payload:
                    summary += f": {payload['action']}"
            entry = {
                "id": entry_id,
                "timestamp": time.time(),
                "time_str": time.strftime("%H:%M:%S"),
                "source": source.lower(),
                "summary": summary,
                "payload": payload,
                "headers": {k: v for k, v in headers.items() if k.lower() in ["content-type", "user-agent", "x-stripe-signature", "x-hub-signature-256"]}
            }
            self.webhook_log.append(entry)
            if len(self.webhook_log) > 30:
                self.webhook_log.pop(0)

        # Broadcast over SSE
        self.sse_broker.publish("webhook_received", entry)

        # Native Notification
        notify_enabled = self.config.get("system", {}).get("native_notifications", True)
        if notify_enabled:
            macos.notify(f"WEBHOOK // {source.upper()}", summary, sound="Hero")

        return entry

    def get_webhooks(self):
        with self.webhook_lock:
            return list(self.webhook_log)

    def _handle_scheduler_job_completed(self, job_dict):
        self.sse_broker.publish("scheduler_job_completed", job_dict)

    def _handle_service_event(self, service_name, event):
        # Broadcast immediately to all connected SSE clients
        self.sse_broker.publish("service_event", {
            "service": service_name,
            "event": event
        })

        # Check native notifications preference
        notify_enabled = self.config.get("system", {}).get("native_notifications", True)
        evt_type = event.get("type", "")
        summary = event.get("summary", "System event triggered")

        if notify_enabled and evt_type in [
            "trade_executed", "bill_settled", "sms_sent", 
            "video_render_completed", "video_render_enqueued",
            "playtest_started", "playtest_stopped",
            "vault_exported", "vault_imported", "launchagent_installed"
        ]:
            title = f"COMMAND CENTER // {service_name.upper()}"
            macos.notify(title, summary, sound="Hero")

        # Real-time Telegram broadcast for crypto & security events
        if "telegram" in self.services and self.services["telegram"].configured:
            try:
                tg_svc = self.services["telegram"]
                if evt_type in ["photon_swap_executed", "trade_executed"]:
                    payload = event.get("payload", {})
                    msg = telegram.format_trade_alert(
                        token_symbol=payload.get("symbol", "SOL"),
                        action=payload.get("side", "BUY"),
                        amount_sol=payload.get("amount_sol", 0.5),
                        price_usd=payload.get("price_usd", 0.0),
                        tokens_qty=payload.get("tokens_received", 0.0),
                        tx_hash=payload.get("tx_hash")
                    )
                    tg_svc.broadcast_alert(msg)
                elif evt_type == "crypto_alert_triggered":
                    alt = event.get("payload", {}).get("alert", {})
                    msg = telegram.format_price_alert(
                        alt.get("symbol", "TOKEN"),
                        alt.get("current_price", 0),
                        alt.get("condition", "ABOVE"),
                        alt.get("target_price", 0)
                    )
                    tg_svc.broadcast_alert(msg)
                elif evt_type in ["lockdown_engaged", "lockdown_disengaged"]:
                    msg = telegram.format_lockdown_notice(evt_type == "lockdown_engaged")
                    tg_svc.broadcast_alert(msg)
            except Exception:
                pass

    def broadcast_action(self, service_name, action, result):
        self.sse_broker.publish("action_dispatched", {
            "service": service_name,
            "action": action,
            "result": result
        })

    def load_config(self):
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"[WARN] Error reading config.json: {e}")
        return {"system": {"host": "127.0.0.1", "port": 8787}}

    def save_config(self, new_config):
        with self.lock:
            self.config = new_config
            try:
                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(self.config, f, indent=2)
                # Update config in services
                for service in self.services.values():
                    service.config = self.config
                return True
            except Exception as e:
                print(f"[ERROR] Failed to save config: {e}")
                return False

    def poll_all_services(self):
        """Runs periodic polling across all services."""
        for name, service in self.services.items():
            try:
                service.poll()
            except Exception as e:
                print(f"[ERR] Exception in service '{name}': {e}")

    def get_full_state(self):
        state = {
            "system": {
                "server_time": time.time(),
                "host": self.config.get("system", {}).get("host", "127.0.0.1"),
                "port": self.config.get("system", {}).get("port", 8787),
                "os": "macOS",
                "version": "1.0.0"
            },
            "services": {}
        }
        for name, service in self.services.items():
            state["services"][name] = service.get_state()
        state["scheduler"] = self.scheduler.get_status()
        state["webhooks"] = self.get_webhooks()
        return state

    def start_background_loop(self):
        def loop():
            # Initial poll
            self.poll_all_services()
            while self.running:
                interval = self.config.get("system", {}).get("refresh_interval_sec", 4)
                time.sleep(interval)
                self.poll_all_services()

        thread = threading.Thread(target=loop, daemon=True, name="FeederLoop")
        thread.start()

feeder = None

class CommandCenterHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        # Quiet standard output for clean operations
        pass

    def send_json(self, data, status_code=200):
        body = json.dumps(data, indent=2).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:8787")
        self.send_header("Cache-Control", "no-cache, no-store, must-revalidate")
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        path = self.path.split("?")[0]

        if path == "/api/state":
            state = feeder.get_full_state()
            self.send_json(state)
            return

        if path == "/api/webhooks":
            self.send_json({"success": True, "webhooks": feeder.get_webhooks()})
            return

        if path == "/api/scheduler":
            self.send_json({"success": True, "jobs": feeder.scheduler.get_status()})
            return

        if path == "/api/ledger/history":
            from urllib.parse import parse_qs, urlparse
            query = parse_qs(urlparse(self.path).query)
            metric = query.get("metric", ["load"])[0]
            try:
                hours = float(query.get("hours", [24.0])[0])
            except ValueError:
                hours = 24.0
            from utils.ledger import get_history
            history = get_history(metric=metric, hours=hours)
            self.send_json({"success": True, "metric": metric, "history": history, "count": len(history)})
            return

        if path == "/api/ledger/audit":
            from urllib.parse import parse_qs, urlparse
            query = parse_qs(urlparse(self.path).query)
            try:
                limit = int(query.get("limit", [50])[0])
            except ValueError:
                limit = 50
            service = query.get("service", [None])[0]
            from utils.ledger import get_audit_log
            audit = get_audit_log(limit=limit, service=service)
            self.send_json({"success": True, "audit": audit, "count": len(audit)})
            return

        if path == "/api/processes":
            from urllib.parse import parse_qs, urlparse
            query = parse_qs(urlparse(self.path).query)
            by = query.get("by", ["cpu"])[0]
            try:
                limit = int(query.get("limit", [15])[0])
            except ValueError:
                limit = 15
            from utils.process_watchdog import get_top_processes
            procs = get_top_processes(by=by, limit=limit)
            self.send_json({"success": True, "by": by, "processes": procs, "count": len(procs)})
            return

        if path == "/api/events":
            self.send_response(200)
            self.send_header("Content-Type", "text/event-stream; charset=utf-8")
            self.send_header("Cache-Control", "no-cache, no-transform")
            self.send_header("Connection", "keep-alive")
            self.send_header("Access-Control-Allow-Origin", "http://127.0.0.1:8787")
            self.send_header("X-Accel-Buffering", "no")
            self.end_headers()

            q = feeder.sse_broker.subscribe()
            try:
                # Send initial handshake frame
                handshake = f"data: {json.dumps({'type': 'connected', 'timestamp': time.time(), 'message': 'Command Center SSE Stream Active'})}\n\n"
                self.wfile.write(handshake.encode("utf-8"))
                self.wfile.flush()

                while feeder.running:
                    try:
                        evt = q.get(timeout=10)
                        msg = f"data: {json.dumps(evt)}\n\n"
                        self.wfile.write(msg.encode("utf-8"))
                        self.wfile.flush()
                    except queue.Empty:
                        # Keep-alive comment heartbeat
                        self.wfile.write(b": ping\n\n")
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, Exception):
                pass
            finally:
                feeder.sse_broker.unsubscribe(q)
            return

        if path == "/api/config":
            # Mask secret keys for security
            cfg = json.loads(json.dumps(feeder.config))
            for k, sec in cfg.get("integrations", {}).items():
                if isinstance(sec, dict):
                    for prop in sec:
                        if any(token in prop for token in ["key", "secret", "token"]):
                            val = sec[prop]
                            if val:
                                sec[prop] = val[:4] + "••••••••" if len(val) > 4 else "••••"
            self.send_json(cfg)
            return

        # Serve frontend files
        if path == "/" or path == "/index.html":
            file_path = os.path.join(STATIC_DIR, "index.html")
        else:
            rel_path = path.lstrip("/")
            if rel_path.startswith("static/"):
                rel_path = rel_path[len("static/"):]
            file_path = os.path.join(STATIC_DIR, rel_path)

        if os.path.exists(file_path) and os.path.isfile(file_path):
            mime_type, _ = mimetypes.guess_type(file_path)
            if not mime_type:
                mime_type = "application/octet-stream"
            try:
                with open(file_path, "rb") as f:
                    content = f.read()
                self.send_response(200)
                self.send_header("Content-Type", mime_type)
                self.send_header("Content-Length", str(len(content)))
                if path == "/sw.js":
                    self.send_header("Service-Worker-Allowed", "/")
                    self.send_header("Cache-Control", "no-cache")
                self.end_headers()
                self.wfile.write(content)
                return
            except Exception as e:
                self.send_error(500, f"Error reading file: {e}")
                return

        self.send_error(404, "File Not Found")

    def do_HEAD(self):
        self.do_GET()

    def do_POST(self):
        path = self.path.split("?")[0]
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length)

        try:
            payload = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            self.send_json({"success": False, "error": "Invalid JSON"}, 400)
            return

        # Check if Emergency Lockdown is active
        settings_svc = feeder.services.get("settings")
        lockdown_active = getattr(settings_svc, "lockdown_active", False)

        if path.startswith("/api/webhooks/"):
            if lockdown_active:
                self.send_json({
                    "success": False,
                    "error": "LOCKDOWN_ACTIVE",
                    "message": "SYSTEM UNDER EMERGENCY LOCKDOWN: Inbound webhooks rejected."
                }, 403)
                return

            source = path[len("/api/webhooks/"):].strip("/") or "generic"
            headers_dict = dict(self.headers)
            entry = feeder.record_webhook(source, payload, headers_dict)
            chatops_out = None
            if source in ["discord", "slack"] and isinstance(payload, dict) and payload.get("command") and "comms" in feeder.services:
                chatops_out = feeder.services["comms"].dispatch_action("execute_chatops_command", {
                    "command": payload.get("command"),
                    "platform": source,
                    "user": payload.get("user", f"{source.title()}User")
                })
            self.send_json({
                "success": True,
                "message": f"Webhook received from {source}",
                "entry": entry,
                "chatops": chatops_out
            })
            return

        if path == "/api/auth/webauthn-challenge":
            settings_svc = feeder.services.get("settings")
            if settings_svc:
                res = settings_svc.dispatch_action("generate_biometric_challenge", payload)
                self.send_json(res)
            else:
                self.send_json({"success": False, "error": "Settings service unavailable"}, 500)
            return

        if path == "/api/auth/webauthn-verify":
            settings_svc = feeder.services.get("settings")
            if settings_svc:
                res = settings_svc.dispatch_action("verify_biometric_response", payload)
                self.send_json(res)
            else:
                self.send_json({"success": False, "error": "Settings service unavailable"}, 500)
            return

        if path == "/api/action":
            service_name = payload.get("service")
            action = payload.get("action")
            action_payload = payload.get("payload", {})

            # In lockdown mode, block outbound and hazardous mutations (except toggle_lockdown)
            MUTATING_BLOCKED_ACTIONS = {
                "send_sms", "make_call", "dispatch_email", "execute_trade",
                "execute_swap", "pull_updates", "enqueue_video_render", "clone_and_inspect"
            }
            if lockdown_active and action in MUTATING_BLOCKED_ACTIONS:
                self.send_json({
                    "success": False,
                    "error": "LOCKDOWN_ACTIVE",
                    "message": f"SYSTEM UNDER EMERGENCY LOCKDOWN: Action '{action}' blocked for system protection."
                }, 403)
                return

            if not service_name or service_name not in feeder.services:
                self.send_json({"success": False, "error": f"Unknown service: {service_name}"}, 400)
                return

            svc = feeder.services[service_name]
            result = svc.dispatch_action(action, action_payload)
            feeder.broadcast_action(service_name, action, result)
            self.send_json(result)
            return

        if path == "/api/config":
            # Update configuration
            new_integrations = payload.get("integrations")
            if new_integrations:
                feeder.config.setdefault("integrations", {}).update(new_integrations)
            new_intel = payload.get("intelligence")
            if new_intel:
                feeder.config.setdefault("intelligence", {}).update(new_intel)

            saved = feeder.save_config(feeder.config)
            feeder.poll_all_services()
            self.send_json({"success": saved})
            return

        self.send_error(404, "Not Found")

def run_server():
    global feeder
    feeder = CommandCenterFeeder(CONFIG_FILE)
    feeder.start_background_loop()

    host = "127.0.0.1"  # Bound to 127.0.0.1 only
    port = feeder.config.get("system", {}).get("port", 8787)

    server = ThreadedHTTPServer((host, port), CommandCenterHandler)
    print(f"============================================================")
    print(f" COMMAND CENTER // macOS Business Operating System")
    print(f" Server active on: http://{host}:{port}")
    print(f" Binding: 127.0.0.1 only (External network access blocked)")
    print(f"============================================================")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down Command Center feeder...")
        feeder.running = False
        server.server_close()

if __name__ == "__main__":
    run_server()
