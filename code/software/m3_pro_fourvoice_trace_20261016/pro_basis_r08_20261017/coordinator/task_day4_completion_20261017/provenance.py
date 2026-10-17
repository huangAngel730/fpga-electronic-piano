"""Streaming C9 source/row/independent-window binding, without REAL approval."""
from __future__ import annotations

import argparse
import hashlib
from itertools import zip_longest
from pathlib import Path
import sys
from types import ModuleType

_common_path = Path(__file__).with_name("common.py")
_raw = _common_path.read_bytes()
if hashlib.sha256(_raw).hexdigest() != "55cb7481fe9c0870247a7d8b2453dea859f0f2e81879795cc0e34ffe8c996dca":
    raise RuntimeError("BOOTSTRAP_COMMON_SOURCE_CHANGED")
c = ModuleType("_d4_provenance_common")
c.__file__ = str(_common_path.resolve())
c.__package__ = ""
sys.modules[c.__name__] = c
exec(compile(_raw, str(_common_path), "exec", dont_inherit=True, optimize=0), c.__dict__)

SOFT = c.SOFT
OLD_CODEC = SOFT / "pro_basis_r07_20261017/public_capture_tb/c9_binding/c9_capture.py"
OLD_CODEC_SHA = "0d3fcea8d75cdadcea6f6a663e6840735ccd050bbf072e01c3de61fa2477e931"
PORT_MAP = c.ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r07_20261017/public_capture_tb/c9_binding/PORT_MAP_C9.json"
PORT_MAP_SHA = "65a4fcca8b83ab72eaed3aaf5bf7cd48db18ad0691027aaaf57d1e9e4ced0807"
C9_SOURCE_SHA = "d458ab16277bd46751318ac368b22df1b21b35c4867c47942e7bff7d27fc3aa2"


def _same(actual, expected):
    if isinstance(actual, str) and isinstance(expected, str):
        return actual.lower() == expected.lower()
    return type(actual) is type(expected) and actual == expected


