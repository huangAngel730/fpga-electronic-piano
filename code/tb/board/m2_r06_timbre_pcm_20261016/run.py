#!/usr/bin/env python3
"""Frozen R06 Program 0/1 to PCM comparison, isolated from board/Gowin."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile

ROOT = Path(__file__).resolve().parents[4]
ZIP = ROOT / "code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1TD_R06_XSAFE_7ms_ModelSim输入_20261016.zip"
ZIP_SHA = "4be2b4c185691a3e493827a3a95303fa90f49ba6336eb4a8e0183942c8f05483"
PASS = "PASS M2_R06_TIMBRE_PCM_ISOLATED frames=128 "
FAIL = "TIMBRE_PCM_NOT_DISTINCT"
TB = Path(__file__).with_name("tb_timbre_pcm_40m.sv")


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--output", type=Path, required=True)
    ap.add_argument("--cad", type=Path, default=Path("D:/Gowin/oss-cad-suite"))
    args = ap.parse_args()
    output = args.output.resolve()
    allowed = (ROOT / "code/output").resolve()
    if output == allowed or not output.is_relative_to(allowed) or output.exists():
        ap.error("--output must be a fresh directory inside code/output")
    if sha(ZIP.read_bytes()) != ZIP_SHA:
        ap.error("frozen R06 ZIP SHA differs")
    bins = args.cad / "bin"
    tools = {name: bins / (name + ".exe") for name in ("yosys", "iverilog", "vvp")}
    if any(not path.is_file() for path in tools.values()):
        ap.error("missing frozen runner tools in " + str(bins))
    output.mkdir(parents=True)
    receipt = {"scope": "R06_PROGRAM_PCM_ISOLATED", "r06_zip_sha256": ZIP_SHA,
               "status": "FAILED", "board_release_allowed": False,
               "source_sha256": {}, "tools": {}, "steps": []}
    for name, path in tools.items():
        receipt["tools"][name] = {"path": str(path.resolve()),
                                  "sha256": sha(path.read_bytes())}
    with zipfile.ZipFile(ZIP) as archive:
        for member in archive.namelist():
            name = Path(member).name
            if member.startswith("inputs/sources/") and (
                    name.startswith("m1td_") or name in
                    ("audio_defs_pkg.sv", "sustain_control_contract_pkg.sv")):
                data = archive.read(member)
                (output / name).write_bytes(data)
                receipt["source_sha256"][name] = sha(data)
            if member.startswith("inputs/include/") and name.endswith(".svh"):
                data = archive.read(member)
                (output / name).write_bytes(data)
                receipt["source_sha256"][name] = sha(data)
            if member.startswith("inputs/rom/") and name.endswith((".mem", ".hex")):
                data = archive.read(member)
                destination = output / "rom" / name
                destination.parent.mkdir(exist_ok=True)
                destination.write_bytes(data)
                receipt["source_sha256"]["rom/" + name] = sha(data)
    receipt["source_sha256"][TB.name] = sha(TB.read_bytes())
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join((str(bins), str(args.cad / "lib"), env.get("PATH", "")))
    script = output / "lower.ys"
    net = output / "allocator.v"
    script.write_text(
        f"read_slang --top m1td_voice_allocator_4 {(output / 'm1td_voice_allocator_4.sv').as_posix()}\n"
        f"proc\nopt\ntechmap\nopt\nwrite_verilog -noattr {net.as_posix()}\n",
        encoding="ascii", newline="\n")

    def step(name: str, argv: list[str], timeout: int = 100) -> tuple[int, bytes]:
        start = time.monotonic()
        try:
            proc = subprocess.run(argv, cwd=output, env=env, capture_output=True,
                                  timeout=timeout, check=False)
            code, stdout, stderr, timed_out = proc.returncode, proc.stdout, proc.stderr, False
        except subprocess.TimeoutExpired as exc:
            code, stdout, stderr, timed_out = 124, exc.stdout or b"", exc.stderr or b"", True
        (output / (name + ".stdout.bin")).write_bytes(stdout)
        (output / (name + ".stderr.bin")).write_bytes(stderr)
        receipt["steps"].append({"name": name, "argv": argv, "cwd": str(output),
                                 "exit": code, "timed_out": timed_out,
                                 "elapsed_s": round(time.monotonic() - start, 3),
                                 "stdout_sha256": sha(stdout), "stderr_sha256": sha(stderr)})
        return code, stdout

    try:
        if step("lower", [str(tools["yosys"]), "-Q", "-T", "-s", str(script)])[0]:
            return 1
        binary = output / "timbre_pcm.vvp"
        sources = [output / "audio_defs_pkg.sv", output / "sustain_control_contract_pkg.sv"]
        sources.extend(sorted(f for f in output.glob("m1td_*.sv")
                              if f.name != "m1td_voice_allocator_4.sv"))
        compile_argv = [str(tools["iverilog"]), "-g2012", "-s", "tb_m2_timbre_pcm",
                        "-I", str(output), "-o", str(binary)]
        compile_argv.extend(str(f) for f in (*sources, net, TB))
        if step("compile", compile_argv)[0]:
            return 1
        code, stdout = step("positive", [str(tools["vvp"]), str(binary)])
        receipt_positive = stdout.decode("utf-8", "replace")
        text = receipt_positive
        if code or len([line for line in text.splitlines() if line.startswith(PASS)]) != 1 or "FATAL:" in text:
            return 1
        code, stdout = step("negative_skip_program1", [str(tools["vvp"]), str(binary),
                                                         "+skip_program1"])
        text = stdout.decode("utf-8", "replace")
        if code != 1 or FAIL not in text or PASS in text:
            return 1
        receipt["status"] = "PASS_ISOLATED_PCM_L2"
        print(next(line for line in receipt_positive.splitlines() if line.startswith(PASS)))
        return 0
    finally:
        receipt["inputs_unchanged"] = all(
            sha((output / name).read_bytes()) == original for name, original in
            receipt["source_sha256"].items() if name != TB.name)
        receipt["tb_unchanged"] = sha(TB.read_bytes()) == receipt["source_sha256"][TB.name]
        (output / "RUN_RECEIPT.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        print("receipt:", output / "RUN_RECEIPT.json")


if __name__ == "__main__":
    sys.exit(main())
