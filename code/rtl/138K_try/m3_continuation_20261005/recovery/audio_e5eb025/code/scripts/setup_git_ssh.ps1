# Configure git to use the Windows native OpenSSH client for this repo.
#
# Why this exists
# ---------------
# Git for Windows bundles a Cygwin build of ssh at
#   C:\Program Files\Git\usr\bin\ssh.exe
# which creates a Windows named pipe for its signal handling at startup.
# Under a restricted sandbox (and in some corporate environments) creating
# that pipe is denied, so ssh dies before authenticating:
#
#   ssh.exe: *** fatal error - couldn't create signal pipe, Win32 error 5
#   fatal: Could not read from remote repository.
#
# The Windows native client at C:\WINDOWS\System32\OpenSSH\ssh.exe does not
# use a named pipe and works in the same environment. Pointing git at it
# removes the need to elevate permissions for every fetch and push.
#
# This writes to .git/config, which is NOT distributed with the repository,
# so each teammate runs this once per clone.
#
# Keep this file pure ASCII - see the "PowerShell script conventions"
# section in the code/ AGENTS.md.

$ErrorActionPreference = "Stop"

# --- Locate a usable ssh ------------------------------------------------
$candidates = @(
    (Join-Path $env:SystemRoot "System32\OpenSSH\ssh.exe"),
    (Join-Path $env:ProgramFiles "OpenSSH\ssh.exe")
)
$nativeSsh = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1

if (-not $nativeSsh) {
    Write-Host "Windows native OpenSSH client not found. Looked in:" -ForegroundColor Red
    $candidates | ForEach-Object { Write-Host "  $_" -ForegroundColor Red }
    Write-Host ""
    Write-Host "Install it via: Settings > System > Optional features > OpenSSH Client" -ForegroundColor Yellow
    Write-Host "or run: Add-WindowsCapability -Online -Name OpenSSH.Client~~~~0.0.1.0" -ForegroundColor Yellow
    exit 1
}

Write-Host "Using ssh client: $nativeSsh" -ForegroundColor Cyan

# --- Point this repository at it ----------------------------------------
# git wants forward slashes in this setting.
$sshForGit = $nativeSsh -replace '\\', '/'
& git config core.sshCommand $sshForGit
if ($LASTEXITCODE -ne 0) {
    Write-Host "Failed to write core.sshCommand." -ForegroundColor Red
    exit 1
}
Write-Host "Set core.sshCommand = $sshForGit"

# --- Verify the remote is reachable -------------------------------------
Write-Host ""
Write-Host "Testing remote access..." -ForegroundColor Cyan
$previous = $ErrorActionPreference
$ErrorActionPreference = "Continue"
$output = (& git ls-remote --heads origin 2>&1 | Out-String).Trim()
$code = $LASTEXITCODE
$ErrorActionPreference = $previous

if ($code -ne 0) {
    Write-Host "Remote check FAILED (exit $code):" -ForegroundColor Red
    Write-Host $output -ForegroundColor Red
    Write-Host ""
    Write-Host "The ssh client works, but the remote is still unreachable." -ForegroundColor Yellow
    Write-Host "Check that your key is registered with GitHub:" -ForegroundColor Yellow
    Write-Host "  ssh -T git@github.com" -ForegroundColor Yellow
    exit 1
}

$branchCount = @($output -split "`r?`n" | Where-Object { $_ }).Count
Write-Host "Remote reachable, $branchCount branch(es) visible." -ForegroundColor Green
Write-Host ""
Write-Host "Done. git fetch/push in this repository no longer needs elevation." -ForegroundColor Green
exit 0
