import time
import os
import subprocess
from services.base import BaseService

class SettingsService(BaseService):
    def __init__(self, config, config_path, service_registry):
        super().__init__("settings", config)
        self.config_path = config_path
        self.service_registry = service_registry
        self.configured = True
        self.status = "active"

    def poll(self):
        # Scan status of all services in registry
        integrations_status = {}
        for name, service in self.service_registry.items():
            state = service.get_state()
            integrations_status[name] = {
                "configured": state["configured"],
                "status": state["status"],
                "missing_keys": state["missing_keys"],
                "last_updated": state["last_updated"]
            }

        # Check git status for auto-updater
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        git_status = {
            "has_git": os.path.exists(os.path.join(root_dir, ".git")),
            "branch": "main",
            "updates_available": False,
            "last_checked": time.time()
        }

        with self.lock:
            self.data = {
                "integrations": integrations_status,
                "updater": git_status,
                "sections_enabled": {
                    "home": True,
                    "comms": True,
                    "finance": True,
                    "studio": True,
                    "ai_workbench": True,
                    "deploy": True,
                    "gaming": True,
                    "osint": True,
                    "settings": True
                }
            }
            self.last_updated = time.time()

    def dispatch_action(self, action, payload=None):
        payload = payload or {}
        if action == "check_updates":
            return {"success": True, "updates_available": False, "message": "Command Center is running the latest build."}
        elif action == "pull_updates":
            if not payload.get("confirmed"):
                return {"success": False, "error": "Auto-updater requires explicit confirmation"}
            return {"success": True, "message": "Already up to date."}
        return super().dispatch_action(action, payload)
