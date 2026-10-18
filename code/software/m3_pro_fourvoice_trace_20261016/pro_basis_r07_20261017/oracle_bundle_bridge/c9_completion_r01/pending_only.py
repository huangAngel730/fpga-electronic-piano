"""The six original NOT_RUN cases, via a serial CALLABLE_ROUTE only."""
from __future__ import annotations

import argparse
import ast
from contextlib import redirect_stderr, redirect_stdout
import copy
import hashlib
import json
from pathlib import Path
import sys
from types import ModuleType

ROOT = Path(__file__).resolve().parents[6]
BASE = Path(__file__).resolve().parents[1]
DOC = ROOT / ("code/docs/test/m3_pro_fourvoice_trace_20261016/"
               "pro_basis_r07_20261017/oracle_bundle_bridge")
TB = ROOT / ("code/tb/board/m3_pro_fourvoice_trace_20261016/"
              "pro_basis_r07_20261017/oracle_bundle_bridge")
COMMON_PATH = ROOT / ("code/software/m3_pro_fourvoice_trace_20261016/"
    "pro_basis_r08_20261017/coordinator/task_day4_completion_20261017/common.py")
COMMON_SHA = "55cb7481fe9c0870247a7d8b2453dea859f0f2e81879795cc0e34ffe8c996dca"
OLD_PRODUCTION_SHA = "0bc7b4a3a038f5a483e7307927c8bd1934b48ab3a3b3f53639a948ca3cf9aac0"
OLD_HELPER_SHA = "a4a5172417991ba0197bd287ceea757a007d9c33fa1fa33e24c519ec0bc9689c"
SPEC_SHA = "e23c3b193f6cf971a551dfc563223b83370620c77a3de6f58570403f93cb6cb5"
CASES_SHA = "b92b3440736454df73244fb8fa2b4d1c11c475ba8f6d062fe8fbb76129188a64"
ALLOWED = (
    "hold_startup_lossless", "unknown_handshake_and_advance_preserved",
    "tampered_trace_identity", "missing_hold_field", "cycle_regression",
    "dropped_non_frame_breaks_internal_binding")
_COMMON = None


def support():
    global _COMMON
    if _COMMON is None:
        raw = COMMON_PATH.read_bytes()
        if hashlib.sha256(raw).hexdigest() != COMMON_SHA:
            raise ValueError("COMMON_SOURCE_CHANGED")
        module = ModuleType("_m3_c9_d4_common_pending")
        module.__file__ = str(COMMON_PATH)
        exec(compile(raw, str(COMMON_PATH), "exec"), module.__dict__)
        _COMMON = module
    return _COMMON


def _helpers():
    c = support()
    path = BASE / "selftest.py"
    raw = path.read_bytes()
    c.require(hashlib.sha256(raw).hexdigest() == OLD_HELPER_SHA, "OLD_HELPER_CHANGED")
    tree = ast.parse(raw.decode("utf-8"), filename=str(path))
    selected = {"sha256", "write_json", "descriptor", "line_index_sha256",
                "bind_trace", "write_r7a_trace"}
    nodes = [node for node in tree.body if
             (isinstance(node, ast.FunctionDef) and node.name in selected)]
    c.require({node.name for node in nodes} == selected, "HELPER_DEFINITION_SET")
    module = ModuleType("_m3_d4_legacy_helpers_only")
    module.__dict__.update({"copy": copy, "hashlib": hashlib, "json": json,
                            "Path": Path, "Any": object})
    derived = ast.Module(body=nodes, type_ignores=[])
    exec(compile(ast.fix_missing_locations(derived), str(path), "exec"), module.__dict__)
    module.derivation = {
        "source": c.artifact(path), "unchanged_function_nodes": sorted(selected),
        "omitted": ["all imports", "subprocess runner", "selftest main"],
        "derived_AST_sha256": hashlib.sha256(
            ast.dump(derived, include_attributes=False).encode()).hexdigest()}
    return module


