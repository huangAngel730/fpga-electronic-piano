# Shared Python discovery for the T026 GUI and test runner.
# Keep this file ASCII-only for Windows PowerShell 5.1.
function Resolve-T026Python {
    param([string]$PythonExe = "")

    $candidates = New-Object 'System.Collections.Generic.List[string]'
    if (-not [string]::IsNullOrWhiteSpace($PythonExe)) {
        $candidates.Add($PythonExe)
    } else {
        foreach ($name in @("python", "py")) {
            $command = Get-Command $name -CommandType Application -ErrorAction SilentlyContinue |
                Select-Object -First 1
            if ($null -ne $command) {
                $candidates.Add($command.Source)
            }
        }
        if (-not [string]::IsNullOrWhiteSpace($env:USERPROFILE)) {
            $candidates.Add((Join-Path $env:USERPROFILE "miniconda3\python.exe"))
        }
        if (-not [string]::IsNullOrWhiteSpace($env:LOCALAPPDATA)) {
            $candidates.Add((Join-Path $env:LOCALAPPDATA "Programs\Python\Python312\python.exe"))
        }
        $candidates.Add("D:\ProgramData\anaconda3\python.exe")
    }

    foreach ($candidate in $candidates) {
        if (-not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            continue
        }
        $savedPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"
        try {
            $resolved = & $candidate -X utf8 -c "import sys; print(sys.executable)" 2>$null
            $exitCode = $LASTEXITCODE
        } catch {
            $exitCode = 1
        } finally {
            $ErrorActionPreference = $savedPreference
        }
        if ($exitCode -eq 0) {
            $resolvedPath = ([string](@($resolved) | Select-Object -Last 1)).Trim()
            if (Test-Path -LiteralPath $resolvedPath -PathType Leaf) {
                return $resolvedPath
            }
        }
    }

    throw "Python executable not found. Install Python or use -PythonExe with its full path."
}
