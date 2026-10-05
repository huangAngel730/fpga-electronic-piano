#!/usr/bin/env python3
"""Build a reversible event-time FCW register experiment without editing formal RTL."""
from datetime import datetime, timezone
import json
import math
import os
import re
from pathlib import Path
import subprocess
import sys
import xml.etree.ElementTree as ET

from capture_t034_formal_build import (
    ROOT, PROJECT, active_sdc_commands, digest, git, project_inputs,
    validate_synthesis_against_pnr, verify_build)

OUT = ROOT / "code/output/t029_pitch_register"
SOURCE = ROOT / "code/rtl/common/simple_voice.sv"
TB = ROOT / "code/tb/board/tb_t029_pitch_trace.sv"


def candidate(text):
    old = '''    note_pitch #(
        .ACC_BITS       (ACC_BITS),
        .SAMPLE_RATE_HZ (SAMPLE_RATE_HZ)
    ) u_note_pitch (
        .note_number (note_q),
        .phase_step  (step_q)
    );'''
    new = '''    logic [ACC_BITS-1:0] incoming_step;
    note_pitch #(
        .ACC_BITS       (ACC_BITS),
        .SAMPLE_RATE_HZ (SAMPLE_RATE_HZ)
    ) u_note_pitch (
        .note_number (event_data.note_number),
        .phase_step  (incoming_step)
    );
    // Candidate only: compute step at the accepted Note On edge. The phase
    // accumulator uses the previous step on coincident event/sample edges.
    always_ff @(posedge clk or negedge rst_n) begin
        if (!rst_n) step_q <= ACC_BITS'(32'd39370534); // A4 (MIDI 69)
        else if (event_valid && event_data.event_type == EVENT_NOTE_ON)
            step_q <= incoming_step;
    end'''
    if text.count(old) != 1:
        raise ValueError("Source pitch instance changed; no candidate generated")
    return text.replace(old, new)


def prepare():
    paths = project_inputs()
    dirty = git("status", "--porcelain", "--untracked-files=no", "--",
                *[str(p.relative_to(ROOT)) for p in paths])
    if dirty:
        raise ValueError("Formal project inputs are dirty: " + dirty)
    OUT.mkdir(parents=True, exist_ok=True)
    generated = OUT / "candidate_simple_voice.sv"
    generated.write_text(candidate(SOURCE.read_text(encoding="utf-8")), encoding="utf-8")
    project = ET.parse(PROJECT).getroot()
    count = 0
    for element in project.findall("./FileList/File"):
        source = (PROJECT.parent / element.attrib["path"]).resolve()
        if source == SOURCE:
            element.set("path", generated.as_posix())
            count += 1
        else:
            element.set("path", source.as_posix())
    if count != 1:
        raise ValueError(f"Expected one original voice in project, got {count}")
    item = OUT / "t029_pitch_register.gprj"
    ET.ElementTree(project).write(item, encoding="utf-8", xml_declaration=True)
    return generated, item


def compare_traces(first, second):
    if len(first) != len(second):
        raise ValueError(f"Trace length differs: {len(first)} / {len(second)}")
    for index, (before, after) in enumerate(zip(first, second)):
        if before != after:
            raise ValueError(f"Candidate differs at cycle {index}: {before} / {after}")
    return len(first)


def traces(generated):
    tool = Path("D:/Gowin/oss-cad-suite")
    files = [ROOT / "code/rtl/common/audio_defs_pkg.sv",
             ROOT / "code/rtl/common/note_pitch.sv"]
    outputs = []
    for tag, voice in (("baseline", SOURCE), ("candidate", generated)):
        out = OUT / f"{tag}.vvp"
        log = OUT / f"{tag}.trace.log"
        # Environment batch provides Icarus DLL search paths.
        bat = OUT / f"{tag}.bat"
        lines = ["@echo off",f'call "{tool / "environment.bat"}" >nul',
                 f'"{tool / "bin/iverilog.exe"}" -g2012 -s tb_t029_pitch_trace -I "{ROOT / "code/rtl/common"}" -o "{out}" ' +
                 " ".join(f'"{p}"' for p in (*files, voice, TB)),
                 "if errorlevel 1 exit /b 1",
                 f'"{tool / "bin/vvp.exe"}" "{out}"',
                 "exit /b %errorlevel%"]
        bat.write_text("\r\n".join(lines) + "\r\n", encoding="ascii")
        with log.open("w", encoding="utf-8") as stream:
            rc = subprocess.run(["cmd.exe", "/c", str(bat)], cwd=OUT,
                                stdout=stream, stderr=subprocess.STDOUT, check=False).returncode
        if rc:
            raise ValueError(f"{tag} trace simulation failed: {log}")
        lines = [line for line in log.read_text(encoding="utf-8", errors="replace").splitlines()
                 if line.startswith("TRACE ")]
        if len(lines) < 1600 or "notes=128 retriggers=128 controls=128" not in log.read_text(encoding="utf-8", errors="replace"):
            raise ValueError(f"Missing complete {tag} simulation trace")
        outputs.append(lines)
    return compare_traces(*outputs)


