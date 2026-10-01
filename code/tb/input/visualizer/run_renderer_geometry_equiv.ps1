# Renderer-only regression; pure ASCII for Windows PowerShell 5.1.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
. (Join-Path $root 'code/scripts/enter_fpga_env.ps1') | Out-Null
$stage = Join-Path $root 'code/output/renderer_geometry_equiv'
New-Item -ItemType Directory -Path $stage -Force | Out-Null
$rtl = Join-Path $root 'code/rtl/input/visualizer/visual_scene_renderer.sv'
$tb = Join-Path $PSScriptRoot 'tb_renderer_geometry_equiv.sv'
foreach($cfg in @(@(640,49,36),@(37,13,100),@(17,49,36),@(1,128,0))) {
    $exe = Join-Path $stage ('equiv_'+$cfg[0]+'_'+$cfg[1]+'.vvp')
    & 'D:/Gowin/oss-cad-suite/bin/iverilog.exe' -g2012 -s tb_renderer_geometry_equiv -P "tb_renderer_geometry_equiv.W=$($cfg[0])" -P "tb_renderer_geometry_equiv.N=$($cfg[1])" -P "tb_renderer_geometry_equiv.BASE=$($cfg[2])" -o $exe $rtl $tb
    if($LASTEXITCODE -ne 0){throw 'Geometry compile failed'}
    & 'D:/Gowin/oss-cad-suite/bin/vvp.exe' $exe
    if($LASTEXITCODE -ne 0){throw 'Geometry equivalence failed'}
}
