# Bounded MIDI scheduler regressions and required negative mutants.
# Uses ModelSim and stages ASCII-only paths for reproducible Windows runs.
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
$runName = 'midi_scheduler_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '_' + [guid]::NewGuid().ToString('N').Substring(0,8)
$logDir = Join-Path $repoRoot ('code\output\' + $runName)
New-Item -ItemType Directory -Path $logDir | Out-Null
$stage = Join-Path $env:TEMP ('midi_scheduler_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null

$sourcePaths = @(
    'code/rtl/common/audio_defs_pkg.sv',
    'code/rtl/common/uart_rx.sv',
    'code/rtl/input/midi_input/midi_event_parser.sv',
    'code/rtl/input/midi_input/midi_input.sv',
    'code/tb/input/tb_midi_controls.sv',
    'code/tb/input/tb_midi_control_queue.sv',
    'code/tb/input/tb_midi_controls_uart.sv',
    'code/tb/input/tb_midi_input.sv',
    'code/tb/input/tb_midi_cc64.sv',
    'code/tb/input/tb_midi_control_fairness.sv',
    'code/tb/input/tb_midi_control_fairness_uart.sv'
)
# Explicit decoding also protects UTF-8 RTL comments in mutant copies on PS5.1.
$parserText = Get-Content -LiteralPath (Join-Path $repoRoot $sourcePaths[2]) -Raw -Encoding UTF8

function Invoke-RtlTest {
    param(
        [string]$Name,
        [string]$Top,
        [string[]]$Extra = @(),
        [string]$ParserOverride = '',
        [bool]$ExpectPass = $true
    )
    Write-Host ('Running ' + $Name)
    $testStage = Join-Path $stage $Name
    New-Item -ItemType Directory -Path $testStage | Out-Null
    $stagedSources = @()
    for ($index = 0; $index -lt $sourcePaths.Count; $index++) {
        $destination = Join-Path $testStage ('src_' + $index + '.sv')
        if ($index -eq 2 -and $ParserOverride.Length -ne 0) {
            [IO.File]::WriteAllText($destination, $ParserOverride,
                [Text.UTF8Encoding]::new($false))
        } else {
            Copy-Item -LiteralPath (Join-Path $repoRoot $sourcePaths[$index]) -Destination $destination
        }
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
            $result = @(& $vsim -c @Extra $Top -do 'run -all; quit -f' 2>&1)
            $runExit = $LASTEXITCODE
        }
        $ErrorActionPreference = $previousEap
    } finally {
        Pop-Location
    }
    ($library + $compile) | Out-File -LiteralPath (Join-Path $logDir ($Name + '_compile.log')) -Encoding utf8
    $result | Out-File -LiteralPath (Join-Path $logDir ($Name + '_run.log')) -Encoding utf8
    $result | Where-Object { $_ -match 'PASS|Fatal|FAIL|Error' } | ForEach-Object { Write-Host $_ }
    $compiled = $libraryExit -eq 0 -and $compileExit -eq 0
    $passed = $compiled -and $runExit -eq 0 -and ($result -match 'PASS') -and
        -not ($result -match 'ERROR:|FAIL|Fatal:|\*\* Fatal')
    if ($ExpectPass -and -not $passed) {
        ($library + $compile) | ForEach-Object { Write-Host $_ }
        throw ('MIDI scheduler regression failed: ' + $Name + '; logs: ' + $logDir)
    }
    if (-not $ExpectPass) {
        if (-not $compiled) {
            ($library + $compile) | ForEach-Object { Write-Host $_ }
            throw ('Mutant did not compile, so rejection is not behavioral: ' + $Name)
        }
        if ($passed) {
            throw ('MIDI scheduler mutant escaped: ' + $Name + '; logs: ' + $logDir)
        }
        Write-Host ('PASS rejected mutant ' + $Name)
    }
}

try {
    Invoke-RtlTest -Name 'mapping' -Top 'tb_midi_controls'
    Invoke-RtlTest -Name 'queue_fast' -Top 'tb_midi_control_queue'
    Invoke-RtlTest -Name 'queue_50m' -Top 'tb_midi_control_queue' -Extra @('-gCLK_HZ=50000000')
    Invoke-RtlTest -Name 'uart_50m' -Top 'tb_midi_controls_uart'
    Invoke-RtlTest -Name 'note_uart_regression' -Top 'tb_midi_input'
    Invoke-RtlTest -Name 'cc64_regression' -Top 'tb_midi_cc64'
    Invoke-RtlTest -Name 'fairness_fast' -Top 'tb_midi_control_fairness'
    Invoke-RtlTest -Name 'fairness_50m' -Top 'tb_midi_control_fairness' -Extra @('-gCLK_HZ=50000000')
    Invoke-RtlTest -Name 'fairness_uart_50m' -Top 'tb_midi_control_fairness_uart'

    $oldFair = @'
            (((fifo_count == 0) && !parsed_discrete) ||
             (discrete_handshake && burst_limit_reached));
'@
    $oldOnly = @'
            ((fifo_count == 0) && !parsed_discrete);
'@
    $stallSafe = @'
            event_data = locked_event;
'@
    $stallBad = @'
            event_data = locked_event;
            if (parsed_control)
                event_data.control_value = parsed_event_data.control_value;
'@
    $rateSafe = "control_cooldown <= RATE_WIDTH'(CONTROL_INTERVAL - 1);"
    $rateBad = "control_cooldown <= '0;"
    foreach ($mutation in @(
        @('old_starvation', $oldFair, $oldOnly, 'tb_midi_control_fairness'),
        @('stalled_payload_mutation', $stallSafe, $stallBad, 'tb_midi_control_fairness'),
        @('no_rate_limit', $rateSafe, $rateBad, 'tb_midi_control_queue')
    )) {
        if (-not $parserText.Contains($mutation[1])) {
            throw ('Mutation anchor missing: ' + $mutation[0])
        }
        $mutantText = $parserText.Replace($mutation[1], $mutation[2])
        Invoke-RtlTest -Name $mutation[0] -Top $mutation[3] `
            -ParserOverride $mutantText -ExpectPass $false
    }
    Write-Host ('PASS bounded MIDI scheduler regressions and mutants; logs: ' + $logDir)
} finally {
    $resolved = [IO.Path]::GetFullPath($stage)
    $tempRoot = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe cleanup target: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction SilentlyContinue
}
