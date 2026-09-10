#!/usr/bin/env python3
"""
R.E.Y. // Model Override Engine
Enforces a chosen default model across OpenCode global configs, SQLite sessions,
and desktop IDE preferences, overriding whatever was selected in the IDE.
Zero manual typing: Page 1 (Top 7) + Page 2 (Options A-W for all 30 models).
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
DB_PATH = os.path.join(HOME, ".local", "share", "opencode", "opencode.db")
DESKTOP_DIR = os.path.join(os.environ.get("APPDATA", ""), "ai.opencode.desktop")

# Page 1: Top Recommended Fleet Models
PAGE1_MODELS = {
    "1": ("openrouter/cohere/north-mini-code:free", "openrouter", "Cohere North Mini Code (Free)"),
    "2": ("openrouter/nvidia/nemotron-3.5-lightning:free", "openrouter", "NVIDIA Nemotron 3.5 Lightning (Free)"),
    "3": ("openrouter/google/gemma-4-31b-it:free", "openrouter", "Google Gemma-4 31B (Free)"),
    "4": ("openrouter/openrouter/free", "openrouter", "OpenRouter Auto Free Router"),
    "5": ("kilo/kilo-auto/free", "kilo", "Kilo Code Auto (Free, No Key)"),
    "6": ("groq/qwen/qwen3.8-27b", "groq", "Groq Qwen 3.8 27B (Free)"),
    "7": ("openrouter/poolside/laguna-xs-2.1:free", "openrouter", "Poolside Laguna-XS 2.1 (Free)")
}

# Page 2: Extended Allowlisted Fleet Models (Zero typing, select by letter)
PAGE2_MODELS = {
    "A": ("openrouter/google/gemma-4-26b-a4b-it:free", "openrouter", "Google Gemma-4 26B A4B (Free)"),
    "B": ("openrouter/inclusionai/ling-3.0-flash-fin:free", "openrouter", "InclusionAI Ling 3.0 Flash Fin (Free)"),
    "C": ("openrouter/inclusionai/ling-3.0-flash-sante:free", "openrouter", "InclusionAI Ling 3.0 Flash Sante (Free)"),
    "D": ("openrouter/liquid/lfm-2.5-2.6b:free", "openrouter", "Liquid LFM 2.5 2.6B (Free)"),
    "E": ("openrouter/nex-agi/nex-n2.5-pro:free", "openrouter", "Nex-AGI Nex N2.5 Pro (Free)"),
    "F": ("openrouter/nvidia/nemotron-3-super-120b-a12b:free", "openrouter", "NVIDIA Nemotron 3 Super 120B (Free)"),
    "G": ("openrouter/nvidia/nemotron-3-ultra-550b-a55b:free", "openrouter", "NVIDIA Nemotron 3 Ultra 550B (Free)"),
    "H": ("openrouter/poolside/laguna-s-2.1:free", "openrouter", "Poolside Laguna-S 2.1 (Free)"),
    "I": ("openrouter/thinkingmachines/inkling:free", "openrouter", "ThinkingMachines Inkling (Free)"),
    "J": ("groq/openai/gpt-oss-120b", "groq", "Groq GPT OSS 120B (Free)"),
    "K": ("groq/openai/gpt-oss-20b", "groq", "Groq GPT OSS 20B (Free)"),
    "L": ("groq/openai/gpt-oss-safeguard-20b", "groq", "Groq GPT OSS Safeguard 20B (Free)"),
    "M": ("groq/qwen/qwen3.6-27b", "groq", "Groq Qwen 3.6 27B (Free)"),
    "N": ("mistral/codestral-latest", "mistral", "Mistral Codestral Latest (Free Credits)"),
    "O": ("mistral/mistral-small-4", "mistral", "Mistral Small 4 (Free Credits)"),
    "P": ("opencode/big-pickle", "opencode", "OpenCode Big Pickle (Local Free)"),
    "Q": ("opencode/nemotron-3.5-lightning-free", "opencode", "OpenCode Nemotron 3.5 Lightning (Free)"),
    "R": ("opencode/nemotron-3-ultra-free", "opencode", "OpenCode Nemotron 3 Ultra (Free)"),
    "S": ("opencode/ling-3.0-flash-fin-free", "opencode", "OpenCode Ling 3.0 Flash Fin (Free)"),
    "T": ("opencode/mimo-v2.5-free", "opencode", "OpenCode Mimo v2.5 (Free)"),
    "U": ("opencode/muse-spark-1.3-contributor-free", "opencode", "OpenCode Muse Spark 1.3 Contributor (Free)"),
    "V": ("opencode/muse-spark-1.2-contributor-free", "opencode", "OpenCode Muse Spark 1.2 Contributor (Free)"),
    "W": ("opencode/muse-spark-1.3-free", "opencode", "OpenCode Muse Spark 1.3 Standard (Free)")
}

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
                with open(fpath, "r", encoding="utf-8") as f:
                    dcontent = f.read()
                if "model-selection" in dcontent:
                    dcontent = re.sub(r'"modelID":"[^"]+"', f'"modelID":"{raw_model_id}"', dcontent)
                    dcontent = re.sub(r'"providerID":"[^"]+"', f'"providerID":"{provider_id}"', dcontent)
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(dcontent)
            except Exception:
                pass

def set_override(full_model_id):
    """Enforces a single model override everywhere."""
    provider_id, raw_model_id = parse_model_string(full_model_id)

    lock_data = {
        "mode": "single",
        "model": full_model_id,
        "provider": provider_id,
        "raw_model": raw_model_id,
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
        print("[i] Available codes: 1-7 (Page 1), A-W (Page 2). Example: W, U, T")
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
    lock_data = {
        "mode": "rotate",
        "active": True,
        "pool": pool,
        "current_index": 0,
        "model": first["model"],
        "provider": first["provider"],
        "raw_model": first["raw_model"],
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
    """Removes the active override or rotation lock."""
    if os.path.exists(OVERRIDE_LOCK):
        os.remove(OVERRIDE_LOCK)
        print("[+] Model override and rotation cleared. OpenCode will use config defaults.")
    else:
        print("[i] No active model override was set.")

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

    for k, (model_id, prov, desc) in sorted(PAGE2_MODELS.items()):
        print(f" [{k}] {desc}")
        print(f"     ID: {model_id}")
    print("-" * 75)
    print(" [0] Return to Page 1")
    print("=" * 75)

    try:
        choice = input("\n Select model [A-W] or enter 2-5 models (e.g. W, U, T), or 0 to go back: ").strip()
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
    if choice_upper in PAGE2_MODELS:
        selected_model = PAGE2_MODELS[choice_upper][0]
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
    print(" [8] View Other Allowlisted Models (Page 2: Options A-W, Zero Typing)")
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
    elif choice_upper in PAGE2_MODELS:
        selected_model = PAGE2_MODELS[choice_upper][0]
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
        if arg in ("--clear", "-c", "clear"):
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
        else:
            set_override(arg)
    else:
        interactive_menu()
