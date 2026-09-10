@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%USERPROFILE%\.config\opencode\scripts\rey-monitor.ps1" %*
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] R.E.Y. Monitor exited with error code %ERRORLEVEL%.
    pause
)
