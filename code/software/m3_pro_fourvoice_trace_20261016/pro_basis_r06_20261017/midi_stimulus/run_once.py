"""One bounded R06 software run with immutable source binding and raw streams."""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    root = Path(__file__).resolve().parents[5]
    for entry in spec["bound_inputs"]:
        path = root / entry["path"]
        if not path.is_file() or sha(path) != entry["sha256"]:
            raise SystemExit("BOUND_INPUT_MISMATCH:" + entry["path"])
    args.output.mkdir(parents=True, exist_ok=False)
    products = args.output / "products"
    command = [sys.executable, "-B", "-X", "utf8", str(Path(__file__).with_name("selftest.py")),
               "--parameters", str(Path(__file__).with_name("parameters.json")),
               "--cases", str(Path(__file__).with_name("cases.json")),
               "--output", str(products)]
    started = time.time()
    try:
        done = subprocess.run(command, cwd=root, capture_output=True, timeout=spec["timeout_seconds"])
        timed_out = False
    except subprocess.TimeoutExpired as exc:
        done = exc
        timed_out = True
    stdout = done.stdout or b""
    stderr = done.stderr or b""
    (args.output / "stdout.bin").write_bytes(stdout)
    (args.output / "stderr.bin").write_bytes(stderr)
    exit_code = None if timed_out else done.returncode
    receipt = {"status": "PASS" if exit_code == 0 else "FAIL",
               "argv": command, "cwd": str(root), "timeout_seconds": spec["timeout_seconds"],
               "elapsed_seconds": time.time() - started, "timed_out": timed_out,
               "exit_code": exit_code, "stdout_sha256": hashlib.sha256(stdout).hexdigest(),
               "stderr_sha256": hashlib.sha256(stderr).hexdigest(),
               "hdl_sim_eda_hardware_calls": 0}
    (args.output / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(receipt))
    return 0 if receipt["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
