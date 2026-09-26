@echo off
setlocal

set "APP=%~dp0midi_monitor_gui.py"
set "RESOLVER=%~dp0resolve_midi_python.cmd"

call "%RESOLVER%"
if errorlevel 1 goto no_python

"%MIDI_MONITOR_PYTHON%" -X utf8 "%APP%"
if not errorlevel 1 exit /b 0

echo.
echo MIDI monitor startup failed.
echo Python used: %MIDI_MONITOR_PYTHON%
echo The detailed Python error is shown above.
echo.
pause
exit /b 1

:no_python
echo.
echo No usable Python 3.9 or newer was found.
echo Run install_midi_monitor_dependencies.cmd first.
echo.
pause
exit /b 1
