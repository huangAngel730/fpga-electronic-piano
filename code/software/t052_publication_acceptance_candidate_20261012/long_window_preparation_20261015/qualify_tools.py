"""Read static Icarus identities and run exactly two metadata-only -V queries."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import time

from prepare import identity, inventory, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--suite", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("OUTPUT_EXISTS")
    before = inventory(args.suite)
    args.output.mkdir(parents=True)
    environment = os.environ.copy()
    environment["PATH"] = os.pathsep.join((str(args.suite / "bin"),
                                           str(args.suite / "lib"), environment.get("PATH", "")))
    environment["IVERILOG_ROOT"] = str(args.suite / "lib/ivl")
    steps = []
    for name, pattern in (("iverilog", rb"Icarus Verilog version[^\r\n]+"),
                          ("vvp", rb"Icarus Verilog runtime version[^\r\n]+")):
        command = [str((args.suite / ("bin/"+name+".exe")).resolve()), "-V"]
        started = time.monotonic()
        stdout, stderr = args.output / (name+".stdout.bin"), args.output / (name+".stderr.bin")
        with stdout.open("xb") as out, stderr.open("xb") as err:
            try:
                process = subprocess.run(command, cwd=args.output, env=environment,
                                         stdout=out, stderr=err, timeout=30)
                code, timed_out = process.returncode, False
            except subprocess.TimeoutExpired:
                code, timed_out = 124, True
        match = re.search(pattern, stdout.read_bytes()+stderr.read_bytes())
        steps.append(dict(argv=command, exit_code=code, timeout=timed_out,
                          elapsed_seconds=time.monotonic()-started,
                          version=match[0].decode("ascii") if match else None,
                          stdout=identity(stdout), stderr=identity(stderr)))
        if code or not match:
            break
    after = inventory(args.suite)
    passed = not before["missing"] and before == after and len(steps) == 2 and all(
        s["exit_code"] == 0 and s["version"] for s in steps)
    receipt = dict(status="TOOL_METADATA_PASS" if passed else "TOOL_METADATA_FAIL",
                   steps=steps, before=before, after=after,
                   HDL_compiles=0, RTL_runs=0, version_queries=len(steps),
                   dynamic_loaded_dependencies="UNKNOWN")
    write_json(args.output / "receipt.json", receipt)
    print(json.dumps(dict(status=receipt["status"], version_queries=len(steps),
                          inventory_files=len(before["files"]))))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
