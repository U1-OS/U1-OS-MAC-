"""Isolated local fixtures only. No real user files, accounts, subprocesses or network."""
import base64
import io
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
import wave
from unittest.mock import Mock, patch

from utils import u1_media_research as mr


class ResearchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data_patch = patch.object(mr.workspace, 'DATA', Path(self.temp.name) / 'prism')
        self.data_patch.start()
        self.addCleanup(self.data_patch.stop)
        self.network = patch('urllib.request.urlopen', side_effect=AssertionError('Network is forbidden in these tests'))
        self.network.start()
        self.addCleanup(self.network.stop)

    def case(self, title='Public domain research'):
        return mr.action(dict(action='case_save', title=title, scope='public', notes='A question, not a dossier.', authorised_confirmed=True))

    def evidence(self, case_id, **extra):
        body = dict(action='evidence_save', case_id=case_id, title='Published statement',
                    source_url='https://example.org/source', note='Observed a public statement.',
                    observed_at='2026-09-08T10:30:00+10:00', label='unverified')
        body.update(extra)
        return mr.action(body)

    def upload(self, name='sample.wav', content=b'RIFF-local-test-fixture', mime='audio/wav'):
        start = mr.workspace.handle_post('prism/upload-start', dict(name=name, size=len(content), mime=mime, folder='Media'))
        mr.workspace.handle_post('prism/upload-chunk', dict(id=start['id'], offset=0, content=base64.b64encode(content).decode()))
        return start['id']

    def test_case_crud_persists_and_does_not_use_general_records(self):
        created = self.case()
        changed = mr.action(dict(action='case_save', id=created['id'], expected_updated=created['updated_at'],
                                 title='Revised research', scope='authorised', notes='Updated', authorised_confirmed=True))
        self.assertEqual(mr.case_detail(created['id'])['case']['title'], 'Revised research')
        with mr.workspace.database() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM records').fetchone()[0], 0)
        mr.action(dict(action='case_delete', id=created['id'], expected_updated=changed['updated_at']))
        with self.assertRaises(ValueError):
            mr.case_detail(created['id'])

    def test_requires_authorised_scope(self):
        for body in [dict(action='case_save', title='x', scope='public'),
                     dict(action='case_save', title='x', scope='private-dump', authorised_confirmed=True)]:
            with self.subTest(body=body), self.assertRaises(ValueError):
                mr.action(body)

    def test_evidence_update_delete_timestamps_and_verification(self):
        case = self.case()
        evidence = self.evidence(case['id'])
        row = mr.case_detail(case['id'])['case']['evidence'][0]
        self.assertEqual(row['label'], 'unverified')
        self.assertTrue(row['observed_at'].startswith('2026-09-08T00:30'))
        self.assertNotEqual(row['observed_at'], row['created_at'])
        with self.assertRaises(ValueError):
            self.evidence(case['id'], id=evidence['id'], expected_updated=evidence['updated_at'], label='verified')
        changed = self.evidence(case['id'], id=evidence['id'], expected_updated=evidence['updated_at'],
                                label='verified', verification_note='Compared the statement to its primary published source.')
        row = mr.case_detail(case['id'])['case']['evidence'][0]
        self.assertEqual(row['created_at'], evidence['updated_at'])
        self.assertEqual(row['label'], 'verified')
        mr.action(dict(action='evidence_delete', case_id=case['id'], id=evidence['id'], expected_updated=changed['updated_at']))
        self.assertEqual(mr.case_detail(case['id'])['case']['evidence'], [])

    def test_conflicts_and_cross_case_edits_are_rejected(self):
        first, second = self.case(), self.case('Second')
        evidence = self.evidence(first['id'])
        for body in [dict(action='case_delete', id=first['id'], expected_updated=first['updated_at']),
                     dict(action='evidence_delete', case_id=second['id'], id=evidence['id'], expected_updated=evidence['updated_at']),
                     dict(action='case_delete', id=second['id'])]:
            with self.subTest(body=body), self.assertRaises(ValueError):
                mr.action(body)

    def test_delete_case_removes_evidence(self):
        case = self.case()
        self.evidence(case['id'])
        fresh = mr.case_detail(case['id'])['case']
        mr.action(dict(action='case_delete', id=case['id'], expected_updated=fresh['updated_at']))
        with mr.database() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM u1_mr_evidence').fetchone()[0], 0)

    def test_export_preserves_attribution_and_no_network_runs(self):
        case = self.case()
        self.evidence(case['id'], note='<script>not executable</script>')
        exported = mr.export_case(case['id'])
        decoded = json.loads(base64.b64decode(exported['content']))
        self.assertEqual(decoded['format'], 'u1-research-casebook')
        self.assertEqual(decoded['case']['evidence'][0]['source_url'], 'https://example.org/source')
        self.assertIn('not automatic', decoded['notice'])
        self.assertIn('<script>', decoded['case']['evidence'][0]['note'])

    def test_urls_timestamps_field_limits_and_unknown_actions(self):
        for value in ['file:///etc/passwd', 'javascript:alert(1)', 'https://u:p@example.org', 'https://example.org:bad/',
                      'https://example.org/\nsecret', 'https://example.org\\@localhost/']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                mr.source_url(value)
        for value in ['2026-09-08T10:30:00', 'not a date', '9999-99-99T00:00:00Z']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                mr.timestamp(value)
        for body in [dict(action='download', url='https://example.org'), dict(action='execute', command='x'), [],
                     dict(action='case_save', title='x' * 161, scope='public', authorised_confirmed=True)]:
            with self.subTest(body=body), self.assertRaises(ValueError):
                mr.action(body)

    def test_record_limits(self):
        self.case()
        with patch.object(mr, 'MAX_CASES', 1), self.assertRaises(ValueError):
            self.case()
        case = self.case('Has evidence')
        self.evidence(case['id'])
        with patch.object(mr, 'MAX_EVIDENCE', 1), self.assertRaises(ValueError):
            self.evidence(case['id'])

    def test_safe_managed_source_and_path_rejection(self):
        source_id = self.upload()
        metadata, content = mr.managed_source(source_id)
        self.assertEqual(metadata['id'], source_id)
        self.assertEqual(content, b'RIFF-local-test-fixture')
        for value in ['/etc/passwd', '../outside', 'https://example.org/video.mp4', source_id + '/x']:
            with self.subTest(value=value), self.assertRaises(ValueError):
                mr.managed_source(value)

    def test_source_symlink_checksum_and_directory_symlink_rejected(self):
        source_id = self.upload()
        source = mr.workspace.DATA / 'files' / source_id
        source.write_bytes(b'Changed-local-content!')
        with self.assertRaises(ValueError):
            mr.managed_source(source_id)
        outside = Path(self.temp.name) / 'isolated-outside-fixture'
        outside.write_bytes(b'RIFF-local-test-fixture')
        source.unlink()
        source.symlink_to(outside)
        with self.assertRaises(ValueError):
            mr.managed_source(source_id)
        source.unlink()
        files = mr.workspace.DATA / 'files'
        files.rmdir()
        other = Path(self.temp.name) / 'other-fixtures'
        other.mkdir()
        (other / source_id).write_bytes(b'RIFF-local-test-fixture')
        files.symlink_to(other, target_is_directory=True)
        with self.assertRaises(ValueError):
            mr.managed_source(source_id)

    def test_playlist_incomplete_deleted_and_oversized_sources(self):
        playlist = self.upload(name='remote.m3u8', content=b'#EXTM3U\nhttps://example.org/x')
        with self.assertRaises(ValueError):
            mr.managed_source(playlist)
        source_id = self.upload()
        for update in ["status='uploading'", "status='ready',deleted=1", "deleted=NULL,size=999999999", "size=1,received=0"]:
            with mr.workspace.database() as conn:
                conn.execute('UPDATE files SET ' + update + ' WHERE id=?', (source_id,))
            with self.subTest(update=update), self.assertRaises(ValueError):
                mr.managed_source(source_id)

    def test_export_requires_rights_engine_and_fixed_format(self):
        with self.assertRaises(ValueError):
            mr.action(dict(action='clip_export', clip_in=0, clip_out=1, format='mp4'))
        with patch.object(mr, 'ffmpeg_binary', return_value=(None, 'unavailable')), self.assertRaises(ValueError):
            mr.action(dict(action='clip_export', clip_in=0, clip_out=1, format='mp4', rights_confirmed=True))
        with self.assertRaises(ValueError):
            mr.action(dict(action='clip_export', clip_in=0, clip_out=1, format='../../file', rights_confirmed=True))

    def test_real_export_contract_with_mocked_process(self):
        source_id = self.upload()
        calls = []

        def runner(args, timeout):
            calls.append((args, timeout))
            if len(calls) == 1:
                return 1, b'Duration: 00:00:10.00\n Stream #0:0: Audio: pcm_s16le\n'
            Path(args[-1]).write_bytes(b'RIFF-rendered-fixture')
            return 0, b''

        with patch.object(mr, 'ffmpeg_binary', return_value=('/trusted/ffmpeg', 'mock')), patch.object(mr, 'run_bounded', side_effect=runner):
            result = mr.action(dict(action='clip_export', source_id=source_id, clip_in=1, clip_out=3, format='wav', rights_confirmed=True))
        self.assertEqual(base64.b64decode(result['content']), b'RIFF-rendered-fixture')
        self.assertEqual(result['engine'], 'FFmpeg')
        self.assertIn('-fs', calls[1][0])
        self.assertIn('-map_metadata', calls[1][0])
        self.assertIn('wav', calls[1][0])
        self.assertEqual(calls[1][1], mr.EXPORT_TIMEOUT)
        self.assertFalse(Path(calls[1][0][-1]).exists())

    def test_no_success_on_failed_output_and_source_range_overrun(self):
        source_id = self.upload()
        for end, log in [(3, b'failed'), (12, b'failed')]:
            with patch.object(mr, 'ffmpeg_binary', return_value=('/trusted/ffmpeg', 'mock')), patch.object(mr, 'run_bounded', side_effect=[(1, b'Duration: 00:00:10.00\nStream #0:0: Audio: pcm\n'), (1, log)]), self.assertRaises(ValueError):
                mr.action(dict(action='clip_export', source_id=source_id, clip_in=0, clip_out=end, format='wav', rights_confirmed=True))

    def test_media_lock_rejects_concurrent_work(self):
        mr.MEDIA_LOCK.acquire()
        try:
            with patch.object(mr, 'ffmpeg_binary', return_value=('/trusted/ffmpeg', 'mock')), self.assertRaises(ValueError):
                mr.action(dict(action='inspect', source_id='a' * 32))
        finally:
            mr.MEDIA_LOCK.release()


