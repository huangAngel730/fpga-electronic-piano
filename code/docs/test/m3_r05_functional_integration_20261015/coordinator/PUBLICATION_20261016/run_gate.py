"""Unchanged nine-check publication gate; snapshot exact staged/tracked bytes."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[5]


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(*args):
    return subprocess.check_output(["git", *args], cwd=REPO)


def snapshot():
    names = sorted(set(git("ls-files", "-z").decode("utf-8").split("\0")) - {""})
    return {"head": git("rev-parse", "HEAD").decode().strip(),
            "staged_diff_sha256": sha(git("diff", "--cached", "--binary")),
            "tracked_working_bytes": {n: sha((REPO / n).read_bytes()) for n in names if (REPO / n).is_file()}}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True, choices=("R01", "R02"))
    args = parser.parse_args()
    output = HERE / ("gate_" + args.run_id)
    output.mkdir(exist_ok=False)
    before = snapshot()
    shell = Path("C:/Users/songdongkuan/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe")
    command = [str(shell), "-NoProfile", "-File", str(REPO / "code/scripts/check_repo.ps1")]
    environment = dict(os.environ)
    environment["PATH"] = str(Path(sys.executable).parent) + os.pathsep + environment.get("PATH", "")
    start = time.monotonic()
    timeout = False
    with (output / "stdout.log").open("xb") as stdout, (output / "stderr.log").open("xb") as stderr:
        process = subprocess.Popen(command, cwd=REPO, stdout=stdout, stderr=stderr, env=environment)
        try:
            process.wait(timeout=900)
        except subprocess.TimeoutExpired:
            timeout = True
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            process.wait(timeout=30)
    after = snapshot()
    raw = (output / "stdout.log").read_bytes()
    output_text = raw.decode("utf-8", errors="replace")
    passed = not timeout and process.returncode == 0 and before == after and output_text.count("[PASS]") == 9 and "[FAIL]" not in output_text
    receipt = {"status": "PASS" if passed else "FAIL", "scope": "UNCHANGED_REPOSITORY_GATE_NOT_NEW_A_B_C_D_REGRESSION",
               "command": command, "cwd": str(REPO), "exit_code": process.returncode,
               "timed_out": timeout, "elapsed_seconds": time.monotonic() - start,
               "pass_count": output_text.count("[PASS]"), "before": before, "after": after,
               "exact_inputs_unchanged": before == after, "shell_sha256": sha(shell.read_bytes()),
               "python": str(Path(sys.executable)), "python_sha256": sha(Path(sys.executable).read_bytes()),
               "stdout_sha256": sha(raw), "stderr_sha256": sha((output / "stderr.log").read_bytes()),
               "board_release_allowed": False}
    with (output / "GATE_RECEIPT.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, indent=2)
        stream.write("\n")
    with zipfile.ZipFile(HERE / ("REPOSITORY_GATE_" + args.run_id + ".zip"), "x", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.iterdir()):
            archive.write(path, path.name)
    print(json.dumps({k: receipt[k] for k in ("status", "exit_code", "pass_count", "elapsed_seconds", "exact_inputs_unchanged")}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
