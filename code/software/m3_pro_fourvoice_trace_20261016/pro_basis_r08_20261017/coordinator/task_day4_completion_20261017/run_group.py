"""One frozen completion batch; in-process, no external tools or devices."""
from __future__ import annotations

import argparse
import contextlib
from datetime import datetime, timezone
import hashlib
import importlib.machinery
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import time
import traceback
from types import ModuleType

_common_path = Path(__file__).with_name("common.py").resolve()
_common_raw = _common_path.read_bytes()
COMMON_SHA = "55cb7481fe9c0870247a7d8b2453dea859f0f2e81879795cc0e34ffe8c996dca"
if hashlib.sha256(_common_raw).hexdigest() != COMMON_SHA:
    raise RuntimeError("BOOTSTRAP_COMMON_SOURCE_CHANGED")
c = ModuleType("_d4_run_common")
c.__file__ = str(_common_path)
c.__package__ = ""
sys.modules[c.__name__] = c
exec(compile(_common_raw, str(_common_path), "exec", dont_inherit=True, optimize=0), c.__dict__)
ROOT, DOC = c.ROOT, c.DOC
OLD_AUDIT = Path(__file__).parent.parent / "run_group.py"
OLD_AUDIT_SHA = "c688d8f0815fbda8b7d756d6f6eb0fd194c79b0e65ee4a16bb6b17c486626c4f"


def utc():
    return datetime.now(timezone.utc).isoformat()


def raw_identity(path):
    digest = hashlib.sha256()
    size = 0
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
            size += len(block)
    return {"bytes": size, "sha256": digest.hexdigest()}


