"""R10 preparation entry: assemble the real source application, then handoff.

This entry has no HDL/tool route. The unresolved stop/finish phase prevents a
full frozen FRAME_PLAN; the existing canonical generator remains the sole
producer after the missing M2 phase input arrives.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import types


def helpers():
    path = Path(__file__).with_name("common.py")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != "025d801ffcb98697f7732632feb8b6a6c214fc551bbd2e5c382ce3eded11c2f5":
        raise RuntimeError("N10_COORDINATOR_COMMON_CHANGED")
    module = types.ModuleType("_n10_coordinator_common")
    module.__file__ = str(path)
    sys.modules[module.__name__] = module
    exec(compile(raw, str(path), "exec", dont_inherit=True), module.__dict__)
    return module


def process(request: dict, output_dir: Path) -> dict:
    c = helpers()
    c.require(request.get("schema") == "N10_M3_PREPARE_PIPELINE_REQUEST_V1", "N10_REQUEST_SCHEMA")
    c.require(set(request) == {"schema", "mode", "capture_id", "application_request", "source_contract_refs", "context", "module_bindings"}, "N10_REQUEST_FIELDS")
    c.require(request["mode"] == "PREPARE_APPLICATION_ONLY", "N10_NO_EXECUTION_OR_CAPTURE_ROUTE")
    out = c.no_alias(output_dir)
    c.require(out.is_relative_to(c.OUT) and out != c.OUT, "N10_OUTPUT_SCOPE")
    application_path = c.checked(request["application_request"])
    application_request = c.read(application_path)
    c.require(application_request["approved"] is False, "N10_APPLICATION_NOT_PERMISSION")
    c.require(application_request["execution_spec"]["window_parameters"]["CAPTURE_ID"] == request["capture_id"], "N10_CAPTURE_ID_MISMATCH")
    for descriptor in request["source_contract_refs"]:
        c.checked(descriptor)
    binding_path = c.checked(request["module_bindings"])
    c.require(binding_path == c.DOC / "MODULE_BINDINGS.json", "N10_ONLY_COORDINATOR_BINDING_FILE")
    bindings = c.read(binding_path)
    c.require(bindings["schema"] == "N10_M3_COORDINATOR_BINDINGS_V1", "N10_BINDING_SCHEMA")
    c.require(c.checked(bindings["application_adapter"]) == c.SW / "admission/adapter.py"
              and c.checked(bindings["handoff"]) == c.SW / "serial/handoff.py", "N10_ONLY_ASSIGNED_MODULES")
    adapter = c.load(bindings["application_adapter"], "_n10_restricted_application_adapter")
    handoff = c.load(bindings["handoff"], "_n10_handoff_assembler")
    out.mkdir(parents=True, exist_ok=False)
    c.save(out / "INPUT_REQUEST.json", request)
    report = {}
    try:
        report = adapter.build_application(application_request, out / "application")
        c.require(report["execution_allowed"] is False and report["real_pass"] is False, "N10_APPLICATION_FALSE_AUTHORITY")
        prepared = handoff.assemble({"schema": "N10_M3_HANDOFF_REQUEST_V1", "capture_id": request["capture_id"],
            "application_request": request["application_request"], "application_report": report,
            "source_contract_refs": request["source_contract_refs"], "context": request["context"]}, out / "handoff")
        for descriptor in request["source_contract_refs"]:
            c.checked(descriptor)
        c.checked(request["application_request"])
        c.checked(request["module_bindings"])
        result = {"schema": "N10_M3_PIPELINE_RESULT_V1", "status": "PREPARED_PENDING_FINISH_PHASE_AND_M2_ADMISSION",
                  "capture_id": request["capture_id"], "application_report": report,
                  "handoff_report": prepared, "source_contract_refs": request["source_contract_refs"],
                  "full_capture_chain": "EXISTING_CODE_REUSED; not invoked before phase and actual inputs",
                  "FRAME_PLAN": "NOT_GENERATED_PENDING_FINISH_PHASE", "HDL": "NOT_RUN",
                  "math_input_bundle": "NOT_RUN_NO_ACTUAL_CAPTURE", "execution_allowed": False,
                  "real_verified": False, "math_verified": False, "board_release_allowed": False}
        c.save(out / "PIPELINE_RESULT.json", result)
        return result
    except BaseException as error:
        c.save(out / "FIRST_FAILURE.json", {"reason": repr(error), "application_report": report,
                                           "real_verified": False, "board_release_allowed": False})
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    c = helpers()
    c.install_guard()
    result = process(c.read(args.request), args.output)
    print(json.dumps({"status": result["status"], "HDL": result["HDL"], "execution_allowed": False}))
    return 3  # Prepared application, never an execution/real verification PASS.


if __name__ == "__main__":
    raise SystemExit(main())
