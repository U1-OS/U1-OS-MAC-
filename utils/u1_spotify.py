"""Opt-in, read-only Spotify adapter. GET never reads Keychain or contacts Spotify."""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import ssl
import stat
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = '/api/workspace/spotify'
CALLBACK_PATH = '/spotify/callback'
REGISTER_REDIRECT = 'http://127.0.0.1/spotify/callback'
SCOPE = 'user-read-playback-state'
MAX_BODY = 4096
FRESH_SECONDS = 45

# A dedicated service avoids changing either existing Google or image credentials.
# Secrets enter over stdin, never arguments, source, environment, or log output.
SWIFT = r'''import Foundation
import Security
guard CommandLine.arguments.count == 3 else { exit(2) }
let op = CommandLine.arguments[1], account = CommandLine.arguments[2]
guard ["get", "set", "delete"].contains(op),
      account.range(of: "^[a-f0-9]{64}$", options: .regularExpression) != nil else { exit(2) }
let base: [String: Any] = [kSecClass as String: kSecClassGenericPassword,
    kSecAttrService as String: "local.u1os.spotify.readonly", kSecAttrAccount as String: account,
    kSecAttrSynchronizable as String: false]
if op == "get" {
    var query = base
    query[kSecReturnData as String] = true
    query[kSecMatchLimit as String] = kSecMatchLimitOne
    var result: CFTypeRef?
    guard SecItemCopyMatching(query as CFDictionary, &result) == errSecSuccess,
          let data = result as? Data, data.count <= 32768 else { exit(3) }
    FileHandle.standardOutput.write(data)
} else if op == "delete" {
    let status = SecItemDelete(base as CFDictionary)
    guard status == errSecSuccess || status == errSecItemNotFound else { exit(3) }
} else {
    let data = FileHandle.standardInput.readData(ofLength: 32769)
    guard data.count > 0 && data.count <= 32768,
          (try? JSONSerialization.jsonObject(with: data)) is [String: Any] else { exit(2) }
    let update = [kSecValueData as String: data]
    var status = SecItemUpdate(base as CFDictionary, update as CFDictionary)
    if status == errSecItemNotFound {
        var entry = base
        entry[kSecValueData as String] = data
        entry[kSecAttrAccessible as String] = kSecAttrAccessibleWhenUnlockedThisDeviceOnly
        status = SecItemAdd(entry as CFDictionary, nil)
    }
    guard status == errSecSuccess else { exit(3) }
}
'''


class SpotifyError(Exception):
    """Only fixed public error codes are used, never provider response text."""


def _blocked():
    try:
        from utils.u1_safety import manager as safety_manager
        return bool(safety_manager().blocked())
    except Exception:
        return True


def _private_file(path):
    info = path.lstat()
    if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1 or info.st_mode & 0o077:
        raise SpotifyError('storage_unavailable')
    return info


def _read_metadata(path):
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except FileNotFoundError:
        return {}
    with os.fdopen(fd, 'rb') as stream:
        info = os.fstat(stream.fileno())
        if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1 or info.st_mode & 0o077 or info.st_size > MAX_BODY:
            raise SpotifyError('storage_unavailable')
        value = json.loads(stream.read(MAX_BODY + 1))
    if not isinstance(value, dict) or not re.fullmatch(r'[a-fA-F0-9]{32}', value.get('client_id', '')):
        raise SpotifyError('storage_unavailable')
    return {'client_id': value['client_id'], 'credentials_saved': value.get('credentials_saved') is True}


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _http(endpoint, *, token=None, form=None):
    urls = {'token': 'https://accounts.spotify.com/api/token',
            'player': 'https://api.spotify.com/v1/me/player?additional_types=episode'}
    url = urls[endpoint]
    headers = {'Accept': 'application/json', 'User-Agent': 'U1OS-Spotify-Readonly/1'}
    data = None
    if endpoint == 'token':
        data = urllib.parse.urlencode(form).encode('ascii')
        headers['Content-Type'] = 'application/x-www-form-urlencoded'
    else:
        headers['Authorization'] = 'Bearer ' + _token_string(token)
    request = urllib.request.Request(url, data=data, headers=headers, method='POST' if data is not None else 'GET')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect(),
                                        urllib.request.HTTPSHandler(context=ssl.create_default_context()))
    deadline = time.monotonic() + 15
    try:
        with opener.open(request, timeout=8) as response:
            status_code = response.status
            if status_code == 204:
                return 204, {}, 0
            limit = 32768 if endpoint == 'token' else 262144
            chunks, size = [], 0
            while True:
                if time.monotonic() > deadline:
                    raise SpotifyError('unavailable')
                chunk = response.read(min(8192, limit + 1 - size))
                if not chunk:
                    break
                chunks.append(chunk)
                size += len(chunk)
                if size > limit:
                    raise SpotifyError('unavailable')
            payload = json.loads(b''.join(chunks))
            if not isinstance(payload, dict):
                raise SpotifyError('unavailable')
            return status_code, payload, 0
    except urllib.error.HTTPError as error:
        try:
            retry = int(error.headers.get('Retry-After', '30'))
        except (TypeError, ValueError):
            retry = 30
        code = error.code
        error.close()  # Do not read, echo, or log error bodies (including OAuth errors).
        return code, {}, min(3600, max(15, retry))


