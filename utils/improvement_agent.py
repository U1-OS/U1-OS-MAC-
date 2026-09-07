"""A bounded, local-only maintenance advisor. Never executes repairs or AI calls."""
import copy
import importlib.util
import json
import shutil
import sys
import threading
import time
from pathlib import Path

from utils.integrations_hub import persist

ROOT = Path(__file__).resolve().parent.parent
STORE = ROOT / 'data' / 'improvement-agent.json'
INTERVAL = 900
LOCK = threading.RLock()
WAKE = threading.Event()
STATE = dict(enabled=True, checked_at=None, checking=False, findings=[], history=[], error=None)
STARTED = False


def save():
    STORE.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    persist(STATE, str(STORE))


def snapshot():
    with LOCK:
        result = copy.deepcopy(STATE)
    result.update(success=True, interval_seconds=INTERVAL, mode='Local, rule-based advisor',
                  next_check_at=(result['checked_at'] + INTERVAL) if result['enabled'] and result['checked_at'] else None,
                  permissions=['Read local installation metadata', 'Check runtime availability', 'Write its own findings'],
                  safeguards=['No automatic repairs', 'No outbound requests', 'No paid AI calls', 'No account credentials read'])
    return result


def inspect(tool_loader):
    findings = []
    def add(key, priority, title, detail, destination):
        findings.append(dict(id=key, priority=priority, title=title, detail=detail, destination=destination))
    tools = tool_loader()['tools']
    for tool in tools:
        if not tool['installed']:
            add('missing-' + tool['id'], 'attention', tool['name'] + ' is missing',
                'Restore this registered repository before trying to launch it. Auto Finder will not clone or install software without your action.', 'tools')
        elif not tool.get('ready'):
            add('runtime-' + tool['id'], 'attention', tool['name'] + ' needs setup', tool['setup_issue'], 'tools')
    for module, title in [('reportlab', 'PDF generation'), ('pypdf', 'PDF text extraction')]:
        if importlib.util.find_spec(module) is None:
            add('dependency-' + module, 'setup', title + ' dependency is missing',
                'Install ' + module + ' into the U1 OS Python runtime to enable this capability. No installation has been started.', 'studio')
    for executable, description in [('ffmpeg', 'Local audio/video processing'), ('ollama', 'Offline language models')]:
        if not shutil.which(executable):
            add('dependency-' + executable, 'setup', description + ' is not available',
                executable + ' was not found on the server PATH. This is optional; other workspace features can still be used.', 'settings')
    for provider in ['claude', 'codex']:
        if not (Path.home() / '.local/bin' / provider).is_file():
            add('provider-' + provider, 'setup', provider.title() + ' CLI is missing',
                'Install and sign in to the official CLI before asking this provider to run a task. A website login alone is not detected here.', 'integrations')
    free = shutil.disk_usage(ROOT).free / 1024**3
    if free < 5:
        add('disk-space', 'attention', 'Less than 5 GB of disk space remains',
            'About %.1f GB is free. Review media exports and local caches yourself; Auto Finder never deletes your files.' % free, 'settings')
    if sys.version_info < (3, 11):
        add('python-version', 'attention', 'Update the Python runtime', 'This workspace expects Python 3.11 or newer.', 'settings')
    add('account-access', 'improvement', 'Review account connections',
        'Connect only the accounts you need. Saved API settings and installed apps are not proof of authorized account access.', 'integrations')
    add('coverage', 'improvement', 'Review feature readiness before relying on live data',
        'Provider feeds may be unavailable, and some recovered modules contain demonstrations. Keep unavailable data clearly labelled and verify critical workflows before use.', 'usage')
    return findings


def start(tool_loader):
    global STARTED
    with LOCK:
        if STARTED:
            return
        STARTED = True
        try:
            saved = json.loads(STORE.read_text())
            STATE['enabled'] = saved.get('enabled') is not False
            STATE['history'] = saved.get('history', [])[-40:]
        except (OSError, ValueError, TypeError):
            pass

    def loop():
        while True:
            WAKE.clear()
            with LOCK:
                enabled = STATE['enabled']
                if enabled:
                    STATE['checking'] = True
            if enabled:
                try:
                    findings = inspect(tool_loader)
                    with LOCK:
                        previous = STATE['findings']
                        now = time.time()
                        if findings != previous:
                            STATE['history'].append(dict(at=now, count=len(findings), title='Maintenance findings updated'))
                            STATE['history'] = STATE['history'][-40:]
                        STATE.update(findings=findings, checked_at=now, checking=False, error=None)
                        save()
                except Exception:
                    with LOCK:
                        STATE.update(checking=False, error='The local inspection could not finish. The agent will retry at its next interval.')
            WAKE.wait(INTERVAL)
    threading.Thread(target=loop, name='u1-auto-finder', daemon=True).start()


def configure(payload):
    action = payload.get('action')
    if action not in {'pause', 'resume', 'scan'}:
        raise ValueError('Choose pause, resume or scan')
    with LOCK:
        if action == 'pause':
            STATE['enabled'] = False
        elif action == 'resume':
            STATE['enabled'] = True
        elif not STATE['enabled']:
            raise ValueError('Resume Auto Finder before requesting a check')
        save()
    WAKE.set()
    return dict(success=True, queued=action != 'pause', enabled=STATE['enabled'])
