# 🚀 R.E.Y. // Runtime Execution & Yield Monitor - Opencode Monitoring CLI

A complete, self-contained, and portable distribution pack containing:
- 🖥️ **R.E.Y. CLI Model Fleet Monitor**: Real-time console HUD tracking OpenCode IDE state, active workspaces, subagents, and per-machine token yields.
- 🤖 **30-Model Free Fleet & Agent Team**: Zero-cost setup integrating Kilo, OpenCode Zen, OpenRouter (14+ free models), Groq, and Mistral with specialized agent routing (`@coder`, `@architect`, `@tester`, etc.).
- 🛡️ **Tiered Fallback Chains & Stability Patches**: Clamped rate-limit retry, 90s watchdog auto-failover, and Windows PowerShell execution fixes.
- 📦 **30+ Bundled Skills**: Modular skills for plans, frontend design, QA, code review, and systematic debugging.

Designed to be run instantly via `npx` or installed onto any machine in 1 command.

---

## ⚡ Instant Run (Zero Install via npx)

Launch the R.E.Y. live HUD directly in any terminal (Windows, macOS, or Linux):

```bash
npx rey-opencode-monitor
```

Or install globally:

```bash
npm install -g rey-opencode-monitor
rey
```

---

## 📦 What's Inside

```text
rey-opencode-monitor/
├── scripts/
│   ├── rey-monitor.ps1           # Real-time CLI HUD monitor with resize resilience
│   ├── rey-state.py              # Sub-50ms SQLite reader across all workspaces
│   ├── rey-launch.ps1            # Safe single-instance background launcher
│   ├── rey.cmd                   # Global command launcher (type 'rey' anywhere)
│   ├── jarvis-monitor.ps1        # Backwards-compatible alias
│   ├── jarvis-state.py           # Backwards-compatible alias
│   ├── jarvis-launch.ps1         # Backwards-compatible alias
│   └── jarvis.cmd                # Backwards-compatible alias
├── configs/
│   ├── opencode.json             # Root config with instructions & health check command
│   ├── opencode.jsonc            # 30-model free fleet, providers & agent team roster
│   ├── model-fallback.json       # Tiered fallback chains with watchdog timeout
│   └── skill-routing.yaml        # Skill-to-agent mapping configuration
├── instructions/
│   └── delegation.md             # Free fleet auto-delegation policies
├── commands/
│   └── fallback-status.md        # Command templates
├── skills/                       # 30+ production skills bundled directly
├── patches/                      # Runtime stability and retry patches
├── .env.example                  # Template for API keys (never commit real keys)
├── install.ps1                   # Master installer (non-destructive with .bak preservation)
├── inject.ps1                    # 1-Click injector for a specific repository
└── verify.ps1                    # Diagnostic and health check script
```

---

## ⚡ Setup on Another / Fresh Machine

### 🍎 On macOS & Linux (Terminal / zsh / bash)

```bash
# 1. Clone repository
git clone https://github.com/reyaustine/rey-opencode-monitor.git ~/rey-opencode-monitor
cd ~/rey-opencode-monitor

# 2. Set API keys (optional, add to ~/.zshrc or ~/.bashrc)
export OPENROUTER_API_KEY="sk-or-v1-..."
export GROQ_API_KEY="gsk_..."

# 3. Run the non-destructive installer
chmod +x install.sh
./install.sh

# 4. Launch R.E.Y. anywhere!
rey
```

---

### 🪟 On Windows (PowerShell)

```powershell
# 1. Clone repository
git clone https://github.com/reyaustine/rey-opencode-monitor.git "$env:USERPROFILE\rey-opencode-monitor"
cd "$env:USERPROFILE\rey-opencode-monitor"

# 2. Set API keys (User scope - persists across reboots)
[Environment]::SetEnvironmentVariable("OPENROUTER_API_KEY", "sk-or-v1-...", "User")
[Environment]::SetEnvironmentVariable("GROQ_API_KEY", "gsk_...", "User")

# 3. Run master installer
.\install.ps1 -GlobalOnly

# 4. Launch R.E.Y. anywhere!
rey
```

#### What the installer does automatically on both platforms:
1. **Clean & Non-Destructive**: Backs up any existing configuration files to `.bak.<timestamp>` before updating.
2. **Deploys Machine-Global Config**: Installs `opencode.json`, `opencode.jsonc`, `model-fallback.json`, and `skill-routing.yaml` into `~/.config/opencode/`.
3. **Installs R.E.Y. Monitor**: Deploys monitor scripts to `~/.config/opencode/scripts/` and registers the global `rey` command (and `jarvis` alias) in PATH.
4. **Installs Skills**: Copies 30+ production skills into `~/.agents/skills/`.
5. **Applies Stability Patches**: Applies runtime patches for retry backoff and watchdog failover.

---

## 🖥️ Launching R.E.Y. // Runtime Execution & Yield Monitor

Once installed, launch the monitor at any time from any directory:

```powershell
rey
```
*(Or type `jarvis` — both point to the R.E.Y. engine)*

