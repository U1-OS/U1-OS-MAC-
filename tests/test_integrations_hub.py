import os as _os
import sys as _sys

# Run from anywhere: put the project root on sys.path so `utils` and
# `services` import whether this file is run directly, via unittest
# discovery, or from another working directory.
_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
if _ROOT not in _sys.path:
    _sys.path.insert(0, _ROOT)

import json
import os
import tempfile
import unittest
from utils import integrations_hub as hub
from services.crypto import CryptoService


class IntegrationsTests(unittest.TestCase):
    def test_new_install_has_no_accounts(self):
        cards = hub.catalog({"integrations": {}}, "/app")["cards"]
        self.assertEqual(len(cards), 18)
        self.assertTrue(all(card["status"] == "not_configured" for card in cards))

    def test_secrets_never_returned(self):
        config = {"integrations": {"openai": {"api_key": "secret-example"}}}
        output = json.dumps(hub.catalog(config, "/app"))
        self.assertNotIn("secret-example", output)
        self.assertIn("settings_saved", output)

    def test_blank_secret_preserved_and_clear_explicit(self):
        original = {"integrations": {"openai": {"api_key": "secret-example"}}}
        updated = hub.updated_config(original, {"integration": "openai", "values": {"api_key": ""}})
        self.assertEqual(updated, original)
        cleared = hub.updated_config(original, {"integration": "openai", "clear": True})
        self.assertEqual(cleared["integrations"]["openai"], {})
        self.assertEqual(original["integrations"]["openai"]["api_key"], "secret-example")

    def test_rejects_private_wallet_key(self):
        with self.assertRaises(ValueError):
            hub.updated_config({}, {"integration": "solana", "values": {"private_key": "no"}})

    def test_atomic_owner_only_storage(self):
        with tempfile.TemporaryDirectory() as folder:
            filename = os.path.join(folder, "config.json")
            hub.persist({"integrations": {}}, filename)
            self.assertEqual(os.stat(filename).st_mode & 0o777, 0o600)
            with open(filename) as stream:
                self.assertEqual(json.load(stream), {"integrations": {}})

    def test_crypto_setup_has_no_fabricated_data_or_actions(self):
        service = CryptoService({"system": {"setup_mode": True}})
        self.assertEqual(service.data["positions"], [])
        self.assertEqual(service.data["tokens"], [])
        self.assertFalse(service.dispatch_action("execute_swap", {"confirmed": True})["success"])
        self.assertFalse(service.dispatch_action("start_trading_bot")["success"])
        service.poll()
        self.assertEqual(service.bot_state["status"], "NOT_CONFIGURED")


if __name__ == "__main__":
    unittest.main()
