# T025 read-only synthetic PCM-to-STAT integration test (NOT the piano top).
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $PSScriptRoot 'enter_fpga_env.ps1') | Out-Null
$iv='D:\Gowin\oss-cad-suite\bin\iverilog.exe'
$vvp='D:\Gowin\oss-cad-suite\bin\vvp.exe'
$stage=Join-Path $env:TEMP ('t025_stat_chain_'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    $sources=@('code\rtl\mixer\pcm_mixer_4voice.sv',
               'code\rtl\audio_out\pcm_result_hold.sv',
               'code\rtl\audio_out\pcm_frame_buffer.sv',
               'code\rtl\common\pcm_clip_counter.sv',
               'code\rtl\common\uart_tx.sv',
               'code\rtl\common\uart_rx.sv',
               'code\rtl\board\uart_status_reporter.sv',
               'code\tb\board\tb_t025_stat_chain.sv')
    $staged=@()
    for($i=0;$i -lt $sources.Count;$i++){
        $source=Join-Path $root $sources[$i]
        if(-not(Test-Path -LiteralPath $source)){throw "Missing source $source"}
        $target=Join-Path $stage ('source_'+$i+'.sv')
        Copy-Item -LiteralPath $source -Destination $target
        $staged+=$target
    }
    $exe=Join-Path $stage 'stat.vvp'
    $prior=$ErrorActionPreference
    try {
        $ErrorActionPreference='Continue'
        & $iv -g2012 -Wall -s tb_t025_stat_chain -o $exe @staged
        if($LASTEXITCODE -ne 0){throw 'T025 synthetic STAT compile failed'}
        & $vvp $exe
        if($LASTEXITCODE -ne 0){throw 'T025 synthetic STAT simulation failed'}
    } finally {$ErrorActionPreference=$prior}
    Write-Host 'T025 synthetic four-input PCM to seven-field STAT: PASS'
} finally {
    $resolved=[IO.Path]::GetFullPath($stage)
    $tempRoot=[IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')+'\'
    if(-not $resolved.StartsWith($tempRoot,[StringComparison]::OrdinalIgnoreCase)){
        throw "Unsafe cleanup target: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction SilentlyContinue
}
