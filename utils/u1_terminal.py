"""Local PTY sessions. All access is POST-only behind server CSRF/origin checks.

Each session additionally needs an unguessable capability. No shell command is
executed by reading a page. The user must acknowledge and start a session.
"""
import atexit
import base64
import fcntl
import os
from pathlib import Path
import pty
import secrets
import select
import shutil
import signal
import struct
import subprocess
import sys
import termios
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
HELPER = Path(__file__).with_name("u1_pty_child.py")
SHELL = "/bin/zsh"
MAX_BUFFER = 262144
IDLE_SECONDS = 900
_lock = threading.RLock()
_sessions = {}
_reaper = None


def dimensions(body):
    cols, rows = body.get("cols", 100), body.get("rows", 28)
    if type(cols) is not int or type(rows) is not int or not 20 <= cols <= 300 or not 5 <= rows <= 100:
        raise ValueError("Terminal dimensions must be 20-300 columns and 5-100 rows.")
    return cols, rows


class Session:
    def __init__(self, cols, rows):
        self.id = secrets.token_urlsafe(18)
        self.capability = secrets.token_urlsafe(32)
        self.lock = threading.RLock()
        self.buffer = bytearray()
        self.total = 0
        self.closed = False
        self.last_seen = time.monotonic()
        master, slave = pty.openpty()
        self.fd = master
        fcntl.ioctl(master, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        env = {key: os.environ[key] for key in ("HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TMPDIR") if key in os.environ}
        home = Path(env.get("HOME", str(Path.home())))
        env.update(PATH=f"{home}/.local/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin", TERM="xterm-256color", COLORTERM="truecolor", SHELL=SHELL)
        try:
            self.process = subprocess.Popen([sys.executable, str(HELPER), SHELL], cwd=ROOT, env=env, stdin=slave, stdout=slave, stderr=slave, close_fds=True)
        except Exception:
            os.close(master)
            raise
        finally:
            os.close(slave)
        os.set_blocking(master, False)
        threading.Thread(target=self.read, name="u1-terminal-output", daemon=True).start()

    def read(self):
        while not self.closed:
            try:
                ready, _, _ = select.select([self.fd], [], [], .3)
                if not ready:
                    if self.process.poll() is not None:
                        break
                    continue
                data = os.read(self.fd, 8192)
                if not data:
                    break
                with self.lock:
                    self.buffer.extend(data)
                    self.total += len(data)
                    if len(self.buffer) > MAX_BUFFER:
                        del self.buffer[:-MAX_BUFFER]
            except (OSError, ValueError):
                break

    def close(self):
        self.closed = True
        if self.process.poll() is None:
            try:
                os.killpg(self.process.pid, signal.SIGHUP)
            except ProcessLookupError:
                self.process.terminate()
            try:
                self.process.wait(timeout=1)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(self.process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                self.process.wait(timeout=1)
        try:
            os.close(self.fd)
        except OSError:
            pass


def reap():
    while True:
        time.sleep(30)
        with _lock:
            expired = [sid for sid, session in _sessions.items() if time.monotonic() - session.last_seen > IDLE_SECONDS]
            sessions = [_sessions.pop(sid) for sid in expired]
        for session in sessions:
            session.close()


def close_all():
    with _lock:
        sessions = list(_sessions.values())
        _sessions.clear()
    for session in sessions:
        session.close()


atexit.register(close_all)


def handle_post(body):
    global _reaper
    action = body.get("action")
    if action not in {"start", "poll", "input", "resize", "close"}:
        raise ValueError("Unknown terminal action.")
    if action == "start":
        if body.get("acknowledge") is not True:
            raise ValueError("Acknowledge that this terminal can change files on your Mac.")
        cols, rows = dimensions(body)
        with _lock:
            if len(_sessions) >= 2:
                raise ValueError("Two terminal sessions are already open. Close one first.")
            session = Session(cols, rows)
            _sessions[session.id] = session
            if _reaper is None:
                _reaper = threading.Thread(target=reap, name="u1-terminal-cleanup", daemon=True)
                _reaper.start()
        tools = {name: bool(shutil.which(name, path=f"{Path.home()}/.local/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin")) for name in ("claude", "codex")}
        return dict(success=True, session=session.id, capability=session.capability, cwd=str(ROOT), tools=tools, idle_seconds=IDLE_SECONDS)
    with _lock:
        session = _sessions.get(str(body.get("session", "")))
    supplied = body.get("capability")
    if session is None or not isinstance(supplied, str) or not secrets.compare_digest(session.capability, supplied):
        raise ValueError("Terminal session is unavailable or not authorized.")
    session.last_seen = time.monotonic()
    if action == "close":
        with _lock:
            _sessions.pop(session.id, None)
        session.close()
        return dict(success=True, closed=True)
    if action == "resize":
        cols, rows = dimensions(body)
        fcntl.ioctl(session.fd, termios.TIOCSWINSZ, struct.pack("HHHH", rows, cols, 0, 0))
        return dict(success=True)
    if action == "input":
        data = body.get("input")
        if not isinstance(data, str) or not data or len(data.encode("utf-8")) > 8192:
            raise ValueError("Terminal input must be 1-8192 UTF-8 bytes.")
        if session.closed or session.process.poll() is not None:
            raise ValueError("The shell has exited. Start a new terminal.")
        encoded = data.encode("utf-8")
        with session.lock:
            sent = os.write(session.fd, encoded)
        return dict(success=True, written=sent)
    cursor = body.get("cursor", 0)
    if type(cursor) is not int or cursor < 0:
        raise ValueError("Invalid terminal output cursor.")
    with session.lock:
        start = session.total - len(session.buffer)
        offset = min(session.total, max(cursor, start))
        output = bytes(session.buffer[offset-start:offset-start+32768])
        return dict(success=True, output=base64.b64encode(output).decode("ascii"), cursor=offset+len(output), truncated=cursor<start, exited=session.process.poll() is not None)
