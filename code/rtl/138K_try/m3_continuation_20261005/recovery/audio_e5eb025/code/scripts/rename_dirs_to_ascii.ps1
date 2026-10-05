# Rename the two CJK top-level directories to ASCII names.
#
# WHY THIS IS NOT DONE BY THE AGENT
# ---------------------------------
# The DSH sandbox denies directory renames even in its widest mode: a rename
# returns "Access denied" from git mv, [IO.Directory]::Move, and cmd move,
# although the ACL on the parent grants DeleteSubDirectoriesAndFiles and a
# plain FILE rename in the same tree succeeds. The block is imposed by the
# sandbox, not by Windows permissions, so it must be run from a shell that the
# sandbox does not wrap.
#
# WHY RENAME AT ALL
# -----------------
# gw_sh's embedded Tcl interpreter maps every non-ASCII character in a project
# path to "?", so it cannot open a project stored under a CJK directory. The
# same class of failure is likely in the rest of the Gowin flow (place & route,
# bitstream, Programmer), so removing CJK from the directory names fixes the
# whole toolchain rather than working around one command.
#
# WHAT THIS SCRIPT DOES
# ---------------------
#   1. verifies the working tree is clean (refuses otherwise: a rename on top
#      of uncommitted work makes the failure hard to reason about)
#   2. renames <repo>/<CJK> -> <repo>/code  and  <repo>/<CJK> -> <repo>/prep
#      using git mv, so the index records a rename and history stays traceable
#   3. prints a summary
#
# It does NOT rewrite file contents. Text references are updated separately by
# the agent, because a blind search/replace would also hit the ordinary Chinese
# word for "code" wherever it appears as prose.
#
# HOW TO RUN
# ----------
# Open an elevated PowerShell (Run as administrator is NOT required; a normal
# PowerShell outside the DSH sandbox is enough) and run:
#
#     powershell -ExecutionPolicy Bypass -File .\rename_dirs_to_ascii.ps1
#
# from the repository root. To undo, run with -Undo.

param(
    [switch]$Undo
)

$ErrorActionPreference = 'Stop'

# Build the CJK names from code points so this file stays pure ASCII.
#   U+4EE3 U+7801 = "code" in Chinese
#   U+51C6 U+5907 = "preparation" in Chinese
$codeCjk = [char]0x4EE3 + [char]0x7801
$prepCjk = [char]0x51C6 + [char]0x5907

# $PSScriptRoot is always an absolute path, including under "powershell -File".
# $MyInvocation.MyCommand.Path is NOT: under -File it can be the same relative
# path the caller typed, so two Split-Path calls then stop one level short.
# That bug already bit once (the script reported the repo as <root>\<code>).
if (-not $PSScriptRoot) {
    throw 'cannot determine script directory; run this with -File, not by pasting'
}
$repo = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location -LiteralPath $repo

Write-Host "repo: $repo"
Write-Host ''

# --- Guard: we really are at the repository root -----------------------------
# The first version of this script walked up one level too few and cheerfully
# reported "<root>\<code>" as the repo. Fail loudly instead of skipping.
if (-not (Test-Path -LiteralPath (Join-Path $repo '.git'))) {
    throw "not a repository root (no .git): $repo"
}
foreach ($d in @($codeCjk, $prepCjk)) {
    if (-not (Test-Path -LiteralPath (Join-Path $repo $d))) {
        throw "expected top-level directory not found: $d (under $repo)"
    }
}

# --- Guard: a clean (or at least rename-only) tree ---------------------------
# Untracked build products are tolerated; tracked modifications are not,
# because git mv on top of a dirty tree makes a failed rename hard to undo.
$status = & git status --porcelain
if ($LASTEXITCODE -ne 0) {
    throw 'not a git repository, or git failed'
}
$tracked = $status | Where-Object { $_ -notmatch '^\?\?' }
if ($tracked) {
    Write-Host 'WARNING: tracked files have uncommitted changes:'
    $tracked | ForEach-Object { Write-Host "  $_" }
    Write-Host ''
    Write-Host 'Commit or stash first, then re-run. Aborting.'
    exit 1
}

# --- Rename ------------------------------------------------------------------
$pairs = if ($Undo) {
    @(
        @{ From = 'code'; To = $codeCjk },
        @{ From = 'prep'; To = $prepCjk }
    )
} else {
    @(
        @{ From = $codeCjk; To = 'code' },
        @{ From = $prepCjk; To = 'prep' }
    )
}

foreach ($p in $pairs) {
    if (-not (Test-Path -LiteralPath $p.From)) {
        Write-Host "SKIP: $($p.From) does not exist"
        continue
    }
    if (Test-Path -LiteralPath $p.To) {
        Write-Host "SKIP: $($p.To) already exists"
        continue
    }
    Write-Host "renaming $($p.From) -> $($p.To)"
    & git mv -- $p.From $p.To
    if ($LASTEXITCODE -ne 0) {
        throw "git mv failed for $($p.From)"
    }
}

Write-Host ''
Write-Host '=== result ==='
Get-ChildItem -Directory -Force | ForEach-Object { Write-Host "  $($_.Name)" }
Write-Host ''
Write-Host 'next: rewrite the text references, then run the repo checks.'
