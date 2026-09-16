param(
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

# Keep this script ASCII-only for Windows PowerShell 5.1 compatibility.
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$guiProgram = Join-Path $repoRoot "code\software\uart_status_gui.py"

if ([string]::IsNullOrWhiteSpace($PythonExe)) {
    $pythonCandidates = @(
        (Join-Path $env:USERPROFILE "miniconda3\python.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe")
    )
    $PythonExe = $pythonCandidates |
        Where-Object { Test-Path -LiteralPath $_ -PathType Leaf } |
        Select-Object -First 1
}

if ([string]::IsNullOrWhiteSpace($PythonExe) -or
    -not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) {
    throw "Python executable not found. Use -PythonExe with an absolute path."
}
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
