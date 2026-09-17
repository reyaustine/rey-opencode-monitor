"""Tests for rey-status.py functions."""

import json
import pytest
from unittest.mock import patch, MagicMock
import sys
import os


class TestGetState:
    """Tests for get_state function."""

    def test_returns_error_when_script_missing(self, rey_status, temp_config_dir):
        scripts_dir = temp_config_dir["config_dir"] / "scripts"
        scripts_dir.mkdir(exist_ok=True)
        state_script = scripts_dir / "rey-state.py"
        state_script.write_text("# dummy")

        with patch.object(rey_status.os.path, "exists", return_value=False):
            with patch.object(rey_status, "SCRIPTS_DIR", str(scripts_dir)):
                result = rey_status.get_state()
                assert result["ok"] is False
                assert "not found" in result["error"]

    def test_parses_json_output(self, rey_status, temp_config_dir):
        scripts_dir = temp_config_dir["config_dir"] / "scripts"
        scripts_dir.mkdir(exist_ok=True)
        state_script = scripts_dir / "rey-state.py"
        state_script.write_text("# dummy")

        expected_state = {
            "ok": True, "active_threads": 2, "override_model": "test/model",
            "current_workspace": "/test/workspace",
            "model_health": {"unresponsive_count": 0}
        }
        mock_proc = MagicMock()
        mock_proc.stdout = json.dumps(expected_state)
        mock_proc.stderr = ""

        with patch.object(rey_status, "SCRIPTS_DIR", str(scripts_dir)):
            with patch("subprocess.run", return_value=mock_proc):
                result = rey_status.get_state()

        assert result == expected_state

    def test_handles_subprocess_error(self, rey_status, temp_config_dir):
        scripts_dir = temp_config_dir["config_dir"] / "scripts"
        scripts_dir.mkdir(exist_ok=True)
        state_script = scripts_dir / "rey-state.py"
        state_script.write_text("# dummy")

        with patch.object(rey_status, "SCRIPTS_DIR", str(scripts_dir)):
            with patch("subprocess.run", side_effect=Exception("Process failed")):
                result = rey_status.get_state()

        assert result["ok"] is False
        assert "Process failed" in result["error"]

    def test_handles_invalid_json(self, rey_status, temp_config_dir):
        scripts_dir = temp_config_dir["config_dir"] / "scripts"
        scripts_dir.mkdir(exist_ok=True)
        state_script = scripts_dir / "rey-state.py"
        state_script.write_text("# dummy")

        mock_proc = MagicMock()
        mock_proc.stdout = "not valid json"
        mock_proc.stderr = ""

        with patch.object(rey_status, "SCRIPTS_DIR", str(scripts_dir)):
            with patch("subprocess.run", return_value=mock_proc):
                result = rey_status.get_state()

        assert result["ok"] is False
        assert "error" in result

    def test_returns_no_output(self, rey_status, temp_config_dir):
        scripts_dir = temp_config_dir["config_dir"] / "scripts"
        scripts_dir.mkdir(exist_ok=True)
        state_script = scripts_dir / "rey-state.py"
        state_script.write_text("# dummy")

        mock_proc = MagicMock()
        mock_proc.stdout = ""
        mock_proc.stderr = ""

        with patch.object(rey_status, "SCRIPTS_DIR", str(scripts_dir)):
            with patch("subprocess.run", return_value=mock_proc):
                result = rey_status.get_state()

        assert result["ok"] is False
        assert result["error"] == "no output"


class TestGetQuota:
    """Tests for get_quota function."""

    def test_reads_cached_quota(self, rey_status, temp_config_dir, fake_openrouter_quota_json):
        quota_path = temp_config_dir["config_dir"] / "openrouter-quota.json"
        quota_path.write_text(json.dumps(fake_openrouter_quota_json))

        with patch.object(rey_status, "CONFIG_DIR", str(temp_config_dir["config_dir"])):
            result = rey_status.get_quota()

        assert result == fake_openrouter_quota_json

    def test_returns_none_when_missing(self, rey_status, temp_config_dir):
        with patch.object(rey_status, "CONFIG_DIR", str(temp_config_dir["config_dir"])):
            result = rey_status.get_quota()
            assert result is None

    def test_handles_malformed_json(self, rey_status, temp_config_dir):
        quota_path = temp_config_dir["config_dir"] / "openrouter-quota.json"
        quota_path.write_text("not valid json")

        with patch.object(rey_status, "CONFIG_DIR", str(temp_config_dir["config_dir"])):
            result = rey_status.get_quota()
            assert result is None


