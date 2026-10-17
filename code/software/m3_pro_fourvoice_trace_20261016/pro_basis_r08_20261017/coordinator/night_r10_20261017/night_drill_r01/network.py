"""Single-publisher Git transport with a 30 second owned-process deadline."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
import types
import threading
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[7]
OUTPUT = ROOT / "code/output/m3_m2_night_drill_20261017"
JOB_PATH = ROOT / "code/software/t052_runner_acceptance_candidate_20261012/windows_job.py"
JOB_SHA = "5450b8943b0616cc0f8ad7147c1c6a4b20eb4f04d8a7cc3fb515825941c0df1b"
GIT = "C:/Program Files/Git/cmd/git.exe"
COMMANDS = {
    "fetch": ["fetch", "origin"],
    "remote": ["ls-remote", "--exit-code", "origin", "refs/heads/develop"],
    "push": ["push", "--porcelain", "--quiet", "origin", "develop"],
}


def write_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def run(kind: str, operation_id: str, retry_basis: str | None = None) -> int:
    if not operation_id.replace("_", "").replace("-", "").isalnum():
        raise ValueError("UNSAFE_OPERATION_ID")
    state = OUTPUT / "state" / "network.json"
    ledger = json.loads(state.read_text(encoding="utf-8")) if state.exists() else {}
    attempts = ledger.setdefault(operation_id, [])
    if attempts and (len(attempts) >= 2 or not retry_basis or attempts[-1]["status"] == "OK"):
        raise RuntimeError("RETRY_REQUIRES_NEW_BASIS_AND_UNUSED_SINGLE_RETRY")
    run_dir = OUTPUT / "runs" / f"{operation_id}_{len(attempts) + 1:02d}"
    run_dir.mkdir(parents=True, exist_ok=False)
    argv = [GIT, "-c", "http.proxy=http://127.0.0.1:7892", "-c", "http.version=HTTP/1.1",
            "-c", "credential.interactive=false", *COMMANDS[kind]]
    source = JOB_PATH.read_bytes()
    if hashlib.sha256(source).hexdigest() != JOB_SHA:
        raise RuntimeError("JOB_DEPENDENCY_CHANGED")
    module = types.ModuleType("frozen_owned_job")
    exec(compile(source, str(JOB_PATH), "exec"), module.__dict__)
    record = {"kind": kind, "operation_id": operation_id, "attempt": len(attempts) + 1,
              "retry_basis": retry_basis, "argv": argv, "cwd": str(ROOT),
              "utc": datetime.now(timezone.utc).isoformat(), "timeout_seconds": 30,
              "process_wait_seconds": 28, "status": "STARTING", "pid": None}
    attempts.append(record)
    write_json(state, ledger)
    write_json(run_dir / "LAUNCH.json", record)
    start = time.monotonic()
    job = module.WindowsJob()
    def deadline_exit():
        try:
            job.terminate()
        finally:
            # Closing this process also closes its KILL_ON_JOB_CLOSE handle.
            # No potentially blocking evidence write precedes the fallback.
            os._exit(124)
    watchdog = threading.Timer(29, deadline_exit)
    watchdog.daemon = True
    watchdog.start()
    proc = None
    try:
        with (run_dir / "stdout.bin").open("xb") as stdout, (run_dir / "stderr.bin").open("xb") as stderr:
            proc = subprocess.Popen(argv, cwd=ROOT, stdout=stdout, stderr=stderr,
                                    creationflags=0x00000004 | 0x08000000, env=os.environ.copy())
            record["pid"] = proc.pid
            job.attach_and_resume(proc)
            write_json(run_dir / "LAUNCH.json", record)
            try:
                code = proc.wait(timeout=max(0.1, 28 - (time.monotonic() - start)))
                record["status"] = "OK" if code == 0 else "FAILED"
            except subprocess.TimeoutExpired:
                record["termination"] = job.terminate()
                proc.wait(timeout=1.5)
                record["status"] = "UNKNOWN_TIMEOUT" if kind == "push" else "TIMEOUT"
                code = 124
    except Exception as exc:
        if proc is not None and proc.poll() is None:
            job.terminate()
        code = 125
        record["status"] = "ERROR"
        record["exception"] = repr(exc)
    finally:
        job.close()
    record.update(exit_code=code, elapsed_seconds=time.monotonic() - start,
                  process_exit_code=None if proc is None else proc.poll())
    record["within_30_seconds"] = record["elapsed_seconds"] <= 30
    write_json(run_dir / "RESULT.json", record)
    write_json(state, ledger)
    watchdog.cancel()
    print(json.dumps(record, ensure_ascii=False))
    return code


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("kind", choices=COMMANDS)
    parser.add_argument("operation_id")
    parser.add_argument("--retry-basis")
    args = parser.parse_args()
    raise SystemExit(run(args.kind, args.operation_id, args.retry_basis))
