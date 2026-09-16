@echo off
setlocal

set "PYTHON_EXE=%USERPROFILE%\miniconda3\pythonw.exe"
if exist "%PYTHON_EXE%" goto launch

where pythonw.exe >nul 2>&1
if errorlevel 1 goto missing_python
set "PYTHON_EXE=pythonw.exe"

:launch
start "" "%PYTHON_EXE%" -X utf8 -B "%~dp0uart_status_gui.py"
exit /b 0

:missing_python
echo Python GUI executable was not found.
echo Expected: %%USERPROFILE%%\miniconda3\pythonw.exe
pause
exit /b 1
