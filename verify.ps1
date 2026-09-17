[CmdletBinding()]
param()

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "   OpenCode Swarm Diagnostic & Health Check               " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check opencode CLI
$OpenCodeCmd = Get-Command opencode -ErrorAction SilentlyContinue
if ($OpenCodeCmd) {
  $version = opencode --version 2>$null
  Write-Host "[OK] OpenCode CLI installed: v$version" -ForegroundColor Green
} else {
  Write-Host "[-] OpenCode CLI not found in PATH." -ForegroundColor Red
}

# 2. Check runtime patches
Write-Host "`n[*] Verifying runtime stability patches..." -ForegroundColor Cyan
node (Join-Path $ScriptDir "patches\patch-opencode-binary.js")
node (Join-Path $ScriptDir "patches\patch-desktop-asar.js")
node (Join-Path $ScriptDir "patches\patch-gemini-enum.js")
node (Join-Path $ScriptDir "patches\patch-watchdog-timeout.js")
node (Join-Path $ScriptDir "patches\patch-context-length-fallback.js")
node (Join-Path $ScriptDir "patches\fix-model-key-regex.js")

# 3. Agent discovery
Write-Host "`n[*] Querying opencode agent list..." -ForegroundColor White
$agentOutput = opencode agent list 2>&1
$agentLines = @($agentOutput | Where-Object { $_ -match '^\s*-\s+[a-zA-Z]' })
$agentCount = $agentLines.Count
if ($agentCount -gt 0) {
  Write-Host "[OK] Successfully loaded $agentCount agents into OpenCode Swarm!" -ForegroundColor Green
  foreach ($line in $agentLines) {
    Write-Host "    $line" -ForegroundColor Gray
  }
} else {
  Write-Host "[!] Agent list returned no items or output was verbose." -ForegroundColor Yellow
}

# 4. Python test suite + PS1 parse regression check
Write-Host "`n[*] Running Python test suite + PS1 parse check..." -ForegroundColor Cyan
try {
  $pytest = Get-Command pytest -ErrorAction SilentlyContinue
  if (-not $pytest) { $pytest = Get-Command python -ErrorAction SilentlyContinue }
  if ($pytest) {
    $testResult = & python -m pytest tests -q 2>&1
    $testExit = $LASTEXITCODE
    $testResult | ForEach-Object { Write-Host "    $_" -ForegroundColor Gray }
    if ($testExit -eq 0) {
      Write-Host "[OK] Test suite passed." -ForegroundColor Green
    } else {
      Write-Host "[!] Test suite failed (exit $testExit)." -ForegroundColor Yellow
    }
  } else {
    Write-Host "[!] pytest/python not found - skipping test suite." -ForegroundColor Yellow
  }
} catch {
  Write-Host "[!] Test suite error: $($_.Exception.Message)" -ForegroundColor Yellow
}

# 5. PS1 BOM / parse smoke check
Write-Host "`n[*] Checking PowerShell script encoding (UTF-8 BOM)..." -ForegroundColor Cyan
$ps1Bad = @()
Get-ChildItem -Path (Join-Path $ScriptDir "scripts") -Filter "*.ps1" -ErrorAction SilentlyContinue | ForEach-Object {
  $b = [System.IO.File]::ReadAllBytes($_.FullName)
  $hasBom = ($b.Length -ge 3 -and $b[0] -eq 0xEF -and $b[1] -eq 0xBB -and $b[2] -eq 0xBF)
  $hasMulti = $false; foreach ($x in $b) { if ($x -ge 0x80) { $hasMulti = $true; break } }
  if ($hasMulti -and -not $hasBom) { $ps1Bad += $_.Name }
}
if ($ps1Bad.Count -eq 0) {
  Write-Host "[OK] All PS1 scripts with multibyte content have UTF-8 BOM." -ForegroundColor Green
} else {
  Write-Host "[!] BOM-less multibyte PS1 files: $($ps1Bad -join ', ')" -ForegroundColor Yellow
}

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "[OK] Diagnostic Complete." -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
