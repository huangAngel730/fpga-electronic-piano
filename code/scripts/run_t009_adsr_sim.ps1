# T009 ADSR仿真脚本
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
}

# 尝试使用Icarus Verilog
$iverilog = Get-Command iverilog -ErrorAction SilentlyContinue
if ($iverilog) {
    Write-Host "Using Icarus Verilog" -ForegroundColor Green

    iverilog -g2012 -o tb_adsr.vvp `
        -s tb_adsr_piano `
        rtl\audio\adsr_piano_envelope.sv `
        tb\audio\tb_adsr_piano.sv

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Compilation failed" -ForegroundColor Red
        exit 1
    }

    vvp tb_adsr.vvp
    $exitCode = $LASTEXITCODE
    Remove-Item tb_adsr.vvp -ErrorAction SilentlyContinue

    if ($exitCode -eq 0) {
        Write-Host "`nPASS: T009 ADSR simulation" -ForegroundColor Green
        exit 0
    } else {
        Write-Host "`nFAIL: T009 ADSR simulation" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "ERROR: iverilog not found" -ForegroundColor Red
    exit 1
}
