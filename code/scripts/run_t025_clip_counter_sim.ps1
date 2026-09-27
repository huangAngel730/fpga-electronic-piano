# T025 independent clip counter with real frame-buffer handshake and mixer.
# Pure ASCII for Windows PowerShell 5.1.
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $PSScriptRoot 'enter_fpga_env.ps1') | Out-Null
$iv='D:\Gowin\oss-cad-suite\bin\iverilog.exe'
$vvp='D:\Gowin\oss-cad-suite\bin\vvp.exe'
foreach($tool in @($iv,$vvp)) { if(-not(Test-Path -LiteralPath $tool)){throw "Missing simulator: $tool"} }
$stage=Join-Path $env:TEMP ('t025_clip_'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    $sources=@(
        'code\rtl\common\pcm_clip_counter.sv',
        'code\rtl\audio_out\pcm_frame_buffer.sv',
        'code\rtl\mixer\pcm_mixer_4voice.sv',
        'code\tb\common\tb_pcm_clip_counter.sv'
    )
    $staged=@()
    for($i=0;$i -lt $sources.Count;$i++) {
        $source=Join-Path $root $sources[$i]
        if(-not(Test-Path -LiteralPath $source)){throw "Missing source: $source"}
        $target=Join-Path $stage ('source_'+$i+'.sv')
        Copy-Item -LiteralPath $source -Destination $target
        $staged += $target
    }
    $output=Join-Path $stage 'clip.vvp'
    $prior=$ErrorActionPreference
    try {
        $ErrorActionPreference='Continue'
        & $iv -g2012 -Wall -s tb_pcm_clip_counter -o $output @staged
        $compileExit=$LASTEXITCODE
        if($compileExit -ne 0){throw "T025 clip compile failed: $compileExit"}
        & $vvp $output
        $runExit=$LASTEXITCODE
        if($runExit -ne 0){throw "T025 clip simulation failed: $runExit"}
    } finally { $ErrorActionPreference=$prior }
    Write-Host 'T025 clip counter and PCM buffer handshake: ALL PASS'
} finally {
    $resolved=[IO.Path]::GetFullPath($stage)
    $tempRoot=[IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')+'\'
    if(-not $resolved.StartsWith($tempRoot,[StringComparison]::OrdinalIgnoreCase)){
        throw "Unsafe cleanup target $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction SilentlyContinue
}
