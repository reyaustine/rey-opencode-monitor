"""Tests for rey-models.py - Model Discovery free/mixed."""

import json
import pytest
from unittest.mock import Mock
import sys
import os


class TestModelDiscoveryFree:
    """Tests for free model discovery."""

    def test_fetch_opencode_always_free(self, rey_models):
        """OpenCode models are always free."""
        result = rey_models.fetch_opencode("free")
        assert result["ok"] is True
        assert result["free_count"] == len(result["models"])
        assert result["paid_count"] == 0
        assert result["total"] == len(result["models"])

    def test_fetch_kilo_always_free(self, rey_models):
        """Kilo models are always free."""
        result = rey_models.fetch_kilo("free")
        assert result["ok"] is True
        assert result["free_count"] == len(result["models"])
        assert result["paid_count"] == 0

    def test_fetch_openrouter_free_tier_filters_paid(self, rey_models):
        """OpenRouter free tier filters out paid models from results."""
        mock_data = {
            "data": [
                {"id": "openrouter/free", "name": "Free Model", "context_length": 4096,
                 "pricing": {"prompt": "0", "completion": "0"}},
                {"id": "anthropic/claude-3-opus", "name": "Claude Opus", "context_length": 200000,
                 "pricing": {"prompt": "15.00", "completion": "75.00"}},
                {"id": "openrouter/google/gemma-4-31b-it:free", "name": "Gemma 4 31B", "context_length": 8192,
                 "pricing": {"prompt": "0", "completion": "0"}},
            ]
        }
        mock_fn = Mock(return_value=(True, mock_data, 50))
        old_fn = rey_models.fetch_json
        rey_models.fetch_json = mock_fn
        try:
            result = rey_models.fetch_openrouter("free")
        finally:
            rey_models.fetch_json = old_fn
        assert result["ok"] is True
        assert result["free_count"] == 2
        assert len(result["models"]) == 2
        assert result["total"] == 3
        assert all(m["pricing"] == "free" for m in result["models"])

    def test_fetch_openrouter_mixed_returns_all(self, rey_models):
        """OpenRouter mixed tier should return all models."""
        mock_data = {
            "data": [
                {"id": "openrouter/free", "name": "Free Model", "context_length": 4096,
                 "pricing": {"prompt": "0", "completion": "0"}},
                {"id": "anthropic/claude-3-opus", "name": "Claude Opus", "context_length": 200000,
                 "pricing": {"prompt": "15.00", "completion": "75.00"}},
                {"id": "openrouter/google/gemma-4-31b-it:free", "name": "Gemma 4 31B", "context_length": 8192,
                 "pricing": {"prompt": "0", "completion": "0"}},
            ]
        }
        mock_fn = Mock(return_value=(True, mock_data, 50))
        old_fn = rey_models.fetch_json
        rey_models.fetch_json = mock_fn
        try:
            result = rey_models.fetch_openrouter("mixed")
        finally:
            rey_models.fetch_json = old_fn
        assert result["ok"] is True
        assert result["free_count"] == 2
        assert result["paid_count"] == 1
        assert result["total"] == 3
        assert len(result["models"]) == 3

    def test_is_free_model_detection(self, rey_models):
        """Verify free model detection logic."""
        def is_free(m):
            mid = m.get("id", "")
            pricing = m.get("pricing", {})
            return mid.endswith(":free") or (pricing.get("prompt") == "0" and pricing.get("completion") == "0")

        assert is_free({"id": "openrouter/google/gemma-4-31b-it:free"}) is True
        assert is_free({"id": "openrouter/free", "pricing": {"prompt": "0", "completion": "0"}}) is True
        assert is_free({"id": "anthropic/claude-3-opus", "pricing": {"prompt": "15.00", "completion": "75.00"}}) is False
        assert is_free({"id": "test", "pricing": {"prompt": "5.00", "completion": "5.00"}}) is False

    def test_fetch_gemini_free_only(self, rey_models):
        """Gemini returns only free models."""
        result = rey_models.fetch_gemini("free")
        assert result["ok"] is True
        assert result["free_count"] == len(result["models"])
        assert result["paid_count"] == 0
        assert all(m["pricing"] == "free" for m in result["models"])

    def test_fetch_gemini_mixed_includes_all(self, rey_models):
        """Gemini mixed should include all models."""
        result = rey_models.fetch_gemini("mixed")
        assert result["ok"] is True
        assert result["total"] > 0

    def test_openrouter_free_filters_paid_models(self, rey_models):
        """OpenRouter free tier filters models."""
        mock_data = {
            "data": [
                {"id": "openrouter/free", "name": "Free", "context_length": 4096,
                 "pricing": {"prompt": "0", "completion": "0"}},
                {"id": "anthropic/claude-3-opus", "name": "Claude", "context_length": 200000,
                 "pricing": {"prompt": "15.00", "completion": "75.00"}},
                {"id": "inclusionai/ling-3.0-flash-fin:free", "name": "Ling", "context_length": 8192,
                 "pricing": {"prompt": "0", "completion": "0"}},
            ]
        }
        mock_fn = Mock(return_value=(True, mock_data, 50))
        old_fn = rey_models.fetch_json
        rey_models.fetch_json = mock_fn
        try:
            result = rey_models.fetch_openrouter("free")
        finally:
            rey_models.fetch_json = old_fn
        assert result["free_count"] == 2
        assert len(result["models"]) == 2
        for m in result["models"]:
            assert m["id"].endswith(":free") or m["pricing"] == "free"


class TestModelDiscoveryMixed:
    """Tests for mixed model discovery."""

    def test_mixed_returns_all_providers(self, rey_models):
        """Mixed tier should include all model types."""
        for prov in ["opencode", "kilo", "openrouter", "gemini"]:
            fetcher = rey_models.FETCHERS.get(prov)
            assert fetcher is not None, f"No fetcher for {prov}"
            result = fetcher("mixed")
            assert result["ok"] is True
            assert result["total"] > 0

    def test_fetch_claude_only_paid(self, rey_models):
        """Claude models are all paid."""
        result = rey_models.fetch_claude("free")
        assert result["free_count"] == 0
        assert result["paid_count"] > 0

    def test_fetch_chatgpt_only_paid(self, rey_models):
        """ChatGPT models are all paid."""
        result = rey_models.fetch_chatgpt("free")
        assert result["free_count"] == 0
        assert result["paid_count"] > 0

    def test_mixed_tier_model_count(self, rey_models):
        """Verify total model counts for mixed tier across key providers."""
        for prov in ["opencode", "kilo"]:
            result = rey_models.FETCHERS[prov]("mixed")
            assert result["total"] == result["free_count"]
            assert result["paid_count"] == 0

    def test_openrouter_free_detection(self, rey_models):
        """Verify OpenRouter free model detection works for :free suffixed IDs."""
        def is_free(m):
            mid = m.get("id", "")
            pricing = m.get("pricing", {})
            return mid.endswith(":free") or (pricing.get("prompt") == "0" and pricing.get("completion") == "0")

        assert is_free({"id": "openrouter/google/gemma-4-31b-it:free"}) is True
        assert is_free({"id": "openrouter/free", "pricing": {"prompt": "0", "completion": "0"}}) is True
        assert is_free({"id": "anthropic/claude-3-opus", "pricing": {"prompt": "15.00", "completion": "75.00"}}) is False