def save(path, value):
    with Path(path).open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    args = parser.parse_args()
    spec_path = args.spec.resolve()
    spec = c.read_json(spec_path)
    c.require(not sys.flags.optimize and sys.dont_write_bytecode and sys.flags.utf8_mode == 1,
              "ASSERTIONS_NO_BYTECODE_UTF8_REQUIRED")
    c.require(spec["schema"] == "M3_C9_D4_RUN_SPEC_V1" and spec["group"] == "TASK_DAY4_REMAINDER_SW", "RUN_SPEC")
    c.require(Path.cwd().resolve() == ROOT and spec["cwd"] == str(ROOT), "RUN_CWD")
    c.require(spec["python"] == raw_identity(sys.executable), "PYTHON_IDENTITY")
    c.require(spec["entry"] == raw_identity(__file__), "RUNNER_IDENTITY")
    actual_argv = [sys.executable, *sys.orig_argv[1:]]
    c.require(spec["argv"] == actual_argv == [sys.executable, "-B", "-X", "utf8", str(Path(__file__).resolve()), str(spec_path)], "ACTUAL_ARGV_MISMATCH")
    phase = spec["phase"]
    c.require(phase in ("initial", "repair"), "RUN_PHASE")
    limit = 120 if phase == "initial" else 60
    c.require(spec["limit_s"] == limit, "RUN_LIMIT")
    frozen_path = c.checked_descriptor(spec["frozen_manifest"])
    frozen_document = c.read_json(frozen_path, max_bytes=64 * 1024 * 1024)
    frozen = frozen_document["files"]
    external = frozen_document.get("external_files", {})
    entry_name = Path(__file__).resolve().relative_to(ROOT).as_posix()
    c.require(frozen[entry_name] == spec["entry"], "FROZEN_RUNNER")
    c.require(frozen[_common_path.relative_to(ROOT).as_posix()]["sha256"] == COMMON_SHA,
              "FROZEN_BOOTSTRAP_COMMON")
    audit_module = c.load_source(OLD_AUDIT, OLD_AUDIT_SHA, "_d4_frozen_audit")
    cases = spec["cases"]
    c.require(cases and len({(case["component"], case["id"]) for case in cases}) == len(cases), "UNIQUE_FROZEN_CASES")
    for case in cases:
        for key in ("selftest", "case_manifest"):
            c.require(raw_identity(ROOT / case[key]) == frozen[case[key]], "FROZEN_CASE_SOURCE:" + case[key])
        manifest = c.read_json(ROOT / case["case_manifest"])
        matches = [item for item in manifest["cases"] if item.get("id", item.get("name")) == case["id"]]
        c.require(matches == [case["definition"]], "FROZEN_CASE_DEFINITION:" + case["id"])
    ledger_path = DOC / "CONSUMPTION.json"
    ledger = c.read_json(ledger_path)
    c.require(ledger["group"] == spec["group"], "LEDGER_GROUP")
    if phase == "initial":
        c.require(ledger["initial_consumed"] == 0, "INITIAL_ALREADY_CONSUMED")
        ledger["initial_consumed"] = 1
    else:
        c.require(ledger["initial_consumed"] == 1 and ledger["repair_consumed"] < 3, "REPAIR_NOT_AVAILABLE")
        c.require(ledger["status"] in ("FAIL_PARTIAL", "TIMEOUT_PARTIAL") and spec.get("defect_basis"), "TARGETED_DEFECT_BASIS_REQUIRED")
        permitted = set(spec["repair_case_keys"])
        c.require({case["component"] + ":" + case["id"] for case in cases} == permitted, "REPAIR_SCOPE")
        c.require(permitted <= set(ledger["remaining_case_keys"]), "PASSED_CASE_REPLAY_FORBIDDEN")
        ledger["repair_consumed"] += 1
    out = c.no_alias(spec["output"])
    allowed_output = ROOT / "code/output/m3_c9_complete_d4_20261017"
    c.require(out.is_relative_to(allowed_output), "RUN_OUTPUT_SCOPE")
    out.mkdir(parents=True, exist_ok=False)
    save(out / "SPEC.json", spec)
    ledger.update(status="RUNNING", current_output=out.relative_to(ROOT).as_posix())
    done = threading.Event()
    lock = threading.Lock()
    results, violations, reads = [], [], {}
    started = utc()
    began = time.monotonic()
    deadline = began + limit
    active = {}
    first_failure = {}

    def receipt(code, status):
        return {"schema": "M3_C9_D4_RUN_RECEIPT_V1", "group": spec["group"], "phase": phase,
                "status": status, "exit_code": code, "pid": os.getpid(),
                "started_utc": started, "ended_utc": utc(), "elapsed_s": time.monotonic() - began,
                "limit_s": limit, "argv": spec["argv"], "cwd": str(ROOT),
                "bootstrap_common": {"path": _common_path.relative_to(ROOT).as_posix(), "sha256": COMMON_SHA},
                "cases_total": len(cases), "cases_completed": len(results),
                "assertions_matched": sum(item["assertion"] == "MATCHED" for item in results),
                "results": list(results), "first_failure_or_active": dict(first_failure or active),
                "audit_violations": list(violations), "read_inputs": dict(reads),
                "candidate_subprocesses": 0, "HDL_EDA_device_calls": 0,
                "old_consumption_restored": False, "real_verified": False,
                "board_release_allowed": False}

    def watchdog():
        if not done.wait(max(0, deadline - time.monotonic() - 0.2)):
            # A blocked receipt write must never prevent the deadline exit.
            # A separate best-effort writer uses a different filename. Its
            # completion wait is bounded; native exit124 remains authoritative.
            written = threading.Event()
            def timeout_snapshot():
                try:
                    save(out / "TIMEOUT_SNAPSHOT.json", receipt(124, "TIMEOUT_PARTIAL"))
                finally:
                    written.set()
            try:
                threading.Thread(target=timeout_snapshot, daemon=True,
                                 name="d4-timeout-witness").start()
                written.wait(0.1)
            finally:
                os._exit(124)

    (out / "temp").mkdir()
    tempfile.tempdir = str(out / "temp")
    stdout = (out / "stdout.raw").open("w", encoding="utf-8", buffering=1, newline="\n")
    stderr = (out / "stderr.raw").open("w", encoding="utf-8", buffering=1, newline="\n")
    # All ordinary file/stream setup happened before consumption. From the
    # persistent RUNNING transition onward every startup/candidate error is
    # handled by the same final receipt path.
    temporary_ledger = ledger_path.with_suffix(".tmp")
    save(temporary_ledger, ledger)
    os.replace(temporary_ledger, ledger_path)
    code, status = 0, "PASS_LIMITED_SOFTWARE"
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            threading.Thread(target=watchdog, daemon=True, name="d4-whole-batch-deadline").start()
            audit_module.install_audit(out, frozen, external, violations, reads)
            # Legacy selftests use importlib's default source loader. Execute
            # their exact frozen .py bytes without consulting any stale .pyc.
            # Audit rules remain unchanged; bytecode is never admitted.
            original_get_code = importlib.machinery.SourceFileLoader.get_code
            def frozen_source_code(loader, fullname):
                source = Path(loader.path).resolve()
                if source.is_relative_to(ROOT):
                    name = source.relative_to(ROOT).as_posix()
                    c.require(source.suffix == '.py' and name in frozen, 'UNFROZEN_SOURCE_IMPORT:' + name)
                    raw = source.read_bytes()
                    c.require({'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest()} == frozen[name],
                              'FROZEN_SOURCE_IMPORT_CHANGED:' + name)
                    return compile(raw, str(source), 'exec', dont_inherit=True, optimize=0)
                return original_get_code(loader, fullname)
            importlib.machinery.SourceFileLoader.get_code = frozen_source_code
            sys.path[0:0] = list(dict.fromkeys(str((ROOT / case['selftest']).parent) for case in cases))
            for number, case in enumerate(cases):
                active.update(component=case["component"], case=case["id"])
                print(json.dumps({"begin": active, "utc": utc()}), flush=True)
                case_out = out / "cases" / f"{number:03d}"
                case_out.parent.mkdir(parents=True, exist_ok=True)
                try:
                    module = c.load_source(ROOT / case["selftest"], frozen[case["selftest"]]["sha256"])
                    actual = module.run_case(case["id"], case_out)
                    c.require(isinstance(actual, dict), "CASE_EVIDENCE_DICT_REQUIRED")
                    c.require(not violations, "FORBIDDEN_OPERATION_ATTEMPT")
                    item = {"component": case["component"], "id": case["id"],
                            "definition": case["definition"], "assertion": "MATCHED", "result": actual}
                    save(case_out / "COORDINATOR_RESULT.json", item)
                except Exception as error:
                    traceback.print_exc()
                    code, status = 1, "FAIL_PARTIAL"
                    if not first_failure:
                        first_failure.update(active)
                    item = {"component": case["component"], "id": case["id"],
                            "definition": case["definition"], "assertion": "FAILED",
                            "error": type(error).__name__ + ":" + str(error)}
                    save(out / f"CASE_FAILURE_{number:03d}.json", item)
                results.append(item)
                print(json.dumps({"end": case["id"], "assertion": item["assertion"]}), flush=True)
                if violations:
                    raise PermissionError("AUDIT_VIOLATION_STOPS_BATCH")
            active.clear()
        except BaseException:
            traceback.print_exc()
            code, status = 1, "FAIL_PARTIAL"
        finally:
            try:
                stdout.flush()
                stderr.flush()
                for name, expected in list(reads.items()):
                    path = Path(name)
                    if not path.is_absolute():
                        path = ROOT / path
                    if raw_identity(path) != expected:
                        raise ValueError("INPUT_CHANGED:" + name)
                streams = {"stdout": raw_identity(out / "stdout.raw"), "stderr": raw_identity(out / "stderr.raw")}
            except BaseException as error:
                code, status = 1, "FAIL_PARTIAL"
                violations.append({"event": "finalization", "reason": type(error).__name__ + ":" + str(error)})
                streams = {}
            with lock:
                if time.monotonic() >= deadline:
                    code, status = 124, "TIMEOUT_PARTIAL"
                value = receipt(code, status)
                value['repository_import_policy'] = 'EXACT_FROZEN_SOURCE_BYTES_NO_PYC'
                value.update(streams)
                temporary_receipt = out / "RECEIPT.tmp"
                save(temporary_receipt, value)
                os.replace(temporary_receipt, out / "RECEIPT.json")
                if time.monotonic() >= deadline:
                    code, status = 124, "TIMEOUT_PARTIAL"
                    save(out / "DEADLINE_DURING_FINAL_RECEIPT.json", receipt(code, status))
                done.set()
    stdout.close()
    stderr.close()
    print(json.dumps({"status": status, "exit_code": code, "cases_completed": len(results), "cases_total": len(cases), "receipt": str(out / "RECEIPT.json")}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
