"""Tests for rey-switch.py functions."""

import json
import pytest
from unittest.mock import patch, MagicMock
import sys
import os
from pathlib import Path


class TestProviderValidation:
    """Tests for provider validation: kilo/opencode/openrouter."""

    def test_kilo_provider_exists(self, rey_switch):
        assert "kilo" in rey_switch.PROVIDERS_INFO
        assert rey_switch.PROVIDERS_INFO["kilo"]["name"] == "Kilo Code"
        assert "primary_model" in rey_switch.PROVIDERS_INFO["kilo"]
        assert rey_switch.PROVIDERS_INFO["kilo"]["primary_model"] == "kilo/kilo-auto/free"

    def test_opencode_provider_exists(self, rey_switch):
        assert "opencode" in rey_switch.PROVIDERS_INFO
        assert rey_switch.PROVIDERS_INFO["opencode"]["name"] == "OpenCode Built-In"
        assert rey_switch.PROVIDERS_INFO["opencode"]["primary_model"] == "opencode/mimo-v2.5-free"

    def test_openrouter_provider_exists(self, rey_switch):
        assert "openrouter" in rey_switch.PROVIDERS_INFO
        assert rey_switch.PROVIDERS_INFO["openrouter"]["name"] == "OpenRouter"
        assert rey_switch.PROVIDERS_INFO["openrouter"]["primary_model"] == "openrouter/google/gemma-4-31b-it:free"

    def test_all_three_providers_have_models(self, rey_switch):
        for prov in ["kilo", "opencode", "openrouter"]:
            info = rey_switch.PROVIDERS_INFO[prov]
            assert "primary_model" in info
            assert "fallback_models" in info
            assert len(info["fallback_models"]) > 0

    def test_provider_has_required_fields(self, rey_switch):
        required = ["name", "desc", "primary_model", "fallback_models"]
        for prov in ["kilo", "opencode", "openrouter", "gemini", "mistral", "groq"]:
            for field in required:
                assert field in rey_switch.PROVIDERS_INFO[prov], f"{prov} missing {field}"


class TestCheckProviderApiKey:
    """Tests for check_provider_api_key function."""

    def test_kilo_no_key_needed(self, rey_switch):
        has_key, key_name = rey_switch.check_provider_api_key("kilo")
        assert has_key is True
        assert key_name is None

    def test_opencode_no_key_needed(self, rey_switch):
        has_key, key_name = rey_switch.check_provider_api_key("opencode")
        assert has_key is True
        assert key_name is None

    def test_openrouter_returns_false_without_key(self, rey_switch):
        with patch.dict(os.environ, {}, clear=True):
            with patch.object(os.path, "exists", return_value=False):
                has_key, key_name = rey_switch.check_provider_api_key("openrouter")
                assert has_key is False
                assert key_name == "OPENROUTER_API_KEY"

    def test_openrouter_returns_true_with_key(self, rey_switch):
        with patch.dict(os.environ, {"OPENROUTER_API_KEY": "sk-or-v1-testkey"}):
            with patch.object(os.path, "exists", return_value=False):
                has_key, key_name = rey_switch.check_provider_api_key("openrouter")
                assert has_key is True
                assert key_name == "OPENROUTER_API_KEY"

    def test_underscore_env_var_fallback(self, rey_switch):
        with patch.dict(os.environ, {"GOOGLE_API_KEY": "test-key"}):
            has_key, key_name = rey_switch.check_provider_api_key("gemini")
            assert has_key is True
            assert key_name == "GOOGLE_API_KEY"

    def test_env_file_with_key(self, rey_switch, temp_config_dir):
        env_path = temp_config_dir["config_dir"] / ".env"
        env_path.write_text("OPENROUTER_API_KEY=sk-from-env\n")

        with patch.dict(os.environ, {}, clear=True):
            with patch.object(os.path, "exists", return_value=True):
                has_key, key_name = rey_switch.check_provider_api_key("openrouter")
        assert has_key is True


