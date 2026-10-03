"""G: real delay RTL + isolated transaction adapter, fail-closed ModelSim run."""
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

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
BENCH = ROOT / "code/tb/board/m3_delay_transaction_candidate"
CONTRACT = ROOT / "code/docs/evidence/M3_G_H_I_T028_contract_20261004.json"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_identity():
    identity = json.loads(CONTRACT.read_text(encoding="utf-8"))["readonly_source_sha256"]
    for relative, expected in identity.items():
        if sha(ROOT / relative) != expected:
            raise ValueError("readonly contract SHA changed: " + relative)
    return identity


def output_dir(path, prefix):
    output = ROOT / "code/output"
    output.mkdir(exist_ok=True)
    if path:
        path = path.resolve()
        if output.resolve() not in path.parents:
            raise ValueError("output must be new child of code/output")
        path.mkdir(parents=True, exist_ok=False)
        return path
    return Path(tempfile.mkdtemp(prefix=prefix, dir=output))


class Simulator:
    def __init__(self, out, tools):
        self.out, self.tools, self.runs = out, tools, {}
        for name in ("vlib", "vlog", "vsim"):
            if not (tools / (name + ".exe")).is_file():
                raise FileNotFoundError("ModelSim missing " + name)

    def run(self, label, command, cwd, timeout=300):
        command = list(map(str, command))
        try:
            result = subprocess.run(command, cwd=cwd, capture_output=True,
                                    timeout=timeout, check=False)
            data, code = result.stdout + result.stderr, result.returncode
        except subprocess.TimeoutExpired as error:
            data = (error.stdout or b"") + (error.stderr or b"") + b"\nRUNNER_TIMEOUT\n"
            code = 124
        log = self.out / (label + ".log")
        log.write_bytes(data)
        self.runs[label] = dict(command=command, cwd=str(cwd), exit_code=code, log_sha256=sha(log))
        print(label, code, flush=True)
        return code, data.decode("utf-8", errors="replace")

    def simulate(self, label, folder, sources, top, options=()):
        statuses = []
        transcript = ""
        commands = [
            [self.tools / "vlib.exe", "work"],
            [self.tools / "vlog.exe", "-sv", "+incdir+" + str(ROOT / "code/rtl/board"), *sources],
            [self.tools / "vsim.exe", "-c", "-onfinish", "stop", "-voptargs=+acc", top, *options,
             "-do", "onbreak {quit -code 1}; onerror {quit -code 1}; run -all; "
             f"if {{[examine -radix unsigned /{top}/test_passed] != 1}} "
             "{quit -code 1}; quit -code 0"]]
        for phase, command in zip(("library", "compile", "run"), commands):
            code, transcript = self.run(label + "_" + phase, command, folder)
            statuses.append(code)
            if code:
                break
        if statuses != [0, 0, 0] or "PASS" not in transcript or "Fatal:" in transcript:
            raise RuntimeError(f"{label} not a complete behavioral capture: {statuses}\n{transcript[-2000:]}")
        return statuses


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--output", type=Path)
    cli.add_argument("--modelsim-bin", type=Path, default=Path(os.environ.get(
        "MODELSIM_BIN", "E:/FPGA/Bpan/modelsim/modelsim1/win64")))
    args = cli.parse_args()
    out = output_dir(args.output, "m3_delay_transaction_")
    evidence = dict(scope="G isolated candidate L2/L3, no synthesis/production adoption", passed=False, cases=[])
    simulator = None
    try:
        evidence["readonly_sources"] = source_identity()
        oracle = load_module("g_oracle", BENCH / "oracle.py")
        simulator = Simulator(out, args.modelsim_bin)
        if simulator.run("tool_version", [args.modelsim_bin / "vsim.exe", "-version"], out, 30)[0]:
            raise RuntimeError("tool version failed")
        adapter = BENCH / "m3_delay_transaction_adapter.sv"
        sources = [ROOT / "code/rtl/audio/delay_effect.sv", adapter, BENCH / "tb_delay_transaction.sv"]
        evidence["sources"] = {p.relative_to(ROOT).as_posix(): sha(p) for p in sources + [BENCH / "oracle.py", Path(__file__)]}
        cases = [("depth16", 16, None, None, None), ("depth1024", 1024, None, None, None),
                 ("duplicate", 16, ".sample_enable(launch)", ".sample_enable(launch || state == WAIT_RAW)", "duplicate sample launch"),
                 ("wrong_id", 16, "id_q <= request_id;", "id_q <= request_id ^ 32'd1;", "result id corruption"),
                 ("ignore_cancel", 16, "end else if (cancel) begin", "end else if (1'b0) begin", "cancel/valid admission mismatch")]
        for name, depth, before, after, reason in cases:
            folder = out / name
            folder.mkdir()
            stimulus = oracle.vectors(depth)
            (folder / "vectors.txt").write_text("".join(" ".join(map(str, v)) + "\n" for v in stimulus), encoding="utf-8")
            selected = sources.copy()
            if before:
                text = adapter.read_text(encoding="utf-8")
                if text.count(before) != 1:
                    raise ValueError("mutation anchor: " + name)
                mutant = folder / adapter.name
                mutant.write_text(text.replace(before, after, 1), encoding="utf-8", newline="\n")
                selected[1] = mutant
            statuses = simulator.simulate(name, folder, selected, "tb_delay_transaction", [f"-gDEPTH={depth}"])
            capture = folder / "transaction.capture"
            verdict = dict(name=name, exit_codes=statuses, capture_sha256=sha(capture), passed=False)
            try:
                verdict["counts"] = oracle.check_capture(capture, stimulus, depth)
                verdict["passed"] = reason is None
            except AssertionError as error:
                verdict["rejection"] = str(error)
                verdict["passed"] = reason is not None and reason in str(error)
            evidence["cases"].append(verdict)
            if not verdict["passed"]:
                raise AssertionError("behavioral case failed: " + str(verdict))
        # Truncation, empty and unknown capture must not be accepted.
        negative = out / "invalid.capture"
        original = (out / "depth16/transaction.capture").read_text(encoding="utf-8")
        evidence["capture_negatives"] = []
        for label, text in [("empty", ""), ("truncated", original.rsplit("END", 1)[0]),
                            ("unknown", original.replace("C 0 ", "C X ", 1))]:
            negative.write_text(text, encoding="utf-8")
            try:
                oracle.check_capture(negative, oracle.vectors(16), 16)
                raise RuntimeError("bad capture accepted: " + label)
            except (AssertionError, ValueError, IndexError) as error:
                evidence["capture_negatives"].append(dict(name=label, rejected=str(error)))
        if source_identity() != evidence["readonly_sources"]:
            raise ValueError("readonly source changed during run")
        for relative, digest in evidence["sources"].items():
            if sha(ROOT / relative) != digest:
                raise ValueError("test source changed during run: " + relative)
        evidence["passed"] = True
    except (OSError, ValueError, RuntimeError, AssertionError, subprocess.SubprocessError) as error:
        evidence["error"] = str(error)
        print("FAIL", error)
    evidence["runs"] = simulator.runs if simulator else {}
    (out / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print("Evidence:", out / "evidence.json")
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
