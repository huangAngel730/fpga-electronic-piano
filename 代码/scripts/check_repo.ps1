# Repository health check.
#
# IMPORTANT: Keep this file pure ASCII.
# The default `pwsh` on the team machines is Windows PowerShell 5.1 Desktop,
# which decodes BOM-less UTF-8 source files as ANSI/GBK. Non-ASCII literals
# therefore get corrupted into parse errors and the whole script dies before
# running a single check. That is exactly what happened here before 2026-09-12:
# the literal ".\<chinese>\scripts\..." was decoded into garbage, the quotes no
# longer matched, and every merge gate silently stopped executing.
# Chinese paths are now built at runtime from code points.
# See the "PowerShell script conventions" section in the code/ AGENTS.md.
#
# Second lesson: native tools cannot receive non-ASCII paths or a non-ASCII
# working directory. iverilog.exe fails with exit code 0xC0000142 (DLL init
# failure) when handed a path under a CJK directory. Sources are therefore
# staged into an ASCII temp directory before compiling.

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

# --- Chinese path fragments, built from code points (see header note) -------
# Do NOT write these words as literals anywhere in this file.
$codeDir   = [string]([char]0x4EE3 + [char]0x7801)                       # code
$prepDir   = [string]([char]0x51C6 + [char]0x5907)                       # preparation
$docDir    = [string]([char]0x6587 + [char]0x6863)                       # documents
$scriptDir = [string]([char]0x811A + [char]0x672C)                       # scripts
$entryDoc  = [string]([char]0x534F + [char]0x4F5C + [char]0x5165 + [char]0x53E3) + ".md"
$topicDir  = [string]([char]0x9009 + [char]0x9898)                       # topic selection
$teamDir   = [string]([char]0x56E2 + [char]0x961F)                       # team sharing pack

$prepRoot = Join-Path $repoRoot $prepDir
$outputRoot = Join-Path $repoRoot (Join-Path $codeDir "output\repo-check")
$failures = [System.Collections.Generic.List[string]]::new()

function Add-CheckResult {
    param(
        [string]$Name,
        [bool]$Passed,
        [string]$Detail
    )

    Write-Host ("  [{0}] {1}" -f $(if ($Passed) { "PASS" } else { "FAIL" }), $Name)
    if (-not $Passed -and $Detail) {
        Write-Host ("         {0}" -f $Detail) -ForegroundColor DarkYellow
    }

    if (-not $Passed) {
        $failures.Add("${Name}: ${Detail}")
    }
}

# Run a native command without letting its stderr abort the script.
# Windows PowerShell 5.1 turns native stderr into a terminating error when
# $ErrorActionPreference is "Stop", so warnings from git/iverilog would kill
# the check even on success. Success is judged by exit code, not by whether
# anything was written to stderr.
function Invoke-Native {
    param(
        [string]$FilePath,
        [string[]]$Arguments,
        [string]$WorkingDirectory
    )

    $previous = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    $pushed = $false
    if ($WorkingDirectory) {
        Push-Location -LiteralPath $WorkingDirectory
        $pushed = $true
    }
    try {
        $text = (& $FilePath @Arguments 2>&1 | Out-String)
        return [pscustomobject]@{
            ExitCode = $LASTEXITCODE
            Output   = $text.Trim()
        }
    } finally {
        if ($pushed) { Pop-Location }
        $ErrorActionPreference = $previous
    }
}

Write-Host "Repository check" -ForegroundColor Cyan
Write-Host "Root: $repoRoot"
Write-Host ""

