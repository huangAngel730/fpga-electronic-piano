"""Software-only tests for the T052 P0-2 capture checker successor."""

from __future__ import annotations

import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

CHECKER_PATH = Path(__file__).resolve().with_name("checker.py")
CHECKER_SPEC = importlib.util.spec_from_file_location("t052_p0_2_checker", CHECKER_PATH)
checker = importlib.util.module_from_spec(CHECKER_SPEC)
CHECKER_SPEC.loader.exec_module(checker)


MANIFEST = (
    checker.ROOT
    / "code/docs/test/t052_publication_acceptance_20261012"
    / "CONTROL_PREPARATION_20261012/P0_1_DRIVER_20261013"
    / "combination_manifest.json"
)
MANIFEST_SHA = "0949f09747f517b08b36d6df78f8712111bb84f2da152b5a6969986532421b6c"
PLAN = (
    checker.ROOT
    / "code/docs/test/t052_publication_acceptance_20261012"
    / "M2_CONTROL_PLAN_20261012/controls_proposed.jsonl"
)
M2_ARCHIVE = (
    checker.ROOT
    / "code/docs/evidence/m2_ab_failure_t052_static_review_20261013"
    / "RAW_EVIDENCE.zip"
)
M2_ARCHIVE_SHA = "6a531fae9c846ad2098c26919cc063cac9df9e84f7ff89a18e4d4890c92ccf56"


