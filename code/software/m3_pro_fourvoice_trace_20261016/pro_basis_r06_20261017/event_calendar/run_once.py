"""Run one immutable, bounded R06 event-calendar software group."""

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
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    root = Path(__file__).resolve().parents[5]
    for item in spec["bound_inputs"]:
        path = root / item["path"]
        if not path.is_file() or path.stat().st_size != item["bytes"] or (
            sha256(path) != item["sha256"]
        ):
            raise SystemExit("BOUND_INPUT_MISMATCH:" + item["path"])
    args.output.mkdir(parents=True, exist_ok=False)
    command = [
        sys.executable, "-B", "-X", "utf8", str(Path(__file__).with_name("selftest.py")),
        "--plan", str(root / spec["midi_plan"]),
        "--cases", str(Path(__file__).with_name("cases.json")),
        "--output", str(args.output / "products"),
    ]
    started = time.time()
    try:
        done = subprocess.run(command, cwd=root, capture_output=True,
                              timeout=spec["timeout_seconds"])
        timed_out = False
        stdout = done.stdout
        stderr = done.stderr
        exit_code = done.returncode
    except subprocess.TimeoutExpired as exc:
        timed_out = True
        stdout = exc.stdout or b""
        stderr = exc.stderr or b""
        exit_code = None
    elapsed = time.time() - started
    (args.output / "stdout.bin").write_bytes(stdout)
    (args.output / "stderr.bin").write_bytes(stderr)
    receipt = {
        "schema": "M3_R06_EVENT_CALENDAR_RUN_RECEIPT_V1",
        "status": "PASS" if exit_code == 0 else "FAIL",
        "argv": command,
        "cwd": str(root),
        "timeout_seconds": spec["timeout_seconds"],
        "elapsed_seconds": elapsed,
        "timed_out": timed_out,
        "exit_code": exit_code,
        "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
        "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
        "software_groups_consumed": 1,
        "hdl_sim_eda_hardware_calls": 0,
    }
    (args.output / "receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
