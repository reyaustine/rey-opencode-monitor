#!/usr/bin/env python3
"""
R.E.Y. // FIX & DIAGNOSTICS ENGINE
Scans the OpenCode/REY environment for common issues and auto-repairs them.
Checks: config files, JSON validity, instructions, API keys, database, providers.
"""

import os
import sys
import json
import re
import shutil
import subprocess

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RESET = "\033[0m"
BOLD = "\033[1m"
CYAN = "\033[36m"
GREEN = "\033[32m"
YELLOW = "\033[33m"
RED = "\033[31m"
GRAY = "\033[90m"

HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME, ".config", "opencode")
SCRIPTS_DIR = os.path.join(CONFIG_DIR, "scripts")
SWARM_DIR = os.path.join(HOME, "opencode-swarm-pack")
SWARM_CONFIGS = os.path.join(SWARM_DIR, "configs")
SWARM_SCRIPTS = os.path.join(SWARM_DIR, "scripts")


def _resolve_opencode_data_path(filename: str) -> str:
    """Cross-platform OpenCode data dir resolver.
    macOS: ~/Library/Application Support/opencode/<filename>
    Linux/Windows: ~/.local/share/opencode/<filename>
    """
    candidates = [
        os.path.join(HOME, "Library", "Application Support", "opencode", filename),
        os.path.join(HOME, ".local", "share", "opencode", filename),
        os.path.join(os.environ.get("USERPROFILE", HOME), ".local", "share", "opencode", filename),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return os.path.join(HOME, ".local", "share", "opencode", filename)


AUTH_PATH = _resolve_opencode_data_path("auth.json")
DB_PATH = _resolve_opencode_data_path("opencode.db")

CONFIG_FILES = ["opencode.jsonc", "opencode.json", "model-fallback.json", "skill-routing.yaml"]
REQUIRED_SCRIPTS = [
    "rey-monitor.ps1", "rey-state.py", "rey-health.py", "rey-quota.py",
    "rey-override.py", "rey-logs.py", "rey-deals.py", "rey-models.py"
]

fixes_applied = []
issues_found = []


def section(title):
    print(f"\n{CYAN}{'=' * 70}{RESET}")
    print(f"  {BOLD}{title}{RESET}")
    print(f"{CYAN}{'=' * 70}{RESET}")


def ok(msg):
    print(f"  {GREEN}[OK]{RESET}   {msg}")


def warn(msg):
    print(f"  {YELLOW}[WARN]{RESET} {msg}")
    issues_found.append(msg)


def fixed(msg):
    print(f"  {GREEN}[FIXED]{RESET} {msg}")
    fixes_applied.append(msg)


def fail(msg):
    print(f"  {RED}[FAIL]{RESET} {msg}")
    issues_found.append(msg)


def check_config_files():
    section("1. CONFIG FILES")
    for fname in CONFIG_FILES:
        path = os.path.join(CONFIG_DIR, fname)
        if not os.path.exists(path):
            warn(f"{fname} MISSING")
            src = os.path.join(SWARM_CONFIGS, fname)
            if os.path.exists(src):
                try:
                    os.makedirs(CONFIG_DIR, exist_ok=True)
                    shutil.copy2(src, path)
                    fixed(f"{fname} deployed from swarm-pack")
                except Exception as e:
                    fail(f"{fname} deploy failed: {e}")
            else:
                fail(f"{fname} not found in swarm-pack either")
        else:
            size = os.path.getsize(path)
            if size < 20:
                warn(f"{fname} is nearly empty ({size} bytes)")
                src = os.path.join(SWARM_CONFIGS, fname)
                if os.path.exists(src):
                    try:
                        shutil.copy2(src, path)
                        fixed(f"{fname} redeployed (was empty)")
                    except Exception as e:
                        fail(f"{fname} redeploy failed: {e}")
            else:
                ok(f"{fname} present ({size} bytes)")


def check_json_validity():
    section("2. JSON VALIDITY")
    for fname in ["opencode.json", "model-fallback.json"]:
        path = os.path.join(CONFIG_DIR, fname)
        if not os.path.exists(path):
            continue
        try:
            with open(path, "r", encoding="utf-8") as f:
                json.load(f)
            ok(f"{fname} valid JSON")
        except Exception as e:
            warn(f"{fname} INVALID JSON: {e}")

    # jsonc needs comment stripping
    jsonc = os.path.join(CONFIG_DIR, "opencode.jsonc")
    if os.path.exists(jsonc):
        try:
            with open(jsonc, "r", encoding="utf-8") as f:
                content = f.read()
            clean = re.sub(r'(?m)^\s*//.*$', '', content)
            data = json.loads(clean)
            model = data.get("model", "?")
            ok(f"opencode.jsonc valid JSONC (model: {model})")
        except Exception as e:
            warn(f"opencode.jsonc INVALID: {e}")


def check_scripts():
    section("3. R.E.Y. SCRIPTS")
    if not os.path.isdir(SCRIPTS_DIR):
        warn(f"scripts dir missing: {SCRIPTS_DIR}")
        try:
            os.makedirs(SCRIPTS_DIR, exist_ok=True)
            fixed("created scripts directory")
        except Exception as e:
            fail(f"could not create scripts dir: {e}")
            return

    for sname in REQUIRED_SCRIPTS:
        path = os.path.join(SCRIPTS_DIR, sname)
        if os.path.exists(path):
            ok(f"{sname}")
        else:
            warn(f"{sname} MISSING")
            src = os.path.join(SWARM_SCRIPTS, sname)
            if os.path.exists(src):
                try:
                    shutil.copy2(src, path)
                    fixed(f"{sname} deployed from swarm-pack")
                except Exception as e:
                    fail(f"{sname} deploy failed: {e}")
            else:
                fail(f"{sname} not in swarm-pack")


def check_instructions():
    section("4. INSTRUCTIONS & COMMANDS")
    for sub in ["instructions", "commands"]:
        dst_dir = os.path.join(CONFIG_DIR, sub)
        src_dir = os.path.join(SWARM_DIR, sub)
        if os.path.isdir(dst_dir) and os.listdir(dst_dir):
            ok(f"{sub}/ present ({len(os.listdir(dst_dir))} files)")
        elif os.path.isdir(src_dir):
            try:
                os.makedirs(dst_dir, exist_ok=True)
                for fn in os.listdir(src_dir):
                    shutil.copy2(os.path.join(src_dir, fn), os.path.join(dst_dir, fn))
                fixed(f"{sub}/ deployed from swarm-pack")
            except Exception as e:
                fail(f"{sub}/ deploy failed: {e}")
        else:
            warn(f"{sub}/ missing (not in swarm-pack either)")


def check_python():
    section("5. PYTHON RUNTIME")
    import platform
    exe = sys.executable
    ver = platform.python_version()
    ok(f"Python {ver} at {exe}")
    if sys.version_info < (3, 8):
        warn("Python 3.8+ recommended")


def check_auth_keys():
    section("6. PROVIDER API KEYS")
    # Map logical provider -> key slot in auth.json (gemini lives under "google").
    # Kilo needs no key; mistral/gemini can also be env-var providers.
    key_map = {
        "openrouter": "openrouter",
        "groq": "groq",
        "gemini": "google",
        "mistral": "mistral",
    }
    env_map = {"gemini": "GEMINI_API_KEY", "mistral": "MISTRAL_API_KEY"}
    no_key_ok = {"kilo", "opencode"}

    if not os.path.exists(AUTH_PATH):
        warn(f"auth.json not found at {AUTH_PATH}")
        warn("Some providers may be unavailable (run 'rey setup')")
        return
    try:
        with open(AUTH_PATH, "r", encoding="utf-8-sig") as f:
            auth = json.load(f)
    except Exception as e:
        fail(f"auth.json unreadable: {e}")
        return

    for prov in ["openrouter", "groq", "gemini", "mistral", "kilo", "opencode"]:
        if prov in no_key_ok:
            ok(f"{prov} (no key required)")
            continue
        slot = key_map.get(prov)
        has_auth = bool(slot and auth.get(slot) and auth[slot].get("key"))
        has_env = bool(env_map.get(prov) and os.environ.get(env_map[prov]))
        if has_auth or has_env:
            ok(f"{prov} key configured")
        else:
            warn(f"{prov} key not configured (auth.json or {env_map.get(prov, 'env')})")


def check_database():
    section("7. OPENCODE DATABASE")
    if os.path.exists(DB_PATH):
        size = os.path.getsize(DB_PATH)
        ok(f"opencode.db present ({size:,} bytes)")
        # Verify rey-state.py can read it
        state_script = os.path.join(SCRIPTS_DIR, "rey-state.py")
        if os.path.exists(state_script):
            try:
                out = subprocess.run(
                    [sys.executable, state_script],
                    capture_output=True, text=True, timeout=15
                )
                if out.stdout:
                    data = json.loads(out.stdout)
                    if data.get("ok"):
                        ok(f"rey-state.py OK ({data.get('active_threads', 0)} active threads)")
                    else:
                        warn(f"rey-state.py returned error: {data.get('error', '?')}")
                else:
                    warn("rey-state.py returned no output")
            except Exception as e:
                warn(f"rey-state.py failed: {e}")
    else:
        warn(f"opencode.db NOT FOUND at {DB_PATH}")
        warn("OpenCode may not have been run yet")


def check_swarm_pack():
    section("8. SWARM PACK SOURCE")
    if os.path.isdir(SWARM_DIR):
        ok(f"swarm-pack present: {SWARM_DIR}")
        bin_js = os.path.join(SWARM_DIR, "bin", "rey.js")
        if os.path.exists(bin_js):
            ok("bin/rey.js present")
        else:
            fail("bin/rey.js MISSING")
    else:
        warn(f"swarm-pack not found: {SWARM_DIR}")


def main():
    print(f"\n{CYAN}{'=' * 70}{RESET}")
    print(f"  {BOLD}R.E.Y. // FIX & DIAGNOSTICS ENGINE{RESET}")
    print(f"  Scanning environment and auto-repairing common issues...")
    print(f"{CYAN}{'=' * 70}{RESET}")

    check_config_files()
    check_json_validity()
    check_scripts()
    check_instructions()
    check_python()
    check_auth_keys()
    check_database()
    check_swarm_pack()

    # Summary
    section("SUMMARY")
    if fixes_applied:
        print(f"  {GREEN}{BOLD}Auto-repairs applied: {len(fixes_applied)}{RESET}")
        for f in fixes_applied:
            print(f"    {GREEN}+{RESET} {f}")
    else:
        print(f"  {GREEN}No repairs needed - environment is healthy.{RESET}")

    if issues_found:
        print(f"\n  {YELLOW}{BOLD}Remaining warnings: {len(issues_found)}{RESET}")
        for i in issues_found:
            print(f"    {YELLOW}!{RESET} {i}")
    else:
        print(f"\n  {GREEN}No outstanding issues.{RESET}")

    print(f"\n{CYAN}{'=' * 70}{RESET}\n")
    return 1 if issues_found else 0


if __name__ == "__main__":
    sys.exit(main())
