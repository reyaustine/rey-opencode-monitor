#!/usr/bin/env python3
"""
R.E.Y. // Runtime Execution & Yield Monitor - Opencode Monitoring CLI
Cross-platform terminal HUD monitor for macOS, Linux, and Windows.
Tracks OpenCode IDE status, active workspaces, sub-agents, and per-machine token metrics.
Press Q to quit. Press T to toggle Token Fleet view.
"""

import os
import sys
import time
import math
import shutil
import json
import socket
from pathlib import Path

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
DARK_CYAN = "\033[36m"
CLEAR_SCREEN = "\033[2J"
CURSOR_HOME = "\033[H"
HIDE_CURSOR = "\033[?25l"
SHOW_CURSOR = "\033[?25h"

# Non-blocking input support
IS_WINDOWS = sys.platform == 'win32'
if IS_WINDOWS:
    import msvcrt
else:
    import termios
    import tty
    import select

SPIN_CHARS = ['|', '/', '-', '\\']
REFRESH_EVERY = 15  # ticks between state refreshes (~3s)
TICK_S = 0.2
MAX_THREADS = 7

# Try importing rey_state directly if in same directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

try:
    import rey_state
except ImportError:
    rey_state = None

def get_terminal_dimensions():
    try:
        cols, rows = shutil.get_terminal_size((80, 30))
        return max(40, cols), max(12, rows)
    except Exception:
        return 80, 30

def shorten(text, max_len):
    if not text:
        return '-'
    text = str(text).strip()
    if max_len <= 3:
        return text[:max_len]
    if len(text) > max_len:
        return text[:max_len - 2] + '..'
    return text

def safe_sub(text, start, length):
    if not text or start >= len(text):
        return ''
    return text[start:start + length]

class KeyReader:
    def __init__(self):
        self.old_settings = None
        if not IS_WINDOWS and sys.stdin.isatty():
            try:
                self.old_settings = termios.tcgetattr(sys.stdin)
                tty.setcbreak(sys.stdin.fileno())
            except Exception:
                pass

    def get_key(self):
        try:
            if IS_WINDOWS:
                if msvcrt.kbhit():
                    ch = msvcrt.getch()
                    try:
                        return ch.decode('utf-8')
                    except Exception:
                        return ''
            else:
                if select.select([sys.stdin], [], [], 0)[0]:
                    return sys.stdin.read(1)
        except Exception:
            pass
        return None

    def restore(self):
        if self.old_settings and sys.stdin.isatty():
            try:
                termios.tcsetattr(sys.stdin, termios.TCSADRAIN, self.old_settings)
            except Exception:
                pass

