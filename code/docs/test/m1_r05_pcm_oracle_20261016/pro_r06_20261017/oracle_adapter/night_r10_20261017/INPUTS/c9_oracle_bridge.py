"""Mechanical C9 public-row bridge; no DSP oracle or execution authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any, Iterable


BINDING_SCHEMA = "M3_R7C_C9_INPUT_BINDING_V1"
ROW_SCHEMA = "M3_R7C_C9_PUBLIC_ROW_V1"
R7A_ROW_SCHEMA = "M3_R7A_C9_PUBLIC_ROW_V1"
OUTPUT_SCHEMA = "M3_R7C_C9_MECHANICAL_INDEX_V1"
BASELINE = "16ac226552f6fb65347b229b8fad42146ed45644"

FROZEN_INPUTS = {
    "source_closure": (
        "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/"
        "r06_public_chain_20261017/c9_m1_semantics_20261017/"
        "SOURCE_CLOSURE_R06C9.zip",
        182685,
        "d458ab16277bd46751318ac368b22df1b21b35c4867c47942e7bff7d27fc3aa2",
    ),
    "source_decision": (
        "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/"
        "r06_public_chain_20261017/c9_m1_semantics_20261017/"
        "SOURCE_DECISION_R06C9.json",
        25519,
        "2766cf25223072c244d03da36e656f1b0946363e2d3cfa8c983d74fe9c3cd8a2",
    ),
    "capture_contract": (
        "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/"
        "r06_observer_20261017/c9_m1_semantics_20261017/"
        "CAPTURE_CONTRACT_R06C9.json",
        8582,
        "2a36e92e5ea4c518f9b3a4787e5632271907db7603dcedeed31bf2dfe74a2ead",
    ),
    "row_schema": (
        "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/"
        "r06_observer_20261017/c9_m1_semantics_20261017/"
        "NORMALIZED_ROW_SCHEMA_R06C9.json",
        33317,
        "0fca8cd3deba9f5edd11aa2b97e3023465f3210b03eb6e6115b3eb7eceb927c1",
    ),
    "observer_exports": (
        "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/"
        "r06_observer_20261017/c9_m1_semantics_20261017/"
        "OBSERVER_EXPORTS_R06C9.json",
        12066,
        "d8ee0c4c4ffc284e076a89a52aed1dd2363107ab6d7a63f77202b1eeb53a4867",
    ),
}

REQUIRED_FIELDS = (
    "cycle", "epoch", "rst_n", "frame_tick", "event_valid", "event_ready",
    "event_data", "apply_valid", "apply_event_seq", "apply_data",
    "occupied_mask", "releasing_mask", "note_on_mask", "note_off_mask",
    "retire_mask", "slot_sources", "slot_channels", "slot_notes",
    "slot_generations", "req_valid", "req_ready", "req_id", "advance_mask",
    "advance_frame_req_id", "result_valid", "result_ready", "result_id",
    "result_left", "result_right", "result_clip_mask", "commit", "commit_id",
    "commit_left", "commit_right", "commit_clip", "cancel", "cancel_reason",
    "config_valid", "config_ready", "config_payload", "effect_input_valid",
    "effect_input_ready", "effect_input_id", "effect_input_left",
    "effect_input_right", "effect_input_clip_mask", "tx_sample_valid",
    "tx_frame_id", "tx_req_id", "tx_left", "tx_right", "tx_clip", "tx_hold",
    "tx_startup_zero", "bclk", "ws", "din", "pll_locked", "audio_stable",
    "pa_en", "finish", "tx_metadata_valid", "tx_req_id_valid",
    "tx_clip_mask", "metadata_error", "frame_id_overflow", "apply_kind",
    "apply_mask", "router_apply_seq", "router_apply_seq_valid", "config_take",
    "upstream_clip_mask", "effect_clip_mask", "feedback_clip_mask",
)

PRESERVED_C9_FIELDS = (
    "apply_valid", "apply_data", "apply_kind", "apply_mask",
    "router_apply_seq", "router_apply_seq_valid", "config_take",
    "upstream_clip_mask", "effect_clip_mask", "feedback_clip_mask",
)


class C9BridgeReject(ValueError):
    """The C9 evidence cannot be indexed without invention or loss."""


def _reject_float(value: str) -> None:
    raise C9BridgeReject("NONINTEGER_JSON_NUMBER:" + value)


def _reject_constant(value: str) -> None:
    raise C9BridgeReject("NONFINITE_JSON_NUMBER:" + value)


def _pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in items:
        if key in result:
            raise C9BridgeReject("DUPLICATE_JSON_KEY:" + key)
        result[key] = value
    return result


def _loads(raw: bytes, where: str) -> Any:
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_pairs,
                          parse_float=_reject_float,
                          parse_constant=_reject_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise C9BridgeReject("UNREADABLE_JSON:" + where + ":" + str(exc)) from exc


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _path_text(path: Path, repo_root: Path) -> str:
    resolved_path = path.resolve()
    try:
        return resolved_path.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(resolved_path)


def _resolve(repo_root: Path, descriptor: Any, role: str) -> Path:
    if (not isinstance(descriptor, dict)
            or set(descriptor) != {"path", "bytes", "sha256"}):
        raise C9BridgeReject("INPUT_DESCRIPTOR:" + role)
    expected = FROZEN_INPUTS[role]
    if (descriptor["path"], descriptor["bytes"], descriptor["sha256"]) != expected:
        raise C9BridgeReject("FROZEN_INPUT_IDENTITY:" + role)
    path = (repo_root / descriptor["path"]).resolve()
    if (not path.is_file() or path.stat().st_size != descriptor["bytes"]
            or _sha256(path) != descriptor["sha256"]):
        raise C9BridgeReject("INPUT_BYTES_MISMATCH:" + role)
    return path


def verify_binding(binding: dict[str, Any], repo_root: Path) -> dict[str, Any]:
    required = {"schema", "baseline", "status", "inputs", "trace", "pending",
                "execution", "board_release_allowed"}
    if not isinstance(binding, dict) or set(binding) != required:
        raise C9BridgeReject("BINDING_SHAPE")
    if binding["schema"] != BINDING_SCHEMA or binding["baseline"] != BASELINE:
        raise C9BridgeReject("BINDING_VERSION")
    if set(binding["inputs"]) != set(FROZEN_INPUTS):
        raise C9BridgeReject("BINDING_ROLE_SET")
    paths = {role: _resolve(repo_root, binding["inputs"][role], role)
             for role in FROZEN_INPUTS}
    source = _loads(paths["source_decision"].read_bytes(), "source_decision")
    contract = _loads(paths["capture_contract"].read_bytes(), "capture_contract")
    schema = _loads(paths["row_schema"].read_bytes(), "row_schema")
    exports = _loads(paths["observer_exports"].read_bytes(), "observer_exports")
    if (source.get("source_units") != 72 or source.get("ROMs") != 9
            or source.get("headers") != 2 or source.get("literal_modules") != 74
            or source.get("compiled") is not False
            or source.get("board_release_allowed") is not False):
        raise C9BridgeReject("SOURCE_DECISION_CONTRACT")
    routes = contract.get("new_routed_ports")
    if (contract.get("field_count") != 74
            or contract.get("observation_ports") != 67
            or contract.get("nineteen_fields") != 19
            or not isinstance(routes, list) or len(routes) != 28
            or contract.get("HDL_EDA_device_runs_authorized") != 0
            or contract.get("board_release_allowed") is not False):
        raise C9BridgeReject("CAPTURE_CONTRACT")
    if (schema.get("required") != list(REQUIRED_FIELDS)
            or schema.get("additionalProperties") is not False
            or not isinstance(schema.get("properties"), dict)
            or set(schema["properties"]) != set(REQUIRED_FIELDS)):
        raise C9BridgeReject("ROW_SCHEMA_74")
    ports = exports.get("expected_observation_ports")
    export_routes = exports.get("new_routes")
    if (not isinstance(ports, dict) or len(ports) != 67
            or not isinstance(export_routes, list) or len(export_routes) != 28
            or exports.get("board_release_allowed") is not False):
        raise C9BridgeReject("EXPORTS_67")
    route_fields = {route.get("field") for route in export_routes}
    if not set(PRESERVED_C9_FIELDS) <= route_fields:
        raise C9BridgeReject("C9_ROUTE_FIELDS")
    return {"paths": paths, "schema": schema, "contract": contract,
            "exports": exports}


def _matches_schema(value: Any, rules: dict[str, Any]) -> bool:
    for option in rules.get("anyOf", []):
        kind = option.get("type")
        if kind == "null" and value is None:
            return True
        if kind == "integer" and type(value) is int:
            if "minimum" in option and value < option["minimum"]:
                continue
            if "maximum" in option and value > option["maximum"]:
                continue
            if "enum" in option and value not in option["enum"]:
                continue
            return True
        if kind == "string" and isinstance(value, str):
            if "maxLength" in option and len(value) > option["maxLength"]:
                continue
            if "enum" in option and value not in option["enum"]:
                continue
            if "pattern" in option and re.fullmatch(option["pattern"], value) is None:
                continue
            return True
    return False


def _known_bit(value: Any) -> bool | None:
    if type(value) is int and value in (0, 1):
        return bool(value)
    return None


def _lane_advance(mask: Any) -> dict[str, Any]:
    if type(mask) is int or (isinstance(mask, str)
                             and re.fullmatch("[01]{1,4}", mask)):
        numeric = mask if type(mask) is int else int(mask, 2)
        exact_four = type(mask) is int or len(mask) == 4
        if numeric == 0b1111 and exact_four:
            return {"raw_mask": mask, "all_four_lanes": True,
                    "status": "ALL_FOUR_LANES",
                    "reason": "exact public advance_mask is 4'b1111"}
        if numeric == 0:
            return {"raw_mask": mask, "all_four_lanes": False,
                    "status": "NO_LANE_ADVANCE",
                    "reason": "exact public advance_mask is 4'b0000"}
        return {"raw_mask": mask, "all_four_lanes": False,
                "status": "PARTIAL_LANE_MASK",
                "reason": "nonzero mask is not proof that all four lanes advanced"}
    return {"raw_mask": mask, "all_four_lanes": None,
            "status": "PENDING_UNKNOWN_LANE_MASK",
            "reason": "X/Z/null mask cannot establish four-lane advance"}


def _plan_sequence(record: dict[str, Any], fields: dict[str, Any],
                   line: int) -> Any:
    association = record["plan_association"]
    if association is not None or fields["apply_event_seq"] is not None:
        raise C9BridgeReject(f"INDEPENDENT_PLAN_MAPPING_UNVERIFIED:{line}")
    return None


def _adapt_r7a_public_record(
        record: Any, descriptor: dict[str, Any], line: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Mechanically bind Role A PUBLIC_ROWS_C9 without editing its JSONL."""
    required = {"schema", "capture_id", "origin", "source", "fields",
                "raw_ports", "missing_reasons", "events", "semantics"}
    if not isinstance(record, dict) or set(record) != required:
        raise C9BridgeReject(f"R7A_ROW_ENVELOPE:{line}")
    if record["schema"] != R7A_ROW_SCHEMA:
        raise C9BridgeReject(f"R7A_ROW_SCHEMA:{line}")
    origin_map = {
        "SYNTHETIC_SCHEMA_FIXTURE": "SYNTHETIC_C9_FIXTURE",
        "HDL_PUBLIC_CAPTURE_UNVERIFIED": "HDL_PUBLIC_CAPTURE_UNVERIFIED",
    }
    if record["origin"] not in origin_map:
        raise C9BridgeReject(f"R7A_ROW_ORIGIN:{line}")
    if (not isinstance(record["raw_ports"], dict)
            or not isinstance(record["missing_reasons"], dict)
            or not isinstance(record["events"], list)
            or not isinstance(record["semantics"], dict)):
        raise C9BridgeReject(f"R7A_EVIDENCE_SHAPE:{line}")
    fields = record["fields"]
    if not isinstance(fields, dict) or set(fields) != set(REQUIRED_FIELDS):
        raise C9BridgeReject(f"R7A_FIELDS_NOT_EXACT_74:{line}")
    source = record["source"]
    source_keys = {"raw_sha256", "reset_edges_sha256", "line", "cycle",
                   "epoch", "time_ps", "sampling_phase"}
    if (not isinstance(source, dict) or set(source) != source_keys
            or not isinstance(source["raw_sha256"], str)
            or re.fullmatch("[0-9a-f]{64}", source["raw_sha256"]) is None
            or not isinstance(source["reset_edges_sha256"], str)
            or re.fullmatch("[0-9a-f]{64}",
                            source["reset_edges_sha256"]) is None
            or source["line"] != line
            or source["cycle"] != fields["cycle"]
            or source["epoch"] != fields["epoch"]
            or source["sampling_phase"] != "POSEDGE_PRE_NBA"
            or type(source["time_ps"]) is not int
            or source["time_ps"] < 0):
        raise C9BridgeReject(f"R7A_SOURCE_IDENTITY:{line}")
    adapted = {
        "schema": ROW_SCHEMA,
        "capture_id": record["capture_id"],
        "origin": origin_map[record["origin"]],
        "source": {
            "trace_path": descriptor["path"],
            "raw_capture_sha256": source["raw_sha256"],
            "line": source["line"],
            "cycle": source["cycle"],
            "epoch": source["epoch"],
            "sampling_phase": source["sampling_phase"],
        },
        "fields": {name: fields[name] for name in REQUIRED_FIELDS},
        "plan_association": None,
    }
    evidence = {
        "schema": record["schema"],
        "origin": record["origin"],
        "source": source,
        "raw_ports": record["raw_ports"],
        "missing_reasons": record["missing_reasons"],
        "events": record["events"],
        "semantics": record["semantics"],
    }
    return adapted, evidence


