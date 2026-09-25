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
# failure) when handed a path under a CJK directory. This script no longer
# compiles anything itself -- its own legacy compile was removed on 2026-09-15
# -- so the only remaining compile is delegated to run_t007_sim.ps1, which does
# its own ASCII staging.

$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path

# --- Directory and file names ------------------------------------------------
# The two TOP-LEVEL directory names are ASCII since the rename:
#   old CJK "code" dir -> code     old CJK "prep" dir -> prep
# They are written as plain literals now. Building them from code points was a
# workaround for Windows PowerShell 5.1 decoding this file as GBK, which only
# applied while the names were non-ASCII and had to appear in a pure-ASCII
# source file.
#
# The names below this level are still Chinese and still built from code
# points, because those directories were NOT renamed. Do not write those words
# as literals anywhere in this file.
$codeDir   = "code"
$prepDir   = "prep"
$docDir    = [string]([char]0x6587 + [char]0x6863)                       # documents
$scriptDir = [string]([char]0x811A + [char]0x672C)                       # scripts
$entryDoc  = [string]([char]0x534F + [char]0x4F5C + [char]0x5165 + [char]0x53E3) + ".md"
$topicDir  = [string]([char]0x9009 + [char]0x9898)                       # topic selection
$teamDir   = [string]([char]0x56E2 + [char]0x961F)                       # team sharing pack

