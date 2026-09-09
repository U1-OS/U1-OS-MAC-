"""Start this installation without stopping another app or requiring accounts."""
import json
import fcntl
import hashlib
import os
from contextlib import contextmanager
from pathlib import Path
import subprocess
import stat
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent
PORT = 8788
URL = "http://127.0.0.1:%d" % PORT


def running_here():
    try:
        with urllib.request.urlopen(URL + "/healthz", timeout=1) as response:
            value = json.load(response)
            identity = hashlib.sha256(str(ROOT.resolve()).encode("utf-8")).hexdigest()
            return (value.get("service") == "u1-os" and type(value.get("protocol")) is int
                    and value["protocol"] == 1 and type(value.get("locked")) is bool
                    and value.get("installation_id") == identity)
    except Exception:
        return False


@contextmanager
def startup_lock():
    """Kernel-owned lock, automatically released on exit; never unlink its inode.

    The old ownerless .u1-os-launch.lock directory is neither trusted nor deleted.
    All updated launchers coordinate on this separate persistent regular file.
    """
    path = ROOT / ".u1-os-launch.flock"
    descriptor = os.open(path, os.O_RDWR | os.O_CREAT | getattr(os, "O_NOFOLLOW", 0), 0o600)
    try:
        info = os.fstat(descriptor)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1 or info.st_uid != os.getuid():
            raise SystemExit("U1 OS startup lock must be an owner-controlled regular file.")
        os.fchmod(descriptor, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("U1 OS startup is already in progress. Try again shortly.")
        yield
    finally:
        os.close(descriptor)


def main():
    runtime = ROOT / ".runtime" / "bin" / "python3"
    if not runtime.exists():
        raise SystemExit("Python runtime is missing. See INSTALLATION.md.")
    if not running_here():
        with startup_lock():
            if running_here():
                print("U1 OS is running at " + URL)
                if "--no-browser" not in sys.argv:
                    subprocess.run(["/usr/bin/open", URL + "/"], check=True)
                return
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
    print("U1 OS is running at " + URL)
    if "--no-browser" not in sys.argv:
        subprocess.run(["/usr/bin/open", URL + "/"], check=True)


if __name__ == "__main__":
    main()
