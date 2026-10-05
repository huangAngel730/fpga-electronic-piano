# -----------------------------------------------------------------------------
# run_uart_echo_probe_sim.ps1
# UART RX external-drive echo diagnostic self-check simulation script.
#
# Usage (run from repository root):
#   .\code\scripts\run_uart_echo_probe_sim.ps1
#
# Tests (all iverilog, SystemVerilog 2012):
#   tb_uart_tx         - code/rtl/common/uart_tx.sv       (unit, reused)
#   tb_uart_rx         - code/rtl/common/uart_rx.sv       (unit, reused)
#   tb_echo_fifo       - code/rtl/common/echo_fifo.sv     (unit, new)
#   tb_uart_echo_probe - code/rtl/board/uart_echo_probe.sv (integration, new)
#
# The integration test does three things a serial terminal cannot do offline:
#   1. it decodes the ASCII report on uart_tx back into lines and fields,
#      so the checked values are exactly what a human would read on COM13;
#   2. it drives probe_rx with well-formed and deliberately malformed frames;
#   3. it decodes both echo pins byte by byte and compares them against the
#      bytes that were sent, so "echo works" is a byte-exact statement rather
#      than "something came back".
#
# Notes:
#   1. This script loads the FPGA tool environment itself. The oss-cad-suite
#      iverilog needs its runtime libraries; calling it without loading the
#      environment fails with 0xC0000139 (entry point not found).
#   2. Sources are staged into an ASCII-only temp directory before compiling,
#      because PowerShell truncates non-ASCII characters when passing
#      arguments to native exes.
#   3. This file is deliberately kept ASCII-only. Windows PowerShell 5.1 reads
#      UTF-8 files without a BOM as ANSI, which corrupts non-ASCII comments and
#      can break parsing.
#   4. Exit code: 0 if all tests PASS, 1 if any test FAILs or a tool error occurs.
#   5. The integration test runs about 210 ms of simulated time (about 210k
#      sys_clk cycles at 1 MHz). It is dominated by waiting for complete
#      reports: one report is about 175 bytes, which takes about 15.8 ms at
#      the simulated 115200 bps.
#
# On-board reference (not exercised by this script):
#   Wiring, CH340 settings, expected report lines and the decision table are
#   documented at the top of code/rtl/board/uart_echo_probe.sv and in
#   code/constraints/uart_echo_probe.cst.
# -----------------------------------------------------------------------------

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $repoRoot

# Load tool environment
. (Join-Path $PSScriptRoot "enter_fpga_env.ps1") | Out-Null

$iverilog = "D:\Gowin\oss-cad-suite\bin\iverilog.exe"
$vvp      = "D:\Gowin\oss-cad-suite\bin\vvp.exe"

foreach ($tool in @($iverilog, $vvp)) {
    if (-not (Test-Path -LiteralPath $tool)) {
        Write-Host "Missing tool: $tool" -ForegroundColor Red
        exit 1
    }
}

$segRtl = "code\rtl"
$segTb  = "code\tb"

$uartTx    = "$segRtl\common\uart_tx.sv"
$uartRx    = "$segRtl\common\uart_rx.sv"
$echoFifo  = "$segRtl\common\echo_fifo.sv"
$resetSync = "$segRtl\common\reset_sync.sv"
$echoTop   = "$segRtl\board\uart_echo_probe.sv"

$tests = @(
    @{
        Name = "tb_uart_tx"
        Src  = @($uartTx, "$segTb\common\tb_uart_tx.sv")
    },
    @{
        Name = "tb_uart_rx"
        Src  = @($uartRx, "$segTb\common\tb_uart_rx.sv")
    },
    @{
        Name = "tb_echo_fifo"
        Src  = @($echoFifo, "$segTb\common\tb_echo_fifo.sv")
    },
    @{
        Name = "tb_uart_echo_probe"
        Src  = @($uartTx, $uartRx, $echoFifo, $resetSync, $echoTop,
                 "$segTb\board\tb_uart_echo_probe.sv")
    }
)

$failed = @()
# Unique staging directory per run: a fixed name let a stale .vvp from an earlier
# run satisfy the "did the compile produce an artifact" test, and let two
# concurrent runs delete each other's sources (see run_t007_sim.ps1 for the
# failure signatures this produced on 2026-09-18).
$stageRoot = Join-Path $env:TEMP ("uart_echo_probe_sim_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null

foreach ($test in $tests) {
    $name = $test.Name
    $out  = Join-Path $stageRoot "$name.vvp"

    Write-Host ""
    Write-Host ("=" * 60)
    Write-Host "Compile and run $name"
    Write-Host ("=" * 60)

    Remove-Item -LiteralPath $out -ErrorAction SilentlyContinue

    # Stage sources into the ASCII-only temp directory
    $staged = @()
    $idx = 0
    foreach ($src in $test.Src) {
        $dst = Join-Path $stageRoot "src_$idx.sv"
        Copy-Item -LiteralPath (Join-Path $repoRoot $src) -Destination $dst -Force
        $staged += $dst
        $idx++
    }

    # Compile. iverilog writes some warnings to stderr; judge by artifact.
    # stderr must not abort the script, so relax ErrorActionPreference here:
    # a warning would otherwise be treated as a terminating error.
    $ivArgs = @("-g2012", "-Wall", "-o", $out) + $staged
    $prevEap = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    & $iverilog @ivArgs 2>&1 | ForEach-Object { "  $_" }
    $ErrorActionPreference = $prevEap

    if (-not (Test-Path -LiteralPath $out)) {
        Write-Host "  Compile failed, no simulation artifact produced" -ForegroundColor Red
        $failed += $name
        continue
    }

    # Run
    $result = & $vvp $out 2>&1 | ForEach-Object { "$_" }
    $result | ForEach-Object { $_ }

    if ($result -match "^FAIL") {
        Write-Host "  >>> $name FAIL" -ForegroundColor Red
        $failed += $name
    } else {
        Write-Host "  >>> $name PASS" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host ("=" * 60)
if ($failed.Count -eq 0) {
    Write-Host "ALL PASS" -ForegroundColor Green
    exit 0
} else {
    Write-Host ("FAILED: " + ($failed -join ", ")) -ForegroundColor Red
    exit 1
}
