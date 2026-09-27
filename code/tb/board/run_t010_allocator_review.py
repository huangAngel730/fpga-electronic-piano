#!/usr/bin/env python3
"""Read-only T010 public-port review of unmodified M1 source.

Uses installed Yosys read_slang/techmap to lower struct arrays to a generic
netlist, then Icarus/VVP for behavioural checks. This is not Gowin's encrypted
netlist or a claim of direct Icarus source compatibility. Missing tooling,
compile errors, no PASS marker or any failed scenario must return nonzero.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
SCENARIOS = ("baseline", "identity", "single_release", "release_retrigger",
             "release_isolation", "age_wrap")


def run(command, out: Path, name: str, timeout: int = 60):
    result = subprocess.run(command, cwd=out, capture_output=True, text=True,
                            encoding="utf-8", errors="replace", timeout=timeout)
    output = result.stdout + result.stderr
    (out / (name + ".log")).write_bytes(output.encode("utf-8"))
    return result.returncode, output


def main() -> int:
    source = ROOT / "code/rtl/audio/voice_allocator_4.sv"
    tb = ROOT / "code/tb/board/tb_t010_allocator_review.sv"
    out = ROOT / "code/output/t010_allocator_review"
    out.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    record = {"source": source.relative_to(ROOT).as_posix(), "source_sha256": digest,
              "method": "unmodified source -> Yosys/read_slang/techmap -> generic Verilog -> Icarus/VVP",
              "scenarios": [], "error": None}
    cad = Path(os.environ.get("YOSYSHQ_ROOT", "D:/Gowin/oss-cad-suite"))
    tools = {name: cad / "bin" / (name + ".exe") for name in ("yosys", "iverilog", "vvp")}
    try:
        for path in tools.values():
            if not path.is_file():
                raise OSError(f"Missing review tool: {path}")
        shutil.copyfile(source, out / "source.sv")
        shutil.copyfile(tb, out / "tb.sv")
        (out / "lower.ys").write_bytes(
            b"read_slang --top voice_allocator_4 source.sv\n"
            b"proc\nopt\ntechmap\nopt\nwrite_verilog -noattr allocator_netlist.v\n")
        rc, text = run([str(tools["yosys"]), "-Q", "-T", "-s", "lower.ys"], out, "lower")
        if rc:
            raise RuntimeError(f"SystemVerilog lowering failed, exit={rc}; see {out/'lower.log'}")
        record["netlist_sha256"] = hashlib.sha256((out / "allocator_netlist.v").read_bytes()).hexdigest()
        rc, text = run([str(tools["iverilog"]), "-g2012", "-Wall", "-s",
                        "tb_t010_allocator_review", "-o", "review.vvp",
                        "allocator_netlist.v", "tb.sv"], out, "compile")
        if rc:
            raise RuntimeError(f"TB compile failed, exit={rc}; see {out/'compile.log'}")
        for scenario in SCENARIOS:
            rc, text = run([str(tools["vvp"]), "review.vvp", "+CASE=" + scenario], out, scenario)
            marker = "PASS T010 " + scenario + " checks="
            passed = rc == 0 and marker in text
            lines = [line for line in text.splitlines()
                     if "PASS T010" in line or "FAIL T010" in line]
            record["scenarios"].append({"name": scenario, "exit": rc,
                                        "passed": passed, "evidence": lines})
            print(("PASS" if passed else "FAIL") + " T010 " + scenario + f" exit={rc}")
            for line in lines:
                print("  " + line)
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        record["error"] = str(exc)
        print("ERROR T010 review: " + str(exc), file=sys.stderr)
    finally:
        record["source_unchanged"] = hashlib.sha256(source.read_bytes()).hexdigest() == digest
        (out / "summary.json").write_bytes((json.dumps(record, indent=2) + "\n").encode("utf-8"))
    if record["error"] or not record["source_unchanged"]:
        return 2
    failures = sum(not scenario["passed"] for scenario in record["scenarios"])
    print(f"T010 review: {len(SCENARIOS)-failures}/{len(SCENARIOS)} scenarios pass; original source unchanged.")
    print(f"Evidence: {out/'summary.json'}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
