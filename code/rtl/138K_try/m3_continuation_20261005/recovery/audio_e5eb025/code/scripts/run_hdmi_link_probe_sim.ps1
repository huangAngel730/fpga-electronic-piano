# M2 top wiring test with explicit behavioural vendor-IP placeholders.
$ErrorActionPreference='Stop'
$root=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $PSScriptRoot 'enter_fpga_env.ps1') | Out-Null
$iv='D:\Gowin\oss-cad-suite\bin\iverilog.exe'
$vvp='D:\Gowin\oss-cad-suite\bin\vvp.exe'
$stage=Join-Path $env:TEMP ('hdmi_wiring_'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    $src=@('code\rtl\common\reset_sync.sv','code\rtl\common\video_scan_timing.sv',
           'code\rtl\board\hdmi_link_probe.sv','code\tb\board\tb_hdmi_link_probe.sv')
    $args=@()
    foreach($p in $src){
        $dest=Join-Path $stage ([IO.Path]::GetFileName($p))
        Copy-Item -LiteralPath (Join-Path $root $p) -Destination $dest
        $args+=$dest
    }
    $out=Join-Path $stage 'probe.vvp'
    $saved=$ErrorActionPreference
    $ErrorActionPreference='Continue'
    & $iv -g2012 -Wall -s tb_hdmi_link_probe -o $out @args
    $rc=$LASTEXITCODE
    $ErrorActionPreference=$saved
    if($rc -ne 0){throw "Wiring test compile failed: $rc"}
    & $vvp $out
    if($LASTEXITCODE -ne 0){throw 'Wiring test simulation failed'}
} finally {
    $resolved=[IO.Path]::GetFullPath($stage)
    $tempRoot=[IO.Path]::GetFullPath($env:TEMP).TrimEnd('\')+'\'
    if(-not $resolved.StartsWith($tempRoot,[StringComparison]::OrdinalIgnoreCase)){
        throw "Unsafe cleanup target $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction SilentlyContinue
}
