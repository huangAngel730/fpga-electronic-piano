# T010 canonical self-check for the current four-slot allocator.
# Uses the independent external-port six-case review plus Python recency oracle.
# ASCII only for PowerShell 5.1. Failures propagate their exit status.
$ErrorActionPreference = 'Stop'
$script = Join-Path $PSScriptRoot 'run_t010_allocator_review.ps1'
if (-not (Test-Path -LiteralPath $script -PathType Leaf)) { throw "Missing T010 gate: $script" }
& $script
exit $LASTEXITCODE
