# -----------------------------------------------------------------------------
# run_t007_sim.ps1
# T007 (top-level bring-up) regression simulation script.
#
# Usage (run from repository root):
#   .\code\scripts\run_t007_sim.ps1
#
# Compiles and runs the top-level self-check testbench, which covers:
#   - pa_en must be 1 (amp off) while reset is asserted  [power-on pop guard]
#   - pa_en must go to 0 after reset release
#   - BCLK = 3.072 MHz, LRCK = 48 kHz, strictly 64:1
#   - DIN decodes to a 440 Hz sine at the expected amplitude
#   - left/right channels identical
#   - uart_tx idle level high
#
# Notes:
#   1. This script loads the FPGA tool environment itself and does not rely on
#      the caller having set PATH.
#   2. Sources are staged into an ASCII-only temp directory before compiling.
#      The repository path contains non-ASCII characters, and PowerShell
#      truncates non-ASCII characters when passing arguments to native exes.
#   3. This file is deliberately kept ASCII-only. Windows PowerShell 5.1 reads
#      UTF-8 files without a BOM as ANSI, which corrupts non-ASCII comments and
#      can break parsing.
#   4. Compile and run are driven through a generated .bat file instead of
#      calling iverilog.exe directly. Reason: in Windows PowerShell 5.1 any
#      output on a native program's stderr raises NativeCommandError, which
#      aborts the script even when $ErrorActionPreference is lowered, and
#      iverilog always prints at least the timescale warning. Driving the tools
#      from cmd.exe sidesteps that entirely. This is the same approach used by
#      run_t005_sim.ps1.
#   5. The .bat runs oss-cad-suite environment.bat first. Without it the
#      binaries fail to start with 0xC0000139 (entry point not found).
#   6. Exit code: 0 if all tests PASS, 1 if any test FAILs or a tool error occurs.
# -----------------------------------------------------------------------------

$repoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
Set-Location $repoRoot

$iverilog = "D:\Gowin\oss-cad-suite\bin\iverilog.exe"
$vvp      = "D:\Gowin\oss-cad-suite\bin\vvp.exe"
$envBat   = "D:\Gowin\oss-cad-suite\environment.bat"

foreach ($tool in @($iverilog, $vvp, $envBat)) {
    if (-not (Test-Path -LiteralPath $tool)) {
        Write-Host "Missing tool: $tool" -ForegroundColor Red
        exit 1
    }
}

# Top-level directory names are ASCII since the rename (the old CJK "code"
# directory is now plain "code").
$segRtl = "code\rtl"
$segTb  = "code\tb"

