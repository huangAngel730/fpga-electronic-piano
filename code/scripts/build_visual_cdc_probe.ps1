# M2 independent 64-bit mailbox CDC proof. Neither mode is a board image.
# Sentinel intentionally fails 64 payload endpoints; bounded must pass.
param(
    [Parameter(Mandatory=$true)][string]$ReferenceRoot,
    [ValidateSet('sentinel','bounded')][string]$Mode = 'bounded'
)
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$ref = (Resolve-Path -LiteralPath $ReferenceRoot).Path
$sourcePll = Join-Path $ref 'cam_dvi\src\gowin_pll\TMDS_PLL_800_600_60.v'
$expectedSource = 'E43E57D7301929DCDECEABF5274FAB46080697F82E3FA2D30479D69E87C0801A'
$expectedDerived = 'EDEDFD3E361C7E9B4523DE6B3B50E00C98BAED5B9900A361C606AB574376F9BA'
if (-not (Test-Path -LiteralPath $sourcePll -PathType Leaf) -or
    (Get-FileHash -LiteralPath $sourcePll -Algorithm SHA256).Hash -ne $expectedSource) {
    throw 'Missing or unreviewed Sipeed 60K PLL source'
}
$out = Join-Path $repo ('code\output\visual_cdc_probe\'+$Mode)
New-Item -ItemType Directory -Path $out -Force | Out-Null
$vendorDir = Join-Path $out 'vendor'
New-Item -ItemType Directory -Path $vendorDir -Force | Out-Null
$pllPath = Join-Path $vendorDir 'TMDS_PLL_800_600_60.v'
$pll = [IO.File]::ReadAllText($sourcePll)
$edits = @(
    @('IDIV_SEL = 1;','IDIV_SEL = 1;'),
    @('MDIV_SEL = 16;','MDIV_SEL = 20;'),
    @('ODIV0_SEL = 4;','ODIV0_SEL = 8;'),
    @('ODIV1_SEL = 20;','ODIV1_SEL = 40;')
)
foreach($edit in $edits) {
    $old = 'PLLA_inst.'+$edit[0]
    if (-not $pll.Contains($old)) { throw 'PLL source parameter drift' }
    $pll = $pll.Replace($old,'PLLA_inst.'+$edit[1])
}
$pll = "// M2 derived 125/25 MHz configuration; original copyright below.`n"+$pll
[IO.File]::WriteAllText($pllPath,$pll,[Text.UTF8Encoding]::new($false))
if ((Get-FileHash -LiteralPath $pllPath -Algorithm SHA256).Hash -ne $expectedDerived) {
    throw 'Derived PLL differs from reviewed HDMI PLL'
}
Copy-Item -LiteralPath (Join-Path $ref 'LICENSE') -Destination $vendorDir -Force
$sdctext = [IO.File]::ReadAllText((Join-Path $repo 'code\constraints\visual_cdc_probe.sdc'))
$bus = 'set_max_delay -from [get_regs {u_bridge/payload_hold*}] -to [get_regs {u_bridge/video_data*}] 10.000'
if ($sdctext.Split(@($bus),[StringSplitOptions]::None).Length -ne 2) {
    throw 'Expected exactly one reviewed 10 ns mailbox bound'
}
if ($Mode -eq 'sentinel') {
    $sdctext = $sdctext.Replace($bus,$bus.Replace('10.000','0.001'))
}
$sdcPath = Join-Path $out 'visual_cdc_probe.sdc'
[IO.File]::WriteAllText($sdcPath,$sdctext,[Text.UTF8Encoding]::new($false))
$sources = @(
    (Join-Path $repo 'code\rtl\common\audio_defs_pkg.sv'),
    $pllPath,
    (Join-Path $repo 'code\rtl\common\reset_sync.sv'),
    (Join-Path $repo 'code\rtl\common\visual_event_bridge.sv'),
    (Join-Path $repo 'code\rtl\board\visual_cdc_probe.sv')
)
$project = @('<?xml version="1.0" encoding="UTF-8"?>',
    '<!DOCTYPE gowin-fpga-project>',
    '<Project><Template>FPGA</Template><Version>5</Version>',
    '<Device name="GW5AT-60B" pn="GW5AT-LV60PG484AC1/I0">gw5at60b-002</Device>',
    '<FileList>')
foreach($file in $sources) {
    $escaped = [Security.SecurityElement]::Escape($file.Replace('\','/'))
    $project += ('<File path="{0}" type="file.verilog" enable="1"/>' -f $escaped)
}
$cst = (Join-Path $repo 'code\constraints\visual_cdc_probe.cst').Replace('\','/')
$project += ('<File path="{0}" type="file.cst" enable="1"/>' -f [Security.SecurityElement]::Escape($cst))
$project += ('<File path="{0}" type="file.sdc" enable="1"/>' -f [Security.SecurityElement]::Escape($sdcPath.Replace('\','/')))
$project += '</FileList></Project>'
$gprj = Join-Path $out 'visual_cdc_probe.gprj'
[IO.File]::WriteAllLines($gprj,$project,[Text.UTF8Encoding]::new($false))
$gowinHome = $env:GOWIN_HOME
if (-not $gowinHome) { $gowinHome = 'D:\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64' }
$gw = Join-Path $gowinHome 'IDE\bin\gw_sh.exe'
if (-not (Test-Path -LiteralPath $gw -PathType Leaf)) { throw "Missing Gowin tool: $gw" }
$tcl = Join-Path $out 'run_build.tcl'
$commands = @(
    ('open_project {'+$gprj.Replace('\','/')+'}'),
    'set_option -top_module visual_cdc_probe',
    'set_option -verilog_std sysv2017',
    'run syn',
    'run pnr'
)
[IO.File]::WriteAllLines($tcl,$commands,[Text.UTF8Encoding]::new($false))
$previous = $ErrorActionPreference
try {
    $ErrorActionPreference = 'Continue'
    & $gw $tcl 2>&1 | Tee-Object -FilePath (Join-Path $out 'build.log')
    $rc = $LASTEXITCODE
} finally { $ErrorActionPreference = $previous }
if ($rc -ne 0) { throw "Gowin CDC probe failed: $rc" }
$report = Join-Path $out 'impl\pnr\visual_cdc_probe_tr_content.html'
if (-not (Test-Path -LiteralPath $report -PathType Leaf)) {
    throw "Missing STA report: $report"
}
& python (Join-Path $PSScriptRoot 'check_visual_cdc_report.py') $report --mode $Mode
if ($LASTEXITCODE -ne 0) { throw "CDC $Mode report gate failed; never program probe" }
Write-Host "PASS $Mode proof in $out; synthetic inputs, no physical CDC or full video claim"
