param()

$ErrorActionPreference = 'Stop'
$m3WorkRoot = [IO.Path]::GetFullPath($PSScriptRoot)
$m3AllowedRoot = 'E:\FPGA\GAOYUNFPGA\138K_try\m3_continuation_20261005'
if ($m3WorkRoot.TrimEnd('\') -ne $m3AllowedRoot) {
    throw 'This entry must run only in its isolated continuation directory.'
}
$m3AuditRoot = 'E:\FPGA\GAOYUNFPGA\138K_try\comparison_20261005_dab75308'
$m3Snapshot = Join-Path $m3WorkRoot 'audit_snapshot'
$m3Input = Get-Content -LiteralPath (Join-Path $m3Snapshot 'input_audit.json') -Raw | ConvertFrom-Json
$m3Normalized = Get-Content -LiteralPath (Join-Path $m3Snapshot 'normalized_audit.json') -Raw | ConvertFrom-Json
$m3Review = Get-Content -LiteralPath (Join-Path $m3Snapshot 'V0171_review_original.json') -Raw | ConvertFrom-Json
$m3FinalManifest = '1e29e550b129176e06fe609631229ae7c03a22ed3ad9ac4652f0705c7a234a36'
$m3ParserHash = '834887a990a4866d54669c5f18588a0b799aa4c08ccb27c91a2f9e5609f331c6'
$m3Tests = [Collections.Generic.List[string]]::new()
function Assert-M3Fact([bool] $Condition, [string] $Description) {
    if (-not $Condition) { throw "FAIL: $Description" }
    $m3Tests.Add($Description)
}

$m3Names = [Collections.Generic.HashSet[string]]::new()
$m3Direct = @($m3Input.files | Where-Object { @($_.actual_matches).Count -gt 0 })
foreach ($m3File in $m3Direct) { [void]$m3Names.Add($m3File.name) }
$m3NormMatch = @($m3Normalized.files | Where-Object { @($_.matches).Count -gt 0 })
foreach ($m3File in $m3NormMatch) { [void]$m3Names.Add($m3File.name) }
$m3Unresolved = @($m3Normalized.files | Where-Object { @($_.matches).Count -eq 0 })
Assert-M3Fact (@($m3Input.files).Count -eq 47) '47 historical project entries'
Assert-M3Fact (@($m3Input.files | Where-Object { @($_.input_matches).Count -gt 0 }).Count -eq 36) '36 input matches'
Assert-M3Fact ($m3Direct.Count -eq 33) '33 direct actual matches'
Assert-M3Fact ($m3NormMatch.Count -eq 5) '5 explicit normalization matches'
Assert-M3Fact ($m3Names.Count -eq 38) '38 unique actual identities, not 47'
Assert-M3Fact ($m3Unresolved.Count -eq 9) '9 unresolved identities'
Assert-M3Fact (@($m3Input.roms).Count -eq 7) '7 ROM entries in prior audit'
Assert-M3Fact (@($m3Input.scan_errors).Count -eq 15) '15 prior scan errors preserved'
Assert-M3Fact ($m3Review.source_parser_sha256 -eq $m3ParserHash) 'de68038 exact parser identity'
Assert-M3Fact ($m3Review.new_physical_gate.manifest_sha256 -eq $m3FinalManifest) 'V0171 expected final manifest identity'
Assert-M3Fact ($m3Input.expected_final_manifest_sha256 -eq $m3FinalManifest) 'handoff expected manifest agrees with review'
Assert-M3Fact ($m3Review.fairness.exact_single_parser_source_change -eq $true) 'historical single-parser-only source change'
Assert-M3Fact ($m3Review.fairness.Hold_uncertainty_ns -eq 0.55) 'historical system Hold uncertainty 0.550ns'
Assert-M3Fact ($m3Input.tool_run -eq $false) 'prior audit did not run EDA'

$m3Hashes = foreach ($m3FileName in @('input_audit.json', 'normalized_audit.json', 'V0165_manifest_original.json', 'V0171_review_original.json', 'reference_inspection.json', 'device_info_original.csv')) {
    $m3Original = (Get-FileHash -LiteralPath (Join-Path $m3AuditRoot $m3FileName) -Algorithm SHA256).Hash.ToLowerInvariant()
    $m3Copied = (Get-FileHash -LiteralPath (Join-Path $m3Snapshot $m3FileName) -Algorithm SHA256).Hash.ToLowerInvariant()
    Assert-M3Fact ($m3Original -eq $m3Copied) "unchanged audit snapshot $m3FileName"
    [ordered]@{file=$m3FileName; original_sha256=$m3Original; snapshot_sha256=$m3Copied}
}
$m3ReferenceHashes = foreach ($m3FileName in @('board_138k_schematic.pdf', 'board_138k_reference.cst', 'board_138k_page_5.png', 'board_138k_page_6.png', 'board_138k_page_7.png', 'gowin_user_guide.pdf')) {
    [ordered]@{file=$m3FileName; sha256=(Get-FileHash -LiteralPath (Join-Path $m3AuditRoot $m3FileName) -Algorithm SHA256).Hash.ToLowerInvariant()}
}
$m3OutputHashes = foreach ($m3FileName in @('README.md', 'M2_冻结工程补包请求.md', 'record_checkpoint.ps1')) {
    [ordered]@{file=$m3FileName; sha256=(Get-FileHash -LiteralPath (Join-Path $m3WorkRoot $m3FileName) -Algorithm SHA256).Hash.ToLowerInvariant()}
}
$m3Result = [ordered]@{
    local_time=(Get-Date).ToString('o')
    utc_time=[DateTime]::UtcNow.ToString('o')
    task='V0171 audio+HDMI 60K control versus 138K B/C offline physical timing comparison'
    status='BLOCKED_FROZEN_ENGINEERING_PACKET_INCOMPLETE'
    actual_grade='static audit only; no simulation, synthesis, PnR, STA, programming'
    source_repo_access='read-only; no scripts or Git write operations executed'
    notification='待用户转发，尚未送达'
    assertions_passed=$m3Tests.Count
    assertion_names=@($m3Tests)
    exit_code_meaning='0 means audit checkpoint succeeded, not physical timing PASS'
    expected_final_manifest_sha256=$m3FinalManifest
    final_manifest_received=$false
    parser_sha256=$m3ParserHash
    input_entries=47
    input_matches=36
    direct_actual_matches=33
    normalization_actual_matches=5
    actual_identities_verified=38
    unresolved=@($m3Unresolved | Select-Object name, expected_actual_sha256)
    historical_M2_only=$m3Review.new_physical_gate.facts
    target_clocks_mhz=@{system=50;pixel=25;serial=125}
    hold_uncertainty_ns=0.550
    target_devices=@{B='gw5ast138b-011';C='gw5ast138c-007';part='GW5AST-LV138PG484AC1/I0';package='PBGA484A';speed='C1/I0'}
    schematic_pages_visually_reviewed_this_turn=@(5,6,7)
    source_snapshot_hashes=@($m3Hashes)
    reference_hashes=@($m3ReferenceHashes)
    deliverable_hashes=@($m3OutputHashes)
}
$m3Result | ConvertTo-Json -Depth 12 | Set-Content -LiteralPath (Join-Path $m3WorkRoot 'checkpoint.json') -Encoding utf8NoBOM
Write-Output "PASS: $($m3Tests.Count) static checkpoint assertions; physical comparison remains BLOCKED."
exit 0
