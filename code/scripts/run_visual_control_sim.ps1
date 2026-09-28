# M2 score/mode CDC adapter module self-check; pure ASCII for PS5.1.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $PSScriptRoot 'enter_fpga_env.ps1') | Out-Null
$iv = 'D:\Gowin\oss-cad-suite\bin\iverilog.exe'
$vvp = 'D:\Gowin\oss-cad-suite\bin\vvp.exe'
$stage = Join-Path $env:TEMP ('visual_control_'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    $sources = @('code\rtl\common\reset_sync.sv',
        'code\rtl\common\visual_mailbox_cdc.sv',
        'code\rtl\common\visual_control_bridge.sv',
        'code\tb\common\tb_visual_control_bridge.sv')
    $args = @()
    for($i=0;$i -lt $sources.Count;$i++) {
        $dest = Join-Path $stage ('src_'+$i+'.sv')
        Copy-Item -LiteralPath (Join-Path $root $sources[$i]) -Destination $dest
        $args += $dest
    }
    foreach($half in @(7,17,41)) {
        $out = Join-Path $stage ('control_'+$half+'.vvp')
        $saved = $ErrorActionPreference
        try {
            $ErrorActionPreference='Continue'
            & $iv -g2012 -Wall -s tb_visual_control_bridge -P "tb_visual_control_bridge.VIDEO_HALF=$half" -o $out @args
            $rc=$LASTEXITCODE
        } finally { $ErrorActionPreference=$saved }
        if($rc -ne 0){throw "Compile failed: $rc"}
        & $vvp $out
        if($LASTEXITCODE -ne 0){throw "Control simulation failed at half=$half"}
    }
} finally {
    $full=[IO.Path]::GetFullPath($stage)
    $temp=[IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')+'\'
    if(-not $full.StartsWith($temp,[StringComparison]::OrdinalIgnoreCase)){throw 'Unsafe temp cleanup'}
    Remove-Item -LiteralPath $full -Recurse -Force -ErrorAction SilentlyContinue
}
Write-Host 'M2 independent score/mode CDC: ALL PASS (no board or physical timing claim)'
