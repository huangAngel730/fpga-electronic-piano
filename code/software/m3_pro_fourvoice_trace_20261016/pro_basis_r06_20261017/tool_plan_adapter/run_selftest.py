"""One R06 <=90 second software group for the new plan adapter."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[4]
DOCS = (ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/"
        "pro_basis_r06_20261017/tool_plan_adapter").resolve()
TB = (ROOT / "code/tb/board/m3_pro_fourvoice_trace_20261016/"
      "pro_basis_r06_20261017/tool_plan_adapter").resolve()
ADAPTER = HERE / "plan_adapter.py"
WORKER = HERE / "fixture_worker.py"
HELPER = (ROOT / "code/software/t052_runner_acceptance_candidate_20261012/"
          "windows_job.py").resolve()
PYTHON = Path(sys.executable).resolve()
SCOPE = DOCS / "TEST_SCOPE.json"


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def identity(path):
    item = Path(path)
    return {"path": str(item.resolve()), "bytes": item.stat().st_size,
            "sha256": sha(item)}


def rel(path):
    return Path(path).resolve().relative_to(ROOT).as_posix()


def write_json(path, value):
    with Path(path).open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def require(value, reason):
    if not value:
        raise AssertionError(reason)


def entry(path):
    return {"path": rel(path), "sha256": sha(path)}


def make_spec(source, output, marker, worker_mode="stream",
              plan_mode="SOFTWARE_FIXTURE", approved=False):
    return {
        "schema": "M3_R6_TOOL_PLAN_SPEC_V1",
        "mode": plan_mode,
        "approved": approved,
        "tool_kind": "PYTHON_SOFTWARE_FIXTURE" if plan_mode == "SOFTWARE_FIXTURE"
                     else "REAL_TOOL_REQUEST_PLACEHOLDER",
        "fixture_authority": "R06_M3_SOFTWARE_FIXTURE_ONLY"
                             if plan_mode == "SOFTWARE_FIXTURE" else None,
        "sources": [entry(source)],
        "roms": [entry(TB / "fixture_rom.hex")],
        "testbenches": [entry(TB / "fixture_tb.sv")],
        "executable": {"path": str(PYTHON), "sha256": sha(PYTHON)},
        "dependencies": [entry(WORKER), entry(HELPER), entry(ADAPTER)],
        "argv": [str(PYTHON), "-I", "-S", "-B", str(WORKER), worker_mode],
        "cwd": rel(HERE),
        "output_dir": rel(output),
        "consumption_marker": rel(marker),
        "timeout_seconds": 5,
    }


def invoke(root, label, args, expected):
    folder = root / "control"
    folder.mkdir(exist_ok=True)
    command = [str(PYTHON), "-I", "-S", "-B", str(ADAPTER), *args]
    started = time.monotonic()
    run = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=12,
                         check=False)
    elapsed = round(time.monotonic() - started, 6)
    (folder / f"{label}.stdout.raw").write_bytes(run.stdout)
    (folder / f"{label}.stderr.raw").write_bytes(run.stderr)
    require(run.returncode == expected,
            f"{label}: exit {run.returncode}, expected {expected}")
    parsed = json.loads(run.stdout.decode("utf-8"))
    return {"label": label, "argv": command, "cwd": str(ROOT),
            "exit_code": run.returncode, "elapsed_seconds": elapsed,
            "stdout": identity(folder / f"{label}.stdout.raw"),
            "stderr": identity(folder / f"{label}.stderr.raw"),
            "observed": parsed}


def assemble(root, label, spec):
    spec_path = root / f"{label}.spec.json"
    plan_path = root / f"{label}.plan.json"
    write_json(spec_path, spec)
    call = invoke(root, label + "_assemble",
                  ["assemble", "--spec", rel(spec_path), "--output", rel(plan_path)], 0)
    return spec_path, plan_path, sha(plan_path), call


def main():
    started = time.monotonic()
    deadline = started + 90
    root = DOCS / "RUN_01"
    root.mkdir(exist_ok=False)
    scope = json.loads(SCOPE.read_text(encoding="utf-8"))
    expected_sources = scope["source_identities"]
    actual_sources = {name: identity(ROOT / item["path"])
                      for name, item in expected_sources.items()}
    require(actual_sources == expected_sources, "FROZEN_SOURCE_IDENTITY_MISMATCH")
    receipt = {"schema": "M3_R6_TOOL_PLAN_ADAPTER_GROUP_V1",
        "result": "FAIL_PARTIAL", "level": "L1_SOFTWARE_FIXTURE_ONLY",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "maximum_seconds": 90, "group_number": 1,
        "scope": identity(SCOPE), "source_identities": actual_sources,
        "cases": [], "first_failure": None, "fixture_process_launches": 0,
        "real_tool_launches": 0,
        "not_run": ["Icarus", "ModelSim", "Gowin", "RTL simulation",
                    "physical tools", "hardware"],
        "board_release_allowed": False, "error": None}
    write_json(root / "START.json", receipt)
    try:
        require(scope["groups_allowed"] == 1
                and scope["maximum_group_seconds"] == 90,
                "GROUP_SCOPE_CHANGED")

        # 1. Bound positive plan and time-stamped live stdout/stderr.
        output = root / "valid_stream" / "process"
        marker = root / "valid_stream.consumed.json"
        _, plan, plan_sha, call = assemble(root, "valid_stream",
            make_spec(TB / "fixture_source.sv", output, marker))
        receipt["cases"].append({"case": "valid_stream", "assemble": call})
        receipt["cases"][-1]["audit"] = invoke(root, "valid_stream_audit",
            ["audit", "--plan", rel(plan), "--sha256", plan_sha], 0)
        receipt["cases"][-1]["run"] = invoke(root, "valid_stream_run",
            ["run-fixture", "--plan", rel(plan), "--sha256", plan_sha], 0)
        process_receipt = json.loads((output / "RECEIPT.json").read_text(encoding="utf-8"))
        require(process_receipt["job_attached"]
                and process_receipt["root_exit_code"] == 0
                and len((output / "stream_events.jsonl").read_text(
                    encoding="utf-8").splitlines()) == 6,
                "VALID_STREAM_LIFECYCLE_OR_EVENTS")
        receipt["fixture_process_launches"] += 1
        receipt["cases"][-1]["result"] = "PASS"

        # 2. Expected tool error preserves the first failure and both streams.
        output = root / "expected_error" / "process"
        marker = root / "expected_error.consumed.json"
        _, plan, plan_sha, call = assemble(root, "expected_error",
            make_spec(TB / "fixture_source.sv", output, marker, "error"))
        item = {"case": "expected_error_first_failure", "assemble": call}
        item["run"] = invoke(root, "expected_error_run",
            ["run-fixture", "--plan", rel(plan), "--sha256", plan_sha], 1)
        process_receipt = json.loads((output / "RECEIPT.json").read_text(encoding="utf-8"))
        require(process_receipt["first_failure"] == {
            "stage": "fixture_process", "exit_code": 7, "timed_out": False},
            "FIRST_FAILURE_NOT_EXACT")
        item["result"] = "PASS_EXPECTED_REFUSAL"
        receipt["cases"].append(item)
        receipt["fixture_process_launches"] += 1
        receipt["first_failure"] = {"case": item["case"],
                                    **process_receipt["first_failure"]}

        # 3. A source changed after assembly is rejected before launch.
        mutable = root / "mutable_source.sv"
        mutable.write_text("module mutable_v1; endmodule\n", encoding="ascii")
        output = root / "wrong_input" / "process"
        marker = root / "wrong_input.consumed.json"
        _, plan, plan_sha, call = assemble(root, "wrong_input",
            make_spec(mutable, output, marker))
        mutable.write_text("module mutable_v2; endmodule\n", encoding="ascii")
        audit_call = invoke(root, "wrong_input_audit",
            ["audit", "--plan", rel(plan), "--sha256", plan_sha], 2)
        require(audit_call["observed"]["reason"] == "INPUT_CHANGED"
                and not marker.exists() and not output.exists(),
                "CHANGED_INPUT_NOT_PRELAUNCH_REFUSED")
        receipt["cases"].append({"case": "changed_input", "assemble": call,
            "audit": audit_call, "result": "PASS_EXPECTED_REFUSAL",
            "process_launches": 0})

        # 4. A caller cannot create approval; true is rejected at assembly.
        spec_path = root / "caller_approved_true.spec.json"
        plan_path = root / "caller_approved_true.plan.json"
        spec = make_spec(TB / "fixture_source.sv",
            root / "caller_approved_true" / "process",
            root / "caller_approved_true.consumed.json", approved=True)
        write_json(spec_path, spec)
        approved_call = invoke(root, "caller_approved_true_assemble",
            ["assemble", "--spec", rel(spec_path), "--output", rel(plan_path)], 2)
        require(approved_call["observed"]["reason"] == "CALLER_MUST_NOT_SET_APPROVED",
                "CALLER_APPROVAL_NOT_REJECTED")
        receipt["cases"].append({"case": "caller_approved_true",
            "call": approved_call, "result": "PASS_EXPECTED_REFUSAL",
            "process_launches": 0})

        # 5. Even a valid real-tool request is audit-only without M2 admission.
        real_output = ROOT / "code/output/m3_r6_tool_plan_unapproved_fixture"
        real_marker = ROOT / "code/output/m3_r6_tool_plan_unapproved_fixture.consumed.json"
        _, plan, plan_sha, call = assemble(root, "real_unapproved",
            make_spec(TB / "fixture_source.sv", real_output, real_marker,
                      plan_mode="REAL_TOOL_REQUEST"))
        run_call = invoke(root, "real_unapproved_run",
            ["run-fixture", "--plan", rel(plan), "--sha256", plan_sha], 4)
        require("M2_EXECUTION_ADMISSION_REQUIRED" in run_call["observed"]["reason"]
                and not real_output.exists() and not real_marker.exists(),
                "REAL_TOOL_NOT_PRELAUNCH_REFUSED")
        receipt["cases"].append({"case": "real_tool_without_M2_admission",
            "assemble": call, "run": run_call,
            "result": "PASS_EXPECTED_REFUSAL", "process_launches": 0})

        # 6. A conflicting output directory is rejected without consumption.
        output = root / "output_conflict" / "process"
        marker = root / "output_conflict.consumed.json"
        _, plan, plan_sha, call = assemble(root, "output_conflict",
            make_spec(TB / "fixture_source.sv", output, marker))
        output.mkdir(parents=True)
        run_call = invoke(root, "output_conflict_run",
            ["run-fixture", "--plan", rel(plan), "--sha256", plan_sha], 5)
        require(not marker.exists(), "OUTPUT_CONFLICT_CONSUMED")
        receipt["cases"].append({"case": "exclusive_output_conflict",
            "assemble": call, "run": run_call,
            "result": "PASS_EXPECTED_REFUSAL", "process_launches": 0})

        # 7. Two consumers race one atomic marker; exactly one launches.
        output = root / "concurrent" / "process"
        marker = root / "concurrent.consumed.json"
        _, plan, plan_sha, call = assemble(root, "concurrent",
            make_spec(TB / "fixture_source.sv", output, marker))
        command = [str(PYTHON), "-I", "-S", "-B", str(ADAPTER),
            "run-fixture", "--plan", rel(plan), "--sha256", plan_sha]
        racers = [subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE,
                   stderr=subprocess.PIPE) for _ in range(2)]
        race_results = []
        for index, process in enumerate(racers):
            out, err = process.communicate(timeout=12)
            (root / "control" / f"concurrent_{index}.stdout.raw").write_bytes(out)
            (root / "control" / f"concurrent_{index}.stderr.raw").write_bytes(err)
            race_results.append({"exit_code": process.returncode,
                "stdout": json.loads(out.decode("utf-8")),
                "stdout_identity": identity(root / "control" / f"concurrent_{index}.stdout.raw"),
                "stderr_identity": identity(root / "control" / f"concurrent_{index}.stderr.raw")})
        require(sorted(item["exit_code"] for item in race_results) == [0, 3]
                and sum(item["stdout"].get("process_launches", 1) == 0
                        for item in race_results) == 1,
                "CONCURRENT_CONSUMPTION_NOT_EXCLUSIVE")
        receipt["fixture_process_launches"] += 1
        receipt["cases"].append({"case": "concurrent_consumption",
            "assemble": call, "racers": race_results, "result": "PASS"})

        require(time.monotonic() < deadline, "GROUP_TIMEOUT")
        require({name: identity(ROOT / item["path"])
                 for name, item in expected_sources.items()} == expected_sources,
                "SOURCE_CHANGED_DURING_GROUP")
        receipt["result"] = "PASS_SOFTWARE_FIXTURE_ONLY"
    except Exception as error:
        receipt["error"] = type(error).__name__ + ": " + str(error)
    finally:
        receipt["elapsed_seconds"] = round(time.monotonic() - started, 6)
        receipt["exit_code"] = 0 if receipt["result"] == "PASS_SOFTWARE_FIXTURE_ONLY" else 1
        receipt["sources_after"] = {
            name: identity(ROOT / item["path"])
            for name, item in expected_sources.items()}
        write_json(root / "GROUP_RECEIPT.json", receipt)
        print(json.dumps({key: receipt[key] for key in (
            "result", "level", "elapsed_seconds", "exit_code", "error",
            "fixture_process_launches", "real_tool_launches")}))
    return receipt["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
