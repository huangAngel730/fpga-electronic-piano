"""Run one bounded Gowin build of the exact T056 138K L adapted project."""

from __future__ import annotations

import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


sys.dont_write_bytecode = True
SCRIPT_DIR = Path(__file__).resolve().parent
ROOT = SCRIPT_DIR.parents[1]
sys.path.insert(0, str(SCRIPT_DIR))

import check_138k_l_build as acceptance  # noqa: E402
import prepare_138k_l_project as adapter  # noqa: E402


MAX_TIMEOUT_SECONDS = 1800
DEFAULT_GOWIN = Path(
    "D:/Gowin/Gowin_V1.9.11.03_Education/"
    "Gowin_V1.9.11.03_Education_x64/IDE/bin/gw_sh.exe"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def require_new_run(path: Path) -> Path:
    resolved = acceptance.require_run(path)
    if resolved.exists():
        raise FileExistsError("REFUSE_OVERWRITE_EXISTING_RUN " + str(resolved))
    return resolved


def terminate_tree(process: subprocess.Popen[bytes]) -> None:
    if os.name == "nt":
        subprocess.run(
            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        )
    if process.poll() is None:
        process.kill()
    process.wait(timeout=30)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=int, default=MAX_TIMEOUT_SECONDS)
    parser.add_argument("--gowin", type=Path, default=DEFAULT_GOWIN)
    args = parser.parse_args()
    if not 1 <= args.timeout_seconds <= MAX_TIMEOUT_SECONDS:
        parser.error(f"timeout must be 1..{MAX_TIMEOUT_SECONDS} seconds")
    run = require_new_run(args.output)
    if not args.gowin.is_file():
        raise FileNotFoundError("GOWIN_TOOL_NOT_FOUND " + str(args.gowin))

    project = run / "project"
    adapter.generate(project)
    frozen_path = project / "receipt.json"
    project_path = project / adapter.SOURCE_PROJECT
    log_path = run / "build.log"
    receipt_path = run / "build_receipt.json"
    assessment_path = run / "assessment.json"
    before_frozen = sha256(frozen_path)
    before_project = sha256(project_path)
    command = [str(args.gowin.resolve()), "run.tcl"]
    receipt: dict[str, object] = {
        "date": "2026-10-06",
        "state": "running",
        "attempt_count": 1,
        "started": datetime.now().astimezone().isoformat(),
        "command": command,
        "cwd": str(project),
        "timeout_seconds": args.timeout_seconds,
        "timed_out": False,
        "exit_code": None,
        "programmed": False,
        "frozen_receipt_sha256_before": before_frozen,
        "project_sha256_before": before_project,
        "runner_sha256": sha256(Path(__file__)),
        "acceptance_sha256": sha256(Path(acceptance.__file__)),
    }
    write_json(receipt_path, receipt)
    with log_path.open("wb") as stream:
        process = subprocess.Popen(
            command,
            cwd=project,
            stdout=stream,
            stderr=subprocess.STDOUT,
        )
        try:
            exit_code = process.wait(timeout=args.timeout_seconds)
        except subprocess.TimeoutExpired:
            receipt["timed_out"] = True
            terminate_tree(process)
            exit_code = 124
    receipt.update(
        {
            "state": "finished" if exit_code == 0 else "failed",
            "finished": datetime.now().astimezone().isoformat(),
            "exit_code": exit_code,
            "build_log_sha256": sha256(log_path),
            "frozen_receipt_sha256_after": sha256(frozen_path),
            "project_sha256_after": sha256(project_path),
        }
    )
    write_json(receipt_path, receipt)
    if exit_code != 0:
        print(json.dumps(receipt, ensure_ascii=False, indent=2))
        return 1

    result = acceptance.validate(run)
    write_json(assessment_path, result)
    receipt["assessment_passed"] = result["passed"]
    write_json(receipt_path, receipt)
    # Re-run after the final receipt write so its SHA and all report evidence
    # are assessed exactly as left on disk.
    result = acceptance.validate(run)
    write_json(assessment_path, result)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
