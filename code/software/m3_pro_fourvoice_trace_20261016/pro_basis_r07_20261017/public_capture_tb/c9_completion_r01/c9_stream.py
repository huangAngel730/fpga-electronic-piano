"""Streaming C9 capture conversion; derived projections never become authority."""
from __future__ import annotations

import argparse
import hashlib
import json
from itertools import zip_longest
from pathlib import Path
import sys
from types import ModuleType

ROOT = Path(__file__).resolve().parents[6]
COMMON_PATH = ROOT / ("code/software/m3_pro_fourvoice_trace_20261016/"
    "pro_basis_r08_20261017/coordinator/task_day4_completion_20261017/common.py")
COMMON_SHA = "55cb7481fe9c0870247a7d8b2453dea859f0f2e81879795cc0e34ffe8c996dca"
SOFT = ROOT / "code/software/m3_pro_fourvoice_trace_20261016"
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016"
CAPTURE_DOC = DOC / "pro_basis_r07_20261017/public_capture_tb"
MAX_LINE_BYTES = 1024 * 1024
MAX_META_BYTES = 16 * 1024 * 1024
MAX_CAPTURE_BYTES = 64 * 1024 * 1024 * 1024
MAX_OUTPUT_BYTES = 512 * 1024 * 1024 * 1024
MAX_ROWS = 100_000_000
DEPENDENCIES = {
    "c9_capture": (
        SOFT / "pro_basis_r07_20261017/public_capture_tb/c9_binding/c9_capture.py",
        "0d3fcea8d75cdadcea6f6a663e6840735ccd050bbf072e01c3de61fa2477e931"),
    "bridge": (
        SOFT / "pro_basis_r07_20261017/oracle_bundle_bridge/c9_binding/c9_oracle_bridge.py",
        "5460dcf7e8539072200d55d123bc3855be2a759fea6eb84698c1e991fc22b4d8"),
}
FROZEN_DATA = {
    "port_map": (
        CAPTURE_DOC / "c9_binding/PORT_MAP_C9.json",
        "65a4fcca8b83ab72eaed3aaf5bf7cd48db18ad0691027aaaf57d1e9e4ced0807"),
    "old_map": (
        CAPTURE_DOC / "PORT_MAP.json",
        "686be53c43363f04bcee2bd1b70352000462493441483d6d7dccd40ca17d97da"),
}
ROW_KEYS = {"schema", "capture_id", "origin", "source", "fields",
            "raw_ports", "missing_reasons", "events", "semantics"}
SOURCE_KEYS = {"raw_sha256", "reset_edges_sha256", "line", "cycle", "epoch",
               "time_ps", "sampling_phase"}
_COMMON = None


def support():
    """Bootstrap only the coordinator's fixed source; no pyc or path imports."""
    global _COMMON
    if _COMMON is None:
        raw = COMMON_PATH.read_bytes()
        if hashlib.sha256(raw).hexdigest() != COMMON_SHA:
            raise ValueError("COMMON_SOURCE_CHANGED")
        module = ModuleType("_m3_c9_d4_common_b")
        module.__file__ = str(COMMON_PATH)
        exec(compile(raw, str(COMMON_PATH), "exec"), module.__dict__)
        _COMMON = module
    return _COMMON


def dependencies():
    c = support()
    loaded = {name: c.load_source(path, sha)
              for name, (path, sha) in DEPENDENCIES.items()}
    data = {}
    for name, (path, sha) in FROZEN_DATA.items():
        c.require(c.identity(path)["sha256"] == sha, "FROZEN_DATA:" + name)
        data[name] = c.read_json(path)
    loaded.update(data)
    binding_path = DOC / ("pro_basis_r07_20261017/oracle_bundle_bridge/"
                          "c9_binding/INPUT_BINDING.json")
    c.require(c.identity(binding_path)["sha256"] ==
              "30ad034522ce03a146f06d797923a259da9dd31081f788f703a0459f5eb0bd18",
              "C9_INPUT_BINDING_CHANGED")
    binding = c.read_json(binding_path)
    verified = loaded["bridge"].verify_binding(binding, ROOT)
    loaded["field_schema"] = verified["schema"]["properties"]
    loaded["binding"] = binding
    return loaded


def json_line(stream, value):
    c = support()
    raw = (json.dumps(value, ensure_ascii=False, separators=(",", ":"),
                      allow_nan=False) + "\n").encode("utf-8")
    c.require(len(raw) <= MAX_LINE_BYTES, "OUTPUT_LINE_BOUND")
    c.require(stream.tell() + len(raw) <= MAX_OUTPUT_BYTES, "OUTPUT_SIZE_BOUND")
    stream.write(raw)
    return hashlib.sha256(raw).hexdigest()


