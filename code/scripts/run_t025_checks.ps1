# T025 self-check: UART STAT output and shared performance-event FIFO.
# Run from repository root: .\code\scripts\run_t025_checks.ps1
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $repoRoot

& (Join-Path $PSScriptRoot 'run_t025_sim.ps1')
if (-not $?) { throw 'T025 UART status test failed' }

. (Join-Path $PSScriptRoot 'enter_fpga_env.ps1') | Out-Null
$iverilog = 'D:\Gowin\oss-cad-suite\bin\iverilog.exe'
$vvp = 'D:\Gowin\oss-cad-suite\bin\vvp.exe'
foreach ($tool in @($iverilog, $vvp)) {
    if (-not (Test-Path -LiteralPath $tool)) { throw "Missing simulator: $tool" }
}

$stage = Join-Path $env:TEMP ('t025_checks_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    $sources = @(
        'code\rtl\common\audio_defs_pkg.sv',
        'code\rtl\common\performance_event_fifo.sv',
        'code\tb\common\tb_performance_event_fifo.sv'
    )
    $staged = @()
    for ($i = 0; $i -lt $sources.Count; $i++) {
        $source = Join-Path $repoRoot $sources[$i]
        if (-not (Test-Path -LiteralPath $source)) { throw "Missing source: $source" }
        $destination = Join-Path $stage ('src_' + $i + '.sv')
        Copy-Item -LiteralPath $source -Destination $destination
        $staged += $destination
    }

    $output = Join-Path $stage 'tb_performance_event_fifo.vvp'
    & $iverilog -g2012 -Wall -s tb_performance_event_fifo -o $output @staged
    if ($LASTEXITCODE -ne 0) { throw 'T025 common FIFO compile failed' }
    & $vvp $output
    if ($LASTEXITCODE -ne 0) { throw 'T025 common FIFO simulation failed' }
    $counterOut = Join-Path $stage 'tb_system_status_counters.vvp'
    $counterRtl = Join-Path $stage 'status_counters.sv'
    $counterTb = Join-Path $stage 'tb_system_status_counters.sv'
    Copy-Item -LiteralPath (Join-Path $repoRoot 'code\rtl\common\system_status_counters.sv') -Destination $counterRtl
    Copy-Item -LiteralPath (Join-Path $repoRoot 'code\tb\common\tb_system_status_counters.sv') -Destination $counterTb
    & $iverilog -g2012 -Wall -s tb_system_status_counters -o $counterOut $counterRtl $counterTb
    if ($LASTEXITCODE -ne 0) { throw 'T025 status counters compile failed' }
    & $vvp $counterOut
    if ($LASTEXITCODE -ne 0) { throw 'T025 status counters simulation failed' }
    Write-Host 'T025 UART status and common FIFO and counters: ALL PASS'
}
finally {
    Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
}
