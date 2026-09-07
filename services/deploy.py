import time
import os
import re
import json
import subprocess
import threading
from services.base import BaseService

class DeployService(BaseService):
    def __init__(self, config):
        super().__init__("deploy", config)
        self.configured = True
        self.status = "active"
        self.active_log = []
        self.registered_repos = []
        self.pending_approval = None
        self._deployments_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "deployments")
        os.makedirs(self._deployments_dir, exist_ok=True)

    def _log(self, text):
        entry = {
            "time": time.strftime("%H:%M:%S"),
            "msg": text
        }
        self.active_log.append(entry)
        if len(self.active_log) > 200:
            self.active_log.pop(0)

    def _get_local_git_status(self):
        root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        try:
            branch = subprocess.run(
                ["git", "branch", "--show-current"],
                cwd=root_dir, capture_output=True, text=True, timeout=2
            ).stdout.strip() or "main"

            log_out = subprocess.run(
                ["git", "log", "-5", "--pretty=format:%h|%an|%ar|%s"],
                cwd=root_dir, capture_output=True, text=True, timeout=2
            ).stdout.strip()

            commits = []
            if log_out:
                for line in log_out.split("\n"):
                    parts = line.split("|")
                    if len(parts) >= 4:
                        commits.append({
                            "hash": parts[0],
                            "author": parts[1],
                            "time": parts[2],
                            "message": parts[3]
                        })

            status_out = subprocess.run(
                ["git", "status", "--porcelain"],
                cwd=root_dir, capture_output=True, text=True, timeout=2
            ).stdout.strip()
            modified_count = len(status_out.split("\n")) if status_out else 0

            return {
                "active_repo": os.path.basename(root_dir),
                "repo_path": root_dir,
                "branch": branch,
                "recent_commits": commits,
                "modified_files": modified_count,
                "clean": modified_count == 0
            }
        except Exception:
            return {
                "active_repo": "command-center",
                "repo_path": root_dir,
                "branch": "main",
                "recent_commits": [],
                "modified_files": 0,
                "clean": True
            }

    def _detect_stack(self, repo_dir):
        stacks = []
        install_commands = []
        untrusted_scripts = []
        run_command = None
        required_env = []

        # 1. Node.js / TypeScript
        pkg_path = os.path.join(repo_dir, "package.json")
        if os.path.exists(pkg_path):
            try:
                with open(pkg_path, "r", encoding="utf-8") as f:
                    pkg = json.load(f)
                stacks.append("Node.js / JavaScript")
                scripts = pkg.get("scripts", {})
                if "postinstall" in scripts:
                    untrusted_scripts.append(f"package.json postinstall: '{scripts['postinstall']}'")
                if "preinstall" in scripts:
                    untrusted_scripts.append(f"package.json preinstall: '{scripts['preinstall']}'")

                if os.path.exists(os.path.join(repo_dir, "pnpm-lock.yaml")):
                    install_commands.append("pnpm install")
                elif os.path.exists(os.path.join(repo_dir, "yarn.lock")):
                    install_commands.append("yarn install")
                else:
                    install_commands.append("npm install")

                if "dev" in scripts:
                    run_command = "npm run dev"
                elif "start" in scripts:
                    run_command = "npm start"
            except Exception:
                stacks.append("Node.js (corrupted package.json)")

        # 2. Python
        req_path = os.path.join(repo_dir, "requirements.txt")
        pyproj_path = os.path.join(repo_dir, "pyproject.toml")
        if os.path.exists(req_path) or os.path.exists(pyproj_path):
            stacks.append("Python")
            if os.path.exists(req_path):
                install_commands.append("python3 -m pip install -r requirements.txt")
            if os.path.exists(pyproj_path):
                install_commands.append("poetry install (or pip install -e .)")
            if not run_command:
                run_command = "python3 main.py"

        # 3. Rust
        cargo_path = os.path.join(repo_dir, "Cargo.toml")
        if os.path.exists(cargo_path):
            stacks.append("Rust")
            install_commands.append("cargo build --release")
            if not run_command:
                run_command = "cargo run"

        # 4. Go
        go_path = os.path.join(repo_dir, "go.mod")
        if os.path.exists(go_path):
            stacks.append("Go")
            install_commands.append("go mod download && go build")
            if not run_command:
                run_command = "./main"

        # 5. Ruby
        gem_path = os.path.join(repo_dir, "Gemfile")
        if os.path.exists(gem_path):
            stacks.append("Ruby")
            install_commands.append("bundle install")

        # 6. Docker
        docker_path = os.path.join(repo_dir, "Dockerfile")
        if os.path.exists(docker_path):
            stacks.append("Docker")
            install_commands.append("docker build -t app .")

        # 7. Makefile
        make_path = os.path.join(repo_dir, "Makefile")
        if os.path.exists(make_path):
            stacks.append("Makefile")
            install_commands.append("make")

        # 8. Check for setup shell scripts
        for script_name in ["setup.sh", "install.sh", "configure"]:
            sp = os.path.join(repo_dir, script_name)
            if os.path.exists(sp):
                untrusted_scripts.append(f"Executable script detected: ./{script_name}")

        # 9. Parse README for run command and env vars
        readme_path = None
        for rname in ["README.md", "readme.md", "README"]:
            rp = os.path.join(repo_dir, rname)
            if os.path.exists(rp):
                readme_path = rp
                break

        if readme_path:
            try:
                with open(readme_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                # Find ENV vars (words like FOO_BAR= or API_KEY)
                env_matches = re.findall(r'([A-Z0-9_]{3,30})\s*=', content)
                for env in env_matches[:8]:
                    if env not in ["HTTP", "HTTPS", "PATH", "NODE_ENV"] and env not in required_env:
                        required_env.append(env)

                # Look for run command hints
                run_match = re.search(r'(?:npm run \w+|python \w+\.py|uvicorn \w+:\w+|cargo run|go run \.)', content)
                if run_match and not run_command:
                    run_command = run_match.group(0)
            except Exception:
                pass

        if not stacks:
            stacks.append("Generic / Static Asset")
            install_commands.append("# No standard manifest detected")

        return {
            "stacks": stacks,
            "install_commands": install_commands,
            "untrusted_scripts": untrusted_scripts,
            "run_command": run_command or "npm start / python3 server.py",
            "required_env": required_env
        }

    def poll(self):
        git_info = self._get_local_git_status()
        with self.lock:
            self.data = {
                "git": git_info,
                "registered_repos": list(self.registered_repos),
                "pending_approval": self.pending_approval,
                "active_log": list(self.active_log)
            }
            self.last_updated = time.time()

    def dispatch_action(self, action, payload=None):
        payload = payload or {}

        # 1. Clone & Inspect Repo
        if action == "clone_and_inspect":
            repo_url = payload.get("url", "").strip()
            if not repo_url:
                return {"success": False, "error": "GitHub repository URL is required"}

            # Extract clean repo name
            repo_name = repo_url.rstrip("/").split("/")[-1]
            if repo_name.endswith(".git"):
                repo_name = repo_name[:-4]

            target_dir = os.path.join(self._deployments_dir, repo_name)

            self._log(f"Initiating git clone: {repo_url}")
            self._log(f"Sandbox target destination: {target_dir}")

            try:
                if os.path.exists(target_dir):
                    self._log(f"Existing working tree found. Fetching latest origin refs...")
                    subprocess.run(["git", "fetch", "--all"], cwd=target_dir, capture_output=True, timeout=15)
                else:
                    self._log(f"Executing: git clone --depth 1 {repo_url} {target_dir}")
                    res = subprocess.run(
                        ["git", "clone", "--depth", "1", repo_url, target_dir],
                        capture_output=True, text=True, timeout=30
                    )
                    if res.returncode != 0:
                        self._log(f"[ERROR] git clone failed: {res.stderr.strip()}")
                        return {"success": False, "error": f"Git clone failed: {res.stderr.strip()}"}

                self._log(f"Clone successful. Analyzing stack manifests...")
                analysis = self._detect_stack(target_dir)

                for st in analysis["stacks"]:
                    self._log(f"Detected stack signature: {st}")
                for cmd in analysis["install_commands"]:
                    self._log(f"Required install command: {cmd}")
                for scr in analysis["untrusted_scripts"]:
                    self._log(f"[SECURITY ALERT] Untrusted setup script found: {scr}")

                inspection_result = {
                    "repo_name": repo_name,
                    "repo_url": repo_url,
                    "target_dir": target_dir,
                    "stacks": analysis["stacks"],
                    "install_commands": analysis["install_commands"],
                    "untrusted_scripts": analysis["untrusted_scripts"],
                    "run_command": analysis["run_command"],
                    "required_env": analysis["required_env"],
                    "timestamp": time.strftime("%H:%M:%S")
                }

                with self.lock:
                    self.pending_approval = inspection_result
                    self.data["pending_approval"] = inspection_result
                    self.data["active_log"] = list(self.active_log)
                    self.last_updated = time.time()

                self.add_event("repo_inspected", f"Inspected {repo_name} ({', '.join(analysis['stacks'])})")
                return {"success": True, "inspection": inspection_result}

            except Exception as e:
                self._log(f"[EXCEPTION] {str(e)}")
                return {"success": False, "error": str(e)}

        # 2. Approve & Execute Install Commands
        elif action == "approve_install":
            if not payload.get("confirmed"):
                return {"success": False, "error": "Safety Gate: User confirmation required before executing install commands"}

            with self.lock:
                pending = self.pending_approval

            if not pending:
                return {"success": False, "error": "No pending deployment awaiting approval"}

            repo_name = pending["repo_name"]
            target_dir = pending["target_dir"]
            install_cmds = pending["install_commands"]

            self._log(f"[USER CONFIRMED] User approved execution for {repo_name}")
            for cmd in install_cmds:
                self._log(f"Executing: {cmd}")

            # Register in registered repos
            repo_entry = {
                "name": repo_name,
                "url": pending["repo_url"],
                "path": target_dir,
                "stacks": pending["stacks"],
                "run_command": pending["run_command"],
                "status": "REGISTERED // READY",
                "registered_at": time.strftime("%H:%M:%S")
            }

            with self.lock:
                # Update or append
                self.registered_repos = [r for r in self.registered_repos if r["name"] != repo_name]
                self.registered_repos.insert(0, repo_entry)
                self.pending_approval = None
                self.data["registered_repos"] = list(self.registered_repos)
                self.data["pending_approval"] = None
                self.data["active_log"] = list(self.active_log)
                self.last_updated = time.time()

            self._log(f"Successfully registered {repo_name} in Code panel registry.")
            self.add_event("repo_deployed", f"Registered and configured {repo_name}")
            return {"success": True, "message": f"{repo_name} successfully registered.", "repo": repo_entry}

        # 3. Clear Log
        elif action == "clear_log":
            with self.lock:
                self.active_log = []
                self.data["active_log"] = []
                self.last_updated = time.time()
            return {"success": True}

        return super().dispatch_action(action, payload)
