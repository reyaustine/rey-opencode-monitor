#Requires -Version 5.1
<#
.SYNOPSIS
  Single-instance launcher for the global JARVIS model fleet monitor.
  Starts the monitor window only if it is not already running.
  Safe to call at logon, at opencode startup, or before agentic work.
#>
param()

$MONITOR = Join-Path $HOME '.config\opencode\scripts\jarvis-monitor.ps1'

$running = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
  Where-Object {
    ($_.ProcessId -ne $PID) -and
    ($_.CommandLine -like '*jarvis-monitor.ps1*') -and
    ($_.CommandLine -notlike '*-NonInteractive*')
  }
if ($running) {
  Write-Host 'JARVIS monitor already running.'
  exit 0
}
if (-not (Test-Path -LiteralPath $MONITOR)) {
  Write-Host ("Monitor script not found: " + $MONITOR)
  exit 1
}
Start-Process -FilePath 'powershell.exe' -ArgumentList @(
  '-NoExit', '-ExecutionPolicy', 'Bypass', '-File', $MONITOR
) -WindowStyle Normal
Write-Host 'JARVIS monitor launched.'
