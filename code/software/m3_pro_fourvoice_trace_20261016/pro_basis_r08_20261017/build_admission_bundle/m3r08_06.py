"""Assemble an application and source body. Never approves or executes it."""
import importlib.util
from pathlib import Path
import re
import sys
import zipfile

_p = Path(__file__).resolve().parents[1] / "plan_consumption_guard/m3r08_common.py"
if "_m3r08_common" not in sys.modules:
    _s = importlib.util.spec_from_file_location("_m3r08_common", _p)
    _m = importlib.util.module_from_spec(_s)
    sys.modules[_s.name] = _m
    _s.loader.exec_module(_m)
c = sys.modules["_m3r08_common"]
WINDOW = ("CAPTURE_ID", "PLAN_STOP_ID", "STOP_DRIVER_CYCLE", "EXPECTED_FINISH_CORE_CYCLE", "MAX_CORE_SAMPLES", "MAX_SIM_TIME_PS")


def evaluate(request):
    c.need(request.get("schema") == "M3_R08_ADMISSION_APPLICATION_REQUEST_V1", "ADMISSION_SCHEMA")
    c.need(request.get("approved") is False and request.get("authenticated") is False, "SELF_APPROVAL_FORBIDDEN")
    c.need(request["origin"] in ("SYNTHETIC", "REAL_CANDIDATE"), "ADMISSION_ORIGIN")
    c.need(not any(re.search(r"P7|BYPASS|ALLOW_|OWNED_EXECUTOR", key, re.I) for key in request["environment"]), "LEGACY_EXECUTION_SWITCH")
    output = Path(request["bundle_output"])
    c.no_alias(output)
    output = output.resolve()
    c.need(output.is_relative_to(c.DOC / "build_admission_bundle") or
           output.is_relative_to(c.DOC / "coordinator"), "APPLICATION_OUTPUT_SCOPE")
    for key in ("future_cwd", "future_output", "future_marker"):
        c.relative(request[key])
    pending = []
    audit01 = c.load_component("recursive_include_audit", "m3r08_01")
    base_request = request["dependency_requests"]["01"]
    base_result = audit01.evaluate(base_request)
    payload, base_id = c.archive(base_request["archive"])
    if request["origin"] == "REAL_CANDIDATE":
        c.need(base_id["sha256"] == c.C6_SHA, "OFFICIAL_C6_IDENTITY_REQUIRED")
    base_graph = base_result["graph"]
    units = list(base_graph["units"])
    roles, added = set(), []
    for source in request["append_sources"]:
        c.need(source["role"] in ("TB", "OBSERVER", "DRIVER") and source["role"] not in roles, "SOURCE_ROLE_DUPLICATE")
        path, ident = c.checked_file(source["file"])
        name = "r08_added/" + c.relative(path.name)
        c.need(name not in payload, "APPEND_SOURCE_COLLISION")
        payload[name] = path.read_bytes()
        roles.add(source["role"])
        units.append(name)
        added.append({"role": source["role"], "member": name, "original": ident})
    c.need(roles == {"TB", "OBSERVER", "DRIVER"}, "REQUIRED_TB_OBSERVER_DRIVER")
    port_request = request["dependency_requests"].get("02")
    if port_request is not None:
        top_sha = next(item["original"]["sha256"] for item in added if item["role"] == "TB")
        c.need(port_request["top_file"]["sha256"] == top_sha, "PORT_MAP_TB_SOURCE_MISMATCH")
        compiled_sha = {c.digest(payload[name]) for name in units}
        c.need(all(item["sha256"] in compiled_sha for item in port_request["module_files"]), "PORT_MAP_MODULE_SOURCE_MISMATCH")
    for alias in request["rom_aliases"]:
        name, source = c.relative(alias["path"]), c.relative(alias["source"])
        c.need(name not in payload and source in payload and source.startswith("rom/"), "ROM_ALIAS_SOURCE")
        payload[name] = payload[source]
    payload["compile_request.f"] = ("".join("+incdir+" + d + "\n" for d in base_graph["incdirs"]) +
                                     "\n".join(units) + "\n").encode("utf-8")
    combined = audit01.inspect(payload, "compile_request.f")
    c.need(request["top"] in combined["module_to_source"], "TOP_NOT_IN_SOURCE_GRAPH")
    if combined["unknown"]:
        pending.append("PARAMETER_RUNTIME_READMEM_NOT_ELABORATED")
    if request["origin"] == "REAL_CANDIDATE":
        c.need(len(base_graph["units"]) == 71 and len(combined["units"]) == 74 and
               len(base_graph["ROM_payloads"]) == 9 and len(base_graph["include_edges"]) == 3, "C6_CLOSURE_COUNTS")
    clock = request["clock_model"]
    clock_member = c.relative(clock["member"])
    c.need(clock_member in units and c.digest(payload[clock_member]) == clock["sha256"], "CLOCK_MODEL_SOURCE_BINDING")
    c.need(clock["kind"] == "SIMULATION_ONLY" or
           (request["origin"] == "SYNTHETIC" and clock["kind"] == "SYNTHETIC_NONEXECUTED_FIXTURE"), "CLOCK_MODEL_CLASS")
    stimulus = []
    for entry in request.get("stimulus_inputs", []):
        stimulus_path, stimulus_identity = c.checked_file(entry)
        member = c.relative(stimulus_path.name)
        c.need(member not in payload, "STIMULUS_MEMBER_COLLISION")
        payload[member] = stimulus_path.read_bytes()
        stimulus.append({"original": stimulus_identity, "member": "inputs/" + member})
    driver_parameters = request.get("driver_parameter_paths", {})
    if request["origin"] == "REAL_CANDIDATE":
        c.need(driver_parameters == {"BYTE_PLAN": "bytes.drv", "RESET_PLAN": "reset.drv", "READY_PLAN": "ready.drv"}, "DRIVER_PARAMETER_BINDING")
        c.need(all(name in payload for name in driver_parameters.values()), "DRIVER_INPUT_BODY_MISSING")
    if request["origin"] == "REAL_CANDIDATE" and len(stimulus) != 4:
        pending.append("FOUR_FROZEN_DRIVER_INPUTS_REQUIRED")
    dependency_results = {"01": base_result}
    for number, directory, module_name in (("02", "public_port_map", "m3r08_02"),
                                           ("03", "plan_consumption_guard", "m3r08_03"),
                                           ("05", "tool_dependency_identity", "m3r08_05")):
        item = request["dependency_requests"].get(number)
        if item is None:
            pending.append("MISSING_DEPENDENCY_REQUEST:" + number)
            continue
        dependency_results[number] = c.load_component(directory, module_name).evaluate(item)
        if dependency_results[number]["status"].startswith("PENDING"):
            pending.append("DEPENDENCY_UNKNOWN:" + number)
    reservation = request.get("reservation_receipt")
    if reservation is None:
        pending.append("OUTPUT_RESERVATION_NOT_BOUND")
    else:
        path, reservation_id = c.checked_file(reservation)
        record = c.parse(path.read_bytes())
        c.need(record.get("schema") == "M3_R08_OUTPUT_RESERVATION_V1" and record.get("state") == "RESERVED" and
               record.get("execution_allowed") is False, "RESERVATION_RECEIPT_BINDING")
        claim_path, claim_id = c.checked_file(record["claim"])
        claim = c.parse(claim_path.read_bytes())
        c.need(not claim_path.with_suffix(".terminal.json").exists(), "RESERVATION_ALREADY_CONSUMED")
        c.need("03" in dependency_results and claim["plan_sha256"] == dependency_results["03"]["audit"]["plan"]["sha256"] and
               claim["output"] == str((c.ROOT / request["future_output"]).resolve()) and
               claim["nonce"] == request["reservation_nonce"] and
               claim["capture_id"] == request["window_parameters"]["CAPTURE_ID"], "RESERVATION_APPLICATION_MISMATCH")
        dependency_results["04"] = {"receipt": reservation_id, "original_record": record}
    windows = request["window_parameters"]
    c.need(set(windows) == set(WINDOW), "WINDOW_PARAMETER_FIELDS")
    for key in WINDOW:
        if windows[key] is None:
            pending.append("WINDOW_NOT_FROZEN:" + key)
        elif key in ("CAPTURE_ID", "PLAN_STOP_ID"):
            c.need(type(windows[key]) is str and re.fullmatch(r"[A-Za-z0-9_-]+", windows[key]), "WINDOW_TOKEN")
        else:
            c.need(type(windows[key]) is int and windows[key] >= 0, "WINDOW_NUMERIC")
    if all(windows[k] is not None for k in WINDOW[2:]):
        c.need(windows["STOP_DRIVER_CYCLE"] > 0 and windows["MAX_SIM_TIME_PS"] > 0 and
               windows["MAX_CORE_SAMPLES"] > windows["EXPECTED_FINISH_CORE_CYCLE"], "WINDOW_BOUNDS")
    if request["timeout_seconds"] is None:
        pending.append("EXECUTION_TIMEOUT_NOT_FROZEN")
    else:
        c.need(type(request["timeout_seconds"]) in (int, float) and 0 < request["timeout_seconds"] <= 300,
               "APPLICATION_TIMEOUT_RANGE")
    if not request["argv"]:
        pending.append("EXACT_TOOL_ARGV_NOT_FROZEN")
    if request["origin"] == "REAL_CANDIDATE":
        pending.extend(["M2_TRUSTED_FIRST_EXECUTION_ADMISSION_REQUIRED", "FIXED_PYTHON_GUARD_DOES_NOT_ADMIT_HDL_TOOLS"])
    application = {"schema": "M3_R08_FIRST_EXECUTION_APPLICATION_V1", "origin": request["origin"],
                   "approved": False, "authenticated": False, "execution_allowed": False,
                   "source_base": base_id, "append_sources": added, "compile_list": "inputs/compile_request.f",
                   "top": request["top"], "clock_model": request["clock_model"],
                   "stimulus_inputs": stimulus,
                   "driver_parameter_paths": driver_parameters,
                   "window_parameters": windows, "argv_as_requested": request["argv"],
                   "cwd_as_requested": request["future_cwd"], "output_as_requested": request["future_output"],
                   "marker_as_requested": request["future_marker"], "timeout_seconds": request["timeout_seconds"],
                   "expected_assertions": request["expected_assertions"], "pending": pending,
                   "dependency_requests": request["dependency_requests"], "dependency_results": dependency_results,
                   "known_tool_requests": request.get("known_tool_requests", {}),
                   "source_graph": combined, "board_release_allowed": False}
    application_sha = c.digest(c.canonical(application).encode("utf-8"))
    output.mkdir(parents=True, exist_ok=False)
    archive_path = output / "SOURCE_APPLICATION.zip"
    with zipfile.ZipFile(archive_path, "x", compression=zipfile.ZIP_DEFLATED) as zipped:
        for name, raw in sorted(payload.items()):
            zipped.writestr("inputs/" + c.relative(name), raw)
        zipped.writestr("APPLICATION.json", c.canonical(application) + "\n")
    c.write_json(output / "APPLICATION.json", application)
    c.write_json(output / "APPLICATION_IDENTITY.json", {"canonical_application_sha256": application_sha,
                                                       "source_archive": c.identity(archive_path)})
    return c.result("M3_R08_BUILD_ADMISSION_BUNDLE_V1", "PENDING_UNKNOWN" if pending else "ACCEPT",
                    application=application, application_sha256=application_sha, source_archive=c.identity(archive_path),
                    artifacts={"admission_missing_items.json": {"pending": pending, "M2_admission": "NOT_GRANTED"}})


if __name__ == "__main__":
    raise SystemExit(c.cli(evaluate))
