# BYOK Initial Setup & Team Roster — Implementation Plan

> **For agentic workers:** Use subagent-driven-development or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a first-run interactive setup wizard to the R.E.Y. CLI that lets users configure their AI provider API keys (BYOK) and generates an optimized team roster assignment based on their selected providers.

**Architecture:** A new PowerShell script (`rey-setup.ps1`) handles the interactive first-run wizard. The main `rey-monitor.ps1` checks for a config marker file (`setup-complete.json`) on launch and routes to the setup wizard if absent. Setup data is persisted to `byok-config.json` and used by a Python helper (`rey-roster.py`) to generate the team roster suggestion.

**Tech Stack:** PowerShell 5.1 (interactive TUI), Python 3.x (roster generation logic), JSON config files

---

## Global Constraints

- PowerShell 5.1 compatibility (no `Read-Host -AsSecureString`, use `[System.Security.SecureString]` directly)
- UTF-8 BOM encoding for all `.ps1` files (required for box-drawing characters on Windows PS 5.1)
- No external module dependencies — pure built-in cmdlets only
- All config files stored in `~/.config/opencode/`
- API keys stored in `.env` file (never in JSON — `.env` is already gitignored)

---

## File Structure

| File | Responsibility |
|------|---------------|
| `scripts/rey-setup.ps1` | **NEW** — Interactive first-run wizard (provider selection + key input) |
| `scripts/rey-monitor.ps1` | **MODIFY** — Add setup check on launch, add `S` key for re-run setup |
| `scripts/rey-roster.py` | **NEW** — Generates optimal team roster from BYOK config |
| `scripts/rey-roster.ps1` | **NEW** — PowerShell wrapper to call roster.py and display results |
| `setup-complete.json` | **NEW** — Marker file created after setup finishes |
| `byok-config.json` | **NEW** — Stores which providers are enabled + model preferences |
| `.env` | **MODIFY** — Add API keys (OPENROUTER_API_KEY, GROQ_API_KEY, GEMINI_API_KEY, ANTHROPIC_API_KEY, OPENAI_API_KEY) |

---

### Task 1: Create `byok-config.json` Schema & Setup Marker

**Files:**
- Create: `C:\Users\rey.echavez\.config\opencode\byok-config.json`
- Create: `C:\Users\rey.echavez\.config\opencode\setup-complete.json`

**Interfaces:**
- Produces: Config schema that `rey-setup.ps1` writes and `rey-monitor.ps1` reads

- [ ] **Step 1: Create the BYOK config template**

```json
{
  "version": 1,
  "setup_date": "",
  "providers": {
    "openrouter": { "enabled": false, "key_ref": "OPENROUTER_API_KEY" },
    "groq": { "enabled": false, "key_ref": "GROQ_API_KEY" },
    "gemini": { "enabled": false, "key_ref": "GEMINI_API_KEY" },
    "claude": { "enabled": false, "key_ref": "ANTHROPIC_API_KEY" },
    "chatgpt": { "enabled": false, "key_ref": "OPENAI_API_KEY" }
  },
  "roster": {
    "coder": "",
    "reviewer": "",
    "planner": "",
    "researcher": "",
    "debugger": ""
  }
}
```

- [ ] **Step 2: Create the setup-complete marker (empty placeholder, created by setup wizard on completion)**

Create an empty file `C:\Users\rey.echavez\.config\opencode\.setup-complete` (dotfile marker).

- [ ] **Step 3: Add `.setup-complete` to tracked files (not gitignored)**

Verify `.gitignore` does not exclude `.setup-complete`. This file should NOT be committed — it's machine-specific. Add `*setup-complete*` and `*byok-config*` to `.gitignore`.

- [ ] **Step 4: Commit**

```bash
git add .gitignore
git commit -m "chore(gitignore): exclude machine-specific setup and BYOK config files"
```

---

### Task 2: Build Interactive Provider Selection Screen

**Files:**
- Create: `C:\Users\rey.echavez\.config\opencode\scripts\rey-setup.ps1`

**Interfaces:**
- Produces: `byok-config.json` with enabled providers marked
- Produces: `.env` entries for API keys

- [ ] **Step 1: Create the setup script with UTF-8 BOM and header**

