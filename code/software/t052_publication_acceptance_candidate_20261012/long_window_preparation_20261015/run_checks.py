"""Capture software self-test raw logs and identities; no HDL operations."""
import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

from prepare import HERE, TB, audit_sources, identity, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        parser.error("OUTPUT_EXISTS")
    output.mkdir(parents=True)
    paths = sorted([*HERE.glob("*.py"), *TB.glob("*.sv")])
    before = {str(p): identity(p) for p in paths}
    # Preserve tested source before invocation, including any failed version.
    with zipfile.ZipFile(output / "source_before.zip", "x", zipfile.ZIP_DEFLATED) as z:
        for p in paths:
            z.write(p, p.relative_to(HERE.parents[3]).as_posix())
    command = [sys.executable, "-B", "-X", "utf8", str(HERE / "test_long.py")]
    started = time.monotonic()
    with (output / "stdout.bin").open("xb") as stdout, (output / "stderr.bin").open("xb") as stderr:
        try:
            process = subprocess.run(command, cwd=HERE, stdout=stdout, stderr=stderr, timeout=60)
            code, timed_out = process.returncode, False
        except subprocess.TimeoutExpired:
            code, timed_out = 124, True
    after = {str(p): identity(p) for p in paths}
    stderr = (output / "stderr.bin").read_text(encoding="utf-8", errors="replace")
    passed = code == 0 and not timed_out and before == after and "Ran 17 tests" in stderr and "\nOK\n" in stderr
    result = dict(status="SOFTWARE_SELFTEST_PASS" if passed else "SOFTWARE_SELFTEST_FAIL",
                  command=command, cwd=str(HERE), exit_code=code, timeout=timed_out,
                  elapsed_seconds=time.monotonic()-started, before=before, after=after,
                  python=identity(Path(sys.executable)), python_version=sys.version,
                  stdout=identity(output / "stdout.bin"), stderr=identity(output / "stderr.bin"),
                  scope="HANDWRITTEN_SOFTWARE_FIXTURES_ONLY", HDL_calls=0, RTL_runs=0,
                  source_audit=audit_sources(), complete_T052=False)
    write_json(output / "receipt.json", result)
    print(json.dumps({k: result[k] for k in ("status", "exit_code", "elapsed_seconds", "scope")}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
