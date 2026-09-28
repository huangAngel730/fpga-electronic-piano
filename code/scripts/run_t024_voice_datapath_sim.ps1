# M2 T024 diagnostic probe sanity; no M1 RTL changes.
$ErrorActionPreference='Stop'
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $PSScriptRoot 'enter_fpga_env.ps1') | Out-Null
$iv='D:\Gowin\oss-cad-suite\bin\iverilog.exe'
$vvp='D:\Gowin\oss-cad-suite\bin\vvp.exe'
$stage=Join-Path $env:TEMP ('t024_probe_'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    $romDir=Join-Path $stage 'model\generated\wavetables'
    New-Item -ItemType Directory -Path $romDir -Force | Out-Null
    foreach($name in @('sine_1024_32767.mem','velocity_gain_rom.mem')){
        Copy-Item -LiteralPath (Join-Path $repo ('code\model\generated\wavetables\'+$name)) -Destination $romDir
    }
    $inputs=@('code\rtl\board\voice_datapath_probe.sv',
              'code\rtl\audio\dds_oscillator.sv',
              'code\rtl\audio\adsr_piano_envelope.sv',
              'code\rtl\mixer\pcm_mixer_4voice.sv',
              'code\tb\board\tb_voice_datapath_probe.sv')
    $staged=@()
    foreach($rel in $inputs){
        $dst=Join-Path $stage ([IO.Path]::GetFileName($rel))
        Copy-Item -LiteralPath (Join-Path $repo $rel) -Destination $dst
        $staged+=$dst
    }
    $out=Join-Path $stage 'probe.vvp'
    $prior=$ErrorActionPreference
    Push-Location -LiteralPath $stage
    try {
        $ErrorActionPreference='Continue'
        & $iv -g2012 -Wall -s tb_voice_datapath_probe -o $out @staged
        $compile=$LASTEXITCODE
        if($compile -ne 0){throw "Probe compile failed: $compile"}
        & $vvp $out
        $run=$LASTEXITCODE
        if($run -ne 0){throw "Probe self-check failed: $run"}
    } finally {Pop-Location;$ErrorActionPreference=$prior}
    Write-Host 'PASS T024 1/4-lane observable activity and reset.'
} finally {
    $absolute=[IO.Path]::GetFullPath($stage)
    $parent=[IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')+'\'
    if(-not $absolute.StartsWith($parent,[StringComparison]::OrdinalIgnoreCase)){
        throw "Unsafe temp cleanup target: $absolute"
    }
    Remove-Item -LiteralPath $absolute -Recurse -Force -ErrorAction SilentlyContinue
}
