#!/usr/bin/env python3
"""
R.E.Y. // Dynamic Model Discovery Engine
Fetches live models from each enabled provider, filters by tier (free/mixed),
and outputs JSON for the setup wizard and roster generator.
"""

import json
import os
import sys
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME = Path.home()
CONFIG_DIR = HOME / ".config" / "opencode"
BYOK_CONFIG = CONFIG_DIR / "byok-config.json"
MODEL_TIER = CONFIG_DIR / "model-tier.json"
LIVE_MODELS = CONFIG_DIR / "live-models.json"
AUTH_PATH = HOME / ".local" / "share" / "opencode" / "auth.json"

# ── Hardcoded model lists for providers without public APIs ──────────────────

GEMINI_MODELS = [
    {"id": "gemini-2.5-pro",        "name": "Gemini 2.5 Pro",        "context_length": 1048576, "pricing": "free"},
    {"id": "gemini-2.5-flash",      "name": "Gemini 2.5 Flash",      "context_length": 1048576, "pricing": "free"},
    {"id": "gemini-2.0-flash",      "name": "Gemini 2.0 Flash",      "context_length": 1048576, "pricing": "free"},
]

CLAUDE_MODELS = [
    {"id": "claude-opus-4-20250514",    "name": "Claude Opus 4",     "context_length": 200000, "pricing": "paid"},
    {"id": "claude-sonnet-4-20250514",  "name": "Claude Sonnet 4",   "context_length": 200000, "pricing": "paid"},
    {"id": "claude-haiku-3-5-20241022", "name": "Claude 3.5 Haiku",  "context_length": 200000, "pricing": "paid"},
]

CHATGPT_MODELS = [
    {"id": "gpt-4.1",        "name": "GPT-4.1",        "context_length": 1050000, "pricing": "paid"},
    {"id": "gpt-4.1-mini",   "name": "GPT-4.1 Mini",   "context_length": 1050000, "pricing": "paid"},
    {"id": "o3",             "name": "o3",              "context_length": 1050000, "pricing": "paid"},
    {"id": "o3-mini",        "name": "o3-mini",         "context_length": 1050000, "pricing": "paid"},
    {"id": "o4-mini",        "name": "o4-mini",         "context_length": 1050000, "pricing": "paid"},
]

OPENCODE_MODELS = [
    {"id": "opencode/auto",              "name": "OpenCode Auto",              "context_length": 128000, "pricing": "free"},
    {"id": "opencode/big-pickle",        "name": "OpenCode Big Pickle",        "context_length": 128000, "pricing": "free"},
    {"id": "opencode/muse-spark-1.3-contributor-free", "name": "OpenCode Muse Spark", "context_length": 128000, "pricing": "free"},
]

KILO_MODELS = [
    {"id": "kilo/auto",        "name": "Kilo Auto",        "context_length": 128000, "pricing": "free"},
    {"id": "kilo/auto/free",   "name": "Kilo Auto Free",   "context_length": 128000, "pricing": "free"},
]


# ── HTTP helpers ────────────────────────────────────────────────────────────

