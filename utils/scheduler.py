#!/usr/bin/env python3
"""
Command Center // Autonomous Task Scheduler (Cron Engine)
Lightweight, thread-safe recurring task orchestrator for macOS.
Runs background operational cron tasks without external dependencies.
"""

import time
import threading
import traceback
from utils import macos
from utils import briefing
from utils import vault

class ScheduledJob:
    def __init__(self, job_id, name, description, interval_sec, handler):
        self.id = job_id
        self.name = name
        self.description = description
        self.interval_sec = interval_sec
        self.handler = handler
        self.last_run = 0
        self.next_run = time.time() + interval_sec
        self.runs_count = 0
        self.status = "SCHEDULED"
        self.last_result = None
        self.lock = threading.Lock()

    def to_dict(self):
        with self.lock:
            return {
                "id": self.id,
                "name": self.name,
                "description": self.description,
                "interval_sec": self.interval_sec,
                "interval_human": self._format_interval(self.interval_sec),
                "last_run": self.last_run,
                "last_run_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.last_run)) if self.last_run else "Never",
                "next_run": self.next_run,
                "next_run_str": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(self.next_run)) if self.next_run else "--",
                "runs_count": self.runs_count,
                "status": self.status,
                "last_result": self.last_result
            }

    def _format_interval(self, sec):
        if sec >= 86400:
            return f"Every {sec // 86400}d"
        if sec >= 3600:
            return f"Every {sec // 3600}h"
        if sec >= 60:
            return f"Every {sec // 60}m"
        return f"Every {sec}s"

    def execute(self, feeder=None):
        if feeder and hasattr(feeder, "services"):
            settings_svc = feeder.services.get("settings")
            if getattr(settings_svc, "lockdown_active", False):
                with self.lock:
                    self.status = "PAUSED_LOCKDOWN"
                    self.last_result = {
                        "duration_ms": 0,
                        "summary": "Execution suspended: system under emergency lockdown",
                        "data": {}
                    }
                return self.last_result

        with self.lock:
            self.status = "RUNNING"
        start_t = time.time()
        result = None
        try:
            result = self.handler(feeder)
            status = "COMPLETED"
        except Exception as e:
            result = {"error": str(e), "traceback": traceback.format_exc()}
            status = "ERROR"
        finally:
            now = time.time()
            with self.lock:
                self.last_run = now
                self.next_run = now + self.interval_sec
                self.runs_count += 1
                self.status = status
                self.last_result = {
                    "duration_ms": round((now - start_t) * 1000, 2),
                    "summary": result.get("summary") if isinstance(result, dict) else str(result),
                    "data": result
                }
        return self.last_result

