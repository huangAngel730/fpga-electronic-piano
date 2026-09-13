# Move the repository to a pure-ASCII path.
#
# WHY
# ---
# gw_sh embeds a Tcl interpreter that replaces every non-ASCII character in a
# path with "?". With the project at
#
#     D:\17\<CJK>\<CJK>\<CJK>\code\build\electronic_piano.gprj
#
# it reports:
#
#     project file D:/17/?????/?????????/???FPGA/code/build/....gprj does not exist
#
# Renaming the two top-level CJK directories was necessary but not sufficient:
# three CJK components remain in the repository root path itself. Moving the
# repository to an all-ASCII path removes the whole class of problem, for
# gw_sh and for every other tool in the flow (place & route, bitstream,
# Programmer).
#
# TARGET
# ------
#     D:\17\project_17\fpga_gowin
#
# A junction currently occupies that path, pointing back at the repository.
# It must be removed first, otherwise the move would target itself.
#
# WHAT IS DELIBERATELY NOT COPIED
# -------------------------------
# .tools/ (1.95 GB) holds downloaded vendor installers and the installers
# extracted from them. The working toolchain lives outside the repository, in
# D:\Gowin\, so .tools/ is a re-downloadable cache and is skipped. It is
# gitignored and untracked.
#
# WHY THIS SCRIPT EXISTS INSTEAD OF A PLAIN Move-Item
# ---------------------------------------------------
# Several things must happen in a specific order, and a mistake can destroy
# the repository:
#   1. remove the junction (rmdir, WITHOUT a trailing backslash, or the
#      target's contents are deleted instead of the link)
#   2. move the tree
#   3. fix the workspace registration that DSH reads, or the next session
#      cannot find the workspace
#   4. delete the now-stale old prep directory (the CJK one), which cannot be
#      removed while its files are owned by the sandbox account
#
# HOW TO RUN
# ----------
# Run from a normal PowerShell outside the DSH sandbox, as the repository
# owner is a stale sandbox account for some files. Elevation is not needed.
#
#     powershell -ExecutionPolicy Bypass -File .\code\scripts\move_repo_to_ascii.ps1
#
# Add -WhatIf to print the plan without touching anything.
#
# DO NOT cd INTO THE REPOSITORY FIRST
# -----------------------------------
# Windows refuses to rename a directory that any process has as its current
# working directory, and it reports the refusal as
#
#     Move-Item : Cannot move item because the item at <path> is in use.
#
# An earlier version of this script told the reader to cd into the repository,
# which guaranteed that failure: the calling shell held the directory open for
# the entire run. The script now changes its own location out of the tree
# before moving and changes back afterwards, and the wrapper command below
# starts in a neutral directory. Note that this only unbinds THIS process --
# any other process sitting in the tree (an editor, a terminal, another agent
# session) will still block the move, and the error message will not say which.
#
#     cd $env:USERPROFILE
#     powershell -ExecutionPolicy Bypass -File D:\...\code\scripts\move_repo_to_ascii.ps1
#
# WHEN THE MOVE FAILS AS "IN USE"
# -------------------------------
# Nothing is damaged; the script stops before changing anything. To find the
# holders, close whatever is parked in the tree and retry. If a DSH agent
# session is holding it, create the file this script watches for and that
# session will step out of the directory:
#
#     New-Item -ItemType File D:\17\project_17\MOVE_READY
#
# -WaitForRelease waits for that file before moving, so the session that owns
# the repository can be told to let go without racing the move.

param(
    [switch]$WhatIf,
    [switch]$WaitForRelease,
    [int]$ReleaseTimeoutSec = 600
)

$ErrorActionPreference = 'Stop'

# --- Configuration -----------------------------------------------------------
$target = 'D:\17\project_17\fpga_gowin'
$releaseFlag = 'D:\17\project_17\MOVE_READY'

# Build CJK names from code points so this file stays pure ASCII.
$codeCjk = [char]0x4EE3 + [char]0x7801   # "code"
$prepCjk = [char]0x51C6 + [char]0x5907   # "preparation"

if (-not $PSScriptRoot) {
    throw 'cannot determine script directory; run this with -File'
}
# <repo>\code\scripts -> <repo>
$source = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Say($m) { Write-Host $m }
function Step($m) { Write-Host ''; Write-Host "=== $m ===" }

Say "source : $source"
Say "target : $target"
if ($WhatIf) { Say 'MODE   : -WhatIf (nothing will be changed)' }

# --- Preconditions -----------------------------------------------------------
Step 'preconditions'

