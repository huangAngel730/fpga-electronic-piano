"""M2 checks an extracted T027 receipt without importing it into production.

Usage: python -X utf8 code/scripts/run_t027_delivery_review.py --receipt DIR
A rejected receipt returns 1. Compilation errors are never counted as RTL proof.
NumPy is needed by the delivered model; Icarus is needed for the receipt TB.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
DELIVERY_FILES = (
    "code/model/t027_timbre_model.py",
    "code/model/test_t027_timbre.py",
    "code/model/generate_t027_roms.py",
    "code/model/generated/sine_wavetable.hex",
    "code/model/generated/triangle_wavetable.hex",
    "code/rtl/audio/timbre_oscillator.sv",
)


def run(command, cwd, log):
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=90)
    text = result.stdout + result.stderr
    log.write_text(text, encoding="utf-8", newline="\n")
    return result.returncode, text


def words(path):
    values = [int(line.strip(), 16) for line in path.read_text().splitlines()
              if line.strip() and not line.lstrip().startswith("//")]
    return [value if value < 32768 else value - 65536 for value in values]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "code/output/t027_m1_review_20261001/review")
    args = parser.parse_args()
    receipt = args.receipt.resolve()
    stage = args.output.resolve()
    stage.mkdir(parents=True, exist_ok=True)
    evidence = {"receipt": str(receipt), "source_hashes": {}, "checks": {}}
    for name in DELIVERY_FILES:
        evidence["source_hashes"][name] = hashlib.sha256((receipt / name).read_bytes()).hexdigest()
    checks = evidence["checks"]
    code, _ = run([sys.executable, "-X", "utf8", str(receipt / DELIVERY_FILES[1])],
                  receipt, stage / "m1_model.log")
    checks["m1_claimed_suite"] = {"pass": code == 0, "exit_code": code}
    spec = importlib.util.spec_from_file_location("m1_t027_receipt", receipt / DELIVERY_FILES[0])
    model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model)
    generated = {"sine": model.generate_sine_wavetable(),
                 "triangle": model.generate_triangle_wavetable()}
    rom_match = True
    amplitude_ok = True
    harmonics = {}
    for name, table in generated.items():
        original = receipt / f"code/model/generated/{name}_wavetable.hex"
        regenerated = model.generate_rom_hex(table, name.title())
        target = stage / original.name
        target.write_text(regenerated, encoding="utf-8", newline="\n")
        exact = (original.read_bytes().replace(b"\r\n", b"\n") == target.read_bytes()
                 and len(table) == 1024)
        rom_match = rom_match and exact
        amplitude_ok = amplitude_ok and min(table) >= -8192 and max(table) <= 8192
        analysis = model.analyze_harmonic_content(table)
        harmonics[name] = {"length": len(table), "minimum": int(min(table)),
                          "maximum": int(max(table)), "rom_matches_generator": exact,
                          "thd_harmonics_2_through_10": float(analysis["thd"]),
                          "third_relative_to_fundamental": float(analysis["harmonics"][3]["normalized"])}
    evidence["waveforms"] = harmonics
    formal = words(ROOT / "code/model/generated/wavetables/sine_1024_8192.mem")
    evidence["formal_waveform"] = {"minimum": min(formal), "maximum": max(formal)}
    checks["rom_reproducibility"] = {"pass": rom_match}
    checks["frozen_waveform_amplitude"] = {"pass": bool(amplitude_ok)}
    checks["distinct_third_harmonic"] = {"pass": harmonics["triangle"]["third_relative_to_fundamental"] > 0.05}
    tree = ast.parse((receipt / DELIVERY_FILES[1]).read_text(encoding="utf-8"))
    assertion_counts = {node.name: sum(isinstance(child, ast.Assert) for child in ast.walk(node))
                        for node in tree.body if isinstance(node, ast.FunctionDef) and node.name.startswith("test_")}
    evidence["m1_test_assertion_counts"] = assertion_counts
    checks["behavior_tests_have_assertions"] = {"pass": all(assertion_counts.values())}
    iverilog = shutil.which("iverilog")
    vvp = shutil.which("vvp")
    if not iverilog or not vvp:
        raise RuntimeError("Icarus tools unavailable; no RTL conclusion")
    # oss-cad-suite tools need their bundled DLLs. This only changes child env.
    os.environ["PATH"] = str(Path(iverilog).resolve().parent.parent / "lib") + os.pathsep + os.environ["PATH"]
    code, compile_text = run([iverilog, "-g2012", "-s", "tb_t027_delivery_review",
                              "-o", str(stage / "tb.vvp"),
                              str(receipt / DELIVERY_FILES[-1]),
                              str(ROOT / "code/tb/board/tb_t027_delivery_review.sv")],
                             stage, stage / "compile.log")
    checks["rtl_compile"] = {"pass": code == 0, "exit_code": code}
    if code == 0:
        code, text = run([vvp, str(stage / "tb.vvp")], stage, stage / "rtl.log")
        result_lines = [line for line in text.splitlines() if line.startswith("RESULT ")]
        evidence["rtl_result"] = result_lines
        checks["rtl_behavior"] = {"pass": code == 0 and "PASS T027 receipt RTL" in text,
                                   "exit_code": code}
        for line in text.splitlines():
            if line.startswith(("ERROR", "RESULT", "FATAL")):
                print(line)
    else:
        print(compile_text)
        checks["rtl_behavior"] = {"pass": False, "reason": "compile failed, not behavioral evidence"}
    evidence["accepted"] = all(value["pass"] for value in checks.values())
    (stage / "evidence.json").write_text(json.dumps(evidence, indent=2, ensure_ascii=False) + "\n",
                                         encoding="utf-8", newline="\n")
    for name, value in checks.items():
        print(f"{name}: {'PASS' if value['pass'] else 'FAIL'}")
    print("Evidence:", stage / "evidence.json")
    return 0 if evidence["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