```powershell
#Requires -Version 5.1
<#
.SYNOPSIS
  R.E.Y. // BYOK Initial Setup Wizard
  Interactive first-run configuration for AI provider API keys.
  Press Enter to confirm, Arrow keys to navigate, Space to toggle.
#>
param()

# UTF-8 BOM for PowerShell 5.1 compatibility
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$ErrorActionPreference = 'Stop'
```

- [ ] **Step 2: Define provider registry with display metadata**

```powershell
$providers = @(
  @{ Id = 'openrouter'; Label = 'OpenRouter';  Desc = '200+ models, free tier, unified gateway';     Icon = '🌐'; KeyEnv = 'OPENROUTER_API_KEY';  KeyHint = 'sk-or-v1-...' },
  @{ Id = 'groq';       Label = 'Groq';        Desc = 'Ultra-fast inference (Llama, Mixtral)';      Icon = '⚡'; KeyEnv = 'GROQ_API_KEY';       KeyHint = 'gsk_...' },
  @{ Id = 'gemini';     Label = 'Google Gemini'; Desc = 'Gemini 2.5 Flash/Pro, generous free tier';  Icon = '🔮'; KeyEnv = 'GEMINI_API_KEY';     KeyHint = 'AIza...' },
  @{ Id = 'claude';     Label = 'Anthropic Claude'; Desc = 'Claude Sonnet/Opus, best reasoning';    Icon = '🧠'; KeyEnv = 'ANTHROPIC_API_KEY';  KeyHint = 'sk-ant-...' },
  @{ Id = 'chatgpt';    Label = 'OpenAI ChatGPT'; Desc = 'GPT-4o, o1, o3 models';                  Icon = '🤖'; KeyEnv = 'OPENAI_API_KEY';     KeyHint = 'sk-...' }
)
```

- [ ] **Step 3: Build the provider selection TUI with checkbox toggle**

The selection screen should:
1. Show ASCII art header: `R.E.Y. // BYOK SETUP — STEP 1 OF 2`
2. List all 5 providers with `[X]` / `[ ]` checkboxes
3. Arrow keys navigate, Space toggles, Enter confirms
4. Show provider descriptions and key format hints
5. Minimum 1 provider must be selected

```powershell
function Show-ProviderSelection {
  param($providers, [array]$selected)

  $cursorIdx = 0

  while ($true) {
    # Clear and draw header
    try { [Console]::Clear() } catch { Clear-Host }

    $header = @'
  ============================================================
   R.E.Y. // BYOK SETUP — STEP 1 OF 2: SELECT PROVIDERS
  ============================================================

  Toggle providers with [SPACE], navigate with [↑/↓], confirm with [ENTER]
  At least 1 provider required. Keys are stored in .env (never committed).

'@
    Write-Host $header -ForegroundColor Cyan

    for ($i = 0; $i -lt $providers.Count; $i++) {
      $p = $providers[$i]
      $isSelected = $selected -contains $p.Id
      $check = if ($isSelected) { '[X]' } else { '[ ]' }
      $arrow = if ($i -eq $cursorIdx) { ' ► ' } else { '   ' }
      $color = if ($i -eq $cursorIdx) { 'Yellow' } else { 'White' }

      Write-Host ("{0}{1} {2} {3}" -f $arrow, $check, $p.Icon, $p.Label) -ForegroundColor $color -NoNewline
      Write-Host ("  {0}" -f $p.Desc) -ForegroundColor DarkGray
      Write-Host ("         Key format: {0}  |  Env: {1}" -f $p.KeyHint, $p.KeyEnv) -ForegroundColor DarkGray
    }

    Write-Host ""
    Write-Host "  Press [ENTER] to continue →" -ForegroundColor Green

    # Input handling
    $key = [Console]::ReadKey($true)
    switch ($key.Key) {
      'UpArrow'   { if ($cursorIdx -gt 0) { $cursorIdx-- } }
      'DownArrow' { if ($cursorIdx -lt ($providers.Count - 1)) { $cursorIdx++ } }
      'Spacebar' {
        $pid = $providers[$cursorIdx].Id
        if ($selected -contains $pid) {
          $selected = @($selected | Where-Object { $_ -ne $pid })
        } else {
          $selected += $pid
        }
      }
      'Enter' {
        if ($selected.Count -gt 0) { return $selected }
        Write-Host "  ! Select at least one provider" -ForegroundColor Red
        Start-Sleep -Seconds 1
      }
    }
  }
}
```