def _apply_classification(fields: dict[str, Any]) -> str:
    values = [fields[name] for name in ("apply_valid", "apply_kind", "apply_data",
                                         "router_apply_seq",
                                         "router_apply_seq_valid")]
    if any(type(value) is not int for value in values):
        return "PENDING_UNKNOWN_APPLY_SEMANTICS"
    kind = fields["apply_kind"]
    if (kind in {3, 4, 8} and fields["apply_data"] == 0
            and fields["router_apply_seq"] == 0
            and fields["router_apply_seq_valid"] == 0):
        return "INVALID_CAUSE_SENTINEL"
    if fields["apply_valid"] != 1:
        return "NOT_APPLIED"
    if kind == 0:
        return "NOT_APPLIED_KIND_NONE"
    if kind not in range(9):
        return "PENDING_RESERVED_KIND"
    if fields["router_apply_seq_valid"] != 1:
        return "PENDING_ROUTER_SEQUENCE_CAUSE"
    return "ROUTER_STAGE_PRESERVED"


def index_records(binding: dict[str, Any], raw_lines: Iterable[bytes],
                  repo_root: Path,
                  input_format: str = "r7c-contract") -> dict[str, Any]:
    verified = verify_binding(binding, repo_root)
    trace = binding["trace"]
    if (not isinstance(trace, dict) or set(trace) != {"status", "descriptor"}
            or trace["status"] not in {"SYNTHETIC_C9_FIXTURE_NOT_RUN",
                                       "REAL_C9_CAPTURE_UNVERIFIED"}
            or not isinstance(trace["descriptor"], dict)):
        raise C9BridgeReject("TRACE_DESCRIPTOR_PENDING")
    descriptor = trace["descriptor"]
    if (set(descriptor) != {"path", "bytes", "sha256"}
            or not isinstance(descriptor["path"], str)
            or not descriptor["path"]
            or type(descriptor["bytes"]) is not int
            or descriptor["bytes"] < 0
            or not isinstance(descriptor["sha256"], str)
            or re.fullmatch("[0-9a-f]{64}", descriptor["sha256"]) is None):
        raise C9BridgeReject("TRACE_DESCRIPTOR")
    rows = []
    properties = verified["schema"]["properties"]
    capture_id = None
    origin = None
    raw_capture_sha256 = None
    for line, raw in enumerate(raw_lines, start=1):
        if not raw.strip():
            raise C9BridgeReject(f"EMPTY_TRACE_LINE:{line}")
        record = _loads(raw, f"trace:{line}")
        upstream_evidence = None
        if input_format == "r7a-public-c9":
            record, upstream_evidence = _adapt_r7a_public_record(
                record, descriptor, line)
        elif input_format != "r7c-contract":
            raise C9BridgeReject("INPUT_FORMAT")
        required = {"schema", "capture_id", "origin", "source", "fields",
                    "plan_association"}
        if not isinstance(record, dict) or set(record) != required:
            raise C9BridgeReject(f"ROW_ENVELOPE:{line}")
        if record["schema"] != ROW_SCHEMA:
            raise C9BridgeReject(f"ROW_SCHEMA:{line}")
        if (not isinstance(record["capture_id"], str) or not record["capture_id"]
                or record["origin"] not in {"SYNTHETIC_C9_FIXTURE",
                                             "HDL_PUBLIC_CAPTURE_UNVERIFIED"}):
            raise C9BridgeReject(f"ROW_IDENTITY:{line}")
        if capture_id is None:
            capture_id, origin = record["capture_id"], record["origin"]
        if record["capture_id"] != capture_id or record["origin"] != origin:
            raise C9BridgeReject(f"MIXED_CAPTURE:{line}")
        fields = record["fields"]
        if not isinstance(fields, dict) or list(fields) != list(REQUIRED_FIELDS):
            raise C9BridgeReject(f"FIELDS_NOT_EXACT_74:{line}")
        for name in REQUIRED_FIELDS:
            if not _matches_schema(fields[name], properties[name]):
                raise C9BridgeReject(f"FIELD_VALUE:{line}:{name}")
        source = record["source"]
        source_keys = {"trace_path", "raw_capture_sha256", "line", "cycle", "epoch",
                       "sampling_phase"}
        if (not isinstance(source, dict) or set(source) != source_keys
                or source["trace_path"] != descriptor["path"]
                or not isinstance(source["raw_capture_sha256"], str)
                or re.fullmatch("[0-9a-f]{64}",
                                source["raw_capture_sha256"]) is None
                or source["line"] != line
                or source["cycle"] != fields["cycle"]
                or source["epoch"] != fields["epoch"]
                or source["sampling_phase"] != "POSEDGE_PRE_NBA"):
            raise C9BridgeReject(f"SOURCE_IDENTITY:{line}")
        if raw_capture_sha256 is None:
            raw_capture_sha256 = source["raw_capture_sha256"]
        elif source["raw_capture_sha256"] != raw_capture_sha256:
            raise C9BridgeReject(f"MIXED_RAW_CAPTURE:{line}")
        plan_sequence = _plan_sequence(record, fields, line)
        frame_flag = _known_bit(fields["frame_tick"])
        indexed_row = {
            "source": {**source, "raw_line_sha256": hashlib.sha256(raw).hexdigest()},
            "fields": fields,
            "frame_f": frame_flag,
            "advance_request_tag": fields["advance_frame_req_id"],
            "lane_advance": _lane_advance(fields["advance_mask"]),
            "apply": {
                "classification": _apply_classification(fields),
                "apply_valid": fields["apply_valid"],
                "apply_data": fields["apply_data"],
                "apply_kind": fields["apply_kind"],
                "apply_mask": fields["apply_mask"],
                "router_apply_seq": fields["router_apply_seq"],
                "router_apply_seq_valid": fields["router_apply_seq_valid"],
                "independent_apply_event_seq": plan_sequence,
            },
            "config_take": fields["config_take"],
            "clip": {
                "upstream": fields["upstream_clip_mask"],
                "effect": fields["effect_clip_mask"],
                "feedback": fields["feedback_clip_mask"],
            },
            "audio_stable_raw": fields["audio_stable"],
        }
        if upstream_evidence is not None:
            indexed_row["upstream_evidence"] = upstream_evidence
        rows.append(indexed_row)
    if not rows:
        raise C9BridgeReject("EMPTY_TRACE")
    return {
        "schema": OUTPUT_SCHEMA,
        "status": "SYNTHETIC_C9_INDEX" if origin == "SYNTHETIC_C9_FIXTURE"
                  else "C9_REAL_CANDIDATE_PENDING_AUTHORITY",
        "baseline": BASELINE,
        "capture_id": capture_id,
        "origin": origin,
        "row_count": len(rows),
        "rows": rows,
        "trace_input": descriptor,
        "input_adapter": {
            "mode": input_format,
            "upstream_schema": (R7A_ROW_SCHEMA if input_format == "r7a-public-c9"
                                else ROW_SCHEMA),
            "field_values_modified": False,
            "plan_association_invented": False,
        },
        "contract_inputs": {role: binding["inputs"][role]
                            for role in FROZEN_INPUTS},
        "pending": ["PENDING_INDEPENDENT_INPUT_PLAN_MAPPING",
                    "PENDING_REAL_LANE_TICK_EVIDENCE",
                    "PENDING_AUDIO_STABLE_POLICY",
                    "PENDING_REAL_C9_TRACE"],
        "router_seq_used_as_plan_seq": False,
        "advance_request_tag_used_as_frame_f": False,
        "deduplicated_by_router_seq": False,
        "dsp_oracle_executed": False,
        "hdl_eda_device_called": False,
        "real_verified": False,
        "board_release_allowed": False,
    }


