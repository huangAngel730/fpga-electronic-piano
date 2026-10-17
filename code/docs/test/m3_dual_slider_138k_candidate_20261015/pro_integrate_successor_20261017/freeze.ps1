$ErrorActionPreference = 'Stop'
$started = [DateTime]::UtcNow
$hereDir = $PSScriptRoot
$repoDir = (Resolve-Path -LiteralPath (Join-Path $hereDir '../../../../..')).Path
$utf8 = [Text.UTF8Encoding]::new($false)
$spec = Get-Content -LiteralPath (Join-Path $hereDir 'INPUT_SPEC.json') -Encoding UTF8 -Raw | ConvertFrom-Json
$copyDir = Join-Path $hereDir 'INPUT_ORIGINALS'
if (Test-Path -LiteralPath $copyDir) { throw 'EXCLUSIVE_OUTPUT_ALREADY_EXISTS' }
[void][IO.Directory]::CreateDirectory($copyDir)
$rows = @()
foreach ($group in @('external_files', 'repository_files')) {
    foreach ($property in $spec.$group.PSObject.Properties) {
        $sourcePath = [string]$property.Value
        if ($group -eq 'repository_files') { $sourcePath = Join-Path $repoDir $sourcePath }
        $sourcePath = (Resolve-Path -LiteralPath $sourcePath).Path
        $targetPath = Join-Path $copyDir ($property.Name + [IO.Path]::GetExtension($sourcePath))
        $before = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash.ToLowerInvariant()
        [IO.File]::Copy($sourcePath, $targetPath, $false)
        $after = (Get-FileHash -LiteralPath $targetPath -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($before -ne $after) { throw 'COPY_SHA_MISMATCH' }
        $rows += [ordered]@{id=$property.Name; source=$sourcePath; frozen=$targetPath; bytes=(Get-Item -LiteralPath $targetPath).Length; sha256=$after}
    }
}
[IO.File]::WriteAllText((Join-Path $hereDir 'INPUT_IDENTITIES.json'), (ConvertTo-Json -InputObject $rows -Depth 8) + "`n", $utf8)
$inventory = @()
foreach ($relative in $spec.inventories) {
    $directory = Join-Path $repoDir $relative
    foreach ($file in Get-ChildItem -LiteralPath $directory -File -Recurse) {
        if ($relative -eq 'code/build' -and $file.Extension -notin @('.gprj', '.sdc')) { continue }
        $inventory += [ordered]@{scope=$relative; path=$file.FullName; bytes=$file.Length; sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()}
    }
}
[IO.File]::WriteAllText((Join-Path $hereDir 'DISCOVERY_INVENTORY.json'), (ConvertTo-Json -InputObject $inventory -Depth 8) + "`n", $utf8)
$receipt = [ordered]@{kind='STATIC_INPUT_COPY_NOT_RTL_TEST'; start_utc=$started.ToString('o'); end_utc=[DateTime]::UtcNow.ToString('o'); argv=@((Get-Process -Id $PID).Path, '-File', $PSCommandPath); cwd=(Get-Location).Path; machine=[Environment]::MachineName; pid=$PID; powershell_version=$PSVersionTable.PSVersion.ToString(); powershell_sha256=(Get-FileHash -LiteralPath (Get-Process -Id $PID).Path -Algorithm SHA256).Hash.ToLowerInvariant(); copied=$rows.Count; inventories=$inventory.Count; exit_code=0; software_validation_rounds_consumed=0; simulator_EDA_hardware_git_writes=0}
[IO.File]::WriteAllText((Join-Path $hereDir 'FREEZE_RECEIPT.json'), (ConvertTo-Json $receipt -Depth 8) + "`n", $utf8)
[IO.File]::WriteAllText((Join-Path $hereDir 'freeze.stdout'), (ConvertTo-Json $receipt -Depth 8) + "`n", $utf8)
[IO.File]::WriteAllText((Join-Path $hereDir 'freeze.stderr'), '', $utf8)
$receipt | ConvertTo-Json -Depth 8
