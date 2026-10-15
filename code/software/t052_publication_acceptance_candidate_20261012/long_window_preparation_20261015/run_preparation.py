"""Software-only repeatable preparation with raw logs and frozen source copies."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

from prepare import HERE, ROOT, TB, identity, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--m1-confirmation", required=True, type=Path)
    parser.add_argument("--suite", type=Path, default=Path("D:/Gowin/oss-cad-suite"))
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error("OUTPUT_EXISTS")
    output.mkdir(parents=True)
    sources = sorted([*HERE.glob("*.py"), *TB.glob("*.sv")])
    before = {str(p): identity(p) for p in sources}
    with zipfile.ZipFile(output / "source_before.zip", "x", zipfile.ZIP_DEFLATED) as archive:
        for path in sources:
            archive.write(path, path.relative_to(ROOT).as_posix())
    commands = [
        ("software_tests", [sys.executable, "-B", "-X", "utf8", str(HERE / "run_checks.py"),
                            "--output", str(output / "software_tests")], 90),
        ("tool_metadata", [sys.executable, "-B", "-X", "utf8", str(HERE / "qualify_tools.py"),
                           "--output", str(output / "tool_metadata"), "--suite",
                           str(args.suite.resolve())], 90),
        ("prepare", [sys.executable, "-B", "-X", "utf8", str(HERE / "prepare.py"),
                     "--output", str(output / "prepared"), "--m1-confirmation",
                     str(args.m1_confirmation.resolve()), "--suite", str(args.suite.resolve()),
                     "--tool-qualification", str(output / "tool_metadata/receipt.json")], 180),
    ]
    steps = []
    for name, command, cap in commands:
        started = time.monotonic()
        stdout_path, stderr_path = output / (name+".stdout.bin"), output / (name+".stderr.bin")
        with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
            try:
                result = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr, timeout=cap)
                code, timed_out = result.returncode, False
            except subprocess.TimeoutExpired:
                code, timed_out = 124, True
        steps.append(dict(name=name, argv=command, cwd=str(ROOT), exit_code=code,
                          timeout=timed_out, cap_seconds=cap,
                          elapsed_seconds=time.monotonic()-started,
                          stdout=identity(stdout_path), stderr=identity(stderr_path)))
        if code or timed_out:
            break
    after = {str(p): identity(p) for p in sources}
    passed = len(steps) == 3 and all(s["exit_code"] == 0 for s in steps) and before == after
    receipt = dict(status="STATIC_PREPARATION_PASS" if passed else "STATIC_PREPARATION_FAIL",
                   before=before, after=after, steps=steps,
                   HDL_compiles=0, RTL_runs=0, EDA_runs=0, execution_authorized=False,
                   pending="M2 exact tools/budget/provenance-runner decision")
    write_json(output / "receipt.json", receipt)
    print(json.dumps({k: receipt[k] for k in ("status", "HDL_compiles", "RTL_runs", "pending")}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
