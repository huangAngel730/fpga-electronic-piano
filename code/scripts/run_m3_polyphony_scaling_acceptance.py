"""D043/D044 B0 software and optional B1 RTL transport workflow.

Fresh output, bounded process tree, raw logs, receipt. No tool installation,
synthesis, git writes, serial, programming, or device operations.
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
        self.extra_env = {}
        self.extra_path = []

    def command(self, label, command, expected_exit=0):
        remaining = 1800 - (time.monotonic() - self.start)
        if remaining <= 0:
            raise RuntimeError("WORKFLOW_TIMEOUT")
        stem = f"{len(self.steps):03d}_{label}"
        out = self.output / (stem + ".stdout.bin")
        err = self.output / (stem + ".stderr.bin")
        step = {"command": command, "cwd": str(ROOT), "label": label, "expected_exit": expected_exit,
                "timeout_seconds": min(900, remaining)}
        begin = time.monotonic()
        env = os.environ.copy()
        env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
        if self.extra_path:
            env["PATH"] = os.pathsep.join(self.extra_path) + os.pathsep + env["PATH"]
        env.update(self.extra_env)
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
        # Suspension/interruption can let wait() observe an already-exited child
        # after the wall-time deadline. Its exit0 must not bypass the time bound.
        step["elapsed_limit_exceeded"] = step["elapsed_seconds"] > step["timeout_seconds"]
        self.steps.append(step)
        if step["elapsed_limit_exceeded"]:
            raise RuntimeError(f"ELAPSED_LIMIT_EXCEEDED:{label}:{step['elapsed_seconds']}")
        if step["exit_code"] != expected_exit or step["timed_out"]:
            raise RuntimeError(f"COMMAND_FAIL:{label}:{step['exit_code']}")
        return out.read_bytes()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--repo-gates", action="store_true")
    parser.add_argument("--stage", choices=("b0", "b1", "b2a"), default="b0")
    parser.add_argument("--iverilog", type=Path, default=Path("D:/Gowin/oss-cad-suite/bin/iverilog.exe"))
    parser.add_argument("--vvp", type=Path, default=Path("D:/Gowin/oss-cad-suite/bin/vvp.exe"))
    args = parser.parse_args()
    output = args.output.resolve()
    output.relative_to((ROOT / "code/output").resolve())
    output.mkdir(parents=True, exist_ok=False)
    run = Run(output)
    receipt = {"schema": 1, "utc": datetime.now(timezone.utc).isoformat(),
               "stage": "T061_B1_PROTOCOL_RTL" if args.stage == "b1" else "T061_B0_REVIEW_REPAIR", "task_complete": False,
               "runner_command": [sys.executable, *sys.argv], "cwd": str(ROOT),
               "python": {"path": sys.executable, "version": sys.version,
                          "sha256": hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()},
               "baseline_git": BASELINE,
               "scope": "B1 public RTL transport with mock operation, NOT audio" if args.stage == "b1" else "Python source budget and opaque protocol oracle only",
               "no_synthesis_STA_device_or_git_write": True,
               "new_candidate_HDL": args.stage == "b1",
               "gate_scope": "Existing repository gates may compile/simulate old T007/T019 RTL",
               "drain_scope": "B1 fixture has actual ROM/queue ownership and a bounded fail-closed fence; real sound engine and MIDI service remain unproved" if args.stage == "b1" else "Explicit software handshake contract; RTL drain bound and service bound unproved"}
    if args.stage == "b2a":
        receipt.update(stage="T061_B2A_REAL_MATH_BACKEND",
                       scope="Real lane DDS/continuous ADSR/PitchMod and shared ROM/gain/mix; NOT full MIDI/B1 integration",
                       new_candidate_HDL=True,
                       drain_scope="Actual pitch/ROM outstanding counters; cancellation retains DSP side effects")
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
        if args.stage in ("b1", "b2a"):
            candidate_paths += sorted((ROOT / "code/rtl/common/polyphony_scaling_candidate").glob("*.sv"))
            candidate_paths += sorted((ROOT / "code/tb/common/polyphony_scaling_candidate").glob("*.sv"))
        if args.stage == "b2a":
            candidate_paths += [ROOT / "code/software/audio_math_acceptance_candidate" / name
                                for name in ("dds_model.py", "envelope_model.py")]
        receipt["candidate_sources_before"] = [identity(path) for path in candidate_paths]
        protected = sorted((ROOT / "code/docs/hardware/polyphony_scaling_v1/B0_20261009").rglob("*"))
        if args.stage in ("b1", "b2a"):
            for name in ("REPAIR_20261009", "REPAIR_20261009_02", "B1_20261010"):
                protected += sorted((ROOT / "code/docs/hardware/polyphony_scaling_v1" / name).rglob("*"))
        protected += [ROOT / "code/docs" / name for name in
                      ("当前状态.md", "任务看板.md", "验证记录.md", "技术决策记录.md", "模块接口规范.md")]
        protected += [ROOT / name for name in ("code/rtl/board/electronic_piano_top.sv",
                      "code/rtl/common/audio_defs_pkg.sv", "code/constraints/electronic_piano.cst")]
        protected = [path for path in protected if path.is_file()]
        receipt["old_seal_and_shared_before"] = [identity(path) for path in protected]
        if args.stage == "b0":
            old_sources = []
            for name in ("inventory.py", "protocol_oracle.py"):
                run.command("old_" + name.split(".")[0], ["git", "show",
                            "41d2871:code/software/polyphony_scaling_candidate/" + name])
                old_sources.append(ROOT / run.steps[-1]["stdout"]["path"])
            probe = [sys.executable, "-B", "-X", "utf8", str(CANDIDATE / "review_regression.py")]
            run.command("historical_defects", probe + ["--mode", "historical", "--old-inventory", str(old_sources[0]),
                                                        "--old-oracle", str(old_sources[1])])
            run.command("repair_probes", probe + ["--mode", "current"])
            for mode in ("mutant_type", "mutant_drain"):
                run.command(mode, probe + ["--mode", mode], expected_exit=2)
        elif args.stage == "b1":
            from b1_run import run_b1
            receipt["b1"] = run_b1(run, args)
        else:
            from b2_run import run_b2
            receipt["b2a"] = run_b2(run, args)
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
        receipt["old_seal_and_shared_after"] = [identity(path) for path in protected]
        if receipt["old_seal_and_shared_before"] != receipt["old_seal_and_shared_after"]:
            raise RuntimeError("OLD_SEAL_OR_SHARED_FILE_CHANGED")
        if receipt["frozen_inputs_before"] != receipt["frozen_inputs_after"]:
            raise RuntimeError("FROZEN_CHANGED_DURING_RUN")
        if receipt["candidate_sources_before"] != receipt["candidate_sources_after"]:
            raise RuntimeError("CANDIDATE_CHANGED_DURING_RUN")
        receipt["status"] = "B1_PROTOCOL_RTL_PASS_T061_PARTIAL" if args.stage == "b1" else "B0_REPAIR_SCOPE_PASS_T061_PARTIAL"
        if args.stage == "b2a":
            receipt["status"] = "B2A_REAL_MATH_BACKEND_PASS_T061_PARTIAL"
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