- [ ] **Step 4: Test the selection screen runs**

Run: `pwsh scripts/rey-setup.ps1` (or `powershell scripts/rey-setup.ps1`)
Expected: Interactive checkbox UI appears, can toggle providers with Space, navigates with arrows

---

### Task 3: Build API Key Input Screen

**Files:**
- Modify: `C:\Users\rey.echavez\.config\opencode\scripts\rey-setup.ps1` (append)

**Interfaces:**
- Consumes: Array of selected provider IDs from Task 2
- Produces: `.env` file with API key entries

- [ ] **Step 1: Add the key input function**

```powershell
function Show-KeyInput {
  param($providers, [array]$selectedIds)

  $selected = $providers | Where-Object { $selectedIds -contains $_.Id }
  $keys = @{}

  foreach ($p in $selected) {
    try { [Console]::Clear() } catch { Clear-Host }

    Write-Host ""
    Write-Host "  ============================================================" -ForegroundColor Cyan
    Write-Host "   R.E.Y. // BYOK SETUP — API KEY INPUT" -ForegroundColor Cyan
    Write-Host "  ============================================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "  Provider: $($p.Icon) $($p.Label)" -ForegroundColor Yellow
    Write-Host "  $($p.Desc)" -ForegroundColor DarkGray
    Write-Host ""
    Write-Host "  Paste your API key and press [ENTER]" -ForegroundColor White
    Write-Host "  (or press [ENTER] to skip this provider)" -ForegroundColor DarkGray
    Write-Host "  Key format hint: $($p.KeyHint)" -ForegroundColor DarkGray
    Write-Host ""

    # Read key securely (mask input)
    $secureKey = Read-Host "  $($p.KeyEnv)" -AsSecureString
    # Convert SecureString to plain text for .env storage
    $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    $plainKey = [System.Runtime.InteropServices.Marshal]::PtrToStringAuto($bstr)
    [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)

    if (-not [string]::IsNullOrWhiteSpace($plainKey)) {
      $keys[$p.KeyEnv] = $plainKey.Trim()
      Write-Host "  [OK] Key saved" -ForegroundColor Green
    } else {
      Write-Host "  [SKIP] No key provided" -ForegroundColor Yellow
    }
    Start-Sleep -Milliseconds 500
  }

  return $keys
}
```

- [ ] **Step 2: Add the .env writer function**

```powershell
function Save-EnvKeys {
  param([hashtable]$keys)

  $confDir = if ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { Join-Path $HOME '.config\opencode' }
  $envPath = Join-Path $confDir '.env'

  # Read existing .env to preserve other entries
  $existingLines = @()
  if (Test-Path -LiteralPath $envPath) {
    $existingLines = Get-Content -LiteralPath $envPath -Encoding UTF8
  }

  # Remove old entries for keys we're about to write
  $envKeys = @($keys.Keys)
  $filtered = $existingLines | Where-Object {
    $line = $_.Trim()
    if ([string]::IsNullOrWhiteSpace($line)) { return $true }
    if ($line.StartsWith('#')) { return $true }
    foreach ($k in $envKeys) {
      if ($line -match "^$k=") { return $false }
    }
    return $true
  }

  # Append new key entries
  $newLines = @()
  foreach ($kv in $keys.GetEnumerator()) {
    $newLines += "$($kv.Key)=$($kv.Value)"
  }

  $allLines = @($filtered) + @($newLines) | Where-Object { $_ -ne $null }
  $allLines | Set-Content -Path $envPath -Encoding UTF8
}
```

- [ ] **Step 3: Test key input screen**

Run: `pwsh scripts/rey-setup.ps1` → select providers → confirm
Expected: For each selected provider, a key input prompt appears. Keys are saved to `.env`.

---

### Task 4: Build Team Roster Generator

**Files:**
- Create: `C:\Users\rey.echavez\.config\opencode\scripts\rey-roster.py`