def bounded_metadata(path):
    c = support()
    with c.no_alias(path).open("rb") as stream:
        raw = stream.read(MAX_META_BYTES + 1)
    c.require(len(raw) <= MAX_META_BYTES, "METADATA_SIZE_BOUND")
    return raw


def checked_unchanged(descriptors):
    c = support()
    for descriptor in descriptors.values():
        c.checked_descriptor(descriptor, allow_external=True)


def iter_raw_records(path, digest):
    c = support()
    with c.no_alias(path).open("rb") as source:
        number = 0
        while True:
            physical = source.readline(MAX_LINE_BYTES + 1)
            if not physical:
                return
            number += 1
            c.require(number <= MAX_ROWS and len(physical) <= MAX_LINE_BYTES,
                      "RAW_LINE_OR_COUNT_BOUND")
            c.require(bool(physical.strip()), "EMPTY_RAW_LINE")
            digest.update(physical)
            item = c.loads(physical)
            c.require(isinstance(item, dict), "RAW_ROW_NOT_OBJECT")
            yield number, physical, item


def validate_public_row(row, number=None, loaded=None):
    """Validate the complete frozen C9 row; never invent missing observations."""
    c = support()
    d = loaded or dependencies()
    bridge = d["bridge"]
    c.require(isinstance(row, dict) and set(row) == ROW_KEYS, "C9_ROW_ENVELOPE")
    c.require(row["schema"] == "M3_R7A_C9_PUBLIC_ROW_V1", "C9_ROW_SCHEMA")
    c.require(row["origin"] in {"SYNTHETIC_SCHEMA_FIXTURE",
                               "HDL_PUBLIC_CAPTURE_UNVERIFIED"}, "C9_ORIGIN")
    c.require(isinstance(row["capture_id"], str) and row["capture_id"], "C9_CAPTURE_ID")
    fields = row["fields"]
    c.require(isinstance(fields, dict) and set(fields) == set(bridge.REQUIRED_FIELDS),
              "C9_FIELDS_74")
    schema_path = ROOT / bridge.FROZEN_INPUTS["row_schema"][0]
    if "field_schema" not in d:
        frozen = bridge.FROZEN_INPUTS["row_schema"]
        c.require(c.identity(schema_path) == {"bytes": frozen[1], "sha256": frozen[2]},
                  "C9_FIELD_SCHEMA_IDENTITY")
        d["field_schema"] = c.read_json(schema_path)["properties"]
    for name in bridge.REQUIRED_FIELDS:
        c.require(bridge._matches_schema(fields[name], d["field_schema"][name]),
                  "C9_FIELD_VALUE:" + name)
    source = row["source"]
    c.require(isinstance(source, dict) and set(source) == SOURCE_KEYS, "C9_SOURCE_KEYS")
    for key in ("raw_sha256", "reset_edges_sha256"):
        value = source[key]
        c.require(isinstance(value, str) and len(value) == 64
                  and all(char in "0123456789abcdef" for char in value), "C9_SOURCE_SHA")
    for key in ("line", "cycle", "time_ps"):
        c.require(type(source[key]) is int and source[key] >= (1 if key == "line" else 0),
                  "C9_SOURCE_POSITION")
    c.require(source["sampling_phase"] == "POSEDGE_PRE_NBA"
              and source["cycle"] == fields["cycle"]
              and source["epoch"] == fields["epoch"], "C9_SOURCE_FIELDS")
    if number is not None:
        c.require(source["line"] == number and source["cycle"] == number - 1,
                  "C9_SOURCE_SEQUENCE")
    c.require(isinstance(row["raw_ports"], dict)
              and set(row["raw_ports"]) == set(d["port_map"]["raw_ports"]),
              "C9_RAW_PORTS_72")
    m = d.get("pure")
    if m is None:
        m = d["c9_capture"].legacy_pure()
        d["pure"] = m
    values = {name: m.scalar(row["raw_ports"][name], spec)
              for name, spec in d["port_map"]["raw_ports"].items()}
    for field, entry in d["port_map"]["normalized_mapping"].items():
        expected = values[entry["port"]]
        if field == "tx_req_id" and values["obs_tx_req_id_valid"] != 1:
            expected = None
        c.require(fields[field] == expected, "C9_RAW_NORMALIZED_MISMATCH:" + field)
    c.require(isinstance(row["missing_reasons"], dict)
              and isinstance(row["events"], list) and isinstance(row["semantics"], dict),
              "C9_EVIDENCE_SHAPE")
    c.require(fields["apply_event_seq"] is None, "INDEPENDENT_PLAN_MAPPING_UNVERIFIED")
    c.require(row["semantics"].get("independent_plan_mapping") == "PENDING",
              "INDEPENDENT_PLAN_MAPPING_UNVERIFIED")
    return row


