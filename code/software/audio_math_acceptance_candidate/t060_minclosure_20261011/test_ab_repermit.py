"""Software-only tests for the locked T060 A/B re-permit preparation."""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock


HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from prepare_ab_repermit import (  # noqa: E402
    KEY_TOOLS,
    build_proposed_config,
    canonical_sha256,
    identity,
    load_json,
    pin_inventory,
    require_unredirected_root,
    validate_output_path,
)


class StrictJsonTests(unittest.TestCase):
    def test_duplicate_key_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "duplicate.json"
            path.write_text('{"x": 1, "x": 2}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "REPERMIT_DUPLICATE_KEY:x"):
                load_json(path)

    def test_nonfinite_number_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "nan.json"
            path.write_text('{"x": NaN}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "REPERMIT_NONFINITE:NaN"):
                load_json(path)


class IdentityInventoryTests(unittest.TestCase):
    def test_inventory_detects_match_change_and_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "same.bin").write_bytes(b"same")
            (root / "changed.bin").write_bytes(b"before")
            pins = {
                "same.bin": identity(root / "same.bin"),
                "changed.bin": identity(root / "changed.bin"),
                "missing.bin": {
                    "bytes": 1,
                    "sha256": "0" * 64,
                },
            }
            (root / "changed.bin").write_bytes(b"after")
            result = pin_inventory(pins, root)
            self.assertFalse(result["all_match"])
            self.assertEqual(result["observed_count"], 2)
            self.assertEqual(result["missing"], ["missing.bin"])
            self.assertEqual(result["changed"][0]["path"], "changed.bin")

    def test_canonical_digest_ignores_dictionary_order(self) -> None:
        self.assertEqual(
            canonical_sha256({"b": 2, "a": 1}),
            canonical_sha256({"a": 1, "b": 2}),
        )


class OutputScopeTests(unittest.TestCase):
    def test_redirected_code_output_root_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            lexical = root / "code/output"
            physical = root / "outside"
            lexical.mkdir(parents=True)
            physical.mkdir()
            with mock.patch.object(Path, "is_symlink", return_value=False):
                with self.assertRaisesRegex(
                    ValueError,
                    "REPERMIT_CODE_OUTPUT_REDIRECTED",
                ):
                    require_unredirected_root(lexical, physical)

    def test_repository_path_outside_code_output_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "code/output").mkdir(parents=True)
            with self.assertRaisesRegex(
                ValueError,
                "REPERMIT_OUTPUT_OUTSIDE_CODE_OUTPUT",
            ):
                validate_output_path(root / "code/rtl/new", root)

    def test_fresh_code_output_child_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "code/output").mkdir(parents=True)
            expected = (root / "code/output/new").resolve()
            actual_root, actual_output = validate_output_path(expected, root)
            self.assertEqual(actual_root, root.resolve())
            self.assertEqual(actual_output, expected)


class ProposalLockTests(unittest.TestCase):
    def test_proposal_remains_non_runnable_and_requires_new_approval(self) -> None:
        key_tb = (
            "code/tb/board/m3_midi_pcm_acceptance/"
            "t060_minclosure_20261011/tb_minclosure.sv"
        )
        key_observer = (
            "code/tb/board/m3_midi_pcm_acceptance/"
            "t060_minclosure_20261011/observer.svh"
        )
        fake_identity = {"bytes": 1, "sha256": "1" * 64}
        old = {
            "inputs": {
                "plan_A.json": fake_identity,
                "plan_B.json": fake_identity,
                "source_calendar.json": fake_identity,
                key_tb: fake_identity,
                key_observer: fake_identity,
                "future_group_A/stimulus_A.txt": fake_identity,
                "future_group_B/stimulus_B.txt": fake_identity,
            },
            "compile_sources": ["sources/a.sv"],
            "end_cycles": {"A": 4095000, "B": 1600},
            "mutations": {"A": [], "B": []},
            "tools": {
                "yosys": "yosys",
                "iverilog": "iverilog",
                "vvp": "vvp",
                "python": "python",
            },
            "tool_files": {
                name: {"bytes": 1, "sha256": sha256}
                for name, sha256 in KEY_TOOLS.items()
            },
        }
        predecessor = {
            "config": old,
            "input_inventory": {
                "expected_count": 177,
                "expected_manifest_sha256": "2" * 64,
            },
            "tool_inventory": {
                "expected_count": 621,
                "expected_manifest_sha256": "3" * 64,
            },
            "old_attempt": {
                "approval": fake_identity,
                "marker": fake_identity,
                "run_receipt": fake_identity,
            },
            "m2_compile_diagnostic": {
                "status": "PREPARED_NOT_EXECUTED",
                "blocks_AB_repermit_finalization": True,
            },
        }
        proposal = build_proposed_config(
            predecessor,
            {"computer_name": "LAPTOP-KSS1MRR7"},
        )
        self.assertFalse(proposal["execution_authorized"])
        self.assertFalse(proposal["direct_runner_compatible"])
        self.assertTrue(proposal["predecessor"]["reuse_forbidden"])
        self.assertIn("run residual A.vvp", proposal["forbidden"])
        self.assertEqual(
            proposal["frozen_workload"]["end_cycles"],
            {"A": 4095000, "B": 1600},
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
