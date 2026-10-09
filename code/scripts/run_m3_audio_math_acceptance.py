"""D043 new candidate entry point. Fail closed until real A1/A2 are complete.

No installation, simulation, synthesis or device access. --repo-gates invokes
only the existing repository gate when explicitly requested. Output is fresh.
--component-only is a self-test, never a T060/A1 acceptance pass.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = ROOT / "code/software/audio_math_acceptance_candidate"
BASELINE = "6f3e813"
FROZEN_PREFIX = "code/rtl/138K_try/clock_trials_20261005/H_pll_core40_route2"
PINNED_CAPTURE = {
    "audio_observation.jsonl": "d17cf87952ac0c663e681e0b47051e9412af4a2979fb509aaa5d7114d5b32cc5",
    "midi_pcm.capture": "bd0035de464cb8c757c7e29a132073181e9e8179aa8303ab1ec110c6990042d6",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(path):
    data = path.read_bytes()
    return {"path": str(path), "bytes": len(data), "sha256": sha(data),
            "lf_sha256": sha(data.replace(b"\r\n", b"\n"))}


class Run:
    def __init__(self, output, total_seconds, step_seconds):
        self.output = output
        self.start = time.monotonic()
        self.total_seconds = total_seconds
        self.step_seconds = step_seconds
        self.steps = []

    def command(self, label, command, env=None):
        remaining = self.total_seconds - (time.monotonic() - self.start)
        if remaining <= 0:
            raise RuntimeError("WORKFLOW_TIMEOUT")
        stem = f"{len(self.steps):03d}_{label}"
        stdout = self.output / (stem + ".stdout.bin")
        stderr = self.output / (stem + ".stderr.bin")
        begin = time.monotonic()
        step = {"command": command, "cwd": str(ROOT), "label": label,
                "timeout_seconds": min(self.step_seconds, remaining)}
        try:
            with stdout.open("xb") as out, stderr.open("xb") as err:
                process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=out, stderr=err)
                try:
                    step["exit_code"] = process.wait(timeout=step["timeout_seconds"])
                    step["timed_out"] = False
                except subprocess.TimeoutExpired:
                    # Kill the process tree on Windows; no unrelated processes.
                    if os.name == "nt":
                        killer = subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"],
                                                capture_output=True, timeout=30, check=False)
                        step["timeout_tree_kill"] = {"exit_code": killer.returncode,
                                                     "stdout": killer.stdout.decode("utf-8", "replace"),
                                                     "stderr": killer.stderr.decode("utf-8", "replace")}
                    else:
                        process.kill()
                    process.wait(timeout=30)
                    step["exit_code"], step["timed_out"] = process.returncode, True
        except OSError as error:
            step.update(exit_code=None, timed_out=False, launch_error=str(error))
        step["elapsed_seconds"] = round(time.monotonic() - begin, 6)
        step["stdout"], step["stderr"] = identity(stdout), identity(stderr)
        self.steps.append(step)
        if step["exit_code"] != 0 or step["timed_out"]:
            raise RuntimeError(f"COMMAND_FAIL:{label}:{step['exit_code']}")
        return stdout.read_bytes()


def frozen_inventory(run):
    paths = run.command("frozen_tree", ["git", "ls-tree", "-r", "--name-only", BASELINE, "--",
                                        FROZEN_PREFIX + "/sources", FROZEN_PREFIX + "/rom"])
    paths = paths.decode("utf-8").splitlines()
    if not paths or len([p for p in paths if "/rom/" in p]) != 7:
        raise RuntimeError("FROZEN_SOURCE_OR_ROM_LIST_MISSING")
    paths += ["code/tb/board/platform_audio_acceptance_20261005/observer.sv.in",
              "code/tb/board/m3_midi_pcm_acceptance/tb_midi_pcm.sv",
              "code/scripts/run_platform_audio_capture.py",
              "code/docs/evidence/platform_preparation_20261005.json"]
    result = []
    for path in paths:
        expected = run.command("frozen_blob", ["git", "show", f"{BASELINE}:{path}"])
        actual = identity(ROOT / path)
        if actual["lf_sha256"] != sha(expected.replace(b"\r\n", b"\n")):
            raise RuntimeError("FROZEN_IDENTITY_CHANGED:" + path)
        actual.update(git_baseline=BASELINE, git_blob_sha256=sha(expected))
        result.append(actual)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--capture-root", type=Path,
                        default=ROOT / "code/output/platform_preparation_20261005/capture2")
    parser.add_argument("--component-only", action="store_true")
    parser.add_argument("--repo-gates", action="store_true")
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--step-timeout", type=int, default=900)
    args = parser.parse_args()
    if not (1 <= args.timeout <= 1800 and 1 <= args.step_timeout <= 900):
        parser.error("timeout must be1..1800; step-timeout1..900")
    output = args.output.resolve()
    allowed_output = (ROOT / "code/output").resolve()
    if not output.is_relative_to(allowed_output) or output == allowed_output:
        parser.error("output must be a new child of repository code/output")
    if output.exists():
        parser.error("refusing existing output: " + str(output))
    output.mkdir(parents=True)
    run = Run(output, args.timeout, args.step_timeout)
    receipt = {"schema": 1, "started_utc": datetime.now(timezone.utc).isoformat(),
               "status": "RUNNING", "task_baseline": BASELINE,
               "invocation": [sys.executable, *sys.argv], "cwd": str(ROOT),
               "python": {"version": sys.version, **identity(Path(sys.executable))},
               "environment": {key: os.environ.get(key) for key in ("PATH", "PYTHONPATH", "PYTHONHOME")},
               "limits": {"total_seconds": args.timeout, "per_step_seconds": args.step_timeout},
               "a1_complete": False, "a2_complete": False, "t060_complete": False,
               "t061_started": False, "real_dds_timeline_integrated": False,
               "complete_56_original_negatives_run": False, "real_capture_replayed": False,
               "unverified": ["Accepted-event/control/LFO timeline integration", "Real capture2 DDS replay",
                              "Envelope/ROM/gain/mix PCM golden", "56 original counterexamples",
                              "T061 inventory/budget/scheduler/statebank/voice candidate", "Any hardware evidence"]}
    exit_code = 1
    try:
        receipt["git_head"] = run.command("git_head", ["git", "rev-parse", "HEAD"]).decode().strip()
        receipt["git_version"] = run.command("git_version", ["git", "--version"]).decode().strip()
        receipt["frozen_inputs"] = frozen_inventory(run)
        receipt["candidate_sources"] = [identity(path) for path in sorted(CANDIDATE.glob("*.py"))]
        receipt["candidate_sources"].append(identity(Path(__file__).resolve()))
        environment = os.environ.copy()
        environment.pop("PYTHONPATH", None)
        environment.pop("PYTHONHOME", None)
        environment["PYTHONDONTWRITEBYTECODE"] = "1"
        unit_stdout = run.command("component_tests", [sys.executable, "-B", "-X", "utf8",
                                                       str(CANDIDATE / "test_candidates.py")], environment)
        receipt["component_results"] = json.loads(unit_stdout.decode("utf-8").strip().splitlines()[-1])
        if not receipt["component_results"]["successful"]:
            raise RuntimeError("UNIT_RECEIPT_FAILED")
        if args.repo_gates:
            environment["PATH"] = str(Path(sys.executable).parent) + os.pathsep + environment["PATH"]
            gate_output = run.command("repository_gate", ["powershell.exe", "-NoProfile", "-ExecutionPolicy",
                                                           "Bypass", "-File", str(ROOT / "code/scripts/check_repo.ps1")],
                                      environment)
            # Raw gate output is authoritative; count avoids inferring9 from exit0.
            gate_text = gate_output.decode("utf-8", "replace")
            receipt["repository_gate"] = {"exit_code": 0, "pass_lines": gate_text.count("[PASS]"),
                                          "fail_lines": gate_text.count("[FAIL]")}
            if receipt["repository_gate"]["fail_lines"]:
                raise RuntimeError("REPOSITORY_GATE_FAIL_LINES")
        else:
            receipt["repository_gate"] = {"status": "NOT_RUN"}
        receipt["capture_root"] = str(args.capture_root.resolve())
        receipt["capture_inputs"] = []
        missing = []
        for name, expected in PINNED_CAPTURE.items():
            path = args.capture_root / name
            if not path.is_file():
                missing.append(str(path.resolve()))
            else:
                actual = identity(path.resolve())
                actual["expected_raw_sha256"] = expected
                receipt["capture_inputs"].append(actual)
                if actual["sha256"] != expected:
                    raise RuntimeError("ORIGINAL_CAPTURE_RAW_SHA_MISMATCH:" + name)
        receipt["missing_original_inputs"] = missing
        receipt["still_required_from_M2"] = ["56 original counterexamples with original index/manifest",
                                             "Exact capture2 generated observer/TB/source/ROM identity manifest"]
        if args.component_only:
            receipt["status"], exit_code = "COMPONENT_SELFTEST_ONLY", 0
        elif missing:
            receipt["status"], exit_code = "BLOCKED_MISSING_ORIGINAL_CAPTURE", 2
        else:
            transport = run.command("transport_only", [sys.executable, "-B", "-X", "utf8",
                                                         str(CANDIDATE / "strict_capture.py"),
                                                         str((args.capture_root / "audio_observation.jsonl").resolve()),
                                                         str((args.capture_root / "midi_pcm.capture").resolve())], environment)
            receipt["real_transport_results"] = json.loads(transport.decode("utf-8"))
            receipt["status"], exit_code = "PARTIAL_TRANSPORT_ONLY_A1_INCOMPLETE", 3
        # Recheck all pinned inputs after commands; no silent source drift.
        for before in receipt["frozen_inputs"] + receipt["candidate_sources"] + receipt["capture_inputs"]:
            if identity(Path(before["path"]))["sha256"] != before["sha256"]:
                raise RuntimeError("INPUT_CHANGED_DURING_RUN:" + before["path"])
    except (RuntimeError, OSError, ValueError, subprocess.SubprocessError) as error:
        receipt.update(status="FAIL", error=str(error))
        exit_code = 1
    receipt.update(exit_code=exit_code, elapsed_seconds=round(time.monotonic() - run.start, 6), steps=run.steps)
    receipt["artifacts"] = [identity(path) for path in sorted(output.iterdir()) if path.is_file()]
    (output / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": receipt["status"], "exit_code": exit_code, "receipt": str(output / "receipt.json")},
                     ensure_ascii=False))
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