class CaptionTests(unittest.TestCase):
    SRT = '1\n00:00:01,000 --> 00:00:03,000\nFirst line\n\n2\n00:00:04,000 --> 00:00:06,000\nSecond line\n'

    def test_trim_intersects_renumbers_and_rebases(self):
        result = mr.captions_export(dict(captions=self.SRT, rights_confirmed=True, trim_to_clip=True, clip_in=2, clip_out=5))
        self.assertEqual(base64.b64decode(result['content']).decode(), '1\n00:00:00,000 --> 00:00:01,000\nFirst line\n\n2\n00:00:02,000 --> 00:00:03,000\nSecond line\n')

    def test_caption_full_export_and_invalid_srt(self):
        result = mr.captions_export(dict(captions=self.SRT.replace('\n', '\r\n'), rights_confirmed=True))
        self.assertEqual(base64.b64decode(result['content']).decode(), self.SRT)
        for value in ['', self.SRT.replace('00:00:01,000', '00:00:08,000'), self.SRT.replace('00:00:04,000', '00:00:02,000'),
                      self.SRT.replace('First line', '<script>x</script>'), self.SRT.replace('1\n', '7\n', 1), 'x' * 48001]:
            with self.subTest(value=value[:40]), self.assertRaises(ValueError):
                mr.captions_export(dict(captions=value, rights_confirmed=True))

    def test_time_bounds_and_rights(self):
        for start, end in [(True, 1), (0, float('nan')), (0, float('inf')), (-1, 1), (2, 2), (3, 2), (0, 121), (86400, 86401), ('0', 2), (None, 2)]:
            with self.subTest(start=start, end=end), self.assertRaises(ValueError):
                mr.clip_range(dict(clip_in=start, clip_out=end))
        self.assertEqual(mr.clip_range(dict(clip_in=0, clip_out=120)), (0.0, 120.0))
        with self.assertRaises(ValueError):
            mr.captions_export(dict(captions=self.SRT))
        with self.assertRaises(ValueError):
            mr.captions_export(dict(captions=self.SRT, rights_confirmed=True, trim_to_clip=True, clip_in=10, clip_out=12))


