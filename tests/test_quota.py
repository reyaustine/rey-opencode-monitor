"""Tests for rey-quota.py functions."""

import json
import pytest
from unittest.mock import patch, MagicMock
import sys
import os
import urllib.request
import urllib.error


class TestSafeFloat:
    """Tests for safe_float function."""

    def test_valid_float(self, rey_quota):
        assert rey_quota.safe_float("3.14") == 3.14
        assert rey_quota.safe_float(3.14) == 3.14
        assert rey_quota.safe_float(3) == 3.0

    def test_invalid_float_returns_default(self, rey_quota):
        assert rey_quota.safe_float("abc") == 0.0
        assert rey_quota.safe_float(None) == 0.0
        assert rey_quota.safe_float("") == 0.0
        assert rey_quota.safe_float("abc", default=1.5) == 1.5

    def test_edge_cases(self, rey_quota):
        assert rey_quota.safe_float("0") == 0.0
        assert rey_quota.safe_float("-1.5") == -1.5
        assert rey_quota.safe_float("1e3") == 1000.0


class TestSafeInt:
    """Tests for safe_int function."""

    def test_valid_int(self, rey_quota):
        assert rey_quota.safe_int("42") == 42
        assert rey_quota.safe_int(42) == 42
        assert rey_quota.safe_int(3.14) == 3

    def test_invalid_int_returns_default(self, rey_quota):
        assert rey_quota.safe_int("abc") == 0
        assert rey_quota.safe_int(None) == 0
        assert rey_quota.safe_int("") == 0
        assert rey_quota.safe_int("abc", default=5) == 5


class TestClassifyBudget:
    """Tests for classify_budget function."""

    def test_depleted(self, rey_quota):
        status, percent = rey_quota.classify_budget(0, 100)
        assert status == "DEPLETED"
        assert percent == 0.0

    def test_critical(self, rey_quota):
        status, percent = rey_quota.classify_budget(5, 100)
        assert status == "CRITICAL"
        assert percent == 5.0

    def test_low(self, rey_quota):
        status, percent = rey_quota.classify_budget(20, 100)
        assert status == "LOW"
        assert percent == 20.0

    def test_ok(self, rey_quota):
        status, percent = rey_quota.classify_budget(50, 100)
        assert status == "OK"
        assert percent == 50.0

    def test_zero_limit(self, rey_quota):
        status, percent = rey_quota.classify_budget(10, 0)
        assert status == "UNKNOWN"
        assert percent == 0.0

    def test_negative_remaining(self, rey_quota):
        status, percent = rey_quota.classify_budget(-5, 100)
        assert status == "DEPLETED"
        assert percent == 0.0

    def test_percent_capped_at_100(self, rey_quota):
        status, percent = rey_quota.classify_budget(150, 100)
        assert status == "OK"
        assert percent == 100.0

    def test_uses_constants(self, rey_quota):
        status, _ = rey_quota.classify_budget(25, 100)
        assert status == "LOW"
        status, _ = rey_quota.classify_budget(10, 100)
        assert status == "CRITICAL"


class TestLoadAuthKeys:
    """Tests for load_auth_keys function with edge cases."""

    def test_loads_from_auth_json(self, rey_quota, temp_config_dir, fake_auth_json):
        auth_path = temp_config_dir["local_share"] / "auth.json"
        auth_path.write_text(json.dumps(fake_auth_json))

        with patch.object(rey_quota.os.path, "exists", return_value=True):
            with patch.object(rey_quota, "AUTH_PATH", str(auth_path)):
                keys = rey_quota.load_auth_keys()
                assert keys["openrouter"] == "sk-or-v1-fakekey123"
                assert keys["groq"] == "gsk_fakekey456"
                assert keys["gemini"] == "fake-gemini-key"
                assert keys["mistral"] == "fake-mistral-key"

    def test_returns_empty_when_file_missing(self, rey_quota, temp_config_dir):
        missing_path = temp_config_dir["local_share"] / "nonexistent.json"
        with patch.object(rey_quota, "AUTH_PATH", str(missing_path)):
            with patch.object(rey_quota.os.path, "exists", return_value=False):
                keys = rey_quota.load_auth_keys()
                assert keys == {}

    def test_handles_malformed_json(self, rey_quota, temp_config_dir):
        auth_path = temp_config_dir["local_share"] / "auth.json"
        auth_path.write_text("not valid json")

        with patch.object(rey_quota, "AUTH_PATH", str(auth_path)):
            with patch.object(rey_quota.os.path, "exists", return_value=True):
                keys = rey_quota.load_auth_keys()
                assert keys == {}

    def test_ignores_extra_providers(self, rey_quota, temp_config_dir, fake_auth_json):
        auth_data = {"openrouter": {"key": "key1"}, "unknown_provider": {"key": "key2"}}
        auth_path = temp_config_dir["local_share"] / "auth.json"
        auth_path.write_text(json.dumps(auth_data))

        with patch.object(rey_quota, "AUTH_PATH", str(auth_path)):
            with patch.object(rey_quota.os.path, "exists", return_value=True):
                keys = rey_quota.load_auth_keys()
                assert "openrouter" in keys
                assert "unknown_provider" not in keys

    def test_missing_provider_in_auth(self, rey_quota, temp_config_dir):
        auth_data = {"openrouter": {"key": "key1"}}
        auth_path = temp_config_dir["local_share"] / "auth.json"
        auth_path.write_text(json.dumps(auth_data))

        with patch.object(rey_quota, "AUTH_PATH", str(auth_path)):
            with patch.object(rey_quota.os.path, "exists", return_value=True):
                keys = rey_quota.load_auth_keys()
                assert "openrouter" in keys
                assert "groq" not in keys