def iter_public_rows(path, loaded=None):
    c = support()
    d = loaded or dependencies()
    capture = None
    prior_time = -1
    count = 0
    for number, row in enumerate(c.iter_jsonl(path, MAX_LINE_BYTES), 1):
        c.require(number <= MAX_ROWS, "ROW_COUNT_BOUND")
        validate_public_row(row, number, d)
        identity = (row["capture_id"], row["origin"], row["source"]["raw_sha256"],
                    row["source"]["reset_edges_sha256"])
        if capture is None:
            capture = identity
        c.require(identity == capture, "MIXED_C9_CAPTURE")
        c.require(row["source"]["time_ps"] > prior_time, "C9_TIME_SEQUENCE")
        prior_time = row["source"]["time_ps"]
        count += 1
        yield row
    c.require(count > 0, "EMPTY_C9_CAPTURE")


def _normalize_row(item, previous, d, raw_sha):
    c = support()
    m = d["pure"]
    port_map = d["port_map"]
    values = {name: m.scalar(item["ports"][name], spec)
              for name, spec in port_map["raw_ports"].items()}
    fields = {name: values[entry["port"]]
              for name, entry in port_map["normalized_mapping"].items()}
    reasons = dict(port_map["unimplemented"])
    fields.update({name: None for name in reasons})
    fields.update(cycle=previous["fields"]["cycle"],
                  epoch=previous["fields"]["epoch"], finish=item["finish"])
    if fields["epoch"] is None:
        reasons["epoch"] = previous["missing_reasons"].get("epoch", "RESET_EPOCH_UNKNOWN")
    for name, value in fields.items():
        if isinstance(value, str):
            reasons[name] = "OBSERVED_PUBLIC_XZ"
    if values["obs_tx_req_id_valid"] != 1:
        fields["tx_req_id"] = None
        reasons["tx_req_id"] = "NO_KNOWN_VALID_TX_REQUEST_ID_RAW_BITS_RETAINED"
    cause = "INACTIVE_RAW_HELD_VALUES_UNINTERPRETED"
    if fields["apply_valid"] == 1:
        cause = "UNKNOWN_CAUSE"
        if fields["apply_kind"] in (3, 4, 8):
            sentinels = (fields["router_apply_seq_valid"], fields["apply_data"],
                         fields["router_apply_seq"])
            if all(type(value) is int for value in sentinels):
                c.require(sentinels == (0, 0, 0), "INVALID_CAUSE_SENTINEL_CONTRACT")
                cause = "INVALID_CAUSE_SENTINEL_NOT_AN_INPUT_EVENT"
        elif fields["router_apply_seq_valid"] == 1:
            cause = "ROUTER_CAUSE_ONLY_INDEPENDENT_PLAN_MAPPING_PENDING"
    packing = None
    if fields["config_take"] == 1 and type(fields["config_payload"]) is int:
        payload = fields["config_payload"]
        packing = {"enable": (payload >> 61) & 1,
                   "delay_samples": (payload >> 45) & 65535,
                   "dry_gain": (payload >> 30) & 32767,
                   "wet_gain": (payload >> 15) & 32767,
                   "feedback": payload & 32767}
    return {"schema": "M3_R7A_C9_PUBLIC_ROW_V1",
            "capture_id": previous["capture_id"], "origin": previous["origin"],
            "source": {**previous["source"], "raw_sha256": raw_sha},
            "fields": {name: fields[name] for name in d["bridge"].REQUIRED_FIELDS},
            "raw_ports": item["ports"], "missing_reasons": reasons,
            "events": previous["events"],
            "semantics": {
                "apply_cause": cause, "stage_deduplicated": False,
                "independent_plan_mapping": "PENDING",
                "config_on_actual_take": packing,
                "advance_frame_req_id_is_FRAME_F": False,
                "advance_mask_source": "PUBLIC_M1_LANE_TICK_ROUTE_NOT_REQUEST_ACCEPTANCE"}}


