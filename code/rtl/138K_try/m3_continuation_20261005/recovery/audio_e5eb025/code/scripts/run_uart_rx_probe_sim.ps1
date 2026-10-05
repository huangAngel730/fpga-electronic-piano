# -----------------------------------------------------------------------------
# run_uart_rx_probe_sim.ps1
# UART RX diagnostic self-check simulation script.
#
# Usage (run from repository root):
#   .\code\scripts\run_uart_rx_probe_sim.ps1
#
# Tests (all iverilog, SystemVerilog 2012):
#   tb_uart_tx        - code/rtl/common/uart_tx.sv      (unit)
#   tb_uart_rx        - code/rtl/common/uart_rx.sv      (unit)
#   tb_uart_rx_probe  - code/rtl/board/uart_rx_probe.sv (integration)
#
# The integration test decodes the ASCII report that the probe sends on
# uart_tx back into lines and fields, so it checks exactly what a human
# would see in a serial terminal.
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
#
# On-board reference (not exercised by this script, for reading the report):
#   The probe emits, every REPORT_MS, a line per candidate pin:
#     A lv=1 ed=001E by=0003 la=55 fe=0000 mn=01B2
#   mn is the measured bit period in sys_clk cycles, so the peer baud rate is
#   50_000_000 / mn.  At 115200 bps that is 0x01B2 = 434.
#   The pin whose by count grows is the real UART RX pin.
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

$uartTx     = "$segRtl\common\uart_tx.sv"
$uartRx     = "$segRtl\common\uart_rx.sv"
$resetSync  = "$segRtl\common\reset_sync.sv"
$probeTop   = "$segRtl\board\uart_rx_probe.sv"

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
        Name = "tb_uart_rx_probe"
        Src  = @($uartTx, $uartRx, $resetSync, $probeTop,
                 "$segTb\board\tb_uart_rx_probe.sv")
    }
)

$failed = @()
# Unique staging directory per run (GUID suffix).
#
# A FIXED name ($env:TEMP\uart_rx_probe_sim) was used until 2026-09-18. Two runs
# started at the same time (another developer, another AI agent on the same
# host, or a manual run overlapping the push gate) deleted and recreated the
# directory the first run was compiling in; observed as "Compile failed, no
# simulation artifact produced" and a false FAIL on identical sources. Same fix
# as run_t007_sim.ps1 and run_uart_echo_probe_sim.ps1.
$stageRoot = Join-Path $env:TEMP ("uart_rx_probe_sim_" + [guid]::NewGuid().ToString("N"))
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
