#Requires -Version 5.1
<#
.SYNOPSIS
  Single-instance launcher for the global R.E.Y. Runtime Execution & Yield Monitor.
  Starts the monitor window only if it is not already running.
  Safe to call at logon, at opencode startup, or before agentic work.
#>
param()

$MONITOR = Join-Path $HOME '.config\opencode\scripts\rey-monitor.ps1'

$running = Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" |
  Where-Object {
    ($_.ProcessId -ne $PID) -and
    (($_.CommandLine -like '*rey-monitor.ps1*') -or ($_.CommandLine -like '*jarvis-monitor.ps1*')) -and
    ($_.CommandLine -notlike '*-NonInteractive*')
  }
if ($running) {
  Write-Host 'R.E.Y. monitor already running.' -ForegroundColor Yellow
  exit 0
}
if (-not (Test-Path -LiteralPath $MONITOR)) {
  Write-Host ("Monitor script not found: " + $MONITOR) -ForegroundColor Red
  exit 1
}
Start-Process -FilePath 'powershell.exe' -ArgumentList @(
  '-NoExit', '-ExecutionPolicy', 'Bypass', '-File', $MONITOR
) -WindowStyle Normal
Write-Host 'R.E.Y. // Runtime Execution & Yield Monitor launched.' -ForegroundColor Cyan
