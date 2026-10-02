"""M2 real-simulator receipt review. Exit1 while hardware/contract blockers remain.
No changes to received RTL/model/LUTs; output-only binaries/negative fixtures.
Usage: python -X utf8 code/scripts/review_pitch_mod_delivery.py --receipt DIR
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import shutil
import tempfile

ROOT = Path(__file__).resolve().parents[2]
CAD = Path("D:/Gowin/oss-cad-suite")


def run(command, stage, name):
    process = subprocess.run(command, cwd=stage, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=120)
    text = process.stdout + process.stderr
    (stage / (name + ".log")).write_text(text, encoding="utf-8", newline="\n")
    return process.returncode, text


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", required=True, type=Path)
    cfg = parser.parse_args()
    rec = cfg.receipt.resolve()
    stage = ROOT / "code/output/pitch_mod_M1_review_20261002/replay"
    stage.mkdir(parents=True, exist_ok=True)
    os.environ["PATH"] = str(CAD / "lib") + os.pathsep + str(CAD / "bin") + os.pathsep + os.environ["PATH"]
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    manifest = json.loads((rec / "changes.json").read_text(encoding="utf-8"))
    for row in manifest["files"]:
        if hashlib.sha256((rec / row["path"]).read_bytes()).hexdigest() != row["new_sha256"]:
            raise RuntimeError("Received manifest hash mismatch: " + row["path"])
    facts = {"manifest_hashes_valid": True, "scope": "real receipt sim not actual hardware acceptance"}
    work = Path(tempfile.mkdtemp(prefix="model_execution_", dir=stage))
    shutil.copytree(rec / "code/model", work / "code/model", ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
    # Sender model writes generated/model_report.json; run only on a working copy.
    for label in ["test_pitch_mod.py", "check_rtl_equivalence.py"]:
        code, text = run([sys.executable, "-X", "utf8", str(work / "code/model" / label)], stage, label)
        if code:
            print(text[-3000:]);return code
        print(text.strip())
    rtl = rec / "code/rtl/audio/pitch_mod_fcw.sv"
    tb = rec / "code/tb/audio/tb_pitch_mod_fcw.sv"
    exe = stage / "tb.vvp"
    code, text = run([str(CAD / "bin/iverilog.exe"), "-g2012", "-s", "tb_pitch_mod_fcw",
                      "-o", str(exe), str(rtl), str(tb)], stage, "compile")
    if code:
        print(text[-3000:]);return code
    rom = rec / "code/model/generated/pitch_mod"
    args = ["+" + key + "=" + str(rom / name) for key, name in [
            ("OCT_PATH", "oct_ratio_q16.mem"), ("SUB_PATH", "sub_ratio_q16.mem"), ("LFO_PATH", "lfo_sine_q15.mem")]]
    vectors = rom / "pitch_mod_vectors.txt"
    rows = vectors.read_text().splitlines()
    if len(rows) != 62273:
        raise RuntimeError("Unexpected delivered vector coverage")
    base_cmd = [str(CAD / "bin/vvp.exe"), str(exe)] + args
    code, text = run(base_cmd + ["+VECTORS=" + str(vectors)], stage, "actual_RTL")
    facts["real62273_vector_pass"] = code == 0 and "62273 samples matched golden model" in text and "FATAL" not in text
    print(text.strip())
    if not facts["real62273_vector_pass"]:
        return code or 1
    bad = stage / "wrong_expected_vectors.txt"
    columns = rows[0].split();columns[-1] = f"{int(columns[-1], 16) ^ 1:08x}"
    bad.write_text(" ".join(columns) + "\n" + "\n".join(rows[1:]) + "\n", encoding="ascii", newline="\n")
    code, text = run(base_cmd + ["+VECTORS=" + str(bad)], stage, "wrong_FCW_expected")
    facts["wrong_FCW_expected_rejected"] = code != 0 and "mismatched" in text
    empty = stage / "empty_vectors.txt"
    empty.write_text("", encoding="ascii")
    code, text = run(base_cmd + ["+VECTORS=" + str(empty)], stage, "empty_vectors")
    facts["sender_TB_empty_vectors_false_PASS"] = code == 0 and "0 samples matched" in text
    facts["LUT_initialization_inside_translate_off"] = all(
        needle in rtl.read_text(encoding="utf-8").split("    initial begin", 1)[1].split("    end", 1)[0]
        for needle in ["synthesis translate_off", "$readmemh(oct_path", "$readmemh(sub_path", "$readmemh(lfo_path"])
    facts["formal_integration_accepted"] = False
    facts["source_hashes"] = {str(p.relative_to(rec)): hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in [rtl, tb, vectors]}
    (stage / "review.json").write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8", newline="\n")
    if not facts["wrong_FCW_expected_rejected"]:
        raise RuntimeError("Negative expected mismatch not rejected")
    print("REAL VECTOR SIMULATION PASS; DELIVERED CANDIDATE NOT APPROVED FOR INTEGRATION")
    print("LUT synth transport/NoteOn off-sample semantics/verifier/contract fixes required; see M2 report")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
