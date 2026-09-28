#!/usr/bin/env python3
"""Read-only T010 public-port review of unmodified M1 source.

Uses installed Yosys read_slang/techmap to lower struct arrays to a generic
netlist, then Icarus/VVP for behavioural checks. This is not Gowin's encrypted
netlist or a claim of direct Icarus source compatibility. Missing tooling,
compile errors, no PASS marker or any failed scenario must return nonzero.
"""
import argparse
import hashlib
import json
import os
import re
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
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path,
                        default=ROOT / "code/rtl/audio/voice_allocator_4.sv")
    parser.add_argument("--output", type=Path,
                        default=ROOT / "code/output/t010_allocator_review")
    args = parser.parse_args()
    source = args.source.resolve()
    out = args.output.resolve()
    if not source.is_file():
        parser.error(f"Source file missing: {source}")
    if not out.is_relative_to((ROOT / "code/output").resolve()):
        parser.error("Review output must be within code/output")
    tb = ROOT / "code/tb/board/tb_t010_allocator_review.sv"
    out.mkdir(parents=True, exist_ok=True)
    content = source.read_bytes().decode("utf-8-sig")
    content = re.sub(r"//[^\n]*|/\*.*?\*/", "", content, flags=re.S)
    vector_release = bool(re.search(r"\binput\s+logic\s*\[\s*3\s*:\s*0\s*\]\s*release_done\b", content))
    scalar_release = bool(re.search(r"\binput\s+logic\s+release_done\b", content))
    if vector_release == scalar_release:
        parser.error("Expected one scalar or 4-bit release_done input")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    record = {"source": source.relative_to(ROOT).as_posix()
              if source.is_relative_to(ROOT) else str(source),
              "source_sha256": digest,
              "method": "unmodified source -> Yosys/read_slang/techmap -> generic Verilog -> Icarus/VVP",
              "scenarios": [], "error": None,
              "release_done_interface": "per-slot[3:0]" if vector_release else "legacy scalar"}
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
        compile_cmd = [str(tools["iverilog"]), "-g2012", "-Wall", "-s",
                       "tb_t010_allocator_review", "-o", "review.vvp"]
        if vector_release:
            compile_cmd.append("-DT010_RELEASE_VECTOR")
        compile_cmd.extend(["allocator_netlist.v", "tb.sv"])
        rc, text = run(compile_cmd, out, "compile")
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
        if vector_release:
            generator = ROOT / "code/tb/board/generate_t010_allocator_vectors.py"
            oracle_tb = ROOT / "code/tb/board/tb_t010_allocator_vectors.sv"
            rc, text = run([sys.executable, str(generator), str(out / "oracle_vectors.txt")],
                           out, "oracle_generate")
            if rc or "T010 oracle vectors=" not in text:
                raise RuntimeError("Independent oracle vector generation failed")
            shutil.copyfile(oracle_tb, out / "oracle_tb.sv")
            rc, text = run([str(tools["iverilog"]), "-g2012", "-Wall", "-s",
                            "tb_t010_allocator_vectors", "-o", "oracle.vvp",
                            "allocator_netlist.v", "oracle_tb.sv"], out, "oracle_compile")
            if rc:
                raise RuntimeError(f"Oracle TB compile failed: {out/'oracle_compile.log'}")
            rc, text = run([str(tools["vvp"]), "oracle.vvp",
                            "+VECTORS=" + (out / "oracle_vectors.txt").as_posix()],
                           out, "oracle")
            marker = "PASS T010 oracle vectors=" + str(
                len((out / "oracle_vectors.txt").read_text(encoding="ascii").splitlines()))
            passed = rc == 0 and marker in text
            evidence = [line for line in text.splitlines()
                        if "PASS T010" in line or "FAIL T010" in line]
            record["scenarios"].append({"name": "oracle", "exit": rc,
                                        "passed": passed, "evidence": evidence})
            print(("PASS" if passed else "FAIL") + f" T010 oracle exit={rc}")
            for line in evidence:
                print("  " + line)
            record["oracle_vectors_sha256"] = hashlib.sha256(
                (out / "oracle_vectors.txt").read_bytes()).hexdigest()
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        record["error"] = str(exc)
        print("ERROR T010 review: " + str(exc), file=sys.stderr)
    finally:
        record["source_unchanged"] = hashlib.sha256(source.read_bytes()).hexdigest() == digest
        (out / "summary.json").write_bytes((json.dumps(record, indent=2) + "\n").encode("utf-8"))
    if record["error"] or not record["source_unchanged"]:
        return 2
    directed = [item for item in record["scenarios"] if item["name"] in SCENARIOS]
    directed_passed = sum(item["passed"] for item in directed)
    oracle = next((item for item in record["scenarios"] if item["name"] == "oracle"), None)
    print(f"T010 review: {directed_passed}/{len(SCENARIOS)} directed scenarios; "
          f"oracle={'PASS' if oracle and oracle['passed'] else 'FAIL' if oracle else 'not run'}; "
          "original source unchanged.")
    print(f"Evidence: {out/'summary.json'}")
    return 1 if directed_passed != len(SCENARIOS) or (vector_release and
                    (oracle is None or not oracle["passed"])) else 0


if __name__ == "__main__":
    raise SystemExit(main())
