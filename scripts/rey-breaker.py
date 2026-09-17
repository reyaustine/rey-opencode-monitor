#!/usr/bin/env python3
"""
R.E.Y. // Circuit Breaker & Auto-Quarantine Engine
Tracks recent consecutive model and provider failures (401, 404, 429, 500, timeouts, invalid keys).
When error counts reach 5 in a rolling window (or consecutive failures):
 - Model-level: Excludes the model from the team roster while preserving the provider
   if other models from that provider are still healthy.
 - Provider-level: Excludes the entire provider if 5+ errors occur across models
   or on provider-wide credentials/endpoints.
Automatically reassigns affected agent roles in opencode.jsonc / opencode.json to healthy fallbacks.
"""

import os
import sys
import json
import time
import sqlite3
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME, ".config", "opencode")
CIRCUIT_FILE = os.path.join(CONFIG_DIR, "circuit-breaker.json")
JSONC_PATH = os.path.join(CONFIG_DIR, "opencode.jsonc")
JSON_PATH = os.path.join(CONFIG_DIR, "opencode.json")
FALLBACK_PATH = os.path.join(CONFIG_DIR, "model-fallback.json")
ROSTER_PATH = os.path.join(CONFIG_DIR, "roster.json")


def _resolve_db_path() -> Optional[str]:
    """Cross-platform OpenCode DB resolver.
    macOS: ~/Library/Application Support/opencode/opencode.db
    Linux/Windows: ~/.local/share/opencode/opencode.db
    """
    user_home = os.path.expanduser("~")
    candidates = [
        os.path.join(user_home, "Library", "Application Support", "opencode", "opencode.db"),
        os.path.join(user_home, ".local", "share", "opencode", "opencode.db"),
        os.path.join(os.environ.get("USERPROFILE", user_home), ".local", "share", "opencode", "opencode.db"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    # Return Linux default even if not found (will be caught by exists() checks)
    return os.path.join(user_home, ".local", "share", "opencode", "opencode.db")


DB_PATH = _resolve_db_path()

ERROR_THRESHOLD = 5
WINDOW_MS = 2 * 3600 * 1000  # Rolling 2-hour window

# Fallback models per role if a model or provider is quarantined
DEFAULT_HEALTHY_FALLBACKS = {
    "coder": [
        "kilo/cohere/north-mini-code:free",
        "openrouter/google/gemma-4-31b-it:free",
        "opencode/mimo-v2.5-free",
        "gemini/gemini-2.5-flash"
    ],
    "build": [
        "kilo/kilo-auto/free",
        "openrouter/google/gemma-4-26b-a4b-it:free",
        "opencode/mimo-v2.5-free"
    ],
    "plan": [
        "kilo/nvidia/nemotron-3-ultra-550b-a55b:free",
        "openrouter/google/gemma-4-31b-it:free",
        "opencode/mimo-v2.5-free"
    ],
    "qa": [
        "kilo/nvidia/nemotron-3.5-lightning:free",
        "openrouter/google/gemma-4-26b-a4b-it:free",
        "opencode/mimo-v2.5-free"
    ],
    "tester": [
        "kilo/poolside/laguna-xs-2.1:free",
        "openrouter/google/gemma-4-26b-a4b-it:free",
        "opencode/ling-3.0-flash-fin-free"
    ],
    "verifier": [
        "kilo/nvidia/nemotron-3-ultra-550b-a55b:free",
        "openrouter/google/gemma-4-31b-it:free",
        "opencode/mimo-v2.5-free"
    ],
    "general": [
        "kilo/kilo-auto/free",
        "openrouter/google/gemma-4-31b-it:free",
        "gemini/gemini-2.5-flash"
    ]
}


def load_circuit_state() -> dict:
    if os.path.exists(CIRCUIT_FILE):
        try:
            with open(CIRCUIT_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception:
            pass
    return {
        "quarantined_models": {},
        "quarantined_providers": {},
        "model_error_counts": {},
        "provider_error_counts": {},
        "last_checked_timestamp": 0,
        "history": []
    }


def save_circuit_state(state: dict) -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)
    try:
        with open(CIRCUIT_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2)
    except Exception as e:
        print(f"[!] Error saving circuit-breaker.json: {e}", file=sys.stderr)


def is_user_abort(err_msg: str, err_name: str) -> bool:
    """Check if error was initiated by user abort rather than model/provider failure."""
    txt = f"{err_name} {err_msg}".lower()
    return "aborted" in txt or "messageaborted" in txt or "user canceled" in txt or "user cancelled" in txt


def get_recent_messages(window_ms: int = WINDOW_MS) -> Tuple[List[dict], List[dict]]:
    """Extract recent errors and successes from SQLite opencode.db."""
    if not os.path.exists(DB_PATH):
        return [], []

    now_ms = int(time.time() * 1000)
    cutoff_ts = now_ms - window_ms

    errors = []
    successes = []
    try:
        conn = sqlite3.connect(DB_PATH, timeout=5)
        cur = conn.cursor()
        query = """
        SELECT 
            id,
            session_id,
            time_created,
            json_extract(data, '$.providerID') as provider,
            json_extract(data, '$.modelID') as model,
            json_extract(data, '$.error') as error,
            json_extract(data, '$.error.name') as err_name,
            json_extract(data, '$.error.data.message') as err_msg,
            json_extract(data, '$.error.data.statusCode') as status_code,
            json_extract(data, '$.role') as role
        FROM message
        WHERE time_created > ?
        ORDER BY time_created ASC
        """
        cur.execute(query, (cutoff_ts,))
        for row in cur.fetchall():
            mid, sid, created, prov, model, err_raw, err_name, err_msg, status_code, role = row
            prov_clean = str(prov).lower() if prov else "unknown"
            mod_clean = str(model) if model else "unknown"
            
            # Skip non-actionable aborted calls
            e_name = str(err_name or "")
            e_msg = str(err_msg or (str(err_raw)[:150] if err_raw else ""))
            if is_user_abort(e_msg, e_name):
                continue

            if err_raw is not None:
                errors.append({
                    "message_id": mid,
                    "session_id": sid,
                    "timestamp": created or now_ms,
                    "provider": prov_clean,
                    "model": mod_clean,
                    "error_name": e_name or "Error",
                    "error_msg": e_msg,
                    "status_code": status_code or 0
                })
            elif role == "assistant":
                successes.append({
                    "message_id": mid,
                    "session_id": sid,
                    "timestamp": created or now_ms,
                    "provider": prov_clean,
                    "model": mod_clean
                })
        conn.close()
    except Exception as e:
        print(f"[!] Error reading opencode.db: {e}", file=sys.stderr)

    return errors, successes


def full_model_name(prov: str, mod: str) -> str:
    if not mod or mod == "unknown":
        return prov
    if mod.startswith(f"{prov}/"):
        return mod
    return f"{prov}/{mod}"


def is_model_quarantined(m: str, quarantined_models: dict) -> bool:
    if not m:
        return False
    if m in quarantined_models:
        return True
    m_clean = m.lower()
    for qm in quarantined_models:
        qm_clean = qm.lower()
        if m_clean == qm_clean or m_clean.endswith("/" + qm_clean) or qm_clean.endswith("/" + m_clean):
            return True
    return False


def auto_heal_roster(quarantined_models: dict, quarantined_providers: dict) -> List[str]:
    """Reassigns any agents/roles in opencode.jsonc & opencode.json that use quarantined models/providers."""
    changes = []
    if not os.path.exists(JSONC_PATH):
        return changes

    try:
        with open(JSONC_PATH, "r", encoding="utf-8") as f:
            jsonc_text = f.read()

        clean_json = re.sub(r"(?m)^\s*//.*$", "", jsonc_text)
        clean_json = re.sub(r",\s*([\]}])", r"\1", clean_json)
        cfg = json.loads(clean_json)

        # 1. Update enabled_providers: remove quarantined providers
        enabled = list(cfg.get("enabled_providers", []))
        new_enabled = [p for p in enabled if p.lower() not in quarantined_providers]
        if set(new_enabled) != set(enabled):
            providers_str = json.dumps(new_enabled)
            jsonc_text = re.sub(r'"enabled_providers"\s*:\s*\[[^\]]*\]', f'"enabled_providers": {providers_str}', jsonc_text)
            changes.append(f"Disabled quarantined providers: {list(set(enabled) - set(new_enabled))}")

        # 2. Check default model
        curr_default = cfg.get("model", "")
        def_prov = curr_default.split("/")[0].lower() if "/" in curr_default else ""
        if is_model_quarantined(curr_default, quarantined_models) or def_prov in quarantined_providers:
            candidates = [
                "kilo/kilo-auto/free",
                "openrouter/google/gemma-4-31b-it:free",
                "opencode/mimo-v2.5-free",
                "gemini/gemini-2.5-flash"
            ]
            for cand in candidates:
                cand_p = cand.split("/")[0].lower()
                if not is_model_quarantined(cand, quarantined_models) and cand_p not in quarantined_providers:
                    jsonc_text = re.sub(r'"model"\s*:\s*"[^"]*"', f'"model": "{cand}"', jsonc_text, count=1)
                    changes.append(f"Default model healed: {curr_default} -> {cand}")
                    break

        # 3. Check agent roles in jsonc
        if cfg.get("agent"):
            for ag_name, ag_conf in cfg["agent"].items():
                if isinstance(ag_conf, dict) and ag_conf.get("model"):
                    ag_model = ag_conf["model"]
                    ag_prov = ag_model.split("/")[0].lower() if "/" in ag_model else ""
                    if is_model_quarantined(ag_model, quarantined_models) or ag_prov in quarantined_providers:
                        role_key = ag_name if ag_name in DEFAULT_HEALTHY_FALLBACKS else "general"
                        fallbacks = DEFAULT_HEALTHY_FALLBACKS.get(role_key, DEFAULT_HEALTHY_FALLBACKS["general"])
                        for cand in fallbacks:
                            cand_p = cand.split("/")[0].lower()
                            if not is_model_quarantined(cand, quarantined_models) and cand_p not in quarantined_providers:
                                pat = rf'("{re.escape(ag_name)}"\s*:\s*\{{[^}}]*"model"\s*:\s*)"[^"]*"'
                                jsonc_text = re.sub(pat, rf'\1"{cand}"', jsonc_text, count=1)
                                changes.append(f"Agent @{ag_name} healed: {ag_model} -> {cand}")
                                break

        if changes:
            with open(JSONC_PATH, "w", encoding="utf-8") as f:
                f.write(jsonc_text)

            # Update opencode.json as well
            if os.path.exists(JSON_PATH):
                try:
                    with open(JSON_PATH, "r", encoding="utf-8") as jf:
                        jdata = json.load(jf)
                    j_changed = False
                    for ch in changes:
                        if "Default model healed" in ch:
                            new_m = ch.split("-> ")[-1]
                            jdata["model"] = new_m
                            j_changed = True
                    if j_changed:
                        with open(JSON_PATH, "w", encoding="utf-8") as jf:
                            json.dump(jdata, jf, indent=2)
                except Exception:
                    pass

    except Exception as e:
        print(f"[!] Error auto-healing roster: {e}", file=sys.stderr)

    return changes


def check_and_update_circuit_breaker(window_ms: int = WINDOW_MS) -> dict:
    """Core evaluation loop: processes errors and triggers circuit breaks."""
    state = load_circuit_state()

    # 1. Gather recent errors and successes in rolling window
    recent_errors, recent_successes = get_recent_messages(window_ms=window_ms)

    # Check missing API keys for currently configured providers
    zero_key_providers = {"kilo", "opencode", "lmstudio", "ollama", "local"}
    try:
        sys.path.insert(0, os.path.join(CONFIG_DIR, "scripts"))
        import rey_state
        r_state = rey_state.get_state()
        missing_keys = r_state.get("missing_api_keys", [])
        for mk in missing_keys:
            prov = mk.replace("_API_KEY", "").lower()
            if prov not in zero_key_providers and prov not in state["quarantined_providers"]:
                state["quarantined_providers"][prov] = {
                    "errors": ERROR_THRESHOLD,
                    "reason": f"Missing or invalid {mk}",
                    "quarantined_at": time.strftime("%Y-%m-%d %H:%M:%S")
                }
    except Exception:
        pass

    # Group errors and successes per model and provider
    model_errs: Dict[str, int] = {}
    model_reasons: Dict[str, str] = {}
    prov_models_seen: Dict[str, set] = {}
    prov_healthy_models: Dict[str, set] = {}
    prov_auth_failures: Dict[str, str] = {}

    for err in recent_errors:
        prov = err["provider"]
        mod = err["model"]
        full_mod = full_model_name(prov, mod)
        reason = f"{err.get('status_code', '')} {err.get('error_name', '')}: {err.get('error_msg', '')}".strip()

        model_errs[full_mod] = model_errs.get(full_mod, 0) + 1
        model_reasons[full_mod] = reason
        
        if prov not in prov_models_seen:
            prov_models_seen[prov] = set()
        prov_models_seen[prov].add(full_mod)

        # Check for provider-wide auth failure
        err_lower = err.get("error_msg", "").lower()
        if any(w in err_lower for w in ["invalid api key", "unauthorized", "wrong api key", "401"]):
            prov_auth_failures[prov] = reason

    # Successes decrement model error counts and mark models as healthy
    for succ in recent_successes:
        prov = succ["provider"]
        mod = succ["model"]
        full_mod = full_model_name(prov, mod)
        if full_mod in model_errs:
            model_errs[full_mod] = max(0, model_errs[full_mod] - 1)
        
        if prov not in prov_healthy_models:
            prov_healthy_models[prov] = set()
        prov_healthy_models[prov].add(full_mod)

    # 2. Evaluate Quarantine Thresholds
    quarantined_models = state.get("quarantined_models", {})
    quarantined_provs = state.get("quarantined_providers", {})
    newly_quarantined = []

    # Check model-level threshold (5 errors)
    for m, count in model_errs.items():
        if count >= ERROR_THRESHOLD and m not in quarantined_models:
            quarantined_models[m] = {
                "errors": count,
                "reason": model_reasons.get(m, "5+ repeated API errors"),
                "quarantined_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            newly_quarantined.append(f"MODEL: {m} ({count} errors)")

    # Check provider-level threshold:
    # RULE:
    # 1. Provider has provider-wide auth/key failure (e.g. Invalid API Key, 401)
    #    -> Quarantine provider!
    # 2. Provider has reached 5 errors across models AND NO other models are responding/working!
    #    -> "unless other models of them from that provider is still responding and working then dont exclude the provider"
    prov_err_totals: Dict[str, int] = {}
    for err in recent_errors:
        prov = err["provider"]
        prov_err_totals[prov] = prov_err_totals.get(prov, 0) + 1

    for p, total_err_count in prov_err_totals.items():
        if p in zero_key_providers and total_err_count < ERROR_THRESHOLD:
            continue

        # Check if provider has working models
        has_working_models = len(prov_healthy_models.get(p, set())) > 0
        all_seen_models_quarantined = False
        if p in prov_models_seen:
            seen_mods = prov_models_seen[p]
            all_seen_models_quarantined = all(sm in quarantined_models for sm in seen_mods)

        auth_err = prov_auth_failures.get(p)

        if auth_err and p not in quarantined_provs:
            quarantined_provs[p] = {
                "errors": total_err_count,
                "reason": f"Auth blocker: {auth_err}",
                "quarantined_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            newly_quarantined.append(f"PROVIDER: {p} (Invalid API Key / Auth)")
        elif total_err_count >= ERROR_THRESHOLD and not has_working_models and all_seen_models_quarantined and p not in quarantined_provs:
            quarantined_provs[p] = {
                "errors": total_err_count,
                "reason": f"5+ errors across all models and no responding models",
                "quarantined_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
            newly_quarantined.append(f"PROVIDER: {p} (All models failing)")

    state["quarantined_models"] = quarantined_models
    state["quarantined_providers"] = quarantined_provs
    state["model_error_counts"] = model_errs
    state["provider_error_counts"] = prov_err_totals
    state["last_checked_timestamp"] = int(time.time() * 1000)

    # 3. Auto-heal Roster if any item was quarantined
    healing_changes = []
    if quarantined_models or quarantined_provs:
        healing_changes = auto_heal_roster(quarantined_models, quarantined_provs)

    save_circuit_state(state)

    return {
        "ok": True,
        "newly_quarantined": newly_quarantined,
        "quarantined_models": list(quarantined_models.keys()),
        "quarantined_providers": list(quarantined_provs.keys()),
        "healing_changes": healing_changes,
        "details": state
    }


def reset_circuit_breaker(target: Optional[str] = None) -> dict:
    """Clears quarantine and resets error counters."""
    state = load_circuit_state()
    if not target or target.lower() in ("all", "*"):
        state["quarantined_models"] = {}
        state["quarantined_providers"] = {}
        state["model_error_counts"] = {}
        state["provider_error_counts"] = {}
        save_circuit_state(state)
        return {"ok": True, "reset": "all"}

    t_low = target.lower().strip()
    removed = []

    if t_low in state["quarantined_providers"]:
        del state["quarantined_providers"][t_low]
        state["provider_error_counts"].pop(t_low, None)
        removed.append(f"provider:{t_low}")

    for m in list(state["quarantined_models"].keys()):
        if t_low in m.lower():
            del state["quarantined_models"][m]
            state["model_error_counts"].pop(m, None)
            removed.append(f"model:{m}")

    save_circuit_state(state)
    return {"ok": True, "reset": removed}


def main():
    if "--status" in sys.argv:
        state = load_circuit_state()
        print(json.dumps(state, indent=2))
        return 0

    if "--reset" in sys.argv:
        idx = sys.argv.index("--reset")
        target = sys.argv[idx + 1] if len(sys.argv) > idx + 1 else "all"
        res = reset_circuit_breaker(target)
        print(json.dumps(res, indent=2))
        return 0

    res = check_and_update_circuit_breaker()
    print(json.dumps(res, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