Push-Location $repoRoot
try {
    # ---------------------------------------------------------------------
    # 1. Required entry-point documents
    # ---------------------------------------------------------------------
    $requiredPaths = @(
        "AGENTS.md",
        "README.md",
        ".gitattributes",
        ".editorconfig",
        (Join-Path $prepDir "README.md"),
        (Join-Path $prepDir (Join-Path $scriptDir "README.md")),
        (Join-Path $codeDir "README.md"),
        (Join-Path $codeDir (Join-Path "docs" "README.md")),
        (Join-Path $codeDir (Join-Path "docs" $entryDoc)),
        "legacy-prototype\AGENTS.md",
        "legacy-prototype\README.md"
    )

    $missingPaths = @($requiredPaths | Where-Object { -not (Test-Path -LiteralPath $_) })
    Add-CheckResult "Required paths present ($($requiredPaths.Count))" `
        ($missingPaths.Count -eq 0) ("missing: " + ($missingPaths -join ", "))

    # ---------------------------------------------------------------------
    # 2. Git whitespace
    # ---------------------------------------------------------------------
    $diff = Invoke-Native -FilePath "git" -Arguments @("diff", "--check")
    Add-CheckResult "Git whitespace clean" ($diff.ExitCode -eq 0) $diff.Output

    # ---------------------------------------------------------------------
    # 3. Forbidden tracked files
    # ---------------------------------------------------------------------
    $ls = Invoke-Native -FilePath "git" -Arguments @("ls-files")
    if ($ls.ExitCode -ne 0) {
        Add-CheckResult "Forbidden tracked files" $false ("git ls-files failed: " + $ls.Output)
    } else {
        $trackedFiles = @($ls.Output -split "`r?`n" | Where-Object { $_ })
        $forbiddenPatterns = @(
            "^\.tools/",
            "(^|/)output/",
            "\.(vcd|fst|fsdb|wlf|vvp|fs|bit|sof|pof)$",
            ("^" + $prepDir + "/" + $topicDir + "\.7z$"),
            ("^" + $prepDir + "/" + $teamDir)
        )
        $forbiddenTracked = @(
            $trackedFiles | Where-Object {
                $candidate = $_
                $forbiddenPatterns | Where-Object { $candidate -match $_ }
            }
        )
        Add-CheckResult "Forbidden tracked files" ($forbiddenTracked.Count -eq 0) `
            ($forbiddenTracked -join ", ")
    }

    # ---------------------------------------------------------------------
    # 4. Python syntax
    #
    # Uses ast.parse instead of `python -m py_compile`.
    # py_compile writes a __pycache__ directory next to the source, which
    # litters the repo and can be denied outright. ast.parse only reads.
    # ---------------------------------------------------------------------
    $pyScriptDir = Join-Path $prepRoot $scriptDir
    $pythonFiles = @(Get-ChildItem -LiteralPath $pyScriptDir -Filter "*.py" -File -ErrorAction SilentlyContinue)
    $pythonFailed = [System.Collections.Generic.List[string]]::new()
    $syntaxProbe =
        "import ast,sys,pathlib;" +
        "p=pathlib.Path(sys.argv[1]);" +
        "ast.parse(p.read_bytes().decode('utf-8'))"
    foreach ($file in $pythonFiles) {
        $r = Invoke-Native -FilePath "python" -Arguments @("-X", "utf8", "-c", $syntaxProbe, $file.FullName)
        if ($r.ExitCode -ne 0) {
            $pythonFailed.Add("$($file.Name): $(($r.Output -split "`r?`n")[-1])")
        }
    }
    Add-CheckResult "Python syntax ($($pythonFiles.Count) files)" `
        ($pythonFailed.Count -eq 0) ($pythonFailed -join "; ")

    # ---------------------------------------------------------------------
    # 5. DOCX structure
    # ---------------------------------------------------------------------
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $docxDir = Join-Path $prepRoot $docDir
    $docxFiles = @(Get-ChildItem -LiteralPath $docxDir -Filter "*.docx" -File -ErrorAction SilentlyContinue)
    $docxFailed = [System.Collections.Generic.List[string]]::new()
    foreach ($file in $docxFiles) {
        try {
            $archive = [System.IO.Compression.ZipFile]::OpenRead($file.FullName)
            try {
                if ($null -eq $archive.GetEntry("word/document.xml")) {
                    throw "word/document.xml missing"
                }
                foreach ($entry in $archive.Entries) {
                    $stream = $entry.Open()
                    try {
                        $buffer = New-Object byte[] 8192
                        while ($stream.Read($buffer, 0, $buffer.Length) -gt 0) {}
                    } finally {
                        $stream.Dispose()
                    }
                }
            } finally {
                $archive.Dispose()
            }
        } catch {
            $docxFailed.Add("$($file.Name): $($_.Exception.Message)")
        }
    }
    Add-CheckResult "DOCX structure ($($docxFiles.Count) files)" `
        ($docxFailed.Count -eq 0) ($docxFailed -join "; ")

    # ---------------------------------------------------------------------
    # 6. Legacy prototype RTL: compile and smoke run
    #
    # Sources are staged into an ASCII directory first. Passing a CJK path to
    # iverilog.exe makes it die with 0xC0000142 before it even parses a file.
    # ---------------------------------------------------------------------
    . (Join-Path $codeDir (Join-Path "scripts" "enter_fpga_env.ps1"))
    try {
        New-Item -ItemType Directory -Force -Path $outputRoot -ErrorAction Stop | Out-Null
    } catch {
        Write-Host ("         note: cannot create {0}; artifacts will not be archived" -f $outputRoot) -ForegroundColor DarkYellow
    }

    $stageDir = Join-Path ([System.IO.Path]::GetTempPath()) "repo_check_legacy"
    if (Test-Path -LiteralPath $stageDir) {
        Remove-Item -LiteralPath $stageDir -Recurse -Force
    }
    New-Item -ItemType Directory -Force -Path $stageDir | Out-Null

    $legacySources = @(
        "legacy-prototype\rtl\electronic_piano_top.v",
        "legacy-prototype\rtl\key_debounce.v",
        "legacy-prototype\rtl\tone_generator.v",
        "legacy-prototype\tb\tb_electronic_piano.v"
    )
    foreach ($source in $legacySources) {
        Copy-Item -LiteralPath $source -Destination $stageDir -Force
    }

    $vvpName = "legacy-prototype.vvp"
    $compile = Invoke-Native -FilePath "iverilog.exe" -WorkingDirectory $stageDir -Arguments @(
        "-g2012", "-Wall", "-s", "tb_electronic_piano", "-o", $vvpName,
        "electronic_piano_top.v", "key_debounce.v", "tone_generator.v", "tb_electronic_piano.v"
    )
    $compilePassed = ($compile.ExitCode -eq 0) -and (Test-Path -LiteralPath (Join-Path $stageDir $vvpName))
    Add-CheckResult "Legacy RTL compile" $compilePassed `
        $(if ($compilePassed) { $compile.Output } else { "exit=$($compile.ExitCode) $($compile.Output)" })

    if ($compilePassed) {
        # Note: vvp writes a VCD next to the .vvp file, so run it in the
        # ASCII stage dir and keep the repo clean.
        $sim = Invoke-Native -FilePath "vvp.exe" -WorkingDirectory $stageDir -Arguments @($vvpName)
        $simPassed = ($sim.ExitCode -eq 0) -and
                     ($sim.Output -notmatch "ERROR:") -and
                     ($sim.Output -match '\$finish called')
        $simDetail = if ($simPassed) {
            (($sim.Output -split "`r?`n" | Where-Object { $_ -match '\$finish called' }) -join " ")
        } else {
            "exit=$($sim.ExitCode) $($sim.Output)"
        }
        Add-CheckResult "Legacy RTL smoke" $simPassed $simDetail

        # Preserve the artifacts under the repo output dir for inspection.
        # This is best-effort: the working directory may be read-only under a
        # sandbox, and an inability to archive evidence must not turn an
        # otherwise passing check into a failure.
        $archived = [System.Collections.Generic.List[string]]::new()
        $archiveSkipped = $false
        foreach ($artifact in @($vvpName, "electronic_piano.vcd")) {
            $produced = Join-Path $stageDir $artifact
            if (-not (Test-Path -LiteralPath $produced)) { continue }
            try {
                Copy-Item -LiteralPath $produced -Destination $outputRoot -Force -ErrorAction Stop
                $archived.Add($artifact)
            } catch {
                $archiveSkipped = $true
            }
        }
        if ($archiveSkipped) {
            Write-Host ("         note: could not archive artifacts to {0} (read-only?); simulation result is still valid" -f $outputRoot) -ForegroundColor DarkYellow
        }
    }

    Remove-Item -LiteralPath $stageDir -Recurse -Force -ErrorAction SilentlyContinue
} finally {
    Pop-Location
}

Write-Host ""
if ($failures.Count -gt 0) {
    Write-Host "Repository check FAILED ($($failures.Count)):" -ForegroundColor Red
    $failures | ForEach-Object { Write-Host "- $_" -ForegroundColor Red }
    exit 1
}

Write-Host "All repository checks passed." -ForegroundColor Green
exit 0
