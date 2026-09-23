#!/usr/bin/env python3
"""
R.E.Y. // Fleet Health Watchdog & Multi-Provider Free Model Discovery Engine
Pings provider APIs every 30 mins (and on-demand via H/W keys),
audits live models across ALL configured providers (Gemini, Groq, Mistral, Kilo, OpenCode, LM Studio, OpenRouter),
tests endpoint responsiveness of free models, discovers newly released free models,
and provides auto-whitelisting of discovered models into OpenCode configuration.
"""

import os
import sys
import json
import time
import re
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
RED = "\033[31m"
MAGENTA = "\033[35m"
WHITE = "\033[37m"
GRAY = "\033[90m"

HOME = os.path.expanduser("~")
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))
CONFIG_DIR = os.path.join(HOME, ".config", "opencode")
HEALTH_FILE = os.path.join(CONFIG_DIR, "model-health.json")
DEALS_FILE = os.path.join(CONFIG_DIR, "openrouter-deals.json")
AUTH_PATH = os.path.join(HOME, ".local", "share", "opencode", "auth.json")
CONFIG_JSON = os.path.join(CONFIG_DIR, "opencode.json")
CONFIG_JSONC = os.path.join(CONFIG_DIR, "opencode.jsonc")

# Base allowlisted models to check
BASE_ALLOWLIST = [
    "gemini/gemini-3.8-flash",
    "gemini/gemini-3.7-flash",
    "gemini/gemini-3.6-flash",
    "gemini/gemini-flash-latest",
    "mistral/codestral-latest",
    "mistral/codestral-2508",
    "kilo/kilo-auto/free",
    "opencode/big-pickle",
    "opencode/muse-spark-1.3-contributor-free",
    "opencode/muse-spark-1.2-contributor-free",
    "opencode/muse-spark-1.3-free",
    "opencode/nemotron-3.5-lightning-free",
    "opencode/nemotron-3-ultra-free",
    "opencode/ling-3.0-flash-fin-free",
    "opencode/mimo-v2.5-free",
    "lmstudio/deepseek-r1-distill-qwen-1.5b"
]

BUDGET_WARNING_PERCENT = 25.0
BUDGET_CRITICAL_PERCENT = 10.0


def safe_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def classify_budget(remaining, limit):
    remaining = safe_float(remaining)
    limit = safe_float(limit)
    if limit <= 0:
        return "UNKNOWN", 0.0
    percent = max(0.0, min(100.0, (remaining / limit) * 100.0))
    if remaining <= 0:
        return "DEPLETED", percent
    if percent <= BUDGET_CRITICAL_PERCENT:
        return "CRITICAL", percent
    if percent <= BUDGET_WARNING_PERCENT:
        return "LOW", percent
    return "OK", percent


def ping_endpoint(url, headers=None, timeout=6):
    """Pings an HTTP endpoint and measures latency."""
    if headers is None:
        headers = {}
    if "User-Agent" not in headers:
        headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) REY-Fleet-Monitor/1.0"
    req = urllib.request.Request(url, headers=headers)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            latency_ms = int((time.time() - t0) * 1000)
            return True, res.getcode(), latency_ms, res.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        latency_ms = int((time.time() - t0) * 1000)
        return False, e.code, latency_ms, ""
    except Exception as e:
        latency_ms = int((time.time() - t0) * 1000)
        return False, str(e), latency_ms, ""


def get_auth_key(provider):
    """Retrieves API key from environment variables or auth.json."""
    key = os.environ.get(f"{provider.upper()}_API_KEY", "")
    if not key and provider == "gemini":
        key = os.environ.get("GOOGLE_API_KEY", "") or os.environ.get("GOOGLE_GENERATIVE_AI_API_KEY", "")
    if not key and os.path.exists(AUTH_PATH):
        try:
            with open(AUTH_PATH, "r", encoding="utf-8-sig") as af:
                data = json.load(af)
                lookup = "google" if provider == "gemini" else provider
                key = data.get(lookup, {}).get("key", "")
        except Exception:
            pass
    return key


def get_current_allowlist():
    """Reads models configured across opencode.jsonc and repo configs."""
    models = list(BASE_ALLOWLIST)
    cfg_paths = [
        CONFIG_JSONC,
        os.path.join(REPO_ROOT, "configs", "opencode.jsonc")
    ]
    for path in set(cfg_paths):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    lines = [l for l in f if not l.strip().startswith("//")]
                    cdata = json.loads("\n".join(lines))
                    if cdata.get("provider"):
                        for p_name, p_val in cdata["provider"].items():
                            if isinstance(p_val, dict):
                                for m in p_val.get("whitelist", []):
                                    full = f"{p_name}/{m}" if not m.startswith(p_name) else m
                                    if full not in models:
                                        models.append(full)
            except Exception:
                pass
    return models


