# T004 standalone DDS regression versus M1 model.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $PSScriptRoot 'enter_fpga_env.ps1') | Out-Null
$iverilog = 'D:\Gowin\oss-cad-suite\bin\iverilog.exe'
$vvp = 'D:\Gowin\oss-cad-suite\bin\vvp.exe'
$stage = Join-Path $env:TEMP ('t004_m2_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    $rom = Join-Path $stage 'sine.mem'
    $vectors = Join-Path $stage 'dds_vectors.txt'
    $generate = @"
from pathlib import Path
import sys
sys.path.insert(0, str(Path(sys.argv[1]) / 'code/model'))
from dds_model import WavetableOscillator, make_wavetable, midi_note_to_fcw
# Keep the existing M1 standalone ROM amplitude, pending PCM scale decision.
table = make_wavetable('sine', 1024, 32767)
Path(sys.argv[2]).write_text(''.join(f'{value & 0xffff:04x}\n' for value in table), encoding='utf-8', newline='\n')
osc = WavetableOscillator(table=table, fcw=midi_note_to_fcw(69))
with Path(sys.argv[3]).open('w', encoding='utf-8', newline='\n') as stream:
    for index in range(1000):
        if index == 900:
            osc.reset()
        fcw = (midi_note_to_fcw(69) if index < 500 else
               midi_note_to_fcw(72) if index < 700 else
               0 if index < 800 else 0xffffffff if index < 900 else midi_note_to_fcw(69))
        osc.set_fcw(fcw)
        phase = osc.phase
        value = osc.step()
        stream.write(f'{index} {fcw:08x} {phase:08x} {value}\n')
"@
    $generate | python -X utf8 - $repoRoot $rom $vectors
    if ($LASTEXITCODE -ne 0) { throw 'T004 M1 reference generation failed' }
    $rtl = Join-Path $stage 'dds.sv'
    $tb = Join-Path $stage 'tb.sv'
    Copy-Item -LiteralPath (Join-Path $repoRoot 'code\rtl\audio\dds_oscillator.sv') -Destination $rtl
    Copy-Item -LiteralPath (Join-Path $repoRoot 'code\tb\audio\tb_dds_oscillator.sv') -Destination $tb
    $compiled = Join-Path $stage 'dds.vvp'
    $savedPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $iverilog -g2012 -Wall -s tb_dds_oscillator -o $compiled $rtl $tb
    $compileExit = $LASTEXITCODE
    $ErrorActionPreference = $savedPreference
    if ($compileExit -ne 0) { throw 'T004 RTL compilation failed' }
    & $vvp $compiled "+WAVETABLE_PATH=$rom" "+VECTORS=$vectors"
    if ($LASTEXITCODE -ne 0) { throw 'T004 DDS versus M1 model mismatch' }
    $ErrorActionPreference = 'Continue'
    & $vvp $compiled "+WAVETABLE_PATH=$(Join-Path $stage 'missing.mem')" "+VECTORS=$vectors" *> (Join-Path $stage 'missing_rom.log')
    $missingExit = $LASTEXITCODE
    $ErrorActionPreference = $savedPreference
    if ($missingExit -eq 0) { throw 'T004 missing-ROM negative test falsely passed' }
    # A truncated ROM must also fail even if its first word exists.
    $shortRom = Join-Path $stage 'short.mem'
    Get-Content -LiteralPath $rom -TotalCount 1 | Set-Content -LiteralPath $shortRom -Encoding Ascii
    $ErrorActionPreference = 'Continue'
    & $vvp $compiled "+WAVETABLE_PATH=$shortRom" "+VECTORS=$vectors" *> (Join-Path $stage 'short_rom.log')
    $shortExit = $LASTEXITCODE
    $ErrorActionPreference = $savedPreference
    if ($shortExit -eq 0) { throw 'T004 truncated-ROM negative test falsely passed' }
    $tamper = @"
from pathlib import Path
import sys
p = Path(sys.argv[1]); lines = p.read_text(encoding='utf-8').splitlines()
parts = lines[10].split(); parts[3] = str(int(parts[3]) + 1); lines[10] = ' '.join(parts)
p.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
"@
    $tamper | python -X utf8 - $vectors
    if ($LASTEXITCODE -ne 0) { throw 'T004 negative-vector preparation failed' }
    $ErrorActionPreference = 'Continue'
    & $vvp $compiled "+WAVETABLE_PATH=$rom" "+VECTORS=$vectors" *> (Join-Path $stage 'bad_vector.log')
    $mismatchExit = $LASTEXITCODE
    $ErrorActionPreference = $savedPreference
    if ($mismatchExit -eq 0) { throw 'T004 corrupt-vector negative test falsely passed' }
    Write-Host "T004 ALL PASS: 1000 model samples; missing ROM exit=$missingExit; truncated ROM exit=$shortExit; corrupt vector exit=$mismatchExit"
    # Expected negative tests must not leak their exit code to callers.
    $global:LASTEXITCODE = 0
} finally {
    $resolved = [IO.Path]::GetFullPath($stage)
    $tempRoot = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith($tempRoot, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe cleanup target: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction SilentlyContinue
}
