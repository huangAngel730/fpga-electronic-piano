@echo off
setlocal

set "REQ=%~dp0requirements-midi.txt"
set "RESOLVER=%~dp0resolve_midi_python.cmd"

call "%RESOLVER%"
if errorlevel 1 goto no_python

echo Using Python:
echo   %MIDI_MONITOR_PYTHON%
"%MIDI_MONITOR_PYTHON%" --version

if /i "%~1"=="--check" exit /b 0

echo.
echo Installing MIDI monitor dependencies...
"%MIDI_MONITOR_PYTHON%" -m pip install -r "%REQ%"
if errorlevel 1 goto install_failed

"%MIDI_MONITOR_PYTHON%" -c "import mido, rtmidi; print('Verified: mido and python-rtmidi can be imported.')"
if errorlevel 1 goto verify_failed

goto success

:no_python
echo.
echo No usable Python 3.9 or newer was found.
echo This launcher checked Miniconda, Anaconda, standard Python folders, and PATH.
echo If Python is installed elsewhere, set MIDI_MONITOR_PYTHON to python.exe and retry.
pause
exit /b 1

:install_failed
echo.
echo Dependency installation failed.
echo The detailed pip error is shown above. Check the network and retry.
pause
exit /b 1

:verify_failed
echo.
echo Packages were downloaded, but the import check failed.
echo The detailed Python error is shown above.
pause
exit /b 1

:success
echo.
echo MIDI monitor dependencies installed successfully.
pause
exit /b 0
