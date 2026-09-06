#!/usr/bin/env python3
"""
Command Center — SQLite Telemetry & Audit Ledger
Zero-dependency persistent local database for time-series metrics and security audit records.
Database path: data/commandcenter.db
"""

import os
import sqlite3
import time
import json
from typing import Dict, Any, List, Optional

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "commandcenter.db")

class TelemetryLedger:
    _instance = None

    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    @classmethod
    def get_instance(cls, db_path: str = DB_PATH):
        if cls._instance is None:
            cls._instance = cls(db_path)
        return cls._instance

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, timeout=5.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS telemetry_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    cpu_load_1m REAL,
                    cpu_load_5m REAL,
                    ram_used_gb REAL,
                    ram_total_gb REAL,
                    disk_free_gb REAL,
                    disk_total_gb REAL,
                    battery_percent INTEGER,
                    power_source TEXT,
                    ports_open INTEGER,
                    ports_exposed INTEGER
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_telemetry_ts ON telemetry_snapshots(timestamp)")

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp REAL NOT NULL,
                    service TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT DEFAULT 'operator',
                    details TEXT,
                    status TEXT DEFAULT 'OK'
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_audit_ts ON audit_log(timestamp)")
            conn.commit()

    def record_snapshot(self, data: Dict[str, Any]) -> int:
        """Insert a telemetry snapshot into the time-series ledger."""
        ts = data.get("timestamp", time.time())
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO telemetry_snapshots (
                    timestamp, cpu_load_1m, cpu_load_5m, ram_used_gb, ram_total_gb,
                    disk_free_gb, disk_total_gb, battery_percent, power_source,
                    ports_open, ports_exposed
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                ts,
                data.get("cpu_load_1m", 0.0),
                data.get("cpu_load_5m", 0.0),
                data.get("ram_used_gb", 0.0),
                data.get("ram_total_gb", 0.0),
                data.get("disk_free_gb", 0.0),
                data.get("disk_total_gb", 0.0),
                data.get("battery_percent", 100),
                data.get("power_source", "AC Power"),
                data.get("ports_open", 0),
                data.get("ports_exposed", 0)
            ))
            conn.commit()
            return cursor.lastrowid

    def log_audit(self, service: str, action: str, details: str = "", actor: str = "operator", status: str = "OK") -> int:
        """Append an immutable audit entry."""
        ts = time.time()
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_log (timestamp, service, action, actor, details, status)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (ts, service, action, actor, details, status))
            conn.commit()
            return cursor.lastrowid

    def get_history(self, metric: str = "load", hours: float = 24.0, limit: int = 200) -> List[Dict[str, Any]]:
        """Retrieve structured historical points for sparklines and analysis."""
        since_ts = time.time() - (hours * 3600.0)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT timestamp, cpu_load_1m, cpu_load_5m, ram_used_gb, disk_free_gb, battery_percent, ports_open, ports_exposed
                FROM telemetry_snapshots
                WHERE timestamp >= ?
                ORDER BY timestamp ASC
                LIMIT ?
            """, (since_ts, limit))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_audit_log(self, limit: int = 50, service: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieve recent audit events."""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if service:
                cursor.execute("""
                    SELECT id, timestamp, service, action, actor, details, status
                    FROM audit_log
                    WHERE service = ?
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (service, limit))
            else:
                cursor.execute("""
                    SELECT id, timestamp, service, action, actor, details, status
                    FROM audit_log
                    ORDER BY timestamp DESC
                    LIMIT ?
                """, (limit,))
            rows = cursor.fetchall()
            return [dict(r) for r in rows]

    def get_stats(self) -> Dict[str, Any]:
        """Return ledger table counts and database size."""
        db_size_bytes = 0
        if os.path.exists(self.db_path):
            db_size_bytes = os.path.getsize(self.db_path)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM telemetry_snapshots")
            total_snapshots = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM audit_log")
            total_audits = cursor.fetchone()[0]

            cursor.execute("SELECT MIN(timestamp), MAX(timestamp) FROM telemetry_snapshots")
            min_ts, max_ts = cursor.fetchone()

            return {
                "db_path": self.db_path,
                "db_size_bytes": db_size_bytes,
                "db_size_kb": round(db_size_bytes / 1024, 2),
                "total_snapshots": total_snapshots,
                "total_audits": total_audits,
                "oldest_snapshot": min_ts,
                "newest_snapshot": max_ts
            }

# Module-level convenience functions
def get_ledger() -> TelemetryLedger:
    return TelemetryLedger.get_instance()

def record_snapshot(data: Dict[str, Any]) -> int:
    return get_ledger().record_snapshot(data)

def log_audit(service: str, action: str, details: str = "", actor: str = "operator", status: str = "OK") -> int:
    return get_ledger().log_audit(service, action, details, actor, status)

def get_history(metric: str = "load", hours: float = 24.0) -> List[Dict[str, Any]]:
    return get_ledger().get_history(metric, hours)

def get_audit_log(limit: int = 50, service: Optional[str] = None) -> List[Dict[str, Any]]:
    return get_ledger().get_audit_log(limit, service)

def get_stats() -> Dict[str, Any]:
    return get_ledger().get_stats()
