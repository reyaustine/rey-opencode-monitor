#!/usr/bin/env python3
"""
R.E.Y. // Advanced Provider Switcher & IDE Model Visibility Commander
Supports Primary + Secondary dual provider routing, subagent delegation mapping,
and real-time Show/Hide model visibility synchronization across OpenCode CLI & IDE.
"""

import os
import sys
import json
import re
import glob
import time
import sqlite3
from typing import Dict, List, Tuple, Optional, Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

# ANSI Color Codes
CYAN = "\033[96m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
MAGENTA = "\033[95m"
WHITE = "\033[97m"
GRAY = "\033[90m"
BOLD = "\033[1m"
RESET = "\033[0m"
CLEAR = "\033[2J\033[H"

HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME, ".config", "opencode")
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


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


DESKTOP_DIR = _get_desktop_dir()
DB_PATH = _resolve_db_path()
CONFIG_PATHS = [
    os.path.join(CONFIG_DIR, "opencode.jsonc"),
    os.path.join(CONFIG_DIR, "opencode.json"),
    os.path.join(ROOT_DIR, "configs", "opencode.jsonc"),
    os.path.join(ROOT_DIR, "configs", "opencode.json"),
    os.path.join(ROOT_DIR, "opencode.jsonc"),
    os.path.join(ROOT_DIR, "opencode.json"),
]

FALLBACK_PATHS = [
    os.path.join(CONFIG_DIR, "model-fallback.json"),
    os.path.join(ROOT_DIR, "configs", "model-fallback.json"),
    os.path.join(ROOT_DIR, "model-fallback.json"),
]

BYOK_PATH = os.path.join(CONFIG_DIR, "byok-config.json")
GLOBAL_DAT = os.path.join(DESKTOP_DIR, "opencode.global.dat")

# Provider metadata and model sets
PROVIDERS_INFO = {
    "kilo": {
        "name": "Kilo Code",
        "desc": "kilo.ai zero-config free models gateway",
        "primary_model": "kilo/kilo-auto/free",
        "small_model": "kilo/poolside/laguna-xs-2.1:free",
        "coder_model": "kilo/cohere/north-mini-code:free",
        "plan_model": "kilo/nvidia/nemotron-3-ultra-550b-a55b:free",
        "explore_model": "kilo/inclusionai/ling-3.0-flash-fin:free",
        "qa_model": "kilo/nvidia/nemotron-3.5-lightning:free",
        "linter_model": "kilo/poolside/laguna-xs-2.1:free",
        "verifier_model": "kilo/nvidia/nemotron-3-ultra-550b-a55b:free",
        "reviewer_model": "kilo/nvidia/nemotron-3-super-120b-a12b:free",
        "fallback_models": [
            "kilo/kilo-auto/free",
            "kilo/poolside/laguna-xs-2.1:free",
            "kilo/nex-agi/nex-n2.5-pro:free",
            "kilo/nvidia/nemotron-3.5-lightning:free",
            "kilo/nvidia/nemotron-3-ultra-550b-a55b:free",
            "kilo/cohere/north-mini-code:free"
        ]
    },
    "openrouter": {
        "name": "OpenRouter",
        "desc": "openrouter.ai free endpoints & high-context reasoning",
        "primary_model": "openrouter/google/gemma-4-31b-it:free",
        "small_model": "openrouter/google/gemma-4-26b-a4b-it:free",
        "coder_model": "openrouter/cohere/north-mini-code:free",
        "plan_model": "openrouter/nvidia/nemotron-3-ultra-550b-a55b:free",
        "explore_model": "openrouter/inclusionai/ling-3.0-flash-fin:free",
        "qa_model": "openrouter/nvidia/nemotron-3.5-lightning:free",
        "linter_model": "openrouter/poolside/laguna-xs-2.1:free",
        "verifier_model": "openrouter/google/gemma-4-31b-it:free",
        "reviewer_model": "openrouter/nvidia/nemotron-3-super-120b-a12b:free",
        "fallback_models": [
            "openrouter/google/gemma-4-31b-it:free",
            "openrouter/google/gemma-4-26b-a4b-it:free",
            "openrouter/openrouter/free",
            "openrouter/nvidia/nemotron-3.5-lightning:free",
            "openrouter/poolside/laguna-xs-2.1:free",
            "openrouter/inclusionai/ling-3.0-flash-fin:free",
            "openrouter/cohere/north-mini-code:free"
        ]
    },
    "opencode": {
        "name": "OpenCode Built-In",
        "desc": "opencode local high-speed free models",
        "primary_model": "opencode/mimo-v2.5-free",
        "small_model": "opencode/big-pickle",
        "coder_model": "opencode/mimo-v2.5-free",
        "plan_model": "opencode/nemotron-3-ultra-free",
        "explore_model": "opencode/ling-3.0-flash-fin-free",
        "qa_model": "opencode/nemotron-3.5-lightning-free",
        "linter_model": "opencode/ling-3.0-flash-fin-free",
        "verifier_model": "opencode/mimo-v2.5-free",
        "reviewer_model": "opencode/mimo-v2.5-free",
        "fallback_models": [
            "opencode/mimo-v2.5-free",
            "opencode/ling-3.0-flash-fin-free",
            "opencode/big-pickle",
            "opencode/nemotron-3.5-lightning-free",
            "opencode/nemotron-3-ultra-free"
        ]
    },
    "gemini": {
        "name": "Google Gemini",
        "desc": "Google AI Studio 1M+ context free key",
        "primary_model": "gemini/gemini-3.6-flash",
        "small_model": "gemini/gemini-3.1-flash-lite",
        "coder_model": "gemini/gemini-3.6-flash",
        "plan_model": "gemini/gemini-3.6-flash",
        "explore_model": "gemini/gemini-3.6-flash",
        "qa_model": "gemini/gemini-3.6-flash",
        "linter_model": "gemini/gemini-3.1-flash-lite",
        "verifier_model": "gemini/gemini-3.6-flash",
        "reviewer_model": "gemini/gemini-3.6-flash",
        "fallback_models": [
            "gemini/gemini-3.6-flash",
            "gemini/gemini-3.1-flash-lite",
            "gemini/gemini-3.5-flash-lite",
            "gemini/gemini-3-flash-preview"
        ]
    },
    "mistral": {
        "name": "Mistral Codestral",
        "desc": "High-accuracy code generation & FIM",
        "primary_model": "mistral/codestral-latest",
        "small_model": "mistral/codestral-2508",
        "coder_model": "mistral/codestral-latest",
        "plan_model": "mistral/codestral-latest",
        "explore_model": "mistral/codestral-2508",
        "qa_model": "mistral/codestral-latest",
        "linter_model": "mistral/codestral-2508",
        "verifier_model": "mistral/codestral-latest",
        "reviewer_model": "mistral/codestral-latest",
        "fallback_models": [
            "mistral/codestral-latest",
            "mistral/codestral-2508"
        ]
    },
    "groq": {
        "name": "Groq LPU",
        "desc": "Ultra-low latency hardware acceleration",
        "primary_model": "groq/openai/gpt-oss-120b",
        "small_model": "groq/compound-mini",
        "coder_model": "groq/openai/gpt-oss-120b",
        "plan_model": "groq/openai/gpt-oss-120b",
        "explore_model": "groq/compound-mini",
        "qa_model": "groq/openai/gpt-oss-20b",
        "linter_model": "groq/compound-mini",
        "verifier_model": "groq/openai/gpt-oss-120b",
        "reviewer_model": "groq/openai/gpt-oss-120b",
        "fallback_models": [
            "groq/openai/gpt-oss-120b",
            "groq/compound-mini",
            "groq/openai/gpt-oss-20b"
        ]
    }
}

