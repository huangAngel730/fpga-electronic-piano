"""NOT_RUN cases for the additive R6-3 R7 profile intake candidate."""

from __future__ import annotations

import copy
import unittest

from intake_r07_fix_candidate import IntakeReject, analyze


def row(cycle: int, *, frame: int = 0, valid: int = 0, ready: int = 0,
        req_id: int | None = 0, result: int = 0, commit: int = 0,
        tx: int = 0, startup: int = 0, hold: int = 0,
        meta_valid: int = 1, id_valid: int = 1,
        raw_cancel: int = 0, finish: int = 0) -> dict:
    field_names = {
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
    fields = dict.fromkeys(field_names)
    fields.update({
        "cycle": cycle, "epoch": 0, "rst_n": 1, "frame_tick": frame,
        "req_valid": valid, "req_ready": ready, "req_id": req_id,
        "advance_mask": None, "advance_frame_req_id": None,
        "result_valid": result, "result_ready": result, "result_id": req_id,
        "commit": commit, "commit_id": req_id,
        "cancel": raw_cancel, "cancel_reason": None,
        "tx_sample_valid": tx, "tx_req_id": req_id if id_valid else None,
        "tx_left": 0, "tx_right": 0, "tx_clip": 0,
        "tx_hold": hold, "tx_startup_zero": startup,
        "finish": finish,
    })
    events = []
    if frame:
        events.append("FRAME_F")
    if valid and ready:
        events.append("ACCEPT_A")
    if result:
        events.append("RESULT_TRANSFER")
    if commit:
        events.append("COMMIT")
    if tx:
        events.append("TX_ADOPT")
    if finish:
        events.append("FINISH")
    return {
        "schema": "M3_R7A_PUBLIC_ROW_V1",
        "capture_id": "R63_R07_FIX_SYNTHETIC",
        "origin": "SYNTHETIC_SCHEMA_FIXTURE",
        "source": {"line": cycle + 1, "cycle": cycle, "epoch": 0,
                   "time_ps": cycle * 25_000,
                   "sampling_phase": "POSEDGE_PRE_NBA",
                   "raw_sha256": "1" * 64, "reset_edges_sha256": "2" * 64},
        "fields": fields,
        "extensions": {
            "schema": "M3_R7A_TX_EXTENSION_V1",
            "obs_core_clk": 1,
            "obs_polyphonic_valid": 1,
            "obs_tx_metadata_valid": meta_valid,
            "obs_tx_req_id_valid": id_valid,
            "obs_tx_clip_mask": 0,
            "obs_metadata_error": 0,
            "obs_frame_id_overflow": 0,
            "uart_tx": 1,
            "raw_tx_req_id_bits": req_id,
        },
        "missing_reasons": {},
        "events": events,
    }


def base_rows() -> list[dict]:
    return [
        row(0, frame=1),
        row(1, valid=1, ready=1, req_id=0),
        row(2, result=1, req_id=0),
        row(3, commit=1, req_id=0),
        row(4, tx=1, req_id=0),
        row(5, tx=1, req_id=0, hold=1, finish=1),
    ]


class R7FixCandidateTests(unittest.TestCase):
    def test_f_firstvalid_a_remain_distinct_and_id_zero_is_valid(self) -> None:
        report = analyze(base_rows())
        self.assertEqual(report["frames"][0]["F"]["cycle"], 0)
        self.assertEqual(report["frames"][0]["first_valid"]["cycle"], 1)
        self.assertEqual(report["frames"][0]["A"]["cycle"], 1)
        self.assertEqual(report["transactions"][0]["req_id"], 0)

    def test_hold_does_not_consume_pending_again(self) -> None:
        report = analyze(base_rows())
        self.assertTrue(report["tx_samples"][0]["consumes_pending"])
        self.assertFalse(report["tx_samples"][1]["consumes_pending"])
        self.assertEqual(report["tx_samples"][1]["kind"], "HOLD")
        self.assertEqual(report["transactions"][0]["state"], "ADOPTED_HELD")
        self.assertIn("TX_ADOPT", base_rows()[5]["events"])

    def test_startup_keeps_null_request_identity(self) -> None:
        rows = base_rows()
        rows[4] = row(4, tx=1, startup=1, id_valid=0, req_id=None)
        rows[5] = row(5, finish=1)
        report = analyze(rows)
        self.assertEqual(report["tx_samples"][0]["kind"], "STARTUP")
        self.assertIsNone(report["tx_samples"][0]["req_id"])
        self.assertEqual(report["transactions"][0]["state"],
                         "COMMITTED_PENDING_TX")
        self.assertIn("PENDING_TX_ADOPTION", report["pending_reasons"])
        self.assertIn("TX_ADOPT", rows[4]["events"])

    def test_invalid_metadata_hold_remains_sample_not_adoption(self) -> None:
        rows = base_rows()
        rows[5] = row(5, tx=1, hold=1, meta_valid=0, id_valid=0,
                      req_id=None, finish=1)
        rows[5]["extensions"]["raw_tx_req_id_bits"] = "0" * 26 + "101010"
        report = analyze(rows)
        self.assertEqual(report["tx_samples"][1]["kind"], "HOLD")
        self.assertFalse(report["tx_samples"][1]["consumes_pending"])
        self.assertIn("TX_ADOPT", rows[5]["events"])

    def test_reset_row_events_are_gated(self) -> None:
        rows = base_rows()
        rows[0]["fields"]["rst_n"] = 0
        rows[0]["events"] = []
        rows[0]["fields"]["frame_tick"] = 1
        with self.assertRaisesRegex(IntakeReject, "REQUEST_WITHOUT_FRAME"):
            analyze(rows)

    def test_raw_cancel_is_not_business_cancel(self) -> None:
        rows = base_rows()
        rows.insert(1, row(1, raw_cancel=1))
        for index, item in enumerate(rows):
            item["source"]["line"] = index + 1
            item["source"]["cycle"] = index
            item["source"]["time_ps"] = index * 25_000
            item["fields"]["cycle"] = index
        report = analyze(rows)
        self.assertEqual(len(report["raw_frame_cancels"]), 1)
        self.assertEqual(report["business_cancels"], [])

    def test_c3_profile_never_emits_lossy_d3(self) -> None:
        report = analyze(base_rows())
        self.assertEqual(report["legacy_d3_projection_status"],
                         "PENDING_UNSUPPORTED_PROFILE")
        self.assertEqual(report["legacy_d3_records"], [])

    def test_real_origin_requires_trusted_provenance(self) -> None:
        rows = copy.deepcopy(base_rows())
        for item in rows:
            item["origin"] = "HDL_PUBLIC_CAPTURE_UNVERIFIED"
        report = analyze(rows)
        self.assertIn("PENDING_SOURCE_PROVENANCE", report["pending_reasons"])
        self.assertFalse(report["real_pro_intake_pass"])

    def test_partial_r7_profile_is_rejected(self) -> None:
        rows = base_rows()
        del rows[0]["fields"]["pa_en"]
        with self.assertRaisesRegex(IntakeReject, "FIELD_PROFILE"):
            analyze(rows)


if __name__ == "__main__":
    unittest.main()