class ProcessTests(unittest.TestCase):
    def process(self, raw=b'bounded log'):
        process = Mock()
        process.stdout = io.BytesIO(raw)
        process.returncode = 0
        return process

    def test_bounded_output_without_shell(self):
        process = self.process()
        with patch.object(mr.subprocess, 'Popen', return_value=process) as popen:
            code, log = mr.run_bounded(['/trusted/ffmpeg', '-version'], 1)
        self.assertEqual((code, log), (0, b'bounded log'))
        self.assertFalse(popen.call_args.kwargs['shell'])
        self.assertEqual(popen.call_args.kwargs['stdin'], subprocess.DEVNULL)

    def test_log_overflow_kills_process(self):
        process = self.process(b'x' * (mr.MAX_LOG + 1))
        with patch.object(mr.subprocess, 'Popen', return_value=process), self.assertRaises(ValueError):
            mr.run_bounded(['/trusted/ffmpeg'], 1)
        process.kill.assert_called()

    def test_timeout_kills_and_waits(self):
        process = self.process()
        process.wait.side_effect = [subprocess.TimeoutExpired('ffmpeg', 1), 0]
        with patch.object(mr.subprocess, 'Popen', return_value=process), self.assertRaisesRegex(ValueError, 'time limit'):
            mr.run_bounded(['/trusted/ffmpeg'], 1)
        process.kill.assert_called_once()
        self.assertTrue(process.stdout.closed)

    def test_imageio_installed_binary_and_unavailable_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'binaries').mkdir()
            binary = root / 'binaries' / 'ffmpeg-fixture'
            binary.write_text('isolated non-executed fixture')
            binary.chmod(0o700)
            module = Mock()
            module.get_ffmpeg_exe.return_value = str(binary)
            with patch.object(mr.shutil, 'which', return_value=None), patch.object(mr.importlib, 'import_module', return_value=module):
                self.assertEqual(mr.ffmpeg_binary()[0], str(binary))
                module.get_ffmpeg_exe.assert_called_once()
        with patch.object(mr, 'ffmpeg_binary', return_value=(None, 'unavailable')):
            cap = mr.capabilities()
            self.assertFalse(cap['ffmpeg_available'])
            self.assertTrue(cap['srt_export'])
            self.assertFalse(cap['rdap'])
            self.assertFalse(cap['subscription_sync'])


