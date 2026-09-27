# T025: registered PCM generation plus clipping flag and actual frame buffer.
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $PSScriptRoot 'enter_fpga_env.ps1') | Out-Null
$iverilog='D:\Gowin\oss-cad-suite\bin\iverilog.exe'
$vvp='D:\Gowin\oss-cad-suite\bin\vvp.exe'
foreach($tool in @($iverilog,$vvp)) {
    if(-not(Test-Path -LiteralPath $tool)){throw "Missing simulator: $tool"}
}
$stage=Join-Path $env:TEMP ('t025_result_'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    $sources=@(
        'code\rtl\audio_out\pcm_result_hold.sv',
        'code\rtl\audio_out\pcm_frame_buffer.sv',
        'code\rtl\common\pcm_clip_counter.sv',
        'code\rtl\mixer\pcm_mixer_4voice.sv',
        'code\tb\audio_out\tb_pcm_result_hold.sv'
    )
    $staged=@()
    for($i=0;$i -lt $sources.Count;$i++){
        $src=Join-Path $root $sources[$i]
        if(-not(Test-Path -LiteralPath $src)){throw "Missing source: $src"}
        $dst=Join-Path $stage ('src_'+$i+'.sv')
        Copy-Item -LiteralPath $src -Destination $dst
        $staged+=$dst
    }
    $vvpFile=Join-Path $stage 'result.vvp'
    $previous=$ErrorActionPreference
    try {
        $ErrorActionPreference='Continue'
        & $iverilog -g2012 -Wall -s tb_pcm_result_hold -o $vvpFile @staged
        if($LASTEXITCODE -ne 0){throw 'T025 result hold compile failed'}
        & $vvp $vvpFile
        if($LASTEXITCODE -ne 0){throw 'T025 result hold simulation failed'}
    } finally {$ErrorActionPreference=$previous}
    Write-Host 'T025 result ID/PCM/clip handoff: ALL PASS'
} finally {
    $resolved=[IO.Path]::GetFullPath($stage)
    $tempRoot=[IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')+'\'
    if(-not $resolved.StartsWith($tempRoot,[StringComparison]::OrdinalIgnoreCase)){
        throw "Unsafe cleanup target: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction SilentlyContinue
}
