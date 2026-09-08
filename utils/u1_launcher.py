"""User-facing launcher; never kills a process based only on its port."""
import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
URL = 'http://127.0.0.1:8788'


def status():
    try:
        request = urllib.request.Request(URL + '/api/integrations', headers={'Accept': 'application/json'})
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open(request, timeout=3) as response:
            data = json.load(response)
        if data.get('installation_root') != str(ROOT):
            return {'ready': False, 'reason': 'Port 8788 is not this U1 OS installation.'}
        return {'ready': True, 'url': URL, 'reason': 'This local U1 OS installation is responding. Account access is verified separately.'}
    except Exception:
        return {'ready': False, 'reason': 'The local U1 OS backend is not reachable.'}


def start():
    runtime = ROOT / '.runtime/bin/python3'
    if not runtime.is_file():
        raise RuntimeError('The local Python runtime is missing. Follow INSTALLATION.md; no global packages were installed.')
    result = subprocess.run([str(runtime), str(ROOT / 'launch_u1.py'), '--no-browser'], cwd=ROOT)
    if result.returncode:
        raise RuntimeError('Startup did not complete. Review the local command-center.log.')
    result = status()
    if not result['ready']:
        raise RuntimeError(result['reason'])
    return result


def stop():
    if not status()['ready']:
        raise RuntimeError('Cannot establish ownership of a running U1 OS backend. No process was stopped.')
    try:
        value = (ROOT / '.u1-os.pid').read_text().strip()
        if not value.isdigit() or int(value) < 2:
            raise ValueError('Invalid PID')
        pid = int(value)
        command = subprocess.check_output(['/bin/ps', '-p', str(pid), '-o', 'command='], text=True).strip()
        if str(ROOT / 'server.py') not in command:
            raise ValueError('Process does not match this installation')
    except (OSError, ValueError, subprocess.CalledProcessError):
        raise RuntimeError('The saved process identity cannot be verified. No process was stopped.')
    os.kill(pid, signal.SIGTERM)
    for _ in range(30):
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return {'ready': False, 'reason': 'U1 OS stopped gracefully.'}
        time.sleep(0.1)
    raise RuntimeError('The server is still shutting down. No force-kill was used.')


def open_workspace():
    candidates = (ROOT / 'dist/U1 OS.app', Path.home() / 'Desktop/U1 OS.app')
    target = next((str(path) for path in candidates if (path / 'Contents/MacOS/U1OS').is_file()), URL + '/#home')
    subprocess.run(['/usr/bin/open', target], check=True)


def main(argv=None):
    parser = argparse.ArgumentParser(description='U1 OS local application launcher')
    parser.add_argument('action', nargs='?', default='open', choices=('open', 'start', 'status', 'check', 'stop', 'restart'))
    parser.add_argument('--no-open', action='store_true', help='Start without opening a window')
    parser.add_argument('--json', action='store_true', help='Print machine-readable readiness')
    args = parser.parse_args(argv)
    try:
        if args.action in ('status', 'check'):
            result = status()
        elif args.action == 'stop':
            result = stop()
        else:
            if args.action == 'restart':
                stop()
            result = start()
            if args.action == 'open' and not args.no_open:
                open_workspace()
        print(json.dumps(result) if args.json else result['reason'])
        return 0 if result['ready'] or args.action == 'stop' else 1
    except (RuntimeError, OSError, subprocess.CalledProcessError) as error:
        print(json.dumps({'ready': False, 'reason': str(error)}) if args.json else 'U1 OS: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