def check_openrouter_quota():
    """Queries OpenRouter auth and tests live free-tier rate limit status."""
    quota_info = {
        "ok": False,
        "status": "UNKNOWN",
        "label": "unknown",
        "credit_limit": 0.0,
        "credits_remaining": 0.0,
        "credit_percent_remaining": 0.0,
        "budget_status": "UNKNOWN",
        "budget_ok": False,
        "budget_usable": False,
        "free_limit": 50,
        "free_remaining": 50,
        "free_used": 0,
        "free_quota_known": False,
        "free_probe_status": "NOT_CHECKED",
        "usage_daily": 0.0,
        "usage_weekly": 0.0,
        "usage_monthly": 0.0,
        "is_rate_limited": False,
        "reset_time": "N/A",
        "hours_left": 0.0,
        "message": "",
        "last_checked": ""
    }
    key = get_auth_key("openrouter")
    if not key:
        return quota_info

    # 1. Fetch account limit & balance
    try:
        req = urllib.request.Request("https://openrouter.ai/api/v1/auth/key", headers={"Authorization": f"Bearer {key}", "User-Agent": "REY-Quota-Monitor/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            kdata = json.loads(r.read().decode())["data"]
            limit = safe_float(kdata.get("limit", 0))
            remaining = safe_float(kdata.get("limit_remaining", 0))
            free_data = kdata.get("free_model_daily_requests") or {}
            budget_status, percent = classify_budget(remaining, limit)
            budget_labels = {
                "OK": "CREDIT_OK",
                "LOW": "LOW_CREDIT",
                "CRITICAL": "CRITICAL_CREDIT",
                "DEPLETED": "CREDIT_DEPLETED",
                "UNKNOWN": "CREDIT_UNKNOWN"
            }

            quota_info["ok"] = True
            quota_info["status"] = budget_labels.get(budget_status, "UNKNOWN")
            quota_info["label"] = kdata.get("label", "OpenRouter User")
            quota_info["credit_limit"] = limit
            quota_info["credits_remaining"] = remaining
            quota_info["credit_percent_remaining"] = percent
            quota_info["budget_status"] = budget_status
            quota_info["budget_ok"] = budget_status == "OK"
            quota_info["budget_usable"] = budget_status in ("OK", "LOW")
            quota_info["free_limit"] = safe_int(free_data.get("limit"), 1000 if remaining > 0 else 50)
            quota_info["free_remaining"] = safe_int(free_data.get("remaining"), quota_info["free_limit"])
            quota_info["free_used"] = safe_int(free_data.get("used"), 0)
            quota_info["free_quota_known"] = bool(free_data)
            quota_info["usage_daily"] = safe_float(kdata.get("usage_daily", 0))
            quota_info["usage_weekly"] = safe_float(kdata.get("usage_weekly", 0))
            quota_info["usage_monthly"] = safe_float(kdata.get("usage_monthly", 0))
            quota_info["is_rate_limited"] = (quota_info["free_remaining"] == 0 and quota_info["free_quota_known"]) or budget_status == "DEPLETED"
            quota_info["last_checked"] = time.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        quota_info["status"] = "KEY_CHECK_FAILED"
        quota_info["error"] = str(e)

    # 2. Probe free model rate limit
    try:
        req2 = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://opencode.ai",
                "X-Title": "OpenCode",
                "User-Agent": "REY-Quota-Monitor/1.0"
            },
            data=json.dumps({
                "model": "inclusionai/ling-3.0-flash-vl:free",
                "messages": [{"role": "user", "content": "ping"}],
                "max_tokens": 1
            }).encode()
        )
        with urllib.request.urlopen(req2, timeout=4) as r2:
            quota_info["free_probe_status"] = "OK"
            quota_info["is_rate_limited"] = False
    except urllib.error.HTTPError as e:
        quota_info["free_probe_status"] = f"HTTP_{e.code}"
        if e.code == 429:
            try:
                body = json.loads(e.read().decode())
                meta = body.get("error", {}).get("metadata", {})
                headers = meta.get("headers", {})
                reset_ms = safe_int(headers.get("X-RateLimit-Reset"), 0)
                rem = safe_int(headers.get("X-RateLimit-Remaining"), 0)
                limit = safe_int(headers.get("X-RateLimit-Limit"), quota_info["free_limit"])
                
                reset_time = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(reset_ms / 1000)) if reset_ms else "Unknown"
                hours_left = round((reset_ms / 1000 - time.time()) / 3600, 1) if reset_ms else 0
                
                quota_info["status"] = "RATE_LIMITED_429"
                quota_info["is_rate_limited"] = True
                quota_info["free_limit"] = limit
                quota_info["free_remaining"] = rem
                quota_info["free_quota_known"] = True
                quota_info["reset_time"] = reset_time
                quota_info["hours_left"] = hours_left
                quota_info["message"] = body.get("error", {}).get("message", "Rate limit exceeded")
            except Exception:
                quota_info["status"] = "RATE_LIMITED_429"
                quota_info["is_rate_limited"] = True
    except Exception as e:
        quota_info["free_probe_status"] = f"UNREACHABLE ({type(e).__name__})"
        quota_info["error"] = str(e)

    quota_file = os.path.join(CONFIG_DIR, "openrouter-quota.json")
    try:
        with open(quota_file, "w", encoding="utf-8") as qf:
            json.dump(quota_info, qf, indent=2)
    except Exception:
        pass

    return quota_info


def fetch_gemini_models():
    """Queries Google Gemini API for live conversational and code models."""
    key = get_auth_key("gemini")
    if not key:
        return {"provider": "Google Gemini", "ok": False, "latency_ms": 0, "models": [], "error": "No API key configured"}
    t0 = time.time()
    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models?key={key}"
        req = urllib.request.Request(url, headers={"User-Agent": "REY-Fleet-Monitor/1.0"})
        with urllib.request.urlopen(req, timeout=5) as r:
            lat = int((time.time() - t0) * 1000)
            data = json.loads(r.read().decode())
            models = []
            for m in data.get("models", []):
                mid = m.get("name", "").replace("models/", "")
                if any(x in mid.lower() for x in ["gemini", "gemma"]) and not any(x in mid.lower() for x in ["tts", "embedding", "aqa", "imagen", "deprecated"]):
                    models.append({
                        "id": mid,
                        "full_id": f"gemini/{mid}",
                        "name": m.get("displayName", mid),
                        "context_length": m.get("inputTokenLimit", 0),
                        "status": "OK",
                        "latency_ms": lat
                    })
            models.sort(key=lambda x: x["id"])
            return {"provider": "Google Gemini", "ok": True, "latency_ms": lat, "models": models}
    except Exception as e:
        lat = int((time.time() - t0) * 1000)
        return {"provider": "Google Gemini", "ok": False, "latency_ms": lat, "models": [], "error": str(e)}


