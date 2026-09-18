#!/usr/bin/env python3
"""
R.E.Y. // Model Override Engine
Enforces a chosen default model across OpenCode global configs, SQLite sessions,
and desktop IDE preferences, overriding whatever was selected in the IDE.
Zero manual typing: Page 1 (Top 7) + Page 2 (Options A-Z) + Dynamic Models (AA-ZZ).
"""

import sys
import os
import json
import sqlite3
import glob
import re

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME, ".config", "opencode")
CONFIG_JSON = os.path.join(CONFIG_DIR, "opencode.json")
CONFIG_JSONC = os.path.join(CONFIG_DIR, "opencode.jsonc")
OVERRIDE_LOCK = os.path.join(CONFIG_DIR, "override-lock.json")


def _get_desktop_dir() -> str:
    """Cross-platform OpenCode Desktop app data dir."""
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA", "")
        return os.path.join(appdata, "ai.opencode.desktop") if appdata else ""
    elif sys.platform == "darwin":
        return os.path.join(HOME, "Library", "Application Support", "ai.opencode.desktop")
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME", os.path.join(HOME, ".config"))
        return os.path.join(xdg, "ai.opencode.desktop")


def _resolve_db_path() -> str:
    """Cross-platform OpenCode DB resolver.
    macOS: ~/Library/Application Support/opencode/opencode.db
    Linux/Windows: ~/.local/share/opencode/opencode.db
    """
    candidates = [
        os.path.join(HOME, "Library", "Application Support", "opencode", "opencode.db"),
        os.path.join(HOME, ".local", "share", "opencode", "opencode.db"),
        os.path.join(os.environ.get("USERPROFILE", HOME), ".local", "share", "opencode", "opencode.db"),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return os.path.join(HOME, ".local", "share", "opencode", "opencode.db")


DB_PATH = _resolve_db_path()
DESKTOP_DIR = _get_desktop_dir()

# Page 1: Top Recommended Fleet Models
PAGE1_MODELS = {
    "1": ("gemini/gemini-3.8-flash", "gemini", "Google Gemini 3.8 Flash (AI Studio Free)"),
    "2": ("gemini/gemini-3.7-flash", "gemini", "Google Gemini 3.7 Flash (AI Studio Free)"),
    "3": ("gemini/gemini-3.6-flash", "gemini", "Google Gemini 3.6 Flash (AI Studio Free)"),
    "4": ("mistral/codestral-latest", "mistral", "Mistral Codestral Latest (Free Key)"),
    "5": ("openrouter/cohere/north-mini-code:free", "openrouter", "Cohere North Mini Code (Free)"),
    "6": ("openrouter/nvidia/nemotron-3.5-lightning:free", "openrouter", "NVIDIA Nemotron 3.5 Lightning (Free)"),
    "7": ("kilo/kilo-auto/free", "kilo", "Kilo Code Auto (Free, No Key)")
}

# Page 2: Extended Allowlisted Fleet Models (Zero typing, select by letter)
PAGE2_MODELS = {
    "A": ("gemini/gemini-flash-latest", "gemini", "Google Gemini Flash Latest (AI Studio Free)"),
    "B": ("openrouter/google/gemma-4-31b-it:free", "openrouter", "Google Gemma-4 31B (OpenRouter Free)"),
    "C": ("openrouter/google/gemma-4-26b-a4b-it:free", "openrouter", "Google Gemma-4 26B A4B (OpenRouter Free)"),
    "D": ("openrouter/openrouter/free", "openrouter", "OpenRouter Auto Free Router"),
    "E": ("openrouter/poolside/laguna-xs-2.1:free", "openrouter", "Poolside Laguna-XS 2.1 (Free)"),
    "F": ("openrouter/poolside/laguna-s-2.1:free", "openrouter", "Poolside Laguna-S 2.1 (Free)"),
    "G": ("openrouter/inclusionai/ling-3.0-flash-fin:free", "openrouter", "InclusionAI Ling 3.0 Flash Fin (Free)"),
    "H": ("openrouter/inclusionai/ling-3.0-flash-sante:free", "openrouter", "InclusionAI Ling 3.0 Flash Sante (Free)"),
    "I": ("openrouter/liquid/lfm-2.5-2.6b:free", "openrouter", "Liquid LFM 2.5 2.6B (Free)"),
    "J": ("openrouter/nex-agi/nex-n2.5-pro:free", "openrouter", "Nex-AGI Nex N2.5 Pro (Free)"),
    "K": ("openrouter/nvidia/nemotron-3-super-120b-a12b:free", "openrouter", "NVIDIA Nemotron 3 Super 120B (Free)"),
    "L": ("openrouter/nvidia/nemotron-3-ultra-550b-a55b:free", "openrouter", "NVIDIA Nemotron 3 Ultra 550B (Free)"),
    "M": ("openrouter/thinkingmachines/inkling:free", "openrouter", "ThinkingMachines Inkling (Free)"),
    "N": ("mistral/codestral-2508", "mistral", "Mistral Codestral 2508 (Free Key)"),
    "O": ("opencode/big-pickle", "opencode", "OpenCode Big Pickle (Local Free)"),
    "P": ("opencode/nemotron-3.5-lightning-free", "opencode", "OpenCode Nemotron 3.5 Lightning (Free)"),
    "Q": ("opencode/nemotron-3-ultra-free", "opencode", "OpenCode Nemotron 3 Ultra (Free)"),
    "R": ("opencode/ling-3.0-flash-fin-free", "opencode", "OpenCode Ling 3.0 Flash Fin (Free)"),
    "S": ("opencode/mimo-v2.5-free", "opencode", "OpenCode Mimo v2.5 (Free)"),
    "T": ("opencode/muse-spark-1.3-contributor-free", "opencode", "OpenCode Muse Spark 1.3 Contributor (Free)"),
    "U": ("opencode/muse-spark-1.2-contributor-free", "opencode", "OpenCode Muse Spark 1.2 Contributor (Free)"),
    "V": ("opencode/muse-spark-1.3-free", "opencode", "OpenCode Muse Spark 1.3 Standard (Free)"),
    "W": ("lmstudio/deepseek-r1-distill-qwen-1.5b", "lmstudio", "DeepSeek R1 Distill Qwen 1.5B (LM Studio)"),
    "X": ("lmstudio/qwen3.5-0.8b", "lmstudio", "Qwen 3.5 0.8B (LM Studio)"),
    "Y": ("openrouter/inclusionai/ling-3.0-flash-vl:free", "openrouter", "InclusionAI Ling 3.0 Flash VL (Free 262k)"),
    "Z": ("openrouter/thinkingmachines/inkling-small:free", "openrouter", "ThinkingMachines Inkling Small (Free 1M)")
}


def _next_double_letter(current):
    """Get next double-letter code (AA, AB, AC... ZZ)."""
    if len(current) != 2:
        return None
    first, second = current[0], current[1]
    if second == "Z":
        if first == "Z":
            return None  # Out of double-letter codes
        return f"{chr(ord(first) + 1)}A"
    else:
        return f"{first}{chr(ord(second) + 1)}"


def _load_dynamic_models():
    """
    Load dynamic models from allowlist configs and merge with static PAGE1 and PAGE2.
    Returns a combined dict of all models (PAGE1, PAGE2, and dynamic ones).
    """
    combined = {**PAGE1_MODELS, **PAGE2_MODELS}
    
    # Provider to prefix mapping for full model IDs
    PROVIDER_PREFIX = {
        "openrouter": "openrouter",
        "kilo": "kilo",
        "opencode": "opencode",
        "gemini": "gemini",
        "mistral": "mistral",
        "groq": "groq",
        "deepseek": "deepseek",
        "lmstudio": "lmstudio",
    }
    
    # Gather all allowlisted models from configs with descriptions
    # Map: full_model_id -> (provider, description)
    allowlisted = {}
    config_paths = [
        CONFIG_JSONC,
        os.path.join(os.path.dirname(__file__), "..", "configs", "opencode.jsonc"),
        CONFIG_JSON,
        os.path.join(os.path.dirname(__file__), "..", "configs", "opencode.json"),
        os.path.join(CONFIG_DIR, "model-fallback.json")
    ]
    
    for path in config_paths:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                # Strip comments like in rey-health.py
                lines = []
                for line in content.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("//") or stripped.startswith("/*"):
                        continue
                    idx = line.find(" //")
                    if idx != -1:
                        line = line[:idx]
                    lines.append(line)
                cleaned = "\n".join(lines)
                cdata = json.loads(cleaned, strict=False)
                
                # Extract from all providers' whitelists and models dict
                if "provider" in cdata:
                    for prov_name, prov_data in cdata["provider"].items():
                        prefix = PROVIDER_PREFIX.get(prov_name, prov_name)
                        whitelist = prov_data.get("whitelist", [])
                        models_dict = prov_data.get("models", {})
                        for m in whitelist:
                            if not m:
                                continue
                            # Build full model ID with provider prefix
                            if not m.startswith(prefix + "/"):
                                full_id = f"{prefix}/{m}"
                            else:
                                full_id = m
                            # Get description from models dict if available
                            desc = None
                            if m in models_dict and "name" in models_dict[m]:
                                desc = models_dict[m]["name"]
                            allowlisted[full_id] = (prov_name, desc)
                
                # Also extract from fallbackModels in model-fallback.json
                if "agents" in cdata and "*" in cdata["agents"]:
                    fallback_models = cdata["agents"]["*"].get("fallbackModels", [])
                    for m in fallback_models:
                        if m and m.startswith("openrouter/"):
                            # fallback models already have full ID
                            if m not in allowlisted:
                                allowlisted[m] = ("openrouter", None)
                            
            except Exception:
                pass
    
    # Fallback extra models if configs missing or incomplete
    FALLBACK_EXTRA_MODELS = {
        "openrouter/qwen/qwen3.8-27b:free": ("openrouter", "Qwen 3.8 27B (free)"),
        "openrouter/deepseek/deepseek-v4-flash-0731:free": ("openrouter", "DeepSeek V4 Flash (free)"),
        "openrouter/z-ai/glm-5.2:free": ("openrouter", "GLM 5.2 (free)"),
        "openrouter/nvidia/nemotron-3.5-content-safety:free": ("openrouter", "Nemotron 3.5 Content Safety (free)"),
        "openrouter/nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free": ("openrouter", "Nemotron 3 Nano Omni (free)"),
        "openrouter/dots-studio/dots-3-note-preview:free": ("openrouter", "Dots3-Note Preview (free)"),
        "openrouter/stealth/union-alpha": ("openrouter", "Union Alpha (free)"),
        "openrouter/nex-agi/nex-n2.5-mini:free": ("openrouter", "Nex-N2.5-Mini (free)"),
        "kilo/stepfun/step-3.7-flash:free": ("kilo", "Step 3.7 Flash (free)"),
    }
    for mid, (prov, desc) in FALLBACK_EXTRA_MODELS.items():
        if mid not in allowlisted:
            allowlisted[mid] = (prov, desc)
    
    # Remove duplicates already present in PAGE1+PAGE2
    existing = set()
    for entry in combined.values():
        if entry and len(entry) > 0:
            existing.add(entry[0])
    
    # Convert to list of (model_id, provider, desc, raw_id) tuples for processing
    new_entries = []
    for model_id in sorted(allowlisted.keys()):
        if model_id in existing:
            continue
        prov, desc_from_config = allowlisted[model_id]
        provider_id, model_str = parse_model_string(model_id)
        provider_display = prov if prov else provider_id
        
        # Use description from config if available, else generate heuristic
        if desc_from_config:
            display_name = desc_from_config
        else:
            # Heuristic generation (same as before)
            if model_str.startswith("openrouter/"):
                model_str = model_str.replace("openrouter/", "")
            if ":" in model_str:
                model_str = model_str.replace(":free", "")
            words = []
            current_word = []
            for char in model_str:
                if char.isupper():
                    if current_word:
                        words.append("".join(current_word))
                        current_word = []
                    current_word.append(char)
                elif char in "-_.":
                    if current_word:
                        words.append("".join(current_word))
                        current_word = []
                else:
                    current_word.append(char.lower())
            if current_word:
                words.append("".join(current_word))
            display_name = " ".join(word.capitalize() for word in words if word)
            # Fallback display names for known patterns
            if "ling-3.0-flash" in model_str:
                if "vl" in model_str:
                    display_name = "InclusionAI Ling 3.0 Flash VL"
                elif "sante" in model_str:
                    display_name = "InclusionAI Ling 3.0 Flash Sante"
                elif "fin" in model_str:
                    display_name = "InclusionAI Ling 3.0 Flash Fin"
        
        # Create description
        if provider_id == "openrouter":
            desc = f"{display_name} (OpenRouter Free)"
        else:
            desc = f"{display_name} ({provider_display.title()} Free)"
        
        # Extract raw model for database storage
        raw_id = parse_model_string(model_id)[1]
        new_entries.append((model_id, provider_display, desc, raw_id))
    
    # Generate letter codes starting after Z (AA, AB, AC...)
    code = "AA"
    idx = 0
    while idx < len(new_entries):
        if code not in combined:
            model_id, provider, desc, raw_id = new_entries[idx]
            combined[code] = (model_id, provider, desc)
            idx += 1
        code = _next_double_letter(code)
        if code is None:
            break
    
    return combined


def get_all_models():
    """Get combined dict of PAGE1, PAGE2, and dynamic models."""
    return _load_dynamic_models()


def parse_model_string(model_str):
    """Parses 'provider/model' into (provider_id, model_id)."""
    parts = model_str.split("/", 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    return "openrouter", model_str


def clean_json_text(text):
    """Safely removes comments from JSONC without touching URLs."""
    lines = []
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("//") or stripped.startswith("/*"):
            continue
        idx = line.find(" //")
        if idx != -1:
            line = line[:idx]
        lines.append(line)
    cleaned = "\n".join(lines)
    cleaned = re.sub(r",\s*([\]}])", r"\1", cleaned)
    return cleaned


def _apply_model_systemwide(full_model_id, verbose=True):
    """Applies model across opencode.json, opencode.jsonc, opencode.db, and desktop dat files."""
    provider_id, raw_model_id = parse_model_string(full_model_id)

    # 1. Update opencode.json & opencode.jsonc
    for path in [CONFIG_JSON, CONFIG_JSONC]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                clean = clean_json_text(content)
                data = json.loads(clean, strict=False)
                data["model"] = full_model_id
                if "agent" in data and "build" in data["agent"]:
                    data["agent"]["build"]["model"] = full_model_id
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except Exception as e:
                if verbose:
                    print(f"[!] Error updating {path}: {e}")

    # Mirror into repo configs if local
    local_repo_configs = [
        os.path.join(os.path.dirname(__file__), "..", "configs", "opencode.json"),
        os.path.join(os.path.dirname(__file__), "..", "configs", "opencode.jsonc")
    ]
    for path in local_repo_configs:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                clean = clean_json_text(content)
                data = json.loads(clean, strict=False)
                data["model"] = full_model_id
                if "agent" in data and "build" in data["agent"]:
                    data["agent"]["build"]["model"] = full_model_id
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except Exception:
                pass

    # 2. Update active sessions in SQLite opencode.db
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            new_model_json = json.dumps({
                "id": raw_model_id,
                "providerID": provider_id,
                "variant": "default"
            })
            import time
            cutoff_ms = int((time.time() - (48 * 3600)) * 1000)
            c.execute(
                "UPDATE session SET model = ? WHERE time_updated > ?",
                (new_model_json, cutoff_ms)
            )
            updated_sessions = c.rowcount
            conn.commit()
            conn.close()
            if verbose:
                print(f"[+] Overrode {updated_sessions} active/recent sessions in SQLite database.")
        except Exception as e:
            if verbose:
                print(f"[!] SQLite session update error: {e}")

    # 3. Update desktop dat files if present
    if os.path.exists(DESKTOP_DIR):
        dat_files = glob.glob(os.path.join(DESKTOP_DIR, "*.dat"))
        for fpath in dat_files:
            try:
                with open(fpath, "r", encoding="utf-8-sig") as f:
                    dcontent = f.read()
                if "model-selection" in dcontent:
                    dcontent = re.sub(
                        r'\\"modelID\\":\\"[^"\\]+\\"',
                        lambda m: '\\"modelID\\":\\"%s\\"' % raw_model_id,
                        dcontent
                    )
                    dcontent = re.sub(
                        r'\\"providerID\\":\\"[^"\\]+\\"',
                        lambda m: '\\"providerID\\":\\"%s\\"' % provider_id,
                        dcontent
                    )
                    dcontent = re.sub(r'"modelID":"[^"]+"', f'"modelID":"{raw_model_id}"', dcontent)
                    dcontent = re.sub(r'"providerID":"[^"]+"', f'"providerID":"{provider_id}"', dcontent)
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(dcontent)
            except Exception:
                pass


def get_base_default_model():
    """Gets the baseline default model from configs or defaults."""
    if os.path.exists(OVERRIDE_LOCK):
        try:
            with open(OVERRIDE_LOCK, "r", encoding="utf-8") as f:
                ldata = json.load(f)
                if ldata.get("original_model"):
                    return ldata["original_model"]
        except Exception:
            pass

    for path in [CONFIG_JSON, CONFIG_JSONC]:
        if os.path.exists(path):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    content = f.read()
                clean = clean_json_text(content)
                data = json.loads(clean)
                if data.get("model"):
                    return data["model"]
            except Exception:
                pass

    return "openrouter/google/gemma-4-31b-it:free"


def set_override(full_model_id):
    """Enforces a single model override everywhere."""
    provider_id, raw_model_id = parse_model_string(full_model_id)
    original_model = get_base_default_model()

    lock_data = {
        "mode": "single",
        "model": full_model_id,
        "provider": provider_id,
        "raw_model": raw_model_id,
        "original_model": original_model,
        "active": True
    }
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(OVERRIDE_LOCK, "w", encoding="utf-8") as f:
            json.dump(lock_data, f, indent=2)
    except Exception as e:
        print(f"[!] Could not write override lock: {e}")

    _apply_model_systemwide(full_model_id)
    print(f"\n[OK] Model override strictly locked to: {full_model_id}")
    print("[*] All active sessions, configs, and IDE defaults now use this model!")


def set_rotation(codes_or_str):
    """
    Configures a rotating model pool that loops through 2-5 models,
    switching to the next model after every prompt.
    """
    if isinstance(codes_or_str, str):
        raw_items = [p.strip().upper() for p in re.split(r'[,;\s]+', codes_or_str) if p.strip()]
    else:
        raw_items = [str(p).strip().upper() for p in codes_or_str if str(p).strip()]

    all_models = {**PAGE1_MODELS, **PAGE2_MODELS}

    pool = []
    invalid = []
    for item in raw_items:
        if item in all_models:
            mid, prov, desc = all_models[item]
            pool.append({
                "code": item,
                "model": mid,
                "provider": prov,
                "raw_model": parse_model_string(mid)[1],
                "desc": desc
            })
        else:
            if "/" in item:
                prov, raw = parse_model_string(item.lower())
                pool.append({
                    "code": raw[:10],
                    "model": item.lower(),
                    "provider": prov,
                    "raw_model": raw,
                    "desc": item.lower()
                })
            else:
                invalid.append(item)

    if invalid:
        print(f"\n[!] Invalid model code(s): {', '.join(invalid)}")
        print("[i] Available codes: 1-7 (Page 1), A-Z (Page 2). Example: W, U, T")
        return False

    if len(pool) < 2:
        print(f"\n[!] Rotation pool requires at least 2 models (you provided {len(pool)}). Example: W, U, T")
        return False

    if len(pool) > 5:
        print(f"\n[!] Maximum 5 models allowed in rotation pool (you provided {len(pool)}).")
        return False

    latest_prompt_id = None
    if os.path.exists(DB_PATH):
        try:
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute("SELECT id FROM message WHERE json_extract(data, '$.role') = 'user' ORDER BY time_created DESC LIMIT 1")
            row = c.fetchone()
            if row:
                latest_prompt_id = row[0]
            conn.close()
        except Exception:
            pass

    first = pool[0]
    original_model = get_base_default_model()
    lock_data = {
        "mode": "rotate",
        "active": True,
        "pool": pool,
        "current_index": 0,
        "model": first["model"],
        "provider": first["provider"],
        "raw_model": first["raw_model"],
        "original_model": original_model,
        "last_prompt_id": latest_prompt_id,
        "pending_rotation": False
    }

    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(OVERRIDE_LOCK, "w", encoding="utf-8") as f:
            json.dump(lock_data, f, indent=2)
    except Exception as e:
        print(f"[!] Could not write override lock: {e}")

    _apply_model_systemwide(first["model"])

    print("\n" + "=" * 75)
    print(" [+] ROTATING MODEL POOL ACTIVATED! (Auto-loops after every prompt)")
    print("=" * 75)
    for idx, item in enumerate(pool):
        active_tag = "  <-- ACTIVE FOR PROMPT 1" if idx == 0 else ""
        print(f"   [{idx + 1}/{len(pool)}] [{item['code']}] {item['desc']}{active_tag}")
        print(f"         ID: {item['model']}")
    print("-" * 75)
    seq = " -> ".join(f"[{p['code']}]" for p in pool)
    print(f" Loop sequence: {seq} -> (loops back to [{pool[0]['code']}])")
    print(" R.E.Y. will automatically rotate to the next model in the pool after each prompt!")
    print("=" * 75 + "\n")
    return True


def clear_override():
    """Removes the active override or rotation lock and immediately restores the default model."""
    original_model = "openrouter/google/gemma-4-31b-it:free"
    had_lock = False
    if os.path.exists(OVERRIDE_LOCK):
        had_lock = True
        try:
            with open(OVERRIDE_LOCK, "r", encoding="utf-8") as f:
                ldata = json.load(f)
                if ldata.get("original_model"):
                    original_model = ldata["original_model"]
        except Exception:
            pass
        try:
            os.remove(OVERRIDE_LOCK)
        except Exception:
            pass

    _apply_model_systemwide(original_model, verbose=False)
    if had_lock:
        print("\n" + "=" * 75)
        print(" [+] MODEL OVERRIDE / ROTATION CLEARED!")
        print(f" [*] Restored default model: {original_model}")
        print(" [*] Updated opencode.json, opencode.jsonc, active sessions, and IDE defaults.")
        print("=" * 75 + "\n")
    else:
        print(f"\n[i] No active override lock was set. Ensured default model: {original_model}")


def parse_multi_input(text):
    """Checks if input represents a multi-model rotation request."""
    if not text:
        return None
    tokens = [p.strip().upper() for p in re.split(r'[,;\s]+', text) if p.strip()]
    if len(tokens) >= 2:
        return tokens
    return None


def show_page2():
    """Page 2: Full listing of remaining 23 allowlisted models (zero manual typing)."""
    print("\n" + "=" * 75)
    print(" R.E.Y. MODEL OVERRIDE - PAGE 2: ALL ALLOWLISTED FLEET MODELS (ZERO TYPING)")
    print("=" * 75)

    # Get all models including dynamic ones
    all_models = get_all_models()
    
    # Display only Page 2 models and dynamic models
    displayed_codes = set(PAGE2_MODELS.keys())
    dynamic_codes = [code for code in all_models.keys() if code not in PAGE1_MODELS and code not in PAGE2_MODELS]
    
    for code in sorted(list(displayed_codes) + sorted(dynamic_codes)):
        if code in all_models:
            model_id, prov, desc = all_models[code]
            print(f" [{code}] {desc}")
            print(f"     ID: {model_id}")
    print("-" * 75)
    print(" [0] Return to Page 1")
    print("=" * 75)

    try:
        choice = input("\n Select model [A-Z] or enter 2-5 models (e.g. W, U, T), or 0 to go back: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return

    if choice == "0" or not choice:
        interactive_menu()
        return

    multi = parse_multi_input(choice)
    if multi:
        set_rotation(multi)
        return

    choice_upper = choice.upper()
    if choice_upper in all_models:
        selected_model = all_models[choice_upper][0]
        set_override(selected_model)
    elif choice_upper in PAGE1_MODELS:
        selected_model = PAGE1_MODELS[choice_upper][0]
        set_override(selected_model)
    else:
        print("Invalid choice.")


def interactive_menu():
    """CLI interactive model picker (Page 1: Top 7 + Option 8 for Page 2 + Rotation Pool)."""
    print("\n" + "=" * 75)
    print(" R.E.Y. MODEL OVERRIDE CONTROLLER (Enforces Model on OpenCode IDE)")
    print("=" * 75)
    
    current_lock = None
    if os.path.exists(OVERRIDE_LOCK):
        try:
            with open(OVERRIDE_LOCK, "r", encoding="utf-8") as f:
                ldata = json.load(f)
                if ldata.get("active"):
                    if ldata.get("mode") == "rotate":
                        pool = ldata.get("pool", [])
                        curr_idx = ldata.get("current_index", 0)
                        flow = " -> ".join(f"[{p['code']}]" + ("*" if i == curr_idx else "") for i, p in enumerate(pool))
                        curr_code = pool[curr_idx]["code"] if curr_idx < len(pool) else "?"
                        curr_model = ldata.get("model", "")
                        current_lock = f"[ROTATING POOL: {flow}] Current: [{curr_code}] {curr_model}"
                    else:
                        current_lock = ldata.get("model")
        except Exception:
            pass

    if current_lock:
        print(f" CURRENT ACTIVE OVERRIDE: {current_lock} [LOCKED]")
    else:
        print(" CURRENT ACTIVE OVERRIDE: None (using config default)")
    print("-" * 75)

    for k, (model_id, prov, desc) in sorted(PAGE1_MODELS.items()):
        print(f" [{k}] {desc}")
        print(f"     ID: {model_id}")
    
    # Show Page 2 and dynamic models count
    all_models = get_all_models()
    page2_codes = set(PAGE2_MODELS.keys())
    dynamic_codes = [code for code in all_models.keys() if code not in PAGE1_MODELS and code not in PAGE2_MODELS]
    
    print(f" [8] View Other Allowlisted Models (Page 2: Options A-Z, Zero Typing) [+{len(dynamic_codes)} dynamic models available]")
    print(" [R] Setup Rotating Model Pool (e.g. W, U, T to loop 2-5 models per prompt)")
    print(" [9] Clear / Remove Override & Rotation")
    print(" [0] Cancel (Keep current)")
    print("=" * 75)

    try:
        choice = input("\n Select option [0-9, R] or enter 2-5 models (e.g. W, U, T): ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return

    if choice == "0" or not choice:
        print("Cancelled.")
        return

    multi = parse_multi_input(choice)
    if multi:
        set_rotation(multi)
        return

    choice_upper = choice.upper()
    if choice_upper == "R":
        try:
            rot_input = input("\n Enter 2 to 5 model codes to rotate (e.g. W, U, T or 1, 2, 3): ").strip()
            if rot_input:
                set_rotation(rot_input)
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled.")
        return
    elif choice in PAGE1_MODELS:
        selected_model = PAGE1_MODELS[choice][0]
        set_override(selected_model)
    elif choice_upper in all_models:
        selected_model = all_models[choice_upper][0]
        set_override(selected_model)
    elif choice == "8":
        show_page2()
    elif choice == "9":
        clear_override()
    else:
        print("Invalid choice.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg in ("--help", "-h", "help"):
            print("\n  R.E.Y. // Model Override CLI")
            print("  Usage: rey override [option | model_code | model_id]")
            print("\n  Options:")
            print("    --status, -s     Show current active model override lock")
            print("    --clear, -c      Clear active override lock")
            print("    --rotate, -r     Rotate between multiple models (e.g. rey override -r 1 4 7)")
            print("    --page2, -p2     Show extended model list (A-Z)")
            print("    --menu, -m       Launch interactive menu")
            print("\n  Examples:")
            print("    rey override 7                          # Lock to Kilo Code Auto")
            print("    rey override openrouter/google/gemma... # Lock by model ID")
            print("    rey override --clear                    # Clear lock")
            print("    rey override --status                   # View lock status\n")
            sys.exit(0)
        elif arg in ("--status", "-s", "status"):
            current_lock = None
            if os.path.exists(OVERRIDE_LOCK):
                try:
                    with open(OVERRIDE_LOCK, "r", encoding="utf-8") as f:
                        ldata = json.load(f)
                        if ldata.get("active"):
                            if ldata.get("mode") == "rotate":
                                pool = ldata.get("pool", [])
                                curr_idx = ldata.get("current_index", 0)
                                flow = " -> ".join(f"[{p.get('code','?')}]" + ("*" if i == curr_idx else "") for i, p in enumerate(pool))
                                curr_model = ldata.get("model", "")
                                current_lock = f"[ROTATION POOL: {flow}] Current: {curr_model}"
                            else:
                                current_lock = ldata.get("model")
                except Exception:
                    pass
            if current_lock:
                print(f"\n  [LOCK ACTIVE] Model: {current_lock}\n")
            else:
                print("\n  [INFO] No active model override lock. OpenCode is using defaults.\n")
            sys.exit(0)
        elif arg in ("--clear", "-c", "clear"):
            clear_override()
        elif arg in ("--menu", "-m", "menu"):
            interactive_menu()
        elif arg in ("--page2", "-p2", "page2"):
            show_page2()
        elif arg in ("--rotate", "-r", "rotate"):
            if len(sys.argv) > 2:
                set_rotation(" ".join(sys.argv[2:]))
            else:
                interactive_menu()
        elif "," in arg or len(sys.argv) > 2:
            items = sys.argv[1:]
            set_rotation(" ".join(items))
        elif arg in PAGE1_MODELS:
            set_override(PAGE1_MODELS[arg][0])
        elif arg.upper() in get_all_models():
            set_override(get_all_models()[arg.upper()][0])
        elif arg.startswith("-"):
            print(f"\n[!] Unknown option: {arg}. Run 'rey override --help' for usage.\n")
            sys.exit(1)
        else:
            set_override(arg)
    else:
        interactive_menu()