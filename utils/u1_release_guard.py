"""Reviewed, pinned fast-forward updates with a managed-data checkpoint.

Preparation and application are separate, explicit background jobs. No reset,
stash, dependency installation, provider login or automatic rollback occurs.
"""
import copy
import os
from pathlib import Path
import re
import subprocess
import threading
import time
import uuid

from utils import u1_recovery


class ReleaseGuard:
    def __init__(self, root):
        self.root = Path(root)
        self.lock = threading.RLock()
        self.job = None
        self.plan = None

    def git(self, *args, timeout=30):
        result = subprocess.run(
            ['git', '-c', 'core.hooksPath=/dev/null', *args], cwd=self.root,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
            timeout=timeout, env={**os.environ, 'GIT_TERMINAL_PROMPT': '0'}
        )
        if result.returncode:
            raise ValueError('The Git operation could not complete. No forced recovery was attempted.')
        return result.stdout.strip()

    def identity(self):
        branch = self.git('branch', '--show-current')
        if not branch or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._/-]{0,180}', branch):
            raise ValueError('Choose a named, supported branch before updating.')
        self.git('check-ref-format', 'refs/heads/' + branch)
        remote = self.git('remote', 'get-url', 'origin')
        allowed = {'https://github.com/U1-OS/U1-OS-MAC-.git',
                   'https://github.com/U1-OS/U1-OS-MAC-',
                   'git@github.com:U1-OS/U1-OS-MAC-.git'}
        if remote not in allowed:
            raise ValueError('The update remote is not the approved U1 OS repository.')
        if self.git('status', '--porcelain'):
            raise ValueError('The checkout has local changes. Commit or preserve them before preparing an update.')
        head = self.git('rev-parse', '--verify', 'HEAD')
        if not re.fullmatch(r'[0-9a-f]{40,64}', head):
            raise ValueError('The installed commit could not be identified.')
        return branch, head

    def snapshot(self):
        with self.lock:
            plan = copy.deepcopy(self.plan)
            if plan:
                plan['expired'] = time.time() >= plan['expires']
            return {'job': copy.deepcopy(self.job), 'plan': plan,
                    'notice': 'Reviewed fast-forward only. Managed backup excludes credentials and other plugin stores. Rollback is not automatic.'}

    def _prepare(self):
        branch, base = self.identity()
        self.git('fetch', '--quiet', '--no-tags', 'origin',
                 'refs/heads/' + branch + ':refs/remotes/origin/' + branch, timeout=60)
        target = self.git('rev-parse', '--verify', 'refs/remotes/origin/' + branch)
        if not re.fullmatch(r'[0-9a-f]{40,64}', target):
            raise ValueError('The remote commit could not be identified.')
        if target == base:
            return {'current': True, 'message': 'This branch already matches the checked remote commit.'}
        self.git('merge-base', '--is-ancestor', base, target)
        changes = self.git('log', '--max-count=20', '--format=%h %s', base + '..' + target).splitlines()
        backup = u1_recovery.make_backup()
        archive = u1_recovery.ROOT / 'backups' / (backup['backup_id'] + '.zip')
        checksum, _ = u1_recovery.digest_file(archive)
        if self.identity() != (branch, base):
            raise ValueError('The checkout changed during preparation. The backup was retained; prepare again.')
        identifier = uuid.uuid4().hex
        rollback_ref = 'refs/u1/checkpoints/' + identifier
        self.git('update-ref', rollback_ref, base)
        plan = {'id': identifier, 'branch': branch, 'from_commit': base,
                'to_commit': target, 'backup_id': backup['backup_id'],
                'backup_sha256': checksum, 'checkpoint_ref': rollback_ref,
                'created': time.time(), 'expires': time.time() + 900,
                'changes': changes, 'applied': False,
                'source': 'Configured U1-OS/U1-OS-MAC- GitHub branch',
                'signature_verified': False}
        with self.lock:
            self.plan = plan
        return {'message': 'Checkpoint prepared. Review the exact target and confirm Apply separately.', 'plan_id': identifier}

    def _apply(self, body):
        with self.lock:
            plan = copy.deepcopy(self.plan)
        if not plan or body.get('plan_id') != plan['id'] or body.get('expected_commit') != plan['to_commit']:
            raise ValueError('Prepare and review an exact update target before applying it.')
        if plan['applied'] or time.time() >= plan['expires']:
            raise ValueError('This update plan is used or expired. Prepare a fresh checkpoint.')
        if self.identity() != (plan['branch'], plan['from_commit']):
            raise ValueError('The installed branch or commit changed. Prepare the update again.')
        target = self.git('rev-parse', '--verify', 'refs/remotes/origin/' + plan['branch'])
        if target != plan['to_commit']:
            raise ValueError('The reviewed remote target changed. A new review is required.')
        self.git('merge-base', '--is-ancestor', plan['from_commit'], target)
        archive = u1_recovery.ROOT / 'backups' / (plan['backup_id'] + '.zip')
        checksum, _ = u1_recovery.digest_file(archive)
        if checksum != plan['backup_sha256']:
            raise ValueError('The checkpoint archive changed. No update was applied.')
        if self.identity() != (plan['branch'], plan['from_commit']):
            raise ValueError('The checkout changed while checking its backup. Prepare again.')
        self.git('merge', '--ff-only', '--no-edit', '--no-stat', target, timeout=90)
        actual = self.git('rev-parse', '--verify', 'HEAD')
        if actual != target:
            raise ValueError('The resulting commit did not match the reviewed target. Stop and inspect the checkout.')
        with self.lock:
            self.plan['applied'] = True
        return {'message': 'The reviewed update was applied. Restart explicitly to load it.',
                'from_commit': plan['from_commit'], 'to_commit': actual,
                'restart_required': True, 'backup_id': plan['backup_id'],
                'checkpoint_ref': plan['checkpoint_ref']}

    def run(self, action, body):
        if body.get('confirmed') is not True:
            return {'success': False, 'error': 'confirmation_required',
                    'message': 'Review the update and backup scope before continuing.'}
        if action not in {'prepare', 'apply'}:
            return {'success': False, 'error': 'unsupported_action'}
        with self.lock:
            if self.job and self.job['status'] == 'running':
                return {'success': False, 'error': 'update_busy', 'message': 'Wait for the current update job.'}
            if action == 'prepare':
                self.plan = None
            job = {'id': uuid.uuid4().hex, 'action': action, 'status': 'running', 'started': time.time()}
            self.job = job
        def worker():
            try:
                result = self._prepare() if action == 'prepare' else self._apply(dict(body))
                with self.lock:
                    job.update(status='complete', result=result, finished=time.time())
            except Exception as error:
                message = str(error) if isinstance(error, ValueError) else 'Update preparation or application failed. Inspect the checkpoint; no forced reset was run.'
                with self.lock:
                    job.update(status='failed', error=message, finished=time.time())
        threading.Thread(target=worker, name='u1-reviewed-update', daemon=True).start()
        return {'success': True, 'job_id': job['id'], 'message': 'Update job started. Completion is reported separately.'}
