"""Capture new preflight stdout/stderr/identities; no old test group or HDL."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
DOCS = ROOT / "code/docs/test/t052_publication_acceptance_20261012/long_window_preparation_20261015/chat8_readiness_20261016"


def identity(path):
    h = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            h.update(block)
    return {"bytes": path.stat().st_size, "sha256": h.hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepared", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(DOCS.resolve()):
        raise SystemExit("OUTPUT_OUTSIDE_DISPATCH_WRITE_SET")
    output.mkdir()
    files = sorted([*HERE.glob("*.py"), *HERE.parent.glob("*.py")])
    before = {str(p): identity(p) for p in files}
    with zipfile.ZipFile(output / "source_before.zip", "x", zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            archive.write(path, path.relative_to(ROOT).as_posix())
    argv = [sys.executable, "-B", "-X", "utf8", str(HERE / "collect_readiness.py"),
            "--output", str(output / "evidence"), "--prepared", str(args.prepared.resolve())]
    started = time.monotonic()
    with (output / "collector.stdout.bin").open("xb") as out, \
            (output / "collector.stderr.bin").open("xb") as err:
        try:
            process = subprocess.run(argv, cwd=ROOT, stdout=out, stderr=err, timeout=120)
            code, timed_out = process.returncode, False
        except subprocess.TimeoutExpired:
            code, timed_out = 124, True
    after = {str(p): identity(p) for p in files}
    evidence = output / "evidence/READINESS_RECEIPT.json"
    observed = json.loads(evidence.read_text(encoding="utf-8")) if evidence.exists() else {}
    passed = (code == 3 and not timed_out and before == after and observed.get("status") ==
              "SOURCE_ENV_RESOURCE_MATERIAL_COMPLETE_WRITE_PROBE_SCOPE_NOT_GRANTED")
    receipt = {"status": "AUTHORIZED_PREFLIGHT_SOFTWARE_PASS_EXECUTION_PARTIAL" if passed else "FAIL",
               "exit_code": 0 if passed else 1, "child_exit_code": code, "timed_out": timed_out,
               "child_argv": argv, "cwd": str(ROOT), "actual_argv": sys.orig_argv,
               "elapsed_seconds": time.monotonic()-started, "source_before": before,
               "source_after": after, "python": identity(Path(sys.executable)),
               "stdout": identity(output / "collector.stdout.bin"),
               "stderr": identity(output / "collector.stderr.bin"),
               "new_T052_compiles_runs_checks": 0, "Git_writes": 0,
               "execution_authorized": False, "validation_level": "L0",
               "remaining_boundary": "WRITE_PROBE_SCOPE_NOT_GRANTED"}
    with (output / "RUN_RECEIPT.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    print(json.dumps({k: receipt[k] for k in ("status", "exit_code", "child_exit_code")}))
    return receipt["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