def validate_capture(request: dict, artifacts: dict, output_dir: Path) -> dict:
    """Bind actual public rows to original raw bits and independent plans.

    An external execution receipt remains declared evidence. This function
    cannot authenticate a producer, grant execution, or supply a math oracle.
    """
    out = c.output_directory(output_dir)
    before = {}
    inputs = request["inputs"]
    required = ("raw", "resets", "end", "stdout", "window_plan", "midi_plan",
                "frame_input", "frame_rules")
    paths = {}
    for role in required:
        c.require(role in inputs, "PROVENANCE_INPUT_MISSING:" + role)
        paths[role] = c.checked_descriptor(inputs[role])
        before[role] = c.artifact(paths[role])
    c.require("public_rows" in artifacts and "frame_plan" in artifacts,
              "CANONICAL_CAPTURE_AND_UNIQUE_FRAME_PLAN_REQUIRED")
    normalized = c.checked_descriptor(artifacts["public_rows"])
    frame_plan_path = c.checked_descriptor(artifacts["frame_plan"])
    before["public_rows"] = c.artifact(normalized)
    before["frame_plan"] = c.artifact(frame_plan_path)
    for role, item in artifacts.items():
        if isinstance(item, dict) and {"path", "bytes", "sha256"} <= item.keys():
            before["derived:" + role] = c.artifact(c.checked_descriptor(item))
    refs = request["source_contract_refs"]
    c.require(isinstance(refs, list) and refs, "SOURCE_CONTRACT_REFS_REQUIRED")
    for index, ref in enumerate(refs):
        before["source_ref:" + str(index)] = c.artifact(c.checked_descriptor(ref))
    c.require(any(item["sha256"] == C9_SOURCE_SHA for item in refs), "LATEST_C9_SOURCE_IDENTITY_REQUIRED")
    c.require(c.identity(PORT_MAP)["sha256"] == PORT_MAP_SHA, "C9_PORT_MAP_CHANGED")
    port_map = c.read_json(PORT_MAP)
    old = c.load_source(OLD_CODEC, OLD_CODEC_SHA).legacy_pure()
    capture_id = request["capture_id"]
    origin = request["origin"]
    c.require(origin in ("SYNTHETIC_SCHEMA_FIXTURE", "HDL_PUBLIC_CAPTURE_UNVERIFIED"), "CAPTURE_ORIGIN")
    end = c.read_json(paths["end"])
    window = c.read_json(paths["window_plan"])
    frame_input = c.read_json(paths["frame_input"])
    plan = c.read_json(frame_plan_path)
    c.require(window.get("schema") == "M3_R7D_INDEPENDENT_WINDOW_V1", "INDEPENDENT_WINDOW_SCHEMA")
    c.require(window.get("capture_id") == end.get("capture_id") == capture_id, "WINDOW_CAPTURE_ID")
    c.require(window.get("input_plan_sha256") == inputs["midi_plan"]["sha256"], "WINDOW_INPUT_PLAN_SHA")
    c.require(end.get("reason") == "PLANNED_WINDOW_END", "PLANNED_FINISH_REQUIRED")
    c.require(window.get("plan_stop_id") == end.get("plan_stop_id"), "PLAN_STOP_ID")
    for key in ("first_core_ps", "core_period_ps", "row_count", "finish_time_ps"):
        c.require(type(window.get(key)) is int and window[key] > 0, "WINDOW_NUMERIC:" + key)
    c.require(type(window.get("finish_cycle")) is int and window["finish_cycle"] >= 0, "WINDOW_FINISH_CYCLE")
    c.require(window["finish_cycle"] == window["row_count"] - 1, "WINDOW_CONTINUITY")
    c.require(window["finish_time_ps"] == window["first_core_ps"] + window["finish_cycle"] * window["core_period_ps"], "WINDOW_TIMEBASE")
    c.require((end.get("finish_cycle"), end.get("time_ps"), end.get("row_count")) ==
              (window["finish_cycle"], window["finish_time_ps"], window["row_count"]), "END_WINDOW_MISMATCH")
    c.require(plan.get("schema") == "M3_R06_UNIQUE_FRAME_PLAN_V1", "UNIQUE_FRAME_PLAN_SCHEMA")
    c.require(plan.get("input_sha256") == inputs["frame_input"]["sha256"] and
              plan.get("rules_sha256") == inputs["frame_rules"]["sha256"], "FRAME_PLAN_INPUT_RULES_BINDING")
    c.require(plan.get("finish") == frame_input.get("finish"), "FRAME_PLAN_INDEPENDENT_FINISH")
    c.require(plan["finish"]["cycle"] == end["finish_cycle"], "FRAME_PLAN_CAPTURE_FINISH")
    with paths["resets"].open("rb") as reset_file:
        reset_bytes = reset_file.read(16 * 1024 * 1024 + 1)
    c.require(len(reset_bytes) <= 16 * 1024 * 1024, "RESET_METADATA_SIZE_LIMIT")
    states = old.reset_states(reset_bytes, capture_id)
    planned_frames = [(epoch["epoch"], cycle) for epoch in plan["epochs"] for cycle in epoch["cycles"]]
    observed_frames = []
    raw_sha = before["raw"]["sha256"]
    reset_sha = before["resets"]["sha256"]
    counts = {"rows": 0, "finish": 0, "epoch_unknown": 0}
    for number, pair in enumerate(zip_longest(c.iter_jsonl(paths["raw"]), c.iter_jsonl(normalized)), 1):
        raw, row = pair
        c.require(raw is not None and row is not None, "RAW_NORMALIZED_COVERAGE")
        c.require(raw.get("schema") == "M3_R7A_C9_RAW_CORE_ROW_V1" and row.get("schema") == "M3_R7A_C9_PUBLIC_ROW_V1", "C9_RAW_NORMALIZED_SCHEMA")
        c.require(raw.get("capture_id") == row.get("capture_id") == capture_id and row.get("origin") == origin, "ROW_CAPTURE_ORIGIN")
        cycle = number - 1
        now = window["first_core_ps"] + cycle * window["core_period_ps"]
        c.require((raw.get("source_line"), raw.get("cycle"), raw.get("time_ps")) == (number, cycle, now), "RAW_WINDOW_COORDINATES")
        c.require(raw.get("epoch") is None and raw.get("epoch_reason") == "BIND_FROM_INDEPENDENT_RESET_EDGES", "RAW_EPOCH_INDEPENDENCE")
        c.require(row.get("raw_ports") == raw.get("ports"), "RAW_PORT_EVIDENCE_CHANGED")
        source = row.get("source", {})
        c.require((source.get("raw_sha256"), source.get("reset_edges_sha256"), source.get("line"),
                   source.get("cycle"), source.get("time_ps"), source.get("sampling_phase")) ==
                  (raw_sha, reset_sha, number, cycle, now, "POSEDGE_PRE_NBA"), "ROW_SOURCE_BINDING")
        fields = row.get("fields", {})
        c.require(set(fields) == set(port_map["normalized_fields"]), "FULL_74_FIELDS_REQUIRED")
        c.require(set(raw["ports"]) == set(port_map["raw_ports"]), "RAW_PUBLIC_PORT_SET")
        values = {name: old.scalar(raw["ports"][name], declaration)
                  for name, declaration in port_map["raw_ports"].items()}
        c.require(values["obs_core_clk"] == values["obs_polyphonic_valid"] == 1, "PUBLIC_CORE_MODE_QUALIFICATION")
        for name, mapping in port_map["normalized_mapping"].items():
            expected = values[mapping["port"]]
            if name == "tx_req_id" and values["obs_tx_req_id_valid"] != 1:
                expected = None
            c.require(_same(fields[name], expected), "NORMALIZED_RAW_VALUE:" + name + ":" + str(number))
        for name in port_map["unimplemented"]:
            c.require(fields[name] is None, "UNPROVEN_FIELD_PROMOTED:" + name)
        epoch, pending_epoch = old.bind_epoch(states, now, fields["rst_n"])
        c.require(fields["epoch"] == source.get("epoch") == epoch, "INDEPENDENT_RESET_EPOCH")
        counts["epoch_unknown"] += int(pending_epoch is not None)
        c.require(fields["cycle"] == cycle, "NORMALIZED_CYCLE")
        finish = int(number == window["row_count"])
        c.require(type(raw.get("finish")) is int and raw["finish"] == fields["finish"] == finish, "FINISH_COVERAGE")
        c.require(("FINISH" in row.get("events", [])) == bool(finish), "FINISH_EVENT")
        if fields["rst_n"] == 1 and fields["frame_tick"] == 1:
            observed_frames.append((epoch, cycle))
        counts["finish"] += finish
        counts["rows"] += 1
    c.require(counts["rows"] == window["row_count"] and counts["finish"] == 1, "COMPLETE_CAPTURE_WINDOW")
    c.require(observed_frames == planned_frames, "UNIQUE_FRAME_PLAN_COVERAGE_MISMATCH")
    marker = (f"MONITOR_END capture_id={capture_id} cycle={end['finish_cycle']} "
              f"time_ps={end['time_ps']} rows={end['row_count']} reason=PLANNED_WINDOW_END")
    marker_count = 0
    with paths["stdout"].open("rb") as stdout_file:
        while raw_line := stdout_file.readline(1024 * 1024 + 1):
            c.require(len(raw_line) <= 1024 * 1024, "STDOUT_LINE_SIZE_LIMIT")
            line = raw_line.decode("utf-8").removeprefix("# ").strip()
            if "MONITOR_END" in line:
                c.require(line == marker, "UNIQUE_ACTUAL_MONITOR_END")
                marker_count += 1
    c.require(marker_count == 1, "UNIQUE_ACTUAL_MONITOR_END")
    pending = ["PENDING_INDEPENDENT_PLAN_APPLY_MAPPING", "PENDING_AUDIO_STABLE_POLICY",
               "PENDING_M1_MATH_ORACLE", "PENDING_M2_PRODUCER_AUTHORITY"]
    if origin == "HDL_PUBLIC_CAPTURE_UNVERIFIED":
        pending.append("PENDING_TRUSTED_EXECUTION_RECEIPT")
    for role, expected in before.items():
        path = c.checked_descriptor(expected)
        c.require(c.artifact(path) == expected, "PROVENANCE_INPUT_CHANGED:" + role)
    result = {"schema": "M3_C9_CHAIN_PROVENANCE_V1", "capture_id": capture_id,
              "origin": origin, "status": "SYNTHETIC_CHAIN_BOUND" if origin == "SYNTHETIC_SCHEMA_FIXTURE" else "C9_CANDIDATE_PENDING_AUTHORITY",
              "counts": counts, "frame_count": len(observed_frames), "files": before,
              "source_contract_refs": refs, "pending": pending,
              "mechanical_binding_only": True, "real_verified": False,
              "execution_allowed": False, "board_release_allowed": False}
    c.write_json(out / "PROVENANCE.json", result)
    return {**result, "artifacts": {"provenance": c.artifact(out / "PROVENANCE.json")}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--request", required=True, type=Path)
    parser.add_argument("--artifacts", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    validate_capture(c.read_json(args.request), c.read_json(args.artifacts), args.output)
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
