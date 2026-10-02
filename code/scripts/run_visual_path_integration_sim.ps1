# M2 standalone bridge + scan + M3 wrapper connection test.
# M3 sources are read-only; -VisualizerRoot may point at a newer checkout.
param([string]$VisualizerRoot)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
if (-not $VisualizerRoot) { $VisualizerRoot = $repoRoot }
$visualRoot = (Resolve-Path -LiteralPath $VisualizerRoot).Path
. (Join-Path $PSScriptRoot 'enter_fpga_env.ps1') | Out-Null
$iverilog = 'D:\Gowin\oss-cad-suite\bin\iverilog.exe'
$vvp = 'D:\Gowin\oss-cad-suite\bin\vvp.exe'
foreach ($tool in @($iverilog,$vvp)) {
    if (-not (Test-Path -LiteralPath $tool)) { throw "Missing simulator: $tool" }
}
$src = @(
    (Join-Path $repoRoot 'code\rtl\common\audio_defs_pkg.sv'),
    (Join-Path $repoRoot 'code\rtl\common\reset_sync.sv'),
    (Join-Path $repoRoot 'code\rtl\common\visual_event_bridge.sv'),
    (Join-Path $repoRoot 'code\rtl\common\visual_mailbox_cdc.sv'),
    (Join-Path $repoRoot 'code\rtl\common\visual_control_bridge.sv'),
    (Join-Path $repoRoot 'code\rtl\common\video_scan_timing.sv')
)
foreach ($file in @('visual_live_state.sv','visual_score_tracker.sv',
                    'visual_scene_renderer.sv','visual_hit_flash.sv','m3_visualizer.sv')) {
    $src += Join-Path $visualRoot ('code\rtl\input\visualizer\'+$file)
}
$src += Join-Path $repoRoot 'code\tb\board\tb_visual_path_integration.sv'
$stage = Join-Path $env:TEMP ('visual_path_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    $staged = @()
    for ($i = 0; $i -lt $src.Count; $i++) {
        if (-not (Test-Path -LiteralPath $src[$i] -PathType Leaf)) {
            throw "Missing independent source: $($src[$i])"
        }
        $dest = Join-Path $stage ('src_'+$i+'.sv')
        Copy-Item -LiteralPath $src[$i] -Destination $dest
        $staged += $dest
    }
    $out = Join-Path $stage 'visual_path.vvp'
    $saved = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        & $iverilog -g2012 -Wall -s tb_visual_path_integration -o $out @staged
        $compileCode = $LASTEXITCODE
    } finally { $ErrorActionPreference = $saved }
    if ($compileCode -ne 0) { throw "Visual path compile failed: $compileCode" }
    & $vvp $out
    if ($LASTEXITCODE -ne 0) { throw "Visual path simulation failed: $LASTEXITCODE" }
    Write-Host 'PASS M2 visual path connection (module-level behavior only)'
} finally {
    $resolved = [IO.Path]::GetFullPath($stage)
    $tempRoot = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')+'\'
    if (-not $resolved.StartsWith($tempRoot,[StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe cleanup target: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction SilentlyContinue
}