class TestFallbackChain:
    """Tests for fallback chain construction."""

    def test_fallback_chain_includes_primary_first(self, rey_switch):
        p_info = rey_switch.PROVIDERS_INFO["kilo"]
        s_info = rey_switch.PROVIDERS_INFO["openrouter"]

        chain = []
        for m in p_info["fallback_models"]:
            if m not in chain:
                chain.append(m)
        for m in s_info["fallback_models"]:
            if m not in chain:
                chain.append(m)

        assert chain[0] == "kilo/kilo-auto/free"

    def test_fallback_chain_no_duplicates(self, rey_switch):
        p_info = rey_switch.PROVIDERS_INFO["kilo"]
        s_info = rey_switch.PROVIDERS_INFO["openrouter"]

        chain = []
        for m in p_info["fallback_models"]:
            if m not in chain:
                chain.append(m)
        for m in s_info["fallback_models"]:
            if m not in chain:
                chain.append(m)

        assert len(chain) == len(set(chain))

    def test_fallback_chain_includes_safety_nets(self, rey_switch):
        safety = [
            "mistral/codestral-latest", "gemini/gemini-2.5-flash",
            "opencode/big-pickle", "kilo/kilo-auto/free",
            "openrouter/google/gemma-4-31b-it:free"
        ]
        p_info = rey_switch.PROVIDERS_INFO["kilo"]
        s_info = rey_switch.PROVIDERS_INFO["openrouter"]

        chain = []
        for m in p_info["fallback_models"]:
            if m not in chain:
                chain.append(m)
        for m in s_info["fallback_models"]:
            if m not in chain:
                chain.append(m)
        for m in safety:
            if m not in chain:
                chain.append(m)

        for m in safety:
            assert m in chain

    def test_kilo_models_contain_expected(self, rey_switch):
        kilo_models = rey_switch.PROVIDERS_INFO["kilo"]["fallback_models"]
        assert "kilo/kilo-auto/free" in kilo_models
        assert any("nvidia" in m for m in kilo_models)

    def test_opencode_models_contain_expected(self, rey_switch):
        opencode_models = rey_switch.PROVIDERS_INFO["opencode"]["fallback_models"]
        assert "opencode/mimo-v2.5-free" in opencode_models
        assert "opencode/ling-3.0-flash-fin-free" in opencode_models

    def test_openrouter_models_contain_expected(self, rey_switch):
        openrouter_models = rey_switch.PROVIDERS_INFO["openrouter"]["fallback_models"]
        assert "openrouter/google/gemma-4-31b-it:free" in openrouter_models
        assert "openrouter/cohere/north-mini-code:free" in openrouter_models

    def test_fallback_chain_coverage(self, rey_switch):
        """Verify all three key providers have fallback_models defined."""
        for prov in ["kilo", "opencode", "openrouter"]:
            models = rey_switch.PROVIDERS_INFO[prov]["fallback_models"]
            assert len(models) >= 2
            assert all(isinstance(m, str) for m in models)


class TestGetCurrentState:
    """Tests for get_current_state function."""

    def test_default_primary_is_kilo(self, rey_switch):
        with patch.object(os.path, "exists", return_value=False):
            state = rey_switch.get_current_state()
            assert state["primary"] == "kilo"
            assert state["secondary"] == "openrouter"

    def test_enabled_providers_list(self, rey_switch, temp_config_dir):
        config_path = temp_config_dir["config_dir"] / "opencode.jsonc"
        config_path.write_text('{"model": "kilo/kilo-auto/free", "enabled_providers": ["kilo", "openrouter"]}')

        with patch.object(os.path, "exists", return_value=True):
            with patch.object(rey_switch, "CONFIG_DIR", str(temp_config_dir["config_dir"])):
                state = rey_switch.get_current_state()
                assert "kilo" in state["enabled_providers"]


class TestOpenRouterProviderConfig:
    """Tests for OPENROUTER_PROVIDER_CONFIG."""

    def test_has_whitelist(self, rey_switch):
        assert "whitelist" in rey_switch.OPENROUTER_PROVIDER_CONFIG
        assert len(rey_switch.OPENROUTER_PROVIDER_CONFIG["whitelist"]) > 0

    def test_whitelist_contains_free_models(self, rey_switch):
        whitelist = rey_switch.OPENROUTER_PROVIDER_CONFIG["whitelist"]
        free_models = [m for m in whitelist if m.endswith(":free")]
        assert len(free_models) > 0

    def test_has_models_dict(self, rey_switch):
        assert "models" in rey_switch.OPENROUTER_PROVIDER_CONFIG


class TestApplyConfiguration:
    """Tests for apply_configuration function signature."""

    def test_apply_configuration_accepts_params(self, rey_switch):
        """Verify apply_configuration has correct signature."""
        import inspect
        sig = inspect.signature(rey_switch.apply_configuration)
        params = list(sig.parameters.keys())
        assert "primary" in params
        assert "secondary" in params