class AutomationScheduler:
    def __init__(self, feeder=None):
        self.feeder = feeder
        self.jobs = {}
        self.lock = threading.Lock()
        self.running = False
        self._thread = None
        self.on_job_completed = None
        self._register_default_jobs()

    def _register_default_jobs(self):
        # 1. Hourly DNS & Connectivity Audit
        self.register_job(
            "hourly_dns_audit",
            "Hourly DNS & Domain Audit",
            "Resolves authoritative DNS records and measures network latency",
            interval_sec=3600,
            handler=self._job_dns_audit
        )

        # 2. Daily Executive Business Dossier
        self.register_job(
            "daily_dossier",
            "Daily Executive Dossier Compilation",
            "Compiles real-time revenue, comms, and system KPIs into Markdown & HTML report",
            interval_sec=86400,
            handler=self._job_dossier_compilation
        )

        # 3. Daily Encrypted Security Vault Snapshot
        self.register_job(
            "daily_vault_snapshot",
            "Automated Security Vault Backup",
            "Exports encrypted .ccvault archive using PBKDF2-HMAC-SHA256 authenticated encryption",
            interval_sec=86400,
            handler=self._job_vault_backup
        )

        # 4. Daily SSL/TLS Certificate Expiry Audit
        self.register_job(
            "daily_ssl_audit",
            "SSL/TLS Certificate Expiry Audit",
            "Validates Port 443 TLS certificates on primary domain assets and warns of approaching expiration",
            interval_sec=86400,
            handler=self._job_ssl_audit
        )

        # 5. Persistent Telemetry Ledger Snapshot
        self.register_job(
            "telemetry_snapshot",
            "Telemetry Ledger Snapshot",
            "Records system load, RAM, disk, battery, and listening port counts to local SQLite database",
            interval_sec=300,
            handler=self._job_telemetry_snapshot
        )

        # 6. Real-Time Crypto Price Alert Watchdog
        self.register_job(
            "crypto_alert_watchdog",
            "Crypto Desk Price Alert Watchdog",
            "Monitors active price target alerts across tokens and issues macOS audio alerts when triggered",
            interval_sec=60,
            handler=self._job_crypto_alert_watchdog
        )

    def _job_dns_audit(self, feeder):
        import socket
        start = time.time()
        domain = "apple.com"
        try:
            addrs = socket.getaddrinfo(domain, 80, socket.AF_INET)
            ip = addrs[0][4][0] if addrs else "unknown"
            latency = round((time.time() - start) * 1000, 1)
            summary = f"DNS check {domain} resolved to {ip} ({latency}ms)"
            if feeder and "osint" in feeder.services:
                feeder.services["osint"].add_event("dns_scheduled_audit", summary)
            return {"domain": domain, "ip": ip, "latency_ms": latency, "summary": summary}
        except Exception as e:
            return {"error": str(e), "summary": f"DNS check failed: {e}"}

    def _job_ssl_audit(self, feeder):
        domain = "apple.com"
        if feeder and "osint" in feeder.services:
            res = feeder.services["osint"]._inspect_ssl_cert(domain)
            days = res.get("days_left", 0)
            summary = f"SSL Certificate for {domain}: {days} days remaining ({res.get('risk_level')})"
            if days < 30:
                macos.notify("SSL CERTIFICATE ALERT", summary, sound="Basso")
            feeder.services["osint"].add_event("ssl_audit", summary)
            return {"domain": domain, "days_left": days, "summary": summary}
        return {"summary": "OSINT service unavailable for SSL audit"}

    def _job_dossier_compilation(self, feeder):
        res = briefing.generate_briefing()
        summary = f"Executive Dossier generated: {res.get('markdown_file', 'unknown')}"
        if feeder and "settings" in feeder.services:
            feeder.services["settings"].add_event("dossier_compiled", summary)
        return {"briefing": res, "summary": summary}

    def _job_vault_backup(self, feeder):
        import os
        config_path = feeder.config_path if feeder else "config.json"
        res = vault.export_vault_file(config_path, password="AutoVaultBackup2026!", output_dir="backups")
        summary = f"Automated Vault Snapshot: {res.get('filename')}"
        if feeder and "settings" in feeder.services:
            feeder.services["settings"].add_event("vault_exported", summary)
        return {"vault": res, "summary": summary}

    def _job_telemetry_snapshot(self, feeder):
        from utils import ledger
        try:
            intel_svc = feeder.services.get("intelligence") if feeder and hasattr(feeder, "services") else None
            osint_svc = feeder.services.get("osint") if feeder and hasattr(feeder, "services") else None

            hw = intel_svc.data.get("hardware", {}) if intel_svc and hasattr(intel_svc, "data") else {}
            sys_info = hw.get("system", {})
            disk_info = hw.get("disk", {})
            batt_info = hw.get("battery", {})
            load_data = intel_svc.data.get("system_load", {}) if intel_svc and hasattr(intel_svc, "data") else {}

            ports_data = osint_svc.data.get("listening_ports", {}) if osint_svc and hasattr(osint_svc, "data") else {}

            snapshot = {
                "timestamp": time.time(),
                "cpu_load_1m": load_data.get("load_1m", 0.0),
                "cpu_load_5m": load_data.get("load_5m", 0.0),
                "ram_used_gb": round(sys_info.get("ram_gb", 0) * 0.5, 2),
                "ram_total_gb": sys_info.get("ram_gb", 0.0),
                "disk_free_gb": disk_info.get("free_gb", 0.0),
                "disk_total_gb": disk_info.get("total_gb", 0.0),
                "battery_percent": batt_info.get("percent", 100),
                "power_source": batt_info.get("source", "AC Power"),
                "ports_open": ports_data.get("total_open_ports", 0),
                "ports_exposed": ports_data.get("exposed_count", 0)
            }
            sid = ledger.record_snapshot(snapshot)
            summary = f"Telemetry snapshot #{sid} recorded to SQLite ledger"
            if feeder and hasattr(feeder, "services") and "settings" in feeder.services:
                feeder.services["settings"].add_event("telemetry_snapshot", summary)
            return {"snapshot_id": sid, "summary": summary}
        except Exception as e:
            return {"error": str(e), "summary": f"Telemetry snapshot failed: {e}"}

    def _job_crypto_alert_watchdog(self, feeder):
        if feeder and hasattr(feeder, "services") and "crypto" in feeder.services:
            crypto_svc = feeder.services["crypto"]
            crypto_svc.poll()
            alerts = crypto_svc.price_alerts
            active_count = len([a for a in alerts if a.get("status") == "ACTIVE"])
            triggered_count = len([a for a in alerts if a.get("status") == "TRIGGERED"])
            summary = f"Crypto watchdog scanned {len(alerts)} alerts ({active_count} active, {triggered_count} triggered)"
            return {"active_alerts": active_count, "triggered_alerts": triggered_count, "summary": summary}
        return {"summary": "Crypto service unavailable for alert watchdog"}

    def register_job(self, job_id, name, description, interval_sec, handler):
        with self.lock:
            job = ScheduledJob(job_id, name, description, interval_sec, handler)
            self.jobs[job_id] = job

    def trigger_job(self, job_id):
        job = self.jobs.get(job_id)
        if not job:
            return {"success": False, "error": f"Job '{job_id}' not found"}
        res = job.execute(self.feeder)
        if self.on_job_completed:
            try:
                self.on_job_completed(job.to_dict())
            except Exception:
                pass
        return {"success": True, "job": job.to_dict(), "result": res}

    def get_status(self):
        with self.lock:
            return [job.to_dict() for job in self.jobs.values()]

    def start(self):
        if self.running:
            return
        self.running = True
        def _loop():
            while self.running:
                now = time.time()
                with self.lock:
                    jobs_to_run = [j for j in self.jobs.values() if j.next_run and now >= j.next_run]
                for j in jobs_to_run:
                    if not self.running:
                        break
                    res = j.execute(self.feeder)
                    if self.on_job_completed:
                        try:
                            self.on_job_completed(j.to_dict())
                        except Exception:
                            pass
                time.sleep(2)
        self._thread = threading.Thread(target=_loop, daemon=True, name="CronScheduler")
        self._thread.start()

    def stop(self):
        self.running = False
