"""R13 root-admitted checks; fixture creation occurs inside the charged group.

No target executes at import. Frozen R12/R11/R10/D4 sources are never patched.
Only the current C private reader/entry test hooks are used for fault cases.
"""
from __future__ import annotations

import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback
from types import FunctionType
import uuid

import binding
import entry
import resources
from finalize import atomic_json
from stream_bridge import (CHUNK, Reject, identity, read_control,
                           parse_json, read_descriptor_json, require, strict_child)
from volume_io import VolumeStore, DECODED_PART_LIMIT

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[6]
OUTPUT = ROOT / "code/output/m3_backend_stream_r13_20261018"
PLAN_SHA256 = "729cb21bd4b759f7d5738bdc14964bee1eaf5da053eee20b4a278acf651357d3"
GROUPS = {"P0": ["P001"], "P1": ["P001"], "K": [f"K{i:02d}" for i in range(1, 9)],
          "V": [f"V{i:02d}" for i in range(1, 13)],
          "B": [f"B{i:02d}" for i in range(1, 13)], "W": ["W01"]}
PINNED = {**{str(binding.R12 / name): sha for name, sha in binding.PINS.items()},
    str(binding.R12 / "selftest.py"): "5ce7234c457e8c53cdcbe857e40cc2c1235ad171bd95d647a13a8c04a5930c1c",
    str(ROOT / "code/software/t052_runner_acceptance_candidate_20261012/windows_job.py"):
        "5450b8943b0616cc0f8ad7147c1c6a4b20eb4f04d8a7cc3fb515825941c0df1b"}
CONTRACT_OBJECTS = {"FIELD_ROUTE_TABLE.json", "PROFILE_AND_CAPACITY.json",
    "PLAN_IDENTITY_MAP.json", "EPOCH_RESET_FINISH_CONTRACT.json", "SOURCE_PROVENANCE.json",
    "OPEN_DECISIONS.json", "M2_DECISION_SHEET.md", "README.md"}
CONTRACT_ROOT = (ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/"
    "pro_basis_r08_20261017/coordinator/night_r10_20261017/backend_stream_r13_20261018/contract_bundle")
B08_SPEC = {"path": OUTPUT / "roles/main4/B08_MINIMAL_FIXTURE_NOTE_R02.json",
    "bytes": 18457, "sha256": "f74e26b6d7351af164863c12be32d470b30332deb7be9e885aa28e43a7b389be"}


def _ref(path):
    path = Path(path).resolve()
    return {"path": path.relative_to(ROOT).as_posix() if path.is_relative_to(ROOT)
            else str(path), **identity(path)}


def _mkdir(path, parents=True, exist_ok=False):
    resources.get_budget().check()
    resources.accounting_mkdir(path, parents=parents, exist_ok=exist_ok)


def _save_bytes(path, raw, exclusive=True):
    _mkdir(Path(path).parent, exist_ok=True)
    resources.accounting_save_bytes(path, raw, exclusive=exclusive)
    return _ref(path)


def _save(path, value, exclusive=True):
    raw = (json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False) + "\n").encode("utf-8")
    return _save_bytes(path, raw, exclusive)


def _manifest(path):
    return read_control(path)["value"]


def _resolve(ref):
    path = Path(ref["path"])
    return (path if path.is_absolute() else ROOT / path).resolve()


def _checked_ref(ref, reason="CONTRACT_SOURCE_IDENTITY"):
    require(type(ref) is dict and {"path", "bytes", "sha256"} <= ref.keys(), reason)
    actual = identity(_resolve(ref))
    require(actual == {key: ref[key] for key in ("bytes", "sha256")}, reason)
    return _resolve(ref)


def _ref_json(ref, reason="CONTRACT_SOURCE_IDENTITY"):
    record = read_control(_resolve(ref), ref["sha256"])
    require(record["stamp"]["bytes"] == ref["bytes"], reason)
    return record["value"]


def _expect_reject(call, token):
    try:
        call()
    except (Reject, ValueError, OSError) as error:
        require(token in str(error), "WRONG_REJECT:" + str(error))
        return {"class": type(error).__name__, "error": str(error)}
    raise Reject("EXPECTED_REJECT_NOT_OBSERVED:" + token)


def _delivery_ready(value):
    require(value.get("delivery_channel_confirmed") is True,
            "DELIVERY_CHANNEL_NOT_CONFIRMED")
    delivery = value.get("delivery")
    require(type(delivery) is dict and type(delivery.get("location")) is str
            and delivery["location"] and type(delivery.get("retrieval_method")) is str
            and delivery["retrieval_method"] and delivery.get("all_logical_originals_recoverable") is True,
            "DELIVERY_CHANNEL_INCOMPLETE")
    require(delivery.get("local_only", False) is False and
            delivery["retrieval_method"] != "local-only", "DELIVERY_LOCAL_ONLY")


def _control_guard(path, record):
    require(identity(path) == record["stamp"], "CONTROL_CHANGED_AFTER_SAME_BUFFER_PARSE")


def _same_buffer_case(case):
    control = case / "control.json"
    original = b'{"decision":"original"}\n'
    ref = _save_bytes(control, original)
    events = []
    # Exact production read_control code/defaults, isolated globals only. This
    # callback fires after its actual digest check and at its actual parser call.
    def boundary(raw):
        require(raw == original, "V11_ACTUAL_BUFFER")
        events.append("HASH_COMPLETE_BEFORE_PARSE")
        _save_bytes(control, b'{"decision":"tampered"}\n', exclusive=False)
        return parse_json(raw)
    private_globals = dict(read_control.__globals__, parse_json=boundary)
    consume = FunctionType(read_control.__code__, private_globals,
                           read_control.__name__, read_control.__defaults__)
    consume.__kwdefaults__ = read_control.__kwdefaults__
    record = consume(control, ref["sha256"])
    require(record["raw"] == original and record["value"] == {"decision": "original"}
            and record["stamp"] == {"bytes": ref["bytes"], "sha256": ref["sha256"]},
            "V11_HASH_PARSE_NOT_SAME_BUFFER")
    refusal = _expect_reject(lambda: _control_guard(control, record),
                              "CONTROL_CHANGED_AFTER_SAME_BUFFER_PARSE")
    return {"events": events, "initial": record["stamp"], "terminal": identity(control),
            "terminal_guard": refusal, "private_function_code_is_actual": True}


def _drain(stream):
    chunks = []
    with stream:
        while True:
            data = stream.read(CHUNK)
            if not data:
                break
            require(len(data) <= CHUNK, "READ_REQUEST_BOUND")
            chunks.append(data)
    return b"".join(chunks)


def _volume_case(case_id, root, admission):
    case = root / case_id
    _mkdir(case)
    if case_id == "V11":
        return {"id": case_id, "status": "PASS", "observed": _same_buffer_case(case)}
    if case_id == "V12":
        _delivery_ready(admission)
        invalid = copy.deepcopy(admission)
        invalid["delivery_channel_confirmed"] = True
        invalid["delivery"] = {"location": str(case), "retrieval_method": "local-only",
                                "all_logical_originals_recoverable": True, "local_only": True}
        refusal = _expect_reject(lambda: _delivery_ready(invalid), "DELIVERY_LOCAL_ONLY")
        return {"id": case_id, "status": "PASS", "observed": refusal}
    logical = case / "logical.jsonl"
    store = VolumeStore(case)
    payload = (b"a" * (DECODED_PART_LIMIT - 1) + "音".encode() + b"\n" if case_id == "V02" else
               b"one\r\ntwo\nthree\r\n" if case_id == "V03" else b'{"row":1}\n' * 8192)
    with store.open(logical, "xb") as stream:
        for offset in range(0, len(payload), CHUNK):
            stream.write(payload[offset:offset + CHUNK])
    manifest_path = store.folder_for(logical) / "MANIFEST.json"
    manifest = _manifest(manifest_path)
    part = store.folder_for(logical) / manifest["parts"][0]["compressed"]["path"]
    if case_id == "V04":
        part.unlink()  # Removal never refunds global write quota.
    elif case_id == "V05":
        manifest["parts"].append(copy.deepcopy(manifest["parts"][0]))
    elif case_id == "V06":
        manifest["parts"][0]["sequence"] = 1
    elif case_id == "V07":
        manifest["parts"][0]["logical_offset"] = 1
    elif case_id == "V08":
        manifest["parts"][0]["decoded_sha256"] = "0" * 64
    elif case_id == "V09":
        manifest["original"]["sha256"] = "0" * 64
    elif case_id == "V10":
        with part.open("rb", buffering=0) as source:
            raw = source.read(CHUNK)
            require(not source.read(1), "V10_SMALL_FIXTURE_PART_BOUND")
        with resources.accounting_open(part, "wb", category="all_stores") as damaged:
            require(damaged.write(raw[:-1]) == len(raw) - 1, "V10_SHORT_WRITE")
    if case_id in {"V05", "V06", "V07", "V08", "V09"}:
        _save(manifest_path, manifest, exclusive=False)
    if case_id in {f"V{i:02d}" for i in range(4, 11)}:
        observed = _expect_reject(lambda: _drain(VolumeStore(case).open(logical, "rb")), "VOLUME_")
    else:
        require(_drain(store.open(logical, "rb")) == payload, "VOLUME_NOT_LOSSLESS")
        if case_id == "V02":
            require(len(manifest["parts"]) >= 2 and payload.decode("utf-8").endswith("音\n"),
                    "UTF8_REAL_VOLUME_BOUNDARY_NOT_COVERED")
        observed = {"bytes": len(payload), "sha256": hashlib.sha256(payload).hexdigest()}
    return {"id": case_id, "status": "PASS", "observed": observed}