# Standard OpenRouter full provider definition for opencode.jsonc
OPENROUTER_PROVIDER_CONFIG = {
    "npm": "@ai-sdk/openai-compatible",
    "name": "OpenRouter (free & deals)",
    "options": {
        "baseURL": "https://openrouter.ai/api/v1",
        "apiKey": "{env:OPENROUTER_API_KEY}"
    },
    "whitelist": [
        "google/gemma-4-31b-it:free",
        "google/gemma-4-26b-a4b-it:free",
        "stealth/union-alpha",
        "inclusionai/ling-3.0-flash-vl:free",
        "nex-agi/nex-n2.5-mini:free",
        "nex-agi/nex-n2.5-pro:free",
        "inclusionai/ling-3.0-flash-sante:free",
        "inclusionai/ling-3.0-flash-fin:free",
        "dots-studio/dots-3-note-preview:free",
        "liquid/lfm-2.5-2.6b:free",
        "nvidia/nemotron-3.5-lightning:free",
        "thinkingmachines/inkling-small:free",
        "poolside/laguna-s-2.1:free",
        "thinkingmachines/inkling:free",
        "poolside/laguna-xs-2.1:free",
        "cohere/north-mini-code:free",
        "z-ai/glm-5.2:free",
        "nvidia/nemotron-3.5-content-safety:free",
        "nvidia/nemotron-3-ultra-550b-a55b:free",
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        "nvidia/nemotron-3-super-120b-a12b:free",
        "openrouter/free"
    ],
    "models": {
        "google/gemma-4-31b-it:free": {"name": "Google Gemma 4 31B (free)"},
        "google/gemma-4-26b-a4b-it:free": {"name": "Google Gemma 4 26B (free)"},
        "stealth/union-alpha": {"name": "Union Alpha (free)"},
        "inclusionai/ling-3.0-flash-vl:free": {"name": "Ling 3.0 Flash VL (free)"},
        "nex-agi/nex-n2.5-mini:free": {"name": "Nex-N2.5-Mini (free)"},
        "nex-agi/nex-n2.5-pro:free": {"name": "Nex-N2.5-Pro (free)"},
        "dots-studio/dots-3-note-preview:free": {"name": "Dots3-Note Preview (free)"},
        "liquid/lfm-2.5-2.6b:free": {"name": "Liquid LFM 2.5 (free)"},
        "nvidia/nemotron-3.5-lightning:free": {"name": "Nemotron 3.5 Lightning (free)"},
        "poolside/laguna-s-2.1:free": {"name": "Poolside Laguna S 2.1 (free)"},
        "poolside/laguna-xs-2.1:free": {"name": "Poolside Laguna XS 2.1 (free)"},
        "cohere/north-mini-code:free": {"name": "Cohere North Mini Code (free)"},
        "thinkingmachines/inkling:free": {"name": "ThinkingMachines Inkling (free)"},
        "openrouter/free": {"name": "OpenRouter Auto Free"}
    }
}


