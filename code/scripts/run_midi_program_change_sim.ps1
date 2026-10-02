# Program Change parser, real UART and A+B scheduler regression.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$modelSimBin = 'E:\FPGA\Bpan\modelsim\modelsim1\win64'
if ($env:MODELSIM_BIN) { $modelSimBin = $env:MODELSIM_BIN }
$vlib = Join-Path $modelSimBin 'vlib.exe'
$vlog = Join-Path $modelSimBin 'vlog.exe'
$vsim = Join-Path $modelSimBin 'vsim.exe'
foreach ($tool in @($vlib, $vlog, $vsim)) {
    if (-not (Test-Path -LiteralPath $tool)) { throw "Missing tool: $tool" }
}
$runName = 'midi_program_change_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '_' + [guid]::NewGuid().ToString('N').Substring(0,8)
$logDir = Join-Path $repoRoot ('code\output\' + $runName)
New-Item -ItemType Directory -Path $logDir | Out-Null
$stage = Join-Path $env:TEMP ('midi_program_change_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
$sourcePaths = @(
    'code/rtl/common/audio_defs_pkg.sv',
    'code/rtl/common/uart_rx.sv',
    'code/rtl/input/midi_input/midi_event_parser.sv',
    'code/rtl/input/midi_input/midi_input.sv',
    'code/tb/input/tb_midi_program_change.sv',
    'code/tb/input/tb_midi_program_change_uart.sv',
    'code/tb/input/tb_midi_control_fairness_uart.sv'
)

function Invoke-ProgramTest {
    param([string]$Name, [string]$Top)
    Write-Host ('Running ' + $Name)
    $testStage = Join-Path $stage $Name
    New-Item -ItemType Directory -Path $testStage | Out-Null
    $stagedSources = @()
    for ($index = 0; $index -lt $sourcePaths.Count; $index++) {
        $destination = Join-Path $testStage ('src_' + $index + '.sv')
        Copy-Item -LiteralPath (Join-Path $repoRoot $sourcePaths[$index]) -Destination $destination
        $stagedSources += $destination
    }
    Push-Location $testStage
    try {
        $previousEap = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        $library = @(& $vlib work 2>&1)
        $libraryExit = $LASTEXITCODE
        $compile = @()
        $compileExit = -1
        if ($libraryExit -eq 0) {
            $compile = @(& $vlog -sv @stagedSources 2>&1)
            $compileExit = $LASTEXITCODE
        }
        $result = @()
        $runExit = -1
        if ($compileExit -eq 0) {
            $result = @(& $vsim -c $Top -do 'run -all; quit -f' 2>&1)
            $runExit = $LASTEXITCODE
        }
        $ErrorActionPreference = $previousEap
    } finally {
        Pop-Location
    }
    ($library + $compile) | Out-File -LiteralPath (Join-Path $logDir ($Name + '_compile.log')) -Encoding utf8
    $result | Out-File -LiteralPath (Join-Path $logDir ($Name + '_run.log')) -Encoding utf8
    $result | Where-Object { $_ -match 'PASS|Fatal|FAIL|Error' } | ForEach-Object { Write-Host $_ }
    $passed = $libraryExit -eq 0 -and $compileExit -eq 0 -and $runExit -eq 0 -and
        ($result -match 'PASS') -and -not ($result -match 'ERROR:|FAIL|Fatal:|\*\* Fatal')
    if (-not $passed) {
        ($library + $compile) | ForEach-Object { Write-Host $_ }
        throw ('Program Change regression failed: ' + $Name + '; logs: ' + $logDir)
    }
}

try {
    Invoke-ProgramTest -Name 'program_mapping_fifo' -Top 'tb_midi_program_change'
    Invoke-ProgramTest -Name 'program_uart_50m' -Top 'tb_midi_program_change_uart'
    Invoke-ProgramTest -Name 'program_scheduler_combo_uart_50m' -Top 'tb_midi_control_fairness_uart'
    Write-Host ('PASS Program Change regressions; logs: ' + $logDir)
} finally {
    $resolved = [IO.Path]::GetFullPath($stage)
    $tempRoot = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe cleanup target: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction SilentlyContinue
}
