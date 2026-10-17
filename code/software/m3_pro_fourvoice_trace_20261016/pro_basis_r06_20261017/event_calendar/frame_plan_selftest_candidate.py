"""NOT_RUN self-test candidate for frame_plan_generator_candidate.py.

Execution/import/compilation is forbidden until M2 grants a new incremental
R6-5 software admission.  The cases below are reviewable test intent only.
"""

from __future__ import annotations

import copy
import json
import tempfile
import unittest
from pathlib import Path

import frame_plan_generator_candidate as generator


RULES_PATH = Path(
    "code/docs/test/m2_138k_pro_fourvoice_candidate_20261016/"
    "r06_observer_20261017/FRAME_PLAN_RULES.json"
)


def candidate_input() -> dict:
    return {
        "schema": generator.INPUT_SCHEMA,
        "status": "FROZEN_INDEPENDENT_INPUT",
        "independent_of_observed_trace": True,
        "source_identities": [{"path": "frozen-source-list.json",
                               "sha256": "1" * 64}],
        "epochs": [
            {"epoch": 0, "window_kind": "ACTIVE", "reset_assert_cycle": 1,
             "release_cycle": 7, "stop_cycle": 3799},
            {"epoch": 1, "window_kind": "ACTIVE", "reset_assert_cycle": 3800,
             "release_cycle": 3806, "stop_cycle": 7589},
            {"epoch": 2, "window_kind": "RESET_ONLY",
             "reset_assert_cycle": 7590, "release_cycle": None,
             "stop_cycle": 7600},
        ],
        "finish": {"epoch": 2, "cycle": 7600},
    }


class FramePlanCandidateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.rules_bytes = RULES_PATH.read_bytes()
        self.rules = json.loads(self.rules_bytes.decode("utf-8"))

    def build(self, value: dict | None = None) -> dict:
        document = candidate_input() if value is None else value
        input_bytes = generator._canonical_bytes(document)
        return generator.build_documents(
            document,
            self.rules,
            generator._sha256_bytes(input_bytes),
            generator._sha256_bytes(self.rules_bytes),
        )

    def test_first_edges_and_reset_restart(self) -> None:
        docs = self.build()
        epochs = docs["canonical"]["epochs"]
        self.assertEqual(epochs[0]["cycles"][:4], [840, 1673, 2506, 3340])
        self.assertEqual(epochs[1]["cycles"][:4], [4639, 5472, 6305, 7139])
        self.assertEqual(epochs[2]["cycles"], [])
        self.assertIsNone(epochs[2]["release_cycle"])

    def test_active_global_cycle_zero_is_valid(self) -> None:
        value = candidate_input()
        value["epochs"] = [
            {"epoch": 0, "window_kind": "ACTIVE", "reset_assert_cycle": 0,
             "release_cycle": 0, "stop_cycle": 833},
        ]
        value["finish"] = {"epoch": 0, "cycle": 833}
        epochs = self.build(value)["canonical"]["epochs"]
        self.assertEqual(epochs[0]["cycles"], [833])

    def test_reset_only_cycle_zero_is_valid(self) -> None:
        value = candidate_input()
        value["epochs"] = [
            {"epoch": 0, "window_kind": "RESET_ONLY",
             "reset_assert_cycle": 0, "release_cycle": None, "stop_cycle": 0},
        ]
        value["finish"] = {"epoch": 0, "cycle": 0}
        epochs = self.build(value)["canonical"]["epochs"]
        self.assertEqual(epochs[0]["cycles"], [])

    def test_both_legacy_views_are_one_identity(self) -> None:
        docs = self.build()
        calendar = docs["event_calendar_projection"]
        tx = docs["tx_checker_projection"]
        self.assertEqual(calendar["canonical_plan_id"], tx["canonical_plan_id"])
        self.assertEqual(
            [item["frame_cycles"] for item in calendar["epochs"]],
            [item["cycles"] for item in tx["epochs"]],
        )

    def test_observed_trace_input_is_rejected(self) -> None:
        value = candidate_input()
        value["trace_path"] = "capture.jsonl"
        with self.assertRaisesRegex(generator.PlanInputError,
                                    "FORBIDDEN_OBSERVED_TRACE_INPUT"):
            self.build(value)

    def test_unfrozen_input_is_rejected(self) -> None:
        value = candidate_input()
        value["status"] = "DRAFT"
        with self.assertRaisesRegex(generator.PlanInputError,
                                    "INPUT_NOT_FROZEN"):
            self.build(value)

    def test_non_hex_source_identity_is_rejected(self) -> None:
        value = candidate_input()
        value["source_identities"][0]["sha256"] = "z" * 64
        with self.assertRaisesRegex(generator.PlanInputError,
                                    "SOURCE_IDENTITY_0_SHA256"):
            self.build(value)

    def test_finish_must_equal_last_stop(self) -> None:
        value = candidate_input()
        value["finish"]["cycle"] -= 1
        with self.assertRaisesRegex(generator.PlanInputError,
                                    "FINISH_NOT_LAST_STOP"):
            self.build(value)

    def test_file_entry_refuses_existing_output(self) -> None:
        with tempfile.TemporaryDirectory() as root:
            directory = Path(root)
            input_path = directory / "input.json"
            input_path.write_text(json.dumps(candidate_input()), encoding="utf-8")
            output = directory / "existing"
            output.mkdir()
            with self.assertRaises(FileExistsError):
                generator.generate(input_path, RULES_PATH, output)

    def test_window_overlap_is_rejected(self) -> None:
        value = copy.deepcopy(candidate_input())
        value["epochs"][1]["reset_assert_cycle"] = 3799
        with self.assertRaisesRegex(generator.PlanInputError,
                                    "EPOCH_1_UNDECLARED_GAP_OR_OVERLAP"):
            self.build(value)

    def test_window_gap_is_rejected(self) -> None:
        value = copy.deepcopy(candidate_input())
        value["epochs"][0]["stop_cycle"] = 840
        with self.assertRaisesRegex(generator.PlanInputError,
                                    "EPOCH_1_UNDECLARED_GAP_OR_OVERLAP"):
            self.build(value)

    def test_reset_only_epoch_cannot_invent_release(self) -> None:
        value = copy.deepcopy(candidate_input())
        value["epochs"][2]["release_cycle"] = 7601
        with self.assertRaisesRegex(generator.PlanInputError,
                                    "EPOCH_2_RESET_ONLY_RELEASE"):
            self.build(value)


if __name__ == "__main__":
    unittest.main()