def consume_contract(index_path, index_sha):
    """One actual contract consumer for all K positive/mutated inputs.

    Container identities and semantic bindings are separate checks. Even an
    attacker-updated outer SHA cannot turn a changed raw source/profile/plan
    or epoch/reset origin into an accepted contract.
    """
    record = read_control(index_path, index_sha)
    value = record["value"]
    require(value.get("schema") == "M3_R13_CONTRACT_INDEX_V1", "CONTRACT_INDEX_SCHEMA")
    require(type(value.get("objects")) is list and len(value["objects"]) == 8,
            "CONTRACT_OBJECT_COUNT")
    loaded, records, names = {}, [], set()
    for desc in value["objects"]:
        name = Path(desc["path"]).name
        require(name in CONTRACT_OBJECTS and name not in names, "CONTRACT_OBJECT_SET")
        names.add(name)
        path = _checked_ref(desc, "CONTRACT_OBJECT_IDENTITY")
        if path.suffix == ".json":
            item = read_control(path, desc["sha256"])
            loaded[name] = item["value"]
            records.append((path, item))
    require(names == CONTRACT_OBJECTS and set(value["routes"]) >=
            {"A1", "A2", "A3", "A4", "B", "C", "root"}, "CONTRACT_ROUTE_MISSING")
    require(all(doc["bundle_id"] == value["bundle_id"] for doc in loaded.values()),
            "CONTRACT_BUNDLE_ID")
    routes = loaded["FIELD_ROUTE_TABLE.json"]
    refs = routes["source_refs"]
    require({"port_map", "row_schema", "raw_converter", "raw_scalar_epoch_finish"} <= refs.keys(),
            "CONTRACT_REQUIRED_SOURCE")
    for ref in refs.values():
        _checked_ref(ref)
    ports = _ref_json(refs["port_map"])
    schema = _ref_json(refs["row_schema"])
    fields = routes["fields"]
    require(routes["field_count"] == 74 and routes["raw_port_count"] == 72
            and len(fields) == 74 and len(ports["raw_ports"]) == 72
            and routes["raw_row_schema"] == "M3_R7A_C9_RAW_CORE_ROW_V1"
            and routes["public_row_schema"] == "M3_R7A_C9_PUBLIC_ROW_V1"
            and ports["sampling"] == "POSEDGE_PRE_NBA", "CONTRACT_FIELD_PROFILE")
    require([f["name"] for f in fields] == ports["normalized_fields"]
            and set(schema["required"]) == {f["name"] for f in fields}, "CONTRACT_74_FIELDS")
    for ordinal, field in enumerate(fields, 1):
        name = field["name"]
        rules = schema["properties"][name]
        require(type(field["ordinal"]) is int and field["ordinal"] == ordinal
                and type(field["width_bits"]) is int and type(field["signed"]) is bool
                and field["target_field"] == "fields." + name
                and field["schema_rules"] == rules and field["sampling"]["phase"] == "POSEDGE_PRE_NBA",
                "CONTRACT_FIELD_SCHEMA:" + name)
        bit_rules = [r for r in rules["anyOf"] if r.get("type") == "string" and "maxLength" in r]
        if bit_rules:
            require(field["width_bits"] == bit_rules[0]["maxLength"], "CONTRACT_FIELD_WIDTH:" + name)
        spec = ports["normalized_mapping"].get(name)
        if spec is not None:
            require(field["source_port"] == spec["port"] and
                    field["width_bits"] == spec["width"] and field["signed"] is spec["signed"],
                    "CONTRACT_RAW_PORT_ROUTE:" + name)
            require(ports["raw_ports"][spec["port"]] ==
                    {"width": spec["width"], "signed": spec["signed"]}, "CONTRACT_RAW_PORT_SPEC:" + name)
    capacity = loaded["PROFILE_AND_CAPACITY.json"]
    profile = next(p for p in capacity["profiles"] if p["profile"] == "C9_FULL_PUBLIC_74_MECHANICAL")
    require(profile["normalized_fields"] == 74 and profile["raw_ports"] == 72 and
            profile["raw_schema"] == routes["raw_row_schema"] and
            profile["public_schema"] == routes["public_row_schema"] and
            profile["sampling_phase"] == "POSEDGE_PRE_NBA", "CONTRACT_PROFILE_CONFLICT")
    plan = loaded["PLAN_IDENTITY_MAP.json"]
    for ref in plan["sources"].values():
        _checked_ref(ref, "CONTRACT_PLAN_ORIGINAL_SHA")
    original = _ref_json(plan["sources"]["plan"])
    independent = plan["independent_input"]
    forbidden = {"trace", "trace_path", "observed_frames", "observed_frame_rows", "actual_pcm"}
    require(not forbidden.intersection(independent) and
            "before observing DUT output" in plan["producer"] and
            plan["actual_real_plan_mapping_verified"] is False and
            all(route.get("actual_ref") is None for route in plan["causal_route"]),
            "CONTRACT_PLAN_NOT_INDEPENDENT")
    require(plan["input_schema"] == original["schema"] and
            independent["total_cycles"] == original["total_cycles"] and
            independent["byte_count"] == len(original["bytes"]) and
            independent["event_count"] == len(original["events"]) and
            independent["reset_plan"] == original["reset_plan"] and
            independent["ready_plan"] == original["ready_plan"], "CONTRACT_PLAN_MAPPING")
    for actual, expected in zip(independent["events"], original["events"]):
        require(all(actual.get(k) == expected[k] for k in ("event_seq", "scenario",
                    "normalized_kind", "channel", "note", "velocity7", "velocity10",
                    "source_byte_seq_first", "source_byte_seq_final", "arrival_window", "expected_event_hex")) and
                actual["actual_acceptance"] is None and actual["actual_apply_stages"] is None,
                "CONTRACT_INDEPENDENT_EVENT")
    frame = plan["independent_FRAME_route"]
    require(frame["rules_sha256"] == plan["sources"]["frame_rules"]["sha256"] and
            frame["source_identity_fields"] == ["path", "sha256"] and
            frame["not_generated_in_this_task"] is True, "CONTRACT_FRAME_SOURCE")
    epoch = loaded["EPOCH_RESET_FINISH_CONTRACT.json"]
    for ref in epoch["sources"].values():
        _checked_ref(ref, "CONTRACT_RESET_SOURCE_SHA")
    require(epoch["sources"]["reset_and_finish_algorithms"]["sha256"] ==
            refs["raw_scalar_epoch_finish"]["sha256"] and
            epoch["reset"]["schema"] == "M3_R7A_RESET_SNAPSHOT_V1" and
            epoch["reset"]["values"] == ["sys_rst_n", "obs_rst_n", "obs_pll_locked"] and
            epoch["timebase"]["phase"] == "POSEDGE_PRE_NBA" and
            epoch["independent_epochs"]["epoch_keys"] ==
            ["epoch", "reset_assert_cycle", "release_cycle", "stop_cycle", "window_kind"],
            "CONTRACT_RESET_EPOCH_ORIGIN")
    finish = epoch["real_finish_candidates_preserved"]
    require(finish["approved_finish_cycle"] is None and
            finish["implemented_or_approved_here"] is False, "FINISH_UNEXPECTEDLY_APPROVED")
    require([(c["finish_cycle"], c["row_count"]) for c in finish["candidates"]] ==
            [(1130660, 1130661), (1130661, 1130662)], "CONTRACT_FINISH_CANDIDATES")
    boundary = loaded["SOURCE_PROVENANCE.json"]["acceptance_boundary"]
    require(all(boundary[k] is False for k in
            ("execution_allowed", "real_verified", "math_verified", "board_release_allowed")),
            "AUTHENTICITY_UNEXPECTEDLY_REAL")
    for path, prior in records:
        _control_guard(path, prior)
    _control_guard(index_path, record)
    return {"index": value, "loaded": loaded,
            "pending": ["FINISH_PENDING", "AUTHENTICITY_PENDING"],
            "status": "STATIC_CONTRACT_CONSUMED_REAL_PENDING"}


def _contract_bundle(index_path, index_sha):
    result = consume_contract(index_path, index_sha)
    return result["index"], result["loaded"]


def _k_cases(admission, output, wanted=None):
    wanted = list(GROUPS["K"] if wanted is None else wanted)
    base_ref = admission.get("contract_index_ref")
    require(type(base_ref) is dict, "FROZEN_CONTRACT_INDEX_REF_REQUIRED")
    base = _ref_json(base_ref)
    outcomes = []
    for case_id in wanted:
        folder = output / "cases" / case_id
        _mkdir(folder)
        docs = {}
        for ref in base["objects"]:
            name = Path(ref["path"]).name
            path = _checked_ref(ref)
            if path.suffix == ".json":
                docs[name] = _ref_json(ref)
            else:
                with path.open("rb", buffering=0) as stream:
                    body = stream.read(8 * CHUNK + 1)
                require(len(body) <= 8 * CHUNK, "K_TEXT_BOUND")
                _save_bytes(folder / name, body)
        routes = docs["FIELD_ROUTE_TABLE.json"]
        expected = None
        if case_id == "K02":
            del routes["source_refs"]["port_map"]
            expected = "CONTRACT_REQUIRED_SOURCE"
        elif case_id == "K03":
            docs["PROFILE_AND_CAPACITY.json"]["profiles"][0]["raw_ports"] = 71
            expected = "CONTRACT_PROFILE_CONFLICT"
        elif case_id == "K04":
            docs["PLAN_IDENTITY_MAP.json"]["sources"]["plan"]["sha256"] = "0" * 64
            expected = "CONTRACT_PLAN_ORIGINAL_SHA"
        elif case_id == "K05":
            docs["PLAN_IDENTITY_MAP.json"]["independent_input"]["trace_path"] = "OBSERVED_TRACE_FORBIDDEN"
            expected = "CONTRACT_PLAN_NOT_INDEPENDENT"
        elif case_id == "K06":
            docs["EPOCH_RESET_FINISH_CONTRACT.json"]["sources"]["reset_and_finish_algorithms"] = copy.deepcopy(
                docs["PLAN_IDENTITY_MAP.json"]["sources"]["reset"])
            expected = "CONTRACT_RESET_EPOCH_ORIGIN"
        changed = copy.deepcopy(base)
        for name, value in docs.items():
            _save(folder / name, value)
        changed["objects"] = [_ref(folder / Path(r["path"]).name) for r in base["objects"]]
        index_ref = _save(folder / "CONTRACT_INDEX.json", changed)
        action = lambda: consume_contract(_resolve(index_ref), index_ref["sha256"])
        if expected:
            observed = _expect_reject(action, expected)
            observed["outer_SHA_updated"] = True
        else:
            consumed = action()
            observed = ("FINISH_PENDING" if case_id == "K07" else
                        "AUTHENTICITY_PENDING" if case_id == "K08" else consumed["status"])
            if case_id in {"K07", "K08"}:
                require(observed in consumed["pending"], "K_PENDING_NOT_RETURNED")
        outcomes.append({"id": case_id, "status": "PASS", "observed": observed,
                         "index": index_ref})
    return outcomes


def _p0_case():
    checked = []
    for path, sha in PINNED.items():
        stamp = identity(Path(path))
        require(stamp["sha256"] == sha, "P0_PIN:" + path)
        checked.append({"path": path, **stamp})
    actual_d4 = ROOT / "code/software/m3_pro_fourvoice_trace_20261016/pro_basis_r08_20261017/coordinator/task_day4_completion_20261017/chain.py"
    require(identity(actual_d4) == {"bytes": 12667,
        "sha256": "64bfdf4787aa9dd1ddab30a30ed7cf4fb05be763b9303ec965061005430f1c44"}, "P0_ACTUAL_D4_PIN")
    snapshot = resources.disk_snapshot(OUTPUT)
    resources.get_budget().check()
    return {"id": "P001", "status": "PASS_LOCAL_PENDING_PARENT", "observed": {
        "pins": checked, "disk": snapshot, "budget": resources.get_budget().receipt(),
        "parent_Job_and_native_close_required": True}}


def _budget_open(path, mode, *, budget, category):
    require(budget is resources.get_budget(), "SINGLE_ROOT_BUDGET_REQUIRED")
    budget.check()
    return resources.accounting_open(path, mode, category=category)


def _budget_save(path, raw, *, budget, category, exclusive=True):
    require(budget is resources.get_budget(), "SINGLE_ROOT_BUDGET_REQUIRED")
    _mkdir(Path(path).parent, exist_ok=True)
    resources.accounting_save_bytes(path, raw, category=category, exclusive=exclusive)
    return _ref(path)


def _budget_copy(source, target, *, budget, category, exclusive=True):
    require(budget is resources.get_budget(), "SINGLE_ROOT_BUDGET_REQUIRED")
    _mkdir(Path(target).parent, exist_ok=True)
    resources.accounting_copy_file(source, target, category=category, exclusive=exclusive)
    return _ref(target)


def _budget_mkdir(path, *, budget, exclusive=True):
    require(budget is resources.get_budget(), "SINGLE_ROOT_BUDGET_REQUIRED")
    _mkdir(path, exist_ok=not exclusive)


def _builder_context(phase):
    resources.get_budget().check()
    return {"pid": os.getpid(), "utc": datetime.now(timezone.utc).isoformat()}


def _synthetic_zero_pcm_pins():
    """Active-from-cycle-0 pre-NBA pins; synthetic zero PCM, never HDL proof.

    Match i2s_tx: carry toggles BCLK; a falling carry samples old slot[5]
    into WS, then advances the 64-slot counter. Frame F is the old slot-63
    falling carry, one observed row before BCLK falls. No business signals
    or reset observations are generated here.
    """
    phase = bclk = ws = slot = 0
    modulus = 1 << 32
    while True:
        yield bclk, ws, 0
        phase += PHASE_STEP
        if phase >= modulus:
            phase -= modulus
            if bclk:
                ws = slot >> 5
                slot = (slot + 1) & 63
            bclk ^= 1


