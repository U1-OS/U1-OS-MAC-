"""Temporary state and synthetic PNGs only; provider/Keychain/process I/O denied."""
import copy
import io
import json
from pathlib import Path
import os
import struct
import tempfile
import time
import unittest
import uuid
from unittest.mock import Mock, patch
import zlib

from utils import u1_assistant as assistant
from utils import u1_image_provider as images


def synthetic_png():
    def chunk(kind, raw):
        return struct.pack('>I', len(raw)) + kind + raw + struct.pack('>I', zlib.crc32(kind + raw) & 0xffffffff)
    return (b'\x89PNG\r\n\x1a\n' + chunk(b'IHDR', struct.pack('>IIBBBBB', 1024, 1024, 8, 0, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress((b'\0' + b'\0' * 1024) * 1024)) + chunk(b'IEND', b''))


class AssistantRetentionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='u1-assistant-retention-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for target in ('subprocess.Popen', 'subprocess.run', 'urllib.request.urlopen',
                       'urllib.request.OpenerDirector.open', 'socket.create_connection'):
            guard = patch(target, side_effect=AssertionError('No provider, process or network calls'))
            guard.start()
            self.addCleanup(guard.stop)
        guard = patch.object(images.credentials, 'operation', side_effect=AssertionError('No Keychain calls'))
        guard.start()
        self.addCleanup(guard.stop)
        guard = patch.object(images.credentials, 'ready', return_value=False)
        guard.start()
        self.addCleanup(guard.stop)
        self.binary = self.root / 'provider-never-executed'
        self.binary.write_text('Synthetic status fixture only; never executed.')
        self.binary.chmod(0o700)
        self.service = assistant.AssistantManager(self.root / 'assistant', codex=self.binary,
                                                 autostart=False, safety_check=lambda: False)
        self.png = synthetic_png()

    def submit(self, prompt='Synthetic prompt', conversation_id=None, kind='text'):
        body = dict(request_id=uuid.uuid4().hex, confirmed=True, role='Creator', prompt=prompt)
        if conversation_id:
            body['conversation_id'] = conversation_id
        result = self.service.submit(body, kind=kind)
        return next(job for job in self.service.jobs if job['id'] == result['job']['id'])

    def finish(self, job, answer='Synthetic response'):
        job.update(status='succeeded', finished_at=time.time())
        conversation = next(c for c in self.service.conversations if c['id'] == job['conversation_id'])
        conversation['messages'].append(dict(role='assistant', text=answer, job_id=job['id'], created_at=time.time()))
        self.service._trim_conversation(conversation)
        self.service.payloads.pop(job['id'], None)
        self.service._save()

    def image(self):
        job = self.submit('Synthetic image fixture', kind='image')
        images.store_result(self.service, job, self.png)
        self.finish(job, 'Synthetic PNG fixture saved.')
        return job

    def churn(self, count=64):
        for index in range(count):
            self.finish(self.submit('Unrelated synthetic text ' + str(index)))

    def download(self, file_id, service=None):
        handler = Mock(wfile=io.BytesIO())
        images._image_reply(handler, service or self.service, file_id)
        handler.send_response.assert_called_once_with(200)
        return handler.wfile.getvalue()

    def history(self, job):
        return json.loads(self.service.payloads[job['id']])['history']

    def test_retained_png_remains_listed_and_authorized_after_64_text_jobs(self):
        image = self.image()
        self.churn()
        self.assertEqual(len(self.service.jobs), assistant.MAX_JOBS)
        self.assertIn(image['id'], {job['id'] for job in self.service.jobs})
        self.assertEqual([entry['job_id'] for entry in images.snapshot(self.service)['images']], [image['id']])
        self.assertEqual(self.download(image['id']), self.png)
        self.assertEqual(len(self.service.payloads), 0)

    def test_image_authorization_survives_restart_after_unrelated_job_pruning(self):
        image = self.image()
        self.churn()
        restored = assistant.AssistantManager(self.service.root, codex=self.binary, autostart=False,
                                              safety_check=lambda: False)
        self.assertLessEqual(len(restored.jobs), assistant.MAX_JOBS)
        self.assertEqual(self.download(image['id'], restored), self.png)
        self.assertEqual(images.snapshot(restored)['images'][0]['job_id'], image['id'])

    def test_image_retention_evicts_old_image_and_releases_its_job_pin(self):
        first = self.image()
        path = self.service.root / 'images' / (first['id'] + '.png')
        os.utime(path, (1, 1))
        with patch.object(images, 'MAX_IMAGES', 1):
            second = self.image()
        self.assertFalse(first['artifact']['available'])
        self.assertFalse(path.exists())
        self.churn()
        self.assertNotIn(first['id'], {job['id'] for job in self.service.jobs})
        self.assertEqual(self.download(second['id']), self.png)
        with self.assertRaisesRegex(assistant.AssistantError, 'not found'):
            self.download(first['id'])

    def test_cancelled_discarded_image_does_not_remain_pinned_or_readable(self):
        job = self.image()
        images.discard_result(self.service, job)
        job['status'] = 'cancelled'
        self.assertFalse(images.retained_artifact(job))
        with self.assertRaises(assistant.AssistantError):
            self.download(job['id'])
        self.churn()
        self.assertNotIn(job['id'], {item['id'] for item in self.service.jobs})

    def test_arbitrary_or_previously_pruned_png_is_not_authorized_by_existence(self):
        image = self.image()
        identifier = uuid.uuid4().hex
        assistant._atomic_write(self.service.root / 'images' / (identifier + '.png'), self.png)
        for file_id in (identifier, image['id']):
            if file_id == image['id']:
                self.service.jobs.remove(image)
            with self.subTest(file_id=file_id), self.assertRaises(assistant.AssistantError) as error:
                self.download(file_id)
            self.assertEqual(error.exception.status, 404)
        self.assertEqual(images.snapshot(self.service)['images'], [])

    def test_retained_job_predicate_excludes_failed_running_text_and_unavailable_jobs(self):
        job = self.image()
        for change in ({'status': 'failed'}, {'status': 'running'}, {'kind': 'text'},
                       {'artifact': {'available': False}}, {'artifact': {'available': 'true'}}, {'artifact': None}):
            candidate = {**job, **change}
            with self.subTest(change=change):
                self.assertFalse(images.retained_artifact(candidate))
                self.service.jobs[:] = [candidate]
                self.assertEqual(images.snapshot(self.service)['images'], [])
                with self.assertRaises(assistant.AssistantError):
                    self.download(job['id'])

    def test_pinned_capacity_rejects_without_mutation_or_dropping_authorization(self):
        image = self.image()
        before = copy.deepcopy((self.service.jobs, self.service.conversations, self.service.payloads))
        with patch.object(assistant, 'MAX_JOBS', 1), self.assertRaisesRegex(assistant.AssistantError, 'authorizations were preserved'):
            self.submit()
        self.assertEqual((self.service.jobs, self.service.conversations, self.service.payloads), before)
        self.assertEqual(self.download(image['id']), self.png)

    def test_all_20_retained_images_survive_churn_with_job_count_bounded(self):
        retained = {self.image()['id'] for _ in range(images.MAX_IMAGES)}
        self.churn()
        self.assertEqual(len(self.service.jobs), assistant.MAX_JOBS)
        self.assertEqual({entry['job_id'] for entry in images.snapshot(self.service)['images']}, retained)
        self.assertLessEqual(len(self.service.conversations), assistant.MAX_CONVERSATIONS)

    def test_managed_read_still_rejects_file_links_permissions_and_invalid_png(self):
        job = self.image()
        path = self.service.root / 'images' / (job['id'] + '.png')
        other = self.root / 'outside.png'
        assistant._atomic_write(other, self.png)
        for kind in ('symlink', 'hardlink', 'permissions', 'invalid_png'):
            path.unlink(missing_ok=True)
            if kind == 'symlink':
                path.symlink_to(other)
            elif kind == 'hardlink':
                os.link(other, path)
            else:
                assistant._atomic_write(path, self.png if kind == 'permissions' else b'not a PNG')
                if kind == 'permissions':
                    path.chmod(0o644)
            with self.subTest(kind=kind), self.assertRaises((OSError, ValueError)):
                self.download(job['id'])
        self.assertEqual(other.read_bytes(), self.png)
        for identifier in ('../outside', '/tmp/example.png', 'https://example.invalid/file'):
            with self.assertRaises(assistant.AssistantError):
                self.download(identifier)

    def test_oversized_response_does_not_drop_its_short_prior_instruction(self):
        first = self.submit('Short reviewed fixture instruction')
        answer = 'x' * (assistant.MAX_HISTORY + 1)
        self.assertLess(len(answer.encode()), assistant.MAX_OUTPUT)
        self.finish(first, answer)
        follow = self.submit('Follow up', first['conversation_id'])
        self.assertEqual(self.history(follow), [{'role': 'user', 'text': 'Short reviewed fixture instruction'}])

    def test_oversized_latest_response_preserves_older_short_turns_in_chronology(self):
        first = self.submit('Earlier instruction')
        self.finish(first, 'Earlier short answer')
        latest = self.submit('Recent question', first['conversation_id'])
        self.finish(latest, 'x' * (assistant.MAX_HISTORY + 1))
        follow = self.submit('Follow up', first['conversation_id'])
        self.assertEqual(self.history(follow), [{'role': 'user', 'text': 'Earlier instruction'},
                                              {'role': 'assistant', 'text': 'Earlier short answer'},
                                              {'role': 'user', 'text': 'Recent question'}])

    def test_encoded_history_budget_includes_unicode_escaping_and_json_framing(self):
        first = self.submit('First instruction')
        self.finish(first, '\u00e9' * 5000)
        second = self.submit('Second instruction', first['conversation_id'])
        self.finish(second, '\u00e9' * 1000)
        with patch.object(assistant, 'MAX_HISTORY', 6200):
            follow = self.submit('Follow up', first['conversation_id'])
            history = self.history(follow)
            self.assertLessEqual(len(assistant._encoded(history)), assistant.MAX_HISTORY)
        self.assertIn({'role': 'user', 'text': 'First instruction'}, history)
        self.assertNotIn({'role': 'assistant', 'text': '\u00e9' * 5000}, history)
        self.assertIn({'role': 'assistant', 'text': '\u00e9' * 1000}, history)

    def test_exact_history_boundary_does_not_overrun_by_array_punctuation(self):
        first = self.submit('Short')
        self.finish(first, 'Bounded')
        selected = [{'role': 'assistant', 'text': 'Bounded'}]
        with patch.object(assistant, 'MAX_HISTORY', len(assistant._encoded(selected))):
            follow = self.submit('Follow up', first['conversation_id'])
            self.assertEqual(self.history(follow), selected)
            self.assertEqual(len(assistant._encoded(self.history(follow))), assistant.MAX_HISTORY)

    def test_history_excludes_failed_turns_and_unselected_conversations(self):
        completed = self.submit('Selected instruction')
        self.finish(completed, 'Selected answer')
        unrelated = self.submit('UNSELECTED PRIVATE PROMPT')
        self.finish(unrelated, 'UNSELECTED PRIVATE RESPONSE')
        failed = self.submit('FAILED TURN', completed['conversation_id'])
        failed['status'] = 'failed'
        self.service.payloads.pop(failed['id'])
        follow = self.submit('Follow up', completed['conversation_id'])
        history = self.history(follow)
        self.assertEqual(history, [{'role': 'user', 'text': 'Selected instruction'},
                                   {'role': 'assistant', 'text': 'Selected answer'}])

    def test_existing_confirmation_gate_remains_before_history_submission(self):
        with self.assertRaises(assistant.AssistantError):
            self.service.submit(dict(request_id=uuid.uuid4().hex, prompt='Unconfirmed'))
        self.assertEqual(self.service.jobs, [])
        self.assertEqual(self.service.payloads, {})


if __name__ == '__main__':
    unittest.main()
