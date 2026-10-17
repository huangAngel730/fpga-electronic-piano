"""One admitted R08 software group, in this process only; no tool launcher.

The frozen SPEC includes cases, all repository input identities and the exact
entry point. An exclusive run directory and persistent ledger prevent replay.
This is bounded local test infrastructure, not real execution admission.
"""
import argparse
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import threading
import time
import traceback
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[5]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator"


def utc():
    return datetime.now(timezone.utc).isoformat()


def identity(path):
    h = hashlib.sha256()
    size = 0
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
            size += len(chunk)
    return {"bytes": size, "sha256": h.hexdigest()}


def save(path, value):
    with path.open("w", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def atomic_save(path, value):
    temporary = path.with_suffix(".tmp")
    save(temporary, value)
    os.replace(temporary, path)


def contained(path, base):
    return path == base or base in path.parents


def install_audit(out, frozen, external, violations, reads):
    """Deny process/device/network APIs and candidate writes outside this run.

    This Python audit hook is defense in depth for reviewed local candidates;
    it is not a security boundary for hostile native code or an EDA executor.
    """
    local = threading.local()
    trusted_runtime = Path(sys.prefix).resolve()
    denied = ("subprocess.", "socket.", "ctypes.dlopen", "os.system", "os.startfile", "os.exec", "os.spawn", "os.fork", "_winapi.CreateProcess")

    def checked_path(value, writing=False):
        if isinstance(value, int) or value is None:
            return
        raw_path = os.fsdecode(value)
        if raw_path.startswith(("\\\\.\\", "\\\\?\\", "\\??\\")) or any(re.fullmatch(r"(?i)(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\..*)?", part) for part in Path(raw_path).parts):
            raise PermissionError("R08_DEVICE_PATH_FORBIDDEN:" + raw_path)
        path = Path(raw_path).resolve()
        if writing:
            if not contained(path, out):
                raise PermissionError("R08_WRITE_OUTSIDE_RUN:" + str(path))
            return
        if path.exists() and not path.is_file():
            raise PermissionError("R08_NON_REGULAR_INPUT:" + str(path))
        if contained(path, out):
            return
        if not contained(path, ROOT):
            if str(path) in external:
                actual = identity(path)
                if actual != external[str(path)]:
                    raise PermissionError("R08_EXTERNAL_INPUT_CHANGED:" + str(path))
                reads[str(path)] = actual
                return
            if contained(path, trusted_runtime):
                return
            raise PermissionError("R08_EXTERNAL_INPUT_NOT_FROZEN:" + str(path))
        rel = path.relative_to(ROOT).as_posix()
        if path.is_file():
            if rel not in frozen:
                raise PermissionError("R08_UNFROZEN_REPOSITORY_INPUT:" + rel)
            actual = identity(path)
            if actual != frozen[rel]:
                raise PermissionError("R08_INPUT_CHANGED:" + rel)
            reads[rel] = actual

    def hook(event, args):
        if getattr(local, "active", False):
            return
        local.active = True
        try:
            if event.startswith(denied):
                raise PermissionError("R08_FORBIDDEN_API:" + event)
            if event == "open":
                mode = args[1] or ""
                flags = args[2] or 0
                writing = any(c in mode for c in "wax+") or bool(flags & (os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC))
                checked_path(args[0], writing)
            elif event in ("os.mkdir", "os.remove", "os.rmdir", "os.chmod", "os.utime"):
                checked_path(args[0], True)
            elif event in ("os.rename", "os.link", "os.symlink"):
                checked_path(args[0], True)
                checked_path(args[1], True)
            elif event == "os.chdir":
                path = Path(args[0]).resolve()
                if not contained(path, ROOT):
                    raise PermissionError("R08_CHDIR_OUTSIDE_REPOSITORY")
        except PermissionError as error:
            violations.append({"event": event, "reason": str(error)})
            raise
        finally:
            local.active = False

    sys.addaudithook(hook)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("spec", type=Path)
    args = parser.parse_args()
    spec_path = args.spec.resolve()
    spec = json.loads(spec_path.read_text(encoding="utf-8"))
    if sys.flags.optimize != 0 or not sys.dont_write_bytecode or sys.flags.utf8_mode != 1:
        raise RuntimeError("R08_REQUIRES_ASSERTIONS_BYTECODE_DISABLED_UTF8")
    assert spec["schema"] == "M3_R08_RUN_SPEC_V1"
    group = spec["group"]
    assert group in "RSCTH" and len(group) == 1
    phase = spec["phase"]
    assert phase in ("initial", "repair")
    limit = 90 if phase == "initial" else 60
    assert spec["limit_s"] == limit
    assert Path.cwd().resolve() == ROOT
    assert spec["cwd"] == str(ROOT)
    assert spec["python"] == identity(Path(sys.executable))
    assert spec["entry"] == identity(Path(__file__))
    assert spec["argv"] == [sys.executable, "-B", "-X", "utf8", str(Path(__file__).resolve()), str(spec_path)]
    assert [sys.executable, *sys.orig_argv[1:]] == spec["argv"], "ACTUAL_ARGV_MISMATCH"
    frozen_path = ROOT / spec["frozen_manifest"]["path"]
    assert identity(frozen_path) == {k: spec["frozen_manifest"][k] for k in ("bytes", "sha256")}
    frozen_document = json.loads(frozen_path.read_text(encoding="utf-8"))
    frozen = frozen_document["files"]
    external = frozen_document.get("external_files", {})
    assert spec["entry"] == frozen[Path(__file__).resolve().relative_to(ROOT).as_posix()]
    cases = spec["cases"]
    assert cases and len({(c["component"], c["id"]) for c in cases}) == len(cases)
    for case in cases:
        assert re.fullmatch(r"[A-Za-z0-9_.-]+", case["id"])
        assert re.fullmatch(r"[A-Za-z0-9_]+", case["component"])
        assert identity(ROOT / case["selftest"]) == frozen[case["selftest"]]
        case_manifest_path = ROOT / case["case_manifest"]
        assert identity(case_manifest_path) == frozen[case["case_manifest"]]
        case_manifest = json.loads(case_manifest_path.read_text(encoding="utf-8"))
        assert case_manifest["schema"] == "M3_R08_CASES_V1" and case_manifest["group"] == group
        matches = [item for item in case_manifest["cases"] if item["id"] == case["id"]]
        assert len(matches) == 1
        assert all(matches[0][key] == case[key] for key in ("id", "expected", "description"))
    ledger_path = DOC / "CONSUMPTION.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    item = ledger["groups"][group]
    assert item[phase + "_consumed"] == 0
    if phase == "repair":
        assert item["initial_consumed"] == 1 and item["status"] == "FAIL_PARTIAL"
        assert spec.get("defect_basis"), "Repair requires a concrete retained failure"
    else:
        assert item["status"] == "NOT_STARTED"
    out = DOC / "RUNS" / group / ("R01" if phase == "initial" else "R02")
    assert spec["output"] == str(out)
    out.mkdir(parents=True, exist_ok=False)
    save(out / "SPEC.json", spec)
    item[phase + "_consumed"] = 1
    item["status"] = "RUNNING"
    item[phase + "_output"] = str(out.relative_to(ROOT))
    atomic_save(ledger_path, ledger)
    started = utc()
    start = time.monotonic()
    deadline = start + limit
    done = threading.Event()
    results = []
    violations = []
    reads = {}
    receipt_lock = threading.Lock()
    status = {"case": None, "component": None}
    first_failure = {}

    def receipt(code, result):
        return {"schema": "M3_R08_RUN_RECEIPT_V1", "group": group, "phase": phase,
                "status": result, "exit_code": code, "started_utc": started, "ended_utc": utc(),
                "elapsed_s": time.monotonic() - start, "limit_s": limit,
                "argv": spec["argv"], "cwd": str(ROOT), "spec_identity": identity(out / "SPEC.json"),
                "cases_total": len(cases), "cases_completed": len(results), "results": list(results),
                "first_failure_or_active": dict(first_failure or status), "audit_violations": list(violations),
                "assertions_matched": sum(r["assertion"] == "MATCHED" for r in results),
                "read_inputs": dict(reads), "candidate_subprocesses": 0,
                "scope": "synthetic/pure software only; no REAL or hardware certification"}

    def watchdog():
        if not done.wait(max(0, deadline - time.monotonic())):
            with receipt_lock:
                if done.is_set():
                    return
                save(out / "RECEIPT.json", receipt(124, "TIMEOUT_PARTIAL"))
            os._exit(124)

    temporary = out / "temp"
    temporary.mkdir()
    tempfile.tempdir = str(temporary)
    stdout = (out / "stdout.raw").open("w", encoding="utf-8", buffering=1, newline="\n")
    stderr = (out / "stderr.raw").open("w", encoding="utf-8", buffering=1, newline="\n")
    install_audit(out, frozen, external, violations, reads)
    threading.Thread(target=watchdog, daemon=True, name="r08-deadline").start()
    code, result = 0, "PASS_LIMITED_SOFTWARE"
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        try:
            modules = {}
            for index, case in enumerate(cases):
                status.update(case=case["id"], component=case["component"])
                print(json.dumps({"begin": status, "utc": utc()}), flush=True)
                # Component and case identity remain in frozen SPEC/receipts.
                # Short numeric directories leave room for full SHA filenames
                # under Windows CRT path limits; no claim identity is shortened.
                case_out = out / "cases" / f"{index:03d}"
                case_out.parent.mkdir(parents=True, exist_ok=True)
                try:
                    module_path = ROOT / case["selftest"]
                    if case["component"] not in modules:
                        name = "r08_" + group + "_" + case["component"]
                        module_spec = importlib.util.spec_from_file_location(name, module_path)
                        module = importlib.util.module_from_spec(module_spec)
                        sys.modules[name] = module
                        sys.path.insert(0, str(module_path.parent))
                        module_spec.loader.exec_module(module)
                        modules[case["component"]] = module
                    actual = modules[case["component"]].run_case(case["id"], case_out)
                    assert isinstance(actual, dict), "run_case must return evidence dict"
                    assert not violations, "FORBIDDEN_API_OR_WRITE_ATTEMPT"
                    entry = {"component": case["component"], "id": case["id"], "expected": case["expected"], "result": actual, "assertion": "MATCHED"}
                    save(case_out / "COORDINATOR_RESULT.json", entry)
                except Exception as error:
                    traceback.print_exc()
                    code, result = 1, "FAIL_PARTIAL"
                    if not first_failure:
                        first_failure.update(status)
                    entry = {"component": case["component"], "id": case["id"], "expected": case["expected"], "assertion": "FAILED", "error": type(error).__name__ + ":" + str(error)}
                    # Independent frozen cases continue once each within the same
                    # deadline; no failed or passed case is automatically replayed.
                    save(out / f"CASE_FAILURE_{index:03d}.json", entry)
                results.append(entry)
                print(json.dumps({"completed": case["id"], "assertion": entry["assertion"], "count": len(results)}), flush=True)
                if violations:
                    raise PermissionError("R08_AUDIT_VIOLATION_STOPS_GROUP")
            status.update(case=None, component=None)
        except BaseException:
            traceback.print_exc()
            code, result = 1, "FAIL_PARTIAL"
        finally:
            stream_identities = {}
            try:
                stdout.flush()
                stderr.flush()
                for rel, expected in list(reads.items()):
                    try:
                        if identity(ROOT / rel) != expected:
                            raise ValueError("R08_INPUT_CHANGED:" + rel)
                    except Exception as error:
                        code, result = 1, "FAIL_PARTIAL"
                        violations.append({"event": "finish_input_check", "reason": type(error).__name__ + ":" + str(error)})
                stream_identities = {"stdout": identity(out / "stdout.raw"), "stderr": identity(out / "stderr.raw")}
            except BaseException as error:
                code, result = 1, "FAIL_PARTIAL"
                violations.append({"event": "finalization", "reason": type(error).__name__ + ":" + str(error)})
            with receipt_lock:
                if time.monotonic() >= deadline:
                    code, result = 124, "TIMEOUT_PARTIAL"
                value = receipt(code, result)
                value.update(stream_identities)
                save(out / "RECEIPT.json", value)
                if time.monotonic() >= deadline:
                    code, result = 124, "TIMEOUT_PARTIAL"
                    save(out / "RECEIPT.json", receipt(code, result))
                done.set()
    stdout.close()
    stderr.close()
    # Audit remains active: shared ledger reconciliation is a separate metadata
    # operation by the coordinator, so candidate code cannot alter consumption.
    print(json.dumps({"group": group, "status": result, "exit": code, "completed": len(results), "total": len(cases), "receipt": str(out / "RECEIPT.json")}))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
