"""Static runner delivery receipt; invokes ONLY Python software, never HDL."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

from bounded_runner import identity, write_json

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
TB = ROOT / "code/tb/audio/t052_publication_acceptance_candidate_20261012/long_window_preparation_20261015"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir()
    sources = sorted([*HERE.glob("*.py"), *TB.glob("*.py"), *TB.glob("*.sv")])
    before = {str(p): identity(p) for p in sources}
    with zipfile.ZipFile(out / "source_before.zip", "x", zipfile.ZIP_DEFLATED) as archive:
        for path in sources:
            archive.write(path, path.relative_to(ROOT).as_posix())
    commands = [
        ("row0", [sys.executable, "-B", "-X", "utf8", str(TB / "test_row0_schedule.py"),
                  "--controls", str(args.prepared.resolve() / "controls.hex"),
                  "--output", str(out / "row0")]),
        ("fakes", [sys.executable, "-B", "-X", "utf8", str(HERE / "test_bounded_runner.py"),
                   "--output", str(out / "fakes")]),
        ("proposal", [sys.executable, "-B", "-X", "utf8", str(HERE / "propose_runner.py"),
                      "--prepared", str(args.prepared.resolve()),
                      "--proposal", str(out / "LOCKED_PROPOSAL.json"),
                      "--target", str(ROOT / "code/output/m3_t052_long_actual_R02_PENDING_M2"),
                      "--allowance", str(ROOT / "code/output/m3_t052_long_allowance_R02_PENDING_M2")]),
    ]
    steps = []
    for name, argv in commands:
        started = time.monotonic()
        with (out / (name + ".stdout.bin")).open("xb") as stdout, \
                (out / (name + ".stderr.bin")).open("xb") as stderr:
            try:
                result = subprocess.run(argv, cwd=ROOT, stdout=stdout, stderr=stderr, timeout=90)
                code, timeout = result.returncode, False
            except subprocess.TimeoutExpired:
                code, timeout = 124, True
        steps.append({"name": name, "argv": argv, "cwd": str(ROOT), "exit_code": code,
                      "timeout": timeout, "elapsed_seconds": time.monotonic()-started,
                      "stdout": identity(out / (name + ".stdout.bin")),
                      "stderr": identity(out / (name + ".stderr.bin"))})
        if code:
            break
    after = {str(p): identity(p) for p in sources}
    passed = len(steps) == 3 and all(s["exit_code"] == 0 for s in steps) and before == after
    receipt = {"status": "SOFTWARE_PREPARATION_PASS" if passed else "FAIL",
               "exit_code": 0 if passed else 1, "actual_argv": sys.orig_argv,
               "source_before": before, "source_after": after, "steps": steps,
               "python": identity(Path(sys.executable)), "python_version": sys.version,
               "new_T052_HDL_compiles": 0, "new_T052_RTL_runs": 0,
               "execution_authorized": False, "validation": "L0_STATIC_AND_PYTHON_FAKE_PROCESS_ONLY"}
    write_json(out / "receipt.json", receipt)
    print(json.dumps({k: receipt[k] for k in ("status", "exit_code", "new_T052_HDL_compiles")}))
    return receipt["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
