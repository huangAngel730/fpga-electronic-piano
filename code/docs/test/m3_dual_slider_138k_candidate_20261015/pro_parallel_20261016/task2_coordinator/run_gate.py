"""One bounded repository gate; bind raw logs to unchanged published inputs."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import time

COORD = Path(__file__).resolve().parent
ROOT = COORD.parents[5]


def identity(path):
    with path.open("rb") as stream:
        digest = hashlib.file_digest(stream, "sha256").hexdigest()
    return {"bytes": path.stat().st_size, "sha256": digest}


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n",
                    encoding="utf-8", newline="\n")


def snapshot():
    tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT,
                             capture_output=True, check=True).stdout
    names = {x.decode("utf-8") for x in tracked.split(b"\0") if x}
    planned = json.loads((COORD / "PUBLICATION_FILES.json").read_text(encoding="utf-8"))
    names.update(planned["paths"])
    return {p: identity(ROOT / p) for p in sorted(names) if (ROOT / p).is_file()}


def main():
    if len(sys.argv) != 2 or not re.fullmatch(r"GATE_R[0-9]{2}", sys.argv[1]):
        raise SystemExit("Expected fresh GATE_Rnn directory name")
    out = COORD / sys.argv[1]
    out.mkdir(exist_ok=False)
    before = snapshot()
    save(out / "INPUTS_BEFORE.json", before)
    shell = Path("C:/Windows/System32/WindowsPowerShell/v1.0/powershell.exe")
    wrapper = COORD / "publication_gate.ps1"
    argv = [str(shell), "-NoProfile", "-File", str(wrapper)]
    started = datetime.now(timezone.utc).isoformat()
    timer = time.monotonic()
    process = subprocess.Popen(argv, cwd=ROOT, stdin=subprocess.DEVNULL,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    error = None
    try:
        stdout, stderr = process.communicate(timeout=900)
    except subprocess.TimeoutExpired:
        error = "GATE_TIMEOUT_900S"
        cleanup = subprocess.run(["C:/Windows/System32/taskkill.exe", "/PID",
                                  str(process.pid), "/T", "/F"], capture_output=True,
                                 stdin=subprocess.DEVNULL, check=False, timeout=15)
        (out / "cleanup.stdout.bin").write_bytes(cleanup.stdout)
        (out / "cleanup.stderr.bin").write_bytes(cleanup.stderr)
        stdout, stderr = process.communicate(timeout=15)
    (out / "stdout.bin").write_bytes(stdout)
    (out / "stderr.bin").write_bytes(stderr)
    readable = stdout.decode("utf-8", errors="replace")
    (out / "stdout.txt").write_text(readable, encoding="utf-8", newline="\n")
    after = snapshot()
    save(out / "INPUTS_AFTER.json", after)
    passed_lines = re.findall(r"^\s*\[PASS\].*$", readable, re.MULTILINE)
    failed_lines = re.findall(r"^\s*\[FAIL\].*$", readable, re.MULTILINE)
    passed = (process.returncode == 0 and error is None and len(passed_lines) == 9
              and not failed_lines and "All repository checks passed." in readable
              and before == after)
    receipt = {
        "status": "PASS" if passed else "FAIL", "argv": argv, "cwd": str(ROOT),
        "machine": platform.node(), "start_utc": started,
        "end_utc": datetime.now(timezone.utc).isoformat(),
        "seconds": time.monotonic() - timer, "exit_code": process.returncode,
        "error": error, "pass_count": len(passed_lines), "pass_lines": passed_lines,
        "fail_lines": failed_lines, "candidate_input_count": len(before),
        "input_bytes_unchanged": before == after,
        "shell": {"path": str(shell), **identity(shell)},
        "python": {"path": sys.executable, **identity(Path(sys.executable))},
        "wrapper": {"path": str(wrapper), **identity(wrapper)},
        "raw_stdout": identity(out / "stdout.bin"),
        "raw_stderr": identity(out / "stderr.bin"),
        "environment_keys": sorted(os.environ),
        "scope": "repository publication gate, not new Pro functional or physical evidence",
        "new_functional_rounds": 0, "board_release_allowed": False}
    save(out / "GATE_RECEIPT.json", receipt)
    print(json.dumps({k: receipt[k] for k in
                      ("status", "seconds", "exit_code", "pass_count", "input_bytes_unchanged")}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
