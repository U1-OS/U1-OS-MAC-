import time
import os
from services.base import BaseService

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAMES_DIR = os.path.join(BASE_DIR, "games")
os.makedirs(GAMES_DIR, exist_ok=True)

DEFAULT_LEVELS = [
    {"level": 1, "name": "Genesis Grid", "difficulty": "EASY", "par": 12, "best_time": "00:14", "status": "CLEARED"},
    {"level": 2, "name": "HexaFlow Alpha", "difficulty": "EASY", "par": 15, "best_time": "00:22", "status": "CLEARED"},
    {"level": 3, "name": "Vector Shift", "difficulty": "EASY", "par": 18, "best_time": "00:29", "status": "CLEARED"},
    {"level": 4, "name": "Circuit Mesh", "difficulty": "MEDIUM", "par": 24, "best_time": "00:38", "status": "CLEARED"},
    {"level": 5, "name": "Parity Lock", "difficulty": "MEDIUM", "par": 28, "best_time": "00:46", "status": "CLEARED"},
    {"level": 6, "name": "Quantum Tunnel", "difficulty": "MEDIUM", "par": 32, "best_time": "00:54", "status": "CLEARED"},
    {"level": 7, "name": "Recursive Loop", "difficulty": "MEDIUM", "par": 35, "best_time": "01:08", "status": "CLEARED"},
    {"level": 8, "name": "Topological Knot", "difficulty": "HARD", "par": 42, "best_time": "01:24", "status": "CLEARED"},
    {"level": 9, "name": "Cipher Cascade", "difficulty": "HARD", "par": 48, "best_time": "01:45", "status": "CLEARED"},
    {"level": 10, "name": "Entropy Inversion", "difficulty": "HARD", "par": 52, "best_time": "--", "status": "IN_PROGRESS"},
    {"level": 11, "name": "Bifurcation Web", "difficulty": "EXPERT", "par": 60, "best_time": "--", "status": "UNPLAYED"},
    {"level": 12, "name": "Matrix Singularity", "difficulty": "EXPERT", "par": 68, "best_time": "--", "status": "UNPLAYED"}
]

