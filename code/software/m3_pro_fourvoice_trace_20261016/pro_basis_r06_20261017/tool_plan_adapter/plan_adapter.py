"""Assemble and audit bound tool plans; execute only the fixed R06 fixture.

Real-tool plans can be represented and audited, but this module deliberately has
no real-tool execution route. M2 must issue and implement a separate exact
execution admission. No JSON field or environment variable unlocks that route.
"""

from __future__ import annotations

import argparse
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import threading
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
DOCS = (ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/"
        "pro_basis_r06_20261017/tool_plan_adapter").resolve()
TB = (ROOT / "code/tb/board/m3_pro_fourvoice_trace_20261016/"
      "pro_basis_r06_20261017/tool_plan_adapter").resolve()
WORKER = (HERE / "fixture_worker.py").resolve()
PYTHON = Path(sys.executable).resolve()
JOB_HELPER = (ROOT / "code/software/t052_runner_acceptance_candidate_20261012/"
              "windows_job.py").resolve()
JOB_HELPER_SHA = "5450b8943b0616cc0f8ad7147c1c6a4b20eb4f04d8a7cc3fb515825941c0df1b"
SPEC_SCHEMA = "M3_R6_TOOL_PLAN_SPEC_V1"
PLAN_SCHEMA = "M3_R6_BOUND_TOOL_PLAN_V1"
FIXTURE_AUTHORITY = "R06_M3_SOFTWARE_FIXTURE_ONLY"
ROLES = ("sources", "roms", "testbenches", "dependencies")


class Refusal(ValueError):
    def __init__(self, code, detail=None):
        self.code = code
        self.detail = detail
        super().__init__(code if detail is None else f"{code}: {detail}")