def top_regress(generated):
    tool = Path("D:/Gowin/oss-cad-suite")
    paths = [path for path in project_inputs() if path.suffix == ".sv"]
    ordered = [ROOT / "code/rtl/common/audio_defs_pkg.sv"]
    ordered.extend(generated if path == SOURCE else path for path in paths
                   if path != ordered[0])
    passed = []
    for name in ("tb_key_to_tone", "tb_midi_top_integration"):
        tb = ROOT / "code/tb/board" / (name + ".sv")
        output = OUT / (name + ".vvp")
        log = OUT / (name + ".log")
        bat = OUT / (name + ".bat")
        script = ["@echo off", f'call "{tool / "environment.bat"}" >nul',
                  f'"{tool / "bin/iverilog.exe"}" -g2012 -s {name} '
                  f'-I "{ROOT / "code/rtl/common"}" -o "{output}" ' +
                  " ".join(f'"{path}"' for path in (*ordered,tb)),
                  "if errorlevel 1 exit /b 1",
                  f'"{tool / "bin/vvp.exe"}" "{output}"',
                  "exit /b %errorlevel%"]
        bat.write_text("\r\n".join(script) + "\r\n", encoding="ascii")
        with log.open("w", encoding="utf-8") as stream:
            rc = subprocess.run(["cmd.exe", "/c", str(bat)], cwd=OUT,
                                stdout=stream, stderr=subprocess.STDOUT, check=False).returncode
        content = log.read_text(encoding="utf-8", errors="replace")
        required = (r"15 PASS, 0 FAIL" if name == "tb_key_to_tone" else
                    r"PASS tb_midi_top_integration checks=7")
        if rc or re.search(required, content) is None:
            raise ValueError(f"Candidate top regression {name} failed: {log}")
        print("PASS candidate full-top",name)
        passed.append(log)
    return passed


def build(project):
    home = Path(os.environ.get("GOWIN_HOME", "D:/Gowin/Gowin_V1.9.11.03_Education/Gowin_V1.9.11.03_Education_x64"))
    executable = home / "IDE/bin/gw_sh.exe"
    if not executable.is_file():
        raise ValueError(f"Missing Gowin: {executable}")
    tcl = OUT / "run.tcl"
    tcl.write_text(f"open_project {{{project.as_posix()}}}\n"
                   "set_option -top_module electronic_piano_top\n"
                   "set_option -verilog_std sysv2017\nrun all\n", encoding="utf-8")
    log = OUT / "build.log"
    started = datetime.now(timezone.utc)
    with log.open("w", encoding="utf-8") as stream:
        rc = subprocess.run([str(executable), str(tcl)], cwd=OUT,
                            stdout=stream, stderr=subprocess.STDOUT, check=False).returncode
    if rc:
        raise ValueError(f"Candidate Gowin build failed ({rc}), see {log}")
    if 'Current top module is "electronic_piano_top"' not in log.read_text(encoding="utf-8", errors="replace") or \
            "Bitstream generation completed" not in log.read_text(encoding="utf-8", errors="replace"):
        raise ValueError("Candidate log lacks the expected top or bitstream completion")
    reports = OUT / "impl/pnr"
    timing = reports / "t029_pitch_register_tr_content.html"
    usage = reports / "t029_pitch_register.rpt.txt"
    synth = OUT / "impl/gwsynthesis/t029_pitch_register_syn.rpt.html"
    bitstream = reports / "t029_pitch_register.fs"
    for path in (timing, usage, synth, bitstream):
        if not path.is_file() or not path.stat().st_size or path.stat().st_mtime < started.timestamp()-2:
            raise ValueError(f"Missing/stale candidate Gowin output: {path}")
    data = verify_build(timing.read_text(encoding="utf-8"),
                        usage.read_text(encoding="utf-8"),
                        (ROOT / "code/constraints/electronic_piano.cst").read_text(encoding="utf-8"))
    data["synthesis_bsram"] = validate_synthesis_against_pnr(
        synth.read_text(encoding="utf-8"), data)
    data["active_sdc_commands"] = active_sdc_commands(
        timing.read_text(encoding="utf-8"),
        (ROOT / "code/constraints/audio_timing.sdc").read_text(encoding="utf-8"))
    return data, [log, timing, usage, synth, bitstream]


