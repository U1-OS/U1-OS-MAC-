"""Read-only activation metadata. Never initialize adapters, read keys or call accounts."""
import json
import math
import os
from pathlib import Path
import sqlite3
import stat
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
CODEX = Path('/Users/u1/.local/bin/codex')
PATH = '/api/workspace/activation'
ACTIVE = {'queued', 'running', 'cancelling'}
TERMINAL = {'succeeded', 'failed', 'cancelled', 'timed_out', 'interrupted'}
GUIDES = {
    'google': dict(name='Google', route='integrations', billing='Review Google account consent and requested read-only scopes.',
                   steps=['Review the Desktop app OAuth client setup in Google setup. Keep credentials inside the native setup form.',
                          'Open the existing Google consent flow and review the account and requested scopes yourself.',
                          'Choose one read-only Sync in Connections, then inspect its reported result before recording your review.'],
                   links=[dict(label='Google Cloud setup', url='https://console.cloud.google.com/apis/credentials')]),
    'codex': dict(name='AI Command', route='ai', billing='A confirmed send uses the existing Codex/ChatGPT allowance.',
                  steps=['Open AI Command and review installed versus authorised status. Existing sign-in is handled by Codex.',
                         'Review one prompt, explicitly selected context and conversation history; confirm allowance use in AI Command.',
                         'Send once, inspect the recorded job and response, then return here. A checklist mark is only your own review record.'], links=[]),
    'images': dict(name='Images', route='images', billing='Separate OpenAI API billing; it is not covered by the Codex/ChatGPT allowance.',
                   steps=['Open Images setup and store its separate API key in native Keychain. Do not put keys or tokens in chat.',
                          'Review one image prompt and the separate API billing confirmation in Images.',
                          'Generate once and inspect its real PNG and job evidence before recording your review.'], links=[]),
    'canva': dict(name='Canva', route=None, billing='Manual handoff only. No native Canva account verification or design API action is implemented here.',
                  steps=['Review the unfinished Canva connector boundary. Saved settings or checklist marks cannot connect Canva.',
                         'Open Canva yourself and review one design or brief as a manual handoff.',
                         'Record only that you reviewed the handoff. This is not an OAuth connection or verified API action.'],
                  links=[dict(label='Open Canva for manual handoff', url='https://www.canva.com/'),
                         dict(label='Official Canva Connect documentation', url='https://www.canva.dev/docs/connect/')]),
}


def _timestamp(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        return None
    return value


def _executable(path):
    try:
        return path.is_file() and os.access(path, os.X_OK)
    except OSError:
        return False


def _image_metadata(root):
    """This adapter-owned file contains only configured/updated_at, never a key."""
    path = root / 'image-provider.json'
    try:
        if root.is_symlink():
            return dict(available=False, configured=None, updated_at=None)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        with os.fdopen(fd, 'rb') as stream:
            info = os.fstat(stream.fileno())
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or info.st_nlink != 1 or info.st_mode & 0o077 or info.st_size > 4096):
                raise ValueError('Unsafe metadata')
            raw = stream.read(4097)
        if len(raw) > 4096:
            raise ValueError('Oversized metadata')
        data = json.loads(raw)
        if not isinstance(data, dict) or type(data.get('configured')) is not bool:
            raise ValueError('Invalid metadata')
        return dict(available=True, configured=data['configured'], updated_at=_timestamp(data.get('updated_at')))
    except (OSError, ValueError, UnicodeError):
        return dict(available=False, configured=None, updated_at=None)


def _google_metadata(directory):
    """Project scalar metadata in SQLite; never return the preference JSON or mail."""
    path = directory / 'workspace.sqlite3'
    unavailable = dict(available=False, configured=None, last_sync=None, auto_sync=None)
    connection = None
    try:
        if directory.is_symlink() or path.is_symlink() or not path.is_file():
            return unavailable
        # immutable reads avoid creating journal/shm files. Refuse an outstanding
        # WAL instead of silently reporting a potentially obsolete main DB image.
        wal = Path(str(path) + '-wal')
        if wal.exists() and wal.stat().st_size:
            return unavailable
        connection = sqlite3.connect(path.absolute().as_uri() + '?mode=ro&immutable=1', uri=True, timeout=.1)
        deadline = time.monotonic() + .1
        connection.set_progress_handler(lambda: int(time.monotonic() > deadline), 1000)
        row = connection.execute(
            "SELECT json_extract(value, '$.configured'), json_extract(value, '$.last_sync'), "
            "json_extract(value, '$.auto_sync'), json_type(value, '$.configured'), "
            "json_type(value, '$.auto_sync') FROM preferences "
            "WHERE key = ? AND length(value) <= ? LIMIT 1",
            ('u1_google_readonly_v1', 2 * 1024 * 1024)).fetchone()
        if row is None:
            return dict(available=True, configured=False, last_sync=None, auto_sync=False)
        configured = bool(row[0]) if row[3] in {'true', 'false'} else None
        auto_sync = bool(row[2]) if row[4] in {'true', 'false'} else None
        return dict(available=True, configured=configured, last_sync=_timestamp(row[1]), auto_sync=auto_sync)
    except (OSError, sqlite3.Error, ValueError):
        return unavailable
    finally:
        if connection is not None:
            connection.close()


