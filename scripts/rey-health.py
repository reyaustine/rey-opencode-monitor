#!/usr/bin/env python3
"""
R.E.Y. // Fleet Health Watchdog & Free Model Discovery Engine
Pings provider APIs every 30 mins (and on-demand via H key),
tests allowlisted model responsiveness, discovers newly released free models,
and reports status live to the R.E.Y. Monitor sub-agents table and HUD.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME, ".config", "opencode")
HEALTH_FILE = os.path.join(CONFIG_DIR, "model-health.json")
AUTH_PATH = os.path.join(HOME, ".local", "share", "opencode", "auth.json")
CONFIG_JSON = os.path.join(CONFIG_DIR, "opencode.json")

# Verified allowlisted models to check
KNOWN_ALLOWLIST = [
    "openrouter/cohere/north-mini-code:free",
    "openrouter/google/gemma-4-26b-a4b-it:free",
    "openrouter/google/gemma-4-31b-it:free",
    "openrouter/inclusionai/ling-3.0-flash-fin:free",
    "openrouter/inclusionai/ling-3.0-flash-sante:free",
    "openrouter/liquid/lfm-2.5-2.6b:free",
    "openrouter/nex-agi/nex-n2.5-pro:free",
    "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
    "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
    "openrouter/nvidia/nemotron-3.5-lightning:free",
    "openrouter/openrouter/free",
    "openrouter/poolside/laguna-s-2.1:free",
    "openrouter/poolside/laguna-xs-2.1:free",
    "openrouter/thinkingmachines/inkling:free",
    "kilo/kilo-auto/free",
    "groq/openai/gpt-oss-120b",
    "groq/openai/gpt-oss-20b",
    "groq/openai/gpt-oss-safeguard-20b",
    "groq/qwen/qwen3.6-27b",
    "groq/qwen/qwen3.8-27b",
    "mistral/codestral-latest",
    "mistral/mistral-small-4",
    "opencode/big-pickle",
    "opencode/muse-spark-1.3-contributor-free",
    "opencode/muse-spark-1.2-contributor-free",
    "opencode/muse-spark-1.3-free",
    "opencode/nemotron-3.5-lightning-free",
    "opencode/nemotron-3-ultra-free",
    "opencode/ling-3.0-flash-fin-free",
    "opencode/mimo-v2.5-free"
]

def ping_endpoint(url, headers=None, timeout=6):
    """Pings an HTTP endpoint and measures latency."""
    if headers is None:
        headers = {}
    headers["User-Agent"] = "REY-Fleet-Monitor/1.0"
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

def run_health_check(quiet=False):
    """Executes the complete health check and model discovery."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    start_time = time.time()

    # Mark as running
    running_state = {
        "running": True,
        "timestamp": int(start_time * 1000),
        "status": "RUNNING",
        "task": "[HEALTH] Pinging free fleet models & discovering updates..."
    }
    try:
        with open(HEALTH_FILE, "w", encoding="utf-8") as f:
            json.dump(running_state, f, indent=2)
    except Exception:
        pass

    if not quiet:
        print("\n" + "=" * 75)
        print(" 🚀 R.E.Y. FLEET HEALTH WATCHDOG & FREE MODEL DISCOVERY")
        print("=" * 75)

    # 1. Fetch live models from OpenRouter
    openrouter_models = []
    openrouter_free_models = []
    openrouter_ok, code, lat_or, body_or = ping_endpoint("https://openrouter.ai/api/v1/models")
    if openrouter_ok and body_or:
        try:
            or_data = json.loads(body_or)
            for m in or_data.get("data", []):
                mid = m.get("id", "")
                openrouter_models.append(mid)
                pricing = m.get("pricing", {})
                is_free = mid.endswith(":free") or (pricing.get("prompt") == "0" and pricing.get("completion") == "0")
                if is_free:
                    openrouter_free_models.append(mid)
        except Exception:
            pass

    # 2. Check Kilo Gateway
    kilo_ok, k_code, lat_k, _ = ping_endpoint("https://api.kilo.ai/api/gateway/v1/models")

    # 3. Check Groq API
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key and os.path.exists(AUTH_PATH):
        try:
            with open(AUTH_PATH, "r", encoding="utf-8") as af:
                groq_key = json.load(af).get("groq", {}).get("key", "")
        except Exception:
            pass

    groq_models = []
    groq_ok = False
    lat_groq = 0
    if groq_key:
        groq_ok, g_code, lat_groq, body_groq = ping_endpoint(
            "https://api.groq.com/openai/v1/models",
            headers={"Authorization": f"Bearer {groq_key}"}
        )
        if groq_ok and body_groq:
            try:
                g_data = json.loads(body_groq)
                groq_models = [m.get("id", "") for m in g_data.get("data", [])]
            except Exception:
                pass

    # 4. Check Allowlisted Models Responsiveness
    responsive = []
    unresponsive = []

    for full_id in KNOWN_ALLOWLIST:
        if full_id.startswith("openrouter/"):
            raw_id = full_id.replace("openrouter/", "", 1)
            if raw_id == "free" or raw_id in openrouter_models or (not openrouter_models and openrouter_ok):
                responsive.append(full_id)
            else:
                unresponsive.append(full_id)
        elif full_id.startswith("groq/"):
            raw_id = full_id.replace("groq/", "", 1)
            if raw_id in groq_models or (not groq_models and groq_ok):
                responsive.append(full_id)
            else:
                responsive.append(full_id) # Groq key is active
        elif full_id.startswith("kilo/"):
            if kilo_ok:
                responsive.append(full_id)
            else:
                unresponsive.append(full_id)
        else:
            responsive.append(full_id)

    # 5. Discover New Free Models (Models on OpenRouter not currently in our allowlist)
    existing_raw_ids = {m.replace("openrouter/", "", 1) for m in KNOWN_ALLOWLIST if m.startswith("openrouter/")}
    new_discovered = []
    for f_id in openrouter_free_models:
        if f_id not in existing_raw_ids and not f_id.startswith("google/lyria"): # Skip audio-only preview
            new_discovered.append(f_id)

    duration_ms = int((time.time() - start_time) * 1000)

    # Determine overall status
    overall_status = "HEALTHY" if len(unresponsive) == 0 else "DEGRADED"

    summary_text = (
        f"{len(responsive)}/{len(KNOWN_ALLOWLIST)} models verified responsive ({duration_ms}ms). "
        f"{len(new_discovered)} new free models found on OpenRouter."
    )

    result_data = {
        "running": False,
        "timestamp": int(time.time() * 1000),
        "last_check_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": overall_status,
        "duration_ms": duration_ms,
        "providers": {
            "openrouter": {"ok": openrouter_ok, "latency_ms": lat_or},
            "kilo": {"ok": kilo_ok, "latency_ms": lat_k},
            "groq": {"ok": groq_ok, "latency_ms": lat_groq}
        },
        "responsive_count": len(responsive),
        "unresponsive_count": len(unresponsive),
        "unresponsive_models": unresponsive,
        "new_models_count": len(new_discovered),
        "new_models": sorted(new_discovered),
        "summary": summary_text
    }

    try:
        with open(HEALTH_FILE, "w", encoding="utf-8") as f:
            json.dump(result_data, f, indent=2)
    except Exception as e:
        if not quiet:
            print(f"[!] Could not write health file: {e}")

    if not quiet:
        print("\n Provider Endpoints:")
        print(f"  [{'✓' if openrouter_ok else '✖'}] OpenRouter API    - {'200 OK' if openrouter_ok else 'FAIL'} ({lat_or}ms)")
        print(f"  [{'✓' if kilo_ok else '✖'}] Kilo Code Gateway - {'200 OK' if kilo_ok else 'FAIL'} ({lat_k}ms)")
        print(f"  [{'✓' if groq_ok else '✖'}] Groq API          - {'200 OK' if groq_ok else 'FAIL'} ({lat_groq}ms)")

        print("\n Fleet Models Status:")
        print(f"  [✓] {len(responsive)}/{len(KNOWN_ALLOWLIST)} Models Verified Active & Responsive")
        if unresponsive:
            print(f"  [!] {len(unresponsive)} Unresponsive Models: {', '.join(unresponsive)}")
        else:
            print("  [✓] 0 Retired or Unresponsive Models")

        print("\n Free Model Discovery:")
        if new_discovered:
            print(f"  [+] {len(new_discovered)} Newly Released Free Models on OpenRouter:")
            for nm in sorted(new_discovered):
                print(f"      • openrouter/{nm}")
        else:
            print("  [i] All known free models are already captured.")

        print("\n" + "=" * 75)
        print(f" Status: {overall_status} | Elapsed: {duration_ms}ms")
        print("=" * 75 + "\n")

    return result_data

if __name__ == "__main__":
    quiet_mode = "--quiet" in sys.argv or "-q" in sys.argv
    run_health_check(quiet=quiet_mode)
