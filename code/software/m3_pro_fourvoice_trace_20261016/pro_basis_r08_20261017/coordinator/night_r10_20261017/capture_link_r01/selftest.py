"""Targeted LINK repair checks; dispatch probes never process a fake capture."""
from pathlib import Path
from types import SimpleNamespace

CASES = ["CAPTURE_DISPATCH_BOUND_APPLICATION", "UNFROZEN_PHASE_REJECT",
         "OLD_APPLICATION_BINDING_REJECT", "OUTPUT_ESCAPE_REJECT",
         "APPLICATION_ADAPTER_SCOPE_REJECT", "PREPARATION_DISPATCH"]


def run(entry, adapter, output):
    c = entry.helpers()
    output.mkdir()

    def save(name, value):
        path = output / name
        c.save(path, value)
        return c.ref(path)

    def request_fixture(name, *, frozen=True, old_binding=False):
        # Deliberately not a decodable RAW capture. Only the dispatch seam is
        # exercised. None of the old capture/FRAME/math algorithms is invoked.
        raw = output / (name + ".not_capture")
        raw.write_bytes(b"DISPATCH_PROBE_ONLY_NOT_CAPTURE_DATA\n")
        midi = save(name + "_midi.json", {"test_only": True})
        window = save(name + "_window.json", {
            "schema": "M3_R7D_INDEPENDENT_WINDOW_V1", "capture_id": "LINK_DISPATCH_PROBE",
            "plan_stop_id": "PROBE_ONLY", "finish_cycle": 2, "row_count": 3,
            "first_core_ps": 12500, "core_period_ps": 25000, "finish_time_ps": 62500,
            "input_plan_sha256": midi["sha256"]})
        end = save(name + "_end.json", {"capture_id": "LINK_DISPATCH_PROBE",
            "reason": "PLANNED_WINDOW_END", "finish_cycle": 2, "row_count": 3, "time_ps": 62500})
        frame = save(name + "_frame.json", {"status": "FROZEN_INDEPENDENT_INPUT" if frozen else "PENDING",
            "independent_of_observed_trace": True, "finish": {"cycle": 2}})
        app = save(name + "_app.json", {"approved": False, "execution_spec": {"window_parameters": {
            "CAPTURE_ID": "LINK_DISPATCH_PROBE", "PLAN_STOP_ID": "PROBE_ONLY",
            "EXPECTED_FINISH_CORE_CYCLE": 2}}})
        binding = (entry.DOC / "task_day4_completion_20261017/MODULE_BINDINGS.json") if old_binding else entry.BINDING
        request = {"schema": "M3_C9_CHAIN_REQUEST_V1", "mode": "PROCESS_CAPTURE",
            "capture_id": "LINK_DISPATCH_PROBE", "origin": "SYNTHETIC_SCHEMA_FIXTURE",
            "module_bindings": c.ref(binding), "source_contract_refs": [midi],
            "inputs": {"application_request": app, "frame_input": frame, "frame_rules": midi,
                       "raw": c.ref(raw), "resets": midi, "end": end, "stdout": c.ref(raw),
                       "window_plan": window, "midi_plan": midi}}
        return {"schema": "N10_M3_UNIFIED_PIPELINE_REQUEST_V1", "mode": "PROCESS_CAPTURE",
                "request": save(name + "_request.json", request)}

    results = []

    def reject(case, operation, reason):
        try:
            operation()
        except ValueError as error:
            if reason not in str(error):
                raise AssertionError((case, reason, str(error))) from error
        else:
            raise AssertionError(case + ":ACCEPTED")
        results.append({"case": case, "status": "MATCHED", "expected_rejection": reason})

    envelope = request_fixture("dispatch")
    called = []
    original = entry.capture_module

    def probe(request, out):
        bindings = c.read(c.checked(request["module_bindings"]))
        if bindings["modules"]["application"]["path"] != c.ref(Path(adapter.__file__))["path"]:
            raise AssertionError("APPLICATION_NOT_ADAPTED")
        if not Path(out).is_relative_to(entry.OUT):
            raise AssertionError("OUTPUT_NOT_R10")
        called.append((request["capture_id"], str(out)))
        return {"status": "DISPATCH_PROBE_ONLY_NOT_CAPTURE_VALIDATION", "execution_allowed": False,
                "real_verified": False, "math_verified": False, "board_release_allowed": False}

    entry.capture_module = lambda: SimpleNamespace(process=probe)
    try:
        result = entry.process(envelope, output / "capture_result")
        if len(called) != 1 or result["real_verified"] is not False:
            raise AssertionError("CAPTURE_DISPATCH_NOT_EXACTLY_ONCE")
        results.append({"case": CASES[0], "status": "MATCHED", "calls": called,
                        "boundary": "SPY_DISPATCH_ONLY; no raw/FRAME/serial/math processing"})
        reject(CASES[1], lambda: entry.process(request_fixture("pending", frozen=False), output / "pending_result"),
               "CAPTURE_LINK_PHASE_NOT_FROZEN")
        reject(CASES[2], lambda: entry.process(request_fixture("binding", old_binding=True), output / "binding_result"),
               "CAPTURE_LINK_BINDING")
        reject(CASES[3], lambda: entry.process(envelope, entry.ROOT / "code/output/m3_c9_complete_d4_20261017/escape"),
               "CAPTURE_LINK_STRICT_OUTPUT_SCOPE")
        if len(called) != 1:
            raise AssertionError("REJECTED_CAPTURE_WAS_DISPATCHED")
    finally:
        entry.capture_module = original
    reject(CASES[4], lambda: adapter.build_application({}, entry.OUT), "SCOPE")
    prep = entry.DOC / "night_r10_20261017/PIPELINE_REQUEST_TEMPLATE.json"
    original = entry.preparation_module
    prep_calls = []

    def prepare_probe(request, out):
        if request.get("mode") != "PREPARE_APPLICATION_ONLY":
            raise AssertionError("PREPARATION_PAYLOAD")
        prep_calls.append(str(out))
        return {"status": "PREPARATION_DISPATCH_PROBE_ONLY", "execution_allowed": False,
                "real_verified": False, "math_verified": False, "board_release_allowed": False}

    entry.preparation_module = lambda: SimpleNamespace(process=prepare_probe)
    try:
        entry.process({"schema": "N10_M3_UNIFIED_PIPELINE_REQUEST_V1",
                       "mode": "PREPARE_APPLICATION_ONLY", "request": c.ref(prep)}, output / "prepare_result")
        if len(prep_calls) != 1:
            raise AssertionError("PREPARATION_DISPATCH_NOT_EXACTLY_ONCE")
        results.append({"case": CASES[5], "status": "MATCHED", "calls": prep_calls,
                        "boundary": "SPY_DISPATCH_ONLY; old preparation group not replayed"})
    finally:
        entry.preparation_module = original
    if [r["case"] for r in results] != CASES:
        raise AssertionError("CASE_COMPLETENESS")
    return results