def fetch_json(url, headers=None, timeout=8):
    """Fetch JSON from a URL. Returns (ok, data_or_error, latency_ms)."""
    t0 = time.time()
    try:
        req = urllib.request.Request(url, headers=headers or {"User-Agent": "REY-Model-Discovery/1.0"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body)
            latency = int((time.time() - t0) * 1000)
            return True, data, latency
    except Exception as e:
        latency = int((time.time() - t0) * 1000)
        return False, str(e), latency


def get_api_key(provider):
    """Read API key from .env or auth.json."""
    # Try .env first
    env_path = CONFIG_DIR / ".env"
    if env_path.exists():
        with open(env_path, "r", encoding="utf-8-sig") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() == provider:
                        return v.strip()
    # Try auth.json
    if AUTH_PATH.exists():
        try:
            with open(AUTH_PATH, "r", encoding="utf-8") as f:
                auth = json.load(f)
                return auth.get(provider, {}).get("key", "")
        except Exception:
            pass
    return ""


# ── Provider fetchers ───────────────────────────────────────────────────────

def fetch_openrouter(tier):
    """Fetch models from OpenRouter (public API)."""
    ok, data, latency = fetch_json("https://openrouter.ai/api/v1/models")
    if not ok:
        return {"ok": False, "error": str(data), "latency_ms": latency, "models": [], "total": 0, "free_count": 0, "paid_count": 0}

    models = []
    free_count = 0
    paid_count = 0

    for m in data.get("data", []):
        mid = m.get("id", "")
        pricing = m.get("pricing", {})
        is_free = mid.endswith(":free") or (pricing.get("prompt") == "0" and pricing.get("completion") == "0")

        model_entry = {
            "id": mid,
            "name": m.get("name", mid),
            "context_length": m.get("context_length", 0),
            "pricing": "free" if is_free else "paid",
        }

        if is_free:
            free_count += 1
        else:
            paid_count += 1

        # Apply tier filter
        if tier == "free" and not is_free:
            continue

        models.append(model_entry)

    return {
        "ok": True,
        "models": models,
        "total": free_count + paid_count,
        "free_count": free_count,
        "paid_count": paid_count,
        "latency_ms": latency,
    }


def fetch_groq(tier):
    """Fetch models from Groq (requires API key)."""
    key = get_api_key("GROQ_API_KEY")
    if not key:
        return {"ok": False, "error": "No GROQ_API_KEY found", "models": [], "total": 0, "free_count": 0, "paid_count": 0}

    ok, data, latency = fetch_json(
        "https://api.groq.com/openai/v1/models",
        headers={"Authorization": f"Bearer {key}", "User-Agent": "REY-Model-Discovery/1.0"},
    )
    if not ok:
        return {"ok": False, "error": str(data), "latency_ms": latency, "models": [], "total": 0, "free_count": 0, "paid_count": 0}

    models = []
    for m in data.get("data", []):
        mid = m.get("id", "")
        models.append({
            "id": mid,
            "name": mid,
            "context_length": m.get("context_length", 128000),
            "pricing": "free",  # Groq is free-tier
        })

    return {
        "ok": True,
        "models": models,
        "total": len(models),
        "free_count": len(models),
        "paid_count": 0,
        "latency_ms": latency,
    }


def fetch_gemini(tier):
    """Return hardcoded Gemini models (no public list API)."""
    models = list(GEMINI_MODELS)
    free_count = sum(1 for m in models if m["pricing"] == "free")
    paid_count = len(models) - free_count

    if tier == "free":
        models = [m for m in models if m["pricing"] == "free"]

    return {
        "ok": True,
        "models": models,
        "total": len(GEMINI_MODELS),
        "free_count": free_count,
        "paid_count": paid_count,
        "latency_ms": 0,
    }


def fetch_claude(tier):
    """Return hardcoded Claude models (no public list API)."""
    models = list(CLAUDE_MODELS)
    free_count = sum(1 for m in models if m["pricing"] == "free")
    paid_count = len(models) - free_count

    if tier == "free":
        models = [m for m in models if m["pricing"] == "free"]

    return {
        "ok": True,
        "models": models,
        "total": len(CLAUDE_MODELS),
        "free_count": free_count,
        "paid_count": paid_count,
        "latency_ms": 0,
    }


def fetch_chatgpt(tier):
    """Return hardcoded ChatGPT models (no public list API)."""
    models = list(CHATGPT_MODELS)
    free_count = sum(1 for m in models if m["pricing"] == "free")
    paid_count = len(models) - free_count

    if tier == "free":
        models = [m for m in models if m["pricing"] == "free"]

    return {
        "ok": True,
        "models": models,
        "total": len(CHATGPT_MODELS),
        "free_count": free_count,
        "paid_count": paid_count,
        "latency_ms": 0,
    }


def fetch_opencode(tier):
    """Return OpenCode models (local/self-hosted, always free)."""
    models = list(OPENCODE_MODELS)
    return {
        "ok": True,
        "models": models,
        "total": len(models),
        "free_count": len(models),
        "paid_count": 0,
        "latency_ms": 0,
    }


def fetch_kilo(tier):
    """Return Kilo Code models (free tier)."""
    models = list(KILO_MODELS)
    return {
        "ok": True,
        "models": models,
        "total": len(models),
        "free_count": len(models),
        "paid_count": 0,
        "latency_ms": 0,
    }


FETCHERS = {
    "openrouter": fetch_openrouter,
    "groq":       fetch_groq,
    "gemini":     fetch_gemini,
    "claude":     fetch_claude,
    "chatgpt":    fetch_chatgpt,
    "opencode":   fetch_opencode,
    "kilo":       fetch_kilo,
}


# ── Main ────────────────────────────────────────────────────────────────────

def main():
    # 1. Read BYOK config
    if not BYOK_CONFIG.exists():
        if "--list" in sys.argv or "-l" in sys.argv:
            print("  [!] byok-config.json not found - run 'rey setup' first to configure providers.")
            sys.exit(0)
        print(json.dumps({"ok": False, "error": "byok-config.json not found - run setup first"}))
        sys.exit(0)

    with open(BYOK_CONFIG, "r", encoding="utf-8-sig") as f:
        byok = json.load(f)

    enabled = [
        pid for pid, p in byok.get("providers", {}).items()
        if isinstance(p, dict) and p.get("enabled", False)
    ]

    if not enabled:
        print(json.dumps({"error": "No providers enabled in byok-config.json"}))
        sys.exit(1)

    # 2. Read tier preference
    tier = "free"  # default
    if MODEL_TIER.exists():
        try:
            with open(MODEL_TIER, "r", encoding="utf-8-sig") as f:
                tier_data = json.load(f)
                tier = tier_data.get("tier", "free")
        except Exception:
            pass

    # 3. Fetch models from each enabled provider
    providers_result = {}
    total_models = 0
    total_free = 0
    total_paid = 0

    for pid in enabled:
        fetcher = FETCHERS.get(pid)
        if not fetcher:
            providers_result[pid] = {
                "ok": False,
                "error": f"No fetcher for provider: {pid}",
                "models": [],
                "total": 0,
                "free_count": 0,
                "paid_count": 0,
            }
            continue

        result = fetcher(tier)
        providers_result[pid] = result
        total_models += result.get("total", 0)
        total_free += result.get("free_count", 0)
        total_paid += result.get("paid_count", 0)

    # 4. Build output
    output = {
        "ok": True,
        "tier": tier,
        "generated_at": datetime.now().isoformat(),
        "providers": providers_result,
        "summary": {
            "total_models": total_models,
            "total_after_filter": sum(len(p.get("models", [])) for p in providers_result.values()),
            "free_total": total_free,
            "paid_total": total_paid,
            "by_provider": {
                pid: {
                    "total": p.get("total", 0),
                    "free": p.get("free_count", 0),
                    "paid": p.get("paid_count", 0),
                    "available": len(p.get("models", [])),
                }
                for pid, p in providers_result.items()
            },
        },
    }

    # 5. Write live-models.json
    with open(LIVE_MODELS, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2)

# 6. Print output
    if "--list" in sys.argv or "-l" in sys.argv:
        print_list(output)
    else:
        print(json.dumps(output, indent=2))


def print_list(output):
    """User-friendly model browser display."""
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    GRAY = "\033[90m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    s = output["summary"]
    print(f"\n{CYAN}{'=' * 78}{RESET}")
    print(f"  {BOLD}R.E.Y. // LIVE MODEL BROWSER{RESET}")
    print(f"  Tier: {output['tier']}  |  Generated: {output['generated_at'][:19]}")
    print(f"{CYAN}{'=' * 78}{RESET}")

    for pid, p in output["providers"].items():
        label = pid.upper()
        if not p.get("ok"):
            print(f"\n  {YELLOW}✖ {label}{RESET} - {p.get('error', 'unavailable')}")
            continue
        models = p.get("models", [])
        print(f"\n  {GREEN}✓ {label}{RESET}  "
              f"(total:{p.get('total', 0)} free:{p.get('free_count', 0)} "
              f"paid:{p.get('paid_count', 0)} shown:{len(models)})")
        for m in models[:25]:
            mid = m.get("id", m) if isinstance(m, dict) else m
            ctx = ""
            if isinstance(m, dict) and m.get("context_length"):
                cl = m["context_length"]
                ctx = f"  ctx:{cl // 1000}k" if cl >= 1000 else f"  ctx:{cl}"
            print(f"      {GRAY}•{RESET} {mid}{ctx}")
        if len(models) > 25:
            print(f"      {GRAY}... and {len(models) - 25} more{RESET}")

    print(f"\n{CYAN}{'=' * 78}{RESET}")
    print(f"  {BOLD}Summary:{RESET} {s['total_after_filter']} models shown "
          f"({s['free_total']} free, {s['paid_total']} paid)")
    print(f"{CYAN}{'=' * 78}{RESET}\n")


if __name__ == "__main__":
    main()
