"""Read failed real artifacts, prepare L0 fix, seal without any new tool run."""
from collections import Counter
from datetime import datetime, timezone
import difflib
import hashlib
import json
from pathlib import Path
import sys
import zipfile

HERE = Path(__file__).resolve().parent
SOFT = HERE.parent
sys.path.insert(0, str(SOFT.parent.parent))
from common import ROOT, DOCS, TB_DIR, R05, identity, write_new

BASE = DOCS / "night_20261016/RESUME_R01"
RUN = BASE / "RUN_04"
STAGE = RUN / "stage/inputs"


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def inspect_jsonl(path):
    raw = path.read_bytes()
    records = [json.loads(line) for line in raw.splitlines()]
    return records


def main():
    assert len(list(BASE.glob("RUN_*_CONSUMED.json"))) == 3
    assert not (BASE / "CAPTURE_READY.json").exists()
    summaries = []
    for name in ("RUN_01", "RUN_02", "RUN_03", "RUN_04"):
        p = BASE / name / "RUN_RECEIPT.json"
        r = load(p)
        summaries.append({"run": name, "receipt": identity(p), "status": r["status"], "error": r.get("error"),
            "functional_attempt_consumed": r["functional_attempt_consumed"],
            "functional_calls": [{k: c[k] for k in ("argv", "cwd", "exit_code", "elapsed_s", "stdout", "stderr", "process_created", "timeout")} for c in r["functional_calls"]],
            "elapsed_s": r["elapsed_s"], "source_before_equals_after": r["source_before"] == r["source_after"],
            "tool_pin_available": "tool_before" in r,
            "tools_before_equals_after": r.get("tool_before") == r.get("tool_after") if "tool_before" in r else None})
    raw_capture = inspect_jsonl(STAGE / "STARTUP_CAPTURE.jsonl")
    raw_inputs = inspect_jsonl(STAGE / "STARTUP_INPUTS.jsonl")
    ticks = [r for r in raw_capture if r.get("kind") == "STARTUP_TICK"]
    input_ticks = [r for r in raw_inputs if r.get("kind") == "STARTUP_TICK"]
    schema = load(BASE / "STARTUP_SCHEMA.json")
    widths = schema["startup_capture"]["binary_field_widths"]
    input_widths = schema["startup_inputs"]["binary_field_widths"]
    def rows_check(rows, fields):
        for i, row in enumerate(rows, 1):
            assert row["absolute_cycle"] == i
            assert row["time_ps"] == 12500 + (i-1)*25000
            for key, width in fields.items():
                assert isinstance(row[key], str) and len(row[key]) == width
                assert set(row[key]) <= set("01xXzZ")
    rows_check(ticks, widths)
    rows_check(input_ticks, input_widths)
    diagnostics = {}
    for key in widths:
        values = Counter(row[key] for row in ticks)
        if any(any(c in "xXzZ" for c in value) for value in values):
            diagnostics[key] = dict(values)
    main_capture = inspect_jsonl(STAGE / "REAL_CAPTURE.jsonl")
    main_inputs = inspect_jsonl(STAGE / "REAL_INPUTS.jsonl")
    main_ticks = [r for r in main_capture if r.get("kind") == "TICK"]
    assert not main_ticks
    assert not (STAGE / "STARTUP_BOUNDARY_RAW.json").exists()
    assert diagnostics == {"clipped": {"z": len(ticks)}}
    raw_ids = {name: identity(STAGE / name) for name in ("STARTUP_CAPTURE.jsonl", "STARTUP_INPUTS.jsonl", "REAL_CAPTURE.jsonl", "REAL_INPUTS.jsonl")}
    inspection = {"kind": "FAILED_REAL_RTL_PREFIX_ONLY", "raw_files": raw_ids,
        "startup_rows": len(ticks), "startup_input_rows": len(input_ticks),
        "prefix_contiguous_until_fatal": True, "prefix_counts_equal": len(ticks) == len(input_ticks),
        "startup_end": raw_capture[-1], "startup_input_end": raw_inputs[-1],
        "actual_unknown_fields": diagnostics, "other_audio_fields_known_in_recorded_prefix": True,
        "main_ticks": 0, "main_end": main_capture[-1], "input_end": main_inputs[-1],
        "boundary_raw_generated": False, "ready_generated": False, "real_business_evidence": "UNKNOWN_NOT_CAPTURED"}
    write_new(BASE / "FAILED_PREFIX_INSPECTION.json", inspection)
    # Small future fix; no running, compiling or changing any failed candidate.
    old = ROOT / "code/tb/board/m3_night_fourvoice_integration_candidate_20261015/night_20261016/RESUME_R01/FIX_02/m2_fourvoice_timbre_delay_board_observed.sv"
    new = old.parent.parent / "FIX_03_PENDING" / old.name
    new.parent.mkdir(exist_ok=False)
    before = old.read_bytes()
    declaration = b"    wire night_committed_clip;\n"
    assert before.count(declaration) == 1
    after = before.replace(declaration, b"").replace(b"    wire night_config_valid,night_config_ready;", b"    wire night_config_valid,night_config_ready;\n" + declaration.rstrip(b"\n"))
    assert after.index(declaration.rstrip(b"\n")) < after.index(b"    generate")
    new.write_bytes(after)
    d = BASE / "FIX03_PENDING_DECLARATION.diff"
    d.write_text("".join(difflib.unified_diff(before.decode().splitlines(True), after.decode().splitlines(True),
        fromfile="failed_FIX02", tofile="pending_L0_FIX03")), encoding="utf-8", newline="\n")
    write_new(BASE / "FIX03_PENDING.json", {"status": "L0_STATIC_ONLY_NOT_COMPILED_OR_RUN", "before": identity(old), "after": identity(new),
        "diff": identity(d), "change": "Move observation-only night_committed_clip declaration before generate use",
        "reason": "Real prefix shows clipped Z; late outer declaration allows an earlier generate-scope implicit net",
        "remaining_functional_allowance": 0, "algorithm_rom_clock_modified": False})
    receipt = {"schema": "M3_R05_RESUME_FINAL_RECEIPT_V1", "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "PARTIAL_BLOCKED_FUNCTIONAL_BUDGET_EXHAUSTED", "baseline_head": "c12636c034be62e10c564217298564422a533b9c",
        "authorization": identity(DOCS / "coordinator/night_20261016/RESUME_R01/AUTHORIZATION_AND_DISPATCH.md"),
        "new_modelsim_version": "SE-64 2020.4", "normal_platform_escalation": "ALLOWED_IN_THIS_RESUME_BATCH",
        "functional_groups_consumed": 3, "remaining_functional_groups": 0, "preparation_only_run_count": 1,
        "runs": summaries, "capture_artifacts": raw_ids, "failed_prefix_inspection": identity(BASE / "FAILED_PREFIX_INSPECTION.json"),
        "successful_real_business_capture": False, "ready_generated": False, "boundary_generated": False,
        "initial_reset_explanation": "Earlier static hypothesis, not proved. Latest per-field raw evidence locates persistent observation clipped Z.",
        "snapshot_layout": "FLAT_RELATIVE_SHA_MAP_V1; see each executed receipt source_snapshot_files",
        "pending_fix": identity(BASE / "FIX03_PENDING.json"), "candidate_compile_level": "FIX02 compiled; FIX03 pending only L0",
        "real_per_request_deadline": "UNKNOWN", "serial_pcm_decode": "UNKNOWN", "analog_latency": "UNKNOWN_NOT_MEASURED",
        "board_release_allowed": False, "git_modified_by_this_window": False, "next_owner": "Night coordinator: stop A/C true consumption; M2 review; no further execution without new authorization",
        "startup_has_only_failed_prefix": True}
    write_new(BASE / "NIGHT_RUN_RECEIPT.json", receipt)
    write_new(BASE / "CAPTURE_BLOCKED.json", {"status": receipt["status"], "functional_groups_consumed": 3,
        "remaining": 0, "capture_ready": False, "successful_business_capture": False, "real_failed_prefix_retained": True,
        "receipt": identity(BASE / "NIGHT_RUN_RECEIPT.json"), "consumer_action": "Do not consume failure prefix as successful R05 capture"})
    print(json.dumps({"status": receipt["status"], "startup_rows": len(ticks), "input_rows": len(input_ticks), "unknown_fields": diagnostics,
        "receipt": identity(BASE / "NIGHT_RUN_RECEIPT.json")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
