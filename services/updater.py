"""U1 OS // Updater and maintenance service.

Owns everything about keeping the workspace current: what version is
running, whether the checkout is behind its remote, applying an update,
restoring optional dependencies, rebuilding the macOS app, restarting the
server, and surfacing the findings of the always-on improvement agent.

Design rules, matching the rest of the project:
  * Nothing that changes the installation runs without explicit
    confirmation from the caller.
  * No outbound requests beyond git talking to its own remote.
  * Every failure returns a structured result — never a raised exception
    across the HTTP boundary.
"""

import json
import os
import subprocess
import sys
import threading
import time

from services.base import BaseService

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_FILE = os.path.join(ROOT, "VERSION")
DEFAULT_VERSION = "2.0.0"
GIT_TIMEOUT = 25


def read_version():
    try:
        with open(VERSION_FILE, encoding="utf-8") as handle:
            value = handle.read().strip()
            return value or DEFAULT_VERSION
    except OSError:
        return DEFAULT_VERSION


def _git(*args, timeout=GIT_TIMEOUT):
    """Run a git command inside the checkout. Returns (ok, output)."""
    try:
        out = subprocess.run(
            ["git", *args],
            cwd=ROOT, capture_output=True, text=True, timeout=timeout
        )
        text = (out.stdout or "") + (out.stderr or "")
        return out.returncode == 0, text.strip()
    except FileNotFoundError:
        return False, "git is not installed on this machine"
    except subprocess.TimeoutExpired:
        return False, f"git {' '.join(args)} timed out after {timeout}s"
    except Exception as exc:                                  # pragma: no cover
        return False, f"{type(exc).__name__}: {exc}"


