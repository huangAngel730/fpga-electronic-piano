$ErrorActionPreference = "Stop"

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$outputRoot = Join-Path $repoRoot "代码\output\repo-check"
$failures = [System.Collections.Generic.List[string]]::new()

function Add-CheckResult {
    param(
        [string]$Name,
        [bool]$Passed,
        [string]$Detail
    )

    [pscustomobject]@{
        Check = $Name
        Result = if ($Passed) { "PASS" } else { "FAIL" }
        Detail = $Detail
    }

    if (-not $Passed) {
        $failures.Add("${Name}: ${Detail}")
    }
}

Push-Location $repoRoot
try {
    $requiredPaths = @(
        "AGENTS.md",
        "README.md",
        ".gitattributes",
        ".editorconfig",
        "准备\README.md",
        "准备\脚本\README.md",
        "代码\README.md",
        "代码\docs\README.md",
        "代码\docs\协作入口.md",
        "legacy-prototype\AGENTS.md",
        "legacy-prototype\README.md"
    )

    foreach ($path in $requiredPaths) {
        Add-CheckResult "Required path" (Test-Path -LiteralPath $path) $path
    }

    $diffOutput = & git diff --check 2>&1
    Add-CheckResult "Git whitespace" ($LASTEXITCODE -eq 0) (($diffOutput | Out-String).Trim())

    $trackedFiles = @(& git ls-files)
    $forbiddenPatterns = @(
        "^\.tools/",
        "(^|/)output/",
        "\.(vcd|fst|fsdb|wlf|vvp|fs|bit|sof|pof)$",
        "^准备/选题\.7z$",
        "^准备/团队AI协作共享包"
    )
    $forbiddenTracked = @(
        $trackedFiles | Where-Object {
            $candidate = $_
            $forbiddenPatterns | Where-Object { $candidate -match $_ }
        }
    )
    Add-CheckResult "Forbidden tracked files" ($forbiddenTracked.Count -eq 0) ($forbiddenTracked -join ", ")

    $pythonFiles = @(Get-ChildItem -LiteralPath "准备\脚本" -Filter "*.py" -File)
    $pythonPassed = $true
    $pythonDetails = [System.Collections.Generic.List[string]]::new()
    foreach ($file in $pythonFiles) {
        & python -m py_compile $file.FullName
        if ($LASTEXITCODE -ne 0) {
            $pythonPassed = $false
            $pythonDetails.Add($file.Name)
        }
    }
    Add-CheckResult "Python syntax" $pythonPassed ("{0} files checked; failed: {1}" -f $pythonFiles.Count, ($pythonDetails -join ", "))

    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $docxFiles = @(Get-ChildItem -LiteralPath "准备\文档" -Filter "*.docx" -File)
    $docxPassed = $true
    $docxDetails = [System.Collections.Generic.List[string]]::new()
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
            $docxPassed = $false
            $docxDetails.Add("$($file.Name): $($_.Exception.Message)")
        }
    }
    Add-CheckResult "DOCX structure" $docxPassed ("{0} files checked; {1}" -f $docxFiles.Count, ($docxDetails -join "; "))

    . ".\代码\scripts\enter_fpga_env.ps1"
    New-Item -ItemType Directory -Force -Path $outputRoot | Out-Null
    $vvpFile = Join-Path $outputRoot "legacy-prototype.vvp"
    $sources = @(
        "legacy-prototype\rtl\electronic_piano_top.v",
        "legacy-prototype\rtl\key_debounce.v",
        "legacy-prototype\rtl\tone_generator.v",
        "legacy-prototype\tb\tb_electronic_piano.v"
    )
    & iverilog.exe -g2012 -Wall -s tb_electronic_piano -o $vvpFile @sources
    $compilePassed = $LASTEXITCODE -eq 0
    Add-CheckResult "Legacy RTL compile" $compilePassed $vvpFile

    if ($compilePassed) {
        $rtlOutput = (& vvp.exe $vvpFile 2>&1 | Out-String)
        $rtlPassed = ($rtlOutput -notmatch "ERROR:") -and ($rtlOutput -match "\$finish called")
        Add-CheckResult "Legacy RTL smoke" $rtlPassed ($rtlOutput.Trim())
    }
} finally {
    Pop-Location
}

if ($failures.Count -gt 0) {
    Write-Host "Repository check failed:" -ForegroundColor Red
    $failures | ForEach-Object { Write-Host "- $_" -ForegroundColor Red }
    exit 1
}

Write-Host "All repository checks passed." -ForegroundColor Green

