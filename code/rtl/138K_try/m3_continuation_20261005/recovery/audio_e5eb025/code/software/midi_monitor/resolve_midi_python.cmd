@echo off
rem Find a usable Python 3 interpreter for the MIDI monitor.
rem The selected absolute path is returned in MIDI_MONITOR_PYTHON.

set "_MIDI_MONITOR_OVERRIDE=%MIDI_MONITOR_PYTHON%"
set "MIDI_MONITOR_PYTHON="

call :try_candidate "%_MIDI_MONITOR_OVERRIDE%"
call :try_candidate "%USERPROFILE%\miniconda3\python.exe"
call :try_candidate "%USERPROFILE%\anaconda3\python.exe"
call :try_candidate "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
call :try_candidate "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
call :try_candidate "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
call :try_candidate "%LOCALAPPDATA%\Programs\Python\Python310\python.exe"
call :try_candidate "%LOCALAPPDATA%\Programs\Python\Python39\python.exe"
call :try_candidate "C:\ProgramData\anaconda3\python.exe"
call :try_candidate "D:\ProgramData\anaconda3\python.exe"

for /f "delims=" %%P in ('where python 2^>nul') do call :try_candidate "%%P"
for /f "delims=" %%P in ('where python3 2^>nul') do call :try_candidate "%%P"

if defined MIDI_MONITOR_PYTHON exit /b 0
exit /b 1

:try_candidate
if defined MIDI_MONITOR_PYTHON exit /b 0
if "%~1"=="" exit /b 0
if not exist "%~1" exit /b 0
"%~1" -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 9) else 1)" >nul 2>nul
if errorlevel 1 exit /b 0
set "MIDI_MONITOR_PYTHON=%~1"
exit /b 0
