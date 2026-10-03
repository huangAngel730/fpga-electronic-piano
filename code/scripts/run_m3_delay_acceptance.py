"""Explicit-SHA delay acceptance. Diagnostic runs validate the VERIFIER only."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TB = ROOT / "code/tb/audio/m3_delay_acceptance"
REQUIRED = {
    "module": "delay_effect", "pcm_bits": 24, "gain_bits": 15,
    "product_shift": 15, "rounding": "arithmetic_floor",
    "sum_policy": "shift_each_product_then_add", "feedback_policy": "pcm_plus_shifted_feedback",
    "saturation": "signed_pcm24", "latency_cycles": 2,
    "minimum_launch_spacing_cycles": 4,
    "reset": "async_output_valid_clear_and_logical_history_zero", "depths": [16, 1024],
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_contract(path, diagnostic):
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("contract must be a JSON object")
    for key, value in REQUIRED.items():
        if data.get(key) != value:
            raise ValueError(f"contract disagreement: {key}: expected {value!r}")
    if data.get("zero_delay_policy") not in ("pending", "modulo_depth_old"):
        raise ValueError("zero-delay definition unsupported; do not invent bypass/clear policy")
    expected_status = "diagnostic_not_accepted" if diagnostic else "corrected_candidate"
    if data.get("status") != expected_status:
        raise ValueError(f"contract status must be {expected_status!r}; diagnostic is not a corrected delivery")
    return data


def run(command, directory, env, timeout, label):
    result = subprocess.run(list(map(str, command)), cwd=directory, env=env,
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=timeout)
    output = result.stdout + result.stderr
    (directory / f"{label}.log").write_text(output, encoding="utf-8", newline="\n")
    return result.returncode, output


def rejected_text(code, text, reason):
    return code != 0 and "FATAL:" in text and reason in text


def wrapper(original, mutation):
    anchor = "module delay_effect"
    if original.count(anchor) != 1:
        raise ValueError("unique module mutation anchor missing")
    source = original.replace(anchor, "module m3_original_delay")
    if mutation == "wrong_pointer":
        anchor = "wr_ptr <= (wr_ptr + 1) & (DEPTH - 1);"
        if source.count(anchor) != 1:
            raise ValueError("write pointer mutation anchor changed; update verifier fixture explicitly")
        source = source.replace(anchor, "wr_ptr <= (wr_ptr + 2) & (DEPTH - 1);")
    valid = "assign pcm_valid=raw_valid;"
    pcm = "assign pcm_out=raw_pcm;"
    if mutation == "one_lsb":
        pcm = "assign pcm_out=raw_valid ? raw_pcm^24'd1 : raw_pcm;"
    if mutation == "late_valid":
        valid = "always @(posedge sys_clk or negedge sys_rst_n) if(!sys_rst_n)pcm_valid<=0;else pcm_valid<=raw_valid;"
    return source + f"""
module delay_effect #(parameter DEPTH=1024)(
 input sys_clk,sys_rst_n,sample_enable,input signed[23:0]pcm_in,
 input[15:0]delay_samples,input[14:0]dry_gain,wet_gain,feedback,
 output wire signed[23:0]pcm_out,output logic pcm_valid);
 wire signed[23:0]raw_pcm;wire raw_valid;
 m3_original_delay #(.DEPTH(DEPTH))dut(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),
 .sample_enable(sample_enable),.pcm_in(pcm_in),.delay_samples(delay_samples),
 .dry_gain(dry_gain),.wet_gain(wet_gain),.feedback(feedback),.pcm_out(raw_pcm),.pcm_valid(raw_valid));
 {pcm}
 {valid}