def _materialize_small(admission, output, case_id):
    """New business fixture inside B; reuse frozen structure, never old output.

    Every case has its own raw/window/scenario/app/receipt and input identities.
    B08 expectations are fixed semantic coordinates, not future output hashes.
    """
    if case_id == "B08":
        _checked_ref(B08_SPEC, "B08_SPEC_IDENTITY")
    templates = admission.get("fixture_templates")
    require(type(templates) is dict and set(templates) == set(PIN_SHA), "B_FIXTURE_TEMPLATE_SET")
    for role, ref in templates.items():
        require(ref["sha256"] == PIN_SHA[role], "B_FIXTURE_TEMPLATE_PIN:" + role)
    budget = resources.get_budget()
    io = BinderIO(ROOT, output, budget, _budget_open, _budget_save, _budget_copy, _budget_mkdir)
    _budget_mkdir(output, budget=budget)
    application = document(io.read_reference(templates["application"]))
    request = document(io.read_reference(templates["request"]))
    graph = document(io.read_reference(templates["graph"]))
    seed = document(io.read_reference(templates["seed"]).splitlines()[0])
    port_map = document(io.read_reference(templates["port_map"]))
    require(set(seed["ports"]) == set(port_map["raw_ports"]) and len(seed["ports"]) == 72,
            "B_FIXTURE_72_RAW_PORTS")
    capture_id, rows = seed["capture_id"], 837 if case_id == "B08" else 7
    last, stop_id = rows - 1, "D4_" + case_id + "_SYNTHETIC_STOP"
    start = _builder_context("START")
    plan = document(io.read_reference(templates["midi_plan"]))
    require(plan["events"] == [], "B_FIXTURE_EMPTY_INDEPENDENT_PLAN")
    plan["total_cycles"] = rows - 2
    bodies = {"plan.json": encoded(plan), "bytes.drv": b"",
              "reset.drv": b"0 1\n", "ready.drv": b"0 1\n"}
    stimuli = {name: io.save("stimulus/" + name, body) for name, body in bodies.items()}
    scenario = io.save_json("INDEPENDENT_SCENARIO.json", {
        "origin": "SYNTHETIC_SCHEMA_FIXTURE", "independent_of_observed_trace": True,
        "release_cycle": 0, "stop_cycle": last, "first_core_ps": 25000,
        "core_period_ps": 25000, "expected_frames": [833] if case_id == "B08" else []})
    frame_input = io.save_json("FRAME_INPUT.json", {
        "schema": "M3_R06_FRAME_PLAN_GENERATOR_INPUT_V1", "status": "FROZEN_INDEPENDENT_INPUT",
        "independent_of_observed_trace": True,
        "source_identities": [{"path": scenario["path"], "sha256": scenario["sha256"]},
                              {"path": application["source"]["base"]["path"],
                               "sha256": application["source"]["base"]["sha256"]}],
        "epochs": [{"epoch": 0, "reset_assert_cycle": 0, "release_cycle": 0,
                    "stop_cycle": last, "window_kind": "ACTIVE"}],
        "finish": {"epoch": 0, "cycle": last}})
    parameters = {"CAPTURE_ID": capture_id, "PLAN_STOP_ID": stop_id,
        "STOP_DRIVER_CYCLE": rows - 2, "EXPECTED_FINISH_CORE_CYCLE": last,
        "MAX_CORE_SAMPLES": rows + 16, "MAX_SIM_TIME_PS": rows * 25000 + 1000000}
    window = io.save_json("WINDOW.json", {"schema": "M3_R7D_INDEPENDENT_WINDOW_V1",
        "capture_id": capture_id, "plan_stop_id": stop_id,
        "input_plan_sha256": stimuli["plan.json"]["sha256"], "first_core_ps": 25000,
        "core_period_ps": 25000, "row_count": rows, "finish_cycle": last,
        "finish_time_ps": rows * 25000, "window_parameters": parameters})
    end = io.save_json("END.json", {"schema": "M3_R7A_END_V1", "capture_id": capture_id,
        "plan_stop_id": stop_id, "finish_cycle": last, "time_ps": rows * 25000,
        "row_count": rows, "reason": "PLANNED_WINDOW_END",
        "ledger_status": "NOT_CHECKED_R6_5_REQUIRED", "serial_tail_status": "UNKNOWN_R6_6_REQUIRED"})
    marker = (f"MONITOR_END capture_id={capture_id} cycle={last} time_ps={rows * 25000} "
              f"rows={rows} reason=PLANNED_WINDOW_END\n").encode()
    stdout = io.save("STDOUT.txt", marker * (2 if case_id == "B09" else 1))
    resets = io.save("RESET_EDGES.jsonl", b"".join(encoded({
        "schema": "M3_R7A_RESET_SNAPSHOT_V1", "capture_id": capture_id,
        "kind": kind, "time_ps": at, "edge_seq": seq,
        "values": {"obs_pll_locked": bit, "sys_rst_n": bit, "obs_rst_n": bit}})
        for seq, kind, at, bit in ((1, "INITIAL", 0, "0"), (2, "CHANGE", 10000, "1"))))
    raw_path = output / "RAW.jsonl"
    pin_states = _synthetic_zero_pcm_pins() if case_id == "B08" else None
    with _budget_open(raw_path, "xb", budget=budget, category="raw_plain") as stream:
        for cycle in range(rows):
            budget.check()
            row = copy.deepcopy(seed)
            row.update(source_line=cycle + 1, cycle=cycle, time_ps=(cycle + 1) * 25000,
                       finish=int(cycle == last), epoch=None)
            if case_id == "B08":
                bclk, ws, din = next(pin_states)
                row["ports"].update(i2s_bclk=str(bclk), i2s_lrck=str(ws),
                                    i2s_din=str(din))
                if cycle == 833:
                    row["ports"]["obs_frame_tick"] = "1"
                elif cycle == 834:
                    row["ports"].update(obs_req_valid="1", obs_req_ready="1",
                        obs_req_id=format(42, "032b"), obs_advance_mask="1111",
                        obs_advance_frame_req_id=format(42, "032b"))
                elif cycle == 835:
                    row["ports"].update(obs_cancel="1", obs_raw_cancel_reason="00")
            line = encoded(row)
            require(len(line) <= 4096 and stream.write(line) == len(line), "B_RAW_SHORT_OR_LINE_BOUND")
    raw = io.identify(raw_path, rows * 4096)
    archive, rom_copies, unchanged, replaced = _replace_four_stimuli(
        io, application, graph, bodies, archive_name="SOURCE_APPLICATION_SYNTHETIC_B_R04.zip")
    source = application["source"]
    source["application"], source["stimulus_inputs"] = archive, stimuli
    application["window_reference"] = window
    spec = application["execution_spec"]
    spec["window_parameters"], spec["nonce"] = parameters, uuid.uuid4().hex
    step = next(item for item in spec["steps"] if item["tool"] == "vsim")
    order = ("CAPTURE_ID", "PLAN_STOP_ID", "STOP_DRIVER_CYCLE", "EXPECTED_FINISH_CORE_CYCLE",
             "MAX_CORE_SAMPLES", "MAX_SIM_TIME_PS")
    step["argv"] = [application["tools"]["vsim"]["tool"]["file"]["path"], "-c"] + [
        "-g" + key + "=" + str(parameters[key]) for key in order] + [
        "work.tb_r7a_c9_public_capture", "-do", "run -all; quit -f"]
    application["proposed_plan"] = {"schema": "M3_C9_BOUND_APPLICATION_PLAN_V1",
        "source": copy.deepcopy(source), "tools": copy.deepcopy(application["tools"]),
        "external_inputs": copy.deepcopy(application["external_inputs"]), "window_reference": window,
        "execution": copy.deepcopy(spec), "permission": "NOT_GRANTED", "process_route": "ABSENT"}
    app = io.save_json("APPLICATION_REQUEST.json", application)
    source_closure = io.save_json("SOURCE_CLOSURE.json", {"schema": "M3_R7D_FILE_CLOSURE_V1",
        "files": [source["base"], source["decision"], archive, *source["capture_sources"].values()]})
    rom_closure = io.save_json("ROM_CLOSURE.json", {"schema": "M3_R7D_FILE_CLOSURE_V1",
        "files": [archive, *rom_copies]})
    native = {}
    for tool in application["tools"].values():
        for item in [tool["tool"], *tool.get("dependencies", [])]:
            ref = item["file"]
            key = str(io.path(ref)).casefold()
            require(key not in native or native[key] == ref, "B_NATIVE_IDENTITY_CONFLICT")
            native[key] = ref
    tools = io.save_json("TOOL_CLOSURE.json", {"schema": "M3_R7D_FILE_CLOSURE_V1",
        "files": list(native.values()), "argv": step["argv"], "cwd": spec["cwd"],
        "version": "SYNTHETIC_DECLARATION_ONLY_NOT_EXECUTED"})
    inputs = {"raw": raw, "resets": resets, "end": end, "stdout": stdout,
        "stderr": io.save("STDERR.bin", b""), "frame_input": frame_input,
        "application_request": app, "frame_rules": request["inputs"]["frame_rules"],
        "window_plan": window, "midi_plan": stimuli["plan.json"],
        "source_manifest": source_closure, "rom_manifest": rom_closure, "tool_manifest": tools}
    request = {k: v for k, v in request.items() if k not in
               {"synthetic_application_example", "inputs", "math_inputs"}}
    request.update(inputs=inputs, module_bindings=templates["module_bindings"],
                   origin="SYNTHETIC_SCHEMA_FIXTURE", capture_id=capture_id)
    roles = _declared_roles(request, application)
    now = _builder_context("DECLARATION")
    declared = io.save_json("DECLARED_SYNTHETIC_RECEIPT.json", {
        "schema": "M3_R7D_DECLARED_EXECUTION_V1", "capture_id": capture_id,
        "argv": step["argv"], "cwd": spec["cwd"],
        "bindings": {role: ref["sha256"] for role, ref in roles.items()},
        "exit_code": 0, "timeout": False, "cleanup_complete": True,
        "consumption": {"pid": now["pid"], "group_id": "R13_B_SYNTHETIC_BUILDER_NOT_NATIVE",
                        "started_utc": start["utc"], "ended_utc": now["utc"]}})
    request["math_inputs"] = {"execution_receipt": declared}
    request_ref = io.save_json("CAPTURE_REQUEST.json", request)
    envelope = io.save_json("ENVELOPE.json", {"schema": "N10_M3_UNIFIED_PIPELINE_REQUEST_V1",
        "mode": "PROCESS_CAPTURE", "request": request_ref})
    dependencies = io.copy(templates["r12_dependencies"], "FROZEN_R12_DEPENDENCIES.json")
    control = io.save_json("CONTROL.json", {"schema": "M3_R13_BACKEND_CONTROL_V1",
        "run_id": case_id, "run_kind": "SYNTHETIC_SOFTWARE", "envelope_ref": envelope,
        "dependencies_ref": dependencies, "quota_bytes": EXPECTED_BUDGETS["all_stores"],
        "volume_policy": "GZIP_32M_PARTS_IO_1M", "authority": {
            "execution_allowed": False, "real_verified": False,
            "math_verified": False, "board_release_allowed": False}})
    origin = io.save_json("ORIGIN.json", {"schema": "M3_R13_B_FIXTURE_ORIGIN_V1",
        "case": case_id, "scenario": scenario, "raw": raw, "window": window,
        "new_source_archive": archive, "source_members_unchanged": unchanged,
        "replaced_stimuli": replaced, "builder": now, "native_tool_calls": 0,
        "receipt_is_synthetic_declaration_not_native_execution": True,
        "expected_outputs_precomputed": False, "old40_plus2_replayed": False,
        "B08_spec": {"path": str(B08_SPEC["path"]), "bytes": B08_SPEC["bytes"],
                     "sha256": B08_SPEC["sha256"]} if case_id == "B08" else None})
    return {"control_ref": control, "inputs": inputs, "origin_ref": origin, "rows": rows,
            "postcondition": {"minimum_rows": rows, "terminal": {"rows": rows, "finish_count": 1,
                "last_cycle": last, "monitor_end_count": 1}, "public_role": "public_rows",
                "advance_role": "math_advance_history", "cancel_evidence_role": "intake_ledger",
                "serial_role": "serial", "frame_plan_role": "frame_plan",
                "fixture_spec": {"path": str(B08_SPEC["path"]), "bytes": B08_SPEC["bytes"],
                                 "sha256": B08_SPEC["sha256"]},
                "parent_process_tree_receipt_required": True}}


def _append_raw(path, body):
    with resources.accounting_open(path, "ab", category="raw_plain") as stream:
        require(stream.write(body) == len(body), "FAULT_APPEND_SHORT_WRITE")


def _artifact(complete, role):
    values = complete["audit"]["artifacts"]
    require(role in values, "POST_ARTIFACT_ROLE:" + role)
    return values[role]


def _artifact_stream(case_out, artifact):
    path = Path(artifact["path"])
    path = path if path.is_absolute() else case_out / path
    if artifact["storage"] == "VOLUME":
        return VolumeStore(case_out).open(path, "rb", {k: artifact[k] for k in ("bytes", "sha256")})
    require(identity(path) == {k: artifact[k] for k in ("bytes", "sha256")}, "POST_PLAIN_IDENTITY")
    return resources.accounting_open(path, "rb")


def _logical_records(case_out, artifact):
    require(artifact["bytes"] <= 8 * CHUNK, "SMALL_POSTCONDITION_BOUND")
    values = []
    with _artifact_stream(case_out, artifact) as stream:
        while True:
            line = stream.readline(CHUNK)
            if not line:
                break
            require(line.endswith(b"\n"), "POST_JSONL_TRUNCATED")
            values.append(parse_json(line))
    return values


def _contains_subset(value, expected):
    if isinstance(expected, dict):
        return isinstance(value, dict) and all(k in value and _contains_subset(value[k], v)
                                              for k, v in expected.items())
    return value == expected


def _somewhere(value, expected):
    if _contains_subset(value, expected):
        return True
    if isinstance(value, dict):
        return any(_somewhere(v, expected) for v in value.values())
    if isinstance(value, list):
        return any(_somewhere(v, expected) for v in value)
    return False


def _artifact_values(case_out, artifact):
    if artifact["path"].endswith(".jsonl"):
        return _logical_records(case_out, artifact)
    raw = _drain(_artifact_stream(case_out, artifact))
    require(len(raw) <= 8 * CHUNK, "SMALL_POSTCONDITION_BOUND")
    return parse_json(raw)


def _nested_artifact(case_out, ref):
    path = _resolve(ref)
    store = VolumeStore(case_out)
    return {"path": str(path), "bytes": ref["bytes"], "sha256": ref["sha256"],
            "storage": "VOLUME" if store.is_volume(path) else "PLAIN"}


def _check_small_post(case_id, final_dir, complete, fixture):
    post = fixture["postcondition"]
    terminal = complete["audit"]["terminal"]
    require(terminal == post["terminal"], "B_TERMINAL_SOURCE:" + case_id)
    public = _logical_records(final_dir, _artifact(complete, "public_rows"))
    decoded = _logical_records(final_dir, _artifact(complete, "csv_roundtrip"))
    require(len(public) == fixture["rows"] and public == decoded and
            all(len(r["fields"]) == 74 and len(r["raw_ports"]) == 72 for r in public),
            "B_PUBLIC_CSV_74_72")
    indexes = _logical_records(final_dir, _produced_file(final_dir, "chain/capture/RAW_PUBLIC_LINE_INDEX.jsonl"))
    with resources.accounting_open(_resolve(fixture["inputs"]["raw"]), "rb") as stream:
        raw_lines = list(stream)
    with _artifact_stream(final_dir, _artifact(complete, "public_rows")) as stream:
        public_lines = list(stream)
    require(len(indexes) == len(public) == len(raw_lines), "B_RAW_PUBLIC_INDEX_COVERAGE")
    require(len(public_lines) == len(public), "B_PHYSICAL_PUBLIC_LINE_COUNT")
    for n, (raw_line, row, idx, public_line) in enumerate(zip(raw_lines, public, indexes, public_lines), 1):
        require(row["raw_ports"] == parse_json(raw_line)["ports"] and
                idx["line"] == n and idx["raw_line_sha256"] == hashlib.sha256(raw_line).hexdigest()
                and idx["public_line_sha256"] == hashlib.sha256(public_line).hexdigest(),
                "B_RAW_PUBLIC_LINE_INDEX")
    if case_id == "B08":
        _check_success_postcondition(case_id, final_dir, complete, post)
    if case_id == "B11":
        budget = resources.get_budget().receipt()
        require(budget["unclosed_writers"] == 0 and budget["max_physical_write"] <= CHUNK,
                "B11_GLOBAL_WRITER_CLOSURE")
        census = resources.disk_snapshot(OUTPUT)
        require(census["tree_bytes"] <= resources.WORKSPACE_LIMIT,
                "B11_GLOBAL_ALL_OUTPUT_RESOURCE")
        return {"terminal": terminal, "global_budget": budget, "all_output_census": census,
                "parent_peak_and_Job_receipt_required": True}
    return {"terminal": terminal, "artifact_actual_identities": complete["audit"]["artifacts"],
            "input_raw": fixture["inputs"]["raw"], "parent_Job0_required": True}


