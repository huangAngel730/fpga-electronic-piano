"""Freeze one targeted <=60s consumer repair group, without executing tests."""
import json
from pathlib import Path
import shutil
import sys

import consumer as c


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write("\n")


def entry(path):
    return {"path": path.relative_to(c.ROOT).as_posix(), "sha256": c.identity(path)["sha256"]}


def main():
    pins = json.loads(c.TRUST_PATH.read_text(encoding="utf-8"))
    if c.digest(c.TRUST_PATH.read_bytes()) != c.TRUST_SHA or any(
            c.identity(item["path"]) != item for item in pins.values()):
        raise SystemExit("PINNED_RUNTIME_DRIFT_BEFORE_FREEZE")
    tb = c.ROOT / "code/tb/board/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/tool_plan_adapter"
    base = {"schema": "M3_R6_TOOL_PLAN_SPEC_V1", "mode": "SOFTWARE_FIXTURE", "approved": False,
            "tool_kind": "PYTHON_SOFTWARE_FIXTURE", "fixture_authority": "R06_M3_SOFTWARE_FIXTURE_ONLY",
            "sources": [entry(tb / "fixture_source.sv")], "roms": [entry(tb / "fixture_rom.hex")],
            "testbenches": [entry(tb / "fixture_tb.sv")],
            "executable": {"path": pins["python"]["path"], "sha256": pins["python"]["sha256"]},
            "dependencies": [entry(Path(pins[k]["path"])) for k in ("worker", "job_helper", "legacy")] +
                            [entry(c.HERE / "consumer.py")],
            "argv": [pins["python"]["path"], "-I", "-S", "-B", pins["worker"]["path"], "stream"],
            "cwd": c.HERE.relative_to(c.ROOT).as_posix(),
            "output_dir": (c.DOC / "RUN_01/UNUSED_TEMPLATE_OUTPUT").relative_to(c.ROOT).as_posix(),
            "consumption_marker": (c.DOC / "RUN_01/UNUSED_TEMPLATE_MARKER.json").relative_to(c.ROOT).as_posix(),
            "timeout_seconds": 5}
    save(c.DOC / "BASE_SPEC.json", base)
    save(c.DOC / "CASE_SPEC.json", {"scope": "NEW_CONSUMER_FORGERY_AND_IMMEDIATE_GUARD_ONLY",
        "plan_mutations": ["argv_arguments", "argv_worker", "argv_python", "cwd", "output_dir",
                           "consumption_marker", "timeout_seconds", "inputs", "helper_identity", "spec_identity",
                           "runtime_identity", "unknown_field", "mode", "approved", "status", "fixture_authority",
                           "tool_kind", "real_tool_launch_route_present", "fixed_cwd"],
        "extra_cases": ["rebuilt_consumer_control", "spec_and_plan_rehashed", "spawn_argument_argv",
                        "spawn_argument_cwd", "spawn_argument_shell", "late_plan_tamper"],
        "expected": {"new_cases": 25, "positive_controls": 1, "negative_cases": 24,
                     "CLI_negative_exit2": 2, "fixed_worker_launches": 1},
        "old_seven_cases_replayed": 0, "tree_timeout_overflow_proof_extended": False})
    run = c.DOC / "RUN_01"
    run.mkdir(exist_ok=False)
    support = c.ROOT / "code/software/m3_r05_functional_integration_20261015"
    source = list(c.HERE.glob("*.py")) + list(c.DOC.glob("*.json")) + list(c.DOC.glob("*.md"))
    source += list((c.DOC / "READ_ONLY_ORIGINALS").iterdir())
    source += [Path(pins[k]["path"]) for k in ("legacy", "worker", "job_helper")]
    source += [tb / n for n in ("fixture_source.sv", "fixture_tb.sv", "fixture_rom.hex")]
    source += [support / n for n in ("supervised_process.py", "windows_job.py", "common.py")]
    snapshots = run / "SOURCE_INPUT_ORIGINALS"
    snapshots.mkdir()
    entries = []
    for index, path in enumerate(sorted(set(source)), 1):
        original_identity = c.identity(path)
        snapshot = snapshots / (f"{index:03d}_" + path.name)
        shutil.copyfile(path, snapshot)
        snapshot_identity = c.identity(snapshot)
        if c.identity(path) != original_identity or any(
                original_identity[k] != snapshot_identity[k] for k in ("bytes", "sha256")):
            raise SystemExit("SOURCE_DRIFT_OR_SNAPSHOT_MISMATCH")
        entries.append({"original": original_identity, "snapshot": snapshot_identity})
    # Same Python runtime, independently remeasured at freeze (no old suite run).
    old_runtime = c.ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r07_20261017/public_capture_tb/RUN_SPEC.json"
    runtime = json.loads(old_runtime.read_text(encoding="utf-8"))["tool_runtime"]
    save(c.DOC / "RUN_SPEC.json", {"schema": "M3_R6_4_R07_FIX_RUN_SPEC_V1",
        "baseline": "40d78131e8ed50643dd169816f7bfc7149a8ced9", "group": "ORIGINAL_R06_SINGLE_DEFECT_REPAIR",
        "budget_s": 60, "work_deadline_s": 55, "cleanup_reserve_s": 5,
        "command": [sys.executable, "-s", "-B", str(c.HERE / "selftest.py")], "cwd": str(c.HERE),
        "sources_inputs_dependencies": entries,
        "tool_runtime": [c.identity(item["path"]) for item in runtime],
        "python_version": sys.version, "run": str(run), "old_seven_cases_replayed": 0,
        "initial_group_recovered": False, "repair_groups_allowed": 1, "additional_repairs_allowed": 0,
        "real_tools_HDL_EDA_hardware_allowed": 0, "board_release_allowed": False})
    print(json.dumps({"RUN_SPEC": c.identity(c.DOC / "RUN_SPEC.json"), "functional_groups_run": 0}))


if __name__ == "__main__":
    main()
