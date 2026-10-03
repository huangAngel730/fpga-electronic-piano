"""Fresh, real RTL joint acceptance; no production modifications."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
TB = ROOT / "code/tb/board/m3_control_chain_acceptance"
SOURCES = ["code/rtl/common/audio_defs_pkg.sv", "code/rtl/common/uart_rx.sv",
           "code/rtl/common/performance_event_fifo.sv",
           "code/rtl/input/midi_input/midi_event_parser.sv",
           "code/rtl/input/midi_input/midi_input.sv",
           "code/rtl/board/performance_control_snapshot.sv",
           "code/tb/board/pitch_mod_pipeline_candidate/pitch_mod_fcw_pipeline.sv",
           "code/tb/board/pitch_mod_pipeline_candidate/pitch_mod_snapshot_pipeline.sv"]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(command, directory, env, timeout, label):
    result = subprocess.run(list(map(str, command)), cwd=directory, env=env,
                            capture_output=True, text=True, encoding="utf-8",
                            errors="replace", timeout=timeout)
    output = result.stdout + result.stderr
    (directory / f"{label}.log").write_text(output, encoding="utf-8", newline="\n")
    return result.returncode, output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cad", type=Path, default=Path("D:/Gowin/oss-cad-suite"))
    parser.add_argument("--timeout", type=int, default=240)
    parser.add_argument("--modelsim", type=Path, default=Path("E:/FPGA/Bpan/modelsim/modelsim1/win64"))
    parser.add_argument("--simulator", choices=("modelsim", "icarus"), default="modelsim")
    args = parser.parse_args()
    rootout = ROOT / "code/output"
    rootout.mkdir(exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix="m3_control_chain_", dir=rootout))
    print(f"Fresh evidence: {stage}", flush=True)
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join([str(args.cad / "lib"), str(args.cad / "bin"), env.get("PATH", "")])
    compiler, simulator = args.cad / "bin/iverilog.exe", args.cad / "bin/vvp.exe"
    if args.simulator == "modelsim":
        compiler, simulator = args.modelsim / "vlog.exe", args.modelsim / "vsim.exe"
    paths = [ROOT / rel for rel in SOURCES] + [TB / "tb_control_chain.sv", TB / "scoreboard.py", TB / "manifest.json", ROOT / "code/model/pitch_mod_model.py"]
    for name, source in zip(("oct.mem", "sub.mem", "lfo.mem"), ("oct_ratio_q16.mem", "sub_ratio_q16.mem", "lfo_sine_q15.mem")):
        path = ROOT / "code/model/generated/pitch_mod" / source
        if not path.is_file() or not path.stat().st_size:
            raise RuntimeError(f"missing/empty ROM {path}")
        shutil.copyfile(path, stage / name)
        paths.append(path)
    if any(not p.is_file() or not p.stat().st_size for p in paths):
        raise RuntimeError("missing/empty input")
    rc, version = run([compiler, "-version" if args.simulator == "modelsim" else "-V"], stage, env, 30, "tool_version")
    if rc:
        raise RuntimeError("cannot read simulator version")
    spec = importlib.util.spec_from_file_location("m3_chain_scoreboard", TB / "scoreboard.py")
    scoreboard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(scoreboard)
    evidence = {"source_sha256": {p.relative_to(ROOT).as_posix(): sha(p) for p in paths},
                "simulator_version": version, "seed": 20261003, "level": "L2", "mutants": {}}
    mutants = {
        "held_valid_lfo": (SOURCES[7], ".sample_enable(accepted&&request_occupied[lane])", ".sample_enable(request_valid&&request_occupied[lane])"),
        "live_base": ("code/tb/board/m3_control_chain_acceptance/tb_control_chain.sv", ".request_base_fcw(frozen_base)", ".request_base_fcw(live_base)"),
        "corrupt_tag": (SOURCES[7], "result_id<=held_id;", "result_id<=held_id^32'd1;"),
    }
    for label in ["positive", *mutants]:
        directory = stage / label
        directory.mkdir()
        for rom in ("oct.mem", "sub.mem", "lfo.mem"):
            shutil.copyfile(stage / rom, directory / rom)
        inputs = [ROOT / rel for rel in SOURCES] + [TB / "tb_control_chain.sv"]
        if label != "positive":
            rel, anchor, replacement = mutants[label]
            source = ROOT / rel
            content = source.read_text(encoding="utf-8")
            if content.count(anchor) != 1:
                raise RuntimeError(f"mutation anchor {label}")
            changed = directory / source.name
            changed.write_text(content.replace(anchor, replacement), encoding="utf-8", newline="\n")
            inputs[inputs.index(source)] = changed
        if args.simulator == "modelsim":
            rc, output = run([args.modelsim / "vlib.exe", "work"], directory, env, 30, "library")
            if rc:
                raise RuntimeError(output)
            compile_cmd = [compiler, "-sv", "-work", "work", *inputs]
            sim_cmd = [simulator, "-c", "-voptargs=+acc", "tb_control_chain", "-do", "onbreak {quit -code 1 -f}; run -all; quit -code 0 -f"]
        else:
            compile_cmd = [compiler, "-g2012", "-s", "tb_control_chain", "-o", "sim.vvp", *inputs]
            sim_cmd = [simulator, "sim.vvp"]
        rc, output = run(compile_cmd, directory, env, 60, "compile")
        if rc:
            raise RuntimeError(f"{label} did not compile: {output[-3000:]}")
        rc, output = run(sim_cmd, directory, env, args.timeout, "run")
        fatal = "FATAL:" in output or "** Fatal:" in output
        rejected = fatal
        reason = output
        if not rc and not fatal:
            try:
                coverage = scoreboard.check_capture(directory / "capture.txt", ROOT / "code/model/pitch_mod_model.py")
            except (AssertionError, ValueError) as exc:
                if label == "positive":
                    raise
                (directory / "scoreboard.log").write_text(str(exc), encoding="utf-8")
                rejected = True
                reason = str(exc)
        if label == "positive":
            if rc or fatal or output.count("PASS control chain RTL") != 1:
                raise RuntimeError(output[-3000:])
            evidence["coverage"] = coverage
            print(f"PASS joint accepted-event/Python FCW scoreboard: {coverage}", flush=True)
        else:
            required_reason = {"held_valid_lfo": "LFO advances exactly once", "live_base": "independent FCW oracle", "corrupt_tag": "result tag does not belong"}[label]
            if not rejected or required_reason not in reason:
                raise RuntimeError(f"behavioral mutant survived: {label}")
            evidence["mutants"][label] = "compiled, behavioral assertion rejected"
            print(f"PASS compiled mutant rejected: {label}", flush=True)
    evidence["logs_sha256"] = {p.relative_to(stage).as_posix(): sha(p) for p in stage.rglob("*.log")}
    (stage / "evidence.json").write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print("PASS A control-chain acceptance (no production audio/STA/board claim)")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, RuntimeError, AssertionError, ValueError, subprocess.TimeoutExpired) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        raise SystemExit(1)
