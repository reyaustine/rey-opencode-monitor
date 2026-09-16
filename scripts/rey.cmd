@echo off
if exist "%USERPROFILE%\opencode-swarm-pack\bin\rey.js" (
    node "%USERPROFILE%\opencode-swarm-pack\bin\rey.js" %*
) else (
    node "%USERPROFILE%\.config\opencode\bin\rey.js" %*
)
if %ERRORLEVEL% NEQ 0 (
    echo.
    echo [!] R.E.Y. CLI exited with error code %ERRORLEVEL%.
    pause
)