class HandlerTests(unittest.TestCase):
    def handler(self, body=None, method='POST', **headers):
        raw = json.dumps(body or dict(action='unsupported')).encode()
        handler = Mock(path=mr.ENDPOINT, command=method, rfile=io.BytesIO(raw))
        handler.headers = {'X-U1-CSRF': mr.integrations_hub.CSRF_TOKEN, 'Content-Type': 'application/json', 'Content-Length': str(len(raw))}
        handler.headers.update(headers)
        handler.integration_request_allowed.return_value = True
        return handler

    def test_unrelated_route_is_not_handled(self):
        handler = self.handler()
        handler.path = '/api/workspace/other'
        self.assertFalse(mr.handle_request(handler))
        handler.send_json.assert_not_called()

    def test_origin_and_csrf_guard(self):
        for method in ['GET', 'POST']:
            handler = self.handler(method=method)
            handler.integration_request_allowed.return_value = False
            self.assertTrue(mr.handle_request(handler))
            self.assertEqual(handler.send_json.call_args.args[1], 403)
        for token in ['', 'wrong', '\u00e9']:
            handler = self.handler(**{'X-U1-CSRF': token})
            mr.handle_request(handler)
            self.assertEqual(handler.send_json.call_args.args[1], 403)

    def test_body_bounds_content_type_and_methods(self):
        for headers in [{'Content-Length': '65537'}, {'Content-Length': '-1'}, {'Content-Length': 'nan'},
                        {'Content-Length': '999'}, {'Content-Type': 'text/plain'}, {'Transfer-Encoding': 'chunked'}]:
            handler = self.handler(**headers)
            mr.handle_request(handler)
            self.assertEqual(handler.send_json.call_args.args[1], 400)
        handler = self.handler(method='DELETE')
        mr.handle_request(handler)
        self.assertEqual(handler.send_json.call_args.args[1], 405)

    def test_dispatch_json_validation_and_service_failure(self):
        handler = self.handler(body=['invalid'])
        mr.handle_request(handler)
        self.assertEqual(handler.send_json.call_args.args[1], 400)
        handler = self.handler(method='GET')
        with patch.object(mr, 'snapshot', return_value={'success': True}):
            mr.handle_request(handler)
        self.assertEqual(handler.send_json.call_args.args[0], {'success': True})
        handler = self.handler(method='GET')
        with patch.object(mr, 'snapshot', side_effect=OSError('private path should not leak')):
            mr.handle_request(handler)
        self.assertEqual(handler.send_json.call_args.args[1], 503)
        self.assertNotIn('private path', str(handler.send_json.call_args))