def _hold_startup_synthetic_seed(source, out):
    """Satisfy the old mutation's missing TX-row precondition explicitly.

    This is a synthetic bit-transport fixture, not a physically valid TX state
    sequence or evidence that startup and HOLD should coincide in hardware.
    The unchanged old helper applies its original hold/startup mutation.
    """
    c = support()
    rows = list(c.iter_jsonl(source))  # the fixed 99-row old fixture only
    c.require(len(rows) == 99 and all(row["tx_sample_valid"] == 0 for row in rows),
              "HOLD_SEED_ORIGINAL_PRECONDITION_CHANGED")
    target = rows[1]
    c.require(target["cycle"] == 800 and target["epoch"] == 0
              and target["rst_n"] == 1 and target["frame_tick"] == 0
              and target["req_valid"] == 0 and target["apply_valid"] == 0,
              "HOLD_SEED_IDLE_ROW_CHANGED")
    before = copy.deepcopy(target)
    target["tx_sample_valid"] = 1
    target["_event_order"] = ["TX"]
    seed = out / "SYNTHETIC_TX_SEED.jsonl"
    with seed.open("x", encoding="utf-8", newline="\n") as stream:
        for row in rows:
            stream.write(json.dumps(row, separators=(",", ":"),
                                    ensure_ascii=False) + "\n")
    adaptation = {
        "schema": "M3_D4_HOLD_STARTUP_FIXTURE_ADAPTATION_V1",
        "status": "SYNTHETIC_TX_SEED_FOR_MISSING_HELPER_PRECONDITION",
        "original_fixture": c.artifact(source),
        "synthetic_seed": c.artifact(seed),
        "source_line": 2, "cycle": 800, "before": before, "after": target,
        "changed_keys": ["tx_sample_valid", "_event_order"],
        "old_helper_mutation": "hold_startup; unchanged",
        "case_definition_and_assertions_changed": False,
        "physical_TX_state_validity_claimed": False,
        "real_capture_claimed": False,
    }
    c.write_json(out / "FIXTURE_ADAPTATION.json", adaptation)
    return seed, adaptation