$tests = @(
    @{
        Name = "tb_electronic_piano_top"
        # Ordered list of files to compile AND stage. Header files listed here are
        # staged but must NOT be passed to iverilog as compilation units, so the
        # .svh entries are kept in a separate list below.
        #
        # T020 added the event-driven skeleton: key_debounce -> key_event_source
        # -> simple_voice, plus note_pitch (note number -> phase step). The top
        # level now instantiates them, so they must be compiled in dependency
        # order: packages first, then leaf modules, then the top.
        # T021 (2026-09-15) replaced the M2 placeholder key_debounce with M3's
        # button_debouncer in rtl/input/.
        # D022 (2026-09-15): perf_event_pkg was deleted (merged into
        # audio_defs_pkg) and key_event_source was replaced by M3's
        # button_event_converter. rtl/input/ now uses one subdirectory per module.
        Src  = @("$segRtl\common\audio_defs_pkg.sv",
                 "$segRtl\common\reset_sync.sv",
                 "$segRtl\common\sample_tick_gen.sv",
                 "$segRtl\input\button_debouncer\button_debouncer.sv",
                 "$segRtl\common\note_pitch.sv",
                 "$segRtl\input\button_event_converter\button_event_converter.sv",
                 "$segRtl\common\performance_event_fifo.sv",
                 "$segRtl\common\system_status_counters.sv",
                 "$segRtl\common\uart_tx.sv",
                 "$segRtl\board\uart_status_reporter.sv",
                 "$segRtl\common\uart_rx.sv",
                 "$segRtl\input\midi_input\midi_event_parser.sv",
                 "$segRtl\input\midi_input\midi_input.sv",
                 "$segRtl\common\simple_voice.sv",
                 "$segRtl\audio_out\i2s_tx.sv",
                 "$segRtl\audio_out\pcm_frame_buffer.sv",
                 "$segRtl\board\electronic_piano_top.sv",
                 "$segTb\board\tb_electronic_piano_top.sv")
        # Included headers: staged into the same tree so relative `include works,
        # but not compiled directly. See the staging comment below.
        # Registering sine_table.svh here also puts common/ on the iverilog
        # include search path, which is what simple_voice.sv needs for its
        # plain `include "sine_table.svh"`.
        Inc  = @("$segRtl\common\sine_table.svh")
    }
    @{
        # T021: M3's button debouncer (replaced the M2 placeholder 2026-09-15).
        Name = "tb_button_debouncer"
        Src  = @("$segRtl\input\button_debouncer\button_debouncer.sv",
                 "$segTb\input\tb_button_debouncer.sv")
    }
    @{
        Name = "tb_note_pitch"
        Src  = @("$segRtl\common\note_pitch.sv",
                 "$segTb\common\tb_note_pitch.sv")
    }
    @{
        # T022: M3's button-to-performance-event converter, which replaced the M2
        # placeholder key_event_source under D022 (2026-09-15). Compiles together
        # with audio_defs_pkg because that package is now the single definition
        # site of performance_event_t.
        Name = "tb_button_event_converter"
        Src  = @("$segRtl\common\audio_defs_pkg.sv",
                 "$segRtl\input\button_event_converter\button_event_converter.sv",
                 "$segTb\input\tb_button_event_converter.sv")
    }
    @{
        # T020/T014 end-to-end: key press -> event -> voice -> PCM -> I2S pins -> pitch.
        # This is the acceptance test for the event-driven skeleton.
        Name = "tb_key_to_tone"
        Src  = @("$segRtl\common\audio_defs_pkg.sv",
                 "$segRtl\common\reset_sync.sv",
                 "$segRtl\common\sample_tick_gen.sv",
                 "$segRtl\input\button_debouncer\button_debouncer.sv",
                 "$segRtl\common\note_pitch.sv",
                 "$segRtl\input\button_event_converter\button_event_converter.sv",
                 "$segRtl\common\performance_event_fifo.sv",
                 "$segRtl\common\system_status_counters.sv",
                 "$segRtl\common\uart_tx.sv",
                 "$segRtl\board\uart_status_reporter.sv",
                 "$segRtl\common\uart_rx.sv",
                 "$segRtl\input\midi_input\midi_event_parser.sv",
                 "$segRtl\input\midi_input\midi_input.sv",
                 "$segRtl\common\simple_voice.sv",
                 "$segRtl\audio_out\i2s_tx.sv",
                 "$segRtl\audio_out\pcm_frame_buffer.sv",
                 "$segRtl\board\electronic_piano_top.sv",
                 "$segTb\board\tb_key_to_tone.sv")
        Inc  = @("$segRtl\common\sine_table.svh")
    }
    @{
        Name = "tb_midi_top_integration"
        Src  = @("$segRtl\common\audio_defs_pkg.sv",
                 "$segRtl\common\reset_sync.sv",
                 "$segRtl\common\uart_rx.sv",
                 "$segRtl\input\button_debouncer\button_debouncer.sv",
                 "$segRtl\input\button_event_converter\button_event_converter.sv",
                 "$segRtl\input\midi_input\midi_event_parser.sv",
                 "$segRtl\input\midi_input\midi_input.sv",
                 "$segRtl\common\performance_event_fifo.sv",
                 "$segRtl\common\system_status_counters.sv",
                 "$segRtl\common\uart_tx.sv",
                 "$segRtl\board\uart_status_reporter.sv",
                 "$segRtl\common\note_pitch.sv",
                 "$segRtl\common\simple_voice.sv",
                 "$segRtl\audio_out\i2s_tx.sv",
                 "$segRtl\audio_out\pcm_frame_buffer.sv",
                 "$segRtl\board\electronic_piano_top.sv",
                 "$segTb\board\tb_midi_top_integration.sv")
        Inc  = @("$segRtl\common\sine_table.svh")
    }
)

