@echo off
setlocal

rem Use the same Python discovery as the GUI and test PowerShell scripts.
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\scripts\run_t026_gui.ps1"
if errorlevel 1 (
    echo GUI startup failed. Check the message above.
    pause
    exit /b 1
)
exit /b 0
