# Real50/25MHz clocks; small raster, actual internal display logic.
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '../../../..')).Path
. (Join-Path $root 'code/scripts/enter_fpga_env.ps1') | Out-Null
$out=Join-Path $root 'code/output/diagnostic_score_20261002'
New-Item -ItemType Directory -Force -Path $out | Out-Null
$sources=@('code/rtl/common/audio_defs_pkg.sv','code/rtl/common/reset_sync.sv',
 'code/rtl/common/visual_event_bridge.sv','code/rtl/common/visual_mailbox_cdc.sv',
 'code/rtl/common/visual_control_bridge.sv','code/rtl/common/video_scan_timing.sv',
 'code/rtl/input/visualizer/visual_live_state.sv','code/rtl/input/visualizer/visual_score_tracker.sv',
 'code/rtl/input/visualizer/visual_scene_renderer.sv','code/rtl/input/visualizer/visual_hit_flash.sv','code/rtl/input/visualizer/m3_visualizer.sv',
 'code/rtl/board/audio_visual_display_probe.sv','code/tb/board/audio_visual_phy_model.sv',
 'code/tb/input/visualizer/tb_diagnostic_score_progress.sv') | ForEach-Object {Join-Path $root $_}
$exe=Join-Path $out 'progress.vvp'
& 'D:/Gowin/oss-cad-suite/bin/iverilog.exe' -g2012 -s tb_diagnostic_score_progress -o $exe @sources
if($LASTEXITCODE -ne 0){throw 'Diagnostic compile failed'}
& 'D:/Gowin/oss-cad-suite/bin/vvp.exe' $exe
if($LASTEXITCODE -ne 0){throw 'Diagnostic timeline failed'}
