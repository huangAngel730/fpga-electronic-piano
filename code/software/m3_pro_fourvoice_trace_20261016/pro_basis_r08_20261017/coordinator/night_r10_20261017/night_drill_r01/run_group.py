"""The coordinator's single frozen local group; never starts child tools."""
from __future__ import annotations

import contextlib
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time
import traceback
import types

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[6]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017/night_drill_r01"
OUT = ROOT / "code/output/m3_m2_night_drill_20261017"


def save(path: Path, value: dict) -> None:
    path.parent.mkdir(exist_ok=True, parents=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def freeze() -> dict:
    files = [p for p in sorted(HERE.rglob("*")) if p.is_file() and p.suffix in (".py", ".json")]
    files.extend(DOC / "intake" / name for name in ("CASES.json", "BINDING.json"))
    return {p.relative_to(ROOT).as_posix(): {"bytes": p.stat().st_size,
            "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in files}


def load(path: Path, expected: str, name: str):
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected:
        raise RuntimeError("FROZEN_SOURCE_CHANGED:" + str(path))
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(data, str(path), "exec"), module.__dict__)
    return module


def install_pure_file_guard() -> None:
    allowed = (OUT.resolve(), DOC.resolve())
    def writable(path):
        if isinstance(path, int):
            return
        value = Path(path).resolve()
        if not any(value.is_relative_to(base) for base in allowed):
            raise PermissionError("DRILL_WRITE_OUTSIDE_OWNED_ROOT:" + str(value))
    def audit(event, args):
        if (event == "subprocess.Popen" or event.startswith("socket.")
                or event in ("os.system", "os.posix_spawn", "os.startfile", "ctypes.dlopen", "ctypes.dlsym")
                or event.startswith(("os.exec", "os.spawn"))):
            raise PermissionError("DRILL_EXTERNAL_ACTION_FORBIDDEN:" + event)
        if event == "open":
            path, mode, flags = args
            if (isinstance(mode, str) and any(c in mode for c in "wax+")) or (isinstance(flags, int) and flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
                writable(path)
        if event in ("os.remove", "os.rmdir", "os.mkdir", "os.chmod", "os.utime", "os.truncate"):
            writable(args[0])
        if event in ("os.rename", "os.link", "os.symlink"):
            writable(args[0])
            writable(args[1])
        if event == "os.chdir":
            raise PermissionError("DRILL_CWD_CHANGE_FORBIDDEN")
    sys.addaudithook(audit)


def main() -> int:
    output = OUT / "runs/local_group_01"
    output.mkdir(exist_ok=False, parents=True)
    consumption = json.loads((DOC / "CONSUMPTION.json").read_text(encoding="utf-8"))
    group = consumption["initial_local_group"]
    if group["status"] != "NOT_CONSUMED":
        raise RuntimeError("GROUP_ALREADY_CONSUMED")
    snapshot = freeze()
    cases = json.loads((DOC / "intake/CASES.json").read_text(encoding="utf-8"))
    cases = cases["cases"] if isinstance(cases, dict) else cases
    spec = {"schema": "M3_DRILL_FROZEN_GROUP_R01", "source": snapshot,
            "cases": cases, "argv": [sys.executable, *sys.orig_argv[1:]],
            "cwd": os.getcwd(), "dont_write_bytecode": sys.dont_write_bytecode,
            "seconds_limit": 120, "no_subprocess": True,
            "runtime_guard": "CPython audit hook rejects subprocess/socket/ctypes and writes outside owned output/docs",
            "origin": "LOCAL_SYNTHETIC", "utc": datetime.now(timezone.utc).isoformat()}
    save(output / "SPEC.json", spec)
    group.update(status="CONSUMED_RUNNING", output=str(output.relative_to(ROOT)), spec_sha256=hashlib.sha256((output / "SPEC.json").read_bytes()).hexdigest())
    save(DOC / "CONSUMPTION.json", consumption)
    started = time.monotonic()

    def timeout():
        try:
            save(output / "TIMEOUT.json", {"exit_code": 124, "elapsed_seconds": time.monotonic() - started,
                                           "mechanism": "owned runner self-exit watchdog"})
        finally:
            os._exit(124)

    watchdog = threading.Timer(119, timeout)
    watchdog.daemon = True
    watchdog.start()
    install_pure_file_guard()
    results = []
    code = 1
    try:
        with (output / "stdout.raw").open("x", encoding="utf-8", newline="\n") as stdout, (output / "stderr.raw").open("x", encoding="utf-8", newline="\n") as stderr:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                try:
                    path = HERE / "intake/selftest.py"
                    module = load(path, snapshot[path.relative_to(ROOT).as_posix()]["sha256"], "_m3_drill_frozen_selftest")
                    for case in cases:
                        before = time.monotonic()
                        result = module.run_case(case["id"], output / case["id"])
                        results.append({"id": case["id"], "expected": case.get("expected"),
                                        "result": result, "seconds": time.monotonic() - before})
                        print(json.dumps(results[-1], ensure_ascii=False), flush=True)
                    # Actual repository sample reception is distinct from all
                    # synthetic adapter cases. Git containment was independently
                    # observed before this local, durable operation.
                    path = HERE / "intake/engine.py"
                    engine = load(path, snapshot[path.relative_to(ROOT).as_posix()]["sha256"], "_m3_drill_actual_intake")
                    handoff_path = ROOT / "code/docs/test/m2_night_drill_r01_20261017/HANDOFF.json"
                    handoff = json.loads(handoff_path.read_text(encoding="utf-8"))
                    options = {"task_id": handoff["task_id"], "plan_version": handoff["plan_version"],
                               "origin": "LOCAL_REPOSITORY_SNAPSHOT"}
                    store = engine.Store(OUT / "state/actual_intake")
                    first = store.receive(handoff, ROOT, **options)
                    first_snapshot = store.snapshot()
                    save(output / "ACTUAL_FIRST_RECEIVED.json", first_snapshot)
                    advanced = store.advance(first["key"])
                    reloaded = engine.Store(OUT / "state/actual_intake")
                    duplicate = reloaded.receive(handoff, ROOT, **options)
                    duplicate_advance = reloaded.advance(first["key"])
                    final = reloaded.snapshot()
                    if (first["status"] != "RECEIVED" or first_snapshot["advance_count"] != 0
                            or duplicate["status"] != "DUPLICATE"
                            or duplicate_advance["status"] != "ALREADY_ADVANCED"
                            or not (len(final["receipts"]) == final["advance_count"] == 1)):
                        raise AssertionError("ACTUAL_SAMPLE_ONCE")
                    save(output / "ACTUAL_SAMPLE_RECEIVE.json", {"origin": "ACTUAL_GIT_REPOSITORY_INPUT",
                         "first": first, "advanced": advanced, "duplicate": duplicate,
                         "duplicate_advance": duplicate_advance, "final_state": final,
                         "M2_final_acceptance": "PENDING", "M2_machine_session": "MISSING",
                         "sample_remote_ancestry_proof": "INPUT_VERIFICATION.json; successful startup_fetch",
                         "real_two_machine_class_complete": False})
                    if snapshot != freeze():
                        raise RuntimeError("SOURCE_CHANGED_DURING_GROUP")
                    code = 0
                except BaseException:
                    traceback.print_exc()
    finally:
        # Keep the watchdog armed through evidence/consumption sealing.
        pass
    receipt = {"schema": "M3_DRILL_LOCAL_GROUP_RESULT_R01", "origin": "LOCAL_SYNTHETIC",
               "exit_code": code, "elapsed_seconds": time.monotonic() - started,
               "results": results, "planned": len(cases), "completed": len(results),
               "source_after": freeze(), "limit_seconds": 120,
               "actual_level": "L1_PURE_FILE_SOFTWARE_ONLY"}
    if time.monotonic() - started >= 119:
        receipt["exit_code"] = code = 124
    save(output / "RESULT.json", receipt)
    group.update(status="CONSUMED_PASS" if code == 0 else "CONSUMED_FAIL", result=receipt)
    save(DOC / "CONSUMPTION.json", consumption)
    watchdog.cancel()
    print(json.dumps({"exit_code": code, "completed": len(results), "planned": len(cases),
                      "seconds": receipt["elapsed_seconds"]}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
