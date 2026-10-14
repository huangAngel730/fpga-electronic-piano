"""Bounded software-only probe for the frozen Windows Job/cmd boundary.

This does not invoke HDL tools.  It launches one direct cmd child and one
Python parent which itself launches cmd, both through the exact frozen runner
Job implementation used by the rejected N32-A compile diagnostic.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path
import socket
import sys


ROOT = Path(__file__).resolve().parents[3]
PLAN = ROOT / "code/output/m3_n32_a_plan_20261014_16/plan.json"
CAPSULE = ROOT / "code/output/m3_n32_a_plan_20261014_16/capsule"
HELPERS = CAPSULE / "code/software/t052_runner_acceptance_candidate_20261012"
RUNNER_SHA = "4709a969a4a85132706b94443900f36a831171f621c22580eb0382c95a655e3a"
JOB_SHA = "5450b8943b0616cc0f8ad7147c1c6a4b20eb4f04d8a7cc3fb515825941c0df1b"
PYTHON = Path(sys.executable).resolve()
CMD = Path(r"C:\WINDOWS\System32\cmd.exe")


def identity(path):
    raw = Path(path).read_bytes()
    return {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def require(condition, diagnostic):
    if not condition:
        raise ValueError(diagnostic)


def load_frozen_runner():
    require(identity(HELPERS / "runner.py")["sha256"] == RUNNER_SHA,
            "RUNNER_SHA")
    require(identity(HELPERS / "windows_job.py")["sha256"] == JOB_SHA,
            "WINDOWS_JOB_SHA")
    sys.path.insert(0, str(HELPERS))
    spec = importlib.util.spec_from_file_location(
        "n32_a_frozen_runner_for_cmd_probe", HELPERS / "runner.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n").encode("utf-8")


def run(output):
    output = Path(output).resolve()
    require(output.is_relative_to(ROOT / "code/output"), "OUTPUT_SCOPE")
    require(not output.exists(), "OUTPUT_EXISTS")
    require(socket.gethostname().upper() == "LAPTOP-KSS1MRR7", "MACHINE")
    plan_before = identity(PLAN)
    runner_before = identity(HELPERS / "runner.py")
    job_before = identity(HELPERS / "windows_job.py")
    python_before = identity(PYTHON)
    cmd_before = identity(CMD)
    runner = load_frozen_runner()
    output.mkdir(parents=True)
    budget = runner.Budget(60)
    started = datetime.now(timezone.utc).isoformat()
    direct = runner._run_process(
        output, "direct_cmd", [CMD, "/d", "/c", "exit", "0"],
        output, 20, budget)
    nested_code = (
        "import json,subprocess,sys;"
        f"p=subprocess.Popen([{str(CMD)!r},"
        "'/d','/c','exit','0'],stdin=subprocess.DEVNULL,"
        "stdout=subprocess.PIPE,stderr=subprocess.PIPE);"
        "o,e=p.communicate(timeout=20);"
        "print(json.dumps({'child_pid':p.pid,'child_exit':p.returncode,"
        "'stdout_bytes':len(o),'stderr_bytes':len(e)},sort_keys=True));"
        "raise SystemExit(p.returncode)"
    )
    nested = runner._run_process(
        output, "nested_cmd", [PYTHON, "-I", "-S", "-B", "-c", nested_code],
        output, 30, budget)
    receipt = {
        "schema": "T061_N32_A_CMD_JOB_PROBE_V1",
        "scope": "SOFTWARE_ONLY_NO_HDL_NO_EDA",
        "machine": socket.gethostname(),
        "started_utc": started,
        "ended_utc": datetime.now(timezone.utc).isoformat(),
        "automatic_retries": 0,
        "plan": plan_before,
        "runner": runner_before,
        "windows_job": job_before,
        "python": {"path": str(PYTHON), **python_before},
        "cmd": {"path": str(CMD), **cmd_before},
        "direct": direct,
        "nested": nested,
        "elapsed_seconds": budget.elapsed(),
    }
    receipt["status"] = (
        "PASS" if all(not item["timed_out"] and item["launch_error"] is None
                      and item["exit_code"] == 0 for item in (direct, nested))
        else "FAIL_PARTIAL")
    receipt["post_identity_match"] = {
        "plan": identity(PLAN) == plan_before,
        "runner": identity(HELPERS / "runner.py") == runner_before,
        "windows_job": identity(HELPERS / "windows_job.py") == job_before,
        "python": identity(PYTHON) == python_before,
        "cmd": identity(CMD) == cmd_before,
    }
    require(all(receipt["post_identity_match"].values()), "IDENTITY_DRIFT")
    (output / "receipt.json").write_bytes(encoded(receipt))
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output)
    print(json.dumps({key: result[key] for key in
                      ("status", "elapsed_seconds", "automatic_retries")},
                     sort_keys=True))
    raise SystemExit(0 if result["status"] == "PASS" else 1)
