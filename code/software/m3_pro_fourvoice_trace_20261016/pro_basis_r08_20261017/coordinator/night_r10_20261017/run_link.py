"""One frozen N10-M3-LINK group, with no child process or tool route."""
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
ROOT = HERE.parents[5]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017"
OUT = ROOT / "code/output/m3_c9_chain_night_r10_20261017"


def save(path, value):
    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_bytes(raw)
    temporary.replace(path)


def ref(path):
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix(), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def frozen_sources():
    paths = [p for p in HERE.rglob("*.py") if "night_drill_r01" not in p.parts]
    return {p.relative_to(ROOT).as_posix(): ref(p) for p in sorted(paths)}


def load(path, digest, name):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise RuntimeError("N10_FROZEN_SOURCE_CHANGED")
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(raw, str(path), "exec", dont_inherit=True, optimize=0), module.__dict__)
    return module


def main():
    if sys.flags.optimize != 0 or not sys.dont_write_bytecode:
        raise RuntimeError("N10_REQUIRES_ASSERTIONS_ON_AND_NO_BYTECODE_WRITES")
    output = OUT / "LINK_R01"
    output.mkdir(parents=True, exist_ok=False)
    ledger = json.loads((DOC / "CONSUMPTION.json").read_text(encoding="utf-8"))
    if ledger["initial"]["status"] != "NOT_CONSUMED":
        raise RuntimeError("N10_LINK_ALREADY_CONSUMED")
    deadline = datetime.fromisoformat(ledger["deadline"])
    if deadline.tzinfo is None or (deadline - datetime.now(timezone.utc)).total_seconds() < 120:
        raise RuntimeError("N10_INSUFFICIENT_ORIGINAL_TIMEBOX")
    snapshot = frozen_sources()
    cases = []
    for role in ("admission", "serial"):
        data = json.loads((DOC / role / "CASES.json").read_text(encoding="utf-8"))
        for case in data["cases"]:
            cases.append({**case, "role": role})
    if len({case["id"] for case in cases}) != len(cases):
        raise ValueError("CASE_ID_COLLISION")
    inputs = json.loads((DOC / "FROZEN_INPUTS.json").read_text(encoding="utf-8"))
    for item in inputs["files"]:
        path = Path(item["path"])
        path = path if path.is_absolute() else ROOT / path
        raw = path.read_bytes()
        if len(raw) != item["bytes"] or hashlib.sha256(raw).hexdigest() != item["sha256"]:
            raise RuntimeError("N10_FROZEN_INPUT_CHANGED:" + str(path))
    spec = {"schema": "N10_M3_LINK_SPEC_V1", "utc": datetime.now(timezone.utc).isoformat(),
            "argv": [sys.executable, *sys.orig_argv[1:]], "cwd": os.getcwd(),
            "source": snapshot, "input_manifest": ref(DOC / "FROZEN_INPUTS.json"),
            "cases": cases, "new_integration_operation": "PREPARE_APPLICATION_ONLY+INTEGRATION_HANDOFF, no raw/FRAME/HDL execution",
            "seconds_limit": 120, "guard": "CPython audit rejects subprocess/socket/ctypes and out-of-scope writes",
            "original_START": ledger["original_START"], "deadline": ledger["deadline"], "goal": ledger["goal"]}
    save(output / "SPEC.json", spec)
    ledger["initial"].update(status="CONSUMED_RUNNING", output=output.relative_to(ROOT).as_posix(), spec=ref(output / "SPEC.json"))
    save(DOC / "CONSUMPTION.json", ledger)
    save(output / "CONSUMPTION_AT_START.json", ledger)
    start = time.monotonic()

    def timeout():
        os._exit(124)  # No blocking evidence write can prevent owned-runner exit.

    watchdog = threading.Timer(119, timeout)
    watchdog.daemon = True
    watchdog.start()
    common_path = HERE / "common.py"
    common = load(common_path, snapshot[common_path.relative_to(ROOT).as_posix()]["sha256"], "_n10_runtime_common")
    common.install_guard()
    results = []
    preparation = None
    code = 1
    with (output / "stdout.raw").open("x", encoding="utf-8", newline="\n") as stdout, (output / "stderr.raw").open("x", encoding="utf-8", newline="\n") as stderr:
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            try:
                for case in cases:
                    path = HERE / case["role"] / "selftest.py"
                    module = load(path, snapshot[path.relative_to(ROOT).as_posix()]["sha256"], "_n10_" + case["role"] + "_" + case["id"])
                    began = time.monotonic()
                    actual = module.run_case(case["id"], output / case["id"])
                    if not (isinstance(actual, dict) and actual.get("case_id") == case["id"]
                            and actual.get("expected") == case["expected"]
                            and (actual.get("assertion") == "MATCHED"
                                 or (actual.get("status") == "CASE_EXPECTATION_MATCHED" and actual.get("actual") == case["expected"]))):
                        raise AssertionError("N10_CASE_NOT_EXPLICITLY_MATCHED:" + case["id"])
                    results.append({"case": case, "result": actual, "seconds": time.monotonic() - began})
                    print(json.dumps(results[-1], ensure_ascii=False), flush=True)
                # The actual preparation reads source/inputs, not a synthetic
                # trace. Runtime consumption is an immutable snapshot, so later
                # sealing the live ledger cannot change the handoff input.
                request = common.read(DOC / "PIPELINE_REQUEST_TEMPLATE.json")
                request["context"]["receipts"].setdefault("consumption", []).append(ref(output / "CONSUMPTION_AT_START.json"))
                save(output / "EFFECTIVE_PIPELINE_REQUEST.json", request)
                path = HERE / "chain.py"
                chain = load(path, snapshot[path.relative_to(ROOT).as_posix()]["sha256"], "_n10_actual_prepare_chain")
                preparation = chain.process(request, output / "source_preparation")
                handoff = common.read(output / "source_preparation/handoff/INTEGRATION_HANDOFF.json")
                if (handoff["capture_id"] != request["capture_id"] or handoff["execution_allowed"] is not False
                        or handoff["real_verified"] is not False or handoff["math_verified"] is not False
                        or handoff["unique_FRAME_PLAN_ref"]["ref"] is not None
                        or handoff["math_input_bundle_ref"]["ref"] is not None):
                    raise AssertionError("N10_INTEGRATION_FALSE_IDENTITY_OR_AUTHORITY")
                if frozen_sources() != snapshot:
                    raise RuntimeError("N10_SOURCE_CHANGED_AFTER_GROUP")
                for item in inputs["files"]:
                    path = Path(item["path"])
                    path = path if path.is_absolute() else ROOT / path
                    raw = path.read_bytes()
                    if len(raw) != item["bytes"] or hashlib.sha256(raw).hexdigest() != item["sha256"]:
                        raise RuntimeError("N10_INPUT_CHANGED_AFTER_GROUP")
                code = 0
            except BaseException:
                traceback.print_exc()
    receipt = {"schema": "N10_M3_LINK_RESULT_V1", "exit_code": code, "seconds": time.monotonic() - start,
               "completed": len(results), "planned": len(cases), "results": results,
               "actual_preparation": preparation, "new_HDL_EDA_devices": 0,
               "old_signed_groups_replayed": 0, "execution_allowed": False, "real_verified": False,
               "board_release_allowed": False}
    if time.monotonic() - start >= 119:
        receipt["exit_code"] = code = 124
    save(output / "RESULT.json", receipt)
    ledger["initial"].update(status="CONSUMED_PASS" if code == 0 else "CONSUMED_FAIL", result=ref(output / "RESULT.json"))
    save(DOC / "CONSUMPTION.json", ledger)
    watchdog.cancel()
    print(json.dumps({"exit_code": code, "matched": len(results), "planned": len(cases), "seconds": receipt["seconds"],
                      "source_preparation": None if preparation is None else preparation["status"]}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
