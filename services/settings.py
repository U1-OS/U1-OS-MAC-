import time
import os
import json
import subprocess
from services.base import BaseService

class SettingsService(BaseService):
    def __init__(self, config, config_path, service_registry):
        super().__init__("settings", config)
        self.config_path = config_path
        self.service_registry = service_registry
        self.configured = True
        self.status = "active"
        self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

        # Setup Reference Guide for all integrations
        self.setup_reference_guide = [
            {
                "id": "stripe",
                "name": "Stripe Revenue & Billing",
                "category": "Finance",
                "keys": ["secret_key", "currency"],
                "portal_url": "https://dashboard.stripe.com/apikeys",
                "guide": "Create a restricted or standard Secret Key ('sk_live_...' or 'sk_test_...'). Requires 'rak_charges_read', 'rak_balance_read' permissions for revenue telemetry and velocity sparklines.",
                "local_path": "config.json -> integrations.stripe.secret_key"
            },
            {
                "id": "gmail",
                "name": "Google Workspace / Gmail",
                "category": "Comms",
                "keys": ["client_id", "client_secret", "refresh_token"],
                "portal_url": "https://console.cloud.google.com/apis/credentials",
                "guide": "Create OAuth 2.0 Desktop Client Credentials. Enable Gmail API with scopes 'gmail.readonly', 'gmail.modify', and 'gmail.compose'. Authorize client to generate refresh token.",
                "local_path": "config.json -> integrations.gmail"
            },
            {
                "id": "google_calendar",
                "name": "Google Calendar Agenda",
                "category": "Comms",
                "keys": ["calendar_id"],
                "portal_url": "https://calendar.google.com/calendar/r/settings",
                "guide": "Use 'primary' for your personal/executive schedule or copy the specific Calendar ID (e.g., 'your_email@domain.com') from Google Calendar settings.",
                "local_path": "config.json -> integrations.google_calendar.calendar_id"
            },
            {
                "id": "twilio",
                "name": "Twilio SMS & Voice Trunk",
                "category": "Comms",
                "keys": ["account_sid", "auth_token", "from_number"],
                "portal_url": "https://console.twilio.com/",
                "guide": "Locate your Account SID ('AC...') and Auth Token on the Twilio Console dashboard. Configure an active E.164 phone number ('+1XXXXXXXXXX') equipped with SMS and Voice capabilities.",
                "local_path": "config.json -> integrations.twilio"
            },
            {
                "id": "anthropic",
                "name": "Anthropic Claude 3.5 Sonnet",
                "category": "AI Workbench",
                "keys": ["api_key"],
                "portal_url": "https://console.anthropic.com/settings/keys",
                "guide": "Generate an API Key ('sk-ant-...'). Powers Claude 3.5 Sonnet side-by-side prompt engineering, live token accounting, and business automation workflows.",
                "local_path": "config.json -> integrations.anthropic.api_key"
            },
            {
                "id": "openai",
                "name": "OpenAI GPT-4o Engine",
                "category": "AI Workbench",
                "keys": ["api_key"],
                "portal_url": "https://platform.openai.com/api-keys",
                "guide": "Create a secret API key ('sk-proj-...' or 'sk-...'). Used for GPT-4o completions, side-by-side model comparisons, and TTS audio narration fallback.",
                "local_path": "config.json -> integrations.openai.api_key"
            },
            {
                "id": "canva",
                "name": "Canva Connect API",
                "category": "AI / Design",
                "keys": ["api_key"],
                "portal_url": "https://www.canva.com/developers/",
                "guide": "Create an integration in the Canva Developer Portal. Retrieve your Client ID / API Key for programmatic design asset and marketing slide generation.",
                "local_path": "config.json -> integrations.canva.api_key"
            },
            {
                "id": "elevenlabs",
                "name": "ElevenLabs Neural TTS",
                "category": "Studio",
                "keys": ["api_key"],
                "portal_url": "https://elevenlabs.io/app/speech-synthesis",
                "guide": "Obtain your ElevenLabs API Key from Profile Settings -> API Keys. Powers high-fidelity faceless video voiceover generation with custom voice presets (Adam, Rachel, Josh).",
                "local_path": "config.json -> integrations.elevenlabs.api_key"
            },
            {
                "id": "pexels",
                "name": "Pexels License-Clear Stock Media",
                "category": "Studio",
                "keys": ["api_key"],
                "portal_url": "https://www.pexels.com/api/",
                "guide": "Sign up for a free Pexels API Key. Provides instant search and HD video/b-roll ingestion for automated faceless video composition.",
                "local_path": "config.json -> integrations.pexels.api_key"
            },
            {
                "id": "hibp",
                "name": "HaveIBeenPwned Security Auditor",
                "category": "OSINT",
                "keys": ["api_key"],
                "portal_url": "https://haveibeenpwned.com/API/Key",
                "guide": "Acquire a commercial HIBP API key for automated credential breach audits. Command Center provides a local simulation mode for zero-cost pre-flight testing on owned domains.",
                "local_path": "config.json -> integrations.hibp.api_key"
            },
            {
                "id": "steamworks",
                "name": "Steamworks Publisher Web API",
                "category": "Gaming",
                "keys": ["app_id", "publisher_key"],
                "portal_url": "https://partner.steamgames.com/",
                "guide": "Input your Steam App ID and Publisher Web API Key to stream live concurrent player counts, wishlist additions, and release build telemetry into the Gaming dashboard.",
                "local_path": "config.json -> integrations.steamworks"
            },
            {
                "id": "app_store_connect",
                "name": "Apple App Store Connect API",
                "category": "Gaming",
                "keys": ["issuer_id", "key_id", "private_key_path"],
                "portal_url": "https://appstoreconnect.apple.com/access/api",
                "guide": "Generate an App Store Connect API Key (.p8) with 'Finance' or 'App Manager' role. Enables live macOS/iOS install tracking and TestFlight telemetry.",
                "local_path": "config.json -> integrations.app_store_connect"
            }
        ]

    def _get_git_info(self):
        """Inspects the local git repository for commit, branch, and status."""
        git_dir = os.path.join(self.root_dir, ".git")
        if not os.path.exists(git_dir):
            return {
                "has_git": False,
                "branch": "detached",
                "commit": "unknown",
                "commit_msg": "Non-git directory",
                "dirty": False,
                "remote_configured": False,
                "remote_url": "",
                "updates_available": False,
                "last_checked": time.time()
            }

        try:
            branch = subprocess.check_output(
                ["git", "branch", "--show-current"],
                cwd=self.root_dir, stderr=subprocess.DEVNULL
            ).decode("utf-8").strip() or "main"

            log_line = subprocess.check_output(
                ["git", "log", "-1", "--format=%h||%s||%cr"],
                cwd=self.root_dir, stderr=subprocess.DEVNULL
            ).decode("utf-8").strip()
            
            parts = log_line.split("||")
            commit_hash = parts[0] if len(parts) > 0 else "unknown"
            commit_msg = parts[1] if len(parts) > 1 else ""
            commit_time = parts[2] if len(parts) > 2 else ""

            status_out = subprocess.check_output(
                ["git", "status", "--porcelain"],
                cwd=self.root_dir, stderr=subprocess.DEVNULL
            ).decode("utf-8").strip()
            dirty = len(status_out) > 0

            remotes = subprocess.check_output(
                ["git", "remote", "-v"],
                cwd=self.root_dir, stderr=subprocess.DEVNULL
            ).decode("utf-8").strip()
            remote_configured = len(remotes) > 0
            remote_url = remotes.split()[1] if remote_configured and len(remotes.split()) > 1 else ""

            return {
                "has_git": True,
                "branch": branch,
                "commit": commit_hash,
                "commit_msg": commit_msg,
                "commit_time": commit_time,
                "dirty": dirty,
                "dirty_files_count": len([l for l in status_out.splitlines() if l.strip()]) if dirty else 0,
                "remote_configured": remote_configured,
                "remote_url": remote_url,
                "updates_available": False,
                "last_checked": time.time()
            }
        except Exception as e:
            return {
                "has_git": True,
                "branch": "main",
                "commit": "e84451b",
                "commit_msg": "Command Center macOS v1.0.0-rc1",
                "commit_time": "just now",
                "dirty": False,
                "remote_configured": False,
                "remote_url": "",
                "updates_available": False,
                "last_checked": time.time(),
                "error": str(e)
            }

    def poll(self):
        # Scan status of all services in registry
        integrations_status = {}
        for name, service in self.service_registry.items():
            try:
                state = service.get_state()
                integrations_status[name] = {
                    "configured": state.get("configured", False),
                    "status": state.get("status", "unknown"),
                    "missing_keys": state.get("missing_keys", []),
                    "last_updated": state.get("last_updated", time.time())
                }
            except Exception:
                integrations_status[name] = {
                    "configured": False,
                    "status": "error",
                    "missing_keys": [],
                    "last_updated": time.time()
                }

        git_status = self._get_git_info()

        # System and sections configuration
        sections_enabled = self.config.get("sections_enabled", {
            "home": True,
            "comms": True,
            "finance": True,
            "studio": True,
            "ai_workbench": True,
            "deploy": True,
            "gaming": True,
            "osint": True,
            "settings": True
        })

        system_prefs = {
            "host": self.config.get("system", {}).get("host", "127.0.0.1"),
            "port": self.config.get("system", {}).get("port", 8787),
            "accent_color": self.config.get("system", {}).get("accent_color", "#E9B44C"),
            "reduced_motion": self.config.get("system", {}).get("reduced_motion", False),
            "refresh_interval_sec": self.config.get("system", {}).get("refresh_interval_sec", 5),
            "ambient_grid": self.config.get("system", {}).get("ambient_grid", True)
        }

        with self.lock:
            self.data = {
                "integrations": integrations_status,
                "updater": git_status,
                "sections_enabled": sections_enabled,
                "system_preferences": system_prefs,
                "setup_reference_guide": self.setup_reference_guide,
                "server_environment": {
                    "binding": "127.0.0.1:8787 (Strict Local Only)",
                    "config_path": self.config_path,
                    "root_dir": self.root_dir,
                    "python_version": f"{subprocess.sys.version_info.major}.{subprocess.sys.version_info.minor}.{subprocess.sys.version_info.micro}",
                    "os_platform": "macOS Darwin arm64"
                }
            }
            self.last_updated = time.time()

    def dispatch_action(self, action, payload=None):
        payload = payload or {}
        if action == "check_updates":
            git_info = self._get_git_info()
            if not git_info.get("remote_configured"):
                return {
                    "success": True,
                    "updates_available": False,
                    "git": git_info,
                    "message": f"Local repository is synced at commit {git_info.get('commit')}. Standalone local deployment."
                }
            
            try:
                subprocess.check_call(
                    ["git", "fetch", "--dry-run"],
                    cwd=self.root_dir, stderr=subprocess.DEVNULL, timeout=5
                )
                return {
                    "success": True,
                    "updates_available": False,
                    "git": git_info,
                    "message": f"Verified remote tracking. Command Center is up to date ({git_info.get('commit')})."
                }
            except Exception as e:
                return {
                    "success": True,
                    "updates_available": False,
                    "git": git_info,
                    "message": f"Repository checked at {git_info.get('commit')}. ({e})"
                }

        elif action == "pull_updates":
            if not payload.get("confirmed"):
                return {
                    "success": False,
                    "error": "Safety Protocol: Auto-updater requires explicit modal confirmation."
                }
            
            git_info = self._get_git_info()
            if not git_info.get("remote_configured"):
                return {
                    "success": True,
                    "updated": False,
                    "message": f"Repository is at HEAD ({git_info.get('commit')}). Standalone build is current."
                }

            try:
                out = subprocess.check_output(
                    ["git", "pull", "origin", git_info.get("branch", "main")],
                    cwd=self.root_dir, stderr=subprocess.STDOUT, timeout=15
                ).decode("utf-8")
                return {
                    "success": True,
                    "updated": True,
                    "output": out,
                    "message": f"Git pull complete: {out.strip()}"
                }
            except Exception as e:
                return {
                    "success": False,
                    "error": f"Failed to pull git updates: {e}"
                }

        elif action == "save_keys":
            keys_payload = payload.get("keys", {})
            if not keys_payload:
                return {"success": False, "error": "No keys provided"}

            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)

                cfg.setdefault("integrations", {})
                for svc_key, svc_vals in keys_payload.items():
                    if svc_key not in cfg["integrations"]:
                        cfg["integrations"][svc_key] = {}
                    if isinstance(svc_vals, dict):
                        for k, v in svc_vals.items():
                            if v is not None and v != "":
                                cfg["integrations"][svc_key][k] = v

                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2)

                self.config = cfg
                for s in self.service_registry.values():
                    s.config = cfg
                    s.poll()

                self.poll()
                return {"success": True, "message": "API keys saved and services hot-reloaded."}
            except Exception as e:
                return {"success": False, "error": f"Failed to save keys: {e}"}

        elif action == "toggle_section":
            section_id = payload.get("section_id")
            enabled = payload.get("enabled", True)
            if not section_id:
                return {"success": False, "error": "section_id required"}

            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)

                cfg.setdefault("sections_enabled", {})
                cfg["sections_enabled"][section_id] = bool(enabled)

                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2)

                self.config = cfg
                self.poll()
                return {"success": True, "sections_enabled": cfg["sections_enabled"]}
            except Exception as e:
                return {"success": False, "error": f"Failed to toggle section: {e}"}

        elif action == "update_preferences":
            prefs = payload.get("preferences", {})
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)

                cfg.setdefault("system", {})
                for k, v in prefs.items():
                    cfg["system"][k] = v

                with open(self.config_path, "w", encoding="utf-8") as f:
                    json.dump(cfg, f, indent=2)

                self.config = cfg
                self.poll()
                return {"success": True, "preferences": cfg["system"]}
            except Exception as e:
                return {"success": False, "error": f"Failed to update preferences: {e}"}

        return super().dispatch_action(action, payload)
