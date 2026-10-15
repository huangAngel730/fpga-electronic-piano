"""Run only the M1 R02 incremental Python suite and preserve raw evidence."""

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import zipfile


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]


def identity(path):
    raw = path.read_bytes()
    return dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())


def snapshot(paths):
    return {p.relative_to(ROOT).as_posix(): identity(p) for p in paths}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to((ROOT / "code/output").resolve()) or output.exists():
        parser.error("OUTPUT_EXISTS_OR_OUTSIDE_CODE_OUTPUT")
    output.mkdir(parents=True, exist_ok=False)
    sources = sorted([*HERE.glob("*.py"), *HERE.glob("*.md")])
    protected = sorted([*HERE.parent.glob("*.py"), *HERE.parent.glob("*.md")])
    before, old_before = snapshot(sources), snapshot(protected)
    with zipfile.ZipFile(output / "source_before.zip", "x", zipfile.ZIP_DEFLATED) as archive:
        for path in sources + protected:
            archive.write(path, path.relative_to(ROOT).as_posix())
    argv = [sys.executable, "-B", "-X", "utf8", str(HERE / "test_m1_r02.py")]
    started = time.monotonic()
    with (output / "stdout.bin").open("xb") as stdout, (output / "stderr.bin").open("xb") as stderr:
        try:
            result = subprocess.run(argv, cwd=ROOT, stdout=stdout, stderr=stderr,
                                    timeout=60, check=False)
            code, timeout = result.returncode, False
        except subprocess.TimeoutExpired:
            code, timeout = 124, True
    after, old_after = snapshot(sources), snapshot(protected)
    passed = code == 0 and not timeout and before == after and old_before == old_after
    receipt = dict(schema="M3_R04_M1_R02_SOFTWARE_INCREMENT", status="PASS" if passed else "FAIL",
                   utc=datetime.now(timezone.utc).isoformat(), argv=argv, cwd=str(ROOT),
                   exit_code=code, timed_out=timeout, budget_seconds=60,
                   elapsed_seconds=time.monotonic() - started,
                   source_before=before, source_after=after,
                   protected_main2_before=old_before, protected_main2_after=old_after,
                   python=dict(path=sys.executable, version=sys.version,
                               **identity(Path(sys.executable))),
                   stdout=identity(output / "stdout.bin"), stderr=identity(output / "stderr.bin"),
                   source_snapshot=identity(output / "source_before.zip"),
                   scope="M1_R02_SOFTWARE_FIXTURES_ONLY", HDL_calls=0, RTL_runs=0,
                   EDA_runs=0, device_calls=0, real_execution_validated=False,
                   per_request_deadline="UNKNOWN", board_release_allowed=False)
    with (output / "receipt.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    print(json.dumps(dict(status=receipt["status"], exit_code=code,
                          protected_main2_unchanged=old_before == old_after,
                          source_unchanged=before == after, HDL_calls=0)))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
