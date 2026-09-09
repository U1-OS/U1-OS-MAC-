"""All subprocesses, native Keychain operations and network calls are mocked."""
import base64
import contextlib
import io
import json
from pathlib import Path
import signal
import struct
import subprocess
import sys
import threading
import time
import unittest
from unittest import mock
import uuid
import zlib

from utils import u1_assistant as assistant
from utils import u1_credentials as credentials
from utils import u1_image_provider as images
import test_u1_assistant as fixture

NATIVE_OPERATION = credentials.operation


def chunk(kind, content):
    return struct.pack('>I', len(content)) + kind + content + struct.pack('>I', zlib.crc32(kind + content) & 0xffffffff)


def png(width=1024, height=1024, pixels=None):
    pixels = pixels if pixels is not None else (b'\0' + b'\xff\0\0' * width) * height
    return b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(pixels)) + chunk(b'IEND', b'')


class ImageResponse:
    def __init__(self, raw, url=images.URL, status=200, content_type='application/json'):
        self.raw, self.url, self.status = raw, url, status
        self.headers = {'Content-Type': content_type}
        self.read_limit = None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass

    def geturl(self):
        return self.url

    def read(self, limit):
        self.read_limit = limit
        return self.raw


class FakeImageProcess:
    def __init__(self, args, kwargs, pid, content, release=None, code=0):
        self.args, self.kwargs, self.pid = args, kwargs, pid
        self.content, self.release, self.code = content, release, code
        self.output = Path(args[-1])
        self.returncode, self.killed, self.inputs, self.communications = None, False, [], 0

    def communicate(self, input=None, timeout=None):
        self.communications += 1
        if input is not None:
            self.inputs.append(input)
        if self.killed:
            self.returncode = -signal.SIGKILL
            return None, None
        if self.release and not self.release.wait(min(timeout or .01, .01)):
            raise subprocess.TimeoutExpired(self.args, timeout)
        self.output.write_bytes(self.content)
        self.returncode = self.code
        return None, None

    def wait(self, timeout=None):
        if self.returncode is None and not self.killed:
            raise subprocess.TimeoutExpired(self.args, timeout)
        self.returncode = -signal.SIGKILL if self.killed else self.returncode
        return self.returncode