$prepRoot = Join-Path $repoRoot $prepDir
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
        (Join-Path $codeDir "constraints\electronic_piano.cst"),
        # T007 top-level bring-up: RTL, testbench and regression script.
        # These are the minimum set needed to regenerate a bitstream and to
        # re-run the top-level self-check, so they are gated by this script.
        (Join-Path $codeDir "rtl\board\electronic_piano_top.sv"),
        (Join-Path $codeDir "tb\board\tb_electronic_piano_top.sv"),
        # T021 (2026-09-15): M3's button debouncer replaced the M2 placeholder and
        # is now instantiated by the top level, so gate it like the top level to
        # stop the build from silently losing the file.
        # 2026-09-15: rtl/input/ was reorganised to one subdirectory per module,
        # so the debouncer path gained a directory level.
        (Join-Path $codeDir "rtl\input\button_debouncer\button_debouncer.sv"),
        (Join-Path $codeDir "tb\input\tb_button_debouncer.sv"),
        # T022 / D022 (2026-09-15): M3's button_event_converter replaced the M2
        # placeholder key_event_source, and audio_defs_pkg became the single
        # definition site of performance_event_t (perf_event_pkg.sv deleted).
        # Gate all three so a future cleanup cannot silently drop the event path.
        (Join-Path $codeDir "rtl\input\button_event_converter\button_event_converter.sv"),
        (Join-Path $codeDir "tb\input\tb_button_event_converter.sv"),
        (Join-Path $codeDir "rtl\common\audio_defs_pkg.sv"),
        (Join-Path $codeDir (Join-Path "scripts" "run_t007_sim.ps1")),
        # External board-documentation digests kept read-only under
        # docs/reference. The directory name is ASCII, but the digests carry a
        # CJK suffix; build it from code points (see the header note).
        (Join-Path $codeDir "docs\reference\README.md"),
        (Join-Path $codeDir (Join-Path "docs\reference" ("BOARD_CONTEXT_{0}.md" -f `
            [string]([char]0x5916 + [char]0x90E8 + [char]0x6574 + [char]0x7406 + [char]0x7A3F)))),
        (Join-Path $codeDir (Join-Path "docs\reference" ("DOC_INDEX_{0}.md" -f `
            [string]([char]0x5916 + [char]0x90E8 + [char]0x6574 + [char]0x7406 + [char]0x7A3F)))),
        (Join-Path $codeDir (Join-Path "scripts" "verify_reference_digests.py"))
        # The two legacy-prototype/ entries were dropped on 2026-09-15 when that
        # archive was deleted (see the verification log, V0041).
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
    #
    # Three roots are scanned (recursively):
    #   prep/<scripts>/  - Word report generators
    #   code/scripts/    - build, analysis and data generation helpers
    #   code/model/      - Python golden reference model and its unit tests
    # code/output/ is deliberately NOT scanned: it holds throwaway scratch
    # scripts, not deliverables. Before 2026-09-15 only prep/<scripts>/ was
    # scanned, so no file under code/ was covered at all.
    # ---------------------------------------------------------------------
    $pyScriptDir = Join-Path $prepRoot $scriptDir
    $pyRoots = @(
        $pyScriptDir,
        (Join-Path $repoRoot (Join-Path $codeDir "scripts")),
        (Join-Path $repoRoot (Join-Path $codeDir "model"))
    )
    $pythonFiles = @(
        foreach ($root in $pyRoots) {
            Get-ChildItem -LiteralPath $root -Filter "*.py" -File -Recurse -ErrorAction SilentlyContinue
        }
    )
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
    # 5. Pin constraints match the official reference
    #
    # electronic_piano.cst is excerpted from the official Sipeed reference CST.
    # A wrong pin here is only caught after a wasted board session, so verify
    # every pin/IO_TYPE/PULL_MODE/BANK_VCCIO against the reference on each run.
    # Names differ on purpose (HP_BCK -> i2s_bclk), so the mapping is explicit.
    # ---------------------------------------------------------------------
    $projCst = Join-Path $codeDir "constraints\electronic_piano.cst"
    $refCst = Join-Path $codeDir "constraints\tang_mega_60k_reference.cst"
    if ((Test-Path -LiteralPath $projCst) -and (Test-Path -LiteralPath $refCst)) {
        # local name, official name, pin
        $pinMap = @(
            @("sys_clk",   "sys_clk",   "V22"),
            @("sys_rst_n", "sys_rst_n", "AA13"),
            @("i2s_bclk",  "HP_BCK",    "Y17"),
            @("i2s_lrck",  "HP_WS",     "AB17"),
            @("i2s_din",   "HP_DIN",    "AA16"),
            @("pa_en",     "PA_EN",     "AB16"),
            @("uart_tx",   "txp",       "U15"),
            @("midi_rx",   "LEDs[2]",   "R17")
        )
        # Both CST files carry Chinese comments. Get-Content WITHOUT -Encoding
        # reads them as ANSI/GBK on Windows PowerShell 5.1, which mis-decodes
        # the multibyte sequences and can swallow newlines, merging a comment
        # with the following IO_LOC line. Anchored patterns then stop matching.
        # Always pass -Encoding UTF8 for these files.
        $projLines = @(Get-Content -LiteralPath $projCst -Encoding UTF8)
        $refLines = @(Get-Content -LiteralPath $refCst -Encoding UTF8)
        $pinFailed = [System.Collections.Generic.List[string]]::new()
        foreach ($entry in $pinMap) {
            $localName = $entry[0]
            $officialName = $entry[1]
            $pin = $entry[2]

            $projLoc = @($projLines | Where-Object { $_ -match ("^\s*IO_LOC\s+`"" + $localName + "`"") })
            $refLoc = @($refLines | Where-Object {
                $_ -match ("^\s*IO_LOC\s+`"" + [regex]::Escape($officialName) + "`"")
            })
            $projPort = @($projLines | Where-Object { $_ -match ("^\s*IO_PORT\s+`"" + $localName + "`"") })

            if ($projLoc.Count -ne 1) {
                $pinFailed.Add("${localName}: expected 1 IO_LOC, found $($projLoc.Count)")
                continue
            }
            if ($refLoc.Count -ne 1) {
                $pinFailed.Add("${localName}: reference has $($refLoc.Count) IO_LOC for $officialName")
                continue
            }
            if ($projLoc[0] -notmatch ("\s" + $pin + ";")) {
                $pinFailed.Add("${localName}: pin not $pin in project CST")
            }
            if ($refLoc[0] -notmatch ("\s" + $pin + ";")) {
                $pinFailed.Add("${officialName}: reference pin is not $pin (reference drift?)")
            }
            if ($projPort.Count -ne 1) {
                $pinFailed.Add("${localName}: expected 1 IO_PORT, found $($projPort.Count)")
                continue
            }
            # The official LEDs[2] is an output with PULL=NONE. R17 is now
            # an asynchronous MIDI input: its idle state must be pulled UP.
            $refPort = @($refLines | Where-Object {
                $_ -match ("^\s*IO_PORT\s+`"" + [regex]::Escape($officialName) + "`"")
            })
            if ($refPort.Count -ne 1) {
                $pinFailed.Add("${localName}: expected 1 reference IO_PORT, found $($refPort.Count)")
                continue
            }
            foreach ($attr in @("IO_TYPE", "PULL_MODE", "BANK_VCCIO")) {
                $pattern = [regex]::Escape($attr) + "=([^\s;]+)(?:\s|;)"
                $projMatch = [regex]::Match($projPort[0], $pattern)
                $refMatch = [regex]::Match($refPort[0], $pattern)
                if (-not $projMatch.Success -or -not $refMatch.Success) {
                    $pinFailed.Add("${localName}: missing $attr in project or reference")
                    continue
                }
                $expected = $refMatch.Groups[1].Value
                if ($localName -eq "midi_rx" -and $attr -eq "PULL_MODE") {
                    $expected = "UP"
                }
                if ($projMatch.Groups[1].Value -ne $expected) {
                    $pinFailed.Add("${localName}.${attr} = '$($projMatch.Groups[1].Value)' but expected '$expected'")
                }
            }
            # A 1.5 V bank must never be declared as 3.3 V; that mismatch would
            # damage the pin or silently break input thresholds.
            if ($pin -eq "AA13" -and $projPort[0] -notmatch "BANK_VCCIO=1\.5") {
                $pinFailed.Add("sys_rst_n (AA13) must stay in the 1.5 V bank")
            }
        }
        Add-CheckResult "Pin map matches official reference ($($pinMap.Count) pins)" `
            ($pinFailed.Count -eq 0) ($pinFailed -join "; ")
    } else {
        Add-CheckResult "Pin map matches official reference" $false `
            "project or reference CST not found"
    }

    # ---------------------------------------------------------------------
    # 6. DOCX structure
    # ---------------------------------------------------------------------
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $docxDir = Join-Path $prepRoot $docDir
    # Exclude Word's own lock/temp files. While a .docx is open in Word the
    # directory also contains "~$name.docx", which is not a ZIP archive and
    # would be reported as a corrupt deliverable. It is never tracked by git.
    $docxFiles = @(
        Get-ChildItem -LiteralPath $docxDir -Filter "*.docx" -File -ErrorAction SilentlyContinue |
            Where-Object { -not $_.Name.StartsWith('~$') }
    )
    $docxFailed = [System.Collections.Generic.List[string]]::new()
    $docxSkipped = [System.Collections.Generic.List[string]]::new()
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
            # A file currently open in Word is locked, not corrupt. Report it as
            # skipped rather than failing the suite: it is an environment state,
            # not a defect in the deliverable. Re-run with Word closed to verify.
            # .NET exceptions surface here wrapped in a MethodInvocationException,
            # so the real IOException is on InnerException.
            $inner = $_.Exception.InnerException
            if (($_.Exception -is [System.IO.IOException]) -or
                ($inner -is [System.IO.IOException])) {
                $docxSkipped.Add($file.Name)
                continue
            }
            $docxFailed.Add("$($file.Name): $($_.Exception.Message)")
        }
    }
    $docxLabel = "DOCX structure ($($docxFiles.Count) files"
    if ($docxSkipped.Count -gt 0) {
        $docxLabel += ", $($docxSkipped.Count) locked by Word and skipped"
    }
    $docxLabel += ")"
    Add-CheckResult $docxLabel `
        ($docxFailed.Count -eq 0) ($docxFailed -join "; ")

    # ---------------------------------------------------------------------
    # Load the FPGA tool environment so iverilog.exe / vvp.exe are on PATH
    # for the top-level regression check in section 9.
    #
    # Section 6 ("Legacy prototype RTL: compile and smoke run") was removed on
    # 2026-09-15 together with the legacy-prototype/ archive. That check had
    # become a false-green: it compiled a frozen 2026-09 eight-key prototype
    # whose four source files form a closed set (no include, no readmem), so
    # its result was provably independent of every change under code/ -- it
    # reported PASS for 56 of the 59 commits then on develop. The archive is
    # still recoverable from git history if the provenance is ever needed.
    # ---------------------------------------------------------------------
    . (Join-Path $codeDir (Join-Path "scripts" "enter_fpga_env.ps1"))

    # ---------------------------------------------------------------------
    # 9. T007 top-level regression simulation
    #
    # Compiles and runs tb_electronic_piano_top, the top-level self-check.
    # It asserts the two things that would otherwise be found only on the
    # bench: BCLK/LRCK absolute frequencies and the pa_en power-on-pop guard.
    #
    # This check exists because both defects it now guards against were real:
    #   1. i2s_tx toggled bclk once per bclk_ce, halving BCLK to 1.536 MHz and
    #      pushing LRCK to 24 kHz. The module-level testbench could not see it
    #      because it used synthetic parameters (BCLK_PHASE_STEP=1) and only
    #      checked ratios, never absolute frequency.
    #   2. The test tone phase step divided by CLK_HZ instead of the sample
    #      rate, making the output a 0.42 Hz sine that decoded as silence.
    # See the verification log (docs, V0029).
    # ---------------------------------------------------------------------
    $t007Script = Join-Path $codeDir (Join-Path "scripts" "run_t007_sim.ps1")
    if (Test-Path -LiteralPath $t007Script) {
        # Run in a child PowerShell so that this script's error handling is
        # unaffected by the child's native-command stderr noise.
        $shellExe = (Get-Process -Id $PID).Path
        $t007 = Invoke-Native -FilePath $shellExe -WorkingDirectory $repoRoot -Arguments @(
            "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $t007Script
        )
        $t007Passed = $t007.ExitCode -eq 0
        $t007Detail = if ($t007Passed) {
            "tb_electronic_piano_top PASS (12 checks)"
        } else {
            $tail = ($t007.Output -split "`r?`n" |
                     Where-Object { $_ -match '\[FAIL\]|FAILED|Compile failed' } |
                     Select-Object -First 6) -join " | "
            "exit=$($t007.ExitCode) $tail"
        }
        Add-CheckResult "T007 top-level simulation" $t007Passed $t007Detail
    } else {
        Add-CheckResult "T007 top-level simulation" $false "run_t007_sim.ps1 not found"
    }

    # ---------------------------------------------------------------------
    # 9b. T019 common-package simulation
    #
    # Runs tb_audio_defs_pkg, tb_reset_sync and tb_sample_tick_gen. Added
    # 2026-09-18 after tb_audio_defs_pkg was found FAILING in the working tree:
    # it still asserted the old I2S_BCLK_PHASE_STEP = 263882791 while
    # audio_defs_pkg.sv had been corrected to 527765581 (the parameter is a
    # toggle rate, i.e. 2 x BCLK). The stale expectation had been red for a
    # while and nobody saw it, because only T007 ran inside this gate. The
    # package carries the shared interface constants, so a silently rotting
    # package testbench is a cross-team risk, not a private one.
    # ---------------------------------------------------------------------
    $t019Script = Join-Path $codeDir (Join-Path "scripts" "run_t019_sim.ps1")
    if (Test-Path -LiteralPath $t019Script) {
        $shellExe019 = (Get-Process -Id $PID).Path
        $t019 = Invoke-Native -FilePath $shellExe019 -WorkingDirectory $repoRoot -Arguments @(
            "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $t019Script
        )
        $t019Passed = $t019.ExitCode -eq 0
        $t019Detail = if ($t019Passed) {
            "tb_audio_defs_pkg / tb_reset_sync / tb_sample_tick_gen PASS"
        } else {
            $tail019 = ($t019.Output -split "`r?`n" |
                        Where-Object { $_ -match '\[FAIL\]|FAILED|Compile failed' } |
                        Select-Object -First 6) -join " | "
            "exit=$($t019.ExitCode) $tail019"
        }
        Add-CheckResult "T019 common-package simulation" $t019Passed $t019Detail
    } else {
        Add-CheckResult "T019 common-package simulation" $false "run_t019_sim.ps1 not found"
    }

    # ---------------------------------------------------------------------
    # 10. External reference digests stay annotated and intact
    #
    # docs/reference/ holds board documentation written by someone else.
    # Two things must hold or the directory silently loses its meaning:
    #   a. Each digest still carries the provenance banner. Without it a
    #      reader cannot tell that the file is an external digest rather than
    #      this project's own board fact source, and would treat its
    #      "PBG484A is confirmed" wording as settled while D018 keeps that
    #      spelling undecided.
    #   b. The digest bodies are not edited. The Python helper re-derives the
    #      body and asserts it did not shrink relative to the source file.
    #
    # The heavy lifting lives in verify_reference_digests.py: comparing CJK
    # text from PowerShell 5.1 is a trap (BOM-less UTF-8 is decoded as ANSI),
    # and Python also reports the true on-disk size, which Get-Content can
    # serve stale.
    # ---------------------------------------------------------------------
    $refVerifier = Join-Path $codeDir (Join-Path "scripts" "verify_reference_digests.py")
    if (Test-Path -LiteralPath $refVerifier) {
        $prevEap = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        $refOut = & python -X utf8 $refVerifier 2>&1
        $refCode = $LASTEXITCODE
        $ErrorActionPreference = $prevEap
        $refTail = (($refOut | Where-Object { $_ -match '\S' } |
                     Select-Object -Last 4) -join " | ")
        Add-CheckResult "Reference digests annotated" ($refCode -eq 0) `
            "exit=$refCode $refTail"
    } else {
        Add-CheckResult "Reference digests annotated" $false `
            "verify_reference_digests.py not found"
    }
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