def sha256_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(path):
    item = Path(path)
    raw = item.read_bytes()
    return {"path": str(item.resolve()), "bytes": len(raw),
            "sha256": sha256_bytes(raw)}


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def write_json_exclusive(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def is_within(path, parent):
    try:
        Path(path).resolve().relative_to(Path(parent).resolve())
        return True
    except ValueError:
        return False


def repo_path(value, label, must_exist=True, directory=False):
    if not isinstance(value, str) or not value or Path(value).is_absolute():
        raise Refusal("REPO_RELATIVE_PATH_REQUIRED", label)
    path = (ROOT / value).resolve()
    if not is_within(path, ROOT):
        raise Refusal("PATH_ESCAPE", label)
    if must_exist:
        if not path.exists() or path.is_symlink():
            raise Refusal("PATH_MISSING_OR_SYMLINK", label)
        if directory != path.is_dir():
            raise Refusal("PATH_KIND", label)
    return path


def declared_file(entry, label, allow_external=False):
    if set(entry) != {"path", "sha256"}:
        raise Refusal("FILE_ENTRY_FIELDS", label)
    raw_path = Path(entry["path"])
    if allow_external:
        if not raw_path.is_absolute():
            raise Refusal("EXECUTABLE_ABSOLUTE_PATH_REQUIRED", label)
        path = raw_path.resolve()
        if not path.is_file() or path.is_symlink():
            raise Refusal("EXECUTABLE_MISSING_OR_SYMLINK", label)
    else:
        path = repo_path(entry["path"], label)
        if not path.is_file():
            raise Refusal("INPUT_NOT_FILE", label)
    actual = identity(path)
    if actual["sha256"] != entry["sha256"]:
        raise Refusal("DECLARED_INPUT_SHA_MISMATCH", label)
    return actual


def output_paths(spec):
    output = repo_path(spec["output_dir"], "output_dir", must_exist=False)
    marker = repo_path(spec["consumption_marker"], "consumption_marker",
                       must_exist=False)
    fixture_root = DOCS / "RUN_01"
    real_root = (ROOT / "code/output").resolve()
    if spec["mode"] == "SOFTWARE_FIXTURE":
        if not is_within(output, fixture_root) or not is_within(marker, fixture_root):
            raise Refusal("FIXTURE_OUTPUT_SCOPE")
    else:
        if not is_within(output, real_root) or not is_within(marker, real_root):
            raise Refusal("REAL_OUTPUT_SCOPE")
        if not output.name.startswith("m3_r6_tool_plan_"):
            raise Refusal("REAL_OUTPUT_PREFIX")
    if output == marker or marker.suffix != ".json":
        raise Refusal("CONSUMPTION_MARKER_PATH")
    return output, marker


def normalize_spec(spec, spec_path):
    required = {"schema", "mode", "approved", "tool_kind", "fixture_authority",
                "sources", "roms", "testbenches", "executable", "dependencies",
                "argv", "cwd", "output_dir", "consumption_marker",
                "timeout_seconds"}
    if set(spec) != required or spec.get("schema") != SPEC_SCHEMA:
        raise Refusal("SPEC_FIELDS_OR_SCHEMA")
    if spec["approved"] is not False:
        raise Refusal("CALLER_MUST_NOT_SET_APPROVED")
    if spec["mode"] not in {"SOFTWARE_FIXTURE", "REAL_TOOL_REQUEST"}:
        raise Refusal("PLAN_MODE")
    if not isinstance(spec["tool_kind"], str) or not spec["tool_kind"]:
        raise Refusal("TOOL_KIND")
    if not isinstance(spec["timeout_seconds"], (int, float)) or isinstance(
            spec["timeout_seconds"], bool) or not 0 < spec["timeout_seconds"] <= 60:
        raise Refusal("TIMEOUT_RANGE")
    manifest = []
    for role in ROLES:
        if not isinstance(spec[role], list) or not spec[role]:
            raise Refusal("EMPTY_INPUT_ROLE", role)
        for index, entry in enumerate(spec[role]):
            manifest.append({"role": role, **declared_file(
                entry, f"{role}[{index}]")})
    executable = declared_file(spec["executable"], "executable", True)
    manifest.append({"role": "executable", **executable})
    paths = [item["path"] for item in manifest]
    if len(paths) != len(set(paths)):
        raise Refusal("DUPLICATE_INPUT_PATH")
    cwd = repo_path(spec["cwd"], "cwd", directory=True)
    output, marker = output_paths(spec)
    argv = spec["argv"]
    if (not isinstance(argv, list) or not argv
            or any(not isinstance(item, str) or not item for item in argv)
            or str(Path(argv[0]).resolve()) != executable["path"]):
        raise Refusal("ARGV_EXECUTABLE_BINDING")
    if spec["mode"] == "SOFTWARE_FIXTURE":
        if spec["fixture_authority"] != FIXTURE_AUTHORITY:
            raise Refusal("FIXTURE_AUTHORITY")
        expected = [str(PYTHON), "-I", "-S", "-B", str(WORKER)]
        if argv[:5] != expected or len(argv) != 6 or argv[5] not in {"stream", "error"}:
            raise Refusal("FIXTURE_ARGV_EXACT_BINDING")
        by_path = {item["path"]: item for item in manifest}
        for required_path in (str(WORKER), str(JOB_HELPER)):
            if required_path not in by_path:
                raise Refusal("FIXTURE_DEPENDENCY_NOT_BOUND", required_path)
    elif spec["fixture_authority"] is not None:
        raise Refusal("REAL_PLAN_FIXTURE_AUTHORITY_MUST_BE_NULL")
    return {
        "schema": PLAN_SCHEMA,
        "status": "BOUND_NOT_APPROVED",
        "mode": spec["mode"],
        "approved": False,
        "tool_kind": spec["tool_kind"],
        "fixture_authority": spec["fixture_authority"],
        "spec": identity(spec_path),
        "inputs": manifest,
        "argv": argv,
        "cwd": str(cwd),
        "output_dir": str(output),
        "consumption_marker": str(marker),
        "timeout_seconds": spec["timeout_seconds"],
        "real_execution_admission": "M2_R6_3_REQUIRED_SEPARATE_ARTIFACT",
        "real_tool_launch_route_present": False,
        "board_release_allowed": False,
    }


def assemble(spec_path, output):
    spec_path = repo_path(spec_path, "spec")
    output = repo_path(output, "plan_output", must_exist=False)
    if not is_within(output, DOCS / "RUN_01"):
        raise Refusal("PLAN_OUTPUT_SCOPE")
    plan = normalize_spec(load_json(spec_path), spec_path)
    write_json_exclusive(output, plan)
    return {"result": "BOUND_NOT_APPROVED", "plan": identity(output),
            "real_tool_launches": 0}


def audit(plan_path, expected_sha):
    path = repo_path(plan_path, "plan")
    plan_identity = identity(path)
    if plan_identity["sha256"] != expected_sha:
        raise Refusal("PLAN_SHA_MISMATCH")
    plan = load_json(path)
    if (plan.get("schema") != PLAN_SCHEMA or plan.get("approved") is not False
            or plan.get("status") != "BOUND_NOT_APPROVED"):
        raise Refusal("PLAN_SCHEMA_OR_APPROVAL")
    if identity(plan["spec"]["path"]) != plan["spec"]:
        raise Refusal("SPEC_CHANGED")
    seen = set()
    for item in plan["inputs"]:
        current = identity(item["path"])
        if current != {key: item[key] for key in ("path", "bytes", "sha256")}:
            raise Refusal("INPUT_CHANGED", item["path"])
        if item["path"] in seen:
            raise Refusal("DUPLICATE_INPUT_PATH")
        seen.add(item["path"])
    if str(Path(plan["argv"][0]).resolve()) != next(
            item["path"] for item in plan["inputs"] if item["role"] == "executable"):
        raise Refusal("ARGV_EXECUTABLE_BINDING")
    return plan, {"result": "AUDIT_OK_NOT_APPROVAL", "plan": plan_identity,
                  "inputs": len(plan["inputs"]), "real_tool_launches": 0}


def load_job():
    if os.name != "nt" or identity(JOB_HELPER)["sha256"] != JOB_HELPER_SHA:
        raise Refusal("WINDOWS_OR_PINNED_JOB_HELPER_REQUIRED")
    spec = importlib.util.spec_from_file_location("m3_r6_job_helper", JOB_HELPER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.WindowsJob()


def atomic_claim(marker, plan_sha):
    payload = json.dumps({"schema": "M3_R6_TOOL_PLAN_CONSUMPTION_V1",
        "state": "CLAIMED", "plan_sha256": plan_sha, "pid": os.getpid(),
        "created_utc": datetime.now(timezone.utc).isoformat()}, indent=2).encode()
    try:
        descriptor = os.open(marker, os.O_WRONLY | os.O_CREAT | os.O_EXCL)
    except FileExistsError as error:
        raise Refusal("PLAN_ALREADY_CONSUMED_OR_IN_PROGRESS") from error
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload + b"\n")


def replace_marker(marker, value):
    temporary = marker.with_name(marker.name + f".tmp.{os.getpid()}")
    temporary.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8",
                         newline="\n")
    os.replace(temporary, marker)