def _token_string(value):
    if not isinstance(value, str) or not re.fullmatch(r'[\x21-\x7e]{1,4096}', value):
        raise SpotifyError('auth_required')
    return value


def _tokens(payload, previous=None):
    previous = previous or {}
    expiry = payload.get('expires_in')
    scope = payload.get('scope', previous.get('scope', ''))
    if (type(expiry) is not int or not 1 <= expiry <= 86400 or
            payload.get('token_type', '').lower() != 'bearer' or scope != SCOPE):
        raise SpotifyError('auth_required')
    return {'access_token': _token_string(payload.get('access_token')),
            'refresh_token': _token_string(payload.get('refresh_token', previous.get('refresh_token'))),
            'expires_at': time.time() + expiry, 'scope': SCOPE}


def _text(value, limit=180):
    return ''.join(c for c in value if c >= ' ' and c != '\x7f')[:limit] if isinstance(value, str) else ''


def _playback(payload):
    device = payload.get('device') if isinstance(payload.get('device'), dict) else {}
    if device.get('is_private_session') is True:
        return 'private_session', None
    item = payload.get('item')
    if not isinstance(item, dict) or item.get('type') not in ('track', 'episode'):
        return 'playback_unavailable', None
    kind = item['type']
    artists = item.get('artists') if isinstance(item.get('artists'), list) else []
    show = item.get('show') if isinstance(item.get('show'), dict) else {}
    by = ', '.join(_text(a.get('name'), 80) for a in artists[:8] if isinstance(a, dict)) if kind == 'track' else _text(show.get('name') or show.get('publisher'))
    external = item.get('external_urls') if isinstance(item.get('external_urls'), dict) else {}
    url = external.get('spotify', '')
    if not isinstance(url, str) or not re.fullmatch(r'https://open\.spotify\.com/(track|episode)/[A-Za-z0-9]{1,64}', url):
        url = None
    def millis(value):
        return value if type(value) is int and 0 <= value <= 86400000 else None
    return ('playing' if payload.get('is_playing') is True else 'paused'), {
        'title': _text(item.get('name')), 'artist': by[:240], 'type': kind, 'url': url,
        'device': _text(device.get('name'), 100), 'progress_ms': millis(payload.get('progress_ms')),
        'duration_ms': millis(item.get('duration_ms'))}


class QuietLoopbackServer(HTTPServer):
    allow_reuse_address = False

    def handle_error(self, request, client_address):
        pass  # Never print request paths, callback codes, or handler exceptions.


