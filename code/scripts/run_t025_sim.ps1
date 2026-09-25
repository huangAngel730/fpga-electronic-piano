# T025 UART status reporter self-check. Run at repository root.
# UART TX/RX unit regressions: .\code\scripts\run_uart_rx_probe_sim.ps1
$ErrorActionPreference = 'Stop'

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
Set-Location $repoRoot
. (Join-Path $PSScriptRoot 'enter_fpga_env.ps1') | Out-Null

$iverilog = 'D:\Gowin\oss-cad-suite\bin\iverilog.exe'
$vvp = 'D:\Gowin\oss-cad-suite\bin\vvp.exe'
foreach ($tool in @($iverilog, $vvp)) {
    if (-not (Test-Path -LiteralPath $tool)) {
        throw "Missing simulator: $tool"
    }
}

# Stage sources under an ASCII-only path for Windows native-tool arguments.
$stage = Join-Path $env:TEMP ('t025_sim_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    $sources = @(
        'code\rtl\common\uart_tx.sv',
        'code\rtl\common\uart_rx.sv',
        'code\rtl\board\uart_status_reporter.sv',
        'code\tb\board\tb_uart_status_reporter.sv'
    )
    $staged = @()
    for ($i = 0; $i -lt $sources.Count; $i++) {
        $source = Join-Path $repoRoot $sources[$i]
        if (-not (Test-Path -LiteralPath $source)) {
            throw "Missing source: $source"
        }
        $destination = Join-Path $stage ('src_' + $i + '.sv')
        Copy-Item -LiteralPath $source -Destination $destination
        $staged += $destination
    }

    $output = Join-Path $stage 'tb_uart_status_reporter.vvp'
    & $iverilog -g2012 -Wall -s tb_uart_status_reporter -o $output @staged
    if ($LASTEXITCODE -ne 0) {
        throw 'T025 compile failed'
    }
    & $vvp $output
    if ($LASTEXITCODE -ne 0) {
        throw 'T025 simulation failed'
    }
    Write-Host 'T025 UART status reporter: ALL PASS'
}
finally {
    Remove-Item -LiteralPath $stage -Recurse -Force -ErrorAction SilentlyContinue
}