class TestBuildStatusDeterministic:
    """Tests for build_status function - deterministic output."""

    @pytest.fixture
    def mock_state(self):
        return {
            "ok": True, "active_threads": 1, "override_model": "kilo/kilo-auto/free",
            "current_workspace": "/home/user/project",
            "model_health": {"unresponsive_count": 0, "running": False, "new_models_count": 3},
            "missing_api_keys": [], "db_found": True, "rotation": None
        }

    def _mock_quota(self, budget_status="OK"):
        return {
            "ok": True, "budget_status": budget_status, "credits_remaining": 5.0,
            "credit_limit": 10.0, "credit_percent_remaining": 50.0,
            "free_quota_known": True, "free_remaining": 800, "free_limit": 1000,
            "usage_daily": 0.1, "is_rate_limited": False, "hours_left": 0.0
        }

    def _clean_state(self, state, mh=None):
        s = dict(state)
        if mh is not None:
            s["model_health"] = mh
        else:
            s["model_health"] = {"unresponsive_count": 0, "running": False, "new_models_count": 0}
        return s

    def test_builds_status_with_quota(self, rey_status, mock_state):
        quota = self._mock_quota("OK")
        with patch.object(rey_status, "get_state", return_value=mock_state):
            with patch.object(rey_status, "get_quota", return_value=quota):
                result = rey_status.build_status()

        assert result["ok"] is True
        assert result["threads"] == 1
        assert result["model"] == "kilo/kilo-auto/free"
        assert result["workspace"] == "/home/user/project"
        assert "800/1000 free" in result["openrouter_quota"]
        assert result["db_found"] is True

    def test_health_nominal_when_no_issues(self, rey_status, mock_state):
        quota = self._mock_quota("OK")
        state = self._clean_state(mock_state)

        with patch.object(rey_status, "get_state", return_value=state):
            with patch.object(rey_status, "get_quota", return_value=quota):
                result = rey_status.build_status()

        assert result["health"] == "NOMINAL"

    def test_health_degraded_when_unresponsive(self, rey_status, mock_state):
        quota = self._mock_quota("OK")
        state = self._clean_state(mock_state, {"unresponsive_count": 2, "running": False, "new_models_count": 0})

        with patch.object(rey_status, "get_state", return_value=state):
            with patch.object(rey_status, "get_quota", return_value=quota):
                result = rey_status.build_status()

        assert "DEGRADED" in result["health"]
        assert "2 offline" in result["health"]

    def test_health_checking_when_running(self, rey_status, mock_state):
        quota = self._mock_quota("OK")
        state = self._clean_state(mock_state, {"unresponsive_count": 0, "running": True, "new_models_count": 0})

        with patch.object(rey_status, "get_state", return_value=state):
            with patch.object(rey_status, "get_quota", return_value=quota):
                result = rey_status.build_status()

        assert result["health"] == "CHECKING"

    def test_health_new_models(self, rey_status, mock_state):
        quota = self._mock_quota("OK")
        state = self._clean_state(mock_state, {"unresponsive_count": 0, "running": False, "new_models_count": 5})

        with patch.object(rey_status, "get_state", return_value=state):
            with patch.object(rey_status, "get_quota", return_value=quota):
                result = rey_status.build_status()

        assert "NOMINAL (+5 new)" == result["health"]

    def test_rate_limited_health(self, rey_status, mock_state):
        quota = self._mock_quota("OK")
        quota["is_rate_limited"] = True
        quota["hours_left"] = 1.5
        quota["budget_status"] = "OK"

        with patch.object(rey_status, "get_state", return_value=mock_state):
            with patch.object(rey_status, "get_quota", return_value=quota):
                result = rey_status.build_status()

        assert "OR-429 (1.5h)" == result["health"]

    def test_depleted_health(self, rey_status, mock_state):
        quota = self._mock_quota("DEPLETED")
        quota["credits_remaining"] = 0.0
        quota["is_rate_limited"] = False

        with patch.object(rey_status, "get_state", return_value=mock_state):
            with patch.object(rey_status, "get_quota", return_value=quota):
                result = rey_status.build_status()

        assert "OR-DEPLETED ($0.000 left)" == result["health"]

    def test_critical_health(self, rey_status, mock_state):
        quota = self._mock_quota("CRITICAL")
        quota["credits_remaining"] = 0.5
        quota["is_rate_limited"] = False

        with patch.object(rey_status, "get_state", return_value=mock_state):
            with patch.object(rey_status, "get_quota", return_value=quota):
                result = rey_status.build_status()

        assert "OR-CRITICAL ($0.500 left)" == result["health"]

    def test_missing_api_keys_health(self, rey_status, mock_state):
        quota = self._mock_quota("OK")
        state = dict(mock_state)
        state["missing_api_keys"] = ["OPENROUTER_API_KEY", "GROQ_API_KEY"]

        with patch.object(rey_status, "get_state", return_value=state):
            with patch.object(rey_status, "get_quota", return_value=quota):
                result = rey_status.build_status()

        assert "MISSING API KEY" in result["health"]
        assert "OPENROUTER_API_KEY" in result["health"]

    def test_rotation_active_model(self, rey_status, mock_state):
        quota = self._mock_quota("OK")
        state = dict(mock_state)
        state["rotation"] = {"active": True, "summary": "kilo + openrouter"}

        with patch.object(rey_status, "get_state", return_value=state):
            with patch.object(rey_status, "get_quota", return_value=quota):
                result = rey_status.build_status()

        assert "kilo + openrouter [ROTATING]" == result["model"]

    def test_quota_unknown_when_missing(self, rey_status, mock_state):
        with patch.object(rey_status, "get_state", return_value=mock_state):
            with patch.object(rey_status, "get_quota", return_value=None):
                result = rey_status.build_status()

        assert result["openrouter_quota"] == "?"

    def test_quota_unknown_when_not_ok(self, rey_status, mock_state):
        mock_quota = {"ok": False}
        with patch.object(rey_status, "get_state", return_value=mock_state):
            with patch.object(rey_status, "get_quota", return_value=mock_quota):
                result = rey_status.build_status()

        assert result["openrouter_quota"] == "?"

    def test_free_quota_unknown_formatting(self, rey_status, mock_state):
        mock_quota = {"ok": True, "free_quota_known": False}
        state = self._clean_state(mock_state)

        with patch.object(rey_status, "get_state", return_value=state):
            with patch.object(rey_status, "get_quota", return_value=mock_quota):
                result = rey_status.build_status()

        assert "?/? free" in result["openrouter_quota"]

    def test_state_offline(self, rey_status):
        mock_state = {"ok": False, "error": "State unavailable"}
        with patch.object(rey_status, "get_state", return_value=mock_state):
            with patch.object(rey_status, "get_quota", return_value=None):
                result = rey_status.build_status()

        assert result["ok"] is False
        assert result["threads"] == 0

    def test_deterministic_output(self, rey_status, mock_state):
        """Verify build_status produces identical results for identical inputs."""
        quota = self._mock_quota("OK")
        state = self._clean_state(mock_state)

        with patch.object(rey_status, "get_state", return_value=state):
            with patch.object(rey_status, "get_quota", return_value=quota):
                result1 = rey_status.build_status()
                result2 = rey_status.build_status()

        assert result1 == result2
        assert result1["health"] == result2["health"]
        assert result1["openrouter_quota"] == result2["openrouter_quota"]

    def test_build_status_with_none_state(self, rey_status):
        """Test build_status handles None-like state gracefully."""
        with patch.object(rey_status, "get_state", return_value={"ok": False}):
            with patch.object(rey_status, "get_quota", return_value=None):
                result = rey_status.build_status()

        assert result["ok"] is False
        assert result["threads"] == 0


class TestMainFunction:
    """Tests for main() function."""

    def test_json_output(self, capsys, rey_status):
        mock_status = {"ok": True, "threads": 0, "health": "NOMINAL"}

        with patch.object(rey_status, "build_status", return_value=mock_status):
            with patch("sys.argv", ["rey-status.py", "--json"]):
                exit_code = rey_status.main()

        captured = capsys.readouterr()
        assert exit_code == 0
        output = json.loads(captured.out)
        assert output == mock_status

    def test_offline_output(self, capsys, rey_status):
        mock_status = {"ok": False}

        with patch.object(rey_status, "build_status", return_value=mock_status):
            with patch("sys.argv", ["rey-status.py"]):
                exit_code = rey_status.main()

        captured = capsys.readouterr()
        assert exit_code == 1
        assert "OFFLINE" in captured.out
