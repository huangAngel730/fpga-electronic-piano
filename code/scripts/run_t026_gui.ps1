param(
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

# Keep this script ASCII-only for Windows PowerShell 5.1 compatibility.
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$guiProgram = Join-Path $repoRoot "code\software\uart_test\uart_status_gui.py"
. (Join-Path $PSScriptRoot "resolve_t026_python.ps1")
$PythonExe = Resolve-T026Python -PythonExe $PythonExe
if (-not (Test-Path -LiteralPath $guiProgram -PathType Leaf)) {
    throw "T026 GUI not found: $guiProgram"
}

$savedPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    & $PythonExe -X utf8 -B $guiProgram
    $pythonExitCode = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $savedPreference
}

exit $pythonExitCode
