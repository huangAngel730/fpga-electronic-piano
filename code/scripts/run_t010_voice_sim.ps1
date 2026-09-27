# T010 声部管理仿真脚本（修正版）
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "=== T010 Voice Allocator Simulation ===" -ForegroundColor Cyan

# 使用Icarus Verilog仿真
$iverilog = Get-Command iverilog -ErrorAction SilentlyContinue
if (-not $iverilog) {
    Write-Host "ERROR: iverilog not found" -ForegroundColor Red
    exit 1
}

Write-Host "Compiling RTL..." -ForegroundColor Green
iverilog -g2012 -o build\tb_voice.vvp `
    -s tb_voice_allocator `
    rtl\audio\voice_allocator_4.sv `
    tb\audio\tb_voice_allocator.sv

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Compilation failed" -ForegroundColor Red
    exit 1
}

Write-Host "Running simulation..." -ForegroundColor Green
vvp build\tb_voice.vvp
$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host "`nPASS: T010 Voice allocator simulation" -ForegroundColor Green
} else {
    Write-Host "`nFAIL: T010 Voice allocator simulation (exit code: $exitCode)" -ForegroundColor Red
}

exit $exitCode