def _w_export_inventory(roots):
    files, directories = [], []
    def fail_walk(error):
        raise error
    for role, source_root in roots:
        source_root = Path(source_root).absolute()
        require(source_root != OUTPUT and source_root.is_relative_to(OUTPUT)
                and source_root.is_dir(), "W_EXPORT_SOURCE_SCOPE")
        for current, children, names in os.walk(source_root, followlinks=False, onerror=fail_walk):
            resources.get_budget().check()
            current = Path(current)
            for candidate in [current, *(current / n for n in children),
                              *(current / n for n in names)]:
                stamp = candidate.lstat()
                require(not candidate.is_symlink() and
                        not (getattr(stamp, "st_file_attributes", 0) & 0x400),
                        "W_EXPORT_LINK_OR_REPARSE")
            directories.append({"source_root_role": role,
                "path": current.relative_to(ROOT).as_posix()})
            for name in sorted(names):
                candidate = current / name
                require(candidate.is_file(), "W_EXPORT_NONREGULAR_FILE")
                files.append((role, candidate))
    files.sort(key=lambda item: item[1].relative_to(ROOT).as_posix())
    directories.sort(key=lambda item: item["path"])
    require(files and len({str(p) for _, p in files}) == len(files),
            "W_EXPORT_EMPTY_OR_DUPLICATE")
    return files, directories


def _w_export_identity(path):
    budget = resources.get_budget()
    before = Path(path).stat()
    digest, count = hashlib.sha256(), 0
    with resources.accounting_open(path, "rb") as stream:
        while True:
            budget.check()
            block = stream.read(CHUNK)
            if not block:
                break
            require(len(block) <= CHUNK, "W_EXPORT_READ_BOUND")
            count += len(block)
            require(count <= before.st_size, "W_EXPORT_SOURCE_GREW")
            digest.update(block)
    after = Path(path).stat()
    require(count == before.st_size and
            (before.st_size, before.st_mtime_ns, before.st_ctime_ns,
             before.st_dev, before.st_ino) ==
            (after.st_size, after.st_mtime_ns, after.st_ctime_ns,
             after.st_dev, after.st_ino), "W_EXPORT_SOURCE_CHANGED_DURING_READ")
    budget.check()
    return {"path": Path(path).relative_to(ROOT).as_posix(),
            "bytes": count, "sha256": digest.hexdigest()}


