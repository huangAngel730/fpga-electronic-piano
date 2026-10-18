"""Freeze the R10 preparation inputs; do not load candidates or run tests."""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[6]
REL = Path("m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017")
SW, DOC = ROOT / "code/software" / REL, ROOT / "code/docs/test" / REL
OLD = DOC.parent / "task_day4_completion_20261017"


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def save(path, data):
    with path.open("xb") as stream:
        stream.write((json.dumps(data, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def ref(path):
    path = path.resolve()
    raw = path.read_bytes()
    return {"path": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT) else str(path),
            "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def main():
    start = read(DOC / "CONTINUATION_START_R01.json")
    current = read(DOC / "CONSUMPTION.json")
    if current["initial"]["status"] != "NOT_CONSUMED":
        raise RuntimeError("FREEZE_ONLY_BEFORE_INITIAL_CONSUMPTION")
    files = {}

    def add(path):
        actual = ref(path)
        files[actual["path"]] = actual
        return actual

    def descriptor(value):
        path = Path(value["path"])
        path = path if path.is_absolute() else ROOT / path
        actual = add(path)
        if any(actual[k] != value[k] for k in ("bytes", "sha256")):
            raise ValueError("DECLARED_INPUT_BYTES_CHANGED:" + str(path))
        return actual

    def walk(value):
        if isinstance(value, dict):
            if {"path", "bytes", "sha256"} <= value.keys() and isinstance(value["path"], str):
                descriptor(value)
            else:
                for item in value.values():
                    walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)

    for role in ("admission", "serial"):
        ready = read(DOC / role / "READY.json")
        # Verify every descriptor explicitly declared by the member; there are
        # no candidate imports, AST compilations or test calls in this freezer.
        walk(ready)
        add(DOC / role / "READY.json")
        add(DOC / role / "CASES.json")
    bindings = {"schema": "N10_M3_COORDINATOR_BINDINGS_V1",
                "application_adapter": add(SW / "admission/adapter.py"),
                "handoff": add(SW / "serial/handoff.py"),
                "existing_chain": add(SW.parent / "task_day4_completion_20261017/chain.py"),
                "existing_modules": read(OLD / "MODULE_BINDINGS.json")["modules"]}
    for item in bindings["existing_modules"].values():
        descriptor(item)
    save(DOC / "MODULE_BINDINGS.json", bindings)
    contract_path = ROOT / "code/docs/test/m2_night_r10_20261017/DELIVERY_CONTRACT.json"
    owner = read(contract_path)
    references = [descriptor({"path": p, **value}) for p, value in owner["references"].items()]
    request_path = DOC / "admission/APPLICATION_REQUEST.json"
    application = read(request_path)
    walk(application)
    for p in (OLD / "RESULT.json", OLD / "CONSUMPTION.json", OLD / "HANDOFF.json"):
        add(p)
    save(DOC / "FROZEN_PRE_LINK_CONSUMPTION.json", current)
    template = {"schema": "N10_M3_PREPARE_PIPELINE_REQUEST_V1", "mode": "PREPARE_APPLICATION_ONLY",
                "capture_id": application["execution_spec"]["window_parameters"]["CAPTURE_ID"],
                "application_request": add(request_path), "source_contract_refs": references,
                "module_bindings": add(DOC / "MODULE_BINDINGS.json"),
                "context": {"original_START": start["original_START"], "deadline": start["deadline"], "goal": start["goal"],
                            "receipts": {"old_software": [add(OLD / "RESULT.json"), add(OLD / "HANDOFF.json")],
                                         "consumption": [add(OLD / "CONSUMPTION.json"), add(DOC / "FROZEN_PRE_LINK_CONSUMPTION.json")],
                                         "first_failure": [add(OLD / "RESULT.json")],
                                         "drill_publication": [add(DOC / "night_drill_r01/RESULT_RECEIPT.json"),
                                                               add(DOC / "night_drill_r01/REMOTE_VERIFICATION_LOCAL.json")]}}}
    save(DOC / "PIPELINE_REQUEST_TEMPLATE.json", template)
    add(DOC / "PIPELINE_REQUEST_TEMPLATE.json")
    add(contract_path)
    # All explicit pinned old assembler helper dependencies remain reusable
    # sources, not repeated old test suites.
    old_base = ROOT / "code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017"
    for name in ("coordinator/task_day4_completion_20261017/common.py", "plan_consumption_guard/m3r08_common.py",
                 "recursive_include_audit/m3r08_01.py", "plan_consumption_guard/m3r08_03.py",
                 "output_reservation/m3r08_04.py", "tool_dependency_identity/m3r08_05.py"):
        add(old_base / name)
    add(ROOT / "code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/tool_plan_adapter/r07_fix/consumer.py")
    for p in SW.rglob("*.py"):
        if "night_drill_r01" not in p.parts:
            add(p)
    save(DOC / "FROZEN_INPUTS.json", {"schema": "N10_M3_FROZEN_INPUTS_V1", "files": sorted(files.values(), key=lambda x: x["path"]),
                                     "external_tools": "identity reads only; no executable invocation or redistribution"})
    save(DOC / "RUN_CONTRACT.json", {"schema": "N10_M3_RUN_CONTRACT_V1", "utc": datetime.now(timezone.utc).isoformat(),
        "base_commit": start["base_commit"], "original_START": start["original_START"], "deadline": start["deadline"],
        "goal": start["goal"], "unique_executor_publisher": "night1", "members": {"night2": "admission", "night3": "serial"},
        "argv": [sys.executable, "-B", "-X", "utf8", str(SW / "run_link.py")], "cwd": str(ROOT),
        "interpreter": {"path": sys.executable, "sha256": hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()},
        "frozen_inputs": ref(DOC / "FROZEN_INPUTS.json"), "request_template": ref(DOC / "PIPELINE_REQUEST_TEMPLATE.json"),
        "effective_request_rule": "Append immutable actual CONSUMED_RUNNING snapshot descriptor inside single group before preparation",
        "output": "code/output/m3_c9_chain_night_r10_20261017/LINK_R01", "budget_initial": 120,
        "budget_first_specific_defect_increment": 60, "new_subprocess_HDL_EDA_device": 0,
        "old_114": "REUSED, not replayed", "finish_phase": "PENDING; no canonical FRAME_PLAN generated",
        "validation_boundary": "Source-bound software application/handoff only; no actual capture/math/physical approval"})
    print(json.dumps({"frozen_input_count": len(files), "capture_id": template["capture_id"], "initial_budget": "NOT_CONSUMED"}))


if __name__ == "__main__":
    main()
