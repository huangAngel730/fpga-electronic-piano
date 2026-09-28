# M2 independent T025 formal-top telemetry test. ASCII only for PowerShell 5.1.
$ErrorActionPreference = 'Stop'
$repo = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
. (Join-Path $PSScriptRoot 'enter_fpga_env.ps1') | Out-Null
$toolRoot = 'D:\Gowin\oss-cad-suite'
$envBat = Join-Path $toolRoot 'environment.bat'
$iverilog = Join-Path $toolRoot 'bin\iverilog.exe'
$vvp = Join-Path $toolRoot 'bin\vvp.exe'
foreach ($tool in @($envBat, $iverilog, $vvp)) {
    if (-not (Test-Path -LiteralPath $tool -PathType Leaf)) { throw "Missing tool: $tool" }
}
$stage = Join-Path $repo ('code\output\t025_top_diag\run_'+[guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $stage -Force | Out-Null
$projectText = [IO.File]::ReadAllText((Join-Path $repo 'code\build\electronic_piano.gprj'),[Text.Encoding]::UTF8)
$project = [xml]($projectText.Replace('<?xml version="1"', '<?xml version="1.0"'))
$files = @($project.Project.FileList.File | Where-Object { $_.type -eq 'file.verilog' -and $_.enable -eq '1' })
$base = Join-Path $repo 'code\build'
$staged = @()
foreach ($item in $files) {
    $src = [IO.Path]::GetFullPath((Join-Path $base $item.path))
    $rel = $src.Substring($repo.Length).TrimStart('\')
    $dest = Join-Path $stage $rel
    New-Item -ItemType Directory -Path (Split-Path -Parent $dest) -Force | Out-Null
    Copy-Item -LiteralPath $src -Destination $dest
    $staged += $dest
}
$header = Join-Path $stage 'code\rtl\common\sine_table.svh'
Copy-Item -LiteralPath (Join-Path $repo 'code\rtl\common\sine_table.svh') -Destination $header
$tb = Join-Path $stage 'code\tb\board\tb_t025_top_diag.sv'
New-Item -ItemType Directory -Path (Split-Path -Parent $tb) -Force | Out-Null
Copy-Item -LiteralPath (Join-Path $repo 'code\tb\board\tb_t025_top_diag.sv') -Destination $tb
$pkg = Join-Path $stage 'code\rtl\common\audio_defs_pkg.sv'
$ordered = @($pkg) + @($staged | Where-Object { $_ -ne $pkg }) + @($tb)
$driver = Join-Path $stage 'run.bat'
$srcArgs = ($ordered | ForEach-Object { '"'+$_+'"' }) -join ' '
$lines = @('@echo off',('call "'+$envBat+'" >nul'),('"'+$iverilog+'" -g2012 -s tb_t025_top_diag -I "'+(Split-Path -Parent $header)+'" -o "'+(Join-Path $stage 'tb.vvp')+'" '+$srcArgs),'if errorlevel 1 exit /b 1',('"'+$vvp+'" "'+(Join-Path $stage 'tb.vvp')+'"'),'exit /b %errorlevel%')
[IO.File]::WriteAllLines($driver,$lines,[Text.Encoding]::ASCII)
& cmd.exe /c $driver 2>&1 | Tee-Object -FilePath (Join-Path $stage 'run.log')
if ($LASTEXITCODE -ne 0) { throw "T025 real-top DIAG simulation failed; see $stage\run.log" }
Write-Host "PASS T025 real-top DIAG; log: $stage\run.log"
