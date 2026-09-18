# -----------------------------------------------------------------------------
# run_midi_input_sim.ps1
# ModelSim regression for the standard MIDI input chain.
#
# Usage from repository root:
#   .\code\scripts\run_midi_input_sim.ps1
#
# The script is ASCII-only for Windows PowerShell 5.1 compatibility.
# Override MODELSIM_BIN if ModelSim is installed in another directory.
# -----------------------------------------------------------------------------

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$modelSimBin = "E:\FPGA\Bpan\modelsim\modelsim1\win64"
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

$sourcePaths = @(
    (Join-Path $repoRoot "code\rtl\common\audio_defs_pkg.sv"),
    (Join-Path $repoRoot "code\rtl\common\uart_rx.sv"),
    (Join-Path $repoRoot "code\rtl\input\midi_input\midi_event_parser.sv"),
    (Join-Path $repoRoot "code\rtl\input\midi_input\midi_input.sv"),
    (Join-Path $repoRoot "code\tb\input\tb_midi_input.sv")
)

$stageRoot = Join-Path $env:TEMP ("midi_input_modelsim_" + [guid]::NewGuid().ToString("N"))
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

    $simOutput = & $vsim -c tb_midi_input -do "run -all; quit -f" 2>&1
    $simExitCode = $LASTEXITCODE
    $simOutput | ForEach-Object { Write-Host $_ }

    $passMarker = "PASS: tb_midi_input completed"
    $failPattern = "ERROR:|FAIL:|Fatal:|\*\* Fatal"
    if (($simExitCode -ne 0) -or
        (-not ($simOutput -match $passMarker)) -or
        ($simOutput -match $failPattern)) {
        exit 1
    }
    exit 0
}
finally {
    Pop-Location
}