class UpdaterService(BaseService):
    def __init__(self, config, feeder=None):
        super().__init__("updater", config)
        self.configured = True
        self.status = "active"
        self.feeder = feeder
        self.root_dir = ROOT
        self.started_at = time.time()
        self.last_check = None
        self.last_result = None
        self.agent = None          # set by the server once wired

    # ------------------------------------------------------------------
    # Inspection
    # ------------------------------------------------------------------
    def git_snapshot(self):
        ok_repo, _ = _git("rev-parse", "--is-inside-work-tree")
        if not ok_repo:
            return {
                "is_repo": False,
                "message": "This installation is not a git checkout, so updates must be applied manually."
            }
        # A freshly initialised repo has an unborn HEAD; asking git for a
        # commit there returns a multi-line fatal error rather than a value.
        has_commits, _ = _git("rev-parse", "--verify", "--quiet", "HEAD")
        # --show-current is the only spelling that stays quiet on an
        # unborn HEAD; rev-parse emits a fatal error there.
        ok_branch, branch = _git("branch", "--show-current")
        if not ok_branch or not branch:
            branch = "main"
        if has_commits:
            _, commit = _git("rev-parse", "--short", "HEAD")
            _, subject = _git("log", "-1", "--pretty=%s")
            _, when = _git("log", "-1", "--pretty=%cr")
        else:
            commit, subject, when = None, "No commits yet", None
        ok_remote, remote = _git("remote", "get-url", "origin")
        _, dirty = _git("status", "--porcelain")
        ahead = behind = 0
        tracked = False
        ok_count, counts = _git("rev-list", "--left-right", "--count", f"origin/{branch}...HEAD")
        if ok_count and counts:
            parts = counts.split()
            if len(parts) == 2 and parts[0].isdigit() and parts[1].isdigit():
                behind, ahead = int(parts[0]), int(parts[1])
                tracked = True
        return {
            "is_repo": True,
            "has_commits": bool(has_commits),
            "branch": branch,
            "commit": commit,
            "subject": subject,
            "committed": when,
            "remote": remote if ok_remote else None,
            "remote_configured": ok_remote,
            "uncommitted_files": len([l for l in dirty.splitlines() if l.strip()]),
            "clean": not dirty.strip(),
            "tracking_remote": tracked,
            "commits_behind": behind,
            "commits_ahead": ahead,
            "update_available": behind > 0
        }

    def runtime_snapshot(self):
        optional = {}
        for module, purpose in (
            ("psutil", "CPU, memory and network telemetry"),
            ("reportlab", "PDF generation"),
            ("pypdf", "PDF text extraction"),
        ):
            try:
                __import__(module)
                optional[module] = {"installed": True, "purpose": purpose}
            except Exception:
                optional[module] = {"installed": False, "purpose": purpose}
        app_path = os.path.join(ROOT, "dist", "U1 OS.app")
        return {
            "version": read_version(),
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "python_supported": sys.version_info >= (3, 10),
            "platform": sys.platform,
            "root": ROOT,
            "uptime_seconds": round(time.time() - self.started_at, 1),
            "port": self.config.get("system", {}).get("port", 8788),
            "optional_dependencies": optional,
            "desktop_app_built": os.path.isdir(app_path),
            "desktop_app_path": app_path if os.path.isdir(app_path) else None,
        }

    def changelog(self, limit=15):
        has_commits, _ = _git("rev-parse", "--verify", "--quiet", "HEAD")
        if not has_commits:
            return []
        ok, out = _git("log", f"-{int(limit)}", "--pretty=%h\x1f%cr\x1f%s")
        if not ok:
            return []
        entries = []
        for line in out.splitlines():
            parts = line.split("\x1f")
            if len(parts) == 3:
                entries.append({"commit": parts[0], "when": parts[1], "subject": parts[2]})
        return entries

    def agent_snapshot(self):
        if not self.agent:
            return {"success": False, "available": False,
                    "message": "The improvement agent is not running in this process."}
        try:
            snap = self.agent.snapshot()
            snap["available"] = True
            return snap
        except Exception as exc:
            return {"success": False, "available": False, "error": f"{type(exc).__name__}: {exc}"}

    def poll(self):
        with self.lock:
            self.data = {
                "runtime": self.runtime_snapshot(),
                "git": self.git_snapshot(),
                "changelog": self.changelog(8),
                "agent": self.agent_snapshot(),
                "last_check": self.last_check,
                "last_result": self.last_result,
            }
            self.last_updated = time.time()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def dispatch_action(self, action, payload=None):
        payload = payload or {}

        if action == "get_status":
            self.poll()
            with self.lock:
                return {"success": True, **self.data}

        if action == "check_for_updates":
            git = self.git_snapshot()
            if not git.get("is_repo"):
                return {"success": True, "update_available": False, "git": git,
                        "message": git.get("message")}
            if not git.get("remote_configured"):
                return {"success": True, "update_available": False, "git": git,
                        "message": "No git remote is configured, so there is nothing to check against."}
            ok, out = _git("fetch", "--quiet", "origin")
            self.last_check = time.time()
            if not ok:
                return {"success": False, "error": "fetch_failed",
                        "message": f"Could not reach the remote: {out}", "git": git}
            git = self.git_snapshot()
            behind = git.get("commits_behind", 0)
            self.last_result = "update_available" if behind else "current"
            self.add_event("update_check",
                           f"{behind} update(s) available" if behind else "Workspace is up to date")
            return {
                "success": True,
                "update_available": behind > 0,
                "commits_behind": behind,
                "git": git,
                "message": (f"{behind} update(s) available on {git.get('branch')}."
                            if behind else "This workspace is already up to date.")
            }

        if action == "apply_update":
            if not payload.get("confirmed"):
                return {"success": False, "error": "confirmation_required",
                        "message": "Applying an update changes the installed files. Confirm to continue."}
            git = self.git_snapshot()
            if not git.get("is_repo"):
                return {"success": False, "error": "not_a_repo", "message": git.get("message")}
            if not git.get("clean"):
                return {"success": False, "error": "uncommitted_changes",
                        "message": (f"{git['uncommitted_files']} file(s) have uncommitted changes. "
                                    "Commit or stash them before updating so nothing is lost.")}
            ok, out = _git("pull", "--ff-only", "origin", git.get("branch", "main"), timeout=90)
            after = self.git_snapshot()
            self.last_result = "updated" if ok else "update_failed"
            if not ok:
                return {"success": False, "error": "pull_failed", "output": out,
                        "message": f"Update could not be applied: {out}"}
            self.add_event("update_applied", f"Updated to {after.get('commit')}")
            return {
                "success": True,
                "updated": git.get("commit") != after.get("commit"),
                "from_commit": git.get("commit"),
                "to_commit": after.get("commit"),
                "output": out,
                "git": after,
                "restart_required": True,
                "message": ("Update applied. Restart the workspace to load the new code."
                            if git.get("commit") != after.get("commit")
                            else "Already at the newest commit.")
            }

        if action == "install_dependencies":
            if not payload.get("confirmed"):
                return {"success": False, "error": "confirmation_required",
                        "message": "This installs Python packages into the runtime. Confirm to continue."}
            req = os.path.join(ROOT, "requirements-prism.txt")
            if not os.path.exists(req):
                return {"success": False, "error": "no_requirements",
                        "message": "requirements-prism.txt is not present in this installation."}
            try:
                out = subprocess.run(
                    [sys.executable, "-m", "pip", "install", "-r", req],
                    cwd=ROOT, capture_output=True, text=True, timeout=300
                )
                ok = out.returncode == 0
                self.add_event("dependencies", "Optional dependencies installed" if ok else "Dependency install failed")
                return {
                    "success": ok,
                    "output": ((out.stdout or "") + (out.stderr or ""))[-4000:],
                    "message": ("Optional dependencies are installed. Restart to pick them up."
                                if ok else "pip could not complete the install — see the output.")
                }
            except subprocess.TimeoutExpired:
                return {"success": False, "error": "timeout",
                        "message": "The install did not finish within 5 minutes."}
            except Exception as exc:
                return {"success": False, "error": type(exc).__name__, "message": str(exc)}

        if action == "rebuild_desktop_app":
            if not payload.get("confirmed"):
                return {"success": False, "error": "confirmation_required",
                        "message": "This rebuilds U1 OS.app from source. Confirm to continue."}
            script = os.path.join(ROOT, "macos", "build-desktop.sh")
            if not os.path.exists(script):
                return {"success": False, "error": "no_build_script",
                        "message": "macos/build-desktop.sh is not present in this installation."}
            if sys.platform != "darwin":
                return {"success": False, "error": "wrong_platform",
                        "message": "The desktop app can only be built on macOS."}
            try:
                out = subprocess.run(["bash", script], cwd=ROOT,
                                     capture_output=True, text=True, timeout=600)
                ok = out.returncode == 0
                self.add_event("app_build", "Desktop app rebuilt" if ok else "Desktop app build failed")
                return {
                    "success": ok,
                    "output": ((out.stdout or "") + (out.stderr or ""))[-4000:],
                    "app_path": os.path.join(ROOT, "dist", "U1 OS.app"),
                    "message": "U1 OS.app rebuilt." if ok else "The build did not complete — see the output."
                }
            except subprocess.TimeoutExpired:
                return {"success": False, "error": "timeout",
                        "message": "The build did not finish within 10 minutes."}
            except Exception as exc:
                return {"success": False, "error": type(exc).__name__, "message": str(exc)}

        if action == "restart_server":
            if not payload.get("confirmed"):
                return {"success": False, "error": "confirmation_required",
                        "message": "Restarting drops every open connection. Confirm to continue."}

            def restart():
                time.sleep(1.0)
                os.execv(sys.executable, [sys.executable, os.path.join(ROOT, "server.py")])

            threading.Thread(target=restart, name="u1-restart", daemon=True).start()
            self.add_event("restart", "Workspace restart requested")
            return {"success": True, "restarting": True,
                    "message": "Restarting now — this page will reconnect in a few seconds."}

        if action == "get_changelog":
            return {"success": True, "entries": self.changelog(int(payload.get("limit", 20)))}

        if action == "agent_status":
            return self.agent_snapshot()

        if action == "agent_configure":
            if not self.agent:
                return {"success": False, "message": "The improvement agent is not running in this process."}
            try:
                return self.agent.configure({"action": payload.get("mode")})
            except ValueError as exc:
                return {"success": False, "error": "invalid_mode", "message": str(exc)}
            except Exception as exc:
                return {"success": False, "error": type(exc).__name__, "message": str(exc)}

        return {"success": False, "error": f"Action '{action}' is not available on the updater."}
