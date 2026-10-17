"""C9 application assembly only. No process, tool, DLL or device route."""
import argparse
import ast
import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import sys
import types
import zipfile

ROOT = Path(__file__).resolve().parents[6]
SOFT = ROOT / "code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017"
OUTPUT = ROOT / "code/output/m3_c9_complete_d4_20261017"
COMMON = SOFT / "coordinator/task_day4_completion_20261017/common.py"
COMMON_SHA = "55cb7481fe9c0870247a7d8b2453dea859f0f2e81879795cc0e34ffe8c996dca"
PINS = {
    "common": ("plan_consumption_guard/m3r08_common.py", "2cad307f975178cc00994949817b3b1da952628f2b509932bf13112cf6981c33"),
    "01": ("recursive_include_audit/m3r08_01.py", "921b563cbed11d460ad430f63ada777c411139ade7c60137c8b8be5640621de8"),
    "03": ("plan_consumption_guard/m3r08_03.py", "cfebf362c50187448ec3a7ed868872602e4cae8e5d3ae75b39133d51fee7f213"),
    "04": ("output_reservation/m3r08_04.py", "54d91f493755fae333013a1ea0d024da466a9c677d99d6681b756fa2168b61c0"),
    "05": ("tool_dependency_identity/m3r08_05.py", "d70c34966a87b018d9d07335ca08af20866da24bfce88c5fc8378f00b3f00c4a"),
}
CONSUMER = ROOT / "code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r06_20261017/tool_plan_adapter/r07_fix/consumer.py"
CONSUMER_SHA = "56ba0c5615cbe98094e5d37dc72e9e92002ce4976169723b2fd6f5ba8217bb69"
C9_SHA = "d458ab16277bd46751318ac368b22df1b21b35c4867c47942e7bff7d27fc3aa2"
DECISION_SHA = "2766cf25223072c244d03da36e656f1b0946363e2d3cfa8c983d74fe9c3cd8a2"
EXTERNAL_MANIFEST = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/tool_dependency_identity/EXTERNAL_INPUTS.json"
EXTERNAL_MANIFEST_SHA = "2948315ef48ae229baf9d926676445ebde0bcc8c39fc0ed5a7fe5b89c5df2e0c"
WINDOWS = {"CAPTURE_ID", "PLAN_STOP_ID", "STOP_DRIVER_CYCLE", "EXPECTED_FINISH_CORE_CYCLE", "MAX_CORE_SAMPLES", "MAX_SIM_TIME_PS"}
WINDOW_ORDER = ("CAPTURE_ID", "PLAN_STOP_ID", "STOP_DRIVER_CYCLE", "EXPECTED_FINISH_CORE_CYCLE", "MAX_CORE_SAMPLES", "MAX_SIM_TIME_PS")
TOP = "tb_r7a_c9_public_capture"


def helpers():
    raw = COMMON.read_bytes()
    if hashlib.sha256(raw).hexdigest() != COMMON_SHA:
        raise ValueError("COMMON_SOURCE_PIN_CHANGED")
    name = "_d4_application_common_" + COMMON_SHA[:16]
    if name not in sys.modules:
        module = types.ModuleType(name)
        module.__file__ = str(COMMON)
        sys.modules[name] = module
        exec(compile(raw, str(COMMON), "exec", dont_inherit=True), module.__dict__)
    return sys.modules[name]


def pure_part(key, names, c):
    """Untouched pinned function nodes; omit old import-loader/main blocks."""
    h = helpers()
    name, sha = PINS[key]
    path = SOFT / name
    raw = path.read_bytes()
    h.require(hashlib.sha256(raw).hexdigest() == sha, "REUSED_SOURCE_CHANGED:" + key)
    tree, nodes, found = ast.parse(raw.decode("utf-8")), [], set()
    allowed = {"ast", "hashlib", "json", "os", "pathlib", "re", "struct", "sys", "types"}
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            modules = [alias.name.split(".")[0] for alias in node.names] if isinstance(node, ast.Import) else [node.module]
            if all(item in allowed for item in modules):
                nodes.append(node)
        elif isinstance(node, (ast.FunctionDef, ast.ClassDef)) and node.name in names:
            nodes.append(node)
            found.add(node.name)
    h.require(found == set(names), "PURE_NODE_SET:" + key)
    derived = ast.Module(body=nodes, type_ignores=[])
    module = types.ModuleType("_c9_application_reuse_" + key)
    module.__file__, module.c = str(path), c
    exec(compile(ast.fix_missing_locations(derived), str(path), "exec", dont_inherit=True), module.__dict__)
    module.derivation = {"source": h.artifact(path), "unchanged_definitions": sorted(found),
                         "AST_sha256": hashlib.sha256(ast.dump(derived, include_attributes=False).encode("utf-8")).hexdigest()}
    return module