def _bind_pending_trace(binding: dict[str, Any], trace_path: Path, raw: bytes,
                        repo_root: Path, input_format: str) -> dict[str, Any]:
    if not isinstance(binding, dict) or not isinstance(binding.get("trace"), dict):
        raise C9BridgeReject("BINDING_SHAPE")
    if binding["trace"].get("descriptor") is not None:
        return binding
    if binding.get("trace") != {"status": "PENDING_REAL_C9_TRACE",
                                 "descriptor": None}:
        raise C9BridgeReject("TRACE_DESCRIPTOR_PENDING")
    physical_lines = raw.splitlines(keepends=True)
    if not physical_lines or not physical_lines[0].strip():
        raise C9BridgeReject("EMPTY_TRACE")
    first = _loads(physical_lines[0], "trace:1")
    origins = ({"SYNTHETIC_SCHEMA_FIXTURE": "SYNTHETIC_C9_FIXTURE_NOT_RUN",
                "HDL_PUBLIC_CAPTURE_UNVERIFIED": "REAL_C9_CAPTURE_UNVERIFIED"}
               if input_format == "r7a-public-c9" else
               {"SYNTHETIC_C9_FIXTURE": "SYNTHETIC_C9_FIXTURE_NOT_RUN",
                "HDL_PUBLIC_CAPTURE_UNVERIFIED": "REAL_C9_CAPTURE_UNVERIFIED"})
    if not isinstance(first, dict) or first.get("origin") not in origins:
        raise C9BridgeReject("TRACE_ORIGIN_FOR_BINDING")
    path_text = _path_text(trace_path, repo_root)
    return {
        **binding,
        "trace": {
            "status": origins[first["origin"]],
            "descriptor": {
                "path": path_text,
                "bytes": len(raw),
                "sha256": hashlib.sha256(raw).hexdigest(),
            },
        },
    }


