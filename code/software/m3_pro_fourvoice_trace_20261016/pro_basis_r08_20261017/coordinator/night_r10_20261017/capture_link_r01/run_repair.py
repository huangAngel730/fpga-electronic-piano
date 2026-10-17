"""The one conditional <=60s LINK seam repair; signed groups are not replayed."""
from datetime import datetime, timezone
import contextlib
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
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017"
INTAKE = DOC / "intake_20261018"
OUT = ROOT / "code/output/m3_c9_chain_night_r10_20261017/CAPTURE_LINK_REPAIR_R01"


def ref(path):
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
            "sha256": hashlib.sha256(raw).hexdigest()}


def save(path, value):
    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(raw)
    temporary.replace(path)


def load(path, descriptor, name):
    raw = path.read_bytes()
    actual = {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw),
              "sha256": hashlib.sha256(raw).hexdigest()}
    if actual != descriptor:
        raise ValueError("REPAIR_SOURCE_CHANGED")
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(raw, str(path), "exec", dont_inherit=True, optimize=0), module.__dict__)
    return module


def main():
    if not sys.dont_write_bytecode or sys.flags.optimize:
        raise ValueError("REPAIR_REQUIRES_B_AND_ASSERTIONS")
    ledger_path = DOC / "CONSUMPTION.json"
    ledger = json.loads(ledger_path.read_bytes())
    if ledger["first_defect_increment"]["status"] != "NOT_CONSUMED":
        raise ValueError("LINK_REPAIR_ALREADY_CONSUMED")
    if (datetime.fromisoformat(ledger["deadline"]) - datetime.now(timezone.utc)).total_seconds() < 60:
        raise ValueError("ORIGINAL_TIMEBOX_TOO_SHORT")
    manifest = json.loads((INTAKE / "FROZEN_REPAIR_INPUTS.json").read_bytes())
    runtime = Path(sys.executable).read_bytes()
    if (Path(manifest["runtime"]["path"]).resolve() != Path(sys.executable).resolve()
            or len(runtime) != manifest["runtime"]["bytes"]
            or hashlib.sha256(runtime).hexdigest() != manifest["runtime"]["sha256"]):
        raise ValueError("REPAIR_PYTHON_RUNTIME_CHANGED")
    expected = {item["path"]: item for item in manifest["files"]}
    for name, descriptor in expected.items():
        if ref(ROOT / name) != descriptor:
            raise ValueError("REPAIR_INPUT_CHANGED:" + name)
    cases = json.loads((INTAKE / "REPAIR_CASES.json").read_bytes())["cases"]
    if (datetime.fromisoformat(ledger["deadline"]) - datetime.now(timezone.utc)).total_seconds() < 60:
        raise ValueError("ORIGINAL_TIMEBOX_TOO_SHORT_AFTER_FREEZE_CHECK")
    OUT.mkdir(parents=True, exist_ok=False)
    spec = {"schema": "N10_M3_CAPTURE_LINK_REPAIR_SPEC_V1", "utc": datetime.now(timezone.utc).isoformat(),
            "argv": [sys.executable, *sys.orig_argv[1:]], "cwd": os.getcwd(), "seconds_limit": 60,
            "hard_watchdog_seconds": 59, "manifest": ref(INTAKE / "FROZEN_REPAIR_INPUTS.json"),
            "first_static_defect": ref(INTAKE / "FIRST_STATIC_DEFECT.json"), "cases": cases,
            "original_START": ledger["original_START"], "deadline": ledger["deadline"],
            "goal_createdAt": 1792257077, "old_groups_replayed": 0,
            "boundary": "Dispatch spies and rejection paths only; no capture/FRAME/math replay or tool route"}
    save(OUT / "SPEC.json", spec)
    ledger["first_defect_increment"].update(status="CONSUMED_RUNNING", output=OUT.relative_to(ROOT).as_posix(),
                                            spec=ref(OUT / "SPEC.json"), first_static_defect=spec["first_static_defect"])
    save(ledger_path, ledger)
    save(OUT / "CONSUMPTION_AT_START.json", ledger)
    began = time.monotonic()
    def timeout_marker():
        # This separate soft marker may itself block on filesystem I/O. The
        # independent hard watchdog still exits at59s without waiting for it.
        try:
            save(OUT / "TIMEOUT.json", {"schema": "N10_LINK_REPAIR_TIMEOUT_V1",
                 "exit_code": 124, "utc": datetime.now(timezone.utc).isoformat(),
                 "status": "TIMEOUT_PENDING_HARD_EXIT", "ledger": "CONSUMED_RUNNING_DO_NOT_RETRY"})
        except BaseException:
            pass
    soft_watchdog = threading.Timer(58, timeout_marker)
    soft_watchdog.daemon = True
    watchdog = threading.Timer(59, lambda: os._exit(124))
    watchdog.daemon = True
    soft_watchdog.start()
    watchdog.start()
    code, results = 1, []
    failure = None
    try:
        common_path = HERE.parent / "common.py"
        common = load(common_path, expected[common_path.relative_to(ROOT).as_posix()], "_repair_runtime_common")
        common.install_guard()
        with (OUT / "stdout.raw").open("x", encoding="utf-8", newline="\n") as stdout, \
                (OUT / "stderr.raw").open("x", encoding="utf-8", newline="\n") as stderr:
            with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                modules = {}
                for name in ("entry", "application_adapter", "selftest"):
                    path = HERE / (name + ".py")
                    modules[name] = load(path, expected[path.relative_to(ROOT).as_posix()], "_repair_" + name)
                if modules["selftest"].CASES != cases:
                    raise ValueError("REPAIR_CASES_CHANGED")
                results = modules["selftest"].run(modules["entry"], modules["application_adapter"], OUT / "cases")
                for name, descriptor in expected.items():
                    if ref(ROOT / name) != descriptor:
                        raise ValueError("REPAIR_INPUT_CHANGED_DURING_RUN:" + name)
                if len(results) != len(cases) or any(item["status"] != "MATCHED" for item in results):
                    raise ValueError("REPAIR_NOT_ALL_MATCHED")
                print(json.dumps(results, ensure_ascii=False), flush=True)
                code = 0
    except BaseException as error:
        failure = {"reason": repr(error), "traceback": traceback.format_exc()}
        save(OUT / "FIRST_RUNTIME_FAILURE.json", failure)
        with (OUT / "stderr.raw").open("a", encoding="utf-8", newline="\n") as stderr:
            stderr.write(failure["traceback"])
    for name in ("stdout.raw", "stderr.raw"):
        if not (OUT / name).exists():
            (OUT / name).write_bytes(b"")
    receipt = {"schema": "N10_M3_CAPTURE_LINK_REPAIR_RESULT_V1", "utc": datetime.now(timezone.utc).isoformat(),
               "exit_code": code, "seconds": time.monotonic() - began, "matched": len(results),
               "planned": len(cases), "results": results, "spec": ref(OUT / "SPEC.json"),
               "stdout": ref(OUT / "stdout.raw"), "stderr": ref(OUT / "stderr.raw"),
               "old_signed_groups_replayed": 0, "full_capture_processed": False, "HDL_EDA_devices": 0,
               "first_runtime_failure": failure,
               "real_verified": False, "math_verified": False, "board_release_allowed": False}
    if receipt["seconds"] >= 59:
        receipt["exit_code"] = code = 124
    save(OUT / "RESULT.json", receipt)
    ledger["first_defect_increment"].update(status="CONSUMED_PASS" if code == 0 else "CONSUMED_FAIL",
                                            result=ref(OUT / "RESULT.json"), seconds=receipt["seconds"])
    save(ledger_path, ledger)
    soft_watchdog.cancel()
    watchdog.cancel()
    print(json.dumps({key: receipt[key] for key in ("exit_code", "seconds", "matched", "planned")}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
