"""Combine signed T060 receipts only; no capture replay or RTL execution."""

import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import time

ROOT = Path(__file__).resolve().parents[4]
DOC = ROOT / "code/docs/hardware/audio_math_acceptance_v1"
REVIEW = ROOT / "code/docs/evidence/m2_t060_counter_closure_review_20261011"
SCOPE_SHA = "793a586add95ed4f766690b50258971e3895eba13e0c169831ac37cd3143f0a2"
ROUTER_CARRIER_SHA = "a6e33c1ef54ebc955e029b201f474f027a7273839f3e17539465fcb8043cfd34"
ROUTER_CONTAINER_SHA = "bb1b3487494c130e0c6b55a0e006084aa978961381379b9b6c5d18bce370a401"
COUNTER_ZIP_SHA = "21132b3ca8511900a9323c53056710673c12117822a0b90c03647cf08ed6fa97"
INPUTS = {
    "audio_observation.jsonl": "d17cf87952ac0c663e681e0b47051e9412af4a2979fb509aaa5d7114d5b32cc5",
    "midi_pcm.capture": "bd0035de464cb8c757c7e29a132073181e9e8179aa8303ab1ec110c6990042d6"}


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def require(value, reason):
    if not value:
        raise ValueError(reason)


def dump(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def project(scope):
    """Exact exclusions only, never infer math expectations from flags."""
    require(scope["input_sha256"] == INPUTS, "T060_SCOPE_INPUT_SHA")
    require(scope["newly_independently_verified_END"] == dict(full_pop_push=1, edge_events=19),
            "T060_SCOPE_COUNTERS")
    end = scope["END_metadata_expectation_exclusions"]
    require([(e["field"], e["observed_original"], e["independently_expected"]) for e in end]
            == [("control_stalls", 28, None), ("center_samples", 697, None),
                ("checks", 6228000, None)], "T060_SCOPE_END_EXCLUSIONS")
    flags = scope["exact_fixture_metadata_expectation_exclusions"]
    require([(f["epoch"], f["cycle"], f["request_id"], f["observed_flag"],
              f["independently_expected_flag"]) for f in flags]
            == [(1, 1744211, 2094, 1, None), (1, 1745045, 2095, 1, None)],
            "T060_SCOPE_FLAG_POINTS")
    require(all(type(f[k]) is int for f in flags for k in (
        "epoch", "cycle", "request_id", "observed_flag")), "T060_SCOPE_FLAG_TYPE")
    require(scope["t060_complete"] is False and scope["old_exit3_unchanged"] is True
            and scope["new_capture_RTL_execution_authorized"] is False
            and scope["physical_STA_passed"] is False, "T060_SCOPE_BOUNDARY")
    return dict(schema=1, status="T060_REUSED_EVIDENCE_SCOPE_PARTIAL", t060_complete=False,
                original_input_sha256=dict(INPUTS), END_metadata=[dict(
                    field=e["field"], observed=e["observed_original"], expected=None,
                    disposition="metadata_expectation_excluded", independently_recomputed=False)
                    for e in end], exact_fixture_flags=[dict(
                    epoch=f["epoch"], cycle=f["cycle"], request_id=f["request_id"],
                    observed=f["observed_flag"], expected=None,
                    disposition="metadata_expectation_excluded",
                    PCM_math_and_timing_excluded=False) for f in flags],
                independently_verified_counters=dict(status="REUSED", review="V0283",
                                                      full_pop_push=1, edge_events=19),
                mandatory_strict_checks=scope["must_remain_verified"],
                functional_gaps_not_waived=scope["functional_coverage_not_waived"],
                old_entry=dict(status="PARTIAL", exit_code=3, modified=False,
                               unsupported="ROUTER_OVERLAPPING_FRAME_MATH_UNCOVERED"),
                physical=dict(new_STA_run=False, new_device_operation=False, verified=False),
                no_flag_based_golden_selection=True, applies_to_other_inputs=False,
                new_RTL_execution_authorized=False, old_big_replay_executed=False,
                old_56_negatives_executed=False)


def build():
    scope_raw = (REVIEW / "ACCEPTANCE_SCOPE.json").read_bytes()
    require(sha(scope_raw) == SCOPE_SHA, "T060_SCOPE_AUTHORITY_SHA")
    result = project(json.loads(scope_raw))
    paths = [REVIEW / "ACCEPTANCE_SCOPE.json", REVIEW / "SUMMARY.json",
             DOC / "ROUTER_EVIDENCE_MANIFEST_20261010.json",
             DOC / "ROUTER_EVIDENCE_20261010.json.gz.b64",
             DOC / "CLOSURE_20261011_02/manifest.json",
             DOC / "CLOSURE_20261011_02/seal_receipt.json",
             DOC / "CLOSURE_20261011_02/evidence.zip.b64"]
    carrier = paths[3].read_bytes()
    require(sha(carrier) == ROUTER_CARRIER_SHA, "T060_SCOPE_ROUTER_CARRIER")
    container = gzip.decompress(base64.b64decode(carrier))
    require(sha(container) == ROUTER_CONTAINER_SHA, "T060_SCOPE_ROUTER_CONTAINER")
    records = json.loads(container)
    member = "code/output/m3_audio_router_final_20261010_01/receipt.json"
    record = records[member]
    receipt_raw = base64.b64decode(record["raw_base64"], validate=True)
    require(sha(receipt_raw) == record["sha256"], "T060_SCOPE_ROUTER_RECEIPT")
    receipt = json.loads(receipt_raw)
    require(receipt["exit_code"] == 3 and receipt["status"] == "ROUTER_AUDIO_MATCH_AWAITING_M2_CLOSURE",
            "T060_SCOPE_ORIGINAL_PARTIAL")
    require({Path(i["path"]).name: i["sha256"] for i in receipt["capture_inputs"]} == INPUTS,
            "T060_SCOPE_ROUTER_INPUTS")
    counter_raw = base64.b64decode(paths[-1].read_bytes(), validate=True)
    require(sha(counter_raw) == COUNTER_ZIP_SHA, "T060_SCOPE_COUNTER_SEAL")
    m2 = json.loads(paths[1].read_text(encoding="utf-8"))
    require(m2["counts"]["full_pop_push"] == 1 and m2["counts"]["edge_events"] == 19,
            "T060_SCOPE_M2_COUNTER_RECEIPT")
    result["reused_router_and_math"] = dict(status="REUSED", new_execution=False,
        receipt_member=member, receipt_sha256=sha(receipt_raw),
        receipt_original_exit_code=3, limited_offline_math_L3=True,
        current_counter_review="V0283", retirement_capture_proved=False,
        overlap_capture_proved=False, scope="exact H/capture2 only")
    result["reused_sources"] = {p.relative_to(ROOT).as_posix(): dict(
        bytes=p.stat().st_size, sha256=sha(p.read_bytes())) for p in paths}
    return result, paths


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    require(out != ROOT / "code/output" and out.is_relative_to(ROOT / "code/output"),
            "T060_SCOPE_OUTPUT")
    out.mkdir(parents=True, exist_ok=False)
    start = time.monotonic()
    result, paths = build()
    before = result["reused_sources"]
    dump(out / "scope.json", result)
    after = {p.relative_to(ROOT).as_posix(): dict(bytes=p.stat().st_size,
             sha256=sha(p.read_bytes())) for p in paths}
    require(before == after, "T060_SCOPE_READ_ONLY_DRIFT")
    dump(out / "receipt.json", dict(status="T060_SCOPE_COMBINED_L0_L1_ONLY", exit_code=0,
         t060_complete=False, elapsed_seconds=time.monotonic() - start,
         reused_before=before, reused_after=after, new_math_replays=0,
         new_RTL_simulation=False, scope_sha256=sha((out / "scope.json").read_bytes())))
    print(json.dumps(dict(exit_code=0, t060_complete=False, new_math_replays=0)))


if __name__ == "__main__":
    main()
