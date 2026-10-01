$ErrorActionPreference = 'Stop'
$Root = Split-Path -Parent $PSScriptRoot

$PythonCandidates = @(
    (Join-Path $env:USERPROFILE 'miniconda3\python.exe'),
    (Join-Path $env:USERPROFILE 'anaconda3\python.exe')
)
$PythonCommand = Get-Command python -ErrorAction SilentlyContinue
if ($null -ne $PythonCommand) {
    $PythonCandidates += $PythonCommand.Source
}
$PythonExe = $PythonCandidates |
    Where-Object { $_ -and (Test-Path -LiteralPath $_) } |
    Select-Object -First 1
if (-not $PythonExe) {
    throw 'No usable Python interpreter found.'
}

& $PythonExe "$Root\model\generate_wavetable.py"
if ($LASTEXITCODE -ne 0) { throw 'wavetable generation failed' }
& $PythonExe "$Root\model\validate_prototype.py" --output "$Root\output"
if ($LASTEXITCODE -ne 0) { throw 'Python validation failed' }

$Iverilog = Get-Command iverilog -ErrorAction SilentlyContinue
$Vvp = Get-Command vvp -ErrorAction SilentlyContinue
if ($null -ne $Iverilog -and $null -ne $Vvp) {
    Push-Location $Root
    try {
        New-Item -ItemType Directory -Force -Path output | Out-Null
        iverilog -g2012 -s tb_piano_dds_oscillator `
            -o output\tb_piano_dds_oscillator.vvp `
            rtl\audio\piano_dds_oscillator.sv `
            tb\tb_piano_dds_oscillator.sv
        if ($LASTEXITCODE -ne 0) { throw 'iverilog compile failed' }
        vvp output\tb_piano_dds_oscillator.vvp
        if ($LASTEXITCODE -ne 0) { throw 'RTL simulation failed' }
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Warning 'iverilog/vvp not found; Python model passed, RTL simulation skipped.'
}

