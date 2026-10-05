# T016/T024: independent 1-copy vs 4-copy ADSR placement comparisons.
# This probes the current RTL cost; it does not estimate a complete voice.
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$out=Join-Path $root 'code\output\t016_adsr_scale'
$rom=Join-Path $root 'code\model\generated\wavetables\velocity_gain_rom.mem'
$rtl=Join-Path $root 'code\rtl\audio\adsr_piano_envelope.sv'
$wrapper=Join-Path $root 'code\rtl\board\adsr_scale_probe.sv'
$gw='D:\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64\IDE\bin\gw_sh.exe'
foreach($path in @($rom,$rtl,$wrapper,$gw)){
    if(-not(Test-Path -LiteralPath $path)){throw "Missing dependency: $path"}
}
$sourceHash=(Get-FileHash -LiteralPath $rtl -Algorithm SHA256).Hash
$wrapperHash=(Get-FileHash -LiteralPath $wrapper -Algorithm SHA256).Hash
New-Item -ItemType Directory -Path $out -Force | Out-Null
foreach($count in @(1,4)){
    $dir=Join-Path $out "voice_$count"
    $romDir=Join-Path $dir 'model\generated\wavetables'
    New-Item -ItemType Directory -Path $romDir -Force | Out-Null
    Copy-Item -LiteralPath $rom -Destination (Join-Path $romDir 'velocity_gain_rom.mem') -Force
    Copy-Item -LiteralPath $rtl -Destination (Join-Path $dir 'adsr_piano_envelope.sv') -Force
    Copy-Item -LiteralPath $wrapper -Destination (Join-Path $dir 'adsr_scale_probe.sv') -Force
    $top="adsr_probe_$count"
    $project=@('<?xml version="1.0" encoding="UTF-8"?>',
        '<!DOCTYPE gowin-fpga-project>',
        '<Project><Template>FPGA</Template><Version>5</Version>',
        '<Device name="GW5AT-60B" pn="GW5AT-LV60PG484AC1/I0">gw5at60b-002</Device>',
        '<FileList><File path="adsr_piano_envelope.sv" type="file.verilog" enable="1"/>',
        '<File path="adsr_scale_probe.sv" type="file.verilog" enable="1"/>',
        ('<File path="'+$top+'.sdc" type="file.sdc" enable="1"/>'),
        '</FileList></Project>')
    $gprj=Join-Path $dir ($top+'.gprj')
    [IO.File]::WriteAllLines($gprj,$project,[Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllLines((Join-Path $dir ($top+'.sdc')),
        @('create_clock -name sys_clk -period 20.000 [get_ports {sys_clk}]'),
        [Text.UTF8Encoding]::new($false))
    $fwd=$dir.Replace('\','/')
    $tcl=@(('cd {'+$fwd+'}'),('open_project {'+$gprj.Replace('\','/')+'}'),
        'set_option -verilog_std sysv2017',('set_option -top_module '+$top),'run all')
    $driver=Join-Path $dir 'run_all.tcl'
    [IO.File]::WriteAllLines($driver,$tcl,[Text.UTF8Encoding]::new($false))
    $prior=$ErrorActionPreference
    try {
        $ErrorActionPreference='Continue'
        & $gw $driver 2>&1 | Tee-Object -FilePath (Join-Path $dir 'gowin.log')
        $rc=$LASTEXITCODE
    } finally {$ErrorActionPreference=$prior}
    if($rc -ne 0){throw "Gowin $top failed exit=$rc"}
    foreach($p in @((Join-Path $dir ('impl\pnr\'+$top+'.rpt.txt')),
                     (Join-Path $dir ('impl\pnr\'+$top+'_tr_content.html')),
                     (Join-Path $dir ('impl\pnr\'+$top+'.fs')))){
        if(-not(Test-Path -LiteralPath $p)){throw "Missing $top report: $p"}
    }
    if((Get-FileHash -LiteralPath $rtl -Algorithm SHA256).Hash -ne $sourceHash -or
       (Get-FileHash -LiteralPath $wrapper -Algorithm SHA256).Hash -ne $wrapperHash){
        throw 'RTL modified during resource comparison'
    }
}
& python -X utf8 (Join-Path $PSScriptRoot 'check_t016_adsr_scale.py') $out
if($LASTEXITCODE -ne 0){throw 'Resource/timing comparison rejected'}
& python -X utf8 (Join-Path $PSScriptRoot 'snapshot_t016_adsr_scale.py')
if($LASTEXITCODE -ne 0){throw 'T016 evidence capture rejected'}
Write-Host 'PASS independent 1/4 ADSR PnR comparison. No actual 4-voice sound engine built.'
