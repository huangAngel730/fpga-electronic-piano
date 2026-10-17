"""R08-SW-R NOT_RUN integration cases for unexecuted R6-3/R6-5 candidates."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
from typing import Any


HERE = Path(__file__).resolve().parent
BASIS = HERE.parent.parent
REPO = Path(__file__).resolve().parents[6]
R7_ROW_SCHEMA = "M3_R7A_PUBLIC_ROW_V1"
R7_EXTENSION_SCHEMA = "M3_R7A_TX_EXTENSION_V1"
R7_FIELDS = {
    "cycle", "epoch", "rst_n", "frame_tick", "event_valid", "event_ready",
    "event_data", "apply_valid", "apply_event_seq", "apply_data",
    "occupied_mask", "releasing_mask", "note_on_mask", "note_off_mask",
    "retire_mask", "slot_sources", "slot_channels", "slot_notes",
    "slot_generations", "req_valid", "req_ready", "req_id", "advance_mask",
    "advance_frame_req_id", "result_valid", "result_ready", "result_id",
    "result_left", "result_right", "result_clip_mask", "commit", "commit_id",
    "commit_left", "commit_right", "commit_clip", "cancel", "cancel_reason",
    "config_valid", "config_ready", "config_payload", "effect_input_valid",
    "effect_input_ready", "effect_input_id", "effect_input_left",
    "effect_input_right", "effect_input_clip_mask", "tx_sample_valid",
    "tx_frame_id", "tx_req_id", "tx_left", "tx_right", "tx_clip", "tx_hold",
    "tx_startup_zero", "bclk", "ws", "din", "pll_locked", "audio_stable",
    "pa_en", "finish",
}
R7_EXTENSIONS = {
    "schema", "obs_core_clk", "obs_polyphonic_valid",
    "obs_tx_metadata_valid", "obs_tx_req_id_valid", "obs_tx_clip_mask",
    "obs_metadata_error", "obs_frame_id_overflow", "uart_tx",
    "raw_tx_req_id_bits",
}


def _load(name: str, path: Path) -> Any:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"LOAD_SPEC:{path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _r63() -> Any:
    return _load("r08_r63_candidate",
                 BASIS / "normalized_intake/r07_fix/intake_r07_fix_candidate.py")


def _r65() -> Any:
    return _load("r08_r65_candidate",
                 BASIS / "event_calendar/r07_fix/calendar_r07_fix_candidate.py")


def _generator() -> Any:
    return _load("r08_frame_plan_generator",
                 BASIS / "event_calendar/frame_plan_generator_candidate.py")


def _row(mod: Any, cycle: int, **change: Any) -> dict[str, Any]:
    if (mod.ROW_SCHEMA != R7_ROW_SCHEMA
            or mod.EXTENSION_SCHEMA != R7_EXTENSION_SCHEMA
            or mod.EXPECTED_FIELD_NAMES != R7_FIELDS
            or mod.EXPECTED_EXTENSION_KEYS != R7_EXTENSIONS):
        raise AssertionError("R7_CONTRACT_CONSTANT_DRIFT")
    fields = dict.fromkeys(R7_FIELDS)
    fields.update({"cycle": cycle, "epoch": 0, "rst_n": 1, "frame_tick": 0,
                   "req_valid": 0, "req_ready": 0, "req_id": 0,
                   "advance_mask": 0, "advance_frame_req_id": 0,
                   "result_valid": 0, "result_ready": 0, "result_id": 0,
                   "commit": 0, "commit_id": 0, "cancel": 0,
                   "tx_sample_valid": 0, "tx_req_id": 0, "tx_left": 0,
                   "tx_right": 0, "tx_clip": 0, "tx_hold": 0,
                   "tx_startup_zero": 0, "finish": 0})
    fields.update(change.pop("fields", {}))
    ext = dict.fromkeys(R7_EXTENSIONS)
    ext.update({"schema": R7_EXTENSION_SCHEMA, "obs_core_clk": 1,
                "obs_polyphonic_valid": 1, "obs_tx_metadata_valid": 1,
                "obs_tx_req_id_valid": 1, "obs_tx_clip_mask": 0,
                "obs_metadata_error": 0, "obs_frame_id_overflow": 0,
                "uart_tx": 1, "raw_tx_req_id_bits": 0})
    ext.update(change.pop("extensions", {}))
    events = change.pop("events", [])
    row = {"schema": R7_ROW_SCHEMA, "capture_id": "r08-r",
           "origin": "SYNTHETIC_SCHEMA_FIXTURE",
           "source": {"raw_sha256": "1" * 64,
                      "reset_edges_sha256": "2" * 64, "line": cycle + 1,
                      "cycle": cycle, "epoch": 0, "time_ps": cycle * 25_000,
                      "sampling_phase": "POSEDGE_PRE_NBA"},
           "fields": fields, "extensions": ext, "missing_reasons": {},
           "events": events}
    row.update(change)
    return row


def _r63_rows(mod: Any) -> list[dict[str, Any]]:
    return [
        _row(mod, 0, fields={"frame_tick": 1}, events=["FRAME_F"]),
        _row(mod, 1, fields={"req_valid": 1, "req_ready": 1}, events=["ACCEPT_A"]),
        _row(mod, 2, fields={"result_valid": 1, "result_ready": 1}, events=["RESULT_TRANSFER"]),
        _row(mod, 3, fields={"commit": 1}, events=["COMMIT"]),
        _row(mod, 4, fields={"tx_sample_valid": 1}, events=["TX_ADOPT"]),
        _row(mod, 5, fields={"tx_sample_valid": 1, "tx_hold": 1, "finish": 1},
             events=["TX_ADOPT", "FINISH"]),
    ]


def _plan() -> dict[str, Any]:
    value = {"schema": "M3_R06_UNIQUE_FRAME_PLAN_V1",
             "formula": "n_k=ceil(128*k*2**32/659706977); cycle_k=release_cycle+n_k-1; k>=1",
             "rules_sha256": "3c968a151b0b5369f9dd95465761b2d87449c29975b1fca914f81fc5cfd01560",
             "input_sha256": "1" * 64,
             "source_identities": [{"path": "frozen.json", "sha256": "2" * 64}],
             "parameters": {"acc_bits": 32, "phase_step": 659706977,
                            "core_hz_candidate": 40000000,
                            "half_bclk_toggles_per_frame": 128,
                            "initial_state": {"accumulator": 0, "bclk": 0,
                                              "slot_count": 0}},
             "epochs": [{"epoch": 0, "window_kind": "ACTIVE",
                         "reset_assert_cycle": 0, "release_cycle": 0,
                         "stop_cycle": 1666, "cycles": [833, 1666]},
                        {"epoch": 1, "window_kind": "RESET_ONLY",
                         "reset_assert_cycle": 1667, "release_cycle": None,
                         "stop_cycle": 1668, "cycles": []}],
             "finish": {"epoch": 1, "cycle": 1668}}
    payload = {key: value[key] for key in ("schema", "formula", "rules_sha256",
               "input_sha256", "source_identities", "parameters", "epochs", "finish")}
    digest = hashlib.sha256((json.dumps(payload, sort_keys=True,
        separators=(",", ":")) + "\n").encode()).hexdigest()
    value.update(canonical_identity_sha256=digest,
                 canonical_plan_id=f"sha256:{digest}", independent_of_trace=True,
                 authority="CANDIDATE_INDEPENDENT_PLAN_NOT_M2_ADMITTED")
    return value


def _ledger() -> dict[str, Any]:
    return {"schema": "M3_R63_R07_INTAKE_REPORT_V1", "capture_id": "r08-r",
            "origin": "SYNTHETIC_SCHEMA_FIXTURE",
            "frames": [{"epoch": 0, "frame_ordinal": 1,
                        "F": {"cycle": 833}, "first_valid": {"cycle": 834},
                        "A": {"cycle": 834}, "req_id": 0,
                        "advance_observations": [{"cycle": 834, "mask": 15,
                                                  "req_id": 0}]},
                       {"epoch": 0, "frame_ordinal": 2,
                        "F": {"cycle": 1666}, "first_valid": None, "A": None,
                        "req_id": None, "advance_observations": []}],
            "transactions": [], "tx_samples": [], "raw_frame_cancels": [],
            "business_cancels": [], "pending_reasons": [],
            "legacy_d3_projection_status": "PENDING_UNSUPPORTED_PROFILE"}


def _expect_reject(call: Any, reason: str) -> dict[str, Any]:
    try:
        call()
    except Exception as exc:
        if reason not in str(exc):
            raise
        return {"status": "EXPECTED_REJECT", "reason": reason}
    raise AssertionError(f"EXPECTED_REJECT:{reason}")


def _run_r63(case_id: str) -> tuple[Any, Any]:
    mod, rows = _r63(), None
    rows = _r63_rows(mod)
    if case_id == "R63_ID_ZERO_VALID":
        report = mod.analyze(rows); assert report["transactions"][0]["req_id"] == 0
    elif case_id == "R63_STARTUP_NULL":
        rows[4] = _row(mod, 4, fields={"tx_sample_valid": 1, "tx_req_id": None,
                    "tx_startup_zero": 1}, extensions={"obs_tx_req_id_valid": 0,
                    "raw_tx_req_id_bits": 42}, events=["TX_ADOPT"])
        rows[5] = _row(mod, 5, fields={"finish": 1}, events=["FINISH"])
        report = mod.analyze(rows); assert report["tx_samples"][0]["req_id"] is None
    elif case_id == "R63_HOLD_NO_RECONSUME":
        report = mod.analyze(rows); assert report["tx_samples"][1]["consumes_pending"] is False
    elif case_id == "R63_RAW_CANCEL_FRAME_ONLY":
        rows[0]["fields"]["cancel"] = 1
        report = mod.analyze(rows); assert report["business_cancels"] == []
    elif case_id == "R63_F_A_DISTINCT":
        report = mod.analyze(rows); assert report["frames"][0]["F"]["cycle"] == 0 and report["frames"][0]["A"]["cycle"] == 1
    elif case_id == "R63_TX_EVENT_ON_HOLD":
        report = mod.analyze(rows); assert rows[5]["events"][0] == "TX_ADOPT" and report["tx_samples"][1]["kind"] == "HOLD"
    elif case_id == "R63_REAL_PENDING":
        for row in rows: row["origin"] = "HDL_PUBLIC_CAPTURE_UNVERIFIED"
        report = mod.analyze(rows); assert "PENDING_SOURCE_PROVENANCE" in report["pending_reasons"]
    elif case_id == "R63_PARTIAL_PROFILE_REJECT":
        del rows[0]["fields"]["pa_en"]
        report = _expect_reject(lambda: mod.analyze(rows), "FIELD_PROFILE")
    elif case_id == "R63_RESET_GATES_EVENTS":
        rows[0]["fields"]["rst_n"] = 0; rows[0]["events"] = []
        report = _expect_reject(lambda: mod.analyze(rows), "REQUEST_WITHOUT_FRAME")
    elif case_id == "R63_DUPLICATE_ADOPTION_REJECT":
        rows.insert(5, copy.deepcopy(rows[4]))
        for i, row in enumerate(rows):
            row["source"].update(line=i + 1, cycle=i, time_ps=i * 25_000); row["fields"]["cycle"] = i
        report = _expect_reject(lambda: mod.analyze(rows), "DUPLICATE_ADOPTION")
    elif case_id == "R63_PENDING_TX_ADOPTION":
        rows[4] = _row(mod, 4); rows[5] = _row(mod, 5, fields={"finish": 1}, events=["FINISH"])
        report = mod.analyze(rows); assert "PENDING_TX_ADOPTION" in report["pending_reasons"]
    elif case_id == "R63_SOURCE_AXIS_REJECT":
        rows[1]["source"]["cycle"] = 2
        report = _expect_reject(lambda: mod.analyze(rows), "SOURCE_SEQUENCE")
    else:
        raise KeyError(case_id)
    return rows, report


def _run_r65(case_id: str) -> tuple[Any, Any]:
    mod, plan, ledger = _r65(), _plan(), _ledger()
    if case_id == "R65_F_A_DISTINCT":
        report = mod.analyze(ledger, plan); assert report["frames"][0]["A"]["cycle"] == 834
    elif case_id == "R65_FULL_COVERAGE":
        report = mod.analyze(ledger, plan); assert len(report["frames"]) == 2
    elif case_id == "R65_FIRST_VALID_PENDING":
        report = mod.analyze(ledger, plan); assert "PENDING_FIRST_VALID" in report["pending_reasons"]
    elif case_id == "R65_ADVANCE_PENDING":
        ledger["frames"][0]["advance_observations"] = []
        report = mod.analyze(ledger, plan); assert "PENDING_M1_ADVANCE" in report["pending_reasons"]
    elif case_id == "R65_ADVANCE_POSITION_PRESERVED":
        ledger["frames"][0]["advance_observations"][0]["cycle"] = 835
        report = mod.analyze(ledger, plan); assert report["frames"][0]["advance"]["cycle"] == 835
    elif case_id == "R65_RESET_ONLY_EMPTY":
        report = mod.analyze(ledger, plan); assert all(x["epoch"] == 0 for x in report["frames"])
    elif case_id == "R65_LAST_FRAME_BOUND":
        ledger["frames"][1].update(first_valid={"cycle": 1667}, A={"cycle": 1667}, req_id=1)
        report = _expect_reject(lambda: mod.analyze(ledger, plan), "FIRST_VALID_OUTSIDE")
    elif case_id == "R65_WRONG_FORMULA_REJECT":
        plan["formula"] = "self-consistent alternate"
        report = _expect_reject(lambda: mod.analyze(ledger, plan), "FROZEN_RULES")
    elif case_id == "R65_REAL_PENDING":
        ledger["origin"] = "HDL_PUBLIC_CAPTURE_UNVERIFIED"
        report = mod.analyze(ledger, plan); assert "PENDING_SOURCE_PROVENANCE" in report["pending_reasons"]
    elif case_id == "R65_D3_REJECT":
        ledger["legacy_d3_projection_status"] = "PASS"
        report = _expect_reject(lambda: mod.analyze(ledger, plan), "LEGACY_D3")
    elif case_id == "R65_GLOBAL_CYCLE_ZERO":
        plan["epochs"] = [{"epoch": 0, "window_kind": "RESET_ONLY", "reset_assert_cycle": 0, "release_cycle": None, "stop_cycle": 0, "cycles": []}]
        plan["finish"] = {"epoch": 0, "cycle": 0}
        payload = {key: plan[key] for key in ("schema", "formula", "rules_sha256", "input_sha256", "source_identities", "parameters", "epochs", "finish")}
        digest = hashlib.sha256((json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n").encode()).hexdigest()
        plan["canonical_identity_sha256"] = digest; plan["canonical_plan_id"] = f"sha256:{digest}"; ledger["frames"] = []
        report = mod.analyze(ledger, plan); assert report["frames"] == []
    else:
        raise KeyError(case_id)
    return {"plan": plan, "ledger": ledger}, report


def _run_generator(case_id: str) -> tuple[Any, Any]:
    mod = _generator()
    rules_path = REPO / "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/r06_observer_20261017/FRAME_PLAN_RULES.json"
    rules_bytes = rules_path.read_bytes(); rules = json.loads(rules_bytes)
    value = {"schema": mod.INPUT_SCHEMA, "status": "FROZEN_INDEPENDENT_INPUT",
             "independent_of_observed_trace": True,
             "source_identities": [{"path": "source.json", "sha256": "1" * 64}],
             "epochs": [{"epoch": 0, "window_kind": "ACTIVE", "reset_assert_cycle": 0, "release_cycle": 0, "stop_cycle": 833}],
             "finish": {"epoch": 0, "cycle": 833}}
    if case_id == "GEN_RESET_ONLY_CYCLE_ZERO":
        value["epochs"] = [{"epoch": 0, "window_kind": "RESET_ONLY", "reset_assert_cycle": 0, "release_cycle": None, "stop_cycle": 0}]; value["finish"] = {"epoch": 0, "cycle": 0}
    elif case_id == "GEN_EPOCH_GAP_REJECT":
        value["epochs"].append({"epoch": 1, "window_kind": "RESET_ONLY", "reset_assert_cycle": 835, "release_cycle": None, "stop_cycle": 835}); value["finish"] = {"epoch": 1, "cycle": 835}
    elif case_id == "GEN_TRACE_INPUT_REJECT":
        value["trace_path"] = "observed.jsonl"
    elif case_id != "GEN_ACTIVE_CYCLE_ZERO":
        raise KeyError(case_id)
    call = lambda: mod.build_documents(value, rules,
        mod._sha256_bytes(mod._canonical_bytes(value)), mod._sha256_bytes(rules_bytes))
    if case_id == "GEN_EPOCH_GAP_REJECT": report = _expect_reject(call, "UNDECLARED_GAP")
    elif case_id == "GEN_TRACE_INPUT_REJECT": report = _expect_reject(call, "FORBIDDEN_OBSERVED_TRACE")
    else:
        report = call()
        assert report["canonical"]["epochs"][0]["reset_assert_cycle"] == 0
        expected_cycles = ([833] if case_id == "GEN_ACTIVE_CYCLE_ZERO" else [])
        assert report["canonical"]["epochs"][0]["cycles"] == expected_cycles
    return value, report


def run_case(case_id: str, output_dir: Path) -> dict:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=False)
    input_written = False
    if case_id.startswith("R63_"):
        source, report = _run_r63(case_id)
    elif case_id.startswith("R65_"):
        source, report = _run_r65(case_id)
    elif case_id.startswith("GEN_"):
        source, report = _run_generator(case_id)
    elif case_id == "CROSS_R63_LEDGER_TO_R65_ACTUAL_F_A":
        r63, r65, generator = _r63(), _r65(), _generator()
        rows = [_row(r63, cycle) for cycle in range(836)]
        rows[833]["fields"]["frame_tick"] = 1
        rows[833]["events"] = ["FRAME_F"]
        rows[834]["fields"].update(req_valid=1, req_ready=1,
                                    advance_mask=15, advance_frame_req_id=0)
        rows[834]["events"] = ["ACCEPT_A"]
        rows[835]["fields"]["finish"] = 1
        rows[835]["events"] = ["FINISH"]
        rules_path = REPO / (
            "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/"
            "r06_observer_20261017/FRAME_PLAN_RULES.json")
        rules_bytes = rules_path.read_bytes()
        rules = json.loads(rules_bytes)
        generator_input = {
            "schema": generator.INPUT_SCHEMA,
            "status": "FROZEN_INDEPENDENT_INPUT",
            "independent_of_observed_trace": True,
            "source_identities": [
                {"path": "r08-cross-independent-window.json",
                 "sha256": "3" * 64},
            ],
            "epochs": [
                {"epoch": 0, "window_kind": "ACTIVE",
                 "reset_assert_cycle": 0, "release_cycle": 0,
                 "stop_cycle": 835},
            ],
            "finish": {"epoch": 0, "cycle": 835},
        }
        (output_dir / "input.json").write_text(json.dumps(
            {"rows": rows, "generator_input": generator_input,
             "generator_output": None}, indent=2, default=str) + "\n",
            encoding="utf-8")
        (output_dir / "result.json").write_text(json.dumps(
            {"case_id": case_id, "status": "CALL_STARTED_NOT_COMPLETED"},
            indent=2) + "\n", encoding="utf-8")
        input_written = True
        generated = generator.build_documents(
            generator_input,
            rules,
            generator._sha256_bytes(generator._canonical_bytes(generator_input)),
            generator._sha256_bytes(rules_bytes),
        )
        plan = generated["canonical"]
        (output_dir / "input.json").write_text(json.dumps(
            {"rows": rows, "generator_input": generator_input,
             "generator_output": generated}, indent=2, default=str) + "\n",
            encoding="utf-8")
        ledger = r63.analyze(rows)
        calendar = r65.analyze(ledger, plan)
        assert calendar["frames"][0]["F"]["cycle"] == 833
        assert calendar["frames"][0]["A"]["cycle"] == 834
        source, report = {"rows": rows, "generator_input": generator_input,
                          "generator_output": generated}, calendar
    elif case_id == "CROSS_REAL_NEVER_PROMOTED":
        r63 = _r63(); rows = _r63_rows(r63)
        for row in rows: row["origin"] = "HDL_PUBLIC_CAPTURE_UNVERIFIED"
        ledger = r63.analyze(rows); assert ledger["real_pro_intake_pass"] is False
        source, report = rows, {"status": "PASS", "pending": ledger["pending_reasons"]}
    else:
        raise KeyError(case_id)
    if not input_written:
        (output_dir / "input.json").write_text(
            json.dumps(source, indent=2, default=str) + "\n", encoding="utf-8")
    (output_dir / "result.json").write_text(json.dumps(report, indent=2, default=str) + "\n", encoding="utf-8")
    return {"case_id": case_id, "status": "PASS"}
