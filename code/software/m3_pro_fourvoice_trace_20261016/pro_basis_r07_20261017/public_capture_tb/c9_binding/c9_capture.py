"""C9 successor codec. L0 source only; never compiles or starts a process."""
import argparse
import ast
import hashlib
import json
from pathlib import Path
import re
import types

ROOT = Path(__file__).resolve().parents[6]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r07_20261017/public_capture_tb"
LEGACY = Path(__file__).resolve().parent.parent / "assemble.py"
LEGACY_SHA = "c2339e73c61ba4b04231e9c08a34fd364c365e6cd67ce70007956faf5eb6c003"


def identity(path):
    path = Path(path)
    raw = path.read_bytes()
    return {"path": str(path.resolve()), "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}


def checked(entry):
    path = Path(entry["path"])
    if not path.is_absolute():
        path = ROOT / path
    for part in (path, *path.parents):
        if part.is_symlink() or part.is_junction():
            raise ValueError("INPUT_PATH_ALIAS")
    path = path.resolve()
    if not path.is_relative_to(ROOT) or identity(path)["sha256"] != entry["sha256"]:
        raise ValueError("INPUT_IDENTITY_OR_SCOPE")
    if "bytes" in entry and identity(path)["bytes"] != entry["bytes"]:
        raise ValueError("INPUT_SIZE")
    return path


def legacy_pure():
    """Reuse unchanged legacy scalar/reset/finish algorithms, omit prepare/main."""
    raw = LEGACY.read_bytes()
    if hashlib.sha256(raw).hexdigest() != LEGACY_SHA:
        raise ValueError("LEGACY_SOURCE_CHANGED")
    tree = ast.parse(raw.decode("utf-8"), filename=str(LEGACY))
    definitions = {"Reject", "need", "pairs", "load", "digest", "raw_digest", "integer", "exact",
                   "scalar", "reset_states", "bind_epoch", "stream_rows"}
    nodes, found = [], set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            if not isinstance(node, ast.ImportFrom) or node.module != "prepare":
                nodes.append(node)
        elif isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in definitions:
            nodes.append(node)
            found.add(node.name)
    if found != definitions:
        raise ValueError("LEGACY_PURE_DEFINITION_SET")
    derived = ast.Module(body=nodes, type_ignores=[])
    module = types.ModuleType("c9_reused_r7a_algorithms")
    exec(compile(ast.fix_missing_locations(derived), str(LEGACY), "exec"), module.__dict__)
    module.derivation = {"source": identity(LEGACY), "unchanged_function_nodes": sorted(found),
                         "derived_AST_sha256": hashlib.sha256(ast.dump(derived, include_attributes=False).encode()).hexdigest(),
                         "omitted": ["prepare import", "assemble collection helper", "CLI main"]}
    return module


def normalize(raw, resets, end, stdout, port_map, old_map, origin):
    """Validate legacy time/reset/end projection; retain full C9 raw provenance."""
    m = legacy_pure()
    m.need(type(raw) is bytes and len(raw) <= 64 * 1024 * 1024, "RAW_SIZE_BOUND")
    m.need(origin in ("SYNTHETIC_SCHEMA_FIXTURE", "HDL_PUBLIC_CAPTURE_UNVERIFIED"), "ORIGIN")
    m.need(port_map["schema"] == "M3_R7A_C9_PUBLIC_PORT_MAP_V1" and
           len(port_map["raw_ports"]) == 72 and len(port_map["normalized_fields"]) == 74,
           "C9_BINDING_COUNTS")
    items, projected = [], []
    for line in raw.decode("utf-8").splitlines():
        item = m.load(line)
        m.need(item["schema"] == "M3_R7A_C9_RAW_CORE_ROW_V1", "C9_RAW_SCHEMA_REQUIRED")
        m.exact(item["ports"], port_map["raw_ports"], "C9_RAW_PUBLIC_PORT_SET")
        values = {name: m.scalar(item["ports"][name], spec) for name, spec in port_map["raw_ports"].items()}
        items.append((item, values))
        projection = {**item, "schema": "M3_R7A_RAW_CORE_ROW_V1",
                      "ports": {name: item["ports"][name] for name in old_map["raw_ports"]}}
        projected.append(json.dumps(projection, separators=(",", ":")))
    projection_raw = ("\n".join(projected) + "\n").encode("utf-8")
    receipt, output = {}, []
    original_sha = hashlib.sha256(raw).hexdigest()
    for index, previous in enumerate(m.stream_rows(projection_raw, resets, end, stdout, old_map, origin, receipt)):
        item, values = items[index]
        fields = {name: values[entry["port"]] for name, entry in port_map["normalized_mapping"].items()}
        reasons = dict(port_map["unimplemented"])
        fields.update({name: None for name in reasons})
        fields.update(cycle=previous["fields"]["cycle"], epoch=previous["fields"]["epoch"], finish=item["finish"])
        if fields["epoch"] is None:
            reasons["epoch"] = previous["missing_reasons"].get("epoch", "RESET_EPOCH_UNKNOWN")
        for name, value in fields.items():
            if type(value) is str:
                reasons[name] = "OBSERVED_PUBLIC_XZ"
        if values["obs_tx_req_id_valid"] != 1:
            fields["tx_req_id"] = None
            reasons["tx_req_id"] = "NO_KNOWN_VALID_TX_REQUEST_ID_RAW_BITS_RETAINED"
        m.need(set(fields) == set(port_map["normalized_fields"]), "NORMALIZED_74_FIELDS")
        kind, active, valid = fields["apply_kind"], fields["apply_valid"], fields["router_apply_seq_valid"]
        cause = "INACTIVE_RAW_HELD_VALUES_UNINTERPRETED"
        if active == 1:
            cause = "UNKNOWN_CAUSE"
            if kind in (3, 4, 8):
                sentinels = (valid, fields["apply_data"], fields["router_apply_seq"])
                if all(type(value) is int for value in sentinels):
                    m.need(sentinels == (0, 0, 0), "INVALID_CAUSE_SENTINEL_CONTRACT")
                    cause = "INVALID_CAUSE_SENTINEL_NOT_AN_INPUT_EVENT"
            elif valid == 1:
                cause = "ROUTER_CAUSE_ONLY_INDEPENDENT_PLAN_MAPPING_PENDING"
        packing = None
        if fields["config_take"] == 1 and type(fields["config_payload"]) is int:
            payload = fields["config_payload"]
            packing = {"enable": (payload >> 61) & 1, "delay_samples": (payload >> 45) & 65535,
                       "dry_gain": (payload >> 30) & 32767, "wet_gain": (payload >> 15) & 32767,
                       "feedback": payload & 32767}
        output.append({"schema": "M3_R7A_C9_PUBLIC_ROW_V1", "capture_id": previous["capture_id"], "origin": origin,
                       "source": {**previous["source"], "raw_sha256": original_sha}, "fields": fields,
                       "raw_ports": item["ports"], "missing_reasons": reasons, "events": previous["events"],
                       "semantics": {"apply_cause": cause, "stage_deduplicated": False,
                                     "independent_plan_mapping": "PENDING", "config_on_actual_take": packing,
                                     "advance_frame_req_id_is_FRAME_F": False,
                                     "advance_mask_source": "PUBLIC_M1_LANE_TICK_ROUTE_NOT_REQUEST_ACCEPTANCE"}})
    receipt.update(schema="M3_R7A_C9_CODEC_RECEIPT_V1", raw_sha256=original_sha,
                   projected_legacy_validation_sha256=hashlib.sha256(projection_raw).hexdigest(),
                   derivation=m.derivation, normalized_fields=74, raw_ports=72,
                   status="PENDING_REAL_TRACE_PLAN_MAPPING_AUDIO_STABLE_AND_ADMISSION",
                   source_status="CODEC_RESULT_NOT_HDL_OR_REAL_AUTHORITY_PROOF", real_pass=False, board_release_allowed=False)
    return output, receipt


def main():
    parser = argparse.ArgumentParser()
    for name in ("raw", "resets", "end", "stdout", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--binding", type=Path, default=DOC / "c9_binding/INPUT_BINDING.json")
    parser.add_argument("--origin", choices=("SYNTHETIC_SCHEMA_FIXTURE", "HDL_PUBLIC_CAPTURE_UNVERIFIED"),
                        default="HDL_PUBLIC_CAPTURE_UNVERIFIED")
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    try:
        binding = json.loads(args.binding.read_text(encoding="utf-8"))
        for entry in binding["inputs"]:
            checked(entry)
        port_map = json.loads(checked(binding["port_map"]).read_text(encoding="utf-8"))
        old_map = json.loads(checked(binding["old_port_map"]).read_text(encoding="utf-8"))
        inputs = {}
        for name in ("raw", "resets", "end", "stdout"):
            path = getattr(args, name)
            raw = path.read_bytes()
            with (args.output / (name + ".original")).open("xb") as stream:
                stream.write(raw)
            inputs[name] = raw
        with (args.output / "INPUT.json").open("x", encoding="utf-8", newline="\n") as stream:
            json.dump({"binding": binding, "origin": args.origin,
                       "originals": {name: identity(getattr(args, name)) for name in inputs}}, stream, indent=2)
        rows, receipt = normalize(**inputs, port_map=port_map, old_map=old_map, origin=args.origin)
        with (args.output / "PUBLIC_ROWS_C9.jsonl").open("x", encoding="utf-8", newline="\n") as stream:
            for row in rows:
                stream.write(json.dumps(row, ensure_ascii=False) + "\n")
        with (args.output / "RECEIPT.json").open("x", encoding="utf-8", newline="\n") as stream:
            json.dump(receipt, stream, ensure_ascii=False, indent=2)
        return 3
    except Exception as error:
        with (args.output / "FAILURE.json").open("x", encoding="utf-8", newline="\n") as stream:
            json.dump({"status": "REJECT", "error": type(error).__name__ + ":" + str(error),
                       "real_pass": False, "board_release_allowed": False}, stream)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