**Interfaces:**
- Consumes: `byok-config.json` (which providers are enabled)
- Produces: Roster assignment JSON to stdout (consumed by PowerShell wrapper)

- [ ] **Step 1: Create the Python roster generator**

```python
#!/usr/bin/env python3
"""R.E.Y. Team Roster Generator — assigns optimal models to agent roles based on BYOK config."""

import json
import os
import sys
from pathlib import Path
from datetime import datetime

CONFIG_DIR = Path.home() / '.config' / 'opencode'
BYOK_CONFIG = CONFIG_DIR / 'byok-config.json'

# Provider -> model mapping (best model per role per provider)
ROSTER_RULES = {
    'openrouter': {
        'coder':     {'model': 'deepseek/deepseek-chat',            'reason': 'Best code generation value'},
        'reviewer':  {'model': 'anthropic/claude-sonnet-4',         'reason': 'Thorough code review'},
        'planner':   {'model': 'anthropic/claude-sonnet-4',         'reason': 'Strong architectural planning'},
        'researcher':{'model': 'google/gemini-2.5-flash',           'reason': 'Fast research with large context'},
        'debugger':  {'model': 'deepseek/deepseek-r1',              'reason': 'Chain-of-thought debugging'},
    },
    'groq': {
        'coder':     {'model': 'llama-3.3-70b-versatile',          'reason': 'Fast code generation'},
        'reviewer':  {'model': 'llama-3.3-70b-versatile',          'reason': 'Quick review cycles'},
        'planner':   {'model': 'llama-3.3-70b-versatile',          'reason': 'Rapid planning iterations'},
        'researcher':{'model': 'llama-3.1-8b-instant',             'reason': 'Blazing fast research'},
        'debugger':  {'model': 'llama-3.3-70b-versatile',          'reason': 'Fast debugging loops'},
    },
    'gemini': {
        'coder':     {'model': 'gemini-2.5-flash',                 'reason': 'Fast, capable coding'},
        'reviewer':  {'model': 'gemini-2.5-pro',                   'reason': 'Deep review with large context'},
        'planner':   {'model': 'gemini-2.5-pro',                   'reason': 'Strong planning with 1M context'},
        'researcher':{'model': 'gemini-2.5-flash',                 'reason': 'Fast research, huge context window'},
        'debugger':  {'model': 'gemini-2.5-flash',                 'reason': 'Quick debug iterations'},
    },
    'claude': {
        'coder':     {'model': 'claude-sonnet-4-20250514',         'reason': 'Best-in-class code generation'},
        'reviewer':  {'model': 'claude-sonnet-4-20250514',         'reason': 'Thorough, nuanced review'},
        'planner':   {'model': 'claude-opus-4-20250514',           'reason': 'Deep architectural thinking'},
        'researcher':{'model': 'claude-sonnet-4-20250514',         'reason': 'Comprehensive research'},
        'debugger':  {'model': 'claude-sonnet-4-20250514',         'reason': 'Systematic root cause analysis'},
    },
    'chatgpt': {
        'coder':     {'model': 'gpt-4.1',                          'reason': 'Strong coding across languages'},
        'reviewer':  {'model': 'o3',                                'reason': 'Reasoning-heavy review'},
        'planner':   {'model': 'o3',                                'reason': 'Strategic planning'},
        'researcher':{'model': 'gpt-4.1-mini',                     'reason': 'Fast, affordable research'},
        'debugger':  {'model': 'o3',                                'reason': 'Deep reasoning for hard bugs'},
    },
}

# Priority order for fallback (when multiple providers available)
ROLE_PRIORITY = ['claude', 'chatgpt', 'openrouter', 'gemini', 'groq']

def generate_roster(byok_config):
    enabled = [pid for pid, p in byok_config.get('providers', {}).items() if p.get('enabled')]

    if not enabled:
        return {'error': 'No providers enabled', 'roster': {}}

    roster = {}
    roles = ['coder', 'reviewer', 'planner', 'researcher', 'debugger']

    for role in roles:
        assigned = False
        for provider in ROLE_PRIORITY:
            if provider in enabled and provider in ROSTER_RULES:
                if role in ROSTER_RULES[provider]:
                    info = ROSTER_RULES[provider][role]
                    roster[role] = {
                        'provider': provider,
                        'model': info['model'],
                        'reason': info['reason'],
                    }
                    assigned = True
                    break
        if not assigned:
            # Fallback: use first enabled provider
            for provider in enabled:
                if provider in ROSTER_RULES and role in ROSTER_RULES[provider]:
                    info = ROSTER_RULES[provider][role]
                    roster[role] = {
                        'provider': provider,
                        'model': info['model'],
                        'reason': info['reason'],
                    }
                    break

    return {
        'ok': True,
        'generated_at': datetime.now().isoformat(),
        'enabled_providers': enabled,
        'roster': roster
    }

if __name__ == '__main__':
    try:
        if not BYOK_CONFIG.exists():
            print(json.dumps({'error': 'byok-config.json not found'}))
            sys.exit(1)

        config = json.loads(BYOK_CONFIG.read_text(encoding='utf-8'))
        result = generate_roster(config)
        print(json.dumps(result, indent=2))
    except Exception as e:
        print(json.dumps({'error': str(e)}))
        sys.exit(1)
```