class SpotifyManager:
    def __init__(self, root=ROOT):
        self.root = Path(root)
        self.directory = self.root / 'data' / 'spotify'
        self.helper = self.directory / 'spotify-keychain'
        self.lock = threading.RLock()
        self.operation = threading.Lock()
        self.pending = None
        self.epoch = 0
        self.observed_at = None
        self.item = None
        self.connected = False
        self.next_refresh_at = 0
        self.config = {}
        try:
            for parent in (self.root / 'data', self.directory):
                if parent.is_symlink():
                    raise SpotifyError('storage_unavailable')
            self.config = _read_metadata(self.directory / 'config.json')
            self.status = 'auth_required' if self.config else 'setup_needed'
        except Exception:
            self.status = 'storage_unavailable'

    def _prepare(self):
        for directory in (self.root / 'data', self.directory):
            directory.mkdir(mode=0o700, exist_ok=True)
            info = directory.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
                raise SpotifyError('storage_unavailable')
        if self.directory.stat().st_mode & 0o077:
            raise SpotifyError('storage_unavailable')

    def _write(self, path, value):
        self._prepare()
        if path.exists() or path.is_symlink():
            _private_file(path)
        temporary = self.directory / ('.write-' + secrets.token_hex(12))
        try:
            fd = os.open(temporary, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, 'wb') as stream:
                stream.write(value)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    def _save(self):
        self._write(self.directory / 'config.json', json.dumps(self.config).encode('ascii'))

    def _environment(self):
        return {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'HOME': str(Path.home()),
                'TMPDIR': str(self.directory), 'LANG': 'en_US.UTF-8'}

    def _ensure_helper(self):
        self._prepare()
        if self.helper.exists() or self.helper.is_symlink():
            if not _private_file(self.helper).st_mode & 0o100:
                raise SpotifyError('keychain_setup_needed')
            return
        source = self.directory / 'SpotifyKeychain.swift'
        self._write(source, SWIFT.encode('ascii'))
        cache = self.directory / 'swift-cache'
        cache.mkdir(mode=0o700, exist_ok=True)
        if cache.is_symlink() or cache.stat().st_uid != os.getuid() or cache.stat().st_mode & 0o077:
            raise SpotifyError('storage_unavailable')
        output = self.directory / ('.helper-' + secrets.token_hex(12))
        try:
            result = subprocess.run(['/usr/bin/xcrun', 'swiftc', '-module-cache-path', str(cache), str(source), '-o', str(output)],
                                    shell=False, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                    stderr=subprocess.DEVNULL, timeout=45, env=self._environment(), cwd=self.directory)
            if result.returncode != 0:
                raise SpotifyError('keychain_setup_needed')
            info = output.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid() or info.st_nlink != 1:
                raise SpotifyError('storage_unavailable')
            output.chmod(0o700)
            os.replace(output, self.helper)
        finally:
            output.unlink(missing_ok=True)

    def _keychain(self, action, value=None):
        _private_file(self.helper)
        account = hashlib.sha256((str(self.root) + ':' + self.config['client_id']).encode()).hexdigest()
        raw = json.dumps(value, separators=(',', ':')).encode('ascii') if value is not None else b''
        if len(raw) > 32768:
            raise SpotifyError('auth_required')
        result = subprocess.run([str(self.helper), action, account], input=raw, shell=False,
                                stdout=subprocess.PIPE if action == 'get' else subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, timeout=12, env=self._environment(), cwd=self.directory)
        if result.returncode != 0:
            raise SpotifyError('keychain_unavailable')
        if action == 'get':
            if len(result.stdout) > 32768:
                raise SpotifyError('auth_required')
            tokens = json.loads(result.stdout)
            if not isinstance(tokens, dict) or tokens.get('scope') != SCOPE:
                raise SpotifyError('auth_required')
            _token_string(tokens.get('access_token'))
            _token_string(tokens.get('refresh_token'))
            if type(tokens.get('expires_at')) not in (int, float) or not 0 < tokens['expires_at'] < 1e12:
                raise SpotifyError('auth_required')
            return tokens

    def _allowed(self, epoch):
        blocked = _blocked()  # Safety is always called BEFORE taking our state mutex.
        with self.lock:
            if blocked or epoch != self.epoch:
                raise SpotifyError('safety_blocked')

    def cancel(self):
        with self.lock:
            self.epoch += 1
            if self.pending:
                self.pending['stop'].set()
                self.pending = None
            self.status = 'stale' if self.observed_at else ('auth_required' if self.config else 'setup_needed')

    def snapshot(self):
        with self.lock:
            stale = bool(self.observed_at and time.time() - self.observed_at > FRESH_SECONDS)
            status = self.status
            if stale and status in ('playing', 'paused', 'nothing_playing', 'private_session', 'playback_unavailable'):
                status = 'stale'
            return {'success': True, 'provider': 'Spotify', 'status': status,
                    'configured': bool(self.config), 'credentials_saved': self.config.get('credentials_saved') is True,
                    'connected': self.connected, 'live_verified': bool(self.observed_at and not stale and status in ('playing', 'paused', 'nothing_playing', 'private_session', 'playback_unavailable')),
                    'observed_at': self.observed_at, 'item': dict(self.item) if self.item else None,
                    'next_refresh_at': self.next_refresh_at, 'register_redirect_uri': REGISTER_REDIRECT,
                    'scope': SCOPE, 'read_only': True, 'controls_available': False,
                    'oauth_pending': self.pending is not None}

    def configure(self, client_id):
        if not isinstance(client_id, str) or not re.fullmatch(r'[a-fA-F0-9]{32}', client_id):
            raise SpotifyError('invalid_client_id')
        if self.config.get('credentials_saved') and self.config.get('client_id') != client_id:
            raise SpotifyError('disconnect_before_reconfigure')
        self._ensure_helper()  # Explicit setup only; does not read or test a Keychain item.
        self.cancel()
        with self.lock:
            self.config = {'client_id': client_id, 'credentials_saved': self.config.get('credentials_saved', False)}
            self.status = 'auth_required'
            self._save()
        return self.snapshot()

    def connect(self):
        if not self.config:
            raise SpotifyError('setup_needed')
        _private_file(self.helper)
        self.cancel()
        owner = self

        class Callback(BaseHTTPRequestHandler):
            def setup(self):
                super().setup()
                self.connection.settimeout(2)

            def log_message(self, *args):
                pass

            def do_GET(self):
                ok = False
                try:
                    expected = '127.0.0.1:' + str(self.server.server_port)
                    if self.headers.get('Host') == expected and len(self.path) <= 8192:
                        ok = owner.callback(self.path, expected)
                except Exception:
                    pass
                content = (b'<!doctype html><meta charset="utf-8"><title>Spotify authorization</title><h1>Spotify authorization received</h1><p>Return to U1 OS and use Check playback.</p>' if ok else
                           b'<!doctype html><meta charset="utf-8"><title>Spotify authorization</title><h1>Authorization not completed</h1><p>Return to U1 OS. Start a new connection if needed.</p>')
                self.send_response(200 if ok else 400)
                for key, value in (('Content-Type', 'text/html; charset=utf-8'), ('Content-Length', str(len(content))),
                                   ('Cache-Control', 'no-store'), ('Referrer-Policy', 'no-referrer'),
                                   ('Content-Security-Policy', "default-src 'none'; frame-ancestors 'none'"), ('Connection', 'close')):
                    self.send_header(key, value)
                self.end_headers()
                self.wfile.write(content)

        server = QuietLoopbackServer(('127.0.0.1', 0), Callback)
        server.timeout = 0.5
        verifier = secrets.token_urlsafe(64)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode('ascii')).digest()).rstrip(b'=').decode('ascii')
        pending = {'state': secrets.token_urlsafe(32), 'verifier': verifier, 'deadline': time.monotonic() + 600,
                   'redirect': 'http://127.0.0.1:' + str(server.server_port) + CALLBACK_PATH,
                   'stop': threading.Event(), 'epoch': self.epoch}
        try:
            self._allowed(pending['epoch'])
            with self.lock:
                # Cancellation can occur after the Safety check. Publication must
                # compare the epoch atomically with cancel(), without calling Safety.
                if pending['epoch'] != self.epoch:
                    raise SpotifyError('safety_blocked')
                self.pending = pending
                self.status = 'authorization_pending'
            def listen():
                try:
                    while not pending['stop'].is_set() and time.monotonic() < pending['deadline']:
                        server.handle_request()
                finally:
                    server.server_close()
                    with self.lock:
                        if self.pending is pending:
                            self.pending = None
                            self.status = 'auth_required'
            threading.Thread(target=listen, name='u1-spotify-oauth', daemon=True).start()
        except Exception:
            pending['stop'].set()
            with self.lock:
                if self.pending is pending:
                    self.pending = None
                    self.status = 'auth_required' if self.config else 'setup_needed'
            server.server_close()
            raise
        return dict(self.snapshot(), authorization_url='https://accounts.spotify.com/authorize?' + urllib.parse.urlencode({
            'client_id': self.config['client_id'], 'response_type': 'code', 'redirect_uri': pending['redirect'],
            'scope': SCOPE, 'state': pending['state'], 'code_challenge_method': 'S256', 'code_challenge': challenge}))

    def callback(self, path, host):
        parsed = urllib.parse.urlsplit(path)
        if parsed.path != CALLBACK_PATH or len(path) > 8192:
            return False
        query = urllib.parse.parse_qs(parsed.query, max_num_fields=8)
        state = query.get('state', [])
        if len(state) != 1 or not re.fullmatch(r'[A-Za-z0-9_-]{43}', state[0]):
            return False
        with self.lock:
            pending = self.pending
            if (not pending or urllib.parse.urlsplit(pending['redirect']).netloc != host or
                    time.monotonic() > pending['deadline'] or not hmac.compare_digest(state[0], pending['state'])):
                return False
            self.pending = None  # Consume before any exchange, including denial or failure.
            pending['stop'].set()
        if not self.operation.acquire(blocking=False):
            return False
        try:
            self._allowed(pending['epoch'])
            code = query.get('code', [])
            if 'error' in query or len(code) != 1 or not 1 <= len(code[0]) <= 4096:
                raise SpotifyError('auth_required')
            status_code, payload, _ = _http('token', form={'grant_type': 'authorization_code', 'code': code[0],
                'redirect_uri': pending['redirect'], 'client_id': self.config['client_id'], 'code_verifier': pending['verifier']})
            if status_code != 200:
                raise SpotifyError('auth_required')
            tokens = _tokens(payload)
            self._allowed(pending['epoch'])
            self._keychain('set', tokens)
            self._allowed(pending['epoch'])
            with self.lock:
                self.config['credentials_saved'] = True
                self._save()
                self.connected = True
                self.status = 'connected_unchecked'
            return True
        except Exception:
            with self.lock:
                self.status = 'auth_required'
            return False
        finally:
            self.operation.release()

    def refresh(self):
        with self.lock:
            epoch = self.epoch
            if time.time() < self.next_refresh_at:
                return self.snapshot()
            self.next_refresh_at = time.time() + 15
        self._allowed(epoch)
        if not self.config.get('credentials_saved'):
            raise SpotifyError('auth_required')
        try:
            tokens = self._keychain('get')
            def renew():
                self._allowed(epoch)
                status_code, payload, _ = _http('token', form={'grant_type': 'refresh_token',
                    'refresh_token': tokens['refresh_token'], 'client_id': self.config['client_id']})
                if status_code != 200:
                    raise SpotifyError('auth_required')
                renewed = _tokens(payload, tokens)
                self._allowed(epoch)
                self._keychain('set', renewed)
                return renewed
            renewed = False
            if tokens['expires_at'] <= time.time() + 30:
                tokens = renew()
                renewed = True
            self._allowed(epoch)
            status_code, payload, retry = _http('player', token=tokens['access_token'])
            if status_code == 401 and not renewed:
                tokens = renew()
                self._allowed(epoch)
                status_code, payload, retry = _http('player', token=tokens['access_token'])
            self._allowed(epoch)
            with self.lock:
                if status_code in (200, 204):
                    self.status, self.item = ('nothing_playing', None) if status_code == 204 else _playback(payload)
                    self.connected = True
                    self.observed_at = time.time()
                elif status_code == 401:
                    self.status, self.connected, self.item = 'auth_required', False, None
                elif status_code == 429:
                    self.status = 'rate_limited'
                    self.next_refresh_at = time.time() + max(15, retry)
                else:
                    self.status = 'unavailable'
        except SpotifyError as error:
            with self.lock:
                self.status = str(error) if str(error) in ('auth_required', 'keychain_unavailable', 'safety_blocked') else 'unavailable'
                if self.status == 'auth_required':
                    self.connected, self.item = False, None
        except Exception:
            with self.lock:
                self.status = 'stale' if self.observed_at else 'unavailable'
        return self.snapshot()

    def disconnect(self):
        self.cancel()
        with self.lock:
            self.connected, self.item, self.observed_at = False, None, None
            self.status = 'auth_required' if self.config else 'setup_needed'
        if self.config:
            self._keychain('delete')  # Local removal only. Spotify dashboard revocation is separate.
            with self.lock:
                self.config['credentials_saved'] = False
                self._save()
        return self.snapshot()

    def action(self, body):
        if _blocked():
            raise SpotifyError('safety_blocked')
        if body.get('confirmed') is not True:
            raise SpotifyError('confirmation_required')
        if not self.operation.acquire(blocking=False):
            raise SpotifyError('busy')
        try:
            if body.get('action') == 'configure':
                return self.configure(body.get('client_id'))
            if body.get('action') == 'connect':
                return self.connect()
            if body.get('action') == 'refresh':
                return self.refresh()
            if body.get('action') == 'disconnect':
                return self.disconnect()
            raise SpotifyError('invalid_action')
        finally:
            self.operation.release()


