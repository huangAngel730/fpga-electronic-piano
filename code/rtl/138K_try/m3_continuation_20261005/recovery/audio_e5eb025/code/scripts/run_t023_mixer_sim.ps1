# T023 partial handoff: four-voice mixer compared against M1 Python model.
# Pure ASCII for Windows PowerShell 5.1.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $PSScriptRoot 'enter_fpga_env.ps1') | Out-Null
$iverilog = 'D:\Gowin\oss-cad-suite\bin\iverilog.exe'
$vvp = 'D:\Gowin\oss-cad-suite\bin\vvp.exe'
foreach ($tool in @($iverilog, $vvp)) {
    if (-not (Test-Path -LiteralPath $tool)) { throw "Missing simulator: $tool" }
}
$stage = Join-Path $env:TEMP ('t023_m2_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    $reference = Join-Path $stage 'mixer_ref.txt'
    & python -X utf8 (Join-Path $repoRoot 'code\tb\mixer\generate_pcm_mixer_vectors.py') $reference
    if ($LASTEXITCODE -ne 0) { throw 'T023 Python reference generation failed' }
    $rtl = Join-Path $stage 'pcm_mixer_4voice.sv'
    $tb = Join-Path $stage 'tb_pcm_mixer_4voice.sv'
    Copy-Item -LiteralPath (Join-Path $repoRoot 'code\rtl\mixer\pcm_mixer_4voice.sv') -Destination $rtl
    Copy-Item -LiteralPath (Join-Path $repoRoot 'code\tb\mixer\tb_pcm_mixer_4voice.sv') -Destination $tb
    $output = Join-Path $stage 'mixer.vvp'
    & $iverilog -g2012 -Wall -s tb_pcm_mixer_4voice -o $output $rtl $tb
    if ($LASTEXITCODE -ne 0) { throw 'T023 RTL compile failed' }
    & $vvp $output "+vectors=$reference"
    if ($LASTEXITCODE -ne 0) { throw 'T023 RTL versus Python mismatch' }
    Write-Host 'T023 M2 mixer partial handoff: ALL PASS'
} finally {
    $resolved = [IO.Path]::GetFullPath($stage)
    $tempRoot = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith($tempRoot,[StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe cleanup target: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction SilentlyContinue
}
