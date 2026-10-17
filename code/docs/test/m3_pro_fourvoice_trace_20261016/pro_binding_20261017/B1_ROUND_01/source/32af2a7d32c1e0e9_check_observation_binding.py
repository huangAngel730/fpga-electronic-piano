"""B1 observation-binding metadata gate. No calendar, HDL or audio model.

A successful schema check is never proof of Pro provenance or DUT behavior.
Expected mapping digest is supplied independently by the receiving reviewer.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import re

SHA = re.compile(r"[0-9a-f]{64}\Z")
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017"
CONTRACT_SHA256 = "d89076836f8c60dd6544bbf2d9a5e8fa2f645ef49c8860458210562adf12d716"
ANCHORS = (
    "source_manifest", "rom_manifest", "input_plan", "public_trace",
    "tx_sample_sidecar", "capture_receipt", "raw_stdout", "raw_stderr",
    "intake_report", "m2_binding_review",
)
SEMANTICS = (
    "event_accept_apply", "allocator_release_retire", "frame_lane_identity",
    "advance_mask", "cancel_reset_priority", "backpressure", "effect_acceptance",
    "tx_adoption_hold_startup", "clock_reset_epoch", "finish_end",
)


class Refusal(Exception):
    def __init__(self, code, location, pending=False):
        super().__init__(code)
        self.code, self.location, self.pending = code, location, pending


def require(ok, code, location, pending=False):
    if not ok:
        raise Refusal(code, location, pending)


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "DUPLICATE_JSON_KEY", key)
        result[key] = value
    return result


def strict_json(raw):
    require(len(raw) <= 262144, "JSON_SIZE_LIMIT", "document")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=pairs,
                          parse_constant=lambda token: (_ for _ in ()).throw(
                              Refusal("NONFINITE_JSON", token)))
    except (UnicodeError, json.JSONDecodeError) as error:
        raise Refusal("JSON_ENCODING_OR_SYNTAX", "document") from error


def exact(obj, keys, location):
    require(type(obj) is dict and set(obj) == set(keys), "OBJECT_FIELDS", location)


def integer(value, low, high):
    return type(value) is int and low <= value <= high


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def bounded_file(root, entry, location):
    exact(entry, ("path", "bytes", "sha256"), location)
    name = entry["path"]
    require(type(name) is str and name and "\\" not in name and ":" not in name,
            "ARTIFACT_PATH", location)
    rel = PurePosixPath(name)
    require(not rel.is_absolute() and all(x not in (".", "..") for x in name.split("/"))
            and "//" not in name, "ARTIFACT_PATH", location)
    path = (root / name).resolve()
    require(path.is_relative_to(root.resolve()), "ARTIFACT_PATH_ESCAPE", location)
    require(integer(entry["bytes"], 0, 64 * 1024 * 1024), "ARTIFACT_SIZE", location)
    require(type(entry["sha256"]) is str and SHA.fullmatch(entry["sha256"]),
            "ARTIFACT_SHA_FORMAT", location)
    require(path.is_file(), "ARTIFACT_MISSING", location, True)
    require(path.stat().st_size == entry["bytes"], "ARTIFACT_BYTES", location)
    require(sha(path.read_bytes()) == entry["sha256"], "ARTIFACT_SHA_MISMATCH", location)
    return path


def check(raw, expected_sha, artifact_root, contract):
    require(type(expected_sha) is str and SHA.fullmatch(expected_sha),
            "EXPECTED_BINDING_SHA_REQUIRED", "expected_sha256", True)
    require(sha(raw) == expected_sha, "BINDING_SHA_MISMATCH", "binding")
    obj = strict_json(raw)
    exact(obj, ("schema", "scope", "pro_dut_pass", "board_release_allowed",
                "sample_edge", "clock_hz", "nominal_sample_rate_hz", "frame_id_domain",
                "lane_identity_mode", "anchors", "fields", "semantics", "completion"), "binding")
    require(obj["schema"] == "M3_B1_OBSERVATION_BINDING_V1", "SCHEMA", "schema")
    require(obj["scope"] in ("SYNTHETIC_METADATA_SELFTEST_NOT_PRO", "PRO_BINDING_REVIEW_ONLY"),
            "SCOPE", "scope")
    require(obj["pro_dut_pass"] is False and obj["board_release_allowed"] is False,
            "UNSUPPORTED_PRO_OR_BOARD_CLAIM", "claims")
    require(obj["sample_edge"] == "POSEDGE_PRE_NBA", "SAMPLING_PHASE", "sample_edge")
    require(type(obj["clock_hz"]) is int and obj["clock_hz"] == 40000000 and
            type(obj["nominal_sample_rate_hz"]) is int and obj["nominal_sample_rate_hz"] == 48000,
            "CLOCK_CONTRACT", "clock")
    require(obj["frame_id_domain"] == "FRAME_REQUEST", "ID_DOMAIN", "frame_id_domain")
    require(obj["lane_identity_mode"] in ("COMMON_TICK_MASK", "SCALAR_TICK_ONEHOT_PUBLIC_MAP"),
            "LANE_IDENTITY_MODE", "lane_identity_mode")
    exact(obj["anchors"], ANCHORS, "anchors")
    seen_paths = set()
    for role in ANCHORS:
        entry = obj["anchors"][role]
        require(entry is not None, "IDENTITY_ANCHOR_MISSING", "anchors." + role, True)
        path = bounded_file(artifact_root, entry, "anchors." + role)
        require(path not in seen_paths, "ARTIFACT_ALIAS", "anchors." + role)
        seen_paths.add(path)
    require(type(obj["fields"]) is list, "PUBLIC_FIELDS_STRUCTURE", "fields")
    needed = {item["name"]: item for item in contract["fields"]}
    seen = set()
    for i, item in enumerate(obj["fields"]):
        loc = f"fields[{i}]"
        exact(item, ("name", "width", "signed", "visibility", "locator"), loc)
        name = item["name"]
        require(type(name) is str and name in needed, "UNKNOWN_PUBLIC_FIELD", loc)
        require(name not in seen, "DUPLICATE_PUBLIC_FIELD", loc)
        seen.add(name)
        spec = needed[name]
        require(integer(item["width"], 1, 4096) and
                (spec["width"] is None or item["width"] == spec["width"]), "PUBLIC_WIDTH", loc)
        require(type(item["signed"]) is bool and item["signed"] == spec["signed"],
                "PUBLIC_SIGN", loc)
        allowed = "TB_DERIVED_IDENTITY" if name in ("cycle", "epoch") else "PUBLIC_OBSERVATION"
        require(item["visibility"] == allowed, "PRIVATE_STATE_OR_INVALID_DERIVATION", loc)
        locator = item["locator"]
        require(type(locator) is str and 0 < len(locator.strip()) <= 512 and
                locator.strip().upper() not in ("UNKNOWN", "PENDING", "TODO"),
                "PUBLIC_MAPPING_MISSING", loc, True)
    require(seen == set(needed), "REQUIRED_PUBLIC_FIELD_MISSING", "fields", True)
    exact(obj["semantics"], SEMANTICS, "semantics")
    for name, declaration in obj["semantics"].items():
        require(type(declaration) is str and 0 < len(declaration.strip()) <= 4096 and
                declaration.strip().upper() not in ("UNKNOWN", "PENDING", "TODO"),
                "SEMANTIC_CONTRACT_MISSING", "semantics." + name, True)
    complete = obj["completion"]
    exact(complete, ("process_exit_code", "timeout", "finish_observed", "end_observed",
                     "monitor_end_unique", "tx_sidecar_is_independent", "serial_pins_are_raw"), "completion")
    require(type(complete["process_exit_code"]) is int and complete["process_exit_code"] == 0 and
            complete["timeout"] is False, "CAPTURE_PROCESS_NOT_SUCCESS", "completion")
    for name in ("finish_observed", "end_observed", "monitor_end_unique"):
        require(complete[name] is True, "CAPTURE_CLOSURE_MISSING", "completion." + name, True)
    require(complete["tx_sidecar_is_independent"] is True and complete["serial_pins_are_raw"] is True,
            "DERIVED_TX_OR_SYNTHESIZED_PINS_FORBIDDEN", "completion")
    # Anchor hashes and declarations do not authenticate their author, verify
    # HDL exports, parse traces or derive independent event/transaction calendars.
    # Those remain explicit M2 provenance and B1 real-input work after arrival.
    return {"status": "METADATA_STRUCTURE_READY_PROVENANCE_AND_CALENDAR_PENDING",
            "scope": obj["scope"], "binding_sha256": expected_sha,
            "anchors_verified": len(ANCHORS), "fields_checked": len(seen),
            "authority_verified": False, "real_trace_calendar_checked": False,
            "pro_dut_pass": False, "board_release_allowed": False}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--binding", type=Path)
    ap.add_argument("--expected-binding-sha256")
    ap.add_argument("--artifact-root", type=Path, default=Path.cwd())
    ap.add_argument("--contract", type=Path, default=DOC / "OBSERVATION_CONTRACT.json")
    ap.add_argument("--output", type=Path, required=True)
    args = ap.parse_args()
    try:
        require(args.binding is not None and args.binding.is_file(),
                "PENDING_PRO_SOURCE_OR_TRACE", "binding", True)
        contract_raw = args.contract.read_bytes()
        require(sha(contract_raw) == CONTRACT_SHA256, "CONTRACT_SHA_MISMATCH", "contract")
        result = check(args.binding.read_bytes(), args.expected_binding_sha256,
                       args.artifact_root, strict_json(contract_raw))
        code = 0
    except Refusal as error:
        result = {"status": "PENDING_PRO_SOURCE_OR_TRACE" if error.pending else "REJECTED",
                  "code": error.code, "first_difference": error.location,
                  "pro_dut_pass": False, "board_release_allowed": False}
        code = 2
    except (OSError, TypeError, KeyError) as error:
        result = {"status": "REJECTED", "code": "INPUT_IO_OR_STRUCTURE",
                  "first_difference": type(error).__name__, "pro_dut_pass": False,
                  "board_release_allowed": False}
        code = 2
    with args.output.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    print(json.dumps(result, ensure_ascii=False))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
