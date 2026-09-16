#Requires -Version 5.1

<#
.SYNOPSIS
    R.E.Y. CLI First-Run Setup Wizard — Bring Your Own Key (BYOK) Configuration.

.DESCRIPTION
    Interactive TUI setup wizard for configuring API providers and keys
    used by the R.E.Y. CLI agent system. Guides the user through provider
    selection, API key entry, roster assignment, and persists all configuration
    to local .env and byok-config.json files.

.PARAMETER SkipMonitor
    If specified, suppresses re-launching the R.E.Y. Monitor after setup completes.

.EXAMPLE
    .\rey-setup.ps1
    Launches the interactive setup wizard.

.EXAMPLE
    .\rey-setup.ps1 -SkipMonitor
    Completes setup without re-launching the monitor.
#>

[CmdletBinding()]
param(
    [switch]$SkipMonitor
)

$ErrorActionPreference = 'Continue'

$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Join-Path $HOME '.config\opencode\scripts' }
$confDir   = Split-Path -Parent $scriptDir

# ─────────────────────────────────────────────────────────────
#  Function 1: Show-ProviderSelection
# ─────────────────────────────────────────────────────────────

function Show-ProviderSelection {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [hashtable[]]$providers,

        [string[]]$selected = @()
    )

    $cursorIndex = 0

    while ($true) {
        # ── render ──
        try { [Console]::Clear() } catch { Clear-Host }

        Write-Host ""
        Write-Host "  ============================================================" -ForegroundColor Cyan
        Write-Host "   R.E.Y. // BYOK SETUP — STEP 1 OF 2: SELECT PROVIDERS"     -ForegroundColor Cyan
        Write-Host "  ============================================================" -ForegroundColor Cyan
        Write-Host ""

        for ($i = 0; $i -lt $providers.Count; $i++) {
            $p       = $providers[$i]
            $checked = $selected -contains $p.Id
            $mark    = if ($checked) { 'X' } else { ' ' }
            $icon    = $p.Icon
            $label   = $p.Label
            $desc    = $p.Desc

            if ($i -eq $cursorIndex) {
                $line = "  ► [$mark] $icon $label  — $desc"
                Write-Host $line -ForegroundColor Yellow
            } else {
                $line = "    [$mark] $icon $label  — $desc"
                Write-Host $line -ForegroundColor Gray
            }
        }

        Write-Host ""
        Write-Host "  [↑/↓] Navigate   [Space] Toggle   [Enter] Confirm" -ForegroundColor DarkGray
        Write-Host ""

        # ── input ──
        $key = [Console]::ReadKey($true)

        switch ($key.Key) {
            'UpArrow' {
                if ($cursorIndex -gt 0) { $cursorIndex-- }
            }
            'DownArrow' {
                if ($cursorIndex -lt ($providers.Count - 1)) { $cursorIndex++ }
            }
            'Spacebar' {
                $id = $providers[$cursorIndex].Id
                if ($selected -contains $id) {
                    $selected = $selected | Where-Object { $_ -ne $id }
                } else {
                    $selected += $id
                }
            }
            'Enter' {
                if ($selected.Count -ge 1) {
                    return $selected
                } else {
                    # red error flash
                    $prevFg = [Console]::ForegroundColor
                    [Console]::ForegroundColor = [ConsoleColor]::Red
                    Write-Host "  ✗ You must select at least one provider." -ForegroundColor Red
                    [Console]::ForegroundColor = $prevFg
                    Start-Sleep -Seconds 1
                }
            }
        }
    }
}

# ─────────────────────────────────────────────────────────────
#  Function 2: Show-KeyInput
# ─────────────────────────────────────────────────────────────