@unittest.skipUnless(os.environ.get('U1_MR_REAL_FFMPEG') == '1', 'Opt-in synthetic FFmpeg integration test')
class SyntheticFFmpegTests(unittest.TestCase):
    def test_generated_owned_video_exports_real_mp4_and_wav(self):
        """Synthetic test fixture only, never demo content or a real user file."""
        binary, _ = mr.ffmpeg_binary()
        self.assertIsNotNone(binary, 'The real export test requires an installed FFmpeg')
        with tempfile.TemporaryDirectory(prefix='u1-mr-synthetic-test-') as directory:
            root = Path(directory)
            source = root / 'synthetic-owned-fixture.mp4'
            code, log = mr.run_bounded([
                binary, '-hide_banner', '-nostdin', '-loglevel', 'error', '-y',
                '-f', 'lavfi', '-i', 'color=c=teal:s=64x64:r=10:d=1',
                '-f', 'lavfi', '-i', 'sine=frequency=440:duration=1',
                '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac',
                '-threads', '1', '-shortest', str(source),
            ], 8)
            self.assertEqual(code, 0, log.decode(errors='replace'))
            raw = source.read_bytes()
            with patch.object(mr.workspace, 'DATA', root / 'isolated-prism'):
                uploaded = mr.workspace.handle_post('prism/upload-start', dict(
                    name=source.name, size=len(raw), mime='video/mp4', folder='Synthetic test fixtures'))
                for offset in range(0, len(raw), 32768):
                    mr.workspace.handle_post('prism/upload-chunk', dict(id=uploaded['id'], offset=offset,
                        content=base64.b64encode(raw[offset:offset + 32768]).decode()))
                inspected = mr.action(dict(action='inspect', source_id=uploaded['id']))
                self.assertTrue(inspected['audio'])
                self.assertTrue(inspected['video'])
                for output_format in ['mp4', 'wav']:
                    with self.subTest(format=output_format):
                        exported = mr.action(dict(action='clip_export', source_id=uploaded['id'],
                            clip_in=0.2, clip_out=0.7, format=output_format, rights_confirmed=True))
                        output = root / ('synthetic-export.' + output_format)
                        output.write_bytes(base64.b64decode(exported['content']))
                        self.assertEqual(exported['engine'], 'FFmpeg')
                        self.assertGreater(exported['size'], 100)
                        if output_format == 'wav':
                            with wave.open(str(output), 'rb') as audio:
                                self.assertEqual(audio.getframerate(), 44100)
                                self.assertEqual(audio.getnchannels(), 2)
                                self.assertAlmostEqual(audio.getnframes() / audio.getframerate(), 0.5, delta=0.025)
                        code, log = mr.run_bounded([binary, '-hide_banner', '-nostdin', '-loglevel', 'error',
                                                   '-i', str(output), '-f', 'null', '-'], 4)
                        self.assertEqual(code, 0, log.decode(errors='replace'))


if __name__ == '__main__':
    unittest.main()