def source_fingerprints():
    paths = project_inputs()
    return {str(path.relative_to(ROOT)).replace("\\", "/"): digest(path) for path in paths}


def compare_baseline(fingerprints, candidate_info):
    baseline = json.loads((ROOT / "code/docs/evidence/t034_active_sdc_20260928.json")
                          .read_text(encoding="utf-8"))
    if fingerprints != baseline["input_sha256"]:
        raise ValueError("Cannot compare: formal source inputs differ from T034 baseline")
    original = float(baseline["timing_and_resources"]["fmax_mhz"].replace("(MHz)", ""))
    optimized = float(candidate_info["timing_and_resources"]["fmax_mhz"].replace("(MHz)", ""))
    if not math.isfinite(original) or not math.isfinite(optimized) or optimized <= original:
        raise ValueError(f"Candidate did not improve Fmax: {original} -> {optimized} MHz")
    if candidate_info["tool_and_part"] != baseline["tool_and_part"]:
        raise ValueError("Tool or target part differs from comparison baseline")
    if candidate_info["active_sdc_commands"] != baseline["active_sdc_commands"]:
        raise ValueError("Active SDC commands differ from comparison baseline")
    return {"formal_fmax_mhz": original, "candidate_fmax_mhz": optimized,
            "delta_mhz": round(optimized-original, 3),
            "formal_resources": baseline["timing_and_resources"]["resources"],
            "candidate_resources": candidate_info["timing_and_resources"]["resources"]}


def main():
    try:
        before = source_fingerprints()
        protected = [ROOT/"code/rtl/common/sine_table.svh", TB,
                     ROOT/"code/tb/board/tb_key_to_tone.sv", ROOT/"code/tb/board/tb_midi_top_integration.sv"]
        dependencies = {str(path.relative_to(ROOT)): digest(path) for path in protected}
        generated, project = prepare()
        count = traces(generated)
        print(f"PASS original/candidate exact cycle trace: {count} cycles")
        top_logs = top_regress(generated)
        candidate_info, artifacts = build(project)
        source_hashes = source_fingerprints()
        if source_hashes != before or any(digest(ROOT/path) != fingerprint
                                         for path, fingerprint in dependencies.items()):
            raise ValueError("Source or test dependencies changed during experiment")
        comparison = compare_baseline(source_hashes, candidate_info)
        result = {"scope": "M2 T029 isolated placeholder voice optimization experiment only",
                  "source_commit": git("rev-parse", "HEAD"), "cycle_trace_checks": count,
                  "source_sha256": source_hashes, "dependencies_sha256": dependencies,
                  "candidate_top_checks": {"tb_key_to_tone": 15, "tb_midi_top_integration": 7},
                  "baseline_evidence_sha256": digest(ROOT/"code/docs/evidence/t034_active_sdc_20260928.json"),
                  "candidate_sha256": digest(generated),
                  "artifact_sha256": {path.name: digest(path) for path in [*artifacts, *top_logs, OUT/"baseline.trace.log", OUT/"candidate.trace.log", project]},
                  "gate": candidate_info, "comparison": comparison,
                  "limitations": ["not applied to formal RTL", "candidate bitstream must not be programmed",
                                  "M1 formal DDS/ADSR and T010 polyphony not included"]}
        (OUT / "summary.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print("PASS candidate Gowin baseline comparison:", comparison)
        return 0
    except (OSError, ValueError, subprocess.CalledProcessError) as exc:
        print("FAIL isolated T029 experiment:", exc, file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