$failed = @()
# Unique staging directory per run.
#
# A FIXED name ($env:TEMP\t007_sim) was used until 2026-09-18. Because this
# script is called by check_repo.ps1, any second run started while the first
# was still compiling (another developer, another AI agent on the same host, or
# a manual run overlapping the gate) deleted and recreated the directory the
# first run was compiling in. Observed symptoms, both on identical sources:
#   - "The process cannot access the file because it is being used by another
#      process" while writing the driver .bat, and
#   - "Compile failed, no simulation artifact produced" because the .vvp of
#      the first run had just been deleted by the second run's cleanup.
# Both made the push gate report a false FAIL. A GUID suffix removes the shared
# state; the same idiom is already used by run_midi_input_sim.ps1,
# run_t022_sim.ps1 and run_t026_tests.ps1.
$stageRoot = Join-Path $env:TEMP ("t007_sim_" + [guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Force -Path $stageRoot | Out-Null

foreach ($test in $tests) {
    $name = $test.Name
    if ($name -in @('tb_electronic_piano_top','tb_key_to_tone','tb_midi_top_integration')) {
        & python -X utf8 (Join-Path $PSScriptRoot 'run_t025_top_stat.py') --top $name --tb ('code/tb/board/' + $name + '.sv')
        if ($LASTEXITCODE -ne 0) { $failed += $name }
        continue
    }
    $out  = Join-Path $stageRoot "$name.vvp"
    $log  = Join-Path $stageRoot "$name.log"
    $bat  = Join-Path $stageRoot "$name.bat"

    Write-Host ""
    Write-Host ("=" * 60)
    Write-Host "Compile and run $name"
    Write-Host ("=" * 60)

    # Stage sources into the ASCII-only temp directory.
    #
    # The directory layout is preserved (common/, audio_out/, board/, tb/) rather
    # than flattening every file to src_N.sv. Reason: electronic_piano_top.sv
    # does `include "../common/sine_table.svh"`, and a relative include only
    # resolves if the includer's own directory and its sibling are reproduced.
    # Flattening broke that include with:
    #   Include file ../common/sine_table.svh not found
    $staged = @()
    foreach ($src in $test.Src) {
        $rel = $src -replace '^code\\', ''
        $dst = Join-Path $stageRoot $rel
        $dstDir = Split-Path -Parent $dst
        if (-not (Test-Path -LiteralPath $dstDir)) {
            New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
        }
        Copy-Item -LiteralPath (Join-Path $repoRoot $src) -Destination $dst -Force
        $staged += $dst
    }

    # Stage included headers into the same tree, but keep them out of $staged:
    # iverilog treats a directly-listed .svh as a compilation unit and would
    # choke on it. They only need to exist on disk for `include to find them.
    if ($test.ContainsKey('Inc')) {
        foreach ($inc in $test.Inc) {
            $rel = $inc -replace '^code\\', ''
            $dst = Join-Path $stageRoot $rel
            $dstDir = Split-Path -Parent $dst
            if (-not (Test-Path -LiteralPath $dstDir)) {
                New-Item -ItemType Directory -Force -Path $dstDir | Out-Null
            }
            Copy-Item -LiteralPath (Join-Path $repoRoot $inc) -Destination $dst -Force
        }
    }

    # `include search path.
    #
    # iverilog resolves `include relative to the CURRENT WORKING DIRECTORY, not
    # relative to the file containing the directive. Verified with a minimal
    # repro: a\main.sv containing `include "../b/inc.svh"` fails with
    #     Include file ../b/inc.svh not found
    # even though b\inc.svh exists next to it. Passing -I for each staged
    # directory makes the lookup work regardless of where the .bat runs from.
    $incDirs = @()
    if ($test.ContainsKey('Inc')) {
        foreach ($inc in $test.Inc) {
            $rel = $inc -replace '^code\\', ''
            $dir = Split-Path -Parent (Join-Path $stageRoot $rel)
            if ($incDirs -notcontains $dir) { $incDirs += $dir }
        }
    }
    $incFlags = ($incDirs | ForEach-Object { "-I `"$_`"" }) -join " "

    $srcList = ($staged -join " ")

    # Build the driver batch file.
    $batLines = @(
        "@echo off",
        "call `"$envBat`" >nul 2>&1",
        "`"$iverilog`" -g2012 -Wall $incFlags -o `"$out`" $srcList > `"$log`" 2>&1",
        "echo IVERILOG_EXIT=%ERRORLEVEL%",
        "if not exist `"$out`" (echo COMPILE_FAILED & exit /b 1)",
        "`"$vvp`" `"$out`" >> `"$log`" 2>&1",
        "echo VVP_EXIT=%ERRORLEVEL%"
    )
    $batLines | Out-File -FilePath $bat -Encoding ascii

    $driverOut = cmd /c "`"$bat`"" 2>&1

    # Compile failure is judged by the artifact, not by stderr content.
    if (-not (Test-Path -LiteralPath $out)) {
        Write-Host "  Compile failed, no simulation artifact produced" -ForegroundColor Red
        if (Test-Path -LiteralPath $log) {
            Get-Content -LiteralPath $log -Encoding UTF8 | ForEach-Object { "  $_" }
        }
        $failed += $name
        continue
    }

    $lines = @()
    if (Test-Path -LiteralPath $log) {
        $lines = Get-Content -LiteralPath $log -Encoding UTF8
    }
    $lines | ForEach-Object { "  $_" }

    # Failure detection must cover every marker form the testbenches in this
    # repo actually emit. Matching only "[FAIL]" was NOT sufficient:
    # tb_button_debouncer, tb_button_event_converter, tb_key_event_source and
    # tb_note_pitch report failures as "ERROR:" / "FAIL:", and every timeout path
    # uses "FAIL:" as well, so a failure in any of those could never be reported
    # as FAIL by this script. Fixed 2026-09-15 (see the verification log).
    #
    # The patterns are deliberately narrow to avoid false positives. In
    # particular the per-testbench summary line "N PASS, M FAIL" contains the
    # word FAIL even on a completely clean run, so a bare word match is wrong.
    # Accepted markers:
    #   [FAIL] <item>       item-level failure
    #   FAIL: <text>        summary, timeout and named-item failure
    #   TESTBENCH FAILED    tb_key_event_source / tb_note_pitch summary
    #   >>> ...FAIL         tb_electronic_piano_top / tb_key_to_tone banner
    #   FAIL                whole line, tb_audio_defs_pkg style
    $failPattern = '\[FAIL\]|FAIL:|TESTBENCH FAILED|>>>.*FAIL|^\s*FAIL\s*$'
    $failLines = @($lines | Where-Object { $_ -match $failPattern })
    $failCount = $failLines.Count

    if ($failCount -gt 0) {
        Write-Host "  >>> $name FAIL ($failCount checks failed)" -ForegroundColor Red
        $failed += $name
    } else {
        Write-Host "  >>> $name PASS" -ForegroundColor Green
    }
}

Write-Host ""
Write-Host ("=" * 60)
if ($failed.Count -eq 0) {
    Write-Host "ALL PASS" -ForegroundColor Green
    exit 0
} else {
    Write-Host ("FAILED: " + ($failed -join ", ")) -ForegroundColor Red
    exit 1
}
