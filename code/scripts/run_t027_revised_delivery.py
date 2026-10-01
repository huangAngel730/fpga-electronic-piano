"""M2 real four-instance T027 revised receipt validation; no M1 code rewrite.
The model requires NumPy. Icarus executes the actual submitted oscillator.
"""
import argparse
import ast
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]


def execute(command, stage, label):
    result = subprocess.run(command, cwd=stage, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=120)
    text = result.stdout + result.stderr
    (stage / f"{label}.log").write_text(text, encoding="utf-8", newline="\n")
    return result.returncode, text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, default=ROOT,
                        help="Extracted M1 receipt, or current repository by default")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "code/output/t027_m1_revised_review_20261001/actual_review")
    args = parser.parse_args()
    receipt = args.receipt.resolve()
    stage = args.output.resolve()
    stage.mkdir(parents=True, exist_ok=True)
    import numpy as np
    spec = importlib.util.spec_from_file_location("receipt_timbre", receipt / "code/model/t027_timbre_model.py")
    model = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(model)
    evidence = {"scope": "M2 receipt validation, no formal DDS replacement",
                "checks": {}, "m1_tests": {}, "source_sha256": {}}
    paths = [receipt / ("code/model/" + name) for name in
             ["t027_timbre_model.py", "test_t027_timbre.py", "test_t027_rtl.py", "generate_t027_roms.py"]]
    paths += [receipt / "code/rtl/audio/timbre_oscillator.sv"]
    for source in paths:
        if not source.exists():
            continue
        evidence["source_sha256"][str(source.relative_to(receipt))] = hashlib.sha256(source.read_bytes()).hexdigest()
    for name in ["test_t027_timbre.py", "test_t027_rtl.py"]:
        source = receipt / "code/model" / name
        if not source.exists():
            evidence["m1_tests"][name] = {"received_test_not_imported": True}
            continue
        code, _ = execute([sys.executable, "-X", "utf8", str(source)], stage, name[:-3])
        tree = ast.parse(source.read_text(encoding="utf-8"))
        counts = {n.name: sum(isinstance(c, ast.Assert) for c in ast.walk(n))
                  for n in tree.body if isinstance(n, ast.FunctionDef) and n.name.startswith("test_")}
        evidence["m1_tests"][name] = {"exit_code": code, "assertion_counts": counts,
                                     "invokes_rtl_simulator": False}
    tables = [model.generate_sine_wavetable(), model.generate_triangle_wavetable()]
    rom_pass = True
    for name, table in zip(["sine", "triangle"], tables):
        original = receipt / f"code/model/generated/{name}_wavetable.hex"
        generated = model.generate_rom_hex(table, name.title()).encode()
        exact = original.read_bytes().replace(b"\r\n", b"\n") == generated
        bounded = len(table) == 1024 and int(min(table)) == -8192 and int(max(table)) == 8192
        rom_pass = rom_pass and exact and bounded
        (stage / original.name).write_bytes(generated)
        evidence["source_sha256"][str(original.relative_to(receipt))] = hashlib.sha256(original.read_bytes()).hexdigest()
    evidence["checks"]["ROM_reproduction_and_8192_endpoints"] = bool(rom_pass)
    compiler = shutil.which("iverilog")
    simulator = shutil.which("vvp")
    if not compiler or not simulator:
        raise RuntimeError("Icarus unavailable")
    os.environ["PATH"] = str(Path(compiler).parent.parent / "lib") + os.pathsep + os.environ["PATH"]
    tb = ROOT / "code/tb/board/tb_t027_revised_delivery.sv"
    evidence["M2_tb_sha256"] = hashlib.sha256(tb.read_bytes()).hexdigest()
    code, text = execute([compiler, "-g2012", "-s", "tb_t027_revised_delivery", "-o", str(stage / "tb.vvp"),
                          str(paths[-1]), str(tb)], stage, "compile")
    if code:
        print(text)
        return code
    command = [simulator, str(stage / "tb.vvp"), "+CAPTURE=" + str(stage / "waves.capture")]
    code, text = execute(command, stage, "RTL")
    evidence["RTL_result"] = [line for line in text.splitlines() if line.startswith("PASS tb_t027")]
    passed = code == 0 and len(evidence["RTL_result"]) == 1 and "FATAL" not in text
    evidence["checks"]["four_instance_RTL_scoreboard"] = passed
    print(text.strip())
    if not passed:
        (stage / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
        return code or 1
    code, text = execute(command[:-1] + ["+CAPTURE=" + str(stage / "negative.capture"), "+NEGATIVE_DATA"], stage, "negative_data")
    rejected = code != 0 and "PCM mismatch" in text
    evidence["checks"]["wrong_PCM_LSB_rejected"] = rejected
    blocks = {}
    current = None
    for line in (stage / "waves.capture").read_text().splitlines():
        parts = line.split()
        if parts[0] == "BEGIN":
            current = parts[1]
            blocks[current] = {"expected": int(parts[2]), "data": []}
        else:
            blocks[current]["data"].append(list(map(int, parts[1:])))
    coherent = np.asarray(blocks["four_timbres"]["data"], dtype=float)
    mixed = np.asarray(blocks["four_notes"]["data"], dtype=float)
    assert coherent.shape == (8192, 4) and mixed.shape == (32768, 4)
    spectrum = np.abs(np.fft.rfft(coherent, axis=0))
    ratios = [float(spectrum[24, i] / spectrum[8, i]) for i in range(4)]
    evidence["third_harmonic_to_fundamental"] = ratios
    evidence["checks"]["actual_four_independent_timbres"] = ratios[0] < 0.001 and ratios[2] < 0.001 and ratios[1] > 0.1 and ratios[3] > 0.1
    measured = []
    half = len(mixed) // 2
    window = np.hanning(half)
    n = np.arange(half)
    for i, note in enumerate([21, 69, 108, 57]):
        target = 440.0 * 2 ** ((note - 69) / 12)
        carrier = np.exp(-2j * np.pi * target * n / 48000)
        first = np.sum(mixed[:half, i] * window * carrier)
        second = np.sum(mixed[half:, i] * window * carrier)
        base = float(np.angle(second / first)) * 48000 / (2 * math.pi * half)
        branch = 48000 / half
        actual = base + round((target - base) / branch) * branch
        cents = 1200 * math.log2(actual / target)
        measured.append({"note": note, "target_hz": target, "actual_hz": actual, "error_cents": cents})
    evidence["actual_four_note_frequencies"] = measured
    evidence["checks"]["actual_frequency_error_below_one_cent"] = all(abs(row["error_cents"]) < 1 for row in measured)
    evidence["module_passed"] = all(evidence["checks"].values())
    evidence["M1_claimed_RTL_test_accepted"] = False
    evidence["actual_capture_sha256"] = hashlib.sha256((stage / "waves.capture").read_bytes()).hexdigest()
    (stage / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8", newline="\n")
    for name, passed in evidence["checks"].items():
        print(name, "PASS" if passed else "FAIL")
    print("Actual frequencies:", measured)
    print("Evidence:", stage / "evidence.json")
    return 0 if evidence["module_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
