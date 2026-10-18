"""One R10 preparation/capture entry; file processing never grants execution.

The frozen D4 pipeline still owns all normalization, FRAME, serial and math
wrapping. This successor changes its application binding, not its algorithms.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
import types

ROOT = Path(__file__).resolve().parents[7]
REL = Path("m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator")
SW = ROOT / "code/software" / REL
DOC = ROOT / "code/docs/test" / REL
N10 = SW / "night_r10_20261017"
OUT = ROOT / "code/output/m3_c9_chain_night_r10_20261017"
BINDING = DOC / "night_r10_20261017/intake_20261018/CAPTURE_MODULE_BINDINGS.json"
BINDING_SHA = "dc66002f2a14017ae7abb439ea683b9b2dc1dfca18a35c6b07b43e6a37d661f8"
COMMON_SHA = "025d801ffcb98697f7732632feb8b6a6c214fc551bbd2e5c382ce3eded11c2f5"
PREPARATION_SHA = "7c975cff2d19b98c2569c56bbb7a4f6f5f4ffeb6a93c59643253e074e5b4127e"
CAPTURE_SHA = "64bfdf4787aa9dd1ddab30a30ed7cf4fb05be763b9303ec965061005430f1c44"


def load(path, digest, name):
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != digest:
        raise ValueError("CAPTURE_LINK_PIN_CHANGED:" + str(path))
    module = types.ModuleType(name)
    module.__file__ = str(path)
    sys.modules[name] = module
    exec(compile(raw, str(path), "exec", dont_inherit=True, optimize=0), module.__dict__)
    return module


def helpers():
    return load(N10 / "common.py", COMMON_SHA, "_capture_link_common")


def preparation_module():
    return load(N10 / "chain.py", PREPARATION_SHA, "_capture_link_preparation")


def capture_module():
    return load(SW / "task_day4_completion_20261017/chain.py", CAPTURE_SHA,
                "_capture_link_reused_d4")


def capture_preflight(request, c):
    c.require(request.get("schema") == "M3_C9_CHAIN_REQUEST_V1"
              and request.get("mode") == "PROCESS_CAPTURE", "CAPTURE_LINK_CAPTURE_SCHEMA")
    c.require(request.get("synthetic_application_example") is not True,
              "CAPTURE_LINK_NO_WINDOW_EXEMPTION")
    c.require(request.get("origin") in ("SYNTHETIC_SCHEMA_FIXTURE", "HDL_PUBLIC_CAPTURE_UNVERIFIED"),
              "CAPTURE_LINK_ORIGIN")
    binding = c.checked(request["module_bindings"])
    c.require(binding == BINDING and hashlib.sha256(binding.read_bytes()).hexdigest() == BINDING_SHA,
              "CAPTURE_LINK_BINDING")
    bindings = c.read(binding)
    c.require(bindings["schema"] == "M3_C9_CHAIN_MODULE_BINDINGS_V1", "CAPTURE_LINK_BINDING_SCHEMA")
    for descriptor in bindings["modules"].values():
        c.checked(descriptor)
    inputs = request["inputs"]
    required = ("application_request", "frame_input", "frame_rules", "raw", "resets", "end",
                "stdout", "window_plan", "midi_plan")
    c.require(all(name in inputs for name in required), "CAPTURE_LINK_MISSING_INPUT")
    paths = {name: c.checked(inputs[name]) for name in required}
    window, end = c.read(paths["window_plan"]), c.read(paths["end"])
    frame, application = c.read(paths["frame_input"]), c.read(paths["application_request"])
    c.require(frame.get("status") == "FROZEN_INDEPENDENT_INPUT"
              and frame.get("independent_of_observed_trace") is True,
              "CAPTURE_LINK_PHASE_NOT_FROZEN")
    finish = window.get("finish_cycle")
    c.require(type(finish) is int and finish >= 0, "CAPTURE_LINK_FINISH_PENDING")
    c.require(all(type(window.get(key)) is int and window[key] > 0
                  for key in ("row_count", "finish_time_ps", "first_core_ps", "core_period_ps")),
              "CAPTURE_LINK_TIMEBASE_PENDING")
    c.require(window["row_count"] == finish + 1
              and window["finish_time_ps"] == window["first_core_ps"] + finish * window["core_period_ps"],
              "CAPTURE_LINK_WINDOW_COORDINATES")
    c.require(frame.get("finish", {}).get("cycle") == finish, "CAPTURE_LINK_FRAME_FINISH")
    c.require(window.get("schema") == "M3_R7D_INDEPENDENT_WINDOW_V1"
              and window.get("capture_id") == end.get("capture_id") == request.get("capture_id")
              and end.get("reason") == "PLANNED_WINDOW_END", "CAPTURE_LINK_WINDOW_IDENTITY")
    c.require((end.get("finish_cycle"), end.get("time_ps"), end.get("row_count")) ==
              (finish, window["finish_time_ps"], window["row_count"]), "CAPTURE_LINK_END_WINDOW")
    c.require(window.get("input_plan_sha256") == inputs["midi_plan"]["sha256"],
              "CAPTURE_LINK_PLAN_IDENTITY")
    parameters = application["execution_spec"]["window_parameters"]
    c.require(application.get("approved") is False
              and parameters["CAPTURE_ID"] == request["capture_id"]
              and parameters["PLAN_STOP_ID"] == window.get("plan_stop_id")
              and parameters["EXPECTED_FINISH_CORE_CYCLE"] == finish,
              "CAPTURE_LINK_APPLICATION_WINDOW")
    c.require(bool(request.get("source_contract_refs")), "CAPTURE_LINK_SOURCE_REFS")
    for descriptor in request["source_contract_refs"]:
        c.checked(descriptor)
    return bindings


def process(envelope, output_dir):
    c = helpers()
    c.require(isinstance(envelope, dict) and set(envelope) == {"schema", "mode", "request"}
              and envelope["schema"] == "N10_M3_UNIFIED_PIPELINE_REQUEST_V1", "CAPTURE_LINK_ENVELOPE")
    out = c.no_alias(output_dir)
    c.require(out.is_relative_to(OUT) and out != OUT, "CAPTURE_LINK_STRICT_OUTPUT_SCOPE")
    c.require(not out.exists(), "CAPTURE_LINK_OUTPUT_EXISTS")
    request_path = c.checked(envelope["request"])
    request = c.read(request_path)
    mode = envelope["mode"]
    if mode == "PREPARE_APPLICATION_ONLY":
        c.require(request.get("schema") == "N10_M3_PREPARE_PIPELINE_REQUEST_V1"
                  and request.get("mode") == mode, "CAPTURE_LINK_PREPARATION_SCHEMA")
        result = preparation_module().process(request, out)
    elif mode == "PROCESS_CAPTURE":
        capture_preflight(request, c)
        result = capture_module().process(request, out)
    else:
        raise ValueError("CAPTURE_LINK_MODE")
    c.checked(envelope["request"])
    if mode == "PROCESS_CAPTURE":
        capture_preflight(request, c)
    c.require(result.get("execution_allowed") is False and result.get("real_verified") is False
              and result.get("math_verified") is False and result.get("board_release_allowed") is False,
              "CAPTURE_LINK_FALSE_AUTHORITY")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if not sys.dont_write_bytecode or sys.flags.optimize:
        raise ValueError("CAPTURE_LINK_REQUIRES_PYTHON_B_ASSERTIONS_ON")
    c = helpers()
    c.install_guard()
    result = process(c.read(args.request), args.output)
    print(json.dumps({"status": result["status"], "execution_allowed": False,
                      "real_verified": False, "math_verified": False}))
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
