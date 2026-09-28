# Independent PT8211 WS polarity diagnostic; nonzero means review failure.
$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $PSScriptRoot 'enter_fpga_env.ps1') | Out-Null
$cad = $env:YOSYSHQ_ROOT
if (-not $cad) { throw 'YOSYSHQ_ROOT is missing' }
$iv = Join-Path $cad 'bin\iverilog.exe'
$vp = Join-Path $cad 'bin\vvp.exe'
foreach ($tool in @($iv, $vp)) {
    if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) { throw "Missing: $tool" }
}
$stage = Join-Path $env:TEMP ('t005_pt8211_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage -ErrorAction Stop | Out-Null
try {
    $rtl = Join-Path $stage 'i2s_tx.sv'
    $tb = Join-Path $stage 'tb_pt8211_ws_polarity.sv'
    $out = Join-Path $stage 'review.vvp'
    Copy-Item -LiteralPath (Join-Path $root 'code\rtl\audio_out\i2s_tx.sv') -Destination $rtl
    Copy-Item -LiteralPath (Join-Path $root 'code\tb\audio_out\tb_pt8211_ws_polarity.sv') -Destination $tb
    Write-Host "Source SHA256: $((Get-FileHash -LiteralPath $rtl -Algorithm SHA256).Hash)"
    $ErrorActionPreference = 'Continue'
    & $iv -g2012 -Wall -s tb_pt8211_ws_polarity -o $out $rtl $tb 2>&1 | ForEach-Object { "  $_" }
    $compileRc = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($compileRc -ne 0 -or -not (Test-Path -LiteralPath $out)) { throw "Compile failed: $compileRc" }
    $ErrorActionPreference = 'Continue'
    & $vp $out 2>&1 | ForEach-Object { "  $_" }
    $simRc = $LASTEXITCODE
    $ErrorActionPreference = 'Stop'
    if ($simRc -ne 0) { Write-Host "PT8211 review FAIL: $simRc"; exit $simRc }
    Write-Host 'PT8211 review PASS'
    exit 0
} finally {
    $resolved = [IO.Path]::GetFullPath($stage)
    $temp = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith($temp, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe cleanup target: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction SilentlyContinue
}
