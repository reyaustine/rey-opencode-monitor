#!/usr/bin/env python3
"""
R.E.Y. // Fleet Health Watchdog & Free Model Discovery Engine
Pings provider APIs every 30 mins (and on-demand via H key),
tests responsiveness of ALL Free models, discovers newly released free models,
tracks newly updated live paid models on OpenRouter, and reports deals & status live.
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
DIM = "\033[2m"
CYAN = "\033[36m"
YELLOW = "\033[33m"
GREEN = "\033[32m"
RED = "\033[31m"
MAGENTA = "\033[35m"
WHITE = "\033[37m"
GRAY = "\033[90m"

HOME = os.path.expanduser("~")
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

def get_current_allowlist():
    """Reads models configured across opencode.jsonc."""
    models = list(BASE_ALLOWLIST)
    if os.path.exists(CONFIG_JSONC):
        try:
            with open(CONFIG_JSONC, "r", encoding="utf-8") as f:
                lines = [l for l in f if not l.strip().startswith("//")]
                cdata = json.loads("\n".join(lines))
                # Add provider whitelists
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
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key and os.path.exists(AUTH_PATH):
        try:
            with open(AUTH_PATH, "r", encoding="utf-8") as f:
                key = json.load(f).get("openrouter", {}).get("key", "")
        except Exception:
            pass
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

def run_health_check(quiet=False):
    """Executes the complete health check, free model audit, and model discovery."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    start_time = time.time()

    # Mark as running
    running_state = {
        "running": True,
        "timestamp": int(start_time * 1000),
        "status": "RUNNING",
        "task": "[HEALTH] Auditing ALL Free & Paid models on OpenRouter..."
    }
    try:
        with open(HEALTH_FILE, "w", encoding="utf-8") as f:
            json.dump(running_state, f, indent=2)
    except Exception:
        pass

    if not quiet:
        print(f"\n{CYAN}{'=' * 85}{RESET}")
        print(f"  {BOLD}🚀 R.E.Y. // FLEET HEALTH WATCHDOG & MODEL DISCOVERY AUDIT{RESET}")
        print(f"{CYAN}{'=' * 85}{RESET}")

    # 1. Fetch live models from OpenRouter
    all_openrouter_models = []
    openrouter_free_models = []
    openrouter_paid_models = []
    openrouter_ok, code, lat_or, body_or = ping_endpoint("https://openrouter.ai/api/v1/models", timeout=10)
    
    if openrouter_ok and body_or:
        try:
            or_data = json.loads(body_or)
            for m in or_data.get("data", []):
                all_openrouter_models.append(m)
                mid = m.get("id", "")
                pricing = m.get("pricing", {})
                is_free = mid.endswith(":free") or (pricing.get("prompt") == "0" and pricing.get("completion") == "0")
                if is_free:
                    openrouter_free_models.append(m)
                else:
                    openrouter_paid_models.append(m)
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

    # 4. Check LM Studio LAN Gateway (key from env or auth.json; optional)
    lmstudio_key = os.environ.get("LMSTUDIO_API_KEY", "")
    if not lmstudio_key and os.path.exists(AUTH_PATH):
        try:
            with open(AUTH_PATH, "r", encoding="utf-8-sig") as af:
                lmstudio_key = json.load(af).get("lmstudio", {}).get("key", "")
        except Exception:
            pass
    lmstudio_headers = {"Authorization": f"Bearer {lmstudio_key}"} if lmstudio_key else {}
    lmstudio_ok, lm_code, lat_lm, _ = ping_endpoint(
        "http://192.168.254.140:1234/v1/models",
        headers=lmstudio_headers,
        timeout=3
    )

    # 5. Deep-audit ALL Free Models on OpenRouter concurrently
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
            # Check model endpoints status
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

    # 6. Allowlisted Models Responsiveness
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
            if groq_ok:
                responsive.append(full_id)
            else:
                unresponsive.append(full_id)
        elif full_id.startswith("kilo/"):
            if kilo_ok:
                responsive.append(full_id)
            else:
                unresponsive.append(full_id)
        elif full_id.startswith("lmstudio/"):
            if lmstudio_ok:
                responsive.append(full_id)
            else:
                # LM Studio is optional — skip these models gracefully
                # instead of marking them unresponsive when LM Studio is simply offline
                pass
        else:
            responsive.append(full_id)

    # 7. Discover New Free Models on OpenRouter
    existing_raw_ids = {m.replace("openrouter/", "", 1) for m in current_allowlist if m.startswith("openrouter/")}
    new_free_models = []
    for fm in openrouter_free_models:
        f_id = fm.get("id", "")
        if f_id not in existing_raw_ids and not f_id.startswith("google/lyria"):
            new_free_models.append({
                "id": f"openrouter/{f_id}",
                "raw_id": f_id,
                "name": fm.get("name", f_id),
                "context_length": fm.get("context_length", 0),
                "status": free_model_health.get(f_id, {}).get("status", "OK"),
                "uptime": free_model_health.get(f_id, {}).get("uptime_1d", 100.0)
            })

    # 8. Track Live Paid Models Updates (Past 7-14 days)
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

    # 9. Read active discounted deals snapshot
    active_deals_count = 0
    if os.path.exists(DEALS_FILE):
        try:
            with open(DEALS_FILE, "r", encoding="utf-8") as df:
                ddata = json.load(df)
                active_deals_count = ddata.get("total_deals", 0)
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

    result_data = {
        "running": False,
        "timestamp": int(time.time() * 1000),
        "last_check_str": time.strftime("%Y-%m-%d %H:%M:%S"),
        "status": overall_status,
        "duration_ms": duration_ms,
        "providers": {
            "openrouter": {"ok": openrouter_ok, "latency_ms": lat_or},
            "kilo": {"ok": kilo_ok, "latency_ms": lat_k},
            "groq": {"ok": groq_ok, "latency_ms": lat_groq},
            "lmstudio": {"ok": lmstudio_ok, "latency_ms": lat_lm}
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
            print(f"  {RED}[CREDIT DEPLETED]{RESET} Free probe {quota_info.get('free_probe_status', 'unknown')} | free {free_rem}/{free_lim} | paid ${credits:.3f}/{credit_limit:.2f} ({percent:.1f}%)")
        elif budget_status == "CRITICAL":
            print(f"  {YELLOW}[CRITICAL CREDIT]{RESET} Free probe {quota_info.get('free_probe_status', 'unknown')} | free {free_rem}/{free_lim} | paid ${credits:.3f}/{credit_limit:.2f} ({percent:.1f}%) | ${daily:.3f} used today")
        elif budget_status == "LOW":
            print(f"  {YELLOW}[LOW CREDIT]{RESET} Free probe {quota_info.get('free_probe_status', 'unknown')} | free {free_rem}/{free_lim} | paid ${credits:.3f}/{credit_limit:.2f} ({percent:.1f}%) | ${daily:.3f} used today")
        else:
            print(f"  {GREEN}[CREDIT OK]{RESET} Free probe {quota_info.get('free_probe_status', 'unknown')} | free {free_rem}/{free_lim} | paid ${credits:.3f}/{credit_limit:.2f} ({percent:.1f}%) | ${daily:.3f} used today")

        print("\n Provider Gateways:")
        print(f"  [{'✓' if openrouter_ok else '✖'}] OpenRouter API    - {'200 OK' if openrouter_ok else 'FAIL'} ({lat_or}ms)")
        print(f"  [{'✓' if kilo_ok else '✖'}] Kilo Code Gateway - {'200 OK' if kilo_ok else 'FAIL'} ({lat_k}ms)")
        print(f"  [{'✓' if groq_ok else '✖'}] Groq API          - {'200 OK' if groq_ok else 'FAIL'} ({lat_groq}ms)")
        print(f"  [{'✓' if lmstudio_ok else '✖'}] LM Studio LAN     - {'200 OK' if lmstudio_ok else 'OFFLINE'} ({lat_lm}ms)")

        print(f"\n All Live OpenRouter Free Models ({len(openrouter_free_models)} Models Audited):")
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

        print("\n" + "=" * 85)
        print(f" Status: {overall_status} | Elapsed: {duration_ms}ms | Last Check: {result_data['last_check_str']}")
        print("=" * 85 + "\n")

    return result_data

def auto_whitelist_new_models():
    """
    Automatically adds newly discovered free models to opencode.json whitelists.
    Returns (added_count, added_models) tuple.
    """
    health_data = {}
    if os.path.exists(HEALTH_FILE):
        try:
            with open(HEALTH_FILE, "r", encoding="utf-8") as f:
                health_data = json.load(f)
        except Exception:
            return 0, []

    new_models = health_data.get("new_free_models_detail", [])
    if not new_models:
        return 0, []

    # Read current config
    config_path = CONFIG_JSONC if os.path.exists(CONFIG_JSONC) else CONFIG_JSON
    if not os.path.exists(config_path):
        return 0, []

    try:
        with open(config_path, "r", encoding="utf-8") as f:
            if config_path.endswith(".jsonc"):
                lines = [l for l in f if not l.strip().startswith("//")]
                config = json.loads("\n".join(lines))
            else:
                config = json.load(f)
    except Exception:
        return 0, []

    if "provider" not in config:
        config["provider"] = {}

    added_models = []
    for nm in new_models:
        raw_id = nm.get("raw_id", "")
        if not raw_id or raw_id.startswith("google/lyria"):
            continue

        # Determine provider from model ID
        # OpenRouter models: "provider/model-name:free"
        parts = raw_id.split("/")
        if len(parts) < 2:
            continue

        provider_name = parts[0]
        model_name = "/".join(parts[1:])

        # Ensure provider section exists
        if provider_name not in config["provider"]:
            config["provider"][provider_name] = {"whitelist": []}

        if "whitelist" not in config["provider"][provider_name]:
            config["provider"][provider_name]["whitelist"] = []

        # Check if already whitelisted
        current_whitelist = config["provider"][provider_name]["whitelist"]
        if model_name not in current_whitelist and raw_id not in current_whitelist:
            current_whitelist.append(model_name)
            added_models.append(f"{provider_name}/{model_name}")

    if added_models:
        # Write back to config
        try:
            with open(config_path, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except Exception:
            return 0, []

        # Also update model-fallback.json
        _update_fallback_models(added_models)

    return len(added_models), added_models


def _update_fallback_models(new_model_ids):
    """Adds new models to model-fallback.json agent lists."""
    fallback_path = os.path.join(CONFIG_DIR, "model-fallback.json")
    if not os.path.exists(fallback_path):
        return

    try:
        with open(fallback_path, "r", encoding="utf-8") as f:
            fallback = json.load(f)
    except Exception:
        return

    if "agents" not in fallback:
        return

    # Convert full model IDs to kilo/openrouter format for fallback
    kilo_models = []
    for mid in new_model_ids:
        # Extract the model part for kilo gateway
        if "/" in mid:
            parts = mid.split("/", 1)
            if len(parts) > 1:
                kilo_models.append(f"kilo/{parts[1]}")

    if not kilo_models:
        return

    # Add to all agent fallback lists (avoid duplicates)
    for agent_key, agent_val in fallback.get("agents", {}).items():
        if isinstance(agent_val, dict) and "fallbackModels" in agent_val:
            for m in kilo_models:
                if m not in agent_val["fallbackModels"]:
                    agent_val["fallbackModels"].append(m)

    try:
        with open(fallback_path, "w", encoding="utf-8") as f:
            json.dump(fallback, f, indent=2)
    except Exception:
        pass


def get_all_provider_models():
    """
    Fetches ALL models from all configured providers (free + paid).
    Returns a dict with provider name -> list of models with status info.
    """
    all_models = {}

    # 1. OpenRouter - fetch ALL models
    try:
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/models",
            headers={"User-Agent": "REY-Fleet-Monitor/1.0"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
            or_models = []
            for m in data.get("data", []):
                mid = m.get("id", "")
                pricing = m.get("pricing", {})
                prompt_price = safe_float(pricing.get("prompt", "0"))
                completion_price = safe_float(pricing.get("completion", "0"))
                is_free = mid.endswith(":free") or (prompt_price == 0 and completion_price == 0)

                or_models.append({
                    "id": mid,
                    "name": m.get("name", mid),
                    "context_length": m.get("context_length", 0),
                    "pricing": {
                        "prompt": prompt_price,
                        "completion": completion_price
                    },
                    "is_free": is_free,
                    "status": "FREE" if is_free else "PAID",
                    "created": m.get("created", 0)
                })
            all_models["openrouter"] = or_models
    except Exception:
        all_models["openrouter"] = []

    # 2. Groq
    groq_key = os.environ.get("GROQ_API_KEY", "")
    if not groq_key and os.path.exists(AUTH_PATH):
        try:
            with open(AUTH_PATH, "r", encoding="utf-8") as af:
                groq_key = json.load(af).get("groq", {}).get("key", "")
        except Exception:
            pass

    if groq_key:
        try:
            req = urllib.request.Request(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {groq_key}", "User-Agent": "REY-Fleet-Monitor/1.0"}
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
                groq_models = []
                for m in data.get("data", []):
                    groq_models.append({
                        "id": m.get("id", ""),
                        "name": m.get("id", ""),
                        "context_length": m.get("context_length", 0),
                        "pricing": {"prompt": 0, "completion": 0},
                        "is_free": True,
                        "status": "FREE",
                        "created": 0
                    })
                all_models["groq"] = groq_models
        except Exception:
            all_models["groq"] = []
    else:
        all_models["groq"] = []

    # 3. Gemini
    try:
        gemini_models = [
            {"id": "gemini-2.5-pro", "name": "Gemini 2.5 Pro", "context_length": 1048576, "is_free": True, "status": "FREE"},
            {"id": "gemini-2.5-flash", "name": "Gemini 2.5 Flash", "context_length": 1048576, "is_free": True, "status": "FREE"},
            {"id": "gemini-2.0-flash", "name": "Gemini 2.0 Flash", "context_length": 1048576, "is_free": True, "status": "FREE"},
        ]
        all_models["gemini"] = gemini_models
    except Exception:
        all_models["gemini"] = []

    # 4. Kilo
    try:
        req = urllib.request.Request(
            "https://api.kilo.ai/api/gateway/v1/models",
            headers={"User-Agent": "REY-Fleet-Monitor/1.0"}
        )
        with urllib.request.urlopen(req, timeout=8) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
            kilo_models = []
            for m in data.get("data", []):
                kilo_models.append({
                    "id": m.get("id", ""),
                    "name": m.get("name", m.get("id", "")),
                    "context_length": m.get("context_length", 128000),
                    "pricing": {"prompt": 0, "completion": 0},
                    "is_free": True,
                    "status": "FREE",
                    "created": 0
                })
            all_models["kilo"] = kilo_models
    except Exception:
        all_models["kilo"] = []

    # 5. OpenCode
    try:
        opencode_models = [
            {"id": "opencode/auto", "name": "OpenCode Auto", "context_length": 128000, "is_free": True, "status": "FREE"},
            {"id": "opencode/big-pickle", "name": "OpenCode Big Pickle", "context_length": 128000, "is_free": True, "status": "FREE"},
            {"id": "opencode/muse-spark-1.3-contributor-free", "name": "OpenCode Muse Spark", "context_length": 128000, "is_free": True, "status": "FREE"},
        ]
        all_models["opencode"] = opencode_models
    except Exception:
        all_models["opencode"] = []

    return all_models


def display_all_models(all_models, config_path=None):
    """Displays all models from all providers with status indicators."""
    if not config_path:
        config_path = CONFIG_JSONC if os.path.exists(CONFIG_JSONC) else CONFIG_JSON

    # Load current whitelist
    whitelisted = set()
    if os.path.exists(config_path):
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                if config_path.endswith(".jsonc"):
                    lines = [l for l in f if not l.strip().startswith("//")]
                    config = json.loads("\n".join(lines))
                else:
                    config = json.load(f)

            for p_name, p_val in config.get("provider", {}).items():
                if isinstance(p_val, dict):
                    for m in p_val.get("whitelist", []):
                        full = f"{p_name}/{m}" if not m.startswith(p_name) else m
                        whitelisted.add(full)
        except Exception:
            pass

    print(f"\n{'=' * 95}")
    print(f"  {BOLD}R.E.Y. // ALL MODELS FROM ALL PROVIDERS (Free + Paid){RESET}")
    print(f"{'=' * 95}")

    total_models = 0
    total_free = 0
    total_whitelisted = 0

    for provider, models in sorted(all_models.items()):
        if not models:
            continue

        free_count = sum(1 for m in models if m.get("is_free"))
        paid_count = len(models) - free_count
        whitelisted_count = 0

        print(f"\n  {BOLD}{CYAN}{provider.upper()}{RESET} ({len(models)} models: {GREEN}{free_count} free{RESET}, {YELLOW}{paid_count} paid{RESET})")
        print(f"  {'-' * 90}")

        # Sort: free first, then by name
        sorted_models = sorted(models, key=lambda x: (not x.get("is_free", False), x.get("name", "")))

        for m in sorted_models:
            mid = m.get("id", "")
            name = m.get("name", mid)
            ctx = m.get("context_length", 0)
            ctx_str = f"{ctx // 1000}k" if ctx >= 1000 else str(ctx)
            is_free = m.get("is_free", False)
            is_whitelisted = f"{provider}/{mid}" in whitelisted or mid in whitelisted

            if is_whitelisted:
                whitelisted_count += 1
                status_icon = f"{GREEN}[WL]{RESET}"
            elif is_free:
                status_icon = f"{YELLOW}[FREE]{RESET}"
            else:
                status_icon = f"{GRAY}[PAID]{RESET}"

            pricing = m.get("pricing", {})
            prompt_p = pricing.get("prompt", 0)
            compl_p = pricing.get("completion", 0)

            if is_free or (prompt_p == 0 and compl_p == 0):
                price_str = f"{GREEN}free{RESET}"
            else:
                price_str = f"${prompt_p * 1_000_000:.2f}/${compl_p * 1_000_000:.2f} per 1M"

            print(f"  {status_icon} {mid:<50} | ctx:{ctx_str:<6} | {price_str}")

        total_models += len(models)
        total_free += free_count
        total_whitelisted += whitelisted_count

    print(f"\n{'=' * 95}")
    print(f"  {BOLD}TOTAL:{RESET} {total_models} models | {GREEN}{total_free} free{RESET} | {CYAN}{total_whitelisted} whitelisted{RESET}")
    print(f"  {DIM}Press 'A' in R.E.Y. Monitor to auto-whitelist all discovered free models{RESET}")
    print(f"{'=' * 95}\n")


if __name__ == "__main__":
    quiet_mode = "--quiet" in sys.argv or "-q" in sys.argv
    if "--auto-whitelist" in sys.argv or "-a" in sys.argv:
        count, models = auto_whitelist_new_models()
        if count > 0:
            print(f"\n  {GREEN}[AUTO-WHITELIST]{RESET} Added {count} new free models:")
            for m in models:
                print(f"    {GREEN}+{RESET} {m}")
        else:
            print(f"\n  {YELLOW}[AUTO-WHITELIST]{RESET} No new models to add (all discovered models already whitelisted)")
    elif "--all-models" in sys.argv or "-m" in sys.argv:
        all_models = get_all_provider_models()
        display_all_models(all_models)
    else:
        run_health_check(quiet=quiet_mode)
