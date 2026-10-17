"""Binding-envelope attack fixtures only; no toy DUT, waveform or calendar."""
from copy import deepcopy
import json
from pathlib import Path

from check_observation_binding import ANCHORS, SEMANTICS, sha


def save(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def prepare(out, contract):
    inputs = out / "inputs"
    inputs.mkdir()
    bodies = inputs / "METADATA_ONLY_NOT_PRO_ARTIFACTS"
    bodies.mkdir()
    anchors = {}
    for role in ANCHORS:
        raw = ("SCHEMA_TEST_MARKER_ONLY_NO_RTL_NO_TRACE_NO_M2_ATTESTATION " + role + "\n").encode()
        p = bodies / (role + ".txt")
        p.write_bytes(raw)
        anchors[role] = {"path": p.relative_to(inputs).as_posix(), "bytes": len(raw), "sha256": sha(raw)}
    base = {"schema": "M3_B1_OBSERVATION_BINDING_V1", "scope": "SYNTHETIC_METADATA_SELFTEST_NOT_PRO",
            "pro_dut_pass": False, "board_release_allowed": False, "sample_edge": "POSEDGE_PRE_NBA",
            "clock_hz": 40000000, "nominal_sample_rate_hz": 48000, "frame_id_domain": "FRAME_REQUEST",
            "lane_identity_mode": "COMMON_TICK_MASK", "anchors": anchors,
            "fields": [{"name": f["name"], "width": f["width"] or 8, "signed": f["signed"],
                        "visibility": "TB_DERIVED_IDENTITY" if f["name"] in ("cycle", "epoch") else "PUBLIC_OBSERVATION",
                        "locator": "METADATA_SELFTEST_NOT_A_PRO_PORT:" + f["name"]} for f in contract["fields"]],
            "semantics": {name: "METADATA_SELFTEST_DECLARATION_NOT_REAL_SEMANTICS" for name in SEMANTICS},
            "completion": {"process_exit_code": 0, "timeout": False, "finish_observed": True,
                           "end_observed": True, "monitor_end_unique": True,
                           "tx_sidecar_is_independent": True, "serial_pins_are_raw": True}}
    plans = []

    def add(name, code, location, mutate=None, raw_transform=None, expected_hash=None):
        obj = deepcopy(base)
        if mutate:
            mutate(obj)
        p = inputs / (name + ".json")
        if raw_transform:
            raw = raw_transform(json.dumps(obj, ensure_ascii=False).encode())
            p.write_bytes(raw)
        else:
            save(p, obj)
            raw = p.read_bytes()
        plans.append({"name": name, "binding": str(p), "expected_sha256": expected_hash or sha(raw),
                      "expected_exit": 0 if code is None else 2,
                      "expected_code": code, "expected_first_difference": location})

    def field(obj, name):
        return next(f for f in obj["fields"] if f["name"] == name)

    add("metadata_structure_positive_only", None, None)
    add("wrong_expected_binding_sha", "BINDING_SHA_MISMATCH", "binding", expected_hash="0" * 64)
    add("unprovided_expected_binding_sha", "EXPECTED_BINDING_SHA_REQUIRED", "expected_sha256")
    plans[-1]["expected_sha256"] = None
    add("legacy_toy_scope", "SCOPE", "scope", lambda x: x.update(scope="SYNTHETIC_FIXTURE_NOT_PRO_DUT"))
    add("false_Pro_PASS", "UNSUPPORTED_PRO_OR_BOARD_CLAIM", "claims", lambda x: x.update(pro_dut_pass=True))
    add("false_board_release", "UNSUPPORTED_PRO_OR_BOARD_CLAIM", "claims", lambda x: x.update(board_release_allowed=True))
    add("wrong_edge", "SAMPLING_PHASE", "sample_edge", lambda x: x.update(sample_edge="POST_NBA"))
    add("bool_clock", "CLOCK_CONTRACT", "clock", lambda x: x.update(clock_hz=True))
    add("lane_as_frame_ID", "ID_DOMAIN", "frame_id_domain", lambda x: x.update(frame_id_domain="LANE_REQUEST"))
    add("staggered_toy_lanes", "LANE_IDENTITY_MODE", "lane_identity_mode", lambda x: x.update(lane_identity_mode="TOY_STAGGERED_LANES"))
    add("missing_trace_anchor", "IDENTITY_ANCHOR_MISSING", "anchors.public_trace", lambda x: x["anchors"].update(public_trace=None))
    add("missing_M2_binding_review", "IDENTITY_ANCHOR_MISSING", "anchors.m2_binding_review", lambda x: x["anchors"].update(m2_binding_review=None))
    add("path_traversal", "ARTIFACT_PATH", "anchors.source_manifest", lambda x: x["anchors"]["source_manifest"].update(path="../outside.txt"))
    add("absolute_path", "ARTIFACT_PATH", "anchors.source_manifest", lambda x: x["anchors"]["source_manifest"].update(path="C:/outside.txt"))
    add("artifact_bool_size", "ARTIFACT_SIZE", "anchors.source_manifest", lambda x: x["anchors"]["source_manifest"].update(bytes=True))
    add("source_manifest_byte_drift", "ARTIFACT_BYTES", "anchors.source_manifest", lambda x: x["anchors"]["source_manifest"].update(bytes=1))
    add("trace_sha_drift", "ARTIFACT_SHA_MISMATCH", "anchors.public_trace", lambda x: x["anchors"]["public_trace"].update(sha256="f" * 64))
    add("anchor_alias", "ARTIFACT_ALIAS", "anchors.rom_manifest", lambda x: x["anchors"].update(rom_manifest=deepcopy(x["anchors"]["source_manifest"])))
    add("missing_advance_mask", "REQUIRED_PUBLIC_FIELD_MISSING", "fields", lambda x: x.update(fields=[f for f in x["fields"] if f["name"] != "advance_mask"]))
    add("missing_TX_adoption_ID", "REQUIRED_PUBLIC_FIELD_MISSING", "fields", lambda x: x.update(fields=[f for f in x["fields"] if f["name"] != "tx_req_id"]))
    add("missing_effect_input_accept", "REQUIRED_PUBLIC_FIELD_MISSING", "fields", lambda x: x.update(fields=[f for f in x["fields"] if f["name"] != "effect_input_ready"]))
    add("duplicate_cycle_field", "DUPLICATE_PUBLIC_FIELD", "fields[61]", lambda x: x["fields"].append(deepcopy(x["fields"][0])))
    add("wrong_PCM_width", "PUBLIC_WIDTH", "fields[27]", lambda x: field(x, "result_left").update(width=16))
    add("private_PCM_as_golden", "PRIVATE_STATE_OR_INVALID_DERIVATION", "fields[27]", lambda x: field(x, "result_left").update(visibility="PRIVATE_DSP_STATE"))
    add("unknown_public_map", "PUBLIC_MAPPING_MISSING", "fields[27]", lambda x: field(x, "result_left").update(locator="UNKNOWN"))
    add("whitespace_public_map", "PUBLIC_MAPPING_MISSING", "fields[27]", lambda x: field(x, "result_left").update(locator="  \t  "))
    add("padded_unknown_public_map", "PUBLIC_MAPPING_MISSING", "fields[27]", lambda x: field(x, "result_left").update(locator=" UNKNOWN "))
    add("missing_Release_semantics", "SEMANTIC_CONTRACT_MISSING", "semantics.allocator_release_retire", lambda x: x["semantics"].update(allocator_release_retire="UNKNOWN"))
    add("whitespace_Release_semantics", "SEMANTIC_CONTRACT_MISSING", "semantics.allocator_release_retire", lambda x: x["semantics"].update(allocator_release_retire=" \t "))
    add("padded_pending_Release_semantics", "SEMANTIC_CONTRACT_MISSING", "semantics.allocator_release_retire", lambda x: x["semantics"].update(allocator_release_retire=" PENDING "))
    add("missing_finish", "CAPTURE_CLOSURE_MISSING", "completion.finish_observed", lambda x: x["completion"].update(finish_observed=False))
    add("missing_END", "CAPTURE_CLOSURE_MISSING", "completion.end_observed", lambda x: x["completion"].update(end_observed=False))
    add("missing_MONITOR_END", "CAPTURE_CLOSURE_MISSING", "completion.monitor_end_unique", lambda x: x["completion"].update(monitor_end_unique=False))
    add("failed_capture", "CAPTURE_PROCESS_NOT_SUCCESS", "completion", lambda x: x["completion"].update(process_exit_code=1))
    add("timeout_capture", "CAPTURE_PROCESS_NOT_SUCCESS", "completion", lambda x: x["completion"].update(timeout=True))
    add("commit_filled_TX_sample", "DERIVED_TX_OR_SYNTHESIZED_PINS_FORBIDDEN", "completion", lambda x: x["completion"].update(tx_sidecar_is_independent=False))
    add("PCM_synthesized_serial", "DERIVED_TX_OR_SYNTHESIZED_PINS_FORBIDDEN", "completion", lambda x: x["completion"].update(serial_pins_are_raw=False))
    add("duplicate_JSON_claim_key", "DUPLICATE_JSON_KEY", "scope", raw_transform=lambda b: b.replace(b'{', b'{"scope":"PRO_BINDING_REVIEW_ONLY",', 1))
    add("truncated_JSON", "JSON_ENCODING_OR_SYNTAX", "document", raw_transform=lambda b: b[:-2])
    add("empty_replacement_contract", "CONTRACT_SHA_MISMATCH", "contract")
    replacement = inputs / "UNTRUSTED_EMPTY_CONTRACT.json"
    save(replacement, {"fields": []})
    plans[-1]["contract"] = str(replacement)
    plans.append({"name": "actual_missing_Pro_arrival", "binding": None, "expected_sha256": None,
                  "expected_exit": 2, "expected_code": "PENDING_PRO_SOURCE_OR_TRACE",
                  "expected_first_difference": "binding"})
    return plans