def convert_files(raw, resets, end, stdout, output_dir,
                  origin="SYNTHETIC_SCHEMA_FIXTURE"):
    """Stream files, retaining the full raw and a clearly derived 43-port file."""
    c = support()
    d = dependencies()
    m = d["c9_capture"].legacy_pure()
    d["pure"] = m
    paths = {"raw": Path(raw), "resets": Path(resets), "end": Path(end),
             "stdout": Path(stdout)}
    inputs = {name: c.artifact(path) for name, path in paths.items()}
    c.require(inputs["raw"]["bytes"] <= MAX_CAPTURE_BYTES, "CAPTURE_SIZE_BOUND")
    c.require(origin in {"SYNTHETIC_SCHEMA_FIXTURE",
                         "HDL_PUBLIC_CAPTURE_UNVERIFIED"}, "ORIGIN")
    out = c.output_directory(output_dir)
    projected = out / "DERIVED_RAW_43.jsonl"
    public = out / "PUBLIC_ROWS_C9.jsonl"
    line_index = out / "RAW_PUBLIC_LINE_INDEX.jsonl"
    legacy_receipt = {}
    try:
        count = 0
        projection_input_digest = hashlib.sha256()
        with projected.open("xb") as sink:
            for count, physical, item in iter_raw_records(paths["raw"], projection_input_digest):
                c.require(count <= MAX_ROWS, "ROW_COUNT_BOUND")
                m.need(item.get("schema") == "M3_R7A_C9_RAW_CORE_ROW_V1",
                       "C9_RAW_SCHEMA_REQUIRED")
                m.exact(item.get("ports"), d["port_map"]["raw_ports"], "C9_RAW_PUBLIC_PORT_SET")
                for name, spec in d["port_map"]["raw_ports"].items():
                    m.scalar(item["ports"][name], spec)
                projection = {**item, "schema": "M3_R7A_RAW_CORE_ROW_V1",
                              "ports": {name: item["ports"][name]
                                        for name in d["old_map"]["raw_ports"]}}
                json_line(sink, projection)
        c.require(count > 0, "EMPTY_RAW_CAPTURE")
        c.require(projection_input_digest.hexdigest() == inputs["raw"]["sha256"],
                  "RAW_CHANGED_DURING_PROJECTION")
        legacy = m.stream_rows(projected, bounded_metadata(paths["resets"]),
                               bounded_metadata(paths["end"]),
                               bounded_metadata(paths["stdout"]), d["old_map"],
                               origin, legacy_receipt)
        original_digest = hashlib.sha256()
        with public.open("xb") as sink, line_index.open("xb") as index_sink:
            for previous, current in zip_longest(
                    legacy, iter_raw_records(paths["raw"], original_digest)):
                c.require(previous is not None and current is not None,
                          "PROJECTION_ROW_COUNT_MISMATCH")
                number, physical, item = current
                row = _normalize_row(item, previous, d, inputs["raw"]["sha256"])
                validate_public_row(row, number, d)
                row_sha = json_line(sink, row)
                json_line(index_sink, {
                    "line": number, "cycle": row["source"]["cycle"],
                    "epoch": row["source"]["epoch"],
                    "raw_line_sha256": hashlib.sha256(physical).hexdigest(),
                    "public_line_sha256": row_sha})
        c.require(original_digest.hexdigest() == inputs["raw"]["sha256"], "RAW_CHANGED_DURING_READ")
        checked_unchanged(inputs)
        result = {
            "schema": "M3_D4_C9_STREAM_RECEIPT_V1",
            "status": "SOFTWARE_CONVERTED_PENDING_REAL_AUTHORITY",
            "row_count": count, "origin": origin, "inputs": inputs,
            "c9_contract_inputs": d["binding"]["inputs"],
            "artifacts": {"public_rows": c.artifact(public),
                          "derived_raw_43": c.artifact(projected),
                          "line_index": c.artifact(line_index)},
            "legacy_validation": legacy_receipt, "derivation": m.derivation,
            "limits": {"line_bytes": MAX_LINE_BYTES, "metadata_bytes": MAX_META_BYTES,
                       "capture_bytes": MAX_CAPTURE_BYTES, "output_bytes": MAX_OUTPUT_BYTES,
                       "rows": MAX_ROWS},
            "whole_capture_read_bytes_or_list": False,
            "FRAME_PLAN_generated": False, "source_authenticated": False,
            "math_verified": False, "real_verified": False, "board_release_allowed": False,
            "pending": ["INDEPENDENT_PLAN_MAPPING", "AUDIO_STABLE",
                        "REAL_CAPTURE_AUTHENTICATION", "M1_MATH", "M2_ADMISSION"]}
        c.write_json(out / "RECEIPT.json", result)
        return result
    except BaseException as error:
        c.write_json(out / "FAILURE.json", {
            "status": "REJECT_PARTIAL_ARTIFACTS_RETAINED",
            "error": type(error).__name__ + ":" + str(error),
            "inputs": inputs, "real_verified": False, "board_release_allowed": False})
        raise


def main():
    parser = argparse.ArgumentParser()
    for name in ("raw", "resets", "end", "stdout", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--origin", default="HDL_PUBLIC_CAPTURE_UNVERIFIED",
                        choices=("SYNTHETIC_SCHEMA_FIXTURE", "HDL_PUBLIC_CAPTURE_UNVERIFIED"))
    args = parser.parse_args()
    result = convert_files(args.raw, args.resets, args.end, args.stdout,
                           args.output, args.origin)
    print(json.dumps({"status": result["status"], "rows": result["row_count"]}))
    return 3


if __name__ == "__main__":
    raise SystemExit(main())
