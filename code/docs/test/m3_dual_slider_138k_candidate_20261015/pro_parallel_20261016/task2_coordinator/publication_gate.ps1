# Publication gate only; no FPGA build, programming or device operation.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '../../../../../../')).Path
$env:GOWIN_HOME = 'E:\FPGA\GAOYUNFPGA\138K\tools\gowin_1_9_11_03'
$env:GOWIN_PROGRAMMER_HOME = 'D:\program\gaoyunFPGA\Gowin\Gowin_V1.9.11.03_Education_x64\Programmer'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PATH = 'C:\Users\songdongkuan\miniconda3;' + $env:PATH
Set-Location -LiteralPath $repoRoot
& (Join-Path $repoRoot 'code/scripts/check_repo.ps1')
exit $LASTEXITCODE
