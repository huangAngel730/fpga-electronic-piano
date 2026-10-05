# M3 CC64 parser/UART and supplemental sustain lifecycle regressions.
# Pure ASCII; all compilation products live in an isolated temporary directory.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $PSScriptRoot 'enter_fpga_env.ps1') | Out-Null
$iv = 'D:\Gowin\oss-cad-suite\bin\iverilog.exe'
$vvp = 'D:\Gowin\oss-cad-suite\bin\vvp.exe'
$stage = Join-Path $env:TEMP ('cc64_input_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    $sources = @(
        'code/rtl/common/audio_defs_pkg.sv',
        'code/rtl/board/sustain_control_contract_pkg.sv',
        'code/rtl/common/uart_rx.sv',
        'code/rtl/input/midi_input/midi_event_parser.sv',
        'code/rtl/input/midi_input/midi_input.sv',
        'code/rtl/input/sustain_control/sustain_controller.sv',
        'code/tb/input/tb_midi_cc64.sv',
        'code/tb/input/tb_midi_input.sv',
        'code/tb/input/tb_sustain_controller.sv'
    )
    $staged = @()
    for ($i = 0; $i -lt $sources.Count; $i++) {
        $dest = Join-Path $stage ('src_' + $i + '.sv')
        Copy-Item -LiteralPath (Join-Path $repoRoot $sources[$i]) -Destination $dest
        $staged += $dest
    }
    Copy-Item -LiteralPath (Join-Path $repoRoot 'code/rtl/board/sustain_controller_ports.svh') -Destination $stage
    foreach ($top in @('tb_midi_cc64', 'tb_midi_input', 'tb_sustain_controller')) {
        $binary = Join-Path $stage ($top + '.vvp')
        $previousEap = $ErrorActionPreference
        $ErrorActionPreference = 'Continue'
        & $iv -g2012 -Wall -I $stage -s $top -o $binary @staged 2>&1 | ForEach-Object { Write-Host $_ }
        $compileExit = $LASTEXITCODE
        $result = @()
        $runExit = -1
        if ($compileExit -eq 0 -and (Test-Path -LiteralPath $binary)) {
            $result = & $vvp $binary 2>&1
            $runExit = $LASTEXITCODE
        }
        $ErrorActionPreference = $previousEap
        $result | ForEach-Object { Write-Host $_ }
        if ($compileExit -ne 0 -or $runExit -ne 0 -or
            -not ($result -match 'PASS') -or ($result -match 'ERROR:|FAIL|FATAL')) {
            throw "CC64 regression failed: $top"
        }
    }
    Write-Host 'PASS CC64 input and sustain supplemental regressions'
} finally {
    $resolved = [IO.Path]::GetFullPath($stage)
    $tempRoot = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe cleanup target: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction SilentlyContinue
}
