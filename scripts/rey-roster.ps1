#Requires -Version 5.1
<#
.SYNOPSIS
  R.E.Y. // Team Roster Display — shows optimal model assignments per agent role.
  Called by rey-setup.ps1 after BYOK configuration completes.
#>
param()

$OutputEncoding = [System.Text.Encoding]::UTF8
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch { }
$ErrorActionPreference = 'Continue'

$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Join-Path $HOME '.config\opencode\scripts' }
$confDir   = if ($PSScriptRoot) { Split-Path -Parent $PSScriptRoot } else { Join-Path $HOME '.config\opencode' }

function Show-Roster {
  # Call Python roster generator
  $pyRoster = Join-Path $scriptDir 'rey-roster.py'
  if (-not (Test-Path -LiteralPath $pyRoster)) {
    Write-Host '  [ERROR] rey-roster.py not found' -ForegroundColor Red
    return
  }

  $pyOut = & python "$pyRoster" 2>$null
  if (-not $pyOut) {
    Write-Host '  [ERROR] Roster generation failed' -ForegroundColor Red
    return
  }

  # Parse JSON (handle BOM)
  $raw = [System.IO.File]::ReadAllBytes($pyRoster)
  $jsonText = $pyOut -join "`n"
  try {
    $data = $jsonText | ConvertFrom-Json
  } catch {
    Write-Host "  [ERROR] Failed to parse roster: $($_.Exception.Message)" -ForegroundColor Red
    return
  }

  if ($data.error) {
    Write-Host "  [ERROR] $($data.error)" -ForegroundColor Red
    return
  }

  # Draw roster screen
  try { [Console]::Clear() } catch { Clear-Host }

  $roleIcons = @{
    'coder'      = [char]0x1F4BB   # 💻
    'reviewer'   = [char]0x1F50D   # 🔍
    'planner'    = [char]0x1F4CB   # 📋
    'researcher' = [char]0x1F4DA   # 📚
    'debugger'   = [char]0x1F41B   # 🐛
  }

  $roleLabels = @{
    'coder'      = 'CODE WRITER'
    'reviewer'   = 'CODE REVIEWER'
    'planner'    = 'ARCHITECT/PLANNER'
    'researcher' = 'RESEARCHER'
    'debugger'   = 'DEBUGGER'
  }

  $providerColors = @{
    'openrouter' = 'Magenta'
    'groq'       = 'Green'
    'gemini'     = 'Blue'
    'claude'     = 'Yellow'
    'chatgpt'    = 'Cyan'
  }

  Write-Host ''
  Write-Host '  ============================================================' -ForegroundColor Cyan
  Write-Host '   R.E.Y. // TEAM ROSTER — YOUR AI SQUAD' -ForegroundColor Cyan
  Write-Host '  ============================================================' -ForegroundColor Cyan
  Write-Host ''
  Write-Host "  Based on providers: $($data.enabled_providers -join ', ')" -ForegroundColor DarkGray
  Write-Host "  Generated: $($data.generated_at)" -ForegroundColor DarkGray
  Write-Host ''
  Write-Host '  +-----------------+--------------------------+-----------------------------+' -ForegroundColor DarkGray
  Write-Host '  | ROLE            | MODEL                    | WHY                         |' -ForegroundColor DarkGray
  Write-Host '  +-----------------+--------------------------+-----------------------------+' -ForegroundColor DarkGray

  $roleOrder = @('coder', 'reviewer', 'planner', 'researcher', 'debugger')
  foreach ($role in $roleOrder) {
    $r = $data.roster.$role
    if ($r) {
      $icon = $roleIcons[$role]
      $label = $roleLabels[$role]
      $model = [string]$r.model
      if ($model.Length -gt 24) { $model = $model.Substring(0, 22) + '..' }
      $reason = [string]$r.reason
      if ($reason.Length -gt 27) { $reason = $reason.Substring(0, 25) + '..' }

      $provColor = if ($providerColors.ContainsKey([string]$r.provider)) { $providerColors[[string]$r.provider] } else { 'White' }

      Write-Host '  | ' -ForegroundColor DarkGray -NoNewline
      Write-Host ('{0} {1,-14}' -f $icon, $label) -ForegroundColor White -NoNewline
      Write-Host ' | ' -ForegroundColor DarkGray -NoNewline
      Write-Host ('{0,-24}' -f $model) -ForegroundColor $provColor -NoNewline
      Write-Host ' | ' -ForegroundColor DarkGray -NoNewline
      Write-Host ('{0,-27}' -f $reason) -ForegroundColor DarkGray -NoNewline
      Write-Host ' |' -ForegroundColor DarkGray
    }
  }

  Write-Host '  +-----------------+--------------------------+-----------------------------+' -ForegroundColor DarkGray
  Write-Host ''
  Write-Host '  [A] Accept & Apply   [M] Modify Assignments   [S] Skip for Now' -ForegroundColor Yellow
  Write-Host ''

  # Save roster to byok-config.json
  $byokPath = Join-Path $confDir 'byok-config.json'
  if (Test-Path -LiteralPath $byokPath) {
    $byokRaw = [System.IO.File]::ReadAllBytes($byokPath)
    if ($byokRaw.Length -ge 3 -and $byokRaw[0] -eq 0xEF -and $byokRaw[1] -eq 0xBB -and $byokRaw[2] -eq 0xBF) {
      $byokRaw = $byokRaw[3..($byokRaw.Length - 1)]
    }
    $byok = [System.Text.Encoding]::UTF8.GetString($byokRaw) | ConvertFrom-Json

    foreach ($role in $roleOrder) {
      $r = $data.roster.$role
      if ($r) {
        $byok.roster.$role = "$($r.provider)/$($r.model)"
      }
    }

    $newJson = $byok | ConvertTo-Json -Depth 10
    [System.IO.File]::WriteAllText($byokPath, $newJson, [System.Text.UTF8Encoding]::new($true))
  }

  # Wait for user input
  try { [Console]::CursorVisible = $true } catch { }
  $key = [Console]::ReadKey($true)
  switch ($key.Key) {
    'A' {
      Write-Host '  [OK] Roster accepted and applied!' -ForegroundColor Green
      Start-Sleep -Seconds 1
    }
    'S' {
      Write-Host '  [SKIP] Roster skipped. You can run setup again with rey [S].' -ForegroundColor Yellow
      Start-Sleep -Seconds 1
    }
    default {
      Write-Host '  [OK] Roster saved.' -ForegroundColor Green
      Start-Sleep -Seconds 1
    }
  }
}

# ─── Entry Point ─────────────────────────────────────────────────────────────
Show-Roster
