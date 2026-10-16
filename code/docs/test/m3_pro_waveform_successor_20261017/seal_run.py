"""Own the bounded Python-only seal process, without consuming RTL rounds."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

sys.dont_write_bytecode = True
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
JOB = ROOT / "code/software/t052_runner_acceptance_candidate_20261012/windows_job.py"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")


def main():
    spec = importlib.util.spec_from_file_location("seal_job", JOB)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    argv = [sys.executable, "-B", str(HERE / "finalize.py")]
    budget = min(90, (datetime.fromisoformat("2026-10-16T20:51:00+00:00")
                      - datetime.now(timezone.utc)).total_seconds())
    assert budget > 0
    receipt = {"argv": argv, "cwd": str(ROOT), "timeout_seconds": budget,
               "start_utc": datetime.now(timezone.utc).isoformat(),
               "source_sha256": sha(HERE / "finalize.py"), "job_sha256": sha(JOB),
               "python_sha256": sha(Path(sys.executable)), "timeout": False,
               "machine": platform.node(), "platform": platform.platform(),
               "environment": {k: os.environ[k] for k in ("SystemRoot", "WINDIR", "OS", "PROCESSOR_ARCHITECTURE") if k in os.environ},
               "old_allowances_restored": False, "rtl_eda_hardware_invocations": 0}
    write(HERE / "SEAL_EXECUTION.launch.json", receipt)
    job = module.WindowsJob()
    started = time.monotonic()
    try:
        with (HERE / "SEAL_EXECUTION.stdout").open("xb") as stdout, (HERE / "SEAL_EXECUTION.stderr").open("xb") as stderr:
            process = subprocess.Popen(argv, cwd=ROOT, stdout=stdout, stderr=stderr,
                                       stdin=subprocess.DEVNULL, creationflags=0x00000004)
            receipt["pid"] = process.pid
            job.attach_and_resume(process)
            try:
                receipt["exit_code"] = process.wait(timeout=budget)
            except subprocess.TimeoutExpired:
                receipt["timeout"] = True
                job.terminate()
                receipt["exit_code"] = process.wait(timeout=5)
    finally:
        job.close()
        receipt["elapsed_seconds"] = time.monotonic() - started
        receipt["end_utc"] = datetime.now(timezone.utc).isoformat()
        receipt["stdout_sha256"] = sha(HERE / "SEAL_EXECUTION.stdout")
        receipt["stderr_sha256"] = sha(HERE / "SEAL_EXECUTION.stderr")
        write(HERE / "SEAL_EXECUTION.receipt.json", receipt)
    print((HERE / "SEAL_EXECUTION.stdout").read_text(encoding="utf-8"))
    print(json.dumps(receipt, indent=2))
    return receipt["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
