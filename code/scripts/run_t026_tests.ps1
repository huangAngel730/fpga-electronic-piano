param(
    [string]$PythonExe = ""
)

$ErrorActionPreference = "Stop"

# Keep this script ASCII-only for Windows PowerShell 5.1 compatibility.
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$softwareDir = Join-Path $repoRoot "code\software"
$programSource = Join-Path $softwareDir "uart_status_monitor.py"
$guiSource = Join-Path $softwareDir "uart_status_gui.py"
$testSource = Join-Path (Join-Path $softwareDir "tests") "test_uart_status_monitor.py"
. (Join-Path $PSScriptRoot "resolve_t026_python.ps1")
$PythonExe = Resolve-T026Python -PythonExe $PythonExe

if (-not (Test-Path -LiteralPath $programSource -PathType Leaf)) {
    throw "T026 program not found: $programSource"
}
if (-not (Test-Path -LiteralPath $guiSource -PathType Leaf)) {
    throw "T026 GUI not found: $guiSource"
}
if (-not (Test-Path -LiteralPath $testSource -PathType Leaf)) {
    throw "T026 tests not found: $testSource"
}

function Invoke-Python {
    param(
        [string[]]$Arguments
    )

    $savedPreference = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        & $PythonExe @Arguments
        $pythonExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $savedPreference
    }

    if ($pythonExitCode -ne 0) {
        exit $pythonExitCode
    }
}

# Stage only T026 files under an ASCII-only temporary path. Nothing is
# removed afterward, which preserves the project's write-only safety rule.
$stageRoot = Join-Path $env:TEMP ("t026_tests_" + [guid]::NewGuid().ToString("N"))
$stageSoftware = Join-Path $stageRoot "software"
$stageTests = Join-Path $stageSoftware "tests"
New-Item -ItemType Directory -Path $stageTests | Out-Null
Copy-Item -LiteralPath $programSource -Destination $stageSoftware
Copy-Item -LiteralPath $guiSource -Destination $stageSoftware
Copy-Item -LiteralPath $testSource -Destination $stageTests

$stageProgram = Join-Path $stageSoftware "uart_status_monitor.py"
$stageGui = Join-Path $stageSoftware "uart_status_gui.py"

Write-Host "[T026] Python: $PythonExe"
Write-Host "[T026] Staged files: $stageRoot"

Write-Host "[T026] Syntax check"
Invoke-Python -Arguments @(
    "-X",
    "utf8",
    "-B",
    "-m",
    "py_compile",
    $stageProgram,
    $stageGui
)

Write-Host "[T026] Unit tests"
Invoke-Python -Arguments @(
    "-X",
    "utf8",
    "-B",
    "-m",
    "unittest",
    "discover",
    "-s",
    $stageTests,
    "-p",
    "test_*.py",
    "-v"
)

Write-Host "[T026] Simulation smoke test"
Invoke-Python -Arguments @(
    "-X",
    "utf8",
    "-B",
    $stageProgram,
    "--simulate",
    "--count",
    "3",
    "--interval",
    "0"
)

Write-Host "[T026] PASS"
