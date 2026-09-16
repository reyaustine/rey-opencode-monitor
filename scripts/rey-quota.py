#!/usr/bin/env python3
"""
R.E.Y. // PROVIDER QUOTA MONITOR
Comprehensive rate-limit and quota checker across ALL providers.
Shows live status and allows switching to providers with available capacity.
"""

import os
import sys
import json
import time
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ANSI color codes
RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
MAGENTA = "\033[35m"
WHITE = "\033[37m"
GRAY = "\033[90m"

HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME, ".config", "opencode")
AUTH_PATH = os.path.join(HOME, ".local", "share", "opencode", "auth.json")
OPENROUTER_DEALS = os.path.join(CONFIG_DIR, "openrouter-deals.json")

# Provider configurations to monitor
PROVIDERS = {
    "openrouter": {
        "name": "OpenRouter",
        "free_limit": 50,
        "auth_key_env": "OPENROUTER_API_KEY",
        "auth_path_key": "openrouter",
        "base_url": "https://openrouter.ai/api/v1",
        "models_endpoint": "https://openrouter.ai/api/v1/models",
        "quota_endpoint": "https://openrouter.ai/api/v1/auth/key",
        "test_endpoint": "https://openrouter.ai/api/v1/chat/completions",
        "test_payload": {
            "model": "inclusionai/ling-3.0-flash-vl:free",
            "messages": [{"role": "user", "content": "ping"}],
            "max_tokens": 1
        }
    },
    "kilo": {
        "name": "Kilo Code",
        "free_limit": 200,
        "base_url": "https://api.kilo.ai/api/gateway/v1",
        "models_endpoint": "https://api.kilo.ai/api/gateway/v1/models",
        "check_method": "HEAD"
    },
    "groq": {
        "name": "Groq",
        "free_limit": 100,
        "auth_key_env": "GROQ_API_KEY",
        "auth_path_key": "groq",
        "base_url": "https://api.groq.com/openai/v1",
        "models_endpoint": "https://api.groq.com/openai/v1/models",
        "check_method": "HEAD"
    },
    "gemini": {
        "name": "Google Gemini",
        "free_limit": 150,
        "auth_key_env": "GEMINI_API_KEY",
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai",
        "models_endpoint": "https://generativelanguage.googleapis.com/v1/models",
        "check_method": "HEAD"
    },
    "mistral": {
        "name": "Mistral",
        "free_limit": 100,
        "auth_key_env": "MISTRAL_API_KEY",
        "base_url": "https://api.mistral.ai/v1",
        "models_endpoint": "https://api.mistral.ai/v1/models",
        "check_method": "HEAD"
    }
}

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

def load_auth_keys():
    """Load API keys from auth.json"""
    keys = {}
    if os.path.exists(AUTH_PATH):
        try:
            with open(AUTH_PATH, "r", encoding="utf-8-sig") as f:
                auth_data = json.load(f)
                for provider in ["openrouter", "groq", "gemini", "mistral"]:
                    if provider in auth_data:
                        keys[provider] = auth_data[provider].get("key", "")
        except Exception:
            pass
    return keys

def ping_endpoint(url, headers=None, timeout=6, method="GET"):
    """Ping an HTTP endpoint and measures latency."""
    if headers is None:
        headers = {}
    headers["User-Agent"] = "REY-Quota-Monitor/1.0"
    req = urllib.request.Request(url, headers=headers, method=method)
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            latency_ms = int((time.time() - t0) * 1000)
            return True, res.getcode(), latency_ms, ""
    except urllib.error.HTTPError as e:
        latency_ms = int((time.time() - t0) * 1000)
        return False, e.code, latency_ms, ""
    except Exception as e:
        latency_ms = int((time.time() - t0) * 1000)
        return False, str(e), latency_ms, ""