class ReyMonitor:
    def __init__(self):
        self.logs = []
        self.thread_cache = {}
        self.was_working = False
        self.last_w = 0
        self.last_h = 0
        self.view_mode = 'FLEET'  # 'FLEET' or 'TOKENS'

        self.state = {
            'tick': 0,
            'ide_status': 'CHECKING...',
            'ide_color': GRAY,
            'workspace': '-',
            'default_model': 'unknown',
            'small_model': 'unknown',
            'providers': 'unknown',
            'model_count': 'unknown',
            'version': 'unknown',
            'thread_count': 0,
            'activity': 'IDLE',
            'health': 'STARTING',
            'tokens_total': '0',
            'tokens_prompt': '0',
            'tokens_comp': '0',
            'tokens_cache': '0',
            'tokens_cost': '$0.00',
            'token_models': [],
            'last_refresh': 'never'
        }
        self.add_log('R.E.Y. monitor initialized (macOS / cross-platform)')

    def add_log(self, msg):
        ts = time.strftime('%H:%M:%S')
        self.logs.append(f"[{ts}] {msg}")
        while len(self.logs) > 6:
            self.logs.pop(0)

    def refresh_status(self):
        ok = True

        # 1. Read Global Config
        conf_dir = os.path.expanduser('~/.config/opencode')
        cfg_json = os.path.join(conf_dir, 'opencode.json')
        cfg_jsonc = os.path.join(conf_dir, 'opencode.jsonc')

        try:
            if os.path.exists(cfg_json):
                with open(cfg_json, 'r', encoding='utf-8') as f:
                    cdata = json.load(f)
                    if cdata.get('model'):
                        self.state['default_model'] = str(cdata['model'])
                    if cdata.get('small_model'):
                        self.state['small_model'] = str(cdata['small_model'])

            if os.path.exists(cfg_jsonc):
                with open(cfg_jsonc, 'r', encoding='utf-8') as f:
                    lines = [l for l in f if not l.strip().startswith('//')]
                    cdata = json.loads('\n'.join(lines))
                    if cdata.get('enabled_providers'):
                        self.state['providers'] = ', '.join(cdata['enabled_providers'])

                    m_count = 0
                    if cdata.get('provider'):
                        for p_name, p_val in cdata['provider'].items():
                            if isinstance(p_val, dict):
                                m_count += len(p_val.get('whitelist', []))
                                m_count += len(p_val.get('models', {}))
                    if m_count > 0:
                        self.state['model_count'] = f"{m_count} allowlisted"
        except Exception as e:
            ok = False
            self.add_log('config parse err: ' + shorten(str(e), 35))

        # 2. Read OpenCode Version
        if self.state['version'] == 'unknown':
            # Check npm global package.json
            candidates = [
                os.path.expanduser('~/.nvm/versions/node/**/lib/node_modules/opencode-ai/package.json'),
                os.path.expanduser('/usr/local/lib/node_modules/opencode-ai/package.json'),
                os.path.expanduser('/opt/homebrew/lib/node_modules/opencode-ai/package.json'),
                os.path.join(os.environ.get('APPDATA', ''), 'npm/node_modules/opencode-ai/package.json')
            ]
            for p in candidates:
                if os.path.exists(p):
                    try:
                        with open(p, 'r', encoding='utf-8') as pf:
                            self.state['version'] = json.load(pf).get('version', 'opencode')
                            break
                    except Exception:
                        pass
            if self.state['version'] == 'unknown':
                self.state['version'] = '1.17.11'

        # 3. Read SQLite Telemetry from rey_state
        try:
            if rey_state:
                db_data = rey_state.get_state()
            else:
                # Run external rey-state.py
                py_script = os.path.join(SCRIPT_DIR, 'rey-state.py')
                if not os.path.exists(py_script):
                    py_script = os.path.join(SCRIPT_DIR, 'jarvis-state.py')
                import subprocess
                out = subprocess.check_output([sys.executable, py_script], stderr=subprocess.DEVNULL)
                db_data = json.loads(out.decode('utf-8'))

            if db_data.get('ok'):
                self.state['thread_count'] = int(db_data.get('active_threads', 0))
                self.state['workspace'] = str(db_data.get('current_workspace', '-'))

                sessions = db_data.get('sessions', [])
                live_ids = {s['id'] for s in sessions}

                # Prune dead threads
                for k in list(self.thread_cache.keys()):
                    if k not in live_ids:
                        del self.thread_cache[k]

                for s in sessions:
                    sid = s['id']
                    prev = self.thread_cache.get(sid)
                    prev_state = prev.get('state') if prev else ''
                    curr_state = s.get('state', 'DONE')

                    short_id = safe_sub(sid, 0, 12)
                    if curr_state == 'WORKING' and prev_state != 'WORKING':
                        self.add_log(f"thread {short_id} THINKING: " + shorten(s.get('title', ''), 35))
                    if curr_state == 'DONE' and prev_state == 'WORKING':
                        self.add_log(f"thread {short_id} DONE cost={s.get('cost', 0)}")

                    self.thread_cache[sid] = s

                # Process tokens
                tdata = db_data.get('tokens')
                if tdata:
                    gt = tdata.get('grand_total', {})
                    if gt:
                        self.state['tokens_total'] = str(gt.get('total_fmt', '0'))
                        self.state['tokens_prompt'] = str(gt.get('prompt_fmt', '0'))
                        self.state['tokens_comp'] = str(gt.get('completion_fmt', '0'))
                        self.state['tokens_cache'] = str(gt.get('cache_read_fmt', '0'))
                        cost_val = float(gt.get('cost', 0.0))
                        self.state['tokens_cost'] = f"${cost_val:.4f}"
                    self.state['token_models'] = tdata.get('models', [])
            else:
                ok = False
                self.add_log('db query err: ' + shorten(db_data.get('error', ''), 35))
        except Exception as e:
            ok = False
            self.add_log('session sync FAILED: ' + shorten(str(e), 35))

        # 4. Check OpenCode IDE Process
        try:
            if IS_WINDOWS:
                import subprocess
                out = subprocess.check_output(
                    ['tasklist', '/FI', 'IMAGENAME eq OpenCode.exe', '/NH'],
                    text=True, stderr=subprocess.DEVNULL
                )
                if 'OpenCode.exe' in out:
                    self.state['ide_status'] = 'ONLINE'
                    self.state['ide_color'] = GREEN
                else:
                    self.state['ide_status'] = 'OFFLINE'
                    self.state['ide_color'] = GRAY
            else:
                import subprocess
                out = subprocess.check_output(['pgrep', '-f', '[O]penCode'], text=True, stderr=subprocess.DEVNULL).strip()
                if out:
                    pid = out.split()[0]
                    self.state['ide_status'] = f"ONLINE (PID {pid})"
                    self.state['ide_color'] = GREEN
                else:
                    self.state['ide_status'] = 'OFFLINE'
                    self.state['ide_color'] = GRAY
        except Exception:
            self.state['ide_status'] = 'ONLINE' if self.state['thread_count'] > 0 else 'STANDBY'
            self.state['ide_color'] = GREEN if self.state['thread_count'] > 0 else GRAY

        working = (self.state['thread_count'] > 0)
        if working and not self.was_working:
            self.add_log('fleet thinking...')
        if not working and self.was_working:
            self.add_log('fleet idle - all done')
        self.was_working = working

        if working:
            self.state['activity'] = 'THINKING'
        elif 'ONLINE' in self.state['ide_status']:
            self.state['activity'] = 'IDLE (STANDBY)'
        else:
            self.state['activity'] = 'IDLE'

        self.state['health'] = 'ALL SYSTEMS NOMINAL' if ok else 'DEGRADED - CHECK LOG'
        self.state['last_refresh'] = time.strftime('%H:%M:%S')

    def draw(self, frame):
        cols, rows = get_terminal_dimensions()

        # Handle screen resize
        if cols != self.last_w or rows != self.last_h:
            self.last_w = cols
            self.last_h = rows
            sys.stdout.write(CLEAR_SCREEN)

        working = self.was_working
        spin = SPIN_CHARS[frame % 4]
        amp = 10 if working else 8
        level = int(10 + amp * math.sin(frame / 4.0))
        level = max(0, min(20, level))
        bar = ('#' * level).ljust(20, '.')

        health_color = GREEN if self.state['health'] == 'ALL SYSTEMS NOMINAL' else RED
        act_color = YELLOW if working else GREEN
        tag = '[ THINKING ]' if working else '[ STANDBY ]'
        head_color = YELLOW if working else CYAN

        lines = []
        max_w = max(10, cols - 1)

        def row(text, color=""):
            # Strip ANSI length calculation for safe padding
            raw = text.ljust(max_w)[:max_w]
            if color:
                return f"{color}{raw}{RESET}"
            return raw

        lines.append(row('  ' + '=' * 62, head_color))
        lines.append(row(f"   R.E.Y.  //  RUNTIME EXECUTION & YIELD MONITOR  {tag} [ {spin} ] [{bar}]", head_color))
        lines.append(row('  ' + '=' * 62, head_color))
        lines.append(row(f"   opencode IDE  : {self.state['ide_status']}", self.state['ide_color']))
        lines.append(row(f"   workspace     : {self.state['workspace']}", WHITE))
        lines.append(row(f"   default model : {self.state['default_model']}", WHITE))
        lines.append(row(f"   small model   : {self.state['small_model']}", WHITE))
        lines.append(row(f"   providers     : {self.state['providers']}", WHITE))
        lines.append(row(f"   models visible: {self.state['model_count']}", WHITE))
        lines.append(row(f"   opencode      : {self.state['version']}", WHITE))
        lines.append(row(f"   active threads: {self.state['thread_count']}", MAGENTA))
        lines.append(row(f"   activity      : {self.state['activity']}", act_color))
        lines.append(row(f"   status        : {self.state['health']}", health_color))
        lines.append(row(f"   tokens used   : {self.state['tokens_total']}  (prompt: {self.state['tokens_prompt']} | compl: {self.state['tokens_comp']} | cache: {self.state['tokens_cache']})  [{self.state['tokens_cost']}]", CYAN))
        lines.append(row(f"   last refresh  : {self.state['last_refresh']}   (Q: quit | T: toggle model tokens)", GRAY))

        if self.view_mode == 'TOKENS':
            # --- TOKENS VIEW ---
            lines.append(row('  ' + '-' * 62, DARK_CYAN))
            lines.append(row(f"  TOKEN FLEET BREAKDOWN (TOTAL: {self.state['tokens_total']} | COST: {self.state['tokens_cost']})  [PRESS T FOR LOGS/FLEET]", CYAN))
            lines.append(row(f"  {'PROVIDER':<12} | {'MODEL':<35} | {'PROMPT':<9} | {'COMPL':<8} | {'TOTAL':<9} | {'CALLS':<5}", YELLOW))
            lines.append(row('  ' + '-' * 92, GRAY))

            max_token_rows = max(3, rows - 21)
            token_models = self.state.get('token_models', [])
            for i in range(max_token_rows):
                if i < len(token_models):
                    m = token_models[i]
                    p = shorten(m.get('provider', ''), 12)
                    mod = shorten(m.get('model', ''), 35)
                    p_fmt = str(m.get('prompt_fmt', '0'))
                    c_fmt = str(m.get('completion_fmt', '0'))
                    t_fmt = str(m.get('total_fmt', '0'))
                    calls = str(m.get('calls', '0'))

                    line_str = f"  {p:<12} | {mod:<35} | {p_fmt:<9} | {c_fmt:<8} | {t_fmt:<9} | {calls:<5}"
                    col = MAGENTA if p == 'openrouter' else (GREEN if p == 'kilo' else WHITE)
                    lines.append(row(line_str, col))
                else:
                    lines.append(row(''))
            lines.append(row('  ' + '-' * 62, DARK_CYAN))
        else:
            # --- FLEET VIEW ---
            log_start_row = 15
            if rows >= 38:
                lines.append(row('  ' + '-' * 62, DARK_CYAN))
                lines.append(row('  TOP MODEL TOKENS  [PRESS T FOR FULL BREAKDOWN]', CYAN))
                t_models = self.state.get('token_models', [])[:3]
                for tm in t_models:
                    line_str = f"   {tm.get('provider',''):<10} {shorten(tm.get('model',''), 30):<30} total:{tm.get('total_fmt',''):<8} (prompt:{tm.get('prompt_fmt','')}, comp:{tm.get('completion_fmt','')})"
                    lines.append(row(line_str, GRAY))
                log_start_row = 20

            lines.append(row('  ' + '-' * 62, DARK_CYAN))
            lines.append(row('  LIVE LOG', YELLOW))

            max_logs = 5
            if rows < (log_start_row + 14):
                max_logs = max(1, rows - (log_start_row + 10))

            for i in range(max_logs):
                line_str = ('  ' + self.logs[i]) if i < len(self.logs) else ''
                lines.append(row(line_str, GRAY))

            lines.append(row('  ' + '-' * 62, DARK_CYAN))
            lines.append(row('  SUB-AGENTS (ID | WORKSPACE | AGENT | MODEL | TASK | STATE)', YELLOW))

            ordered = sorted(self.thread_cache.values(), key=lambda t: 0 if t.get('state') == 'WORKING' else 1)
            max_sub_rows = MAX_THREADS
            if rows < 34:
                max_sub_rows = max(1, rows - (len(lines) + 2))

            for i in range(max_sub_rows):
                if i < len(ordered):
                    t = ordered[i]
                    sid = safe_sub(t.get('id', ''), 0, 12)
                    ws = shorten(t.get('workspace', ''), 12)
                    ag = shorten(t.get('agent', ''), 7)
                    mod = shorten(t.get('model', ''), 22)
                    task = shorten(t.get('title', ''), 24)
                    st = str(t.get('state', 'DONE'))

                    line_str = f"  {sid:<12} | {ws:<12} | {ag:<7} | {mod:<22} | {task:<24} [{st}]"
                    col = YELLOW if st == 'WORKING' else GRAY
                    lines.append(row(line_str, col))
                else:
                    lines.append(row(''))

            lines.append(row('  ' + '-' * 62, DARK_CYAN))

        # Render full frame with cursor home
        output = CURSOR_HOME + '\n'.join(lines[:rows - 1]) + '\n'
        sys.stdout.write(output)
        sys.stdout.flush()

    def run(self):
        sys.stdout.write(CLEAR_SCREEN + HIDE_CURSOR)
        sys.stdout.flush()

        key_reader = KeyReader()
        frame = 0

        try:
            self.refresh_status()
            while True:
                ch = key_reader.get_key()
                if ch:
                    if ch.lower() == 'q':
                        break
                    elif ch.lower() == 't':
                        self.view_mode = 'FLEET' if self.view_mode == 'TOKENS' else 'TOKENS'
                        sys.stdout.write(CLEAR_SCREEN)
                        sys.stdout.flush()

                if frame > 0 and (frame % REFRESH_EVERY) == 0:
                    self.refresh_status()

                self.draw(frame)

                if self.was_working:
                    frame += 2
                else:
                    frame += 1

                time.sleep(TICK_S)
        finally:
            key_reader.restore()
            sys.stdout.write(SHOW_CURSOR + "\n")
            print(f"{CYAN}  R.E.Y. monitor stopped. Stay nominal, stay in control.{RESET}\n")

if __name__ == '__main__':
    monitor = ReyMonitor()
    monitor.run()
