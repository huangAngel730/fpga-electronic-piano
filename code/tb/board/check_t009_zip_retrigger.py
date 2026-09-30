#!/usr/bin/env python3
"""Review M1's offline T009 ZIP against repository or explicit ZIP candidate RTL.

Produces an ignored evidence directory, returning nonzero if any named
state has a model-to-RTL Q15 difference above two LSB. It never installs
package files into the project model or audio RTL directory.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import uuid
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = ROOT / "code/output/t009_zip_review"
MODEL_MEMBER = "code/model/adsr_piano.py"
TEST_MEMBER = "code/model/test_adsr_transition_limits.py"
RTL_MEMBER = "code/rtl/audio/adsr_piano_envelope.sv"
PHASES = ("ATTACK", "DECAY", "SUSTAIN", "RELEASE")


def fingerprint(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_member(z, name):
    matches = [item for item in z.infolist() if item.filename == name]
    if len(matches) != 1 or matches[0].file_size > 200_000:
        raise ValueError(f"Missing, duplicated, or oversized ZIP member: {name}")
    return z.read(matches[0])


def process(args, stage):
    stage.mkdir(parents=True)
    data = {}
    with ZipFile(args.zip) as archive:
        for member in (MODEL_MEMBER, TEST_MEMBER, RTL_MEMBER):
            data[member] = read_member(archive, member)
    model_path = stage / "adsr_piano.py"
    model_path.write_bytes(data[MODEL_MEMBER])
    (stage / "test_adsr_transition_limits.py").write_bytes(data[TEST_MEMBER])
    (stage / "audio_defs.py").write_bytes((ROOT / "code/model/audio_defs.py").read_bytes())
    repository_rtl = ROOT / RTL_MEMBER
    if args.use_zip_rtl:
        rtl = stage / "adsr_piano_envelope.sv"
        rtl.write_bytes(data[RTL_MEMBER])
    else:
        rtl = repository_rtl
        if data[RTL_MEMBER] != rtl.read_bytes():
            raise ValueError("ZIP RTL differs from current repository; pass --use-zip-rtl to review the candidate")
    log = stage / "model_test.log"
    result = subprocess.run([sys.executable, "-X", "utf8", "test_adsr_transition_limits.py"],
                            cwd=stage, capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=30)
    log.write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode or "通过: 6/6" not in result.stdout:
        raise ValueError(f"ZIP model tests fail, see {log}")
    sys.path.insert(0, str(stage))
    sys.modules.pop("adsr_piano", None)
    try:
        from adsr_piano import PianoADSREnvelope, velocity_to_gain  # noqa: PLC0415
        with (stage / "velocity.mem").open("w", encoding="ascii") as stream:
            stream.writelines(f"{velocity_to_gain(v):04x}\n" for v in range(1024))
        trace = stage / "rtl.trace"
        cad = Path(os.environ.get("YOSYSHQ_ROOT", "D:/Gowin/oss-cad-suite"))
        tb = ROOT / "code/tb/board/tb_t009_retrigger_matrix.sv"
        bat = stage / "matrix.bat"
        binary = stage / "matrix.vvp"
        lines = ["@echo off", f'call "{cad / "environment.bat"}" >nul',
                 f'"{cad / "bin/iverilog.exe"}" -g2012 -s tb_t009_retrigger_matrix '
                 f'-o "{binary}" "{rtl}" "{tb}"',
                 "if errorlevel 1 exit /b 1",
                 f'"{cad / "bin/vvp.exe"}" "{binary}" '
                 f'"+VELOCITY_ROM_PATH={stage / "velocity.mem"}" "+TRACE={trace}"',
                 "exit /b %errorlevel%"]
        bat.write_text("\r\n".join(lines) + "\r\n", encoding="ascii")
        result = subprocess.run(["cmd.exe", "/c", str(bat)], cwd=stage,
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=60)
        rtl_log = stage / "rtl_run.log"
        rtl_log.write_text(result.stdout + result.stderr, encoding="utf-8")
        if result.returncode or "PASS tb_t009_retrigger_matrix" not in result.stdout:
            raise ValueError(f"RTL trace failed, see {rtl_log}")
        model = None
        phase = None
        reports = {}
        trace_count = 0
        for line_no, line in enumerate(trace.read_text(encoding="utf-8").splitlines(), 1):
            fields = line.split()
            if fields == ["R"]:
                model = PianoADSREnvelope()
                phase = None
            elif len(fields) == 2 and fields[0] == "N" and model is not None:
                phase = model.state
                # Each section begins with a full velocity note from IDLE.
                phase = phase if int(fields[1]) == 1 else "INITIAL"
                model.note_on(int(fields[1]))
                reports.setdefault(phase, {"samples": 0, "max_delta": 0,
                                           "first_failure": None})
            elif fields == ["F"] and model is not None:
                model.note_off()
            elif len(fields) == 3 and fields[0] == "S" and model is not None and phase:
                actual = int(fields[1])
                expected = model.step()
                error = abs(actual - expected)
                trace_count += 1
                report = reports[phase]
                report["samples"] += 1
                report["max_delta"] = max(report["max_delta"], error)
                if error > 2 and report["first_failure"] is None:
                    report["first_failure"] = {"line": line_no, "sample": trace_count,
                                               "rtl": actual, "model": expected,
                                               "delta": error, "model_state": model.state,
                                               "rtl_state": int(fields[2])}
            else:
                raise ValueError(f"Invalid trace row {line_no}: {line}")
        if (not set(PHASES) <= reports.keys() or trace_count != 13425
                or any(reports[p]["samples"] != 241 for p in PHASES)):
            raise ValueError(f"Missing coverage: {reports}")
        return {"zip_sha256": fingerprint(args.zip),
                "m1_model_sha256": hashlib.sha256(data[MODEL_MEMBER]).hexdigest(),
                "repository_rtl_sha256": fingerprint(repository_rtl),
                "tested_rtl_sha256": fingerprint(rtl),
                "tested_rtl_source": "ZIP candidate" if args.use_zip_rtl else "repository",
                "repository_audio_defs_sha256": fingerprint(ROOT / "code/model/audio_defs.py"),
                "model_six_tests": "PASS", "sample_count": trace_count,
                "phase_comparison": {p: reports[p] for p in PHASES},
                "artifacts_sha256": {f.name: fingerprint(f) for f in (trace, log, rtl_log)},
                "passed": all(reports[p]["first_failure"] is None for p in PHASES)}
    finally:
        sys.modules.pop("adsr_piano", None)
        sys.path.remove(str(stage))


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("zip", type=Path)
    cli.add_argument("--use-zip-rtl", action="store_true",
                     help="Compare the ZIP model against its candidate RTL in the ignored staging area")
    args = cli.parse_args()
    stage = OUTPUT / uuid.uuid4().hex
    stage.parent.mkdir(parents=True, exist_ok=True)
    try:
        result = process(args, stage)
        (stage / "summary.json").write_text(json.dumps(result, ensure_ascii=False,
                                                        indent=2) + "\n", encoding="utf-8")
        for name, report in result["phase_comparison"].items():
            print(name, report)
        print("T009 ZIP review:", "PASS" if result["passed"] else "FAIL",
              "summary:", stage / "summary.json")
        return 0 if result["passed"] else 1
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print("FAIL T009 ZIP review:", error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
