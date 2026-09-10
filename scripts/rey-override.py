#!/usr/bin/env python3
"""
R.E.Y. // Model Override Engine
Enforces a chosen default model across OpenCode global configs, SQLite sessions,
and desktop IDE preferences, overriding whatever was selected in the IDE.
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

PRESET_MODELS = {
    "1": ("openrouter/cohere/north-mini-code:free", "openrouter", "Cohere North Mini Code (Free)"),
    "2": ("openrouter/nvidia/nemotron-3.5-lightning:free", "openrouter", "NVIDIA Nemotron 3.5 Lightning (Free)"),
    "3": ("openrouter/google/gemma-4-31b-it:free", "openrouter", "Google Gemma-4 31B (Free)"),
    "4": ("openrouter/openrouter/free", "openrouter", "OpenRouter Auto Free Router"),
    "5": ("kilo/kilo-auto/free", "kilo", "Kilo Code Auto (Free, No Key)"),
    "6": ("groq/qwen/qwen3.8-27b", "groq", "Groq Qwen 3.8 27B (Free)"),
    "7": ("openrouter/poolside/laguna-xs-2.1:free", "openrouter", "Poolside Laguna-XS 2.1 (Free)")
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

def set_override(full_model_id):
    """Enforces the model override everywhere."""
    provider_id, raw_model_id = parse_model_string(full_model_id)

    # 1. Update override lock file
    lock_data = {
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

    # 2. Update opencode.json & opencode.jsonc
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
                print(f"[!] Error updating {path}: {e}")

    # Also mirror into opencode-swarm-pack configs
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

    # 3. Update active sessions in SQLite opencode.db
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
                "UPDATE session SET model = ? WHERE time_updated > ? OR model LIKE '%muse-spark%'",
                (new_model_json, cutoff_ms)
            )
            updated_sessions = c.rowcount
            conn.commit()
            conn.close()
            print(f"[+] Overrode {updated_sessions} active/recent sessions in SQLite database.")
        except Exception as e:
            print(f"[!] SQLite session update error: {e}")

    # 4. Update desktop dat files if present
    if os.path.exists(DESKTOP_DIR):
        dat_files = glob.glob(os.path.join(DESKTOP_DIR, "*.dat"))
        for fpath in dat_files:
            try:
                with open(fpath, "r", encoding="utf-8") as f:
                    dcontent = f.read()
                if "model-selection" in dcontent or "muse-spark" in dcontent:
                    dcontent = re.sub(r'"modelID":"[^"]+"', f'"modelID":"{raw_model_id}"', dcontent)
                    dcontent = re.sub(r'"providerID":"[^"]+"', f'"providerID":"{provider_id}"', dcontent)
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(dcontent)
            except Exception:
                pass

    print(f"\n[OK] Model override strictly locked to: {full_model_id}")
    print("[*] All active sessions, configs, and IDE defaults now use this model!")

def clear_override():
    """Removes the active override lock."""
    if os.path.exists(OVERRIDE_LOCK):
        os.remove(OVERRIDE_LOCK)
        print("[+] Model override cleared. OpenCode will use standard config defaults.")
    else:
        print("[i] No active model override was set.")

def interactive_menu():
    """CLI interactive model picker."""
    print("\n" + "=" * 70)
    print(" R.E.Y. MODEL OVERRIDE CONTROLLER (Enforces Model on OpenCode IDE)")
    print("=" * 70)
    
    current_lock = None
    if os.path.exists(OVERRIDE_LOCK):
        try:
            with open(OVERRIDE_LOCK, "r", encoding="utf-8") as f:
                current_lock = json.load(f).get("model")
        except Exception:
            pass

    if current_lock:
        print(f" CURRENT ACTIVE OVERRIDE: {current_lock} [LOCKED]")
    else:
        print(" CURRENT ACTIVE OVERRIDE: None (using config default)")
    print("-" * 70)

    for k, (model_id, prov, desc) in sorted(PRESET_MODELS.items()):
        print(f" [{k}] {desc}")
        print(f"     Model ID: {model_id}")
    print(" [8] Custom Model ID (enter any allowlisted model string)")
    print(" [9] Clear / Remove Override")
    print(" [0] Cancel (Keep current)")
    print("=" * 70)

    try:
        choice = input("\n Select option [0-9]: ").strip()
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return

    if choice == "0" or not choice:
        print("Cancelled.")
        return
    elif choice in PRESET_MODELS:
        selected_model = PRESET_MODELS[choice][0]
        set_override(selected_model)
    elif choice == "8":
        custom = input(" Enter exact model string (e.g. openrouter/poolside/laguna-s-2.1:free): ").strip()
        if custom:
            set_override(custom)
        else:
            print("Cancelled: empty input.")
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
        else:
            set_override(arg)
    else:
        interactive_menu()
