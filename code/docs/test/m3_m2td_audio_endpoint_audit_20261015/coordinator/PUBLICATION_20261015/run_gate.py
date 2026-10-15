"""Run the unchanged repository publication gate and preserve raw evidence."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import zipfile


def sha(data):
    return hashlib.sha256(data).hexdigest()


def git(repo, *args):
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, check=True).stdout


def snapshot(repo):
    paths = git(repo, "ls-files", "-z").decode("utf-8").split("\0")
    return {
        "head": git(repo, "rev-parse", "HEAD").decode().strip(),
        "staged_diff_sha256": sha(git(repo, "diff", "--cached", "--binary")),
        "tracked_working_bytes": {
            name: sha((repo / name).read_bytes())
            for name in paths if name and (repo / name).is_file()
        },
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", choices=("R02",), required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    repo = root.parents[5]
    output = root / ("gate_" + args.run_id)
    output.mkdir(exist_ok=False)
    before = snapshot(repo)
    shell = Path("C:/Users/songdongkuan/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/powershell/pwsh.exe")
    command = [str(shell), "-NoProfile", "-File", str(repo / "code/scripts/check_repo.ps1")]
    environment = dict(os.environ)
    environment["PATH"] = str(Path(sys.executable).parent) + os.pathsep + environment.get("PATH", "")
    start = time.monotonic()
    timeout = False
    with (output / "stdout.log").open("xb") as stdout, (output / "stderr.log").open("xb") as stderr:
        process = subprocess.Popen(command, cwd=repo, stdout=stdout, stderr=stderr, env=environment)
        try:
            process.wait(timeout=900)
        except subprocess.TimeoutExpired:
            timeout = True
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            process.wait(timeout=30)
    after = snapshot(repo)
    stdout_bytes = (output / "stdout.log").read_bytes()
    stdout_text = stdout_bytes.decode("utf-8", errors="replace")
    passed = not timeout and process.returncode == 0 and before == after
    passed = passed and stdout_text.count("[PASS]") == 9 and "[FAIL]" not in stdout_text
    receipt = {
        "scope": "ORIGINAL_REPOSITORY_GATE_NOT_TARGETED_STA",
        "command": command, "cwd": str(repo),
        "exit_code": process.returncode, "timed_out": timeout,
        "elapsed_seconds": time.monotonic() - start,
        "pass_count": stdout_text.count("[PASS]"),
        "before": before, "after": after,
        "exact_inputs_unchanged": before == after,
        "shell_sha256": sha(shell.read_bytes()),
        "python_for_child_commands": sys.executable,
        "python_sha256": sha(Path(sys.executable).read_bytes()),
        "process_local_python_path_prefix": str(Path(sys.executable).parent),
        "stdout_sha256": sha(stdout_bytes),
        "stderr_sha256": sha((output / "stderr.log").read_bytes()),
        "status": "PASS" if passed else "FAIL",
        "board_release_allowed": False,
    }
    (output / "GATE_RECEIPT.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    with zipfile.ZipFile(root / ("REPOSITORY_GATE_" + args.run_id + ".zip"), "x", zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(output.iterdir()):
            archive.write(path, path.name)
    print(json.dumps({key: receipt[key] for key in ("status", "exit_code", "pass_count", "elapsed_seconds", "exact_inputs_unchanged")}))
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
