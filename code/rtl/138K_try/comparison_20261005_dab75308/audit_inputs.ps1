param(
    [Parameter(Mandatory=$true)][string]$Manifest,
    [Parameter(Mandatory=$true)][string]$Review,
    [Parameter(Mandatory=$true)][string[]]$SearchRoots
)
$ErrorActionPreference = 'Stop'
$experimentRoot = $PSScriptRoot
if (-not $experimentRoot.StartsWith('E:\FPGA\GAOYUNFPGA\138K_try\')) { throw 'Unauthorized output root' }
$manifestData = Get-Content -LiteralPath $Manifest -Raw -Encoding UTF8 | ConvertFrom-Json
$reviewData = Get-Content -LiteralPath $Review -Raw -Encoding UTF8 | ConvertFrom-Json
$items = @($manifestData.source_builds)
if ($items.Count -eq 0) { throw 'No files in manifest' }
$names = @{}
foreach ($item in $items) { $names[[IO.Path]::GetFileName($item.input_source)] = $true }
foreach ($rom in $manifestData.roms.PSObject.Properties) { $names[[IO.Path]::GetFileName($rom.Name)] = $true }
$names['sustain_controller_ports.svh'] = $true
$candidates = @{}
$scanErrors = @()
foreach ($root in $SearchRoots) {
    $rootErrors = @()
    foreach ($file in Get-ChildItem -LiteralPath $root -Recurse -File -ErrorAction SilentlyContinue -ErrorVariable rootErrors) {
        if ($names.ContainsKey($file.Name)) {
            $entry = [ordered]@{path=$file.FullName; sha256=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant(); size=$file.Length}
            if (-not $candidates.ContainsKey($file.Name)) { $candidates[$file.Name] = @() }
            $candidates[$file.Name] += $entry
        }
    }
    $scanErrors += @($rootErrors | ForEach-Object { $_.ToString() })
}
$records = @()
foreach ($item in $items) {
    $name = [IO.Path]::GetFileName($item.input_source)
    $sourceHash = $item.input_sha
    $actualHash = $item.actual_sha
    if ($name -eq 'midi_event_parser.sv') { $sourceHash=$reviewData.source_parser_sha256; $actualHash=$sourceHash }
    $found = @()
    if ($candidates.ContainsKey($name)) { $found = @($candidates[$name]) }
    $records += [ordered]@{name=$name; expected_input_sha256=$sourceHash; expected_actual_sha256=$actualHash; input_matches=@($found | Where-Object {$_.sha256 -eq $sourceHash}); actual_matches=@($found | Where-Object {$_.sha256 -eq $actualHash}); candidates=$found}
}
$romRecords = @()
foreach ($rom in $manifestData.roms.PSObject.Properties) {
    $name = [IO.Path]::GetFileName($rom.Name)
    $romRecords += [ordered]@{name=$name; expected_sha256=$rom.Value; matches=@($candidates[$name] | Where-Object {$_.sha256 -eq $rom.Value}); candidates=@($candidates[$name])}
}
$audit = [ordered]@{scope='V0171 exact source search; old V0165 manifest plus reviewed parser replacement; not a reconstructed V0171 manifest'; manifest=$Manifest; manifest_sha256=(Get-FileHash -LiteralPath $Manifest).Hash; review=$Review; review_sha256=(Get-FileHash -LiteralPath $Review).Hash; expected_final_manifest_sha256=$reviewData.new_physical_gate.manifest_sha256; search_roots=$SearchRoots; scan_errors=$scanErrors; files=$records; roms=$romRecords; include_candidates=@($candidates['sustain_controller_ports.svh']); tool_run=$false}
$json = $audit | ConvertTo-Json -Depth 12
[IO.File]::WriteAllText((Join-Path $experimentRoot 'input_audit.json'), $json+[Environment]::NewLine, [Text.UTF8Encoding]::new($false))
$records | ForEach-Object { '{0}: input={1} actual={2} candidates={3}' -f $_.name,$_.input_matches.Count,$_.actual_matches.Count,$_.candidates.Count }
$romRecords | ForEach-Object { 'ROM {0}: matches={1}' -f $_.name,$_.matches.Count }
