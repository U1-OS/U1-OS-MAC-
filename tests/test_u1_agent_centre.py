import os as _os
import sys as _sys

# Run from anywhere: put the project root on sys.path so `utils` and
# `services` import whether this file is run directly, via unittest
# discovery, or from another working directory.
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from utils import u1_agent_centre as agents


class AgentCentreTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = patch.object(agents, 'STORE', Path(self.temp.name) / 'agents.sqlite3')
        self.store.start()

    def tearDown(self):
        self.store.stop()
        self.temp.cleanup()

    def test_four_agents_default_to_manual(self):
        state = agents.snapshot()
        self.assertEqual(len(state['agents']), 4)
        self.assertTrue(all(not a['enabled'] for a in state['agents']))
        self.assertEqual(state['history'], [])

    def test_research_does_not_invent_market_data(self):
        result = agents.run('trading')['run']
        self.assertEqual(result['evidence']['market_data'], 'not_connected')
        self.assertEqual(result['evidence']['execution'], 'not_implemented')
        self.assertNotIn('profit', result)

    def test_execution_actions_are_rejected(self):
        for action in ['execute', 'trade', 'publish', 'install', 'change_permissions']:
            with self.assertRaises(ValueError):
                agents.handle_post(dict(action=action, agent='trading'))

    def test_monitor_setting_persists(self):
        agents.handle_post(dict(action='configure', agent='design', enabled=True))
        self.assertTrue(next(a for a in agents.snapshot()['agents'] if a['id']=='design')['enabled'])
        with self.assertRaises(ValueError):
            agents.handle_post(dict(action='configure', agent='design', enabled='true'))

    def test_feedback_is_deduplicated(self):
        result = agents.run('trading')['run']
        payload = dict(action='feedback', agent='trading', run_id=result['id'], finding='market-connection', value=1)
        agents.handle_post(payload)
        agents.handle_post(payload)
        self.assertEqual(agents.snapshot()['feedback_count'], 1)
        payload['value'] = -1
        agents.handle_post(payload)
        new_run = agents.run('trading')['run']
        self.assertEqual(new_run['findings'][0]['key'], 'market-connection')
        self.assertEqual(new_run['findings'][0]['feedback_score'], -1)

    def test_feedback_cannot_target_another_agent(self):
        result = agents.run('trading')['run']
        with self.assertRaises(ValueError):
            agents.handle_post(dict(action='feedback', agent='design', run_id=result['id'], finding='market-connection', value=1))

    def test_crypto_reports_missing_feed(self):
        with patch.object(agents, 'request_json', side_effect=OSError('offline')):
            result = agents.run('crypto')['run']
        self.assertEqual(result['evidence']['quotes'], [])
        self.assertEqual(len(result['findings']), 3)

    def test_crypto_rejects_nonfinite_quotes(self):
        with patch.object(agents, 'request_json', return_value={'data': {'amount': 'NaN', 'currency': 'USD'}}):
            result = agents.run('crypto')['run']
        self.assertEqual(result['evidence']['quotes'], [])

    def test_crypto_preserves_actual_quotes_and_source(self):
        with patch.object(agents, 'request_json', return_value={'data': {'amount': '123.45', 'currency': 'USD'}}):
            result = agents.run('crypto')['run']
        self.assertEqual([q['symbol'] for q in result['evidence']['quotes']], ['BTC','ETH','SOL'])
        self.assertTrue(all(q['amount'] == 123.45 and q['retrieved_at'] > 0 for q in result['evidence']['quotes']))

    def test_invalid_visual_payload_is_rejected(self):
        with self.assertRaises(ValueError):
            agents.validate_visual({'html': '<script>'})
        with self.assertRaises(ValueError):
            agents.validate_visual(dict(logos_clipped=-1, controls_unlabelled=0, horizontal_overflow=0, viewport_width=1200))

    def test_no_local_model_is_not_claimed_connected(self):
        with patch.object(agents, 'request_json', side_effect=OSError('offline')):
            self.assertFalse(agents.models()['available'])
        with patch.object(agents, 'models', return_value={'models': []}):
            with self.assertRaises(ValueError):
                agents.run('trading', model='invented-model')

    def test_runs_are_serialised(self):
        with agents.RUN_LOCK:
            with self.assertRaises(ValueError):
                agents.run('trading')


if __name__ == '__main__':
    unittest.main()
