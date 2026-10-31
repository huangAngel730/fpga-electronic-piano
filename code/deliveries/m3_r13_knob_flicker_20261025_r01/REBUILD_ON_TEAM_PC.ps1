param([Parameter(Mandatory=$true)][string]$GowinExe)
$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $GowinExe -PathType Leaf)) { throw '指定的 gw_sh.exe 不存在' }
if ([IO.Path]::GetFileName($GowinExe) -ne 'gw_sh.exe') { throw '请指定商业版 V1.9.12.04 的 gw_sh.exe' }
& $GowinExe (Join-Path $PSScriptRoot 'source/rebuild.tcl')
if ($LASTEXITCODE -ne 0) { throw "Gowin 重建失败，退出码 $LASTEXITCODE；请保留输出" }
