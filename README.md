# 🚀 OpenCode Swarm Portable Distribution Pack

A complete, self-contained, and portable package containing the **22-Agent OpenCode Swarm Team**, multi-model fallback chains, rate-limit acceleration patches, and 30+ bundled agent skills.

Designed to be cloned onto any machine and injected into any project in 1 command.

---

## 📦 What's Inside

```text
opencode-swarm-pack/
├── configs/
│   ├── opencode.jsonc            # Engine config (DeepSeek primary, plugins, direct execution)
│   ├── opencode-swarm.json       # Full 22-agent swarm team roster with turbo mode
│   ├── model-fallback.json       # Tiered fallback chains, 90s watchdog timeout, 60s cooldown
│   └── skill-routing.yaml        # Skill-to-agent mapping configuration
├── skills/                       # 30+ production skills bundled directly in the repo
├── patches/
│   ├── patch-opencode-binary.js  # Machine patch: clamps opencode.exe retry backoff to 3s
│   ├── patch-swarm-posix.js      # Machine patch: fixes Windows PowerShell false-positive parsing
│   └── patch-watchdog-timeout.js # Machine patch: installs 90s watchdog auto-abort & failover
├── install.ps1                   # Master installer for setting up a machine
├── inject.ps1                    # 1-Click injector for a specific repository
└── verify.ps1                    # Diagnostic and health check script
```

---

## ⚡ Setting Up on a Different / Fresh Machine

When you work on another machine (laptop, home PC, or server):

### Step 1: Clone This Repository
```powershell
git clone <YOUR-PRIVATE-REPO-URL> C:\Users\<YourUser>\opencode-swarm-pack
cd C:\Users\<YourUser>\opencode-swarm-pack
```

### Step 2: Run the Master Installer
```powershell
# Set up OpenCode globally on this machine:
.\install.ps1 -GlobalOnly
```
**What this does automatically:**
1. Checks that Node.js (v20+) is available.
2. Ensures the `opencode-swarm` and `@smart-coders-hq/opencode-model-fallback` plugins are installed.
3. Deploys the machine-global configuration into `~/.config/opencode/`.
4. Deploys all 30+ bundled skills into `~/.agents/skills/`.
5. Automatically applies all 3 runtime stability patches (3s retry clamp, PowerShell fix, 90s watchdog).

---

## 🎯 Injecting into a Specific Project

If you want a project to have its own dedicated `.opencode/` directory:

```powershell
.\inject.ps1 -Target "D:\Projects\MyOtherApp"
```

To also copy all 30+ skills into that project's `.agents/skills/`:
```powershell
.\inject.ps1 -Target "D:\Projects\MyOtherApp" -IncludeSkills
```

---

## 🔍 Diagnostic & Health Check

To verify that your OpenCode runtime, binary patches, and 22-agent team are functioning properly:

```powershell
.\verify.ps1
```

---

## 🛡️ Built-in Resilience Features

* **3-Second Rate-Limit Clamp**: Prevents 33s–60s upstream rate-limit waits by clamping OpenCode's retry backoff to 3 seconds.
* **90-Second Watchdog Failover**: If a model hangs or takes longer than 90 seconds without responding, the watchdog aborts and immediately replays the prompt on the next fallback model.
* **Windows PowerShell Write Detection**: Prevents Windows PowerShell commands (`Get-ChildItem`, etc.) from being falsely blocked by POSIX syntax parsers.
* **Tiered Fallback Chain**: Primary `deepseek-chat` with instant fallbacks to OpenCode Zen (`big-pickle`, `mimo-v2.5`, `ling-3.0-flash`) and OpenRouter free models (`gemma-4-31b`, `qwen-2.5-72b`, `llama-3.3-70b`).
