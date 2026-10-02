"""M2 receipt review; a diagnostic fix is never an accepted implementation.

Run with --receipt pointing to the directory containing changes.json and code/.
All simulations and generated files stay in --output (default code/output).
The exit status reflects acceptance of the RECEIVED source, not a scratch copy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CAD = Path("D:/Gowin/oss-cad-suite")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--output", type=Path,
                        default=ROOT / "code/output/pitch_mod_minfix_reproduce_20261002")
    cfg = parser.parse_args()
    receipt, output = cfg.receipt.resolve(), cfg.output.resolve()
    if output == receipt or receipt in output.parents:
        parser.error("output must be separate from receipt")
    output.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment["PATH"] = str(CAD / "lib") + os.pathsep + str(CAD / "bin") + os.pathsep + environment["PATH"]
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    facts = {"acceptance_scope": "received source only", "checks": {}}
    manifest = json.loads((receipt / "changes.json").read_text(encoding="utf-8-sig"))
    hashes = []
    for row in manifest["files"]:
        actual = digest(receipt / row["path"])
        hashes.append({"path": row["path"], "expected": row["new_sha256"],
                       "actual": actual, "matches": actual == row["new_sha256"]})
    facts["manifest"] = hashes
    facts["checks"]["hashes"] = all(row["matches"] for row in hashes)
    stage = output / "execution"
    # Copying preserves the received bytes; tests may write model reports here.
    shutil.copytree(receipt / "code", stage / "code", dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    def run(name, command, cwd, timeout=120):
        log_path = output / (name + ".log")
        timed_out = False
        with log_path.open("w", encoding="utf-8", newline="\n") as log:
            try:
                result = subprocess.run(command, cwd=cwd, env=environment,
                                        stdout=log, stderr=subprocess.STDOUT,
                                        timeout=timeout, check=False)
                code = result.returncode
            except subprocess.TimeoutExpired:
                timed_out, code = True, None
        text = log_path.read_text(encoding="utf-8", errors="replace")
        if len(text) > 32000:
            text = text[:8000] + "\n[bounded review log: middle omitted]\n" + text[-8000:]
            log_path.write_text(text, encoding="utf-8", newline="\n")
        facts.setdefault("runs", {})[name] = {
            "exit": code, "timeout": timed_out, "command": list(map(str, command)),
            "log_sha256": digest(log_path)}
        print(f"{name}: exit={code}, timeout={timed_out}")
        return code, text

    model = stage / "code/model"
    for name in ("generate_pitch_mod_luts.py", "test_pitch_mod.py",
                 "generate_pitch_mod_vectors.py", "check_rtl_equivalence.py"):
        code, _ = run(name, [sys.executable, "-X", "utf8", str(model / name)], model)
        facts["checks"][name] = code == 0
    run("sender_runner", [sys.executable, "-X", "utf8",
                          str(stage / "code/scripts/run_pitch_mod_tests.py")], stage)
    facts["checks"]["sender_runner"] = facts["runs"]["sender_runner"]["exit"] == 0
    rom = model / "generated/pitch_mod"
    vector = rom / "pitch_mod_vectors.txt"
    rows = vector.read_text(encoding="ascii").splitlines()
    facts["generated_vector_count"] = len(rows)
    rtl = stage / "code/rtl/audio/pitch_mod_fcw.sv"
    tb = stage / "code/tb/audio/tb_pitch_mod_fcw.sv"
    compiler, simulator = str(CAD / "bin/iverilog.exe"), str(CAD / "bin/vvp.exe")

    def compile_source(name, source, bench=tb, top="tb_pitch_mod_fcw"):
        binary = output / (name + ".vvp")
        code, _ = run(name + "_compile", [compiler, "-g2012", "-s", top,
                                         "-o", str(binary), str(source), str(bench)], stage / "code")
        return code, binary

    code, binary = compile_source("received", rtl)
    facts["checks"]["received_compile"] = code == 0
    behavior_source = rtl
    declaration = "        automatic string oct_path, sub_path, lfo_path;"
    if code != 0 and declaration in rtl.read_text(encoding="utf-8"):
        text = rtl.read_text(encoding="utf-8").replace(declaration, "")
        text = text.replace("    initial begin", "    // synthesis translate_off\n"
                            "    string oct_path, sub_path, lfo_path;\n"
                            "    // synthesis translate_on\n    initial begin", 1)
        behavior_source = output / "declaration_compat_only.sv"
        behavior_source.write_text(text, encoding="utf-8", newline="\n")
        facts["declaration_compatibility_used"] = True
        code, binary = compile_source("compatibility", behavior_source)
    lut_args = ["+" + key + "=" + str(rom / name) for key, name in (
        ("OCT_PATH", "oct_ratio_q16.mem"), ("SUB_PATH", "sub_ratio_q16.mem"),
        ("LFO_PATH", "lfo_sine_q15.mem"))]
    if code == 0:
        def sim(name, executable, fixture, timeout=30):
            return run(name, [simulator, str(executable), *lut_args,
                              "+VECTORS=" + str(fixture)], stage / "code", timeout)
        status, _ = sim("received_behavior", binary, vector)
        facts["checks"]["received_behavior"] = status == 0
        empty = output / "empty.txt"
        empty.write_text("", encoding="ascii")
        status, _ = sim("empty_negative", binary, empty)
        facts["checks"]["empty_rejected"] = status is not None and status != 0
        malformed = output / "malformed.txt"
        malformed.write_text("BAD_LINE\n", encoding="ascii")
        status, _ = sim("malformed_negative", binary, malformed, timeout=1)
        facts["checks"]["malformed_exits_nonzero_without_timeout"] = status is not None and status != 0
        bench = ROOT / "code/tb/audio/tb_pitch_mod_noteon_contract_review.sv"
        code, contract_binary = compile_source("received_contract", behavior_source,
                                                bench, "tb_pitch_mod_noteon_contract_review")
        if code == 0:
            status, _ = sim("received_contract", contract_binary, vector)
            facts["checks"]["received_contract"] = status == 0
        # Scope-limited diagnostic experiment. NEVER write this into formal RTL.
        text = behavior_source.read_text(encoding="utf-8")
        old = ("        end else if (note_on) begin\n"
               "            lfo_phase <= 32'd0;           // ")
        if old in text:
            start = text.index(old)
            end = text.index("\n        end\n    end", start)
            text = text[:start] + ("        end else if (sample_enable) begin\n"
                   "            lfo_phase <= (note_on ? 32'd0 : lfo_phase) + LFO_INC;\n"
                   "        end else if (note_on) begin\n"
                   "            lfo_phase <= 32'd0;") + text[end:]
            text = text.replace("lfo_lut[lfo_phase[31:22]]",
                                "lfo_lut[note_on ? 10'd0 : lfo_phase[31:22]]")
            scratch = output / "noteon_diagnostic_only.sv"
            scratch.write_text(text, encoding="utf-8", newline="\n")
            code, scratch_binary = compile_source("diagnostic", scratch)
            if code == 0:
                status, _ = sim("diagnostic", scratch_binary, vector)
                facts["diagnostic_match"] = status == 0
                wrong = output / "wrong_expected.txt"
                first = rows[0].split()
                first[-1] = f"{int(first[-1], 16) ^ 1:08x}"
                wrong.write_text(" ".join(first) + "\n" + "\n".join(rows[1:]) + "\n", encoding="ascii")
                status, _ = sim("wrong_expected_negative", scratch_binary, wrong)
                facts["checks"]["wrong_expected_rejected"] = status is not None and status != 0
                short = output / "truncated_to_old_count.txt"
                short.write_text("\n".join(rows[:62273]) + "\n", encoding="ascii")
                status, _ = sim("old_count_truncation", scratch_binary, short)
                facts["checks"]["new_saturation_coverage_truncation_rejected"] = status is not None and status != 0
    facts["accepted"] = all(facts["checks"].values())
    facts["formal_integration_accepted"] = False  # Requires separate M2 hardware/contract review.
    (output / "review.json").write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8")
    print("RECEIVED ACCEPTANCE:", facts["accepted"])
    return 0 if facts["accepted"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