def check_provider_api_key(prov: str) -> Tuple[bool, Optional[str]]:
    prov_keys = {
        'openrouter': ['OPENROUTER_API_KEY'],
        'groq': ['GROQ_API_KEY'],
        'gemini': ['GEMINI_API_KEY', 'GOOGLE_API_KEY'],
        'google': ['GEMINI_API_KEY', 'GOOGLE_API_KEY'],
        'mistral': ['MISTRAL_API_KEY'],
        'anthropic': ['ANTHROPIC_API_KEY'],
        'openai': ['OPENAI_API_KEY'],
        'deepseek': ['DEEPSEEK_API_KEY'],
        'cerebras': ['CEREBRAS_API_KEY'],
        'together': ['TOGETHER_API_KEY'],
        'xai': ['XAI_API_KEY'],
        'cohere': ['COHERE_API_KEY'],
        'perplexity': ['PERPLEXITY_API_KEY'],
        'kilo': [],
        'opencode': [],
        'lmstudio': [],
        'ollama': [],
        'local': [],
    }
    reqs = prov_keys.get(prov.lower(), [f"{prov.upper()}_API_KEY"])
    if not reqs:
        return True, None
    for k in reqs:
        if os.environ.get(k) and len(os.environ[k].strip()) > 5:
            return True, k
    env_p = os.path.join(HOME, ".config", "opencode", ".env")
    if os.path.exists(env_p):
        try:
            with open(env_p, "r", encoding="utf-8-sig", errors="replace") as ef:
                for line in ef:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        k = k.strip()
                        if k.startswith("export "):
                            k = k[7:].strip()
                        v = v.strip().strip('"\'')
                        if k in reqs and len(v) > 5 and not v.startswith(("your_", "sk-xxx", "dummy")):
                            os.environ[k] = v
                            return True, k
        except Exception:
            pass
    return False, reqs[0]


def read_json_flexible(path: str) -> Optional[dict]:
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        # Remove trailing commas and comments for JSON parsing
        lines = []
        for line in text.splitlines():
            s = line.strip()
            if s.startswith("//") or s.startswith("#"):
                continue
            lines.append(line)
        cleaned = "\n".join(lines)
        cleaned = re.sub(r",\s*([\]}])", r"\1", cleaned)
        return json.loads(cleaned)
    except Exception:
        return None


def get_current_state() -> dict:
    """Reads current primary, secondary, and visibility status."""
    primary = "kilo"
    secondary = "openrouter"
    enabled_providers = []
    disabled_providers = []

    primary_cfg = os.path.join(CONFIG_DIR, "opencode.jsonc")
    if not os.path.exists(primary_cfg):
        primary_cfg = os.path.join(ROOT_DIR, "configs", "opencode.jsonc")

    if os.path.exists(primary_cfg):
        data = read_json_flexible(primary_cfg)
        if data:
            model = data.get("model", "")
            if "/" in model:
                primary = model.split("/")[0]
            enabled_providers = data.get("enabled_providers", [])
            disabled_providers = data.get("disabled_providers", [])

            # Secondary is deduced from small_model or build agents
            small_model = data.get("small_model", "")
            if "/" in small_model:
                sec_cand = small_model.split("/")[0]
                if sec_cand != primary:
                    secondary = sec_cand

    # Check desktop IDE dat visibility
    desktop_visibility = {}
    if os.path.exists(GLOBAL_DAT):
        try:
            gdat = json.load(open(GLOBAL_DAT, "r", encoding="utf-8"))
            if "model" in gdat and isinstance(gdat["model"], str):
                minner = json.loads(gdat["model"])
                for item in minner.get("user", []):
                    pid = item.get("providerID")
                    v = item.get("visibility", "show")
                    if pid:
                        if pid not in desktop_visibility:
                            desktop_visibility[pid] = {"show": 0, "hide": 0}
                        desktop_visibility[pid][v] = desktop_visibility[pid].get(v, 0) + 1
        except Exception:
            pass

    return {
        "primary": primary,
        "secondary": secondary,
        "enabled_providers": enabled_providers,
        "disabled_providers": disabled_providers,
        "desktop_visibility": desktop_visibility,
    }


