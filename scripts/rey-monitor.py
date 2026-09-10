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
import random
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
CHASSIS = "\033[90m"
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

def get_robot_lines(frame, is_working, task_title, health_ok, elapsed_s=0, punch_active=False, punch_tick=0):
    spinners = ["|", "/", "-", "\\"]
    mouths = ["▄  ", " ▄ ", "  ▄", " ▄ "]

    # 1. Frustration Punch Sequence (when task running 10-20+ mins or triggered)
    if is_working and punch_active:
        glow = RED
        if punch_tick < 5:
            # Phase 1: Winding up furious
            mood = 'ANGRY!'
            ant, lb, rb, le, re, mth = '♨', '╲', '╱', 'ಠ', 'ಠ', '▃▃▃'
            status_text = '>10m! So frustrated!! '
            st_trunc = status_text[:22].ljust(22)
            mth_center = mth.center(3)
            return [
                f"{CHASSIS}┌── {glow}R.E.Y. BOT{CHASSIS} ─ [{glow}{mood:<7}{CHASSIS}]─┐{RESET}",
                f"{CHASSIS}│         ╭───╮            │{RESET}",
                f"{CHASSIS}│         │ {glow}{ant}{CHASSIS} │            │{RESET}",
                f"{CHASSIS}│       ╭─┴───┴─╮          │{RESET}",
                f"{CHASSIS}│      ╱  *GRRR* ╲         │{RESET}",
                f"{CHASSIS}│     │   {glow}{lb}   {rb}{CHASSIS}   │        │{RESET}",
                f"{CHASSIS}│     │   {glow}{le}   {re}{CHASSIS}   │        │{RESET}",
                f"{CHASSIS}│     │           │        │{RESET}",
                f"{CHASSIS}│     │    {glow}{mth_center}{CHASSIS}    │        │{RESET}",
                f"{CHASSIS}│      ╲  *FIST* ╱         │{RESET}",
                f"{CHASSIS}│       ╰───────╯          │{RESET}",
                f"{CHASSIS}└─ {WHITE}{st_trunc}{CHASSIS} ─┘{RESET}"
            ]
        elif punch_tick < 15:
            # Phase 2: THE SCREEN PUNCH!
            mood = 'PUNCH! '
            status_text = '*POW!* FINISH TASK!   '
            st_trunc = status_text[:22].ljust(22)
            return [
                f"{CHASSIS}┌── {glow}R.E.Y. BOT{CHASSIS} ─ [{glow}{mood:<7}{CHASSIS}]─┐{RESET}",
                f"{CHASSIS}│         ╭───╮            │{RESET}",
                f"{CHASSIS}│         │ {glow}♨{CHASSIS} │            │{RESET}",
                f"{CHASSIS}│       ╭─┴───┴─╮          │{RESET}",
                f"{CHASSIS}│      ╱ *POW!!* ╲         │{RESET}",
                f"{CHASSIS}│     │   {glow}╲   ╱{CHASSIS}   │        │{RESET}",
                f"{CHASSIS}│     │  {glow}[==👊==]{CHASSIS} │        │{RESET}",
                f"{CHASSIS}│     │   {glow}*BAM!*{CHASSIS}  │        │{RESET}",
                f"{CHASSIS}│     │    {glow}▃▃▃{CHASSIS}    │        │{RESET}",
                f"{CHASSIS}│      ╲         ╱         │{RESET}",
                f"{CHASSIS}│       ╰───────╯          │{RESET}",
                f"{CHASSIS}└─ {WHITE}{st_trunc}{CHASSIS} ─┘{RESET}"
            ]
        else:
            # Phase 3: Cooldown / Panting
            mood = 'EXHAUST'
            ant, lb, rb, le, re, mth = '~', '╱', '╲', '•', '•', mouths[frame % 4]
            glow = YELLOW
            status_text = 'Phew... hurry it up!  '
            st_trunc = status_text[:22].ljust(22)
            mth_center = mth.center(3)
            return [
                f"{CHASSIS}┌── {glow}R.E.Y. BOT{CHASSIS} ─ [{glow}{mood:<7}{CHASSIS}]─┐{RESET}",
                f"{CHASSIS}│         ╭───╮            │{RESET}",
                f"{CHASSIS}│         │ {glow}{ant}{CHASSIS} │            │{RESET}",
                f"{CHASSIS}│       ╭─┴───┴─╮          │{RESET}",
                f"{CHASSIS}│      ╱         ╲         │{RESET}",
                f"{CHASSIS}│     │   {glow}{lb}   {rb}{CHASSIS}   │        │{RESET}",
                f"{CHASSIS}│     │   {glow}{le}   {re}{CHASSIS}   │        │{RESET}",
                f"{CHASSIS}│     │           │        │{RESET}",
                f"{CHASSIS}│     │    {glow}{mth_center}{CHASSIS}    │        │{RESET}",
                f"{CHASSIS}│      ╲         ╱         │{RESET}",
                f"{CHASSIS}│       ╰───────╯          │{RESET}",
                f"{CHASSIS}└─ {WHITE}{st_trunc}{CHASSIS} ─┘{RESET}"
            ]

    # 2. Standard Task & Idle Expression Logic
    if not health_ok:
        ant, lb, rb, le, re, mth = "☡", "╲", "╱", "✖", "✖", "▃▃▃"
        glow, mood, status_text = RED, "ALERT", "Check error log!"
    elif is_working:
        t_low = (task_title or "").lower()
        if any(k in t_low for k in ["fix", "bug", "issue", "error"]):
            ant, lb, rb, le, re, mth = "⚡", "╲", "╱", "•", "•", "╰━╯"
            glow, mood, status_text = YELLOW, "DEBUG", "Fixing issue..."
        elif any(k in t_low for k in ["test", "verify", "qa", "check"]):
            ant, lb, rb, le, re, mth = "⚇", "─", "─", "◎", "◎", mouths[frame % 4]
            glow, mood, status_text = CYAN, "TESTING", "Verifying..."
        elif any(k in t_low for k in ["build", "code", "refactor"]):
            ant, lb, rb, le, re, mth = "⚙", "─", "─", "[", "]", "━━━"
            glow, mood, status_text = GREEN, "CODING", "Synthesizing..."
        elif any(k in t_low for k in ["review", "architect", "research"]):
            ant, lb, rb, le, re, mth = "⌖", "╭", "─", "◉", "◯", "───"
            glow, mood, status_text = MAGENTA, "ANALYZE", "Deep thinking..."
        else:
            ant, lb, rb, le, re, mth = spinners[frame % 4], "─", "╱", "◯", "◉", mouths[frame % 4]
            glow, mood, status_text = YELLOW, "THINKING", "Processing task..."
    else:
        # Standby cycles: 6 distinct living moods (25 ticks each = ~5 seconds per mood)
        cycle = (frame // 25) % 6
        sub_tick = frame % 25
        if cycle == 0:
            # Looking around
            ant, lb, rb, mth, glow, mood = "⚇", "─", "─", "───", CYAN, "LOOK"
            if sub_tick < 7:
                le, re, status_text = "◖", "◖", "Scanning left..."
            elif sub_tick < 14:
                le, re, status_text = "◉", "◉", "Standing by..."
            elif sub_tick < 20:
                le, re, status_text = "◗", "◗", "Scanning right..."
            else:
                le, re, status_text = "◉", "◉", "Standing by..."
        elif cycle == 1:
            # YAWNING SEQUENCE!
            mood = "YAWN"
            glow = YELLOW
            ant = "~"
            if sub_tick < 8:
                lb, rb, le, re, mth = "─", "─", "˘", "˘", " - "
                status_text = "Feeling drowsy...     "
            elif sub_tick < 18:
                # Big wide yawn!
                lb, rb, le, re, mth = "╭", "╮", ">", "<", "╰◯╯"
                status_text = "Yaaaaawn... *stretch* "
            else:
                # Post yawn sigh
                lb, rb, le, re, mth = "─", "─", "─", "─", " ˘ "
                status_text = "*sigh* so sleepy...   "
        elif cycle == 2:
            # DEEP SLEEP / SNOOZING
            mood = "SLEEP"
            glow = DIM
            zs = ["z", "Z", "z", "Z"]
            ant = zs[(frame // 6) % 4]
            lb, rb = "─", "─"
            if (sub_tick % 10) < 5:
                le, re, mth = "─", "─", "───"
                status_text = "zzz... snoozing...    "
            else:
                le, re, mth = "˘", "˘", " ˘ "
                status_text = "zzz... dreaming code  "
        elif cycle == 3:
            # Curious
            ant, lb, rb, le, re, mth = "⚇", "^", "─", "◖", "◉", " ▱ "
            glow, mood, status_text = MAGENTA, "CURIOUS", "Awaiting task..."
        elif cycle == 4:
            # Happy
            ant, lb, rb, le, re, mth = "☼", "╭", "╮", "^", "^", "╰━╯"
            glow, mood, status_text = GREEN, "HAPPY", "All nominal!"
        else:
            # Playful wink
            ant, lb, rb, mth = "★", "╭", "─", "╰━╯"
            le, re = "^", ("◉" if (frame % 10 < 7) else "^")
            glow, mood, status_text = GREEN, "WINK", "Ready for work!"

    st_trunc = (status_text[:22]).ljust(22)
    mth_center = mth.center(3)

    return [
        f"{CHASSIS}┌── {glow}R.E.Y. BOT{CHASSIS} ─ [{glow}{mood:<7}{CHASSIS}]─┐{RESET}",
        f"{CHASSIS}│         ╭───╮            │{RESET}",
        f"{CHASSIS}│         │ {glow}{ant}{CHASSIS} │            │{RESET}",
        f"{CHASSIS}│       ╭─┴───┴─╮          │{RESET}",
        f"{CHASSIS}│      ╱         ╲         │{RESET}",
        f"{CHASSIS}│     │   {glow}{lb}   {rb}{CHASSIS}   │        │{RESET}",
        f"{CHASSIS}│     │   {glow}{le}   {re}{CHASSIS}   │        │{RESET}",
        f"{CHASSIS}│     │           │        │{RESET}",
        f"{CHASSIS}│     │    {glow}{mth_center}{CHASSIS}    │        │{RESET}",
        f"{CHASSIS}│      ╲         ╱         │{RESET}",
        f"{CHASSIS}│       ╰───────╯          │{RESET}",
        f"{CHASSIS}└─ {WHITE}{st_trunc}{CHASSIS} ─┘{RESET}"
    ]

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
        self.working_start_time = None
        self.punch_active = False
        self.punch_tick = 0
        self.last_punch_frame = -999
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
        self.last_health_check = time.time()
        self.add_log('R.E.Y. monitor initialized (cross-platform)')

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

            if db_data and db_data.get('ok'):
                self.state['thread_count'] = int(db_data.get('active_threads', 0))
                self.state['workspace'] = str(db_data.get('current_workspace', '-'))
                if db_data.get('override_model'):
                    self.state['default_model'] = f"{db_data['override_model']} [LOCKED]"

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
                    if sid == 'ses_watchdog':
                        if curr_state == 'WORKING' and prev_state != 'WORKING':
                            self.add_log('[HEALTH] fleet check started')
                        if curr_state == 'DONE' and prev_state == 'WORKING':
                            self.add_log(f"[HEALTH] {shorten(s.get('title', ''), 40)}")
                    else:
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
                self.add_log('db query err: ' + shorten(db_data.get('error', '') if db_data else 'none', 35))
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
            self.working_start_time = time.time()
            self.punch_active = False
            self.punch_tick = 0
        if not working and self.was_working:
            self.add_log('fleet idle - all done')
            self.working_start_time = None
            self.punch_active = False
            self.punch_tick = 0
        if working and not self.working_start_time:
            self.working_start_time = time.time()
        self.was_working = working

        if working:
            mins = int((time.time() - self.working_start_time) / 60) if self.working_start_time else 0
            if mins > 0:
                self.state['activity'] = f"THINKING ({mins}m elapsed)"
            else:
                self.state['activity'] = 'THINKING'
        elif 'ONLINE' in self.state['ide_status']:
            self.state['activity'] = 'IDLE (STANDBY)'
        else:
            self.state['activity'] = 'IDLE'

        if ok:
            mh = db_data.get('model_health') if ('db_data' in locals() and db_data) else None
            if mh:
                if mh.get('running'):
                    self.state['health'] = 'CHECKING FLEET HEALTH...'
                elif mh.get('unresponsive_count', 0) > 0:
                    self.state['health'] = f"DEGRADED ({mh['unresponsive_count']} UNRESPONSIVE)"
                elif mh.get('new_models_count', 0) > 0:
                    self.state['health'] = f"NOMINAL (+{mh['new_models_count']} NEW FREE)"
                else:
                    self.state['health'] = 'ALL SYSTEMS NOMINAL'
            else:
                self.state['health'] = 'ALL SYSTEMS NOMINAL'
        else:
            self.state['health'] = 'DEGRADED - CHECK LOG'
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

        health_color = GREEN if 'NOMINAL' in self.state['health'] else (YELLOW if 'CHECKING' in self.state['health'] else RED)
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
        sys_items = [
            (f"   opencode IDE  : {self.state['ide_status']}", self.state['ide_color']),
            (f"   workspace     : {self.state['workspace']}", WHITE),
            (f"   default model : {self.state['default_model']}", WHITE),
            (f"   small model   : {self.state['small_model']}", WHITE),
            (f"   providers     : {self.state['providers']}", WHITE),
            (f"   models visible: {self.state['model_count']}", WHITE),
            (f"   opencode      : {self.state['version']}", WHITE),
            (f"   active threads: {self.state['thread_count']}", MAGENTA),
            (f"   activity      : {self.state['activity']}", act_color),
            (f"   status        : {self.state['health']}", health_color),
            (f"   tokens used   : {self.state['tokens_total']}  (prompt: {self.state['tokens_prompt']} | compl: {self.state['tokens_comp']} | cache: {self.state['tokens_cache']})  [{self.state['tokens_cost']}]", CYAN),
            (f"   last refresh  : {self.state['last_refresh']}  (Q: quit | T: tokens | O: override | H: health)", GRAY),
        ]

        if cols >= 95:
            active_task_title = ""
            for t in self.thread_cache.values():
                if t.get('state') == 'WORKING':
                    active_task_title = t.get('title', '')
                    break
            health_ok = (self.state['health'] == 'ALL SYSTEMS NOMINAL')

            elapsed_s = (time.time() - self.working_start_time) if (working and self.working_start_time) else 0

            # Frustration Punch Trigger:
            # When task has run for 10-20+ minutes (elapsed_s >= 600)
            # Or task title has [punch] for testing
            if working and (elapsed_s >= 600 or any(k in (active_task_title.lower()) for k in ['[punch]', 'massive', 'heavy'])):
                if not self.punch_active:
                    if (frame - self.last_punch_frame) > 150:  # at least 30s cooldown
                        if random.random() < 0.08 or '[punch]' in active_task_title.lower():
                            self.punch_active = True
                            self.punch_tick = 0
                            self.last_punch_frame = frame
                else:
                    self.punch_tick += 1
                    if self.punch_tick > 20:
                        self.punch_active = False
            else:
                self.punch_active = False

            robot_lines = get_robot_lines(frame, working, active_task_title, health_ok, elapsed_s, self.punch_active, self.punch_tick)

            for idx, (txt, col) in enumerate(sys_items):
                left_part = (txt[:65]).ljust(65)
                c_left = f"{col}{left_part}{RESET}"
                bot_line = robot_lines[idx]
                trailing = ' ' * max(0, max_w - 95)
                lines.append(f"{c_left}  {bot_line}{trailing}")
        else:
            for txt, col in sys_items:
                lines.append(row(txt, col))

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
                    elif ch.lower() == 'o':
                        key_reader.restore()
                        sys.stdout.write(SHOW_CURSOR + CLEAR_SCREEN)
                        sys.stdout.flush()
                        try:
                            import rey_override
                            rey_override.interactive_menu()
                        except Exception:
                            import subprocess
                            subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "rey-override.py")])
                        key_reader = KeyReader()
                        sys.stdout.write(HIDE_CURSOR + CLEAR_SCREEN)
                        sys.stdout.flush()
                        self.refresh_status()
                    elif ch.lower() == 'h':
                        key_reader.restore()
                        sys.stdout.write(SHOW_CURSOR + CLEAR_SCREEN)
                        sys.stdout.flush()
                        try:
                            import rey_health
                            rey_health.run_health_check(quiet=False)
                        except Exception:
                            import subprocess
                            subprocess.run([sys.executable, os.path.join(SCRIPT_DIR, "rey-health.py")])
                        print("\n  Press Enter to return to R.E.Y. Monitor...")
                        try:
                            input()
                        except Exception:
                            pass
                        key_reader = KeyReader()
                        sys.stdout.write(HIDE_CURSOR + CLEAR_SCREEN)
                        sys.stdout.flush()
                        self.last_health_check = time.time()
                        self.refresh_status()

                # 30-minute background health & discovery watchdog
                if (time.time() - self.last_health_check) >= 1800:
                    self.last_health_check = time.time()
                    import subprocess
                    health_script = os.path.join(SCRIPT_DIR, "rey-health.py")
                    if os.path.exists(health_script):
                        subprocess.Popen([sys.executable, health_script, "--quiet"])
                        self.add_log("[HEALTH] 30m background watchdog started")

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
