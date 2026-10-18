"""Thirteen assembler cases; imports/runs no candidate until run_case."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import types
import zipfile

ROOT = Path(__file__).resolve().parents[6]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/build_admission_bundle/c9_completion_r01"
COMMON = ROOT / "code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/task_day4_completion_20261017/common.py"
COMMON_SHA = "55cb7481fe9c0870247a7d8b2453dea859f0f2e81879795cc0e34ffe8c996dca"


def helper():
    raw = COMMON.read_bytes()
    if hashlib.sha256(raw).hexdigest() != COMMON_SHA:
        raise ValueError("COMMON_SOURCE_PIN_CHANGED")
    name = "_d4_application_test_common_" + COMMON_SHA[:16]
    if name not in sys.modules:
        module = types.ModuleType(name)
        module.__file__ = str(COMMON)
        sys.modules[name] = module
        exec(compile(raw, str(COMMON), "exec", dont_inherit=True), module.__dict__)
    return sys.modules[name]


def refresh_plan(request):
    return {"schema": "M3_C9_BOUND_APPLICATION_PLAN_V1", "source": copy.deepcopy(request["source"]),
            "tools": copy.deepcopy(request["tools"]), "external_inputs": copy.deepcopy(request["external_inputs"]),
            "window_reference": copy.deepcopy(request["window_reference"]),
            "execution": copy.deepcopy(request["execution_spec"]), "permission": "NOT_GRANTED", "process_route": "ABSENT"}


def archive_fixture(source, destination, missing_header=False, missing_unit=False, device=False, incdir=False, provenance=False):
    with zipfile.ZipFile(source) as original, zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as fixture:
        for entry in original.infolist():
            if entry.is_dir() or (missing_header and entry.filename == "inputs/include/sine_table.svh"):
                continue
            raw = original.read(entry)
            if provenance and entry.filename == "provenance/ORIGINAL_dds_oscillator.sv":
                raw += b"\n// SYNTHETIC PROVENANCE TAMPER; NOT COMPILED\n"
            if incdir and entry.filename == "inputs/compile_c9_capture.f":
                raw = b"+incdir+unapproved\n" + raw
            if missing_unit and entry.filename == "inputs/compile_c9_capture.f":
                old = b"m3_c9/tb_r7a_c9_public_capture.sv"
                if old not in raw:
                    raise ValueError("FIXTURE_COMPILE_UNIT_ABSENT")
                raw = b"\n".join(line for line in raw.splitlines() if line.strip() != old) + b"\n"
            fixture.writestr(entry.filename, raw)
        if device:
            fixture.writestr("inputs/NUL", b"SYNTHETIC DEVICE-PATH REJECTION INPUT; NEVER MATERIALIZE\n")


def run_case(case_id, output_dir):
    h = helper()
    out = h.output_directory(output_dir)
    request = h.read_json(DOC / "APPLICATION_REQUEST.json")
    expected = "PENDING_M2_EXECUTION_ADMISSION"
    if case_id in ("D4_A_MISSING_HEADER", "D4_A_MISSING_75", "D4_A_ZIP_DEVICE", "D4_A_INCDIR_TAMPER", "D4_A_PROVENANCE_TAMPER"):
        source = h.checked_descriptor(request["source"]["application"])
        fixture = out / "INPUT_SOURCE.zip"
        archive_fixture(source, fixture, missing_header=case_id == "D4_A_MISSING_HEADER",
                        missing_unit=case_id == "D4_A_MISSING_75", device=case_id == "D4_A_ZIP_DEVICE",
                        incdir=case_id == "D4_A_INCDIR_TAMPER", provenance=case_id == "D4_A_PROVENANCE_TAMPER")
        request["source"]["application"] = h.artifact(fixture)
        request["proposed_plan"] = refresh_plan(request)
        expected = {"D4_A_MISSING_HEADER": "HEADER_MISSING:sine_table.svh", "D4_A_MISSING_75": "C9_SOURCE_COUNT_72_PLUS_3",
                    "D4_A_ZIP_DEVICE": "DEVICE_NAME", "D4_A_INCDIR_TAMPER": "C9_EXACT_COMPILE_ORDER_AND_INCDIRS",
                    "D4_A_PROVENANCE_TAMPER": "C9_DECISION_PAYLOAD_CHANGED:provenance/ORIGINAL_dds_oscillator.sv"}[case_id]
    elif case_id == "D4_A_WRONG_BASE":
        path = ROOT / "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/r06_public_chain_20261017/SOURCE_CLOSURE_R06C6.zip"
        request["source"]["base"] = h.artifact(path)
        request["proposed_plan"] = refresh_plan(request)
        expected = "C9_BASE_IDENTITY_REQUIRED"
    elif case_id == "D4_A_PLAN_TAMPER":
        request["proposed_plan"]["execution"]["steps"][1]["argv"].append("UNDECLARED_ARGUMENT")
        expected = "PLAN_FIELD_MISMATCH:execution"
    elif case_id == "D4_A_WINDOW_TAMPER":
        request["execution_spec"]["window_parameters"]["STOP_DRIVER_CYCLE"] += 1
        request["proposed_plan"] = refresh_plan(request)
        expected = "WINDOW_REFERENCE_MISMATCH"
    elif case_id == "D4_A_SELF_APPROVAL":
        request["approved"] = True
        expected = "SELF_APPROVAL_FORBIDDEN"
    elif case_id == "D4_A_UNKNOWN_OUTPUT":
        request["execution_spec"]["output"] = "UNCONTROLLED_OUTPUT"
        request["proposed_plan"] = refresh_plan(request)
        expected = "EXECUTION_SPEC_FIELDS"
    elif case_id == "D4_A_ARGV_DUPLICATE":
        request["execution_spec"]["steps"][2]["argv"].insert(2, "-gMAX_CORE_SAMPLES=1")
        request["proposed_plan"] = refresh_plan(request)
        expected = "EXACT_TOOL_ARGV_TEMPLATE:vsim"
    elif case_id == "D4_A_EXTERNAL_TAMPER":
        request["external_inputs"] = copy.deepcopy(request["window_reference"])
        request["proposed_plan"] = refresh_plan(request)
        expected = "EXTERNAL_INPUT_MANIFEST_REQUIRED"
    elif case_id != "D4_A_ACTUAL_C9":
        raise ValueError("UNKNOWN_CASE")
    h.write_json(out / "INPUT.json", {"case_id": case_id, "expected": expected, "request": request})
    binding = h.read_json(DOC / "IMPLEMENTATION_BINDING.json")
    path = h.checked_descriptor(binding["assembler"])
    module = h.load_source(path, binding["assembler"]["sha256"])
    try:
        result = module.build_application(request, out / "a")
    except Exception as error:
        actual = {"status": "REJECT", "reason": str(error), "error": type(error).__name__}
        h.write_json(out / "ACTUAL.json", actual)
        h.require(expected == str(error), "CASE_REJECTION_MISMATCH:" + str(error))
        return {"case_id": case_id, "assertion": "MATCHED", "expected": expected, "actual": actual,
                "execution_allowed": False, "real_pass": False}
    h.write_json(out / "ACTUAL.json", result)
    h.require(expected == result["status"] and result["execution_allowed"] is False, "CASE_STATUS")
    application = h.read_json(h.checked_descriptor(result["artifacts"]["application"]))
    h.require(application["source_counts"] == {"base_units": 72, "with_capture_units": 75, "ROMs": 9, "headers": 2, "aliases": 2}, "C9_COUNTS")
    h.require(application["source_envelope"] == {"decision_payloads_verified": 86, "input_payloads": 84,
              "base_archive_members": 87, "application_archive_members": 97,
              "provenance_members": ["provenance/ORIGINAL_COMPILE.f", "provenance/ORIGINAL_dds_oscillator.sv"],
              "wrapper_manifest_byte_identical": True}, "C9_SOURCE_ENVELOPE")
    h.require(application["guard"]["permission"] == "NOT_GRANTED" and not application["guard"]["old_Python_worker_audit_invoked"], "NO_EXECUTION_ROUTE")
    claim = h.read_json(h.checked_descriptor(result["artifacts"]["claim"]))
    h.require(claim["plan_sha256"] == result["plan_sha256"] and claim["nonce"] == request["execution_spec"]["nonce"], "RESERVATION_PLAN_NONCE")
    tools = h.read_json(h.checked_descriptor(result["artifacts"]["tools"]))
    h.require(all(item["report"]["executables_started"] == item["report"]["DLLs_loaded"] == 0 for item in tools.values()), "NO_NATIVE_ACTION")
    return {"case_id": case_id, "assertion": "MATCHED", "expected": expected, "actual_status": result["status"],
            "artifacts": result["artifacts"], "execution_allowed": False, "real_pass": False}