def dump_jsonl(path: Path, rows: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


class CheckerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = checker.load_manifest(MANIFEST, MANIFEST_SHA)
        cls.expected = checker.expected_window(PLAN)

    def fresh_rows(self, fixture: bool = True) -> dict[str, list[dict]]:
        return {
            track: [checker.metadata(self.manifest, track, fixture)]
            + copy.deepcopy(self.expected[track])
            for track in checker.TRACKS
        }

    def write_rows(self, root: Path, rows: dict[str, list[dict]]) -> dict[str, Path]:
        paths = {}
        for track in checker.TRACKS:
            paths[track] = root / f"{track}.jsonl"
            dump_jsonl(paths[track], rows[track])
        return paths

    def assert_reject(self, diagnostic: str, function, *args, **kwargs) -> None:
        with self.assertRaisesRegex((ValueError, checker.UnknownEvidence), diagnostic):
            function(*args, **kwargs)

    def receipt_seam(self, root: Path, paths: dict[str, Path]) -> dict:
        """Build a temporary validator seam only; tests never accept this as RTL."""
        empty = root / "empty.log"
        empty.write_bytes(b"")
        empty_spec = {"path": str(empty), **checker.identity(empty)}
        sources = {
            role: {key: item[key] for key in ("bytes", "sha256")}
            for role, item in self.manifest["sources"].items()
        }
        tools = {
            role: {key: item[key] for key in ("bytes", "sha256")}
            for role, item in self.manifest["tools"].items()
        }
        return {
            "schema": "T052_PUBLIC_PORT_RUN_RECEIPT_V2",
            "evidence_kind": "RTL_RUN",
            "approval_sha256": "a" * 64,
            "manifest_sha256": MANIFEST_SHA,
            "machine": "VALIDATOR_SEAM_NOT_EXECUTED",
            "status": "PASS",
            "exit_code": 0,
            "timeout": False,
            "source_snapshots": copy.deepcopy(self.manifest["sources"]),
            "tools_before": tools,
            "tools_after": copy.deepcopy(tools),
            "sources_before": sources,
            "sources_after": copy.deepcopy(sources),
            "compile": {
                "argv": copy.deepcopy(self.manifest["compile_argv"]),
                "cwd": str(root.resolve()),
                "exit_code": 0,
                "timeout": False,
                "stdout": copy.deepcopy(empty_spec),
                "stderr": copy.deepcopy(empty_spec),
                "executable": copy.deepcopy(self.manifest["tools"]["compile"]),
            },
            "run": {
                "argv": copy.deepcopy(self.manifest["run_argv"]),
                "cwd": str(root.resolve()),
                "exit_code": 0,
                "timeout": False,
                "stdout": copy.deepcopy(empty_spec),
                "stderr": copy.deepcopy(empty_spec),
                "executable": copy.deepcopy(self.manifest["tools"]["runtime"]),
            },
            "artifacts": {
                role: {"path": str(path), **checker.identity(path)}
                for role, path in paths.items()
            },
        }

    def validate_mutated_receipt(self, mutation, diagnostic: str) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            paths = self.write_rows(root, self.fresh_rows(fixture=False))
            receipt = self.receipt_seam(root, paths)
            mutation(receipt)
            receipt_path = root / "receipt.json"
            receipt_path.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
            self.assert_reject(
                diagnostic, checker.validate_run_receipt,
                receipt_path, checker.identity(receipt_path)["sha256"], "a" * 64,
                MANIFEST, self.manifest, paths,
            )

    def test_01_independent_calendar_is_six_three_three(self) -> None:
        ledger = self.expected["publications"][-1]
        self.assertEqual(
            ledger,
            {"type": "END", "accepted": 6, "published": 3,
             "cancelled": 3, "open": 0},
        )
        self.assertEqual(len(self.expected["observations"]), 129)

    def test_02_complete_software_fixture_passes_without_rtl_claim(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            paths = self.write_rows(Path(name), self.fresh_rows())
            result = checker.check(
                MANIFEST, MANIFEST_SHA, PLAN, paths, fixture=True
            )
        self.assertEqual(result["status"], "SOFTWARE_FIXTURE_PASS")
        self.assertFalse(result["RTL_verified"])
        self.assertFalse(result["T052_complete"])

    def test_03_all_ready_valid_zero_complete_trace_is_rejected(self) -> None:
        rows = self.fresh_rows()
        for row in rows["observations"][1:-1]:
            row.update(calc_ready=0, result_valid=0, result_req_id=0)
        rows["publications"] = [
            rows["publications"][0],
            {"type": "END", "accepted": 0, "published": 0,
             "cancelled": 0, "open": 0},
        ]
        self.assert_reject(
            "SOURCE_CALENDAR_PINS",
            checker.validate_rows, rows, self.expected, self.manifest, True,
        )

    def test_04_forged_source_sha_complete_trace_is_rejected(self) -> None:
        rows = self.fresh_rows()
        rows["controls"][0]["observer_sha256"] = "0" * 64
        self.assert_reject(
            "SOURCE_META:controls",
            checker.validate_rows, rows, self.expected, self.manifest, True,
        )

    def test_05_software_origin_cannot_impersonate_actual(self) -> None:
        rows = self.fresh_rows(fixture=True)
        self.assert_reject(
            "SOURCE_META:controls",
            checker.validate_rows, rows, self.expected, self.manifest, False,
        )

    def test_06_actual_origin_cannot_impersonate_software_fixture(self) -> None:
        rows = self.fresh_rows(fixture=False)
        self.assert_reject(
            "SOURCE_META:controls",
            checker.validate_rows, rows, self.expected, self.manifest, True,
        )

    def test_07_actual_mode_requires_externally_pinned_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            paths = self.write_rows(Path(name), self.fresh_rows(fixture=False))
            self.assert_reject(
                "ACTUAL_RUN_RECEIPT_REQUIRED", checker.check,
                MANIFEST, MANIFEST_SHA, PLAN, paths, False,
            )

    def test_08_software_receipt_cannot_qualify_actual_mode(self) -> None:
        with tempfile.TemporaryDirectory() as name:
            root = Path(name)
            paths = self.write_rows(root, self.fresh_rows(fixture=False))
            receipt = root / "software_receipt.json"
            receipt.write_text(json.dumps({
                "schema": "T052_PUBLIC_PORT_RUN_RECEIPT_V2",
                "evidence_kind": "SOFTWARE_FIXTURE",
                "approval_sha256": "a" * 64,
                "manifest_sha256": MANIFEST_SHA,
                "machine": "SOFTWARE_ONLY",
                "status": "FAIL",
                "exit_code": 1,
                "timeout": False,
                "source_snapshots": {},
                "tools_before": {},
                "tools_after": {},
                "sources_before": {},
                "sources_after": {},
                "compile": {},
                "run": {},
                "artifacts": {},
            }, sort_keys=True), encoding="utf-8")
            receipt_sha = checker.identity(receipt)["sha256"]
            self.assert_reject(
                "RUN_RECEIPT_IDENTITY", checker.check,
                MANIFEST, MANIFEST_SHA, PLAN, paths, False,
                receipt, receipt_sha, "a" * 64,
            )

    def test_09_manifest_requires_external_sha_pin(self) -> None:
        self.assert_reject(
            "MANIFEST_EXTERNAL_PIN", checker.load_manifest,
            MANIFEST, "0" * 64,
        )

    def test_10_meta_integer_type_is_strict(self) -> None:
        rows = self.fresh_rows()
        rows["controls"][0]["clock_period_ns"] = 20.0
        self.assert_reject(
            "SOURCE_META:controls",
            checker.validate_rows, rows, self.expected, self.manifest, True,
        )

    def test_11_end_integer_types_are_strict(self) -> None:
        for field in ("accepted", "published", "cancelled", "open"):
            for bad in (False, 0.0):
                with self.subTest(field=field, bad=bad):
                    rows = self.fresh_rows()
                    rows["publications"][-1][field] = bad
                    self.assert_reject(
                        "END_INTEGER:" + field,
                        checker.validate_rows, rows, self.expected,
                        self.manifest, True,
                    )

    def test_12_control_time_is_integer_and_exact(self) -> None:
        rows = self.fresh_rows()
        rows["controls"][1]["time"] += 1
        self.assert_reject(
            "CONTROL_PLAN_TIME:0",
            checker.validate_rows, rows, self.expected, self.manifest, True,
        )

    def test_13_reset_time_is_integer_and_exact(self) -> None:
        rows = self.fresh_rows()
        rows["resets"][1]["time"] += 1
        self.assert_reject(
            "RESET_EDGE_COVERAGE:0",
            checker.validate_rows, rows, self.expected, self.manifest, True,
        )

    def test_14_open_window_stays_unknown(self) -> None:
        rows = self.fresh_rows()
        rows["publications"][-1]["open"] = 1
        with self.assertRaisesRegex(checker.UnknownEvidence, "OPEN_REQUEST_AT_END"):
            checker.validate_rows(rows, self.expected, self.manifest, True)

    def test_15_truncated_window_stays_unknown(self) -> None:
        rows = self.fresh_rows()
        rows["observations"].pop(-2)
        with self.assertRaisesRegex(checker.UnknownEvidence, "INCOMPLETE_WINDOW"):
            checker.validate_rows(rows, self.expected, self.manifest, True)

    def test_16_duplicate_json_key_is_rejected(self) -> None:
        self.assert_reject(
            "DUPLICATE_JSON_KEY", checker.decode, '{"type":"A","type":"B"}',
        )

    def test_17_m2_all_zero_complete_counterexample_is_rejected(self) -> None:
        self.assertEqual(hashlib.sha256(M2_ARCHIVE.read_bytes()).hexdigest(),
                         M2_ARCHIVE_SHA)
        root = "T052_complete_software_probes/suppress_all_public_accepts/"
        with zipfile.ZipFile(M2_ARCHIVE) as archive:
            rows = {
                track: [checker.decode(line) for line in
                        archive.read(root + track + ".jsonl").decode("utf-8").splitlines()]
                for track in checker.TRACKS
            }
        self.assert_reject(
            "SOURCE_META:controls",
            checker.validate_rows, rows, self.expected, self.manifest, False,
        )

    def test_18_m2_forged_sha_complete_counterexample_is_rejected(self) -> None:
        root = "T052_complete_software_probes/forged_source_labels/"
        with zipfile.ZipFile(M2_ARCHIVE) as archive:
            rows = {
                track: [checker.decode(line) for line in
                        archive.read(root + track + ".jsonl").decode("utf-8").splitlines()]
                for track in checker.TRACKS
            }
        self.assert_reject(
            "SOURCE_META:controls",
            checker.validate_rows, rows, self.expected, self.manifest, False,
        )

    def test_19_receipt_source_before_after_binding(self) -> None:
        self.validate_mutated_receipt(
            lambda row: row["sources_after"]["dut"].update(sha256="0" * 64),
            "RUN_SOURCE_BEFORE_AFTER",
        )

    def test_20_receipt_snapshot_role_binding(self) -> None:
        self.validate_mutated_receipt(
            lambda row: row["source_snapshots"].pop("dut"),
            "RUN_SOURCE_SNAPSHOTS",
        )

    def test_21_receipt_compile_argv_binding(self) -> None:
        self.validate_mutated_receipt(
            lambda row: row["compile"]["argv"].append("--forged"),
            "STEP_RESULT:compile",
        )

    def test_22_receipt_tool_binding(self) -> None:
        self.validate_mutated_receipt(
            lambda row: row["compile"].update(
                executable=copy.deepcopy(self.manifest["tools"]["runtime"])
            ),
            "STEP_TOOL:compile",
        )

    def test_23_receipt_log_identity_binding(self) -> None:
        def mutate(row):
            row["compile"]["stdout"]["sha256"] = "0" * 64
        self.validate_mutated_receipt(mutate, "FILE_IDENTITY:")

    def test_24_receipt_artifact_identity_binding(self) -> None:
        def mutate(row):
            row["artifacts"]["controls"]["sha256"] = "0" * 64
        self.validate_mutated_receipt(mutate, "FILE_IDENTITY:")


if __name__ == "__main__":
    unittest.main(verbosity=2)