class ImageProviderTests(unittest.TestCase):
    patch = fixture.AssistantTests.patch
    close_managers = fixture.AssistantTests.close_managers
    make_manager = fixture.AssistantTests.make_manager
    payload = fixture.AssistantTests.payload
    signal_owned = fixture.AssistantTests.signal_owned
    wait_for = fixture.AssistantTests.wait_for
    terminal = fixture.AssistantTests.terminal

    def setUp(self):
        fixture.AssistantTests.setUp(self)
        self.keychain = self.patch('utils.u1_credentials.operation', side_effect=AssertionError('No real Keychain access'))
        self.ensure = self.patch('utils.u1_credentials.ensure_helper', side_effect=AssertionError('No real compiler'))
        self.ready = self.patch('utils.u1_credentials.ready', return_value=False)
        self.png = png()

    def configured_manager(self, **kwargs):
        manager = self.make_manager(**kwargs)
        assistant._atomic_write(manager.root / 'image-provider.json', assistant._encoded(dict(configured=True, updated_at=0)))
        self.ready.return_value = True
        return manager

    def image_body(self, **kwargs):
        body = dict(action='generate', request_id=uuid.uuid4().hex, prompt='A red abstract illustration.', confirmed_api_billing=True)
        body.update(kwargs)
        return body

    def fake_image_provider(self, *, content=None, release=None, code=0):
        def spawn(args, **kwargs):
            self.assertFalse(any(p.returncode is None for p in self.processes), 'Workers overlapped')
            if args[1] == 'exec':
                process = fixture.FakeProcess(args, kwargs, 60000 + len(self.processes), release)
            else:
                process = FakeImageProcess(args, kwargs, 60000 + len(self.processes), self.png if content is None else content, release, code)
            self.processes.append(process)
            return process
        self.popen.side_effect = spawn

    def response(self, **kwargs):
        raw = kwargs.pop('raw', json.dumps({'data': [{'b64_json': base64.b64encode(self.png).decode()}]}).encode())
        response = ImageResponse(raw, **kwargs)
        opener = mock.Mock()
        opener.open.return_value = response
        return response, opener

    def api_handler(self, manager, handler):
        with mock.patch.object(assistant, 'manager', return_value=manager):
            return images.handle_request(handler)

    def test_status_never_reads_credentials_or_claims_authorisation(self):
        state = images.snapshot(self.make_manager())
        self.assertTrue(state['adapter_installed'])
        self.assertEqual(state['state'], 'setup_needed')
        self.assertFalse(state['ready_to_request'])
        self.assertIsNone(state['authorised'])
        configured = images.snapshot(self.configured_manager())
        self.assertEqual(configured['state'], 'configured_unverified')
        self.assertIsNone(configured['authorised'])
        self.assertTrue(configured['ready_to_request'])
        self.keychain.assert_not_called()
        self.ensure.assert_not_called()
        self.popen.assert_not_called()

    def test_separate_api_billing_confirmation_is_required(self):
        manager = self.configured_manager()
        for confirmed in (None, False, 1, 'true'):
            with self.subTest(confirmed=confirmed), self.assertRaises(assistant.AssistantError):
                images.submit(self.image_body(confirmed_api_billing=confirmed), manager)
        self.popen.assert_not_called()
        self.keychain.assert_not_called()

    def test_unconfigured_generation_is_rejected(self):
        with self.assertRaises(assistant.AssistantError):
            images.submit(self.image_body(), self.make_manager())
        self.popen.assert_not_called()

    def test_model_url_count_and_size_overrides_are_rejected(self):
        manager = self.configured_manager()
        for field, value in [('model', 'other'), ('url', 'https://evil.invalid'), ('n', 10), ('size', '1536x1024'), ('api_key', 'secret')]:
            with self.subTest(field=field), self.assertRaises(assistant.AssistantError):
                images.submit(self.image_body(**{field: value}), manager)

    def test_configure_keeps_only_metadata_on_disk(self):
        manager = self.make_manager()
        key = 'sk-test-' + 'x' * 24
        helper = manager.root / 'credentials' / 'image-keychain'
        self.ensure.side_effect = None
        self.ensure.return_value = helper
        self.keychain.side_effect = None
        self.keychain.return_value = dict(success=True)
        self.ready.return_value = True
        images.configure(dict(action='configure', confirmed=True, api_key=key), manager)
        self.keychain.assert_called_once_with(helper, 'set', dict(api_key=key))
        stored = (manager.root / 'image-provider.json').read_text()
        self.assertNotIn(key, stored)
        self.assertEqual(set(json.loads(stored)), {'configured', 'updated_at'})
        self.assertEqual((manager.root / 'image-provider.json').stat().st_mode & 0o777, 0o600)
        self.popen.assert_not_called()

    def test_safety_blocks_keychain_write(self):
        manager = self.make_manager(safety_check=lambda: True)
        self.ensure.side_effect = None
        self.ensure.return_value = manager.root / 'fake-helper'
        with self.assertRaises(assistant.AssistantError):
            images.configure(dict(action='configure', confirmed=True, api_key='sk-test-' + 'x' * 24), manager)
        self.keychain.assert_not_called()

    def test_active_image_job_blocks_credential_change(self):
        manager = self.configured_manager()
        images.submit(self.image_body(), manager)
        with self.assertRaises(assistant.AssistantError):
            images.configure(dict(action='disconnect', confirmed=True), manager)
        self.keychain.assert_not_called()

    def test_disconnect_uses_image_service_only(self):
        manager = self.configured_manager()
        self.keychain.side_effect = None
        self.keychain.return_value = dict(success=True)
        result = images.configure(dict(action='disconnect', confirmed=True), manager)
        self.keychain.assert_called_once_with(credentials.helper_path(manager.root), 'delete')
        self.assertFalse(result['configured'])
        self.assertNotIn('local.u1os.google.readonly', credentials.SWIFT)
        self.assertIn('local.u1os.openai.images', credentials.SWIFT)

    def test_native_helper_secret_is_stdin_only(self):
        self.run.side_effect = None
        self.run.return_value = mock.Mock(returncode=0, stdout=b'{"success":true}')
        key = 'sk-test-' + 'x' * 24
        with mock.patch.object(credentials, '_trusted_helper', return_value=True):
            NATIVE_OPERATION(self.base / 'mock-helper', 'set', dict(api_key=key))
        args, kwargs = self.run.call_args
        self.assertNotIn(key, str(args))
        self.assertNotIn(key, str(kwargs['env']))
        self.assertIn(key.encode(), kwargs['input'])
        self.assertFalse(kwargs['shell'])
        self.assertEqual(kwargs['stderr'], subprocess.DEVNULL)
        self.assertEqual(kwargs['timeout'], 35)

    def test_valid_png_is_decoded_and_bounded(self):
        info = images.validate_png(self.png)
        self.assertEqual((info['width'], info['height']), (1024, 1024))
        self.assertEqual(info['mime'], 'image/png')
        self.assertEqual(info['bytes'], len(self.png))

    def test_invalid_pngs_and_decompression_bombs_are_rejected(self):
        for content in (b'<svg onload="bad"/>', self.png[:-2], self.png + b'trailing',
                        self.png[:20] + b'\xff' + self.png[21:], png(1, 1),
                        png(pixels=b'\0' * (1024 * 1024 * 8))):
            with self.subTest(length=len(content)), self.assertRaises(ValueError):
                images.validate_png(content)

    def test_official_https_no_redirects_or_inherited_proxies(self):
        response, opener = self.response()
        payload = dict(model=images.MODEL, prompt='A red illustration.', n=1, size='1024x1024', quality='low', output_format='png')
        with mock.patch.object(images.urllib.request, 'build_opener', return_value=opener) as build:
            self.assertEqual(images.request_image(payload, 'sk-test-' + 'x' * 24), self.png)
        request = opener.open.call_args.args[0]
        self.assertEqual(request.full_url, 'https://api.openai.com/v1/images/generations')
        self.assertEqual(request.get_method(), 'POST')
        self.assertEqual(json.loads(request.data), payload)
        self.assertEqual(opener.open.call_args.kwargs['timeout'], 150)
        self.assertEqual(response.read_limit, images.MAX_RESPONSE + 1)
        self.assertEqual(build.call_args.args[0].proxies, {})
        self.assertIsInstance(build.call_args.args[1], images.NoRedirect)
        self.assertIsNone(images.NoRedirect().redirect_request(None, None, 302, None, {}, 'https://evil.invalid'))

    def test_redirect_content_type_status_and_bad_base64_are_rejected(self):
        variants = [dict(url='https://evil.invalid/'), dict(status=302), dict(content_type='image/svg+xml')]
        for data in ({'data': [{'url': 'https://evil.invalid'}]}, {'data': [{'b64_json': '!!!!'}]}, {'data': []}, {'data': [{}, {}]}, [], {'data': ['not an object']}):
            variants.append(dict(raw=json.dumps(data).encode()))
        for values in variants:
            response, opener = self.response(**values)
            with mock.patch.object(images.urllib.request, 'build_opener', return_value=opener), self.assertRaises((ValueError, TypeError)):
                images.request_image({}, 'sk-test-' + 'x' * 24)

    def test_oversized_http_response_rejected(self):
        response, opener = self.response(raw=b'x' * (images.MAX_RESPONSE + 1))
        with mock.patch.object(images.urllib.request, 'build_opener', return_value=opener), self.assertRaises(ValueError):
            images.request_image({}, 'sk-test-' + 'x' * 24)

    def test_image_shared_worker_persists_png_and_evidence(self):
        self.fake_image_provider()
        manager = self.configured_manager(autostart=True)
        result = images.submit(self.image_body(), manager)
        self.terminal(manager)
        job = manager.jobs[0]
        self.assertEqual(job['kind'], 'image')
        self.assertEqual(job['status'], 'succeeded')
        self.assertEqual(job['billing'], 'separate_openai_api')
        self.assertEqual(job['output_bytes'], len(self.png))
        self.assertIsNone(manager.authorised)
        file = manager.root / 'images' / (job['id'] + '.png')
        self.assertEqual(file.read_bytes(), self.png)
        self.assertEqual(file.stat().st_mode & 0o777, 0o600)
        process = self.processes[0]
        self.assertEqual(process.args[1:3], ['-I', '-B'])
        self.assertIn('--worker', process.args)
        self.assertFalse(process.kwargs['shell'])
        self.assertTrue(process.kwargs['start_new_session'])
        self.assertEqual(json.loads(process.inputs[0])['output_format'], 'png')
        state = images.snapshot(manager)
        self.assertTrue(state['authorised'])
        self.assertEqual(state['images'][0]['job_id'], result['job']['id'])
        self.keychain.assert_not_called()

    def test_text_and_image_workers_do_not_overlap(self):
        gate = threading.Event()
        self.fake_image_provider(release=gate)
        manager = self.configured_manager(autostart=True)
        manager.submit(self.payload())
        images.submit(self.image_body(), manager)
        self.wait_for(lambda: len(self.processes) == 1)
        self.assertEqual(manager.jobs[1]['status'], 'queued')
        gate.set()
        self.terminal(manager)
        self.assertEqual(len(self.processes), 2)
        self.assertTrue(all(j['status'] == 'succeeded' for j in manager.jobs))

    def test_duplicate_image_request_is_not_requeued(self):
        manager = self.configured_manager()
        body = self.image_body()
        first, second = images.submit(body, manager), images.submit(body, manager)
        self.assertEqual(first['job']['id'], second['job']['id'])
        self.assertTrue(second['duplicate'])
        self.assertEqual(len(manager.jobs), 1)

    def test_safety_blocks_image_dispatch(self):
        manager = self.configured_manager(autostart=True, safety_check=lambda: True)
        images.submit(self.image_body(), manager)
        self.wait_for(lambda: manager.paused)
        self.assertEqual(manager.jobs[0]['status'], 'queued')
        self.popen.assert_not_called()

    def test_image_cancellation_kills_only_owned_worker(self):
        self.fake_image_provider(release=threading.Event())
        manager = self.configured_manager(autostart=True)
        images.submit(self.image_body(), manager)
        self.wait_for(lambda: self.processes and self.processes[0].communications >= 1)
        manager.cancel()
        self.terminal(manager)
        self.assertEqual(manager.jobs[0]['status'], 'cancelled')
        self.kill.assert_called_once_with(self.processes[0].pid, signal.SIGKILL)
        self.assertEqual(len(self.processes), 1)

    def test_image_failure_does_not_expose_worker_output(self):
        self.fake_image_provider(content=b'PRIVATE_API_KEY_OR_ERROR', code=1)
        manager = self.configured_manager(autostart=True)
        images.submit(self.image_body(), manager)
        self.terminal(manager)
        self.assertEqual(manager.jobs[0]['status'], 'failed')
        self.assertNotIn('PRIVATE_API_KEY_OR_ERROR', json.dumps(manager.snapshot()))

    def test_twenty_image_retention_limit(self):
        manager = self.make_manager()
        for index in range(images.MAX_IMAGES + 2):
            job = dict(id=uuid.uuid4().hex, kind='image', status='succeeded', title=str(index), finished_at=time.time())
            manager.jobs.append(job)
            images.store_result(manager, job, self.png)
        self.assertEqual(len(list((manager.root / 'images').glob('*.png'))), images.MAX_IMAGES)
        self.assertEqual(sum(j['artifact']['available'] for j in manager.jobs), images.MAX_IMAGES)

    def test_worker_main_fixed_payload_no_key_on_disk(self):
        output = self.base / 'result.png'
        output.touch(mode=0o600)
        key = 'sk-test-' + 'x' * 24
        self.keychain.side_effect = None
        self.keychain.return_value = dict(api_key=key)
        stdin = mock.Mock(buffer=io.BytesIO(json.dumps(dict(prompt='Selected prompt', model='override')).encode()))
        with mock.patch.object(sys, 'argv', ['worker', '--worker', str(self.base / 'helper'), str(output)]), mock.patch.object(sys, 'stdin', stdin), mock.patch.object(images, 'request_image', return_value=self.png) as call:
            self.assertEqual(images.worker_main(), 0)
        payload, passed_key = call.call_args.args
        self.assertEqual(payload['model'], 'gpt-image-1.5')
        self.assertEqual(payload['n'], 1)
        self.assertEqual(payload['quality'], 'low')
        self.assertEqual(passed_key, key)
        self.assertNotIn(key.encode(), output.read_bytes())

    def test_worker_failure_prints_no_details(self):
        self.keychain.side_effect = ValueError('PRIVATE_KEYCHAIN_DETAIL')
        stdin = mock.Mock(buffer=io.BytesIO(b'{"prompt":"A reviewed prompt"}'))
        stdout, stderr = io.StringIO(), io.StringIO()
        with mock.patch.object(sys, 'argv', ['worker', '--worker', str(self.base / 'helper'), str(self.base / 'output')]), mock.patch.object(sys, 'stdin', stdin), contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            self.assertEqual(images.worker_main(), 1)
        self.assertEqual(stdout.getvalue() + stderr.getvalue(), '')

    def test_origin_csrf_and_exact_route(self):
        manager = self.make_manager()
        handler = fixture.Handler(path='/api/workspace/image-provider/other')
        self.assertFalse(self.api_handler(manager, handler))
        for method in ('GET', 'POST'):
            handler = fixture.Handler(method=method, path='/api/workspace/image-provider', allowed=False)
            self.api_handler(manager, handler)
            self.assertEqual(handler.status, 403)
        handler = fixture.Handler(method='POST', path='/api/workspace/image-provider', body=self.image_body())
        handler.headers['X-U1-CSRF'] = 'invalid'
        self.api_handler(manager, handler)
        self.assertEqual(handler.status, 403)
        self.assertEqual(handler.rfile.tell(), 0)
        self.keychain.assert_not_called()

    def test_binary_endpoint_private_headers_and_identifier(self):
        self.fake_image_provider()
        manager = self.configured_manager(autostart=True)
        result = images.submit(self.image_body(), manager)
        self.terminal(manager)
        handler = fixture.Handler(path='/api/workspace/image-provider?image_id=' + result['job']['id'])
        self.api_handler(manager, handler)
        self.assertEqual(handler.status, 200)
        self.assertEqual(handler.wfile.getvalue(), self.png)
        self.assertEqual(handler.response_headers['Content-Type'], 'image/png')
        self.assertEqual(handler.response_headers['Cache-Control'], 'no-store')
        self.assertEqual(handler.response_headers['X-Content-Type-Options'], 'nosniff')
        handler = fixture.Handler(path='/api/workspace/image-provider?image_id=../../secret')
        self.api_handler(manager, handler)
        self.assertEqual(handler.status, 400)

    def test_http_generate_and_generic_credential_failures(self):
        manager = self.configured_manager()
        handler = fixture.Handler(method='POST', path='/api/workspace/image-provider', body=self.image_body())
        self.api_handler(manager, handler)
        self.assertEqual(handler.status, 202)
        self.assertEqual(handler.result()['job']['kind'], 'image')
        self.popen.assert_not_called()
        manager.cancel()
        self.ensure.side_effect = ValueError('PRIVATE_COMPILER_OR_CREDENTIAL_DETAIL')
        handler = fixture.Handler(method='POST', path='/api/workspace/image-provider', body=dict(action='configure', confirmed=True, api_key='sk-test-' + 'x' * 24))
        self.api_handler(manager, handler)
        self.assertEqual(handler.status, 503)
        self.assertNotIn('PRIVATE_COMPILER_OR_CREDENTIAL_DETAIL', handler.wfile.getvalue().decode())


if __name__ == '__main__':
    unittest.main()
