# Build a Gowin project in this repository from the command line.
#
# Usage:  .\build_electronic_piano.ps1 [-Flow synth|pnr|bitstream]
#         .\build_electronic_piano.ps1 -Flow bitstream -Project probe\uart_rx_probe
#
# -Project is a path under code/build/ without the .gprj extension. The default
# is the main design, so every existing invocation keeps working unchanged.
# The diagnostic UART-RX probe project lives in its own subdirectory on purpose:
# Gowin writes impl/ next to the .gprj, and some of those intermediate files
# (cmd.do, device.cfg) are not prefixed with the project name, so two projects
# sharing code/build/impl/ would overwrite each other's scratch files.
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
# HISTORY: two directory junctions used to give the tools an ASCII view of a
# CJK repository. That is gone. The repository, every directory inside it, and
# the paths handed to the toolchain are now genuinely ASCII, so no mirror is
# needed. This script now derives everything from its own location.
#
# The Verilog language option matters: the sources are SystemVerilog, and the
# synthesizer defaults to Verilog 2001, which produces
#
#     ERROR (EX3863): Syntax error near 'unsigned'
#     ERROR (EX2656): Verilog 2001 keyword 'unsigned' used in incorrect context
#     ERROR (EX3444): 'package' is an unknown type
#
# The option name and value are both easy to get wrong, and neither the GUI
# option table nor the documentation gives the command-line spelling directly.
# What is actually true, established by probing gw_sh:
#
#   - The option is named -verilog_std, NOT -vlog_std.
#     IDE\data\config\synthesisoptions.xml (SYN17) lists the command as
#     "set_option -vlog_std sysv", but that string is the GUI-side command:
#     the token vlog_std appears only in GaoUtils.dll and that XML, never in
#     gw_sh.exe. Passing it to gw_sh fails with
#         unknown option: -vlog_std
#     -verilog_std is accepted, which confirms the name.
#
#   - The value is sysv2017. "sysv" is rejected with
#         unknown verilog language value
#     despite being what the GUI XML and the GUI label ("System Verilog")
#     suggest. Accepted values are v2001 and sysv2017; every other spelling
#     tried (... sysv, sv, sv2017, systemverilog, verilog2001, ...) is
#     rejected. v2001 is what you get by default anyway, i.e. the broken case.
#
# So the correct line is "set_option -verilog_std sysv2017". It is written into
# the generated Tcl rather than passed ad hoc so that the command-line build
# stays reproducible.
#
# This file is pure ASCII on purpose: Windows PowerShell 5.1 decodes BOM-less
# UTF-8 as GBK/ANSI, which has already silently broken a script in this repo.

param(
    [ValidateSet('synth', 'pnr', 'bitstream')]
    [string]$Flow = 'synth',

    # Project path under code/build/, without the .gprj extension.
    # Use 'probe\uart_rx_probe' for the UART-RX pin diagnostic.
    [string]$Project = 'electronic_piano'
)

$ErrorActionPreference = 'Continue'

# --- Paths ------------------------------------------------------------------
# Top-level directory names are ASCII since the rename (code, prep).
$codeDir = 'code'
# $PSScriptRoot is <repo>/code/scripts, so the repo root is two levels up.
$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$isMainProject = $Project -eq 'electronic_piano'
$project = Join-Path $repoRoot "$codeDir\build\$Project.gprj"
$projectDir = Split-Path -Parent $project

if (-not (Test-Path -LiteralPath $project)) {
    Write-Host "ERROR: project file not found: $project"
    exit 1
}

# Guard the property this script now depends on. If someone clones the
# repository into a path containing CJK characters, gw_sh fails later with a
# misleading "does not exist" message; say so here instead.
$badChars = $project.ToCharArray() | Where-Object { [int]$_ -gt 127 }
if ($badChars) {
    Write-Host "ERROR: project path is not pure ASCII: $project"
    Write-Host '       gw_sh replaces non-ASCII characters with "?" and then'
    Write-Host '       reports the project as missing. Move the repository to an'
    Write-Host '       all-ASCII path; see code/docs/ (development environment).'
    exit 1
}

Write-Host '=== Gowin build ==='
Write-Host "repo   : $repoRoot"
Write-Host "project: $project"
Write-Host "flow   : $Flow"
Write-Host ''

