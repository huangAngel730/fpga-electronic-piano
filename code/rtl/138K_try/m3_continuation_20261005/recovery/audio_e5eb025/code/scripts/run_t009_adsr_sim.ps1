# T009 sample-counted boundary checks. Full model comparison remains separate.
$ErrorActionPreference = 'Stop'
$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $PSScriptRoot 'enter_fpga_env.ps1') | Out-Null
$iverilog = 'D:\Gowin\oss-cad-suite\bin\iverilog.exe'
$vvp = 'D:\Gowin\oss-cad-suite\bin\vvp.exe'
$stage = Join-Path $env:TEMP ('t009_gate_' + [guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage | Out-Null
try {
    $rom = Join-Path $stage 'velocity.mem'
    $generate = @"
from pathlib import Path
import sys
sys.path.insert(0, str(Path(sys.argv[1]) / 'code/model'))
from adsr_piano import velocity_to_gain
Path(sys.argv[2]).write_text(''.join(f'{velocity_to_gain(v):04x}\n' for v in range(1024)), encoding='utf-8', newline='\n')
"@
    $generate | python -X utf8 - $repoRoot $rom
    if ($LASTEXITCODE -ne 0) { throw 'T009 M1 ROM reference generation failed' }
    $rtl = Join-Path $stage 'adsr.sv'
    $tb = Join-Path $stage 'tb.sv'
    Copy-Item -LiteralPath (Join-Path $repoRoot 'code\rtl\audio\adsr_piano_envelope.sv') -Destination $rtl
    Copy-Item -LiteralPath (Join-Path $repoRoot 'code\tb\audio\tb_adsr_piano.sv') -Destination $tb
    $compiled = Join-Path $stage 'adsr.vvp'
    $savedPreference = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & $iverilog -g2012 -Wall -s tb_adsr_piano -o $compiled $rtl $tb
    $compileExit = $LASTEXITCODE
    $ErrorActionPreference = $savedPreference
    if ($compileExit -ne 0) { throw 'T009 compilation failed' }
    $ErrorActionPreference = 'Continue'
    & $vvp $compiled "+VELOCITY_ROM_PATH=$rom"
    $simExit = $LASTEXITCODE
    $ErrorActionPreference = $savedPreference
    if ($simExit -ne 0) { throw "T009 envelope boundary checks failed (exit=$simExit)" }
    $traceProgram = Join-Path $stage 'trace.vvp'
    $tracePath = Join-Path $stage 'trace.txt'
    $checker = Join-Path $repoRoot 'code\tb\audio\check_adsr_model_trace.py'
    $ErrorActionPreference = 'Continue'
    & $iverilog -g2012 -Wall -s tb_adsr_model_trace -o $traceProgram $rtl $tb
    $traceCompileExit = $LASTEXITCODE
    $ErrorActionPreference = $savedPreference
    if ($traceCompileExit -ne 0) { throw 'T009 trace TB compilation failed' }
    & $vvp $traceProgram "+VELOCITY_ROM_PATH=$rom" "+TRACE=$tracePath"
    if ($LASTEXITCODE -ne 0) { throw 'T009 trace simulation failed' }
    & python -X utf8 $checker $tracePath
    if ($LASTEXITCODE -ne 0) { throw 'T009 RTL versus M1 model mismatch' }

    # Missing ROM and deliberately damaged trace must return real failures.
    $ErrorActionPreference = 'Continue'
    & $vvp $compiled "+VELOCITY_ROM_PATH=$(Join-Path $stage 'missing.mem')" *> (Join-Path $stage 'missing_rom.log')
    $missingExit = $LASTEXITCODE
    $ErrorActionPreference = $savedPreference
    if ($missingExit -eq 0) { throw 'T009 missing-ROM negative test falsely passed' }
    # The first ROM entry alone is insufficient; reject truncated files too.
    $shortRom = Join-Path $stage 'short.mem'
    Get-Content -LiteralPath $rom -TotalCount 1 | Set-Content -LiteralPath $shortRom -Encoding Ascii
    $ErrorActionPreference = 'Continue'
    & $vvp $compiled "+VELOCITY_ROM_PATH=$shortRom" *> (Join-Path $stage 'short_rom.log')
    $shortExit = $LASTEXITCODE
    $ErrorActionPreference = $savedPreference
    if ($shortExit -eq 0) { throw 'T009 truncated-ROM negative test falsely passed' }
    $tamper = @"
from pathlib import Path
import sys
p = Path(sys.argv[1]); dest = Path(sys.argv[2])
lines = p.read_text(encoding='utf-8').splitlines()
for idx, line in enumerate(lines):
    if line.startswith('S '):
        parts = line.split(); parts[1] = str(int(parts[1]) + 100)
        lines[idx] = ' '.join(parts)
        break
else:
    raise ValueError('trace has no audio samples')
dest.write_text('\n'.join(lines) + '\n', encoding='utf-8', newline='\n')
"@
    $badTrace = Join-Path $stage 'bad_trace.txt'
    $tamper | python -X utf8 - $tracePath $badTrace
    if ($LASTEXITCODE -ne 0) { throw 'T009 negative trace preparation failed' }
    $ErrorActionPreference = 'Continue'
    & python -X utf8 $checker $badTrace *> (Join-Path $stage 'bad_trace.log')
    $mismatchExit = $LASTEXITCODE
    $ErrorActionPreference = $savedPreference
    if ($mismatchExit -eq 0) { throw 'T009 corrupt-trace negative test falsely passed' }
    Write-Host "T009 STAGE PASS: 73210 amplitude samples within provisional 2 Q15 LSB; missing ROM exit=$missingExit; truncated ROM exit=$shortExit; corrupt trace exit=$mismatchExit; state boundaries and low-velocity model policy pending M1"
    $global:LASTEXITCODE = 0
    $global:LASTEXITCODE = 0
} finally {
    $resolved = [IO.Path]::GetFullPath($stage)
    $tempRoot = [IO.Path]::GetFullPath($env:TEMP).TrimEnd('\') + '\'
    if (-not $resolved.StartsWith($tempRoot,[StringComparison]::OrdinalIgnoreCase)) {
        throw "Unsafe cleanup target: $resolved"
    }
    Remove-Item -LiteralPath $resolved -Recurse -Force -ErrorAction SilentlyContinue
}