- [ ] **Step 2: Test roster generation**

Run: `python scripts/rey-roster.py`
Expected: JSON output with roster assignments (may show error if byok-config.json doesn't exist yet — that's OK)

---

### Task 5: Build Team Roster Display Screen (PowerShell)

**Files:**
- Create: `C:\Users\rey.echavez\.config\opencode\scripts\rey-roster.ps1`

**Interfaces:**
- Consumes: Output from `rey-roster.py`
- Produces: Interactive roster display with accept/modify options

- [ ] **Step 1: Create the roster display script**

```powershell
#Requires -Version 5.1
<#
.SYNOPSIS
  R.E.Y. // Team Roster Display — shows optimal model assignments per agent role.
#>
param()

try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$ErrorActionPreference = 'Continue'

$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Join-Path $HOME '.config\opencode\scripts' }
$confDir = Split-Path -Parent $scriptDir

function Show-Roster {
  # Call Python roster generator
  $pyRoster = Join-Path $scriptDir 'rey-roster.py'
  if (-not (Test-Path -LiteralPath $pyRoster)) {
    Write-Host "  [ERROR] rey-roster.py not found" -ForegroundColor Red
    return
  }

  $pyOut = & python "$pyRoster" 2>$null
  if (-not $pyOut) {
    Write-Host "  [ERROR] Roster generation failed" -ForegroundColor Red
    return
  }

  $data = $pyOut | ConvertFrom-Json

  if ($data.error) {
    Write-Host "  [ERROR] $($data.error)" -ForegroundColor Red
    return
  }

  # Draw roster screen
  try { [Console]::Clear() } catch { Clear-Host }

  $roleIcons = @{
    'coder'      = '💻'
    'reviewer'   = '🔍'
    'planner'    = '📋'
    'researcher' = '📚'
    'debugger'   = '🐛'
  }

  $roleLabels = @{
    'coder'      = 'CODE WRITER'
    'reviewer'   = 'CODE REVIEWER'
    'planner'    = 'ARCHITECT/PLANNER'
    'researcher' = 'RESEARCHER'
    'debugger'   = 'DEBUGGER'
  }

  Write-Host ""
  Write-Host "  ============================================================" -ForegroundColor Cyan
  Write-Host "   R.E.Y. // TEAM ROSTER — YOUR AI SQUAD" -ForegroundColor Cyan
  Write-Host "  ============================================================" -ForegroundColor Cyan
  Write-Host ""
  Write-Host "  Based on your providers: $($data.enabled_providers -join ', ')" -ForegroundColor DarkGray
  Write-Host "  Generated: $($data.generated_at)" -ForegroundColor DarkGray
  Write-Host ""
  Write-Host "  ┌─────────────────┬──────────────────────────┬─────────────────────────────┐" -ForegroundColor DarkGray
  Write-Host "  │ ROLE            │ MODEL                    │ WHY                         │" -ForegroundColor DarkGray
  Write-Host "  ├─────────────────┼──────────────────────────┼─────────────────────────────┤" -ForegroundColor DarkGray

  foreach ($role in @('coder', 'reviewer', 'planner', 'researcher', 'debugger')) {
    $r = $data.roster.$role
    if ($r) {
      $icon = $roleIcons[$role]
      $label = $roleLabels[$role]
      $model = $r.model
      if ($model.Length -gt 24) { $model = $model.Substring(0, 22) + '..' }
      $reason = $r.reason
      if ($reason.Length -gt 27) { $reason = $reason.Substring(0, 25) + '..' }

      $providerColor = switch ($r.provider) {
        'openrouter' { 'Magenta' }
        'groq'       { 'Green' }
        'gemini'     { 'Blue' }
        'claude'     { 'Yellow' }
        'chatgpt'    { 'Cyan' }
        default      { 'White' }
      }

      Write-Host "  │ " -ForegroundColor DarkGray -NoNewline
      Write-Host ("{0} {1,-14}" -f $icon, $label) -ForegroundColor White -NoNewline
      Write-Host " │ " -ForegroundColor DarkGray -NoNewline
      Write-Host ("{0,-24}" -f $model) -ForegroundColor $providerColor -NoNewline
      Write-Host " │ " -ForegroundColor DarkGray -NoNewline
      Write-Host ("{0,-27}" -f $reason) -ForegroundColor DarkGray -NoNewline
      Write-Host " │" -ForegroundColor DarkGray
    }
  }

  Write-Host "  └─────────────────┴──────────────────────────┴─────────────────────────────┘" -ForegroundColor DarkGray
  Write-Host ""
  Write-Host "  [A] Accept & Apply   [M] Modify Assignments   [S] Skip for Now" -ForegroundColor Yellow
  Write-Host ""

  # Save roster to byok-config.json
  $byokPath = Join-Path $confDir 'byok-config.json'
  if (Test-Path -LiteralPath $byokPath) {
    $byok = Get-Content -LiteralPath $byokPath -Raw | ConvertFrom-Json
    foreach ($role in @('coder', 'reviewer', 'planner', 'researcher', 'debugger')) {
      $r = $data.roster.$role
      if ($r) {
        $byok.roster.$role = "$($r.provider)/$($r.model)"
      }
    }
    $byok | ConvertTo-Json -Depth 10 | Set-Content -Path $byokPath -Encoding UTF8
  }

  $key = [Console]::ReadKey($true)
  switch ($key.Key) {
    'A' { Write-Host "  [OK] Roster accepted!" -ForegroundColor Green; Start-Sleep -Seconds 1 }
    'S' { Write-Host "  [SKIP] Roster skipped. You can run setup again with 'rey setup'." -ForegroundColor Yellow; Start-Sleep -Seconds 1 }
    default { Write-Host "  [OK] Roster saved." -ForegroundColor Green; Start-Sleep -Seconds 1 }
  }
}

Show-Roster
```

