"""Bounded software execution with immutable preflight and original dual streams."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
import time

from consume_capture import sha256


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = args.command
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        parser.error("command required")
    args.output.mkdir(parents=True, exist_ok=False)
    sources = {str(p.resolve()): sha256(p) for p in Path(__file__).parent.glob("*.py")}
    preflight = {"command": command, "cwd": str(Path.cwd()), "timeout_seconds": 300,
                 "python": str(Path(sys.executable).resolve()), "python_version": sys.version,
                 "python_sha256": sha256(sys.executable), "source_sha256": sources,
                 "started_utc": datetime.now(timezone.utc).isoformat(),
                 "execution_kind": "SOFTWARE_ONLY", "EDA_executions": 0}
    (args.output / "PREFLIGHT.json").write_text(json.dumps(preflight, indent=2) + "\n", encoding="utf-8")
    start = time.monotonic()
    with (args.output / "stdout.txt").open("xb") as out, (args.output / "stderr.txt").open("xb") as err:
        try:
            completed = subprocess.run(command, stdout=out, stderr=err, timeout=300, check=False)
            code, timed_out = completed.returncode, False
        except subprocess.TimeoutExpired:
            code, timed_out = 124, True
    result = {**preflight, "exit_code": code, "timed_out": timed_out,
              "elapsed_seconds": time.monotonic() - start,
              "ended_utc": datetime.now(timezone.utc).isoformat(),
              "source_after_sha256": {p: sha256(p) for p in sources},
              "stdout_sha256": sha256(args.output / "stdout.txt"),
              "stderr_sha256": sha256(args.output / "stderr.txt")}
    (args.output / "RUN_RECEIPT.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
