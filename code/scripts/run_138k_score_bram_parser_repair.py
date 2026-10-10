"""Bounded same-edge MIDI parser miter for isolated RAM timing candidate."""
from pathlib import Path
import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
SCOPE = ROOT / "code/rtl/138K_try/score_bram_timing_repair_20261010"
TB = ROOT / "code/tb/board/score_bram_timing_repair_20261010/tb_parser_miter.sv"
CAD = Path("D:/Gowin/oss-cad-suite")
import prepare_138k_score_bram_integration as ram


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.relative_to((ROOT / "code/output").resolve())
    if out.exists() or out == (ROOT / "code/output").resolve() or not str(out).isascii():
        parser.error("UNIQUE_ASCII_OUTPUT_REQUIRED")
    manifest = json.loads((SCOPE / "revision_manifest.json").read_bytes())
    inputs = ram.inputs(out)[0]
    frozen = inputs["sources/midi_event_parser.sv"]
    candidate = (SCOPE / "sources/midi_event_parser.sv").read_bytes()
    assert sha(frozen) == manifest["frozen_parser_sha256"]
    assert sha(candidate) == manifest["candidate_parser_sha256"]
    pkg = inputs["sources/audio_defs_pkg.sv"]
    source_paths = [Path(__file__), TB, Path(ram.__file__), SCOPE / "revision_manifest.json",
                    SCOPE / "sources/midi_event_parser.sv", CAD / "bin/iverilog.exe", CAD / "bin/vvp.exe"]
    record = {"date": "2026-10-10", "passed": False, "scope": "same-cycle parser candidate versus exact failed RAM fulltop parser",
              "source_sha256": {str(p): sha(p.read_bytes()) for p in source_paths}, "steps": {},
              "frozen_parser_sha256": sha(frozen), "candidate_parser_sha256": sha(candidate),
              "new_Gowin_calls": 0, "physical_STA_passed": False, "programmed": False}
    out.mkdir(parents=True, exist_ok=False)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1")
    env["PATH"] = os.pathsep.join((str(CAD / "bin"), str(CAD / "lib"), env.get("PATH", "")))
    started = time.monotonic()

    def run(label, command, timeout):
        command = list(map(str, command))
        start = time.monotonic()
        with (out / (label + ".stdout.log")).open("xb") as stdout, (out / (label + ".stderr.log")).open("xb") as stderr:
            process = subprocess.Popen(command, cwd=out, env=env, stdout=stdout, stderr=stderr,
                                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            timed = False
            try:
                code = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed = True
                subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, timeout=20)
                process.wait(timeout=20)
                code = process.returncode
        raw = (out / (label + ".stdout.log")).read_bytes() + (out / (label + ".stderr.log")).read_bytes()
        record["steps"][label] = {"command": command, "exit": code, "timed_out": timed,
                                  "seconds": round(time.monotonic() - start, 3),
                                  "stdout_sha256": sha((out / (label + ".stdout.log")).read_bytes()),
                                  "stderr_sha256": sha((out / (label + ".stderr.log")).read_bytes())}
        print(label, code, flush=True)
        if timed:
            raise ValueError(label + "_TIMEOUT")
        return code, raw

    try:
        # Only int qualifier syntax is adapted for this simulator.
        (out / "audio_defs_pkg.sv").write_bytes(re.sub(rb"\bint unsigned\b", b"integer", pkg))
        (out / "reference.sv").write_bytes(frozen.replace(b"module midi_event_parser #(",
                                                         b"module midi_event_parser_frozen #(", 1))
        (out / "candidate.sv").write_bytes(candidate)
        (out / "bench.sv").write_bytes(TB.read_bytes())
        patterns = {"positive": None,
                    "wrong_channel": (b"mod_sent_value[slot/2]", b"mod_sent_value[(slot/2+1)%16]"),
                    "wrong_inflight_priority": (b"wire local_locked = control_locked &&", b"wire local_locked = !control_locked &&")}
        record["cases"] = {}
        for name, mutation in patterns.items():
            folder = out / name
            folder.mkdir()
            data = candidate
            if mutation:
                before, after = mutation
                assert data.count(before) == 1
                data = data.replace(before, after, 1)
            (folder / "dut.sv").write_bytes(data)
            units = [out / "audio_defs_pkg.sv", folder / "dut.sv", out / "reference.sv", out / "bench.sv"]
            cmd = [CAD / "bin/iverilog.exe", "-B", CAD / "lib/ivl", "-g2012", "-s", "tb_m2_parser_miter",
                   "-o", folder / "miter.vvp", *units]
            code, _ = run(name + "_compile", cmd, 60)
            if code:
                raise ValueError(name + "_COMPILE_FAILED")
            code, log = run(name + "_simulate", [CAD / "bin/vvp.exe", folder / "miter.vvp"], 300)
            if mutation:
                diagnostic = any(value in log for value in (b"registered state mismatch", b"port equivalence mismatch",
                                                             b"PENDING_VALUE_EQ", b"MOD_SENT_VALUE_EQ"))
                if code != 1 or not diagnostic:
                    raise ValueError(name + "_NOT_REJECTED_BY_MITER")
            elif code or log.count(b"PASS M2 full original parser miter lane=") != 4:
                raise ValueError("POSITIVE_MITER_NOT_COMPLETE")
            record["cases"][name] = {"compile_exit": 0, "actual_sim_exit": code,
                                      "mutated_simulation_copy_only": mutation is not None,
                                      "compiled_input_sha256": {str(p): sha(p.read_bytes()) for p in units},
                                      "pass_lines": [s for s in log.decode("utf-8", errors="replace").splitlines() if s.startswith("PASS ")]}
        if any(sha(Path(p).read_bytes()) != h for p, h in record["source_sha256"].items()):
            raise ValueError("SOURCE_CHANGED")
        record["passed"] = True
    except Exception as error:
        record["error"] = type(error).__name__ + ": " + str(error)
        print(record["error"], flush=True)
    record["elapsed_seconds"] = round(time.monotonic() - started, 3)
    record["output_sha256"] = {str(p.relative_to(out)): sha(p.read_bytes()) for p in out.rglob("*") if p.is_file()}
    (out / "receipt.json").write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print("PARSER_REPAIR_MITER", record["passed"], record["elapsed_seconds"], flush=True)
    return 0 if record["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