- [ ] **Step 2: Test roster display**

Run: `pwsh scripts/rey-roster.ps1`
Expected: Table showing role → model → reason assignments with provider-colored model names

---

### Task 6: Wire Setup Wizard Completion Flow

**Files:**
- Modify: `C:\Users\rey.echavez\.config\opencode\scripts\rey-setup.ps1` (add main orchestration)

**Interfaces:**
- Consumes: Provider selection (Task 2) + Key input (Task 3)
- Produces: `byok-config.json` + `.env` entries + `.setup-complete` marker
- Produces: Calls `rey-roster.ps1` for team roster display

- [ ] **Step 1: Add main orchestration to rey-setup.ps1**

Append this to the end of `rey-setup.ps1`:

```powershell
# --- Main Setup Flow ---
function Start-Setup {
  try { [Console]::CursorVisible = $true } catch { }

  $confDir = if ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { Join-Path $HOME '.config\opencode' }

  # Step 1: Provider Selection
  $selected = @()
  $selected = Show-ProviderSelection -providers $providers -selected $selected

  # Step 2: API Key Input
  $keys = Show-KeyInput -providers $providers -selectedIds $selected

  # Step 3: Save BYOK Config
  $byokConfig = @{
    version = 1
    setup_date = (Get-Date -Format 'yyyy-MM-dd HH:mm:ss')
    providers = @{}
    roster = @{
      coder = ''
      reviewer = ''
      planner = ''
      researcher = ''
      debugger = ''
    }
  }
  foreach ($p in $providers) {
    $byokConfig.providers[$p.Id] = @{
      enabled = ($selected -contains $p.Id)
      key_ref = $p.KeyEnv
    }
  }

  $byokPath = Join-Path $confDir 'byok-config.json'
  $byokConfig | ConvertTo-Json -Depth 10 | Set-Content -Path $byokPath -Encoding UTF8

  # Step 4: Save API keys to .env
  if ($keys.Count -gt 0) {
    Save-EnvKeys -keys $keys
  }

  # Step 5: Create setup-complete marker
  $markerPath = Join-Path $confDir '.setup-complete'
  (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') | Set-Content -Path $markerPath -Encoding UTF8

  # Step 6: Show Team Roster
  $rosterPs1 = Join-Path $scriptDir 'rey-roster.ps1'
  if (Test-Path -LiteralPath $rosterPs1) {
    & powershell -ExecutionPolicy Bypass -File "$rosterPs1"
  }

  # Done
  try { [Console]::Clear() } catch { Clear-Host }
  Write-Host ""
  Write-Host "  ============================================================" -ForegroundColor Green
  Write-Host "   R.E.Y. // SETUP COMPLETE!" -ForegroundColor Green
  Write-Host "  ============================================================" -ForegroundColor Green
  Write-Host ""
  Write-Host "  Providers configured: $($selected -join ', ')" -ForegroundColor White
  Write-Host "  API keys saved to:    $confDir\.env" -ForegroundColor DarkGray
  Write-Host "  Config saved to:      $byokPath" -ForegroundColor DarkGray
  Write-Host ""
  Write-Host "  You can re-run setup anytime with: rey setup" -ForegroundColor Yellow
  Write-Host "  Or press [S] in the monitor to reconfigure." -ForegroundColor Yellow
  Write-Host ""
  Write-Host "  Press any key to launch R.E.Y. Monitor..." -ForegroundColor Cyan
  try { [Console]::ReadKey($true) | Out-Null } catch { }
}

Start-Setup
```

