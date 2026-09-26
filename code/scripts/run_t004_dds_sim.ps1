# T004 DDS仿真脚本
# 使用Icarus Verilog或ModelSim

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "=== T004 DDS Oscillator Simulation ===" -ForegroundColor Cyan

# 检查黄金参考文件
$goldenFile = "model\generated\dds_test\dds_a4_440hz.txt"
if (-not (Test-Path $goldenFile)) {
    Write-Host "ERROR: Golden reference not found: $goldenFile" -ForegroundColor Red
    Write-Host "Generating golden reference..." -ForegroundColor Yellow

    Push-Location model
    python generate_dds_test_vectors.py
    Pop-Location

    if (-not (Test-Path $goldenFile)) {
        Write-Host "ERROR: Failed to generate golden reference" -ForegroundColor Red
        exit 1
    }
}

# 检查波表.mem文件
$memFile = "model\generated\wavetables\sine_1024_32767.mem"
if (-not (Test-Path $memFile)) {
    Write-Host "ERROR: Wavetable .mem file not found: $memFile" -ForegroundColor Red
    Write-Host "Generating wavetable..." -ForegroundColor Yellow

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

    if (-not (Test-Path $memFile)) {
        Write-Host "ERROR: Failed to generate wavetable" -ForegroundColor Red
        exit 1
    }
}

# 尝试使用Icarus Verilog
$iverilog = Get-Command iverilog -ErrorAction SilentlyContinue
if ($iverilog) {
    Write-Host "Using Icarus Verilog" -ForegroundColor Green

    # 编译
    iverilog -g2012 -o tb_dds.vvp `
        -s tb_dds_oscillator `
        rtl\audio\dds_oscillator.sv `
        tb\audio\tb_dds_oscillator.sv

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Compilation failed" -ForegroundColor Red
        exit 1
    }

    # 运行
    vvp tb_dds.vvp
    $exitCode = $LASTEXITCODE

    # 清理
    Remove-Item tb_dds.vvp -ErrorAction SilentlyContinue

    if ($exitCode -eq 0) {
        Write-Host "`nPASS: T004 DDS simulation" -ForegroundColor Green
        exit 0
    } else {
        Write-Host "`nFAIL: T004 DDS simulation" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "ERROR: No simulator found (iverilog)" -ForegroundColor Red
    Write-Host "Please install Icarus Verilog or use ModelSim" -ForegroundColor Yellow
    exit 1
}
