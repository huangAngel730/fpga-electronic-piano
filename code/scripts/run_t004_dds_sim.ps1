# T004 DDS仿真脚本（修正版）
# 使用Icarus Verilog

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "=== T004 DDS Oscillator Simulation ===" -ForegroundColor Cyan

# 检查黄金参考文件
$goldenFile = "model\generated\dds_test\dds_a4_440hz.txt"
if (-not (Test-Path $goldenFile)) {
    Write-Host "Generating DDS test vectors..." -ForegroundColor Yellow
    Push-Location model
    python generate_dds_test_vectors.py
    Pop-Location

    if (-not (Test-Path $goldenFile)) {
        Write-Host "ERROR: Failed to generate test vectors" -ForegroundColor Red
        exit 1
    }
}

# 检查波表.mem文件
$memFile = "model\generated\wavetables\sine_1024_32767.mem"
if (-not (Test-Path $memFile)) {
    Write-Host "Generating sine wavetable..." -ForegroundColor Yellow
    Push-Location model
    python -c @"
from dds_model import make_wavetable
table = make_wavetable('sine', 1024, 32767)
with open('generated/wavetables/sine_1024_32767.mem', 'w') as f:
    for val in table:
        unsigned = val if val >= 0 else (1 << 16) + val
        f.write(f'{unsigned:04x}\n')
print('Generated sine_1024_32767.mem')
"@
    Pop-Location
}

# 使用Icarus Verilog仿真
$iverilog = Get-Command iverilog -ErrorAction SilentlyContinue
if (-not $iverilog) {
    Write-Host "ERROR: iverilog not found" -ForegroundColor Red
    Write-Host "Please install Icarus Verilog" -ForegroundColor Yellow
    exit 1
}

Write-Host "Compiling RTL..." -ForegroundColor Green
iverilog -g2012 -o build\tb_dds.vvp `
    -s tb_dds_oscillator `
    rtl\audio\dds_oscillator.sv `
    tb\audio\tb_dds_oscillator.sv

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Compilation failed" -ForegroundColor Red
    exit 1
}

Write-Host "Running simulation..." -ForegroundColor Green
vvp build\tb_dds.vvp
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host "`nPASS: T004 DDS simulation" -ForegroundColor Green
} else {
    Write-Host "`nFAIL: T004 DDS simulation (exit code: $exitCode)" -ForegroundColor Red
}

exit $exitCode