def build_index(binding_path: Path, trace_path: Path, repo_root: Path,
                input_format: str = "r7c-contract") -> dict[str, Any]:
    binding = _loads(binding_path.read_bytes(), str(binding_path))
    raw = trace_path.read_bytes()
    binding = _bind_pending_trace(binding, trace_path, raw, repo_root,
                                  input_format)
    descriptor = binding.get("trace", {}).get("descriptor")
    descriptor_path = Path(descriptor["path"]) if isinstance(descriptor, dict) \
        and isinstance(descriptor.get("path"), str) else None
    if (not isinstance(descriptor, dict) or descriptor_path is None
            or (descriptor_path if descriptor_path.is_absolute()
                else repo_root / descriptor_path).resolve() != trace_path.resolve()
            or trace_path.stat().st_size != descriptor.get("bytes")
            or hashlib.sha256(raw).hexdigest() != descriptor.get("sha256")):
        raise C9BridgeReject("TRACE_BYTES_MISMATCH")
    return index_records(binding, raw.splitlines(keepends=True), repo_root,
                         input_format=input_format)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", required=True, type=Path)
    parser.add_argument("--trace", required=True, type=Path)
    parser.add_argument("--repo-root", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--input-format",
                        choices=("r7c-contract", "r7a-public-c9"),
                        default="r7c-contract")
    args = parser.parse_args()
    report = build_index(args.binding, args.trace, args.repo_root,
                         input_format=args.input_format)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2,
                                      sort_keys=True) + "\n",
                           encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
