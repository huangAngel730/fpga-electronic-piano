#!/usr/bin/env python3
"""T009 zero-slope RTL boundary and model trace gate, no model/RTL rewrite."""
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
STAGE = ROOT / "code/output/t009_zero_slope_rtl"

def main():
    STAGE.mkdir(parents=True, exist_ok=True)
    cad = Path(os.environ.get("YOSYSHQ_ROOT", "D:/Gowin/oss-cad-suite"))
    binary = STAGE / "zero.vvp"
    trace = STAGE / "zero.trace"
    quote = lambda value: '"' + str(value) + '"'
    commands = [
        'call ' + quote(cad / "environment.bat") + ' >nul',
        ' '.join(quote(value) for value in [
            cad / "bin/iverilog.exe", "-g2012", "-s", "tb_adsr_zero_slope",
            "-o", binary, ROOT / "code/rtl/audio/adsr_piano_envelope.sv",
            ROOT / "code/tb/audio/tb_adsr_zero_slope.sv",
        ]),
        ' '.join(quote(value) for value in [
            cad / "bin/vvp.exe", binary,
            "+TRACE=" + str(trace),
            "+VELOCITY_ROM_PATH=" + str(ROOT / "code/model/generated/wavetables/velocity_gain_rom.mem"),
        ]),
    ]
    bat = STAGE / "run.bat"
    bat.write_bytes(("@echo off\r\n" + "\r\nif errorlevel 1 exit /b 1\r\n".join(commands)
                     + "\r\nexit /b %errorlevel%\r\n").encode("ascii"))
    result = subprocess.run(["cmd.exe", "/c", str(bat)], cwd=STAGE,
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=60)
    (STAGE / "run.log").write_text(result.stdout + result.stderr, encoding="utf-8")
    for line in result.stdout.splitlines():
        if "PASS ADSR" in line or "FATAL" in line:
            print(line)
    if result.returncode or "PASS ADSR zero-slope" not in result.stdout:
        print(result.stderr, file=sys.stderr)
        return result.returncode or 1
    sys.path.insert(0, str(ROOT / "code/model"))
    from adsr_piano import PianoADSREnvelope
    state_ids = {"IDLE": 0, "ATTACK": 1, "DECAY": 2, "SUSTAIN": 3, "RELEASE": 4}
    model = None
    samples = 0
    max_error = 0
    for number, line in enumerate(trace.read_text(encoding="utf-8").splitlines(), 1):
        parts = line.split()
        if parts == ["R"]:
            model = PianoADSREnvelope()
        elif len(parts) == 2 and parts[0] == "N" and model is not None:
            model.note_on(int(parts[1]))
        elif len(parts) == 3 and parts[0] == "S" and model is not None:
            expected = model.step()
            actual, state = map(int, parts[1:])
            error = abs(actual - expected)
            max_error = max(max_error, error)
            if error > 2 or state != state_ids[model.state]:
                raise ValueError(f"row{number}: model={expected}/{model.state} RTL={actual}/{state}")
            samples += 1
        else:
            raise ValueError(f"Malformed trace row{number}")
    if samples != 2883:
        raise ValueError(f"Incomplete trace count{samples}")
    print(f"PASS zero-slope model trace samples={samples} max_delta={max_error} exact_states=True")
    return 0

if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, subprocess.TimeoutExpired) as error:
        print("FAIL ADSR zero-slope:", error, file=sys.stderr)
        raise SystemExit(1)