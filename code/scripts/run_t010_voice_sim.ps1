# T010 声部管理仿真脚本
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot\..

Write-Host "=== T010 Voice Allocator Simulation ===" -ForegroundColor Cyan

$iverilog = Get-Command iverilog -ErrorAction SilentlyContinue
if ($iverilog) {
    Write-Host "Using Icarus Verilog" -ForegroundColor Green

    iverilog -g2012 -o tb_voice.vvp `
        -s tb_voice_allocator `
        rtl\audio\voice_allocator_4.sv `
        tb\audio\tb_voice_allocator.sv

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Compilation failed" -ForegroundColor Red
        exit 1
    }

    vvp tb_voice.vvp
    $exitCode = $LASTEXITCODE
    Remove-Item tb_voice.vvp -ErrorAction SilentlyContinue

    if ($exitCode -eq 0) {
        Write-Host "`nPASS: T010 Voice allocator simulation" -ForegroundColor Green
        exit 0
    } else {
        Write-Host "`nFAIL: T010 Voice allocator simulation" -ForegroundColor Red
        exit 1
    }
} else {
    Write-Host "ERROR: iverilog not found" -ForegroundColor Red
    exit 1
}