class TestCheckOpenRouterQuotaEdgeCases:
    """Edge case tests for check_openrouter_quota."""

    def test_returns_default_when_no_key(self, rey_quota):
        result = rey_quota.check_openrouter_quota({})
        assert result["ok"] is False
        assert result["status"] == "UNKNOWN"

    def test_handles_network_error(self, rey_quota):
        with patch.dict(rey_quota.os.environ, {}, clear=True):
            with patch.object(rey_quota, "load_auth_keys", return_value={"openrouter": "sk-test"}):
                with patch("urllib.request.urlopen", side_effect=Exception("Network error")):
                    result = rey_quota.check_openrouter_quota({"openrouter": "sk-test"})
                    assert result["ok"] is False
                    assert "error" in result

    def test_handles_429_rate_limit(self, rey_quota):
        with patch.dict(rey_quota.os.environ, {}, clear=True):
            with patch.object(rey_quota, "load_auth_keys", return_value={"openrouter": "sk-test"}):
                quota_response = {
                    "data": {
                        "label": "test", "limit": 10.0, "limit_remaining": 5.0,
                        "free_model_daily_requests": {"limit": 100, "remaining": 50, "used": 50}
                    }
                }
                quota_mock = MagicMock()
                quota_mock.read.return_value = json.dumps(quota_response).encode()
                quota_mock.__enter__ = MagicMock(return_value=quota_mock)
                quota_mock.__exit__ = MagicMock(return_value=False)

                error_body = {
                    "error": {"message": "Rate limit exceeded", "metadata": {"headers": {
                        "X-RateLimit-Reset": "1700000000000", "X-RateLimit-Remaining": "0",
                        "X-RateLimit-Limit": "50"}}}}
                error_mock = MagicMock()
                error_mock.read.return_value = json.dumps(error_body).encode()
                error_mock.code = 429
                http_error = urllib.error.HTTPError("url", 429, "Rate Limited", {}, error_mock)

                def side_effect(req, *args, **kwargs):
                    if "auth/key" in req.full_url:
                        return quota_mock
                    raise http_error

                with patch("urllib.request.urlopen", side_effect=side_effect):
                    result = rey_quota.check_openrouter_quota({"openrouter": "sk-test"})

                assert result["is_rate_limited"] is True
                assert result["status"] == "RATE_LIMITED_429"


class TestCheckProvider:
    """Tests for check_provider function."""

    def test_openrouter_delegates(self, rey_quota):
        with patch.object(rey_quota, "check_openrouter_quota") as mock_check:
            mock_check.return_value = {"provider": "openrouter", "ok": True}
            result = rey_quota.check_provider("openrouter", rey_quota.PROVIDERS["openrouter"], {})
            assert result["provider"] == "openrouter"
            mock_check.assert_called_once()

    def test_generic_provider_success(self, rey_quota):
        config = {
            "name": "TestProvider", "models_endpoint": "https://api.test.com/models",
            "free_limit": 100, "check_method": "HEAD"
        }
        with patch.object(rey_quota, "ping_endpoint", return_value=(True, 200, 50, "")):
            result = rey_quota.check_provider("test", config, {})
        assert result["provider"] == "test"
        assert result["name"] == "TestProvider"
        assert result["ok"] is True
        assert result["status"] == "OK (200)"
        assert result["latency_ms"] == 50

    def test_generic_provider_failure(self, rey_quota):
        config = {
            "name": "TestProvider", "models_endpoint": "https://api.test.com/models",
            "free_limit": 100, "check_method": "HEAD"
        }
        with patch.object(rey_quota, "ping_endpoint", return_value=(False, "Timeout", 5000, "")):
            result = rey_quota.check_provider("test", config, {})
        assert result["ok"] is False
        assert "FAIL" in result["status"]
        assert result["is_rate_limited"] is True

    def test_providers_have_required_fields(self, rey_quota):
        for name, config in rey_quota.PROVIDERS.items():
            assert "name" in config
            assert "free_limit" in config
            assert config["free_limit"] > 0