def make_plan(request):
    """No I/O. All proposed execution fields reconstructed from original spec."""
    return {"schema": "M3_C9_BOUND_APPLICATION_PLAN_V1", "source": copy.deepcopy(request["source"]),
            "tools": copy.deepcopy(request["tools"]), "external_inputs": copy.deepcopy(request["external_inputs"]),
            "window_reference": copy.deepcopy(request["window_reference"]),
            "execution": copy.deepcopy(request["execution_spec"]), "permission": "NOT_GRANTED", "process_route": "ABSENT"}


def read_archive(descriptor):
    h = helpers()
    path = h.checked_descriptor(descriptor)
    payload, members, folded, total = {}, {}, set(), 0
    with zipfile.ZipFile(path) as archive:
        for entry in archive.infolist():
            if entry.is_dir():
                continue
            name = entry.filename
            p = PurePosixPath(name)
            h.require(not p.is_absolute() and ".." not in p.parts and "\\" not in name and ":" not in name,
                      "ZIP_PATH_ESCAPE")
            h.require(p.as_posix() == name and all(part.rstrip(" .") == part for part in p.parts), "ZIP_NONCANONICAL_WINDOWS_PATH")
            h.require(name.casefold() not in folded and (entry.external_attr >> 16) & 0o170000 != 0o120000,
                      "ZIP_DUPLICATE_OR_ALIAS")
            folded.add(name.casefold())
            total += entry.file_size
            h.require(entry.file_size <= 16 * 1024 * 1024 and total <= 64 * 1024 * 1024, "SOURCE_ARCHIVE_BOUND")
            raw = archive.read(entry)
            members[name] = raw
            if name.startswith("inputs/"):
                payload[name[7:]] = raw
    return payload, h.artifact(path), members


