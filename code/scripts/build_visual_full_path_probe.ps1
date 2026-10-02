# M2 independent visual resource/STA probe. FAIL is the expected current result.
# Does not touch the electronic piano project, program SRAM, or modify M3 RTL.
param(
    [Parameter(Mandatory=$true)][string]$VisualizerRoot,
    [Parameter(Mandatory=$true)][string]$GuiDviIpDir,
    [Parameter(Mandatory=$true)][string]$ReferenceRoot,
    [ValidateSet('auto','measured')][string]$SerialResetPlacement = 'auto'
)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$m3 = (Resolve-Path -LiteralPath $VisualizerRoot).Path
$gui = (Resolve-Path -LiteralPath $GuiDviIpDir).Path
$reference = (Resolve-Path -LiteralPath $ReferenceRoot).Path
$source = Join-Path $repoRoot 'code\rtl\board\visual_full_path_probe.sv'
$vendorBuild = Join-Path $repoRoot 'code\output\hdmi_link_probe\vendor'
$pll = Join-Path $vendorBuild 'TMDS_PLL_800_600_60.v'
$dvi = Join-Path $vendorBuild 'DVI_TX_Top.v'
$pllHash = 'EDEDFD3E361C7E9B4523DE6B3B50E00C98BAED5B9900A361C606AB574376F9BA'
$dviHash = 'B378C6A41D06A14215DC9EC54ED20BFC91309A0BB1543C589246717DA3AEE2AB'
# Reuse the already reviewed M2 GUI-IP build entry point, which rejects
# missing/altered GUI config, code, netlist, macro, and generation log.
if (-not (Test-Path -LiteralPath $pll -PathType Leaf) -or
    -not (Test-Path -LiteralPath $dvi -PathType Leaf) -or
    (Get-FileHash -LiteralPath $pll -Algorithm SHA256).Hash -ne $pllHash -or
    (Get-FileHash -LiteralPath $dvi -Algorithm SHA256).Hash -ne $dviHash) {
    & (Join-Path $PSScriptRoot 'build_hdmi_link_probe.ps1') `
      -ReferenceRoot $reference -GeneratedDviIpDir $gui -Flow all
    if ($LASTEXITCODE -ne 0) { throw 'HDMI vendor preflight failed' }
}
if ((Get-FileHash -LiteralPath $pll -Algorithm SHA256).Hash -ne $pllHash -or
    (Get-FileHash -LiteralPath $dvi -Algorithm SHA256).Hash -ne $dviHash) {
    throw 'Unreviewed PLL or GUI DVI source'
}
$common = @(
    'audio_defs_pkg.sv', 'reset_sync.sv',
    'visual_event_bridge.sv', 'video_scan_timing.sv',
    'visual_mailbox_cdc.sv', 'visual_control_bridge.sv'
) | ForEach-Object { Join-Path $repoRoot ('code\rtl\common\' + $_) }
$visual = @(
    'visual_live_state.sv', 'visual_score_tracker.sv',
    'visual_scene_renderer.sv', 'visual_hit_flash.sv', 'm3_visualizer.sv'
) | ForEach-Object { Join-Path $m3 ('code\rtl\input\visualizer\' + $_) }
$sources = @($common) + @($pll,$dvi) + @($visual) + @($source)
foreach ($file in $sources) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "Missing source: $file"
    }
}
$out = Join-Path $repoRoot 'code\output\visual_full_path_probe'
if ($SerialResetPlacement -eq 'measured') {
    $out = Join-Path $out 'measured_serial_reset'
}
New-Item -ItemType Directory -Force -Path $out | Out-Null
$physicalConstraint = Join-Path $repoRoot 'code\constraints\hdmi_link_probe.cst'
if ($SerialResetPlacement -eq 'measured') {
    # Place only the two existing M2 serial-reset FFs. All HDMI pins, IO
    # standards, PLL and M3 sources stay in their reviewed configuration.
    $cstText = [IO.File]::ReadAllText($physicalConstraint)
    $expected = 'INS_LOC "u_video_pll/PLLA_inst" PLL_R[0];'
    if ($cstText.Split(@($expected),[StringSplitOptions]::None).Length -ne 2) {
        throw 'Unexpected HDMI CST input; refusing reset placement trial'
    }
    $cstText += "`n// M2 measured serial-reset FF placement, independent probe only.`n"
    $cstText += 'INS_LOC "u_serial_reset/sync_chain_0_s0" R49C101[1][A];' + "`n"
    $cstText += 'INS_LOC "u_serial_reset/sync_chain_1_s0" R49C101[1][B];' + "`n"
    $physicalConstraint = Join-Path $out 'measured_serial_reset.cst'
    [IO.File]::WriteAllText($physicalConstraint,$cstText,[Text.UTF8Encoding]::new($false))
}
$project = @(
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<!DOCTYPE gowin-fpga-project>',
    '<Project><Template>FPGA</Template><Version>5</Version>',
    '<Device name="GW5AT-60B" pn="GW5AT-LV60PG484AC1/I0">gw5at60b-002</Device>',
    '<FileList>'
)
foreach ($file in $sources) {
    $escaped = [Security.SecurityElement]::Escape($file.Replace('\','/'))
    $project += ('<File path="{0}" type="file.verilog" enable="1"/>' -f $escaped)
}
foreach ($extension in @('cst','sdc')) {
    $file = if ($extension -eq 'cst') { $physicalConstraint } else {
        Join-Path $repoRoot 'code\constraints\visual_full_path_probe.sdc'
    }
    $escaped = [Security.SecurityElement]::Escape($file.Replace('\','/'))
    $project += ('<File path="{0}" type="file.{1}" enable="1"/>' -f $escaped,$extension)
}
$project += '</FileList></Project>'
$gprj = Join-Path $out 'visual_full_path_probe.gprj'
[IO.File]::WriteAllLines($gprj,$project,[Text.UTF8Encoding]::new($false))
$tcl = Join-Path $out 'run_build.tcl'
$cmds = @(
    ('open_project {'+$gprj.Replace('\','/')+'}'),
    'set_option -top_module visual_full_path_probe',
    'set_option -verilog_std sysv2017',
    'run all'
)
[IO.File]::WriteAllLines($tcl,$cmds,[Text.UTF8Encoding]::new($false))
$homeDir = $env:GOWIN_HOME
if (-not $homeDir) {
    $homeDir = 'D:\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64'
}
$gowin = Join-Path $homeDir 'IDE\bin\gw_sh.exe'
if (-not (Test-Path -LiteralPath $gowin -PathType Leaf)) { throw "Missing Gowin tool: $gowin" }
$previous = $ErrorActionPreference
try {
    $ErrorActionPreference = 'Continue'
    & $gowin $tcl 2>&1 | Tee-Object -FilePath (Join-Path $out 'build.log')
    $buildCode = $LASTEXITCODE
} finally { $ErrorActionPreference = $previous }
if ($buildCode -ne 0) { throw "Gowin build failed: $buildCode" }
$timing = Join-Path $out 'impl\pnr\visual_full_path_probe_tr_content.html'
$pins = Join-Path $out 'impl\pnr\visual_full_path_probe.rpt.txt'
if ($SerialResetPlacement -eq 'measured') {
    & python (Join-Path $PSScriptRoot 'check_visual_serial_reset_report.py') $timing --cst $physicalConstraint
    if ($LASTEXITCODE -ne 0) { throw 'Measured serial reset recovery failed. Never program.' }
}
& python (Join-Path $PSScriptRoot 'check_visual_full_path_report.py') $timing `
    --pin-report $pins
if ($LASTEXITCODE -ne 0) {
    throw "Visual renderer failed STA gate. Do not program: $out"
}
Write-Host "PASS independent visual probe STA. Still requires CDC and real-display verification: $out"
