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
node (Join-Path $ScriptDir "patches\patch-swarm-posix.js")
node (Join-Path $ScriptDir "patches\patch-swarm-parse-error.js")
node (Join-Path $ScriptDir "patches\patch-fast-boot.js")
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

Write-Host "`n==========================================================" -ForegroundColor Cyan
Write-Host "[OK] Diagnostic Complete." -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
