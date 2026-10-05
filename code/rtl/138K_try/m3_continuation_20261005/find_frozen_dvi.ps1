$ErrorActionPreference = 'Stop'
$m3Here = 'E:/FPGA/GAOYUNFPGA/138K_try/m3_continuation_20261005'
if ($PSScriptRoot.Replace('\','/') -ne $m3Here) { throw 'Unexpected script directory' }
$m3Targets = @(
    'b378c6a41d06a14215dc9ec54ed20bfc91309a0bb1543c589246717da3aee2ab',
    '162f68cab4262f8a3acae17f2fc66b6d9ef403815fd5ebeeecf30b59d88e203c',
    'e5045dd28131089b999fe75bb27e8ee82e33ab3fcdb39b7c8bc9a1570309ffe1',
    '1a1745e4785009d9bcb9815ebad19e0b13f51834d7bc68ed90ea5fd662278656'
)
$m3Roots = @('E:/FPGA','D:/program/gaoyunFPGA',
    'C:/Users/songdongkuan/Downloads','C:/Users/songdongkuan/Desktop')
$m3ScanErrors = @()
$m3Files = @(& rg --files -uuu @m3Roots -g '*.v' -g '*.vo' -g '*.vg' -g '*.ipc' -g '!**/.git/**' -g '!**/node_modules/**' 2>&1 | ForEach-Object {
    $m3Line = $_.ToString()
    if ($m3Line.StartsWith('rg:')) { $m3ScanErrors += $m3Line }
    else { $m3Line }
})
$m3Hits = @()
$m3Count = 0
$m3Skipped = 0
$m3Digest = [Security.Cryptography.SHA256]::Create()
try {
    foreach ($m3Path in $m3Files) {
        try {
            if ((Get-Item -LiteralPath $m3Path).Length -gt 1048576) { $m3Skipped++; continue }
            $m3Bytes = [IO.File]::ReadAllBytes($m3Path)
            $m3RawSha = [Convert]::ToHexString($m3Digest.ComputeHash($m3Bytes)).ToLowerInvariant()
            $m3Text = [Text.Encoding]::UTF8.GetString($m3Bytes).Replace("`r`n","`n")
            $m3LfSha = [Convert]::ToHexString($m3Digest.ComputeHash([Text.Encoding]::UTF8.GetBytes($m3Text))).ToLowerInvariant()
            $m3Count++
            if ($m3RawSha -in $m3Targets -or $m3LfSha -in $m3Targets) {
                $m3Hits += [PSCustomObject]@{path=$m3Path;raw_sha256=$m3RawSha;lf_sha256=$m3LfSha}
            }
        } catch { $m3ScanErrors += "$m3Path : $($_.Exception.Message)" }
    }
} finally { $m3Digest.Dispose() }
$m3Report = [PSCustomObject]@{
    time=(Get-Date -Format o); scope='Read-only raw/LF hash search including renamed Verilog files'
    roots=$m3Roots; target_sha256=$m3Targets; candidates=$m3Files.Count
    hashed=$m3Count; skipped_over_1MiB=$m3Skipped; matches=$m3Hits; scan_errors=$m3ScanErrors
    cli_sha256=(Get-FileHash -LiteralPath 'E:/FPGA/GAOYUNFPGA/138K_try/tools/gowin_1_9_11_03/IDE/bin/gw_sh.exe').Hash.ToLowerInvariant()
    installer_sha256=(Get-FileHash -LiteralPath 'D:/program/gaoyunFPGA/Gowin_V1.9.11.03_Education_x64_win (1)/Gowin_V1.9.11.03_Education_x64_win.exe').Hash.ToLowerInvariant()
    source_repo_written=$false; PnR_executed=$false
}
$m3Report | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath "$m3Here/dvi_search_proof.json" -Encoding utf8
$m3Report | Select-Object time,candidates,hashed,skipped_over_1MiB,@{n='match_count';e={$_.matches.Count}},@{n='scan_error_count';e={$_.scan_errors.Count}},cli_sha256,installer_sha256 | ConvertTo-Json
if ($m3Hits.Count -gt 0) { $m3Hits | ConvertTo-Json }
exit 0
