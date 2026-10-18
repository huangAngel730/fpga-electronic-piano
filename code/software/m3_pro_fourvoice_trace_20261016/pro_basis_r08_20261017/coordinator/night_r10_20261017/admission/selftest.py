"""Three new R10 seams. Candidate loading happens only inside run_case."""
import hashlib
import json
from pathlib import Path
import types

ROOT = Path(__file__).resolve().parents[7]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/night_r10_20261017/admission"
R10_OUTPUT = ROOT / "code/output/m3_c9_chain_night_r10_20261017"


def write_json(path, value):
    path = Path(path)
    if path.exists():
        raise FileExistsError(path)
    path.write_bytes((json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8"))


def check(ok, reason):
    if not ok:
        raise ValueError(reason)


def load_adapter(binding):
    path = ROOT / binding["adapter"]["path"]
    raw = path.read_bytes()
    check(len(raw) == binding["adapter"]["bytes"] and hashlib.sha256(raw).hexdigest() == binding["adapter"]["sha256"], "ADAPTER_PIN")
    module = types.ModuleType("_r10_application_seam_" + binding["adapter"]["sha256"][:20])
    module.__file__, module.__package__ = str(path), ""
    exec(compile(raw, str(path), "exec", dont_inherit=True), module.__dict__)
    return module


def run_case(case_id, out):
    out = Path(out).resolve()
    out.mkdir(parents=True, exist_ok=False)
    binding = json.loads((DOC / "BINDING.json").read_bytes())
    definitions = json.loads((DOC / "CASES.json").read_bytes())["cases"]
    selected = next((item for item in definitions if item["id"] == case_id), None)
    check(selected is not None, "UNKNOWN_CASE")
    request_raw = (DOC / "APPLICATION_REQUEST.json").read_bytes()
    check(hashlib.sha256(request_raw).hexdigest() == binding["request"]["sha256"] and
          len(request_raw) == binding["request"]["bytes"], "REQUEST_PIN")
    request = json.loads(request_raw)
    targets = ([out / "a"] if case_id == "R10_APPLICATION_PREPARE" else
               [ROOT / "code/output/m3_c9_complete_d4_20261017" / ("R10_REJECT_" + out.name)]
               if case_id == "R10_REJECT_OLD_OUTPUT" else
               [R10_OUTPUT, ROOT / "code/output/R10_OTHER_ROOT_REJECTED"])
    write_json(out / "INPUT.json", {"case": selected, "request": request,
                                    "targets": [str(path) for path in targets],
                                    "origin": "ACTUAL_C9_SOURCE_AND_EXISTING_R62_PLAN_PROPOSAL",
                                    "HDL_executed": False, "execution_allowed": False})
    module = load_adapter(binding)
    actual = {"case_id": case_id, "execution_allowed": False, "real_pass": False}
    try:
        if case_id == "R10_APPLICATION_PREPARE":
            result = module.build_application(request, targets[0])
            application = json.loads((ROOT / result["artifacts"]["application"]["path"]).read_bytes())
            resolved = json.loads((ROOT / result["artifacts"]["resolved_plan"]["path"]).read_bytes())
            derivation = json.loads((ROOT / result["artifacts"]["output_scope_derivation"]["path"]).read_bytes())
            window_path = ROOT / request["window_reference"]["path"]
            window = json.loads(window_path.read_bytes())
            check(result["status"] == "PENDING_M2_EXECUTION_ADMISSION" and result["execution_allowed"] is False and
                  application["approved"] is False and application["authenticated"] is False, "NO_ADMISSION_GRANTED")
            check(Path(resolved["resolved_cwd"]).is_relative_to(targets[0]) and
                  Path(resolved["resolved_output"]).is_relative_to(targets[0]) and
                  str(resolved["resolved_output"]).endswith("C9_R10_PROPOSAL_20261018"), "R10_RESOLVED_OUTPUT")
            check(derivation["source"]["sha256"] == binding["legacy_assembler"]["sha256"] and
                  derivation["changed_globals"] == ["OUTPUT"] and derivation["source_bytes_changed"] is False,
                  "ONLY_OUTPUT_SCOPE_DERIVATION")
            check(window["status"] == "PROPOSED_NOT_M2_FROZEN" and window["M2_frozen"] is False and
                  window["FRAME_INPUT_generated"] is False and window["FRAME_PLAN_generated"] is False and
                  window["finish_phase_disagreement"]["possible_finish_core_cycles"] == [1130660, 1130661], "NO_FAKE_PHASE_FREEZE")
            old_request = json.loads((ROOT / binding["legacy_request"]["path"]).read_bytes())
            check(request["source"] == old_request["source"] and request["tools"] == old_request["tools"] and
                  request["external_inputs"] == old_request["external_inputs"] and
                  all(item["origin"] == "REAL_CANDIDATE" for item in request["tools"].values()), "ACTUAL_INPUTS_REUSED")
            check(request["execution_spec"]["window_parameters"] == window["window_parameters"] and
                  request["proposed_plan"]["window_reference"] == request["window_reference"] and
                  request["proposed_plan"]["execution"] == request["execution_spec"], "PROPOSAL_REQUEST_CONSISTENCY")
            actual.update(status="R10_PROPOSAL_PREPARED_PENDING", result=result)
        else:
            rejections = []
            for path in targets:
                existed = path.exists()
                try:
                    module.build_application(request, path)
                except ValueError as error:
                    check(str(error) == "R10_STRICT_OUTPUT_SCOPE", "BOUNDARY_REJECTION:" + str(error))
                    rejections.append(str(error))
                else:
                    raise ValueError("BOUNDARY_ACCEPTED")
                check(path.exists() == existed, "REJECT_CREATED_OUTPUT")
            actual.update(status=("OLD_OUTPUT_REJECTED" if case_id == "R10_REJECT_OLD_OUTPUT" else "ROOT_AND_OTHER_REJECTED"), rejections=rejections)
        write_json(out / "ACTUAL.json", actual)
        check(actual["status"] == selected["expected"], "CASE_EXPECTATION")
        result = {"case_id": case_id, "assertion": "MATCHED", "expected": selected["expected"],
                  "actual": actual, "candidate_application_only": True,
                  "execution_allowed": False, "HDL_executed": False, "real_pass": False}
        write_json(out / "RESULT.json", result)
        return result
    except Exception as error:
        write_json(out / "FAILURE.json", {"reason": str(error), "error": type(error).__name__, "partial_actual": actual})
        raise