def _export_w_originals(admission, final_dir, input_dir, actual_input):
    # Runs only from W's charged worker, after actual entry/final audit.
    # No compression, source rewriting, deletion, retry or fresh deadline.
    budget = resources.get_budget()
    _delivery_ready(admission)
    roots = [("actual_final_dir", final_dir), ("W_inputs", input_dir)]
    files, directories = _w_export_inventory(roots)
    frozen = [(role, path, _w_export_identity(path)) for role, path in files]
    raw_frozen = [ref for _, _, ref in frozen if ref["path"] == actual_input["path"]]
    require(raw_frozen == [actual_input], "W_EXPORT_ACTUAL_RAW_NOT_FROZEN")
    destination = OUTPUT / "DELIVERY" / "W01"
    _mkdir(destination, exist_ok=False)
    all_digest, total, global_sequence = hashlib.sha256(), 0, 0
    originals, parts = [], []
    for file_sequence, (role, path, expected) in enumerate(frozen, 1):
        budget.check()
        digest, copied, file_parts = hashlib.sha256(), 0, []
        with resources.accounting_open(path, "rb") as source:
            while copied < expected["bytes"]:
                global_sequence += 1
                part_path = destination / (f"original-{file_sequence:06d}-"
                                           f"part-{len(file_parts) + 1:06d}.bin")
                part_digest, part_count = hashlib.sha256(), 0
                offset, stream_offset = copied, total
                with resources.accounting_open(part_path, "xb", category="delivery") as target:
                    while (part_count < 32 * CHUNK and copied < expected["bytes"]):
                        budget.check()
                        request = min(CHUNK, 32 * CHUNK - part_count,
                                      expected["bytes"] - copied)
                        block = source.read(request)
                        require(0 < len(block) <= request, "W_EXPORT_SOURCE_TRUNCATED")
                        require(target.write(block) == len(block), "W_EXPORT_SHORT_WRITE")
                        part_digest.update(block)
                        digest.update(block)
                        all_digest.update(block)
                        part_count += len(block)
                        copied += len(block)
                        total += len(block)
                descriptor = {"path": part_path.relative_to(ROOT).as_posix(),
                              "bytes": part_count, "sha256": part_digest.hexdigest()}
                require(_w_export_identity(part_path) == descriptor,
                        "W_EXPORT_PART_READBACK_IDENTITY")
                part = {"sequence": len(file_parts) + 1,
                    "stream_sequence": global_sequence, "offset": offset,
                    "stream_offset": stream_offset, **descriptor}
                file_parts.append(part)
                parts.append(part)
            require(source.read(1) == b"", "W_EXPORT_SOURCE_GREW")
        require(copied == expected["bytes"] and digest.hexdigest() == expected["sha256"],
                "W_EXPORT_SOURCE_IDENTITY_CHANGED")
        originals.append({"file_sequence": file_sequence, "source_root_role": role,
            "source": expected, "stream_offset": total - copied,
            "parts": file_parts, "empty_file": copied == 0,
            "restore": "Create original repo-relative path; concatenate parts by sequence. "
                       "Do not decode internal gzip volumes, JSON manifests or markers."})
    require(_w_export_inventory(roots) == (files, directories),
            "W_EXPORT_SOURCE_TREE_CHANGED")
    for _, path, expected in frozen:
        require(_w_export_identity(path) == expected, "W_EXPORT_TERMINAL_SOURCE_CHANGED")
    require(_w_export_inventory(roots) == (files, directories),
            "W_EXPORT_TERMINAL_TREE_CHANGED")
    budget.check()
    manifest = {"schema": "M3_R13_W_DELIVERY_ORIGINALS_V1",
        "status": "EXPORT_VERIFIED_PENDING_USER_TRANSFER", "run_id": "W01",
        "channel": admission["delivery"], "channel_confirmed": True,
        "delivery_root": destination.relative_to(ROOT).as_posix(),
        "source_roots": [{"role": role, "path": Path(p).relative_to(ROOT).as_posix()}
                         for role, p in roots],
        "directories": directories, "originals": originals,
        "full_stream": {"order": "originals.file_sequence then parts.sequence",
            "bytes": total, "sha256": all_digest.hexdigest(),
            "files": len(originals), "parts": len(parts)},
        "part_bytes_limit": 32 * CHUNK, "physical_io_bytes_limit": CHUNK,
        "offset_base": 0, "sequence_base": 1, "part_category": "delivery",
        "manifest_category": "control", "copied_bytes_are_unmodified": True,
        "terminal_all_sources_rehashed": True, "retries": 0,
        "instantaneous_ABA_not_observable": True,
        "remote_received": False, "accepted": False, "integrated": False}
    raw = (json.dumps(manifest, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False) + "\n").encode("utf-8")
    require(len(raw) <= 8 * CHUNK, "W_EXPORT_MANIFEST_CONTROL_BOUND")
    manifest_path = destination / "MANIFEST.json"
    resources.accounting_save_bytes(manifest_path, raw, category="control", exclusive=True)
    manifest_ref = {"path": manifest_path.relative_to(ROOT).as_posix(),
                    "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
    require(_w_export_identity(manifest_path) == manifest_ref,
            "W_EXPORT_MANIFEST_READBACK_IDENTITY")
    budget.check()
    return {"status": manifest["status"], "manifest": manifest_ref,
        "delivery_root": manifest["delivery_root"], "channel": manifest["channel"],
        "full_stream": manifest["full_stream"], "all_physical_parts": parts,
        "terminal_all_sources_rehashed": True, "remote_received": False}


def _actual_cases(group, admission, output, wanted_override=None):
    if group == "W":
        bound = bind_w_inputs(admission["w_input_freeze_ref"], root=ROOT,
            output=output / "inputs" / "W01", budget=resources.get_budget(),
            open_file=_budget_open, save_bytes=_budget_save, copy_file=_budget_copy,
            mkdir=_budget_mkdir, builder_context=_builder_context)
        final_dir = output / "cases" / "W01"
        actual_input = {}
        def observe_actual_input(event, payload):
            if event == "after_backend_before_final_verify":
                actual_input.update(payload["result"]["inputs"]["raw"])
                require(actual_input == bound["inputs"]["raw"], "W01_ACTUAL_RESULT_INPUT_BINDING")
        entry.install_test_hook(observe_actual_input)
        try:
            complete = entry.run(_resolve(bound["control_ref"]), bound["control_ref"]["sha256"], final_dir)
        finally:
            entry.install_test_hook(None)
        require(actual_input, "W01_ACTUAL_BACKEND_INPUT_NOT_OBSERVED")
        terminal = complete["audit"]["terminal"]
        # raw is an input of the actual result, never a fabricated output role.
        require(terminal["rows"] >= MIN_ROWS and actual_input["bytes"] >= MIN_RAW_BYTES,
                "W01_FULL_WINDOW_GEOMETRY")
        delivery = _export_w_originals(admission, final_dir, output / "inputs" / "W01", actual_input)
        return [{"id": "W01", "status": "PASS", "observed": {
            "control": bound["control_ref"], "raw_input": actual_input,
            "delivery": delivery, "terminal": terminal, "whole_output_resources": resources.disk_snapshot(OUTPUT),
            "global_budget": resources.get_budget().receipt(), "parent_peak_Job0_required": True}}]
    wanted = list(wanted_override or [c for c in GROUPS["B"] if c not in {"B02", "B03", "B04"}])
    outcomes = []
    baseline = None  # Successful B01 from this call only; never discover an old run.
    for case_id in wanted:
        if baseline is not None and case_id in {"B07", "B10", "B11"}:
            fixture, final_dir, complete, complete_ref = baseline
            for ref in (complete_ref, fixture["control_ref"], fixture["origin_ref"],
                        fixture["inputs"]["raw"]):
                _checked_ref(ref, "B_REUSED_BASELINE_CHANGED")
            observed = _check_small_post(case_id, final_dir, complete, fixture)
            observed.update(baseline_case_id="B01", reused_actual_execution=True,
                            baseline_complete=complete_ref)
            outcomes.append({"id": case_id, "status": "PASS", "observed": observed,
                             "control": fixture["control_ref"],
                             "fixture_origin": fixture["origin_ref"]})
            continue
        fixture = _materialize_small(admission, output / "inputs" / case_id, case_id)
        raw_path = _resolve(fixture["inputs"]["raw"])
        final_dir = output / "cases" / case_id
        fault = OSError("R13_B05_INJECTED_READER")
        seen = {"events": [], "injected": False, "fault_count": None,
                "reader": None, "after_fault_pulls": 0, "backend_returned": False}
        expected_error = {"B05": "R13_B05_INJECTED_READER", "B06": "R12_STREAM_SIZE_CHANGED",
                          "B09": "MONITOR_END_UNIQUE_REQUIRED",
                          "B12": "FINAL_INPUT_IDENTITY_CHANGED"}.get(case_id)
        def reader_hook(event, payload):
            if Path(payload["path"]).resolve() != raw_path:
                return
            seen["events"].append({"event": event, "count": payload["count"],
                                   "eof": payload["eof"], "closed": payload.get("closed"),
                                   "selected_reader": payload["reader"] is seen["reader"]})
            if (seen["injected"] and payload["reader"] is seen["reader"]
                    and event in {"reader_before_pull", "reader_after_pull"}):
                seen["after_fault_pulls"] += 1
            if (not seen["injected"] and event == "reader_after_pull" and
                    payload["count"] > 0 and not payload["eof"] and
                    getattr(payload["reader"], "expected", None) is not None):
                seen.update(injected=True, fault_count=payload["count"], reader=payload["reader"])
                if case_id == "B05":
                    raise fault
                if case_id == "B06":
                    _append_raw(raw_path, b"X")
        def entry_hook(event, payload):
            if event == "after_backend_before_final_verify":
                seen["backend_returned"] = True
                require(Path(payload["final_dir"]).resolve() == final_dir.resolve(), "B12_TARGET_SCOPE")
                require(_resolve(payload["result"]["inputs"]["raw"]) == raw_path,
                        "B12_ACTUAL_RESULT_INPUT_RAW")
                _append_raw(raw_path, b"X")
        binding.install_test_hook(reader_hook if case_id in {"B05", "B06"} else None)
        entry.install_test_hook(entry_hook if case_id == "B12" else None)
        caught, complete = None, None
        try:
            complete = entry.run(_resolve(fixture["control_ref"]), fixture["control_ref"]["sha256"], final_dir)
        except BaseException as error:
            caught = error
        finally:
            binding.install_test_hook(None)
            entry.install_test_hook(None)
        if expected_error:
            require(caught is not None and expected_error in str(caught),
                    "BUSINESS_EXACT_REJECTION:" + case_id + ":" + str(caught))
            require(not (final_dir / "COMPLETE.json").exists() and
                    not (final_dir / "COMPLETE.pending.json").exists(), "BUSINESS_FAILURE_BARRIER:" + case_id)
            failure = read_control(final_dir / "R13_FAILURE.json")["value"]
            require(failure["completion_written"] is False and expected_error in failure["error"],
                    "BUSINESS_FAILURE_RECEIPT:" + case_id)
            if case_id == "B05":
                require(caught is fault and seen["injected"] and seen["reader"] is not None
                        and seen["after_fault_pulls"] == 0 and seen["reader"].drained == 0,
                        "B05_ORIGINAL_EXCEPTION_NO_DRAIN")
                closes = [r for r in seen["events"] if r["event"] == "reader_after_close" and r["selected_reader"]]
                require(closes and all(r["count"] == seen["fault_count"] and r["closed"] is True
                                       and r["eof"] is False for r in closes), "B05_ACTUAL_CLOSE_NO_DRAIN")
            if case_id == "B06":
                require(seen["injected"], "B06_ACTUAL_READER_BOUNDARY_NOT_ENTERED")
            if case_id == "B12":
                require(seen["backend_returned"], "B12_ACTUAL_BACKEND_NOT_ENTERED")
            observed = {"error": type(caught).__name__ + ":" + str(caught),
                "events": seen["events"], "backend_returned": seen["backend_returned"],
                "exact_original_exception": caught is fault if case_id == "B05" else None,
                "COMPLETE_absent": True, "mutated_own_input": str(raw_path)}
        else:
            if caught is not None:
                raise caught.with_traceback(caught.__traceback__)
            require((final_dir / "COMPLETE.json").is_file() and complete is not None
                    and complete["status"] == "COMPLETE_SOFTWARE_ONLY", "BUSINESS_COMPLETE_MARKER")
            observed = _check_small_post(case_id, final_dir, complete, fixture)
            if case_id == "B01":
                baseline = (fixture, final_dir, complete, _ref(final_dir / "COMPLETE.json"))
        outcomes.append({"id": case_id, "status": "PASS", "observed": observed,
                         "control": fixture["control_ref"], "fixture_origin": fixture["origin_ref"]})
    if wanted_override is None:
        outcomes += [{"id": case_id, "status": "DEFERRED_TO_PARENT_JOB_RECEIPT",
            "observed": {"parent_actual_Job_receipt_required": True,
                         "scenario": {"B02": "NATURAL_EXIT_AND_JOB0", "B03": "DESCENDANT_OBSERVATION",
                                      "B04": "TIMEOUT_CLEANUP"}[case_id]}}
            for case_id in ("B02", "B03", "B04")]
    return sorted(outcomes, key=lambda r: r["id"])


def _produced_file(final_dir, relative):
    path = strict_child(final_dir, final_dir / relative)
    store = VolumeStore(final_dir)
    stamp = store.descriptor(path) if store.is_volume(path) else identity(path)
    return {"path": str(path), **stamp, "storage": "VOLUME" if store.is_volume(path) else "PLAIN"}


def _check_success_postcondition(case_id, case_out, complete, post):
    require(case_id == "B08" and identity(B08_SPEC["path"]) ==
            {"bytes": B08_SPEC["bytes"], "sha256": B08_SPEC["sha256"]}, "B08_SPEC_IDENTITY")
    require(complete["audit"]["terminal"] == {"rows": 837, "finish_count": 1,
            "last_cycle": 836, "monitor_end_count": 1}, "B08_TERMINAL_837")
    public = _logical_records(case_out, _artifact(complete, "public_rows"))
    require(len(public) == 837 and all(len(r["fields"]) == 74 and len(r["raw_ports"]) == 72
                                     for r in public), "B08_PUBLIC_837_74_72")
    require(sum(r["fields"]["frame_tick"] == 1 for r in public) == 1 and
            sum(r["fields"]["req_valid"] == r["fields"]["req_ready"] == 1 for r in public) == 1 and
            sum(r["fields"]["cancel"] == 1 for r in public) == 1 and
            sum(r["fields"]["finish"] == 1 for r in public) == 1 and
            sum(r["fields"]["advance_mask"] != 0 for r in public) == 1, "B08_PUBLIC_EVENT_COUNTS")
    for cycle, expected in ((833, {"frame_tick": 1, "finish": 0}),
            (834, {"req_valid": 1, "req_ready": 1, "req_id": 42, "advance_mask": 15,
                   "advance_frame_req_id": 42, "cancel": 0, "finish": 0}),
            (835, {"cancel": 1, "cancel_reason": 0, "advance_mask": 0, "finish": 0}),
            (836, {"finish": 1, "frame_tick": 0, "cancel": 0})):
        require(_contains_subset(public[cycle]["fields"], {"cycle": cycle, **expected}),
                "B08_PUBLIC_CYCLE_SEQUENCE:" + str(cycle))
    advances = _logical_records(case_out, _artifact(complete, "math_advance_history"))
    require(len(advances) == 1 and _contains_subset(advances[0], {
        "source": {"line": 835, "cycle": 834, "epoch": 0, "time_ps": 20875000,
                   "sampling_phase": "POSEDGE_PRE_NBA"},
        "advance": {"raw_mask": 15, "all_four_lanes": True, "status": "ALL_FOUR_LANES"},
        "request_tag": 42, "req_id": 42, "commit_observed_same_row": 0, "cancel_raw": 0,
        "retained_even_if_unpublished_or_cancelled": True}), "B08_EXACT_ADVANCE_HISTORY")
    ledger = _artifact_values(case_out, _artifact(complete, "intake_ledger"))
    require(_somewhere(ledger["frames"], {"req_id": 42,
                "F": {"cycle": 833, "source_line": 834},
                "A": {"cycle": 834, "source_line": 835}}) and
            _somewhere(ledger["raw_frame_cancels"], {"cycle": 835, "source_line": 836,
                "raw_cancel_reason": 0, "business_cancel_derived": False}) and
            ledger["business_cancels"] == [], "B08_INTAKE_CANCEL_RETENTION")
    calendar = _artifact_values(case_out, _artifact(complete, "calendar"))
    require(_somewhere(calendar, {"epoch": 0, "req_id": 42,
            "F": {"cycle": 833, "source_line": 834},
            "A": {"cycle": 834, "source_line": 835}}), "B08_CALENDAR_FRAME_ACCEPT")
    serial = _artifact_values(case_out, _artifact(complete, "serial"))
    require(_contains_subset(serial["counts"], {"rows": 837, "FRAME_F": 1,
            "accepted": 1, "result": 0, "commit": 0}), "B08_SERIAL_COUNTS")
    transactions = _logical_records(case_out, _nested_artifact(case_out, serial["artifacts"]["transactions"]))
    cancelled = [r for r in transactions if r["kind"] == "CANCEL"]
    require(len(cancelled) == 1 and _contains_subset(cancelled[0], {
        "source_line": 836, "cycle": 835, "epoch": 0, "time_ps": 20900000,
        "kind": "CANCEL", "raw_reason": 0,
        "entry": {"epoch": 0, "id": 42, "F": 833, "V": 834, "A": 834,
                  "request_cycle": 834, "accept_source_line": 835}}), "B08_SERIAL_CANCEL")
    frame = _artifact_values(case_out, _artifact(complete, "frame_plan"))
    require(len(frame["epochs"]) == 1 and frame["epochs"][0]["cycles"] == [833] and
            frame["epochs"][0]["release_cycle"] == 0 and
            frame["epochs"][0]["stop_cycle"] == 836 and
            frame["finish"] == {"epoch": 0, "cycle": 836}, "B08_INDEPENDENT_FRAME_PLAN")
    # Output hashes are measured by the real completion audit AFTER execution.
    # None are preconditions for constructing this independent semantic case.


# Root-adopted W binder. All generated input work remains inside W.
"""R03 static candidate: root-owned W input binding, never a launcher.

No module import has been performed for validation. Merge the selected helpers
into the existing C selftest only after root self-audit. All actual file IO is
injected; no timer, tool, subprocess, Git or target algorithm runs here.
"""

import copy
from datetime import datetime
import hashlib
import io as binary_io
import json
from pathlib import Path, PurePosixPath
import re
import zipfile

CHUNK = 1 << 20
MAX_CONTROL = 8 * CHUNK
MIN_ROWS = 1_130_662
MIN_RAW_BYTES = 1_398_627_657
RAW_MAX = 4_631_191_552
PHASE_STEP = 659_706_977
RAW_SCHEMA = "M3_R7A_C9_RAW_CORE_ROW_V1"
PORT_MAP_SHA = "65a4fcca8b83ab72eaed3aaf5bf7cd48db18ad0691027aaaf57d1e9e4ced0807"
EXPECTED_BUDGETS = {"all_stores": 8 << 30, "delivery": 8 << 30,
                    "raw_plain": RAW_MAX, "all_other": 3_958_743_040}
PIN_SHA = {
    "recipe": "2e880fc06e4a34d1c62d7f409193d909f3999257464e62c362e21acf601961d4",
    "seed": "2188b80bbe4561c44a1728fabc50dbb0bd9b6101582700799d537f0443631882",
    "port_map": PORT_MAP_SHA,
    "application": "d49c15e629a700b929c67f8ec0de2e18eb323cfba1866175e3d82eb016107f08",
    "request": "977f31e7157aa2141da9e6402142a78ed886dfeadeb40949043335e12c276b77",
    "graph": "3f293f01cb31bdb82f64526e7b5d295a1fb87ed86225ca4824b4a21392c8b959",
    "r12_dependencies": "73525eaa939c0b9627e42d9e763d93e206028102d8e7fed07350a493a8aac731",
    "module_bindings": "dc66002f2a14017ae7abb439ea683b9b2dc1dfca18a35c6b07b43e6a37d661f8",
    "midi_plan": "35a723e210a2cce83bdb5b346855beb0fca3fe3a5c806c247cdd8ffc8bc0a59a",
}


class BinderPending(ValueError):
    pass


def need(ok, reason):
    if not ok:
        raise BinderPending("W_INPUT_BINDER_PENDING:" + reason)


def pairs(items):
    result = {}
    for key, value in items:
        need(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def encoded(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=False, allow_nan=False) + "\n").encode("utf-8")


def document(raw):
    return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                      parse_constant=lambda _: need(False, "NONFINITE_JSON"))