endmodule
"""


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rtl", type=Path, required=True)
    parser.add_argument("--contract", type=Path, required=True, help="explicit machine-readable acceptance contract JSON")
    parser.add_argument("--diagnostic-only", action="store_true", help="NEVER claim M1 corrected algorithm acceptance")
    parser.add_argument("--cad", type=Path, default=Path("D:/Gowin/oss-cad-suite"))
    parser.add_argument("--timeout", type=float, default=60)
    args = parser.parse_args()
    if args.timeout <= 0:
        raise ValueError("timeout must be positive")
    rtl, contract_path = args.rtl.resolve(strict=True), args.contract.resolve(strict=True)
    if not rtl.stat().st_size or not contract_path.stat().st_size:
        raise ValueError("empty source/contract")
    contract = validate_contract(contract_path, args.diagnostic_only)
    rootout = ROOT / "code/output"
    rootout.mkdir(exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="m3_delay_", dir=rootout))
    print(f"Fresh evidence: {stage}", flush=True)
    spec = importlib.util.spec_from_file_location("m3_independent_delay_vectors", TB / "vectors.py")
    vectors = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = vectors
    spec.loader.exec_module(vectors)
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join((str(args.cad / "lib"), str(args.cad / "bin"), env.get("PATH", "")))
    compiler, simulator = args.cad / "bin/iverilog.exe", args.cad / "bin/vvp.exe"
    rc, version = run([compiler, "-V"], stage, env, 30, "tool_version")
    if rc:
        raise RuntimeError("cannot read simulator version")
    evidence = {"rtl_path": str(rtl), "rtl_sha256": sha(rtl), "contract_path": str(contract_path),
                "contract_sha256": sha(contract_path), "contract": contract,
                "verifier_sha256": {p.relative_to(ROOT).as_posix(): sha(p) for p in [Path(__file__), TB / "vectors.py", TB / "tb_delay_acceptance.sv", TB / "manifest.json"]},
                "simulator_version": version, "seed": 20261003, "depths": {}, "mutants": {}, "input_rejections": {}}
    # Re-enter the public CLI with missing paths: fail BEFORE spawning a simulator.
    for label, bad_rtl, bad_contract in (("missing_rtl", stage / "absent.sv", contract_path),
                                       ("missing_contract", rtl, stage / "absent.json")):
        cmd = [sys.executable, Path(__file__), "--rtl", bad_rtl, "--contract", bad_contract]
        if args.diagnostic_only:
            cmd.append("--diagnostic-only")
        rc, text = run(cmd, stage, env, 30, label)
        if rc == 0 or "FAIL:" not in text:
            raise RuntimeError(f"CLI accepted {label}")
        evidence["input_rejections"][label] = "actual public CLI rejected missing file"
    wrong_timing = stage / "wrong_timing_contract.json"
    changed_contract = dict(contract, latency_cycles=3)
    wrong_timing.write_text(json.dumps(changed_contract), encoding="utf-8")
    cmd = [sys.executable, Path(__file__), "--rtl", rtl, "--contract", wrong_timing]
    if args.diagnostic_only:
        cmd.append("--diagnostic-only")
    rc, text = run(cmd, stage, env, 30, "wrong_contract_timing")
    if rc == 0 or "contract disagreement: latency_cycles" not in text:
        raise RuntimeError("mismatched E+2 timing contract accepted")
    evidence["input_rejections"]["wrong_contract_timing"] = "public CLI rejected latency3"
    for depth in (16, 1024):
        directory = stage / f"depth{depth}"
        directory.mkdir()
        # ASCII scratch source is an EXACT copy, including original defects.
        source = directory / "source.sv"
        source.write_bytes(rtl.read_bytes())
        rows, counters = vectors.generate(depth, contract["zero_delay_policy"])
        vector_file = directory / "vectors.txt"
        vectors.write_vectors(vector_file, rows)
        assert vectors.read_vectors(vector_file, depth) == rows
        command = [compiler, "-g2012", "-s", "tb_delay_acceptance", f"-Ptb_delay_acceptance.DEPTH={depth}", "-o", "sim.vvp", source, TB / "tb_delay_acceptance.sv"]
        rc, text = run(command, directory, env, 60, "compile")
        if rc:
            raise RuntimeError(f"positive compile: {text[-3000:]}")
        rc, text = run([simulator, "sim.vvp"], directory, env, args.timeout, "run")
        if rc or text.count("PASS delay independent cycle TB") != 1 or "FATAL:" in text:
            evidence["failed_depth"] = depth
            (stage / "evidence_failed.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
            raise RuntimeError(f"explicit original SHA failed (not patched): {text[-3000:]}")
        vectors.check_capture(directory / "capture.txt", rows)
        preserved_capture = directory / "positive_capture.txt"
        preserved_capture.write_bytes((directory / "capture.txt").read_bytes())
        counters["cycles"] = len(rows)
        counters["vectors_sha256"] = sha(vector_file)
        counters["positive_capture_sha256"] = sha(preserved_capture)
        evidence["depths"][str(depth)] = counters
        print(f"PASS depth{depth}: {counters}", flush=True)
        if depth != 16:
            continue
        # Three real, compilable behavioral faults, not syntax failures.
        for label, expected in (("one_lsb", "PCM/feedback history mismatch"),
                                ("late_valid", "valid timing/count mismatch"),
                                ("wrong_pointer", "PCM/feedback history mismatch")):
            changed = directory / f"{label}.sv"
            changed.write_text(wrapper(rtl.read_text(encoding="utf-8"), label), encoding="utf-8", newline="\n")
            mutant_cmd = command.copy()
            mutant_cmd[mutant_cmd.index(source)] = changed
            mutant_cmd[mutant_cmd.index("sim.vvp")] = f"{label}.vvp"
            rc, text = run(mutant_cmd, directory, env, 60, f"{label}_compile")
            if rc:
                raise RuntimeError(f"mutant {label} not compiled: {text[-1000:]}")
            rc, text = run([simulator, f"{label}.vvp"], directory, env, args.timeout, label)
            if not rejected_text(rc, text, expected):
                raise RuntimeError(f"behavioral mutant survived/failed unrelated: {label}: {text[-1000:]}")
            evidence["mutants"][label] = "compile success + behavioral rejection"
            print(f"PASS compiled mutant rejected: {label}", flush=True)
        # Guard tests run against the already-compiled ACTUAL positive RTL TB.
        bad_inputs = {"empty": "0\n", "malformed": "1\n1 1 BAD\n", "count_mismatch": "2\n" + " ".join(map(str, rows[0])) + "\n"}
        reasons = {"empty": "empty/malformed vector count", "malformed": "malformed record/count mismatch", "count_mismatch": "malformed record/count mismatch"}
        for label, content in bad_inputs.items():
            bad = directory / f"{label}.txt"
            bad.write_text(content, encoding="utf-8", newline="\n")
            try:
                vectors.read_vectors(bad, depth)
            except ValueError:
                pass
            else:
                raise AssertionError(f"Python accepted {label}")
            rc, text = run([simulator, "sim.vvp", f"+VECTORS={bad.name}"], directory, env, args.timeout, label)
            if not rejected_text(rc, text, reasons[label]):
                raise RuntimeError(f"TB accepted {label}: {text}")
            evidence["input_rejections"][label] = "Python and actual RTL TB rejected"
        rc, text = run([simulator, "sim.vvp", "+VECTORS=does_not_exist.txt"], directory, env, args.timeout, "missing_vectors")
        if not rejected_text(rc, text, "missing vector file"):
            raise RuntimeError("missing vectors accepted")
        evidence["input_rejections"]["missing_vectors"] = "actual TB rejected"
        for label, content in (("empty_capture", ""), ("capture_count", "0 0 000000\n0 0 000000\n"),
                               ("malformed_capture", "bad record\n")):
            bad_capture = directory / f"{label}.txt"
            bad_capture.write_text(content, encoding="utf-8")
            try:
                vectors.check_capture(bad_capture, [rows[0]])
            except ValueError:
                evidence["input_rejections"][label] = "independent capture parser rejected"
            else:
                raise RuntimeError(f"capture guard accepted {label}")
        bad = directory / "unknown_capture.txt"
        bad.write_text("0 1 xxxxxx\n", encoding="utf-8")
        try:
            vectors.check_capture(bad, [rows[0]])
        except ValueError:
            evidence["input_rejections"]["unknown_capture"] = "independent capture parser rejected"
        else:
            raise RuntimeError("X capture accepted")
        # Explicit X injection at the DUT output validates the SV guard as well.
        x_source = directory / "unknown_output.sv"
        changed = wrapper(rtl.read_text(encoding="utf-8"), "none")
        changed = changed.replace("assign pcm_out=raw_pcm;", "assign pcm_out=raw_valid ? 24'hxxxxxx : raw_pcm;")
        x_source.write_text(changed, encoding="utf-8", newline="\n")
        x_cmd = command.copy(); x_cmd[x_cmd.index(source)] = x_source
        x_cmd[x_cmd.index("sim.vvp")] = "unknown_output.vvp"
        rc, text = run(x_cmd, directory, env, 60, "unknown_compile")
        if rc:
            raise RuntimeError("X guard fixture not compiled")
        rc, text = run([simulator, "unknown_output.vvp"], directory, env, args.timeout, "unknown_output")
        if not rejected_text(rc, text, "unknown X output"):
            raise RuntimeError("unknown RTL output accepted")
        evidence["input_rejections"]["unknown_output"] = "actual TB rejected X output"
        # Force an actual simulator wait, then require subprocess timeout rejection.
        hang_tb = directory / "hang.sv"
        hang_tb.write_text("module hang;reg clk=0;always #10 clk=~clk;endmodule\n", encoding="utf-8")
        rc, text = run([compiler, "-s", "hang", "-o", "hang.vvp", hang_tb], directory, env, 60, "hang_compile")
        if rc:
            raise RuntimeError("timeout guard fixture not compiled")
        try:
            run([simulator, "hang.vvp"], directory, env, 0.2, "hang")
        except subprocess.TimeoutExpired:
            evidence["input_rejections"]["timeout"] = "actual nonterminating simulator killed/rejected"
        else:
            raise RuntimeError("timeout guard did not reject")
        print("PASS fail-closed vector/capture/unknown/timeout guards", flush=True)
    evidence["result"] = "VERIFIER_READY_ALGORITHM_PENDING" if args.diagnostic_only else "CORRECTED_CANDIDATE_L2_PASS_PENDING_M2_REVIEW"
    evidence["zero_delay"] = "pending; no zero-delay acceptance claim" if contract["zero_delay_policy"] == "pending" else "explicit modulo_depth_old tested"
    evidence["logs_sha256"] = {p.relative_to(stage).as_posix(): sha(p) for p in stage.rglob("*.log")}
    (stage / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(f"PASS {evidence['result']}; {evidence['zero_delay']}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, ValueError, AssertionError, subprocess.TimeoutExpired) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
