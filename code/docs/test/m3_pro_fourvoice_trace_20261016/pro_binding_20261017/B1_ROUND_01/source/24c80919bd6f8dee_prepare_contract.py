"""Write the candidate observation contract and immutable source identities."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
DOC = ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_binding_20261017"
TB = ROOT / "code/tb/board/m3_pro_fourvoice_trace_20261016/pro_binding_20261017"


def identity(p):
    data = p.read_bytes()
    return {"path": str(p.resolve()), "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def save(p, obj):
    with p.open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(obj, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main():
    groups = {
        "time_reset": [("cycle", 64), ("epoch", 32), ("rst_n", 1), ("frame_tick", 1)],
        "event_input_apply": [("event_valid", 1), ("event_ready", 1), ("event_data", 64),
                              ("apply_valid", 1), ("apply_event_seq", 32), ("apply_data", 64)],
        "voice_lifecycle": [("occupied_mask", 4), ("releasing_mask", 4), ("note_on_mask", 4),
                            ("note_off_mask", 4), ("retire_mask", 4), ("slot_sources", 16),
                            ("slot_channels", 16), ("slot_notes", 32), ("slot_generations", 128)],
        "frame_request_advance": [("req_valid", 1), ("req_ready", 1), ("req_id", 32),
                                  ("advance_mask", 4), ("advance_frame_req_id", 32)],
        "result_commit": [("result_valid", 1), ("result_ready", 1), ("result_id", 32),
                          ("result_left", 24), ("result_right", 24), ("result_clip_mask", 2),
                          ("commit", 1), ("commit_id", 32), ("commit_left", 24),
                          ("commit_right", 24), ("commit_clip", 1)],
        "cancel": [("cancel", 1), ("cancel_reason", None)],
        "config_accept": [("config_valid", 1), ("config_ready", 1), ("config_payload", None)],
        "effect_audio_accept": [("effect_input_valid", 1), ("effect_input_ready", 1),
                                ("effect_input_id", 32), ("effect_input_left", 24),
                                ("effect_input_right", 24), ("effect_input_clip_mask", 2)],
        "tx_adoption_sidecar": [("tx_sample_valid", 1), ("tx_frame_id", 32), ("tx_req_id", 32),
                                ("tx_left", 24), ("tx_right", 24), ("tx_clip", 1),
                                ("tx_hold", 1), ("tx_startup_zero", 1)],
        "B2_pins_and_closure": [("bclk", 1), ("ws", 1), ("din", 1), ("pll_locked", 1),
                                ("audio_stable", 1), ("pa_en", 1), ("finish", 1)],
    }
    fields = [{"name": name, "width": width,
               "signed": name.endswith(("_left", "_right")), "group": group,
               "mapping_status": "M2_PUBLIC_MAP_REQUIRED"}
              for group, members in groups.items() for name, width in members]
    contract = {
        "schema": "M3_B1_MINIMAL_OBSERVATION_CONTRACT_V1", "status": "PENDING_PRO_SOURCE_OR_TRACE",
        "purpose": "Candidate normalized read-only observation contract, not production ports or an implementation",
        "clock_hz_candidate": 40000000, "nominal_sample_rate_hz_candidate": 48000,
        "sample_edge": "POSEDGE_PRE_NBA", "fields": fields,
        "frame_id_domain": "FRAME_REQUEST", "voice_slot_is_lane_id": False,
        "advance_modes": ["COMMON_TICK_MASK", "SCALAR_TICK_ONEHOT_PUBLIC_MAP"],
        "same_edge_common_tick": "Observed single shared enable advancing four real voices is represented once with mask1111 and frame req ID; never fabricate four staggered transactions",
        "epoch": "Derive only from same-clock observed reset-entry boundaries; initial reset is mandatory; no toy frame-derived epoch",
        "tx": "Independently observed TX-adoption sidecar at same cycle/epoch/frame; commit is not sample; ID0 valid; hold/startup metadata required",
        "completion": "Bound original raw stdout/stderr and successful capture receipt; unique MONITOR_END plus real finish/END; no truncated-success inference",
        "M2_confirmation_required": "All normalized widths/packed order, public export visibility, acceptance/apply/retirement priority and ID mapping are candidates until bound by M2 exact source",
        "forbidden_expectation_sources": ["DUT private wave/env/phase", "DUT result/commit as PCM golden", "Commit as TX sample", "Old toy or old PG484 labeled new Pro"],
        "pro_dut_pass": False, "board_release_allowed": False,
    }
    save(DOC / "OBSERVATION_CONTRACT.json", contract)
    inputs = [
        ROOT / "AGENTS.md", ROOT / "code/AGENTS.md", ROOT / "code/rtl/input/AGENTS.md",
        ROOT / "code/docs/协作入口.md", ROOT / "code/docs/138K四声部后续集成任务总览_2026-10-15.md",
        ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/C/CALENDAR_CONTRACT.json",
        ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/C/RESULT.md",
        ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/C/LATEST_RECEIPT.json",
        ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/D/FIXTURE_CONTRACT.md",
        ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/D/RESULT.md",
        ROOT / "code/software/m3_pro_fourvoice_trace_20261016/D/delta_audit.py",
        ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/D/pro_monitor_20261017/CONTRACT.md",
        ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/D/pro_monitor_20261017/RESULT.md",
        ROOT / "code/tb/board/m3_pro_fourvoice_trace_20261016/D/pro_monitor_20261017/pro_frame_monitor.sv",
        ROOT / "code/rtl/board/m2_fourvoice_timbre_delay_candidate_20261015/m2_fourvoice_timbre_delay_frame_core.sv",
        ROOT / "code/rtl/board/polyphonic_event_router.sv", ROOT / "code/rtl/board/polyphonic_envelope_bank.sv",
        ROOT / "code/docs/test/m3_pro_fourvoice_trace_20261016/pro_serial_successor_20261017/REQUIRED_PUBLIC_OBSERVATIONS.md",
    ]
    coord = DOC / "coordinator_20261017"
    inputs += [coord / x for x in ("DAY_PLAN.md", "USER_COMMUNICATION_AUTH.md")]
    inputs += list(Path("E:/FPGA/GAOYUNFPGA/night_task/10.17/task-day").glob("*.md"))
    target = DOC / "INPUT_ORIGINALS"
    target.mkdir(exist_ok=False)
    entries = []
    for p in inputs:
        item = identity(p)
        copy = target / (item["sha256"][:16] + "_" + p.name)
        if not copy.exists():
            shutil.copyfile(p, copy)
        assert identity(copy)["sha256"] == item["sha256"]
        entries.append({"original": item, "snapshot": identity(copy)})
    save(DOC / "INPUT_IDENTITIES.json", {"baseline_head": "414e1a9d3ee0617c5e8ba72dd4b22c36122c9926",
        "captured_utc": datetime.now(timezone.utc).isoformat(), "files": entries,
        "new_Pro_source_received": False, "actual_new_Pro_trace_received": False,
        "old_evidence_level_upgraded": False})
    TB.mkdir(parents=True, exist_ok=True)
    with (TB / "README.md").open("x", encoding="utf-8", newline="\n") as stream:
        stream.write("# B1只读观察接入占位说明\n\n未收到M2新Pro源与公开映射，没有可合法实例化的DUT，因此本轮不新增toy/TB/monitor RTL。最小观察合同在对应docs/test/pro_binding_20261017/OBSERVATION_CONTRACT.json；旧共同四路tick与scalar monitor的差额必须先固定，不伪造四个lane交易。此目录保留明确接入边界，不代表RTL已实现/仿真。\n")
    print(json.dumps({"contract": identity(DOC / "OBSERVATION_CONTRACT.json"), "fields": len(fields), "input_files": len(entries)}))


if __name__ == "__main__":
    main()
