#!/usr/bin/env python3
"""One bounded R06 MIDI Program 0/1 router regression; no board/Gowin run."""
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
R06 = ROOT / "code/docs/evidence/m2_m1td_physical_20261015/M2_138K_M1TD_R06_XSAFE_7ms_ModelSim输入_20261016.zip"
R06_SHA = "4be2b4c185691a3e493827a3a95303fa90f49ba6336eb4a8e0183942c8f05483"
SOURCES = (
    "audio_defs_pkg.sv", "sustain_control_contract_pkg.sv", "uart_rx.sv",
    "midi_event_parser.sv", "midi_input.sv", "performance_event_fifo.sv",
    "m1td_note_pitch.sv",
    "m1td_sustain_controller.sv", "m1td_polyphonic_event_router.sv",
)
ALLOCATOR = "m1td_voice_allocator_4.sv"
INCLUDE = "sustain_controller_ports.svh"
PASS = "PASS R06_MIDI_PROGRAM_40M "


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--cad", type=Path, default=Path("D:/Gowin/oss-cad-suite"))
    args = parser.parse_args()
    output = args.output.resolve()
    allowed = (ROOT / "code/output").resolve()
    if output == allowed or not output.is_relative_to(allowed) or output.exists():
        parser.error("--output must be a new directory under code/output")
    if digest(R06.read_bytes()) != R06_SHA:
        parser.error("frozen R06 ZIP SHA mismatch")
    bin_dir = args.cad / "bin"
    for name in ("yosys.exe", "iverilog.exe", "vvp.exe"):
        if not (bin_dir / name).is_file():
            parser.error(f"missing {bin_dir / name}")
    output.mkdir(parents=True)
    receipt = {"scope": "R06_MIDI_PROGRAM_UART_SHARED_FIFO_ROUTER", "r06_sha256": R06_SHA,
               "status": "FAILED", "board_release_allowed": False,
               "source_sha256": {}, "steps": []}
    with zipfile.ZipFile(R06) as archive:
        for name in (*SOURCES, ALLOCATOR):
            data = archive.read(f"inputs/sources/{name}")
            (output / name).write_bytes(data)
            receipt["source_sha256"][name] = digest(data)
        data = archive.read(f"inputs/include/{INCLUDE}")
        (output / INCLUDE).write_bytes(data)
        receipt["source_sha256"][INCLUDE] = digest(data)
    tb = Path(__file__).with_name("tb_program_select_40m.sv")
    receipt["source_sha256"][tb.name] = digest(tb.read_bytes())
    env = os.environ.copy()
    env["PATH"] = os.pathsep.join((str(args.cad / "lib"), str(bin_dir),
                                    env.get("PATH", "")))
    net = output / "allocator.v"
    script = output / "lower.ys"
    script.write_text(
        f"read_slang --top m1td_voice_allocator_4 {(output / ALLOCATOR).as_posix()}\n"
        f"proc\nopt\ntechmap\nopt\nwrite_verilog -noattr {net.as_posix()}\n",
        encoding="ascii", newline="\n")

    def step(label: str, argv: list[str]) -> tuple[int, bytes, bytes]:
        start = time.monotonic()
        timed_out = False
        try:
            proc = subprocess.run(argv, cwd=output, env=env, capture_output=True,
                                  timeout=90, check=False)
            code, stdout, stderr = proc.returncode, proc.stdout, proc.stderr
        except subprocess.TimeoutExpired as exc:
            timed_out = True
            code, stdout, stderr = 124, exc.stdout or b"", exc.stderr or b""
        (output / f"{label}.stdout.bin").write_bytes(stdout)
        (output / f"{label}.stderr.bin").write_bytes(stderr)
        receipt["steps"].append({"label": label, "argv": argv, "exit": code,
                                 "timed_out": timed_out,
                                 "elapsed_s": round(time.monotonic() - start, 3),
                                 "stdout_sha256": digest(stdout),
                                 "stderr_sha256": digest(stderr)})
        return code, stdout, stderr

    try:
        if step("lower", [str(bin_dir / "yosys.exe"), "-Q", "-T", "-s", str(script)])[0]:
            return 1
        binary = output / "program.vvp"
        argv = [str(bin_dir / "iverilog.exe"), "-g2012", "-s",
                "tb_program_select_40m", "-I", str(output), "-o", str(binary)]
        argv += [str(output / name) for name in SOURCES]
        argv += [str(net), str(tb)]
        if step("compile", argv)[0]:
            return 1
        code, stdout, stderr = step("simulate", [str(bin_dir / "vvp.exe"), str(binary)])
        lines = stdout.decode("utf-8", "replace").splitlines()
        if code or len([line for line in lines if line.startswith(PASS)]) != 1 or                 any("FATAL" in line or "ERROR:" in line for line in lines):
            return 1
        receipt["status"] = "PASS_ISOLATED_MIDI_ROUTER_L2"
        print(next(line for line in lines if line.startswith(PASS)))
        return 0
    finally:
        receipt["inputs_unchanged"] = all(
            digest((output / name).read_bytes()) == value
            for name, value in receipt["source_sha256"].items() if name != tb.name)
        (output / "RUN_RECEIPT.json").write_text(
            json.dumps(receipt, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
        print(f"receipt: {output / 'RUN_RECEIPT.json'}")


if __name__ == "__main__":
    sys.exit(main())
