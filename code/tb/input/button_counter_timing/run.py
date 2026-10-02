"""Formal counter timing regression. No FPGA, synthesis or programming.

Frozen old oracle + current production converter/FIFO. Artifacts use a NEW
code/output directory. --selftest checks delayed-count/no-full-bypass failures.
Only Python stdlib and already-installed Icarus are required.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
from datetime import datetime

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[3]


def lf_sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cad", type=Path, default=Path("D:/Gowin/oss-cad-suite"))
    parser.add_argument("--output", type=Path)
    parser.add_argument("--selftest", action="store_true")
    args = parser.parse_args()
    manifest = json.loads((HERE / "oracle_manifest.json").read_text(encoding="utf-8"))
    for name, expected in manifest["files_sha256_LF"].items():
        if lf_sha(HERE / name) != expected:
            parser.error("Frozen independent oracle changed: " + name)
    default = REPO / "code/output" / (
        "button_counter_formal_" + datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    output = (args.output or default).resolve()
    if not output.is_relative_to((REPO / "code/output").resolve()):
        parser.error("Output must be inside this repository's code/output")
    if output.exists():
        parser.error(
            "Output exists; preserve previous evidence and use a fresh directory"
        )
    if not str(output).isascii():
        parser.error("Native tool staging requires an ASCII output path")
    tools = [args.cad / "bin/iverilog.exe", args.cad / "bin/vvp.exe"]
    if not all(path.is_file() for path in tools):
        parser.error("Icarus tool not found; use --cad (no installation performed)")
    output.mkdir(parents=True)
    inputs = {
        "audio_defs_pkg.sv": REPO / "code/rtl/common/audio_defs_pkg.sv",
        "button_dut.sv": REPO / (
            "code/rtl/input/button_event_converter/button_event_converter.sv"
        ),
        "fifo_dut.sv": REPO / "code/rtl/common/performance_event_fifo.sv",
        "tb_original.sv": REPO / "code/tb/input/tb_button_event_converter.sv",
        "tb_button_counter_timing.sv": HERE / "tb_button_counter_timing.sv",
    }
    inputs.update({name: HERE / name for name in manifest["files_sha256_LF"]})
    for name, source in inputs.items():
        (output / name).write_text(
            source.read_text(encoding="utf-8"), encoding="utf-8", newline="\n"
        )
    # Environment changes apply ONLY to each compiler/simulator child.
    env = dict(os.environ)
    env["PATH"] = os.pathsep.join(
        (str(args.cad / "lib"), str(args.cad / "bin"), env["PATH"])
    )
    results = []

    def execute(label: str, command: list[str]) -> tuple[int, str]:
        completed = subprocess.run(
            command, cwd=output, env=env,
            capture_output=True, text=True, timeout=90,
        )
        text = completed.stdout + completed.stderr
        (output / (label + ".log")).write_text(text, encoding="utf-8", newline="\n")
        return completed.returncode, text

    def compile_tb(
        label: str, top: str, files: list[str], parameters: list[str]
    ) -> Path:
        binary = output / (label + ".vvp")
        command = [
            str(tools[0]), "-g2012", "-s", top, "-o", str(binary),
            *parameters, *files,
        ]
        code, text = execute(label + "_compile", command)
        if code or "error:" in text.lower():
            raise RuntimeError(
                label + " compile failed; see preserved log\n" + text[-2000:]
            )
        return binary

    sources = [
        "audio_defs_pkg.sv", "fifo_reference.sv", "fifo_no_full_bypass.sv",
        "button_reference.sv", "button_dut.sv", "fifo_dut.sv",
        "tb_button_counter_timing.sv",
    ]
    for depth, local_depth in ((3, 2), (32, 2), (3, 1), (32, 4)):
        label = f"depth{depth}_local{local_depth}"
        binary = compile_tb(
            label, "tb_button_counter_timing", sources,
            ["-P", f"tb_button_counter_timing.DEPTH={depth}",
             "-P", f"tb_button_counter_timing.LOCAL={local_depth}"],
        )
        code, text = execute(label + "_run", [str(tools[1]), str(binary)])
        match = re.search(
            r"PASS button_counter_timing depth=(\d+) checks=(\d+) cycles=(\d+)",
            text,
        )
        if code or not match or re.search(r"FATAL|ERROR", text):
            raise RuntimeError(label + " regression failed\n" + text[-2000:])
        results.append({
            "depth": depth, "local_depth": local_depth,
            "checks": int(match[2]), "cycles": int(match[3]), "status": "PASS",
        })
        print("\n".join(
            line for line in text.splitlines()
            if line.startswith(("DIRECTED", "PASS"))
        ))
    binary = compile_tb(
        "original", "tb_button_event_converter",
        ["audio_defs_pkg.sv", "button_dut.sv", "tb_original.sv"], [],
    )
    code, text = execute("original_run", [str(tools[1]), str(binary)])
    if (code or "PASS: tb_button_event_converter completed all checks" not in text
            or re.search(r"FATAL|ERROR", text)):
        raise RuntimeError("Original module TB failed\n" + text[-2000:])
    print("PASS original tb_button_event_converter (Icarus, unchanged TB)")
    negative = []
    if args.selftest:
        button = (output / "button_dut.sv").read_text(encoding="utf-8")
        header, body = button.split("    import audio_defs_pkg::*;", 1)
        # Real one-cycle delayed output, same public ports and compilable RTL.
        delayed = (header + "    logic [31:0] counter_accumulator;\n"
                   "    always_ff @(posedge clk) begin\n"
                   "        if(!rst_n) overflow_count <= 0;\n"
                   "        else overflow_count <= counter_accumulator;\n"
                   "    end\n    import audio_defs_pkg::*;"
                   + body.replace("overflow_count", "counter_accumulator"))
        fifo = (output / "fifo_dut.sv").read_text(encoding="utf-8")
        assert "((count < DEPTH) || pop)" in fifo
        no_bypass = fifo.replace("((count < DEPTH) || pop)", "(count < DEPTH)")
        for label, filename, mutation, expected_failure in (
            ("reject_delayed_count", "button_dut.sv", delayed,
             "counter exactly same cycle"),
            ("reject_no_full_bypass", "fifo_dut.sv", no_bypass,
             "counter candidate same ready"),
        ):
            mutant = label + ".sv"
            (output / mutant).write_text(mutation, encoding="utf-8", newline="\n")
            files = [mutant if name == filename else name for name in sources]
            binary = compile_tb(label, "tb_button_counter_timing", files, [])
            code, text = execute(label + "_run", [str(tools[1]), str(binary)])
            if code == 0 or expected_failure not in text:
                raise RuntimeError(
                    "Negative test did not reject the intended behavioral error: "
                    + label
                )
            negative.append({
                "case": label, "compile_exit": 0, "run_exit": code,
                "expected_failure": expected_failure, "status": "REJECTED",
            })
            print("PASS negative rejected:", label)
    report = {
        "status": "PASS",
        "scope": "L2 simulation only; no new synthesis/PnR or board test",
        "source_inputs": {
            str(path.relative_to(REPO)): lf_sha(path) for path in inputs.values()
        },
        "oracle_provenance": manifest, "runs": results, "original_tb": "PASS",
        "negative": negative,
        "checks": sum(record["checks"] for record in results),
    }
    (output / "results.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    print("PASS formal counter regression", report["checks"], "checks; logs:", output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
