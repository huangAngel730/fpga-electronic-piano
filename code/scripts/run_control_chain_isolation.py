"""Reproduce M2 control-chain isolation experiments without changing formal RTL.

Generates output-only reference/no-full-bypass/parallel-counter modules, then
compares real button pulses and FIFOs at depths 3 and 32. Exit zero means the
experiment produced its EXPECTED outcomes, never that a candidate is deployed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
CAD = Path("D:/Gowin/oss-cad-suite")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def stage_candidates(folder: Path) -> dict:
    fifo_path = ROOT / "code/rtl/common/performance_event_fifo.sv"
    button_path = ROOT / "code/rtl/input/button_event_converter/button_event_converter.sv"
    fifo = fifo_path.read_text(encoding="utf-8")
    button = button_path.read_text(encoding="utf-8")
    bypass = "((count < DEPTH) || pop)"
    if fifo.count(bypass) != 1:
        raise ValueError("FIFO implementation changed; review the benchmark before replay")
    declaration = "    logic [31:0]                 overflow_increment;"
    old = """            if (overflow_increment != 32'd0) begin
                if (overflow_count >= (32'hFFFF_FFFF - overflow_increment)) begin
                    overflow_count <= 32'hFFFF_FFFF;
                end else begin
                    overflow_count <= overflow_count + overflow_increment;
                end
            end"""
    if button.count(old) != 1 or button.count(declaration) != 1:
        raise ValueError("Button implementation changed; no automatic source rewrite allowed")
    parallel = button.replace(declaration, """    localparam integer MAX_DROP_PER_CYCLE = 2*BUTTON_COUNT;
    localparam integer DROP_W = $clog2(MAX_DROP_PER_CYCLE+1);
    logic [DROP_W-1:0] overflow_increment;
    wire [31:0] overflow_result [0:MAX_DROP_PER_CYCLE];
    assign overflow_result[0] = overflow_count;
    // Parallel constant-increment adders depend only on registered count;
    // the event/ready chain ends at a bounded selection mux, not carry logic.
    for(genvar inc=1;inc<=MAX_DROP_PER_CYCLE;inc=inc+1) begin:g_overflow_result
        wire [32:0] candidate_sum = {1'b0,overflow_count} + 33'(inc);
        assign overflow_result[inc] = candidate_sum[32] ? 32'hffffffff : candidate_sum[31:0];
    end""")
    parallel = parallel.replace("overflow_increment = 32'd0;", "overflow_increment = '0;")
    parallel = parallel.replace("overflow_increment = overflow_increment + 32'd1;",
                                "overflow_increment = overflow_increment + 1'b1;")
    parallel = parallel.replace(old, """            if (overflow_increment != 0)
                overflow_count <= overflow_result[overflow_increment];""")
    files = {
        "fifo_reference.sv": fifo.replace("module performance_event_fifo", "module fifo_reference", 1),
        "fifo_no_full_bypass.sv": fifo.replace("module performance_event_fifo", "module fifo_no_full_bypass", 1).replace(bypass, "(count < DEPTH)"),
        "button_reference.sv": button.replace("module button_event_converter", "module button_reference", 1),
        "button_parallel_counter.sv": parallel.replace("module button_event_converter", "module button_parallel_counter", 1),
        "button_parallel_counter_formal_name.sv": parallel,
    }
    for name, source in files.items():
        (folder / name).write_text(source, encoding="utf-8", newline="\n")
    return {"formal_FIFO_sha256": sha(fifo_path), "formal_button_sha256": sha(button_path),
            "generated_sha256": {name: sha(folder / name) for name in files}}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--generate-only", action="store_true")
    args = parser.parse_args()
    folder = args.output.resolve()
    folder.relative_to(ROOT / "code/output")
    if folder.exists():
        parser.error("output already exists; preserve previous experiments")
    folder.mkdir(parents=True)
    record = stage_candidates(folder)
    record.update({"formal_RTL_modified": False, "deployment_accepted": False,
                   "counter_candidate_observation_delay": 0,
                   "handshake_or_queue_capacity_changed": False,
                   "scope": "M2 experiment; M3 notice/acceptance needed before formal adoption"})
    if not args.generate_only:
        env = dict(os.environ)
        env["PATH"] = str(CAD / "lib") + os.pathsep + str(CAD / "bin") + os.pathsep + env["PATH"]
        sources = [ROOT / "code/rtl/common/audio_defs_pkg.sv"] + [folder / name for name in
                   ("fifo_reference.sv", "fifo_no_full_bypass.sv", "button_reference.sv", "button_parallel_counter.sv")]
        sources.append(ROOT / "code/tb/common/tb_control_chain_counter_compare.sv")
        record["runs"] = {}
        for depth in (3, 32):
            binary = folder / f"compare_{depth}.vvp"
            commands = {
                "compile": [str(CAD / "bin/iverilog.exe"), "-g2012", "-s", "tb_control_chain_counter_compare",
                            "-P", f"tb_control_chain_counter_compare.DEPTH={depth}", "-o", str(binary), *map(str, sources)],
                "run": [str(CAD / "bin/vvp.exe"), str(binary)],
            }
            for name, command in commands.items():
                log_path = folder / f"{name}_{depth}.log"
                with log_path.open("w", encoding="utf-8", newline="\n") as log:
                    result = subprocess.run(command, cwd=ROOT, env=env, stdout=log,
                                            stderr=subprocess.STDOUT, timeout=60, check=False)
                text = log_path.read_text(encoding="utf-8", errors="replace")
                record["runs"][f"{name}_{depth}"] = {"exit": result.returncode, "command": command,
                                                        "log_sha256": sha(log_path)}
                if result.returncode:
                    print(text[-3000:])
                    raise RuntimeError(f"{name} depth{depth} failed")
                if name == "run":
                    marker = f"PASS control_chain_candidates depth={depth}"
                    if marker not in text or "conservative_drop=1" not in text or "FATAL" in text:
                        raise RuntimeError("Missing expected directed-loss and nonvacuous comparison verdict")
                    print("\n".join(line for line in text.splitlines() if line.startswith(("DIRECTED", "PASS"))))
        record["functional_experiment_pass"] = True
        record["no_full_bypass_rejected"] = "new local button loss at simultaneous full FIFO pop/new pulse"
    (folder / "experiment.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print("Formal FIFO/button source untouched; physical acceptance requires a separate build review.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
