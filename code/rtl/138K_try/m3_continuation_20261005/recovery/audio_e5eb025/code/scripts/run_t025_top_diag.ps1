# Fixed-tone historical diagnostic; normal top acceptance uses STAT runner.
$ErrorActionPreference='Stop'
& python -X utf8 (Join-Path $PSScriptRoot 'run_t025_top_stat.py') --top tb_t025_top_diag --tb code/tb/board/tb_t025_top_diag.sv
if($LASTEXITCODE -ne 0){throw 'T025 fixed-tone diagnostic failed'}
Write-Host 'PASS T025 fixed-tone DIAG; this is not the normal performance STAT mode.'
