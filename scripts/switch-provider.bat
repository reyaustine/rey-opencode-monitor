@echo off
title OpenCode Provider Switcher & IDE Visibility Manager
python "%~dp0rey-switch.py" %*
if %ERRORLEVEL% NEQ 0 (
    powershell -ExecutionPolicy Bypass -NoProfile -File "%~dp0switch-provider.ps1" %*
)

