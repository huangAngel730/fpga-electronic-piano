"""Consume the one bounded R7-C software group and preserve raw streams."""

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
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if spec.get("schema") != "M3_R07_ORACLE_BRIDGE_RUN_SPEC_V1":
        raise SystemExit("BAD_RUN_SPEC")
    root = Path(spec["cwd"]).resolve()
    output = args.output.resolve()
    if output != (root / spec["exclusive_output"]).resolve():
        raise SystemExit("EXCLUSIVE_OUTPUT_MISMATCH")
    if output.exists():
        raise SystemExit("OUTPUT_EXISTS")
    frozen_after = []
    for item in spec["frozen_files"]:
        path = root / item["path"]
        actual = sha256(path) if path.is_file() else None
        if actual != item["sha256"] or path.stat().st_size != item["bytes"]:
            raise SystemExit("FROZEN_INPUT_MISMATCH:" + item["path"])
        frozen_after.append({"path": item["path"], "sha256": actual, "matches": True})
    output.mkdir(parents=True)
    command = [
        sys.executable,
        "-B",
        "-X",
        "utf8",
        str(root / spec["selftest"]),
        "--spec",
        str(spec_path),
        "--cases",
        str(root / spec["cases"]),
        "--output",
        str(output / "products"),
    ]
    started_utc = time.time()
    try:
        process = subprocess.run(
            command,
            cwd=root,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=spec["timeout_seconds"],
            check=False,
        )
        timed_out = False
        exit_code = process.returncode
        stdout = process.stdout
        stderr = process.stderr
    except subprocess.TimeoutExpired as error:
        timed_out = True
        exit_code = 124
        stdout = error.stdout or b""
        stderr = error.stderr or b""
    elapsed = time.time() - started_utc
    (output / "stdout.bin").write_bytes(stdout)
    (output / "stderr.bin").write_bytes(stderr)
    for item in frozen_after:
        path = root / item["path"]
        item["sha256_after"] = sha256(path)
        item["matches"] = item["sha256_after"] == item["sha256"]
    receipt = {
        "schema": "M3_R07_ORACLE_BRIDGE_RUN_RECEIPT_V1",
        "status": "PASS" if exit_code == 0 and not timed_out and all(item["matches"] for item in frozen_after) else "FAIL",
        "argv": command,
        "cwd": str(root),
        "timeout_seconds": spec["timeout_seconds"],
        "elapsed_seconds": elapsed,
        "timed_out": timed_out,
        "exit_code": exit_code,
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "frozen_files_after": frozen_after,
        "r7c_software_groups_consumed": 1,
        "repair_groups_consumed": 0,
        "m1_math_or_oracle_runs": 0,
        "hdl_eda_hardware_runs": 0,
        "real_capture_cases": 0,
        "board_release_allowed": False,
    }
    (output / "receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
