"""Run the repository gate once and preserve an exact, hash-bound receipt."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise SystemExit("output already exists; refuse overwrite")
    args.output.mkdir(parents=True)
    repo = Path(__file__).resolve().parents[3]
    command = [
        "powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", "code/scripts/check_repo.ps1",
    ]
    environment = os.environ.copy()
    environment["PATH"] = str(Path(sys.executable).resolve().parent) + os.pathsep + environment["PATH"]
    completed = subprocess.run(
        command, cwd=repo, env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    stdout_path = args.output / "stdout.bin"
    stderr_path = args.output / "stderr.bin"
    stdout_path.write_bytes(completed.stdout)
    stderr_path.write_bytes(completed.stderr)
    status = (
        "PASS" if completed.returncode == 0 and
        b"All repository checks passed." in completed.stdout and
        not completed.stderr else "FAIL"
    )
    receipt = {
        "schema": 1,
        "status": status,
        "exit_code": completed.returncode,
        "command": command,
        "cwd": str(repo),
        "python_executable": str(Path(sys.executable).resolve()),
        "stdout_bytes": len(completed.stdout),
        "stdout_sha256": digest(completed.stdout),
        "stderr_bytes": len(completed.stderr),
        "stderr_sha256": digest(completed.stderr),
    }
    (args.output / "receipt.json").write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(receipt, sort_keys=True))
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
