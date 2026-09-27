# T009 ADSR仿真脚本（修正版）
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "=== T009 ADSR Piano Envelope Simulation ===" -ForegroundColor Cyan

# 检查Velocity ROM
$romFile = "model\generated\wavetables\velocity_gain_rom.mem"
if (-not (Test-Path $romFile)) {
    Write-Host "Generating Velocity ROM..." -ForegroundColor Yellow
    Push-Location model
    python -c @"
from adsr_piano import velocity_to_gain
with open('generated/wavetables/velocity_gain_rom.mem', 'w') as f:
    for v in range(1024):
        gain = velocity_to_gain(v)
        f.write(f'{gain:04x}\n')
print('Generated velocity_gain_rom.mem')
"@
    Pop-Location

    if (-not (Test-Path $romFile)) {
        Write-Host "ERROR: Failed to generate Velocity ROM" -ForegroundColor Red
        exit 1
    }
}

# 使用Icarus Verilog仿真
$iverilog = Get-Command iverilog -ErrorAction SilentlyContinue
if (-not $iverilog) {
    Write-Host "ERROR: iverilog not found" -ForegroundColor Red
    exit 1
}

Write-Host "Compiling RTL..." -ForegroundColor Green
iverilog -g2012 -o build\tb_adsr.vvp `
    -s tb_adsr_piano `
    rtl\audio\adsr_piano_envelope.sv `
    tb\audio\tb_adsr_piano.sv

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Compilation failed" -ForegroundColor Red
    exit 1
}

Write-Host "Running simulation..." -ForegroundColor Green
vvp build\tb_adsr.vvp
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host "`nPASS: T009 ADSR simulation" -ForegroundColor Green
} else {
    Write-Host "`nFAIL: T009 ADSR simulation (exit code: $exitCode)" -ForegroundColor Red
}

exit $exitCode