# --- Locate the Gowin toolchain ---------------------------------------------
$gowinHome = $env:GOWIN_HOME
if (-not $gowinHome) {
    $gowinHome = 'D:\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64'
}
$gwSh = Join-Path $gowinHome 'IDE\bin\gw_sh.exe'
if (-not (Test-Path -LiteralPath $gwSh)) {
    Write-Host "ERROR: gw_sh.exe not found at $gwSh"
    Write-Host '       Set GOWIN_HOME if the toolchain lives elsewhere.'
    exit 1
}
Write-Host "tool   : $gwSh"
Write-Host ''

# Main build: mirror project into ignored directory and use explicit ROM paths.
# Gowin's parser resolves readmemh relative to its process, not reliably to GPRJ.
if ($isMainProject) {
    $formalProject = $project
    $stagedDir = Join-Path $repoRoot 'code/build/staged_formal'
    New-Item -ItemType Directory -Force -Path $stagedDir | Out-Null
    $text = [IO.File]::ReadAllText($formalProject)
    [xml]$doc = $text.Replace('<?xml version="1"','<?xml version="1.0"')
    foreach ($entry in $doc.Project.FileList.File) {
        $inputFile = [IO.Path]::GetFullPath((Join-Path $projectDir $entry.path))
        if ($entry.type -eq 'file.verilog') {
            $sourceText = [IO.File]::ReadAllText($inputFile)
            # The agreed sustain port header lives in board/, not input/.
            $portHeader = Join-Path $repoRoot 'code/rtl/board/sustain_controller_ports.svh'
            $sourceText = $sourceText.Replace('`include "sustain_controller_ports.svh"',
                ('`include "' + $portHeader.Replace('\','/') + '"'))
            foreach ($name in @('sine_1024_8192.mem','sine_1024_32767.mem','velocity_gain_rom.mem','piano_band_4x256_8191.mem')) {
                $rom = Join-Path $repoRoot ('code/model/generated/wavetables/' + $name)
                if (-not (Test-Path -LiteralPath $rom)) { throw "Missing ROM: $rom" }
                $sourceText = $sourceText.Replace('model/generated/wavetables/' + $name,$rom.Replace('\','/'))
            }
            if ($sourceText -ne [IO.File]::ReadAllText($inputFile)) {
                $generated = Join-Path $stagedDir ([IO.Path]::GetFileName($inputFile))
                [IO.File]::WriteAllText($generated,$sourceText,[Text.UTF8Encoding]::new($false))
                $inputFile = $generated
            }
        }
        $entry.path = $inputFile.Replace('\','/')
    }
    $projectDir = $stagedDir
    $project = Join-Path $stagedDir 'electronic_piano.gprj'
    $doc.Save($project)
}

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
$gprjFwd = ($project -replace '\\', '/')
$script = @(
    "cd {$($projectDir.Replace('\','/'))}"
    "open_project {$gprjFwd}"
    'set_option -verilog_std sysv2017'
)
switch ($Flow) {
    'synth'     { $script += 'run syn' }
    'pnr'       { $script += 'run pnr' }
    'bitstream' { $script += 'run all' }
}

$tclFile = Join-Path $projectDir "run_$Flow.tcl"
# Write with an explicit UTF-8 encoding and no BOM: gw_sh's Tcl reads the file
# as bytes, and a BOM would become part of the first command.
[IO.File]::WriteAllLines($tclFile, $script, [Text.UTF8Encoding]::new($false))

Write-Host "running $Flow ..."
Write-Host "  tcl: $tclFile"
$buildOutput = & $gwSh $tclFile 2>&1
$buildOutput | ForEach-Object { Write-Host "  $_" }
$rc = $LASTEXITCODE
if (($buildOutput -join "`n") -match 'EX3988|ERROR\s*\(') { $rc = 1; Write-Host 'ERROR: ROM/parser failure cannot be accepted as a successful build' }
Write-Host ''
Write-Host "gw_sh exit code: $rc"

# --- Collect outputs --------------------------------------------------------
# gw_sh writes impl/ next to the project file.
$impl = Join-Path $projectDir 'impl'
if (Test-Path -LiteralPath $impl) {
    Write-Host ''
    Write-Host 'outputs:'
    Get-ChildItem $impl -Recurse -File -ErrorAction SilentlyContinue |
        Where-Object { $_.Extension -in '.fs', '.rpt', '.log', '.json', '.bin', '.txt' } |
        Sort-Object FullName |
        ForEach-Object { Write-Host ('  {0,-58} {1,10} B' -f $_.Name, $_.Length) }
}

if ($isMainProject -and $Flow -ne 'synth' -and $rc -eq 0) {
    & python -X utf8 (Join-Path $PSScriptRoot 'check_t024_formal_report.py') $projectDir
    if ($LASTEXITCODE -ne 0) { $rc = 1 }
}
exit $rc
