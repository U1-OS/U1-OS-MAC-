"""Release-plan contracts using mocked Git only: never fetch or change checkout."""
import unittest
from unittest.mock import patch
from utils.u1_release_guard import ReleaseGuard
from utils import u1_recovery


class ReleaseGuardTests(unittest.TestCase):
    def setUp(self):
        self.guard = ReleaseGuard('.')
        self.head = 'a' * 40
        self.target = 'b' * 40
        self.calls = []
        self.addCleanup(patch.stopall)
        patch.object(self.guard, 'identity', side_effect=lambda: ('main', self.head)).start()
        patch.object(self.guard, 'git', side_effect=self.git).start()
        patch.object(u1_recovery, 'make_backup', return_value={'backup_id':'c'*32}).start()
        patch.object(u1_recovery, 'digest_file', return_value=('d'*64, 12)).start()

    def git(self, *args, **kwargs):
        self.calls.append(args)
        if args[0] == 'rev-parse':
            return self.head if args[1] == 'HEAD' else self.target
        if args[0] == 'log': return 'Reviewed local fixture'
        if args[0] == 'merge': self.head = self.target
        return ''

    def test_prepare_has_exact_commit_and_checkpoint_without_applying(self):
        self.guard._prepare()
        plan = self.guard.snapshot()['plan']
        self.assertEqual(plan['from_commit'], 'a'*40)
        self.assertEqual(plan['to_commit'], 'b'*40)
        self.assertFalse(plan['applied'])
        self.assertFalse(plan['signature_verified'])
        self.assertTrue(plan['checkpoint_ref'].startswith('refs/u1/checkpoints/'))
        self.assertFalse(any(call[0] == 'merge' for call in self.calls))

    def test_changed_or_expired_plan_is_not_applied(self):
        self.guard._prepare()
        plan = self.guard.plan
        with self.assertRaises(ValueError):
            self.guard._apply({'plan_id':plan['id'],'expected_commit':'e'*40})
        plan['expires'] = 0
        with self.assertRaises(ValueError):
            self.guard._apply({'plan_id':plan['id'],'expected_commit':plan['to_commit']})
        self.assertFalse(any(call[0] == 'merge' for call in self.calls))

    def test_reviewed_fast_forward_only_and_cannot_apply_twice(self):
        self.guard._prepare()
        plan = self.guard.plan
        body = {'plan_id':plan['id'],'expected_commit':plan['to_commit']}
        result = self.guard._apply(body)
        self.assertTrue(result['restart_required'])
        self.assertTrue(self.guard.snapshot()['plan']['applied'])
        self.assertTrue(any(call[0]=='merge' and '--ff-only' in call for call in self.calls))
        self.assertFalse(any(call[0] in ('reset','stash','checkout') for call in self.calls))
        with self.assertRaises(ValueError): self.guard._apply(body)

    def test_changed_backup_or_checkout_blocks_apply(self):
        self.guard._prepare()
        body = {'plan_id':self.guard.plan['id'],'expected_commit':self.target}
        with patch.object(u1_recovery, 'digest_file', return_value=('f'*64, 12)):
            with self.assertRaises(ValueError): self.guard._apply(body)
        self.head = 'e'*40
        with self.assertRaises(ValueError): self.guard._apply(body)
        self.assertFalse(any(call[0]=='merge' for call in self.calls))


if __name__ == '__main__': unittest.main()