### Monitor Features:
* **Live OpenCode IDE Telemetry**: Detects whether OpenCode desktop or headless is `ONLINE` or `OFFLINE`.
* **Cross-Workspace Awareness**: Tracks the active project workspace (e.g., `Ohana`, `HR-Sportfest-App`) and detects subagent threads from all repositories in real-time (<50ms via direct SQLite WAL read).
* **Token Usage Tracker (All-Time & Per-Model)**: Tracks aggregate tokens used on the machine (prompt, completion, cache read, cost) and displays full per-model breakdowns.
* **Unique Per Machine (`.gitignore`)**: Token telemetry data is saved locally to `~/.config/opencode/token-tracker.json` and gitignored in this repo so each machine retains its own independent usage stats without merge conflicts.
* **Interactive Views (<kbd>T</kbd>)**: Press <kbd>T</kbd> while the monitor is open to toggle instantly between `[FLEET / LIVE LOGS]` and `[TOKEN FLEET BREAKDOWN]`.
* **Resize Resilient**: Dynamic window dimension detection automatically scales rows, pads output, and prevents line-wrapping crashes when resizing or snapping terminal windows.

```text
==============================================================
 R.E.Y.  //  RUNTIME EXECUTION & YIELD MONITOR  [ STANDBY ] [ | ] [##########..........]
==============================================================
 opencode IDE  : ONLINE (PID 15540)
 workspace     : Ohana
 default model : kilo/kilo-auto/free
 small model   : opencode/big-pickle
 providers     : kilo, opencode, openrouter, groq, mistral, huggingface
 models visible: 30 allowlisted
 opencode      : 1.17.11
 active threads: 0
 activity      : IDLE (STANDBY)
 status        : ALL SYSTEMS NOMINAL
 tokens used   : 131.2M  (prompt: 9.5M | compl: 395k | cache: 121.1M)  [$0.1356]
 last refresh  : 11:22:54   (Q: quit | T: toggle model tokens)
--------------------------------------------------------------
TOKEN FLEET BREAKDOWN (TOTAL: 131.2M | COST: $0.1356)  [PRESS T FOR LOGS/FLEET]
PROVIDER     | MODEL                               | PROMPT    | COMPL    | TOTAL     | CALLS
--------------------------------------------------------------------------------------------
opencode     | muse-spark-1.2-contributor-free     | 3.7M      | 177.6k   | 56.1M     | 462
opencode     | muse-spark-1.3-contributor-free     | 1.2M      | 47.8k    | 41.5M     | 163
opencode     | mimo-v2.5-free                      | 1.5M      | 146.2k   | 18.8M     | 306
openrouter   | thinkingmachines/inkling:free       | 1.3M      | 6.5k     | 6.5M      | 109
kilo         | nex-agi/nex-n2.5-mini:free          | 423.8k    | 7.5k     | 3.1M      | 27
openrouter   | minimax/minimax-m3:free             | 304.8k    | 2.3k     | 2.4M      | 26
opencode     | big-pickle                          | 408.7k    | 5.0k     | 1.6M      | 17
openrouter   | qwen/qwen3-coder-flash              | 287.1k    | 425      | 501.5k    | 7
--------------------------------------------------------------
```

---

## 🤖 30-Model Free Fleet & Agent Team

The configuration whitelists **30 zero-cost models** across 6 providers:
- **Kilo Code**: `kilo/kilo-auto/free` (No API key required)
- **OpenCode Zen**: `big-pickle`, `ling-3.0-flash-fin-free`, `mimo-v2.5-free`, `muse-spark-1.2/1.3`, `nemotron-3-ultra-free`, `nemotron-3.5-lightning-free` (Built-in free models)
- **OpenRouter Free Models**: `openrouter/free` router, `nemotron-3.5-lightning:free`, `nemotron-3-ultra-550b:free`, `gemma-4-31b-it:free`, `north-mini-code:free`, `ling-3.0-flash-fin:free`, etc.
- **Groq Free Plan**: `llama-3.3-70b-versatile`, `gpt-oss-120b`, `gpt-oss-20b`, `qwen3.6-27b`, `qwen3.8-27b`
- **Mistral Free Credits**: `codestral-latest`, `mistral-small-4`

### Specialized Swarm Roster (`@mention`):
- `@orchestrator` → Lead Project Manager (`openrouter/free`)
- `@coder` → Deep algorithmic coding & refactoring (`north-mini-code:free`)
- `@explorer` → Quick patches, CSS tweaks & file inspection (`ling-3.0-flash-fin:free`)
- `@architect` → System architecture & repository analysis (`nemotron-3-ultra-550b:free`)
- `@tester` → Unit tests, TDD & validation (`nemotron-3.5-lightning:free`)
- `@reviewer` → Code review & QA checks (`nemotron-3-super-120b:free`)
- `@critic` → Critical analysis & stress-testing (`lfm-2.5-2.6b:free`)
- `@researcher` → Technical research & library discovery (`gemma-4-31b-it:free`)
- `@docs` → Documentation & inline specs (`laguna-xs-2.1:free`)
- `@designer` → UI/UX design & visual components (`inkling:free`)

---

## 🎯 Injecting into a Specific Project

To equip a project with its own `.opencode/` workspace configuration:

```powershell
.\inject.ps1 -Target "D:\Projects\MyProject" -IncludeSkills
```

---

## 🔍 Diagnostic Verification

Verify CLI health, runtime patches, and agent discovery at any time:

```powershell
.\verify.ps1
```