def run_case(case_id, output_dir):
    c = support()
    c.require(case_id in ALLOWED, "ONLY_SIX_ORIGINAL_NOT_RUN_CASES_ALLOWED")
    c.require(c.identity(DOC / "RUN_SPEC_R02.json")["sha256"] == SPEC_SHA,
              "OLD_SPEC_CHANGED")
    c.require(c.identity(TB / "cases.json")["sha256"] == CASES_SHA, "OLD_CASES_CHANGED")
    spec = c.read_json(DOC / "RUN_SPEC_R02.json")
    definition = next(case for case in c.read_json(TB / "cases.json")["cases"]
                      if case["name"] == case_id)
    for descriptor in spec["binding"]["inputs"]:
        c.checked_descriptor(descriptor)
    for descriptor in spec["frozen_files"]:
        c.checked_descriptor(descriptor)
    source = c.checked_descriptor(spec["fixture_source_trace"])
    out = c.output_directory(output_dir)
    production = c.load_source(BASE / "oracle_bundle_bridge.py", OLD_PRODUCTION_SHA)
    helper = _helpers()
    binding = copy.deepcopy(spec["binding"])
    schema_desc = next(item for item in binding["inputs"]
                       if item["role"] == "r7a_record_schema")
    required_fields = c.read_json(c.checked_descriptor(schema_desc))["properties"]["fields"]["required"]
    trace = out / "PUBLIC_ROWS.jsonl"
    mutation = definition["mutation"]
    first_mutation = "none" if mutation in {"drop_non_frame", "tampered_sha"} else mutation
    fixture_adaptation = None
    source_for_helper = source
    if case_id == "hold_startup_lossless":
        source_for_helper, fixture_adaptation = _hold_startup_synthetic_seed(source, out)
    helper.write_r7a_trace(source_for_helper, trace, binding["capture_id"],
                          required_fields, first_mutation)
    binding = helper.bind_trace(binding, trace, ROOT, out / "capture_binding.json")
    if mutation == "drop_non_frame":
        helper.write_r7a_trace(source, trace, binding["capture_id"], required_fields, mutation)
        replacement = helper.descriptor("normalized_trace", trace, ROOT)
        binding["inputs"] = [replacement if item["role"] == "normalized_trace"
                             else item for item in binding["inputs"]]
    elif mutation == "tampered_sha":
        target = next(item for item in binding["inputs"] if item["role"] == "normalized_trace")
        target["sha256"] = "0" * 64
    binding_path = out / "BINDING.json"
    c.write_json(binding_path, binding)
    c.write_json(out / "CASE_DEFINITION.json", definition)
    old_argv = sys.argv
    stdout_path, stderr_path = out / "stdout.txt", out / "stderr.txt"
    callable_argv = [str(BASE / "oracle_bundle_bridge.py"), "--binding",
                     str(binding_path), "--root", str(ROOT), "--output", str(out / "bundle")]
    try:
        sys.argv = callable_argv
        with stdout_path.open("x", encoding="utf-8", newline="\n") as stdout, \
                stderr_path.open("x", encoding="utf-8", newline="\n") as stderr, \
                redirect_stdout(stdout), redirect_stderr(stderr):
            actual_exit = production.main()
    finally:
        sys.argv = old_argv
    channel = stdout_path if actual_exit == 0 else stderr_path
    lines = channel.read_text(encoding="utf-8").splitlines()
    c.require(bool(lines), "NO_ACTUAL_PRODUCTION_DIAGNOSTIC")
    payload = c.loads(lines[-1])
    c.require(actual_exit == definition["expected_exit"], "LEGACY_EXPECTED_EXIT")
    c.require(payload["status"] == definition["expected_status"], "LEGACY_EXPECTED_STATUS")
    if "error_contains" in definition:
        c.require(definition["error_contains"] in payload.get("error", ""), "LEGACY_EXPECTED_ERROR")
    if actual_exit == 0:
        bundle_root = out / "bundle"
        bundle = c.read_json(bundle_root / "BUNDLE.json")
        gaps = c.read_json(bundle_root / "CONTRACT_GAPS.json")
        # The original fixture has 99 rows; this bounded old-only test may collect it.
        rows = list(c.iter_jsonl(bundle_root / "ROW_INDEX.jsonl"))
        c.require(bundle["row_count"] == 99 and len(rows) == 99, "LEGACY_ROW_COUNT")
        c.require(gaps["legacy_b0_status"] == "PENDING_UNSUPPORTED_PROFILE", "LEGACY_PROFILE_UPGRADE")
        copied = next(item for item in bundle["inputs"] if item["role"] == "normalized_trace")
        c.require(copied["byte_exact"], "LEGACY_TRACE_COPY")
        c.require(any(row["midi_event_association"]["status"]
                      == "PLAN_PAYLOAD_UNIQUE_OUTSIDE_ARRIVAL_WINDOW" for row in rows),
                  "LEGACY_DELAYED_ASSOCIATION")
        if mutation == "hold_startup":
            c.require(any(row["tx"]["sample_valid"] == 1 and row["tx"]["hold"] == 1
                          and row["tx"]["startup_zero"] == 1 for row in rows),
                      "LEGACY_HOLD_STARTUP_LOSS")
        if mutation == "unknown_handshake":
            unknown = [row for row in rows if row["request_a"] is None]
            c.require(bool(unknown) and "REQUEST_A_UNKNOWN" in unknown[0]["signals"]
                      and unknown[0]["common_advance"] is None, "LEGACY_UNKNOWN_LOSS")
    result = {
        "schema": "M3_D4_OLD_R7C_PENDING_CASE_RECEIPT_V1",
        "case_id": case_id, "status": "PASS", "route": "CALLABLE_ROUTE",
        "actual_production_exit": actual_exit, "actual_payload": payload,
        "callable_argv": callable_argv, "process_started": False,
        "original_case_definition": c.artifact(out / "CASE_DEFINITION.json"),
        "helper_derivation": helper.derivation,
        "fixture_adaptation": fixture_adaptation,
        "stdout": c.artifact(stdout_path), "stderr": c.artifact(stderr_path),
        "old_consumption_modified": False, "original_positive_rerun": False,
        "C9_or_large_file_claim": False, "real_verified": False,
        "board_release_allowed": False}
    c.write_json(out / "RESULT.json", result)
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", required=True, choices=ALLOWED)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(run_case(args.case, args.output)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