def run_fixture(plan_path, expected_sha):
    plan, audit_result = audit(plan_path, expected_sha)
    if plan["mode"] != "SOFTWARE_FIXTURE":
        raise PermissionError("M2_EXECUTION_ADMISSION_REQUIRED_REAL_TOOL_NOT_LAUNCHED")
    if plan["fixture_authority"] != FIXTURE_AUTHORITY:
        raise Refusal("FIXTURE_AUTHORITY")
    output = Path(plan["output_dir"])
    marker = Path(plan["consumption_marker"])
    if output.exists():
        raise FileExistsError("EXCLUSIVE_OUTPUT_ALREADY_EXISTS")
    atomic_claim(marker, expected_sha)
    output.mkdir(parents=True, exist_ok=False)
    before = {item["path"]: identity(item["path"]) for item in plan["inputs"]}
    receipt = {"schema": "M3_R6_TOOL_PLAN_EXECUTION_RECEIPT_V1",
        "result": "FAIL_PARTIAL", "plan_sha256": expected_sha,
        "audit": audit_result, "argv": plan["argv"], "cwd": plan["cwd"],
        "output_dir": str(output), "consumption_marker": str(marker),
        "timeout_seconds": plan["timeout_seconds"], "job_attached": False,
        "streaming_capture": "PIPE_THREADS_TO_RAW_AND_TIMESTAMPED_EVENTS",
        "root_exit_code": None, "timed_out": False, "cleanup": None,
        "first_failure": None, "error": None, "real_tool_launches": 0,
        "fixture_process_launches": 0, "board_release_allowed": False,
        "inputs_before": before}
    start = time.monotonic()
    process = None
    job = None
    event_lock = threading.Lock()
    event_sequence = [0]
    event_path = output / "stream_events.jsonl"

    def capture(pipe, stream_name, raw_path):
        with raw_path.open("xb") as raw_stream, event_path.open(
                "a", encoding="utf-8", newline="\n") as events:
            while True:
                chunk = pipe.readline()
                if not chunk:
                    break
                raw_stream.write(chunk)
                raw_stream.flush()
                with event_lock:
                    event_sequence[0] += 1
                    event = {"sequence": event_sequence[0], "stream": stream_name,
                        "elapsed_seconds": round(time.monotonic() - start, 6),
                        "bytes": len(chunk), "sha256": sha256_bytes(chunk),
                        "text_utf8_replace": chunk.decode("utf-8", errors="replace").rstrip("\r\n")}
                    events.write(json.dumps(event) + "\n")
                    events.flush()
    try:
        job = load_job()
        process = subprocess.Popen(plan["argv"], cwd=plan["cwd"],
            stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | 4)
        receipt["fixture_process_launches"] = 1
        job.attach_and_resume(process)
        receipt["job_attached"] = True
        threads = [threading.Thread(target=capture, args=(process.stdout, "stdout",
                   output / "stdout.raw"), daemon=True),
                   threading.Thread(target=capture, args=(process.stderr, "stderr",
                   output / "stderr.raw"), daemon=True)]
        for thread in threads:
            thread.start()
        try:
            receipt["root_exit_code"] = process.wait(timeout=plan["timeout_seconds"])
        except subprocess.TimeoutExpired:
            receipt["timed_out"] = True
            receipt["cleanup"] = job.terminate()
            receipt["root_exit_code"] = process.wait(timeout=5)
        for thread in threads:
            thread.join(timeout=3)
            if thread.is_alive():
                raise RuntimeError("STREAM_READER_DID_NOT_FINISH")
        if not receipt["timed_out"]:
            receipt["cleanup"] = {"mechanism": "KILL_ON_JOB_CLOSE", "owned_job": True}
        if receipt["root_exit_code"] == 0 and not receipt["timed_out"]:
            receipt["result"] = "PASS_SOFTWARE_FIXTURE_ONLY"
        else:
            receipt["first_failure"] = {"stage": "fixture_process",
                "exit_code": receipt["root_exit_code"],
                "timed_out": receipt["timed_out"]}
    except BaseException as error:
        receipt["error"] = type(error).__name__ + ": " + str(error)
        receipt["first_failure"] = receipt["first_failure"] or {
            "stage": "adapter", "error": receipt["error"]}
        if not isinstance(error, Exception):
            raise
    finally:
        if process is not None and not receipt["job_attached"]:
            if process.poll() is None:
                process.kill()
            receipt["root_exit_code"] = process.wait(timeout=5)
            receipt["cleanup"] = {"mechanism": "CURRENT_POPEN_HANDLE_KILL"}
        if job is not None:
            job.close()
        receipt["elapsed_seconds"] = round(time.monotonic() - start, 6)
        receipt["inputs_after"] = {
            item["path"]: identity(item["path"]) for item in plan["inputs"]}
        receipt["inputs_unchanged"] = receipt["inputs_before"] == receipt["inputs_after"]
        receipt["logs"] = {name: identity(output / name) for name in
            ("stdout.raw", "stderr.raw", "stream_events.jsonl")
            if (output / name).exists()}
        if not receipt["inputs_unchanged"] and receipt["first_failure"] is None:
            receipt["result"] = "FAIL_PARTIAL"
            receipt["first_failure"] = {"stage": "post_identity",
                                        "error": "INPUT_CHANGED"}
        write_json_exclusive(output / "RECEIPT.json", receipt)
        replace_marker(marker, {"schema": "M3_R6_TOOL_PLAN_CONSUMPTION_V1",
            "state": "CONSUMED", "plan_sha256": expected_sha,
            "receipt": identity(output / "RECEIPT.json"),
            "result": receipt["result"], "pid": os.getpid()})
    return receipt


