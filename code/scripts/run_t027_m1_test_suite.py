"""M2 fail-closed runner for received M1 T027 real TB + capture.
M1 received test_t027_rtl.py main verdict is not imported due to identified bugs.
Only Icarus is exercised here; original ModelSim logs are provenance, not rerun.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CAD = Path("D:/Gowin/oss-cad-suite")
TOP = "tb_t027_timbre_rtl"


def table(path):
    values = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip() or line.lstrip().startswith("//"):
            continue
        word = int(line.strip(), 16)
        if not 0 <= word <= 65535:
            raise ValueError("Invalid16 ROM word")
        values.append(word if word < 32768 else word - 65536)
    if len(values) != 1024 or max(values) != 8192 or min(values) != -8192:
        raise ValueError("ROM count or frozen amplitude wrong")
    return values


def verify(path, sine, triangle, flip_expected=False):
    phases, latched = [0] * 4, [0] * 4
    pipes = [[(0, 0, False)] * 4 for _ in range(4)]
    valid_outputs = latch_count = checks = cycles = 0
    previous_cycle = None
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.startswith("C "):
            raise ValueError("Non-capture line")
        fields = line.split()[1:]
        if len(fields) != 15:
            raise ValueError("Malformed capture row")
        cycle, reset, ticks, on, off, select, *tail = map(int, fields)
        fcws, outs, valid_mask = tail[:4], tail[4:8], tail[8]
        if previous_cycle is not None and cycle != previous_cycle + 1:
            raise ValueError("Missing/duplicate capture cycle")
        previous_cycle = cycle
        if not reset:
            phases, latched = [0] * 4, [0] * 4
            pipes = [[(0, 0, False)] * 4 for _ in range(4)]
        else:
            for lane in range(4):
                pipes[lane] = [(phases[lane] >> 22, latched[lane], bool(ticks & (1 << lane)))] + pipes[lane][:3]
                if ticks & (1 << lane):
                    phases[lane] = (phases[lane] + fcws[lane]) & 0xffffffff
                if on & (1 << lane):
                    latched[lane] = (select >> lane) & 1
                    latch_count += 1
        for lane in range(4):
            address, timbre, valid = pipes[lane][3]
            checks += 1
            if bool(valid_mask & (1 << lane)) != valid:
                raise AssertionError(f"valid mismatch cycle{cycle} lane{lane}")
            if not reset and outs[lane] != 0:
                raise AssertionError("reset output not zero")
            if valid:
                expected = (triangle if timbre else sine)[address]
                if flip_expected:
                    expected ^= 1
                if outs[lane] != expected:
                    raise AssertionError(f"PCM mismatch cycle{cycle} lane{lane} expected{expected} got{outs[lane]}")
                valid_outputs += 1
        cycles += 1
    if cycles < 10000 or valid_outputs < 40000 or latch_count < 20:
        raise ValueError("vacuous/incomplete capture")
    return {"Python_comparisons": checks, "valid_outputs": valid_outputs,
            "latch_events": latch_count, "capture_cycles": cycles}


def positive_verdict(code, log):
    return (code == 0 and len(re.findall(r"^PASS " + TOP + r"\b", log, re.M)) == 1
            and not re.search(r"FATAL|Fatal:|\*\* Error:|^FAIL", log, re.M))


def negative_verdict(code, log):
    return (code != 0 and re.search(r"FATAL:.*FAIL " + TOP + r" PCM mismatch", log) is not None
            and "PASS " + TOP not in log)


def execute(command, stage, name):
    r = subprocess.run(command, cwd=stage, capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=120)
    text = r.stdout + r.stderr
    (stage / (name + ".log")).write_text(text, encoding="utf-8", newline="\n")
    return r.returncode, text


def main():
    stage = ROOT / "code/output/t027_real_tests_M1_review_20261001/strict_M2"
    stage.mkdir(parents=True, exist_ok=True)
    paths = [ROOT / rel for rel in ["code/rtl/audio/timbre_oscillator.sv",
             "code/tb/audio/tb_t027_timbre_rtl.sv", "code/model/generated/sine_wavetable.hex",
             "code/model/generated/triangle_wavetable.hex", "code/model/test_t027_timbre.py"]]
    os.environ["PATH"] = str(CAD / "lib") + os.pathsep + str(CAD / "bin") + os.pathsep + os.environ["PATH"]
    for source in paths[:-1]:
        shutil.copyfile(source, stage / source.name)
    code, text = execute([sys.executable, "-X", "utf8", str(paths[-1])], stage, "model")
    if code or "通过：5/5" not in text:
        raise RuntimeError("Model test failed: " + text)
    code, text = execute([str(CAD / "bin/iverilog.exe"), "-g2012", "-s", TOP,
                          "-o", "tb.vvp", paths[0].name, paths[1].name], stage, "compile")
    if code:
        raise RuntimeError("RTL compile failed: " + text)
    command = [str(CAD / "bin/vvp.exe"), "tb.vvp"]
    code, text = execute(command + ["+CAPTURE=accepted.capture"], stage, "positive")
    if not positive_verdict(code, text):
        raise RuntimeError("Positive simulation verdict rejected: " + text)
    sine, triangle = table(stage / paths[2].name), table(stage / paths[3].name)
    facts = verify(stage / "accepted.capture", sine, triangle)
    print(text.strip())
    # A passing simulation/capture with injected post-simulation fatal must fail.
    if positive_verdict(code, text + "\nFATAL injected independent failure\n"):
        raise RuntimeError("Late simulator error accepted")
    if positive_verdict(1, text):
        raise RuntimeError("Nonzero exit accepted after PASS")
    # A negative with no CORRUPT cannot be counted as bias detection.
    if negative_verdict(code, text):
        raise RuntimeError("Uncorrupted positive counted as negative rejection")
    try:
        verify(stage / "accepted.capture", sine, triangle, flip_expected=True)
    except AssertionError as exc:
        if "PCM mismatch" not in str(exc):
            raise
    else:
        raise RuntimeError("Python negative comparator ignored1LSB error")
    neg_code, neg_text = execute(command + ["+CAPTURE=negative.capture", "+CORRUPT"], stage, "negative")
    if not negative_verdict(neg_code, neg_text):
        raise RuntimeError("Negative did not fail at requested PCM bias: " + neg_text)
    print("PASS real TB negative PCM1LSB rejected; bad verdict fixtures rejected")
    # capture failures/timeout/missing file do not count as a negative PASS.
    if negative_verdict(1, "FATAL: timeout") or negative_verdict(0, neg_text):
        raise RuntimeError("Unrelated/zero-exit failure accepted as negative")
    evidence = {"scope": "Independent dual-timbre M1 tests, not V1 piano or formal FCW/audio build",
        "models_passed": 5, "TB_result": [l for l in text.splitlines() if l.startswith("PASS " + TOP)],
        "capture_result": facts, "real_negative_return_code": neg_code,
        "strict_verdict_fixtures": ["late FATAL", "PASS plus nonzero exit", "negative disabled", "unrelated timeout", "zero exit"],
        "negative_detected": True, "source_sha256": {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths},
        "capture_sha256": hashlib.sha256((stage / "accepted.capture").read_bytes()).hexdigest(),
        "logs_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.glob("*.log")},
        "ModelSim_rerun": False, "hardware_or_Gowin_changed": False}
    (stage / "evidence.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    print("PASS Python capture:", facts)
    print("Evidence:", stage / "evidence.json")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
