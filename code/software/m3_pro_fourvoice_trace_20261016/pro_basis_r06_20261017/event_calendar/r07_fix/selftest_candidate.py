"""NOT_RUN cases for the additive R6-5 R7 calendar candidate."""

from __future__ import annotations

import copy
import hashlib
import json
import unittest

from calendar_r07_fix_candidate import CalendarReject, analyze


def plan() -> dict:
    document = {
        "schema": "M3_R06_UNIQUE_FRAME_PLAN_V1",
        "formula": "n_k=ceil(128*k*2**32/659706977); cycle_k=release_cycle+n_k-1; k>=1",
        "rules_sha256": "3c968a151b0b5369f9dd95465761b2d87449c29975b1fca914f81fc5cfd01560",
        "input_sha256": "1" * 64,
        "source_identities": [{"path": "frozen.json", "sha256": "2" * 64}],
        "parameters": {
            "acc_bits": 32,
            "phase_step": 659706977,
            "core_hz_candidate": 40000000,
            "half_bclk_toggles_per_frame": 128,
            "initial_state": {"accumulator": 0, "bclk": 0, "slot_count": 0},
        },
        "epochs": [
            {"epoch": 0, "window_kind": "ACTIVE", "reset_assert_cycle": 1,
             "release_cycle": 1, "stop_cycle": 1667, "cycles": [834, 1667]},
            {"epoch": 1, "window_kind": "RESET_ONLY", "reset_assert_cycle": 1668,
             "release_cycle": None, "stop_cycle": 1670, "cycles": []},
        ],
        "finish": {"epoch": 1, "cycle": 1670},
    }
    payload = {key: document[key] for key in (
        "schema", "formula", "rules_sha256", "input_sha256",
        "source_identities", "parameters", "epochs", "finish",
    )}
    digest = hashlib.sha256((json.dumps(payload, sort_keys=True,
        separators=(",", ":")) + "\n").encode()).hexdigest()
    document.update({
        "canonical_identity_sha256": digest,
        "canonical_plan_id": f"sha256:{digest}",
        "authority": "CANDIDATE_INDEPENDENT_PLAN_NOT_M2_ADMITTED",
        "independent_of_trace": True,
        "real_authority_claimed": False,
    })
    return document


def ledger() -> dict:
    return {
        "schema": "M3_R63_R07_INTAKE_REPORT_V1",
        "capture_id": "R65_R07_FIX_SYNTHETIC",
        "origin": "SYNTHETIC_SCHEMA_FIXTURE",
        "frames": [
            {"epoch": 0, "frame_ordinal": 1,
             "F": {"cycle": 834, "source_line": 835},
             "first_valid": {"cycle": 835, "source_line": 836},
             "A": {"cycle": 835, "source_line": 836}, "req_id": 0,
             "advance_observations": [{"cycle": 835, "source_line": 836,
                                       "mask": 15, "req_id": 0}]},
            {"epoch": 0, "frame_ordinal": 2,
             "F": {"cycle": 1667, "source_line": 1668},
             "first_valid": None, "A": None, "req_id": None,
             "advance_observations": []},
        ],
        "transactions": [], "tx_samples": [], "raw_frame_cancels": [],
        "business_cancels": [],
        "business_cancel_status": "PENDING_TRANSACTION_CANCEL_RULE",
        "legacy_d3_projection_status": "PENDING_UNSUPPORTED_PROFILE",
        "pending_reasons": [],
    }


class R7CalendarCandidateTests(unittest.TestCase):
    def test_f_and_a_can_be_distinct(self) -> None:
        report = analyze(ledger(), plan())
        self.assertEqual(report["frames"][0]["F"]["cycle"], 834)
        self.assertEqual(report["frames"][0]["A"]["cycle"], 835)

    def test_missing_same_edge_request_is_not_rejected(self) -> None:
        report = analyze(ledger(), plan())
        self.assertIn("PENDING_FIRST_VALID", report["pending_reasons"])

    def test_full_frame_window_is_required(self) -> None:
        value = ledger()
        value["frames"].pop()
        with self.assertRaisesRegex(CalendarReject, "FRAME_COVERAGE"):
            analyze(value, plan())

    def test_reset_only_tail_has_no_fabricated_frame(self) -> None:
        report = analyze(ledger(), plan())
        self.assertFalse(any(item["epoch"] == 1 for item in report["frames"]))

    def test_reset_only_global_cycle_zero_is_valid(self) -> None:
        value = plan()
        value["epochs"] = [
            {"epoch": 0, "window_kind": "RESET_ONLY",
             "reset_assert_cycle": 0, "release_cycle": None,
             "stop_cycle": 0, "cycles": []},
        ]
        value["finish"] = {"epoch": 0, "cycle": 0}
        payload = {key: value[key] for key in (
            "schema", "formula", "rules_sha256", "input_sha256",
            "source_identities", "parameters", "epochs", "finish",
        )}
        digest = hashlib.sha256((json.dumps(payload, sort_keys=True,
            separators=(",", ":")) + "\n").encode()).hexdigest()
        value["canonical_identity_sha256"] = digest
        value["canonical_plan_id"] = f"sha256:{digest}"
        empty = ledger()
        empty["frames"] = []
        report = analyze(empty, value)
        self.assertEqual(report["frames"], [])

    def test_last_frame_window_ends_at_epoch_stop(self) -> None:
        value = ledger()
        value["frames"][1].update({
            "first_valid": {"cycle": 1668, "source_line": 1669},
            "A": {"cycle": 1668, "source_line": 1669},
            "req_id": 1,
            "advance_observations": [
                {"cycle": 1668, "source_line": 1669, "mask": 15, "req_id": 1}
            ],
        })
        with self.assertRaisesRegex(CalendarReject,
                                    "FIRST_VALID_OUTSIDE_FRAME_WINDOW"):
            analyze(value, plan())

    def test_missing_real_advance_remains_pending(self) -> None:
        value = ledger()
        value["frames"][0]["advance_observations"] = []
        report = analyze(value, plan())
        self.assertIn("PENDING_M1_ADVANCE", report["pending_reasons"])

    def test_advance_is_never_invented_at_a_plus_one(self) -> None:
        value = ledger()
        value["frames"][0]["advance_observations"][0]["cycle"] = 836
        report = analyze(value, plan())
        self.assertEqual(report["frames"][0]["advance"]["cycle"], 836)

    def test_real_origin_is_pending_source_provenance(self) -> None:
        value = ledger()
        value["origin"] = "HDL_PUBLIC_CAPTURE_UNVERIFIED"
        report = analyze(value, plan())
        self.assertIn("PENDING_SOURCE_PROVENANCE", report["pending_reasons"])

    def test_legacy_profile_cannot_be_promoted(self) -> None:
        value = ledger()
        value["legacy_d3_projection_status"] = "PASS"
        with self.assertRaisesRegex(CalendarReject, "LEGACY_D3"):
            analyze(value, plan())

    def test_alternate_self_consistent_formula_is_rejected(self) -> None:
        value = plan()
        value["formula"] = "different formula"
        with self.assertRaisesRegex(CalendarReject, "FROZEN_RULES"):
            analyze(ledger(), value)


if __name__ == "__main__":
    unittest.main()
