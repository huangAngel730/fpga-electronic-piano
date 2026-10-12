"""Strict, portable T060 scope composition; never imports sound models."""

import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import sys


HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
REVIEW = "code/docs/evidence/m2_t060_counter_closure_review_20261011"
ROUTER = "code/docs/hardware/audio_math_acceptance_v1/ROUTER_EVIDENCE_20261010.json.gz.b64"
ROUTER_MEMBER = "code/output/m3_audio_router_final_20261010_01/receipt.json"
PINS = {
    "acceptance_scope.json": "793a586add95ed4f766690b50258971e3895eba13e0c169831ac37cd3143f0a2",
    "counter_review.json": "75078c3200922df24495b95c4274fd48d15cab10d5bd701d47680a3542876500",
    "router_receipt.json": "1eeaaf8ad6c635d673a9db197b4bfe638872c310aa18fd3527d1709b014dff17",
}
INPUT_SHA = {
    "audio_observation.jsonl": "d17cf87952ac0c663e681e0b47051e9412af4a2979fb509aaa5d7114d5b32cc5",
    "midi_pcm.capture": "bd0035de464cb8c757c7e29a132073181e9e8179aa8303ab1ec110c6990042d6",
}


def require(condition, diagnostic):
    if not condition:
        raise ValueError(diagnostic)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def identity(raw):
    return {"bytes": len(raw), "sha256": sha(raw)}


def canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False,
                      separators=(",", ":")).encode("utf-8")


def pairs(items):
    result = {}
    for key, value in items:
        require(key not in result, "SCOPE_DUPLICATE_KEY:" + key)
        result[key] = value
    return result


def load(raw):
    def invalid_constant(value):
        raise ValueError("SCOPE_NONFINITE:" + value)
    return json.loads(raw, object_pairs_hook=pairs, parse_constant=invalid_constant)


def dump(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, allow_nan=False, indent=2)
        stream.write("\n")


def fresh(path):
    path = path.resolve()
    require(not path.exists(), "SCOPE_OUTPUT_EXISTS")
    path.mkdir(parents=True)
    return path


def read_authority(bundle):
    """Trust anchors are fixed source constants, never a re-signed input manifest."""
    authority = bundle / "authority"
    require(authority.is_dir() and not authority.is_symlink(), "SCOPE_MISSING_RECEIPT")
    require({p.name for p in authority.iterdir()} == set(PINS), "SCOPE_RECEIPT_SET")
    raw = {}
    for name, expected in PINS.items():
        path = authority / name
        require(path.is_file() and not path.is_symlink(), "SCOPE_MISSING_RECEIPT:" + name)
        data = path.read_bytes()
        require(sha(data) == expected, "SCOPE_RECEIPT_SHA:" + name)
        raw[name] = data
    return raw


def path_key(path):
    text = path.replace("\\", "/")
    require("/code/" in text, "SCOPE_HISTORICAL_PATH")
    return "code/" + text.split("/code/", 1)[1]


def expected_summary(raw):
    scope = load(raw["acceptance_scope.json"])
    counter = load(raw["counter_review.json"])
    router = load(raw["router_receipt.json"])
    require(scope["input_sha256"] == INPUT_SHA, "SCOPE_AUTHORITY_INPUT")
    require(router["exit_code"] == 3 and router["t060_complete"] is False
            and router["status"] == "ROUTER_AUDIO_MATCH_AWAITING_M2_CLOSURE",
            "SCOPE_ORIGINAL_PARTIAL")
    require(router["audio_math_replayed"] is True and router["independent_router_replayed"] is True,
            "SCOPE_REUSED_MATH_RECEIPT")
    captures = {Path(i["path"].replace("\\", "/")).name: identity_record(i)
                for i in router["capture_inputs"]}
    require({k: v["sha256"] for k, v in captures.items()} == INPUT_SHA,
            "SCOPE_REUSED_CAPTURE_SHA")
    require(counter["counts"]["full_pop_push"] == 1 and counter["counts"]["edge_events"] == 19
            and counter["new_PCM_math"] is False, "SCOPE_COUNTER_RECEIPT")
    frozen = {path_key(i["path"]): identity_record(i) for i in router["frozen_inputs"]}
    dependencies = {path_key(i["path"]): identity_record(i) for i in router["candidate_sources"]}
    require(len(frozen) == 56 and len(dependencies) == 13, "SCOPE_HISTORICAL_SOURCE_SET")
    rom = {k: v for k, v in frozen.items() if "/rom/" in k}
    require(len(rom) == 7, "SCOPE_HISTORICAL_ROM_SET")
    return {
        "schema": 1,
        "status": "T060_SCOPE_SOFTWARE_COMPOSITION_PARTIAL",
        "baseline": "H_pll_core40_route2 / exact original capture2 only",
        "input_identity": captures,
        "ROM_identity": rom,
        "dependency_identity": dependencies,
        "frozen_source_identity": frozen,
        "identity_basis": "Historical original receipt, not a new source/capture/math execution",
        "reused_receipts": {name: identity(data) for name, data in sorted(raw.items())},
        "REUSED": {
            "router_and_audio_math": {"receipt": "router_receipt.json", "original_exit_code": 3,
                                      "limited_offline_math_L3": True, "new_execution": False},
            "two_END_counters": {"review": "V0283", "full_pop_push": 1, "edge_events": 19,
                                 "real_E_K_same_edge_hits": 0, "new_execution": False},
        },
        "EXCLUDED_METADATA_EXPECTATION": {
            "END": [{"field": i["field"], "observed": i["observed_original"], "expected": None,
                     "independently_recomputed": False}
                    for i in scope["END_metadata_expectation_exclusions"]],
            "fixture_points": [{"epoch": i["epoch"], "cycle": i["cycle"],
                                "request_id": i["request_id"], "observed_flag": i["observed_flag"],
                                "expected": None, "PCM_math_and_timing_excluded": False}
                               for i in scope["exact_fixture_metadata_expectation_exclusions"]],
        },
        "mandatory_strict_checks": scope["must_remain_verified"],
        "UNCOVERED": scope["functional_coverage_not_waived"],
        "NOT_RUN": ["new capture math replay", "old 56 negative captures", "new RTL capture",
                    "synthesis", "PnR", "physical STA", "device validation"],
        "t060_complete": False, "t061_complete": False,
        "physical_STA_passed": False, "physical_validation": False,
        "new_RTL_execution_authorized": False,
        "old_entry": {"modified": False, "status": "PARTIAL", "exit_code": 3,
                      "unsupported": "ROUTER_OVERLAPPING_FRAME_MATH_UNCOVERED"},
        "metadata_does_not_select_golden_PCM": True,
        "applies_to_future_capture_automatically": False,
    }


