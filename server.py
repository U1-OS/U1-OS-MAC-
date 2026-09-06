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
from services.intelligence import IntelligenceService
from services.finance import FinanceService
from services.comms import CommsService
from services.deploy import DeployService
from services.ai_workbench import AIWorkbenchService
from services.studio import StudioService
from services.gaming import GamingService
from services.osint import OSINTService
from services.settings import SettingsService

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
        self.services["settings"] = SettingsService(self.config, self.config_path, self.services)

        # Wire real-time event callbacks for streaming & notifications
        for svc_name, svc in self.services.items():
            svc.on_event = self._handle_service_event

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

        if path == "/api/action":
            service_name = payload.get("service")
            action = payload.get("action")
            action_payload = payload.get("payload", {})

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