_instance = None
_instance_lock = threading.Lock()


def manager():
    global _instance
    with _instance_lock:
        if _instance is None:
            _instance = SpotifyManager()
        return _instance


def cancel_all():
    """Parent Safety hook: invoke outside its mutex; never starts a manager/listener."""
    instance = _instance
    if instance is not None:
        instance.cancel()


def _reply(handler, status_code, payload):
    raw = json.dumps(payload, ensure_ascii=True, allow_nan=False).encode('utf-8')
    handler.send_response(status_code)
    for key, value in (('Content-Type', 'application/json; charset=utf-8'), ('Content-Length', str(len(raw))),
                       ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'), ('Connection', 'close')):
        handler.send_header(key, value)
    if status_code == 405:
        handler.send_header('Allow', 'GET, POST')
    handler.end_headers()
    handler.wfile.write(raw)
    handler.close_connection = True


def handle_request(handler):
    if urllib.parse.urlsplit(handler.path).path != PATH:
        return False
    try:
        if not handler.integration_request_allowed():
            _reply(handler, 403, {'success': False, 'error': 'request_not_allowed'})
            return True
        if handler.command == 'GET':
            _reply(handler, 200, manager().snapshot())
        elif handler.command == 'POST':
            from utils.integrations_hub import CSRF_TOKEN
            supplied = handler.headers.get('X-U1-CSRF', '')
            if not isinstance(supplied, str) or not supplied.isascii() or not hmac.compare_digest(supplied, CSRF_TOKEN):
                _reply(handler, 403, {'success': False, 'error': 'request_not_allowed'})
                return True
            if handler.headers.get('Transfer-Encoding') or handler.headers.get('Content-Type', '').split(';')[0].strip() != 'application/json':
                raise SpotifyError('invalid_request')
            length = int(handler.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_BODY:
                raise SpotifyError('invalid_request')
            raw = handler.rfile.read(length)
            if len(raw) != length:
                raise SpotifyError('invalid_request')
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise SpotifyError('invalid_request')
            _reply(handler, 200, manager().action(body))
        else:
            _reply(handler, 405, {'success': False, 'error': 'method_not_allowed'})
    except SpotifyError as error:
        allowed = {'safety_blocked', 'confirmation_required', 'busy', 'invalid_action', 'invalid_client_id',
                   'disconnect_before_reconfigure', 'keychain_setup_needed', 'keychain_unavailable',
                   'storage_unavailable', 'auth_required', 'setup_needed', 'invalid_request'}
        code = str(error) if str(error) in allowed else 'unavailable'
        _reply(handler, 409 if code == 'busy' else 400, {'success': False, 'error': code})
    except Exception:
        _reply(handler, 503, {'success': False, 'error': 'spotify_unavailable'})
    return True