class BinderIO:
    """Hooks must enforce global writer limits and no aliases, including ZIP.

    open_file(path,mode,*,budget,category) -> seekable binary context manager.
    save_bytes(path,body,*,budget,category,exclusive) -> descriptor.
    copy_file(source,target,*,budget,category,exclusive) -> descriptor.
    mkdir(path,*,budget,exclusive) -> None.
    Categories raw_plain/all_other debit the root's existing shared allocation.
    Hook checks happen on every physical operation; wrappers add <=1MiB calls.
    """
    def __init__(self, root, output, budget, open_file, save_bytes, copy_file, mkdir):
        self.root, self.output = Path(root).resolve(), Path(output).resolve()
        self.budget, self.open_file = budget, open_file
        self.save_bytes, self.copy_file, self.mkdir_hook = save_bytes, copy_file, mkdir
        scope = self.root / "code/output/m3_backend_stream_r13_20261018"
        need(self.output != scope and self.output.is_relative_to(scope), "OUTPUT_SCOPE")
        need(all(callable(x) for x in (open_file, save_bytes, copy_file, mkdir)),
             "ALL_IO_HOOKS_REQUIRED")

    def path(self, descriptor):
        need(type(descriptor) is dict and set(descriptor) == {"path", "bytes", "sha256"},
             "DESCRIPTOR_FIELDS")
        need(type(descriptor["bytes"]) is int and descriptor["bytes"] >= 0
             and isinstance(descriptor["sha256"], str)
             and re.fullmatch("[0-9a-f]{64}", descriptor["sha256"]), "DESCRIPTOR_IDENTITY")
        path = Path(descriptor["path"])
        return (path if path.is_absolute() else self.root / path).resolve()

    def ref(self, path, count, digest):
        path = Path(path).resolve()
        return {"path": path.relative_to(self.root).as_posix()
                if path.is_relative_to(self.root) else str(path),
                "bytes": count, "sha256": digest}

    def identify(self, path, limit):
        digest, count = hashlib.sha256(), 0
        self.budget.check()
        with self.open_file(Path(path), "rb", budget=self.budget,
                            category="all_other") as stream:
            while True:
                self.budget.check()
                block = stream.read(CHUNK)
                if not block:
                    break
                count += len(block)
                need(len(block) <= CHUNK and count <= limit, "IDENTITY_BYTE_BOUND")
                digest.update(block)
        self.budget.check()
        return self.ref(path, count, digest.hexdigest())

    def verified(self, ref):
        actual = self.identify(self.path(ref), ref["bytes"])
        need(actual["bytes"] == ref["bytes"] and actual["sha256"] == ref["sha256"],
             "FROZEN_FILE_CHANGED:" + ref["path"])
        return actual

    def read_reference(self, ref):
        self.path(ref)
        need(ref["bytes"] <= MAX_CONTROL, "CONTROL_BOUND")
        digest, body = hashlib.sha256(), bytearray()
        with self.open_file(self.path(ref), "rb", budget=self.budget,
                            category="all_other") as stream:
            while True:
                self.budget.check()
                block = stream.read(CHUNK)
                if not block:
                    break
                body.extend(block)
                need(len(block) <= CHUNK and len(body) <= ref["bytes"], "CONTROL_BOUND")
                digest.update(block)
        need(len(body) == ref["bytes"] and digest.hexdigest() == ref["sha256"],
             "CONTROL_IDENTITY")
        self.budget.check()
        return bytes(body)

    def save(self, name, body):
        path = (self.output / name).resolve()
        need(path != self.output and path.is_relative_to(self.output), "SAVE_SCOPE")
        need(isinstance(body, bytes) and len(body) <= MAX_CONTROL, "SAVE_CONTROL_BOUND")
        self.budget.check()
        result = self.save_bytes(path, body, budget=self.budget,
                                 category="all_other", exclusive=True)
        need(result == self.ref(path, len(body), hashlib.sha256(body).hexdigest()),
             "SAVE_HOOK_DESCRIPTOR")
        self.verified(result)
        return result

    def save_json(self, name, value):
        return self.save(name, encoded(value))

    def copy(self, ref, name):
        source = self.path(ref)
        self.verified(ref)
        target = (self.output / name).resolve()
        need(target != self.output and target.is_relative_to(self.output), "COPY_SCOPE")
        result = self.copy_file(source, target, budget=self.budget,
                                category="all_other", exclusive=True)
        need(result == self.ref(target, ref["bytes"], ref["sha256"]), "COPY_HOOK_DESCRIPTOR")
        self.verified(result)
        return result


class _ZipIO:
    """Only bounded ZIP archive IO, never a target/facade monkeypatch."""
    def __init__(self, stream, budget):
        self.stream, self.budget = stream, budget

    def read(self, size=-1):
        if size is None or size < 0:
            here = self.tell()
            end = self.seek(0, 2)
            self.seek(here)
            size = end - here
        need(type(size) is int and 0 <= size <= 64 * CHUNK, "ZIP_READ_BOUND")
        parts, remaining = [], size
        while remaining:
            self.budget.check()
            block = self.stream.read(min(CHUNK, remaining))
            need(len(block) <= min(CHUNK, remaining), "ZIP_READ_CHUNK")
            if not block:
                break
            parts.append(block)
            remaining -= len(block)
        self.budget.check()
        return b"".join(parts)

    def write(self, body):
        view, offset = memoryview(body).cast("B"), 0
        while offset < len(view):
            self.budget.check()
            chunk = view[offset:offset + CHUNK]
            need(self.stream.write(chunk) == len(chunk), "ZIP_SHORT_WRITE")
            offset += len(chunk)
        self.budget.check()
        return len(view)

    def seek(self, offset, whence=0):
        self.budget.check()
        result = self.stream.seek(offset, whence)
        self.budget.check()
        return result

    def tell(self):
        self.budget.check()
        return self.stream.tell()

    def flush(self):
        self.stream.flush()
        self.budget.check()

    def seekable(self):
        return True


class _PlainRawSink:
    def __init__(self, io):
        self.io, self.path = io, io.output / "RAW.jsonl"
        self.manager = io.open_file(self.path, "xb", budget=io.budget, category="raw_plain")
        self.stream = self.manager.__enter__()
        self.digest, self.count, self.closed = hashlib.sha256(), 0, False

    def write(self, line):
        need(not self.closed and isinstance(line, bytes) and 0 < len(line) <= 4096
             and line.endswith(b"\n"), "RAW_LINE_BOUND")
        need(self.count + len(line) <= RAW_MAX, "RAW_TOTAL_BOUND")
        self.io.budget.check()
        need(self.stream.write(line) == len(line), "RAW_SHORT_WRITE")
        self.digest.update(line)
        self.count += len(line)
        self.io.budget.check()
        return len(line)

    def finish(self):
        need(not self.closed, "RAW_CLOSED")
        self.manager.__exit__(None, None, None)
        self.closed = True
        expected = self.io.ref(self.path, self.count, self.digest.hexdigest())
        self.io.verified(expected)
        self.io.budget.check()
        return expected

    def abort(self):
        if not self.closed:
            self.closed = True
            self.manager.__exit__(None, None, None)
        # No delete, drain or finish marker. Preserve all partial bytes.


def frame_cycle(k):
    # Input synthesis uses the frozen independent formula. It does not write
    # UNIQUE_FRAME_PLAN, FRAME_PLAN or TX_FRAME_PLAN. Real producer stays D4's.
    return (128 * k * (1 << 32) + PHASE_STEP - 1) // PHASE_STEP - 1


def produce_inputs(recipe_ref, seed_ref, port_map_ref, *,
                   sink_factory, put_control, budget, read_reference):
    """Storage-only hooks: sink_factory(role) and put_control(name, raw_bytes).

    Returned logical raw must be resolved byte-for-byte by the C IO adapter.
    Every generated byte, compression, hash and subsequent D4 work uses the SAME
    caller-owned 900-second Budget. This function never starts a fresh timer.
    """
    budget.check()
    recipe = json.loads(read_reference(recipe_ref).decode("utf-8"),
                        object_pairs_hook=pairs)
    need(recipe["schema"] == "M3_R13_SYNTHETIC_WINDOW_RECIPE_V1", "RECIPE_SCHEMA")
    need(recipe["origin"] == "SYNTHETIC_SCHEMA_FIXTURE", "SYNTHETIC_ONLY")
    rows = recipe["rows"]
    need(type(rows) is int and MIN_ROWS <= rows <= MIN_ROWS, "EXACT_ADMITTED_ROWS")
    need(recipe["first_core_ps"] == 25000
         and recipe["core_period_ps"] == 25000, "FROZEN_TIMEBASE")
    capture_id, stop_id = recipe["capture_id"], recipe["plan_stop_id"]
    for value in (capture_id, stop_id):
        need(isinstance(value, str) and re.fullmatch("[A-Za-z0-9_-]{1,32}", value),
             "SAFE_BOUNDED_ID")
    need(recipe["profile"] == "ACTIVE_FRAME_SPARSE_DIAGNOSTICS_NO_REAL_CLAIM",
         "EXPLICIT_SYNTHETIC_PROFILE")
    seed_lines = read_reference(seed_ref).splitlines()
    need(len(seed_lines) == 7, "ARCHIVED_SEVEN_ROW_SEED_REQUIRED")
    seed = json.loads(seed_lines[0].decode("utf-8"), object_pairs_hook=pairs)
    need(seed["schema"] == RAW_SCHEMA, "SEED_RAW_SCHEMA")
    need(port_map_ref["sha256"] == PORT_MAP_SHA, "PINNED_PUBLIC_PORT_MAP_REQUIRED")
    port_map = json.loads(read_reference(port_map_ref).decode("utf-8"),
                          object_pairs_hook=pairs)
    declarations = port_map["raw_ports"]
    need(len(declarations) == 72 and set(seed["ports"]) == set(declarations),
         "PRESERVE_ALL_72_RAW_PORTS")
    ports = dict(seed["ports"])
    for name, declaration in declarations.items():
        width = declaration["width"]
        need(type(width) is int and len(ports[name]) == width
             and re.fullmatch("[01]+", ports[name]), "KNOWN_SEED_WIDTH:" + name)
    # Known nonzero, explicitly synthetic values. No observed PCM is a golden.
    # Idle ready/UART and held payload are retained as raw values, not accepts.
    ports.update(obs_event_ready="1", obs_req_ready="1", uart_tx="1")
    ports["obs_apply_data"] = format(0x0011223344556677, "064b")
    ports["obs_advance_frame_req_id"] = format(42, "032b")

    def variant(frame, phase, bclk, ws):
        values = dict(ports)
        values.update(i2s_bclk=str(bclk), i2s_lrck=str(ws), i2s_din="0")
        values["obs_frame_tick"] = str(int(frame))
        values["obs_cancel"] = str(int(frame))
        values["obs_raw_cancel_reason"] = "01" if frame else "00"
        if phase == 1:
            values.update(obs_effect_input_valid="1", obs_effect_input_ready="1",
                          obs_effect_input_left=format(2048, "024b"),
                          obs_effect_input_right=format((1 << 24) - 1024, "024b"),
                          obs_effect_input_clip_mask="01",
                          obs_upstream_clip_mask="01", obs_effect_clip_mask="10",
                          obs_feedback_clip_mask="00")
        elif phase == 2:
            # Autonomous release observation: invalid cause, not a MIDI event.
            values.update(obs_apply_valid="1", obs_apply_kind="0011",
                          obs_apply_mask="0001", obs_apply_data="0" * 64,
                          obs_router_apply_seq="0" * 32,
                          obs_router_apply_seq_valid="0")
        elif phase == 3:
            payload = (1 << 61) | (31 << 45) | (16384 << 30) | (8192 << 15) | 4096
            values.update(obs_config_take="1", obs_config_valid="1",
                          obs_config_ready="1",
                          obs_config_payload=format(payload, "062b"))
        return json.dumps(values, separators=(",", ":"), sort_keys=True).encode("ascii")

    # Twenty bounded encodings: five business phases x four clock states.
    # Per-row pins select existing bytes; no per-row port JSON serialization.
    variants = {(frame, phase, bclk, ws): variant(frame, phase, bclk, ws)
                for frame, phase in ((False, 0), (True, 0),
                                     (False, 1), (False, 2), (False, 3))
                for bclk in (0, 1) for ws in (0, 1)}
    # Freeze scenario/window inputs BEFORE emitting the observation stream.
    scenario = {"schema": "M3_R13_INDEPENDENT_SYNTHETIC_SCENARIO_V1",
                "recipe": recipe_ref, "seed": seed_ref, "port_map": port_map_ref,
                "row_count": rows, "finish_cycle": rows - 1,
                "frame_formula": "ceil(128*k*2**32/659706977)-1; k>=1",
                "source": "declared deterministic software input, never HDL",
                "serial_pins": {
                    "origin": "SYNTHETIC_ZERO_PCM_MECHANICAL_CLOCK",
                    "sampling_phase": "POSEDGE_PRE_NBA", "release_cycle": 0,
                    "accumulator_bits": 32, "phase_step": PHASE_STEP,
                    "initial": {"phase": 0, "bclk": 0, "slot": 0, "ws": 0},
                    "ws_update": "falling carry samples old slot[5], then slot=(slot+1)%64",
                    "din": 0, "TX_metadata_or_real_PCM_created": False},
                "sparse_phases_after_each_F": {"1": "FX_OBSERVATION",
                                             "2": "INVALID_CAUSE_RELEASE",
                                             "3": "CONFIG_TAKE"},
                "coverage_debt": ["no request/result/commit/TX transaction",
                                  "mechanical clock pins with zero DIN; TX coverage remains PARTIAL",
                                  "no valid independent apply mapping or golden"],
                "real_verified": False, "math_verified": False}
    scenario_ref = put_control("INDEPENDENT_SCENARIO.json", encoded(scenario))
    finish_time = rows * 25000
    frame_input = {"schema": "M3_R06_FRAME_PLAN_GENERATOR_INPUT_V1",
                   "status": "FROZEN_INDEPENDENT_INPUT",
                   "independent_of_observed_trace": True,
                   "source_identities": [
                       {"path": scenario_ref["path"], "sha256": scenario_ref["sha256"]},
                       {"path": recipe["base_source"]["path"],
                        "sha256": recipe["base_source"]["sha256"]}],
                   "epochs": [{"epoch": 0, "reset_assert_cycle": 0,
                               "release_cycle": 0, "stop_cycle": rows - 1,
                               "window_kind": "ACTIVE"}],
                   "finish": {"epoch": 0, "cycle": rows - 1}}
    controls = {
        "frame_input": ("FRAME_INPUT.json", encoded(frame_input)),
        "window_plan": ("WINDOW.json", encoded({
            "schema": "M3_R7D_INDEPENDENT_WINDOW_V1", "capture_id": capture_id,
            "plan_stop_id": stop_id, "input_plan_sha256": recipe["midi_plan"]["sha256"],
            "first_core_ps": 25000, "core_period_ps": 25000,
            "row_count": rows, "finish_cycle": rows - 1,
            "finish_time_ps": finish_time,
            "window_parameters": {"CAPTURE_ID": capture_id, "PLAN_STOP_ID": stop_id,
                "STOP_DRIVER_CYCLE": rows - 2,
                "EXPECTED_FINISH_CORE_CYCLE": rows - 1,
                "MAX_CORE_SAMPLES": rows + 16,
                "MAX_SIM_TIME_PS": finish_time + 1_000_000}})),
        "end": ("END.json", encoded({
            "schema": "M3_R7A_END_V1", "capture_id": capture_id,
            "plan_stop_id": stop_id, "finish_cycle": rows - 1,
            "time_ps": finish_time, "row_count": rows, "reason": "PLANNED_WINDOW_END",
            "ledger_status": "NOT_CHECKED_R6_5_REQUIRED",
            "serial_tail_status": "UNKNOWN_R6_6_REQUIRED"})),
        "stdout": ("STDOUT.txt", (
            f"MONITOR_END capture_id={capture_id} cycle={rows - 1} "
            f"time_ps={finish_time} rows={rows} reason=PLANNED_WINDOW_END\n").encode()),
        "resets": ("RESET_EDGES.jsonl", b"".join(encoded({
            "schema": "M3_R7A_RESET_SNAPSHOT_V1", "capture_id": capture_id,
            "kind": kind, "time_ps": at, "edge_seq": seq,
            "values": {"obs_pll_locked": bit, "sys_rst_n": bit, "obs_rst_n": bit}})
            for seq, kind, at, bit in ((1, "INITIAL", 0, "0"),
                                      (2, "CHANGE", 10000, "1"))))}
    refs = {role: put_control(name, raw) for role, (name, raw) in controls.items()}
    raw_sink = sink_factory("raw_capture")
    pin_states = _synthetic_zero_pcm_pins()
    k, upcoming, previous_frame = 1, frame_cycle(1), -100
    decoded_bytes = 0
    try:
        for cycle in range(rows):
            budget.check()
            is_frame = cycle == upcoming
            if is_frame:
                previous_frame = cycle
                k += 1
                upcoming = frame_cycle(k)
            phase = cycle - previous_frame
            phase = phase if phase in (1, 2, 3) else 0
            bclk, ws, _ = next(pin_states)
            port_bytes = variants[(is_frame, phase, bclk, ws)]
            prefix = (f'{{"schema":"{RAW_SCHEMA}","capture_id":"{capture_id}",'
                      f'"source_line":{cycle + 1},"cycle":{cycle},'
                      f'"time_ps":{(cycle + 1) * 25000},"epoch":null,'
                      '"epoch_reason":"BIND_FROM_INDEPENDENT_RESET_EDGES",'
                      f'"finish":{int(cycle == rows - 1)},"ports":').encode("ascii")
            line = prefix + port_bytes + b"}\n"
            need(len(line) <= 4096, "ADMITTED_RAW_LINE_GEOMETRY")
            need(raw_sink.write(line) == len(line), "RAW_SHORT_WRITE")
            decoded_bytes += len(line)
        need(decoded_bytes >= MIN_RAW_BYTES, "RAW_MINIMUM_NOT_REACHED")
        refs["raw_logical"] = raw_sink.finish()
    except BaseException as primary:
        # Preserve the active error even if closing a partial writer also fails.
        try:
            raw_sink.abort()
        except BaseException as cleanup:
            primary.add_note("RAW_ABORT_FAILED:" + type(cleanup).__name__ + ":" + str(cleanup))
        raise
    budget.check()
    return {"schema": "M3_R13_INPUT_CANDIDATE_V1",
            "status": "SYNTHETIC_INPUTS_ONLY_D4_NOT_CALLED",
            "refs": refs, "scenario": scenario_ref, "rows": rows,
            "raw_decoded_bytes": decoded_bytes,
            "requires_actual_D4": True,
            "W_admission": "NOT_GRANTED_BY_INPUT_BINDER",
            "integration_gaps": [
                "C storage Path/identity facade must read raw logical volume exactly",
                "bind new application_request window_parameters to WINDOW",
                "bind real source/ROM/tool closure plus midi plan and frame rules",
                "do not reuse seven-row execution receipt, row hashes or EXPECTED",
                "new synthetic receipt must remain declared, never trusted HDL",
                "B must validate actual D4 profile and record expected PARTIAL semantics",
                "all D4 outputs and comparisons must execute; no D4 replacement"],
            "real_verified": False, "math_verified": False,
            "board_release_allowed": False}



