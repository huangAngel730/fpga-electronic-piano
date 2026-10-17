"""Streaming mechanical M1 input bundle. Observed PCM never becomes golden PCM."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[6]
COMMON_PATH = ROOT / ("code/software/m3_pro_fourvoice_trace_20261016/"
    "pro_basis_r08_20261017/coordinator/task_day4_completion_20261017/common.py")
COMMON_SHA = "55cb7481fe9c0870247a7d8b2453dea859f0f2e81879795cc0e34ffe8c996dca"
STREAM_PATH = ROOT / ("code/software/m3_pro_fourvoice_trace_20261016/"
    "pro_basis_r07_20261017/public_capture_tb/c9_completion_r01/c9_stream.py")
STREAM_SHA = "5584ab7201544a8d30bfdd7603a51483d1c5340ccc219e853df0d146d042ebef"
CONTRACT_PATH = ROOT / ("code/docs/test/m1_r05_pcm_oracle_20261016/"
    "pro_r06_20261017/oracle_adapter/NEXT_INPUT_CONTRACT.md")
CONTRACT_SHA = "b9cd60d3df2184e318b03e6d973f3ebf319ae73614f6e7deb51f771159a52373"
REQUIRED_ROLES = {
    "source_closure", "rom_manifest", "observer", "driver", "tb",
    "tool_identity", "capture_contract", "midi_plan", "public_rows", "raw_capture",
    "reset_edges", "end", "stdout", "execution_receipt", "frame_plan",
    "ledger", "tx_report"}
_COMMON = None


def support():
    global _COMMON
    if _COMMON is None:
        raw = COMMON_PATH.read_bytes()
        if hashlib.sha256(raw).hexdigest() != COMMON_SHA:
            raise ValueError("COMMON_SOURCE_CHANGED")
        module = ModuleType("_m3_c9_d4_common_bundle")
        module.__file__ = str(COMMON_PATH)
        exec(compile(raw, str(COMMON_PATH), "exec"), module.__dict__)
        _COMMON = module
    return _COMMON


def _handshake(valid, ready):
    if type(valid) is int and valid == 0 or type(ready) is int and ready == 0:
        return False
    if type(valid) is int and valid == 1 and type(ready) is int and ready == 1:
        return True
    return None


def build_bundle(request, output_dir):
    """request.inputs is role -> path/bytes/sha256; incomplete roles stay pending."""
    c = support()
    c.require(isinstance(request, dict)
              and request.get("schema") == "M3_D4_C9_MATH_BUNDLE_REQUEST_V1",
              "MATH_BUNDLE_REQUEST")
    c.require(isinstance(request.get("inputs"), dict), "MATH_BUNDLE_INPUTS")
    c.require("public_rows" in request["inputs"], "PUBLIC_ROWS_REQUIRED")
    c.require(c.identity(CONTRACT_PATH)["sha256"] == CONTRACT_SHA, "M1_NEXT_INPUT_CONTRACT_CHANGED")
    paths = {role: c.checked_descriptor(desc, allow_external=True)
             for role, desc in request["inputs"].items()}
    before = {role: c.artifact(path) for role, path in paths.items()}
    stream = c.load_source(STREAM_PATH, STREAM_SHA)
    d = stream.dependencies()
    out = c.output_directory(output_dir)
    index_path = out / "MATH_ROW_INDEX.jsonl"
    fx_path = out / "FX_HISTORY.jsonl"
    advances_path = out / "ADVANCE_HISTORY.jsonl"
    events_path = out / "INPUT_AND_APPLY_HISTORY.jsonl"
    count = 0
    fx_count = 0
    advance_count = 0
    apply_count = 0
    try:
        with index_path.open("xb") as index, fx_path.open("xb") as fx, \
                advances_path.open("xb") as advances, events_path.open("xb") as events:
            for count, row in enumerate(stream.iter_public_rows(paths["public_rows"], d), 1):
                fields = row["fields"]
                if "raw_capture" in before:
                    c.require(row["source"]["raw_sha256"] == before["raw_capture"]["sha256"],
                              "BUNDLE_RAW_CAPTURE_MISMATCH")
                if "reset_edges" in before:
                    c.require(row["source"]["reset_edges_sha256"] == before["reset_edges"]["sha256"],
                              "BUNDLE_RESET_EDGES_MISMATCH")
                if "capture_id" in request:
                    c.require(row["capture_id"] == request["capture_id"], "BUNDLE_CAPTURE_ID")
                lane = d["bridge"]._lane_advance(fields["advance_mask"])
                applied = d["bridge"]._apply_classification(fields)
                row_digest = hashlib.sha256(json.dumps(
                    row, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
                    allow_nan=False).encode("utf-8")).hexdigest()
                source = {**row["source"], "canonical_row_content_sha256": row_digest}
                record = {
                    "source": source,
                    "canonical_row": row,
                    "frame_f_raw": fields["frame_tick"],
                    "actual_accept_a": _handshake(fields["req_valid"], fields["req_ready"]),
                    "advance_request_tag": fields["advance_frame_req_id"],
                    "lane_advance": lane,
                    "apply_classification": applied,
                    "independent_apply_event_seq": None,
                    "expected_pcm": None,
                    "actual_pcm_is_golden": False,
                    "math_status": "PENDING_M1_MODEL_AND_INDEPENDENT_PLAN",
                }
                stream.json_line(index, record)
                if (fields["effect_input_valid"] != 0
                        or fields["config_take"] != 0):
                    fx_count += 1
                    stream.json_line(fx, {
                        "source": source,
                        "actual_effect_input": {name: fields[name] for name in (
                            "effect_input_valid", "effect_input_ready", "effect_input_id",
                            "effect_input_left", "effect_input_right", "effect_input_clip_mask")},
                        "actual_config": {name: fields[name] for name in (
                            "config_take", "config_payload")},
                        "config_components": row["semantics"].get("config_on_actual_take"),
                        "actual_clips": {name: fields[name] for name in (
                            "upstream_clip_mask", "effect_clip_mask", "feedback_clip_mask")},
                        "expected_fx_input": None,
                        "status": "OBSERVATION_ONLY_NOT_GOLDEN"})
                if fields["advance_mask"] != 0:
                    advance_count += 1
                    stream.json_line(advances, {
                        "source": source, "advance": lane,
                        "request_tag": fields["advance_frame_req_id"],
                        "req_id": fields["req_id"],
                        "commit_observed_same_row": fields["commit"],
                        "cancel_raw": fields["cancel"],
                        "retained_even_if_unpublished_or_cancelled": True})
                if fields["event_valid"] != 0 or fields["apply_valid"] != 0:
                    apply_count += 1
                    stream.json_line(events, {
                        "source": source,
                        "actual_input": {name: fields[name] for name in (
                            "event_valid", "event_ready", "event_data")},
                        "actual_stage": {name: fields[name] for name in (
                            "apply_valid", "apply_data", "apply_kind", "apply_mask",
                            "router_apply_seq", "router_apply_seq_valid")},
                        "classification": applied,
                        "independent_apply_event_seq": None,
                        "status": "PENDING_INDEPENDENT_INPUT_PLAN_MAPPING"})
        stream.checked_unchanged(before)
        missing = sorted(REQUIRED_ROLES - set(paths))
        bundle = {
            "schema": "M3_D4_C9_MATH_INPUT_BUNDLE_V1",
            "status": "MECHANICAL_INPUT_READY_MATH_PENDING",
            "next_input_contract": c.artifact(CONTRACT_PATH),
            "inputs": before, "missing_roles": missing,
            "row_count": count, "all_rows_retained": True,
            "history_counts": {"fx": fx_count, "advance": advance_count,
                               "input_and_apply": apply_count},
            "artifacts": {"row_index": c.artifact(index_path),
                          "fx_history": c.artifact(fx_path),
                          "advance_history": c.artifact(advances_path),
                          "input_apply_history": c.artifact(events_path)},
            "expected_math": None,
            "legacy_b0_status": "PENDING_UNSUPPORTED_PROFILE",
            "pending": ["M1_INDEPENDENT_GOLDEN_MODEL", "INDEPENDENT_PLAN_MAPPING",
                        "AUDIO_STABLE", "TRUSTED_CAPTURE_AUTHORITY", "M2_ADMISSION"],
            "FRAME_PLAN_generated": False,
            "actual_PCM_used_as_expected": False,
            "math_verified": False, "real_verified": False, "board_release_allowed": False}
        c.write_json(out / "MATH_INPUT_BUNDLE.json", bundle)
        result = {**bundle, "artifacts": {
            **bundle["artifacts"], "math_input_bundle": c.artifact(out / "MATH_INPUT_BUNDLE.json")}}
        c.write_json(out / "RECEIPT.json", result)
        return result
    except BaseException as error:
        c.write_json(out / "FAILURE.json", {
            "status": "REJECT_PARTIAL_ARTIFACTS_RETAINED", "inputs": before,
            "error": type(error).__name__ + ":" + str(error),
            "math_verified": False, "real_verified": False})
        raise


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    result = build_bundle(support().read_json(args.request), args.output)
    print(json.dumps({"status": result["status"], "rows": result["row_count"]}))
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
