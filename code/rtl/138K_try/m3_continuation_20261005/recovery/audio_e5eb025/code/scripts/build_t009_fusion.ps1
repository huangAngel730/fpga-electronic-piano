# Reproducible standalone T009 Gowin build. No changes to the piano top.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$out = Join-Path $root 'code\output\t009_fusion'
New-Item -ItemType Directory -Path $out -Force | Out-Null
$rtl = Join-Path $root 'code\rtl\audio\adsr_piano_envelope.sv'
$sourceRom = Join-Path $root 'code\model\generated\wavetables\velocity_gain_rom.mem'
$rom = Join-Path $out 'model\generated\wavetables\velocity_gain_rom.mem'
New-Item -ItemType Directory -Path ([IO.Path]::GetDirectoryName($rom)) -Force | Out-Null
foreach ($p in @($rtl, $sourceRom)) {
    if (-not (Test-Path -LiteralPath $p)) { throw "Missing input: $p" }
}
Copy-Item -LiteralPath $rtl -Destination (Join-Path $out 'adsr_piano_envelope.sv') -Force
Copy-Item -LiteralPath $sourceRom -Destination $rom -Force
$gprj = Join-Path $out 'adsr_probe.gprj'
$sdc = Join-Path $out 'adsr_probe.sdc'
[IO.File]::WriteAllLines($sdc, @('create_clock -name sys_clk -period 20.000 [get_ports {sys_clk}]'),
                         [Text.UTF8Encoding]::new($false))
$project = @(
    '<?xml version="1.0" encoding="UTF-8"?>',
    '<!DOCTYPE gowin-fpga-project>',
    '<Project><Template>FPGA</Template><Version>5</Version>',
    '<Device name="GW5AT-60B" pn="GW5AT-LV60PG484AC1/I0">gw5at60b-002</Device>',
    '<FileList><File path="adsr_piano_envelope.sv" type="file.verilog" enable="1"/>',
    '<File path="adsr_probe.sdc" type="file.sdc" enable="1"/></FileList></Project>'
)
[IO.File]::WriteAllLines($gprj, $project, [Text.UTF8Encoding]::new($false))
$gowinHome = $env:GOWIN_HOME
if (-not $gowinHome) { $gowinHome = 'D:\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64' }
$gw = Join-Path $gowinHome 'IDE\bin\gw_sh.exe'
if (-not (Test-Path -LiteralPath $gw)) { throw "Missing Gowin: $gw" }
$tcl = Join-Path $out 'run_all.tcl'
[IO.File]::WriteAllLines($tcl, @(
    ('cd {' + $out.Replace('\','/') + '}'),
    ('open_project {' + $gprj.Replace('\','/') + '}'),
    'set_option -verilog_std sysv2017',
    'set_option -top_module adsr_piano_envelope',
    'run all'
), [Text.UTF8Encoding]::new($false))
$previous = $ErrorActionPreference
try {
    $ErrorActionPreference = 'Continue'
    & $gw $tcl 2>&1 | Tee-Object -FilePath (Join-Path $out 'build.log')
    $rc = $LASTEXITCODE
} finally { $ErrorActionPreference = $previous }
if ($rc -ne 0) { throw "T009 Gowin build failed ($rc)" }
$report = Join-Path $out 'impl\pnr\adsr_probe_tr_content.html'
$usage = Join-Path $out 'impl\pnr\adsr_probe.rpt.txt'
$fs = Join-Path $out 'impl\pnr\adsr_probe.fs'
foreach ($p in @($report, $usage, $fs)) {
    if (-not (Test-Path -LiteralPath $p)) { throw "T009 missing build result: $p" }
}
& python (Join-Path $PSScriptRoot 'check_t009_fusion_report.py') $report $usage
if ($LASTEXITCODE -ne 0) { throw 'T009 PnR or timing gate failed' }
Write-Host 'PASS T009 standalone Gowin flow; not a top-level or board result.'
