# M3 visualization regressions. This file must remain pure ASCII.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $PSScriptRoot 'enter_fpga_env.ps1') | Out-Null
$iverilog = 'D:\Gowin\oss-cad-suite\bin\iverilog.exe'
$vvp = 'D:\Gowin\oss-cad-suite\bin\vvp.exe'
foreach ($tool in @($iverilog, $vvp)) {
    if (-not (Test-Path -LiteralPath $tool)) { throw "Missing simulator: $tool" }
}
$stage = Join-Path $env:TEMP ('m3_visual_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    $sources = @(
        'code\rtl\common\audio_defs_pkg.sv',
        'code\rtl\input\visualizer\visual_live_state.sv',
        'code\rtl\input\visualizer\visual_score_tracker.sv',
        'code\rtl\input\visualizer\visual_scene_renderer.sv',
        'code\rtl\input\visualizer\m3_visualizer.sv',
        'code\tb\input\visualizer\tb_visual_live_state.sv',
        'code\tb\input\visualizer\tb_visual_score_tracker.sv',
        'code\tb\input\visualizer\tb_m3_visualizer.sv'
    )
    $staged = @()
    for ($i = 0; $i -lt $sources.Count; $i++) {
        $source = Join-Path $repoRoot $sources[$i]
        if (-not (Test-Path -LiteralPath $source)) { throw "Missing source: $source" }
        $dest = Join-Path $stage ('src_' + $i + '.sv')
        Copy-Item -LiteralPath $source -Destination $dest
        $staged += $dest
    }
    foreach ($top in @('tb_visual_live_state','tb_visual_score_tracker','tb_m3_visualizer')) {
        $out = Join-Path $stage ($top + '.vvp')
        & $iverilog -g2012 -Wall -s $top -o $out @staged
        if ($LASTEXITCODE -ne 0) { throw "Compile failed: $top" }
        & $vvp $out
        if ($LASTEXITCODE -ne 0) { throw "Simulation failed: $top" }
    }
    Write-Host 'M3 visualization regressions: ALL PASS'
} finally {
    $resolved = [IO.Path]::GetFullPath($stage)
    $tempRoot = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith($tempRoot,[StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe cleanup target: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction SilentlyContinue
}
