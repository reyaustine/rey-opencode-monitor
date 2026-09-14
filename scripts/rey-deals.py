#!/usr/bin/env python3
"""
R.E.Y. // OpenRouter Discounted Models & Deals Engine
Detects real-time promotional discounts across OpenRouter model endpoints (e.g. 25%-80% OFF).
Saves live deals to ~/.config/opencode/openrouter-deals.json and renders an interactive terminal deals HUD.
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
CLEAR_SCREEN = "\033[2J"
CURSOR_HOME = "\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"

HOME = os.path.expanduser("~")
CONFIG_DIR = os.path.join(HOME, ".config", "opencode")
DEALS_FILE = os.path.join(CONFIG_DIR, "openrouter-deals.json")

IS_WINDOWS = sys.platform == 'win32'
if IS_WINDOWS:
    import msvcrt
else:
    import termios
    import tty
    import select

def get_terminal_dimensions():
    import shutil
    try:
        cols, rows = shutil.get_terminal_size((105, 30))
        return max(50, cols), max(12, rows)
    except Exception:
        return 105, 30

def fmt_per_million(cost_str):
    if not cost_str:
        return "$0.00"
    try:
        val = float(cost_str) * 1_000_000
        if val == 0:
            return "$0.00 (FREE)"
        if val < 0.01:
            return f"${val:.4f}"
        return f"${val:.2f}"
    except Exception:
        return str(cost_str)

def fetch_openrouter_deals(quiet=False):
    """Fetches all live models and queries their endpoints concurrently for active discounts."""
    os.makedirs(CONFIG_DIR, exist_ok=True)
    t0 = time.time()

    if not quiet:
        print(f"\n{CYAN}{'=' * 85}{RESET}")
        print(f"  {BOLD}🔍 R.E.Y. // OPENROUTER LIVE PROMOTIONS & DISCOUNTED DEALS SCANNER{RESET}")
        print(f"{CYAN}{'=' * 85}{RESET}")
        print("  Scanning OpenRouter catalog for active endpoint price cuts...")

    # 1. Fetch catalog
    req = urllib.request.Request("https://openrouter.ai/api/v1/models", headers={"User-Agent": "REY-Deals-Scanner/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        all_models = data.get("data", [])
    except Exception as e:
        if not quiet:
            print(f"  {RED}[!] Failed to fetch OpenRouter models: {e}{RESET}")
        return []

    # Map model ID to basic info
    model_meta = {}
    for m in all_models:
        mid = m.get("id", "")
        model_meta[mid] = {
            "name": m.get("name", mid),
            "context_length": m.get("context_length", 0),
            "created": m.get("created", 0),
            "base_prompt": m.get("pricing", {}).get("prompt", "0"),
            "base_compl": m.get("pricing", {}).get("completion", "0"),
        }

    # Filter candidates: skip models that are already 100% free by default (we focus on paid models on sale)
    candidates = [m["id"] for m in all_models if not m["id"].endswith(":free")]

    def check_endpoints(mid):
        deals = []
        try:
            url = f"https://openrouter.ai/api/v1/models/{mid}/endpoints"
            r = urllib.request.Request(url, headers={"User-Agent": "REY-Deals-Scanner/1.0"})
            with urllib.request.urlopen(r, timeout=5) as ep_resp:
                ep_data = json.loads(ep_resp.read().decode("utf-8", errors="replace"))
                endpoints = ep_data.get("data", {}).get("endpoints", [])
                for ep in endpoints:
                    pricing = ep.get("pricing", {})
                    disc = pricing.get("discount", 0)
                    if disc and float(disc) > 0:
                        disc_val = float(disc)
                        disc_pct = int(round(disc_val * 100))
                        prompt_unit = pricing.get("prompt", "0")
                        compl_unit = pricing.get("completion", "0")
                        
                        meta = model_meta.get(mid, {})
                        deals.append({
                            "model_id": mid,
                            "name": meta.get("name", mid),
                            "provider": ep.get("provider_name", "OpenRouter"),
                            "discount": disc_val,
                            "discount_pct": disc_pct,
                            "context_length": ep.get("context_length", meta.get("context_length", 0)),
                            "prompt_raw": prompt_unit,
                            "completion_raw": compl_unit,
                            "prompt_fmt": fmt_per_million(prompt_unit),
                            "completion_fmt": fmt_per_million(compl_unit),
                            "uptime_1d": ep.get("uptime_last_1d", 100)
                        })
        except Exception:
            pass
        return deals

    all_deals = []
    # Query in batches using thread pool
    with ThreadPoolExecutor(max_workers=30) as executor:
        results = executor.map(check_endpoints, candidates)
        for res in results:
            all_deals.extend(res)

    # De-duplicate by model + provider + discount
    seen = set()
    unique_deals = []
    for d in all_deals:
        key = (d["model_id"], d["provider"], d["discount_pct"], d["prompt_raw"])
        if key not in seen:
            seen.add(key)
            unique_deals.append(d)

    # Sort primarily by highest discount %, then by model name
    unique_deals.sort(key=lambda x: (-x["discount_pct"], x["model_id"]))

    duration_ms = int((time.time() - t0) * 1000)

    # Save to cache file
    payload = {
        "timestamp": int(time.time() * 1000),
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "duration_ms": duration_ms,
        "total_deals": len(unique_deals),
        "deals": unique_deals
    }
    try:
        with open(DEALS_FILE, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
    except Exception:
        pass

    if not quiet:
        print(f"  {GREEN}✓ Scan completed in {duration_ms}ms! Found {len(unique_deals)} active promotional deals.{RESET}")

    return unique_deals

def get_cached_or_fresh_deals():
    if os.path.exists(DEALS_FILE):
        try:
            with open(DEALS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            age = (time.time() * 1000 - data.get("timestamp", 0)) / 1000
            if age < 1800 and data.get("deals"):  # fresh within 30m
                return data.get("deals", [])
        except Exception:
            pass
    return fetch_openrouter_deals(quiet=True)

def interactive_deals_menu():
    deals = get_cached_or_fresh_deals()
    sort_mode = "DISCOUNT"  # 'DISCOUNT', 'PRICE', 'CONTEXT'
    
    sys.stdout.write(CLEAR_SCREEN + HIDE_CURSOR)
    sys.stdout.flush()

    try:
        while True:
            cols, rows = get_terminal_dimensions()

            # Apply sort
            if sort_mode == "DISCOUNT":
                sorted_deals = sorted(deals, key=lambda x: (-x["discount_pct"], x["model_id"]))
            elif sort_mode == "PRICE":
                sorted_deals = sorted(deals, key=lambda x: float(x.get("prompt_raw", 0)))
            else:
                sorted_deals = sorted(deals, key=lambda x: -x.get("context_length", 0))

            header_lines = [
                f"{CYAN}{'=' * (cols - 1)}{RESET}",
                f"  {BOLD}{WHITE}R.E.Y. // OPENROUTER DISCOUNTED MODELS & PROMOTIONAL DEALS{RESET}  {GREEN}[{len(sorted_deals)} ACTIVE DEALS]{RESET}",
                f"  {DIM}Keys: [{BOLD}S{RESET}] Toggle Sort ({sort_mode}) | [{BOLD}R{RESET}] Rescan API | [{BOLD}Q{RESET}/Esc/Enter] Return to Monitor",
                f"{CYAN}{'-' * (cols - 1)}{RESET}",
                f"  {'MODEL':<34} | {'PROVIDER':<14} | {'DISCOUNT':<10} | {'PROMPT / 1M':<12} | {'COMPL / 1M':<12} | {'CTX':<8}",
                f"{GRAY}{'-' * (cols - 1)}{RESET}"
            ]

            body_lines = []
            if not sorted_deals:
                body_lines.append(f"  {YELLOW}No active promotional discounts found or API unreachable. Press R to rescan.{RESET}")
            else:
                for d in sorted_deals:
                    mid = d["model_id"]
                    if len(mid) > 34:
                        mid = mid[:32] + ".."
                    prov = d["provider"][:14]
                    pct = d["discount_pct"]
                    pct_str = f"[{pct}% OFF]"
                    col_pct = GREEN if pct >= 50 else (YELLOW if pct >= 25 else CYAN)
                    
                    p_fmt = d["prompt_fmt"]
                    c_fmt = d["completion_fmt"]
                    ctx = f"{d['context_length'] // 1000}k" if d['context_length'] >= 1000 else str(d['context_length'])

                    line = f"  {mid:<34} | {prov:<14} | {col_pct}{pct_str:<10}{RESET} | {WHITE}{p_fmt:<12}{RESET} | {WHITE}{c_fmt:<12}{RESET} | {GRAY}{ctx:<8}{RESET}"
                    body_lines.append(line)

            # Render frame
            sys.stdout.write(CURSOR_HOME)
            for hl in header_lines:
                sys.stdout.write(hl[:cols + 20] + "\n")

            avail_rows = max(1, rows - len(header_lines) - 2)
            for i in range(avail_rows):
                if i < len(body_lines):
                    sys.stdout.write(body_lines[i][:cols + 25] + "\n")
                else:
                    sys.stdout.write(" " * (cols - 1) + "\n")

            sys.stdout.write(f"{CYAN}{'=' * (cols - 1)}{RESET}\n")
            sys.stdout.flush()

            # Input
            key = None
            if IS_WINDOWS:
                ch = msvcrt.getch()
                try:
                    key = ch.decode("utf-8").lower()
                except Exception:
                    key = ""
            else:
                try:
                    old_settings = termios.tcgetattr(sys.stdin)
                    tty.setcbreak(sys.stdin.fileno())
                    if select.select([sys.stdin], [], [], 10)[0]:
                        key = sys.stdin.read(1).lower()
                finally:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

            if key in ['q', '\x1b', '\r', '\n']:
                break
            elif key == 's':
                if sort_mode == "DISCOUNT":
                    sort_mode = "PRICE"
                elif sort_mode == "PRICE":
                    sort_mode = "CONTEXT"
                else:
                    sort_mode = "DISCOUNT"
                sys.stdout.write(CLEAR_SCREEN)
            elif key == 'r':
                sys.stdout.write(CLEAR_SCREEN + SHOW_CURSOR)
                sys.stdout.flush()
                deals = fetch_openrouter_deals(quiet=False)
                print("\n  Press any key to view results...")
                if IS_WINDOWS:
                    msvcrt.getch()
                else:
                    sys.stdin.read(1)
                sys.stdout.write(CLEAR_SCREEN + HIDE_CURSOR)

    finally:
        sys.stdout.write(SHOW_CURSOR + CLEAR_SCREEN)
        sys.stdout.flush()

if __name__ == "__main__":
    if "--scan" in sys.argv or "-s" in sys.argv:
        fetch_openrouter_deals(quiet=False)
    else:
        interactive_deals_menu()
