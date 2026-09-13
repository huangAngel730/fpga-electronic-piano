$ErrorActionPreference = "Stop"

$gowinRoot = "D:\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64"
$programmerRoot = "D:\Gowin\Programmer_V1.9.12.02"
$deviceFile = "$gowinRoot\IDE\data\device\GW5AT-60B\PBGA484A.json"
$workspaceLink = "D:\Gowin\workspace\embedded_fpga"

$checks = [ordered]@{
    "Gowin EDA CLI" = Test-Path -LiteralPath "$gowinRoot\IDE\bin\gw_sh.exe"
    "Gowin EDA GUI" = Test-Path -LiteralPath "$gowinRoot\IDE\bin\gw_ide.exe"
    "GW5AT-60B PBGA484A device database" = Test-Path -LiteralPath $deviceFile
    "Gowin Programmer CLI" = Test-Path -LiteralPath "$programmerRoot\bin\programmer_cli.exe"
    "ASCII workspace junction" = Test-Path -LiteralPath $workspaceLink
    "Icarus Verilog" = Test-Path -LiteralPath "D:\Gowin\oss-cad-suite\bin\iverilog.exe"
    "Verilator" = Test-Path -LiteralPath "D:\Gowin\oss-cad-suite\bin\verilator_bin.exe"
    "Yosys" = Test-Path -LiteralPath "D:\Gowin\oss-cad-suite\bin\yosys.exe"
    "GTKWave" = Test-Path -LiteralPath "D:\Gowin\oss-cad-suite\bin\gtkwave.exe"
}

$checks.GetEnumerator() | ForEach-Object {
    [pscustomobject]@{
        Check = $_.Key
        Result = if ($_.Value) { "PASS" } else { "MISSING" }
    }
} | Format-Table -AutoSize

if ($checks.Values -contains $false) {
    exit 1
}

Write-Host "All FPGA development environment checks passed."
