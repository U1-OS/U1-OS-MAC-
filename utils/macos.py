#!/usr/bin/env python3
"""
Command Center // macOS Native Integrations
Handles desktop notifications via AppleScript and LaunchAgent management for auto-start.
"""

import os
import sys
import subprocess
import shutil
import logging

logger = logging.getLogger("CommandCenter.macOS")

AGENT_LABEL = "com.commandcenter.feeder"

def notify(title: str, message: str, subtitle: str = "", sound: str = "Hero") -> bool:
    """
    Dispatches a native macOS desktop notification via osascript.
    Falls back gracefully on headless or non-macOS environments.
    """
    if sys.platform != "darwin":
        return False

    try:
        # Escape quotes for AppleScript string literal
        clean_title = title.replace('"', '\\"').replace("'", "\\'")
        clean_msg = message.replace('"', '\\"').replace("'", "\\'")
        clean_sub = subtitle.replace('"', '\\"').replace("'", "\\'") if subtitle else ""

        script_parts = [f'display notification "{clean_msg}" with title "{clean_title}"']
        if clean_sub:
            script_parts.append(f'subtitle "{clean_sub}"')
        if sound:
            script_parts.append(f'sound name "{sound}"')

        full_script = " ".join(script_parts)
        subprocess.run(
            ["osascript", "-e", full_script],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
            check=False
        )
        return True
    except Exception as e:
        logger.warning(f"Failed to dispatch macOS notification: {e}")
        return False

def get_agent_plist_path() -> str:
    """Returns absolute path to the LaunchAgent plist file."""
    launch_agents_dir = os.path.expanduser("~/Library/LaunchAgents")
    os.makedirs(launch_agents_dir, exist_ok=True)
    return os.path.join(launch_agents_dir, f"{AGENT_LABEL}.plist")

def is_agent_installed() -> bool:
    """Checks whether the LaunchAgent plist file is installed."""
    plist_path = get_agent_plist_path()
    return os.path.exists(plist_path)

def is_agent_running() -> bool:
    """Checks if launchctl reports the agent as active."""
    try:
        res = subprocess.run(
            ["launchctl", "list"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=3
        )
        return AGENT_LABEL in res.stdout
    except Exception:
        return False

def generate_launchagent_plist(repo_path: str = None, python_path: str = None) -> str:
    """
    Generates a standard macOS LaunchAgent property list XML string.
    """
    if not repo_path:
        repo_path = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if not python_path:
        python_path = sys.executable or shutil.which("python3") or "/usr/bin/python3"

    server_script = os.path.join(repo_path, "server.py")
    log_dir = os.path.join(repo_path, "logs")
    os.makedirs(log_dir, exist_ok=True)
    out_log = os.path.join(log_dir, "launchagent.log")
    err_log = os.path.join(log_dir, "launchagent.err.log")

    plist_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>{AGENT_LABEL}</string>
    <key>ProgramArguments</key>
    <array>
        <string>{python_path}</string>
        <string>{server_script}</string>
    </array>
    <key>WorkingDirectory</key>
    <string>{repo_path}</string>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <dict>
        <key>SuccessfulExit</key>
        <false/>
    </dict>
    <key>StandardOutPath</key>
    <string>{out_log}</string>
    <key>StandardErrorPath</key>
    <string>{err_log}</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>PATH</key>
        <string>/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:/opt/homebrew/bin</string>
    </dict>
</dict>
</plist>
"""
    return plist_content

def install_agent(repo_path: str = None) -> dict:
    """
    Installs and registers the LaunchAgent plist file with launchctl.
    """
    if sys.platform != "darwin":
        return {"success": False, "error": "LaunchAgent is only supported on macOS"}

    plist_path = get_agent_plist_path()
    content = generate_launchagent_plist(repo_path=repo_path)

    try:
        with open(plist_path, "w", encoding="utf-8") as f:
            f.write(content)

        # Unload existing if loaded
        subprocess.run(["launchctl", "unload", plist_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
        # Load fresh agent
        res = subprocess.run(["launchctl", "load", plist_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)

        if res.returncode == 0:
            return {
                "success": True,
                "message": f"LaunchAgent registered and loaded successfully ({AGENT_LABEL})",
                "plist_path": plist_path
            }
        else:
            return {
                "success": True,
                "message": f"LaunchAgent written to {plist_path} (load warning: {res.stderr.strip()})",
                "plist_path": plist_path
            }
    except Exception as e:
        return {"success": False, "error": str(e)}

def uninstall_agent() -> dict:
    """
    Unloads and removes the LaunchAgent plist file.
    """
    plist_path = get_agent_plist_path()
    try:
        if os.path.exists(plist_path):
            subprocess.run(["launchctl", "unload", plist_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
            os.remove(plist_path)
            return {"success": True, "message": f"LaunchAgent {AGENT_LABEL} removed cleanly"}
        else:
            return {"success": True, "message": "LaunchAgent was not installed"}
    except Exception as e:
        return {"success": False, "error": str(e)}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="macOS Native Integrations for Command Center")
    parser.add_argument("action", choices=["notify", "status", "install", "uninstall"])
    parser.add_argument("--title", default="Command Center", help="Notification title")
    parser.add_argument("--message", default="macOS System Bridge Operational", help="Notification message")
    parser.add_argument("--subtitle", default="", help="Notification subtitle")
    args = parser.parse_args()

    if args.action == "notify":
        ok = notify(args.title, args.message, args.subtitle)
        print(f"Notification sent: {ok}")
    elif args.action == "status":
        print(f"Agent Plist Exists: {is_agent_installed()}")
        print(f"Agent Running in launchctl: {is_agent_running()}")
    elif args.action == "install":
        res = install_agent()
        print(res)
    elif args.action == "uninstall":
        res = uninstall_agent()
        print(res)