def _archive_member(archive, info, budget):
    need(info.file_size <= 16 * CHUNK, "ZIP_MEMBER_BOUND")
    body = bytearray()
    with archive.open(info, "r") as stream:
        while True:
            budget.check()
            block = stream.read(CHUNK)
            if not block:
                break
            body.extend(block)
            need(len(block) <= CHUNK and len(body) <= info.file_size, "ZIP_MEMBER_BOUND")
    need(len(body) == info.file_size, "ZIP_MEMBER_SIZE")
    return bytes(body)


def _replace_four_stimuli(io, application, graph, bodies,
                          archive_name="SOURCE_APPLICATION_SYNTHETIC_W_R03.zip"):
    old_zip_ref = application["source"]["application"]
    original_bytes = io.read_reference(old_zip_ref)
    nodes = {item["path"]: item for item in graph["nodes"]}
    roms = {item["path"]: item for item in graph["ROM_payloads"]}
    need(len(graph["units"]) == len(set(graph["units"])) == 75
         and len(nodes) == 77 and set(graph["units"]) <= nodes.keys()
         and len(roms) == 9, "FROZEN_75_SOURCE_9_ROM_GRAPH")
    replacements = {"inputs/" + name: body for name, body in bodies.items()}
    new_path = io.output / archive_name
    unchanged, replaced, rom_copies = [], [], []
    seen, node_seen, rom_seen = set(), set(), set()
    with zipfile.ZipFile(_ZipIO(binary_io.BytesIO(original_bytes), io.budget)) as original:
        members = original.infolist()
        need(len(members) <= 256 and sum(x.file_size for x in members) <= 64 * CHUNK,
             "SOURCE_ARCHIVE_BOUND")
        with io.open_file(new_path, "xb", budget=io.budget, category="all_other") as raw:
            with zipfile.ZipFile(_ZipIO(raw, io.budget), "w", compression=zipfile.ZIP_DEFLATED) as successor:
                for info in members:
                    io.budget.check()
                    name, posix = info.filename, PurePosixPath(info.filename)
                    need(not posix.is_absolute() and ".." not in posix.parts
                         and "\\" not in name and ":" not in name
                         and len(name.encode("utf-8")) <= 512
                         and all(p.rstrip(" .") == p for p in posix.parts)
                         and (posix.as_posix() == name or info.is_dir()), "ZIP_PATH")
                    need(name.casefold() not in seen
                         and (info.external_attr >> 16) & 0o170000 != 0o120000,
                         "ZIP_DUPLICATE_OR_ALIAS")
                    seen.add(name.casefold())
                    body = _archive_member(original, info, io.budget)
                    if name in replacements:
                        body = replacements[name]
                        replaced.append(name)
                    else:
                        unchanged.append({"member": name, "bytes": len(body),
                                          "sha256": hashlib.sha256(body).hexdigest()})
                    if name.startswith("inputs/"):
                        relative = name[7:]
                        expected = nodes.get(relative, roms.get(relative))
                        if expected is not None:
                            need(len(body) == expected["bytes"] and
                                 hashlib.sha256(body).hexdigest() == expected["sha256"],
                                 "FROZEN_SOURCE_OR_ROM_CHANGED:" + relative)
                        if relative in nodes:
                            node_seen.add(relative)
                        if relative in roms:
                            rom_seen.add(relative)
                            rom_copies.append(io.save("rom_originals/" + relative, body))
                    successor.writestr(copy.copy(info), body)
                    io.budget.check()
    need(set(replaced) == set(replacements) and len(replaced) == 4
         and node_seen == set(nodes) and rom_seen == set(roms), "ZIP_EXACT_REPLACEMENT_OR_GRAPH")
    # Changed archive identity is measured after its writer closes. Original
    # untouched member bytes are preserved; compression bytes need not match.
    new_ref = io.identify(new_path, 64 * CHUNK)
    io.verified(old_zip_ref)
    return new_ref, rom_copies, unchanged, sorted(replaced)


def _declared_roles(request, application):
    inputs = request["inputs"]
    result = {key: inputs[key] for key in ("source_manifest", "rom_manifest", "tool_manifest")}
    for name, role in (("input_plan", "midi_plan"), ("window_plan", "window_plan"),
                       ("raw_stdout", "stdout"), ("raw_stderr", "stderr"),
                       ("raw_trace", "raw"), ("reset_edges", "resets"),
                       ("finish_receipt", "end")):
        result[name] = inputs[role]
    result["driver"] = application["source"]["capture_sources"]["DRIVER"]
    result["observer"] = application["source"]["capture_sources"]["OBSERVER"]
    return result


def _context(value):
    need(type(value) is dict and set(value) == {"pid", "utc"}
         and type(value["pid"]) is int and value["pid"] > 0, "ACTUAL_BUILDER_CONTEXT")
    moment = datetime.fromisoformat(value["utc"])
    need(moment.utcoffset() is not None, "ACTUAL_BUILDER_TIMEZONE")
    return moment


def bind_w_inputs(freeze_ref, *, root, output, budget, open_file,
                  save_bytes, copy_file, mkdir, builder_context):
    """Create inputs only, within root's existing admitted W clock and writers.

    freeze_ref is an explicit same-buffer descriptor (see R03 notes). There
    are no guessed defaults for the native identities, source graph, nonce or
    global writer allocation. Hooks must create parent directories safely.
    Missing frozen parameters raise BinderPending, with partials preserved.
    No COMPLETE marker, D4 call, process launch, timer or EXPECTED is emitted.
    """
    try:
        return _bind_w_inputs(freeze_ref, root=root, output=output, budget=budget,
                              open_file=open_file, save_bytes=save_bytes,
                              copy_file=copy_file, mkdir=mkdir,
                              builder_context=builder_context)
    except FileNotFoundError as error:
        raise BinderPending("W_INPUT_BINDER_PENDING:MISSING_ORIGINAL:" + str(error)) from error
    except KeyError as error:
        raise BinderPending("W_INPUT_BINDER_PENDING:MISSING_FROZEN_PARAMETER:" +
                            str(error)) from error


