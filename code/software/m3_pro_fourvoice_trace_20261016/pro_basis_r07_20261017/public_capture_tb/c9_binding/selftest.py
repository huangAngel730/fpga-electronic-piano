"""Unrun C9 successor cases. No import of candidate until run_case is called."""
import importlib.util
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[6]
TB = ROOT / "code/tb/board/m3_pro_fourvoice_trace_20261016/pro_basis_r07_20261017/public_capture_tb/c9_binding"
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_basis_r07_20261017/public_capture_tb"


def run_case(case_id, output_dir):
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=False)
    raw = (TB / "C9_SYNTHETIC.raw.jsonl").read_bytes()
    rows = [json.loads(line) for line in raw.decode().splitlines()]
    expected = None
    if case_id == "C9_RAW_XZ":
        rows[5]["ports"]["obs_effect_input_left"] = "x" * 24
    elif case_id == "C9_INVALID_CAUSE_CONTRADICTION":
        rows[2]["ports"]["obs_router_apply_seq_valid"] = "1"
        expected = "INVALID_CAUSE_SENTINEL_CONTRACT"
    elif case_id == "C9_WRONG_RAW_VERSION":
        rows[0]["schema"] = "M3_R7A_RAW_CORE_ROW_V1"
        expected = "C9_RAW_SCHEMA_REQUIRED"
    elif case_id == "C9_MISSING_CLIP":
        del rows[5]["ports"]["obs_feedback_clip_mask"]
        expected = "C9_RAW_PUBLIC_PORT_SET"
    elif case_id == "C9_CONFIG_WITHOUT_TAKE":
        rows[5]["ports"]["obs_config_take"] = "0"
    elif case_id not in ("C9_STAGE_SENTINELS_AND_SHARED_SEQ", "C9_THREE_CLIPS", "C9_LANE_TAG_NOT_FRAME"):
        raise ValueError("UNKNOWN_CASE")
    raw = ("\n".join(json.dumps(row) for row in rows) + "\n").encode()
    inputs = {"raw": raw, "resets": (TB / "C9_SYNTHETIC.resets.jsonl").read_bytes(),
              "end": (TB / "C9_SYNTHETIC.end.json").read_bytes(), "stdout": (TB / "C9_SYNTHETIC.stdout.txt").read_bytes()}
    for name, body in inputs.items():
        (out / (name + ".original")).write_bytes(body)
    port_map = json.loads((DOC / "c9_binding/PORT_MAP_C9.json").read_text(encoding="utf-8"))
    old_map = json.loads((DOC / "PORT_MAP.json").read_text(encoding="utf-8"))
    (out / "INPUT.json").write_text(json.dumps({"case": case_id, "expected_rejection": expected,
        "port_map": port_map, "old_map": old_map, "input_files": list(inputs)}, indent=2), encoding="utf-8", newline="\n")
    spec = importlib.util.spec_from_file_location("c9_capture_under_test", Path(__file__).with_name("c9_capture.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    try:
        actual, receipt = module.normalize(**inputs, port_map=port_map, old_map=old_map, origin="SYNTHETIC_SCHEMA_FIXTURE")
    except Exception as error:
        (out / "ACTUAL.json").write_text(json.dumps({"error": type(error).__name__, "reason": str(error)}), encoding="utf-8")
        if expected is None or str(error) != expected:
            raise
        return {"case": case_id, "expected_rejection_matched": expected, "real_pass": False}
    (out / "ACTUAL.json").write_text(json.dumps({"rows": actual, "receipt": receipt}, indent=2), encoding="utf-8")
    assert expected is None and len(actual) == 7 and all(len(row["fields"]) == 74 for row in actual)
    assert all(row["fields"]["apply_event_seq"] is None and row["fields"]["audio_stable"] is None for row in actual)
    if case_id == "C9_STAGE_SENTINELS_AND_SHARED_SEQ":
        assert actual[0]["fields"]["router_apply_seq"] == actual[1]["fields"]["router_apply_seq"] == 0
        assert [row["fields"]["apply_kind"] for row in actual[:5]] == [1, 2, 3, 4, 8]
        assert all("INVALID_CAUSE_SENTINEL" in row["semantics"]["apply_cause"] for row in actual[2:5])
    elif case_id == "C9_THREE_CLIPS":
        assert [actual[5]["fields"][key] for key in ("upstream_clip_mask", "effect_clip_mask", "feedback_clip_mask")] == [1, 2, 3]
    elif case_id == "C9_LANE_TAG_NOT_FRAME":
        assert actual[1]["fields"]["advance_mask"] == 15 and actual[1]["fields"]["advance_frame_req_id"] == 42
        assert actual[1]["fields"]["frame_tick"] == 0 and "FRAME_F" not in actual[1]["events"]
    elif case_id == "C9_RAW_XZ":
        assert actual[5]["fields"]["effect_input_left"] == "x" * 24
    elif case_id == "C9_CONFIG_WITHOUT_TAKE":
        assert actual[5]["semantics"]["config_on_actual_take"] is None
    return {"case": case_id, "synthetic_assertions_matched": True, "real_pass": False, "board_release_allowed": False}