def update_jsonc_preserving_comments(
    path: str,
    primary_prov: str,
    secondary_prov: str,
    enabled_providers: List[str],
    disabled_providers: List[str]
) -> bool:
    """Safely updates opencode.jsonc while keeping all comments and formatting."""
    if not os.path.exists(path):
        return False

    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read()

        p_info = PROVIDERS_INFO.get(primary_prov, PROVIDERS_INFO["kilo"])
        s_info = PROVIDERS_INFO.get(secondary_prov, PROVIDERS_INFO["openrouter"])

        primary_model = p_info["primary_model"]
        small_model = s_info["small_model"] if secondary_prov != primary_prov else p_info["small_model"]

        # 1. Update top-level "model" (exactly 2 leading spaces)
        content = re.sub(
            r'^(  "model"\s*:\s*)"[^"]+"',
            r'\g<1>"' + primary_model + '"',
            content,
            flags=re.MULTILINE
        )

        # 2. Update top-level "small_model" (exactly 2 leading spaces)
        content = re.sub(
            r'^(  "small_model"\s*:\s*)"[^"]+"',
            r'\g<1>"' + small_model + '"',
            content,
            flags=re.MULTILINE
        )

        # 3. Update enabled_providers array
        enabled_str = '[\n' + ',\n'.join(f'    "{p}"' for p in enabled_providers) + '\n  ]'
        content = re.sub(
            r'"enabled_providers"\s*:\s*\[[^\]]*\]',
            f'"enabled_providers": {enabled_str}',
            content
        )

        # 4. Update disabled_providers array
        disabled_str = '[\n' + ',\n'.join(f'    "{p}"' for p in disabled_providers) + '\n  ]'
        content = re.sub(
            r'"disabled_providers"\s*:\s*\[[^\]]*\]',
            f'"disabled_providers": {disabled_str}',
            content
        )

        # 5. Ensure openrouter block exists under provider with npm sdk and options
        or_block_json = json.dumps(OPENROUTER_PROVIDER_CONFIG, indent=2)
        or_indented = "\n".join(["    " + l if i > 0 else '    "openrouter": ' + l for i, l in enumerate(or_block_json.splitlines())])

        if '"openrouter":' not in content:
            # Insert before lmstudio or before the end of provider
            if '"lmstudio":' in content:
                content = content.replace('"lmstudio":', or_indented + ',\n    "lmstudio":')
            elif '"disabled_providers"' in content:
                content = re.sub(r'(\n  \}\s*,\s*\n  "disabled_providers")', r',\n' + or_indented + r'\1', content)
        else:
            # Replace existing openrouter block with full definition
            content = re.sub(
                r'//\s*"openrouter"\s*:\s*\{[^\}]*"whitelist"\s*:\s*\[[^\]]*\]\s*\}',
                or_indented,
                content
            )
            content = re.sub(
                r'"openrouter"\s*:\s*\{[^\}]*"whitelist"\s*:\s*\[[^\]]*\]\s*\}',
                or_indented,
                content
            )

        # 6. Update agent models with Primary & Secondary specialized balance
        agent_mapping = {
            "build": p_info["primary_model"],
            "explore": p_info["explore_model"],
            "plan": p_info["plan_model"],
            "orchestrator": p_info["primary_model"],
            "coder": p_info["coder_model"],
            # Secondary handles verification/lint/support for load balancing
            "linter": s_info["linter_model"],
            "qa": s_info["qa_model"],
            "tester": s_info["linter_model"],
            "verifier": s_info["verifier_model"],
            "reviewer": s_info["reviewer_model"],
            "docs": s_info.get("primary_model", p_info["primary_model"]),
        }

        for agent, mod in agent_mapping.items():
            pattern = rf'("{agent}"\s*:\s*\{{[^}}]*?)^\s*"model"\s*:\s*"[^"]+"'
            content = re.sub(pattern, rf'\g<1>      "model": "{mod}"', content, flags=re.MULTILINE | re.DOTALL)

        with open(path, "w", encoding="utf-8") as f:
            f.write(content)

        return True
    except Exception as e:
        print(f"{RED}[!] Error updating {os.path.basename(path)}: {e}{RESET}")
        return False


def update_json_file(
    path: str,
    primary_prov: str,
    secondary_prov: str,
    enabled_providers: List[str],
    disabled_providers: List[str]
) -> bool:
    """Updates pure JSON configuration files."""
    if not os.path.exists(path):
        return False
    try:
        data = read_json_flexible(path)
        if not data:
            return False

        p_info = PROVIDERS_INFO.get(primary_prov, PROVIDERS_INFO["kilo"])
        s_info = PROVIDERS_INFO.get(secondary_prov, PROVIDERS_INFO["openrouter"])

        data["model"] = p_info["primary_model"]
        data["small_model"] = s_info["small_model"] if secondary_prov != primary_prov else p_info["small_model"]
        data["enabled_providers"] = enabled_providers
        data["disabled_providers"] = disabled_providers

        # Ensure provider block
        if "provider" not in data:
            data["provider"] = {}

        if "openrouter" in enabled_providers:
            data["provider"]["openrouter"] = OPENROUTER_PROVIDER_CONFIG
        elif "openrouter" in data["provider"] and "openrouter" in disabled_providers:
            # Still keep provider definition so IDE recognizes it, but disabled in array
            data["provider"]["openrouter"] = OPENROUTER_PROVIDER_CONFIG

        if "agent" in data:
            data["agent"]["build"]["model"] = p_info["primary_model"]
            if "explore" in data["agent"]:
                data["agent"]["explore"]["model"] = p_info["explore_model"]
            if "plan" in data["agent"]:
                data["agent"]["plan"]["model"] = p_info["plan_model"]
            if "orchestrator" in data["agent"]:
                data["agent"]["orchestrator"]["model"] = p_info["primary_model"]
            if "coder" in data["agent"]:
                data["agent"]["coder"]["model"] = p_info["coder_model"]
            if "linter" in data["agent"]:
                data["agent"]["linter"]["model"] = s_info["linter_model"]
            if "qa" in data["agent"]:
                data["agent"]["qa"]["model"] = s_info["qa_model"]
            if "verifier" in data["agent"]:
                data["agent"]["verifier"]["model"] = s_info["verifier_model"]
            if "reviewer" in data["agent"]:
                data["agent"]["reviewer"]["model"] = s_info["reviewer_model"]

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        return True
    except Exception as e:
        print(f"{RED}[!] Error updating {os.path.basename(path)}: {e}{RESET}")
        return False


def update_fallback_chains(primary_prov: str, secondary_prov: str) -> None:
    """Combines Primary, Secondary, and Tertiary safety nets in model-fallback.json."""
    p_info = PROVIDERS_INFO.get(primary_prov, PROVIDERS_INFO["kilo"])
    s_info = PROVIDERS_INFO.get(secondary_prov, PROVIDERS_INFO["openrouter"])

    chain = []
    # 1. Primary models first
    for m in p_info["fallback_models"]:
        if m not in chain:
            chain.append(m)

    # 2. Secondary models next
    for m in s_info["fallback_models"]:
        if m not in chain:
            chain.append(m)

    # 3. Universal safety nets (Mistral Codestral, Gemini Flash, OpenCode Pickle)
    safety = [
        "mistral/codestral-latest",
        "gemini/gemini-3.6-flash",
        "opencode/big-pickle",
        "kilo/kilo-auto/free",
        "openrouter/google/gemma-4-31b-it:free"
    ]
    for m in safety:
        if m not in chain:
            chain.append(m)

    for p in FALLBACK_PATHS:
        if not os.path.exists(p):
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                fb_data = json.load(f)
            fb_data["fallbackModels"] = chain
            with open(p, "w", encoding="utf-8") as f:
                json.dump(fb_data, f, indent=2)
            print(f"  {GREEN}[✓]{RESET} Synced fallback chain -> {os.path.basename(p)}")
        except Exception as e:
            print(f"  {YELLOW}[!] Fallback sync warning ({os.path.basename(p)}): {e}{RESET}")