def _bind_w_inputs(freeze_ref, *, root, output, budget, open_file,
                   save_bytes, copy_file, mkdir, builder_context):
    io = BinderIO(root, output, budget, open_file, save_bytes, copy_file, mkdir)
    budget.check()
    freeze = document(io.read_reference(freeze_ref))
    need(set(freeze) == {"schema", "templates", "physical_budgets", "nonce", "run_id"}
         and freeze["schema"] == "M3_R13_W_INPUT_BINDER_FREEZE_V1"
         and freeze["run_id"] == "W01", "FROZEN_BINDER_PARAMETERS")
    need(freeze["physical_budgets"] == EXPECTED_BUDGETS
         and sum(EXPECTED_BUDGETS.values()) == 24 << 30, "ROOT_WRITER_PROFILE_PENDING")
    need(isinstance(freeze["nonce"], str)
         and re.fullmatch("[0-9a-f]{32,64}", freeze["nonce"]), "NEW_NONCE_REQUIRED")
    templates = freeze["templates"]
    need(set(templates) == set(PIN_SHA), "EXACT_FROZEN_TEMPLATE_SET")
    for role, ref in templates.items():
        need(ref["sha256"] == PIN_SHA[role], "TEMPLATE_PIN:" + role)
    # All decisions use the same buffers which passed their identity checks.
    master_recipe = document(io.read_reference(templates["recipe"]))
    application = document(io.read_reference(templates["application"]))
    request_template = document(io.read_reference(templates["request"]))
    graph = document(io.read_reference(templates["graph"]))
    dependency_raw = io.read_reference(templates["r12_dependencies"])
    dependency_doc = document(dependency_raw)
    need(dependency_doc["schema"] == "M3_R12_PINNED_DEPENDENCIES_V1", "R12_DEPENDENCY_SCHEMA")
    io.read_reference(templates["module_bindings"])
    plan = document(io.read_reference(templates["midi_plan"]))
    need(master_recipe["rows"] == MIN_ROWS and plan["events"] == []
         and application["approved"] is False
         and request_template["origin"] == "SYNTHETIC_SCHEMA_FIXTURE"
         and freeze["nonce"] != application["execution_spec"]["nonce"], "SYNTHETIC_TEMPLATE_OR_NONCE")
    need(callable(builder_context), "ACTUAL_BUILDER_CONTEXT_HOOK_REQUIRED")
    begin = builder_context("START")
    begin_time = _context(begin)
    io.mkdir_hook(io.output, budget=budget, exclusive=True)
    budget.check()
    # Source dependency document retains its exact original bytes and sources.
    dependency_ref = io.copy(templates["r12_dependencies"], "FROZEN_R12_DEPENDENCIES.json")
    plan["total_cycles"] = MIN_ROWS - 2
    bodies = {"plan.json": encoded(plan), "bytes.drv": b"",
              "reset.drv": b"0 1\n", "ready.drv": b"0 1\n"}
    stimulus_refs = {name: io.save("stimulus/" + name, body) for name, body in bodies.items()}
    recipe = copy.deepcopy(master_recipe)
    recipe["midi_plan"] = stimulus_refs["plan.json"]
    bound_recipe_ref = io.save_json("BOUND_FULL_WINDOW_RECIPE_R03.json", recipe)
    sinks = []
    def raw_factory(role):
        need(role == "raw_capture" and not sinks, "EXACT_ONE_PLAIN_RAW_SINK")
        sink = _PlainRawSink(io)
        sinks.append(sink)
        return sink
    generated = produce_inputs(bound_recipe_ref, templates["seed"], templates["port_map"],
                               sink_factory=raw_factory, put_control=io.save,
                               budget=budget, read_reference=io.read_reference)
    refs = generated["refs"]
    window = document(io.read_reference(refs["window_plan"]))
    need(window["input_plan_sha256"] == stimulus_refs["plan.json"]["sha256"]
         and window["capture_id"] == recipe["capture_id"]
         and window["row_count"] == MIN_ROWS, "GENERATED_WINDOW_BINDING")
    new_zip, rom_copies, unchanged, replaced = _replace_four_stimuli(io, application, graph, bodies)
    source = application["source"]
    source["application"], source["stimulus_inputs"] = new_zip, stimulus_refs
    application["window_reference"] = refs["window_plan"]
    spec = application["execution_spec"]
    spec["window_parameters"], spec["nonce"] = window["window_parameters"], freeze["nonce"]
    need([step["tool"] for step in spec["steps"]] == ["vlib", "vlog", "vsim"]
         and spec["top"] == "tb_r7a_c9_public_capture" and spec["cwd"] == "inputs",
         "PROPOSED_TOOL_STEPS")
    order = ("CAPTURE_ID", "PLAN_STOP_ID", "STOP_DRIVER_CYCLE",
             "EXPECTED_FINISH_CORE_CYCLE", "MAX_CORE_SAMPLES", "MAX_SIM_TIME_PS")
    step = spec["steps"][2]
    step["argv"] = [application["tools"]["vsim"]["tool"]["file"]["path"], "-c"] + [
        "-g" + key + "=" + str(spec["window_parameters"][key]) for key in order] + [
        "work.tb_r7a_c9_public_capture", "-do", "run -all; quit -f"]
    application["proposed_plan"] = {
        "schema": "M3_C9_BOUND_APPLICATION_PLAN_V1", "source": copy.deepcopy(source),
        "tools": copy.deepcopy(application["tools"]),
        "external_inputs": copy.deepcopy(application["external_inputs"]),
        "window_reference": refs["window_plan"], "execution": copy.deepcopy(spec),
        "permission": "NOT_GRANTED", "process_route": "ABSENT"}
    app_ref = io.save_json("APPLICATION_REQUEST.json", application)
    source_members = [source["base"], source["decision"], source["application"],
                      *source["capture_sources"].values()]
    for ref in [*source_members, *source["contracts"].values(), application["external_inputs"],
                request_template["inputs"]["frame_rules"], *request_template["source_contract_refs"]]:
        io.verified(ref)
    source_ref = io.save_json("SOURCE_CLOSURE.json", {"schema": "M3_R7D_FILE_CLOSURE_V1",
                                                     "files": source_members})
    rom_ref = io.save_json("ROM_CLOSURE.json", {"schema": "M3_R7D_FILE_CLOSURE_V1",
                                               "files": [new_zip, *rom_copies]})
    native = {}
    for tool in application["tools"].values():
        for item in [tool["tool"], *tool.get("dependencies", [])]:
            ref = item["file"]
            key = str(io.path(ref)).casefold()
            need(key not in native or native[key] == ref, "NATIVE_IDENTITY_CONFLICT")
            native[key] = ref
    for ref in native.values():
        io.verified(ref)  # file identity only; never invoke PE/native tools.
    tool_ref = io.save_json("TOOL_CLOSURE.json", {"schema": "M3_R7D_FILE_CLOSURE_V1",
        "files": list(native.values()), "argv": step["argv"], "cwd": spec["cwd"],
        "version": "SYNTHETIC_DECLARATION_ONLY_NOT_EXECUTED; frozen native file identities"})
    inputs = {"raw": refs["raw_logical"], "resets": refs["resets"], "end": refs["end"],
              "stdout": refs["stdout"], "frame_input": refs["frame_input"],
              "stderr": io.save("CAPTURE_STDERR_SYNTHETIC_EMPTY.bin", b""),
              "application_request": app_ref, "frame_rules": request_template["inputs"]["frame_rules"],
              "window_plan": refs["window_plan"], "midi_plan": stimulus_refs["plan.json"],
              "source_manifest": source_ref, "rom_manifest": rom_ref, "tool_manifest": tool_ref}
    request = {key: copy.deepcopy(value) for key, value in request_template.items()
               if key not in {"synthetic_application_example", "inputs", "math_inputs"}}
    request.update(capture_id=recipe["capture_id"], origin="SYNTHETIC_SCHEMA_FIXTURE",
                   inputs=inputs, module_bindings=templates["module_bindings"])
    roles = _declared_roles(request, application)
    end = builder_context("DECLARATION")
    end_time = _context(end)
    need(end["pid"] == begin["pid"] and end_time >= begin_time, "BUILDER_CONTEXT_CHANGED")
    # Existing R11 requires these structural clean values. Their declared-only
    # meaning is explicit in ORIGIN, not a claim that vsim/tool execution ran.
    receipt = {"schema": "M3_R7D_DECLARED_EXECUTION_V1", "capture_id": recipe["capture_id"],
        "argv": step["argv"], "cwd": spec["cwd"],
        "bindings": {key: ref["sha256"] for key, ref in roles.items()},
        "exit_code": 0, "timeout": False, "cleanup_complete": True,
        "consumption": {"pid": begin["pid"], "group_id": "R13_W_SYNTHETIC_BUILDER_NOT_NATIVE",
                        "started_utc": begin["utc"], "ended_utc": end["utc"]}}
    receipt_ref = io.save_json("DECLARED_SYNTHETIC_RECEIPT.json", receipt)
    request["math_inputs"] = {"execution_receipt": receipt_ref}
    request_ref = io.save_json("CAPTURE_REQUEST.json", request)
    envelope_ref = io.save_json("ENVELOPE.json", {"schema": "N10_M3_UNIFIED_PIPELINE_REQUEST_V1",
        "mode": "PROCESS_CAPTURE", "request": request_ref})
    authority = {"execution_allowed": False, "real_verified": False,
                 "math_verified": False, "board_release_allowed": False}
    control_ref = io.save_json("CONTROL.json", {"schema": "M3_R13_BACKEND_CONTROL_V1",
        "run_id": "W01", "run_kind": "SYNTHETIC_SOFTWARE", "envelope_ref": envelope_ref,
        "dependencies_ref": dependency_ref, "quota_bytes": freeze["physical_budgets"]["all_stores"],
        "volume_policy": "GZIP_32M_PARTS_IO_1M", "authority": authority})
    origin_ref = io.save_json("W_INPUT_ORIGIN_R03.json", {
        "schema": "M3_R13_W_INPUT_ORIGIN_V1", "origin": "SYNTHETIC_SCHEMA_FIXTURE",
        "template_freeze": freeze_ref, "independent_scenario": generated["scenario"],
        "master_recipe": templates["recipe"], "bound_recipe": bound_recipe_ref,
        "new_application_zip": new_zip, "original_application_zip":
            document(io.read_reference(templates["application"]))["source"]["application"],
        "replaced_members": replaced, "unchanged_members": unchanged,
        "frozen_graph": templates["graph"], "source_units": 75, "roms": 9,
        "raw_frame_end_inherited": False, "old_EXPECTED_or_receipt_reused": False,
        "receipt_semantics": {"argv": "PROPOSED_NOT_EXECUTED", "pid_times": "ACTUAL_BUILDER_ONLY",
            "exit_cleanup": "STRUCTURAL_DECLARATION_NOT_VSIM_OBSERVATION"},
        "native_tool_calls": 0, "W_GO": False, **authority})
    for ref in [request_ref, envelope_ref, control_ref, receipt_ref, dependency_ref,
                app_ref, origin_ref, *inputs.values(), *templates.values()]:
        io.verified(ref)
    budget.check()
    return {"schema": "M3_R13_W_INPUT_BINDING_CANDIDATE_RESULT_V1",
        "status": "INPUTS_BOUND_ACTUAL_D4_NOT_CALLED", "control_ref": control_ref,
        "envelope_ref": envelope_ref, "dependency_ref": dependency_ref,
        "request_ref": request_ref, "inputs": inputs, "origin_ref": origin_ref,
        "required_W_postcondition": {"minimum_rows": MIN_ROWS,
            "raw_input_role": "raw", "raw_descriptor": inputs["raw"],
            "minimum_raw_bytes": MIN_RAW_BYTES},
        "postcondition_integration": "Current C W raw_role artifact lookup must explicitly bind final input raw; do not guess an absent artifact role.",
        "all_stores_quota_requires_shared_root_account": True,
        "W_GO": False, "actual_D4_required": True, **authority}





def worker(group, admission_path, admission_sha, output):
    record = read_control(admission_path, admission_sha)
    admission = record["value"]
    require(admission.get("plan_sha256") == PLAN_SHA256 and admission.get("group") == group
            and admission.get("state") == "CONSUMED_RUNNING", "WORKER_ADMISSION")
    require({"root_deadline_monotonic", "accounting_profile", "external_log_escrows"} <= admission.keys(),
            "WORKER_SHARED_ACCOUNTING_ADMISSION_REQUIRED")
    resources.configure_accounting(admission["accounting_profile"], admission["external_log_escrows"],
                                   admission["root_deadline_monotonic"])
    output = strict_child(OUTPUT, output)
    require(not output.exists(), "FRESH_WORKER_OUTPUT")
    _mkdir(output)
    atomic_json(output / "CONSUMPTION_RUNNING.json", {"schema": "M3_R13_WORKER_CONSUMPTION_V1",
        "group": group, "admission": {"path": str(Path(admission_path).resolve()), **record["stamp"]},
        "complete": False, "root_deadline_monotonic": admission["root_deadline_monotonic"]})
    try:
        if group in {"P0", "P1"}:
            # P1 is admitted only by the root LOCATED_REPAIR/frozen repair gate.
            # This local observation never substitutes for the parent Job proof.
            outcomes = [_p0_case()]
        elif group == "K":
            outcomes = _k_cases(admission, output)
        elif group == "V":
            _mkdir(output / "cases")
            outcomes = [_volume_case(case, output / "cases", admission) for case in GROUPS["V"]]
        elif group in ("B", "W"):
            if group == "W":
                require(admission.get("resource_profile") == "PASS", "W_RESOURCE_PROFILE_PENDING")
                _delivery_ready(admission)
                require(resources.preflight(OUTPUT, full_window=True)["decision"] == "GO",
                        "W_ACTUAL_START_FREE_PENDING")
            outcomes = _actual_cases(group, admission, output)
        elif group == "R":
            affected, repair_group = admission.get("affected_case_ids"), admission.get("repair_group")
            require(type(affected) is list and 0 < len(affected) == len(set(affected)) <= 16
                    and repair_group in {"K", "V", "B"} and set(affected) <= set(GROUPS[repair_group]),
                    "R_SINGLE_GROUP_SCOPE")
            if repair_group == "K":
                outcomes = _k_cases(admission, output, affected)
            elif repair_group == "V":
                _mkdir(output / "cases")
                outcomes = [_volume_case(case, output / "cases", admission) for case in affected]
            else:
                require(not {"B02", "B03", "B04"}.intersection(affected),
                        "R_PARENT_JOB_CASES_REQUIRE_PARENT_DISPATCH")
                outcomes = _actual_cases("B", admission, output, affected)
        else:
            raise Reject("WORKER_GROUP")
        resources.get_budget().check()
        _control_guard(admission_path, record)
        parent_required = group in {"P0", "P1", "B"} or (
            group == "R" and admission.get("repair_group") == "B")
        result = {"schema": "M3_R13_WORKER_LOCAL_RESULT_V1" if parent_required else "M3_R13_WORKER_COMPLETE_V1",
            "status": "PASS_LOCAL_PENDING_PARENT" if parent_required else "PASS", "group": group,
            "cases": outcomes, "parent_receipt_required": parent_required,
            "global_budget": resources.get_budget().receipt(), "real_verified": False,
            "math_verified": False, "execution_allowed": False, "board_release_allowed": False}
        atomic_json(output / ("WORKER_LOCAL_RESULT.json" if parent_required else "WORKER_COMPLETE.json"), result)
        resources.get_budget().check()
        return result
    except BaseException as primary:
        failure = {"schema": "M3_R13_WORKER_FAILURE_V1", "group": group,
            "error": type(primary).__name__ + ":" + str(primary),
            "traceback": traceback.format_exc(), "complete": False}
        try:
            atomic_json(output / "WORKER_FAILURE.json", failure)
        except BaseException as secondary:
            primary.add_note("SECONDARY_WORKER_FAILURE_WRITE:" + type(secondary).__name__ + ":" + str(secondary))
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--worker", action="store_true", required=True)
    parser.add_argument("--group", required=True, choices=(*GROUPS, "R"))
    parser.add_argument("--admission", required=True, type=Path)
    parser.add_argument("--admission-sha256", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    worker(args.group, args.admission, args.admission_sha256, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