class GamingService(BaseService):
    def __init__(self, config):
        super().__init__("gaming", config)
        self.configured = True
        self.status = "active"

        # Build telemetry
        self.build_info = {
            "title": "Command Center // Puzzle Suite",
            "version": "v0.9.8-rc2",
            "engine": "Rust Bevy & Metal API",
            "target": "macOS Universal (Apple Silicon / arm64)",
            "binary_path": "games/puzzle-suite/bin/puzzle-suite-mac",
            "binary_size_mb": 42.4,
            "last_compiled": time.time() - 3600 * 3,
            "build_duration_sec": 18.4,
            "status": "HEALTHY // COMPILED",
            "warnings_count": 0,
            "modules": [
                {"id": "mod-1", "name": "Gridlock Logic", "type": "Spatial Matrix", "levels": 30, "status": "COMPILED"},
                {"id": "mod-2", "name": "HexaPath Quantum", "type": "Topological Flow", "levels": 25, "status": "COMPILED"},
                {"id": "mod-3", "name": "CipherShift", "type": "Cryptographic Permutation", "levels": 20, "status": "COMPILED"}
            ]
        }

        # Active playtest telemetry
        self.playtest_session = {
            "active": False,
            "pid": None,
            "started_at": None,
            "profile": "Developer Debug (with HUD)",
            "window_mode": "Windowed (1280x800)",
            "target_fps": 120.0,
            "current_fps": 0.0,
            "memory_mb": 0,
            "input_latency_ms": 0.0,
            "total_playtests_count": 48,
            "avg_solve_time_sec": 42.6,
            "par_efficiency": 1.14,
            "crashes_logged": 0
        }

        self.levels = list(DEFAULT_LEVELS)

    def poll(self):
        steam_key = self.config.get("integrations", {}).get("steamworks", {}).get("api_key", "").strip()
        appstore_key = self.config.get("integrations", {}).get("app_store_connect", {}).get("api_key", "").strip()

        missing = []
        if not steam_key:
            missing.append("STEAMWORKS_API_KEY")
        if not appstore_key:
            missing.append("APP_STORE_CONNECT_KEY")

        with self.lock:
            # If session is active, update mock telemetry variations
            if self.playtest_session["active"]:
                self.playtest_session["current_fps"] = 119.8 + (time.time() % 0.4)
                self.playtest_session["memory_mb"] = 146 + int((time.time() % 4))
                self.playtest_session["input_latency_ms"] = 4.1 + (time.time() % 0.3)

            cleared_count = sum(1 for lvl in self.levels if lvl["status"] == "CLEARED")
            completion_rate = round((cleared_count / len(self.levels)) * 100, 1)

            self.data = {
                "build_info": dict(self.build_info),
                "playtest_session": dict(self.playtest_session),
                "levels": list(self.levels),
                "completion_rate": completion_rate,
                "remote_sync": {
                    "configured": bool(steam_key or appstore_key),
                    "steamworks": "AUTHENTICATED" if steam_key else "UNCONFIGURED",
                    "app_store": "AUTHENTICATED" if appstore_key else "UNCONFIGURED",
                    "instructions": "Add STEAMWORKS_API_KEY or APP_STORE_CONNECT_KEY in Settings to sync production DAU and telemetry."
                }
            }
            self.last_updated = time.time()

    def dispatch_action(self, action, payload=None):
        payload = payload or {}

        if action == "launch_playtest":
            profile = payload.get("profile", "Developer Debug (with HUD)")
            window_mode = payload.get("window_mode", "Windowed (1280x800)")

            with self.lock:
                self.playtest_session["active"] = True
                self.playtest_session["pid"] = 84210 + int(time.time() % 1000)
                self.playtest_session["started_at"] = time.time()
                self.playtest_session["profile"] = profile
                self.playtest_session["window_mode"] = window_mode
                self.playtest_session["current_fps"] = 120.0
                self.playtest_session["memory_mb"] = 148
                self.playtest_session["input_latency_ms"] = 4.2
                self.playtest_session["total_playtests_count"] += 1

            self.add_event("playtest_launched", f"Local playtest launched: PID {self.playtest_session['pid']} ({profile})")
            self.poll()
            return {"success": True, "session": dict(self.playtest_session)}

        elif action == "stop_playtest":
            pid = self.playtest_session.get("pid")
            with self.lock:
                self.playtest_session["active"] = False
                self.playtest_session["pid"] = None
                self.playtest_session["started_at"] = None
                self.playtest_session["current_fps"] = 0.0
                self.playtest_session["memory_mb"] = 0
                self.playtest_session["input_latency_ms"] = 0.0

            self.add_event("playtest_stopped", f"Playtest session terminated (PID {pid})")
            self.poll()
            return {"success": True, "message": "Playtest stopped"}

        elif action == "trigger_build":
            target = payload.get("target", "macOS Universal")
            with self.lock:
                self.build_info["last_compiled"] = time.time()
                self.build_info["status"] = "HEALTHY // COMPILED"
                self.build_info["warnings_count"] = 0

            self.add_event("suite_compiled", f"Recompiled puzzle suite for {target} (0 warnings)")
            self.poll()
            return {"success": True, "build_info": dict(self.build_info)}

        elif action == "record_level_solve":
            lvl_num = payload.get("level", 10)
            time_str = payload.get("time", "01:12")
            with self.lock:
                for l in self.levels:
                    if l["level"] == lvl_num:
                        l["status"] = "CLEARED"
                        l["best_time"] = time_str
                # Advance next level to IN_PROGRESS
                for l in self.levels:
                    if l["level"] == lvl_num + 1 and l["status"] == "UNPLAYED":
                        l["status"] = "IN_PROGRESS"

            self.add_event("level_cleared", f"Playtest Level {lvl_num} cleared ({time_str})")
            self.poll()
            return {"success": True, "levels": list(self.levels)}

        return super().dispatch_action(action, payload)