def update_sqlite_sessions(full_model: str) -> None:
    """Updates active/recent sessions in opencode.db so the IDE pill syncs immediately."""
    if not os.path.exists(DB_PATH):
        return

    parts = full_model.split("/", 1)
    provider_id = parts[0]
    raw_model_id = parts[1] if len(parts) > 1 else parts[0]

    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        new_model_json = json.dumps({
            "id": raw_model_id,
            "providerID": provider_id,
            "variant": "default"
        })
        cutoff_ms = int((time.time() - (48 * 3600)) * 1000)
        c.execute(
            "UPDATE session SET model = ? WHERE time_updated > ?",
            (new_model_json, cutoff_ms)
        )
        updated = c.rowcount
        conn.commit()
        conn.close()
        print(f"  {GREEN}[✓]{RESET} Synced {updated} active sessions in opencode.db")
    except Exception as e:
        print(f"  {YELLOW}[!] SQLite session sync note: {e}{RESET}")


def update_desktop_ide_preferences(full_model: str) -> None:
    """Updates desktop workspace .dat model-selection so IDE pill syncs without restart."""
    if not os.path.exists(DESKTOP_DIR):
        return

    parts = full_model.split("/", 1)
    provider_id = parts[0]
    raw_model_id = parts[1] if len(parts) > 1 else parts[0]

    count = 0
    for dat_file in glob.glob(os.path.join(DESKTOP_DIR, "*.dat")):
        try:
            with open(dat_file, "r", encoding="utf-8-sig") as f:
                content = f.read()

            if "model-selection" in content or '"modelID":' in content:
                content = re.sub(r'\\"modelID\\":\\"[^"\\]+\\"', f'\\"modelID\\":\\"{raw_model_id}\\"', content)
                content = re.sub(r'\\"providerID\\":\\"[^"\\]+\\"', f'\\"providerID\\":\\"{provider_id}\\"', content)
                content = re.sub(r'"modelID":"[^"]+"', f'"modelID":"{raw_model_id}"', content)
                content = re.sub(r'"providerID":"[^"]+"', f'"providerID":"{provider_id}"', content)

                with open(dat_file, "w", encoding="utf-8") as f:
                    f.write(content)
                count += 1
        except Exception:
            pass

    if count > 0:
        print(f"  {GREEN}[✓]{RESET} Synced model selection in {count} desktop IDE state files")


def sync_ide_visibility_in_global_dat(
    provider_visibility: Dict[str, str],
    hide_paid_models: bool = False
) -> int:
    """
    Directly updates opencode.global.dat in ai.opencode.desktop.
    Sets 'visibility': 'show' or 'hide' for each model in the IDE 'Manage models' catalog.
    """
    if not os.path.exists(GLOBAL_DAT):
        return 0

    try:
        with open(GLOBAL_DAT, "r", encoding="utf-8") as f:
            gdat = json.load(f)

        if "model" not in gdat or not isinstance(gdat["model"], str):
            return 0

        minner = json.loads(gdat["model"])
        user_list = minner.get("user", [])
        changed_count = 0

        for item in user_list:
            pid = item.get("providerID", "")
            mid = item.get("modelID", "")

            # 1. Provider-level visibility override
            if pid in provider_visibility:
                target_vis = provider_visibility[pid]
                if item.get("visibility") != target_vis:
                    item["visibility"] = target_vis
                    changed_count += 1

            # 2. Filter paid models if requested
            if hide_paid_models and pid == "openrouter":
                is_free = mid.endswith(":free") or mid in [
                    "stealth/union-alpha", "google/lyria-3-pro-preview",
                    "google/lyria-3-clip-preview", "openrouter/free"
                ]
                if not is_free and item.get("visibility") == "show":
                    item["visibility"] = "hide"
                    changed_count += 1

        minner["user"] = user_list
        gdat["model"] = json.dumps(minner)

        with open(GLOBAL_DAT, "w", encoding="utf-8") as f:
            json.dump(gdat, f, indent=2)

        print(f"  {GREEN}[✓]{RESET} Updated {changed_count} model visibility flags in OpenCode Desktop IDE")
        return changed_count
    except Exception as e:
        print(f"  {RED}[!] Error updating global.dat: {e}{RESET}")
        return 0