- [ ] **Step 2: Test full setup flow**

Run: `pwsh scripts/rey-setup.ps1`
Expected: Provider selection → Key input → Config saved → Roster displayed → Setup complete screen

---

### Task 7: Add Setup Check to Main Monitor

**Files:**
- Modify: `C:\Users\rey.echavez\.config\opencode\scripts\rey-monitor.ps1`

**Interfaces:**
- Consumes: `.setup-complete` marker file existence
- Produces: Routes to `rey-setup.ps1` if marker absent

- [ ] **Step 1: Add setup check at the top of the initialization block**

Find the line (around line 753):
```powershell
# --- Initialization ---
try {
  $Host.UI.RawUI.WindowTitle = 'R.E.Y. // Runtime Execution & Yield Monitor - Opencode Monitoring CLI'
```

Insert BEFORE it:

```powershell
# --- First-Run Setup Check ---
$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Join-Path $HOME '.config\opencode\scripts' }
$confDir = Split-Path -Parent $scriptDir
$setupMarker = Join-Path $confDir '.setup-complete'
if (-not (Test-Path -LiteralPath $setupMarker)) {
  $setupScript = Join-Path $scriptDir 'rey-setup.ps1'
  if (Test-Path -LiteralPath $setupScript) {
    try { [Console]::Clear() } catch { Clear-Host }
    Write-Host ""
    Write-Host "  R.E.Y. // First-run detected. Launching setup wizard..." -ForegroundColor Cyan
    Write-Host ""
    Start-Sleep -Seconds 1
    & powershell -ExecutionPolicy Bypass -File "$setupScript"
    # After setup, re-launch monitor
    & powershell -ExecutionPolicy Bypass -File "$PSCommandPath"
    exit
  }
}
```

- [ ] **Step 2: Add `S` key handler for re-run setup**

Find the key handling block (around line 778-851). After the `H` key handler, add:

```powershell
          if ($key.Key -eq 'S') {
            try { [Console]::CursorVisible = $true } catch { }
            try { [Console]::Clear() } catch { Clear-Host }
            $setupScript = Join-Path $scriptDir 'rey-setup.ps1'
            if (Test-Path -LiteralPath $setupScript) {
              & powershell -ExecutionPolicy Bypass -File "$setupScript"
            }
            Refresh-Status
            try { [Console]::Clear() } catch { Clear-Host }
            try { [Console]::CursorVisible = $false } catch { }
          }
```

