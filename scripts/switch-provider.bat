@echo off
title OpenCode Provider Switcher
color 0B
cls
echo.
echo  ╔══════════════════════════════════════════╗
echo  ║   OpenCode Free Model Provider Switcher  ║
echo  ╠══════════════════════════════════════════╣
echo  ║                                          ║
echo  ║  [1] Kilo      - kilo.ai free models     ║
echo  ║  [2] OpenCode  - opencode built-in free  ║
echo  ║  [3] OpenRouter - openrouter.ai free     ║
echo  ║  [0] Cancel                              ║
echo  ║                                          ║
echo  ╚══════════════════════════════════════════╝
echo.
set /p "choice=  Select provider [0-3]: "

if "%choice%"=="1" goto :kilo
if "%choice%"=="2" goto :opencode
if "%choice%"=="3" goto :openrouter
if "%choice%"=="0" goto :end
echo.
echo  Invalid choice. Please enter 0, 1, 2, or 3.
pause
goto :end

:kilo
set PROVIDER=kilo
set LABEL=Kilo (kilo.ai)
goto :switch

:opencode
set PROVIDER=opencode
set LABEL=OpenCode (built-in)
goto :switch

:openrouter
set PROVIDER=openrouter
set LABEL=OpenRouter (openrouter.ai)
goto :switch

:switch
echo.
echo  Switching to: %LABEL%
echo  ─────────────────────────────
powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0switch-provider.ps1" -Provider %PROVIDER%
echo.
echo  Restart OpenCode to use the new provider.
echo.
pause

:end
