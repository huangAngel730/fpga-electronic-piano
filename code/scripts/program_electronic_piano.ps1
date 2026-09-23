# Download a bitstream to the Tang Mega 60K board.
#
# Pure ASCII on purpose: Windows PowerShell 5.1 decodes BOM-less UTF-8 as GBK,
# which corrupts non-ASCII literals (see code/AGENTS.md).
#
# Usage:
#   .\code\scripts\program_electronic_piano.ps1              # SRAM download (volatile)
#   .\code\scripts\program_electronic_piano.ps1 -Mode flash  # write external flash (persistent)
#   .\code\scripts\program_electronic_piano.ps1 -ScanOnly    # just check the cable/chain
#
#   # diagnostic UART-RX probe bitstream instead of the main design:
#   .\code\scripts\program_electronic_piano.ps1 -Bitstream code\build\probe\impl\pnr\uart_rx_probe.fs
#
#   # diagnostic UART RX echo bitstream (external CH340 drives PMOD0 R17):
#   .\code\scripts\program_electronic_piano.ps1 -Bitstream code\build\echo_probe\impl\pnr\uart_echo_probe.fs
#
# SRAM download is the default because it is reversible: power-cycling the board
# restores whatever was in flash. Use -Mode flash only when you intend to keep
# the design on the board across power cycles.
#
# -Bitstream takes a path relative to the repository root (or an absolute path).

[CmdletBinding()]
param(
    [ValidateSet('sram', 'flash')]
    [string]$Mode = 'sram',

    [switch]$ScanOnly,

    # Repository-relative path of the .fs file to download.
    [string]$Bitstream = 'code\build\impl\pnr\electronic_piano.fs',

    # Override if the Programmer is installed somewhere else.
    [string]$ProgrammerRoot = 'D:\Gowin\Programmer_V1.9.12.02'
)

$ErrorActionPreference = 'Stop'

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

# Keep the repository path ASCII-safe for the native tool: PowerShell 5.1 can
# truncate non-ASCII arguments passed to an exe, so we always run the CLI with
# its own directory as the working directory and pass forward-slash paths.
$cli = Join-Path $ProgrammerRoot 'bin\programmer_cli.exe'
if (-not (Test-Path -LiteralPath $cli)) {
    throw "programmer_cli.exe not found at: $cli"
}
$cliDir = Split-Path -Parent $cli

if ([IO.Path]::IsPathRooted($Bitstream)) {
    $bitstream = $Bitstream
} else {
    $bitstream = Join-Path $repoRoot $Bitstream
}
if (-not $ScanOnly -and -not (Test-Path -LiteralPath $bitstream)) {
    throw "Bitstream not found: $bitstream`nRun: .\code\scripts\build_electronic_piano.ps1 -Flow pnr"
}

$fsArg = ($bitstream -replace '\\', '/')

# operation_index: 2 = SRAM Program, 6 = embFlash Erase,Program,Verify.
# The Tang Mega 60K has no embedded flash for the FPGA, so "flash" here means
# the external SPI flash: 9 = exFlash Erase,Program,Verify.
$operation = switch ($Mode) {
    'sram'  { 2 }
    'flash' { 9 }
}

Write-Host '=== electronic_piano programmer ==='
Write-Host "repo      : $repoRoot"
Write-Host "tool      : $cli"
Write-Host "device    : GW5AT-60B"
Write-Host "mode      : $Mode (operation_index=$operation)"
Write-Host "bitstream : $fsArg"
Write-Host ''

# Native tools write progress to stderr; PS 5.1 would treat that as a fatal
# error, so relax the preference for the duration of the call.
$prevEap = $ErrorActionPreference
$ErrorActionPreference = 'Continue'
Push-Location $cliDir
try {
    if ($ScanOnly) {
        Write-Host '--- scanning JTAG chain ---'
        & $cli --scan 2>&1 | ForEach-Object { Write-Host "  $_" }
        $code = $LASTEXITCODE
        Write-Host ''
        Write-Host "scan exit code: $code"
        if ($code -ne 0) {
            Write-Host ''
            Write-Host 'No Gowin device found. Check:'
            Write-Host '  1. USB cable from the PC to the board JTAG/debug port'
            Write-Host '  2. Gowin USB Cable driver installed (driver\GowinUSBCableDriverV5_for_win7+.exe)'
            Write-Host '  3. Board powered on'
        }
        exit $code
    }

    Write-Host '--- scanning JTAG chain ---'
    & $cli --scan 2>&1 | ForEach-Object { Write-Host "  $_" }
    if ($LASTEXITCODE -ne 0) {
        throw "JTAG scan failed (exit $LASTEXITCODE); aborting before programming."
    }

    Write-Host ''
    Write-Host "--- programming ($Mode) ---"
    & $cli --device GW5AT-60B --operation_index $operation --fsFile $fsArg 2>&1 |
        ForEach-Object { Write-Host "  $_" }
    $code = $LASTEXITCODE
    Write-Host ''
    Write-Host "programmer exit code: $code"
    if ($code -eq 0) {
        Write-Host 'Download reported success.'
        if ($Mode -eq 'sram') {
            Write-Host 'SRAM is volatile: the design runs until the board loses power.'
        }
        Write-Host ''
        if ($bitstream -match 'uart_echo_probe') {
            Write-Host 'Expected on-board result: the report line ECHO-PROBE RX=R17'
            Write-Host 'ECHO115200=R18 ECHO31250=T18 every 250 ms on the board'
            Write-Host 'USB-UART port (COM13) at 115200 8N1, and byte-for-byte'
            Write-Host 'echo of whatever is driven into R17. Feed R17 from an'
            Write-Host 'external 3.3 V USB-TTL TX at J14 pin 5 (GND J14 pin 12)'
            Write-Host 'or at J9 pin 8 (GND J9 pin 3/4). Optional echo read-back:'
            Write-Host 'J14 pin 8 (115200) / J14 pin 7 (31250).'
            Write-Host 'Pins, wiring and read-out rules: see the header of'
            Write-Host 'code\constraints\uart_echo_probe.cst and section 3.5.3 of'
            Write-Host 'the board fact file code\docs\.'
            Write-Host 'The speaker stays silent (pa_en is held high).'
        } elseif ($bitstream -match 'uart_rx_probe') {
            Write-Host 'Expected on-board result: a UART report every 250 ms on'
            Write-Host 'the board USB-UART port at 115200 8N1, starting with'
            Write-Host 'UART-RX-PROBE A=V14 B=Y14. The speaker stays silent.'
        } else {
            Write-Host 'Expected on-board result: a steady 440 Hz sine tone on the speaker.'
        }
    }
    exit $code
} finally {
    Pop-Location
    $ErrorActionPreference = $prevEap
}
