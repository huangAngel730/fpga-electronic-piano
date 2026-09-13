# Build the electronic_piano Gowin project from the command line.
#
# Usage:  .\build_electronic_piano.ps1 [-Flow synth|pnr|bitstream]
#
# Why a script instead of GUI steps: the project rules require every build to
# be reproducible from the command line (see code/AGENTS.md, build toolchain).
#
# IMPORTANT CONSTRAINTS (see code/AGENTS.md, script authoring rules):
#   - This file must stay pure ASCII. Windows PowerShell 5.1 decodes BOM-less
#     UTF-8 as GBK, which has already silently broken a check script once.
#   - Non-ASCII paths MUST NOT be passed to native executables, and gw_sh is
#     worse than truncated: its embedded Tcl interpreter replaces every CJK
#     character with "?" and then reports "project file ... does not exist".
#     A path like D:/.../<CJK>/build/x.gprj becomes D:/.../???/build/x.gprj.
#
# THE ASCII PATH PROBLEM AND ITS SOLUTION
# ---------------------------------------
# The repository lives under a CJK path (D:\17\<CJK>\<CJK>\<CJK>), and the
# directory that holds the project is itself CJK-named ("code" in Chinese).
# Two directory junctions give the tools a pure ASCII view of the same files:
#
#   D:\17\project_17\fpga_gowin       -> <repo root>
#   D:\17\project_17\fpga_gowin\code  -> <repo root>\<code dir>
#
# so gw_sh sees D:/17/project_17/fpga_gowin/code/build/electronic_piano.gprj.
# Nothing is copied: the junctions point at the real files, so a build always
# uses exactly the sources in the repository.
#
# Create them once, from an elevated shell:
#   cmd /c mklink /J "D:\17\project_17\fpga_gowin"      "<repo root>"
#   cmd /c mklink /J "D:\17\project_17\fpga_gowin\code" "<repo root>\<code dir>"
#
# The script verifies the junctions exist and fails with that hint if not.

param(
    [ValidateSet('synth', 'pnr', 'bitstream')]
    [string]$Flow = 'synth',
    [string]$AsciiRoot = 'D:\17\project_17\fpga_gowin'
)

$ErrorActionPreference = 'Continue'

# --- Paths ------------------------------------------------------------------
# The "code" directory is U+4EE3 U+7801; it is built from code points so this
# file stays pure ASCII while still resolving the real directory name.
$codeDir  = [char]0x4EE3 + [char]0x7801
# $PSScriptRoot is <repo>/<code>/scripts, so the repo root is two levels up.
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

$projectRel = "$codeDir\build\electronic_piano.gprj"

# Verify the ASCII mirror before doing any work: a missing junction is the
# single most likely reason for a confusing "project does not exist" later.
$asciiProject = Join-Path $AsciiRoot "code\build\electronic_piano.gprj"
if (-not (Test-Path $AsciiRoot)) {
    Write-Host "ERROR: ASCII mirror not found: $AsciiRoot"
    Write-Host '       Create it from an elevated shell:'
    Write-Host "         cmd /c mklink /J `"$AsciiRoot`" `"$repoRoot`""
    Write-Host "         cmd /c mklink /J `"$AsciiRoot\code`" `"$repoRoot\$codeDir`""
    exit 1
}
if (-not (Test-Path $asciiProject)) {
    Write-Host "ERROR: project not reachable through the ASCII mirror:"
    Write-Host "       $asciiProject"
    Write-Host "       The 'code' junction is probably missing:"
    Write-Host "         cmd /c mklink /J `"$AsciiRoot\code`" `"$repoRoot\$codeDir`""
    exit 1
}

$badChars = $asciiProject.ToCharArray() | Where-Object { [int]$_ -gt 127 }
if ($badChars) {
    Write-Host "ERROR: project path is not pure ASCII: $asciiProject"
    exit 1
}

Write-Host '=== electronic_piano build ==='
Write-Host "repo        : $repoRoot"
Write-Host "ascii mirror: $AsciiRoot"
Write-Host "flow        : $Flow"
Write-Host ''

# --- Locate the Gowin toolchain ---------------------------------------------
$gowinHome = $env:GOWIN_HOME
if (-not $gowinHome) {
    $gowinHome = 'D:\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64'
}
$gwSh = Join-Path $gowinHome 'IDE\bin\gw_sh.exe'
if (-not (Test-Path $gwSh)) {
    Write-Host "ERROR: gw_sh.exe not found at $gwSh"
    exit 1
}
Write-Host "tool        : $gwSh"
Write-Host ''

# --- Run the flow -----------------------------------------------------------
# gw_sh takes a Tcl script. The "run" command accepts exactly three process
# names, taken from gw_sh's own help text embedded in GWTE.dll:
#     'syn' for synthesis; 'pnr' for place&route; 'all' for all processes.
# "synth", "synthesize" and "place_route" are NOT valid and fail with
# "unknown process". The bitstream is produced by the pnr step; there is no
# separate bitstream process name.
#
# Paths inside the Tcl script use forward slashes and are wrapped in braces:
# a backslash would start a Tcl escape sequence and corrupt the path.
$gprjFwd = ($asciiProject -replace '\\', '/')
switch ($Flow) {
    'synth'     { $tcl = "open_project {$gprjFwd}`nrun syn`n" }
    'pnr'       { $tcl = "open_project {$gprjFwd}`nrun pnr`n" }
    'bitstream' { $tcl = "open_project {$gprjFwd}`nrun all`n" }
}

$tclFile = Join-Path $AsciiRoot "code\build\run_$Flow.tcl"
Set-Content -Path $tclFile -Value $tcl -Encoding ASCII

Write-Host "running $Flow ..."
& $gwSh $tclFile 2>&1 | ForEach-Object { Write-Host "  $_" }
$rc = $LASTEXITCODE
Write-Host ''
Write-Host "gw_sh exit code: $rc"

# --- Collect outputs --------------------------------------------------------
# gw_sh writes impl/ next to the project file, i.e. through the junction and
# therefore into the real repository at <repo>/<code>/build/impl.
$impl = Join-Path $repoRoot "$codeDir\build\impl"
if (Test-Path $impl) {
    Write-Host ''
    Write-Host 'outputs:'
    Get-ChildItem $impl -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in '.fs', '.rpt', '.log', '.json', '.bin', '.txt' } |
        Sort-Object FullName |
        ForEach-Object { Write-Host ("  {0,-58} {1,10} B" -f $_.Name, $_.Length) }
}

exit $rc
