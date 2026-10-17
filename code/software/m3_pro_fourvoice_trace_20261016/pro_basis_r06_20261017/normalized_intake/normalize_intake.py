"""Normalize an R06 61-field observation without claiming a real Pro pass."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
from pathlib import Path


B2_COLUMNS = (
    "cycle epoch rst_n pll_locked audio_stable pa_en frame_tick cancel "
    "req_valid req_ready req_id req_payload lane_tick lane lane_req_id "
    "result_valid result_ready result_id left right clipped commit "
    "commit_id commit_left commit_right commit_clipped bclk ws din"
).split()
B2_BITS = set(
    "rst_n pll_locked audio_stable pa_en frame_tick cancel req_valid "
    "req_ready lane_tick result_valid result_ready clipped commit "
    "commit_clipped bclk ws din".split()
)
B2_HEX = {
    "req_id": 8,
    "req_payload": 16,
    "lane_req_id": 8,
    "result_id": 8,
    "commit_id": 8,
}
B2_PCM = {"left", "right", "commit_left", "commit_right"}
B2_SUPPLEMENT = {"req_payload", "lane_tick", "lane", "lane_req_id"}
EVENT_LABELS = [
    "RESET",
    "FRAME",
    "CANCEL",
    "REQUEST",
    "RETURN",
    "COMMIT",
    "TX",
    "FINISH",
]
REFERENCE_ROLES = {
    "observation_contract",
    "d3_ingest",
    "b2_adapter",
    "b2_contract",
    "monitor_source",
    "monitor_contract",
    "m1_field_map",
    "m1_receipt",
}


class Reject(ValueError):
    """Fail-closed input rejection."""


def need(condition: bool, code: str) -> None:
    if not condition:
        raise Reject(code)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def no_duplicates(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise Reject("DUPLICATE_JSON_KEY_" + key)
        result[key] = value
    return result


def strict_loads(text: str):
    return json.loads(
        text,
        object_pairs_hook=no_duplicates,
        parse_constant=lambda token: (_ for _ in ()).throw(
            Reject("NONFINITE_JSON_" + token)
        ),
    )


def load_json(path: Path):
    return strict_loads(path.read_text(encoding="utf-8"))


def resolve(base: Path, value: str) -> Path:
    path = Path(value)
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def is_integer(value) -> bool:
    return type(value) is int


def is_unknown(value) -> bool:
    return isinstance(value, str) and re.search(r"[xXzZ]", value) is not None


def missing_value(value) -> bool:
    return value is None or is_unknown(value)


def bit(value) -> bool:
    return is_integer(value) and value == 1


def validate_hash(value, code: str, nullable: bool = False) -> None:
    if value is None and nullable:
        return
    need(
        isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None,
        code,
    )


def validate_binding(binding: dict, binding_path: Path) -> tuple[dict, dict]:
    expected = {
        "schema",
        "trace",
        "references",
        "provenance",
        "contracts",
        "projection",
        "upstream_dependencies",
    }
    need(set(binding) == expected, "BINDING_FIELDS")
    need(binding["schema"] == "M3_R06_NORMALIZED_INTAKE_BINDING_V1", "BINDING_SCHEMA")
    base = binding_path.parent

    trace = binding["trace"]
    need(type(trace) is dict and set(trace) == {"path", "sha256"}, "TRACE_BINDING_FIELDS")
    validate_hash(trace["sha256"], "TRACE_SHA_FORMAT")
    trace_path = resolve(base, trace["path"])
    need(trace_path.is_file(), "TRACE_MISSING")
    need(sha256(trace_path) == trace["sha256"], "TRACE_SHA")

    references = binding["references"]
    need(type(references) is list, "REFERENCES_TYPE")
    seen = set()
    resolved_refs = {}
    for entry in references:
        need(type(entry) is dict and set(entry) == {"role", "path", "sha256"}, "REFERENCE_FIELDS")
        role = entry["role"]
        need(role in REFERENCE_ROLES and role not in seen, "REFERENCE_ROLE")
        validate_hash(entry["sha256"], "REFERENCE_SHA_FORMAT")
        path = resolve(base, entry["path"])
        need(path.is_file(), "REFERENCE_MISSING_" + role)
        need(sha256(path) == entry["sha256"], "REFERENCE_SHA_" + role)
        seen.add(role)
        resolved_refs[role] = path
    need(seen == REFERENCE_ROLES, "REFERENCE_ROLES_MISSING")

    provenance = binding["provenance"]
    need(
        type(provenance) is dict
        and set(provenance)
        == {
            "kind",
            "authority_verified",
            "source_manifest_sha256",
            "source_rom_sha256",
            "input_plan_sha256",
            "reason",
        },
        "PROVENANCE_FIELDS",
    )
    need(
        provenance["kind"] in {"SYNTHETIC_FIXTURE", "DECLARED_REAL_PENDING_M2", "REAL_CAPTURE"},
        "PROVENANCE_KIND",
    )
    need(type(provenance["authority_verified"]) is bool, "PROVENANCE_AUTHORITY_TYPE")
    for name in ("source_manifest_sha256", "source_rom_sha256", "input_plan_sha256"):
        validate_hash(provenance[name], "PROVENANCE_" + name.upper(), nullable=True)
    need(isinstance(provenance["reason"], str) and provenance["reason"], "PROVENANCE_REASON")
    if provenance["authority_verified"]:
        need(
            all(provenance[name] is not None for name in (
                "source_manifest_sha256",
                "source_rom_sha256",
                "input_plan_sha256",
            )),
            "PROVENANCE_AUTHORITY_WITHOUT_IDENTITIES",
        )

    contracts = binding["contracts"]
    need(
        type(contracts) is dict
        and set(contracts)
        == {
            "same_edge_order_frozen",
            "same_edge_priority",
            "frame_plan_frozen",
            "frame_plan",
            "finish_contract_frozen",
        },
        "CONTRACT_FIELDS",
    )
    for flag in ("same_edge_order_frozen", "frame_plan_frozen", "finish_contract_frozen"):
        need(type(contracts[flag]) is bool, "CONTRACT_BOOL_" + flag)
    priority = contracts["same_edge_priority"]
    if contracts["same_edge_order_frozen"]:
        need(
            type(priority) is list
            and len(priority) == len(set(priority))
            and set(priority) == set(EVENT_LABELS),
            "SAME_EDGE_PRIORITY",
        )
    else:
        need(priority is None or type(priority) is list, "SAME_EDGE_PENDING_VALUE")
    plan = contracts["frame_plan"]
    if contracts["frame_plan_frozen"]:
        need(type(plan) is list and plan, "FRAME_PLAN_REQUIRED")
    else:
        need(plan is None, "UNFROZEN_FRAME_PLAN_MUST_BE_NULL")
    if plan is not None:
        previous = None
        identities = set()
        for item in plan:
            need(
                type(item) is dict and set(item) == {"cycle", "epoch", "frame_id"},
                "FRAME_PLAN_FIELDS",
            )
            need(all(is_integer(item[name]) and item[name] >= 0 for name in item), "FRAME_PLAN_INTEGER")
            key = (item["epoch"], item["frame_id"])
            need(key not in identities, "FRAME_PLAN_DUPLICATE_ID")
            identities.add(key)
            order = (item["cycle"], item["epoch"], item["frame_id"])
            need(previous is None or order > previous, "FRAME_PLAN_ORDER")
            previous = order

    projection = binding["projection"]
    need(
        type(projection) is dict
        and set(projection)
        == {"clip_reduce", "d3_mapping_frozen", "expected_lane_mask"},
        "PROJECTION_FIELDS",
    )
    need(projection["clip_reduce"] in {None, "OR", "BIT0", "BIT1"}, "CLIP_REDUCE")
    need(type(projection["d3_mapping_frozen"]) is bool, "D3_MAPPING_TYPE")
    need(is_integer(projection["expected_lane_mask"]) and projection["expected_lane_mask"] in range(16), "LANE_MASK")

    dependencies = binding["upstream_dependencies"]
    need(
        type(dependencies) is dict
        and set(dependencies) == {"source_target_audit", "midi_stimulus", "m2_public_capture_contract"},
        "UPSTREAM_DEPENDENCIES",
    )
    need(all(isinstance(value, str) and value for value in dependencies.values()), "UPSTREAM_STATUS")
    return {"trace": trace_path, "references": resolved_refs}, binding


def observation_fields(contract_path: Path) -> tuple[list[str], dict[str, dict]]:
    contract = load_json(contract_path)
    need(contract.get("schema") == "M3_B1_MINIMAL_OBSERVATION_CONTRACT_V1", "OBSERVATION_SCHEMA")
    fields = contract.get("fields")
    need(type(fields) is list and len(fields) == 61, "OBSERVATION_FIELD_COUNT")
    names = [entry.get("name") for entry in fields]
    need(len(names) == len(set(names)) and all(isinstance(name, str) for name in names), "OBSERVATION_FIELD_NAMES")
    return names, {entry["name"]: entry for entry in fields}


def validate_scalar(value, definition: dict, field: str) -> None:
    if missing_value(value):
        return
    need(is_integer(value), "FIELD_NOT_INTEGER_" + field)
    width = definition.get("width")
    if width is None:
        return
    signed = bool(definition.get("signed"))
    if signed:
        minimum = -(1 << (width - 1))
        maximum = (1 << (width - 1)) - 1
    else:
        minimum = 0
        maximum = (1 << width) - 1
    need(minimum <= value <= maximum, "FIELD_RANGE_" + field)


def detect_events(fields: dict, previous_rst) -> list[str]:
    events = []
    if fields["rst_n"] == 0 and previous_rst != 0:
        events.append("RESET")
    if bit(fields["frame_tick"]):
        events.append("FRAME")
    if bit(fields["cancel"]):
        events.append("CANCEL")
    if bit(fields["req_valid"]) and bit(fields["req_ready"]) and not bit(fields["cancel"]):
        events.append("REQUEST")
    if bit(fields["result_valid"]) and bit(fields["result_ready"]):
        events.append("RETURN")
    if bit(fields["commit"]):
        events.append("COMMIT")
    if bit(fields["tx_sample_valid"]):
        events.append("TX")
    if bit(fields["finish"]):
        events.append("FINISH")
    return events


def b2_value(name: str, fields: dict, supplement: dict, clip_reduce):
    if name in B2_SUPPLEMENT:
        return supplement[name]
    aliases = {
        "left": "result_left",
        "right": "result_right",
        "commit_clipped": "commit_clip",
    }
    if name == "clipped":
        value = fields["result_clip_mask"]
        if missing_value(value) or clip_reduce is None:
            return value if missing_value(value) else None
        if clip_reduce == "OR":
            return int(value != 0)
        if clip_reduce == "BIT0":
            return value & 1
        return (value >> 1) & 1
    return fields[aliases.get(name, name)]


def format_b2(name: str, value) -> str:
    need(not missing_value(value), "B2_UNKNOWN_" + name)
    need(is_integer(value), "B2_NOT_INTEGER_" + name)
    if name in B2_BITS:
        need(value in (0, 1), "B2_BIT_" + name)
        return str(value)
    if name in B2_HEX:
        width = B2_HEX[name]
        need(0 <= value < (1 << (width * 4)), "B2_HEX_RANGE_" + name)
        return f"{value:0{width}x}"
    if name in B2_PCM:
        need(-(1 << 23) <= value < (1 << 23), "B2_PCM_RANGE_" + name)
    else:
        need(value >= 0, "B2_UNSIGNED_" + name)
    return str(value)


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")


def write_jsonl(path: Path, values: list[dict]) -> None:
    text = "".join(json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n" for value in values)
    path.write_text(text, encoding="utf-8", newline="\n")


def normalize(binding_path: Path, output: Path) -> dict:
    binding_path = binding_path.resolve()
    binding_bytes_before = binding_path.read_bytes()
    binding_sha = hashlib.sha256(binding_bytes_before).hexdigest()
    binding = strict_loads(binding_bytes_before.decode("utf-8"))
    resolved, binding = validate_binding(binding, binding_path)
    trace_path = resolved["trace"]
    trace_sha = binding["trace"]["sha256"]
    names, definitions = observation_fields(resolved["references"]["observation_contract"])

    allowed_special = {"_event_order", "_missing_reasons", "_b2", "_b2_reasons"}
    canonical = []
    b2_rows = []
    observed_frames = []
    frame_map = {}
    if binding["contracts"]["frame_plan"] is not None:
        frame_map = {
            (item["cycle"], item["epoch"]): item["frame_id"]
            for item in binding["contracts"]["frame_plan"]
        }
    pending = set()
    if not binding["provenance"]["authority_verified"] or any(
        value != "READY" for value in binding["upstream_dependencies"].values()
    ):
        pending.add("PENDING_PRO_SOURCE_OR_TRACE")
    if not binding["contracts"]["same_edge_order_frozen"]:
        pending.add("PENDING_SAME_EDGE_ORDER")
    if not binding["contracts"]["frame_plan_frozen"]:
        pending.add("PENDING_FRAME_PLAN")
    if not binding["contracts"]["finish_contract_frozen"]:
        pending.add("PENDING_FINISH_CONTRACT")
    if binding["projection"]["clip_reduce"] is None:
        pending.add("PENDING_B2_COMPATIBILITY")

    previous_cycle = None
    previous_epoch = None
    previous_rst = None
    same_cycle_order = 0
    finish_line = None
    active_id = None
    returned = False
    committed = False
    source_sha = binding["provenance"]["source_manifest_sha256"]
    raw_lines = trace_path.read_text(encoding="utf-8").splitlines()
    need(raw_lines, "EMPTY_TRACE")
    for line_number, raw_line in enumerate(raw_lines, 1):
        need(raw_line.strip() != "", "BLANK_TRACE_LINE_" + str(line_number))
        row = strict_loads(raw_line)
        need(type(row) is dict, "TRACE_ROW_TYPE_" + str(line_number))
        need(set(row) <= set(names) | allowed_special, "TRACE_EXTRA_FIELD_" + str(line_number))
        reasons = row.get("_missing_reasons", {})
        b2_reasons = row.get("_b2_reasons", {})
        supplement = row.get("_b2", {})
        need(type(reasons) is dict and type(b2_reasons) is dict, "REASONS_TYPE_" + str(line_number))
        need(type(supplement) is dict and set(supplement) <= B2_SUPPLEMENT, "B2_SUPPLEMENT_FIELDS_" + str(line_number))
        need(set(b2_reasons) <= B2_SUPPLEMENT, "B2_REASON_FIELDS_" + str(line_number))
        fields = {}
        normalized_reasons = {}
        for name in names:
            present = name in row
            value = row.get(name)
            if not present or missing_value(value):
                reason = reasons.get(name)
                need(isinstance(reason, str) and reason, "MISSING_REASON_" + name + "_LINE_" + str(line_number))
                normalized_reasons[name] = reason
                pending.add("PENDING_PRO_SOURCE_OR_TRACE")
            validate_scalar(value, definitions[name], name)
            fields[name] = value
        for name in B2_SUPPLEMENT:
            present = name in supplement
            value = supplement.get(name)
            if not present or missing_value(value):
                reason = b2_reasons.get(name)
                need(isinstance(reason, str) and reason, "B2_MISSING_REASON_" + name + "_LINE_" + str(line_number))
                pending.add("PENDING_B2_COMPATIBILITY")

        cycle = fields["cycle"]
        epoch = fields["epoch"]
        need(is_integer(cycle) and cycle >= 0, "CYCLE_REQUIRED_LINE_" + str(line_number))
        need(is_integer(epoch) and epoch >= 0, "EPOCH_REQUIRED_LINE_" + str(line_number))
        if previous_cycle is not None:
            need(cycle in (previous_cycle, previous_cycle + 1), "DROPPED_CYCLE_ROW_LINE_" + str(line_number))
            same_cycle_order = same_cycle_order + 1 if cycle == previous_cycle else 0
        need(finish_line is None, "ROW_AFTER_FINISH_LINE_" + str(line_number))

        control_fields = {
            "rst_n",
            "pll_locked",
            "audio_stable",
            "pa_en",
            "frame_tick",
            "cancel",
            "event_valid",
            "event_ready",
            "apply_valid",
            "req_valid",
            "req_ready",
            "result_valid",
            "result_ready",
            "commit",
            "config_valid",
            "config_ready",
            "effect_input_valid",
            "effect_input_ready",
            "tx_sample_valid",
            "tx_hold",
            "tx_startup_zero",
            "finish",
        }
        for name in control_fields:
            if name in row and is_unknown(fields[name]):
                raise Reject("CONTROL_UNKNOWN_" + name + "_LINE_" + str(line_number))
            if not missing_value(fields[name]):
                need(fields[name] in (0, 1), "CONTROL_NOT_BIT_" + name + "_LINE_" + str(line_number))

        rst_n = fields["rst_n"]
        if previous_epoch is None:
            need(epoch == 0 and rst_n == 0, "INITIAL_RESET_EPOCH")
        else:
            if previous_rst == 1 and rst_n == 0:
                need(epoch == previous_epoch + 1, "RESET_EPOCH_INCREMENT_LINE_" + str(line_number))
                active_id, returned, committed = None, False, False
            else:
                need(epoch == previous_epoch, "WRONG_EPOCH_LINE_" + str(line_number))

        used_groups = []
        if bit(fields["req_valid"]):
            used_groups += ["req_id"]
            if is_unknown(supplement.get("req_payload")):
                raise Reject("REQUEST_UNKNOWN_req_payload_LINE_" + str(line_number))
        if is_integer(fields["advance_mask"]) and fields["advance_mask"] != 0:
            used_groups += ["advance_frame_req_id"]
        if bit(fields["result_valid"]):
            used_groups += ["result_id", "result_left", "result_right", "result_clip_mask"]
        if bit(fields["commit"]):
            used_groups += ["commit_id", "commit_left", "commit_right", "commit_clip"]
        if bit(fields["tx_sample_valid"]):
            used_groups += ["tx_frame_id", "tx_req_id", "tx_left", "tx_right", "tx_clip"]
        for name in used_groups:
            if missing_value(fields[name]):
                raise Reject("USED_DATA_UNKNOWN_" + name + "_LINE_" + str(line_number))

        events = detect_events(fields, previous_rst)
        original_order = row.get("_event_order")
        if original_order is not None:
            need(
                type(original_order) is list
                and len(original_order) == len(set(original_order))
                and set(original_order) == set(events),
                "EVENT_ORDER_CONTENT_LINE_" + str(line_number),
            )
        if binding["contracts"]["same_edge_order_frozen"] and len(events) > 1:
            need(original_order is not None, "SAME_EDGE_ORDER_MISSING_LINE_" + str(line_number))
            priority = binding["contracts"]["same_edge_priority"]
            expected_order = sorted(events, key=priority.index)
            need(original_order == expected_order, "SAME_EDGE_ORDER_LINE_" + str(line_number))

        if bit(fields["cancel"]):
            need(active_id is not None and not bit(fields["commit"]), "CANCEL_STATE_LINE_" + str(line_number))
            active_id, returned, committed = None, False, False
        if "REQUEST" in events:
            need(active_id is None and is_integer(fields["req_id"]), "REQUEST_STATE_LINE_" + str(line_number))
            active_id = (epoch, fields["req_id"])
            returned = False
            committed = False
        if is_integer(fields["advance_mask"]) and fields["advance_mask"] != 0:
            need(active_id is not None and fields["advance_frame_req_id"] == active_id[1], "ADVANCE_ID_LINE_" + str(line_number))
        if "RETURN" in events:
            need(active_id is not None and fields["result_id"] == active_id[1], "RESULT_ID_LINE_" + str(line_number))
            returned = True
        if "COMMIT" in events:
            need(active_id is not None and returned and fields["commit_id"] == active_id[1], "COMMIT_ID_LINE_" + str(line_number))
            committed = True
        if "TX" in events and not bit(fields["tx_startup_zero"]):
            need(active_id is not None and committed and fields["tx_req_id"] == active_id[1], "TX_ID_LINE_" + str(line_number))
            active_id, returned, committed = None, False, False
        if "FRAME" in events:
            observed_frames.append((cycle, epoch))
        if "FINISH" in events:
            need(active_id is None, "FINISH_WITH_PENDING_LINE_" + str(line_number))
            finish_line = line_number

        b2_values = {
            name: b2_value(name, fields, supplement, binding["projection"]["clip_reduce"])
            for name in B2_COLUMNS
        }
        b2_pending_fields = [name for name, value in b2_values.items() if missing_value(value)]
        if b2_pending_fields:
            pending.add("PENDING_B2_COMPATIBILITY")
        b2_rows.append(
            {
                "input_line": line_number,
                "status": "PENDING_B2_COMPATIBILITY" if b2_pending_fields else "READY",
                "pending_fields": b2_pending_fields,
                "values": b2_values,
            }
        )
        canonical.append(
            {
                "schema": "M3_R06_CANONICAL_61_ROW_V1",
                "input_line": line_number,
                "same_cycle_order": same_cycle_order,
                "cycle": cycle,
                "epoch": epoch,
                "input_sha256": trace_sha,
                "source_sha256": source_sha,
                "source_reason": binding["provenance"]["reason"],
                "original_event_order": original_order,
                "events_on_edge": events,
                "fields": fields,
                "missing_reasons": normalized_reasons,
                "b2_supplement": supplement,
                "b2_missing_reasons": b2_reasons,
            }
        )
        previous_cycle, previous_epoch, previous_rst = cycle, epoch, rst_n

    if binding["contracts"]["frame_plan_frozen"]:
        expected_frames = [
            (item["cycle"], item["epoch"])
            for item in binding["contracts"]["frame_plan"]
        ]
        need(observed_frames == expected_frames, "FRAME_PLAN_MISMATCH")
    if binding["contracts"]["finish_contract_frozen"]:
        need(finish_line is not None, "FINISH_REQUIRED")

    need(sha256(trace_path) == trace_sha, "TRACE_CHANGED_DURING_READ")
    need(hashlib.sha256(binding_path.read_bytes()).hexdigest() == binding_sha, "BINDING_CHANGED_DURING_READ")
    for entry in binding["references"]:
        path = resolve(binding_path.parent, entry["path"])
        need(sha256(path) == entry["sha256"], "REFERENCE_CHANGED_" + entry["role"])

    d3_rows = []
    d3_calendar = []
    d3_ready = (
        binding["projection"]["d3_mapping_frozen"]
        and binding["contracts"]["frame_plan_frozen"]
        and binding["contracts"]["finish_contract_frozen"]
    )
    if d3_ready:
        previous_rst = None
        previous_pa = None
        d3_active_id = None
        for item in canonical:
            fields = item["fields"]
            cycle, epoch = item["cycle"], item["epoch"]
            if fields["rst_n"] == 0 and previous_rst != 0:
                d3_rows.append({"kind": "RESET", "cycle": cycle, "epoch": epoch})
                d3_active_id = None
            pa_state = (fields["rst_n"], fields["audio_stable"], fields["pa_en"])
            if not any(missing_value(value) for value in pa_state) and pa_state != previous_pa:
                d3_rows.append({"kind": "PA", "cycle": cycle, "epoch": epoch,
                                "rst_n": pa_state[0], "stable": pa_state[1], "pa_en": pa_state[2]})
                previous_pa = pa_state
            if bit(fields["frame_tick"]):
                need((cycle, epoch) in frame_map, "D3_FRAME_ID_MISSING")
                d3_rows.append({"kind": "FRAME", "cycle": cycle, "epoch": epoch,
                                "frame_id": frame_map[(cycle, epoch)]})
            if bit(fields["cancel"]):
                need(d3_active_id is not None and d3_active_id[0] == epoch, "D3_CANCEL_ID_REQUIRED")
                d3_rows.append({"kind": "CANCEL", "cycle": cycle, "epoch": epoch,
                                "req_id": d3_active_id[1]})
                d3_active_id = None
            if bit(fields["req_valid"]) and bit(fields["req_ready"]) and not bit(fields["cancel"]):
                need(d3_active_id is None, "D3_REQUEST_WHILE_ACTIVE")
                request = {"epoch": epoch, "req_id": fields["req_id"], "cycle": cycle,
                           "lane_mask": binding["projection"]["expected_lane_mask"]}
                d3_calendar.append(request)
                d3_active_id = (epoch, fields["req_id"])
                d3_rows.append({"kind": "REQUEST", "cycle": cycle, "epoch": epoch,
                                "req_id": fields["req_id"], "lane_mask": request["lane_mask"]})
                d3_rows.append({"kind": "ACCEPT", "cycle": cycle, "epoch": epoch,
                                "req_id": fields["req_id"]})
            if is_integer(fields["advance_mask"]) and fields["advance_mask"]:
                for lane in range(4):
                    if fields["advance_mask"] & (1 << lane):
                        d3_rows.append({"kind": "LANE_TICK", "cycle": cycle, "epoch": epoch,
                                        "req_id": fields["advance_frame_req_id"], "lane": lane})
            if bit(fields["result_valid"]) and bit(fields["result_ready"]):
                d3_rows.append({"kind": "RETURN", "cycle": cycle, "epoch": epoch,
                                "req_id": fields["result_id"], "left": fields["result_left"],
                                "right": fields["result_right"]})
            if bit(fields["tx_sample_valid"]) and not bit(fields["tx_startup_zero"]):
                need(d3_active_id == (epoch, fields["tx_req_id"]), "D3_CONSUME_ID")
                d3_rows.append({"kind": "CONSUME", "cycle": cycle, "epoch": epoch,
                                "req_id": fields["tx_req_id"], "frame_id": fields["tx_frame_id"]})
                d3_active_id = None
            if bit(fields["finish"]):
                d3_rows.append({"kind": "END", "cycle": cycle, "epoch": epoch})
            previous_rst = fields["rst_n"]
    else:
        pending.add("PENDING_PRO_SOURCE_OR_TRACE")

    need(not output.exists(), "OUTPUT_EXISTS")
    output.mkdir(parents=True)
    write_jsonl(output / "CANONICAL.jsonl", canonical)
    write_jsonl(output / "B2_VIEW.jsonl", b2_rows)
    b2_csv_written = not any(row["status"] != "READY" for row in b2_rows)
    if b2_csv_written:
        with (output / "B2_PUBLIC.csv").open("w", encoding="utf-8", newline="") as stream:
            writer = csv.writer(stream, lineterminator="\n")
            writer.writerow(B2_COLUMNS)
            for row in b2_rows:
                writer.writerow([format_b2(name, row["values"][name]) for name in B2_COLUMNS])
    if d3_ready:
        write_jsonl(output / "D3.jsonl", d3_rows)
        write_json(
            output / "D3_CALENDAR.json",
            {
                "schema": "M3_PRO_INTAKE_CALENDAR_V1",
                "provenance": binding["provenance"]["kind"],
                "requests": d3_calendar,
            },
        )

    artifacts = {}
    for path in sorted(output.iterdir(), key=lambda value: value.name):
        if path.is_file():
            artifacts[path.name] = {"bytes": path.stat().st_size, "sha256": sha256(path)}
    status = "PENDING" if pending else "STRUCTURE_READY_NOT_PRO_PASS"
    if binding["provenance"]["kind"] == "SYNTHETIC_FIXTURE" and not pending:
        status = "SYNTHETIC_SELFTEST_ONLY"
    receipt = {
        "schema": "M3_R06_NORMALIZED_INTAKE_RECEIPT_V1",
        "status": status,
        "pending": sorted(pending),
        "level": "L1_SOFTWARE_ONLY",
        "canonical_rows": len(canonical),
        "b2_rows": len(b2_rows),
        "b2_csv_written": b2_csv_written,
        "d3_rows": len(d3_rows),
        "d3_jsonl_written": d3_ready,
        "binding_sha256": binding_sha,
        "input_sha256": trace_sha,
        "source_sha256": source_sha,
        "references": binding["references"],
        "artifacts_before_receipt": artifacts,
        "pro_dut_pass": False,
        "board_release_allowed": False,
        "real_finish_pass": False,
    }
    write_json(output / "RECEIPT.json", receipt)
    return receipt


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--binding", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        receipt = normalize(args.binding, args.output.resolve())
        print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
        return 0
    except (Reject, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(
            json.dumps(
                {
                    "status": "REJECT",
                    "first_failure": str(exc),
                    "pro_dut_pass": False,
                    "board_release_allowed": False,
                },
                ensure_ascii=False,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
