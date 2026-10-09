@echo off
setlocal
call "%~1\export.bat"
if errorlevel 1 exit /b %errorlevel%
"%~2" -B -X utf8 "%~3" --exported --output "%~4" --target-output "%~5"
exit /b %errorlevel%