def check_openrouter_quota(auth_keys):
    """Check OpenRouter quota and rate limits."""
    quota_info = {
        "name": "OpenRouter",
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

    # Try auth key from environment first
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        key = auth_keys.get("openrouter", "")
    
    if not key:
        return quota_info

    # 1. Fetch account limit & balance
    try:
        req = urllib.request.Request("https://openrouter.ai/api/v1/auth/key", 
                                     headers={"Authorization": f"Bearer {key}",
                                             "User-Agent": "REY-Quota-Monitor/1.0"})
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
            quota_info["label"] = kdata.get("label", "")
            quota_info["credit_limit"] = round(limit, 4)
            quota_info["credits_remaining"] = round(remaining, 4)
            quota_info["credit_percent_remaining"] = round(percent, 1)
            quota_info["budget_status"] = budget_status
            quota_info["budget_ok"] = budget_status == "OK"
            quota_info["budget_usable"] = budget_status in ("OK", "LOW")
            quota_info["status"] = budget_labels.get(budget_status, "CREDIT_UNKNOWN")
            quota_info["free_limit"] = safe_int(free_data.get("limit"), quota_info["free_limit"])
            quota_info["free_remaining"] = safe_int(free_data.get("remaining"), quota_info["free_remaining"])
            quota_info["free_used"] = safe_int(free_data.get("used"), 0)
            quota_info["free_quota_known"] = bool(free_data)
            quota_info["usage_daily"] = round(safe_float(kdata.get("usage_daily"), 0), 4)
            quota_info["usage_weekly"] = round(safe_float(kdata.get("usage_weekly"), 0), 4)
            quota_info["usage_monthly"] = round(safe_float(kdata.get("usage_monthly"), 0), 4)
            quota_info["last_checked"] = time.strftime("%Y-%m-%d %H:%M:%S")
    except Exception as e:
        quota_info["error"] = str(e)

    # 2. Probe free model rate limit
    try:
        test_req = urllib.request.Request(
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
        with urllib.request.urlopen(test_req, timeout=4) as r2:
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

    return quota_info

def check_provider(provider_name, provider_config, auth_keys):
    """Check a single provider's status."""
    print(f"  Checking {provider_config['name']}...")
    
    if provider_name == "openrouter":
        result = check_openrouter_quota(auth_keys)
        result["provider"] = provider_name
        return result
    
    # Generic provider check
    ok = False
    latency = 0
    status = "UNKNOWN"
    code = 0
    
    # Check models endpoint
    if "models_endpoint" in provider_config:
        ok, code, latency, _ = ping_endpoint(
            provider_config["models_endpoint"], 
            timeout=5
        )
        if ok:
            status = f"OK ({code})"
        else:
            status = f"FAIL ({latency}ms)"
    
    # Check API key if required
    if not ok and "auth_key_env" in provider_config:
        key = os.environ.get(provider_config["auth_key_env"], "")
        if not key and provider_name in auth_keys:
            key = auth_keys[provider_name]
        
        if key:
            # Try a simple API call
            test_url = provider_config["base_url"] + "/models"
            ok2, code2, latency2, _ = ping_endpoint(
                test_url,
                headers={"Authorization": f"Bearer {key}"},
                timeout=5
            )
            if ok2:
                ok = True
                latency = latency2
                status = f"OK ({code2})"
            else:
                status = f"AUTH_FAIL ({latency2}ms)"

    return {
        "provider": provider_name,
        "name": provider_config["name"],
        "ok": ok,
        "status": status,
        "latency_ms": latency,
        "free_limit": provider_config.get("free_limit", 0),
        "free_remaining": max(0, provider_config.get("free_limit", 0) - (0 if ok else 1)),
        "is_rate_limited": not ok and "FAIL" in status
    }

def main():
    print(f"\n{CYAN}{'=' * 80}{RESET}")
    print(f"  {BOLD}🚀 R.E.Y. // PROVIDER QUOTA MONITOR{RESET}")
    print(f"  Live rate-limit status across ALL configured providers")
    print(f"{CYAN}{'=' * 80}{RESET}\n")

    # Load auth keys
    auth_keys = load_auth_keys()

    # Check all providers concurrently
    results = []
    with ThreadPoolExecutor(max_workers=len(PROVIDERS)) as executor:
        futures = {
            name: executor.submit(check_provider, name, config, auth_keys)
            for name, config in PROVIDERS.items()
        }
        for name, future in futures.items():
            try:
                results.append(future.result())
            except Exception as e:
                results.append({
                    "provider": name,
                    "name": PROVIDERS[name]["name"],
                    "ok": False,
                    "status": f"ERROR ({e})",
                    "latency_ms": 0,
                    "free_limit": 0,
                    "free_remaining": 0,
                    "is_rate_limited": False
                })

    # Persist the OpenRouter summary so rey status / monitor show fresh data
    for r in results:
        if r.get("provider") == "openrouter":
            try:
                quota_file = os.path.join(CONFIG_DIR, "openrouter-quota.json")
                with open(quota_file, "w", encoding="utf-8") as qf:
                    json.dump(r, qf, indent=2)
            except Exception:
                pass
            break

    # Sort by health status
    results.sort(key=lambda x: x.get("ok", False), reverse=True)

    # Print summary
    print(f"\n{BOLD}📊 PROVIDER STATUS SUMMARY:{RESET}")
    for r in results:
        if r.get("provider") == "openrouter":
            budget_status = r.get("budget_status", "UNKNOWN")
            if r.get("is_rate_limited"):
                status_icon = "❌"
                status = "RATE LIMITED"
            elif budget_status == "DEPLETED":
                status_icon = "❌"
                status = "CREDIT DEPLETED"
            elif budget_status == "CRITICAL":
                status_icon = "⚠️"
                status = "CRITICAL CREDIT"
            elif budget_status == "LOW":
                status_icon = "⚠️"
                status = "LOW CREDIT"
            elif budget_status == "OK":
                status_icon = "✅"
                status = "CREDIT OK"
            else:
                status_icon = "⚠️"
                status = "CREDIT UNKNOWN"
            free_limit = r.get("free_limit", "?") if r.get("free_quota_known") else "?"
            free_remaining = r.get("free_remaining", "?") if r.get("free_quota_known") else "?"
            credit_limit = safe_float(r.get("credit_limit"), 0)
            credits = safe_float(r.get("credits_remaining"), 0)
            percent = safe_float(r.get("credit_percent_remaining"), 0)
            limit_text = f"{credit_limit:.2f}" if credit_limit > 0 else "?"
            print(f"  {status_icon} {r['name']:<20} {status:<18} free {free_remaining}/{free_limit} | paid ${credits:.3f}/${limit_text} ({percent:.1f}%)")
            continue
        color = GREEN if r.get("ok") else YELLOW if "AUTH" in r.get("status", "") else RED
        limit = r.get("free_limit", 0)
        remaining = r.get("free_remaining", 0)
        status_icon = "✅" if r.get("ok") else "⚠️" if "AUTH" in r.get("status", "") else "❌"
        print(f"  {status_icon} {r['name']:<20} {r['status']:<15} {remaining:>3}/{limit} remaining")

    # Print detailed status
    print(f"\n{BOLD}🔍 DETAILED ANALYSIS:{RESET}")
    
    # Count issues
    total_providers = len(results)
    healthy_providers = sum(1 for r in results if r.get("ok") and not r.get("is_rate_limited") and r.get("budget_status", "OK") in (None, "OK"))
    rate_limited = sum(1 for r in results if r.get("is_rate_limited", False))
    auth_issues = sum(1 for r in results if "AUTH" in r.get("status", ""))
    credit_issues = sum(1 for r in results if r.get("provider") == "openrouter" and r.get("budget_status") in ("LOW", "CRITICAL", "DEPLETED"))

    print(f"\n  Overall Health: {healthy_providers}/{total_providers} providers healthy")
    if rate_limited > 0:
        print(f"  ⚠️  Rate Limited: {rate_limited} providers")
    if credit_issues > 0:
        print(f"  ⚠️  OpenRouter Credit: {credit_issues} provider(s) low or depleted")
    if auth_issues > 0:
        print(f"  🔑 Auth Issues: {auth_issues} providers (missing/invalid API keys)")

    # Show recommended actions
    print(f"\n{BOLD}🎯 RECOMMENDED ACTIONS:{RESET}")
    
    # Find best providers to switch to
    SWITCHABLE = ("kilo", "opencode", "openrouter")
    available_providers = [r for r in results if r.get("ok") and not r.get("is_rate_limited") and r.get("budget_status", "OK") == "OK" and r["provider"] != "openrouter"]
    if available_providers:
        print(f"  ✅ Safe providers to use: ", end="")
        provider_names = [r["name"] for r in available_providers]
        print(f"{', '.join(provider_names)}")
        print(f"  These have API keys configured and are responding normally")

    if rate_limited > 0:
        print(f"  ⚠️  Rate-limited providers: {rate_limited}")
        print(f"     Consider using the healthy providers above instead")
        print(f"     or add more credits to OpenRouter")

    openrouter_result = next((r for r in results if r["provider"] == "openrouter"), None)
    if openrouter_result:
        budget_status = openrouter_result.get("budget_status", "UNKNOWN")
        credits = safe_float(openrouter_result.get("credits_remaining"), 0)
        daily = safe_float(openrouter_result.get("usage_daily"), 0)
        if openrouter_result.get("is_rate_limited"):
            hours_left = openrouter_result.get("hours_left", 0)
            if hours_left > 0:
                print(f"     OpenRouter free-tier reset is in {hours_left:.1f} hours")
            else:
                print(f"     OpenRouter free-tier rate limit is active - consider switching to Kilo or OpenCode")
        elif budget_status == "DEPLETED":
            print(f"     OpenRouter paid credit is depleted (${credits:.3f} remaining; ${daily:.3f} used today)")
        elif budget_status == "CRITICAL":
            print(f"     OpenRouter paid credit is critical: ${credits:.3f} remaining (${daily:.3f} used today)")
        elif budget_status == "LOW":
            print(f"     OpenRouter paid credit is low: ${credits:.3f} remaining (${daily:.3f} used today)")

    # Show provider-specific options (only providers the switcher supports)
    print(f"\n{BOLD}🔄 QUICK PROVIDER SWITCH:{RESET}")
    for r in results:
        if r["provider"] in SWITCHABLE and r.get("ok") and not r.get("is_rate_limited") and r.get("budget_status", "OK") == "OK":
            print(f"  Switch to {r['name']} with: rey switch-provider {r['provider']}")
    for r in results:
        if r["provider"] not in SWITCHABLE and r.get("ok"):
            print(f"  {r['name']} healthy but no dedicated switcher - use 'rey override' instead")

    # Check deals file
    if os.path.exists(OPENROUTER_DEALS):
        try:
            with open(OPENROUTER_DEALS, "r", encoding="utf-8") as f:
                deals_data = json.load(f)
                total_deals = deals_data.get("total_deals", 0)
                if total_deals > 0:
                    print(f"\n  💰 {total_deals} discounted OpenRouter models available (rey deals)")
        except Exception:
            pass

    print(f"\n{CYAN}{'=' * 80}{RESET}")
    print(f"  Last check: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{CYAN}{'=' * 80}{RESET}\n")

if __name__ == "__main__":
    main()
