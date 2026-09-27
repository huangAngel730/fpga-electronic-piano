# M2 read-only T010 review; current M1 defects deliberately return nonzero.
# Never modifies code/rtl/audio/voice_allocator_4.sv or the main build.
$ErrorActionPreference='Stop'
. (Join-Path $PSScriptRoot 'enter_fpga_env.ps1') | Out-Null
$repo=(Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
& python -X utf8 (Join-Path $repo 'code\tb\board\run_t010_allocator_review.py')
$rc=$LASTEXITCODE
if($rc -ne 0){Write-Host "T010 acceptance NOT passed: exit=$rc (see code/output/t010_allocator_review)"}
$global:LASTEXITCODE=$rc
exit $rc
