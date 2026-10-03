"""Compile a frozen full-parser miter and independent RR selector RTL test.

No Gowin/PnR/STA claim. ModelSim logs and hashes are retained in code/output.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[2]
BASELINE = "3d6430e"
PARSER = "code/rtl/input/midi_input/midi_event_parser.sv"
FROZEN_SHA = "cfd4c33e91ba06a73c89dedb66b8636dc0c1bd1778ae454714325207424c28c4"
TB = "code/tb/input/tb_midi_scheduler_equivalence.sv"


def sha(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def command_run(command, cwd, log, timeout=300):
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, timeout=timeout)
        output = result.stdout + result.stderr
        code = result.returncode
    except subprocess.TimeoutExpired as error:
        output = (error.stdout or b"") + (error.stderr or b"") + b"\nRUNNER_TIMEOUT\n"
        code = 124
    log.write_bytes(output)
    return code, output.decode("utf-8", errors="replace")


def main():
    cli = argparse.ArgumentParser(description=__doc__)
    cli.add_argument("--modelsim-bin", type=Path, default=Path(os.environ.get(
        "MODELSIM_BIN", "E:/FPGA/Bpan/modelsim/modelsim1/win64")))
    cli.add_argument("--output", type=Path, help="new directory under code/output")
    args = cli.parse_args()
    output_root = ROOT / "code/output"
    if args.output:
        output = args.output.resolve()
        if output_root.resolve() not in output.parents:
            cli.error("--output must be a new child of code/output")
        output.mkdir(parents=True, exist_ok=False)
    else:
        output = Path(tempfile.mkdtemp(prefix="midi_scheduler_equivalence_", dir=output_root))
    evidence = {"level": "L2 RTL simulation only; whole-system STA pending M2",
                "baseline_commit": BASELINE, "baseline_sha256": FROZEN_SHA,
                "results": [], "passed": False}
    try:
        frozen = subprocess.run(["git", "show", f"{BASELINE}:{PARSER}"], cwd=ROOT,
                                capture_output=True, check=True).stdout
        if sha(frozen) != FROZEN_SHA:
            raise ValueError("frozen baseline raw SHA mismatch")
        marker = b"module midi_event_parser #("
        if frozen.count(marker) != 1:
            raise ValueError("frozen module marker mismatch")
        reference = frozen.replace(marker, b"module midi_event_parser_frozen #(", 1)
        current = (ROOT / PARSER).read_bytes()
        text = current.decode("utf-8")
        evidence["source_sha256"] = {p: sha((ROOT / p).read_bytes()) for p in (
            PARSER, TB, "code/rtl/common/audio_defs_pkg.sv",
            "code/scripts/run_midi_scheduler_equivalence.py")}
        tools = {name: args.modelsim_bin / (name + ".exe") for name in ("vlib", "vlog", "vsim")}
        if not all(p.is_file() for p in tools.values()):
            raise FileNotFoundError("ModelSim vlib/vlog/vsim missing")
        mutants = [
            ("omit_same_slot_latest", "parsed_control_rank <= first_rank_tree[1]",
             "parsed_control_rank < first_rank_tree[1]"),
            ("wrong_second_fallback", "selected_index = second_valid_tree[1] ? old_second_index : 5'd0;",
             "selected_index = second_valid_tree[1] ? old_first_index : 5'd0;"),
            ("wrong_wrap_rank", "parsed_control_index - round_robin_index;",
             "parsed_control_index + round_robin_index;"),
        ]
        cases = [("positive", current)]
        for name, before, after in mutants:
            if text.count(before) != 1:
                raise ValueError("unique mutation anchor missing: " + name)
            cases.append((name, text.replace(before, after, 1).encode("utf-8")))
        # All native simulator paths are ASCII staged. No user directories are
        # deleted; the generated TemporaryDirectory owns its cleanup target.
        with tempfile.TemporaryDirectory(prefix="m3_midi_equiv_") as stage_name:
            stage_root = Path(stage_name)
            version_code, _ = command_run([str(tools["vsim"]), "-version"],
                                          stage_root, output / "tool_version.log", 30)
            if version_code != 0:
                raise RuntimeError("ModelSim version command failed")
            for name, parser_bytes in cases:
                log_dir = output / name
                log_dir.mkdir()
                stage = stage_root / name
                stage.mkdir()
                sources = [
                    ("defs.sv", (ROOT / "code/rtl/common/audio_defs_pkg.sv").read_bytes()),
                    ("parser.sv", parser_bytes), ("frozen.sv", reference),
                    ("tb.sv", (ROOT / TB).read_bytes()),
                ]
                for filename, data in sources:
                    (stage / filename).write_bytes(data)
                commands = [[str(tools["vlib"]), "work"],
                            [str(tools["vlog"]), "-sv", *[s[0] for s in sources]],
                            [str(tools["vsim"]), "-c", "-onfinish", "stop", "-voptargs=+acc", "tb_midi_scheduler_equivalence",
                             "-do", "onbreak {quit -code 1}; onerror {quit -code 1}; run -all; "
                             "if {[examine -radix unsigned /tb_midi_scheduler_equivalence/test_passed] != 1} {quit -code 1}; quit -code 0"]]
                statuses = []
                run_text = ""
                for index, (command, label) in enumerate(zip(commands, ("library", "compile", "run"))):
                    code, run_text = command_run(command, stage, log_dir / (label + ".log"))
                    statuses.append(code)
                    if code != 0:
                        break
                compiled = len(statuses) >= 2 and statuses[0:2] == [0, 0]
                if name == "positive":
                    passed = compiled and statuses == [0, 0, 0] and (
                        "PASS tb_midi_scheduler_equivalence" in run_text) and not re.search(
                        r"Fatal:|\*\* Error|FAIL|RUNNER_TIMEOUT", run_text)
                else:
                    # Must compile and fail the intended behavioral oracle.
                    passed = compiled and len(statuses) == 3 and statuses[2] != 0 and (
                        "selector oracle mismatch" in run_text) and "RUNNER_TIMEOUT" not in run_text
                record = {"name": name, "commands": commands, "exit_codes": statuses,
                          "passed": passed, "parser_sha256": sha(parser_bytes),
                          "log_sha256": {p.name: sha(p.read_bytes()) for p in log_dir.glob("*.log")}}
                record["pass_lines"] = [line for line in run_text.splitlines() if "PASS " in line]
                evidence["results"].append(record)
                print(("PASS " if passed else "FAIL ") + name + " exit_codes=" + str(statuses))
                for line in record["pass_lines"]:
                    print(line)
                if not passed:
                    raise RuntimeError("equivalence case failed: " + name)
        evidence["passed"] = True
    except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as error:
        evidence["error"] = str(error)
        print("FAIL " + str(error))
    write_json(output / "evidence.json", evidence)
    print("Evidence: " + str(output / "evidence.json"))
    return 0 if evidence["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