- [ ] **Step 3: Update the help footer to include `S` key**

Find the line:
```powershell
@{ Text = ("   last refresh  : " + $state.LastRefresh + '  (Q: quit | T: tokens | L: logs | D: deals | O: override | H: health)'); Color = 'DarkGray' }
```

Change to:
```powershell
@{ Text = ("   last refresh  : " + $state.LastRefresh + '  (Q: quit | T: tokens | L: logs | D: deals | O: override | H: health | S: setup)'); Color = 'DarkGray' }
```

- [ ] **Step 4: Test first-run detection**

Rename `.setup-complete` to `.setup-complete.bak` (or delete it), then run `rey`
Expected: Setup wizard launches automatically before the monitor

- [ ] **Step 5: Test `S` key re-run**

Run `rey` with setup already complete → press `S`
Expected: Setup wizard launches, returns to monitor after completion

---

### Task 8: Add `.env` Loading to Monitor Startup

**Files:**
- Modify: `C:\Users\rey.echavez\.config\opencode\scripts\rey-monitor.ps1`

**Interfaces:**
- Consumes: `.env` file with API keys
- Produces: Environment variables set for the session

- [ ] **Step 1: Add .env loader at the top of the script**

After the `$ErrorActionPreference = 'Continue'` line (around line 13), add:

```powershell
# Load .env file for BYOK API keys
try {
  $envFile = if ($PSScriptRoot) { Join-Path (Split-Path -Parent $PSScriptRoot) '.env' } else { Join-Path $HOME '.config\opencode\.env' }
  if (Test-Path -LiteralPath $envFile) {
    Get-Content -LiteralPath $envFile -Encoding UTF8 | ForEach-Object {
      $line = $_.Trim()
      if ($line -and -not $line.StartsWith('#') -and $line -match '^([^=]+)=(.*)$') {
        [Environment]::SetEnvironmentVariable($Matches[1].Trim(), $Matches[2].Trim(), 'Process')
      }
    }
  }
} catch { }
```

- [ ] **Step 2: Test env loading**

Run `rey` → in a separate terminal, check `[Environment]::GetEnvironmentVariable('OPENROUTER_API_KEY', 'Process')` — should show the key value

---

### Task 9: Final Integration Test & Commit

**Files:**
- All modified/created files

- [ ] **Step 1: Full end-to-end test**

1. Delete `.setup-complete` marker
2. Run `pwsh scripts/rey-monitor.ps1`
3. Verify: Setup wizard launches → select providers → enter keys → roster displays → monitor starts
4. Press `S` in monitor → verify re-run setup works
5. Verify `.env` contains API keys
6. Verify `byok-config.json` has correct provider flags
7. Verify `.setup-complete` marker exists

- [ ] **Step 2: Commit all changes**

```bash
git add scripts/rey-setup.ps1 scripts/rey-roster.py scripts/rey-roster.ps1 scripts/rey-monitor.ps1 .gitignore
git commit -m "feat(byok): add first-run setup wizard with provider selection, API key input, and team roster generator

- Interactive TUI for selecting AI providers (Groq, Gemini, OpenRouter, Claude, ChatGPT)
- Secure API key input with .env storage (never committed)
- Auto-generated team roster assigning optimal models to agent roles
- First-run detection routes to setup wizard automatically
- S key in monitor re-runs setup wizard
- .env loader for BYOK keys at monitor startup"
```

- [ ] **Step 3: Push to GitHub**

```bash
git push origin main
```

---

## Summary of Deliverables

| # | Deliverable | Status |
|---|-------------|--------|
| 1 | `.gitignore` updated for BYOK files | — |
| 2 | `rey-setup.ps1` — Interactive provider selection + key input | — |
| 3 | `rey-roster.py` — Python roster generator | — |
| 4 | `rey-roster.ps1` — Roster display wrapper | — |
| 5 | `rey-monitor.ps1` — Setup check + S key + .env loader | — |
| 6 | Integration test + commit + push | — |
