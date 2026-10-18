"""Sole bounded coordinator entry for the one owned-worker recovery group."""
from __future__ import annotations

import contextlib
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import traceback
import types

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[6]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017/night_drill_r01"
OUT = ROOT / "code/output/m3_m2_night_drill_20261017"


def save(path, value):
    raw = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(raw, encoding="utf-8")
    temporary.replace(path)


def descriptor(path):
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def load(path, name, expected):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != expected:
        raise RuntimeError("RECOVERY_SOURCE_CHANGED")
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(raw, str(path), "exec"), module.__dict__)
    return module


def main():
    output = OUT / "runs/worker_group_01"
    output.mkdir(parents=True, exist_ok=False)
    ledger = json.loads((DOC / "CONSUMPTION.json").read_text(encoding="utf-8"))
    if ledger["owned_worker_group"]["status"] != "NOT_CONSUMED":
        raise RuntimeError("WORKER_GROUP_ALREADY_CONSUMED")
    ready = json.loads((DOC / "M3_READY_RECEIPT.json").read_text(encoding="utf-8"))
    paths = [HERE / "recovery/run_recovery.py", HERE / "recovery/owned_worker.py", Path(__file__).resolve()]
    job_path = ROOT / "code/software/t052_runner_acceptance_candidate_20261012/windows_job.py"
    bindings = [descriptor(p) for p in paths] + [descriptor(job_path)]
    if bindings[-1]["sha256"] != "5450b8943b0616cc0f8ad7147c1c6a4b20eb4f04d8a7cc3fb515825941c0df1b":
        raise RuntimeError("OWNED_JOB_HELPER_CHANGED")
    spec = {"source": bindings, "argv": [sys.executable, *sys.orig_argv[1:]],
            "cwd": os.getcwd(), "seconds_limit": 60, "watchdog_seconds": 59,
            "child_policy": "Exactly two direct frozen owned_worker.py executions; suspended into one owned Job before resume",
            "real_network": False, "origin": "LOCAL_SYNTHETIC"}
    save(output / "SPEC.json", spec)
    ledger["owned_worker_group"].update(status="CONSUMED_RUNNING", output=str(output.relative_to(ROOT)))
    save(DOC / "CONSUMPTION.json", ledger)
    context = {key: ready[key] for key in ("original_START", "deadline", "goal")}
    context["consumption"] = ledger
    context["handoff"] = {"handoff_id": ready["sample_handoff_id"], "result_commit": ready["sample_result_commit"]}
    save(output / "CONTEXT.json", context)
    job_module = load(job_path, "_drill_worker_job", bindings[-1]["sha256"])
    job = job_module.WindowsJob()
    original_popen = subprocess.Popen
    owned = []
    actual_launches = []
    began = time.monotonic()

    def guarded_popen(argv, *args, **kwargs):
        if (len(owned) >= 2 or args or not isinstance(argv, list)
                or Path(argv[0]).resolve() != Path(sys.executable).resolve()
                or len(argv) < 7 or Path(argv[6]).resolve() != paths[1].resolve()
                or argv[1:6] != ["-I", "-S", "-B", "-X", "utf8"]
                or kwargs.get("shell") is not False):
            raise PermissionError("ONLY_FROZEN_OWNED_WORKER_ALLOWED")
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | 0x00000004
        proc = original_popen(argv, **kwargs)
        owned.append(proc)
        job.attach_and_resume(proc)
        actual_launches.append({"argv": argv, "pid": proc.pid, "creationflags": kwargs["creationflags"],
                                "cwd": str(kwargs["cwd"]), "owned_job": True})
        save(output / "ACTUAL_LAUNCHES.json", actual_launches)
        return proc

    def timeout():
        try:
            job.terminate()
        finally:
            os._exit(124)

    watchdog = threading.Timer(59, timeout)
    watchdog.daemon = True
    watchdog.start()
    subprocess.Popen = guarded_popen
    result = None
    code = 1
    try:
        with (output / "stdout.raw").open("x", encoding="utf-8", newline="\n") as stdout, (output / "stderr.raw").open("x", encoding="utf-8", newline="\n") as stderr:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                try:
                    module = load(paths[0], "_drill_frozen_recovery", bindings[0]["sha256"])
                    result = module.run(output / "worker_results", context)
                    if [descriptor(p) for p in paths] + [descriptor(job_path)] != bindings:
                        raise RuntimeError("RECOVERY_SOURCE_CHANGED_AFTER_RUN")
                    code = 0
                except BaseException:
                    traceback.print_exc()
    finally:
        subprocess.Popen = original_popen
        job.close()
    receipt = {"schema": "M3_DRILL_WORKER_GROUP_RECEIPT_R01", "origin": "LOCAL_SYNTHETIC",
               "exit_code": code, "elapsed_seconds": time.monotonic() - began,
               "sources": bindings, "actual_launches": actual_launches,
               "owned_processes_closed": all(p.poll() is not None for p in owned), "result": result,
               "remote_recheck_required": True, "App_restart_verified": False, "machine_restart_verified": False}
    if receipt["elapsed_seconds"] >= 59 or not receipt["owned_processes_closed"]:
        receipt["exit_code"] = code = 124
    save(output / "RESULT.json", receipt)
    ledger["owned_worker_group"].update(status="CONSUMED_PASS" if code == 0 else "CONSUMED_FAIL", result=receipt)
    save(DOC / "CONSUMPTION.json", ledger)
    watchdog.cancel()
    print(json.dumps({"exit_code": code, "seconds": receipt["elapsed_seconds"], "owned_processes": len(owned)}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
