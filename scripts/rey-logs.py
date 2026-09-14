#!/usr/bin/env python3
"""
R.E.Y. // Interactive Log & Diagnostics Viewer
Inspects OpenCode runtime logs, model-fallback events, and monitor telemetry.
Press E for Errors/Warnings, F for Fallbacks, A for All Logs, R to Refresh, Q/Esc to Return.
"""

import os
import sys
import json
import time
import re

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
BG_RED = "\033[41m"
BG_YELLOW = "\033[43m"
CLEAR_SCREEN = "\033[2J"
CURSOR_HOME = "\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"

HOME = os.path.expanduser("~")
LOG_DIR = os.path.join(HOME, ".local", "share", "opencode", "log")
LOG_FILE = os.path.join(LOG_DIR, "opencode.log")
FALLBACK_LOG = os.path.join(HOME, ".local", "share", "opencode", "logs", "model-fallback.log")
CONFIG_DIR = os.path.join(HOME, ".config", "opencode")
HEALTH_FILE = os.path.join(CONFIG_DIR, "model-health.json")

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
        cols, rows = shutil.get_terminal_size((100, 30))
        return max(40, cols), max(12, rows)
    except Exception:
        return 100, 30

def read_tail(file_path, max_lines=400):
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, "rb") as f:
            f.seek(0, os.SEEK_END)
            size = f.tell()
            block_size = 1024 * 128  # read up to 128KB from end
            seek_pos = max(0, size - block_size)
            f.seek(seek_pos)
            data = f.read().decode("utf-8", errors="replace")
            lines = data.splitlines()
            if seek_pos > 0 and len(lines) > 1:
                lines = lines[1:]  # drop partial first line
            return lines[-max_lines:]
    except Exception as e:
        return [f"[!] Failed to read {file_path}: {e}"]

def format_log_line(line, width=100):
    """Parses and colors key=value or JSON log lines."""
    clean = line.strip()
    if not clean:
        return ""
    
    # Highlight level
    level_color = WHITE
    is_error = False
    is_warn = False

    if "level=ERROR" in clean or "error=" in clean.lower() or "exception" in clean.lower() or "aborterror" in clean.lower():
        level_color = RED
        is_error = True
    elif "level=WARN" in clean or "warn" in clean.lower() or "timeout" in clean.lower():
        level_color = YELLOW
        is_warn = True
    elif "level=INFO" in clean:
        level_color = CYAN

    # Highlight model fallback events
    if "[model-fallback]" in clean:
        clean = clean.replace("[model-fallback]", f"{MAGENTA}[MODEL-FALLBACK]{RESET}")

    # Format timestamp
    ts_match = re.match(r"^timestamp=([^\s]+)", clean)
    if ts_match:
        ts_raw = ts_match.group(1)
        # short timestamp HH:MM:SS
        try:
            if "T" in ts_raw:
                time_part = ts_raw.split("T")[1][:8]
                clean = f"{GRAY}[{time_part}]{RESET} " + clean[len(ts_match.group(0)):].strip()
        except Exception:
            pass

    # Colorize message=
    clean = re.sub(r'message="([^"]+)"', rf'{BOLD}{level_color}message="{RESET}\1{BOLD}{level_color}"{RESET}', clean)
    clean = re.sub(r'error="([^"]+)"', rf'{RED}{BOLD}error="{RESET}\1{RED}{BOLD}"{RESET}', clean)
    clean = re.sub(r'model=([^\s]+)', rf'model={GREEN}\1{RESET}', clean)
    clean = re.sub(r'fallbackModel="([^"]+)"', rf'fallbackModel="{YELLOW}\1{RESET}"', clean)

    prefix = f"{RED}[ERR]{RESET} " if is_error else (f"{YELLOW}[WRN]{RESET} " if is_warn else "      ")
    return prefix + clean