def _runtime(modules):
    """Inspect existing in-memory evidence only; never call manager()/snapshot()."""
    service = getattr(modules.get('utils.u1_assistant'), '_instance', None)
    result = dict(available=False, paused=None, storage_fault=None, active_count=None,
                  text_success_at=None, image_success_at=None, image_latest_status=None,
                  authorised_at=None, assistant_root=None)
    if service is not None:
        condition = getattr(service, 'condition', None)
        if condition is not None and condition.acquire(timeout=.05):
            try:
                result.update(available=True, paused=service.paused is True,
                              storage_fault=service.storage_fault is True,
                              authorised_at=_timestamp(service.authorised_at),
                              assistant_root=Path(service.root), active_count=0)
                jobs = service.jobs[-64:]
                for job in reversed(jobs):
                    if not isinstance(job, dict):
                        continue
                    status = job.get('status')
                    if status in ACTIVE:
                        result['active_count'] += 1
                    kind = job.get('kind', 'text')
                    if kind == 'image' and result['image_latest_status'] is None and status in ACTIVE | TERMINAL:
                        result['image_latest_status'] = status
                    if status == 'succeeded':
                        field = 'image_success_at' if kind == 'image' else 'text_success_at'
                        result[field] = result[field] or _timestamp(job.get('finished_at'))
            finally:
                condition.release()
    return result


def snapshot(root=None, *, modules=None, codex_path=CODEX):
    """Trusted root/modules overrides support fixtures; no HTTP path overrides."""
    root = Path(root) if root is not None else ROOT
    modules = sys.modules if modules is None else modules
    try:
        runtime = _runtime(modules)
    except Exception:
        runtime = _runtime({})
    assistant_root = runtime.pop('assistant_root') or root / 'data' / 'assistant'
    prism = modules.get('utils.prism_workspace')
    prism_directory = Path(getattr(prism, 'DATA', os.environ.get('PRISM_DATA_DIR', root / 'data' / 'prism')))
    google = _google_metadata(prism_directory)
    google['helper_installed'] = _executable(root / '.runtime' / 'u1-keychain')
    image = _image_metadata(assistant_root)
    image['helper_installed'] = _executable(assistant_root / 'credentials' / 'image-keychain')
    installed = _executable(Path(codex_path))
    image_success = runtime['image_success_at']
    if image['updated_at'] and image_success and image_success < image['updated_at']:
        image_success = None
    statuses = {
        'google': ('recorded_success' if google['last_sync'] else 'configured_unverified' if google['configured']
                   else 'setup_needed' if google['configured'] is False or not google['helper_installed'] else 'unknown'),
        'codex': 'not_installed' if not installed else 'recorded_success' if runtime['text_success_at'] else 'installed_unverified',
        'images': 'setup_needed' if not image['configured'] or not image['helper_installed'] else 'recorded_success' if image_success else 'configured_unverified',
        'canva': 'unfinished_handoff',
    }
    details = {
        'google': dict(google, source='Scalar metadata from the existing local Google preference; no account request.',
                       evidence_at=google['last_sync']),
        'codex': dict(installed=installed, runtime_available=runtime['available'], evidence_at=runtime['text_success_at'],
                      source='Executable metadata and already-loaded managed-job evidence; no CLI/auth probe.'),
        'images': dict(image, evidence_at=image_success, latest_job_status=runtime['image_latest_status'],
                       source='Non-secret setup marker and already-loaded managed-job evidence; no Keychain read.'),
        'canva': dict(adapter_complete=False, evidence_at=None,
                      source='Known unfinished integration boundary. Manual handoff is available; native connection is not.'),
    }
    providers = []
    for identifier, guide in GUIDES.items():
        providers.append(dict(id=identifier, **guide, status=statuses[identifier],
                              evidence=details[identifier], live_verified=False))
    return dict(success=True, read_only=True, checked_at=time.time(), live_verification='not_performed',
                notice='Local setup evidence only. Past success and operator checkmarks do not verify present account access.',
                queue=dict(available=runtime['available'], paused=runtime['paused'],
                           active_count=runtime['active_count'], storage_fault=runtime['storage_fault']),
                operator_records=dict(storage='browser_local_only', changes_provider_status=False), providers=providers)


def _reply(handler, body, code=200):
    content = json.dumps(body, ensure_ascii=True, separators=(',', ':'), allow_nan=False).encode()
    handler.send_response(code)
    for name, value in [('Content-Type', 'application/json; charset=utf-8'), ('Content-Length', str(len(content))),
                        ('Cache-Control', 'no-store'), ('X-Content-Type-Options', 'nosniff'), ('Connection', 'close')]:
        handler.send_header(name, value)
    if code == 405:
        handler.send_header('Allow', 'GET')
    handler.end_headers()
    handler.close_connection = True
    handler.wfile.write(content)


def handle_request(handler):
    """Exact GET-only route. Parent calls after Safety; True means handled."""
    if handler.path.split('?', 1)[0] != PATH:
        return False
    try:
        if not handler.integration_request_allowed():
            _reply(handler, dict(success=False, error='Local same-origin request required.'), 403)
        elif handler.command != 'GET':
            _reply(handler, dict(success=False, error='Activation is read-only. Use the existing provider view for an explicitly reviewed action.'), 405)
        else:
            _reply(handler, snapshot())
    except Exception:
        _reply(handler, dict(success=False, error='Activation metadata is unavailable. No account check was performed.'), 503)
    return True
