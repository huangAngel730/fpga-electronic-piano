# Independent T024 DDS/ADSR scheduler probe. No formal top/CST change or download.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$out = Join-Path $root 'code\output\t024_envelope_bank_build'
New-Item -ItemType Directory -Force -Path $out | Out-Null
$romDir = Join-Path $out 'model\generated\wavetables'
New-Item -ItemType Directory -Force -Path $romDir | Out-Null
foreach($name in @('sine_1024_32767.mem','velocity_gain_rom.mem')) {
    Copy-Item -LiteralPath (Join-Path $root ('code\model\generated\wavetables\'+$name)) -Destination (Join-Path $romDir $name) -Force
}
$inputs = @('code/rtl/common/audio_defs_pkg.sv','code/rtl/common/note_pitch.sv',
            'code/rtl/audio/voice_allocator_4.sv','code/rtl/audio/dds_oscillator.sv',
            'code/rtl/audio/adsr_piano_envelope.sv','code/rtl/board/polyphonic_event_router.sv',
            'code/rtl/board/polyphonic_envelope_bank.sv','code/rtl/board/polyphonic_envelope_bank_probe.sv')
$files = @()
foreach($rel in $inputs) {
    $src=Join-Path $root $rel
    $dest=Join-Path $out ([IO.Path]::GetFileName($src))
    Copy-Item -LiteralPath $src -Destination $dest -Force
    $files += '<File path="'+[IO.Path]::GetFileName($dest)+'" type="file.verilog" enable="1"/>'
}
$sdc=Join-Path $out 'bank_probe.sdc'
[IO.File]::WriteAllText($sdc,'create_clock -name sys_clk -period 20.000 [get_ports {clk}]'+"`n",[Text.UTF8Encoding]::new($false))
$files += '<File path="bank_probe.sdc" type="file.sdc" enable="1"/>'
$gprj=Join-Path $out 'bank_probe.gprj'
$xml = '<?xml version="1.0" encoding="UTF-8"?><!DOCTYPE gowin-fpga-project><Project><Template>FPGA</Template><Version>5</Version><Device name="GW5AT-60B" pn="GW5AT-LV60PG484AC1/I0">gw5at60b-002</Device><FileList>'+($files -join '')+'</FileList></Project>'
[IO.File]::WriteAllText($gprj,$xml,[Text.UTF8Encoding]::new($false))
$toolRoot=$env:GOWIN_HOME
if(-not $toolRoot){$toolRoot='D:\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64'}
$gw=Join-Path $toolRoot 'IDE\bin\gw_sh.exe'
$tcl=Join-Path $out 'run_all.tcl'
[IO.File]::WriteAllLines($tcl,@(('cd {'+$out.Replace('\','/')+'}'),('open_project {'+$gprj.Replace('\','/')+'}'),'set_option -verilog_std sysv2017','set_option -top_module polyphonic_envelope_bank_probe','run all'),[Text.Encoding]::ASCII)
& $gw $tcl 2>&1 | Tee-Object -FilePath (Join-Path $out 'build.log')
if($LASTEXITCODE -ne 0){throw 'T024 independent bank build failed'}
& python (Join-Path $PSScriptRoot 'check_t009_fusion_report.py') (Join-Path $out 'impl\pnr\bank_probe_tr_content.html') (Join-Path $out 'impl\pnr\bank_probe.rpt.txt')
if($LASTEXITCODE -ne 0){throw 'T024 bank internal clock/resource/STA gate failed'}
Write-Host 'PASS independent T024 bank internal STA; no external IO timing, PCM arithmetic or board validation.'