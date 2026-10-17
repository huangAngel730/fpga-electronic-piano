"""Unrun C9 binding counterexamples; candidate imports are deferred to run_case."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/public_port_map/c9_binding"


def run_case(case_id, output_dir):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=False)
    request = copy.deepcopy(json.loads((DOC / "ACTUAL_C9_REQUEST.json").read_text(encoding="utf-8")))
    expected = None
    if case_id == "C9_OPEN_DUT_KIND":
        source = Path(request["capture_request"]["top_file"]["path"]).read_text(encoding="utf-8")
        source = source.replace(".obs_apply_kind(obs_apply_kind)", ".obs_apply_kind()", 1)
        expected = "C9_OBSERVATION_NOT_DIRECTLY_CAPTURED:obs_apply_kind"
        target = "top_file"
    elif case_id == "C9_READY_DRIVER_REVERSED":
        source = Path(request["capture_request"]["top_file"]["path"]).read_text(encoding="utf-8")
        source = source.replace(".event_ready(driver_ready_not_connected)", ".event_ready(obs_event_ready)")
        expected = "MULTIPLE_PUBLIC_DRIVERS:obs_event_ready"
        target = "top_file"
    elif case_id == "C9_PASSIVE_SIGNED_LOST":
        source = Path(request["capture_request"]["module_files"][2]["path"]).read_text(encoding="utf-8")
        source = source.replace("input wire signed [23:0] obs_effect_input_left", "input wire [23:0] obs_effect_input_left")
        expected = "C9_EXPORT_WIDTH_DIRECTION_OR_SIGNED:obs_effect_input_left"
        target = "observer"
    elif case_id != "C9_ACTUAL_DIRECT_BINDING":
        raise ValueError("UNKNOWN_CASE")
    if expected is not None:
        path = out / "mutated_source.sv"
        path.write_text(source, encoding="utf-8", newline="\n")
        raw = path.read_bytes()
        ident = {"path": str(path), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
        if target == "top_file":
            request["capture_request"]["top_file"] = ident
        else:
            request["capture_request"]["module_files"][2] = ident
    (out / "INPUT.json").write_text(json.dumps(request, indent=2), encoding="utf-8", newline="\n")
    spec = importlib.util.spec_from_file_location("c9_ports_under_test", Path(__file__).with_name("c9_ports.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        actual = module.evaluate(request)
    except Exception as error:
        (out / "ACTUAL.json").write_text(json.dumps({"error": type(error).__name__, "reason": str(error)}), encoding="utf-8")
        if expected is None or str(error) != expected:
            raise
        return {"case": case_id, "expected_rejection_matched": expected, "real_pass": False}
    (out / "ACTUAL.json").write_text(json.dumps(actual, indent=2), encoding="utf-8")
    assert expected is None and len(actual["comparisons"]) == 67 and actual["compile_proven"] is False
    return {"case": case_id, "static_bindings_matched": 67, "real_pass": False}
