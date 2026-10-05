# Independent M2 HDMI transport build. Never downloads or touches main build.
param(
    [Parameter(Mandatory=$true)][string]$ReferenceRoot,
    [string]$GeneratedDviIpDir,
    [ValidateSet('synth','all')][string]$Flow = 'all'
)
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$ref = (Resolve-Path -LiteralPath $ReferenceRoot).Path
# The GUI-generated Gowin 3.0 IP has no pixel-frequency setting: 25/125 MHz
# come from the external PLL. Pin its actual outputs, not a hand-edited IPC.
$generatedDir = $null
if($GeneratedDviIpDir) {
    $generatedDir = (Resolve-Path -LiteralPath $GeneratedDviIpDir).Path
    $generatedFiles = @(
        @('DVI_TX_Top.ipc','1A1745E4785009D9BCB9815EBAD19E0B13F51834D7BC68ED90EA5FD662278656'),
        @('DVI_TX_Top.v','B378C6A41D06A14215DC9EC54ED20BFC91309A0BB1543C589246717DA3AEE2AB'),
        @('DVI_TX_Top.vo','E5045DD28131089B999FE75BB27E8EE82E33AB3FCDB39B7C8BC9A1570309FFE1'),
        @('temp\DviTx\DVI_TX_Top.log','ABC8D41BECE79A743B9932D725AD2C75E7611A1FB058A663EB0465046BBAF80E'),
        @('temp\DviTx\dvi_tx_defines.v','4798A2F97B8A42AE560D68D7BA30A7095F0621A6D357A45156C3D713ACFDD0B4')
    )
    foreach($file in $generatedFiles) {
        $p = Join-Path $generatedDir $file[0]
        if(-not (Test-Path -LiteralPath $p -PathType Leaf) -or
           (Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash -ne $file[1]) {
            throw "GUI DVI IP missing or unreviewed: $p"
        }
    }
    $ipc = [IO.File]::ReadAllText((Join-Path $generatedDir 'DVI_TX_Top.ipc'))
    if(-not $ipc.Contains('target_device=gw5at60b-002') -or
       -not $ipc.Contains('type=dvi_tx') -or
       -not $ipc.Contains('TLVDS=true') -or
       $ipc.Contains('RX_CLOCK_IN_FREQUENCY=')) {
        throw 'Unexpected DVI TX 3.0 IP options; inspect generated IPC'
    }
}
$out = Join-Path $repoRoot 'code\output\hdmi_link_probe'
New-Item -ItemType Directory -Force -Path $out | Out-Null
$vendor = Join-Path $out 'vendor'
New-Item -ItemType Directory -Force -Path $vendor | Out-Null
$inputs = @(
    @('cam_dvi\src\gowin_pll\TMDS_PLL_800_600_60.v','E43E57D7301929DCDECEABF5274FAB46080697F82E3FA2D30479D69E87C0801A'),
    @('cam_dvi\src\dvi_tx\DVI_TX_Top.v','A2DC2F338438864307DC8DA6C8F50B582D412EEB5EA899AF9F047A8D6B46815F')
)
if($generatedDir) {
    $inputs[1] = @('DVI_TX_Top.v','B378C6A41D06A14215DC9EC54ED20BFC91309A0BB1543C589246717DA3AEE2AB')
}
$sourcePaths = @()
foreach($entry in $inputs) {
    $p = if($generatedDir -and $entry[0] -eq 'DVI_TX_Top.v') {
        Join-Path $generatedDir $entry[0]
    } else { Join-Path $ref $entry[0] }
    if((Get-FileHash -LiteralPath $p -Algorithm SHA256).Hash -ne $entry[1]) {
        throw "Unreviewed reference source: $p"
    }
    $dest = Join-Path $vendor ([IO.Path]::GetFileName($p))
    if($entry[0] -like '*TMDS_PLL*') {
        # Derived PLLA parameters: 50/1*20 = 1000 MHz VCO;
        # CLKOUT0 /8 = 125 MHz, CLKOUT1 /40 = 25 MHz.
        $pll = [IO.File]::ReadAllText($p)
        $edits = @(@('IDIV_SEL = 1;','IDIV_SEL = 1;'),
                   @('MDIV_SEL = 16;','MDIV_SEL = 20;'),
                   @('ODIV0_SEL = 4;','ODIV0_SEL = 8;'),
                   @('ODIV1_SEL = 20;','ODIV1_SEL = 40;'))
        foreach($edit in $edits) {
            if(-not $pll.Contains('PLLA_inst.'+$edit[0])){throw 'PLL template drift'}
            $pll=$pll.Replace('PLLA_inst.'+$edit[0],'PLLA_inst.'+$edit[1])
        }
        $pll = "// M2 derived 125/25 MHz configuration; original copyright below.`n" + $pll
        [IO.File]::WriteAllText($dest,$pll,[Text.UTF8Encoding]::new($false))
    } else { Copy-Item -LiteralPath $p -Destination $dest -Force }
    $sourcePaths += $dest
}
Copy-Item -LiteralPath (Join-Path $ref 'LICENSE') -Destination $vendor -Force
$sourcePaths += @(
    (Join-Path $repoRoot 'code\rtl\common\reset_sync.sv'),
    (Join-Path $repoRoot 'code\rtl\common\video_scan_timing.sv'),
    (Join-Path $repoRoot 'code\rtl\board\hdmi_link_probe.sv')
)
$project = @(
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<!DOCTYPE gowin-fpga-project>',
    '<Project><Template>FPGA</Template><Version>5</Version>',
    '<Device name="GW5AT-60B" pn="GW5AT-LV60PG484AC1/I0">gw5at60b-002</Device>',
    '<FileList>'
)
foreach($source in $sourcePaths) {
    $escaped = [Security.SecurityElement]::Escape($source.Replace('\','/'))
    $project += ('<File path="{0}" type="file.verilog" enable="1"/>' -f $escaped)
}
foreach($ext in @('cst','sdc')) {
    $p = (Join-Path $repoRoot ('code\constraints\hdmi_link_probe.'+$ext)).Replace('\','/')
    $project += ('<File path="{0}" type="file.{1}" enable="1"/>' -f [Security.SecurityElement]::Escape($p),$ext)
}
$project += '</FileList></Project>'
$gprj = Join-Path $out 'hdmi_link_probe.gprj'
[IO.File]::WriteAllLines($gprj,$project,[Text.UTF8Encoding]::new($false))
$gowinHome = $env:GOWIN_HOME
if(-not $gowinHome){$gowinHome='D:\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64'}
$gw = Join-Path $gowinHome 'IDE\bin\gw_sh.exe'
if(-not (Test-Path -LiteralPath $gw)){throw "Missing tool: $gw"}
$tcl = Join-Path $out 'run_build.tcl'
$run = if($Flow -eq 'synth'){'syn'}else{'all'}
$cmds = @(
    ('open_project {'+$gprj.Replace('\','/')+'}'),
    'set_option -top_module hdmi_link_probe',
    'set_option -verilog_std sysv2017',
    ('run '+$run)
)
[IO.File]::WriteAllLines($tcl,$cmds,[Text.UTF8Encoding]::new($false))
$previous = $ErrorActionPreference
try {
    $ErrorActionPreference='Continue'
    & $gw $tcl 2>&1 | Tee-Object -FilePath (Join-Path $out 'build.log')
    $rc=$LASTEXITCODE
} finally { $ErrorActionPreference=$previous }
if($rc -ne 0){throw "Gowin build failed ($rc): $out"}
if($Flow -eq 'all') {
    $fs = Join-Path $out 'impl\pnr\hdmi_link_probe.fs'
    if(-not (Test-Path -LiteralPath $fs)){throw 'No bitstream generated'}
    $report = Join-Path $out 'impl\pnr\hdmi_link_probe_tr_content.html'
    $pinReport = Join-Path $out 'impl\pnr\hdmi_link_probe.rpt.txt'
    & python (Join-Path $PSScriptRoot 'check_hdmi_link_report.py') $report --pin-report $pinReport --json (Join-Path $out 'timing_summary.json')
    if($LASTEXITCODE -ne 0){throw 'HDMI timing gate failed. Do not program the generated bitstream.'}
    if($generatedDir) {
        & python (Join-Path $PSScriptRoot 'snapshot_hdmi_link_evidence.py') $repoRoot (Join-Path $out 'gui_ip_evidence.json') $generatedDir
    } else {
        & python (Join-Path $PSScriptRoot 'snapshot_hdmi_link_evidence.py') $repoRoot
    }
    if($LASTEXITCODE -ne 0){throw 'HDMI evidence snapshot failed.'}
}
Write-Host "PASS build only. Reports in $out. Not programmed; inspect timing before hardware use."