def apply_configuration(
    primary: str,
    secondary: str,
    show_providers: Optional[List[str]] = None,
    hide_providers: Optional[List[str]] = None,
    hide_paid: bool = False
) -> None:
    """Executes full multi-file synchronization."""
    print(f"\n{CYAN}{'═' * 65}{RESET}")
    print(f"  {BOLD}🚀 SYNCHRONIZING OPENCODE FLEET CONFIGURATION{RESET}")
    print(f"{CYAN}{'═' * 65}{RESET}\n")

    p_info = PROVIDERS_INFO.get(primary, PROVIDERS_INFO["kilo"])
    s_info = PROVIDERS_INFO.get(secondary, PROVIDERS_INFO["openrouter"])

    p_has_key, p_key_name = check_provider_api_key(primary)
    s_has_key, s_key_name = check_provider_api_key(secondary)

    p_tag = f"{GREEN}[KEY OK]{RESET}" if (p_has_key and p_key_name) else (f"{GREEN}[ZERO-CONFIG]{RESET}" if p_has_key else f"{RED}{BOLD}[⚠️ NO API KEY: {p_key_name}]{RESET}")
    s_tag = f"{GREEN}[KEY OK]{RESET}" if (s_has_key and s_key_name) else (f"{GREEN}[ZERO-CONFIG]{RESET}" if s_has_key else f"{RED}{BOLD}[⚠️ NO API KEY: {s_key_name}]{RESET}")

    print(f"  {WHITE}Primary Provider  :{RESET} {GREEN}{p_info['name']}{RESET} ({p_info['primary_model']}) {p_tag}")
    print(f"  {WHITE}Secondary Provider:{RESET} {CYAN}{s_info['name']}{RESET} ({s_info['small_model']}) {s_tag}")

    if not p_has_key:
        print(f"  {RED}{BOLD}⚠️  WARNING: No API key found for {p_info['name']} ({p_key_name})! Requests will fail until added to .env{RESET}")
    if not s_has_key:
        print(f"  {RED}{BOLD}⚠️  WARNING: No API key found for {s_info['name']} ({s_key_name})! Requests will fail until added to .env{RESET}")

    # Determine enabled & disabled providers
    state = get_current_state()
    enabled = set(state["enabled_providers"])
    disabled = set(state["disabled_providers"])

    # Ensure Primary & Secondary are active
    enabled.add(primary)
    disabled.discard(primary)
    enabled.add(secondary)
    disabled.discard(secondary)

    # Apply manual show/hide overrides
    if show_providers:
        for p in show_providers:
            enabled.add(p)
            disabled.discard(p)
    if hide_providers:
        for p in hide_providers:
            if p not in (primary, secondary):  # Protect active primary/secondary
                disabled.add(p)
                enabled.discard(p)

    enabled_list = sorted(list(enabled))
    disabled_list = sorted(list(disabled))

    print(f"  {WHITE}Active in IDE     :{RESET} {', '.join(enabled_list)}")
    if disabled_list:
        print(f"  {WHITE}Hidden from IDE   :{RESET} {', '.join(disabled_list)}")

    # 1. Update config files (jsonc & json)
    print(f"\n{YELLOW}[1/4] Updating OpenCode core configurations...{RESET}")
    for p in CONFIG_PATHS:
        if os.path.exists(p):
            if p.endswith(".jsonc"):
                ok = update_jsonc_preserving_comments(p, primary, secondary, enabled_list, disabled_list)
            else:
                ok = update_json_file(p, primary, secondary, enabled_list, disabled_list)
            if ok:
                print(f"  {GREEN}[✓]{RESET} Updated {os.path.basename(p)}")

    # 2. Update fallback chains
    print(f"\n{YELLOW}[2/4] Updating smart fallback chains...{RESET}")
    update_fallback_chains(primary, secondary)

    # 3. Update active SQLite sessions
    print(f"\n{YELLOW}[3/4] Syncing SQLite runtime database...{RESET}")
    update_sqlite_sessions(p_info["primary_model"])

    # 4. Sync desktop IDE model visibility & preferences
    print(f"\n{YELLOW}[4/4] Syncing OpenCode Desktop IDE...{RESET}")
    update_desktop_ide_preferences(p_info["primary_model"])

    # Update IDE visibility in opencode.global.dat
    prov_vis = {}
    for p in enabled_list:
        prov_vis[p] = "show"
    for p in disabled_list:
        prov_vis[p] = "hide"
    sync_ide_visibility_in_global_dat(prov_vis, hide_paid_models=hide_paid)

    print(f"\n{GREEN}{'═' * 65}{RESET}")
    print(f"  {BOLD}✓ ALL SETTINGS SYNCED ACROSS CLI AND OPENCODE IDE!{RESET}")
    print(f"  Primary   : {p_info['primary_model']}")
    print(f"  Secondary : {s_info['small_model']}")
    print(f"  (OpenCode IDE model dropdown updated with OpenRouter and all selected providers)")
    print(f"{GREEN}{'═' * 65}{RESET}\n")


