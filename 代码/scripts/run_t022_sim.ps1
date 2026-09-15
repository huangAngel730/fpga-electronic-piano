# -----------------------------------------------------------------------------
# run_t022_sim.ps1
# T022 button-to-performance-event ModelSim regression.
#
# Usage from repository root:
#   .\<code-dir>\scripts\run_t022_sim.ps1
#
# The real directory name for "code" is assembled below so this file remains
# ASCII-only and works in Windows PowerShell 5.1 without an encoding dependency.
# -----------------------------------------------------------------------------

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$modelSimBin = "E:\FPGA\Bpan\modelsim\modelsim1\win64"
$vlib = Join-Path $modelSimBin "vlib.exe"
$vlog = Join-Path $modelSimBin "vlog.exe"
$vsim = Join-Path $modelSimBin "vsim.exe"

foreach ($tool in @($vlib, $vlog, $vsim)) {
    if (-not (Test-Path -LiteralPath $tool)) {
        Write-Host "Missing ModelSim tool: $tool" -ForegroundColor Red
        exit 1
    }
}

$codeDir = [char]0x4EE3 + [char]0x7801
$sourcePaths = @(
    (Join-Path $repoRoot "$codeDir\rtl\common\audio_defs_pkg.sv"),
    (Join-Path $repoRoot "$codeDir\rtl\input\button_event_converter.sv"),
    (Join-Path $repoRoot "$codeDir\tb\input\tb_button_event_converter.sv")
)

$stageRoot = Join-Path $env:TEMP ("t022_modelsim_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $stageRoot | Out-Null

$stagedSources = @()
for ($index = 0; $index -lt $sourcePaths.Count; $index++) {
    $destination = Join-Path $stageRoot ("src_" + $index + ".sv")
    Copy-Item -LiteralPath $sourcePaths[$index] -Destination $destination
    $stagedSources += $destination
}

Push-Location $stageRoot
try {
    & $vlib work
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    & $vlog -sv @stagedSources
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

    $simOutput = & $vsim -c tb_button_event_converter -do "run -all; quit -f" 2>&1
    $simExitCode = $LASTEXITCODE
    $simOutput | ForEach-Object { Write-Host $_ }

    if (($simExitCode -ne 0) -or
        (-not ($simOutput -match "PASS: tb_button_event_converter completed all checks"))) {
        exit 1
    }
    exit 0
}
finally {
    Pop-Location
}
