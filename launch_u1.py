"""Start this installation without stopping another app or requiring accounts."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
PORT = 8788
URL = "http://127.0.0.1:%d" % PORT


def running_here():
    try:
        with urllib.request.urlopen(URL + "/api/integrations", timeout=1) as response:
            return json.load(response).get("installation_root") == str(ROOT)
    except Exception:
        return False


def main():
    runtime = ROOT / ".runtime" / "bin" / "python3"
    if not runtime.exists():
        raise SystemExit("Python runtime is missing. See INSTALLATION.md.")
    lock = ROOT / ".u1-os-launch.lock"
    if not running_here():
        try:
            lock.mkdir()
        except FileExistsError:
            raise SystemExit("U1 OS startup is already in progress. Try again shortly.")
        try:
            import socket
            with socket.socket() as probe:
                if probe.connect_ex(("127.0.0.1", PORT)) == 0:
                    raise SystemExit("Port 8788 is occupied by another app. No process was stopped.")
            env = dict(os.environ)
            env["PATH"] = str(runtime.parent) + ":/usr/local/bin:/opt/homebrew/bin:" + env.get("PATH", "")
            with (ROOT / "command-center.log").open("ab") as log:
                process = subprocess.Popen([str(runtime), "-u", str(ROOT / "server.py")],
                    cwd=str(ROOT), env=env, stdin=subprocess.DEVNULL, stdout=log,
                    stderr=subprocess.STDOUT, start_new_session=True)
            (ROOT / ".u1-os.pid").write_text(str(process.pid))
            for _ in range(40):
                if running_here():
                    break
                if process.poll() is not None:
                    raise SystemExit("U1 OS could not start. See command-center.log.")
                time.sleep(0.5)
            else:
                raise SystemExit("U1 OS is still starting. See command-center.log, then reopen the launcher.")
        finally:
            lock.rmdir()
    print("U1 OS is running at " + URL)
    print("Integrations: " + URL + "/integrations.html")
    if "--no-browser" not in sys.argv:
        subprocess.run(["/usr/bin/open", URL + "/integrations.html"], check=True)


if __name__ == "__main__":
    main()
