"""Bounded immutable-source runner for the single R06 software group."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def kill_tree(process: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       check=False)
    else:
        process.kill()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("REFUSE_EXISTING_OUTPUT")
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    if spec.get("schema") != "M3_R06_TX_CLOCK_RESET_RUN_SPEC_V1":
        raise SystemExit("RUN_SPEC_SCHEMA")
    timeout = spec["timeout_seconds"]
    if not isinstance(timeout, int) or not 1 <= timeout <= 90:
        raise SystemExit("TIMEOUT_RANGE")
    frozen = {}
    for item in spec["frozen_files"]:
        path = Path(item["path"])
        actual = sha256(path)
        if actual != item["sha256"]:
            raise SystemExit("FROZEN_FILE_MISMATCH:" + str(path))
        frozen[str(path)] = actual
    argv = [sys.executable if value == "{PYTHON}" else value
            for value in spec["argv"]]
    argv = [str(args.output / "products") if value == "{OUTPUT}" else value
            for value in argv]
    args.output.mkdir(parents=True)
    started = time.time()
    process = subprocess.Popen(argv, cwd=spec["cwd"], stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        timed_out = True
        kill_tree(process)
        stdout, stderr = process.communicate()
    elapsed = time.time() - started
    (args.output / "stdout.bin").write_bytes(stdout)
    (args.output / "stderr.bin").write_bytes(stderr)
    after = {path: sha256(Path(path)) for path in frozen}
    immutable = after == frozen
    status = "PASS" if process.returncode == 0 and not timed_out and immutable else "FAIL"
    receipt = {
        "schema": "M3_R06_TX_CLOCK_RESET_RUN_RECEIPT_V1",
        "status": status, "argv": argv, "cwd": spec["cwd"],
        "timeout_seconds": timeout, "elapsed_seconds": elapsed,
        "timed_out": timed_out, "exit_code": process.returncode,
        "pid": process.pid, "source_before": frozen, "source_after": after,
        "source_immutable": immutable,
        "stdout_sha256": sha256(args.output / "stdout.bin"),
        "stderr_sha256": sha256(args.output / "stderr.bin"),
        "software_groups_consumed": 1,
        "hdl_sim_eda_hardware_calls": 0,
    }
    (args.output / "receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps({key: receipt[key] for key in (
        "status", "exit_code", "elapsed_seconds", "timed_out"
    )}))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