def interactive_log_viewer():
    view_filter = "ERRORS"  # 'ERRORS', 'FALLBACK', 'ALL', 'HEALTH'
    
    sys.stdout.write(CLEAR_SCREEN + HIDE_CURSOR)
    sys.stdout.flush()

    try:
        while True:
            cols, rows = get_terminal_dimensions()
            header_lines = []
            header_lines.append(f"{CYAN}{'=' * (cols - 1)}{RESET}")
            header_lines.append(f"  {BOLD}{WHITE}R.E.Y. // SYSTEM LOG & DIAGNOSTICS VIEWER{RESET}  {GRAY}[FILTER: {BOLD}{view_filter}{RESET}{GRAY}]{RESET}")
            header_lines.append(f"  {DIM}Keys: {RESET}[{BOLD}E{RESET}] Errors & Warnings | [{BOLD}F{RESET}] Fallbacks | [{BOLD}A{RESET}] All Logs | [{BOLD}H{RESET}] Health Report | [{BOLD}R{RESET}] Refresh | [{BOLD}Q{RESET}/Esc] Back")
            header_lines.append(f"{CYAN}{'-' * (cols - 1)}{RESET}")

            body_lines = []
            if view_filter == "ERRORS":
                raw = read_tail(LOG_FILE, max_lines=600)
                filtered = [
                    l for l in raw 
                    if any(k in l for k in ["level=ERROR", "level=WARN", "timeout", "AbortError", "failed", "Aborted", "fallback"])
                ]
                if not filtered:
                    body_lines.append(f"  {GREEN}✓ No errors or warnings found in recent OpenCode logs!{RESET}")
                else:
                    for l in filtered[-max(10, rows - 7):]:
                        body_lines.append("  " + format_log_line(l, cols))

            elif view_filter == "FALLBACK":
                raw = read_tail(FALLBACK_LOG, max_lines=300)
                if not raw and os.path.exists(LOG_FILE):
                    raw_main = read_tail(LOG_FILE, max_lines=600)
                    raw = [l for l in raw_main if "[model-fallback]" in l or "fallback" in l.lower()]
                if not raw:
                    body_lines.append(f"  {GREEN}✓ No model fallbacks or timeouts recorded!{RESET}")
                else:
                    for l in raw[-max(10, rows - 7):]:
                        body_lines.append("  " + format_log_line(l, cols))

            elif view_filter == "HEALTH":
                if os.path.exists(HEALTH_FILE):
                    try:
                        with open(HEALTH_FILE, "r", encoding="utf-8") as hf:
                            hdata = json.load(hf)
                        body_lines.append(f"  {BOLD}Last Check:{RESET} {hdata.get('last_check_str', 'N/A')}  |  {BOLD}Status:{RESET} {hdata.get('status', 'N/A')} ({hdata.get('duration_ms', 0)}ms)")
                        body_lines.append(f"  {BOLD}Responsive Models:{RESET} {hdata.get('responsive_count', 0)}  |  {BOLD}Unresponsive:{RESET} {hdata.get('unresponsive_count', 0)}")
                        
                        unresp = hdata.get("unresponsive_models", [])
                        if unresp:
                            body_lines.append(f"  {RED}{BOLD}⚠ Unresponsive Models:{RESET} {', '.join(unresp)}")
                        
                        new_mods = hdata.get("new_models", [])
                        if new_mods:
                            body_lines.append(f"  {GREEN}{BOLD}✦ New Free Models Discovered ({len(new_mods)}):{RESET}")
                            for nm in new_mods[:8]:
                                body_lines.append(f"    • {nm}")

                        providers = hdata.get("providers", {})
                        body_lines.append(f"  {BOLD}Provider Latencies:{RESET}")
                        for p, info in providers.items():
                            ok_s = f"{GREEN}ONLINE{RESET}" if info.get('ok') else f"{RED}FAIL{RESET}"
                            lat = info.get('latency_ms', 0)
                            body_lines.append(f"    • {p:<12}: {ok_s} ({lat}ms)")
                    except Exception as e:
                        body_lines.append(f"  {RED}Error reading health file: {e}{RESET}")
                else:
                    body_lines.append(f"  {YELLOW}No health file found. Press H in main HUD to run check.{RESET}")

            else:  # ALL
                raw = read_tail(LOG_FILE, max_lines=max(20, rows - 7))
                for l in raw:
                    body_lines.append("  " + format_log_line(l, cols))

            # Render
            sys.stdout.write(CURSOR_HOME)
            for hl in header_lines:
                sys.stdout.write(hl[:cols] + "\n")
            
            avail_rows = max(1, rows - len(header_lines) - 2)
            display_rows = body_lines[-avail_rows:]
            for row_str in display_rows:
                sys.stdout.write(row_str[:cols + 25] + "\n")
            
            # Fill remaining rows with blank space
            for _ in range(avail_rows - len(display_rows)):
                sys.stdout.write(" " * (cols - 1) + "\n")

            sys.stdout.write(f"{CYAN}{'=' * (cols - 1)}{RESET}\n")
            sys.stdout.flush()

            # Wait for key press
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

            if key in ['q', '\x1b', '\r', '\n']:  # Q, Esc, or Enter
                break
            elif key == 'e':
                view_filter = "ERRORS"
                sys.stdout.write(CLEAR_SCREEN)
            elif key == 'f':
                view_filter = "FALLBACK"
                sys.stdout.write(CLEAR_SCREEN)
            elif key == 'a':
                view_filter = "ALL"
                sys.stdout.write(CLEAR_SCREEN)
            elif key == 'h':
                view_filter = "HEALTH"
                sys.stdout.write(CLEAR_SCREEN)
            elif key == 'r':
                sys.stdout.write(CLEAR_SCREEN)

    finally:
        sys.stdout.write(SHOW_CURSOR + CLEAR_SCREEN)
        sys.stdout.flush()

if __name__ == "__main__":
    if "--errors" in sys.argv or "-e" in sys.argv:
        raw = read_tail(LOG_FILE, max_lines=600)
        filtered = [l for l in raw if any(k in l for k in ["level=ERROR", "level=WARN", "timeout", "AbortError", "failed", "fallback"])]
        if not filtered:
            print("✓ No errors or warnings found in recent logs.")
        else:
            for l in filtered[-40:]:
                print(format_log_line(l))
    elif "--fallback" in sys.argv or "-f" in sys.argv:
        raw = read_tail(FALLBACK_LOG, max_lines=300)
        if not raw and os.path.exists(LOG_FILE):
            raw_main = read_tail(LOG_FILE, max_lines=600)
            raw = [l for l in raw_main if "[model-fallback]" in l or "fallback" in l.lower()]
        if not raw:
            print("✓ No fallback events recorded.")
        else:
            for l in raw[-40:]:
                print(format_log_line(l))
    else:
        interactive_log_viewer()
