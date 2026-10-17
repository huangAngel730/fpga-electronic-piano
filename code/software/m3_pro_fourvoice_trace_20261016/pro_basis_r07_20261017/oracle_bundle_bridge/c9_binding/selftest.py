"""NOT_RUN cases for the independent R7-C C9 mechanical bridge."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from c9_oracle_bridge import (C9BridgeReject, R7A_ROW_SCHEMA, REQUIRED_FIELDS,
                              ROW_SCHEMA, build_index)


REPO = Path(__file__).resolve().parents[6]
INPUT_BINDING = REPO / (
    "code/docs/test/m3_pro_fourvoice_trace_20261016/"
    "pro_basis_r07_20261017/oracle_bundle_bridge/c9_binding/INPUT_BINDING.json")


def _fields(cycle: int, **updates: object) -> dict:
    fields = dict.fromkeys(REQUIRED_FIELDS)
    fields.update({"cycle": cycle, "epoch": 0, "rst_n": 1,
                   "frame_tick": 0, "apply_valid": 0,
                   "apply_event_seq": None, "apply_data": 0,
                   "advance_mask": 0, "advance_frame_req_id": 0,
                   "audio_stable": None, "apply_kind": 0,
                   "apply_mask": 0, "router_apply_seq": 0,
                   "router_apply_seq_valid": 0, "config_take": 0,
                   "upstream_clip_mask": 0, "effect_clip_mask": 0,
                   "feedback_clip_mask": 0})
    fields.update(updates)
    return fields


def _record(line: int, cycle: int, **updates: object) -> dict:
    fields = _fields(cycle, **updates)
    return {"schema": ROW_SCHEMA, "capture_id": "c9-synthetic-fixture",
            "origin": "SYNTHETIC_C9_FIXTURE",
            "source": {"trace_path": "fixture_c9_rows.jsonl",
                       "raw_capture_sha256": "a" * 64,
                       "line": line, "cycle": cycle, "epoch": 0,
                       "sampling_phase": "POSEDGE_PRE_NBA"},
            "fields": fields, "plan_association": None}


def _r7a_record(line: int, cycle: int, **updates: object) -> dict:
    return {
        "schema": R7A_ROW_SCHEMA,
        "capture_id": "c9-synthetic-fixture",
        "origin": "SYNTHETIC_SCHEMA_FIXTURE",
        "source": {
            "raw_sha256": "a" * 64,
            "reset_edges_sha256": "c" * 64,
            "line": line,
            "cycle": cycle,
            "epoch": 0,
            "time_ps": 25000 * (cycle + 1),
            "sampling_phase": "POSEDGE_PRE_NBA",
        },
        "fields": _fields(cycle, **updates),
        "raw_ports": {},
        "missing_reasons": {},
        "events": [],
        "semantics": {},
    }


def _write_inputs(output_dir: Path, rows: list[dict],
                  binding: dict, bind_descriptor: bool = True) -> tuple[Path, Path]:
    trace_path = output_dir / "fixture_c9_rows.jsonl"
    try:
        trace_path_text = trace_path.resolve().relative_to(REPO.resolve()).as_posix()
    except ValueError:
        trace_path_text = str(trace_path.resolve())
    for row in rows:
        if row.get("schema") == ROW_SCHEMA:
            row["source"]["trace_path"] = trace_path_text
    trace_bytes = "".join(json.dumps(row, separators=(",", ":")) + "\n"
                          for row in rows).encode("utf-8")
    trace_path.write_bytes(trace_bytes)
    if bind_descriptor:
        binding["trace"] = {
            "status": "SYNTHETIC_C9_FIXTURE_NOT_RUN",
            "descriptor": {"path": trace_path_text,
                           "bytes": len(trace_bytes),
                           "sha256": hashlib.sha256(trace_bytes).hexdigest()},
        }
    binding_path = output_dir / "binding.json"
    binding_path.write_text(json.dumps(binding, indent=2) + "\n",
                            encoding="utf-8", newline="\n")
    return binding_path, trace_path


def _reject(call, expected: str) -> dict:
    try:
        call()
    except C9BridgeReject as exc:
        if expected not in str(exc):
            raise
        return {"status": "EXPECTED_REJECT", "reason": str(exc)}
    raise AssertionError("EXPECTED_REJECT:" + expected)


def run_case(case_id: str, output_dir: Path) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    binding = json.loads(INPUT_BINDING.read_text(encoding="utf-8"))
    rows = [_record(1, 0)]
    expected_reject = None
    input_format = "r7c-contract"
    if case_id == "C9_CONTRACT_BINDING_ACCEPT":
        pass
    elif case_id == "PRESERVE_C9_FIELDS":
        rows = [_record(1, 0, apply_valid=1, apply_data=0x91,
                        apply_kind=6, apply_mask=3, router_apply_seq=9,
                        router_apply_seq_valid=1, config_take=1,
                        upstream_clip_mask=1, effect_clip_mask=2,
                        feedback_clip_mask=3)]
    elif case_id == "INVALID_SENTINEL_348":
        rows = [_record(index, index - 1, apply_valid=1, apply_kind=kind,
                        apply_data=0, router_apply_seq=0,
                        router_apply_seq_valid=0)
                for index, kind in enumerate((3, 4, 8), start=1)]
    elif case_id == "SHARED_SEQ_MULTI_STAGE":
        rows = [_record(1, 0, apply_valid=1, apply_kind=1, apply_data=0x90,
                        router_apply_seq=7, router_apply_seq_valid=1),
                _record(2, 1, apply_valid=1, apply_kind=2, apply_data=0x90,
                        router_apply_seq=7, router_apply_seq_valid=1)]
    elif case_id == "ROUTER_SEQ_NOT_PLAN_SEQ_REJECT":
        rows[0]["fields"].update(apply_valid=1, apply_kind=1,
                                  router_apply_seq=12,
                                  router_apply_seq_valid=1,
                                  apply_event_seq=12)
        expected_reject = "INDEPENDENT_PLAN_MAPPING_UNVERIFIED"
    elif case_id == "INDEPENDENT_PLAN_ASSOCIATION_REJECT":
        rows[0]["fields"].update(apply_valid=1, apply_kind=1,
                                  router_apply_seq=12,
                                  router_apply_seq_valid=1,
                                  apply_event_seq=44)
        rows[0]["plan_association"] = {
            "schema": "M3_R7C_C9_PLAN_ASSOCIATION_V1",
            "status": "INDEPENDENT_PLAN_MATCH",
            "basis": "PLAN_PAYLOAD_AND_ACCEPTANCE_IDENTITY",
            "apply_event_seq": 44,
            "accepted_source_line": 1,
            "plan_identity": {"path": "independent_input_plan.json",
                              "sha256": "b" * 64},
        }
        expected_reject = "INDEPENDENT_PLAN_MAPPING_UNVERIFIED"
    elif case_id == "ADVANCE_TAG_NOT_FRAME":
        rows[0]["fields"].update(frame_tick=0, advance_mask=15,
                                  advance_frame_req_id=77)
    elif case_id == "PARTIAL_MASK_NOT_FOUR_LANE":
        rows[0]["fields"].update(advance_mask=1, advance_frame_req_id=77)
    elif case_id == "UNKNOWN_MASK_PENDING":
        rows[0]["fields"].update(advance_mask="1x01",
                                  advance_frame_req_id=77)
    elif case_id == "BINARY_1111_FOUR_LANE":
        rows[0]["fields"].update(advance_mask="1111",
                                  advance_frame_req_id=77)
    elif case_id == "VALID_ROUTER_SEQ_ZERO":
        rows[0]["fields"].update(apply_valid=1, apply_kind=1,
                                  apply_data=0x90, router_apply_seq=0,
                                  router_apply_seq_valid=1)
    elif case_id == "FIELD_74_REQUIRED_REJECT":
        del rows[0]["fields"]["feedback_clip_mask"]
        expected_reject = "FIELDS_NOT_EXACT_74"
    elif case_id == "SOURCE_LINE_MISMATCH_REJECT":
        rows[0]["source"]["line"] = 2
        expected_reject = "SOURCE_IDENTITY"
    elif case_id == "CONTRACT_HASH_MISMATCH_REJECT":
        binding["inputs"]["row_schema"]["sha256"] = "0" * 64
        expected_reject = "FROZEN_INPUT_IDENTITY:row_schema"
    elif case_id == "UNKNOWN_SEMANTICS_PENDING":
        rows[0]["fields"].update(apply_valid="x", apply_kind="xxxx",
                                  apply_data=None, router_apply_seq=None,
                                  router_apply_seq_valid="x",
                                  audio_stable="x")
    elif case_id == "R7A_PUBLIC_ROWS_MECHANICAL_ADAPTER":
        rows = [_r7a_record(1, 0, apply_valid=1, apply_kind=1,
                            apply_data=0x90, router_apply_seq=0,
                            router_apply_seq_valid=1,
                            upstream_clip_mask=1, effect_clip_mask=2,
                            feedback_clip_mask=3)]
        input_format = "r7a-public-c9"
    elif case_id == "R7A_ADAPTER_FIELD_LOSS_REJECT":
        rows = [_r7a_record(1, 0)]
        del rows[0]["fields"]["feedback_clip_mask"]
        input_format = "r7a-public-c9"
        expected_reject = "R7A_FIELDS_NOT_EXACT_74"
    else:
        raise KeyError(case_id)
    binding_path, trace_path = _write_inputs(
        output_dir, rows, binding,
        bind_descriptor=case_id not in {
            "R7A_PUBLIC_ROWS_MECHANICAL_ADAPTER",
            "R7A_ADAPTER_FIELD_LOSS_REJECT",
        })
    call = lambda: build_index(binding_path, trace_path, REPO,
                               input_format=input_format)
    report = _reject(call, expected_reject) if expected_reject else call()
    if case_id == "PRESERVE_C9_FIELDS":
        row = report["rows"][0]
        if (list(row["fields"]) != list(REQUIRED_FIELDS)
                or (row["apply"]["apply_kind"], row["apply"]["apply_mask"],
                row["apply"]["router_apply_seq"],
                row["apply"]["router_apply_seq_valid"], row["config_take"],
                row["clip"]["upstream"], row["clip"]["effect"],
                row["clip"]["feedback"]) != (6, 3, 9, 1, 1, 1, 2, 3)):
            raise AssertionError("C9_FIELD_LOSS")
    elif case_id == "INVALID_SENTINEL_348":
        if [row["apply"]["classification"] for row in report["rows"]] != [
                "INVALID_CAUSE_SENTINEL"] * 3:
            raise AssertionError("SENTINEL_PROMOTED")
    elif case_id == "SHARED_SEQ_MULTI_STAGE":
        if (report["row_count"] != 2
                or [row["apply"]["apply_kind"] for row in report["rows"]]
                != [1, 2] or report["deduplicated_by_router_seq"]):
            raise AssertionError("MULTI_STAGE_DEDUPLICATED")
    elif case_id == "ADVANCE_TAG_NOT_FRAME":
        row = report["rows"][0]
        if (row["frame_f"] is not False or row["advance_request_tag"] != 77
                or row["lane_advance"]["all_four_lanes"] is not True):
            raise AssertionError("REQUEST_TAG_PROMOTED_TO_FRAME")
    elif case_id == "PARTIAL_MASK_NOT_FOUR_LANE":
        lane = report["rows"][0]["lane_advance"]
        if (lane["raw_mask"] != 1 or lane["all_four_lanes"] is not False
                or lane["status"] != "PARTIAL_LANE_MASK"):
            raise AssertionError("PARTIAL_MASK_PROMOTED")
    elif case_id == "UNKNOWN_MASK_PENDING":
        lane = report["rows"][0]["lane_advance"]
        if (lane["raw_mask"] != "1x01" or lane["all_four_lanes"] is not None
                or lane["status"] != "PENDING_UNKNOWN_LANE_MASK"):
            raise AssertionError("UNKNOWN_MASK_PROMOTED")
    elif case_id == "BINARY_1111_FOUR_LANE":
        lane = report["rows"][0]["lane_advance"]
        if lane["raw_mask"] != "1111" or lane["all_four_lanes"] is not True:
            raise AssertionError("BINARY_1111_NOT_RECOGNIZED")
    elif case_id == "VALID_ROUTER_SEQ_ZERO":
        apply = report["rows"][0]["apply"]
        if (apply["router_apply_seq"] != 0
                or apply["classification"] != "ROUTER_STAGE_PRESERVED"):
            raise AssertionError("VALID_ZERO_REJECTED_AS_SENTINEL")
    elif case_id == "UNKNOWN_SEMANTICS_PENDING":
        if (report["rows"][0]["apply"]["classification"]
                != "PENDING_UNKNOWN_APPLY_SEMANTICS"
                or "PENDING_AUDIO_STABLE_POLICY" not in report["pending"]):
            raise AssertionError("UNKNOWN_INVENTED")
    elif case_id == "R7A_PUBLIC_ROWS_MECHANICAL_ADAPTER":
        row = report["rows"][0]
        if (report["input_adapter"]["mode"] != "r7a-public-c9"
                or list(row["fields"]) != list(REQUIRED_FIELDS)
                or row["source"]["raw_capture_sha256"] != "a" * 64
                or row["apply"]["independent_apply_event_seq"] is not None
                or report["input_adapter"]["field_values_modified"]
                or row["upstream_evidence"]["source"]["raw_sha256"]
                != "a" * 64
                or report["trace_input"]["bytes"] != trace_path.stat().st_size
                or report["trace_input"]["sha256"]
                != hashlib.sha256(trace_path.read_bytes()).hexdigest()):
            raise AssertionError("R7A_ADAPTER_NOT_MECHANICAL")
    (output_dir / "result.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8", newline="\n")
    return {"case_id": case_id, "status": "PASS"}
