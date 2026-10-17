"""Run one frozen normalized-intake software group and preserve raw streams."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    spec_path = args.spec.resolve()
    output = args.output.resolve()
    if output.exists():
        raise SystemExit("output exists")
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if spec["schema"] != "M3_R06_NORMALIZED_INTAKE_RUN_SPEC_V1":
        raise SystemExit("bad spec")
    if output != Path(spec["exclusive_output"]).resolve():
        raise SystemExit("exclusive output mismatch")
    frozen = spec["frozen_files"]
    for item in frozen:
        path = Path(item["path"]).resolve()
        if not path.is_file() or sha256(path) != item["sha256"]:
            raise SystemExit("identity mismatch before run: " + item["path"])
    output.mkdir(parents=True)
    products = output / "products"
    command = [
        sys.executable,
        "-B",
        "-X",
        "utf8",
        str(Path(spec["selftest"]).resolve()),
        "--spec",
        str(spec_path),
        "--cases",
        str(Path(spec["cases"]).resolve()),
        "--output",
        str(products),
    ]
    started = time.time()
    timed_out = False
    try:
        process = subprocess.run(
            command,
            cwd=Path(spec["cwd"]),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=spec["timeout_seconds"],
            check=False,
        )
        exit_code = process.returncode
        stdout = process.stdout
        stderr = process.stderr
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        exit_code = 124
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
    elapsed = time.time() - started
    (output / "stdout.bin").write_bytes(stdout)
    (output / "stderr.bin").write_bytes(stderr)
    unchanged = []
    for item in frozen:
        path = Path(item["path"]).resolve()
        unchanged.append({"path": item["path"], "sha256": sha256(path), "matches": sha256(path) == item["sha256"]})
    receipt = {
        "schema": "M3_R06_NORMALIZED_INTAKE_RUN_RECEIPT_V1",
        "status": "PASS" if exit_code == 0 and not timed_out and all(item["matches"] for item in unchanged) else "FAIL",
        "argv": command,
        "cwd": spec["cwd"],
        "timeout_seconds": spec["timeout_seconds"],
        "elapsed_seconds": elapsed,
        "timed_out": timed_out,
        "exit_code": exit_code,
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "frozen_files_after": unchanged,
        "old_checkers_or_mappers_run": 0,
        "hdl_eda_hardware_runs": 0,
        "board_release_allowed": False,
    }
    (output / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