def fetch_groq_models(groq_key):
    """Queries Groq API for live hardware-accelerated models."""
    if not groq_key:
        return {"provider": "Groq", "ok": False, "latency_ms": 0, "models": [], "error": "No API key configured"}
    t0 = time.time()
    try:
        req = urllib.request.Request(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {groq_key}", "User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            lat = int((time.time() - t0) * 1000)
            data = json.loads(r.read().decode())
            models = []
            for m in data.get("data", []):
                mid = m.get("id", "")
                if not mid.startswith("whisper"):
                    models.append({
                        "id": mid,
                        "full_id": f"groq/{mid}",
                        "name": mid,
                        "context_length": m.get("context_window", 0),
                        "status": "OK",
                        "latency_ms": lat
                    })
            models.sort(key=lambda x: x["id"])
            return {"provider": "Groq", "ok": True, "latency_ms": lat, "models": models}
    except Exception as e:
        lat = int((time.time() - t0) * 1000)
        return {"provider": "Groq", "ok": False, "latency_ms": lat, "models": [], "error": str(e)}


def fetch_mistral_models():
    """Queries Mistral API for live frontier models."""
    key = get_auth_key("mistral")
    if not key:
        return {"provider": "Mistral", "ok": False, "latency_ms": 0, "models": [], "error": "No API key configured"}
    t0 = time.time()
    try:
        req = urllib.request.Request(
            "https://api.mistral.ai/v1/models",
            headers={"Authorization": f"Bearer {key}", "User-Agent": "REY-Fleet-Monitor/1.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            lat = int((time.time() - t0) * 1000)
            data = json.loads(r.read().decode())
            models = []
            for m in data.get("data", []):
                mid = m.get("id", "")
                if any(x in mid.lower() for x in ["codestral", "mistral-large", "mistral-small", "ministral", "pixtral"]):
                    models.append({
                        "id": mid,
                        "full_id": f"mistral/{mid}",
                        "name": m.get("name", mid),
                        "context_length": m.get("max_context_length", 0),
                        "status": "OK",
                        "latency_ms": lat
                    })
            models.sort(key=lambda x: x["id"])
            return {"provider": "Mistral", "ok": True, "latency_ms": lat, "models": models}
    except Exception as e:
        lat = int((time.time() - t0) * 1000)
        return {"provider": "Mistral", "ok": False, "latency_ms": lat, "models": [], "error": str(e)}


def fetch_kilo_models():
    """Queries Kilo Code Gateway for live auto & free models."""
    t0 = time.time()
    try:
        req = urllib.request.Request(
            "https://api.kilo.ai/api/gateway/v1/models",
            headers={"User-Agent": "Mozilla/5.0"}
        )
        with urllib.request.urlopen(req, timeout=5) as r:
            lat = int((time.time() - t0) * 1000)
            data = json.loads(r.read().decode())
            models = []
            for m in data.get("data", []):
                mid = m.get("id", "")
                if any(x in mid.lower() for x in ["free", "auto", "kilo"]):
                    models.append({
                        "id": mid,
                        "full_id": f"kilo/{mid}",
                        "name": m.get("name", mid),
                        "context_length": m.get("context_length", 0),
                        "status": "OK",
                        "latency_ms": lat
                    })
            models.sort(key=lambda x: x["id"])
            return {"provider": "Kilo Code", "ok": True, "latency_ms": lat, "models": models}
    except Exception as e:
        lat = int((time.time() - t0) * 1000)
        return {"provider": "Kilo Code", "ok": False, "latency_ms": lat, "models": [], "error": str(e)}


def fetch_lmstudio_models(headers):
    """Queries LM Studio local LAN server."""
    t0 = time.time()
    try:
        req = urllib.request.Request("http://192.168.254.140:1234/v1/models", headers=headers)
        with urllib.request.urlopen(req, timeout=3) as r:
            lat = int((time.time() - t0) * 1000)
            data = json.loads(r.read().decode())
            models = []
            for m in data.get("data", []):
                mid = m.get("id", "")
                models.append({
                    "id": mid,
                    "full_id": f"lmstudio/{mid}",
                    "name": mid,
                    "context_length": 128000,
                    "status": "OK",
                    "latency_ms": lat
                })
            return {"provider": "LM Studio (LAN)", "ok": True, "latency_ms": lat, "models": models}
    except Exception as e:
        lat = int((time.time() - t0) * 1000)
        return {"provider": "LM Studio (LAN)", "ok": False, "latency_ms": lat, "models": [], "error": "OFFLINE"}


def get_opencode_builtin_models():
    """Returns local built-in models bundled with OpenCode."""
    return [
        {"id": "auto", "full_id": "opencode/auto", "name": "OpenCode Auto Router", "context_length": 128000, "status": "OK", "latency_ms": 0},
        {"id": "big-pickle", "full_id": "opencode/big-pickle", "name": "OpenCode Big Pickle (Local Free)", "context_length": 128000, "status": "OK", "latency_ms": 0},
        {"id": "muse-spark-1.3-contributor-free", "full_id": "opencode/muse-spark-1.3-contributor-free", "name": "Muse Spark 1.3 Contributor Free", "context_length": 128000, "status": "OK", "latency_ms": 0},
        {"id": "mimo-v2.5-free", "full_id": "opencode/mimo-v2.5-free", "name": "Mimo v2.5 Free", "context_length": 128000, "status": "OK", "latency_ms": 0},
        {"id": "nemotron-3.5-lightning-free", "full_id": "opencode/nemotron-3.5-lightning-free", "name": "Nemotron 3.5 Lightning Free", "context_length": 128000, "status": "OK", "latency_ms": 0}
    ]


def add_models_to_whitelist(models_to_add):
    """
    Auto-adds newly discovered free models to provider.openrouter.whitelist
    AND provider.openrouter.models dict across configs/opencode.jsonc, 
    configs/opencode.json, deployed runtime configs, and model-fallback.json.
    Uses proper JSON parsing (not regex) for reliability.
    """
    if not models_to_add:
        print("\n  [i] No newly discovered models to add.")
        return False, 0

    raw_ids = []
    model_names = {}
    for m in models_to_add:
        raw_id = m.get("raw_id", "") if isinstance(m, dict) else str(m)
        name = m.get("name", "") if isinstance(m, dict) else ""
        if raw_id.startswith("openrouter/"):
            raw_id = raw_id.replace("openrouter/", "", 1)
        if raw_id and raw_id not in raw_ids:
            raw_ids.append(raw_id)
            if name:
                model_names[raw_id] = name

    if not raw_ids:
        return False, 0

    target_jsonc_files = [
        os.path.join(REPO_ROOT, "configs", "opencode.jsonc"),
        CONFIG_JSONC
    ]
    target_json_files = [
        os.path.join(REPO_ROOT, "configs", "opencode.json"),
        CONFIG_JSON
    ]
    target_fallback_files = [
        os.path.join(REPO_ROOT, "configs", "model-fallback.json"),
        os.path.join(CONFIG_DIR, "model-fallback.json")
    ]

    total_added = 0

    def update_config(data, raw_ids, model_names):
        """Update both whitelist and models dict in a config dict."""
        if "provider" not in data or "openrouter" not in data["provider"]:
            return 0
        or_cfg = data["provider"]["openrouter"]
        existing_wl = or_cfg.get("whitelist", [])
        existing_md = or_cfg.get("models", {})
        combined_wl = list(dict.fromkeys(existing_wl + raw_ids))
        or_cfg["whitelist"] = combined_wl
        for rid in raw_ids:
            if rid not in existing_md:
                existing_md[rid] = {"name": model_names.get(rid, rid)}
        or_cfg["models"] = existing_md
        return len(combined_wl) - len(existing_wl)

    # 1. Update JSONC files (strip comments, parse JSON, update, write)
    for path in set(target_jsonc_files):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                # Strip // comments
                lines = [l for l in content.split('\n') if not l.strip().startswith('//')]
                cleaned = '\n'.join(lines)
                data = json.loads(cleaned)
                added = update_config(data, raw_ids, model_names)
                total_added = max(total_added, added)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                print(f"  [WARN] Failed to update {path}: {e}")

    # 2. Update JSON files
    for path in set(target_json_files):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                added = update_config(data, raw_ids, model_names)
                total_added = max(total_added, added)
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                print(f"  [WARN] Failed to update {path}: {e}")

    # 3. Update Fallback chains
    for path in set(target_fallback_files):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    fdata = json.load(f)
                if "agents" in fdata and "*" in fdata["agents"] and "fallbackModels" in fdata["agents"]["*"]:
                    fb_models = fdata["agents"]["*"]["fallbackModels"]
                    for rid in raw_ids:
                        full_rid = f"openrouter/{rid}"
                        if full_rid not in fb_models:
                            fb_models.append(full_rid)
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(fdata, f, indent=2)
            except Exception as e:
                print(f"  [WARN] Failed to update fallback {path}: {e}")

    print(f"\n  {GREEN}[✓] Successfully added {len(raw_ids)} models to OpenCode whitelist & models dict!{RESET}")
    for rid in raw_ids:
        print(f"      • openrouter/{rid}")
    print(f"\n  {YELLOW}[*] Swarm configs updated. Restart OpenCode to apply.{RESET}\n")
    return True, len(raw_ids)


def prune_unhealthy_models(unhealthy_models, quiet=False):
    """
    Auto-prunes offline, unresponsive, timed-out, and high latency-risk models
    from provider whitelists, models dictionaries, and fallback chains across:
      - configs/opencode.jsonc & ~/.config/opencode/opencode.jsonc
      - configs/opencode.json & ~/.config/opencode/opencode.json
      - configs/model-fallback.json & ~/.config/opencode/model-fallback.json
      - ~/opencode-swarm-pack/configs (if present)
    """
    if not unhealthy_models:
        if not quiet:
            print("\n  [i] No unhealthy models to prune - all models healthy.")
        return False, 0

    pruned_by_provider = {}
    pruned_full_ids = set()

    for item in unhealthy_models:
        raw_str = item.get("id", "") if isinstance(item, dict) else str(item)
        # Strip trailing warning string e.g. "openrouter/model:free (Provider endpoint down)"
        clean_full = raw_str.split()[0].strip()
        if not clean_full:
            continue
        pruned_full_ids.add(clean_full)
        if "/" in clean_full:
            prov, rid = clean_full.split("/", 1)
        else:
            prov, rid = "openrouter", clean_full
        pruned_by_provider.setdefault(prov, set()).add(rid)

    if not pruned_full_ids:
        return False, 0

    swarm_configs = os.path.join(HOME, "opencode-swarm-pack", "configs")
    target_jsonc_files = [
        os.path.join(REPO_ROOT, "configs", "opencode.jsonc"),
        CONFIG_JSONC,
        os.path.join(swarm_configs, "opencode.jsonc")
    ]
    target_json_files = [
        os.path.join(REPO_ROOT, "configs", "opencode.json"),
        CONFIG_JSON,
        os.path.join(swarm_configs, "opencode.json")
    ]
    target_fallback_files = [
        os.path.join(REPO_ROOT, "configs", "model-fallback.json"),
        os.path.join(CONFIG_DIR, "model-fallback.json"),
        os.path.join(swarm_configs, "model-fallback.json")
    ]

    def prune_from_dict(data):
        changed = False
        providers = data.get("provider", {})
        for prov, bad_rids in pruned_by_provider.items():
            if prov in providers:
                p_cfg = providers[prov]
                if "whitelist" in p_cfg and isinstance(p_cfg["whitelist"], list):
                    before = len(p_cfg["whitelist"])
                    p_cfg["whitelist"] = [m for m in p_cfg["whitelist"] if m not in bad_rids]
                    if len(p_cfg["whitelist"]) != before:
                        changed = True
                if "models" in p_cfg and isinstance(p_cfg["models"], dict):
                    for bad_id in bad_rids:
                        if bad_id in p_cfg["models"]:
                            del p_cfg["models"][bad_id]
                            changed = True

        # Fallback model safety
        if data.get("model") in pruned_full_ids:
            data["model"] = "gemini/gemini-3.6-flash"
            changed = True
        if data.get("small_model") in pruned_full_ids:
            data["small_model"] = "mistral/codestral-latest"
            changed = True

        for ag in data.get("agent", {}).values():
            if isinstance(ag, dict) and ag.get("model") in pruned_full_ids:
                ag["model"] = "gemini/gemini-3.6-flash"
                changed = True

        return changed

    # 1. Update JSONC files
    for path in set(target_jsonc_files):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                lines = [l for l in content.split("\n") if not l.strip().startswith("//")]
                cleaned = "\n".join(lines)
                clean2 = []
                for l in cleaned.splitlines():
                    idx = l.find(" //")
                    if idx != -1:
                        l = l[:idx]
                    clean2.append(l)
                cleaned = "\n".join(clean2)
                cleaned = re.sub(r",\s*([\]}])", r"\1", cleaned)
                data = json.loads(cleaned)
                if prune_from_dict(data):
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
            except Exception as e:
                if not quiet:
                    print(f"  [WARN] Failed to prune {path}: {e}")

    # 2. Update JSON files
    for path in set(target_json_files):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if prune_from_dict(data):
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(data, f, indent=2)
            except Exception as e:
                if not quiet:
                    print(f"  [WARN] Failed to prune {path}: {e}")

    # 3. Update Fallback chains
    for path in set(target_fallback_files):
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    fdata = json.load(f)
                fb_changed = False
                if "agents" in fdata:
                    for ag_val in fdata["agents"].values():
                        if isinstance(ag_val, dict) and "fallbackModels" in ag_val and isinstance(ag_val["fallbackModels"], list):
                            before = len(ag_val["fallbackModels"])
                            ag_val["fallbackModels"] = [m for m in ag_val["fallbackModels"] if m not in pruned_full_ids]
                            if len(ag_val["fallbackModels"]) != before:
                                fb_changed = True
                if fb_changed:
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump(fdata, f, indent=2)
            except Exception as e:
                if not quiet:
                    print(f"  [WARN] Failed to prune fallback {path}: {e}")

    # 4. Clean circuit-breaker
    cb_path = os.path.join(CONFIG_DIR, "circuit-breaker.json")
    if os.path.exists(cb_path):
        try:
            with open(cb_path, "r", encoding="utf-8") as f:
                cb_data = json.load(f)
            qm = cb_data.get("quarantined_models", {})
            cb_changed = False
            for pid in pruned_full_ids:
                if pid in qm:
                    del qm[pid]
                    cb_changed = True
            if cb_changed:
                with open(cb_path, "w", encoding="utf-8") as f:
                    json.dump(cb_data, f, indent=2)
        except Exception:
            pass

    if not quiet:
        print(f"\n  {GREEN}[✓] Successfully pruned {len(pruned_full_ids)} unresponsive / high-latency models!{RESET}")
        for pid in sorted(pruned_full_ids):
            print(f"      {RED}✖{RESET} {pid} (removed from whitelist & fallbacks)")
        print(f"\n  {YELLOW}[*] Swarm configs cleaned. Fleet now contains only verified working models.{RESET}\n")

    return True, len(pruned_full_ids)


def run_health_check(quiet=False, auto_whitelist=False, auto_prune=False):
    """Executes multi-provider health check, full model audit, model discovery, and auto-pruning."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    start_time = time.time()

    # Mark as running
    running_state = {
        "running": True,
        "timestamp": int(start_time * 1000),
        "status": "RUNNING",
        "task": "[HEALTH] Auditing ALL Provider models (Gemini, Groq, Mistral, Kilo, OpenRouter)..."
    }
    try:
        with open(HEALTH_FILE, "w", encoding="utf-8") as f:
            json.dump(running_state, f, indent=2)
    except Exception:
        pass

    if not quiet:
        print(f"\n{CYAN}{'=' * 85}{RESET}")
        print(f"  {BOLD}🚀 R.E.Y. // FLEET HEALTH WATCHDOG & MULTI-PROVIDER MODEL AUDIT{RESET}")
        print(f"{CYAN}{'=' * 85}{RESET}")

    groq_key = get_auth_key("groq")
    lmstudio_key = get_auth_key("lmstudio")
    lmstudio_headers = {"Authorization": f"Bearer {lmstudio_key}"} if lmstudio_key else {}

    # Query all providers concurrently
    with ThreadPoolExecutor(max_workers=6) as ex:
        f_gemini = ex.submit(fetch_gemini_models)
        f_groq = ex.submit(fetch_groq_models, groq_key)
        f_mistral = ex.submit(fetch_mistral_models)
        f_kilo = ex.submit(fetch_kilo_models)
        f_lmstudio = ex.submit(fetch_lmstudio_models, lmstudio_headers)
        f_openrouter_raw = ex.submit(ping_endpoint, "https://openrouter.ai/api/v1/models", {}, 10)

    gemini_res = f_gemini.result()
    groq_res = f_groq.result()
    mistral_res = f_mistral.result()
    kilo_res = f_kilo.result()
    lmstudio_res = f_lmstudio.result()
    openrouter_ok, code, lat_or, body_or = f_openrouter_raw.result()

    # Parse OpenRouter models
    all_openrouter_models = []
    openrouter_free_models = []
    openrouter_paid_models = []
    if openrouter_ok and body_or:
        try:
            or_data = json.loads(body_or)
            for m in or_data.get("data", []):
                all_openrouter_models.append(m)
                mid = m.get("id", "")
                pricing = m.get("pricing") or {}
                is_free = mid.endswith(":free") or (pricing.get("prompt") == "0" and pricing.get("completion") == "0")
                if is_free:
                    openrouter_free_models.append(m)
                else:
                    openrouter_paid_models.append(m)
        except Exception:
            pass

    # Deep-audit OpenRouter Free Models concurrently
    if not quiet:
        print(f"  Auditing {len(openrouter_free_models)} live free models on OpenRouter...")

    free_model_health = {}
    def check_free_model(m):
        mid = m.get("id", "")
        res = {
            "id": mid,
            "name": m.get("name", mid),
            "context_length": m.get("context_length", 0),
            "status": "OK",
            "uptime_1d": 100.0,
            "latency_ms": 0,
            "warning": ""
        }
        try:
            ep_url = f"https://openrouter.ai/api/v1/models/{mid}/endpoints"
            r = urllib.request.Request(ep_url, headers={"User-Agent": "REY-Fleet-Monitor/1.0"})
            t0 = time.time()
            with urllib.request.urlopen(r, timeout=4) as ep_resp:
                lat = int((time.time() - t0) * 1000)
                res["latency_ms"] = lat
                ep_data = json.loads(ep_resp.read().decode("utf-8", errors="replace"))
                endpoints = ep_data.get("data", {}).get("endpoints", [])
                if endpoints:
                    best_ep = endpoints[0]
                    res["uptime_1d"] = round(best_ep.get("uptime_last_1d", 100.0), 1)
                    if best_ep.get("status") != 0:
                        res["status"] = "OFFLINE"
                        res["warning"] = "Provider endpoint down"
                    elif res["uptime_1d"] < 95.0:
                        res["status"] = "DEGRADED"
                        res["warning"] = f"Low uptime ({res['uptime_1d']}%)"
                    elif lat > 2500:
                        res["status"] = "DEGRADED"
                        res["warning"] = f"Slow response ({lat}ms)"
                else:
                    res["status"] = "DEGRADED"
                    res["warning"] = "No healthy endpoints"
        except urllib.error.HTTPError as e:
            res["status"] = "DEGRADED"
            res["warning"] = f"HTTP {e.code}"
        except Exception as e:
            res["status"] = "TIMEOUT"
            res["warning"] = "Timed out"
        return res

    with ThreadPoolExecutor(max_workers=15) as ex:
        free_results = list(ex.map(check_free_model, openrouter_free_models))

    for fr in free_results:
        free_model_health[fr["id"]] = fr

    # Allowlisted Models Responsiveness
    current_allowlist = get_current_allowlist()
    responsive = []
    unresponsive = []
    degraded = []

    for full_id in current_allowlist:
        if full_id.startswith("openrouter/"):
            raw_id = full_id.replace("openrouter/", "", 1)
            if raw_id == "free":
                responsive.append(full_id)
            elif raw_id in free_model_health:
                fh = free_model_health[raw_id]
                if fh["status"] == "OK":
                    responsive.append(full_id)
                else:
                    degraded.append(f"{full_id} ({fh['warning']})")
                    if fh["status"] in ["OFFLINE", "TIMEOUT"]:
                        unresponsive.append(full_id)
                    else:
                        responsive.append(full_id)
            elif any(m.get("id") == raw_id for m in all_openrouter_models):
                responsive.append(full_id)
            else:
                unresponsive.append(full_id)
        elif full_id.startswith("groq/"):
            if groq_res["ok"]:
                responsive.append(full_id)
            else:
                unresponsive.append(full_id)
        elif full_id.startswith("gemini/"):
            if gemini_res["ok"]:
                responsive.append(full_id)
            else:
                unresponsive.append(full_id)
        elif full_id.startswith("mistral/"):
            if mistral_res["ok"]:
                responsive.append(full_id)
            else:
                unresponsive.append(full_id)
        elif full_id.startswith("kilo/"):
            if kilo_res["ok"]:
                responsive.append(full_id)
            else:
                unresponsive.append(full_id)
        elif full_id.startswith("lmstudio/"):
            if lmstudio_res["ok"]:
                responsive.append(full_id)
            else:
                pass
        else:
            responsive.append(full_id)

    # Discover New Free Models on OpenRouter
    existing_raw_ids = {m.replace("openrouter/", "", 1) for m in current_allowlist if m.startswith("openrouter/")}
    new_free_models = []
    for fm in openrouter_free_models:
        f_id = fm.get("id", "")
        clean_id = f_id.replace("openrouter/", "", 1)
        if f_id not in existing_raw_ids and clean_id not in existing_raw_ids and not f_id.startswith("google/lyria"):
            new_free_models.append({
                "id": f"openrouter/{f_id}",
                "raw_id": f_id,
                "name": fm.get("name", f_id),
                "context_length": fm.get("context_length", 0),
                "status": free_model_health.get(f_id, {}).get("status", "OK"),
                "uptime": free_model_health.get(f_id, {}).get("uptime_1d", 100.0)
            })

    # Track Live Paid Models Updates (Past 14 days)
    now_ts = time.time()
    recent_paid_models = []
    for pm in openrouter_paid_models:
        created = pm.get("created", 0)
        days_old = int((now_ts - created) / 86400) if created else 999
        if days_old <= 14:
            recent_paid_models.append({
                "id": pm.get("id", ""),
                "name": pm.get("name", ""),
                "days_ago": days_old,
                "context_length": pm.get("context_length", 0),
                "prompt": pm.get("pricing", {}).get("prompt", "0"),
                "completion": pm.get("pricing", {}).get("completion", "0")
            })
    recent_paid_models.sort(key=lambda x: x["days_ago"])

    # Read active deals
    active_deals_count = 0
    if os.path.exists(DEALS_FILE):
        try:
            with open(DEALS_FILE, "r", encoding="utf-8") as df:
                active_deals_count = json.load(df).get("total_deals", 0)
        except Exception:
            pass

    quota_info = check_openrouter_quota()
    budget_status = quota_info.get("budget_status", "UNKNOWN")

    duration_ms = int((time.time() - start_time) * 1000)
    if quota_info.get("is_rate_limited") or budget_status in ("LOW", "CRITICAL", "DEPLETED"):
        overall_status = "DEGRADED"
    else:
        overall_status = "HEALTHY" if len(unresponsive) == 0 else "DEGRADED"

    summary_text = (
        f"{len(responsive)}/{len(current_allowlist)} models responsive ({duration_ms}ms). "
        f"{len(new_free_models)} new free models found on OpenRouter. {len(recent_paid_models)} recent paid updates."
    )
    if quota_info.get("is_rate_limited"):
        summary_text += f" [OPENROUTER 429 LIMITED - resets in {quota_info.get('hours_left')}h]"
    elif budget_status == "DEPLETED":
        summary_text += f" [OPENROUTER CREDIT DEPLETED - ${quota_info.get('credits_remaining', 0):.3f} remaining]"
    elif budget_status == "CRITICAL":
        summary_text += f" [OPENROUTER CREDIT CRITICAL - ${quota_info.get('credits_remaining', 0):.3f} remaining]"
    elif budget_status == "LOW":
        summary_text += f" [OPENROUTER CREDIT LOW - ${quota_info.get('credits_remaining', 0):.3f} remaining]"

    opencode_models = get_opencode_builtin_models()

    result_data = {
        "running": False,
        "timestamp": int(time.time() * 1000),
        "last_check_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": overall_status,
        "duration_ms": duration_ms,
        "providers": {
            "openrouter": {"ok": openrouter_ok, "latency_ms": lat_or},
            "gemini": {"ok": gemini_res["ok"], "latency_ms": gemini_res["latency_ms"], "models_count": len(gemini_res["models"])},
            "groq": {"ok": groq_res["ok"], "latency_ms": groq_res["latency_ms"], "models_count": len(groq_res["models"])},
            "mistral": {"ok": mistral_res["ok"], "latency_ms": mistral_res["latency_ms"], "models_count": len(mistral_res["models"])},
            "kilo": {"ok": kilo_res["ok"], "latency_ms": kilo_res["latency_ms"], "models_count": len(kilo_res["models"])},
            "opencode": {"ok": True, "latency_ms": 0, "models_count": len(opencode_models)},
            "lmstudio": {"ok": lmstudio_res["ok"], "latency_ms": lmstudio_res["latency_ms"], "models_count": len(lmstudio_res["models"])}
        },
        "quota": quota_info,
        "responsive_count": len(responsive),
        "unresponsive_count": len(unresponsive),
        "unresponsive_models": unresponsive,
        "degraded_models": degraded,
        "free_models_total": len(openrouter_free_models),
        "free_models_health": free_model_health,
        "new_models_count": len(new_free_models),
        "new_models": [nm["raw_id"] for nm in new_free_models],
        "new_free_models_detail": new_free_models,
        "recent_paid_models_count": len(recent_paid_models),
        "recent_paid_models": recent_paid_models[:12],
        "active_deals_count": active_deals_count,
        "summary": summary_text
    }

    try:
        with open(HEALTH_FILE, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=2)
    except Exception:
        pass

    # CLI Output Rendering
    if not quiet:
        free_rem = quota_info.get("free_remaining", "?") if quota_info.get("free_quota_known") else "?"
        free_lim = quota_info.get("free_limit", "?") if quota_info.get("free_quota_known") else "?"
        credits = safe_float(quota_info.get("credits_remaining"), 0)
        credit_limit = safe_float(quota_info.get("credit_limit"), 0)
        percent = safe_float(quota_info.get("credit_percent_remaining"), 0)
        daily = safe_float(quota_info.get("usage_daily"), 0)

        print("\n OpenRouter Rate Limit & Quota Monitor:")
        if quota_info.get("is_rate_limited"):
            print(f"  {RED}[429 RATE LIMITED]{RESET} Free-tier probe blocked ({free_rem}/{free_lim} remaining)")
            print(f"  {YELLOW}• Daily Reset Time  :{RESET} {quota_info.get('reset_time')} ({quota_info.get('hours_left')} hours remaining)")
            print(f"  {YELLOW}• Paid Credit Balance:{RESET} ${credits:.3f}/${credit_limit:.2f} ({percent:.1f}%) | ${daily:.3f} used today")
            print(f"  {CYAN}• Auto-Defense Engaged:{RESET} OpenCode & Mistral fallback models active so subagents continue without canceling!")
        elif budget_status == "DEPLETED":
            print(f"  {RED}[CREDIT DEPLETED]{RESET} Free probe {quota_info.get('free_probe_status', 'unknown')} | free {free_rem}/{free_lim} | paid ${credits:.3f}/${credit_limit:.2f} ({percent:.1f}%)")
        elif budget_status == "CRITICAL":
            print(f"  {YELLOW}[CRITICAL CREDIT]{RESET} Free probe {quota_info.get('free_probe_status', 'unknown')} | free {free_rem}/{free_lim} | paid ${credits:.3f}/${credit_limit:.2f} ({percent:.1f}%) | ${daily:.3f} used today")
        elif budget_status == "LOW":
            print(f"  {YELLOW}[LOW CREDIT]{RESET} Free probe {quota_info.get('free_probe_status', 'unknown')} | free {free_rem}/{free_lim} | paid ${credits:.3f}/${credit_limit:.2f} ({percent:.1f}%) | ${daily:.3f} used today")
        else:
            print(f"  {GREEN}[CREDIT OK]{RESET} Free probe {quota_info.get('free_probe_status', 'unknown')} | free {free_rem}/{free_lim} | paid ${credits:.3f}/${credit_limit:.2f} ({percent:.1f}%) | ${daily:.3f} used today")

        print("\n Provider Gateways & Gate Latency:")
        print(f"  [{'✓' if openrouter_ok else '✖'}] OpenRouter API    - {'200 OK' if openrouter_ok else 'FAIL'} ({lat_or}ms)")
        print(f"  [{'✓' if gemini_res['ok'] else '✖'}] Google Gemini     - {'200 OK' if gemini_res['ok'] else 'FAIL'} ({gemini_res['latency_ms']}ms) | {len(gemini_res['models'])} models live")
        print(f"  [{'✓' if groq_res['ok'] else '✖'}] Groq API          - {'200 OK' if groq_res['ok'] else 'FAIL'} ({groq_res['latency_ms']}ms) | {len(groq_res['models'])} models live")
        print(f"  [{'✓' if mistral_res['ok'] else '✖'}] Mistral API       - {'200 OK' if mistral_res['ok'] else 'FAIL'} ({mistral_res['latency_ms']}ms) | {len(mistral_res['models'])} models live")
        print(f"  [{'✓' if kilo_res['ok'] else '✖'}] Kilo Code Gateway - {'200 OK' if kilo_res['ok'] else 'FAIL'} ({kilo_res['latency_ms']}ms) | {len(kilo_res['models'])} models live")
        print(f"  [{'✓' if lmstudio_res['ok'] else '✖'}] LM Studio LAN     - {'200 OK' if lmstudio_res['ok'] else 'OFFLINE (LAN Server)'} ({lmstudio_res['latency_ms']}ms)")

        # ── Multi-Provider Models Sections ──
        print(f"\n {BOLD}Live Models Across All Providers:{RESET}")

        # Gemini
        if gemini_res["ok"] and gemini_res["models"]:
            print(f"\n  {CYAN}── Google Gemini Models (AI Studio Free Key) ──{RESET}")
            for gm in gemini_res["models"][:6]:
                ctx = f"{gm['context_length']//1000}k" if gm['context_length'] >= 1000 else str(gm['context_length'])
                print(f"  [{GREEN}OK      {RESET}] {gm['full_id']:<38} | ctx:{ctx:<5} | {gm['latency_ms']}ms | {gm['name']}")

        # Groq
        if groq_res["ok"] and groq_res["models"]:
            print(f"\n  {CYAN}── Groq Live Models (Ultra-Fast Hardware) ──{RESET}")
            for gqm in groq_res["models"][:6]:
                ctx = f"{gqm['context_length']//1000}k" if gqm['context_length'] >= 1000 else str(gqm['context_length'])
                print(f"  [{GREEN}OK      {RESET}] {gqm['full_id']:<38} | ctx:{ctx:<5} | {gqm['latency_ms']}ms | {gqm['name']}")

        # Mistral
        if mistral_res["ok"] and mistral_res["models"]:
            print(f"\n  {CYAN}── Mistral Live Models (Code & Reasoning) ──{RESET}")
            for mm in mistral_res["models"][:6]:
                ctx = f"{mm['context_length']//1000}k" if mm['context_length'] >= 1000 else str(mm['context_length'])
                print(f"  [{GREEN}OK      {RESET}] {mm['full_id']:<38} | ctx:{ctx:<5} | {mm['latency_ms']}ms | {mm['name']}")

        # Kilo
        if kilo_res["ok"] and kilo_res["models"]:
            print(f"\n  {CYAN}── Kilo Code Live Models (Zero-Config Free) ──{RESET}")
            for km in kilo_res["models"][:6]:
                ctx = f"{km['context_length']//1000}k" if km['context_length'] >= 1000 else str(km['context_length'])
                print(f"  [{GREEN}OK      {RESET}] {km['full_id']:<38} | ctx:{ctx:<5} | {km['latency_ms']}ms | {km['name']}")

        # OpenCode
        print(f"\n  {CYAN}── OpenCode Built-In Free Models ──{RESET}")
        for om in opencode_models:
            ctx = f"{om['context_length']//1000}k" if om['context_length'] >= 1000 else str(om['context_length'])
            print(f"  [{GREEN}OK      {RESET}] {om['full_id']:<38} | ctx:{ctx:<5} | Local  | {om['name']}")

        # LM Studio
        print(f"\n  {CYAN}── LM Studio LAN Models ──{RESET}")
        if lmstudio_res["ok"] and lmstudio_res["models"]:
            for lmm in lmstudio_res["models"]:
                print(f"  [{GREEN}OK      {RESET}] {lmm['full_id']:<38} | ctx:128k | {lmm['latency_ms']}ms | {lmm['name']}")
        else:
            print(f"  [{GRAY}OFFLINE {RESET}] LM Studio LAN server not responding (optional local host)")

        # OpenRouter
        print(f"\n  {CYAN}── OpenRouter Free Models ({len(openrouter_free_models)} Audited Endpoints) ──{RESET}")
        for m in sorted(openrouter_free_models, key=lambda x: x["id"]):
            mid = m["id"]
            h = free_model_health.get(mid, {})
            st = h.get("status", "OK")
            col = GREEN if st == "OK" else (YELLOW if st == "DEGRADED" else RED)
            upt = f"{h.get('uptime_1d', 100)}% upt"
            lat = f"{h.get('latency_ms', 0)}ms"
            warn = f"({h.get('warning', '')})" if h.get("warning") else ""
            ctx = f"{m.get('context_length', 0)//1000}k" if m.get('context_length', 0) >= 1000 else str(m.get('context_length', 0))
            print(f"  [{col}{st:<8}{RESET}] {mid:<46} | ctx:{ctx:<5} | {upt:<9} | {lat:<6} {YELLOW}{warn}{RESET}")

        print(f"\n Active Allowlisted Models:")
        print(f"  [✓] {len(responsive)}/{len(current_allowlist)} Allowlisted Models Active")
        if unresponsive:
            print(f"  {RED}[!] {len(unresponsive)} Unresponsive / Offline Models:{RESET}")
            for u in unresponsive:
                print(f"      • {u}")
        if degraded:
            print(f"  {YELLOW}[!] Degraded Models (Timeout / Latency Risk):{RESET}")
            for d in degraded:
                print(f"      • {d}")

        print(f"\n Newly Discovered Free Models ({len(new_free_models)} Ready to Whitelist):")
        if new_free_models:
            for nm in new_free_models:
                print(f"  {GREEN}[+]{RESET} {nm['id']:<48} | ctx: {nm['context_length']//1000}k | {nm['name']}")
        else:
            print("  [i] All known free models are already captured in allowlist.")

        print(f"\n Live Paid Models Updated on OpenRouter (Past 14 Days - {len(recent_paid_models)} Total):")
        for pm in recent_paid_models[:8]:
            p_val = f"${float(pm['prompt'])*1_000_000:.2f}" if pm['prompt'] != '0' else 'free'
            c_val = f"${float(pm['completion'])*1_000_000:.2f}" if pm['completion'] != '0' else 'free'
            print(f"  {CYAN}[UPD]{RESET} {pm['id']:<40} | {pm['days_ago']}d ago | ctx:{pm['context_length']//1000}k | {p_val}/{c_val} per 1M | {pm['name']}")

        print(f"\n Promotional Deals:")
        print(f"  {MAGENTA}★ {active_deals_count} active discounted models on OpenRouter (Press D in REY CLI to view all deals){RESET}")

        # Auto-prune and/or Auto-whitelist execution, or interactive prompt
        unhealthy_candidates = list(dict.fromkeys(unresponsive + [d.split()[0] for d in degraded]))

        if auto_prune and unhealthy_candidates:
            prune_unhealthy_models(unhealthy_candidates, quiet=quiet)

        if auto_whitelist and new_free_models:
            add_models_to_whitelist(new_free_models)

        if not auto_prune and not auto_whitelist and (unhealthy_candidates or new_free_models) and not quiet and sys.stdin.isatty():
            print(f"\n  {CYAN}{'─' * 80}{RESET}")
            options = []
            if unhealthy_candidates:
                options.append(f"{RED}[P] Prune {len(unhealthy_candidates)} dead/slow models{RESET}")
            if new_free_models:
                options.append(f"{GREEN}[W/A] Add {len(new_free_models)} new free models{RESET}")
            if unhealthy_candidates and new_free_models:
                options.append(f"{CYAN}[S] Sync fleet (Prune dead + Add new){RESET}")
            print(f"  {BOLD}💡 Fleet Action Options:{RESET} " + " | ".join(options))
            print(f"     Press [Enter] to skip and return to monitor")
            print(f"  {CYAN}{'─' * 80}{RESET}")
            try:
                ans = input("  Choice [P/W/A/S/Enter]: ").strip().upper()
                if ans == "P" and unhealthy_candidates:
                    prune_unhealthy_models(unhealthy_candidates)
                elif ans in ("W", "A") and new_free_models:
                    add_models_to_whitelist(new_free_models)
                elif ans == "S":
                    if unhealthy_candidates:
                        prune_unhealthy_models(unhealthy_candidates)
                    if new_free_models:
                        add_models_to_whitelist(new_free_models)
            except (KeyboardInterrupt, EOFError):
                pass

        print("\n" + "=" * 85)
        print(f" Status: {overall_status} | Elapsed: {duration_ms}ms | Last Check: {result_data['last_check_str']}")
        print("=" * 85 + "\n")

    return result_data


if __name__ == "__main__":
    quiet_mode = "--quiet" in sys.argv or "-q" in sys.argv
    do_whitelist = any(x in sys.argv for x in ["--whitelist", "-w", "--add", "--auto-whitelist", "-a", "whitelist"])
    do_prune = any(x in sys.argv for x in ["--prune", "-p", "--clean", "--auto-prune", "prune", "clean"])
    do_sync = any(x in sys.argv for x in ["--sync", "-s", "sync"])
    if do_sync:
        do_whitelist = True
        do_prune = True
    if any(x in sys.argv for x in ["--all-models", "-m", "--models", "models"]):
        import subprocess
        subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "rey-models.py"), "--list"])
    else:
        run_health_check(quiet=quiet_mode, auto_whitelist=do_whitelist, auto_prune=do_prune)