if (-not (Test-Path -LiteralPath (Join-Path $source '.git'))) {
    throw "source is not a repository root (no .git): $source"
}
if ($source -eq $target) {
    throw 'source and target are the same path'
}
foreach ($bad in $source.Substring(3).Split('\')) {
    if (($bad.ToCharArray() | Where-Object { [int]$_ -gt 127 }).Count -gt 0) {
        Say "  source has a CJK component (expected): $bad"
    }
}
$targetNonAscii = ($target.ToCharArray() | Where-Object { [int]$_ -gt 127 }).Count
if ($targetNonAscii -gt 0) {
    throw "target path is not pure ASCII: $target"
}
Say '  source is a repository root'
Say '  target path is pure ASCII'

# Confirm the working tree has no uncommitted changes, so a failed move is
# easy to reason about and to undo.
Push-Location $source
$dirty = & git status --porcelain
Pop-Location
$dirtyTracked = $dirty | Where-Object { $_ -notmatch '^\?\?' }
if ($dirtyTracked) {
    Say '  WARNING: tracked files have uncommitted changes:'
    $dirtyTracked | Select-Object -First 10 | ForEach-Object { Say "    $_" }
    throw 'commit or stash before moving the repository'
}
Say '  working tree is clean'

# --- Remove the junction -----------------------------------------------------
Step "remove the junction at $target"
$tgtItem = Get-Item -LiteralPath $target -Force -ErrorAction SilentlyContinue
if ($tgtItem) {
    if ($tgtItem.LinkType -eq 'Junction') {
        Say "  it is a Junction -> $($tgtItem.Target)"
        if (-not $WhatIf) {
            # rmdir with NO trailing backslash: a trailing backslash makes
            # cmd follow the link and delete the target's contents instead.
            & cmd /c "rmdir `"$target`""
            if (Test-Path -LiteralPath $target) { throw 'junction removal failed' }
        }
        Say '  removed'
    }
    elseif ($tgtItem.PSIsContainer) {
        $n = (Get-ChildItem -LiteralPath $target -Force).Count
        if ($n -ne 0) {
            throw "target exists, is not a junction, and is not empty: $target"
        }
        Say '  an empty directory is already there; will reuse it'
    }
    else {
        throw "target exists and is a file: $target"
    }
}
else {
    Say '  nothing there'
}

# --- Move --------------------------------------------------------------------
Step 'move the repository'

# Unbind this process from the tree. Windows will not rename a directory that
# is any process's current working directory, and this script was itself
# started from inside the tree in the previous attempt.
$neutral = $env:USERPROFILE
if (-not $neutral -or -not (Test-Path -LiteralPath $neutral)) {
    $neutral = 'C:\'
}
Set-Location -LiteralPath $neutral -ErrorAction Stop
Say "  this process moved its location to: $neutral"

# Wait for other holders to step out. Polling rather than prompting, because
# the typical holder is an agent session or an editor, not a person at this
# console.
if ($WaitForRelease -and -not $WhatIf) {
    Say "  waiting for $releaseFlag (up to $ReleaseTimeoutSec s)"
    $deadline = (Get-Date).AddSeconds($ReleaseTimeoutSec)
    while (-not (Test-Path -LiteralPath $releaseFlag)) {
        if ((Get-Date) -gt $deadline) {
            throw "timed out waiting for $releaseFlag; close whatever is in the repository and retry"
        }
        Start-Sleep -Milliseconds 500
    }
    Say '  release flag seen; proceeding'
}

# Probe writability before moving, so a lock produces a clear message instead
# of a bare "item is in use". Creating and deleting a file exercises the same
# access the rename needs.
if (-not $WhatIf) {
    $probe = Join-Path $source ('.move_probe_' + [Guid]::NewGuid().ToString('N').Substring(0, 8))
    try {
        [IO.File]::WriteAllText($probe, 'x')
        Remove-Item -LiteralPath $probe -Force
        Say '  source directory is writable'
    }
    catch {
        throw "cannot write inside $source -- something still holds it: $($_.Exception.Message)"
    }
}

if (-not $WhatIf) {
    try {
        Move-Item -LiteralPath $source -Destination $target -ErrorAction Stop
    }
    catch {
        Write-Host ''
        Write-Host '  MOVE FAILED -- nothing was changed.'
        Write-Host "  $($_.Exception.Message)"
        Write-Host ''
        Write-Host '  Windows reports a directory-in-use refusal without naming the'
        Write-Host '  process. Close any editor, terminal or agent session whose'
        Write-Host '  working directory is inside the repository and retry.'
        throw 'move failed'
    }
    Say "  moved"
}
Say "  $source"
Say "    -> $target"

$newRoot = $target

# --- Verify ------------------------------------------------------------------
Step 'verify'
foreach ($d in @('.git', 'code', 'prep')) {
    $p = Join-Path $newRoot $d
    $state = 'MISSING'
    if (Test-Path -LiteralPath $p) { $state = 'OK' }
    Say ("  {0,-6} {1}" -f $d, $state)
}
$nonAscii = ($newRoot.ToCharArray() | Where-Object { [int]$_ -gt 127 }).Count
Say "  non-ASCII characters in the new root path: $nonAscii"
if ($nonAscii -ne 0) { throw 'new root is not pure ASCII' }

Push-Location $newRoot
$after = & git status --porcelain
Pop-Location
Say "  git status entries after the move: $(($after | Measure-Object).Count)"

# --- Remove the stale CJK directory -----------------------------------------
Step "remove the stale $prepCjk directory"
$stale = Join-Path $newRoot $prepCjk
if (Test-Path -LiteralPath $stale) {
    Say '  it still exists; its files may be owned by a stale sandbox account.'
    Say '  attempting removal...'
    if (-not $WhatIf) {
        try {
            Remove-Item -LiteralPath $stale -Recurse -Force -ErrorAction Stop
            Say '  removed'
        }
        catch {
            Say "  FAILED: $($_.Exception.Message)"
            Say ''
            Say '  Fix the ownership from an elevated PowerShell, then delete it:'
            Say "    takeown /F `"$stale`" /A /R /D Y"
            Say "    icacls `"$stale`" /grant `"Angel17:(OI)(CI)(F)`" /T /C /Q"
            Say "    icacls `"$stale`" /grant `"CodexSandboxUsers:(OI)(CI)(M)`" /T /C /Q"
            Say "    Remove-Item -LiteralPath `"$stale`" -Recurse -Force"
        }
    }
}
else {
    Say '  already gone'
}

# --- Fix the DSH workspace registration --------------------------------------
# DSH stores the workspace path in JSON, where every backslash is doubled.
# Match and replace on the escaped form: matching the raw path never succeeds,
# because the file contains "D:\\17\\..." rather than "D:\17\...". The first
# version of this script compared the unescaped path and therefore always
# concluded that the workspace was not registered, silently skipping the one
# step whose absence breaks the next session.
Step 'update the DSH workspace registration'
$wsFile = Join-Path $env:USERPROFILE '.dsh\storages\workspace.json'
$srcEsc = $source.Replace('\', '\\')
$tgtEsc = $target.Replace('\', '\\')
if (Test-Path -LiteralPath $wsFile) {
    $json = Get-Content -LiteralPath $wsFile -Raw -Encoding UTF8
    $found = $json.Contains($srcEsc)
    Say "  registered: $found"
    if ($found) {
        if (-not $WhatIf) {
            $backup = "$wsFile.bak"
            Copy-Item -LiteralPath $wsFile -Destination $backup -Force
            $json = $json.Replace($srcEsc, $tgtEsc)
            [IO.File]::WriteAllText($wsFile, $json, [Text.UTF8Encoding]::new($false))
            Say "  updated (backup at $backup)"
        }
        else {
            Say '  would update'
        }
    }
    else {
        Say '  the old path is not registered; nothing to do'
    }
}
else {
    Say "  not found: $wsFile"
}

# --- Check the hardcoded old paths -------------------------------------------
# Search the tracked files for the CJK components of the OLD root path.
#
# The components are taken from $source itself rather than written as literals
# or built from hand-copied code points. Both alternatives are unsafe here:
#   - a CJK literal makes this .ps1 non-ASCII, and Windows PowerShell 5.1 then
#     decodes the whole file as GBK and fails to parse it;
#   - hand-copied code points are silently wrong when the copy is wrong. The
#     first version of this script used 0x5D4E for the first character of the
#     old leaf directory and produced a search string that could never match,
#     so the check would have reported "none" no matter what the files said.
# Deriving the strings from the live path removes both failure modes.
Step 'files that still mention the old path'
$oldParts = @()
foreach ($seg in $source.Substring(3).Split('\')) {
    if (($seg.ToCharArray() | Where-Object { [int]$_ -gt 127 }).Count -gt 0) {
        $oldParts += $seg
    }
}
Say "  looking for $($oldParts.Count) CJK component(s) of the old root"
Push-Location $newRoot
$tracked = & git -c core.quotepath=false ls-files
Pop-Location
$hits = @()
foreach ($f in $tracked) {
    $p = Join-Path $newRoot $f
    if (-not (Test-Path -LiteralPath $p -PathType Leaf)) { continue }
    try {
        $c = Get-Content -LiteralPath $p -Raw -Encoding UTF8 -ErrorAction SilentlyContinue
    }
    catch { continue }
    if (-not $c) { continue }
    foreach ($pat in $oldParts) {
        if ($c -match [regex]::Escape($pat)) { $hits += $f; break }
    }
}
if ($hits.Count -eq 0) {
    Say '  none'
}
else {
    Say "  $($hits.Count) file(s) need updating:"
    $hits | ForEach-Object { Say "    $_" }
}

Step 'done'
Say "repository is now at: $newRoot"
Say ''
Say 'Next: reopen the workspace in DSH at the new path.'
