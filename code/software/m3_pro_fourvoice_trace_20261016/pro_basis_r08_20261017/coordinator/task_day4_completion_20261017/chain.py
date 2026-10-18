"""C9 preparation/capture pipeline. No simulator or device is started here."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from types import ModuleType

_common = Path(__file__).with_name("common.py").resolve()
_raw = _common.read_bytes()
if hashlib.sha256(_raw).hexdigest() != "55cb7481fe9c0870247a7d8b2453dea859f0f2e81879795cc0e34ffe8c996dca":
    raise RuntimeError("BOOTSTRAP_COMMON_SOURCE_CHANGED")
c = ModuleType("_d4_chain_common")
c.__file__ = str(_common)
sys.modules[c.__name__] = c
exec(compile(_raw, str(_common), "exec", dont_inherit=True), c.__dict__)


def process(request: dict, output_dir: Path) -> dict:
    c.require(request.get("schema") == "M3_C9_CHAIN_REQUEST_V1", "CHAIN_REQUEST_SCHEMA")
    mode = request.get("mode")
    c.require(mode in ("PREPARE", "PROCESS_CAPTURE"), "CHAIN_MODE")
    bindings_path = c.checked_descriptor(request["module_bindings"])
    bindings = c.read_json(bindings_path)
    c.require(bindings.get("schema") == "M3_C9_CHAIN_MODULE_BINDINGS_V1", "MODULE_BINDINGS_SCHEMA")
    modules = {}
    for name, desc in bindings["modules"].items():
        path = c.checked_descriptor(desc)
        modules[name] = c.load_source(path, desc["sha256"])
    before = {name: c.artifact(c.checked_descriptor(desc))
              for name, desc in request["inputs"].items()}
    for role in ("frame_input", "frame_rules", "application_request"):
        c.require(role in before, "CHAIN_REQUIRED_INPUT:" + role)
    refs = request.get("source_contract_refs", [])
    c.require(refs, "CHAIN_SOURCE_CONTRACTS_REQUIRED")
    for ref in refs:
        c.checked_descriptor(ref)
    out = c.output_directory(output_dir)
    artifacts = {}
    try:
        application_request = c.read_json(c.checked_descriptor(before["application_request"]))
        synthetic_example = request.get("synthetic_application_example") is True
        if synthetic_example:
            c.require(request.get("origin") == "SYNTHETIC_SCHEMA_FIXTURE", "SYNTHETIC_EXEMPTION_ORIGIN")
            application_binding = "EXAMPLE_APPLICATION_SEPARATE_FROM_SYNTHETIC_CAPTURE_WINDOW"
        else:
            c.require("window_plan" in before and "midi_plan" in before, "APPLICATION_INDEPENDENT_WINDOW_REQUIRED")
            window = c.read_json(c.checked_descriptor(before["window_plan"]))
            parameters = application_request["execution_spec"]["window_parameters"]
            c.require(request["capture_id"] == window["capture_id"] == parameters["CAPTURE_ID"]
                and window["plan_stop_id"] == parameters["PLAN_STOP_ID"]
                and window["finish_cycle"] == parameters["EXPECTED_FINISH_CORE_CYCLE"],
                "APPLICATION_CAPTURE_WINDOW_MISMATCH")
            c.require(before["midi_plan"]["sha256"] == application_request["source"]["stimulus_inputs"]["plan.json"]["sha256"],
                      "APPLICATION_MIDI_PLAN_MISMATCH")
            c.require(c.read_json(c.checked_descriptor(before["frame_input"]))["finish"]["cycle"] == window["finish_cycle"],
                      "APPLICATION_FRAME_FINISH_MISMATCH")
            application_binding = "EXACT_SOURCE_INPUT_WINDOW_APPLICATION_BOUND_NOT_ADMITTED"
        c.require(any(ref["sha256"] == application_request["source"]["base"]["sha256"] for ref in refs),
                  "APPLICATION_SOURCE_CLOSURE_MISMATCH")
        application = modules["application"].build_application(application_request, out / "a")
        c.require(application["execution_allowed"] is False, "APPLICATION_MUST_NOT_GRANT_EXECUTION")
        artifacts.update({"application_" + key: value for key, value in application["artifacts"].items()})
        # This is the only FRAME_PLAN producer. The downstream consumers read
        # its canonical document, never infer F from observed transactions.
        modules["frame_generator"].generate(c.checked_descriptor(before["frame_input"]),
                                             c.checked_descriptor(before["frame_rules"]), out / "frame_plan")
        artifacts["frame_plan"] = c.artifact(out / "frame_plan/UNIQUE_FRAME_PLAN.json")
        artifacts["calendar_projection"] = c.artifact(out / "frame_plan/FRAME_PLAN.json")
        artifacts["tx_projection"] = c.artifact(out / "frame_plan/TX_FRAME_PLAN.json")
        pending = ["M2_EXACT_EXECUTION_ADMISSION", "TRUSTED_PRODUCER_AUTHORITY",
                   "M1_INDEPENDENT_MATH_ORACLE", "INDEPENDENT_APPLY_PLAN_MAPPING",
                   "AUDIO_STABLE_POLICY", "PHYSICAL_AND_BOARD_VERIFICATION"]
        summaries = {"application": application["status"]}
        if mode == "PROCESS_CAPTURE":
            for role in ("raw", "resets", "end", "stdout", "midi_plan", "window_plan"):
                c.require(role in before, "CHAIN_CAPTURE_INPUT:" + role)
            paths = {role: c.checked_descriptor(desc) for role, desc in before.items()}
            converted = modules["stream"].convert_files(paths["raw"], paths["resets"], paths["end"],
                paths["stdout"], out / "capture", origin=request["origin"])
            artifacts["public_rows"] = converted["artifacts"]["public_rows"]
            public = c.checked_descriptor(artifacts["public_rows"])
            modules["codec"].encode_file(public, out / "public_rows.csv")
            modules["codec"].decode_file(out / "public_rows.csv", out / "csv_roundtrip.jsonl")
            from itertools import zip_longest
            row_count = 0
            for row_count, pair in enumerate(zip_longest(c.iter_jsonl(public),
                    c.iter_jsonl(out / "csv_roundtrip.jsonl")), 1):
                c.require(pair[0] is not None and pair[0] == pair[1], "CHAIN_CSV_ROUNDTRIP")
            artifacts["public_csv"] = c.artifact(out / "public_rows.csv")
            artifacts["csv_roundtrip"] = c.artifact(out / "csv_roundtrip.jsonl")
            intake = modules["intake"].project_intake_files(public, out / "intake")
            artifacts.update({"intake_" + key: value for key, value in intake["artifacts"].items()})
            ledger = c.read_json(c.checked_descriptor(intake["artifacts"]["ledger"]))
            calendar = modules["calendar"].analyze(ledger, c.read_json(c.checked_descriptor(artifacts["frame_plan"])))
            c.write_json(out / "CALENDAR_REPORT.json", calendar)
            artifacts["calendar"] = c.artifact(out / "CALENDAR_REPORT.json")
            serial = modules["serial"].analyze_files(public, c.checked_descriptor(artifacts["frame_plan"]),
                                                    out / "serial", expected_scenario_ref=request.get("expected_scenario_ref"))
            c.write_json(out / "SERIAL_REPORT.json", serial)
            artifacts["serial"] = c.artifact(out / "SERIAL_REPORT.json")
            graph = c.read_json(c.checked_descriptor(application["artifacts"]["dependency_graph"]))
            roms = {}
            for rom in graph["ROM_payloads"]:
                path = c.no_alias(out / "a/inputs" / rom["path"])
                c.require(path.is_relative_to(out / "a/inputs"), "ROM_SOURCE_PATH")
                actual = c.artifact(path)
                c.require({key: actual[key] for key in ("bytes", "sha256")} ==
                          {key: rom[key] for key in ("bytes", "sha256")}, "ROM_SOURCE_BYTES")
                roms[rom["path"]] = actual
            c.require(len(roms) == 9, "NINE_ACTUAL_ROM_FILES_REQUIRED")
            c.write_json(out / "ROM_MANIFEST.json", {"schema": "M3_C9_ACTUAL_ROM_INPUTS_V1",
                "files": roms, "application_source": application["artifacts"]["source"],
                "dependency_graph": application["artifacts"]["dependency_graph"],
                "actual_bytes_only_not_math_verification": True})
            artifacts["rom_manifest"] = c.artifact(out / "ROM_MANIFEST.json")
            math_inputs = dict(request.get("math_inputs", {}))
            available = dict(source_closure=application["artifacts"]["source"],
                base_source_closure=application_request["source"]["base"],
                source_decision=application_request["source"]["decision"],
                rom_manifest=artifacts["rom_manifest"],
                observer=application_request["source"]["capture_sources"]["OBSERVER"],
                driver=application_request["source"]["capture_sources"]["DRIVER"],
                tb=application_request["source"]["capture_sources"]["TB"],
                tool_identity=application["artifacts"]["tools"],
                capture_contract=application_request["source"]["contracts"]["capture"],
                public_rows=artifacts["public_rows"], raw_capture=before["raw"],
                reset_edges=before["resets"], end=before["end"], stdout=before["stdout"],
                midi_plan=before["midi_plan"], frame_plan=artifacts["frame_plan"],
                ledger=intake["artifacts"]["ledger"], tx_report=artifacts["serial"])
            noteon = c.ROOT / 'code/docs/test/m2_m1_noteon_erratum_20261017'
            for role, filename, sha in (
                ('noteon_semantics_binding', 'SEMANTICS_BINDING.json',
                 '5678e4dc4a8b79a57b2537fd9db615cc16a556859440be4c57864b0799eb9d14'),
                ('noteon_semantics_acceptance', 'ACCEPTANCE.json',
                 'bdc2b128030453f0fafda259a01e5c0b16c7f71fe1b424a01b209d1e32f3f011')):
                descriptor = c.artifact(noteon / filename)
                c.require(descriptor['sha256'] == sha, 'M2_ACCEPTED_NOTEON_BINDING_CHANGED')
                available[role] = descriptor
            for role, descriptor in available.items():
                if role in math_inputs:
                    c.require(c.checked_descriptor(math_inputs[role]) == c.checked_descriptor(descriptor),
                              "MATH_ROLE_SAME_SOURCE_MISMATCH:" + role)
                math_inputs[role] = descriptor
            # Actual execution_receipt is optional here; absence remains an
            # explicit missing role. No empty receipt or golden PCM is made.
            math_bundle = modules["math"].build_bundle({"schema": "M3_D4_C9_MATH_BUNDLE_REQUEST_V1",
                "capture_id": request["capture_id"], "inputs": math_inputs}, out / "math")
            artifacts.update({"math_" + key: value for key, value in math_bundle["artifacts"].items()})
            provenance = modules["provenance"].validate_capture(request, artifacts, out / "provenance")
            artifacts.update(provenance["artifacts"])
            summaries.update(rows=row_count, calendar=calendar.get("status"),
                serial=serial.get("status"), math=math_bundle["status"],
                missing_math_roles=math_bundle["missing_roles"], provenance=provenance["status"])
        else:
            summaries.update(capture="NOT_RUN", calendar="NOT_RUN", serial="NOT_RUN", math="NOT_RUN")
        for desc in before.values():
            c.checked_descriptor(desc)
        for desc in refs:
            c.checked_descriptor(desc)
        c.checked_descriptor(request["module_bindings"])
        result = {"schema": "M3_C9_CHAIN_HANDOFF_V1", "mode": mode,
            "capture_id": request.get("capture_id"), "origin": request.get("origin"),
            "status": "PREPARED_PENDING_EXECUTION" if mode == "PREPARE" else "SOFTWARE_CHAIN_BOUND_PENDING_REAL_AUTHORITY",
            "inputs": before, "source_contract_refs": refs, "module_bindings": request["module_bindings"],
            "application_capture_binding": application_binding,
            "artifacts": artifacts, "summary": summaries, "pending": pending,
            "unique_FRAME_PLAN_producer": bindings["modules"]["frame_generator"],
            "execution_allowed": False, "math_verified": False,
            "real_verified": False, "board_release_allowed": False}
        c.write_json(out / "HANDOFF.json", result)
        return {**result, "artifacts": {**artifacts, "handoff": c.artifact(out / "HANDOFF.json")}}
    except BaseException as error:
        c.write_json(out / "FAILURE.json", {"status": "PARTIAL_FAILURE_OR_REJECT",
            "error": type(error).__name__ + ":" + str(error), "artifacts_completed": artifacts,
            "inputs": before, "real_verified": False})
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = process(c.read_json(args.request), args.output)
    print(json.dumps({"status": result["status"], "execution_allowed": False}))
    return 3  # limited preparation/candidate evidence, never real acceptance


if __name__ == "__main__":
    raise SystemExit(main())
