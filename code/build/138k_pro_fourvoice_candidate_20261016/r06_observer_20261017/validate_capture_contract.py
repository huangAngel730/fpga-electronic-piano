"""Validate a source-bound candidate contract; never execute HDL or certify G1."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[4]
ARCHIVE = "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/same_version_binding_20261017/M2_PRO_SAME_VERSION_STATIC_BINDING_20261017.zip"
ARCHIVE_SHA = "931b7d2bbfd7ac056707542931101ff844b125936762748e344536d9be6c1ba2"
DEFAULT = ROOT / "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/r06_observer_20261017"


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def parse(raw):
    return json.loads(raw, object_pairs_hook=unique_object)


def load(path):
    return parse(path.read_text(encoding="utf-8"))


def validate(directory, archive):
    raw = archive.read_bytes()
    require(hashlib.sha256(raw).hexdigest() == ARCHIVE_SHA, "SOURCE_ARCHIVE_SHA")
    contract = load(directory / "CAPTURE_CONTRACT.json")
    rules = load(directory / "FRAME_PLAN_RULES.json")
    routes = load(directory / "ROUTING_PLAN.json")
    schema = load(directory / "NORMALIZED_ROW_SCHEMA.json")
    bindings = load(directory / "SOURCE_BINDINGS.json")
    require(contract["schema"] == "M2_R06_PUBLIC_CAPTURE_CONTRACT_V1", "CONTRACT_SCHEMA")
    require(contract["status"] == "PARTIAL_CANDIDATE_PENDING_M1_AND_PUBLIC_EXPORT", "CANDIDATE_STATUS")
    require(contract["sampling_phase"] == "POSEDGE_PRE_NBA", "SAMPLING_PHASE")
    require(contract["source_archive"] == ARCHIVE and contract["source_archive_sha256"] == ARCHIVE_SHA, "SOURCE_BINDING")
    require(all(contract[key] is False for key in ("formal_interface_changed", "real_public_trace_exported", "pro_dut_pass", "board_release_allowed")), "UNSUPPORTED_IMPLEMENTATION_OR_REAL_CLAIM")
    with zipfile.ZipFile(archive) as bundle:
        original_raw = bundle.read("PUBLIC_OBSERVATION_MAP.json")
        require(hashlib.sha256(original_raw).hexdigest() == contract["source_observation_map_sha256"], "SOURCE_MAP_SHA")
        original = parse(original_raw)
        expected = {item["name"]: item for item in original["fields"]}
        fields = contract["fields"]
        actual = {item["name"]: item for item in fields}
        require(len(fields) == len(actual) == contract["field_count"] == 61 and actual.keys() == expected.keys(), "FIELDS61")
        counts = dict(Counter(item["category"] for item in fields))
        require(counts == original["category_counts"] == contract["category_counts"], "SOURCE_CATEGORIES")
        seen_bindings = {}
        for name, item in actual.items():
            reference = expected[name]
            require(all(type(item[key]) is type(reference[key]) and item[key] == reference[key] for key in ("width", "signed", "category", "bound_at_pro_top", "references")), "SOURCE_FIELD_METADATA_" + name)
            require(item["sampling_phase"] == "POSEDGE_PRE_NBA" and item["route_implemented_by_this_change"] is False, "FIELD_PHASE_OR_FALSE_EXPORT_" + name)
            require(type(item["owner"]) is str and item["owner"], "FIELD_OWNER_" + name)
            for ref in item["references"]:
                content = bundle.read(ref["path"])
                require(hashlib.sha256(content).hexdigest() == ref["sha256"], "SOURCE_MEMBER_SHA")
                require(content.decode("utf-8").splitlines()[ref["line"] - 1].strip() == ref["text"].strip(), "SOURCE_LINE")
                seen_bindings[ref["path"]] = ref["sha256"]
        require(bindings == {"archive": ARCHIVE, "sha256": ARCHIVE_SHA, "files": seen_bindings}, "BINDINGS_COMPLETE")
    require(set(schema["required"]) == set(schema["properties"]) == set(actual) and len(schema["required"]) == 61, "ROW_SCHEMA_FIELDS")
    require(schema["additionalProperties"] is False, "ROW_SCHEMA_EXTRAS")
    for name, item in actual.items():
        options = schema["properties"][name]["anyOf"]
        width = item["width"]
        binary = {"type": "string", "pattern": "^[01xXzZ]+$"}
        if width is not None:
            binary["maxLength"] = width
        require(options[1] == {"type": "null"} and options[2] == binary, "SCHEMA_BINARY_ENCODING_" + name)
        integer = {"type": "integer"}
        if width is not None:
            integer.update({"minimum": -(1 << (width - 1)) if item["signed"] else 0,
                            "maximum": (1 << (width - int(item["signed"]))) - 1})
        require(options[0] == integer, "ROW_WIDTH_SIGN_" + name)
    require(set(routes["actual_public_four"]) == {name for name, item in actual.items() if item["bound_at_pro_top"]}, "PUBLIC_FOUR")
    existing = {name for name, item in actual.items() if item["category"] == "EXISTING_PUBLIC_PORT" and not item["bound_at_pro_top"]}
    internal = {name for name, item in actual.items() if item["category"] == "M2_INTERNAL_PENDING_CONTROLLED_EXPORT"}
    require(len(routes["existing16"]) == 16 and set(routes["existing16"]) == existing, "ROUTES_EXISTING16")
    require(len(routes["M2_internal9"]) == 9 and set(routes["M2_internal9"]) == internal, "ROUTES_INTERNAL9")
    require(actual["result_clip_mask"]["normalized_packing"] == {"bit0": "clip_left", "bit1": "clip_right"}, "CLIP_CHANNEL_PACKING")
    require(contract["deadline"]["budget_origin"] == "frame_origin_cycle" and contract["deadline"]["strict_bound_cycles"] == 833, "FRAME_BUDGET_ORIGIN")
    require(all(key in contract["time_bases"] for key in ("frame_origin_cycle", "request_first_valid_cycle", "accept_cycle", "return_cycle", "commit_cycle", "tx_cycle")), "DISTINCT_TIME_BASES")
    require(contract["legacy_D3_projection"]["old_tests_rerun"] is False and contract["tx_sidecar"]["status"] == "NOT_IMPLEMENTED", "LEGACY_OR_TX_FALSE_CLAIM")
    require(contract["completion"]["independent_window_required"] is True, "FRAME_PLAN_INDEPENDENCE")
    require((rules["acc_bits"], rules["phase_step"], rules["core_hz_candidate"], rules["half_bclk_toggles_per_frame"]) == (32, 659706977, 40000000, 128), "FRAME_CLOCK_PARAMETERS")
    first = [(128 * k * (1 << 32) + 659706976) // 659706977 for k in range(1, 7)]
    require(rules["first_edge_indices"] == first == [834, 1667, 2500, 3334, 4167, 5000], "FRAME_FORMULA_PHASE")
    require(rules["initial_state"] == {"accumulator": 0, "bclk": 0, "slot_count": 0}, "RESET_INITIAL_PHASE")
    require(actual["audio_stable"]["contract_status"] == "PENDING_STABILITY_POLICY_AND_IMPLEMENTATION", "STABILITY_FALSE_CLAIM")
    require(actual["config_payload"]["width"] is None and actual["cancel_reason"]["width"] is None, "UNRESOLVED_WIDTH_FALSE_FREEZE")
    return {"status": "SOURCE_BOUND_CONTRACT_CANDIDATE_VALID", "level": "L1_SOFTWARE_CONTRACT_ONLY", "fields": 61,
            "routes_pending": {"existing16": 16, "internal9": 9}, "pending": ["M1 semantics19", "public exports", "TX sidecar", "stability/config/cancel definitions", "independent real reset/window inputs", "Pro identity/physical/board"],
            "external_review_delivered": False, "pro_dut_pass": False, "board_release_allowed": False}


def validate_row(row, directory):
    """Check representation only; null/X/Z do not establish known DUT values."""
    schema = load(directory / "NORMALIZED_ROW_SCHEMA.json")
    require(type(row) is dict and set(row) == set(schema["required"]), "ROW_FIELDS61")
    for name, value in row.items():
        integer, _, binary = schema["properties"][name]["anyOf"]
        if value is None:
            continue
        if type(value) is int:
            require(integer.get("minimum", value) <= value <= integer.get("maximum", value), "ROW_INTEGER_WIDTH_" + name)
        elif type(value) is str:
            require(re.fullmatch(binary["pattern"], value) is not None and len(value) <= binary.get("maxLength", len(value)), "ROW_BITSTRING_WIDTH_" + name)
        else:
            raise ValueError("ROW_TYPE_" + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path, nargs="?", default=DEFAULT)
    parser.add_argument("--archive", type=Path, default=ROOT / ARCHIVE)
    parser.add_argument("--row", type=Path, help="Optional61-field JSON row; representation check only")
    args = parser.parse_args()
    try:
        result = validate(args.directory, args.archive)
        if args.row:
            validate_row(load(args.row), args.directory)
            result["row_status"] = "REPRESENTATION_ONLY_UNKNOWN_VALUES_NOT_CERTIFIED"
    except (ValueError, OSError, KeyError, TypeError, IndexError, zipfile.BadZipFile) as error:
        print(json.dumps({"status": "REJECT", "first_failure": str(error), "pro_dut_pass": False, "board_release_allowed": False}))
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