def emit(value):
    print(json.dumps(value, ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    build = commands.add_parser("assemble")
    build.add_argument("--spec", required=True)
    build.add_argument("--output", required=True)
    check = commands.add_parser("audit")
    check.add_argument("--plan", required=True)
    check.add_argument("--sha256", required=True)
    run = commands.add_parser("run-fixture")
    run.add_argument("--plan", required=True)
    run.add_argument("--sha256", required=True)
    args = parser.parse_args()
    try:
        if args.command == "assemble":
            result = assemble(args.spec, args.output)
            code = 0
        elif args.command == "audit":
            _, result = audit(args.plan, args.sha256)
            code = 0
        else:
            result = run_fixture(args.plan, args.sha256)
            code = 0 if result["result"] == "PASS_SOFTWARE_FIXTURE_ONLY" else 1
    except PermissionError as error:
        result = {"result": "REFUSED", "reason": str(error),
                  "process_launches": 0, "board_release_allowed": False}
        code = 4
    except FileExistsError as error:
        result = {"result": "REFUSED", "reason": str(error),
                  "process_launches": 0, "board_release_allowed": False}
        code = 5
    except Refusal as error:
        result = {"result": "REFUSED", "reason": error.code,
                  "detail": error.detail, "process_launches": 0,
                  "board_release_allowed": False}
        code = 3 if error.code == "PLAN_ALREADY_CONSUMED_OR_IN_PROGRESS" else 2
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as error:
        result = {"result": "ERROR", "reason": type(error).__name__ + ": " + str(error),
                  "process_launches": 0, "board_release_allowed": False}
        code = 2
    emit(result)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
