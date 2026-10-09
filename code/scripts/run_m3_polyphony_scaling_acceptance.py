"""D043/D044 B0 only: pinned source, Python assertions and conditional budget.

Fresh output, bounded process tree, raw logs, receipt. No tools installed, HDL
compile, synthesis, git writes, serial, programming, or device operations.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = ROOT / "code/software/polyphony_scaling_candidate"
sys.path.insert(0, str(CANDIDATE))
from inventory import BASELINE, FROZEN, identity, verify_manifest  # noqa: E402


class Run:
    def __init__(self, output):
        self.output = output
        self.start = time.monotonic()
        self.steps = []

    def command(self, label, command):
        remaining = 1800 - (time.monotonic() - self.start)
        if remaining <= 0:
            raise RuntimeError("WORKFLOW_TIMEOUT")
        stem = f"{len(self.steps):03d}_{label}"
        out = self.output / (stem + ".stdout.bin")
        err = self.output / (stem + ".stderr.bin")
        step = {"command": command, "cwd": str(ROOT), "label": label,
                "timeout_seconds": min(900, remaining)}
        begin = time.monotonic()
        env = os.environ.copy()
        env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
        env["PYTHONDONTWRITEBYTECODE"] = "1"
        env["PYTHONUTF8"] = "1"
        with out.open("xb") as stdout, err.open("xb") as stderr:
            process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=stdout, stderr=stderr)
            try:
                step["exit_code"] = process.wait(timeout=step["timeout_seconds"])
                step["timed_out"] = False
            except subprocess.TimeoutExpired:
                if os.name == "nt":
                    killed = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                            capture_output=True, timeout=30, check=False)
                    step["tree_kill"] = {"exit_code": killed.returncode,
                                         "stdout": killed.stdout.decode("utf-8", "replace"),
                                         "stderr": killed.stderr.decode("utf-8", "replace")}
                else:
                    process.kill()
                process.wait(timeout=30)
                step.update(exit_code=process.returncode, timed_out=True)
        step.update(elapsed_seconds=round(time.monotonic() - begin, 6),
                    stdout=identity(out), stderr=identity(err))
        self.steps.append(step)
        if step["exit_code"] != 0 or step["timed_out"]:
            raise RuntimeError(f"COMMAND_FAIL:{label}:{step['exit_code']}")
        return out.read_bytes()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repo-gates", action="store_true")
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to((ROOT / "code/output").resolve())
    output.mkdir(parents=True, exist_ok=False)
    run = Run(output)
    receipt = {"schema": 1, "utc": datetime.now(timezone.utc).isoformat(),
               "stage": "T061_B0", "task_complete": False,
               "runner_command": [sys.executable, *sys.argv], "cwd": str(ROOT),
               "python": {"path": sys.executable, "version": sys.version,
                          "sha256": hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()},
               "baseline_git": BASELINE, "scope": "Python source budget and opaque protocol oracle only",
               "no_HDL_synthesis_STA_device_or_git_write": True}
    code = 1
    try:
        run.command("git_version", ["git", "--version"])
        receipt["head"] = run.command("git_head", ["git", "rev-parse", "HEAD"]).decode().strip()
        receipt["git_status_before"] = run.command("git_status", ["git", "status", "--short"]).decode("utf-8", "replace")
        receipt["frozen_inputs_before"] = verify_manifest()
        # Also bind the manifest to the approved Git version, not just self-consistent local hashes.
        prefix = FROZEN.relative_to(ROOT).as_posix()
        git_manifest = run.command("git_manifest", ["git", "show", f"{BASELINE}:{prefix}/input_manifest.json"])
        if git_manifest.replace(b"\r\n", b"\n") != (FROZEN / "input_manifest.json").read_bytes().replace(b"\r\n", b"\n"):
            raise RuntimeError("PINNED_MANIFEST_CHANGED")
        for item in receipt["frozen_inputs_before"]:
            blob = run.command("git_frozen_input", ["git", "show", f"{BASELINE}:{item['path']}"])
            if hashlib.sha256(blob.replace(b"\r\n", b"\n")).hexdigest() != item["lf_sha256"]:
                raise RuntimeError(f"PINNED_SOURCE_CHANGED:{item['path']}")
        candidate_paths = sorted(CANDIDATE.glob("*.py")) + [Path(__file__).resolve()]
        receipt["candidate_sources_before"] = [identity(path) for path in candidate_paths]
        run.command("python_unit", [sys.executable, "-B", "-X", "utf8", "-m", "unittest", "discover",
                                    "-s", str(CANDIDATE), "-p", "test_candidate.py", "-v"])
        run.command("budget", [sys.executable, "-B", "-X", "utf8", str(CANDIDATE / "budget.py"),
                               "--output", str(output / "budget")])
        if args.repo_gates:
            shell = shutil.which("pwsh") or shutil.which("powershell")
            if not shell:
                raise RuntimeError("MISSING_POWERSHELL")
            run.command("repo_gates", [shell, "-NoProfile", "-ExecutionPolicy", "Bypass",
                                       "-File", str(ROOT / "code/scripts/check_repo.ps1")])
            receipt["repo_gates_passed"] = True
        else:
            receipt["repo_gates_passed"] = None
        receipt["frozen_inputs_after"] = verify_manifest()
        receipt["candidate_sources_after"] = [identity(path) for path in candidate_paths]
        if receipt["frozen_inputs_before"] != receipt["frozen_inputs_after"]:
            raise RuntimeError("FROZEN_CHANGED_DURING_RUN")
        if receipt["candidate_sources_before"] != receipt["candidate_sources_after"]:
            raise RuntimeError("CANDIDATE_CHANGED_DURING_RUN")
        receipt["status"] = "B0_SCOPE_PASS_T061_PARTIAL"
        code = 0
    except Exception as error:
        receipt.update(status="FAIL", error=f"{type(error).__name__}: {error}")
    receipt.update(exit_code=code, steps=run.steps,
                   elapsed_seconds=round(time.monotonic() - run.start, 6))
    receipt["outputs"] = [identity(path) for path in sorted(output.rglob("*")) if path.is_file()]
    (output / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "exit_code": code, "task_complete": False,
                      "receipt": str(output / "receipt.json"), "error": receipt.get("error")}, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
