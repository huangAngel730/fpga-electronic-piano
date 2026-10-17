"""Single publication gate, binding the tracked and planned exact input bytes."""
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time

SOFT = Path(__file__).resolve().parent
ROOT = SOFT.parents[4]
DOC = ROOT/"code/docs/test/m3_pro_fourvoice_trace_20261016/D/pro_monitor_20261017"


def identity(path):
    with path.open("rb") as stream:
        return {"bytes": path.stat().st_size,
                "sha256": hashlib.file_digest(stream, "sha256").hexdigest()}


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def snapshot():
    output = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, check=True, capture_output=True).stdout
    names = {p.decode("utf-8") for p in output.split(b"\0") if p}
    names.update(json.loads((DOC/"PUBLICATION_FILES.json").read_text(encoding="utf-8"))["paths"])
    return {p: identity(ROOT/p) for p in sorted(names) if (ROOT/p).is_file()}


def main():
    out = DOC/"GATE_R01"
    out.mkdir(exist_ok=False)
    before = snapshot()
    save(out/"INPUTS_BEFORE.json", before)
    shell = Path("C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
    wrapper = SOFT/"publication_gate.ps1"
    argv = [str(shell), "-NoProfile", "-File", str(wrapper)]
    job_path = ROOT/"code/software/t052_runner_acceptance_candidate_20261012/windows_job.py"
    spec = importlib.util.spec_from_file_location("monitor_gate_job", job_path)
    jobmod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(jobmod)
    start = datetime.now(timezone.utc).isoformat()
    began = time.monotonic()
    launch = {"argv": argv, "cwd": str(ROOT), "start_utc": start, "timeout_s": 900,
              "shell": identity(shell), "wrapper": identity(wrapper), "job_helper": identity(job_path)}
    save(out/"LAUNCH.json", launch)
    job = jobmod.WindowsJob()
    timeout = False
    try:
        with (out/"stdout.bin").open("xb") as stdout, (out/"stderr.bin").open("xb") as stderr:
            proc = subprocess.Popen(argv, cwd=ROOT, stdin=subprocess.DEVNULL, stdout=stdout,
                                    stderr=stderr, creationflags=0x00000004)
            job.attach_and_resume(proc)
            try:
                exit_code = proc.wait(timeout=900)
            except subprocess.TimeoutExpired:
                timeout = True
                job.terminate()
                exit_code = proc.wait(timeout=5)
    finally:
        job.close()
    after = snapshot()
    save(out/"INPUTS_AFTER.json", after)
    text = (out/"stdout.bin").read_bytes().decode("utf-8", errors="replace")
    passed_lines = re.findall(r"^\s*\[PASS\].*$", text, re.M)
    failed_lines = re.findall(r"^\s*\[FAIL\].*$", text, re.M)
    passed = exit_code == 0 and not timeout and len(passed_lines) == 9 and not failed_lines
    passed = passed and "All repository checks passed." in text and before == after
    receipt = {"status": "PASS" if passed else "FAIL", **launch,
               "end_utc": datetime.now(timezone.utc).isoformat(), "seconds": time.monotonic()-began,
               "exit_code": exit_code, "timeout": timeout, "pid": proc.pid,
               "pass_count": len(passed_lines), "pass_lines": passed_lines, "fail_lines": failed_lines,
               "candidate_input_count": len(before), "input_bytes_unchanged": before == after,
               "stdout": identity(out/"stdout.bin"), "stderr": identity(out/"stderr.bin"),
               "scope": "Repository publication gate only; no new Pro DUT or EDA evidence",
               "new_monitor_rounds": 0, "board_release_allowed": False}
    save(out/"GATE_RECEIPT.json", receipt)
    print(json.dumps({k: receipt[k] for k in ("status", "seconds", "exit_code", "pass_count", "input_bytes_unchanged")}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
