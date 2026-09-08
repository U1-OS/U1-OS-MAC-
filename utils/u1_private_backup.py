"""Explicit encrypted backup copies and isolated restore drills."""
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import stat
import threading
import uuid

from utils import integrations_hub, u1_recovery

MAGIC = b'U1-PRIVATE-BACKUP\x01'
LIMIT = 16 * 1024 * 1024
LOCK = threading.Lock()


def passphrase(value):
    if not isinstance(value, str) or not 12 <= len(value) <= 128:
        raise ValueError('Use a backup passphrase of 12 to 128 characters.')
    return value


def key(value, salt):
    return hashlib.scrypt(passphrase(value).encode('utf-8'), salt=salt, n=32768, r=8, p=1, dklen=32, maxmem=128*1024*1024)


def encrypt(content, secret):
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if not content or len(content) > LIMIT:
        raise ValueError('Encrypted backup copies support archives up to 16 MiB in this build.')
    salt, nonce = secrets.token_bytes(16), secrets.token_bytes(12)
    return MAGIC + salt + nonce + AESGCM(key(secret, salt)).encrypt(nonce, content, MAGIC)


def decrypt(content, secret):
    from cryptography.exceptions import InvalidTag
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if not isinstance(content, bytes) or not len(MAGIC)+44 < len(content) <= LIMIT+len(MAGIC)+44 or not content.startswith(MAGIC):
        raise ValueError('Choose a valid bounded U1 encrypted backup file.')
    pos = len(MAGIC)
    salt, nonce, ciphertext = content[pos:pos+16], content[pos+16:pos+28], content[pos+28:]
    try:
        return AESGCM(key(secret, salt)).decrypt(nonce, ciphertext, MAGIC)
    except InvalidTag:
        raise ValueError('Incorrect backup passphrase or damaged encrypted file.') from None


def archive_bytes(identifier):
    if not isinstance(identifier, str) or not re.fullmatch(r'[a-f0-9]{32}', identifier):
        raise ValueError('Choose an existing managed backup.')
    path = u1_recovery.ROOT / 'backups' / (identifier + '.zip')
    fd = os.open(path, os.O_RDONLY | getattr(os, 'O_NOFOLLOW', 0))
    with os.fdopen(fd, 'rb') as stream:
        meta = os.fstat(stream.fileno())
        if not stat.S_ISREG(meta.st_mode) or not 0 < meta.st_size <= LIMIT:
            raise ValueError('Choose a regular managed archive no larger than 16 MiB.')
        content = stream.read(LIMIT + 1)
    if len(content) != meta.st_size:
        raise ValueError('The backup changed while being read. Try a new snapshot.')
    return content


def action(body):
    if body.get('confirmed') is not True:
        raise ValueError('Confirm the backup operation and its scope.')
    secret = passphrase(body.get('passphrase'))
    if not LOCK.acquire(blocking=False):
        raise ValueError('A private backup operation is already running.')
    try:
        if body.get('action') == 'encrypt':
            encrypted = encrypt(archive_bytes(body.get('id')), secret)
            return {'success': True, 'filename': 'u1-private-backup.u1backup', 'mime': 'application/octet-stream',
                    'content': base64.b64encode(encrypted).decode('ascii'),
                    'notice': 'Encrypted copy created. The original managed local backup is unchanged and remains unencrypted.'}
        if body.get('action') == 'restore_drill':
            encoded = body.get('content')
            if not isinstance(encoded, str) or len(encoded) > (LIMIT+128)*4//3+8:
                raise ValueError('Choose an encrypted backup within the 16 MiB archive limit.')
            raw = decrypt(base64.b64decode(encoded, validate=True), secret)
            identifier = uuid.uuid4().hex
            directory = u1_recovery.ROOT / 'backups'
            directory.mkdir(parents=True, exist_ok=True)
            path = directory / (identifier + '.zip')
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(raw)
                restored = u1_recovery.restore_backup(identifier)
                return {'success': True, **restored, 'notice': 'Decrypted archive validated and restored to a separate private folder. The active workspace was not replaced.'}
            finally:
                path.unlink(missing_ok=True)
        raise ValueError('Choose encrypt or restore_drill.')
    finally:
        LOCK.release()


def handle_request(handler):
    if handler.path.split('?', 1)[0] != '/api/workspace/private-backup':
        return False
    from utils.u1_safety import _reply
    if not handler.integration_request_allowed():
        _reply(handler, {'success': False, 'error': 'Local same-origin request required'}, 403)
        return True
    if handler.command == 'GET':
        try:
            import cryptography
            _reply(handler, {'success': True, 'available': True, 'backups': u1_recovery.snapshot()['backups'],
                             'limit_bytes': LIMIT, 'source': 'Local managed archives',
                             'notice': 'Encrypted copies do not encrypt the live database or remove existing plaintext backups. Keep the passphrase separately.'})
        except ImportError:
            _reply(handler, {'success': True, 'available': False, 'backups': [], 'notice': 'The cryptography dependency is required.'})
        return True
    if not hmac.compare_digest(handler.headers.get('X-U1-CSRF', ''), integrations_hub.CSRF_TOKEN):
        _reply(handler, {'success': False, 'error': 'Reload before running a backup operation'}, 403)
        return True
    try:
        length = int(handler.headers.get('Content-Length', '0'))
        if not 0 < length <= (LIMIT+1024)*4//3+8192:
            raise ValueError('Invalid request size')
        body = json.loads(handler.rfile.read(length))
        if not isinstance(body, dict):
            raise ValueError('Expected a JSON object')
        _reply(handler, action(body))
    except (ValueError, TypeError) as exc:
        _reply(handler, {'success': False, 'error': str(exc)}, 400)
    except Exception:
        _reply(handler, {'success': False, 'error': 'The private backup operation did not complete. Your active workspace was not replaced.'}, 503)
    return True