def interactive_show_hide_menu() -> None:
    """Interactive submenu to toggle visibility of models and providers in OpenCode IDE."""
    while True:
        state = get_current_state()
        enabled = set(state["enabled_providers"])
        disabled = set(state["disabled_providers"])

        print(f"{CLEAR}")
        print(f"  {CYAN}{'═' * 65}{RESET}")
        print(f"   {BOLD}👁️  OPENCODE IDE // MODEL & PROVIDER VISIBILITY MANAGER{RESET}")
        print(f"  {CYAN}{'═' * 65}{RESET}\n")
        print(f"   Control which providers and models appear in your OpenCode IDE")
        print(f"   model dropdown and 'Manage models' dialog.\n")

        providers = ["openrouter", "kilo", "gemini", "opencode", "mistral", "groq"]
        for idx, p in enumerate(providers, 1):
            name = PROVIDERS_INFO[p]["name"]
            is_on = p in enabled and p not in disabled
            badge = f"{GREEN}[VISIBLE IN IDE]{RESET}" if is_on else f"{GRAY}[HIDDEN]{RESET}"
            print(f"   [{idx}] {name:<22} {badge}")

        print(f"\n   {CYAN}{'─' * 55}{RESET}")
        print(f"   [F] Filter IDE: Show ONLY Free Models (Hide all paid OpenRouter)")
        print(f"   [A] Show ALL Configured Providers in IDE")
        print(f"   [0] Back to Switcher Menu")
        print(f"  {CYAN}{'═' * 65}{RESET}\n")

        choice = input("  Select option: ").strip().upper()
        if choice == "0":
            break
        elif choice in [str(i) for i in range(1, len(providers) + 1)]:
            idx = int(choice) - 1
            target = providers[idx]
            is_currently_on = target in enabled and target not in disabled

            if is_currently_on:
                # Toggle off
                print(f"\n  Hiding {PROVIDERS_INFO[target]['name']} from IDE...")
                apply_configuration(
                    state["primary"],
                    state["secondary"],
                    hide_providers=[target]
                )
            else:
                # Toggle on
                print(f"\n  Enabling {PROVIDERS_INFO[target]['name']} in IDE...")
                apply_configuration(
                    state["primary"],
                    state["secondary"],
                    show_providers=[target]
                )
            input("  Press Enter to continue...")
        elif choice == "F":
            print("\n  Filtering OpenCode IDE to free models only...")
            apply_configuration(
                state["primary"],
                state["secondary"],
                show_providers=["openrouter", "kilo", "opencode", "gemini", "mistral"],
                hide_paid=True
            )
            input("  Press Enter to continue...")
        elif choice == "A":
            print("\n  Enabling all providers in OpenCode IDE...")
            apply_configuration(
                state["primary"],
                state["secondary"],
                show_providers=["openrouter", "kilo", "opencode", "gemini", "mistral", "groq"]
            )
            input("  Press Enter to continue...")


