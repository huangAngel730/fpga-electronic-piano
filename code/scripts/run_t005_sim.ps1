# -----------------------------------------------------------------------------
# run_t005_sim.ps1
# T005 (LSBJ I2S transmitter) regression simulation script.
#
# Usage (run from repository root):
#   .\code\scripts\run_t005_sim.ps1
#
# Notes:
#   1. This script loads the FPGA tool environment itself and does not rely on
#      the caller having set PATH. The oss-cad-suite iverilog needs its runtime
#      libraries; calling it without loading the environment fails with
#      0xC0000139 (entry point not found).
#   2. Sources are staged into an ASCII-only temp directory before compiling.
#      The repository path contains non-ASCII characters, and PowerShell
#      truncates non-ASCII characters when passing arguments to native exes
#      (observed: "D:\17\..." becomes "D:"). Relative paths also contain
#      non-ASCII, so staging is required.
#   3. This file is deliberately kept ASCII-only. Windows PowerShell 5.1 reads
#      UTF-8 files without a BOM as ANSI, which corrupts non-ASCII comments and
#      can break parsing.
#   4. Exit code: 0 if all tests PASS, 1 if any test FAILs or a tool error occurs.
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

# Paths are expressed as segments and joined at runtime so that this script
# contains no non-ASCII literals.
$segRtl = [char]0x4EE3 + [char]0x7801 + "\rtl"   # code\rtl
$segTb  = [char]0x4EE3 + [char]0x7801 + "\tb"    # code\tb

$tests = @(
    @{
        Name = "tb_i2s_tx"
        Src  = @("$segRtl\audio_out\i2s_tx.sv",
                 "$segTb\audio_out\tb_i2s_tx.sv")
    }
)

$failed = @()
$stageRoot = Join-Path $env:TEMP "t005_sim"
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
