# M2 isolated display timing and event CDC regressions. Pure ASCII source.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $PSScriptRoot 'enter_fpga_env.ps1') | Out-Null
$iverilog = 'D:\Gowin\oss-cad-suite\bin\iverilog.exe'
$vvp = 'D:\Gowin\oss-cad-suite\bin\vvp.exe'
foreach ($tool in @($iverilog, $vvp)) {
    if (-not (Test-Path -LiteralPath $tool)) { throw "Missing simulator: $tool" }
}
$stage = Join-Path $env:TEMP ('visual_m2_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    $sources = @(
        'code\rtl\common\audio_defs_pkg.sv',
        'code\rtl\common\reset_sync.sv',
        'code\rtl\common\visual_event_bridge.sv',
        'code\rtl\common\video_scan_timing.sv',
        'code\tb\common\tb_visual_event_bridge.sv',
        'code\tb\common\tb_video_scan_timing.sv'
    )
    $staged = @()
    for ($i=0; $i -lt $sources.Count; $i++) {
        $source = Join-Path $repoRoot $sources[$i]
        if (-not (Test-Path -LiteralPath $source)) { throw "Missing source: $source" }
        $dest = Join-Path $stage ('src_' + $i + '.sv')
        Copy-Item -LiteralPath $source -Destination $dest
        $staged += $dest
    }
    foreach ($half in @(7,17,41)) {
        $out = Join-Path $stage ('bridge_' + $half + '.vvp')
        & $iverilog -g2012 -Wall -s tb_visual_event_bridge -P "tb_visual_event_bridge.VIDEO_HALF=$half" -o $out @staged
        if ($LASTEXITCODE -ne 0) { throw "Bridge compile failed: $half" }
        & $vvp $out
        if ($LASTEXITCODE -ne 0) { throw "Bridge simulation failed: $half" }
    }
    $out = Join-Path $stage 'raster.vvp'
    & $iverilog -g2012 -Wall -s tb_video_scan_timing -o $out @staged
    if ($LASTEXITCODE -ne 0) { throw 'Raster compile failed' }
    & $vvp $out
    if ($LASTEXITCODE -ne 0) { throw 'Raster simulation failed' }
    Write-Host 'M2 display timing and CDC: ALL PASS'
} finally {
    # Verify temp target before any recursive delete (Windows workspace rule).
    $resolved = [IO.Path]::GetFullPath($stage)
    $tempRoot = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith($tempRoot,[StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe cleanup target: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction SilentlyContinue
}
