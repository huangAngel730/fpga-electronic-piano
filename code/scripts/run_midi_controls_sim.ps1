# M3 Pitch Bend/CC1 mapping, transport queue, real-rate and UART regressions.
# No public build files are changed. Logs live in a unique ignored output dir.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $PSScriptRoot 'enter_fpga_env.ps1') | Out-Null
$iv = 'D:\Gowin\oss-cad-suite\bin\iverilog.exe'
$vvp = 'D:\Gowin\oss-cad-suite\bin\vvp.exe'
foreach ($tool in @($iv, $vvp)) {
    if (-not (Test-Path -LiteralPath $tool)) { throw "Missing tool: $tool" }
}
$runName = 'midi_controls_' + (Get-Date -Format 'yyyyMMdd_HHmmss') + '_' + [guid]::NewGuid().ToString('N').Substring(0,8)
$logDir = Join-Path $repoRoot ('code\output\' + $runName)
New-Item -ItemType Directory -Path $logDir | Out-Null
$stage = Join-Path $env:TEMP ('midi_controls_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    $sources = @(
        'code/rtl/common/audio_defs_pkg.sv',
        'code/rtl/common/uart_rx.sv',
        'code/rtl/input/midi_input/midi_event_parser.sv',
        'code/rtl/input/midi_input/midi_input.sv',
        'code/tb/input/tb_midi_controls.sv',
        'code/tb/input/tb_midi_control_queue.sv',
        'code/tb/input/tb_midi_controls_uart.sv',
        'code/tb/input/tb_midi_input.sv',
        'code/tb/input/tb_midi_cc64.sv'
    )
    $staged = @()
    for ($i = 0; $i -lt $sources.Count; $i++) {
        $dest = Join-Path $stage ('src_' + $i + '.sv')
        Copy-Item -LiteralPath (Join-Path $repoRoot $sources[$i]) -Destination $dest
        $staged += $dest
    }
    $tests = @(
        @{Name='mapping'; Top='tb_midi_controls'; Extra=@()},
        @{Name='queue_fast'; Top='tb_midi_control_queue'; Extra=@()},
        @{Name='queue_50m'; Top='tb_midi_control_queue'; Extra=@('-Ptb_midi_control_queue.CLK_HZ=50000000')},
        @{Name='uart_50m'; Top='tb_midi_controls_uart'; Extra=@()},
        @{Name='note_uart_regression'; Top='tb_midi_input'; Extra=@()},
        @{Name='cc64_regression'; Top='tb_midi_cc64'; Extra=@()}
    )
    foreach ($test in $tests) {
        Write-Host ('Running ' + $test.Name)
        $binary = Join-Path $stage ($test.Name + '.vvp')
        $extra = $test.Extra
        $previousEap = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        $compile = @(& $iv -g2012 -Wall -s $test.Top @extra -o $binary @staged 2>&1)
        $compileExit = $LASTEXITCODE
        $result = @(); $runExit = -1
        if ($compileExit -eq 0 -and (Test-Path -LiteralPath $binary)) {
            $result = @(& $vvp $binary 2>&1)
            $runExit = $LASTEXITCODE
        }
        $ErrorActionPreference = $previousEap
        $compile | Out-File -LiteralPath (Join-Path $logDir ($test.Name + '_compile.log')) -Encoding utf8
        $result | Out-File -LiteralPath (Join-Path $logDir ($test.Name + '_run.log')) -Encoding utf8
        $result | ForEach-Object { Write-Host $_ }
        if ($compileExit -ne 0 -or $runExit -ne 0 -or
            -not ($result -match 'PASS') -or ($result -match 'ERROR:|FAIL|FATAL')) {
            $compile | ForEach-Object { Write-Host $_ }
            throw ('MIDI controls regression failed: ' + $test.Name + '; logs: ' + $logDir)
        }
    }
    Write-Host ('PASS all MIDI controls regressions; logs: ' + $logDir)
} finally {
    $resolved = [IO.Path]::GetFullPath($stage)
    $tempRoot = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe cleanup target: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction SilentlyContinue
}
