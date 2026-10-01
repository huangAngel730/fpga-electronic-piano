# Compare against frozen M3 tracker at b61ec93; pure ASCII.
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
. (Join-Path $root 'code/scripts/enter_fpga_env.ps1') | Out-Null
$stage=Join-Path $root 'code/output/tracker_timing_equiv_20261001'
New-Item -ItemType Directory -Force -Path $stage | Out-Null
$old=& git -C $root show b61ec93733bd99630f87d91fa8440ef61fa4355f:code/rtl/input/visualizer/visual_score_tracker.sv
if($LASTEXITCODE -ne 0){throw 'Frozen tracker reference unavailable'}
$text=($old -join "`n")+"`n"
$text=$text.Replace('module visual_score_tracker #','module visual_score_tracker_reference #')
$ref=Join-Path $stage 'visual_score_tracker_reference.sv'
[IO.File]::WriteAllText($ref,$text,[Text.UTF8Encoding]::new($false))
$rtl=Join-Path $root 'code/rtl/input/visualizer/visual_score_tracker.sv'
$pkg=Join-Path $root 'code/rtl/common/audio_defs_pkg.sv'
$tb=Join-Path $PSScriptRoot 'tb_tracker_timing_equiv.sv'
# Padded tree, narrow frame width, tiny/odd divisors, zero travel, wide divisor.
foreach($cfg in @(@(8,32,120,400),@(3,8,119,400),@(1,32,1,400),@(5,32,127,0),@(8,32,2147483647,400))) {
    $name='tracker_'+$cfg[0]+'_'+$cfg[1]+'_'+$cfg[2]
    $exe=Join-Path $stage ($name+'.vvp')
    & 'D:/Gowin/oss-cad-suite/bin/iverilog.exe' -g2012 -s tb_tracker_timing_equiv -P "tb_tracker_timing_equiv.SLOTS=$($cfg[0])" -P "tb_tracker_timing_equiv.FW=$($cfg[1])" -P "tb_tracker_timing_equiv.PREVIEW=$($cfg[2])" -P "tb_tracker_timing_equiv.TRAVEL=$($cfg[3])" -o $exe $pkg $rtl $ref $tb
    if($LASTEXITCODE -ne 0){throw 'Tracker equivalence compile failed'}
    & 'D:/Gowin/oss-cad-suite/bin/vvp.exe' $exe
    if($LASTEXITCODE -ne 0){throw 'Tracker equivalence failed'}
}
