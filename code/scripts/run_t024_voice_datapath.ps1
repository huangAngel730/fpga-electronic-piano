# M2 T024 independent DDS+ADSR+mixer one/four lane timing probe.
# This script never builds or programs the formal electronic_piano_top.
$ErrorActionPreference = 'Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$out=Join-Path $repo 'code\output\t024_voice_datapath'
$gwRoot=if($env:GOWIN_HOME){$env:GOWIN_HOME}else{'D:\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64'}
$gw=Join-Path $gwRoot 'IDE\bin\gw_sh.exe'
if(-not(Test-Path -LiteralPath $gw)){throw "Missing Gowin: $gw"}
$src=@('code\rtl\board\voice_datapath_probe.sv',
       'code\rtl\audio\dds_oscillator.sv',
       'code\rtl\audio\adsr_piano_envelope.sv',
       'code\rtl\mixer\pcm_mixer_4voice.sv')
$roms=@('code\model\generated\wavetables\sine_1024_32767.mem',
        'code\model\generated\wavetables\velocity_gain_rom.mem')
foreach($file in $src+$roms){if(-not(Test-Path -LiteralPath (Join-Path $repo $file))){throw "Missing $file"}}
New-Item -ItemType Directory -Path $out -Force | Out-Null
foreach($lanes in @(1,4)){
    $dir=Join-Path $out "lanes_$lanes"
    $romDir=Join-Path $dir 'model\generated\wavetables'
    New-Item -ItemType Directory -Path $romDir -Force | Out-Null
    foreach($rom in $roms){Copy-Item -LiteralPath (Join-Path $repo $rom) -Destination $romDir -Force}
    $sourcePaths=@()
    foreach($file in $src){
        $target=Join-Path $dir ([IO.Path]::GetFileName($file))
        Copy-Item -LiteralPath (Join-Path $repo $file) -Destination $target -Force
        $sourcePaths+=([IO.Path]::GetFileName($file))
    }
    $top="voice_datapath_probe_$lanes"
    $project=@('<?xml version="1.0" encoding="UTF-8"?>','<!DOCTYPE gowin-fpga-project>',
        '<Project><Template>FPGA</Template><Version>5</Version>',
        '<Device name="GW5AT-60B" pn="GW5AT-LV60PG484AC1/I0">gw5at60b-002</Device>',
        '<FileList>')
    foreach($name in $sourcePaths){$project+=('<File path="'+$name+'" type="file.verilog" enable="1"/>')}
    $project+=('<File path="'+$top+'.sdc" type="file.sdc" enable="1"/>')
    $project+='</FileList></Project>'
    $gprj=Join-Path $dir ($top+'.gprj')
    [IO.File]::WriteAllLines($gprj,$project,[Text.UTF8Encoding]::new($false))
    [IO.File]::WriteAllLines((Join-Path $dir ($top+'.sdc')),
        @('create_clock -name sys_clk -period 20.000 [get_ports {sys_clk}]'),
        [Text.UTF8Encoding]::new($false))
    $fwd=$dir.Replace('\','/')
    $tcl=Join-Path $dir 'run_all.tcl'
    [IO.File]::WriteAllLines($tcl,@(('cd {'+$fwd+'}'),
        ('open_project {'+$gprj.Replace('\','/')+'}'),
        'set_option -verilog_std sysv2017',
        ('set_option -top_module '+$top),'run all'),
        [Text.UTF8Encoding]::new($false))
    $prior=$ErrorActionPreference
    try {
        $ErrorActionPreference='Continue'
        & $gw $tcl 2>&1 | Tee-Object -FilePath (Join-Path $dir 'gowin.log')
        $rc=$LASTEXITCODE
    } finally {$ErrorActionPreference=$prior}
    if($rc -ne 0){throw "Gowin $top failed exit=$rc"}
}
& python -X utf8 (Join-Path $PSScriptRoot 'check_t024_voice_datapath.py') $out
if($LASTEXITCODE -ne 0){throw 'T024 resource/timing probe is NOT timing clean'}
& python -X utf8 (Join-Path $PSScriptRoot 'snapshot_t024_voice_datapath.py')
if($LASTEXITCODE -ne 0){throw 'T024 evidence capture failed'}
Write-Host 'PASS T024 standalone data-path probe. Not a complete voice or formal top.'
