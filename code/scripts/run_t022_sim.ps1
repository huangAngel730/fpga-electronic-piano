# -----------------------------------------------------------------------------
# run_t022_sim.ps1
# T022 button-to-performance-event ModelSim regression.
#
# Usage from repository root:
#   .\code\scripts\run_t022_sim.ps1
#
# 2026-09-15, when T022 was integrated into develop: this file was originally
# authored on M3's branch, which still used the old CJK directory name and the
# flat rtl\input\button_event_converter.sv layout. The repository renamed that
# directory to plain ASCII "code" and moved rtl/input/ to one subdirectory per
# module, so both were updated here. Without this fix the script resolves paths
# that do not exist and fails on Copy-Item.
#
# This file must stay ASCII-only: Windows PowerShell 5.1 decodes BOM-less UTF-8
# sources as ANSI/GBK, and a single non-ASCII byte in the source can break the
# whole script. Note that ModelSim lives at a machine-specific path; override
# $modelSimBin below when running on a different machine.
# -----------------------------------------------------------------------------

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$modelSimBin = "E:\FPGA\Bpan\modelsim\modelsim1\win64"
# Machine-specific tool location: allow an override so this script is not tied
# to one workstation. Set MODELSIM_BIN to the win64 bin directory before running.
if ($env:MODELSIM_BIN) { $modelSimBin = $env:MODELSIM_BIN }
$vlib = Join-Path $modelSimBin "vlib.exe"
$vlog = Join-Path $modelSimBin "vlog.exe"
$vsim = Join-Path $modelSimBin "vsim.exe"

foreach ($tool in @($vlib, $vlog, $vsim)) {
    if (-not (Test-Path -LiteralPath $tool)) {
        Write-Host "Missing ModelSim tool: $tool" -ForegroundColor Red
        exit 1
    }
}

$codeDir = "code"
$sourcePaths = @(
    (Join-Path $repoRoot "$codeDir\rtl\common\audio_defs_pkg.sv"),
    (Join-Path $repoRoot "$codeDir\rtl\input\button_event_converter\button_event_converter.sv"),
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