function Show-KeyInput {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [hashtable[]]$providers,

        [Parameter(Mandatory)]
        [string[]]$selectedIds
    )

    $keys = @{}

    foreach ($sid in $selectedIds) {
        $p = $providers | Where-Object { $_.Id -eq $sid } | Select-Object -First 1

        # ── render prompt ──
        try { [Console]::Clear() } catch { Clear-Host }

        Write-Host ""
        Write-Host "  ============================================================" -ForegroundColor Cyan
        Write-Host "   R.E.Y. // BYOK SETUP — ENTER KEY: $($p.Label)"           -ForegroundColor Cyan
        Write-Host "  ============================================================" -ForegroundColor Cyan
        Write-Host ""
        Write-Host "  $($p.Icon)  $($p.Label) — $($p.Desc)" -ForegroundColor White
        Write-Host ""
        Write-Host "  Environment variable: $($p.KeyEnv)" -ForegroundColor DarkGray
        Write-Host "  Expected format:      $($p.KeyHint)" -ForegroundColor DarkGray
        Write-Host ""
        Write-Host "  Paste your API key below then press Enter." -ForegroundColor Yellow
        Write-Host "  Press Enter without typing to skip this provider." -ForegroundColor DarkGray
        Write-Host ""

        # ── read characters with masking ──
        $secure = New-Object System.Security.SecureString
        $entered = [System.Text.StringBuilder]::new()

        while ($true) {
            $cki = [Console]::ReadKey($true)

            if ($cki.Key -eq 'Enter') {
                Write-Host ""
                break
            }
            elseif ($cki.Key -eq 'Backspace') {
                if ($secure.Length -gt 0) {
                    $secure.RemoveAt($secure.Length - 1) | Out-Null
                    $entered.Remove($entered.Length - 1, 1) | Out-Null
                    # erase the last asterisk on screen
                    $prevX = [Console]::CursorLeft
                    $prevY = [Console]::CursorTop
                    if ($prevX -gt 0) {
                        [Console]::SetCursorPosition($prevX - 1, $prevY)
                        Write-Host " " -NoNewline
                        [Console]::SetCursorPosition($prevX - 1, $prevY)
                    }
                }
            }
            elseif ($cki.Key -eq 'Escape') {
                # treat as skip
                $secure = New-Object System.Security.SecureString
                $entered.Clear() | Out-Null
                Write-Host ""
                break
            }
            else {
                $char = $cki.KeyChar
                if ($char -ne "`0") {
                    $secure.AppendChar($char) | Out-Null
                    $entered.Append($char) | Out-Null
                    Write-Host "*" -NoNewline
                }
            }
        }

        # ── store key if non-empty ──
        if ($secure.Length -gt 0) {
            # convert SecureString → plain string for .env storage
            $bstr = [System.Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure)
            $plain = [System.Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
            [System.Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr) | Out-Null

            $keys[$p.KeyEnv] = $plain
            Write-Host "  [OK] Key saved for $($p.Label)." -ForegroundColor Green
        } else {
            Write-Host "  [SKIP] No key entered for $($p.Label)." -ForegroundColor DarkYellow
        }

        Start-Sleep -Milliseconds 600
    }

    return $keys
}

# ─────────────────────────────────────────────────────────────
#  Function 3: Save-EnvKeys
# ─────────────────────────────────────────────────────────────

function Save-EnvKeys {
    [CmdletBinding()]
    param(
        [Parameter(Mandatory)]
        [hashtable]$keys
    )

    $envPath = Join-Path $confDir '.env'

    # read existing lines
    $existingLines = @()
    if (Test-Path $envPath) {
        $raw = Get-Content $envPath -Encoding UTF8 -ErrorAction SilentlyContinue
        if ($raw) { $existingLines = @($raw) }
    }

    # identify key names we are writing
    $keyNames = $keys.Keys | ForEach-Object { $_ }

    # keep only lines that do NOT match any of our keys
    $kept = @()
    foreach ($line in $existingLines) {
        $trimmed = $line.Trim()
        $isManaged = $false
        foreach ($kn in $keyNames) {
            if ($trimmed -match "^$([regex]::Escape($kn))\s*=") {
                $isManaged = $true
                break
            }
        }
        if (-not $isManaged) {
            $kept += $line
        }
    }

    # append new keys
    foreach ($envVar in $keyNames) {
        $value = $keys[$envVar]
        $kept += "$envVar=$value"
    }

    # write back
    $kept | Set-Content -Path $envPath -Encoding UTF8
}

# ─────────────────────────────────────────────────────────────
#  Function 4: Start-Setup  (main orchestration)
# ─────────────────────────────────────────────────────────────