def get_circuit_breaker_status() -> Tuple[dict, dict]:
    """Retrieve currently quarantined models and providers."""
    cb_path = os.path.join(CONFIG_DIR, "circuit-breaker.json")
    if os.path.exists(cb_path):
        try:
            with open(cb_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("quarantined_models", {}), data.get("quarantined_providers", {})
        except Exception:
            pass
    return {}, {}


def interactive_primary_secondary_wizard() -> None:
    """Step-by-step wizard to choose Primary and Secondary providers."""
    q_mods, q_provs = get_circuit_breaker_status()
    print(f"\n  {CYAN}{'═' * 65}{RESET}")
    print(f"   {BOLD}🎯 PRIMARY & SECONDARY PROVIDER SETUP WIZARD{RESET}")
    print(f"  {CYAN}{'═' * 65}{RESET}\n")

    prov_keys = ["kilo", "openrouter", "opencode", "gemini", "mistral", "groq"]

    print(f"  {BOLD}Step 1 of 2: Select PRIMARY Provider{RESET}")
    print(f"  (Powers lead agent @build, core @coder, @plan, and default model)\n")
    for i, p in enumerate(prov_keys, 1):
        info = PROVIDERS_INFO[p]
        has_k, kn = check_provider_api_key(p)
        if p.lower() in q_provs:
            k_tag = f" {RED}{BOLD}[🚫 QUARANTINED - 5+ ERRORS]{RESET}"
        elif has_k and kn:
            k_tag = f" {GREEN}[KEY OK]{RESET}"
        elif has_k:
            k_tag = f" {GREEN}[ZERO-CONFIG]{RESET}"
        else:
            k_tag = f" {RED}{BOLD}[⚠️ NO KEY: {kn}]{RESET}"
        print(f"   [{i}] {info['name']:<18} - {info['desc']}{k_tag}")
    print(f"   [0] Cancel\n")

    p_choice = input(f"  Choose Primary [1-{len(prov_keys)}]: ").strip()
    if p_choice == "0" or not p_choice.isdigit() or int(p_choice) not in range(1, len(prov_keys) + 1):
        print("  Cancelled.")
        return

    primary_selected = prov_keys[int(p_choice) - 1]

    print(f"\n  {BOLD}Step 2 of 2: Select SECONDARY Provider{RESET}")
    print(f"  (Powers fast @small_model, verification @qa, @linter, @verifier, & 1st fallback)\n")
    for i, p in enumerate(prov_keys, 1):
        info = PROVIDERS_INFO[p]
        has_k, kn = check_provider_api_key(p)
        if p.lower() in q_provs:
            k_tag = f" {RED}{BOLD}[🚫 QUARANTINED - 5+ ERRORS]{RESET}"
        elif has_k and kn:
            k_tag = f" {GREEN}[KEY OK]{RESET}"
        elif has_k:
            k_tag = f" {GREEN}[ZERO-CONFIG]{RESET}"
        else:
            k_tag = f" {RED}{BOLD}[⚠️ NO KEY: {kn}]{RESET}"
        tag = f" {YELLOW}(Current Primary){RESET}" if p == primary_selected else ""
        print(f"   [{i}] {info['name']:<18} - {info['desc']}{tag}{k_tag}")
    print(f"   [0] Cancel\n")

    s_choice = input(f"  Choose Secondary [1-{len(prov_keys)}]: ").strip()
    if s_choice == "0" or not s_choice.isdigit() or int(s_choice) not in range(1, len(prov_keys) + 1):
        print("  Cancelled.")
        return

    secondary_selected = prov_keys[int(s_choice) - 1]

    apply_configuration(primary_selected, secondary_selected)
    input("  Press Enter to return...")


def interactive_main_menu() -> None:
    """Main interactive switcher menu."""
    while True:
        state = get_current_state()
        p = state["primary"]
        s = state["secondary"]
        p_name = PROVIDERS_INFO.get(p, {}).get("name", p)
        s_name = PROVIDERS_INFO.get(s, {}).get("name", s)
        q_mods, q_provs = get_circuit_breaker_status()

        print(f"{CLEAR}")
        print(f"  {CYAN}{'═' * 65}{RESET}")
        print(f"   {BOLD}⚡ OPENCODE FLEET COMMANDER // PROVIDER SWITCHER{RESET}")
        print(f"  {CYAN}{'═' * 65}{RESET}\n")
        print(f"   Current Primary   : {GREEN}{BOLD}{p_name}{RESET} ({PROVIDERS_INFO.get(p, {}).get('primary_model', '-')})")
        print(f"   Current Secondary : {CYAN}{BOLD}{s_name}{RESET} ({PROVIDERS_INFO.get(s, {}).get('small_model', '-')})")
        print(f"   IDE Visibility    : {', '.join(state['enabled_providers'])}\n")
        
        if q_provs or q_mods:
            q_items = [f"{k.upper()}" for k in q_provs.keys()] + [f"{m.split('/')[-1]}" for m in q_mods.keys()]
            print(f"   {RED}{BOLD}⚠️  CIRCUIT BREAKER ACTIVE: {len(q_provs)} providers, {len(q_mods)} models quarantined{RESET}")
            print(f"   {YELLOW}   Quarantined: {', '.join(q_items[:5])}{RESET}\n")

        def p_badge(prov_key):
            if prov_key.lower() in q_provs:
                return f" {RED}{BOLD}[🚫 QUARANTINED]{RESET}"
            return ""

        print(f"  {CYAN}{'─' * 65}{RESET}")
        print(f"   {BOLD}QUICK PRIMARY SWITCH:{RESET}")
        print(f"   [1] Kilo Code       - kilo-auto/free zero-config{p_badge('kilo')}")
        print(f"   [2] OpenRouter      - gemma-4-31b-it:free & all free models{p_badge('openrouter')}")
        print(f"   [3] OpenCode        - mimo-v2.5-free & big-pickle local{p_badge('opencode')}")
        print(f"   [4] Google Gemini   - gemini-3.6-flash 1M context{p_badge('gemini')}")
        print(f"\n   {BOLD}ADVANCED DUAL SETUP & IDE VISIBILITY:{RESET}")
        print(f"   [D] Dual Setup      - Configure Primary + Secondary pair")
        print(f"   [H] IDE Visibility  - Show / Hide models & providers in IDE dropdown")
        print(f"   [R] Refresh / Sync  - Re-sync all configurations and IDE files")
        if q_provs or q_mods:
            print(f"   [U] Unquarantine    - {GREEN}Reset circuit breakers & clear quarantined models{RESET}")
        print(f"   [0] Exit")
        print(f"  {CYAN}{'═' * 65}{RESET}\n")

        prompt_str = "  Select option [0-4, D, H, R" + (", U" if (q_provs or q_mods) else "") + "]: "
        choice = input(prompt_str).strip().upper()

        if choice == "0":
            break
        elif choice == "1":
            sec = "openrouter" if p != "openrouter" else "gemini"
            apply_configuration("kilo", sec)
            input("  Press Enter to continue...")
        elif choice == "2":
            sec = "kilo" if p != "kilo" else "gemini"
            apply_configuration("openrouter", sec)
            input("  Press Enter to continue...")
        elif choice == "3":
            sec = "openrouter"
            apply_configuration("opencode", sec)
            input("  Press Enter to continue...")
        elif choice == "4":
            sec = "kilo"
            apply_configuration("gemini", sec)
            input("  Press Enter to continue...")
        elif choice == "D":
            interactive_primary_secondary_wizard()
        elif choice == "H":
            interactive_show_hide_menu()
        elif choice == "R":
            apply_configuration(p, s)
            input("  Press Enter to continue...")
        elif choice == "U":
            # Reset circuit breakers
            cb_script = os.path.join(ROOT_DIR, "scripts", "rey-breaker.py")
            if not os.path.exists(cb_script):
                cb_script = os.path.join(CONFIG_DIR, "scripts", "rey-breaker.py")
            import subprocess
            subprocess.run([sys.executable, cb_script, "--reset", "all"])
            print(f"\n  {GREEN}✓ Circuit breakers reset! All models and providers unquarantined.{RESET}")
            input("  Press Enter to continue...")


def main():
    args = sys.argv[1:]

    # Command line argument parsing
    if "--status" in args:
        st = get_current_state()
        print(json.dumps(st, indent=2))
        return

    if "--primary" in args or "--secondary" in args:
        primary = "kilo"
        secondary = "openrouter"
        if "--primary" in args:
            primary = args[args.index("--primary") + 1]
        if "--secondary" in args:
            secondary = args[args.index("--secondary") + 1]
        apply_configuration(primary, secondary)
        return

    if "--show-provider" in args:
        prov = args[args.index("--show-provider") + 1]
        st = get_current_state()
        apply_configuration(st["primary"], st["secondary"], show_providers=[prov])
        return

    if "--hide-provider" in args:
        prov = args[args.index("--hide-provider") + 1]
        st = get_current_state()
        apply_configuration(st["primary"], st["secondary"], hide_providers=[prov])
        return

    if len(args) == 1 and args[0].lower() in PROVIDERS_INFO:
        chosen = args[0].lower()
        st = get_current_state()
        secondary = "openrouter" if chosen != "openrouter" else "kilo"
        apply_configuration(chosen, secondary)
        return

    # Default to interactive menu
    interactive_main_menu()


if __name__ == "__main__":
    main()
