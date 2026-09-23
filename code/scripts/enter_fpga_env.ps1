$ErrorActionPreference = "Stop"

function Find-InstalledToolRoot {
    param(
        [string[]]$Candidates,
        [string]$RequiredRelativePath,
        [string]$ToolName
    )

    foreach ($candidate in $Candidates) {
        if ([string]::IsNullOrWhiteSpace($candidate)) {
            continue
        }
        if (Test-Path -LiteralPath (Join-Path $candidate $RequiredRelativePath) -PathType Leaf) {
            return (Resolve-Path -LiteralPath $candidate).Path
        }
    }
    throw "$ToolName was not found. Set its installation root environment variable."
}

# Environment variables take priority; keep both existing and bundled layouts.
$gowinRoot = Find-InstalledToolRoot -ToolName "Gowin IDE" `
    -RequiredRelativePath "IDE\bin\GowinSynthesis.exe" -Candidates @(
        $env:GOWIN_HOME,
        "D:\Gowin\Gowin_V1.9.11.03_Education\Gowin_V1.9.11.03_Education_x64",
        "D:\program\gaoyunFPGA\Gowin\Gowin_V1.9.11.03_Education_x64"
    )
$programmerRoot = Find-InstalledToolRoot -ToolName "Gowin Programmer" `
    -RequiredRelativePath "bin\programmer.exe" -Candidates @(
        $env:GOWIN_PROGRAMMER_HOME,
        (Join-Path $gowinRoot "Programmer"),
        "D:\Gowin\Programmer_V1.9.12.02"
    )
$ossCadRoot = "D:\Gowin\oss-cad-suite"

$requiredDirectories = @(
    $gowinRoot,
    $programmerRoot
)

foreach ($directory in $requiredDirectories) {
    if (-not (Test-Path -LiteralPath $directory)) {
        throw "Required FPGA tool directory is missing: $directory"
    }
}

$toolPaths = @(
    "$gowinRoot\IDE\bin",
    "$programmerRoot\bin"
)

if (Test-Path -LiteralPath "$ossCadRoot\bin") {
    $toolPaths += @(
        "$ossCadRoot\bin",
        "$ossCadRoot\lib"
    )

    $env:YOSYSHQ_ROOT = "$ossCadRoot\"
    $env:SSL_CERT_FILE = "$ossCadRoot\etc\cacert.pem"
    $env:PYTHON_EXECUTABLE = "$ossCadRoot\lib\python3.exe"
    $env:QT_PLUGIN_PATH = "$ossCadRoot\lib\qt6\plugins"
    $env:QT_LOGGING_RULES = "*=false"
    $env:GTK_EXE_PREFIX = $ossCadRoot
    $env:GTK_DATA_PREFIX = $ossCadRoot
    $env:GDK_PIXBUF_MODULEDIR = "$ossCadRoot\lib\gdk-pixbuf-2.0\2.10.0\loaders"
    $env:GDK_PIXBUF_MODULE_FILE = "$ossCadRoot\lib\gdk-pixbuf-2.0\2.10.0\loaders.cache"
    $env:OPENFPGALOADER_SOJ_DIR = "$ossCadRoot\share\openFPGALoader"
    $env:VERILATOR_ROOT = "$ossCadRoot\share\verilator"

    Set-Alias -Name verilator -Value "$ossCadRoot\bin\verilator_bin.exe" -Scope Global
}

$env:GOWIN_HOME = $gowinRoot
$env:PATH = (($toolPaths + $env:PATH.Split(";")) | Select-Object -Unique) -join ";"

Write-Host "FPGA development environment loaded."
Write-Host "GOWIN_HOME: $env:GOWIN_HOME"
Write-Host "ASCII workspace: D:\Gowin\workspace\embedded_fpga"