function Start-Setup {
    [CmdletBinding()]
    param()

    # ── provider catalog ──
    $providers = @(
        @{ Id='openrouter'; Label='OpenRouter';    Desc='200+ models, free tier, unified gateway'; Icon='🌐'; KeyEnv='OPENROUTER_API_KEY'; KeyHint='sk-or-v1-...' }
        @{ Id='groq';       Label='Groq';          Desc='Ultra-fast inference (Llama, Mixtral)';   Icon='⚡'; KeyEnv='GROQ_API_KEY';       KeyHint='gsk_...'     }
        @{ Id='gemini';     Label='Google Gemini';  Desc='Gemini 2.5 Flash/Pro, generous free tier'; Icon='🔮'; KeyEnv='GEMINI_API_KEY';     KeyHint='AIza...'     }
        @{ Id='claude';     Label='Anthropic Claude'; Desc='Claude Sonnet/Opus, best reasoning';     Icon='🧠'; KeyEnv='ANTHROPIC_API_KEY';  KeyHint='sk-ant-...'  }
        @{ Id='chatgpt';    Label='OpenAI ChatGPT'; Desc='GPT-4o, o1, o3 models';                   Icon='🤖'; KeyEnv='OPENAI_API_KEY';     KeyHint='sk-...'      }
    )

    # ── Step 1: provider selection ──
    $selectedIds = Show-ProviderSelection -providers $providers

    # ── Step 2: key entry ──
    $keys = Show-KeyInput -providers $providers -selectedIds $selectedIds

    # ── Save keys to .env ──
    if ($keys.Count -gt 0) {
        Save-EnvKeys -keys $keys
    }

    # ── Build byok-config.json ──
    $configDate = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'

    $configProviders = @{}
    foreach ($p in $providers) {
        $enabled = $selectedIds -contains $p.Id
        $hasKey  = $keys.ContainsKey($p.KeyEnv) -and $keys[$p.KeyEnv].Length -gt 0
        $configProviders[$p.Id] = @{
            enabled = $enabled
            key_ref = if ($hasKey) { $p.KeyEnv } else { "" }
        }
    }

    $config = @{
        version    = 1
        setup_date = $configDate
        providers  = $configProviders
        roster     = @{
            coder      = ""
            reviewer   = ""
            planner    = ""
            researcher = ""
            debugger   = ""
        }
    }

    $configPath = Join-Path $confDir 'byok-config.json'
    $config | ConvertTo-Json -Depth 5 | Set-Content -Path $configPath -Encoding UTF8

    # ── Mark setup complete ──
    $markerPath = Join-Path $confDir '.setup-complete'
    "setup_complete=true" | Set-Content -Path $markerPath -Encoding UTF8

    # ── Launch roster setup if script exists ──
    $rosterScript = Join-Path $scriptDir 'rey-roster.ps1'
    if (Test-Path $rosterScript) {
        & powershell -ExecutionPolicy Bypass -File $rosterScript
    }

    # ── Reload config to capture roster selections ──
    if (Test-Path $configPath) {
        $config = Get-Content $configPath -Raw | ConvertFrom-Json
    }

    # ── Completion screen ──
    try { [Console]::Clear() } catch { Clear-Host }

    $providerNames = @()
    foreach ($p in $providers) {
        if ($selectedIds -contains $p.Id) { $providerNames += $p.Label }
    }
    $providerList = $providerNames -join ', '
    if ([string]::IsNullOrEmpty($providerList)) { $providerList = '(none)' }

    Write-Host ""
    Write-Host "  ============================================================" -ForegroundColor Green
    Write-Host "   R.E.Y. // SETUP COMPLETE!"                                -ForegroundColor Green
    Write-Host "  ============================================================" -ForegroundColor Green
    Write-Host ""
    Write-Host "    Providers configured: $providerList" -ForegroundColor White
    Write-Host "    API keys saved to:    $confDir\.env" -ForegroundColor White
    Write-Host "    Config saved to:      $confDir\byok-config.json" -ForegroundColor White
    Write-Host ""
    Write-Host "    You can re-run setup anytime with: rey setup" -ForegroundColor Yellow
    Write-Host "    Or press [S] in the monitor to reconfigure." -ForegroundColor Yellow
    Write-Host ""
    Write-Host "  Press any key to launch R.E.Y. Monitor..." -ForegroundColor Cyan
    Write-Host ""

    [Console]::ReadKey($true) | Out-Null

    # ── Re-launch monitor (or exit if -SkipMonitor) ──
    if (-not $SkipMonitor) {
        $monitorScript = Join-Path $scriptDir 'rey-monitor.ps1'
        if (Test-Path $monitorScript) {
            & powershell -ExecutionPolicy Bypass -File $monitorScript
        }
    }
    exit
}

# ─────────────────────────────────────────────────────────────
#  Entry point — run when script is executed directly
# ─────────────────────────────────────────────────────────────
Start-Setup
