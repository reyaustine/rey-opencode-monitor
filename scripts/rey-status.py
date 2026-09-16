#!/usr/bin/env python3
"""
R.E.Y. // STATUS SNAPSHOT
Compact, single-line (or short multi-line) fleet status for scripting,
aliases, prompts, and quick checks. Supports --json for machine parsing.
"""

import os
import sys
import json
import subprocess

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME, ".config", "opencode")
SCRIPTS_DIR = os.path.join(CONFIG_DIR, "scripts")


def get_state():
    """Invoke rey-state.py and parse its JSON output."""
    state_script = os.path.join(SCRIPTS_DIR, "rey-state.py")
    if not os.path.exists(state_script):
        return {"ok": False, "error": "rey-state.py not found"}
    try:
        out = subprocess.run(
            [sys.executable, state_script],
            capture_output=True, text=True, timeout=15
        )
        if out.stdout:
            return json.loads(out.stdout)
    except Exception as e:
        return {"ok": False, "error": str(e)}
    return {"ok": False, "error": "no output"}


def get_quota():
    """Read cached OpenRouter quota (fast, no network)."""
    path = os.path.join(CONFIG_DIR, "openrouter-quota.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return None


def build_status():
    state = get_state()
    quota = get_quota()

    threads = state.get("active_threads", 0)
    model = state.get("override_model") or "-"
    rotation = state.get("rotation")
    if rotation and rotation.get("active"):
        model = f"{rotation.get('summary')} [ROTATING]"
    workspace = state.get("current_workspace", "-")

    health = "NOMINAL"
    mh = state.get("model_health")
    quota_budget = quota.get("budget_status") if quota else None
    quota_credits = float(quota.get("credits_remaining", 0) or 0) if quota else 0
    if quota and quota.get("is_rate_limited"):
        health = f"OR-429 ({quota.get('hours_left', 0)}h)"
    elif quota_budget == "DEPLETED":
        health = f"OR-DEPLETED (${quota_credits:.3f} left)"
    elif quota_budget == "CRITICAL":
        health = f"OR-CRITICAL (${quota_credits:.3f} left)"
    elif quota_budget == "LOW":
        health = f"OR-LOW (${quota_credits:.3f} left)"
    elif mh:
        if mh.get("unresponsive_count", 0) > 0:
            health = f"DEGRADED ({mh['unresponsive_count']} offline)"
        elif mh.get("running"):
            health = "CHECKING"
        elif mh.get("new_models_count", 0) > 0:
            health = f"NOMINAL (+{mh['new_models_count']} new)"

    or_quota = "?"
    if quota and quota.get("ok"):
        if quota.get("free_quota_known"):
            free_text = f"{quota.get('free_remaining', '?')}/{quota.get('free_limit', '?')}"
        else:
            free_text = "?/?"
        credits = float(quota.get("credits_remaining", 0) or 0)
        credit_limit = float(quota.get("credit_limit", 0) or 0)
        percent = float(quota.get("credit_percent_remaining", 0) or 0)
        daily = float(quota.get("usage_daily", 0) or 0)
        limit_text = f"{credit_limit:.2f}" if credit_limit > 0 else "?"
        or_quota = f"{free_text} free | ${credits:.3f}/${limit_text} ({percent:.1f}%) | today ${daily:.3f}"

    return {
        "ok": state.get("ok", False),
        "threads": threads,
        "model": model,
        "workspace": workspace,
        "health": health,
        "openrouter_quota": or_quota,
        "db_found": state.get("db_found", False),
    }


def main():
    as_json = "--json" in sys.argv or "-j" in sys.argv
    status = build_status()

    if as_json:
        print(json.dumps(status, indent=2))
        return 0

    if not status["ok"]:
        print("REY: OFFLINE (state unavailable)")
        return 1

    activity = "THINKING" if status["threads"] > 0 else "IDLE"
    line = (
        f"REY | {activity} | threads:{status['threads']} | "
        f"health:{status['health']} | OR:{status['openrouter_quota']} | "
        f"model:{status['model']} | ws:{status['workspace']}"
    )
    print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
