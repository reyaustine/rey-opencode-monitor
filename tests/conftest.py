"""Pytest fixtures for REY test suite."""

import json
import tempfile
import os
import sys
from pathlib import Path
import importlib.util
import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))


def load_script_module(name):
    """Load a Python module from a hyphenated script filename."""
    path = SCRIPTS_DIR / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name.replace("-", "_"), path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name.replace("-", "_")] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def temp_config_dir():
    """Create a temporary config directory structure."""
    with tempfile.TemporaryDirectory() as tmpdir:
        config_dir = Path(tmpdir) / ".config" / "opencode"
        config_dir.mkdir(parents=True)
        local_share = Path(tmpdir) / ".local" / "share" / "opencode"
        local_share.mkdir(parents=True)
        yield {
            "config_dir": config_dir,
            "local_share": local_share,
            "home": Path(tmpdir),
        }


@pytest.fixture
def fake_token_tracker_json():
    """Return a fake token-tracker.json content."""
    return {
        "machine": "TEST-MACHINE",
        "user": "testuser",
        "last_updated": "2026-09-17T12:00:00",
        "grand_total": {
            "total": 1000000,
            "total_fmt": "1.0M",
            "prompt": 500000,
            "prompt_fmt": "500.0k",
            "completion": 100000,
            "completion_fmt": "100.0k",
            "reasoning": 50000,
            "reasoning_fmt": "50.0k",
            "cache_read": 350000,
            "cache_read_fmt": "350.0k",
            "cost": 0.0,
            "calls": 100
        },
        "models": [
            {
                "provider": "openrouter",
                "model": "test/model:free",
                "prompt": 100000,
                "prompt_fmt": "100.0k",
                "completion": 20000,
                "completion_fmt": "20.0k",
                "reasoning": 5000,
                "reasoning_fmt": "5.0k",
                "cache_read": 50000,
                "cache_read_fmt": "50.0k",
                "total": 175000,
                "total_fmt": "175.0k",
                "cost": 0.0,
                "calls": 10
            }
        ]
    }


@pytest.fixture
def fake_openrouter_quota_json():
    """Return a fake openrouter-quota.json content."""
    return {
        "ok": True,
        "status": "LOW_CREDIT",
        "label": "sk-or-v1-test...key",
        "credit_limit": 10.0,
        "credits_remaining": 2.5,
        "credit_percent_remaining": 25.0,
        "budget_status": "LOW",
        "budget_ok": False,
        "budget_usable": True,
        "free_limit": 1000,
        "free_remaining": 800,
        "free_used": 200,
        "free_quota_known": True,
        "free_probe_status": "OK",
        "usage_daily": 0.1,
        "usage_weekly": 0.5,
        "usage_monthly": 1.0,
        "is_rate_limited": False,
        "reset_time": "N/A",
        "hours_left": 0.0,
        "message": "",
        "last_checked": "2026-09-17 12:00:00"
    }


@pytest.fixture
def fake_auth_json():
    """Return a fake auth.json content."""
    return {
        "openrouter": {"key": "sk-or-v1-fakekey123"},
        "groq": {"key": "gsk_fakekey456"},
        "gemini": {"key": "fake-gemini-key"},
        "mistral": {"key": "fake-mistral-key"}
    }


@pytest.fixture
def mock_env(monkeypatch):
    """Mock environment variables for testing."""
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-or-v1-envkey123")
    monkeypatch.setenv("GROQ_API_KEY", "gsk_envkey456")
    monkeypatch.setenv("GEMINI_API_KEY", "env-gemini-key")
    monkeypatch.setenv("MISTRAL_API_KEY", "env-mistral-key")


@pytest.fixture
def sample_quota_response():
    """Sample OpenRouter quota API response."""
    return {
        "data": {
            "label": "sk-or-v1-test...key",
            "limit": 10.0,
            "limit_remaining": 2.5,
            "free_model_daily_requests": {
                "limit": 1000,
                "remaining": 800,
                "used": 200
            },
            "usage_daily": 0.1,
            "usage_weekly": 0.5,
            "usage_monthly": 1.0
        }
    }


@pytest.fixture
def sample_models_response():
    """Sample OpenRouter models API response."""
    return {
        "data": [
            {
                "id": "google/gemma-4-31b-it:free",
                "name": "Google Gemma 4 31B (free)",
                "context_length": 8192,
                "pricing": {"prompt": "0", "completion": "0"}
            },
            {
                "id": "openrouter/free",
                "name": "OpenRouter Auto Free",
                "context_length": 4096,
                "pricing": {"prompt": "0", "completion": "0"}
            },
            {
                "id": "anthropic/claude-3-opus",
                "name": "Claude 3 Opus",
                "context_length": 200000,
                "pricing": {"prompt": "15.00", "completion": "75.00"}
            }
        ]
    }


@pytest.fixture
def no_network(monkeypatch):
    """Disable network calls by default."""
    import urllib.request

    def mock_urlopen(*args, **kwargs):
        raise RuntimeError("Network calls are disabled in tests")

    monkeypatch.setattr(urllib.request, "urlopen", mock_urlopen)


@pytest.fixture
def enable_network(monkeypatch):
    """Re-enable network for specific tests that need it."""
    pass


@pytest.fixture
def rey_quota():
    """Load rey-quota module for testing."""
    return load_script_module("rey-quota")


@pytest.fixture
def rey_status():
    """Load rey-status module for testing."""
    return load_script_module("rey-status")


@pytest.fixture
def rey_switch():
    """Load rey-switch module for testing."""
    return load_script_module("rey-switch")


@pytest.fixture
def rey_models():
    """Load rey-models module for testing."""
    return load_script_module("rey-models")


@pytest.fixture
def rey_state():
    """Load rey-state module for testing."""
    return load_script_module("rey-state")
