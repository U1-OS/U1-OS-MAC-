"""No provider calls: every subprocess, process-group signal and network entry is mocked."""
import io
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import tempfile
import threading
import time
import unittest
from unittest import mock
import uuid

from utils import integrations_hub
from utils import u1_assistant as assistant


class Handler:
    def __init__(self, method='GET', path='/api/workspace/assistant', body=None, allowed=True):
        self.command, self.path, self.allowed = method, path, allowed
        raw = json.dumps(body or {}).encode()
        self.headers = {'Content-Type': 'application/json', 'Content-Length': str(len(raw)),
                        'X-U1-CSRF': integrations_hub.CSRF_TOKEN}
        self.rfile, self.wfile = io.BytesIO(raw), io.BytesIO()
        self.response_headers = {}
        self.status = None

    def integration_request_allowed(self):
        return self.allowed

    def send_response(self, status):
        self.status = status

    def send_header(self, name, value):
        self.response_headers[name] = value

    def end_headers(self):
        pass

    def result(self):
        return json.loads(self.wfile.getvalue())


class FakeProcess:
    def __init__(self, args, kwargs, pid, release=None, answer='A real mocked response.', code=0):
        self.args, self.kwargs, self.pid = args, kwargs, pid
        self.release, self.answer, self.code = release, answer, code
        self.returncode = None
        self.output = Path(args[args.index('--output-last-message') + 1])
        self.killed = False
        self.inputs = []
        self.communications = 0

    def communicate(self, input=None, timeout=None):
        self.communications += 1
        if input is not None:
            self.inputs.append(input)
        if self.killed:
            self.returncode = -signal.SIGKILL
            return None, None
        if self.release and not self.release.wait(min(timeout or .01, .01)):
            raise subprocess.TimeoutExpired(self.args, timeout)
        self.output.write_text(self.answer, encoding='utf-8')
        self.returncode = self.code
        return None, None

    def wait(self, timeout=None):
        if self.returncode is None and not self.killed:
            raise subprocess.TimeoutExpired(self.args, timeout)
        self.returncode = -signal.SIGKILL if self.killed else self.returncode
        return self.returncode


class AssistantTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='u1-assistant-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.codex = self.base / 'codex-test-placeholder'
        self.codex.write_text('Never executed. All subprocess calls are mocked.\n')
        self.codex.chmod(0o700)
        self.processes = []
        self.managers = []
        self.popen = self.patch('subprocess.Popen', side_effect=AssertionError('Unmocked provider invocation'))
        self.run = self.patch('subprocess.run', side_effect=AssertionError('No subprocess.run allowed'))
        self.patch('os.system', side_effect=AssertionError('No shell allowed'))
        self.patch('socket.socket', side_effect=AssertionError('No network allowed'))
        self.patch('socket.create_connection', side_effect=AssertionError('No network allowed'))
        self.patch('urllib.request.urlopen', side_effect=AssertionError('No network allowed'))
        self.kill = self.patch('os.killpg', side_effect=self.signal_owned)
        self.addCleanup(self.close_managers)

    def patch(self, name, **kwargs):
        patcher = mock.patch(name, **kwargs)
        result = patcher.start()
        self.addCleanup(patcher.stop)
        return result

    def close_managers(self):
        for manager in self.managers:
            manager.close()

    def make_manager(self, **kwargs):
        options = dict(codex=self.codex, autostart=False, safety_check=lambda: False)
        options.update(kwargs)
        manager = assistant.AssistantManager(self.base / ('manager-' + str(len(self.managers))), **options)
        self.managers.append(manager)
        return manager

    def payload(self, **kwargs):
        body = dict(action='send', prompt='Draft an outline from only my selected text.',
                    role='Creator', context=[], confirmed=True, request_id=uuid.uuid4().hex)
        body.update(kwargs)
        return body

    def fake_provider(self, *, release=None, answer='A real mocked response.', code=0):
        def spawn(args, **kwargs):
            self.assertFalse(any(p.returncode is None for p in self.processes), 'More than one provider process started')
            process = FakeProcess(args, kwargs, 50000 + len(self.processes), release, answer, code)
            self.processes.append(process)
            return process
        self.popen.side_effect = spawn

    def signal_owned(self, pid, sig):
        self.assertEqual(sig, signal.SIGKILL)
        matches = [p for p in self.processes if p.pid == pid and p.returncode is None]
        self.assertEqual(len(matches), 1, 'Signal must target exactly one unreaped owned child group')
        matches[0].killed = True

    def wait_for(self, predicate, timeout=3):
        until = time.monotonic() + timeout
        while time.monotonic() < until:
            if predicate():
                return
            threading.Event().wait(.005)
        self.fail('Mocked worker did not reach the expected state')

    def terminal(self, manager):
        self.wait_for(lambda: manager.jobs and all(j['status'] not in assistant.ACTIVE for j in manager.jobs))

    def handle(self, manager, handler):
        with mock.patch.object(assistant, 'manager', return_value=manager):
            handled = assistant.handle_request(handler)
        return handled

    def test_installed_is_not_authorised_and_status_never_calls_provider(self):
        manager = self.make_manager()
        provider = manager.snapshot()['provider']
        self.assertTrue(provider['installed'])
        self.assertIsNone(provider['authorised'])
        self.assertEqual(provider['auth_state'], 'unverified')
        self.assertEqual(provider['image_state'], 'separate_api_adapter')
        self.assertFalse(provider['images_available'])
        self.popen.assert_not_called()
        self.run.assert_not_called()

    def test_no_confirmation_no_invocation(self):
        manager = self.make_manager()
        for value in (False, 1, 'true', None):
            with self.subTest(value=value), self.assertRaises(assistant.AssistantError):
                manager.submit(self.payload(confirmed=value))
        self.assertEqual(manager.jobs, [])
        self.popen.assert_not_called()

    def test_validation_bounds_text_and_context(self):
        manager = self.make_manager()
        variants = [dict(prompt=''), dict(prompt='x' * (assistant.MAX_PROMPT + 1)),
                    dict(prompt='\U0001f600' * 2001), dict(prompt='\ud800'),
                    dict(prompt='no\x00'), dict(role='Executor'), dict(role=[]),
                    dict(request_id='../../auth.json'), dict(context='a file'),
                    dict(context=[dict(label='note', text='x')] * 9),
                    dict(context=[dict(label='note', text='x' * 9000)] * 2),
                    dict(context=[dict(label='file', text='x', path='/private/secret')])]
        for values in variants:
            with self.subTest(values=list(values)), self.assertRaises(assistant.AssistantError):
                manager.submit(self.payload(**values))
        self.assertEqual(manager.jobs, [])
        self.popen.assert_not_called()

    def test_missing_cli_rejected_without_auth_guess(self):
        manager = self.make_manager(codex=self.base / 'missing')
        self.assertFalse(manager.provider_status()['installed'])
        with self.assertRaises(assistant.AssistantError):
            manager.submit(self.payload())
        self.popen.assert_not_called()

    def test_idempotent_send_and_conflicting_reuse(self):
        manager = self.make_manager()
        body = self.payload()
        first, second = manager.submit(body), manager.submit(body)
        self.assertEqual(first['job']['id'], second['job']['id'])
        self.assertTrue(second['duplicate'])
        self.assertEqual(len(manager.jobs), 1)
        self.assertEqual(len(manager.conversations[0]['messages']), 1)
        with self.assertRaises(assistant.AssistantError):
            manager.submit(dict(body, prompt='A different request'))

    def test_queue_limit_and_serial_conversation(self):
        manager = self.make_manager()
        first = manager.submit(self.payload())
        with self.assertRaises(assistant.AssistantError):
            manager.submit(self.payload(conversation_id=first['conversation_id']))
        for _ in range(assistant.MAX_PENDING - 1):
            manager.submit(self.payload())
        with self.assertRaises(assistant.AssistantError):
            manager.submit(self.payload())

    def test_secure_command_and_clean_environment(self):
        self.fake_provider()
        with mock.patch.dict(os.environ, {'OPENAI_API_KEY': 'do-not-inherit', 'NODE_OPTIONS': '--require=evil',
                                         'CODEX_THREAD_ID': 'no', 'HTTP_PROXY': 'http://no', 'PATH': '/untrusted'}):
            manager = self.make_manager(autostart=True)
            result = manager.submit(self.payload(prompt='Private selected prompt', context=[dict(label='My note', text='Selected note text')]))
            self.terminal(manager)
        process = self.processes[0]
        args, options = process.args, process.kwargs
        for flag in ('--ephemeral', '--ignore-user-config', '--ignore-rules', '--skip-git-repo-check'):
            self.assertIn(flag, args)
        for setting in ('approval_policy="never"', 'forced_login_method="chatgpt"',
                        'features.shell_tool=false', 'features.unified_exec=false', 'features.hooks=false',
                        'features.apps=false', 'features.multi_agent=false', 'project_doc_max_bytes=0',
                        'mcp_servers={}', 'plugins={}', 'web_search="disabled"'):
            self.assertIn(setting, args)
        self.assertEqual(args[args.index('--sandbox') + 1], 'read-only')
        self.assertEqual(args[-1], '-')
        self.assertFalse(options['shell'])
        self.assertTrue(options['start_new_session'])
        self.assertTrue(options['close_fds'])
        self.assertEqual(options['umask'], 0o077)
        self.assertEqual(options['stdout'], subprocess.DEVNULL)
        self.assertEqual(options['stderr'], subprocess.DEVNULL)
        self.assertNotIn('Private selected prompt', ' '.join(args))
        self.assertNotIn('Selected note text', ' '.join(args))
        self.assertNotIn('OPENAI_API_KEY', options['env'])
        self.assertNotIn('NODE_OPTIONS', options['env'])
        self.assertNotIn('CODEX_THREAD_ID', options['env'])
        self.assertNotIn('HTTP_PROXY', options['env'])
        self.assertNotEqual(options['env']['PATH'], '/untrusted')
        self.assertEqual(options['env']['CODEX_HOME'], manager.codex_home)
        self.assertTrue(str(options['cwd']).startswith(str(manager.runs)))
        packed = json.loads(process.inputs[0])
        self.assertEqual(packed['selected_context'], [dict(label='My note', text='Selected note text')])
        self.assertEqual(packed['history'], [])
        self.assertEqual(manager.jobs[0]['status'], 'succeeded')
        self.assertTrue(manager.provider_status()['authorised'])
        self.assertEqual(manager.snapshot(result['conversation_id'])['conversation']['messages'][-1]['text'], 'A real mocked response.')

    def test_only_one_process_runs_and_pause_controls_dispatch(self):
        gate = threading.Event()
        self.fake_provider(release=gate)
        manager = self.make_manager(autostart=True)
        manager.pause()
        manager.submit(self.payload())
        manager.submit(self.payload())
        self.assertEqual(len(self.processes), 0)
        manager.pause(False)
        self.wait_for(lambda: len(self.processes) == 1)
        manager.pause(True)
        self.assertFalse(self.processes[0].killed)
        gate.set()
        self.wait_for(lambda: manager.jobs[0]['status'] == 'succeeded')
        self.assertEqual(manager.jobs[1]['status'], 'queued')
        self.assertEqual(len(self.processes), 1)
        manager.pause(False)
        self.terminal(manager)
        self.assertEqual(len(self.processes), 2)

    def test_queued_cancel_does_not_signal_any_process(self):
        manager = self.make_manager()
        job = manager.submit(self.payload())['job']
        manager.cancel(job['id'])
        self.assertEqual(manager.jobs[0]['status'], 'cancelled')
        self.assertIsNone(manager.jobs[0]['started_at'])
        self.kill.assert_not_called()
        self.popen.assert_not_called()

    def test_running_cancel_kills_only_owned_group_and_never_resends_stdin(self):
        self.fake_provider(release=threading.Event())
        manager = self.make_manager(autostart=True)
        manager.submit(self.payload())
        self.wait_for(lambda: self.processes and self.processes[0].communications >= 2)
        manager.cancel()
        self.terminal(manager)
        self.kill.assert_called_once_with(self.processes[0].pid, signal.SIGKILL)
        self.assertEqual(manager.jobs[0]['status'], 'cancelled')
        self.assertEqual(len(self.processes[0].inputs), 1)
        self.assertEqual(len(manager.conversations[0]['messages']), 1)

    def test_timeout_reaps_owned_child(self):
        self.fake_provider(release=threading.Event())
        manager = self.make_manager(autostart=True, timeout=.04)
        manager.submit(self.payload())
        self.terminal(manager)
        self.assertEqual(manager.jobs[0]['status'], 'timed_out')
        self.assertTrue(self.processes[0].killed)
        self.assertIsNotNone(self.processes[0].returncode)

    def test_safety_checks_do_not_hold_assistant_mutex(self):
        self.fake_provider()
        manager = self.make_manager(autostart=True)
        checked = []
        def safety():
            self.assertFalse(manager.condition._is_owned())
            checked.append(True)
            return False
        manager.safety_check = safety
        manager.submit(self.payload())
        self.terminal(manager)
        self.assertGreaterEqual(len(checked), 2)

    def test_safety_blocks_dispatch_and_preserves_queue(self):
        blocked = threading.Event()
        blocked.set()
        manager = self.make_manager(autostart=True, safety_check=blocked.is_set)
        manager.submit(self.payload())
        self.wait_for(lambda: manager.paused)
        self.assertEqual(manager.jobs[0]['status'], 'queued')
        self.popen.assert_not_called()
        self.fake_provider()
        blocked.clear()
        manager.pause(False)
        self.terminal(manager)
        self.assertEqual(manager.jobs[0]['status'], 'succeeded')

    def test_safety_rechecked_before_process_launch(self):
        values = iter([False, True])
        manager = self.make_manager(autostart=True, safety_check=lambda: next(values))
        manager.submit(self.payload())
        self.terminal(manager)
        self.assertEqual(manager.jobs[0]['status'], 'cancelled')
        self.assertTrue(manager.paused)
        self.assertIsNone(manager.jobs[0]['started_at'])
        self.popen.assert_not_called()

    def test_default_safety_failure_is_closed(self):
        with mock.patch.dict('sys.modules', {'utils.u1_safety': None}):
            self.assertTrue(assistant._safety_blocked())

    def test_output_and_provider_failures_are_generic(self):
        self.fake_provider(code=1, answer='PRIVATE_PROVIDER_ERROR_OR_TOKEN')
        manager = self.make_manager(autostart=True)
        manager.submit(self.payload())
        self.terminal(manager)
        self.assertEqual(manager.jobs[0]['status'], 'failed')
        self.assertNotIn('PRIVATE_PROVIDER_ERROR_OR_TOKEN', json.dumps(manager.snapshot()))
        self.assertNotIn('PRIVATE_PROVIDER_ERROR_OR_TOKEN', manager.state_file.read_text())
        self.assertEqual(list(manager.runs.iterdir()), [])

    def test_oversized_output_is_not_stored(self):
        self.fake_provider(answer='x' * (assistant.MAX_OUTPUT + 1))
        manager = self.make_manager(autostart=True)
        manager.submit(self.payload())
        self.terminal(manager)
        self.assertEqual(manager.jobs[0]['status'], 'failed')
        self.assertEqual(len(manager.conversations[0]['messages']), 1)
        self.assertEqual(manager.jobs[0]['output_bytes'], 0)

    def test_empty_output_is_not_success(self):
        self.fake_provider(answer='  ')
        manager = self.make_manager(autostart=True)
        manager.submit(self.payload())
        self.terminal(manager)
        self.assertEqual(manager.jobs[0]['status'], 'failed')
        self.assertIsNone(manager.provider_status()['authorised'])

    def test_spawn_failure_never_exposes_exception(self):
        self.popen.side_effect = OSError('PRIVATE_LOCAL_PATH_OR_SECRET')
        manager = self.make_manager(autostart=True)
        manager.submit(self.payload())
        self.terminal(manager)
        self.assertNotIn('PRIVATE_LOCAL_PATH_OR_SECRET', json.dumps(manager.snapshot()))
        self.assertEqual(manager.jobs[0]['status'], 'failed')

    def test_state_and_run_directories_are_owner_only(self):
        manager = self.make_manager()
        manager.submit(self.payload())
        for directory in (manager.root, manager.runs):
            self.assertEqual(directory.stat().st_mode & 0o777, 0o700)
        self.assertEqual(manager.state_file.stat().st_mode & 0o777, 0o600)

    def test_symlink_directory_and_state_rejected(self):
        outside = self.base / 'outside'
        outside.mkdir()
        linked = self.base / 'linked'
        linked.symlink_to(outside, target_is_directory=True)
        with self.assertRaises(OSError):
            assistant.AssistantManager(linked, codex=self.codex)
        manager = self.make_manager()
        target = self.base / 'secret'
        target.write_text('DO_NOT_READ')
        manager.state_file.symlink_to(target)
        with self.assertRaises(OSError):
            assistant._private_read(manager.state_file, assistant.MAX_STATE)
        self.assertEqual(target.read_text(), 'DO_NOT_READ')

    def test_durable_acceptance_failure_prevents_launch(self):
        manager = self.make_manager(autostart=True)
        with mock.patch.object(manager, '_save', side_effect=OSError('SECRET')):
            with self.assertRaises(assistant.AssistantError):
                manager.submit(self.payload())
        self.assertEqual(manager.jobs, [])
        self.assertEqual(manager.conversations, [])
        self.popen.assert_not_called()

    def test_restart_interrupts_pending_requests_without_retry(self):
        manager = self.make_manager()
        manager.submit(self.payload())
        restored = assistant.AssistantManager(manager.root, codex=self.codex, autostart=False, safety_check=lambda: False)
        self.managers.append(restored)
        self.assertEqual(restored.jobs[0]['status'], 'interrupted')
        self.assertTrue(restored.paused)
        self.assertEqual(restored.payloads, {})
        self.popen.assert_not_called()

    def test_retention_is_bounded(self):
        manager = self.make_manager()
        for _ in range(assistant.MAX_JOBS + 5):
            manager.submit(self.payload())
            manager.cancel()
        self.assertEqual(len(manager.jobs), assistant.MAX_JOBS)
        self.assertEqual(len(manager.conversations), assistant.MAX_CONVERSATIONS)
        self.assertLess(manager.state_file.stat().st_size, assistant.MAX_STATE)

    def test_history_includes_completed_turns_but_no_automatic_context_reselection(self):
        self.fake_provider()
        manager = self.make_manager(autostart=True)
        result = manager.submit(self.payload(context=[dict(label='Selected note', text='Original note context')]))
        self.terminal(manager)
        manager.submit(self.payload(conversation_id=result['conversation_id'], prompt='Continue this outline.'))
        self.terminal(manager)
        packed = json.loads(self.processes[-1].inputs[0])
        self.assertEqual(len(packed['history']), 2)
        self.assertEqual(packed['selected_context'], [])
        self.assertNotIn('Original note context', json.dumps(packed))

    def test_delete_requires_confirmation_and_no_active_job(self):
        manager = self.make_manager()
        result = manager.submit(self.payload())
        with self.assertRaises(assistant.AssistantError):
            manager.delete_conversation(result['conversation_id'], True)
        manager.cancel()
        with self.assertRaises(assistant.AssistantError):
            manager.delete_conversation(result['conversation_id'])
        manager.delete_conversation(result['conversation_id'], True)
        self.assertEqual(manager.conversations, [])
        self.assertEqual(len(manager.jobs), 1)

    def test_unowned_route_is_not_handled(self):
        handler = Handler(path='/api/workspace/assistant/other')
        with mock.patch.object(assistant, 'manager') as factory:
            self.assertFalse(assistant.handle_request(handler))
            factory.assert_not_called()
        self.assertIsNone(handler.status)

    def test_same_origin_required_before_accessing_manager(self):
        for method in ('GET', 'POST'):
            handler = Handler(method=method, allowed=False)
            with mock.patch.object(assistant, 'manager') as factory:
                self.assertTrue(assistant.handle_request(handler))
                factory.assert_not_called()
            self.assertEqual(handler.status, 403)

    def test_csrf_required_and_no_body_read_on_rejection(self):
        handler = Handler(method='POST', body=self.payload())
        handler.headers['X-U1-CSRF'] = 'invalid'
        with mock.patch.object(assistant, 'manager') as factory:
            assistant.handle_request(handler)
            factory.assert_not_called()
        self.assertEqual(handler.status, 403)
        self.assertEqual(handler.rfile.tell(), 0)

    def test_get_contract_and_private_response_headers(self):
        manager = self.make_manager()
        for path in ('/api/workspace/assistant', '/api/workspace/jobs'):
            handler = Handler(path=path)
            self.assertTrue(self.handle(manager, handler))
            self.assertEqual(handler.status, 200)
            self.assertEqual(handler.result()['jobs'], [])
            self.assertFalse(handler.result()['paused'])
            self.assertEqual(handler.response_headers['Cache-Control'], 'no-store')
            self.assertEqual(handler.response_headers['X-Content-Type-Options'], 'nosniff')
            self.assertNotIn('Access-Control-Allow-Origin', handler.response_headers)
        self.popen.assert_not_called()

    def test_send_and_job_action_endpoint_contracts(self):
        manager = self.make_manager()
        handler = Handler(method='POST', body=self.payload())
        self.handle(manager, handler)
        self.assertEqual(handler.status, 202)
        self.assertEqual(handler.result()['job']['status'], 'queued')
        for payload in (dict(action='pause', paused=True), dict(action='cancel_all'), dict(action='pause', paused=False)):
            handler = Handler(method='POST', path='/api/workspace/jobs', body=payload)
            self.handle(manager, handler)
            self.assertEqual(handler.status, 200)
        self.assertEqual(manager.jobs[0]['status'], 'cancelled')

    def test_invalid_api_requests_are_bounded_and_generic(self):
        manager = self.make_manager()
        variants = [('Content-Length', '-1', 413), ('Content-Length', str(assistant.MAX_BODY + 1), 413),
                    ('Content-Length', 'not-a-number', 400), ('Content-Type', 'text/plain', 415),
                    ('Transfer-Encoding', 'chunked', 400)]
        for header, value, expected in variants:
            handler = Handler(method='POST', body=self.payload())
            handler.headers[header] = value
            self.handle(manager, handler)
            self.assertEqual(handler.status, expected)
            self.assertEqual(handler.rfile.tell(), 0)
        handler = Handler(method='POST')
        handler.rfile = io.BytesIO(b'[]')
        self.handle(manager, handler)
        self.assertEqual(handler.status, 400)
        self.popen.assert_not_called()

    def test_pause_type_and_cancel_identifier_fail_closed(self):
        manager = self.make_manager()
        for body in (dict(action='pause', paused='false'), dict(action='pause', paused=1), dict(action='cancel')):
            handler = Handler(method='POST', path='/api/workspace/jobs', body=body)
            self.handle(manager, handler)
            self.assertEqual(handler.status, 400)

    def test_internal_error_is_not_exposed(self):
        handler = Handler()
        with mock.patch.object(assistant, 'manager', side_effect=OSError('SECRET_TOKEN')):
            assistant.handle_request(handler)
        self.assertEqual(handler.status, 503)
        self.assertNotIn('SECRET_TOKEN', handler.wfile.getvalue().decode())

    def test_exported_parent_helpers(self):
        manager = self.make_manager()
        manager.submit(self.payload())
        with mock.patch.object(assistant, 'manager', return_value=manager):
            self.assertTrue(assistant.pause()['paused'])
            self.assertEqual(assistant.cancel_all()['jobs'][0]['status'], 'cancelled')
            self.assertEqual(assistant.snapshot()['jobs'][0]['status'], 'cancelled')
            self.assertFalse(assistant.pause(False)['paused'])


if __name__ == '__main__':
    unittest.main()
