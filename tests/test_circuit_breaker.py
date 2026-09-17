#!/usr/bin/env python3
"""
Unit tests for R.E.Y. Circuit Breaker & Auto-Quarantine Engine
Run with: python tests/test_circuit_breaker.py
"""

import os
import sys
import json
import shutil
import tempfile
import unittest
from pathlib import Path

# Add scripts directory to path
SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import importlib

rey_breaker = importlib.import_module("rey-breaker")
rey_roster = importlib.import_module("rey-roster")


class TestCircuitBreaker(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.circuit_file = os.path.join(self.temp_dir, "circuit-breaker.json")
        self.jsonc_file = os.path.join(self.temp_dir, "opencode.jsonc")
        self.json_file = os.path.join(self.temp_dir, "opencode.json")

        self.orig_circuit_file = rey_breaker.CIRCUIT_FILE
        self.orig_jsonc_path = rey_breaker.JSONC_PATH
        self.orig_json_path = rey_breaker.JSON_PATH
        self.orig_get_recent_messages = rey_breaker.get_recent_messages

        rey_breaker.CIRCUIT_FILE = self.circuit_file
        rey_breaker.JSONC_PATH = self.jsonc_file
        rey_breaker.JSON_PATH = self.json_file

    def tearDown(self):
        rey_breaker.CIRCUIT_FILE = self.orig_circuit_file
        rey_breaker.JSONC_PATH = self.orig_jsonc_path
        rey_breaker.JSON_PATH = self.orig_json_path
        rey_breaker.get_recent_messages = self.orig_get_recent_messages
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_user_abort_not_counted_as_error(self):
        self.assertTrue(rey_breaker.is_user_abort("Aborted", "MessageAbortedError"))
        self.assertTrue(rey_breaker.is_user_abort("User cancelled the prompt", "Error"))
        self.assertFalse(rey_breaker.is_user_abort("Rate limit exceeded", "APIError"))
        self.assertFalse(rey_breaker.is_user_abort("Invalid API Key", "APIError"))

    def test_full_model_name(self):
        self.assertEqual(rey_breaker.full_model_name("openrouter", "google/gemma-4-31b-it:free"), "openrouter/google/gemma-4-31b-it:free")
        self.assertEqual(rey_breaker.full_model_name("gemini", "gemini-2.5-flash"), "gemini/gemini-2.5-flash")
        self.assertEqual(rey_breaker.full_model_name("kilo", ""), "kilo")

    def test_model_quarantine_preserves_healthy_provider(self):
        sample_jsonc = """{
          "model": "openrouter/google/gemma-4-31b-it:free",
          "enabled_providers": ["openrouter", "kilo"],
          "agent": {
            "coder": {
              "model": "openrouter/cohere/north-mini-code:free"
            }
          }
        }"""
        with open(self.jsonc_file, "w", encoding="utf-8") as f:
            f.write(sample_jsonc)

        mock_errors = [
            {
                "message_id": f"msg_{i}",
                "session_id": "ses_1",
                "timestamp": 1000 + i,
                "provider": "openrouter",
                "model": "cohere/north-mini-code:free",
                "error_name": "APIError",
                "error_msg": "Rate limit exceeded: 429",
                "status_code": 429
            }
            for i in range(5)
        ]
        mock_successes = [
            {
                "message_id": "msg_succ_1",
                "session_id": "ses_2",
                "timestamp": 2000,
                "provider": "openrouter",
                "model": "google/gemma-4-31b-it:free"
            }
        ]

        rey_breaker.get_recent_messages = lambda **kw: (mock_errors, mock_successes)

        res = rey_breaker.check_and_update_circuit_breaker()

        # Rule 1: Model is quarantined when reaching 5 errors
        self.assertIn("openrouter/cohere/north-mini-code:free", res["quarantined_models"])

        # Rule 2: Provider is NOT quarantined because gemma-4-31b-it:free is healthy & working
        self.assertNotIn("openrouter", res["quarantined_providers"])

        # Rule 3: Auto-healing reassigns @coder role from quarantined model
        with open(self.jsonc_file, "r", encoding="utf-8") as f:
            updated_jsonc = f.read()
        self.assertNotIn("openrouter/cohere/north-mini-code:free", updated_jsonc)
        self.assertIn("coder", updated_jsonc)

    def test_provider_quarantine_on_auth_failure(self):
        sample_jsonc = """{
          "model": "groq/openai/gpt-oss-120b",
          "enabled_providers": ["groq", "kilo"]
        }"""
        with open(self.jsonc_file, "w", encoding="utf-8") as f:
            f.write(sample_jsonc)

        mock_errors = [
            {
                "message_id": "msg_auth",
                "session_id": "ses_1",
                "timestamp": 1000,
                "provider": "groq",
                "model": "openai/gpt-oss-120b",
                "error_name": "APIError",
                "error_msg": "401 Invalid API Key",
                "status_code": 401
            }
        ]

        rey_breaker.get_recent_messages = lambda **kw: (mock_errors, [])

        res = rey_breaker.check_and_update_circuit_breaker()

        # Provider-wide blocker quarantines the provider
        self.assertIn("groq", res["quarantined_providers"])

    def test_roster_excludes_quarantined_models_and_providers(self):
        live_models = {
            "ok": True,
            "providers": {
                "gemini": {
                    "ok": True,
                    "models": [
                        {"id": "gemini-2.5-flash", "pricing": "free", "context_length": 1000000},
                        {"id": "gemini-2.5-pro", "pricing": "free", "context_length": 1000000}
                    ]
                },
                "kilo": {
                    "ok": True,
                    "models": [
                        {"id": "kilo-auto/free", "pricing": "free", "context_length": 128000}
                    ]
                }
            }
        }

        # Case 1: Model quarantined -> excluded from roster, provider remains
        orig_load = rey_roster.load_circuit_breaker
        try:
            rey_roster.load_circuit_breaker = lambda: {
                "models": {"gemini-2.5-flash", "gemini/gemini-2.5-flash"},
                "providers": set()
            }
            roster_res = rey_roster.generate_roster_from_live(live_models)
            self.assertTrue(roster_res["ok"])
            self.assertNotEqual(roster_res["roster"]["coder"]["model"], "gemini-2.5-flash")
            self.assertIn("gemini", roster_res["enabled_providers"])

            # Case 2: Provider quarantined -> entire provider removed from roster
            rey_roster.load_circuit_breaker = lambda: {
                "models": set(),
                "providers": {"gemini"}
            }
            roster_res2 = rey_roster.generate_roster_from_live(live_models)
            self.assertTrue(roster_res2["ok"])
            self.assertNotIn("gemini", roster_res2["enabled_providers"])
            self.assertEqual(roster_res2["roster"]["coder"]["provider"], "kilo")
        finally:
            rey_roster.load_circuit_breaker = orig_load

    def test_reset_circuit_breaker(self):
        state = {
            "quarantined_models": {"test-model": {"errors": 5}},
            "quarantined_providers": {"test-prov": {"errors": 5}},
            "model_error_counts": {"test-model": 5},
            "provider_error_counts": {"test-prov": 5}
        }
        with open(self.circuit_file, "w", encoding="utf-8") as f:
            json.dump(state, f)

        res = rey_breaker.reset_circuit_breaker("all")
        self.assertTrue(res["ok"])

        with open(self.circuit_file, "r", encoding="utf-8") as f:
            cleared = json.load(f)
        self.assertEqual(cleared["quarantined_models"], {})
        self.assertEqual(cleared["quarantined_providers"], {})


if __name__ == "__main__":
    unittest.main()
