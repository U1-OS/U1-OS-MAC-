"""Local application access lock. Not a firewall, Mac lock or order canceller."""
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path


class SafetyError(ValueError):
    pass


def internet_reachable():
    """Require a validated HTTPS response, without transmitting account data."""
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *args, **kwargs):
            return None

    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    for url in ("https://www.gstatic.com/generate_204", "https://cp.cloudflare.com/generate_204"):
        try:
            request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "U1-OS-Safety/1"})
            with opener.open(request, timeout=3) as response:
                if response.status == 204:
                    return True
        except (OSError, urllib.error.URLError, ValueError):
            continue
    return False


class SafetyLock:
    def __init__(self, directory, probe=internet_reachable, clock=time.time):
        self.directory = Path(directory)
        self.path = self.directory / "state.json"
        self.probe = probe
        self.clock = clock
        self.mutex = threading.RLock()
        self.token = secrets.token_urlsafe(32)
        self.config = None
        self.locked = False
        self.reason = "Safety has not been set up"
        self.fault = None
        self.network = None
        self.network_at = 0
        self.network_failures = 0
        self.deadline = None
        self.failures = 0
        self.retry_at = 0
        self.started = False
        self._load()

    def _load(self):
        try:
            if self.directory.is_symlink() or self.path.is_symlink():
                raise SafetyError("Safety storage must not be a symbolic link")
            if not self.path.exists():
                return
            if self.path.stat().st_size > 8192:
                raise SafetyError("Invalid safety configuration")
            fd = os.open(self.path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
            with os.fdopen(fd, "r", encoding="utf-8") as stream:
                value = json.load(stream)
            if (not isinstance(value, dict) or value.get("version") != 1
                    or len(bytes.fromhex(value["salt"])) != 16
                    or len(bytes.fromhex(value["hash"])) != 32
                    or type(value.get("offline")) is not bool
                    or type(value.get("minutes")) is not int
                    or value["minutes"] not in (0, 5, 15, 30, 60, 120, 240)):
                raise SafetyError("Invalid safety configuration")
            self.config = value
            self.locked = True
            self.reason = "Server restarted. Unlock with your safety passphrase."
        except (OSError, ValueError, TypeError, KeyError):
            self.fault = "Safety configuration is unreadable. Owner recovery is required; access remains locked."
            self.locked = True
            self.reason = self.fault

    def _persist(self, value):
        if self.directory.is_symlink() or self.path.is_symlink():
            raise SafetyError("Safety storage must not be a symbolic link")
        self.directory.mkdir(mode=0o700, parents=True, exist_ok=True)
        os.chmod(self.directory, 0o700)
        temporary = self.directory / (".state-" + secrets.token_hex(12))
        try:
            fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as stream:
                json.dump(value, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _hash(passphrase, salt):
        return hashlib.scrypt(passphrase.encode("utf-8"), salt=bytes.fromhex(salt), n=16384, r=8, p=1, dklen=32).hex()

    def _authenticate(self, passphrase):
        if self.clock() < self.retry_at:
            raise SafetyError("Too many attempts. Wait before trying again.")
        if not isinstance(passphrase, str) or not 1 <= len(passphrase) <= 128:
            valid = False
        else:
            valid = hmac.compare_digest(self._hash(passphrase, self.config["salt"]), self.config["hash"])
        if not valid:
            self.failures += 1
            if self.failures >= 5:
                self.retry_at = self.clock() + 60
                self.failures = 0
            raise SafetyError("Incorrect passphrase. The OS remains in its current safety state.")
        self.failures = 0
        self.retry_at = 0

    def _lock(self, reason):
        self.locked = True
        self.reason = reason
        self.deadline = None

    def _expire(self):
        if self.config and not self.locked and self.deadline is not None and self.clock() >= self.deadline:
            self._lock("Dead-man check-in expired")

    def snapshot(self):
        with self.mutex:
            self._expire()
            return {"success": True, "configured": bool(self.config), "locked": self.locked,
                    "reason": self.reason, "fault": self.fault, "csrf_token": self.token,
                    "offline_lock": bool(self.config and self.config["offline"]),
                    "checkin_minutes": self.config["minutes"] if self.config else 0,
                    "deadline": self.deadline, "server_time": self.clock(),
                    "network": self.network, "network_checked_at": self.network_at,
                    "retry_after": max(0, int(self.retry_at - self.clock())),
                    "scope": "U1 OS UI and new API requests only. Existing jobs, streams, other apps and exchange orders are not cancelled."}

    def blocked(self):
        with self.mutex:
            self._expire()
            return self.locked

    def _checkin(self):
        minutes = self.config["minutes"]
        self.deadline = self.clock() + minutes * 60 if minutes else None

    def tick(self, network=None):
        with self.mutex:
            self._expire()
            if network is not None:
                self.network = bool(network)
                self.network_at = self.clock()
                self.network_failures = 0 if network else self.network_failures + 1
                if self.config and self.config["offline"] and self.network_failures >= 2:
                    if not self.locked:
                        self._lock("Internet reachability failed twice")

    def start(self):
        with self.mutex:
            if self.started:
                return
            self.started = True

        def watch():
            last_probe = 0
            while True:
                try:
                    with self.mutex:
                        needed = bool(self.config and self.config["offline"])
                    if needed and time.monotonic() - last_probe >= 12:
                        self.tick(self.probe())
                        last_probe = time.monotonic()
                    else:
                        self.tick()
                except Exception:
                    with self.mutex:
                        if self.config:
                            self._lock("Safety monitor encountered an error")
                time.sleep(1)

        threading.Thread(target=watch, name="U1SafetyWatch", daemon=True).start()

    def action(self, body):
        if body.get("action") in {"pause_jobs", "resume_jobs", "stop_jobs"}:
            with self.mutex:
                self._expire()
                if self.fault:
                    raise SafetyError(self.fault)
                if body.get("confirmed") is not True:
                    raise SafetyError("Confirm this managed-job action")
                if self.locked:
                    if not self.config:
                        raise SafetyError("Owner recovery is required")
                    self._authenticate(body.get("passphrase"))
                    if body["action"] == "resume_jobs":
                        raise SafetyError("Unlock the OS before resuming managed jobs")
            from utils import u1_assistant
            if body["action"] == "stop_jobs":
                job_result = u1_assistant.cancel_all()
            else:
                job_result = u1_assistant.pause(body["action"] == "pause_jobs")
            return {**self.snapshot(), "managed_jobs": job_result}
        with self.mutex:
            self._expire()
            if self.fault:
                raise SafetyError(self.fault)
            action = body.get("action")
            if action == "configure":
                if body.get("confirmed") is not True:
                    raise SafetyError("Confirm the safety scope before saving")
                if self.config:
                    self._authenticate(body.get("current_passphrase"))
                phrase = body.get("passphrase", "")
                if not isinstance(phrase, str) or not 10 <= len(phrase) <= 128:
                    raise SafetyError("Choose a passphrase between 10 and 128 characters")
                minutes = body.get("minutes", 0)
                offline = body.get("offline", True)
                if type(minutes) is not int or minutes not in (0, 5, 15, 30, 60, 120, 240) or type(offline) is not bool:
                    raise SafetyError("Invalid safety settings")
                salt = secrets.token_hex(16)
                config = {"version": 1, "salt": salt, "hash": self._hash(phrase, salt), "offline": offline, "minutes": minutes}
                self._persist(config)
                self.config = config
                self._lock("Safety configured. Unlock to begin your session.")
                self.start()
            elif not self.config:
                raise SafetyError("Set a safety passphrase before using the switch")
            elif action in ("lock", "offline"):
                if action == "lock" or self.config["offline"]:
                    self._lock("Dead-man switch activated" if action == "lock" else "Browser reported connection loss")
            elif action == "unlock":
                self._authenticate(body.get("passphrase"))
                if self.config["offline"]:
                    reachable = self.probe()
                    self.tick(reachable)
                    if not reachable:
                        raise SafetyError("Internet reachability is unavailable. Reconnect, or change offline locking in Safety settings using your passphrase.")
                self.locked = False
                self.reason = "Unlocked by the operator"
                self._checkin()
            elif action == "checkin":
                if self.locked:
                    raise SafetyError("Unlock before checking in")
                self._checkin()
            else:
                raise SafetyError("Unknown safety action")
            return self.snapshot()


_instance = None
_instance_lock = threading.Lock()


def manager():
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = SafetyLock(Path(__file__).resolve().parents[1] / "data" / "safety")
            _instance.start()
        return _instance


def _reply(handler, data, code=200):
    content = json.dumps(data).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(content)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("Connection", "close")
    handler.end_headers()
    handler.close_connection = True
    handler.wfile.write(content)


def gate_request(handler):
    """Return False when a safety response has fully handled the request."""
    path = handler.path.split("?", 1)[0]
    if not path.startswith(("/api/", "/exports/")):
        return True
    safety = manager()
    if path != "/api/safety":
        if safety.blocked():
            _reply(handler, {"success": False, "locked": True, "error": "U1 OS is safety locked. Unlock in the main U1 OS window."}, 423)
            return False
        return True
    if not handler.integration_request_allowed():
        _reply(handler, {"success": False, "error": "Local same-origin request required"}, 403)
        return False
    if handler.command == "GET":
        _reply(handler, safety.snapshot())
        return False
    if not hmac.compare_digest(handler.headers.get("X-U1-Safety", ""), safety.token):
        _reply(handler, {"success": False, "error": "Reload Safety before running an action"}, 403)
        return False
    try:
        length = int(handler.headers.get("Content-Length", "0"))
        if not 0 < length <= 8192:
            raise SafetyError("Invalid request size")
        body = json.loads(handler.rfile.read(length))
        if not isinstance(body, dict):
            raise SafetyError("Expected a JSON object")
        _reply(handler, safety.action(body))
    except (ValueError, TypeError) as exc:
        _reply(handler, {"success": False, "error": str(exc)}, 400)
    except Exception:
        _reply(handler, {"success": False, "error": "Safety could not complete this action. No successful unlock is confirmed."}, 503)
    return False