def identity_record(record):
    return {"bytes": record["bytes"], "sha256": record["sha256"]}


def validate_summary(summary, expected):
    require(type(summary) is dict, "SCOPE_SUMMARY_TYPE")
    # JSON canonical equality distinguishes bool/int/float, unlike Python ==.
    for key, diagnostic in (
        ("input_identity", "SCOPE_INPUT_IDENTITY"),
        ("ROM_identity", "SCOPE_ROM_IDENTITY"),
        ("dependency_identity", "SCOPE_DEPENDENCY_IDENTITY"),
        ("frozen_source_identity", "SCOPE_SOURCE_IDENTITY"),
        ("reused_receipts", "SCOPE_RECEIPT_IDENTITY"),
        ("EXCLUDED_METADATA_EXPECTATION", "SCOPE_EXCLUSION_WIDENED"),
        ("mandatory_strict_checks", "SCOPE_STRICT_CHECKS_REMOVED"),
        ("UNCOVERED", "SCOPE_FUNCTIONAL_GAP_WAIVED"),
        ("t060_complete", "SCOPE_FALSE_COMPLETE"),
        ("t061_complete", "SCOPE_FALSE_COMPLETE"),
        ("physical_STA_passed", "SCOPE_FALSE_STA"),
        ("physical_validation", "SCOPE_FALSE_PHYSICAL"),
        ("new_RTL_execution_authorized", "SCOPE_FALSE_RTL_PERMISSION"),
        ("REUSED", "SCOPE_FALSE_REPLAY_CLAIM"),
        ("NOT_RUN", "SCOPE_FALSE_RUN_CLAIM"),
        ("old_entry", "SCOPE_OLD_PARTIAL_CHANGED"),
    ):
        require(key in summary and canonical(summary[key]) == canonical(expected[key]), diagnostic)
    require(canonical(summary) == canonical(expected), "SCOPE_SUMMARY_SCHEMA_OR_BOUNDARY")


def prepare(repo, output):
    # Read only three small receipts; no original capture/ROM/math module is executed or replayed.
    review = repo / REVIEW
    raw = {"acceptance_scope.json": (review / "ACCEPTANCE_SCOPE.json").read_bytes(),
           "counter_review.json": (review / "SUMMARY.json").read_bytes()}
    carrier = (repo / ROUTER).read_bytes()
    require(sha(carrier) == "a6e33c1ef54ebc955e029b201f474f027a7273839f3e17539465fcb8043cfd34",
            "SCOPE_ROUTER_CARRIER_SHA")
    container = gzip.decompress(base64.b64decode(carrier, validate=False))
    require(sha(container) == "bb1b3487494c130e0c6b55a0e006084aa978961381379b9b6c5d18bce370a401",
            "SCOPE_ROUTER_CONTAINER_SHA")
    raw["router_receipt.json"] = base64.b64decode(load(container)[ROUTER_MEMBER]["raw_base64"],
                                                validate=True)
    for name, expected in PINS.items():
        require(sha(raw[name]) == expected, "SCOPE_RECEIPT_SHA:" + name)
    summary = expected_summary(raw)
    output = fresh(output)
    (output / "authority").mkdir()
    for name, data in raw.items():
        (output / "authority" / name).write_bytes(data)
    dump(output / "scope.json", summary)
    return {"status": "SCOPE_PREPARED_NOT_NEW_MATH", "exit_code": 0,
            "summary": identity((output / "scope.json").read_bytes()), "t060_complete": False}


def verify(bundle, summary_path=None):
    raw = read_authority(bundle)
    expected = expected_summary(raw)
    data = (summary_path or bundle / "scope.json").read_bytes()
    validate_summary(load(data), expected)
    return {"status": "SCOPE_STRUCTURE_AND_IDENTITY_PASS_ONLY", "exit_code": 0,
            "summary": identity(data), "t060_complete": False, "new_math_replays": 0,
            "RTL_runs": 0, "EDA_runs": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    create = modes.add_parser("prepare")
    create.add_argument("--repo", type=Path, default=ROOT)
    create.add_argument("--output", type=Path, required=True)
    check = modes.add_parser("verify")
    check.add_argument("--bundle", type=Path, required=True)
    check.add_argument("--summary", type=Path)
    args = parser.parse_args()
    try:
        result = prepare(args.repo.resolve(), args.output) if args.mode == "prepare" else verify(
            args.bundle, args.summary)
    except (ValueError, KeyError, OSError, TypeError) as error:
        print(json.dumps({"status": "REJECTED_SCOPE", "exit_code": 1, "diagnostic": str(error)}))
        return 1
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