def build_application(request, output_dir):
    h = helpers()
    out = h.no_alias(output_dir)
    h.require(out.is_relative_to(OUTPUT), "APPLICATION_OUTPUT_SCOPE")
    out.mkdir(parents=True, exist_ok=False)
    h.write_json(out / "INPUT.json", request)
    reservation_module, reservation_request, reservation = None, None, None
    try:
        h.require(type(request) is dict and set(request) == {"schema", "source", "tools", "external_inputs",
                  "window_reference", "execution_spec", "proposed_plan", "approved"}, "APPLICATION_REQUEST_FIELDS")
        h.require(request["schema"] == "M3_C9_EXECUTION_APPLICATION_REQUEST_V1", "APPLICATION_SCHEMA")
        h.require(request["approved"] is False, "SELF_APPROVAL_FORBIDDEN")
        old = h.load_source(SOFT / PINS["common"][0], PINS["common"][1])
        include = pure_part("01", {"stripped", "inspect"}, old)
        guard_loader = pure_part("03", {"pure_module"}, old)
        guard, guard_derivation = guard_loader.pure_module(CONSUMER, CONSUMER_SHA, set(),
            {"Refusal", "need", "digest", "pairs", "parse", "canonical"}, "_c9_application_guard_primitives")
        rebuilt = make_plan(request)
        guard.need(type(request["proposed_plan"]) is dict and set(request["proposed_plan"]) == set(rebuilt), "PLAN_FIELDS")
        for key in rebuilt:
            guard.need(guard.canonical(request["proposed_plan"][key]) == guard.canonical(rebuilt[key]), "PLAN_FIELD_MISMATCH:" + key)
        source = request["source"]
        h.require(set(source) == {"base", "decision", "application", "capture_sources", "stimulus_inputs", "contracts"}, "SOURCE_FIELDS")
        h.require(source["base"]["sha256"] == C9_SHA and source["decision"]["sha256"] == DECISION_SHA, "C9_BASE_IDENTITY_REQUIRED")
        base, base_id, base_members = read_archive(source["base"])
        decision = h.read_json(h.checked_descriptor(source["decision"]))
        payload, application_id, application_members = read_archive(source["application"])
        input_root = h.no_alias(out / "inputs")
        for name in payload:
            destination = h.no_alias(input_root / name)
            h.require(destination.is_relative_to(input_root) and destination != input_root, "ZIP_OUTPUT_SCOPE")
        for header in ("sine_table.svh", "sustain_controller_ports.svh"):
            h.require("include/" + header in payload, "HEADER_MISSING:" + header)
        graph = include.inspect(payload, "compile_c9_capture.f")
        base_graph = include.inspect(base, "compile.f")
        h.require(len(base_graph["units"]) == 72 and len(graph["units"]) == 75 and len(set(graph["units"])) == 75,
                  "C9_SOURCE_COUNT_72_PLUS_3")
        h.require(len(graph["ROM_payloads"]) == 9 and len(graph["include_edges"]) >= 3, "C9_ROM_INCLUDE_COUNTS")
        h.require(set(base_members) == set(decision["payloads"]) | {"MANIFEST.json"}, "C9_DECISION_MEMBER_SET")
        for member, expected in decision["payloads"].items():
            for archive_members in (base_members, application_members):
                h.require(member in archive_members and len(archive_members[member]) == expected["bytes"] and
                          old.digest(archive_members[member]) == expected["sha256"], "C9_DECISION_PAYLOAD_CHANGED:" + member)
        h.require(application_members.get("MANIFEST.json") == base_members["MANIFEST.json"], "C9_WRAPPER_MANIFEST_CHANGED")
        roles = {"DRIVER": "midi_public_port_driver.sv", "OBSERVER": "r7a_c9_public_observer.sv", "TB": TOP + ".sv"}
        h.require(set(source["capture_sources"]) == set(roles), "CAPTURE_SOURCE_ROLES")
        expected_units = set(base_graph["units"])
        for role, name in roles.items():
            path = h.checked_descriptor(source["capture_sources"][role])
            member = "m3_c9/" + name
            h.require(member in payload and old.digest(payload[member]) == h.identity(path)["sha256"], "CAPTURE_SOURCE_BODY:" + role)
            expected_units.add(member)
        h.require(set(graph["units"]) == expected_units and TOP in graph["module_to_source"], "C9_EXACT_75_UNITS")
        h.require(graph["units"] == base_graph["units"] + ["m3_c9/" + name for name in roles.values()] and
                  graph["incdirs"] == base_graph["incdirs"], "C9_EXACT_COMPILE_ORDER_AND_INCDIRS")
        for name in ("sine_wavetable.hex", "triangle_wavetable.hex"):
            h.require(name in payload and payload[name] == payload["rom/" + name], "ROM_ALIAS_BYTES:" + name)
        h.require(set(source["stimulus_inputs"]) == {"bytes.drv", "reset.drv", "ready.drv", "plan.json"}, "STIMULUS_FIELDS")
        for name, descriptor in source["stimulus_inputs"].items():
            path = h.checked_descriptor(descriptor)
            h.require(name in payload and old.digest(payload[name]) == h.identity(path)["sha256"], "STIMULUS_BODY:" + name)
        expected_payload = set(base) | {"m3_c9/" + name for name in roles.values()} | set(source["stimulus_inputs"]) | {
            "sine_wavetable.hex", "triangle_wavetable.hex", "compile_c9_capture.f"}
        h.require(set(payload) == expected_payload, "C9_EXACT_APPLICATION_PAYLOAD")
        h.require(set(application_members) == {"inputs/" + name for name in expected_payload} |
                  (set(base_members) - {"inputs/" + name for name in base}), "C9_EXACT_APPLICATION_ARCHIVE_MEMBERS")
        h.require(set(source["contracts"]) == {"exports", "row_schema", "capture"}, "CONTRACT_FIELDS")
        contracts = {key: h.read_json(h.checked_descriptor(value)) for key, value in source["contracts"].items()}
        h.require(contracts["exports"]["top"] == "m2_138k_pro_fourvoice_observer_top_r06c9" and
                  len(contracts["exports"]["expected_observation_ports"]) == 67 and len(contracts["row_schema"]["required"]) == 74,
                  "C9_67_PORT_74_FIELD_CONTRACT")
        spec = request["execution_spec"]
        h.require(set(spec) == {"top", "cwd", "environment", "window_parameters", "steps", "budget", "nonce", "expected_assertions"}, "EXECUTION_SPEC_FIELDS")
        h.require(spec["top"] == TOP and spec["cwd"] == "inputs", "C9_TOP_OR_CWD")
        h.require(type(spec["environment"]) is dict and all(type(k) is str and type(v) is str for k, v in spec["environment"].items()), "ENVIRONMENT_FIELDS")
        h.require(not any(re.search(r"P7|BYPASS|ALLOW_|OWNED_EXECUTOR", key, re.I) for key in spec["environment"]), "LEGACY_EXECUTION_SWITCH")
        windows = spec["window_parameters"]
        window_doc = h.read_json(h.checked_descriptor(request["window_reference"]))
        h.require(set(windows) == WINDOWS and guard.canonical(windows) == guard.canonical(window_doc["window_parameters"]), "WINDOW_REFERENCE_MISMATCH")
        for key in WINDOWS:
            value = windows[key]
            if key in ("CAPTURE_ID", "PLAN_STOP_ID"):
                h.require(type(value) is str and re.fullmatch("[A-Za-z0-9_-]{1,80}", value), "WINDOW_TOKEN")
            else:
                h.require(type(value) is int and value >= 0, "WINDOW_INTEGER")
        h.require(windows["STOP_DRIVER_CYCLE"] > 0 and windows["MAX_SIM_TIME_PS"] > 0 and
                  windows["MAX_CORE_SAMPLES"] > windows["EXPECTED_FINISH_CORE_CYCLE"], "WINDOW_BOUNDS")
        plan_input = h.read_json(h.checked_descriptor(source["stimulus_inputs"]["plan.json"]))
        h.require(windows["STOP_DRIVER_CYCLE"] >= plan_input["total_cycles"], "STOP_BEFORE_INDEPENDENT_INPUT_END")
        budget = spec["budget"]
        h.require(set(budget) == {"wall_seconds", "max_log_bytes", "max_output_bytes"} and
                  all(type(value) is int and value > 0 for value in budget.values()) and budget["wall_seconds"] <= 300, "BUDGET_BOUND")
        h.require(type(spec["nonce"]) is str and re.fullmatch("[0-9a-f]{32,64}", spec["nonce"]), "NONCE")
        h.require(type(spec["expected_assertions"]) is list and bool(spec["expected_assertions"]) and
                  all(type(value) is str and bool(value) for value in spec["expected_assertions"]), "EXPECTED_ASSERTIONS_REQUIRED")
        h.require(set(request["tools"]) == {"vlib", "vlog", "vsim"}, "EXACT_TOOL_ROLES")
        external_descriptor = request["external_inputs"]
        external_path = Path(external_descriptor["path"])
        if not external_path.is_absolute():
            external_path = ROOT / external_path
        h.require(h.no_alias(external_path) == EXTERNAL_MANIFEST and external_descriptor["sha256"] == EXTERNAL_MANIFEST_SHA,
                  "EXTERNAL_INPUT_MANIFEST_REQUIRED")
        external = h.read_json(h.checked_descriptor(external_descriptor))
        allow = {str(h.no_alias(entry["path"])): entry for entry in external["files"]}
        tool_checker = pure_part("05", {"pe_imports", "evaluate"}, old)
        tool_reports = {}
        for role, tool_request in request["tools"].items():
            h.require(tool_request["origin"] == "REAL_CANDIDATE" and tool_request.get("coverage") == "IDENTITY_ONLY", "ACTUAL_TOOL_REQUEST_REQUIRED")
            h.require(Path(tool_request["tool"]["file"]["path"]).name.lower() == role + ".exe", "TOOL_ROLE_FILE")
            for descriptor in [tool_request["tool"]["file"], *[item["file"] for item in tool_request["dependencies"]]]:
                path = h.no_alias(descriptor["path"])
                h.require(str(path) in allow and {key: descriptor[key] for key in ("bytes", "sha256")} ==
                          {key: allow[str(path)][key] for key in ("bytes", "sha256")}, "EXTERNAL_FILE_NOT_FROZEN")
            tool_reports[role] = tool_checker.evaluate(tool_request)
        h.require(type(spec["steps"]) is list and [step.get("tool") for step in spec["steps"]] == ["vlib", "vlog", "vsim"], "TOOL_STEP_ORDER")
        for step in spec["steps"]:
            h.require(set(step) == {"tool", "argv"} and type(step["argv"]) is list and step["argv"] and
                      all(type(arg) is str and arg for arg in step["argv"]), "TOOL_ARGV")
            expected_exe = str(h.no_alias(request["tools"][step["tool"]]["tool"]["file"]["path"]))
            h.require(step["argv"][0] == expected_exe, "TOOL_ARGV_IDENTITY")
        executable = {role: str(h.no_alias(item["tool"]["file"]["path"])) for role, item in request["tools"].items()}
        exact_argv = {"vlib": [executable["vlib"], "work"],
                      "vlog": [executable["vlog"], "-sv", "-f", "compile_c9_capture.f"],
                      "vsim": [executable["vsim"], "-c"] + ["-g" + key + "=" + str(windows[key]) for key in WINDOW_ORDER] +
                              ["work." + TOP, "-do", "run -all; quit -f"]}
        for step in spec["steps"]:
            h.require(step["argv"] == exact_argv[step["tool"]], "EXACT_TOOL_ARGV_TEMPLATE:" + step["tool"])
        guard_report = {"schema": "M3_C9_APPLICATION_GUARD_V1", "permission": "NOT_GRANTED", "process_route": "ABSENT",
                        "bound_fields": sorted(rebuilt), "spec_reconstructed_equal": True,
                        "C9_application_extension_only": True, "guard_primitives": guard_derivation,
                        "guard_loader": guard_loader.derivation, "old_Python_worker_audit_invoked": False,
                        "reason": "Old guard is fixed-Python scope; reuse unchanged pure canonical comparison, never broaden it into HDL permission"}
        resolved = {**rebuilt, "resolved_cwd": str(out / "inputs"),
                    "resolved_output": str(out / "r/coordinator/outputs" / windows["CAPTURE_ID"]),
                    "resolved_environment": spec["environment"], "requested_budget": budget}
        plan_sha = old.digest(guard.canonical(resolved).encode("utf-8"))
        scoped = types.SimpleNamespace(**old.__dict__)
        scoped.DOC = out / "r"
        reservation_module = pure_part("04", {"claim_path", "evaluate"}, scoped)
        reservation_request = {"schema": "M3_R08_RESERVATION_REQUEST_V1", "action": "RESERVE", "root": str(scoped.DOC / "coordinator"),
            "capture_id": windows["CAPTURE_ID"], "plan_sha256": plan_sha, "nonce": spec["nonce"],
            "guard": {"validated_plan_sha256": plan_sha, "permission": "NOT_GRANTED"}, "outcome": None}
        h.write_json(out / "RESERVATION_INPUT.json", reservation_request)
        reservation = reservation_module.evaluate(reservation_request)
        h.require(reservation["output"] == resolved["resolved_output"], "RESERVATION_RESOLVED_OUTPUT")
        for name, raw in payload.items():
            destination = h.no_alias(out / "inputs" / name)
            h.require(destination.is_relative_to(input_root), "ZIP_OUTPUT_SCOPE")
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as stream:
                stream.write(raw)
        with (out / "SOURCE_APPLICATION_C9.zip").open("xb") as stream:
            source_path = h.checked_descriptor(source["application"])
            with source_path.open("rb") as original:
                for block in iter(lambda: original.read(1024 * 1024), b""):
                    stream.write(block)
        pending = ["M2_TRUSTED_EXECUTOR_AND_EXACT_EXECUTION_ADMISSION", "NATIVE_DYNAMIC_DELAY_LOADER_DEPENDENCIES_UNKNOWN",
                   "WINDOW_PHASE_AND_OWNER_FREEZE_REQUIRED", "PARAMETER_RUNTIME_READMEM_NOT_ELABORATED",
                   "REAL_CAPTURE_PCM_PLAN_MAPPING_AUDIO_STABLE_AND_PHYSICAL_NOT_VERIFIED"]
        application = {"schema": "M3_C9_EXECUTION_APPLICATION_V1", "status": "PENDING_M2_EXECUTION_ADMISSION",
            "execution_allowed": False, "approved": False, "authenticated": False, "source": source,
            "source_base_verified": base_id, "source_application_verified": application_id,
            "source_envelope": {"decision_payloads_verified": len(decision["payloads"]),
                                "input_payloads": len(base), "base_archive_members": len(base_members),
                                "application_archive_members": len(application_members),
                                "provenance_members": sorted(name for name in base_members if name.startswith("provenance/")),
                                "wrapper_manifest_byte_identical": True},
            "source_counts": {"base_units": 72, "with_capture_units": 75, "ROMs": 9, "headers": 2, "aliases": 2},
            "contracts": source["contracts"], "window_reference": request["window_reference"], "window_evidence": window_doc,
            "bound_plan": resolved, "plan_sha256": plan_sha, "guard": guard_report,
            "reservation": reservation, "reservation_scope": "APPLICATION_OUTPUT_ONLY_NOT_AN_HDL_EXECUTION_PERMISSION",
            "pending": pending, "derive": {"01": include.derivation, "04": reservation_module.derivation, "05": tool_checker.derivation},
            "board_release_allowed": False}
        outputs = {"application": ("APPLICATION.json", application), "guard": ("GUARD.json", guard_report),
                   "reservation": ("RESERVATION.json", reservation), "dependency_graph": ("DEPENDENCY_GRAPH.json", graph),
                   "tools": ("TOOLS.json", tool_reports), "resolved_plan": ("BOUND_PLAN.json", resolved)}
        artifacts = {}
        for key, (name, value) in outputs.items():
            h.write_json(out / name, value)
            artifacts[key] = h.artifact(out / name)
        artifacts["source"] = h.artifact(out / "SOURCE_APPLICATION_C9.zip")
        artifacts["claim"] = h.artifact(h.checked_descriptor(reservation["claim"]))
        result = {"schema": "M3_C9_APPLICATION_BUILD_RESULT_V1", "status": "PENDING_M2_EXECUTION_ADMISSION",
                  "artifacts": artifacts, "plan_sha256": plan_sha, "pending": pending, "source_units": 75,
                  "execution_allowed": False, "real_pass": False, "board_release_allowed": False}
        h.write_json(out / "RESULT.json", result)
        return result
    except Exception as error:
        if reservation is not None:
            final_request = {**reservation_request, "action": "FINALIZE", "outcome": "FAILURE"}
            h.write_json(out / "FAILURE_FINALIZATION_INPUT.json", final_request)
            try:
                terminal = reservation_module.evaluate(final_request)
                h.write_json(out / "FAILURE_FINALIZATION.json", terminal)
            except Exception as final_error:
                h.write_json(out / "FINALIZATION_FAILURE.json", {"error": type(final_error).__name__, "reason": str(final_error)})
        h.write_json(out / "FAILURE.json", {"status": "REJECT", "error": type(error).__name__, "reason": str(error),
                     "execution_allowed": False, "board_release_allowed": False})
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    h = helpers()
    try:
        result = build_application(h.read_json(args.request), args.output)
        print(json.dumps(result, ensure_ascii=False))
        return 3
    except Exception as error:
        print(json.dumps({"status": "REJECT", "error": type(error).__name__, "reason": str(error), "execution_allowed": False}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
