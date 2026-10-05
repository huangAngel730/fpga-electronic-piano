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

& $PythonExe "$Root\model\generate_wavetable_v2.py"
if ($LASTEXITCODE -ne 0) { throw 'V2 wavetable generation failed' }
& $PythonExe "$Root\model\validate_v2.py" --output "$Root\output\v2"
if ($LASTEXITCODE -ne 0) { throw 'V2 Python validation failed' }

$Iverilog = Get-Command iverilog -ErrorAction SilentlyContinue
$Vvp = Get-Command vvp -ErrorAction SilentlyContinue
if ($null -ne $Iverilog -and $null -ne $Vvp) {
    Push-Location $Root
    try {
        New-Item -ItemType Directory -Force -Path output\v2 | Out-Null
        iverilog -g2012 -s tb_piano_dds_oscillator_v2 `
            -o output\v2\tb_piano_dds_oscillator_v2.vvp `
            rtl_v2\audio\piano_dds_oscillator_v2.sv `
            tb\tb_piano_dds_oscillator_v2.sv
        if ($LASTEXITCODE -ne 0) { throw 'V2 iverilog compile failed' }
        vvp output\v2\tb_piano_dds_oscillator_v2.vvp
        if ($LASTEXITCODE -ne 0) { throw 'V2 RTL simulation failed' }
    }
    finally {
        Pop-Location
    }
}
else {
    Write-Warning 'iverilog/vvp not found; V2 Python model passed, RTL simulation skipped.'
}
